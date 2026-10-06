from dataclasses import replace
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

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


def test_render_daily_report_escapes_pipe_and_brackets_in_title():
    signals = [
        {
            "source": "github",
            "title": "[urgent] fix | rename",
            "url": "https://example.com/repo",
            "summary": "desc",
        }
    ]

    markdown = render_daily_report("2026-09-25", [], [], _run_with_single_github_source(), signals)

    assert "[\\[urgent\\] fix \\| rename](<https://example.com/repo>)" in markdown


def test_render_daily_report_escapes_preexisting_backslash_before_pipe_in_title():
    signals = [
        {
            "source": "github",
            "title": "a\\|b",
            "url": "https://example.com/repo",
            "summary": "desc",
        }
    ]

    markdown = render_daily_report("2026-09-25", [], [], _run_with_single_github_source(), signals)

    assert "[a\\\\\\|b](<https://example.com/repo>)" in markdown


def test_render_daily_report_escapes_script_tag_in_title():
    signals = [
        {
            "source": "github",
            "title": "<script>alert(1)</script>",
            "url": "https://example.com/repo",
            "summary": "desc",
        }
    ]

    markdown = render_daily_report("2026-09-25", [], [], _run_with_single_github_source(), signals)

    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in markdown
    assert "<script>" not in markdown


def test_render_daily_report_escapes_img_onerror_in_summary():
    signals = [
        {
            "source": "github",
            "title": "Repo",
            "url": "https://example.com/repo",
            "summary": "<img src=x onerror=alert(1)>",
        }
    ]

    markdown = render_daily_report("2026-09-25", [], [], _run_with_single_github_source(), signals)

    assert "&lt;img src=x onerror=alert(1)&gt;" in markdown
    assert "<img src=x onerror=alert(1)>" not in markdown


def test_render_daily_report_percent_encodes_angle_bracket_in_url():
    signals = [
        {
            "source": "github",
            "title": "Repo",
            "url": "https://example.com/x>evil",
            "summary": "desc",
        }
    ]

    markdown = render_daily_report("2026-09-25", [], [], _run_with_single_github_source(), signals)

    assert "[Repo](<https://example.com/x%3Eevil>)" in markdown
    assert ">evil" not in markdown


def test_render_daily_report_groups_unknown_source_signals_under_other():
    run = RunMetadata(
        run_id="run-1",
        started_at=datetime(2026, 9, 25, 8, 0, tzinfo=timezone.utc),
        finished_at=datetime(2026, 9, 25, 8, 1, tzinfo=timezone.utc),
        mode="daily",
        since="2026-09-24",
        until="2026-09-25",
        sources=["github"],
        input_counts={"github": 1},
        output_counts={"signals": 2},
        errors=[],
        report_paths=[],
    )
    signals = [
        {
            "source": "github",
            "title": "Repo",
            "url": "https://example.com/repo",
            "summary": "desc",
        },
        {
            "source": "hackernews",
            "title": "Discussion",
            "url": "https://news.ycombinator.com/item?id=1",
            "summary": "desc",
        },
    ]

    markdown = render_daily_report("2026-09-25", [], [], run, signals)

    assert "### github (1件)" in markdown
    assert "### other (1件)" in markdown
    assert markdown.index("### github") < markdown.index("### other")
    assert "Discussion" in markdown


def test_render_daily_report_escapes_preexisting_backslash_before_pipe_in_summary():
    signals = [
        {
            "source": "github",
            "title": "Repo",
            "url": "https://example.com/repo",
            "summary": "a\\|b",
        }
    ]

    markdown = render_daily_report("2026-09-25", [], [], _run_with_single_github_source(), signals)

    assert "| a\\\\\\|b |" in markdown


