import json
from pathlib import Path

from ai_research_radar.storage.run_state import save_run_state
from ai_research_radar.cli.main import main
from ai_research_radar.sources.fixtures import FixtureAdapter
from ai_research_radar.storage.jsonl import read_jsonl


def _write_scoring_config(tmp_path: Path) -> Path:
    path = tmp_path / "scoring.yaml"
    path.write_text(
        "hot_score:\n"
        "  momentum: 0.40\n"
        "  popularity: 0.25\n"
        "  cross_source: 0.20\n"
        "  credibility: 0.15\n"
        "hot_selection:\n"
        "  max_limit: 5\n"
        "  minimum_score: 0\n",
        encoding="utf-8",
    )
    return path


def _run_full_pipeline(tmp_path: Path, monkeypatch) -> Path:
    import ai_research_radar.cli.commands.collect as collect_command

    monkeypatch.setattr(
        collect_command,
        "build_adapters",
        lambda configs: [
            FixtureAdapter(
                source_name="github",
                source_family="technology",
                fixture_path=Path("tests/fixtures/sample_raw_items.jsonl"),
            )
        ],
    )
    data_dir = tmp_path / "data"
    reports_dir = tmp_path / "reports"
    scoring_config = _write_scoring_config(tmp_path)

    assert (
        main(
            [
                "collect",
                "--since",
                "2026-09-24",
                "--until",
                "2026-09-25",
                "--data-dir",
                str(data_dir),
                "--sources-config",
                "config/sources.yaml",
            ]
        )
        == 0
    )
    assert main(["normalize", "--date", "2026-09-25", "--data-dir", str(data_dir)]) == 0
    assert (
        main(
            [
                "score",
                "--date",
                "2026-09-25",
                "--data-dir",
                str(data_dir),
                "--scoring-config",
                str(scoring_config),
            ]
        )
        == 0
    )

    candidates = read_jsonl(data_dir / "runs" / "2026-09-25" / "hot_candidates.jsonl")
    first_id = candidates[0]["hot_id"]
    run_dir = data_dir / "runs" / "2026-09-25"
    selection = {
        "assessments": [
            {
                "hot_id": candidate["hot_id"],
                "decision": "selected" if candidate["hot_id"] == first_id else "rejected",
                "assessed_at": "2026-09-25T01:00:00+00:00",
                "assessor": "agent",
                "relevance": {"status": "related", "matched_terms": [], "reason": "テスト", "method": "agent"},
                "novelty": "テスト",
                "importance": "テスト",
                "reader_impact": "テスト",
                "reason": "テスト",
                "evidence": [
                    {
                        "url": "https://example.com/release",
                        "checked_at": "2026-09-25T00:59:00+00:00",
                        "target_version": None,
                        "status": "verified",
                        "kind": "primary",
                        "claim": "テスト",
                        "note": "",
                    }
                ],
                "unknowns": [],
            }
            for candidate in candidates
        ],
        "screened_ids": [candidate["hot_id"] for candidate in candidates],
        "selection_reason": "テスト",
        "summaries": {candidate["hot_id"]: "テスト概要" for candidate in candidates},
    }
    (run_dir / "selection_input.json").write_text(json.dumps(selection, ensure_ascii=False), encoding="utf-8")
    assert main(["select-hot", "--date", "2026-09-25", "--data-dir", str(data_dir), "--limit", "5"]) == 0

    proposal = {
        "schema_version": 2,
        "proposal_id": f"{first_id}:proposal:1",
        "source_hot_id": first_id,
        "title_idea": "テスト企画",
        "article_type": "Hands-on",
        "target_reader": "AI Engineer",
        "why_now": "テスト",
        "technical_angle": "テスト",
        "experiment_plan": ["セットアップ"],
        "competition": "Low",
        "traffic_opportunity": "High",
        "technical_opportunity": "High",
        "unique_angle": "テスト",
        "evidence_links": candidates[0]["evidence_urls"],
        "risks": ["テスト"],
        "quality": {
            "question": "テストの問い",
            "difference": "テスト",
            "baseline": "テスト",
            "baseline_version": "1.0",
            "measurement": "テスト",
            "inputs_and_environment": "テスト",
            "effort": "1日",
            "effort_assumptions": "テスト",
            "success_condition": "テスト",
            "stop_condition": "テスト",
            "metrics": ["テスト"],
            "evidence": [],
            "unknowns": [],
        },
    }
    input_path = tmp_path / "proposals.json"
    input_path.write_text(json.dumps({"schema_version": 2, "proposals": [proposal]}, ensure_ascii=False), encoding="utf-8")
    assert (
        main(
            [
                "save-proposals",
                "--date",
                "2026-09-25",
                "--data-dir",
                str(data_dir),
                "--input",
                str(input_path),
            ]
        )
        == 0
    )

    return reports_dir


