"""Issue #42: `ai-radar progress show` decides where a stopped agent run resumes.

The resume scenarios 1-11 of Issue #30 are the data in tests/fixtures/resume_scenarios/
(also placed into test_output/ by scripts/setup_resume_scenario.py for agent checks).
The other tests change a copy of a scenario to reach each row of the table.
"""

import hashlib
import importlib.util
import json
import shutil
from pathlib import Path

import pytest

from ai_research_radar.cli.main import main

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ROOT / "tests" / "fixtures" / "resume_scenarios"
DATE = "2026-09-25"

_SCRIPT = ROOT / "scripts" / "setup_resume_scenario.py"
_spec = importlib.util.spec_from_file_location("setup_resume_scenario", _SCRIPT)
setup_script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(setup_script)


def _show(base: Path, capsys, date: str = DATE) -> dict:
    code = main(["progress", "show", "--date", date, "--data-dir", str(base / "data"), "--reports-dir", str(base / "reports")])
    assert code == 0
    return json.loads(capsys.readouterr().out)


def _next(base: Path, capsys) -> tuple:
    result = _show(base, capsys)["next"]
    return result["action"], result["step"], result["stage"], result["reason"]


def _copy(tmp_path: Path, scenario: str) -> Path:
    base = tmp_path / scenario
    shutil.copytree(SCENARIOS / scenario, base)
    return base


def _run_dir(base: Path) -> Path:
    return base / "data" / "runs" / DATE


def _edit_state(base: Path, edit) -> None:
    path = _run_dir(base) / "run_state.json"
    state = json.loads(path.read_text(encoding="utf-8"))
    edit(state)
    path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")


def _add_error(base: Path, source: str, error_type: str, path: str | None = None) -> None:
    error = {"source": source, "type": error_type, "message": "broken"}
    if path is not None:
        error["path"] = path
    _edit_state(base, lambda state: state["errors"].append(error))


def _break(base: Path, path: str) -> None:
    """Leave a file cut off part way through a record, as a CLI stopped while writing it would."""
    (base / "data" / path).write_text('{"hot_id": "x"', encoding="utf-8")


def _add_retries(base: Path, stage: str, kind: str, times: int = 1) -> None:
    def edit(state):
        progress = state.setdefault("agent_progress", {"review_attempts": [], "retries": []})
        progress["retries"] += [{"stage": stage, "kind": kind, "recorded_at": "2026-09-25T00:00:00+00:00"}] * times

    _edit_state(base, edit)