def test_render_daily_report_does_not_merge_real_other_source_with_unknown_fallback():
    run = RunMetadata(
        run_id="run-1",
        started_at=datetime(2026, 9, 25, 8, 0, tzinfo=timezone.utc),
        finished_at=datetime(2026, 9, 25, 8, 1, tzinfo=timezone.utc),
        mode="daily",
        since="2026-09-24",
        until="2026-09-25",
        sources=["other"],
        input_counts={"other": 1},
        output_counts={"signals": 2},
        errors=[],
        report_paths=[],
    )
    signals = [
        {
            "source": "other",
            "title": "Genuine Other Source Item",
            "url": "https://example.com/genuine",
            "summary": "desc",
        },
        {
            "source": "hackernews",
            "title": "Unknown Source Item",
            "url": "https://news.ycombinator.com/item?id=1",
            "summary": "desc",
        },
    ]

    markdown = render_daily_report("2026-09-25", [], [], run, signals)

    assert "### other (1件)" in markdown
    assert "### _other (1件)" in markdown
    assert "### other (2件)" not in markdown


def _selected_hot() -> HotCandidate:
    return HotCandidate(
        hot_id="hot:event:agent-runtime",
        title="Agent Runtime",
        topic="agent-runtime",
        score=88,
        reasons=["Momentum 96", "Popularity 90"],
        evidence_urls=["https://example.com/agent-runtime", "https://example.com/a|b"],
        source_families=["technology"],
        signals=["github:agent-runtime"],
        selected=True,
    )


def _free_text_proposal(**overrides) -> ArticleProposal:
    fields = dict(
        proposal_id="p1",
        source_hot_id="hot:event:agent-runtime",
        title_idea="Agent Runtimeのガードレールを読み解く",
        article_type="Critical Review",
        target_reader="AI Engineer",
        why_now="Show HNで話題になり、既存手法の2つの課題を同時に解決すると主張している",
        technical_angle="設計要素を既存方式と対比する",
        experiment_plan=["論文を読む", "組み込んで挙動を確認する"],
        competition="日本語記事は未確認",
        traffic_opportunity="検索需要は仮説",
        technical_opportunity="決定論的制御の検証",
        unique_angle="自前検証で裏付ける",
        evidence_links=["https://example.com/agent-runtime"],
        risks=["著者ベンチマークは第三者検証ではない"],
    )
    fields.update(overrides)
    return ArticleProposal(**fields)


def _table_rows(markdown: str) -> list[list[str]]:
    """Group consecutive table lines into tables (header first)."""
    tables: list[list[str]] = []
    current: list[str] = []
    for line in markdown.splitlines():
        if line.startswith("|"):
            current.append(line)
        elif current:
            tables.append(current)
            current = []
    if current:
        tables.append(current)
    return tables


def _unescaped_pipe_count(line: str) -> int:
    count = 0
    index = 0
    while index < len(line):
        if line[index] == "\\":
            index += 2
            continue
        if line[index] == "|":
            count += 1
        index += 1
    return count


def _assert_tables_well_formed(markdown: str) -> None:
    for table in _table_rows(markdown):
        expected = _unescaped_pipe_count(table[0])
        assert len(table) >= 2
        assert set(table[1].replace("|", "").split()) == {"---"}
        for row in table:
            assert _unescaped_pipe_count(row) == expected, row


def test_article_proposals_split_deterministic_why_now_into_labeled_rows():
    from ai_research_radar.ideation.proposals import generate_article_proposals

    hot = _selected_hot()
    proposals = generate_article_proposals(hot, max_proposals=3)

    markdown = render_daily_report("2026-09-25", [hot], proposals, _run_with_single_github_source(), [])
    section = markdown.split("#### Article Proposals")[1].split("## Run Summary")[0]

    assert "| # | 企画タイトル | Type | Role | Critique |" in section
    assert f"| 1 | {proposals[0].title_idea} | Technical Explainer | Explainer | " in section
    assert f"##### 1. {proposals[0].title_idea}" in section
    assert "| Role | Explainer |" in section
    assert "| Critique Score | " in section
    assert "| Critique Notes | ・根拠URLは公開情報に限定されており" in section
    assert "<br>・Source Familyが単一のため" in section
    assert "| Debate | AdvocateはExplainerが技術的な検証価値を示せると主張する<br>Critic" in section
    assert "| Why Now |" not in section
    assert "HOT score 88 with reasons" not in section
    assert "| Experiment Plan | 1. 公式情報を確認<br>2. 主要機能を図解<br>3. 既存技術との差分を表にする |" in section
    _assert_tables_well_formed(markdown)


