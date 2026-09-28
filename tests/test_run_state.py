from pathlib import Path

import pytest

from ai_research_radar.cli.commands.run_state import (
    RunStateError,
    add_error,
    load_run_state,
    mark_stage_completed,
    reset_errors_for,
    run_state_path,
    save_run_state,
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
