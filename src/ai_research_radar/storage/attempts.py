from __future__ import annotations

import hashlib
import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_research_radar.storage.provenance import capture_provenance


def _atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, path)


def start_run(data_dir: Path, date: str, *, mode: str, since: str, until: str) -> dict[str, Any]:
    run_id = str(uuid.uuid4())
    root = data_dir / "runs" / date
    root.mkdir(parents=True, exist_ok=True)
    state = {"run_id": run_id, "started_at": datetime.now(timezone.utc).isoformat(), "mode": mode, "since": since, "until": until, "stages_completed": [], "errors": [], "output_counts": {}, "sources": []}
    _atomic(root / f"state-{run_id}.json", state)
    return state


def begin_attempt(data_dir: Path, date: str, *, state: dict[str, Any], stage: str, inputs: dict[str, Path], outputs: dict[str, Path], configs: dict[str, Any]) -> Path:
    attempt = data_dir / "runs" / date / "history" / uuid.uuid4().hex
    attempt.mkdir(parents=True)
    manifest = {"run_id": state["run_id"], "stage": stage, "inputs": {}, "outputs": {}, "provenance": capture_provenance(data_dir, configs)}
    for kind, paths in (("inputs", inputs), ("outputs", outputs)):
        for name, source in paths.items():
            if source.exists():
                target = attempt / kind / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                manifest[kind][name] = {"sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "path": str(target)}
    _atomic(attempt / "manifest.json", manifest)
    return attempt


def finish_attempt(attempt_dir: Path, *, outputs: dict[str, Path], errors: list[dict[str, str]]) -> None:
    _atomic(attempt_dir / "finished.json", {"outputs": {name: str(path) for name, path in outputs.items()}, "errors": errors, "finished_at": datetime.now(timezone.utc).isoformat()})


def invalidate_after(state: dict[str, Any], stage: str) -> None:
    order = ["collect", "normalize", "score", "select-hot", "save-proposals", "report"]
    index = order.index(stage)
    state["stages_completed"] = [value for value in state.get("stages_completed", []) if value in order[:index]]
