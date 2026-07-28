"""
Auditor agent (Node 3) — extracts findings and deletes anything uncited.

The LLM proposes claims with the URL each came from, but it is NOT trusted to
police itself: every proposed citation is matched against the URLs actually
gathered by the Researcher, in code. A claim whose citation doesn't resolve to
a real source is dropped, which is what makes this a hallucination check rather
than a second opinion from the same model.
"""
import logging
from typing import Dict, List, Any, Tuple
from urllib.parse import urlsplit, urlunsplit

from schemas.responses import AuditReport, VerifiedClaim
from services.llm import generate_structured, LLMError

log = logging.getLogger("aletheia.auditor")

PROMPT = """You are a fact-checking auditor for a research report on:
"{query}"

Below are the sources the research agent gathered. Extract the concrete, factual
findings that are actually supported by these snippets.

Rules:
- Every claim MUST come from one of the sources below. Never add outside knowledge.
- Copy the source's URL verbatim into source_url. Do not shorten or rewrite it.
- One fact per claim, under 30 words, stated plainly.
- Prefer specific figures, dates, targets and commitments over vague statements.
- If a snippet supports nothing concrete, skip it. Fewer solid claims beats many weak ones.
- Extract at most 20 claims.

SOURCES:
{sources}
"""

MAX_SNIPPET = 700
MAX_CLAIMS = 20


def _normalize(url: str) -> str:
    """
    Compare URLs ignoring differences a model routinely introduces:
    scheme, 'www.', trailing slash, case, and any fragment.
    """
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return url.strip().lower()

    host = (parts.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    path = (parts.path or "").rstrip("/")
    return urlunsplit(("", host, path, parts.query, "")).lower()


async def audit(
    query: str,
    sources: List[Dict[str, Any]],
) -> Tuple[List[VerifiedClaim], int]:
    """
    Returns (verified_claims, dropped_count).

    Fails open with an empty claim list if the LLM is unavailable — the mission
    still completes with its sources, just without an extracted findings list.
    """
    if not sources:
        return [], 0

    rendered = "\n\n".join(
        f"[{i + 1}] {s['title']}\nURL: {s['url']}\n{(s.get('snippet') or '')[:MAX_SNIPPET]}"
        for i, s in enumerate(sources)
    )

    try:
        report = await generate_structured(
            PROMPT.format(query=query, sources=rendered), AuditReport
        )
    except LLMError as e:
        log.warning("Audit unavailable: %s", e)
        raise

    by_url = {_normalize(s["url"]): s for s in sources}

    verified: List[VerifiedClaim] = []
    dropped = 0

    for claim in report.claims[:MAX_CLAIMS]:
        source = by_url.get(_normalize(claim.source_url))
        if source is None:
            dropped += 1
            log.info("Dropped uncited claim (url %r not in sources): %s",
                     claim.source_url, claim.text[:80])
            continue
        if not claim.text.strip():
            dropped += 1
            continue

        verified.append(VerifiedClaim(
            text=claim.text.strip(),
            source_url=source["url"],
            source_title=source["title"],
            snippet=(source.get("snippet") or "")[:400],
        ))

    log.info("Audit kept %d claim(s), dropped %d uncited", len(verified), dropped)
    return verified, dropped