def _tree_hash(base: Path) -> dict[str, str]:
    return {str(path.relative_to(base)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(base.rglob("*")) if path.is_file()}


# --- the resume scenarios 1-11 (Issue #30) ---

EXPECTED = {
    # 1: the day is already done: nothing is changed.
    "01_done": ("done", None, None, "done"),
    # 2: only `ai-radar daily` ran (no run_state.json): run from step 1, not "done".
    "02_deterministic_only": ("resume", 1, "collect", "no_run_state"),
    # 3: stopped after score: the selection (step 4).
    "03_after_score": ("resume", 4, "select-hot", "not_run"),
    # 4: stopped after the selection, before the proposals: step 6.
    "04_after_selection": ("resume", 6, "save-proposals", "not_run"),
    # 5: stopped after the report, before the review: no review_target.json, so step 8 is run
    # again before the first review attempt.
    "05_after_report": ("resume", 8, None, "review_target_missing"),
    # 6: stopped after the second review asked for changes: fix, then the third attempt.
    "06_review2_changes_requested": ("resume", 9, None, "next_review"),
    # 7: a file left broken (hot_candidates.jsonl): rebuilt from score.
    "07_corrupt_input": ("resume", 3, "score", "corrupt_input"),
    # 8: select-hot reached the rerun limit and stays failed: not returned to, the next step.
    "08_retry_limit_reached": ("resume", 6, "save-proposals", "not_run"),
    # 9: approved, stopped before `progress complete`: record the completion and finish.
    "09_approved_not_completed": ("complete", None, None, "approved"),
    # 10: the third review asked for changes: step 10, no fourth review.
    "10_review3_changes_requested": ("resume", 10, None, "review_attempts_exhausted"),
    # 11: stopped in step 10: step 10 again (not step 8).
    "11_finalize_interrupted": ("resume", 10, None, "finalized"),
}


def test_every_scenario_directory_has_an_expectation():
    assert sorted(EXPECTED) == setup_script.scenario_names()


@pytest.mark.parametrize("scenario", sorted(EXPECTED))
def test_resume_scenario(scenario: str, capsys):
    assert _next(SCENARIOS / scenario, capsys) == EXPECTED[scenario]


def test_scenario_review_attempt_numbers_and_pending_feedback(capsys):
    result = _show(SCENARIOS / "05_after_report", capsys)["next"]
    assert (result["attempt"], result["feedback_pending"]) == (1, False)
    result = _show(SCENARIOS / "06_review2_changes_requested", capsys)
    assert (result["next"]["attempt"], result["next"]["feedback_pending"]) == (3, True)
    assert [record["status"] for record in result["review_attempts"]] == ["changes_requested", "changes_requested"]
    assert _show(SCENARIOS / "10_review3_changes_requested", capsys)["next"]["attempt"] is None


def test_scenario_retry_limit_is_reported_in_skipped_and_retries(capsys):
    result = _show(SCENARIOS / "08_retry_limit_reached", capsys)
    assert result["skipped"] == [{"stage": "select-hot", "kind": "fix", "reason": "failed", "count": 3, "limit": 3}]
    row = next(row for row in result["retries"] if row["stage"] == "select-hot")
    assert row == {"stage": "select-hot", "kind": "fix", "count": 3, "limit": 3, "limit_reached": True}


@pytest.mark.parametrize("scenario", sorted(EXPECTED))
def test_setup_script_places_a_scenario_for_another_date(scenario: str, tmp_path: Path, capsys):
    """The skill uses today's date, so the script renames the fixture date (and re-hashes review_target.json)."""
    output = tmp_path / "test_output"
    stale = output / "data" / "runs" / "2026-10-01" / "run_state.json"
    stale.parent.mkdir(parents=True)
    stale.write_text("{}", encoding="utf-8")
    setup_script.setup(scenario, "2026-10-16", output)

    assert not stale.exists()
    assert not any(DATE in str(path) for path in output.rglob("*"))
    result = _show(output, capsys, date="2026-10-16")["next"]
    assert (result["action"], result["step"], result["stage"], result["reason"]) == EXPECTED[scenario]


def test_setup_script_shifts_every_date_by_the_same_days(tmp_path: Path):
    output = tmp_path / "test_output"
    setup_script.setup("03_after_score", "2026-10-16", output)
    state = json.loads((output / "data" / "runs" / "2026-10-16" / "run_state.json").read_text(encoding="utf-8"))
    # The fixture collected 2026-09-24 .. 2026-09-25.
    assert (state["since"], state["until"]) == ("2026-10-15", "2026-10-16")


@pytest.mark.parametrize("relative", ["", "data", "data/x", "reports"])
def test_setup_script_refuses_production_directories(capsys, tmp_path: Path, relative: str):
    checkout = tmp_path / "checkout"
    (checkout / ".git").mkdir(parents=True)
    output = checkout / relative if relative else checkout
    assert setup_script.main(["01_done", "--output-dir", str(output)]) == 1
    assert "would overwrite production data" in capsys.readouterr().err
    assert not (checkout / "data").exists() or not any((checkout / "data").iterdir())


def test_setup_script_accepts_test_output_in_a_checkout(tmp_path: Path):
    checkout = tmp_path / "checkout"
    (checkout / ".git").mkdir(parents=True)
    assert setup_script.main(["01_done", "--output-dir", str(checkout / "test_output"), "--date", "2026-10-16"]) == 0
    assert (checkout / "test_output" / "data" / "runs" / "2026-10-16" / "run_state.json").exists()


def test_setup_script_rejects_a_date_not_in_yyyy_mm_dd(tmp_path: Path):
    with pytest.raises(SystemExit):
        setup_script.main(["01_done", "--output-dir", str(tmp_path / "out"), "--date", "20261016"])


# --- row 1: done needs the agent run.jsonl, the report and the completion ---


def test_not_done_without_an_agent_run_jsonl(tmp_path: Path, capsys):
    base = _copy(tmp_path, "01_done")
    run_jsonl = _run_dir(base) / "run.jsonl"
    run_jsonl.write_text(run_jsonl.read_text(encoding="utf-8").replace('"mode": "agent"', '"mode": "daily"'), encoding="utf-8")
    # Falls through to the review rows: the last attempt is approved.
    assert _next(base, capsys) == ("complete", None, None, "approved")


def test_not_done_with_a_broken_run_jsonl(tmp_path: Path, capsys):
    base = _copy(tmp_path, "01_done")
    (_run_dir(base) / "run.jsonl").write_text('{"mode": "agent"', encoding="utf-8")
    assert _next(base, capsys)[0] == "complete"


def test_not_done_without_the_report(tmp_path: Path, capsys):
    base = _copy(tmp_path, "01_done")
    (base / "reports" / "daily" / f"{DATE}.md").unlink()
    assert _next(base, capsys) == ("resume", 8, None, "report_missing")


# --- row 3: collect / normalize / score ---


def test_command_error_of_collect_returns_to_step_1(tmp_path: Path, capsys):
    base = _copy(tmp_path, "05_after_report")
    _add_error(base, "collect", "signals_write_error")
    assert _next(base, capsys) == ("resume", 1, "collect", "command_error")


def test_source_level_errors_are_not_a_collect_failure(tmp_path: Path, capsys):
    base = _copy(tmp_path, "05_after_report")
    _add_error(base, "github", "http_error")
    assert _next(base, capsys) == ("resume", 8, None, "review_target_missing")


def test_stage_missing_from_stages_completed_is_returned_to(tmp_path: Path, capsys):
    base = _copy(tmp_path, "05_after_report")
    _edit_state(base, lambda state: state["stages_completed"].remove("normalize"))
    assert _next(base, capsys) == ("resume", 2, "normalize", "not_completed")


@pytest.mark.parametrize(
    ("path", "step", "stage"),
    [
        (f"collected/{DATE}/signals.jsonl", 1, "collect"),
        (f"normalized/{DATE}/signals.jsonl", 2, "normalize"),
        (f"events/{DATE}/events.jsonl", 2, "normalize"),
        (f"runs/{DATE}/hot_candidates.jsonl", 3, "score"),
    ],
)
def test_corrupt_input_returns_to_the_stage_that_writes_the_file(tmp_path: Path, capsys, path: str, step: int, stage: str):
    """The record is under the reading command (here report), so the stage comes from `path`."""
    base = _copy(tmp_path, "05_after_report")
    _break(base, path)
    _add_error(base, "report", "corrupt_input", path)
    assert _next(base, capsys) == ("resume", step, stage, "corrupt_input")


def test_corrupt_input_of_the_proposals_returns_to_step_6(tmp_path: Path, capsys):
    base = _copy(tmp_path, "05_after_report")
    _break(base, f"runs/{DATE}/article_proposals.jsonl")
    _add_error(base, "report", "corrupt_input", f"runs/{DATE}/article_proposals.jsonl")
    assert _next(base, capsys) == ("resume", 6, "save-proposals", "corrupt_input")


def test_corrupt_input_without_path_or_of_another_day_is_not_mapped(tmp_path: Path, capsys):
    base = _copy(tmp_path, "05_after_report")
    _add_error(base, "report", "corrupt_input")
    _add_error(base, "report", "corrupt_input", "runs/2026-09-24/hot_candidates.jsonl")
    assert _next(base, capsys) == ("resume", 8, None, "review_target_missing")


def test_corrupt_input_still_broken_after_the_rebuild_is_not_returned_to(tmp_path: Path, capsys):
    """The one rebuild of the day was used and the file is still broken: move on (recovery.md)."""
    base = _copy(tmp_path, "07_corrupt_input")
    _add_retries(base, "score", "corrupt_input")
    result = _show(base, capsys)
    # select-hot failed reading the same file: it follows the same day-wide limit, so step 6 is next.
    assert (result["next"]["step"], result["next"]["stage"]) == (6, "save-proposals")
    assert result["skipped"] == [
        {"stage": "score", "kind": "corrupt_input", "reason": "corrupt_input", "count": 1, "limit": 1},
        {"stage": "select-hot", "kind": "corrupt_input", "reason": "failed", "count": 1, "limit": 1},
    ]


def test_stopped_part_way_through_the_rebuild_resumes_at_the_reading_stage(tmp_path: Path, capsys):
    """score rebuilt hot_candidates.jsonl, then the run stopped before select-hot ran again:
    the stale record does not send it back to score, and select-hot is not skipped at the limit."""
    base = _copy(tmp_path, "07_corrupt_input")
    _add_retries(base, "score", "corrupt_input")
    shutil.copy(SCENARIOS / "03_after_score" / "data" / "runs" / DATE / "hot_candidates.jsonl", _run_dir(base) / "hot_candidates.jsonl")
    result = _show(base, capsys)
    assert (result["next"]["step"], result["next"]["stage"], result["next"]["reason"]) == (4, "select-hot", "failed")
    assert result["skipped"] == []


def test_a_missing_file_named_by_corrupt_input_counts_as_not_rebuilt(tmp_path: Path, capsys):
    base = _copy(tmp_path, "05_after_report")
    (_run_dir(base) / "article_proposals.jsonl").unlink()
    _add_error(base, "report", "corrupt_input", f"runs/{DATE}/article_proposals.jsonl")
    assert _next(base, capsys) == ("resume", 6, "save-proposals", "corrupt_input")


def test_a_stage_failing_on_its_own_corrupt_input_follows_the_corrupt_limit(tmp_path: Path, capsys):
    """score failed reading a broken events.jsonl: after the one rebuild, neither normalize nor score is returned to."""
    base = _copy(tmp_path, "05_after_report")
    _break(base, f"events/{DATE}/events.jsonl")
    _add_error(base, "score", "corrupt_input", f"events/{DATE}/events.jsonl")
    _add_retries(base, "normalize", "corrupt_input")
    result = _show(base, capsys)
    assert result["next"]["step"] == 8
    assert [(row["stage"], row["kind"]) for row in result["skipped"]] == [("normalize", "corrupt_input"), ("score", "corrupt_input")]


def test_a_stage_failing_on_a_rebuilt_input_is_run_again(tmp_path: Path, capsys):
    """normalize rebuilt events.jsonl and the run stopped before score ran again: back to score."""
    base = _copy(tmp_path, "05_after_report")
    _add_error(base, "score", "corrupt_input", f"events/{DATE}/events.jsonl")
    _add_retries(base, "normalize", "corrupt_input")
    assert _next(base, capsys) == ("resume", 3, "score", "command_error")


def test_a_corrupt_failure_without_path_keeps_the_limit(tmp_path: Path, capsys):
    base = _copy(tmp_path, "05_after_report")
    _add_error(base, "score", "corrupt_input")
    _add_retries(base, "score", "corrupt_input")
    assert _show(base, capsys)["next"]["step"] == 8


def test_command_error_at_the_fix_limit_is_skipped(tmp_path: Path, capsys):
    base = _copy(tmp_path, "05_after_report")
    _add_error(base, "score", "write_error")
    assert _next(base, capsys)[1] == 3
    _add_retries(base, "score", "fix")
    result = _show(base, capsys)
    assert result["next"]["step"] == 8
    assert result["skipped"] == [{"stage": "score", "kind": "fix", "reason": "command_error", "count": 1, "limit": 1}]


def test_other_kinds_do_not_count_toward_the_fix_limit(tmp_path: Path, capsys):
    """selection_mismatch / corrupt_input reruns are counted apart, whatever stage the record names."""
    base = _copy(tmp_path, "05_after_report")
    _add_error(base, "score", "write_error")
    _add_retries(base, "score", "selection_mismatch")
    _add_retries(base, "collect", "selection_mismatch")  # not a valid pair for `progress retry`, still read
    assert _next(base, capsys) == ("resume", 3, "score", "command_error")
    rows = {(row["stage"], row["kind"]): row for row in _show(base, capsys)["retries"]}
    assert rows[(None, "selection_mismatch")]["count"] == 2
    assert rows[("score", "fix")]["count"] == 0


def test_stage_rows_come_before_finalize(tmp_path: Path, capsys):
    base = _copy(tmp_path, "11_finalize_interrupted")
    _add_error(base, "normalize", "write_error")
    assert _next(base, capsys) == ("resume", 2, "normalize", "command_error")


# --- row 4: finalize ---


def test_finalize_comes_before_the_selection_and_the_report(tmp_path: Path, capsys):
    base = _copy(tmp_path, "11_finalize_interrupted")
    (base / "reports" / "daily" / f"{DATE}.md").unlink()
    _edit_state(base, lambda state: state["stage_results"].update({"select-hot": {"status": "failed", "reason": "invalid_input: x"}}))
    assert _next(base, capsys) == ("resume", 10, None, "finalized")


# --- rows 5-6: select-hot / save-proposals ---


def _set_result(base: Path, stage: str, result: dict | None) -> None:
    def edit(state):
        if result is None:
            state["stage_results"].pop(stage)
        else:
            state["stage_results"][stage] = result

    _edit_state(base, edit)


def test_select_hot_old_format_without_stage_results_counts_as_done(tmp_path: Path, capsys):
    base = _copy(tmp_path, "05_after_report")
    _set_result(base, "select-hot", None)
    _set_result(base, "save-proposals", None)
    assert _next(base, capsys) == ("resume", 8, None, "review_target_missing")


def test_stage_results_take_priority_over_stages_completed(tmp_path: Path, capsys):
    base = _copy(tmp_path, "05_after_report")
    _set_result(base, "select-hot", {"status": "failed", "reason": "invalid_assessment: x"})
    assert _next(base, capsys) == ("resume", 4, "select-hot", "failed")


def test_select_hot_not_run_without_stages_completed_returns_to_step_4(tmp_path: Path, capsys):
    base = _copy(tmp_path, "05_after_report")
    _set_result(base, "select-hot", None)
    _edit_state(base, lambda state: state["stages_completed"].remove("select-hot"))
    assert _next(base, capsys) == ("resume", 4, "select-hot", "not_run")


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        ({"status": "completed", "reason": "", "proposal_count": 1}, ("resume", 8, None, "review_target_missing")),
        ({"status": "deferred", "reason": "x", "proposal_count": 0}, ("resume", 8, None, "review_target_missing")),
        ({"status": "not_run", "reason": "選抜の再実行により無効"}, ("resume", 6, "save-proposals", "not_run")),
        ({"status": "failed", "reason": "invalid_proposal: x"}, ("resume", 6, "save-proposals", "failed")),
    ],
)
def test_save_proposals_status(tmp_path: Path, capsys, result: dict, expected: tuple):
    base = _copy(tmp_path, "05_after_report")
    _set_result(base, "save-proposals", result)
    assert _next(base, capsys) == expected


