import json
from pathlib import Path

from ai_research_radar.cli.main import main
from ai_research_radar.schemas.models import HotCandidate
from ai_research_radar.storage.jsonl import read_jsonl, write_jsonl


def _write_selected_candidate(data_dir: Path) -> None:
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
                selected=True,
            )
        ],
    )


def _valid_proposal(source_hot_id: str) -> dict:
    return {
        "proposal_id": "hot:event:tool-a:proposal:1",
        "source_hot_id": source_hot_id,
        "title_idea": "Tool Aを試す",
        "article_type": "Hands-on",
        "target_reader": "AI Engineer",
        "why_now": "Momentumが急上昇している",
        "technical_angle": "セットアップと実行結果を検証する",
        "experiment_plan": ["インストール", "サンプル実行"],
        "competition": "Low",
        "traffic_opportunity": "High",
        "technical_opportunity": "High",
        "unique_angle": "日本語での再現手順を示す",
        "evidence_links": ["https://example.com/a"],
        "risks": ["早期のシグナルであり変動しうる"],
    }


def _run_save_proposals(tmp_path: Path, data_dir: Path, proposal: dict) -> int:
    input_path = tmp_path / "proposals.json"
    input_path.write_text(json.dumps([proposal], ensure_ascii=False), encoding="utf-8")
    return main(
        [
            "save-proposals",
            "--date",
            "2026-09-25",
            "--data-dir",
            str(data_dir),
            "--input",
            str(input_path),
        ]
    )


def _read_state(data_dir: Path) -> dict:
    return json.loads(
        (data_dir / "runs" / "2026-09-25" / "run_state.json").read_text(encoding="utf-8")
    )


def test_cli_save_proposals_writes_valid_proposals(tmp_path: Path):
    data_dir = tmp_path / "data"
    _write_selected_candidate(data_dir)

    exit_code = _run_save_proposals(tmp_path, data_dir, _valid_proposal("hot:event:tool-a"))

    assert exit_code == 0
    proposals = read_jsonl(data_dir / "runs" / "2026-09-25" / "article_proposals.jsonl")
    assert proposals[0]["source_hot_id"] == "hot:event:tool-a"
    state = _read_state(data_dir)
    assert state["stages_completed"][-1] == "save-proposals"
    assert state["output_counts"]["article_proposals"] == 1


def test_cli_save_proposals_rejects_missing_evidence_links(tmp_path: Path):
    data_dir = tmp_path / "data"
    _write_selected_candidate(data_dir)
    proposal = _valid_proposal("hot:event:tool-a")
    proposal["evidence_links"] = []

    exit_code = _run_save_proposals(tmp_path, data_dir, proposal)

    assert exit_code == 1
    assert not (data_dir / "runs" / "2026-09-25" / "article_proposals.jsonl").exists()
    state = _read_state(data_dir)
    assert any(error["source"] == "save-proposals" for error in state["errors"])


def test_cli_save_proposals_rejects_unselected_source_hot_id(tmp_path: Path):
    data_dir = tmp_path / "data"
    _write_selected_candidate(data_dir)

    exit_code = _run_save_proposals(tmp_path, data_dir, _valid_proposal("hot:event:unknown"))

    assert exit_code == 1
    state = _read_state(data_dir)
    assert any(error["source"] == "save-proposals" for error in state["errors"])


def test_cli_save_proposals_rejects_missing_required_field(tmp_path: Path):
    data_dir = tmp_path / "data"
    _write_selected_candidate(data_dir)
    proposal = _valid_proposal("hot:event:tool-a")
    del proposal["risks"]

    exit_code = _run_save_proposals(tmp_path, data_dir, proposal)

    assert exit_code == 1
    state = _read_state(data_dir)
    assert any(error["source"] == "save-proposals" for error in state["errors"])


def test_cli_save_proposals_fails_and_persists_error_when_hot_candidates_missing(tmp_path: Path):
    data_dir = tmp_path / "data"

    exit_code = _run_save_proposals(tmp_path, data_dir, _valid_proposal("hot:event:tool-a"))

    assert exit_code == 1
    state = _read_state(data_dir)
    assert any(
        error["source"] == "save-proposals" and error["type"] == "missing_input"
        for error in state["errors"]
    )
