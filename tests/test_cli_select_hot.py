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
            "--summary",
            "hot:event:tool-a=Tool Aの概要",
            "--summary",
            "hot:event:tool-b=Tool Bの概要",
        ]
    )

    assert exit_code == 0
    candidates = read_jsonl(data_dir / "runs" / "2026-09-25" / "hot_candidates.jsonl")
    by_id = {item["hot_id"]: item for item in candidates}
    assert by_id["hot:event:tool-a"]["selected"] is True
    assert by_id["hot:event:tool-b"]["selected"] is False
    assert "一次情報で確認済み" in by_id["hot:event:tool-a"]["reasons"]
    assert by_id["hot:event:tool-a"]["summary"] == "Tool Aの概要"
    assert by_id["hot:event:tool-b"]["summary"] == "Tool Bの概要"
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


def test_cli_select_hot_deduplicates_reason_across_repeated_invocations(tmp_path: Path):
    data_dir = _write_candidates(tmp_path)
    args = [
        "select-hot",
        "--date",
        "2026-09-25",
        "--data-dir",
        str(data_dir),
        "--select",
        "hot:event:tool-a",
        "--reason",
        "hot:event:tool-a=一次情報で確認済み",
        "--summary",
        "hot:event:tool-a=Tool Aの概要",
    ]

    assert main(args) == 0
    assert main(args) == 0

    candidates = read_jsonl(data_dir / "runs" / "2026-09-25" / "hot_candidates.jsonl")
    by_id = {item["hot_id"]: item for item in candidates}
    assert by_id["hot:event:tool-a"]["reasons"].count("一次情報で確認済み") == 1


def test_cli_select_hot_rejects_empty_reason_text_and_persists_error(tmp_path: Path):
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
            "hot:event:tool-a=",
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


def _select(data_dir: Path, *extra: str) -> int:
    return main(["select-hot", "--date", "2026-09-25", "--data-dir", str(data_dir), *extra])


def _by_id(data_dir: Path) -> dict:
    candidates = read_jsonl(data_dir / "runs" / "2026-09-25" / "hot_candidates.jsonl")
    return {item["hot_id"]: item for item in candidates}


def test_cli_select_hot_keeps_existing_summary_and_replaces_respecified_one(tmp_path: Path):
    data_dir = _write_candidates(tmp_path)
    assert _select(
        data_dir,
        "--select", "hot:event:tool-a",
        "--summary", "hot:event:tool-a=最初の概要",
        "--summary", "hot:event:tool-b=Bの概要",
    ) == 0

    assert _select(data_dir, "--select", "hot:event:tool-a", "--summary", "hot:event:tool-a=書き直した概要") == 0

    by_id = _by_id(data_dir)
    assert by_id["hot:event:tool-a"]["summary"] == "書き直した概要"
    assert by_id["hot:event:tool-b"]["summary"] == "Bの概要"


def test_cli_select_hot_rejects_selected_candidate_without_summary(tmp_path: Path):
    data_dir = _write_candidates(tmp_path)

    exit_code = _select(data_dir, "--select", "hot:event:tool-a", "--summary", "hot:event:tool-b=Bの概要")

    assert exit_code == 1
    by_id = _by_id(data_dir)
    assert by_id["hot:event:tool-a"]["selected"] is False
    assert by_id["hot:event:tool-b"].get("summary", "") == ""
    state = _read_state(data_dir)
    assert any(
        error["source"] == "select-hot"
        and error["type"] == "missing_summary"
        and "hot:event:tool-a" in error["message"]
        for error in state["errors"]
    )


def test_cli_select_hot_warns_about_unselected_candidates_without_summary(tmp_path: Path):
    data_dir = _write_candidates(tmp_path)

    exit_code = _select(data_dir, "--select", "hot:event:tool-a", "--summary", "hot:event:tool-a=Aの概要")

    assert exit_code == 0
    state = _read_state(data_dir)
    warnings = [error for error in state["errors"] if error["type"] == "missing_summary_warning"]
    assert len(warnings) == 1
    assert "hot:event:tool-b" in warnings[0]["message"]
    assert "hot:event:tool-a" not in warnings[0]["message"]


def test_cli_select_hot_rejects_summary_for_unknown_id_or_empty_text(tmp_path: Path):
    data_dir = _write_candidates(tmp_path)

    assert _select(data_dir, "--summary", "hot:event:unknown=概要") == 1
    assert _select(data_dir, "--summary", "hot:event:tool-a=  ") == 1
    assert _select(data_dir, "--summary", "no-equals-sign") == 1

    state = _read_state(data_dir)
    assert any(error["type"] == "invalid_summary" for error in state["errors"])
    assert all(item.get("summary", "") == "" for item in _by_id(data_dir).values())
