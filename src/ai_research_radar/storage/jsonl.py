from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Iterator
from pathlib import Path
from typing import Any, TypeVar

from ai_research_radar.schemas.models import to_json_dict
from ai_research_radar.storage.files import atomic_write_text

T = TypeVar("T")


class JsonlReadError(ValueError):
    """A JSONL file that cannot be read as UTF-8 JSON objects, or a record its decoder rejects.

    line_number is None when the line is unknown (an OSError while opening or reading).
    """

    def __init__(self, path: Path, line_number: int | None, message: str) -> None:
        self.path = path
        self.line_number = line_number
        location = f"{path}:{line_number}" if line_number is not None else f"{path}"
        super().__init__(f"{location}: {message}")


def write_jsonl(path: Path, records: Iterable[Any]) -> int:
    """Write one JSON object per line, replacing the file atomically (see atomic_write_text)."""
    lines = [
        json.dumps(to_json_dict(record) if not isinstance(record, dict) else record, ensure_ascii=False, sort_keys=True)
        + "\n"
        for record in records
    ]
    atomic_write_text(path, "".join(lines))
    return len(lines)


def _iter_records(path: Path) -> Iterator[tuple[int, dict[str, Any]]]:
    """Yield (line_number, record), raising JsonlReadError for every way the file can be unreadable.

    The file is read as bytes and decoded line by line so that a UTF-8 error
    (e.g. a write cut off in the middle of a character) carries its line number.
    """
    try:
        handle = path.open("rb")
    except OSError as exc:
        raise JsonlReadError(path, None, exc.strerror or str(exc)) from exc
    with handle:
        line_number = 0
        try:
            for line_number, raw_line in enumerate(handle, start=1):
                try:
                    text = raw_line.decode("utf-8").strip()
                except UnicodeDecodeError as exc:
                    raise JsonlReadError(path, line_number, f"invalid UTF-8: {exc.reason}") from exc
                if not text:
                    continue
                try:
                    value = json.loads(text)
                except json.JSONDecodeError as exc:
                    raise JsonlReadError(path, line_number, exc.msg) from exc
                if not isinstance(value, dict):
                    raise JsonlReadError(path, line_number, "JSONL records must be objects")
                yield line_number, value
        except OSError as exc:
            raise JsonlReadError(path, None, exc.strerror or str(exc)) from exc


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [record for _, record in _iter_records(path)]


def read_decoded_jsonl(path: Path, decoder: Callable[[dict[str, Any]], T]) -> list[T]:
    """Read a pipeline JSONL and decode each record, reporting any failure as JsonlReadError.

    A decoder signals a broken record with KeyError (missing key), TypeError or
    ValueError (QualityValidationError is a ValueError); each becomes a
    JsonlReadError with the path and line number so every command records the
    same corrupt_input message.
    """
    decoded: list[T] = []
    for line_number, record in _iter_records(path):
        try:
            decoded.append(decoder(record))
        except KeyError as exc:
            raise JsonlReadError(path, line_number, f"missing key {exc.args[0]!r}") from exc
        except (TypeError, ValueError) as exc:
            raise JsonlReadError(path, line_number, f"invalid record: {exc}") from exc
    return decoded