def test_article_proposals_drop_risks_that_duplicate_critique_and_debate_rows():
    from ai_research_radar.ideation.proposals import generate_article_proposals

    hot = _selected_hot()
    proposal = generate_article_proposals(hot, max_proposals=1)[0]
    extra = replace(proposal, risks=[*proposal.risks, "独自リスク"])

    markdown = render_daily_report("2026-09-25", [hot], [extra], _run_with_single_github_source(), [])

    assert "| Risks | ・独自リスク |" in markdown
    assert "軽量Critique:" not in markdown


def test_article_proposals_show_free_text_why_now_as_is():
    hot = _selected_hot()
    proposal = _free_text_proposal()

    markdown = render_daily_report("2026-09-25", [hot], [proposal], _run_with_single_github_source(), [])

    assert f"| 1 | {proposal.title_idea} | Critical Review | - | - |" in markdown
    assert f"| Why Now | {proposal.why_now} |" in markdown
    assert "\n| Role |" not in markdown
    assert "| Target Reader | AI Engineer |" in markdown
    assert "| Technical Angle | 設計要素を既存方式と対比する |" in markdown
    assert "| Unique Angle | 自前検証で裏付ける |" in markdown
    assert "| Competition | 日本語記事は未確認 |" in markdown
    assert "| Traffic Opportunity | 検索需要は仮説 |" in markdown
    assert "| Technical Opportunity | 決定論的制御の検証 |" in markdown
    assert "| Risks | ・著者ベンチマークは第三者検証ではない |" in markdown
    _assert_tables_well_formed(markdown)


def test_article_proposals_keep_every_evidence_url_as_link():
    hot = _selected_hot()
    proposal = _free_text_proposal(evidence_links=["https://example.com/one", "https://example.com/a|b"])

    markdown = render_daily_report("2026-09-25", [hot], [proposal], _run_with_single_github_source(), [])

    assert (
        "| Evidence | [https://example.com/one](<https://example.com/one>)"
        "<br>[https://example.com/a\\|b](<https://example.com/a%7Cb>) |"
    ) in markdown
    _assert_tables_well_formed(markdown)


def test_article_proposals_escape_pipes_newlines_and_html_in_cells_and_headings():
    hot = _selected_hot()
    proposal = _free_text_proposal(
        title_idea="A | B\n<script>x</script>",
        why_now="line1\nline2 | <b>",
        risks=["r1 | r2"],
    )

    markdown = render_daily_report("2026-09-25", [hot], [proposal], _run_with_single_github_source(), [])

    assert "##### 1. A | B &lt;script&gt;x&lt;/script&gt;" in markdown
    assert "| 1 | A \\| B<br>&lt;script&gt;x&lt;/script&gt; |" in markdown
    assert "| Why Now | line1<br>line2 \\| &lt;b&gt; |" in markdown
    assert "| Risks | ・r1 \\| r2 |" in markdown
    assert "<script>" not in markdown
    _assert_tables_well_formed(markdown)


def test_article_proposals_show_placeholder_for_empty_fields_and_no_proposals():
    hot = _selected_hot()
    proposal = _free_text_proposal(risks=[], experiment_plan=[], competition="")

    with_proposal = render_daily_report("2026-09-25", [hot], [proposal], _run_with_single_github_source(), [])
    without = render_daily_report("2026-09-25", [hot], [], _run_with_single_github_source(), [])

    assert "| Risks | - |" in with_proposal
    assert "| Experiment Plan | - |" in with_proposal
    assert "| Competition | - |" in with_proposal
    assert "記事企画なし" in without
    assert "| # | 企画タイトル |" not in without


def test_article_proposals_point_to_critique_rows_when_all_risks_are_duplicates():
    from ai_research_radar.ideation.proposals import generate_article_proposals

    hot = _selected_hot()
    proposal = generate_article_proposals(hot, max_proposals=1)[0]

    markdown = render_daily_report("2026-09-25", [hot], [proposal], _run_with_single_github_source(), [])

    assert "| Risks | Critique Notes / Debateと同じ内容 |" in markdown


def test_article_proposals_do_not_turn_link_syntax_in_title_into_links():
    hot = _selected_hot()
    proposal = _free_text_proposal(title_idea="[click](https://evil.example) 解説")

    markdown = render_daily_report("2026-09-25", [hot], [proposal], _run_with_single_github_source(), [])

    assert "##### 1. \\[click\\](https://evil.example) 解説" in markdown
    assert "| 1 | \\[click\\](https://evil.example) 解説 |" in markdown
    assert "[click](" not in markdown


