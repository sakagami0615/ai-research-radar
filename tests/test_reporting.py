from datetime import datetime, timezone

from ai_research_radar.reporting.markdown import render_daily_report
from ai_research_radar.schemas.models import ArticleProposal, HotCandidate, RunMetadata


def test_render_daily_report_contains_selected_hot_and_errors():
    hot = HotCandidate(
        hot_id="hot:github:repo",
        title="Agent Runtime is surging",
        topic="agent runtime",
        score=92,
        reasons=["Momentum 96", "Source families 2"],
        evidence_urls=["https://github.com/owner/repo"],
        source_families=["technology", "community"],
        signals=["github:repo"],
        selected=True,
    )
    proposal = ArticleProposal(
        proposal_id="p1",
        source_hot_id=hot.hot_id,
        title_idea="Agent Runtimeを比較する",
        article_type="Comparison",
        target_reader="AI Engineer",
        why_now="HOT",
        technical_angle="Compare architecture",
        experiment_plan=["Run sample"],
        competition="Low",
        traffic_opportunity="High",
        technical_opportunity="High",
        unique_angle="Japanese comparison",
        evidence_links=["https://github.com/owner/repo"],
        risks=["Early signal"],
    )
    run = RunMetadata(
        run_id="run-1",
        started_at=datetime(2026, 9, 25, 8, 0, tzinfo=timezone.utc),
        finished_at=datetime(2026, 9, 25, 8, 1, tzinfo=timezone.utc),
        mode="daily",
        since="2026-09-24",
        until="2026-09-25",
        sources=["github", "arxiv"],
        input_counts={"github": 1},
        output_counts={"signals": 1, "hot": 1},
        errors=[{"source": "arxiv", "type": "network_error", "message": "timeout"}],
        report_paths=[],
    )

    markdown = render_daily_report("2026-09-25", [hot], [proposal], run, [])

    assert "# AI Daily Radar 2026-09-25" in markdown
    assert "## 選抜HOT" in markdown
    assert "Agent Runtime is surging" in markdown
    assert "Agent Runtimeを比較する" in markdown
    assert "arxiv" in markdown
    assert "timeout" in markdown


def test_render_daily_report_flags_sources_with_zero_items_as_data_gaps():
    run = RunMetadata(
        run_id="run-1",
        started_at=datetime(2026, 9, 25, 8, 0, tzinfo=timezone.utc),
        finished_at=datetime(2026, 9, 25, 8, 1, tzinfo=timezone.utc),
        mode="daily",
        since="2026-09-24",
        until="2026-09-25",
        sources=["github", "arxiv", "official_blogs"],
        input_counts={"github": 3},
        output_counts={"signals": 3, "hot": 0},
        errors=[
            {"source": "arxiv", "type": "unexpected_error", "message": "HTTP Error 406: Not Acceptable"},
            {"source": "official_blogs", "type": "unexpected_error", "message": "HTTP Error 403: Forbidden"},
        ],
        report_paths=[],
    )

    markdown = render_daily_report("2026-09-25", [], [], run, [])

    assert "## データ欠落" in markdown
    assert "arxiv: unexpected_error - HTTP Error 406: Not Acceptable" in markdown
    assert "official_blogs: unexpected_error - HTTP Error 403: Forbidden" in markdown
    assert "github" not in markdown.split("## データ欠落")[1].split("## 選抜HOT")[0]


def test_render_daily_report_omits_data_gaps_section_when_all_sources_succeeded():
    run = RunMetadata(
        run_id="run-1",
        started_at=datetime(2026, 9, 25, 8, 0, tzinfo=timezone.utc),
        finished_at=datetime(2026, 9, 25, 8, 1, tzinfo=timezone.utc),
        mode="daily",
        since="2026-09-24",
        until="2026-09-25",
        sources=["github"],
        input_counts={"github": 3},
        output_counts={"signals": 3, "hot": 0},
        errors=[],
        report_paths=[],
    )

    markdown = render_daily_report("2026-09-25", [], [], run, [])

    assert "## データ欠落" not in markdown


def test_render_daily_report_lists_zero_count_sources_in_appendix():
    run = RunMetadata(
        run_id="run-1",
        started_at=datetime(2026, 9, 25, 8, 0, tzinfo=timezone.utc),
        finished_at=datetime(2026, 9, 25, 8, 1, tzinfo=timezone.utc),
        mode="daily",
        since="2026-09-24",
        until="2026-09-25",
        sources=["github", "arxiv"],
        input_counts={"github": 0, "arxiv": 0},
        output_counts={"signals": 0, "hot": 0},
        errors=[],
        report_paths=[],
    )

    markdown = render_daily_report("2026-09-25", [], [], run, [])

    assert "## 収集Source一覧" in markdown
    assert "### github (0件)" in markdown
    assert "### arxiv (0件)" in markdown
    assert "該当Signalなし" in markdown


