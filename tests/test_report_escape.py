from datetime import datetime, timezone

from ai_research_radar.reporting.escape import cell, heading, inline, paragraph, span, url
from ai_research_radar.reporting.markdown import render_daily_report
from ai_research_radar.schemas.models import HotCandidate, RunMetadata


def _run(**overrides) -> RunMetadata:
    values = dict(
        run_id="run-1", started_at=datetime(2026, 10, 9, tzinfo=timezone.utc), finished_at=None, mode="agent",
        since="2026-10-08", until="2026-10-09", sources=["github"], input_counts={"github": 1}, output_counts={},
        errors=[], report_paths=[],
    )
    values.update(overrides)
    return RunMetadata(**values)


def _hot(**overrides) -> HotCandidate:
    values = dict(
        hot_id="hot:event:x", title="Title", topic="topic", score=80.0, reasons=["Momentum 90"],
        evidence_urls=["https://example.com/a"], source_families=["technology"], signals=["github:x"], selected=True,
        summary="概要",
    )
    values.update(overrides)
    return HotCandidate(**values)


def test_selected_hot_escapes_external_title_topic_reasons_and_links_evidence():
    hot = _hot(
        title="[click](javascript:alert) <b>\n# not heading",
        topic="a|b",
        reasons=["- not a list\nsecond line"],
        evidence_urls=["https://example.com/a>b"],
    )

    markdown = render_daily_report("2026-10-09", [hot], [], _run(), [])

    assert "### \\[click\\](javascript:alert) &lt;b&gt; # not heading" in markdown
    assert "- Topic: a\\|b" in markdown
    assert "  - \\- not a list second line" in markdown
    assert "- Evidence: [https://example.com/a&gt;b](<https://example.com/a%3Eb>)" in markdown


def test_errors_and_data_gaps_are_one_escaped_line():
    run = _run(
        sources=["github", "arxiv"],
        errors=[{"source": "arxiv", "type": "http_error", "message": "line1\n## line2 <x>"}],
    )

    markdown = render_daily_report("2026-10-09", [], [], run, [])

    assert "- arxiv: http_error - line1 ## line2 &lt;x&gt;" in markdown
    assert "\n## line2" not in markdown


def test_escape_helpers():
    assert span("a\n  b [c]") == "a b \\[c\\]"
    assert span(None) == ""
    assert inline("1. item") == "1\\. item"
    assert heading("title #") == "title \\#"
    assert cell("a|b\nc") == "a\\|b<br>c"
    assert cell("") == "-"
    assert paragraph(" - x\ny ") == "\\- x<br>y"
    assert url("https://e.com/a b|<>") == "https://e.com/a b%7C%3C%3E"
