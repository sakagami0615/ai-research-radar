import json
from pathlib import Path

import pytest

from ai_research_radar.cli.main import main
from ai_research_radar.schemas.models import HotCandidate
from ai_research_radar.storage.jsonl import read_jsonl, write_jsonl

DATE = "2026-09-25"
HOT_ID = "hot:event:tool-a"


def _write_selected_candidate(data_dir: Path) -> None:
    write_jsonl(
        data_dir / "runs" / DATE / "hot_candidates.jsonl",
        [
            HotCandidate(
                hot_id=HOT_ID,
                title="Tool A",
                topic="tool-a",
                score=90.0,
                reasons=["Momentum 90"],
                evidence_urls=["https://example.com/a"],
                source_families=["technology"],
                signals=["github:a"],
                selected=True,
            )
        ],
    )


def _write_unselected_candidate(data_dir: Path) -> None:
    _write_selected_candidate(data_dir)
    path = data_dir / "runs" / DATE / "hot_candidates.jsonl"
    records = read_jsonl(path)
    records[0]["selected"] = False
    path.write_text("".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records), encoding="utf-8")


def _quality() -> dict:
    return {
        "question": "Tool Aは既存ツールBより速いか",
        "difference": "Bは逐次処理、Aは並列処理",
        "baseline": "Tool B",
        "baseline_version": "1.2.0",
        "measurement": "同一入力で処理時間を5回測る",
        "inputs_and_environment": "サンプル100件、Ubuntu 24.04",
        "effort": "1日",
        "effort_assumptions": "公開サンプルが使える",
        "success_condition": "処理時間を比較できる",
        "stop_condition": "インストールできない",
        "metrics": ["処理時間"],
        "evidence": [
            {
                "url": "https://example.com/a",
                "checked_at": "2026-09-25T00:00:00+00:00",
                "target_version": None,
                "status": "verified",
                "kind": "primary",
                "claim": "Tool Aが並列処理に対応した",
                "note": "",
            }
        ],
        "unknowns": ["大規模入力での挙動"],
    }


def _valid_proposal(source_hot_id: str = HOT_ID, proposal_id: str = "hot:event:tool-a:proposal:1") -> dict:
    return {
        "schema_version": 2,
        "proposal_id": proposal_id,
        "source_hot_id": source_hot_id,
        "title_idea": "Tool Aを試す",
        "article_type": "Hands-on",
        "target_reader": "AI Engineer",
        "why_now": "Momentumが急上昇している",
        "technical_angle": "セットアップと実行結果を検証する",
        "experiment_plan": ["インストール", "サンプル実行"],
        "competition": "未調査",
        "traffic_opportunity": "未調査",
        "technical_opportunity": "並列処理の効果を測れる",
        "unique_angle": "日本語での再現手順を示す",
        "evidence_links": ["https://example.com/a"],
        "risks": ["早期のシグナルであり変動しうる"],
        "quality": _quality(),
    }


def _v2_input(proposals: list, **extra) -> dict:
    return {"schema_version": 2, "proposals": proposals, **extra}


def _run_with_bytes(tmp_path: Path, data_dir: Path, content: bytes) -> int:
    input_path = tmp_path / "proposals.json"
    input_path.write_bytes(content)
    return main(["save-proposals", "--date", DATE, "--data-dir", str(data_dir), "--input", str(input_path)])


def _run_with_records(tmp_path: Path, data_dir: Path, records: object) -> int:
    return _run_with_bytes(tmp_path, data_dir, json.dumps(records, ensure_ascii=False).encode("utf-8"))


def _read_state(data_dir: Path) -> dict:
    return json.loads((data_dir / "runs" / DATE / "run_state.json").read_text(encoding="utf-8"))


def _result(data_dir: Path) -> dict:
    return _read_state(data_dir)["stage_results"]["save-proposals"]


def _error_types(data_dir: Path) -> list[str]:
    return [error["type"] for error in _read_state(data_dir)["errors"] if error["source"] == "save-proposals"]


def _proposals_path(data_dir: Path) -> Path:
    return data_dir / "runs" / DATE / "article_proposals.jsonl"


# --- 成功 ---