def test_cli_report_renders_markdown_after_full_pipeline(tmp_path: Path, monkeypatch):
    reports_dir = _run_full_pipeline(tmp_path, monkeypatch)
    data_dir = tmp_path / "data"

    exit_code = main(
        [
            "report",
            "--date",
            "2026-09-25",
            "--data-dir",
            str(data_dir),
            "--reports-dir",
            str(reports_dir),
        ]
    )

    assert exit_code == 0
    report_path = reports_dir / "daily" / "2026-09-25.md"
    assert report_path.exists()
    report_text = report_path.read_text(encoding="utf-8")
    assert "AI Daily Radar 2026-09-25" in report_text
    assert "## 注目候補(選抜外)" in report_text
    assert "## 新モデルリリース" in report_text
    assert "| 検証の問い | テストの問い |" in report_text
    assert "旧形式のため未評価" not in report_text
    assert (data_dir / "runs" / "2026-09-25" / "report_digest.json").exists()

    run = read_jsonl(data_dir / "runs" / "2026-09-25" / "run.jsonl")[0]
    assert run["mode"] == "agent"
    assert run["errors"] == []
    assert run["report_paths"] == [str(report_path)]


def test_cli_report_records_missing_stages_but_still_writes_report(tmp_path: Path):
    data_dir = tmp_path / "data"
    reports_dir = tmp_path / "reports"

    exit_code = main(
        [
            "report",
            "--date",
            "2026-09-25",
            "--data-dir",
            str(data_dir),
            "--reports-dir",
            str(reports_dir),
        ]
    )

    assert exit_code == 0
    run = read_jsonl(data_dir / "runs" / "2026-09-25" / "run.jsonl")[0]
    missing_stage_types = {error["type"] for error in run["errors"]}
    assert "missing_stage" in missing_stage_types
    assert (reports_dir / "daily" / "2026-09-25.md").exists()


def test_cli_report_persists_run_state_when_markdown_write_fails(tmp_path: Path, monkeypatch):
    reports_dir = tmp_path / "reports"
    reports_dir.write_text("not a directory", encoding="utf-8")
    data_dir = tmp_path / "data"

    exit_code = main(
        [
            "report",
            "--date",
            "2026-09-25",
            "--data-dir",
            str(data_dir),
            "--reports-dir",
            str(reports_dir),
        ]
    )

    assert exit_code == 1
    run = read_jsonl(data_dir / "runs" / "2026-09-25" / "run.jsonl")[0]
    assert run["report_paths"] == []
    assert any(error["type"] == "report_write_error" for error in run["errors"])


def test_cli_report_includes_source_appendix_from_normalized_signals(tmp_path: Path, monkeypatch):
    reports_dir = _run_full_pipeline(tmp_path, monkeypatch)
    data_dir = tmp_path / "data"

    exit_code = main(
        [
            "report",
            "--date",
            "2026-09-25",
            "--data-dir",
            str(data_dir),
            "--reports-dir",
            str(reports_dir),
        ]
    )

    assert exit_code == 0
    report_text = (reports_dir / "daily" / "2026-09-25.md").read_text(encoding="utf-8")
    assert "## 収集Source一覧" in report_text
    assert "### github (1件)" in report_text
    assert "### other (1件)" in report_text


def _write_iso_period_run_state(data_dir: Path) -> None:
    save_run_state(
        data_dir,
        "2026-10-04",
        {
            "run_id": "2026-10-04T02:09:55.419525+00:00",
            "since": "2026-10-03T02:09:55+00:00",
            "until": "2026-10-04T02:09:55+00:00",
            "sources": ["github"],
            "stages_completed": [],
            "input_counts": {"github": 1},
            "output_counts": {},
            "errors": [],
        },
    )


