from pathlib import Path

import pytest

from ai_research_radar.storage.files import atomic_write_text
from ai_research_radar.storage.jsonl import read_jsonl, write_jsonl


def test_atomic_write_text_creates_parent_and_writes(tmp_path: Path):
    path = tmp_path / "a" / "b.json"

    atomic_write_text(path, "content\n")

    assert path.read_text(encoding="utf-8") == "content\n"
    assert [item.name for item in path.parent.iterdir()] == ["b.json"]


def test_write_jsonl_keeps_previous_file_when_a_record_fails(tmp_path: Path):
    path = tmp_path / "records.jsonl"
    write_jsonl(path, [{"id": 1}])

    def records():
        yield {"id": 2}
        raise RuntimeError("interrupted")

    with pytest.raises(RuntimeError):
        write_jsonl(path, records())

    assert read_jsonl(path) == [{"id": 1}]
    assert [item.name for item in tmp_path.iterdir()] == ["records.jsonl"]


def test_atomic_write_text_uses_umask_permissions(tmp_path: Path):
    import os

    mask = os.umask(0o022)
    try:
        atomic_write_text(tmp_path / "a.txt", "x")
    finally:
        os.umask(mask)

    assert (tmp_path / "a.txt").stat().st_mode & 0o777 == 0o644


def test_atomic_write_text_removes_temp_file_when_replace_fails(tmp_path: Path, monkeypatch):
    import ai_research_radar.storage.files as files

    def failing_replace(src, dst):
        raise OSError("replace failed")

    monkeypatch.setattr(files.os, "replace", failing_replace)
    with pytest.raises(OSError):
        atomic_write_text(tmp_path / "a.txt", "x")

    assert list(tmp_path.iterdir()) == []


def test_atomic_write_text_removes_temp_file_when_text_cannot_be_encoded(tmp_path: Path):
    path = tmp_path / "a.txt"
    path.write_text("old", encoding="utf-8")

    with pytest.raises(UnicodeEncodeError):
        atomic_write_text(path, "lone \ud83d")

    assert path.read_text(encoding="utf-8") == "old"
    assert [item.name for item in tmp_path.iterdir()] == ["a.txt"]
