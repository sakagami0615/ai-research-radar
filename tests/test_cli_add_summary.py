import json
from pathlib import Path

from ai_research_radar.cli.main import main
from ai_research_radar.reporting.digest import load_digest_summaries
from ai_research_radar.schemas.models import HotCandidate
from ai_research_radar.storage.jsonl import write_jsonl


def _hot(hot_id: str) -> HotCandidate:
    return HotCandidate(
        hot_id=hot_id,
        title=hot_id,
        topic=hot_id,
        score=80.0,
        reasons=[],
        evidence_urls=[f"https://example.com/{hot_id}"],
        source_families=["technology"],
        signals=[f"pypi:{hot_id}"],
        selected=False,
    )


def _setup(tmp_path: Path) -> Path:
    data_dir = tmp_path / "data"
    write_jsonl(data_dir / "runs" / "2026-09-24" / "hot_candidates.jsonl", [_hot("past")])
    write_jsonl(data_dir / "runs" / "2026-09-25" / "hot_candidates.jsonl", [_hot("today")])
    return data_dir


def _add(data_dir: Path, *summaries: str) -> int:
    args = ["add-summary", "--date", "2026-09-25", "--data-dir", str(data_dir)]
    for summary in summaries:
        args.extend(["--summary", summary])
    return main(args)


def _state(data_dir: Path) -> dict:
    return json.loads((data_dir / "runs" / "2026-09-25" / "run_state.json").read_text(encoding="utf-8"))


def test_add_summary_saves_summaries_for_candidates_in_lookback_window(tmp_path: Path):
    data_dir = _setup(tmp_path)

    assert _add(data_dir, "past=過去日の概要") == 0
    assert _add(data_dir, "today=当日の概要") == 0

    assert load_digest_summaries(data_dir, "2026-09-25") == {"past": "過去日の概要", "today": "当日の概要"}
    assert "add-summary" not in _state(data_dir).get("stages_completed", [])


def test_add_summary_rejects_invalid_entries_without_changing_saved_summaries(tmp_path: Path):
    from dataclasses import replace

    data_dir = _setup(tmp_path)
    write_jsonl(
        data_dir / "runs" / "2026-09-25" / "hot_candidates.jsonl",
        [_hot("today"), replace(_hot("own"), summary="候補自身の概要"), replace(_hot("picked"), selected=True)],
    )
    assert _add(data_dir, "past=最初の概要") == 0

    assert _add(data_dir, "past=上書き", "unknown=概要") == 1
    assert _add(data_dir, "own=候補自身に概要がある") == 1
    assert _add(data_dir, "picked=選抜済みは注目候補に出ない") == 1
    assert _add(data_dir, "past= ") == 1
    assert _add(data_dir, "no-equals-sign") == 1
    assert _add(data_dir) == 1

    assert load_digest_summaries(data_dir, "2026-09-25") == {"past": "最初の概要"}
    assert any(
        error["source"] == "add-summary" and error["type"] == "invalid_summary"
        for error in _state(data_dir)["errors"]
    )