def _report_period_row(tmp_path: Path, extra_args: list[str]) -> str:
    data_dir = tmp_path / "data"
    reports_dir = tmp_path / "reports"
    _write_iso_period_run_state(data_dir)

    exit_code = main(
        ["report", "--date", "2026-10-04", "--data-dir", str(data_dir), "--reports-dir", str(reports_dir)]
        + extra_args
    )

    assert exit_code == 0
    report_text = (reports_dir / "daily" / "2026-10-04.md").read_text(encoding="utf-8")
    return next(line for line in report_text.splitlines() if line.startswith("| Period |"))


def test_cli_report_shows_period_in_runtime_config_timezone(tmp_path: Path):
    runtime_config = tmp_path / "runtime.yaml"
    runtime_config.write_text("runtime:\n  timezone: Asia/Tokyo\n", encoding="utf-8")

    row = _report_period_row(tmp_path, ["--runtime-config", str(runtime_config)])

    assert row == "| Period | 2026-10-03 11:09 〜 2026-10-04 11:09 (JST) |"


def test_cli_report_defaults_to_runtime_config_in_working_directory(tmp_path: Path, monkeypatch):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "runtime.yaml").write_text("runtime:\n  timezone: Asia/Tokyo\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    row = _report_period_row(tmp_path, [])

    assert row == "| Period | 2026-10-03 11:09 〜 2026-10-04 11:09 (JST) |"


def test_cli_report_falls_back_to_utc_when_runtime_config_is_missing(tmp_path: Path):
    row = _report_period_row(tmp_path, ["--runtime-config", str(tmp_path / "missing.yaml")])

    assert row == "| Period | 2026-10-03 02:09 〜 2026-10-04 02:09 (UTC) |"


def test_cli_report_falls_back_to_utc_when_runtime_config_is_broken(tmp_path: Path):
    runtime_config = tmp_path / "runtime.yaml"
    runtime_config.write_text("runtime: [unclosed\n", encoding="utf-8")

    row = _report_period_row(tmp_path, ["--runtime-config", str(runtime_config)])

    assert row == "| Period | 2026-10-03 02:09 〜 2026-10-04 02:09 (UTC) |"


def test_cli_report_lists_missing_summaries_without_writing_anything(tmp_path: Path, capsys):
    from ai_research_radar.reporting.digest import save_digest_summaries
    from ai_research_radar.schemas.models import HotCandidate
    from ai_research_radar.storage.jsonl import write_jsonl

    data_dir = tmp_path / "data"
    reports_dir = tmp_path / "reports"
    write_jsonl(
        data_dir / "runs" / "2026-09-25" / "hot_candidates.jsonl",
        [
            HotCandidate("hot:a", "A", "a", 80.0, [], ["https://example.com/a"], ["technology"], ["pypi:a"], False),
            HotCandidate("hot:b", "B", "b", 79.0, [], ["https://example.com/b"], ["technology"], ["pypi:b"], False, summary="概要あり"),
            HotCandidate("hot:c", "C", "c", 78.0, [], ["https://example.com/c"], ["technology"], ["pypi:c"], False),
        ],
    )
    write_jsonl(
        data_dir / "normalized" / "2026-09-25" / "signals.jsonl",
        [
            {
                "signal_id": f"huggingface_orgs:org/{name}",
                "source": "huggingface_orgs",
                "source_family": "technology",
                "content_type": "model",
                "title": f"org/{name}",
                "url": f"https://huggingface.co/org/{name}",
                "published_at": "2026-09-25T00:00:00+00:00",
                "fetched_at": "2026-09-25T00:00:00+00:00",
                "summary": "",
                "categories": [],
                "raw_metrics": {},
                "normalized_scores": {},
                "metadata": {"model_release": {"provider": "Org", "channel": "huggingface"}},
            }
            for name in ("m1", "m2")
        ],
    )
    save_digest_summaries(data_dir, "2026-09-25", {"hot:c": "補完した概要", "https://huggingface.co/org/m2": "補完した概要"})

    exit_code = main(
        [
            "report",
            "--date",
            "2026-09-25",
            "--data-dir",
            str(data_dir),
            "--reports-dir",
            str(reports_dir),
            "--list-missing-summaries",
        ]
    )

    assert exit_code == 0
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line]
    assert lines == [
        {"kind": "notable", "hot_id": "hot:a", "title": "A", "first_seen": "2026-09-25", "evidence_urls": ["https://example.com/a"]},
        {
            "kind": "model_release",
            "key": "https://huggingface.co/org/m1",
            "title": "org/m1",
            "provider": "Org",
            "channel": "huggingface",
            "url": "https://huggingface.co/org/m1",
            "first_seen": "2026-09-25",
        },
    ]
    assert not reports_dir.exists()
    run_dir = data_dir / "runs" / "2026-09-25"
    before = {path.name: path.read_bytes() for path in run_dir.iterdir()}
    assert main(["report", "--date", "2026-09-25", "--data-dir", str(data_dir), "--list-missing-summaries"]) == 0
    assert {path.name: path.read_bytes() for path in run_dir.iterdir()} == before
    assert "report_digest.json" not in before