def test_article_proposals_escape_trailing_hash_in_heading():
    hot = _selected_hot()
    proposal = _free_text_proposal(title_idea="C #")

    markdown = render_daily_report("2026-09-25", [hot], [proposal], _run_with_single_github_source(), [])

    assert "##### 1. C \\#\n" in markdown


def test_article_proposals_keep_rejected_titles_containing_semicolon_in_one_debate_line():
    from ai_research_radar.ideation.proposals import generate_article_proposals

    hot = replace(_selected_hot(), topic="t; y")
    proposal = generate_article_proposals(hot, max_proposals=1)[0]

    markdown = render_daily_report("2026-09-25", [hot], [proposal], _run_with_single_github_source(), [])
    debate_row = next(line for line in markdown.splitlines() if line.startswith("| Debate |"))

    assert debate_row.count("<br>") == 2
    assert "却下候補: t; yを" in debate_row


def test_article_proposals_treat_string_list_fields_as_single_item():
    hot = _selected_hot()
    proposal = _free_text_proposal(risks="単一のリスク", experiment_plan="単一の手順")

    markdown = render_daily_report("2026-09-25", [hot], [proposal], _run_with_single_github_source(), [])

    assert "| Risks | ・単一のリスク |" in markdown
    assert "| Experiment Plan | 1. 単一の手順 |" in markdown


def test_article_proposals_percent_encode_backslash_and_newline_in_evidence_url():
    hot = _selected_hot()
    proposal = _free_text_proposal(evidence_links=["https://a.example/x\\", "https://a.example/y\nz"])

    markdown = render_daily_report("2026-09-25", [hot], [proposal], _run_with_single_github_source(), [])

    assert "(<https://a.example/x%5C>)" in markdown
    assert "(<https://a.example/y%0Az>)" in markdown
    _assert_tables_well_formed(markdown)


def test_source_appendix_percent_encodes_pipe_backslash_and_newline_in_url():
    signals = [
        {"source": "github", "title": "Repo", "url": "https://example.com/a|b\\c\nd", "summary": "desc"}
    ]

    markdown = render_daily_report("2026-09-25", [], [], _run_with_single_github_source(), signals)

    assert "[Repo](<https://example.com/a%7Cb%5Cc%0Ad>)" in markdown
    _assert_tables_well_formed(markdown)


def _run_summary_run(**overrides) -> RunMetadata:
    values = dict(
        run_id="2026-10-04T02:09:55.419525+00:00",
        started_at=datetime(2026, 10, 4, 2, 9, tzinfo=timezone.utc),
        finished_at=datetime(2026, 10, 4, 2, 10, tzinfo=timezone.utc),
        mode="agent",
        since="2026-10-03T02:09:55.415606+00:00",
        until="2026-10-04T02:09:55.415606+00:00",
        sources=["github", "arxiv"],
        input_counts={"arxiv": 0, "github": 30},
        output_counts={"events": 366, "signals": 395},
        errors=[],
        report_paths=[],
    )
    values.update(overrides)
    return RunMetadata(**values)


def _run_summary(markdown: str) -> str:
    return markdown.split("## Run Summary")[1].split("## Errors")[0]


def test_run_summary_is_rendered_as_key_value_table():
    markdown = render_daily_report(
        "2026-10-04", [], [], _run_summary_run(), [], display_timezone=ZoneInfo("Asia/Tokyo")
    )

    summary = _run_summary(markdown)
    assert "| 項目 | 内容 |" in summary
    assert "| --- | --- |" in summary
    assert "| Run ID | 2026-10-04T02:09:55.419525+00:00 |" in summary
    assert "| Period | 2026-10-03 11:09 〜 2026-10-04 11:09 (JST) |" in summary
    assert "| Sources | github, arxiv |" in summary
    assert "| Input Counts | arxiv: 0, github: 30 |" in summary
    assert "| Output Counts | events: 366, signals: 395 |" in summary
    assert "- Run ID" not in summary
    _assert_tables_well_formed(markdown)


