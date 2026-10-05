import json
from pathlib import Path

import pytest

from ai_research_radar.cli.main import main
from ai_research_radar.schemas.models import HotCandidate
from ai_research_radar.storage.jsonl import read_jsonl, write_jsonl

DATE = "2026-09-25"
A = "hot:event:tool-a"
B = "hot:event:tool-b"


def _run_dir(data_dir: Path) -> Path:
    return data_dir / "runs" / DATE


def _write_candidates(tmp_path: Path) -> Path:
    data_dir = tmp_path / "data"
    write_jsonl(
        _run_dir(data_dir) / "hot_candidates.jsonl",
        [
            HotCandidate(hot_id=A, title="Tool A", topic="tool-a", score=90.0, reasons=["Momentum 90"], evidence_urls=["https://example.com/a"], source_families=["technology"], signals=["github:a"], selected=False),
            HotCandidate(hot_id=B, title="Tool B", topic="tool-b", score=80.0, reasons=["Momentum 80"], evidence_urls=["https://example.com/b"], source_families=["technology"], signals=["github:b"], selected=False),
        ],
    )
    return data_dir


def _assessment(hot_id: str, decision: str = "selected", **overrides) -> dict:
    record = {
        "hot_id": hot_id,
        "decision": decision,
        "assessed_at": "2026-09-25T01:00:00+00:00",
        "assessor": "agent",
        "relevance": {"status": "related", "matched_terms": ["agent"], "reason": "AIエージェントのツール", "method": "agent"},
        "novelty": "新機能",
        "importance": "高い",
        "reader_impact": "導入判断に影響",
        "reason": "一次情報で確認済み",
        "evidence": [{"url": "https://example.com/release", "checked_at": "2026-09-25T00:59:00+00:00", "target_version": None, "status": "verified", "kind": "primary", "claim": "リリースを確認", "note": ""}],
        "unknowns": [],
    }
    record.update(overrides)
    return record


def _selection(**overrides) -> dict:
    data = {
        "assessments": [_assessment(A), _assessment(B, "rejected")],
        "screened_ids": [A, B],
        "selection_reason": "Aのみ一次情報で確認できた",
        "summaries": {A: "Tool Aの概要", B: "Tool Bの概要"},
    }
    data.update(overrides)
    return data


def _write_selection(data_dir: Path, data: object) -> Path:
    path = _run_dir(data_dir) / "selection_input.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def _select(data_dir: Path, *extra: str) -> int:
    return main(["select-hot", "--date", DATE, "--data-dir", str(data_dir), *extra])


def _by_id(data_dir: Path) -> dict:
    return {item["hot_id"]: item for item in read_jsonl(_run_dir(data_dir) / "hot_candidates.jsonl")}


def _state(data_dir: Path) -> dict:
    return json.loads((_run_dir(data_dir) / "run_state.json").read_text(encoding="utf-8"))


def _errors(data_dir: Path) -> list[dict]:
    return [error for error in _state(data_dir)["errors"] if error["source"] == "select-hot"]


def _types(data_dir: Path) -> list[str]:
    return [error["type"] for error in _errors(data_dir)]


def _assert_untouched(data_dir: Path) -> None:
    for item in _by_id(data_dir).values():
        assert item["selected"] is False
        assert item.get("assessment") is None
        assert item.get("summary", "") == ""


def test_saves_assessment_selection_and_summary(tmp_path: Path):
    data_dir = _write_candidates(tmp_path)
    _write_selection(data_dir, _selection())

    assert _select(data_dir) == 0

    by_id = _by_id(data_dir)
    assert by_id[A]["selected"] is True
    assert by_id[A]["assessment"] == _assessment(A)
    assert by_id[A]["summary"] == "Tool Aの概要"
    assert by_id[A]["reasons"] == ["Momentum 90"]
    assert by_id[B]["selected"] is False
    assert by_id[B]["assessment"]["decision"] == "rejected"
    assert by_id[B]["summary"] == "Tool Bの概要"
    state = _state(data_dir)
    assert state["stages_completed"][-1] == "select-hot"
    assert state["output_counts"]["selected_hot"] == 1
    assert _errors(data_dir) == []