def _report(tmp_path: Path, date: str) -> tuple[dict, str]:
    data_dir = tmp_path / "data"
    reports_dir = tmp_path / "reports"
    assert main(["report", "--date", date, "--data-dir", str(data_dir), "--reports-dir", str(reports_dir)]) == 0
    run = read_jsonl(data_dir / "runs" / date / "run.jsonl")[0]
    return run, (reports_dir / "daily" / f"{date}.md").read_text(encoding="utf-8")


def test_cli_report_passes_stage_results_to_run_jsonl_and_report(tmp_path: Path):
    deferred = {"status": "deferred", "reason": "未確認", "candidate_count": 3, "screened_count": 3, "unreviewed_count": 0, "selected_count": 0}
    save_run_state(
        tmp_path / "data",
        "2026-10-04",
        {
            "run_id": "2026-10-04T02:09:55.419525+00:00",
            "stages_completed": ["collect", "normalize", "score", "select-hot", "save-proposals"],
            "errors": [],
            "stage_results": {"select-hot": deferred, "save-proposals": {"status": "not_run", "reason": "選抜HOTなし", "proposal_count": 0}},
        },
    )

    run, report_text = _report(tmp_path, "2026-10-04")

    assert run["stage_results"] == {
        "select-hot": deferred,
        "save-proposals": {"status": "not_run", "reason": "選抜HOTなし", "proposal_count": 0},
    }
    assert "| Selection | deferred(候補3件 / 確認3件 / 未確認0件 / 選抜0件) |" in report_text


def test_cli_report_does_not_fill_stage_results_for_old_run_state(tmp_path: Path):
    _write_iso_period_run_state(tmp_path / "data")

    run, report_text = _report(tmp_path, "2026-10-04")

    assert run["stage_results"] == {}
    state = json.loads((tmp_path / "data" / "runs" / "2026-10-04" / "run_state.json").read_text(encoding="utf-8"))
    assert "stage_results" not in state
    assert "| Selection | 記録なし |" in report_text


def test_cli_report_carries_stage_results_when_markdown_write_fails(tmp_path: Path):
    data_dir = tmp_path / "data"
    stage_results = {
        "select-hot": {"status": "completed", "candidate_count": 3, "screened_count": 3, "unreviewed_count": 0, "selected_count": 1},
    }
    save_run_state(
        data_dir,
        "2026-09-25",
        {"run_id": "2026-09-25T02:09:55.419525+00:00", "stages_completed": ["select-hot"], "errors": [], "stage_results": stage_results},
    )
    reports_dir = tmp_path / "reports"
    reports_dir.write_text("not a directory", encoding="utf-8")

    exit_code = main(["report", "--date", "2026-09-25", "--data-dir", str(data_dir), "--reports-dir", str(reports_dir)])

    assert exit_code == 1
    run = read_jsonl(data_dir / "runs" / "2026-09-25" / "run.jsonl")[0]
    assert any(error["type"] == "report_write_error" for error in run["errors"])
    assert run["stage_results"] == stage_results


def test_cli_report_writes_not_run_stage_results_for_new_date(tmp_path: Path):
    run, _ = _report(tmp_path, "2026-10-05")

    assert run["stage_results"] == {
        "select-hot": {"status": "not_run", "reason": "未実行"},
        "save-proposals": {"status": "not_run", "reason": "未実行"},
    }