def test_writes_valid_v2_proposals(tmp_path: Path):
    data_dir = tmp_path / "data"
    _write_selected_candidate(data_dir)

    assert _run_with_records(tmp_path, data_dir, _v2_input([_valid_proposal()])) == 0

    saved = read_jsonl(_proposals_path(data_dir))
    assert saved[0]["source_hot_id"] == HOT_ID
    assert saved[0]["schema_version"] == 2
    assert saved[0]["quality"] == _quality()
    state = _read_state(data_dir)
    assert state["stages_completed"][-1] == "save-proposals"
    assert state["output_counts"]["article_proposals"] == 1
    assert _result(data_dir) == {"status": "completed", "reason": "", "proposal_count": 1}


def test_records_deferred_with_deferral_reason(tmp_path: Path):
    data_dir = tmp_path / "data"
    _write_selected_candidate(data_dir)

    payload = _v2_input([], deferral_reason="  機能を確認できず保留。  ")
    assert _run_with_records(tmp_path, data_dir, payload) == 0

    assert _result(data_dir) == {"status": "deferred", "reason": "機能を確認できず保留。", "proposal_count": 0}
    assert "save-proposals" in _read_state(data_dir)["stages_completed"]


def test_records_not_run_when_nothing_is_selected(tmp_path: Path):
    data_dir = tmp_path / "data"
    _write_unselected_candidate(data_dir)

    assert _run_with_records(tmp_path, data_dir, _v2_input([])) == 0

    assert _result(data_dir) == {"status": "not_run", "reason": "選抜HOTなし", "proposal_count": 0}
    assert "save-proposals" in _read_state(data_dir)["stages_completed"]


# --- 旧形式(deprecated_input) ---


@pytest.mark.parametrize(
    "payload",
    [
        [],
        [{"proposal_id": "x"}],
        {"proposals": []},
        {"schema_version": 1, "proposals": []},
        {"schema_version": "2", "proposals": []},
        {"schema_version": True, "proposals": []},
    ],
    ids=["empty-array", "array", "no-version", "version-1", "version-str", "version-bool"],
)
def test_legacy_top_level_is_deprecated_input(tmp_path: Path, payload, capsys):
    data_dir = tmp_path / "data"
    _write_selected_candidate(data_dir)

    assert _run_with_records(tmp_path, data_dir, payload) == 1

    assert _error_types(data_dir) == ["deprecated_input"]
    assert _result(data_dir)["reason"].startswith("deprecated_input: ")
    assert "schema_version" in capsys.readouterr().out
    assert not _proposals_path(data_dir).exists()


@pytest.mark.parametrize("version", [None, 1], ids=["missing", "v1"])
def test_legacy_proposal_is_deprecated_input(tmp_path: Path, version):
    data_dir = tmp_path / "data"
    _write_selected_candidate(data_dir)
    proposal = _valid_proposal()
    if version is None:
        del proposal["schema_version"]
    else:
        proposal["schema_version"] = version

    assert _run_with_records(tmp_path, data_dir, _v2_input([proposal])) == 1

    assert _error_types(data_dir) == ["deprecated_input"]


# --- 入力全体の構造(invalid_input) ---


@pytest.mark.parametrize(
    "payload",
    ["text", {"schema_version": 2}, {"schema_version": 2, "proposals": {}}, {"schema_version": 2, "proposals": [], "extra": 1}],
    ids=["string", "no-proposals", "proposals-not-list", "unknown-key"],
)
def test_invalid_structure_is_invalid_input(tmp_path: Path, payload):
    data_dir = tmp_path / "data"
    _write_selected_candidate(data_dir)

    assert _run_with_records(tmp_path, data_dir, payload) == 1

    assert _error_types(data_dir) == ["invalid_input"]


@pytest.mark.parametrize("extra", [{}, {"deferral_reason": ""}, {"deferral_reason": "  "}, {"deferral_reason": 1}], ids=["missing", "empty", "blank", "not-string"])
def test_deferral_reason_required_when_selected_without_proposals(tmp_path: Path, extra):
    data_dir = tmp_path / "data"
    _write_selected_candidate(data_dir)

    assert _run_with_records(tmp_path, data_dir, _v2_input([], **extra)) == 1

    assert _error_types(data_dir) == ["invalid_input"]
    assert "deferral_reason" in _result(data_dir)["reason"]


def test_deferral_reason_rejected_when_proposals_exist(tmp_path: Path):
    data_dir = tmp_path / "data"
    _write_selected_candidate(data_dir)

    assert _run_with_records(tmp_path, data_dir, _v2_input([_valid_proposal()], deferral_reason="古い理由")) == 1

    assert _error_types(data_dir) == ["invalid_input"]
    assert not _proposals_path(data_dir).exists()


