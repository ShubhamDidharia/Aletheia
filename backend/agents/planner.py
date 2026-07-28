"""Planner agent — breaks a research goal into independently-searchable sub-tasks."""
import logging

from schemas.responses import ResearchPlan
from services.llm import generate_structured

log = logging.getLogger("aletheia.planner")

PROMPT = """You are an expert research planner for a strategic intelligence agent.

Break the user's research query into 3 to 4 concrete, independently-searchable
sub-tasks. Each sub-task must be a specific web search query that would return
useful, citable results on its own. Do not include meta-tasks like "summarise
findings" — only searches.

Then judge the scope of the query:
- Set is_broad to true ONLY if the query lacks a clear scope: no region, no
  timeframe, and no specific named entities, such that a researcher would
  reasonably ask the user to narrow it before spending effort.
- If the query already names specific companies, a region, or a year, set
  is_broad to false and leave narrow_suggestion empty.
- If is_broad is true, narrow_suggestion must be ONE concrete scope you are
  actually proposing — a named region, named industry, named companies, or a
  specific timeframe. Under 10 words.
  GOOD: "EU-listed companies, 2025-2026" / "US automotive sector" / "Apple and Microsoft"
  BAD: "specific industries or a particular region" / "a certain market" /
       "narrow to particular companies"
  Never use the words "specific", "particular", "certain", or "relevant" —
  they mean you have not actually chosen a scope. Pick one.

User Query: {query}
"""

# A "suggestion" that just restates the need to narrow is not actionable.
_VAGUE_MARKERS = ("specific", "particular", "certain", "relevant", "various", "some ")


async def plan(query: str) -> ResearchPlan:
    """Returns a validated ResearchPlan. Raises LLMError if Gemini is unavailable."""
    plan_result = await generate_structured(PROMPT.format(query=query), ResearchPlan)

    # Don't pause the user for a suggestion that isn't actionable.
    suggestion = plan_result.narrow_suggestion.strip()
    if plan_result.is_broad:
        if not suggestion or any(m in suggestion.lower() for m in _VAGUE_MARKERS):
            log.info("Dropping vague narrow_suggestion %r — skipping scope gate.", suggestion)
            plan_result.is_broad = False
            plan_result.narrow_suggestion = ""

    log.info("Planned %d tasks (broad=%s)", len(plan_result.tasks), plan_result.is_broad)
    return plan_result