@pytest.mark.parametrize("option", [["--select", A], ["--reason", f"{A}=理由"], ["--summary", f"{A}=概要"], ["--select", ""]])
def test_deprecated_options_fail_with_migration_message(tmp_path: Path, option: list[str]):
    data_dir = _write_candidates(tmp_path)
    _write_selection(data_dir, _selection())

    assert _select(data_dir, *option) == 1

    errors = _errors(data_dir)
    assert [error["type"] for error in errors] == ["deprecated_option"]
    assert "selection_input.json" in errors[0]["message"]
    _assert_untouched(data_dir)


def test_missing_hot_candidates_is_missing_input(tmp_path: Path):
    data_dir = tmp_path / "data"
    _write_selection(data_dir, _selection())

    assert _select(data_dir) == 1
    assert _types(data_dir) == ["missing_input"]


def test_missing_selection_input_is_missing_input(tmp_path: Path):
    data_dir = _write_candidates(tmp_path)

    assert _select(data_dir) == 1
    assert _types(data_dir) == ["missing_input"]
    assert "selection_input.json" in _errors(data_dir)[0]["message"]


def test_broken_json_is_invalid_input(tmp_path: Path):
    data_dir = _write_candidates(tmp_path)
    (_run_dir(data_dir) / "selection_input.json").write_text("{", encoding="utf-8")

    assert _select(data_dir) == 1
    assert _types(data_dir) == ["invalid_input"]
    _assert_untouched(data_dir)


@pytest.mark.parametrize("data", [[], {**_selection(), "summary": {}}, {"assessments": [], "screened_ids": []}])
def test_malformed_structure_is_invalid_input(tmp_path: Path, data: object):
    data_dir = _write_candidates(tmp_path)
    _write_selection(data_dir, data)

    assert _select(data_dir) == 1
    assert _types(data_dir) == ["invalid_input"]


@pytest.mark.parametrize("limit", ["abc", "6", "-1"])
def test_invalid_limit_is_invalid_input(tmp_path: Path, limit: str):
    data_dir = _write_candidates(tmp_path)
    _write_selection(data_dir, _selection())

    assert _select(data_dir, "--limit", limit) == 1
    assert _types(data_dir) == ["invalid_input"]


def test_screened_ids_mismatch_is_invalid_assessment(tmp_path: Path):
    data_dir = _write_candidates(tmp_path)
    _write_selection(data_dir, _selection(screened_ids=[A]))

    assert _select(data_dir) == 1
    assert _types(data_dir) == ["invalid_assessment"]
    _assert_untouched(data_dir)


def test_blank_selection_reason_is_invalid_assessment(tmp_path: Path):
    data_dir = _write_candidates(tmp_path)
    _write_selection(data_dir, _selection(selection_reason="  "))

    assert _select(data_dir) == 1
    assert _types(data_dir) == ["invalid_assessment"]


def test_selection_without_verified_primary_evidence_is_invalid_assessment(tmp_path: Path):
    data_dir = _write_candidates(tmp_path)
    weak = _assessment(A, evidence=[{**_assessment(A)["evidence"][0], "status": "unverified"}])
    _write_selection(data_dir, _selection(assessments=[weak, _assessment(B, "rejected")]))

    assert _select(data_dir) == 1
    assert _types(data_dir) == ["invalid_assessment"]


def test_malformed_evidence_check_is_invalid_assessment(tmp_path: Path):
    data_dir = _write_candidates(tmp_path)
    broken = _assessment(B, "rejected", evidence=[{"url": "https://example.com/b"}])
    _write_selection(data_dir, _selection(assessments=[_assessment(A), broken]))

    assert _select(data_dir) == 1
    assert _types(data_dir) == ["invalid_assessment"]


