from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, HttpUrl


STALENESS_YEARS = 3


def is_stale_year(published_year: Optional[int]) -> bool:
    """True when a source is older than 3 years — the doc's recency gate."""
    if published_year is None:
        return False
    return published_year < datetime.now().year - STALENESS_YEARS


class SearchResult(BaseModel):
    """
    A validated source. Anything Tavily returns that fails this is discarded.

    Graph state stores these as plain dicts (model_dump) because LangGraph's
    msgpack checkpoint serializer cannot round-trip Pydantic models.
    """
    title: str = Field(min_length=1)
    url: HttpUrl
    snippet: str = Field(min_length=1)
    published_year: Optional[int] = None
    source_type: str = "web"

    @property
    def is_stale(self) -> bool:
        return is_stale_year(self.published_year)


class ResearchPlan(BaseModel):
    """Planner output: sub-tasks plus a judgement on whether the query is too broad."""
    tasks: List[str] = Field(min_length=1, max_length=6)
    is_broad: bool = Field(
        description="True only if the query lacks a clear scope (no region, "
                    "timeframe, or specific entities) and would benefit from narrowing."
    )
    narrow_suggestion: str = Field(
        default="",
        description="If is_broad, a concrete narrower scope, e.g. 'European market only'. "
                    "Empty string otherwise.",
    )


class ConflictReport(BaseModel):
    """Analyst output: does the evidence actually contradict itself?"""
    has_conflict: bool
    topic: str = Field(default="", description="What the sources disagree about.")
    claim_a: str = Field(default="")
    claim_b: str = Field(default="")
