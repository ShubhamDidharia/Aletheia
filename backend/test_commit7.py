"""
Tests for Commit 7 — Auditor citation enforcement and Visualizer validation.

These cover the parts that must hold regardless of what the LLM returns, so
they stub the LLM and cost no Gemini quota.

Run:  python test_commit7.py
"""
import asyncio

import agents.auditor as auditor_mod
import agents.visualizer as visualizer_mod
from agents.auditor import audit, _normalize
from agents.visualizer import _validate
from schemas.responses import (
    AuditReport, Claim, VerifiedClaim,
    VisualizerOutput, TableData, SWOTData, ChartData, ChartPoint,
)

PASSED = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASSED
    if condition:
        PASSED += 1
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {detail}")
        raise AssertionError(label)


SOURCES = [
    {"url": "https://apple.com/esg-report", "title": "Apple ESG", "snippet": "Carbon neutral by 2030."},
    {"url": "https://microsoft.com/sustainability", "title": "MS Sustainability", "snippet": "Carbon negative by 2030."},
]


def stub_audit(claims):
    async def _fake(prompt, schema, retries=2):
        return AuditReport(claims=claims)
    auditor_mod.generate_structured = _fake


async def test_auditor():
    print("\n=== Auditor: citation enforcement ===")

    # 1. Claims citing real sources survive.
    stub_audit([
        Claim(text="Apple targets carbon neutrality by 2030", source_url="https://apple.com/esg-report"),
        Claim(text="Microsoft targets carbon negative by 2030", source_url="https://microsoft.com/sustainability"),
    ])
    kept, dropped = await audit("q", SOURCES)
    check("cited claims are kept", len(kept) == 2 and dropped == 0, f"{len(kept)=} {dropped=}")
    check("citation is enriched with title+snippet",
          kept[0].source_title == "Apple ESG" and "2030" in kept[0].snippet)

    # 2. A fabricated URL is deleted — the core hallucination check.
    stub_audit([
        Claim(text="Apple targets carbon neutrality by 2030", source_url="https://apple.com/esg-report"),
        Claim(text="Tesla will ship solid-state in Q2", source_url="https://tesla.com/invented-by-the-llm"),
    ])
    kept, dropped = await audit("q", SOURCES)
    check("uncited claim is deleted", len(kept) == 1 and dropped == 1, f"{len(kept)=} {dropped=}")
    check("the surviving claim is the cited one", kept[0].text.startswith("Apple"))

    # 3. Cosmetic URL differences must NOT cause a false deletion.
    stub_audit([
        Claim(text="a", source_url="http://www.apple.com/esg-report/"),
        Claim(text="b", source_url="HTTPS://APPLE.COM/esg-report"),
        Claim(text="c", source_url="https://apple.com/esg-report#section-2"),
    ])
    kept, dropped = await audit("q", SOURCES)
    check("scheme/www/slash/case/fragment variants still match",
          len(kept) == 3 and dropped == 0, f"{len(kept)=} {dropped=}")

    # 4. A genuinely different path must still be rejected.
    stub_audit([Claim(text="x", source_url="https://apple.com/some-other-page")])
    kept, dropped = await audit("q", SOURCES)
    check("different path is rejected", len(kept) == 0 and dropped == 1)

    # 5. Empty claim text is dropped.
    stub_audit([Claim(text="   ", source_url="https://apple.com/esg-report")])
    kept, dropped = await audit("q", SOURCES)
    check("blank claim text is dropped", len(kept) == 0 and dropped == 1)

    # 6. No sources -> no LLM call at all.
    called = False
    async def _tripwire(prompt, schema, retries=2):
        nonlocal called
        called = True
        return AuditReport(claims=[])
    auditor_mod.generate_structured = _tripwire
    kept, dropped = await audit("q", [])
    check("no sources short-circuits without an LLM call", not called and kept == [])

    print("\n=== Auditor: URL normalization ===")
    check("www and trailing slash collapse",
          _normalize("https://www.a.com/b/") == _normalize("http://a.com/b"))
    check("query string is significant",
          _normalize("https://a.com/b?x=1") != _normalize("https://a.com/b?x=2"))


