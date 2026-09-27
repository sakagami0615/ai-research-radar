import json
from pathlib import Path

from ai_research_radar.cli.main import main
from ai_research_radar.schemas.models import HotCandidate
from ai_research_radar.storage.jsonl import read_jsonl, write_jsonl


def _write_candidates(tmp_path: Path) -> Path:
    data_dir = tmp_path / "data"
    write_jsonl(
        data_dir / "runs" / "2026-09-25" / "hot_candidates.jsonl",
        [
            HotCandidate(
                hot_id="hot:event:tool-a",
                title="Tool A",
                topic="tool-a",
                score=90.0,
                reasons=["Momentum 90"],
                evidence_urls=["https://example.com/a"],
                source_families=["technology"],
                signals=["github:a"],
                selected=False,
            ),
            HotCandidate(
                hot_id="hot:event:tool-b",
                title="Tool B",
                topic="tool-b",
                score=80.0,
                reasons=["Momentum 80"],
                evidence_urls=["https://example.com/b"],
                source_families=["technology"],
                signals=["github:b"],
                selected=False,
            ),
        ],
    )
    return data_dir


def _read_state(data_dir: Path) -> dict:
    return json.loads(
        (data_dir / "runs" / "2026-09-25" / "run_state.json").read_text(encoding="utf-8")
    )


def test_cli_select_hot_marks_chosen_ids_selected(tmp_path: Path):
    data_dir = _write_candidates(tmp_path)

    exit_code = main(
        [
            "select-hot",
            "--date",
            "2026-09-25",
            "--data-dir",
            str(data_dir),
            "--select",
            "hot:event:tool-a",
            "--reason",
            "hot:event:tool-a=一次情報で確認済み",
        ]
    )

    assert exit_code == 0
    candidates = read_jsonl(data_dir / "runs" / "2026-09-25" / "hot_candidates.jsonl")
    by_id = {item["hot_id"]: item for item in candidates}
    assert by_id["hot:event:tool-a"]["selected"] is True
    assert by_id["hot:event:tool-b"]["selected"] is False
    assert "一次情報で確認済み" in by_id["hot:event:tool-a"]["reasons"]
    state = _read_state(data_dir)
    assert state["stages_completed"][-1] == "select-hot"
    assert state["output_counts"]["selected_hot"] == 1


def test_cli_select_hot_rejects_unknown_id_and_persists_error(tmp_path: Path):
    data_dir = _write_candidates(tmp_path)

    exit_code = main(
        [
            "select-hot",
            "--date",
            "2026-09-25",
            "--data-dir",
            str(data_dir),
            "--select",
            "hot:event:unknown",
        ]
    )

    assert exit_code == 1
    candidates = read_jsonl(data_dir / "runs" / "2026-09-25" / "hot_candidates.jsonl")
    assert all(candidate["selected"] is False for candidate in candidates)
    state = _read_state(data_dir)
    assert any(
        error["source"] == "select-hot" and error["type"] == "invalid_selection"
        for error in state["errors"]
    )


def test_cli_select_hot_rejects_malformed_reason_and_persists_error(tmp_path: Path):
    data_dir = _write_candidates(tmp_path)

    exit_code = main(
        [
            "select-hot",
            "--date",
            "2026-09-25",
            "--data-dir",
            str(data_dir),
            "--select",
            "hot:event:tool-a",
            "--reason",
            "no-equals-sign-here",
        ]
    )

    assert exit_code == 1
    state = _read_state(data_dir)
    assert any(
        error["source"] == "select-hot" and error["type"] == "invalid_reason"
        for error in state["errors"]
    )


def test_cli_select_hot_fails_and_persists_error_when_hot_candidates_missing(tmp_path: Path):
    exit_code = main(
        [
            "select-hot",
            "--date",
            "2026-09-25",
            "--data-dir",
            str(tmp_path / "data"),
            "--select",
            "hot:event:tool-a",
        ]
    )

    assert exit_code == 1
    state = _read_state(tmp_path / "data")
    assert any(
        error["source"] == "select-hot" and error["type"] == "missing_input"
        for error in state["errors"]
    )