def test_render_daily_report_shows_placeholder_when_no_sources_at_all():
    run = RunMetadata(
        run_id="run-1",
        started_at=datetime(2026, 9, 25, 8, 0, tzinfo=timezone.utc),
        finished_at=datetime(2026, 9, 25, 8, 1, tzinfo=timezone.utc),
        mode="daily",
        since="2026-09-24",
        until="2026-09-25",
        sources=[],
        input_counts={},
        output_counts={},
        errors=[],
        report_paths=[],
    )

    markdown = render_daily_report("2026-09-25", [], [], run, [])

    assert "## 収集Source一覧" in markdown
    assert "本日は収集Signalがありません。" in markdown


def test_render_daily_report_lists_collected_signals_per_source_as_a_table():
    run = RunMetadata(
        run_id="run-1",
        started_at=datetime(2026, 9, 25, 8, 0, tzinfo=timezone.utc),
        finished_at=datetime(2026, 9, 25, 8, 1, tzinfo=timezone.utc),
        mode="daily",
        since="2026-09-24",
        until="2026-09-25",
        sources=["github"],
        input_counts={"github": 1},
        output_counts={"signals": 1},
        errors=[],
        report_paths=[],
    )
    signals = [
        {
            "source": "github",
            "title": "Agent Runtime",
            "url": "https://github.com/owner/agent-runtime",
            "summary": "Agent runtime toolkit",
        }
    ]

    markdown = render_daily_report("2026-09-25", [], [], run, signals)

    assert "### github (1件)" in markdown
    assert "| タイトル | 概要 |" in markdown
    assert "| --- | --- |" in markdown
    assert "[Agent Runtime](<https://github.com/owner/agent-runtime>)" in markdown
    assert "Agent runtime toolkit" in markdown


def test_render_daily_report_wraps_url_containing_parenthesis_in_angle_brackets():
    run = RunMetadata(
        run_id="run-1",
        started_at=datetime(2026, 9, 25, 8, 0, tzinfo=timezone.utc),
        finished_at=datetime(2026, 9, 25, 8, 1, tzinfo=timezone.utc),
        mode="daily",
        since="2026-09-24",
        until="2026-09-25",
        sources=["github"],
        input_counts={"github": 1},
        output_counts={"signals": 1},
        errors=[],
        report_paths=[],
    )
    signals = [
        {
            "source": "github",
            "title": "Repo",
            "url": "https://example.com/wiki/Foo_(bar)",
            "summary": "desc",
        }
    ]

    markdown = render_daily_report("2026-09-25", [], [], run, signals)

    assert "[Repo](<https://example.com/wiki/Foo_(bar)>)" in markdown


def _run_with_single_github_source() -> RunMetadata:
    return RunMetadata(
        run_id="run-1",
        started_at=datetime(2026, 9, 25, 8, 0, tzinfo=timezone.utc),
        finished_at=datetime(2026, 9, 25, 8, 1, tzinfo=timezone.utc),
        mode="daily",
        since="2026-09-24",
        until="2026-09-25",
        sources=["github"],
        input_counts={"github": 1},
        output_counts={"signals": 1},
        errors=[],
        report_paths=[],
    )


def test_render_daily_report_sanitizes_newlines_and_pipes_in_summary():
    signals = [
        {
            "source": "github",
            "title": "Repo",
            "url": "https://example.com/repo",
            "summary": "line1\nline2 | line3",
        }
    ]

    markdown = render_daily_report("2026-09-25", [], [], _run_with_single_github_source(), signals)

    assert "line1 line2 \\| line3" in markdown
    assert "line1\nline2" not in markdown


def test_render_daily_report_truncates_long_summary_at_120_chars():
    long_summary = "あ" * 200
    signals = [
        {
            "source": "github",
            "title": "Repo",
            "url": "https://example.com/repo",
            "summary": long_summary,
        }
    ]

    markdown = render_daily_report("2026-09-25", [], [], _run_with_single_github_source(), signals)

    assert ("あ" * 120 + "…") in markdown
    assert ("あ" * 121) not in markdown


def test_render_daily_report_shows_placeholder_for_empty_summary():
    signals = [
        {
            "source": "github",
            "title": "Repo",
            "url": "https://example.com/repo",
            "summary": "",
        }
    ]

    markdown = render_daily_report("2026-09-25", [], [], _run_with_single_github_source(), signals)

    assert "| [Repo](<https://example.com/repo>) | (概要なし) |" in markdown
