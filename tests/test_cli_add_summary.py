import json
from dataclasses import replace
from pathlib import Path

from ai_research_radar.cli.main import main
from ai_research_radar.reporting.digest import load_digest_summaries
from ai_research_radar.schemas.models import HotCandidate
from ai_research_radar.storage.jsonl import write_jsonl

DATE = "2026-09-25"
# canonical_url keeps the query, so the key contains "=" (which --summary key=text could not split).
MODEL_KEY = "https://hf.co/org/model?revision=a%3Db"


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


def _model_signal() -> dict:
    return {
        "signal_id": "huggingface_orgs:org/model",
        "source": "huggingface_orgs",
        "source_family": "technology",
        "content_type": "model",
        "title": "org/model",
        "url": "https://HF.co/org/model/?revision=a=b",
        "published_at": "2026-09-25T00:00:00+00:00",
        "fetched_at": "2026-09-25T00:00:00+00:00",
        "summary": "",
        "categories": [],
        "raw_metrics": {},
        "normalized_scores": {},
        "metadata": {"model_release": {"provider": "Org", "channel": "huggingface"}},
    }


def _setup(tmp_path: Path) -> Path:
    data_dir = tmp_path / "data"
    write_jsonl(data_dir / "runs" / "2026-09-24" / "hot_candidates.jsonl", [_hot("past")])
    write_jsonl(
        data_dir / "runs" / DATE / "hot_candidates.jsonl",
        [_hot("today"), replace(_hot("own"), summary="候補自身の概要"), replace(_hot("picked"), selected=True)],
    )
    write_jsonl(data_dir / "normalized" / DATE / "signals.jsonl", [_model_signal()])
    return data_dir


def _input(tmp_path: Path, content: object, name: str = "summary_input.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")
    return path


def _add(data_dir: Path, *extra: str) -> int:
    return main(["add-summary", "--date", DATE, "--data-dir", str(data_dir), *extra])


def _errors(data_dir: Path) -> list[dict]:
    state = json.loads((data_dir / "runs" / DATE / "run_state.json").read_text(encoding="utf-8"))
    return [error for error in state.get("errors", []) if error["source"] == "add-summary"]


def test_add_summary_saves_notable_and_model_release_summaries_from_input(tmp_path: Path):
    data_dir = _setup(tmp_path)

    assert _add(data_dir, "--input", str(_input(tmp_path, {"past": "過去日の概要", MODEL_KEY: " モデルの概要 "}))) == 0
    assert _add(data_dir, "--input", str(_input(tmp_path, {"today": "当日の概要", MODEL_KEY: "上書き"}))) == 0

    assert load_digest_summaries(data_dir, DATE) == {"past": "過去日の概要", "today": "当日の概要", MODEL_KEY: "上書き"}
    state = json.loads((data_dir / "runs" / DATE / "run_state.json").read_text(encoding="utf-8"))
    assert "add-summary" not in state.get("stages_completed", [])
    assert _errors(data_dir) == []


def test_add_summary_records_error_types_without_changing_saved_summaries(tmp_path: Path):
    data_dir = _setup(tmp_path)
    assert _add(data_dir, "--input", str(_input(tmp_path, {"past": "最初の概要"}))) == 0
    broken = tmp_path / "broken.json"
    broken.write_text("{broken", encoding="utf-8")
    not_utf8 = tmp_path / "not_utf8.json"
    not_utf8.write_bytes(b"\xff\xfe")

    cases = [
        ([], "invalid_input"),
        (["--input", str(tmp_path / "missing.json")], "missing_input"),
        (["--input", str(broken)], "invalid_input"),
        (["--input", str(not_utf8)], "invalid_input"),
        (["--input", str(_input(tmp_path, ["past"], "list.json"))], "invalid_input"),
        (["--input", str(_input(tmp_path, {}, "empty.json"))], "invalid_summary"),
        (["--input", str(_input(tmp_path, {"past": "上書き", "unknown": "概要"}, "unknown.json"))], "invalid_summary"),
        (["--input", str(_input(tmp_path, {"own": "候補自身に概要がある"}, "own.json"))], "invalid_summary"),
        (["--input", str(_input(tmp_path, {"picked": "選抜済み"}, "picked.json"))], "invalid_summary"),
        (["--input", str(_input(tmp_path, {"past": " "}, "blank.json"))], "invalid_summary"),
        (["--input", str(_input(tmp_path, {"past": ["概要"]}, "nonstr.json"))], "invalid_summary"),
    ]
    for extra, error_type in cases:
        assert _add(data_dir, *extra) == 1, extra
        assert [error["type"] for error in _errors(data_dir)] == [error_type], extra

    assert load_digest_summaries(data_dir, DATE) == {"past": "最初の概要"}


def test_add_summary_records_write_error_when_saved_summaries_are_broken(tmp_path: Path):
    data_dir = _setup(tmp_path)
    saved = data_dir / "runs" / DATE / "digest_summaries.json"
    saved.write_text("{broken", encoding="utf-8")

    assert _add(data_dir, "--input", str(_input(tmp_path, {"past": "概要"}))) == 1

    assert [error["type"] for error in _errors(data_dir)] == ["write_error"]
    assert saved.read_text(encoding="utf-8") == "{broken"
