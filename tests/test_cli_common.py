import json
from pathlib import Path

import pytest

import ai_research_radar.cli.commands.collect as collect_command
import ai_research_radar.cli.commands.daily as daily_command
from ai_research_radar.cli.main import main
from ai_research_radar.sources.fixtures import FixtureAdapter
from ai_research_radar.storage.run_state import load_run_state, run_state_path, save_run_state

DATE = "2026-10-09"


def _report(data_dir: Path, reports_dir: Path) -> str:
    assert main(["report", "--date", DATE, "--data-dir", str(data_dir), "--reports-dir", str(reports_dir)]) == 0
    return (reports_dir / "daily" / f"{DATE}.md").read_text(encoding="utf-8")


def _fixture_adapters(configs):
    return [FixtureAdapter("github", "technology", Path("tests/fixtures/sample_raw_items.jsonl").resolve())]


# --- mark-needs-review / banner ---


def test_mark_needs_review_records_flag_and_report_shows_banner_on_every_generation(tmp_path: Path):
    data_dir, reports_dir = tmp_path / "data", tmp_path / "reports"
    save_run_state(data_dir, DATE, load_run_state(data_dir, DATE))
    assert "要確認" not in _report(data_dir, reports_dir)

    assert main(["mark-needs-review", "--date", DATE, "--data-dir", str(data_dir)]) == 0

    assert load_run_state(data_dir, DATE)["needs_review"] is True
    banner = f"> ⚠️ **要確認**: 自動レビューで解消できなかった指摘があります。`{data_dir}/runs/{DATE}/review_feedback.md` を確認してください。"
    first = _report(data_dir, reports_dir)
    assert first.splitlines()[:3] == [f"# AI Daily Radar {DATE}", "", banner]
    assert banner in _report(data_dir, reports_dir)


def test_mark_needs_review_fails_without_run_state_of_the_date(tmp_path: Path):
    data_dir = tmp_path / "data"

    assert main(["mark-needs-review", "--date", DATE, "--data-dir", str(data_dir)]) == 1

    assert not run_state_path(data_dir, DATE).exists()


def test_collect_clears_needs_review(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(collect_command, "build_adapters", _fixture_adapters)
    data_dir = tmp_path / "data"
    state = load_run_state(data_dir, "2026-09-25")
    state["needs_review"] = True
    save_run_state(data_dir, "2026-09-25", state)

    assert main(["collect", "--since", "2026-09-24", "--until", "2026-09-25", "--data-dir", str(data_dir)]) == 0

    assert "needs_review" not in load_run_state(data_dir, "2026-09-25")


# --- broken run_state.json ---


@pytest.mark.parametrize("content", [b"{broken", b"\xff\xfe{", b"[]"], ids=["json", "utf8", "not-object"])
def test_broken_run_state_ends_with_message_instead_of_traceback(tmp_path: Path, capsys, content: bytes):
    data_dir = tmp_path / "data"
    path = run_state_path(data_dir, DATE)
    path.parent.mkdir(parents=True)
    path.write_bytes(content)

    assert main(["mark-needs-review", "--date", DATE, "--data-dir", str(data_dir)]) == 1

    err = capsys.readouterr().err
    assert err.startswith("error: ") and "run_state.json" in err
    assert path.read_bytes() == content


# --- default directories from runtime.yaml ---


def _runtime(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "runtime.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_subcommands_default_to_output_dirs_of_runtime_config(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(collect_command, "build_adapters", _fixture_adapters)
    runtime = _runtime(tmp_path, "output:\n  data_dir: custom_data\n  reports_dir: custom_reports\n")
    config = ["--runtime-config", str(runtime)]
    sources = ["--sources-config", str(Path(__file__).resolve().parents[1] / "config" / "sources.yaml")]

    assert main(["collect", "--since", "2026-09-24", "--until", "2026-09-25", *sources, *config]) == 0
    assert main(["normalize", "--date", "2026-09-25", *config]) == 0
    assert main(["report", "--date", "2026-09-25", *config]) == 0
    assert main(["mark-needs-review", "--date", "2026-09-25", *config]) == 0

    assert (tmp_path / "custom_data" / "collected" / "2026-09-25" / "signals.jsonl").exists()
    assert (tmp_path / "custom_data" / "normalized" / "2026-09-25" / "signals.jsonl").exists()
    assert json.loads((tmp_path / "custom_data" / "runs" / "2026-09-25" / "run_state.json").read_text())["needs_review"]
    assert (tmp_path / "custom_reports" / "daily" / "2026-09-25.md").exists()
    assert not (tmp_path / "data").exists()


def test_daily_defaults_to_output_dirs_and_arguments_win(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(daily_command, "build_adapters", _fixture_adapters)
    runtime = _runtime(tmp_path, "output:\n  data_dir: custom_data\n  reports_dir: custom_reports\n")
    scoring = Path(__file__).resolve().parents[1] / "config" / "scoring.yaml"
    common = ["--since", "2026-09-24", "--until", "2026-09-25", "--runtime-config", str(runtime), "--scoring-config", str(scoring)]
    sources = ["--sources-config", str(Path(__file__).resolve().parents[1] / "config" / "sources.yaml")]

    assert main(["daily", *common, *sources]) == 0
    assert main(["daily", *common, *sources, "--data-dir", "explicit_data", "--reports-dir", "explicit_reports"]) == 0

    assert (tmp_path / "custom_reports" / "daily" / "2026-09-25.md").exists()
    assert (tmp_path / "custom_data" / "runs" / "2026-09-25" / "run.jsonl").exists()
    assert (tmp_path / "explicit_reports" / "daily" / "2026-09-25.md").exists()
    assert (tmp_path / "explicit_data" / "runs" / "2026-09-25" / "run.jsonl").exists()


def test_broken_runtime_config_falls_back_to_default_dirs(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runtime = _runtime(tmp_path, "output: [broken")

    assert main(["report", "--date", DATE, "--runtime-config", str(runtime)]) == 0

    assert (tmp_path / "data" / "runs" / DATE / "run_state.json").exists()
    assert (tmp_path / "reports" / "daily" / f"{DATE}.md").exists()


# --- write errors that are not OSError ---


def test_unencodable_text_is_recorded_as_write_error(tmp_path: Path):
    data_dir = tmp_path / "data"
    collected = data_dir / "collected" / DATE / "signals.jsonl"
    collected.parent.mkdir(parents=True)
    record = {
        "signal_id": "github:x", "source": "github", "source_family": "technology", "content_type": "tool",
        "title": "lone surrogate \ud83d", "url": "https://example.com/x", "published_at": None,
        "fetched_at": "2026-10-09T00:00:00+00:00", "summary": "", "categories": [], "raw_metrics": {},
        "normalized_scores": {}, "metadata": {},
    }
    collected.write_text(json.dumps(record) + "\n", encoding="utf-8")

    assert main(["normalize", "--date", DATE, "--data-dir", str(data_dir)]) == 1

    errors = load_run_state(data_dir, DATE)["errors"]
    assert [error["type"] for error in errors] == ["write_error"]
    assert not (data_dir / "normalized" / DATE / "signals.jsonl").exists()
    assert list((data_dir / "normalized" / DATE).iterdir()) == []
