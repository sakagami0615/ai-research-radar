from pathlib import Path

from ai_research_radar.cli.commands.run_state import (
    add_error,
    load_run_state,
    mark_stage_completed,
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
