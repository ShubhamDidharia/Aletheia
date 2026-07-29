"""
Researcher agent — executes one search sub-task and validates the results.

Deliberately contains NO interrupt() calls. LangGraph re-runs a node from the
top when it resumes from an interrupt, so any interrupt placed here would cause
every Tavily call in the node to be billed again and every SOURCE_FOUND event to
be re-emitted. Ambiguity gates live in their own cheap nodes in agent_graph.py.
"""
import re
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Set

from pydantic import ValidationError

from schemas.responses import SearchResult
from services.tavily import search
from services import playwright_scraper
from services.redis_service import publish_event

log = logging.getLogger("aletheia.researcher")

# Matches a plausible publication year in free text.
_YEAR_RE = re.compile(r"\b(19[89]\d|20[0-4]\d)\b")


def _extract_year(item: Dict[str, Any]) -> Optional[int]:
    """
    Best-effort publication year.

    Prefers Tavily's published_date; otherwise falls back to the most recent
    plausible year mentioned in the title or snippet.
    """
    raw_date = item.get("published_date") or item.get("publishedDate")
    if raw_date:
        match = _YEAR_RE.search(str(raw_date))
        if match:
            return int(match.group(1))

    text = f"{item.get('title', '')} {item.get('content', '')}"
    years = [int(y) for y in _YEAR_RE.findall(text)]
    if not years:
        return None

    # A page can cite many years; the newest one it mentions is the best
    # available proxy for how current the source is.
    plausible = [y for y in years if y <= datetime.now().year]
    return max(plausible) if plausible else None


async def _rescue_thin_results(
    raw_results: List[Dict[str, Any]],
    session_id: str,
) -> List[Dict[str, Any]]:
    """
    Re-fetch pages Tavily couldn't read (paywalls, bot-blocking, JS-rendered)
    with a headless browser, so they aren't discarded for having no content.

    A no-op when Playwright isn't installed.
    """
    thin = [r for r in raw_results if playwright_scraper.needs_scraping(r.get("content", ""))]
    if not thin or not playwright_scraper.is_available():
        return raw_results

    await publish_event(session_id, {
        "type": "LOG",
        "message": f"{len(thin)} source(s) returned no readable text — retrying with a browser.",
        "icon": "read",
    })

    rescued = 0
    for item in thin:
        url = item.get("url")
        if not url:
            continue
        text = await playwright_scraper.scrape(url)
        if text:
            item["content"] = text
            rescued += 1

    if rescued:
        await publish_event(session_id, {
            "type": "LOG",
            "message": f"Recovered full text from {rescued} of {len(thin)} blocked source(s).",
            "icon": "check",
        })

    return raw_results


async def research(
    task: str,
    session_id: str,
    known_urls: Optional[Set[str]] = None,
) -> List[SearchResult]:
    """
    Search one sub-task, validate every result, and stream findings to the UI.

    `known_urls` holds URLs already gathered by earlier sub-tasks. Sibling
    searches routinely surface the same page, so dedupe here — before
    publishing — or the UI shows the same evidence card twice.
    """
    seen = set(known_urls or ())

    await publish_event(session_id, {
        "type": "LOG",
        "message": f"Searching: {task}",
        "icon": "search",
    })

    raw_results = await search(task)

    raw_results = await _rescue_thin_results(raw_results, session_id)

    valid_results: List[SearchResult] = []
    dropped = 0
    duplicates = 0

    for item in raw_results:
        try:
            result = SearchResult(
                title=(item.get("title") or "").strip(),
                url=item.get("url") or "",
                snippet=(item.get("content") or "").strip(),
                published_year=_extract_year(item),
                source_type="pdf" if str(item.get("url", "")).lower().endswith(".pdf") else "web",
            )
        except ValidationError as e:
            dropped += 1
            log.info("Dropped malformed result from %r: %s", item.get("url"), e.error_count())
            continue

        url = str(result.url)
        if url in seen:
            duplicates += 1
            continue
        seen.add(url)

        valid_results.append(result)
        await publish_event(session_id, {
            "type": "SOURCE_FOUND",
            "title": result.title,
            "url": url,
            "snippet": result.snippet[:400],
            "source_type": result.source_type,
            "published_year": result.published_year,
        })

    notes = []
    if dropped:
        notes.append(f"discarded {dropped} malformed")
    if duplicates:
        notes.append(f"skipped {duplicates} already seen")

    await publish_event(session_id, {
        "type": "LOG",
        "message": (
            f"Found {len(valid_results)} new source(s)"
            + (f" ({', '.join(notes)})" if notes else "")
            + f" for: {task}"
        ),
        "icon": "read",
    })

    return valid_results