def _write_source_overview_run(data_dir: Path, date: str) -> None:
    from ai_research_radar.storage.jsonl import write_jsonl

    save_run_state(
        data_dir,
        date,
        {
            "run_id": f"{date}T00:00:00+00:00",
            "since": date,
            "until": date,
            "sources": ["github", "arxiv"],
            "stages_completed": [],
            "input_counts": {"github": 1},
            "output_counts": {},
            "errors": [],
        },
    )
    write_jsonl(
        data_dir / "normalized" / date / "signals.jsonl",
        [{"source": "github", "title": "Repo", "url": "https://example.com/repo", "summary": "desc"}],
    )


def test_cli_report_shows_source_overviews_saved_by_add_source_overview(tmp_path: Path):
    data_dir = tmp_path / "data"
    _write_source_overview_run(data_dir, "2026-10-04")
    overview_input = tmp_path / "source_overview_input.json"
    overview_input.write_text(json.dumps({"github": "エージェント系が多い。"}, ensure_ascii=False), encoding="utf-8")
    assert main(["add-source-overview", "--date", "2026-10-04", "--data-dir", str(data_dir), "--input", str(overview_input)]) == 0

    _, report_text = _report(tmp_path, "2026-10-04")

    assert "### github (1件)\n\nエージェント系が多い。\n\n<details>" in report_text
    assert "### arxiv (0件)\n\n収集0件\n\n<details>" in report_text


def test_cli_report_warns_and_shows_placeholder_when_source_overviews_are_broken(tmp_path: Path):
    data_dir = tmp_path / "data"
    _write_source_overview_run(data_dir, "2026-10-04")
    (data_dir / "runs" / "2026-10-04" / "source_overviews.json").write_text("{broken", encoding="utf-8")

    _, report_text = _report(tmp_path, "2026-10-04")

    assert "> ⚠️ 次のファイルを読めなかったため、本日の傾向を表示していません。" in report_text
    assert "source_overviews.json" in report_text
    assert "### github (1件)\n\n傾向未作成\n\n<details>" in report_text


def test_cli_report_shows_only_the_note_without_overviews_when_signals_are_broken(tmp_path: Path):
    data_dir = tmp_path / "data"
    _write_source_overview_run(data_dir, "2026-10-04")
    overview_input = tmp_path / "source_overview_input.json"
    overview_input.write_text(json.dumps({"github": "エージェント系が多い。"}, ensure_ascii=False), encoding="utf-8")
    assert main(["add-source-overview", "--date", "2026-10-04", "--data-dir", str(data_dir), "--input", str(overview_input)]) == 0
    (data_dir / "normalized" / "2026-10-04" / "signals.jsonl").write_text("{broken\n", encoding="utf-8")

    run, report_text = _report(tmp_path, "2026-10-04")

    appendix = report_text[report_text.index("## 収集Source一覧") :]
    assert "signals.jsonl を読めなかったため表示できません(Errors を参照)。" in appendix
    assert "### github" not in appendix
    assert "エージェント系が多い。" not in appendix
    assert "傾向未作成" not in appendix
    assert any(error["source"] == "report" and error["type"] == "corrupt_input" for error in run["errors"])


def test_cli_report_marks_legacy_proposals_as_unevaluated(tmp_path: Path, monkeypatch):
    reports_dir = _run_full_pipeline(tmp_path, monkeypatch)
    data_dir = tmp_path / "data"
    proposals_path = data_dir / "runs" / "2026-09-25" / "article_proposals.jsonl"
    # A proposal saved before #11 (no schema_version / quality) must still be readable.
    legacy = read_jsonl(proposals_path)[0]
    del legacy["schema_version"], legacy["quality"]
    proposals_path.write_text(json.dumps(legacy, ensure_ascii=False) + "\n", encoding="utf-8")

    assert main(["report", "--date", "2026-09-25", "--data-dir", str(data_dir), "--reports-dir", str(reports_dir)]) == 0

    report_text = (reports_dir / "daily" / "2026-09-25.md").read_text(encoding="utf-8")
    assert "| 品質評価 | 旧形式のため未評価 |" in report_text
    assert "検証の問い" not in report_text