def test_save_proposals_failed_at_the_fix_limit_is_skipped(tmp_path: Path, capsys):
    base = _copy(tmp_path, "05_after_report")
    _set_result(base, "save-proposals", {"status": "failed", "reason": "invalid_proposal: x"})
    _add_retries(base, "save-proposals", "fix", times=3)
    result = _show(base, capsys)
    assert result["next"]["step"] == 8
    assert result["skipped"][0]["stage"] == "save-proposals"


# --- rows 7-10: the report and the review ---


def test_artifact_changed_since_the_review_started_returns_to_step_8(tmp_path: Path, capsys):
    base = _copy(tmp_path, "06_review2_changes_requested")
    report = base / "reports" / "daily" / f"{DATE}.md"
    report.write_text(report.read_text(encoding="utf-8") + "\n修正\n", encoding="utf-8")
    result = _show(base, capsys)["next"]
    assert (result["step"], result["reason"], result["attempt"]) == (8, "review_target_stale", 3)


def test_review_target_of_an_unrecorded_attempt_returns_to_step_8(tmp_path: Path, capsys):
    """`progress review --start` writes review_target.json before run_state.json (Issue #42 comment)."""
    base = _copy(tmp_path, "06_review2_changes_requested")
    path = _run_dir(base) / "review_target.json"
    target = json.loads(path.read_text(encoding="utf-8"))
    target["attempt"] = 3
    path.write_text(json.dumps(target), encoding="utf-8")
    assert _next(base, capsys) == ("resume", 8, None, "review_target_attempt_mismatch")


