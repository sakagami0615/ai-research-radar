"""Issue #21: report records and shows a select-hot record that disagrees with hot_candidates.jsonl."""

import json
from pathlib import Path

import pytest

from ai_research_radar.cli.main import main
from ai_research_radar.schemas.models import HotCandidate
from ai_research_radar.storage.jsonl import read_jsonl, write_jsonl
from ai_research_radar.storage.run_state import save_run_state

DATE = "2026-09-25"

DEFERRED = {"status": "deferred", "reason": "根拠不足", "candidate_count": 1, "screened_count": 1, "unreviewed_count": 0, "selected_count": 0}
COMPLETED = {"status": "completed", "reason": "選抜した", "candidate_count": 1, "screened_count": 1, "unreviewed_count": 0, "selected_count": 1}
NO_SELECTION_PROPOSALS = {"status": "not_run", "reason": "選抜HOTなし", "proposal_count": 0}
COMPLETED_PROPOSALS = {"status": "completed", "reason": "", "proposal_count": 0}

MISMATCH_NOTICE = "選抜の記録(保留)と選抜結果が一致しません。以下は hot_candidates.jsonl の内容です。"
MISSING_SELECTION = "選抜結果が見つかりません(score の再実行などで選抜が消えた可能性があります)。"


def _candidate(selected: bool) -> HotCandidate:
    return HotCandidate(
        hot_id="hot:event:tool-a",
        title="Tool A",
        topic="tool-a",
        score=90.0,
        reasons=["Momentum 90"],
        evidence_urls=["https://example.com/a"],
        source_families=["technology"],
        signals=["github:a"],
        selected=selected,
        summary="Tool Aの概要",
    )


def _prepare(data_dir: Path, select_hot: dict | None, save_proposals: dict, candidates: list[HotCandidate] | None) -> Path:
    state = {
        "run_id": "2026-09-25T00:00:00+00:00",
        "since": DATE,
        "until": DATE,
        "sources": ["github"],
        "stages_completed": ["collect", "normalize", "score", "select-hot", "save-proposals"],
        "input_counts": {"github": 1},
        "output_counts": {},
        "errors": [],
    }
    if select_hot is not None:
        state["stage_results"] = {"select-hot": select_hot, "save-proposals": save_proposals}
    save_run_state(data_dir, DATE, state)
    hot_path = data_dir / "runs" / DATE / "hot_candidates.jsonl"
    if candidates is not None:
        write_jsonl(hot_path, candidates)
    return hot_path


def _report(tmp_path: Path) -> tuple[dict, str, str]:
    data_dir = tmp_path / "data"
    reports_dir = tmp_path / "reports"
    code = main(["report", "--date", DATE, "--data-dir", str(data_dir), "--reports-dir", str(reports_dir)])
    assert code == 0
    run = read_jsonl(data_dir / "runs" / DATE / "run.jsonl")[0]
    markdown = (reports_dir / "daily" / f"{DATE}.md").read_text(encoding="utf-8")
    section = markdown.split("## 選抜HOT\n")[1].split("\n## ")[0]
    return run, markdown, section


def _mismatch_errors(data_dir: Path) -> list[dict]:
    state = json.loads((data_dir / "runs" / DATE / "run_state.json").read_text(encoding="utf-8"))
    return [error for error in state["errors"] if error["type"] == "selection_mismatch"]


def _assert_recorded_once(tmp_path: Path, run: dict, markdown: str, message: str) -> None:
    error = {"source": "report", "type": "selection_mismatch", "message": message}
    assert _mismatch_errors(tmp_path / "data") == [error]
    assert error in run["errors"]
    assert f"- report: selection_mismatch - {message}" in markdown.split("## Errors\n")[1]


def test_deferred_with_selected_hot_is_recorded_and_shows_file_contents(tmp_path: Path):
    hot_path = _prepare(tmp_path / "data", DEFERRED, NO_SELECTION_PROPOSALS, [_candidate(True)])

    run, markdown, section = _report(tmp_path)

    _assert_recorded_once(
        tmp_path, run, markdown, f"select-hot is deferred in stage_results but {hot_path} has 1 selected"
    )
    assert f"本日の選抜HOTはありません(保留: 根拠不足。候補 1件中 1件を確認、未確認 0件)。{MISMATCH_NOTICE}" in section
    assert "### Tool A" in section
    assert "記事企画は未実行(選抜HOTなし)。" in section


