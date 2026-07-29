"""
Supabase persistence (Commit 9) — long-term memory for finished missions.

Stores the mission, its sources, and the final report with a vector embedding
so a user can ask follow-up questions against past research later.

Entirely optional: without SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY this is a
no-op and every call returns cleanly. A storage failure must never lose a
mission the user already watched complete — the result has been delivered over
the WebSocket by the time we get here.
"""
import os
import asyncio
import logging
from typing import Any, Dict, List, Optional

log = logging.getLogger("aletheia.supabase")

EMBED_MODEL = os.getenv("GEMINI_EMBED_MODEL", "gemini-embedding-001")
EMBED_DIM = 768

_client = None
_checked = False
_disabled_reason: Optional[str] = None


def _get_client():
    """Lazily build the Supabase client; returns None when not configured."""
    global _client, _checked, _disabled_reason

    if _checked:
        return _client
    _checked = True

    url = os.getenv("SUPABASE_URL")
    # Newer Supabase projects issue `sb_secret_…` keys and label them "secret"
    # rather than "service_role". Accept either name so the value people
    # actually see in the dashboard drops straight in.
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SECRET_KEY")
    if not url or not key:
        _disabled_reason = (
            "SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_SECRET_KEY) not "
            "set — missions are not persisted. Add them to backend/.env to enable "
            "long-term memory."
        )
        log.info("Supabase persistence disabled: %s", _disabled_reason)
        return None

    try:
        from supabase import create_client
        _client = create_client(url, key)
        log.info("Supabase persistence enabled.")
    except Exception as e:
        _disabled_reason = f"Supabase client failed to initialise: {e}"
        log.warning(_disabled_reason)
        _client = None

    return _client


def is_enabled() -> bool:
    return _get_client() is not None


def disabled_reason() -> Optional[str]:
    _get_client()
    return _disabled_reason


async def _embed(text: str) -> Optional[List[float]]:
    """Embed the report so follow-up questions can find it semantically."""
    try:
        from services.llm import get_client
        client = get_client()
        response = await client.aio.models.embed_content(
            model=EMBED_MODEL,
            contents=text[:8000],
            config={"output_dimensionality": EMBED_DIM},
        )
        embeddings = getattr(response, "embeddings", None)
        if not embeddings:
            return None
        return list(embeddings[0].values)
    except Exception as e:
        log.info("Embedding unavailable (report stored without one): %s", str(e)[:160])
        return None


async def save_mission(
    session_id: str,
    query: str,
    user_id: Optional[str],
    sources: List[Dict[str, Any]],
    claims: List[Dict[str, Any]],
    ui: str,
    ui_data: Dict[str, Any],
    narrative: str,
    contradictions: List[Dict[str, Any]],
) -> None:
    """Persist a completed mission. Never raises."""
    client = _get_client()
    if client is None:
        return

    try:
        embedding = await _embed(f"{query}\n\n{narrative}\n\n" + "\n".join(
            c.get("text", "") for c in claims
        ))

        # supabase-py is synchronous; keep it off the event loop.
        def _write() -> None:
            mission = {
                "id": session_id,
                "query": query,
                "title": query[:120],
                "status": "complete",
            }
            if user_id:
                mission["user_id"] = user_id
            client.table("missions").upsert(mission).execute()

            if sources:
                client.table("sources").upsert([
                    {
                        "mission_id": session_id,
                        "url": s["url"],
                        "title": s.get("title"),
                        "snippet": (s.get("snippet") or "")[:2000],
                        "source_type": s.get("source_type", "web"),
                        "published_year": s.get("published_year"),
                    }
                    for s in sources
                ], on_conflict="mission_id,url").execute()

            report: Dict[str, Any] = {
                "mission_id": session_id,
                "output_type": ui,
                "content": narrative,
                "structured_data": {
                    "ui": ui,
                    "data": ui_data,
                    "claims": claims,
                    "contradictions": contradictions,
                },
            }
            if embedding:
                report["embedding"] = embedding
            client.table("reports").upsert(report, on_conflict="mission_id").execute()

        await asyncio.to_thread(_write)
        log.info("Persisted mission %s (%d sources, %d claims, embedding=%s)",
                 session_id, len(sources), len(claims), bool(embedding))

    except Exception as e:
        # The user already has their result; storage is best-effort.
        log.warning("Could not persist mission %s: %s", session_id, str(e)[:250])


async def search_past_missions(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Semantic search over previously stored reports.

    Requires the `match_reports` SQL function from supabase_schema.sql.
    """
    client = _get_client()
    if client is None:
        return []

    embedding = await _embed(query)
    if not embedding:
        return []

    try:
        def _search():
            return client.rpc("match_reports", {
                "query_embedding": embedding,
                "match_count": limit,
            }).execute()

        response = await asyncio.to_thread(_search)
        return response.data or []
    except Exception as e:
        log.warning("Semantic search failed: %s", str(e)[:200])
        return []
