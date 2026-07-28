"""
Visualizer agent (Node 4) — decides how the answer should be shaped.

The LLM picks table / swot / chart / report and fills the matching payload.
The choice is then verified in code: a "table" with ragged rows or a "chart"
with no points is downgraded to a plain report rather than shipped to the UI as
a broken component.
"""
import logging
from typing import Dict, List, Any, Tuple

from schemas.responses import (
    VerifiedClaim,
    VisualizerOutput,
    TableData,
    SWOTData,
    ChartData,
    UIType,
)
from services.llm import generate_structured, LLMError

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

Always write `narrative`: 2-4 sentences summarising what the research found.
Never state a fact that is not in the verified findings above.
"""

MAX_CLAIMS_IN_PROMPT = 40


def _validate(output: VisualizerOutput) -> Tuple[UIType, Dict[str, Any], List[str]]:
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
            return "table", TableData(headers=table.headers, rows=fixed).model_dump(), problems

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

    ui, data, problems = _validate(output)
    if problems:
        log.info("Visualizer chose %r but %s — downgraded to %r",
                 output.ui, "; ".join(problems), ui)

    return ui, data, output.narrative.strip(), problems
