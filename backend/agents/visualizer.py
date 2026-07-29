"""
Visualizer agent (Node 4) — decides how the answer should be shaped.

The LLM picks table / swot / chart / report and fills the matching payload.
The choice is then verified in code: a "table" with ragged rows or a "chart"
with no points is downgraded to a plain report rather than shipped to the UI as
a broken component.

For tables it also emits a per-cell citation (Commit 8's audit trail). Those
URLs are matched against the gathered sources in code — an unmatched citation
is cleared rather than shown, so a tooltip never claims provenance it lacks.
"""
import re
import logging
from typing import Dict, List, Any, Tuple

from schemas.responses import (
    VerifiedClaim,
    VisualizerOutput,
    TableDraft,
    TableData,
    Contradiction,
    UIType,
)
from services.llm import generate_structured, LLMError
from agents.auditor import _normalize

log = logging.getLogger("aletheia.visualizer")

PROMPT = """You are a data presentation specialist. Choose the best way to
present the findings of this research and produce it.

RESEARCH GOAL: "{query}"

VERIFIED FINDINGS (these are the only facts you may use):
{claims}

Choose exactly one `ui`:
- "table"  — the goal compares two or more named entities across shared
             attributes. Columns are the entities, the first column is the
             metric name. Every row MUST have exactly as many cells as there
             are headers; use "Not reported" for gaps.
- "swot"   — the goal is a strategic assessment of a single subject.
- "chart"  — the findings contain several comparable NUMERIC values on one
             measure. Do not choose this unless you have real numbers.
- "report" — anything else, or when the findings don't fit the shapes above.

Fill in ONLY the field matching your choice ({{table, swot, chart}}); leave the
others null. For "report", leave all three null.

If you choose "table", also fill `citations`: a grid with EXACTLY the same shape
as `rows` — same number of inner lists, same length each.

`citations[r][c]` must be the URL backing the value at `rows[r][c]`, and
nothing else. Line them up position by position: if the Microsoft figure sits
in column 2, its URL goes in column 2, not column 1. Copy URLs verbatim from
the findings above; never invent one. Use an empty string for the metric-name
column, for any "Not reported" gap, and for anything you cannot cite.

Always write `narrative`: 2-4 sentences summarising what the research found.
Never state a fact that is not in the verified findings above.
"""

MAX_CLAIMS_IN_PROMPT = 40

# A gap carries no claim, so it can carry no citation — the model routinely
# lines a citation up against the placeholder instead of the value beside it.
PLACEHOLDERS = {
    "", "-", "--", "—", "–", "n/a", "na", "none", "unknown",
    "not reported", "not disclosed", "not stated", "not specified",
    "not available", "no data", "tbd",
}


def _is_placeholder(value: str) -> bool:
    return str(value).strip().strip(".").lower() in PLACEHOLDERS


def _verify_citations(
    table: TableDraft,
    known_urls: Dict[str, str],
) -> Tuple[List[List[str]], int]:
    """
    Match every proposed cell citation against a real source URL.

    Returns a grid the same shape as `rows` plus the number of citations
    dropped for not resolving.
    """
    grid: List[List[str]] = []
    dropped = 0

    for r, row in enumerate(table.rows):
        proposed = table.citations[r] if r < len(table.citations) else []
        out: List[str] = []
        for c in range(len(row)):
            raw = proposed[c] if c < len(proposed) else ""
            if not raw or not raw.strip():
                out.append("")
                continue
            if _is_placeholder(row[c]):
                # Citing "Not reported" would put an audit-trail tooltip on a
                # gap, implying evidence for something no source stated.
                dropped += 1
                out.append("")
                continue
            resolved = known_urls.get(_normalize(raw))
            if resolved is None:
                dropped += 1
                out.append("")
            else:
                out.append(resolved)
        grid.append(out)

    return grid, dropped


# Words too generic to tie a row to a specific disagreement.
_TOPIC_STOPWORDS = {
    "the", "and", "for", "with", "from", "about", "target", "targets", "goal",
    "goals", "data", "report", "reports", "date", "dates", "year", "years",
    "company", "companies", "value", "values", "figure", "figures",
}