def test_unreadable_review_target_returns_to_step_8(tmp_path: Path, capsys):
    base = _copy(tmp_path, "06_review2_changes_requested")
    (_run_dir(base) / "review_target.json").write_text("{", encoding="utf-8")
    assert _next(base, capsys) == ("resume", 8, None, "review_target_unreadable")


def _set_last_status(base: Path, status: str) -> None:
    def edit(state):
        record = state["agent_progress"]["review_attempts"][-1]
        record["status"] = status
        record.pop("finished_at", None)

    _edit_state(base, edit)


@pytest.mark.parametrize("status", ["changes_requested", "failed", "started"])
def test_third_attempt_without_approval_goes_to_step_10(tmp_path: Path, capsys, status: str):
    base = _copy(tmp_path, "10_review3_changes_requested")
    _set_last_status(base, status)
    assert _next(base, capsys) == ("resume", 10, None, "review_attempts_exhausted")


def test_started_attempt_counts_as_one(tmp_path: Path, capsys):
    base = _copy(tmp_path, "09_approved_not_completed")
    _set_last_status(base, "started")
    result = _show(base, capsys)["next"]
    assert (result["step"], result["attempt"], result["feedback_pending"]) == (9, 2, False)


def test_feedback_is_pending_only_when_the_feedback_file_is_left(tmp_path: Path, capsys):
    base = _copy(tmp_path, "06_review2_changes_requested")
    (_run_dir(base) / "review_feedback.md").unlink()
    result = _show(base, capsys)["next"]
    assert (result["step"], result["attempt"], result["feedback_pending"]) == (9, 3, False)


