# NOTE: this module assumes sequential, single-writer access (no file
# locking). The pipeline's subcommands run one at a time per date, not
# concurrently, so concurrent writers to the same run_state.json are out
# of scope.
from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class RunStateError(ValueError):
    pass


def run_state_path(data_dir: Path, date: str) -> Path:
    return data_dir / "runs" / date / "run_state.json"


def load_run_state(data_dir: Path, date: str) -> dict[str, Any]:
    path = run_state_path(data_dir, date)
    if not path.exists():
        return {
            "run_id": datetime.now(timezone.utc).isoformat(),
            "since": date,
            "until": date,
            "sources": [],
            "stages_completed": [],
            "input_counts": {},
            "output_counts": {},
            "errors": [],
        }
    with path.open("r", encoding="utf-8") as handle:
        try:
            return json.load(handle)
        except json.JSONDecodeError as exc:
            raise RunStateError(f"{path} is corrupt or truncated: {exc}") from exc


def save_run_state(data_dir: Path, date: str, state: dict[str, Any]) -> None:
    path = run_state_path(data_dir, date)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", dir=path.parent, delete=False, encoding="utf-8"
    ) as handle:
        json.dump(state, handle, ensure_ascii=False, sort_keys=True, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
        tmp_path = handle.name
    os.replace(tmp_path, path)


def mark_stage_completed(state: dict[str, Any], stage: str) -> None:
    stages = state.setdefault("stages_completed", [])
    if stage not in stages:
        stages.append(stage)


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
