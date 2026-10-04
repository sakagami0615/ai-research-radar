import json
from pathlib import Path

from ai_research_radar.cli.commands.run_state import save_run_state
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
    assert (
        main(
            [
                "select-hot",
                "--date",
                "2026-09-25",
                "--data-dir",
                str(data_dir),
                "--select",
                first_id,
            ]
        )
        == 0
    )

    proposal = {
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
    }
    input_path = tmp_path / "proposals.json"
    input_path.write_text(json.dumps([proposal], ensure_ascii=False), encoding="utf-8")
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