def test_run_summary_period_defaults_to_utc():
    markdown = render_daily_report("2026-10-04", [], [], _run_summary_run(), [])

    assert "| Period | 2026-10-03 02:09 〜 2026-10-04 02:09 (UTC) |" in _run_summary(markdown)


def test_run_summary_period_treats_naive_datetime_as_utc():
    run = _run_summary_run(since="2026-10-03T00:00:00", until="2026-10-04T00:00:00")

    markdown = render_daily_report("2026-10-04", [], [], run, [], display_timezone=ZoneInfo("Asia/Tokyo"))

    assert "| Period | 2026-10-03 09:00 〜 2026-10-04 09:00 (JST) |" in _run_summary(markdown)


def test_run_summary_period_keeps_date_only_and_unparseable_values_as_is():
    date_only = render_daily_report(
        "2026-10-04",
        [],
        [],
        _run_summary_run(since="2026-10-03", until="2026-10-04"),
        [],
        display_timezone=ZoneInfo("Asia/Tokyo"),
    )
    mixed = render_daily_report(
        "2026-10-04",
        [],
        [],
        _run_summary_run(since="not-a-dateTime", until="2026-10-04T02:09:55+00:00"),
        [],
        display_timezone=ZoneInfo("Asia/Tokyo"),
    )

    out_of_range = render_daily_report(
        "2026-10-04",
        [],
        [],
        _run_summary_run(since="0001-01-01T00:00:00", until="2026-10-04T02:09:55+00:00"),
        [],
        display_timezone=ZoneInfo("America/New_York"),
    )

    assert "| Period | 2026-10-03 〜 2026-10-04 |" in _run_summary(date_only)
    assert "| Period | 0001-01-01T00:00:00 〜 2026-10-03 22:09 |" in _run_summary(out_of_range)
    assert "| Period | not-a-dateTime 〜 2026-10-04 11:09 |" in _run_summary(mixed)


def test_run_summary_escapes_cells_and_shows_placeholder_for_empty_values():
    run = _run_summary_run(sources=[], input_counts={}, output_counts={"a|b": 1})

    markdown = render_daily_report("2026-10-04", [], [], run, [])

    summary = _run_summary(markdown)
    assert "| Sources | - |" in summary
    assert "| Input Counts | - |" in summary
    assert "| Output Counts | a\\|b: 1 |" in summary
    _assert_tables_well_formed(markdown)


def _assessed_hot(assessment):
    return HotCandidate(
        hot_id="hot:a", title="Tool A", topic="tool-a", score=90, reasons=["Momentum 90"],
        evidence_urls=["https://example.com/a"], source_families=["technology"], signals=["github:a"],
        selected=True, assessment=assessment, summary="概要",
    )


def _empty_run():
    return RunMetadata(
        run_id="r", started_at=datetime(2026, 10, 5, tzinfo=timezone.utc), finished_at=None, mode="agent",
        since="2026-10-04", until="2026-10-05", sources=[], input_counts={}, output_counts={}, errors=[], report_paths=[],
    )


def _full_assessment(**overrides):
    record = {
        "hot_id": "hot:a", "decision": "selected", "assessed_at": "2026-10-05T01:02:03+00:00", "assessor": "agent-xyz",
        "relevance": {"status": "related", "matched_terms": ["agent", "llm"], "reason": "AIエージェント向けのツール", "method": "agent"},
        "novelty": "初の公式実装", "importance": "利用者が多い", "reader_impact": "導入判断が変わる", "reason": "一次情報で確認できた",
        "evidence": [
            {"url": "https://example.com/release", "checked_at": "2026-10-05T01:00:00+00:00", "target_version": "1.0", "status": "verified", "kind": "primary", "claim": "1.0のリリース", "note": "メモ"},
            {"url": "https://news.example.com/x", "checked_at": "2026-10-05T01:01:00+00:00", "target_version": None, "status": "unverified", "kind": "independent", "claim": "", "note": ""},
        ],
        "unknowns": ["性能は未検証"],
    }
    record.update(overrides)
    return record


