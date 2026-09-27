from datetime import datetime, timezone
from pathlib import Path

import pytest

from ai_research_radar.schemas.models import RawItem
from ai_research_radar.storage.jsonl import JsonlReadError, read_jsonl, write_jsonl


def test_write_and_read_jsonl_roundtrip(tmp_path: Path):
    path = tmp_path / "signals.jsonl"
    records = [{"id": "a", "score": 1}, {"id": "b", "score": 2}]

    count = write_jsonl(path, records)

    assert count == 2
    assert path.read_text(encoding="utf-8").count("\n") == 2
    assert read_jsonl(path) == records


def test_write_jsonl_serializes_dataclass_datetime(tmp_path: Path):
    path = tmp_path / "raw-items.jsonl"
    record = RawItem(
        source="github",
        fetched_at=datetime(2026, 9, 25, 8, 0, tzinfo=timezone.utc),
        raw_id="owner/repo",
        raw_url="https://github.com/owner/repo",
        payload={"stars": 42},
    )

    write_jsonl(path, [record])

    assert read_jsonl(path) == [
        {
            "fetched_at": "2026-09-25T08:00:00+00:00",
            "payload": {"stars": 42},
            "raw_id": "owner/repo",
            "raw_url": "https://github.com/owner/repo",
            "source": "github",
        }
    ]


def test_write_jsonl_creates_parent_directories(tmp_path: Path):
    path = tmp_path / "data" / "raw" / "github.jsonl"

    write_jsonl(path, [{"source": "github"}])

    assert path.exists()


def test_read_jsonl_reports_malformed_line(tmp_path: Path):
    path = tmp_path / "broken.jsonl"
    path.write_text('{"ok": true}\n{"broken": \n{"ok": false}\n', encoding="utf-8")

    with pytest.raises(JsonlReadError) as exc:
        read_jsonl(path)

    assert exc.value.line_number == 2
    assert str(path) in str(exc.value)
