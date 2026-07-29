"""
Contradiction detection (Commit 9).

The Analyst (Commit 6) asks a yes/no question to decide whether to pause the
user. This is the fuller sweep that runs once at the end: it compares claims
across every gathered source and returns each disagreement with both sides and
their URLs, so the Visualizer can flag the affected rows.

As with the Auditor, the model is not trusted on citations — both URLs in every
contradiction are matched against the sources actually gathered, in code.
"""
import logging
from typing import Dict, List, Any

from schemas.responses import Contradiction, ContradictionReport
from services.llm import generate_structured, LLMError
from agents.auditor import _normalize

log = logging.getLogger("aletheia.contradiction")

PROMPT = """You are a fact-checking analyst reviewing sources gathered for:
"{query}"

Find every place where two sources make claims that genuinely CONTRADICT each
other on a matter of fact — different dates for the same event, different
figures for the same metric, or opposite statements about the same thing.

The classic case: one source says a company is "carbon neutral" while another
reports "a new factory increases emissions".

Be strict. Do NOT report a contradiction for:
- sources covering different aspects of the topic
- differences in wording, emphasis or opinion
- figures that refer to different years, regions or entities

For each real contradiction give the topic in a few words, both claims (each
under 25 words), and the exact URL of the source each came from, copied
verbatim from the list below. Report at most 5. If there are none, return an
empty list.

SOURCES:
{sources}
"""

MAX_SNIPPET = 600
MAX_CONTRADICTIONS = 5


async def detect_contradictions(
    query: str,
    sources: List[Dict[str, Any]],
) -> List[Contradiction]:
    """
    Returns verified contradictions. Fails open (empty list) if the LLM is
    unavailable — a missing sweep must not sink a finished mission.
    """
    if len(sources) < 2:
        return []

    rendered = "\n\n".join(
        f"[{i + 1}] {s['title']}\nURL: {s['url']}\n{(s.get('snippet') or '')[:MAX_SNIPPET]}"
        for i, s in enumerate(sources)
    )

    try:
        report = await generate_structured(
            PROMPT.format(query=query, sources=rendered), ContradictionReport
        )
    except LLMError as e:
        log.warning("Contradiction sweep unavailable: %s", e)
        return []

    known = {_normalize(s["url"]): s["url"] for s in sources}
    verified: List[Contradiction] = []

    for item in report.contradictions[:MAX_CONTRADICTIONS]:
        url_a = known.get(_normalize(item.source_a))
        url_b = known.get(_normalize(item.source_b))

        # Both sides must trace to real sources, and to *different* ones —
        # a source cannot contradict itself.
        if not url_a or not url_b:
            log.info("Dropped contradiction with unresolvable citation: %s", item.topic)
            continue
        if url_a == url_b:
            log.info("Dropped self-contradiction on a single source: %s", item.topic)
            continue

        verified.append(item.model_copy(update={"source_a": url_a, "source_b": url_b}))

    log.info("Contradictions: %d verified of %d proposed",
             len(verified), len(report.contradictions))
    return verified