def test_selection_over_limit_is_selection_limit_exceeded(tmp_path: Path):
    data_dir = _write_candidates(tmp_path)
    _write_selection(data_dir, _selection(assessments=[_assessment(A), _assessment(B)]))

    assert _select(data_dir, "--limit", "1") == 1
    assert _types(data_dir) == ["selection_limit_exceeded"]
    assert _select(data_dir) == 0
    assert _state(data_dir)["output_counts"]["selected_hot"] == 2


@pytest.mark.parametrize("summaries", [{"hot:event:unknown": "概要"}, {A: "  "}, {A: 1}, ["概要"]])
def test_invalid_summaries_are_invalid_summary(tmp_path: Path, summaries: object):
    data_dir = _write_candidates(tmp_path)
    _write_selection(data_dir, _selection(summaries=summaries))

    assert _select(data_dir) == 1
    assert _types(data_dir) == ["invalid_summary"]
    _assert_untouched(data_dir)


def test_selected_candidate_without_summary_is_missing_summary(tmp_path: Path):
    data_dir = _write_candidates(tmp_path)
    _write_selection(data_dir, _selection(summaries={B: "Bの概要"}))

    assert _select(data_dir) == 1
    errors = _errors(data_dir)
    assert [error["type"] for error in errors] == ["missing_summary"]
    assert A in errors[0]["message"]
    _assert_untouched(data_dir)


def test_unselected_candidate_without_summary_is_warning(tmp_path: Path):
    data_dir = _write_candidates(tmp_path)
    _write_selection(data_dir, _selection(summaries={A: "Aの概要"}))

    assert _select(data_dir) == 0
    errors = _errors(data_dir)
    assert [error["type"] for error in errors] == ["missing_summary_warning"]
    assert B in errors[0]["message"] and A not in errors[0]["message"]


def test_unreviewed_candidates_are_warning(tmp_path: Path):
    data_dir = _write_candidates(tmp_path)
    _write_selection(data_dir, _selection(assessments=[_assessment(A)], screened_ids=[A]))

    assert _select(data_dir) == 0
    errors = _errors(data_dir)
    assert [error["type"] for error in errors] == ["unreviewed_candidates"]
    assert "1 unreviewed candidate(s)" in errors[0]["message"] and B in errors[0]["message"]
    by_id = _by_id(data_dir)
    assert by_id[B]["selected"] is False and by_id[B]["assessment"] is None


def test_rerun_keeps_unspecified_summary_and_replaces_selection(tmp_path: Path):
    data_dir = _write_candidates(tmp_path)
    _write_selection(data_dir, _selection())
    assert _select(data_dir) == 0

    _write_selection(data_dir, _selection(assessments=[_assessment(A, "rejected"), _assessment(B)], summaries={B: "書き直した概要"}))
    assert _select(data_dir) == 0

    by_id = _by_id(data_dir)
    assert by_id[A]["selected"] is False and by_id[A]["summary"] == "Tool Aの概要"
    assert by_id[B]["selected"] is True and by_id[B]["summary"] == "書き直した概要"


def test_input_option_overrides_default_path(tmp_path: Path):
    data_dir = _write_candidates(tmp_path)
    custom = tmp_path / "custom.json"
    custom.write_text(json.dumps(_selection(), ensure_ascii=False), encoding="utf-8")

    assert _select(data_dir, "--input", str(custom)) == 0
    assert _by_id(data_dir)[A]["selected"] is True


def test_zero_candidates_with_empty_selection_succeeds(tmp_path: Path):
    data_dir = tmp_path / "data"
    write_jsonl(_run_dir(data_dir) / "hot_candidates.jsonl", [])
    _write_selection(data_dir, {"assessments": [], "screened_ids": [], "selection_reason": "候補が0件"})

    assert _select(data_dir) == 0
    assert _state(data_dir)["output_counts"]["selected_hot"] == 0
    assert _errors(data_dir) == []


def test_rerun_clears_previous_errors(tmp_path: Path):
    data_dir = _write_candidates(tmp_path)
    assert _select(data_dir) == 1
    _write_selection(data_dir, _selection())

    assert _select(data_dir) == 0
    assert _errors(data_dir) == []
