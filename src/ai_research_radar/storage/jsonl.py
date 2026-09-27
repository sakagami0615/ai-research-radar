from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from ai_research_radar.schemas.models import to_json_dict


class JsonlReadError(ValueError):
    def __init__(self, path: Path, line_number: int, message: str) -> None:
        self.path = path
        self.line_number = line_number
        super().__init__(f"{path}:{line_number}: {message}")


def write_jsonl(path: Path, records: Iterable[Any]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            payload = to_json_dict(record) if not isinstance(record, dict) else record
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
            handle.write("\n")
            count += 1
    return count


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                value = json.loads(text)
            except json.JSONDecodeError as exc:
                raise JsonlReadError(path, line_number, exc.msg) from exc
            if not isinstance(value, dict):
                raise JsonlReadError(path, line_number, "JSONL records must be objects")
            records.append(value)
    return records