def test_completed_without_selected_hot_is_recorded_with_existing_message(tmp_path: Path):
    hot_path = _prepare(tmp_path / "data", COMPLETED, COMPLETED_PROPOSALS, [_candidate(False)])

    run, markdown, section = _report(tmp_path)

    _assert_recorded_once(
        tmp_path, run, markdown, f"select-hot is completed in stage_results but {hot_path} has 0 selected"
    )
    assert MISSING_SELECTION in section
    assert MISMATCH_NOTICE not in section


def test_completed_without_hot_candidates_file_is_recorded_as_zero_selected(tmp_path: Path):
    hot_path = _prepare(tmp_path / "data", COMPLETED, COMPLETED_PROPOSALS, None)

    run, markdown, section = _report(tmp_path)

    _assert_recorded_once(
        tmp_path, run, markdown, f"select-hot is completed in stage_results but {hot_path} does not exist (0 selected)"
    )
    assert MISSING_SELECTION in section


@pytest.mark.parametrize(
    ("select_hot", "save_proposals", "selected"),
    [
        (COMPLETED, COMPLETED_PROPOSALS, True),
        (DEFERRED, NO_SELECTION_PROPOSALS, False),
        # Out of scope: old run states without stage_results, and an invalid record (shown as 記録なし).
        (None, COMPLETED_PROPOSALS, True),
        ({"status": "bogus"}, COMPLETED_PROPOSALS, True),
    ],
)
def test_matching_selection_is_not_recorded(tmp_path: Path, select_hot, save_proposals, selected: bool):
    _prepare(tmp_path / "data", select_hot, save_proposals, [_candidate(selected)])

    run, markdown, section = _report(tmp_path)

    assert _mismatch_errors(tmp_path / "data") == []
    assert "selection_mismatch" not in markdown
    assert MISMATCH_NOTICE not in section
    assert MISSING_SELECTION not in section


@pytest.mark.parametrize("select_hot", [COMPLETED, DEFERRED])
def test_unreadable_hot_candidates_is_only_corrupt_input(tmp_path: Path, select_hot: dict):
    hot_path = _prepare(tmp_path / "data", select_hot, COMPLETED_PROPOSALS, None)
    hot_path.parent.mkdir(parents=True, exist_ok=True)
    hot_path.write_text('{"broken": \n', encoding="utf-8")

    run, markdown, section = _report(tmp_path)

    assert _mismatch_errors(tmp_path / "data") == []
    assert any(error["source"] == "report" and error["type"] == "corrupt_input" for error in run["errors"])
    assert "hot_candidates.jsonl を読めなかったため表示できません(Errors を参照)。" in section
    assert MISMATCH_NOTICE not in section
    assert MISSING_SELECTION not in section


def test_rerun_after_fix_clears_selection_mismatch(tmp_path: Path):
    hot_path = _prepare(tmp_path / "data", COMPLETED, COMPLETED_PROPOSALS, [_candidate(False)])
    _report(tmp_path)
    assert len(_mismatch_errors(tmp_path / "data")) == 1

    write_jsonl(hot_path, [_candidate(True)])
    _report(tmp_path)

    assert _mismatch_errors(tmp_path / "data") == []


def test_selection_mismatch_is_kept_when_report_write_fails(tmp_path: Path):
    data_dir = tmp_path / "data"
    _prepare(data_dir, COMPLETED, COMPLETED_PROPOSALS, None)
    reports_dir = tmp_path / "reports"
    reports_dir.write_text("not a directory", encoding="utf-8")

    assert main(["report", "--date", DATE, "--data-dir", str(data_dir), "--reports-dir", str(reports_dir)]) == 1

    run = read_jsonl(data_dir / "runs" / DATE / "run.jsonl")[0]
    assert [error["type"] for error in run["errors"] if error["source"] == "report"] == ["selection_mismatch", "report_write_error"]
    assert len(_mismatch_errors(data_dir)) == 1
