from dataclasses import replace
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