def test_deferral_reason_rejected_when_nothing_is_selected(tmp_path: Path):
    data_dir = tmp_path / "data"
    _write_unselected_candidate(data_dir)

    assert _run_with_records(tmp_path, data_dir, _v2_input([], deferral_reason="古い理由")) == 1

    assert _error_types(data_dir) == ["invalid_input"]


def test_malformed_json_is_invalid_input(tmp_path: Path):
    data_dir = tmp_path / "data"
    _write_selected_candidate(data_dir)

    assert _run_with_bytes(tmp_path, data_dir, b"not valid json {{{") == 1

    assert _error_types(data_dir) == ["invalid_input"]


def test_non_utf8_input_is_recorded_as_invalid_input(tmp_path: Path):
    data_dir = tmp_path / "data"
    _write_selected_candidate(data_dir)

    assert _run_with_bytes(tmp_path, data_dir, b"\xff\xfe[") == 1

    assert _result(data_dir)["reason"].startswith("invalid_input: ")


# --- 企画の検証(invalid_proposal) ---


def _broken(mutate) -> dict:
    proposal = _valid_proposal()
    mutate(proposal)
    return proposal


@pytest.mark.parametrize(
    "proposal",
    [
        _broken(lambda p: p.pop("risks")),
        _broken(lambda p: p.pop("title_idea")),
        _broken(lambda p: p.update(title_idea="")),
        _broken(lambda p: p.update(experiment_plan="インストール")),
        _broken(lambda p: p.update(evidence_links=[])),
        _broken(lambda p: p.pop("quality")),
        _broken(lambda p: p["quality"].update(metrics=[])),
        _broken(lambda p: p["quality"]["evidence"][0].pop("claim")),
        _broken(lambda p: p.update(source_hot_id="hot:event:unknown")),
        _broken(lambda p: p.update(evidence_links=["https://other.example/b"])),
        _broken(lambda p: p.update(evidence_links=["https://example.com/a", "https://other.example/b"])),
    ],
    ids=[
        "missing-risks",
        "missing-title",
        "empty-title",
        "plan-not-list",
        "no-evidence-links",
        "missing-quality",
        "empty-metrics",
        "invalid-evidence-check",
        "unknown-hot",
        "no-candidate-evidence",
        "additional-url-without-role",
    ],
)
def test_invalid_proposal_is_rejected(tmp_path: Path, proposal):
    data_dir = tmp_path / "data"
    _write_selected_candidate(data_dir)

    assert _run_with_records(tmp_path, data_dir, _v2_input([proposal])) == 1

    assert _error_types(data_dir) == ["invalid_proposal"]
    assert _result(data_dir)["reason"].startswith("invalid_proposal: proposal[0] ")
    assert not _proposals_path(data_dir).exists()


def test_proposal_for_unselected_hot_is_rejected(tmp_path: Path):
    data_dir = tmp_path / "data"
    _write_unselected_candidate(data_dir)

    assert _run_with_records(tmp_path, data_dir, _v2_input([_valid_proposal()])) == 1

    assert _error_types(data_dir) == ["invalid_proposal"]
    assert "not a selected HOT candidate" in _result(data_dir)["reason"]


def test_additional_url_with_role_is_accepted(tmp_path: Path):
    data_dir = tmp_path / "data"
    _write_selected_candidate(data_dir)
    proposal = _valid_proposal()
    proposal["evidence_links"].append("https://other.example/b")
    proposal["quality"]["evidence"].append({**proposal["quality"]["evidence"][0], "url": "https://other.example/b", "claim": "比較対象 Tool B の仕様"})

    assert _run_with_records(tmp_path, data_dir, _v2_input([proposal])) == 0


def test_fourth_proposal_for_same_hot_is_rejected(tmp_path: Path):
    data_dir = tmp_path / "data"
    _write_selected_candidate(data_dir)
    proposals = [_valid_proposal(proposal_id=f"p{index}") for index in range(4)]

    assert _run_with_records(tmp_path, data_dir, _v2_input(proposals)) == 1

    assert "at most three" in _result(data_dir)["reason"]


def test_duplicate_proposal_id_is_rejected(tmp_path: Path):
    data_dir = tmp_path / "data"
    _write_selected_candidate(data_dir)

    assert _run_with_records(tmp_path, data_dir, _v2_input([_valid_proposal(), _valid_proposal()])) == 1

    assert "duplicate proposal_id" in _result(data_dir)["reason"]


