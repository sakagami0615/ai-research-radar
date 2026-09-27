from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


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
        return json.load(handle)


def save_run_state(data_dir: Path, date: str, state: dict[str, Any]) -> None:
    path = run_state_path(data_dir, date)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(state, handle, ensure_ascii=False, sort_keys=True, indent=2)


def mark_stage_completed(state: dict[str, Any], stage: str) -> None:
    if stage not in state["stages_completed"]:
        state["stages_completed"].append(stage)


def add_error(state: dict[str, Any], source: str, error_type: str, message: str) -> None:
    state["errors"].append({"source": source, "type": error_type, "message": message})
