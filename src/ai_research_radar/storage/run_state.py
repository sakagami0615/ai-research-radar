# NOTE: this module assumes sequential, single-writer access (no file
# locking). The pipeline's subcommands run one at a time per date, not
# concurrently, so concurrent writers to the same run_state.json are out
# of scope.
from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_research_radar.schemas.models import NOT_RUN_REASON, valid_stage_result
from ai_research_radar.storage.files import atomic_write_text


class RunStateError(ValueError):
    pass


def run_state_path(data_dir: Path, date: str) -> Path:
    return data_dir / "runs" / date / "run_state.json"


STAGE_RESULT_STAGES = ("select-hot", "save-proposals")
INVALIDATED_REASON = "選抜の再実行により無効"


def _initial_stage_result() -> dict[str, Any]:
    return {"status": "not_run", "reason": NOT_RUN_REASON}


def _stage_results(state: dict[str, Any]) -> dict[str, Any]:
    results = state.get("stage_results")
    if not isinstance(results, dict):
        results = {}
        state["stage_results"] = results
    return results


def _fill_stage_results(state: dict[str, Any]) -> None:
    """Record "not run" for stages that have neither a valid result nor a completed mark.

    A stage already in stages_completed (old data written before stage_results
    existed) is left without a record, so it is shown as "記録なし" instead of
    being misreported as never run.
    """
    results = _stage_results(state)
    completed = state.get("stages_completed")
    completed = completed if isinstance(completed, list) else []
    for stage in STAGE_RESULT_STAGES:
        if valid_stage_result(results.get(stage)) is None and stage not in completed:
            results[stage] = _initial_stage_result()


def load_run_state(data_dir: Path, date: str, *, fill_stage_results: bool = True) -> dict[str, Any]:
    """`report` passes fill_stage_results=False so old data without stage_results stays "記録なし"."""
    path = run_state_path(data_dir, date)
    if not path.exists():
        state: dict[str, Any] = {
            "run_id": datetime.now(timezone.utc).isoformat(),
            "since": date,
            "until": date,
            "sources": [],
            "stages_completed": [],
            "input_counts": {},
            "output_counts": {},
            "errors": [],
        }
        _fill_stage_results(state)
        return state
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RunStateError(f"{path} is corrupt or unreadable: {exc}") from exc
    if not isinstance(state, dict):
        raise RunStateError(f"{path} is not a JSON object")
    if fill_stage_results:
        _fill_stage_results(state)
    return state


def save_run_state(data_dir: Path, date: str, state: dict[str, Any]) -> None:
    atomic_write_text(run_state_path(data_dir, date), json.dumps(state, ensure_ascii=False, sort_keys=True, indent=2))


def mark_stage_completed(state: dict[str, Any], stage: str) -> None:
    stages = state.setdefault("stages_completed", [])
    if stage not in stages:
        stages.append(stage)


def set_stage_result(state: dict[str, Any], stage: str, status: str, reason: str, **counts: int) -> None:
    """Overwrite the stage's result, including a previous success when a rerun fails."""
    _stage_results(state)[stage] = {"status": status, "reason": reason, **counts}


def invalidate_proposals_result(state: dict[str, Any]) -> None:
    """After select-hot succeeds again, saved proposals no longer match the selection.

    The initial "not run" value (first selection of the run) is left as is so a
    first run is not reported as invalidated by a rerun.
    """
    results = _stage_results(state)
    if results.get("save-proposals") == _initial_stage_result():
        return
    results["save-proposals"] = {"status": "not_run", "reason": INVALIDATED_REASON}


def add_error(state: dict[str, Any], source: str, error_type: str, message: str) -> None:
    errors = state.setdefault("errors", [])
    errors.append({"source": source, "type": error_type, "message": message})


def reset_errors_for(state: dict[str, Any], sources: Iterable[str]) -> None:
    """Drop stale errors for the given sources before a stage re-records its own.

    Without this, rerunning a stage (or the whole pipeline) for the same date
    keeps appending to `errors` forever, so a source that has since recovered
    still shows its old failure alongside the current, unrelated ones.
    """
    excluded = set(sources)
    state["errors"] = [
        error for error in state.get("errors", []) if error.get("source") not in excluded
    ]
