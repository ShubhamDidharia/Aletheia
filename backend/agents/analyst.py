"""
Analyst agent — inspects gathered evidence for genuine contradictions.

This is the real version of the doc's "two sources conflict" ambiguity junction:
an LLM reads the actual snippets and reports a specific disagreement, rather
than pattern-matching on substrings.
"""
import logging
from typing import List

from schemas.responses import SearchResult, ConflictReport
from services.llm import generate_structured, LLMError

log = logging.getLogger("aletheia.analyst")

PROMPT = """You are a fact-checking analyst. Below are snippets from web sources
gathered while researching: "{query}"

Identify whether any two sources make claims that genuinely CONTRADICT each other
on a matter of fact — different dates for the same event, different figures for
the same metric, or opposite statements about the same thing.

Be strict. Do NOT report a conflict for:
- sources merely covering different aspects of the topic
- differences in wording, emphasis, or opinion
- figures that refer to different years, regions, or entities

If there is no clear factual contradiction, set has_conflict to false and leave
the other fields empty.

If there IS one, set has_conflict to true, state the topic of disagreement in a
few words, and quote the two conflicting claims (claim_a and claim_b), each
under 25 words.

SOURCES:
{sources}
"""

MAX_SNIPPET = 600


async def detect_conflict(query: str, sources: List[SearchResult]) -> ConflictReport:
    """Returns a ConflictReport. Fails open (no conflict) if the LLM is unavailable."""
    if len(sources) < 2:
        return ConflictReport(has_conflict=False)

    rendered = "\n\n".join(
        f"[{i + 1}] {s.title}\n{s.snippet[:MAX_SNIPPET]}"
        for i, s in enumerate(sources)
    )

    try:
        report = await generate_structured(
            PROMPT.format(query=query, sources=rendered), ConflictReport
        )
    except LLMError as e:
        log.warning("Conflict detection unavailable: %s", e)
        return ConflictReport(has_conflict=False)

    # A conflict with no quoted claims isn't actionable — treat it as none.
    if report.has_conflict and not (report.claim_a.strip() and report.claim_b.strip()):
        return ConflictReport(has_conflict=False)

    log.info("Conflict detection: has_conflict=%s", report.has_conflict)
    return report
