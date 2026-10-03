import json
from pathlib import Path

from ai_research_radar.storage.attempts import begin_attempt, finish_attempt, invalidate_after, start_run
from ai_research_radar.storage.provenance import capture_provenance


def test_rerun_keeps_previous_inputs_outputs(tmp_path: Path):
    first = start_run(tmp_path, "2026-09-29", mode="daily", since="2026-09-29", until="2026-09-29")
    path = begin_attempt(tmp_path, "2026-09-29", state=first, stage="collect", inputs={}, outputs={}, configs={})
    (path / "outputs").mkdir(); (path / "outputs" / "x").write_text("old")
    finish_attempt(path, outputs={}, errors=[])
    second = start_run(tmp_path, "2026-09-29", mode="daily", since="2026-09-29", until="2026-09-29")
    assert second["run_id"] != first["run_id"]
    assert list((tmp_path / "runs" / "2026-09-29" / "history").iterdir())


def test_interrupted_attempt_is_not_success(tmp_path: Path):
    state = start_run(tmp_path, "2026-09-29", mode="daily", since="x", until="x")
    path = begin_attempt(tmp_path, "2026-09-29", state=state, stage="collect", inputs={}, outputs={}, configs={})
    assert not (path / "finished.json").exists()


def test_new_run_invalidates_previous_outputs():
    state = {"stages_completed": ["collect", "normalize", "score"]}
    invalidate_after(state, "collect")
    assert state["stages_completed"] == []


def test_provenance_excludes_secrets(tmp_path: Path):
    result = capture_provenance(tmp_path, {"api_key": "secret", "endpoint": "https://u:p@example.test"})
    assert "secret" not in json.dumps(result)
    assert "u:p" not in json.dumps(result)


def test_provenance_dirty_is_unknown_outside_a_git_repo(tmp_path: Path):
    result = capture_provenance(tmp_path, {})
    assert result["dirty"] is None
    assert result["git_revision"] is None
