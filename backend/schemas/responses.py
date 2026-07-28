from datetime import datetime
from typing import List, Literal, Optional

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


# ──────────────────────────────────────────────────────────────────────────────
# Auditor (Node 3)
# ──────────────────────────────────────────────────────────────────────────────
class Claim(BaseModel):
    """A single factual finding, tied to the source it came from."""
    text: str = Field(min_length=1)
    source_url: str = Field(
        description="The exact URL of the source this claim came from. "
                    "Must be copied verbatim from the supplied source list."
    )


class AuditReport(BaseModel):
    claims: List[Claim] = Field(default_factory=list)


class VerifiedClaim(BaseModel):
    """A claim whose citation was matched against the gathered sources in code."""
    text: str
    source_url: str
    source_title: str
    snippet: str


# ──────────────────────────────────────────────────────────────────────────────
# Visualizer (Node 4) — the Generative UI payloads
# ──────────────────────────────────────────────────────────────────────────────
UIType = Literal["table", "swot", "chart", "report"]


class TableData(BaseModel):
    headers: List[str] = Field(default_factory=list)
    rows: List[List[str]] = Field(default_factory=list)


class SWOTData(BaseModel):
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    opportunities: List[str] = Field(default_factory=list)
    threats: List[str] = Field(default_factory=list)


class ChartPoint(BaseModel):
    label: str
    value: float


class ChartData(BaseModel):
    title: str = ""
    x_label: str = ""
    y_label: str = ""
    points: List[ChartPoint] = Field(default_factory=list)


class VisualizerOutput(BaseModel):
    """
    One LLM call picks the output shape and fills in the matching payload.

    A single call (rather than one to choose plus one to generate) keeps the
    Gemini request count down; the graph validates that the payload actually
    matches the chosen `ui` and downgrades to "report" if it doesn't.
    """
    ui: UIType
    narrative: str = Field(default="", description="A short written analysis, 2-4 sentences.")
    table: Optional[TableData] = None
    swot: Optional[SWOTData] = None
    chart: Optional[ChartData] = None
