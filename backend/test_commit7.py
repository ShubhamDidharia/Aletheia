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
from agents.visualizer import _validate as _validate_raw
from schemas.responses import (
    AuditReport, Claim, VerifiedClaim,
    VisualizerOutput, TableData, SWOTData, ChartData, ChartPoint,
    Contradiction,
)

# Sources the Visualizer is allowed to cite in these tests.
KNOWN = {
    _normalize("https://apple.com/esg-report"): "https://apple.com/esg-report",
    _normalize("https://microsoft.com/sustainability"): "https://microsoft.com/sustainability",
}


def _validate(output, known=None, contradictions=None):
    return _validate_raw(output, known if known is not None else KNOWN, contradictions or [])

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


def test_audit_trail():
    """Commit 8: per-cell citations must be verified, never taken on trust."""
    print("\n=== Visualizer: audit-trail citations ===")

    out = VisualizerOutput(ui="table", narrative="n", table=TableData(
        headers=["Metric", "Apple", "Microsoft"],
        rows=[["Target", "2030", "2030"]],
        citations=[["", "https://apple.com/esg-report", "https://microsoft.com/sustainability"]],
    ))
    ui, data, problems = _validate(out)
    check("real citations survive",
          data["citations"][0][1] == "https://apple.com/esg-report" and not problems)
    check("uncited cell stays empty", data["citations"][0][0] == "")

    # A fabricated citation must be cleared, not rendered as provenance.
    out = VisualizerOutput(ui="table", narrative="n", table=TableData(
        headers=["Metric", "Apple"],
        rows=[["Target", "2030"]],
        citations=[["", "https://invented-by-the-llm.example/page"]],
    ))
    ui, data, problems = _validate(out)
    check("fabricated citation cleared", data["citations"][0][1] == "")
    check("clearing is reported", any("unverifiable" in p for p in problems), str(problems))

    # Citation grid must match the row shape even when the model under-fills it.
    out = VisualizerOutput(ui="table", narrative="n", table=TableData(
        headers=["Metric", "Apple", "Microsoft"],
        rows=[["Target", "2030", "2030"], ["Ambition", "Neutral", "Negative"]],
        citations=[["", "https://apple.com/esg-report"]],
    ))
    ui, data, problems = _validate(out)
    check("citation grid padded to row shape",
          len(data["citations"]) == 2 and all(len(r) == 3 for r in data["citations"]),
          str(data["citations"]))

    # A gap must never carry provenance, even when the model cites it.
    out = VisualizerOutput(ui="table", narrative="n", table=TableData(
        headers=["Metric", "Apple", "Microsoft"],
        rows=[["Carbon target", "Not reported", "By 2030"]],
        citations=[["", "https://apple.com/esg-report", "https://microsoft.com/sustainability"]],
    ))
    ui, data, problems = _validate(out)
    check("citation on a 'Not reported' gap is cleared", data["citations"][0][1] == "")
    check("citation on the real value is kept",
          data["citations"][0][2] == "https://microsoft.com/sustainability")

    for gap in ["N/A", "—", "none", "  Unknown  ", "TBD", ""]:
        out = VisualizerOutput(ui="table", narrative="n", table=TableData(
            headers=["Metric", "Apple"], rows=[["X", gap]],
            citations=[["", "https://apple.com/esg-report"]],
        ))
        _, data, _ = _validate(out)
        assert data["citations"][0][1] == "", f"gap {gap!r} kept a citation"
    check("every placeholder variant is treated as a gap", True)

    # Cosmetic URL variants still resolve.
    out = VisualizerOutput(ui="table", narrative="n", table=TableData(
        headers=["Metric", "Apple"], rows=[["Target", "2030"]],
        citations=[["", "http://www.apple.com/esg-report/"]],
    ))
    ui, data, _ = _validate(out)
    check("url variant resolves to the canonical source",
          data["citations"][0][1] == "https://apple.com/esg-report")