def _discriminating_tokens(topic: str, row_texts: List[str]) -> set[str]:
    """
    The words in `topic` that actually single out a row.

    A term appearing in most rows is the table's subject matter, not the point
    of disagreement — "solid" and "state" show up in nearly every row of a
    solid-state battery comparison. Matching on those flags half the table and
    makes the warning badge meaningless, so drop anything that common.
    """
    tokens = {
        word for word in re.findall(r"[a-z]{4,}", topic.lower())
        if word not in _TOPIC_STOPWORDS
    }
    if not row_texts:
        return tokens

    limit = max(1, len(row_texts) // 2)
    return {
        token for token in tokens
        if sum(1 for text in row_texts if token in text) <= limit
    }


def _apply_contradiction_flags(
    draft: TableDraft,
    contradictions: List[Contradiction],
) -> TableData:
    """
    Flag any row whose cited sources are on opposite sides of a contradiction,
    or whose metric name matches the contradiction's topic.

    Returns the wire-format TableData — the flags are ours, not the model's.
    """
    flagged: List[int] = []
    reasons: Dict[str, str] = {}

    row_texts = [" ".join(str(cell) for cell in row).lower() for row in draft.rows]
    # Worked out once per contradiction, against the whole table.
    tokens_for = {
        id(conflict): _discriminating_tokens(conflict.topic, row_texts)
        for conflict in contradictions
    }

    for r, row in enumerate(draft.rows):
        cited = {u for u in (draft.citations[r] if r < len(draft.citations) else []) if u}
        row_text = row_texts[r]
        label = (row[0] if row else "").lower()

        for conflict in contradictions:
            cites_a_side = conflict.source_a in cited or conflict.source_b in cited
            topic_in_label = bool(conflict.topic) and conflict.topic.lower() in label

            # Relevance must come from the subject matter, never from the
            # citations alone: in a two-entity comparison every row cites the
            # same two sources, so "cites both sides" would flag the whole
            # table. A row qualifies when it is actually about the disputed
            # thing — and cites at least one of the disagreeing sources.
            # One shared word is a weak signal ("battery" in a battery table).
            # Require two of the distinguishing terms when two exist, so the
            # flag lands on the row the sources actually disagree about.
            tokens = tokens_for[id(conflict)]
            hits = sum(1 for token in tokens if token in row_text)
            on_topic = bool(tokens) and cites_a_side and hits >= min(2, len(tokens))

            if topic_in_label or on_topic:
                flagged.append(r)
                reasons[str(r)] = (
                    f"Sources disagree on {conflict.topic}: "
                    f"“{conflict.claim_a}” vs “{conflict.claim_b}”."
                )
                break

    return TableData(
        headers=draft.headers,
        rows=draft.rows,
        citations=draft.citations,
        flagged_rows=flagged,
        flag_reasons=reasons,
    )


def _validate(
    output: VisualizerOutput,
    known_urls: Dict[str, str],
    contradictions: List[Contradiction],
) -> Tuple[UIType, Dict[str, Any], List[str]]:
    """
    Check the payload really matches the declared ui.
    Returns (ui, data, problems). Downgrades to "report" when it doesn't.
    """
    problems: List[str] = []

    if output.ui == "table":
        table = output.table
        if not table or not table.headers or not table.rows:
            problems.append("table payload was empty")
        else:
            width = len(table.headers)
            fixed: List[List[str]] = []
            for row in table.rows:
                if len(row) < width:
                    row = row + ["Not reported"] * (width - len(row))
                elif len(row) > width:
                    row = row[:width]
                fixed.append([str(cell) for cell in row])
            table.rows = fixed

            table.citations, dropped = _verify_citations(table, known_urls)
            if dropped:
                problems.append(f"cleared {dropped} unverifiable citation(s)")

            final = _apply_contradiction_flags(table, contradictions)
            return "table", final.model_dump(), problems

    elif output.ui == "swot":
        swot = output.swot
        if not swot or not any(
            [swot.strengths, swot.weaknesses, swot.opportunities, swot.threats]
        ):
            problems.append("swot payload was empty")
        else:
            return "swot", swot.model_dump(), problems

    elif output.ui == "chart":
        chart = output.chart
        if not chart or len(chart.points) < 2:
            problems.append("chart needed at least 2 numeric points")
        else:
            return "chart", chart.model_dump(), problems

    elif output.ui == "report":
        return "report", {}, problems

    else:  # pragma: no cover - Literal already constrains this
        problems.append(f"unknown ui {output.ui!r}")

    return "report", {}, problems


async def visualize(
    query: str,
    claims: List[VerifiedClaim],
    contradictions: List[Contradiction] | None = None,
) -> Tuple[UIType, Dict[str, Any], str, List[str]]:
    """
    Returns (ui, data, narrative, problems).

    Falls back to a plain report if the LLM is unavailable, so a mission always
    delivers something.
    """
    if not claims:
        return "report", {}, "", ["no verified claims to present"]

    rendered = "\n".join(
        f"- {c.text}  [{c.source_url}]" for c in claims[:MAX_CLAIMS_IN_PROMPT]
    )

    try:
        output = await generate_structured(
            PROMPT.format(query=query, claims=rendered), VisualizerOutput
        )
    except LLMError as e:
        log.warning("Visualizer unavailable: %s", e)
        raise

    known_urls = {_normalize(c.source_url): c.source_url for c in claims}
    ui, data, problems = _validate(output, known_urls, contradictions or [])

    if problems:
        log.info("Visualizer chose %r; %s", output.ui, "; ".join(problems))

    return ui, data, output.narrative.strip(), problems