def test_selected_hot_shows_assessment_block_without_assessor_or_time():
    markdown = render_daily_report("2026-10-05", [_assessed_hot(_full_assessment())], [], _empty_run(), [])

    assert "- Reasons:\n  - Momentum 90\n- 判断理由: 一次情報で確認できた\n" in markdown
    assert "- 関連性: related(方法: agent / 一致語: agent, llm)\n  - AIエージェント向けのツール\n" in markdown
    assert "- 新規性: 初の公式実装\n- 重要性: 利用者が多い\n- 読者への影響: 導入判断が変わる\n" in markdown
    assert "- 根拠:\n  - [https://example.com/release](<https://example.com/release>)(verified / primary):1.0のリリース\n" in markdown
    assert "  - [https://news.example.com/x](<https://news.example.com/x>)(unverified / independent):(主張未記載)\n" in markdown
    assert "- 未確認事項:\n  - 性能は未検証\n" in markdown
    assert "agent-xyz" not in markdown
    assert "2026-10-05T01:02:03" not in markdown
    assert markdown.index("- 未確認事項:") < markdown.index("#### Article Proposals")


def test_selected_hot_shows_none_for_empty_lists():
    markdown = render_daily_report("2026-10-05", [_assessed_hot(_full_assessment(evidence=[], unknowns=[], relevance={"status": "uncertain", "matched_terms": [], "reason": "r", "method": "keyword"}))], [], _empty_run(), [])

    assert "- 関連性: uncertain(方法: keyword / 一致語: なし)" in markdown
    assert "- 根拠: なし" in markdown
    assert "- 未確認事項: なし" in markdown


def test_legacy_candidate_without_assessment_shows_only_reasons():
    markdown = render_daily_report("2026-10-05", [_assessed_hot(None)], [], _empty_run(), [])

    assert "- Reasons:\n  - Momentum 90\n\n#### Article Proposals" in markdown
    assert "判断理由" not in markdown


def test_assessment_text_escapes_markdown_block_markers_and_html():
    markdown = render_daily_report("2026-10-05", [_assessed_hot(_full_assessment(unknowns=["# 見出し", "1. 番号", "- 箇条", "<b>x</b> | y\n次の行"]))], [], _empty_run(), [])

    assert "  - \\# 見出し\n" in markdown
    assert "  - 1\\. 番号\n" in markdown
    assert "  - \\- 箇条\n" in markdown
    assert "  - &lt;b&gt;x&lt;/b&gt; \\| y 次の行\n" in markdown


def test_malformed_assessment_does_not_break_report():
    broken = {"reason": 1, "relevance": "related", "evidence": [None, "x", {"url": None}], "unknowns": "not a list"}

    markdown = render_daily_report("2026-10-05", [_assessed_hot(broken)], [], _empty_run(), [])

    assert "- 関連性: 記録なし" in markdown
    assert "  - (URL未記載)( / ):(主張未記載)" in markdown
    assert "- 未確認事項: なし" in markdown
    assert render_daily_report("2026-10-05", [_assessed_hot("not a dict")], [], _empty_run(), []).count("判断理由") == 0


def test_assessment_text_escapes_thematic_breaks_and_code_fences():
    texts = ["---", "***", "___", "```python", "~~~", "+ 加算", "1) 番号", "=== x"]
    markdown = render_daily_report("2026-10-05", [_assessed_hot(_full_assessment(unknowns=texts))], [], _empty_run(), [])

    for expected in ["\\---", "\\***", "\\___", "\\```python", "\\~~~", "\\+ 加算", "1\\) 番号", "\\=== x"]:
        assert f"  - {expected}\n" in markdown


def test_assessment_shows_placeholder_for_empty_text_fields():
    record = _full_assessment(reason="", novelty=" ", importance=None, reader_impact="")
    markdown = render_daily_report("2026-10-05", [_assessed_hot(record)], [], _empty_run(), [])

    assert "- 判断理由: (未記載)\n" in markdown
    assert "- 新規性: (未記載)\n- 重要性: (未記載)\n- 読者への影響: (未記載)\n" in markdown


def test_relevance_without_reason_or_list_terms_shows_single_line():
    relevance = {"status": "related", "matched_terms": "llm", "reason": "", "method": "agent"}
    markdown = render_daily_report("2026-10-05", [_assessed_hot(_full_assessment(relevance=relevance))], [], _empty_run(), [])

    assert "- 関連性: related(方法: agent / 一致語: なし)\n- 新規性:" in markdown