# --- what show reads and writes ---


@pytest.mark.parametrize("scenario", ["01_done", "02_deterministic_only", "06_review2_changes_requested"])
def test_show_writes_nothing(tmp_path: Path, capsys, scenario: str):
    base = _copy(tmp_path, scenario)
    before = _tree_hash(base)
    _show(base, capsys)
    assert _tree_hash(base) == before


def test_missing_run_state_is_step_1_without_creating_files(tmp_path: Path, capsys):
    result = _show(tmp_path, capsys)
    assert result["next"]["step"] == 1 and result["review_attempts"] == [] and result["completed_at"] is None
    assert not (tmp_path / "data").exists()


def test_broken_run_state_ends_with_exit_code_1(tmp_path: Path, capsys):
    base = _copy(tmp_path, "05_after_report")
    (_run_dir(base) / "run_state.json").write_text("{", encoding="utf-8")
    assert main(["progress", "show", "--date", DATE, "--data-dir", str(base / "data"), "--reports-dir", str(base / "reports")]) == 1
    assert "error:" in capsys.readouterr().err


def test_malformed_agent_progress_ends_with_exit_code_1(tmp_path: Path, capsys):
    base = _copy(tmp_path, "05_after_report")
    _edit_state(base, lambda state: state.update({"agent_progress": {"review_attempts": [{"attempt": 9, "status": "approved"}], "retries": []}}))
    assert main(["progress", "show", "--date", DATE, "--data-dir", str(base / "data"), "--reports-dir", str(base / "reports")]) == 1
    assert "review_attempts" in capsys.readouterr().err