def test_visualizer():
    print("\n=== Visualizer: payload validation ===")

    # Valid table passes through.
    out = VisualizerOutput(ui="table", narrative="n", table=TableData(
        headers=["Metric", "Apple", "Microsoft"],
        rows=[["Target", "2030", "2030"], ["Type", "Neutral", "Negative"]],
    ))
    ui, data, problems = _validate(out)
    check("valid table kept as table", ui == "table" and not problems)
    check("rows preserved", data["rows"][0] == ["Target", "2030", "2030"])

    # Ragged rows get padded, not shipped broken.
    out = VisualizerOutput(ui="table", narrative="n", table=TableData(
        headers=["Metric", "Apple", "Microsoft"],
        rows=[["Target", "2030"], ["Type", "Neutral", "Negative", "extra"]],
    ))
    ui, data, _ = _validate(out)
    check("short row padded to header width",
          data["rows"][0] == ["Target", "2030", "Not reported"], str(data["rows"][0]))
    check("long row truncated to header width",
          data["rows"][1] == ["Type", "Neutral", "Negative"], str(data["rows"][1]))

    # ui says table but payload missing -> downgrade.
    ui, data, problems = _validate(VisualizerOutput(ui="table", narrative="n"))
    check("table with no payload downgrades to report", ui == "report" and problems)

    # SWOT.
    out = VisualizerOutput(ui="swot", narrative="n",
                           swot=SWOTData(strengths=["s"], weaknesses=[], opportunities=[], threats=[]))
    ui, data, problems = _validate(out)
    check("partially filled swot is accepted", ui == "swot" and data["strengths"] == ["s"])

    ui, _, problems = _validate(VisualizerOutput(
        ui="swot", narrative="n", swot=SWOTData()))
    check("entirely empty swot downgrades", ui == "report" and problems)

    # Chart needs >= 2 points.
    out = VisualizerOutput(ui="chart", narrative="n", chart=ChartData(
        title="t", points=[ChartPoint(label="Apple", value=1.0), ChartPoint(label="MS", value=2.0)]))
    ui, data, problems = _validate(out)
    check("chart with 2 points accepted", ui == "chart" and len(data["points"]) == 2)

    ui, _, problems = _validate(VisualizerOutput(
        ui="chart", narrative="n", chart=ChartData(title="t", points=[ChartPoint(label="a", value=1)])))
    check("single-point chart downgrades to report", ui == "report" and problems)

    # Plain report.
    ui, data, problems = _validate(VisualizerOutput(ui="report", narrative="n"))
    check("report passes with empty data", ui == "report" and data == {} and not problems)


async def test_visualize_wrapper():
    print("\n=== Visualizer: no-claims path ===")
    called = False
    async def _tripwire(prompt, schema, retries=2):
        nonlocal called
        called = True
    visualizer_mod.generate_structured = _tripwire
    ui, data, narrative, problems = await visualizer_mod.visualize("q", [])
    check("no claims short-circuits without an LLM call",
          not called and ui == "report" and problems)

    async def _fake(prompt, schema, retries=2):
        return VisualizerOutput(ui="table", narrative="  spaced  ", table=TableData(
            headers=["a", "b"], rows=[["1", "2"]]))
    visualizer_mod.generate_structured = _fake
    ui, data, narrative, problems = await visualizer_mod.visualize(
        "q", [VerifiedClaim(text="t", source_url="u", source_title="s", snippet="x")])
    check("narrative is trimmed", narrative == "spaced")
    check("table survives the wrapper", ui == "table" and data["headers"] == ["a", "b"])


async def main():
    await test_auditor()
    test_visualizer()
    await test_visualize_wrapper()
    print("\n" + "=" * 60)
    print(f"ALL {PASSED} CHECKS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