DEFERRED = {"status": "deferred", "reason": "一次情報を確認できなかった", "candidate_count": 10, "screened_count": 8, "unreviewed_count": 2, "selected_count": 0}
COMPLETED = {"status": "completed", "reason": "Aを確認した", "candidate_count": 2, "screened_count": 2, "unreviewed_count": 0, "selected_count": 1}
NOT_RUN = {"status": "not_run", "reason": "未実行"}


def _stage_run(select_hot=None, save_proposals=None) -> RunMetadata:
    results = {}
    if select_hot is not None:
        results["select-hot"] = select_hot
    if save_proposals is not None:
        results["save-proposals"] = save_proposals
    return _run_summary_run(stage_results=results)


def _selected_section(markdown: str) -> str:
    return markdown.split("## 選抜HOT")[1].split("## 注目候補(選抜外)")[0]


def test_selection_without_record_keeps_legacy_message():
    markdown = render_daily_report("2026-10-04", [], [], _stage_run(), [])

    assert "本日の選抜HOTはありません。" in _selected_section(markdown)


def test_selection_deferred_shows_reason_and_scope():
    markdown = render_daily_report("2026-10-04", [], [], _stage_run(DEFERRED, {"status": "not_run", "reason": "選抜HOTなし", "proposal_count": 0}), [])

    section = _selected_section(markdown)
    assert "本日の選抜HOTはありません(保留: 一次情報を確認できなかった。候補 10件中 8件を確認、未確認 2件)。" in section
    assert "記事企画" not in section


def test_selection_deferred_on_a_day_without_candidates_is_short():
    result = {"status": "deferred", "reason": "候補なし", "candidate_count": 0, "screened_count": 0, "unreviewed_count": 0, "selected_count": 0}

    markdown = render_daily_report("2026-10-04", [], [], _stage_run(result), [])

    assert "本日の選抜HOTはありません(保留: 候補なし。候補0件)。" in _selected_section(markdown)


def test_selection_deferred_drops_trailing_period_of_reason():
    markdown = render_daily_report("2026-10-04", [], [], _stage_run(dict(DEFERRED, reason="確認できなかった。")), [])

    assert "(保留: 確認できなかった。候補 10件中" in _selected_section(markdown)


def test_selection_deferred_escapes_agent_reason():
    result = dict(DEFERRED, reason="# 見出し\n次の行")

    markdown = render_daily_report("2026-10-04", [], [], _stage_run(result), [])

    assert "(保留: \\# 見出し 次の行。" in _selected_section(markdown)


def test_selection_not_run_omits_default_reason():
    markdown = render_daily_report("2026-10-04", [], [], _stage_run(NOT_RUN), [])

    section = _selected_section(markdown)
    assert "選抜は未実行。" in section
    assert "本日の選抜HOTはありません" not in section


def test_selection_failed_with_previous_selection_shows_notice_and_results():
    failed = {"status": "failed", "reason": "invalid_assessment: x"}

    markdown = render_daily_report("2026-10-04", [_assessed_hot(None)], [], _stage_run(failed), [])

    section = _selected_section(markdown)
    assert "選抜は失敗(invalid_assessment: x)。以下は前回成功時の結果です。" in section
    assert "### Tool A" in section


def test_selection_failed_without_previous_selection_has_no_previous_notice():
    markdown = render_daily_report("2026-10-04", [], [], _stage_run({"status": "failed", "reason": "invalid_input: bad"}), [])

    section = _selected_section(markdown)
    assert "選抜は失敗(invalid_input: bad)。" in section
    assert "以下は前回" not in section


def test_selection_completed_without_selected_hot_points_to_rescoring():
    markdown = render_daily_report("2026-10-04", [], [], _stage_run(COMPLETED), [])

    assert "選抜結果が見つかりません(score の再実行などで選抜が消えた可能性があります)。" in _selected_section(markdown)


def test_selection_completed_with_selected_hot_has_no_status_line():
    markdown = render_daily_report("2026-10-04", [_assessed_hot(None)], [], _stage_run(COMPLETED), [])

    section = _selected_section(markdown)
    assert "本日の選抜HOT" not in section
    assert "選抜は" not in section
    assert "### Tool A" in section