def test_contradiction_flags():
    """Commit 9: rows backed by contradicting sources get a warning badge."""
    print("\n=== Visualizer: contradiction flags ===")

    conflict = Contradiction(
        topic="carbon neutrality",
        claim_a="Apple is carbon neutral across its footprint",
        source_a="https://apple.com/esg-report",
        claim_b="A new Apple factory increases emissions",
        source_b="https://microsoft.com/sustainability",
    )

    # The disputed row is flagged; a row about something else is not — even
    # though both rows cite exactly the same pair of sources, which is the
    # normal shape of a two-entity comparison.
    out = VisualizerOutput(ui="table", narrative="n", table=TableData(
        headers=["Metric", "A", "B"],
        rows=[["Carbon neutrality", "Neutral by 2030", "Negative by 2030"],
              ["Revenue", "1", "2"]],
        citations=[
            ["", "https://apple.com/esg-report", "https://microsoft.com/sustainability"],
            ["", "https://apple.com/esg-report", "https://microsoft.com/sustainability"],
        ],
    ))
    ui, data, _ = _validate(out, contradictions=[conflict])
    check("the disputed row is flagged", data["flagged_rows"] == [0], str(data["flagged_rows"]))
    check("flag carries an explanation",
          "carbon neutrality" in data["flag_reasons"]["0"], str(data["flag_reasons"]))
    check("same citations but different subject is not flagged",
          "1" not in data["flag_reasons"], str(data["flag_reasons"]))

    # The two sides usually land in different rows. Citing one side while
    # discussing the disputed subject must still flag.
    out = VisualizerOutput(ui="table", narrative="n", table=TableData(
        headers=["Metric", "Apple", "Microsoft"],
        rows=[
            ["Overall Carbon Ambition", "Carbon neutrality by 2030", "Carbon negative"],
            ["Revenue growth", "8%", "12%"],
        ],
        citations=[
            ["", "https://apple.com/esg-report", "https://microsoft.com/sustainability"],
            ["", "https://apple.com/esg-report", "https://microsoft.com/sustainability"],
        ],
    ))
    ui, data, _ = _validate(out, contradictions=[conflict])
    check("row citing one side and on-topic is flagged", 0 in data["flagged_rows"],
          str(data["flagged_rows"]))
    check("off-topic row citing the same source is not flagged",
          1 not in data["flagged_rows"], str(data["flagged_rows"]))

    # Domain vocabulary must not flag the whole table: in a solid-state
    # battery comparison, "solid"/"state"/"battery" appear in nearly every row.
    battery_conflict = Contradiction(
        topic="All-solid-state battery installation timeline",
        claim_a="installed in vehicles in 2026", source_a="https://apple.com/esg-report",
        claim_b="small-scale production in 2027", source_b="https://microsoft.com/sustainability",
    )
    rows = [
        ["Solid-State Battery Expectation 2026", "High", "Medium"],
        ["Solid-State Energy Density", "400 Wh/kg", "350 Wh/kg"],
        ["Solid-State Fast Charging", "10 min", "12 min"],
        ["Vehicle Installation Timeline", "2026", "2027"],
        ["Solid-State Testing Status", "Pilot", "Lab"],
        ["Solid-State Driving Range", "800 km", "700 km"],
    ]
    out = VisualizerOutput(ui="table", narrative="n", table=TableData(
        headers=["Metric", "A", "B"], rows=rows,
        citations=[["", "https://apple.com/esg-report", "https://microsoft.com/sustainability"]] * len(rows),
    ))
    _, data, _ = _validate(out, contradictions=[battery_conflict])
    flagged = data["flagged_rows"]
    check("domain vocabulary doesn't flag most of the table",
          len(flagged) <= len(rows) // 2, f"flagged {len(flagged)}/{len(rows)}: {flagged}")
    check("the genuinely disputed row is the one flagged",
          flagged == [3], f"flagged {flagged}, expected [3] (Vehicle Installation Timeline)")

    # Generic topic words must not flag half the table.
    generic = Contradiction(topic="2030 target date", claim_a="a",
                            source_a="https://apple.com/esg-report",
                            claim_b="b", source_b="https://microsoft.com/sustainability")
    out = VisualizerOutput(ui="table", narrative="n", table=TableData(
        headers=["Metric", "Apple"], rows=[["Revenue target", "8%"]],
        citations=[["", "https://apple.com/esg-report"]],
    ))
    _, data, _ = _validate(out, contradictions=[generic])
    check("generic topic words don't flag unrelated rows", data["flagged_rows"] == [],
          str(data["flagged_rows"]))

    # Row whose metric name matches the topic -> flagged even without both cites.
    out = VisualizerOutput(ui="table", narrative="n", table=TableData(
        headers=["Metric", "A"],
        rows=[["Carbon neutrality target", "2030"]],
        citations=[["", "https://apple.com/esg-report"]],
    ))
    ui, data, _ = _validate(out, contradictions=[conflict])
    check("row matching the disputed topic is flagged", data["flagged_rows"] == [0])

    # No contradictions -> nothing flagged.
    out = VisualizerOutput(ui="table", narrative="n", table=TableData(
        headers=["Metric", "A"], rows=[["Target", "2030"]],
        citations=[["", "https://apple.com/esg-report"]],
    ))
    ui, data, _ = _validate(out, contradictions=[])
    check("no contradictions leaves rows unflagged",
          data["flagged_rows"] == [] and data["flag_reasons"] == {})


async def test_contradiction_verification():
    """Commit 9: contradiction citations are verified like every other one."""
    print("\n=== Contradiction sweep: citation verification ===")
    import agents.contradiction as contra_mod
    from schemas.responses import ContradictionReport

    sources = [
        {"url": "https://apple.com/esg-report", "title": "Apple", "snippet": "carbon neutral"},
        {"url": "https://reuters.com/factory", "title": "Reuters", "snippet": "emissions rise"},
    ]

    def stub(items):
        async def _fake(prompt, schema, retries=2):
            return ContradictionReport(contradictions=items)
        contra_mod.generate_structured = _fake

    stub([Contradiction(topic="emissions", claim_a="neutral",
                        source_a="https://apple.com/esg-report",
                        claim_b="rising", source_b="https://reuters.com/factory")])
    found = await contra_mod.detect_contradictions("q", sources)
    check("valid contradiction kept", len(found) == 1 and found[0].topic == "emissions")

    stub([Contradiction(topic="x", claim_a="a", source_a="https://apple.com/esg-report",
                        claim_b="b", source_b="https://made-up.example/page")])
    found = await contra_mod.detect_contradictions("q", sources)
    check("contradiction with a fabricated source is dropped", found == [])

    stub([Contradiction(topic="x", claim_a="a", source_a="https://apple.com/esg-report",
                        claim_b="b", source_b="https://apple.com/esg-report")])
    found = await contra_mod.detect_contradictions("q", sources)
    check("a source cannot contradict itself", found == [])

    called = False
    async def _tripwire(prompt, schema, retries=2):
        nonlocal called
        called = True
    contra_mod.generate_structured = _tripwire
    found = await contra_mod.detect_contradictions("q", sources[:1])
    check("single source short-circuits without an LLM call", not called and found == [])


def test_llm_schema_compatibility():
    """
    Every schema handed to generate_structured() must be accepted by the Gemini
    Developer API, which rejects `additionalProperties` outright. A dict-typed
    Pydantic field compiles to exactly that — and the failure is silent in
    production (the step just degrades), so guard it here.
    """
    print("\n=== LLM schemas: Gemini Developer API compatibility ===")
    from schemas.responses import (
        ResearchPlan, ConflictReport, AuditReport, ContradictionReport, VisualizerOutput,
    )

    def find_additional_properties(schema: dict, path: str = "") -> list[str]:
        found = []
        if isinstance(schema, dict):
            if "additionalProperties" in schema:
                found.append(path or "<root>")
            for key, value in schema.items():
                found += find_additional_properties(value, f"{path}.{key}" if path else key)
        elif isinstance(schema, list):
            for i, value in enumerate(schema):
                found += find_additional_properties(value, f"{path}[{i}]")
        return found

    for model in (ResearchPlan, ConflictReport, AuditReport, ContradictionReport, VisualizerOutput):
        offenders = find_additional_properties(model.model_json_schema())
        check(f"{model.__name__} has no additionalProperties",
              not offenders, f"found at {offenders}")


async def main():
    await test_auditor()
    test_visualizer()
    await test_visualize_wrapper()
    test_audit_trail()
    test_contradiction_flags()
    await test_contradiction_verification()
    test_llm_schema_compatibility()
    print("\n" + "=" * 60)
    print(f"ALL {PASSED} CHECKS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