def test_collect_missing_from_stages_completed_returns_to_step_1(tmp_path: Path, capsys):
    base = _copy(tmp_path, "05_after_report")
    _edit_state(base, lambda state: state["stages_completed"].remove("collect"))
    assert _next(base, capsys) == ("resume", 1, "collect", "not_completed")


def test_review_target_without_any_recorded_attempt_returns_to_step_8(tmp_path: Path, capsys):
    base = _copy(tmp_path, "06_review2_changes_requested")
    _edit_state(base, lambda state: state["agent_progress"].update({"review_attempts": []}))
    result = _show(base, capsys)["next"]
    assert (result["step"], result["reason"], result["attempt"]) == (8, "review_target_attempt_mismatch", 1)


def test_review_target_that_is_not_an_object_returns_to_step_8(tmp_path: Path, capsys):
    base = _copy(tmp_path, "06_review2_changes_requested")
    (_run_dir(base) / "review_target.json").write_text("[]", encoding="utf-8")
    assert _next(base, capsys) == ("resume", 8, None, "review_target_unreadable")


def test_unreadable_review_artifact_ends_with_exit_code_1(tmp_path: Path, capsys):
    base = _copy(tmp_path, "06_review2_changes_requested")
    artifact = _run_dir(base) / "selection_input.json"
    artifact.unlink()
    artifact.mkdir()  # reading it raises IsADirectoryError
    assert main(["progress", "show", "--date", DATE, "--data-dir", str(base / "data"), "--reports-dir", str(base / "reports")]) == 1
    assert "failed to read a review artifact" in capsys.readouterr().err
