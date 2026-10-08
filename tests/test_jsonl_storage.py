from datetime import datetime, timezone
from pathlib import Path

import pytest

from ai_research_radar.schemas.models import RawItem
from ai_research_radar.schemas.decoders import decode_hot
from ai_research_radar.storage.jsonl import JsonlReadError, read_decoded_jsonl, read_jsonl, write_jsonl


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


def test_read_jsonl_reports_invalid_utf8_with_line_number(tmp_path: Path):
    path = tmp_path / "broken.jsonl"
    path.write_bytes(b'{"ok": true}\n{"title": "\xe3\x81"}\n')

    with pytest.raises(JsonlReadError) as exc:
        read_jsonl(path)

    assert exc.value.line_number == 2
    assert str(exc.value).startswith(f"{path}:2: invalid UTF-8")


def test_read_jsonl_reports_os_error_without_line_number(tmp_path: Path):
    path = tmp_path / "is-a-directory.jsonl"
    path.mkdir()

    with pytest.raises(JsonlReadError) as exc:
        read_jsonl(path)

    assert exc.value.line_number is None
    assert str(exc.value).startswith(f"{path}: ")


def _hot_record(**overrides) -> dict:
    record = {
        "hot_id": "hot:event:a",
        "title": "A",
        "topic": "a",
        "score": 90.0,
        "reasons": ["Momentum 90"],
        "evidence_urls": ["https://example.com/a"],
        "source_families": ["technology"],
        "signals": ["github:a"],
        "selected": False,
    }
    record.update(overrides)
    return record


def test_read_decoded_jsonl_returns_decoded_records(tmp_path: Path):
    path = tmp_path / "hot_candidates.jsonl"
    write_jsonl(path, [_hot_record()])

    candidates = read_decoded_jsonl(path, decode_hot)

    assert [candidate.hot_id for candidate in candidates] == ["hot:event:a"]


def test_read_decoded_jsonl_reports_missing_key_with_line_number(tmp_path: Path):
    path = tmp_path / "hot_candidates.jsonl"
    record = _hot_record()
    del record["hot_id"]
    write_jsonl(path, [_hot_record(), record])

    with pytest.raises(JsonlReadError) as exc:
        read_decoded_jsonl(path, decode_hot)

    assert exc.value.line_number == 2
    assert str(exc.value) == f"{path}:2: missing key 'hot_id'"


def test_read_decoded_jsonl_reports_decoder_value_error(tmp_path: Path):
    path = tmp_path / "hot_candidates.jsonl"
    write_jsonl(path, [_hot_record(score="abc")])

    with pytest.raises(JsonlReadError) as exc:
        read_decoded_jsonl(path, decode_hot)

    assert str(exc.value).startswith(f"{path}:1: invalid record: ")


def test_read_decoded_jsonl_reports_unsupported_schema_version(tmp_path: Path):
    path = tmp_path / "hot_candidates.jsonl"
    write_jsonl(path, [_hot_record(schema_version=99)])

    with pytest.raises(JsonlReadError) as exc:
        read_decoded_jsonl(path, decode_hot)

    assert str(exc.value) == f"{path}:1: invalid record: unsupported schema_version"
