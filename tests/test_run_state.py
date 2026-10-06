from pathlib import Path

import pytest

from ai_research_radar.cli.commands.run_state import (
    INVALIDATED_REASON,
    RunStateError,
    add_error,
    invalidate_proposals_result,
    load_run_state,
    mark_stage_completed,
    reset_errors_for,
    run_state_path,
    save_run_state,
    set_stage_result,
)


def test_load_run_state_returns_default_when_missing(tmp_path: Path):
    state = load_run_state(tmp_path / "data", "2026-09-27")

    assert state["since"] == "2026-09-27"
    assert state["until"] == "2026-09-27"
    assert state["stages_completed"] == []
    assert state["input_counts"] == {}
    assert state["output_counts"] == {}
    assert state["errors"] == []
    assert "run_id" in state
    assert state["stage_results"] == {
        "select-hot": {"status": "not_run", "reason": "未実行"},
        "save-proposals": {"status": "not_run", "reason": "未実行"},
    }


def test_save_and_load_run_state_roundtrip(tmp_path: Path):
    data_dir = tmp_path / "data"
    state = load_run_state(data_dir, "2026-09-27")
    state["sources"] = ["github"]
    save_run_state(data_dir, "2026-09-27", state)

    reloaded = load_run_state(data_dir, "2026-09-27")

    assert reloaded["sources"] == ["github"]
    assert reloaded["run_id"] == state["run_id"]
    assert (data_dir / "runs" / "2026-09-27" / "run_state.json").exists()


def test_mark_stage_completed_is_idempotent():
    state = {"stages_completed": []}

    mark_stage_completed(state, "collect")
    mark_stage_completed(state, "collect")

    assert state["stages_completed"] == ["collect"]


def test_add_error_appends_error_dict():
    state = {"errors": []}

    add_error(state, "github", "network_error", "timeout")

    assert state["errors"] == [
        {"source": "github", "type": "network_error", "message": "timeout"}
    ]


def test_load_run_state_raises_run_state_error_on_corrupt_json(tmp_path: Path):
    data_dir = tmp_path / "data"
    path = run_state_path(data_dir, "2026-09-27")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(RunStateError):
        load_run_state(data_dir, "2026-09-27")


def test_mark_stage_completed_works_on_dict_missing_key():
    state: dict = {}

    mark_stage_completed(state, "collect")

    assert state["stages_completed"] == ["collect"]


def test_add_error_works_on_dict_missing_key():
    state: dict = {}

    add_error(state, "github", "network_error", "timeout")

    assert state["errors"] == [
        {"source": "github", "type": "network_error", "message": "timeout"}
    ]


def test_reset_errors_for_drops_only_matching_sources():
    state = {
        "errors": [
            {"source": "arxiv", "type": "unexpected_error", "message": "HTTP 406"},
            {"source": "openalex", "type": "unexpected_error", "message": "HTTP 429"},
            {"source": "select-hot", "type": "invalid_selection", "message": "bad id"},
        ]
    }

    reset_errors_for(state, ["arxiv", "openalex"])

    assert state["errors"] == [
        {"source": "select-hot", "type": "invalid_selection", "message": "bad id"}
    ]


def test_reset_errors_for_works_on_dict_missing_key():
    state: dict = {}

    reset_errors_for(state, ["arxiv"])

    assert state["errors"] == []


NOT_RUN = {"status": "not_run", "reason": "未実行"}
DATE = "2026-09-27"


def _saved(tmp_path: Path, state: dict) -> Path:
    data_dir = tmp_path / "data"
    save_run_state(data_dir, DATE, state)
    return data_dir


def test_load_run_state_fills_old_data_only_for_stages_not_completed(tmp_path: Path):
    data_dir = _saved(tmp_path, {"run_id": "r", "stages_completed": ["collect", "select-hot"], "errors": []})

    state = load_run_state(data_dir, DATE)

    assert "select-hot" not in state["stage_results"]
    assert state["stage_results"]["save-proposals"] == NOT_RUN


def test_load_run_state_replaces_non_dict_stage_results(tmp_path: Path):
    data_dir = _saved(tmp_path, {"run_id": "r", "stages_completed": [], "stage_results": "broken"})

    assert load_run_state(data_dir, DATE)["stage_results"] == {"select-hot": NOT_RUN, "save-proposals": NOT_RUN}


def test_load_run_state_keeps_valid_records_and_refills_invalid_ones(tmp_path: Path):
    completed = {"status": "completed", "reason": "r", "selected_count": 1}
    data_dir = _saved(
        tmp_path,
        {"run_id": "r", "stages_completed": [], "stage_results": {"select-hot": completed, "save-proposals": {"status": "weird"}}},
    )

    results = load_run_state(data_dir, DATE)["stage_results"]

    assert results == {"select-hot": completed, "save-proposals": NOT_RUN}


def test_load_run_state_without_fill_keeps_old_data_as_is(tmp_path: Path):
    data_dir = _saved(tmp_path, {"run_id": "r", "stages_completed": []})

    assert "stage_results" not in load_run_state(data_dir, DATE, fill_stage_results=False)


def test_set_stage_result_overwrites_whole_record_and_creates_container():
    state: dict = {"stage_results": "broken"}

    set_stage_result(state, "select-hot", "completed", "r", selected_count=1)
    set_stage_result(state, "select-hot", "failed", "invalid_input: x")

    assert state["stage_results"] == {"select-hot": {"status": "failed", "reason": "invalid_input: x"}}


def test_invalidate_proposals_result_keeps_initial_value():
    state = {"stage_results": {"save-proposals": dict(NOT_RUN)}}

    invalidate_proposals_result(state)

    assert state["stage_results"]["save-proposals"] == NOT_RUN


def test_invalidate_proposals_result_resets_recorded_or_missing_value():
    recorded = {"stage_results": {"save-proposals": {"status": "completed", "reason": "", "proposal_count": 2}}}
    missing: dict = {"stage_results": {}}

    invalidate_proposals_result(recorded)
    invalidate_proposals_result(missing)

    expected = {"status": "not_run", "reason": INVALIDATED_REASON}
    assert recorded["stage_results"]["save-proposals"] == expected
    assert missing["stage_results"]["save-proposals"] == expected
    assert INVALIDATED_REASON == "選抜の再実行により無効"