def test_non_object_element_is_recorded_as_invalid_proposal(tmp_path: Path):
    data_dir = tmp_path / "data"
    _write_selected_candidate(data_dir)

    assert _run_with_records(tmp_path, data_dir, _v2_input([1])) == 1

    assert _result(data_dir)["reason"] == "invalid_proposal: proposal[0] must be an object"


# --- そのほか ---


def test_missing_hot_candidates_is_missing_input(tmp_path: Path):
    data_dir = tmp_path / "data"

    assert _run_with_records(tmp_path, data_dir, _v2_input([_valid_proposal()])) == 1

    assert _error_types(data_dir) == ["missing_input"]


def test_failure_overwrites_previous_success(tmp_path: Path):
    data_dir = tmp_path / "data"
    _write_selected_candidate(data_dir)
    assert _run_with_records(tmp_path, data_dir, _v2_input([_valid_proposal()])) == 0
    broken = _valid_proposal()
    broken["evidence_links"] = []

    assert _run_with_records(tmp_path, data_dir, _v2_input([broken])) == 1

    result = _result(data_dir)
    assert result["status"] == "failed"
    assert result["reason"].startswith("invalid_proposal: ")
    assert set(result) == {"status", "reason"}


def test_write_failure_is_recorded_as_write_error(tmp_path: Path):
    data_dir = tmp_path / "data"
    _write_selected_candidate(data_dir)
    _proposals_path(data_dir).mkdir()

    assert _run_with_records(tmp_path, data_dir, _v2_input([_valid_proposal()])) == 1

    assert _result(data_dir)["reason"].startswith("write_error: failed to write article proposals")


def test_extra_proposal_keys_are_not_saved(tmp_path: Path):
    data_dir = tmp_path / "data"
    _write_selected_candidate(data_dir)
    proposal = _valid_proposal()
    proposal["memo"] = "保存しない"

    assert _run_with_records(tmp_path, data_dir, _v2_input([proposal])) == 0

    assert "memo" not in read_jsonl(_proposals_path(data_dir))[0]


def test_failure_keeps_existing_article_proposals(tmp_path: Path):
    data_dir = tmp_path / "data"
    _write_selected_candidate(data_dir)
    assert _run_with_records(tmp_path, data_dir, _v2_input([_valid_proposal()])) == 0
    before = _proposals_path(data_dir).read_bytes()

    assert _run_with_records(tmp_path, data_dir, [_valid_proposal()]) == 1

    assert _proposals_path(data_dir).read_bytes() == before


def test_only_selected_hot_accepts_proposals_on_mixed_day(tmp_path: Path):
    data_dir = tmp_path / "data"
    _write_selected_candidate(data_dir)
    path = data_dir / "runs" / DATE / "hot_candidates.jsonl"
    records = read_jsonl(path)
    records.append({**records[0], "hot_id": "hot:event:tool-b", "selected": False})
    path.write_text("".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records), encoding="utf-8")

    assert _run_with_records(tmp_path, data_dir, _v2_input([_valid_proposal()])) == 0
    assert _run_with_records(tmp_path, data_dir, _v2_input([_valid_proposal(source_hot_id="hot:event:tool-b")])) == 1
    assert "not a selected HOT candidate" in _result(data_dir)["reason"]


def test_additional_url_with_blank_claim_is_rejected(tmp_path: Path):
    data_dir = tmp_path / "data"
    _write_selected_candidate(data_dir)
    proposal = _valid_proposal()
    proposal["evidence_links"].append("https://other.example/b")
    proposal["quality"]["evidence"].append({**proposal["quality"]["evidence"][0], "url": "https://other.example/b", "claim": "  "})

    assert _run_with_records(tmp_path, data_dir, _v2_input([proposal])) == 1

    assert _error_types(data_dir) == ["invalid_proposal"]


def test_newer_schema_version_message_does_not_call_it_legacy(tmp_path: Path, capsys):
    data_dir = tmp_path / "data"
    _write_selected_candidate(data_dir)

    assert _run_with_records(tmp_path, data_dir, {"schema_version": 3, "proposals": []}) == 1

    assert _error_types(data_dir) == ["deprecated_input"]
    assert "旧形式です" not in capsys.readouterr().out