def test_invalid_stage_records_are_treated_as_missing():
    run = _run_summary_run(stage_results={"select-hot": {"status": "weird"}, "save-proposals": "broken"})

    markdown = render_daily_report("2026-10-04", [], [], run, [])

    assert "本日の選抜HOTはありません。" in _selected_section(markdown)


def test_selection_deferred_with_invalid_counts_shows_question_marks():
    result = dict(DEFERRED, candidate_count="x", screened_count=True)

    markdown = render_daily_report("2026-10-04", [], [], _stage_run(result), [])

    assert "候補 ?件中 ?件を確認" in _selected_section(markdown)


def test_selection_not_run_with_custom_reason_shows_it():
    markdown = render_daily_report("2026-10-04", [], [], _stage_run({"status": "not_run", "reason": "選抜の再実行により無効"}), [])

    assert "選抜は未実行(選抜の再実行により無効)。" in _selected_section(markdown)


def _proposal(hot_id: str) -> ArticleProposal:
    return ArticleProposal(
        proposal_id=f"{hot_id}:p1", source_hot_id=hot_id, title_idea="企画", article_type="Hands-on",
        target_reader="AI Engineer", why_now="今", technical_angle="t", experiment_plan=["e"], competition="Low",
        traffic_opportunity="High", technical_opportunity="High", unique_angle="u",
        evidence_links=["https://example.com/a"], risks=["r"],
    )


def _hot_b() -> HotCandidate:
    return replace(_assessed_hot(None), hot_id="hot:b", title="Tool B")


def test_deferred_proposals_show_reason_placeholder_for_hot_without_proposals():
    deferred = {"status": "deferred", "reason": "", "proposal_count": 0}

    markdown = render_daily_report("2026-10-04", [_assessed_hot(None)], [], _stage_run(COMPLETED, deferred), [])

    assert "記事企画なし(保留: 理由未記載)" in _selected_section(markdown)


def test_deferred_proposals_show_escaped_reason():
    deferred = {"status": "deferred", "reason": "- 検証環境がない", "proposal_count": 0}

    markdown = render_daily_report("2026-10-04", [_assessed_hot(None)], [], _stage_run(COMPLETED, deferred), [])

    assert "記事企画なし(保留: \\- 検証環境がない)" in _selected_section(markdown)


def test_completed_proposals_keep_plain_message_for_hot_without_proposals():
    completed = {"status": "completed", "reason": "", "proposal_count": 1}
    hots = [_assessed_hot(None), _hot_b()]

    markdown = render_daily_report("2026-10-04", hots, [_proposal("hot:a")], _stage_run(COMPLETED, completed), [])

    section = _selected_section(markdown)
    assert "記事企画なし\n" in section
    assert "保留" not in section


def test_invalidated_proposals_show_notice_and_previous_proposals():
    invalidated = {"status": "not_run", "reason": "選抜の再実行により無効"}

    markdown = render_daily_report("2026-10-04", [_assessed_hot(None)], [_proposal("hot:a")], _stage_run(COMPLETED, invalidated), [])

    section = _selected_section(markdown)
    assert "記事企画は未実行(選抜の再実行により無効)。表示中の企画は前回の結果です。" in section
    assert section.index("記事企画は未実行") < section.index("### Tool A")


def test_failed_proposals_without_previous_proposals_show_failure_only():
    failed = {"status": "failed", "reason": "invalid_proposal: x"}

    markdown = render_daily_report("2026-10-04", [_assessed_hot(None)], [], _stage_run(COMPLETED, failed), [])

    section = _selected_section(markdown)
    assert "記事企画の保存は失敗(invalid_proposal: x)。" in section
    assert "前回の結果" not in section


def test_not_run_proposals_omit_default_reason():
    markdown = render_daily_report("2026-10-04", [_assessed_hot(None)], [], _stage_run(COMPLETED, NOT_RUN), [])

    assert "記事企画は未実行。" in _selected_section(markdown)


def test_missing_proposals_record_keeps_legacy_display():
    markdown = render_daily_report("2026-10-04", [_assessed_hot(None)], [], _stage_run(COMPLETED), [])

    section = _selected_section(markdown)
    assert "記事企画は" not in section
    assert "記事企画なし\n" in section
