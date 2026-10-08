"""Issue #18: a broken pipeline JSONL is recorded as corrupt_input instead of a traceback."""

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from ai_research_radar.cli.commands.run_state import save_run_state
from ai_research_radar.cli.main import main
from ai_research_radar.schemas.models import ArticleProposal, HotCandidate
from ai_research_radar.storage.jsonl import read_jsonl, write_jsonl

DATE = "2026-09-25"

# Each broken file starts with a blank line, so the error is on line 2.
CORRUPTIONS = {
    "bad_utf8": b'\n{"title": "\xe3\x81"}\n',
    "bad_json": b'\n{"broken": \n',
    "not_object": b"\n[1, 2]\n",
    "missing_key": b'\n{"title": "x"}\n',
}
JSON_LEVEL = ["bad_utf8", "bad_json", "not_object"]


def _state(data_dir: Path) -> dict:
    return json.loads((data_dir / "runs" / DATE / "run_state.json").read_text(encoding="utf-8"))


def _corrupt_errors(data_dir: Path, source: str) -> list[dict]:
    return [e for e in _state(data_dir)["errors"] if e["source"] == source and e["type"] == "corrupt_input"]


def _write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _assert_recorded(data_dir: Path, source: str, path: Path) -> str:
    errors = _corrupt_errors(data_dir, source)
    assert len(errors) == 1
    message = errors[0]["message"]
    assert message.startswith(f"{path}:2: ")
    return message


def _candidate(selected: bool = True) -> HotCandidate:
    return HotCandidate(
        hot_id="hot:event:tool-a",
        title="Tool A",
        topic="tool-a",
        score=90.0,
        reasons=["Momentum 90"],
        evidence_urls=["https://example.com/a"],
        source_families=["technology"],
        signals=["github:a"],
        selected=selected,
        summary="Tool Aの概要",
    )


def _proposal() -> ArticleProposal:
    return ArticleProposal(
        proposal_id="hot:event:tool-a:proposal:1",
        source_hot_id="hot:event:tool-a",
        title_idea="Tool Aを試す",
        article_type="Hands-on",
        target_reader="AI Engineer",
        why_now="Momentumが急上昇している",
        technical_angle="検証する",
        experiment_plan=["インストール"],
        competition="Low",
        traffic_opportunity="High",
        technical_opportunity="High",
        unique_angle="日本語での再現手順",
        evidence_links=["https://example.com/a"],
        risks=["変動しうる"],
    )


def _quality() -> dict:
    return {
        "question": "q", "difference": "d", "baseline": "b", "baseline_version": "1", "measurement": "m",
        "inputs_and_environment": "e", "effort": "1日", "effort_assumptions": "a", "success_condition": "s",
        "stop_condition": "x", "metrics": ["m"], "evidence": [], "unknowns": [],
    }


# --- normalize / score -------------------------------------------------------


@pytest.mark.parametrize("corruption", list(CORRUPTIONS))
def test_normalize_records_corrupt_collected_signals(tmp_path: Path, corruption: str):
    data_dir = tmp_path / "data"
    collected = data_dir / "collected" / DATE / "signals.jsonl"
    _write_bytes(collected, CORRUPTIONS[corruption])
    normalized = data_dir / "normalized" / DATE / "signals.jsonl"
    _write_bytes(normalized, b'{"previous": true}\n')
    topics = data_dir / "topics" / DATE / "topics.jsonl"
    _write_bytes(topics, b'{"previous": true}\n')

    assert main(["normalize", "--date", DATE, "--data-dir", str(data_dir)]) == 1

    message = _assert_recorded(data_dir, "normalize", collected)
    if corruption == "missing_key":
        assert message.endswith("missing key 'signal_id'")
    assert normalized.read_bytes() == b'{"previous": true}\n'
    assert topics.read_bytes() == b'{"previous": true}\n'
    assert not (data_dir / "events" / DATE / "events.jsonl").exists()
    assert "normalize" not in _state(data_dir)["stages_completed"]


@pytest.mark.parametrize("corruption", list(CORRUPTIONS))
def test_score_records_corrupt_events(tmp_path: Path, corruption: str):
    data_dir = tmp_path / "data"
    events = data_dir / "events" / DATE / "events.jsonl"
    _write_bytes(events, CORRUPTIONS[corruption])
    hot_path = data_dir / "runs" / DATE / "hot_candidates.jsonl"
    _write_bytes(hot_path, b'{"previous": true}\n')

    assert main(["score", "--date", DATE, "--data-dir", str(data_dir), "--scoring-config", "config/scoring.yaml"]) == 1

    message = _assert_recorded(data_dir, "score", events)
    if corruption == "missing_key":
        assert message.endswith("missing key 'event_id'")
    assert hot_path.read_bytes() == b'{"previous": true}\n'
    assert "score" not in _state(data_dir)["stages_completed"]


# --- select-hot / save-proposals --------------------------------------------


@pytest.mark.parametrize("corruption", list(CORRUPTIONS))
def test_select_hot_records_corrupt_hot_candidates_as_failed(tmp_path: Path, corruption: str):
    data_dir = tmp_path / "data"
    run_dir = data_dir / "runs" / DATE
    hot_path = run_dir / "hot_candidates.jsonl"
    _write_bytes(hot_path, CORRUPTIONS[corruption])
    (run_dir / "selection_input.json").write_text(
        json.dumps({"assessments": [], "screened_ids": [], "selection_reason": "候補を確認した"}),
        encoding="utf-8",
    )

    assert main(["select-hot", "--date", DATE, "--data-dir", str(data_dir)]) == 1

    message = _assert_recorded(data_dir, "select-hot", hot_path)
    if corruption == "missing_key":
        assert message.endswith("missing key 'hot_id'")
    result = _state(data_dir)["stage_results"]["select-hot"]
    assert result == {"status": "failed", "reason": f"corrupt_input: {message}"}
    assert hot_path.read_bytes() == CORRUPTIONS[corruption]


@pytest.mark.parametrize("corruption", list(CORRUPTIONS))
def test_save_proposals_records_corrupt_hot_candidates_as_failed(tmp_path: Path, corruption: str):
    data_dir = tmp_path / "data"
    run_dir = data_dir / "runs" / DATE
    hot_path = run_dir / "hot_candidates.jsonl"
    _write_bytes(hot_path, CORRUPTIONS[corruption])
    proposals_path = run_dir / "article_proposals.jsonl"
    _write_bytes(proposals_path, b'{"previous": true}\n')
    input_path = tmp_path / "draft_proposals.json"
    # v2 input (#11): an empty proposals list, so only the broken hot_candidates.jsonl can fail.
    input_path.write_text(json.dumps({"schema_version": 2, "proposals": []}), encoding="utf-8")

    assert main(["save-proposals", "--date", DATE, "--data-dir", str(data_dir), "--input", str(input_path)]) == 1

    message = _assert_recorded(data_dir, "save-proposals", hot_path)
    if corruption == "missing_key":
        assert message.endswith("missing key 'hot_id'")
    result = _state(data_dir)["stage_results"]["save-proposals"]
    assert result == {"status": "failed", "reason": f"corrupt_input: {message}"}
    assert proposals_path.read_bytes() == b'{"previous": true}\n'


def test_save_proposals_reads_selected_ids_through_the_decoder(tmp_path: Path):
    data_dir = tmp_path / "data"
    write_jsonl(data_dir / "runs" / DATE / "hot_candidates.jsonl", [_candidate()])
    input_path = tmp_path / "draft_proposals.json"
    proposal = {**asdict(_proposal()), "schema_version": 2, "quality": _quality()}
    input_path.write_text(json.dumps({"schema_version": 2, "proposals": [proposal]}, ensure_ascii=False), encoding="utf-8")

    assert main(["save-proposals", "--date", DATE, "--data-dir", str(data_dir), "--input", str(input_path)]) == 0
    assert _state(data_dir)["stage_results"]["save-proposals"]["status"] == "completed"


def test_save_proposals_checks_input_format_before_reading_hot_candidates(tmp_path: Path):
    """The agent's own input is checked first (as before #11): an old-format input is
    deprecated_input even when hot_candidates.jsonl is also broken."""
    data_dir = tmp_path / "data"
    _write_bytes(data_dir / "runs" / DATE / "hot_candidates.jsonl", CORRUPTIONS["bad_json"])
    input_path = tmp_path / "draft_proposals.json"
    input_path.write_text("[]", encoding="utf-8")

    assert main(["save-proposals", "--date", DATE, "--data-dir", str(data_dir), "--input", str(input_path)]) == 1

    assert [e["type"] for e in _state(data_dir)["errors"] if e["source"] == "save-proposals"] == ["deprecated_input"]


def test_save_proposals_reports_corrupt_hot_candidates_before_deferral_reason(tmp_path: Path):
    """Whether deferral_reason is required depends on the selection, so a broken
    hot_candidates.jsonl is reported as corrupt_input, not as a deferral_reason error."""
    data_dir = tmp_path / "data"
    _write_bytes(data_dir / "runs" / DATE / "hot_candidates.jsonl", CORRUPTIONS["bad_json"])
    input_path = tmp_path / "draft_proposals.json"
    input_path.write_text(json.dumps({"schema_version": 2, "proposals": [], "deferral_reason": "保留"}), encoding="utf-8")

    assert main(["save-proposals", "--date", DATE, "--data-dir", str(data_dir), "--input", str(input_path)]) == 1

    assert [e["type"] for e in _state(data_dir)["errors"] if e["source"] == "save-proposals"] == ["corrupt_input"]


# --- report ------------------------------------------------------------------


def _prepare_report_inputs(data_dir: Path, *, stage_results: dict | None = None) -> None:
    run_dir = data_dir / "runs" / DATE
    state = {
        "run_id": "2026-09-25T00:00:00+00:00",
        "since": DATE,
        "until": DATE,
        "sources": ["github"],
        "stages_completed": ["collect", "normalize", "score", "select-hot", "save-proposals"],
        "input_counts": {"github": 1},
        "output_counts": {},
        "errors": [],
    }
    if stage_results is not None:
        state["stage_results"] = stage_results
    save_run_state(data_dir, DATE, state)
    write_jsonl(run_dir / "hot_candidates.jsonl", [_candidate()])
    write_jsonl(run_dir / "article_proposals.jsonl", [_proposal()])
    write_jsonl(
        data_dir / "normalized" / DATE / "signals.jsonl",
        [{"source": "github", "title": "Signal A", "url": "https://example.com/a", "summary": "概要"}],
    )


COMPLETED = {
    "select-hot": {"status": "completed", "reason": "選抜した", "candidate_count": 1, "screened_count": 1, "unreviewed_count": 0, "selected_count": 1},
    "save-proposals": {"status": "completed", "reason": "", "proposal_count": 1},
}


def _report(tmp_path: Path, data_dir: Path) -> tuple[int, str]:
    reports_dir = tmp_path / "reports"
    code = main(
        [
            "report",
            "--date",
            DATE,
            "--data-dir",
            str(data_dir),
            "--reports-dir",
            str(reports_dir),
            "--runtime-config",
            str(tmp_path / "missing-runtime.yaml"),
        ]
    )
    report_path = reports_dir / "daily" / f"{DATE}.md"
    return code, report_path.read_text(encoding="utf-8") if report_path.exists() else ""


def _section(markdown: str, heading: str) -> str:
    start = markdown.index(f"## {heading}\n")
    end = markdown.find("\n## ", start + 1)
    return markdown[start:] if end == -1 else markdown[start:end]


def _assert_report_recorded(tmp_path: Path, data_dir: Path, path: Path, markdown: str) -> str:
    message = _assert_recorded(data_dir, "report", path)
    run = read_jsonl(data_dir / "runs" / DATE / "run.jsonl")[0]
    assert {"source": "report", "type": "corrupt_input", "message": message} in run["errors"]
    assert run["report_paths"] == [str(tmp_path / "reports" / "daily" / f"{DATE}.md")]
    assert f"- report: corrupt_input - {message}" in _section(markdown, "Errors")
    return message


@pytest.mark.parametrize("corruption", list(CORRUPTIONS))
def test_report_marks_unreadable_hot_candidates(tmp_path: Path, corruption: str):
    data_dir = tmp_path / "data"
    _prepare_report_inputs(data_dir, stage_results=COMPLETED)
    hot_path = data_dir / "runs" / DATE / "hot_candidates.jsonl"
    _write_bytes(hot_path, CORRUPTIONS[corruption])

    code, markdown = _report(tmp_path, data_dir)

    assert code == 0
    _assert_report_recorded(tmp_path, data_dir, hot_path, markdown)
    section = _section(markdown, "選抜HOT")
    assert "hot_candidates.jsonl を読めなかったため表示できません(Errors を参照)。" in section
    assert "選抜結果が見つかりません" not in section


def test_report_unreadable_hot_candidates_replaces_legacy_no_selection_line(tmp_path: Path):
    data_dir = tmp_path / "data"
    _prepare_report_inputs(data_dir, stage_results=None)
    _write_bytes(data_dir / "runs" / DATE / "hot_candidates.jsonl", CORRUPTIONS["bad_json"])

    code, markdown = _report(tmp_path, data_dir)

    assert code == 0
    section = _section(markdown, "選抜HOT")
    assert "hot_candidates.jsonl を読めなかったため表示できません(Errors を参照)。" in section
    assert "本日の選抜HOTはありません。" not in section


@pytest.mark.parametrize("deferred", [False, True])
@pytest.mark.parametrize("corruption", list(CORRUPTIONS))
def test_report_marks_unreadable_article_proposals(tmp_path: Path, corruption: str, deferred: bool):
    data_dir = tmp_path / "data"
    stage_results = dict(COMPLETED)
    if deferred:
        stage_results["save-proposals"] = {"status": "deferred", "reason": "根拠不足", "proposal_count": 0}
    _prepare_report_inputs(data_dir, stage_results=stage_results)
    proposals_path = data_dir / "runs" / DATE / "article_proposals.jsonl"
    _write_bytes(proposals_path, CORRUPTIONS[corruption])

    code, markdown = _report(tmp_path, data_dir)

    assert code == 0
    message = _assert_report_recorded(tmp_path, data_dir, proposals_path, markdown)
    if corruption == "missing_key":
        assert message.endswith("missing key 'proposal_id'")
    section = _section(markdown, "選抜HOT")
    assert "### Tool A" in section
    assert "article_proposals.jsonl を読めなかったため表示できません(Errors を参照)。" in section
    assert "記事企画なし" not in section


@pytest.mark.parametrize("corruption", JSON_LEVEL)
def test_report_marks_unreadable_normalized_signals(tmp_path: Path, corruption: str):
    data_dir = tmp_path / "data"
    _prepare_report_inputs(data_dir, stage_results=COMPLETED)
    signals_path = data_dir / "normalized" / DATE / "signals.jsonl"
    _write_bytes(signals_path, CORRUPTIONS[corruption])

    code, markdown = _report(tmp_path, data_dir)

    assert code == 0
    _assert_report_recorded(tmp_path, data_dir, signals_path, markdown)
    section = _section(markdown, "収集Source一覧")
    assert "signals.jsonl を読めなかったため表示できません(Errors を参照)。" in section
    assert "### github" not in section
    # The selection section is unaffected by an unreadable signals file.
    assert "### Tool A" in _section(markdown, "選抜HOT")


def test_report_signals_without_required_keys_are_not_corrupt(tmp_path: Path):
    data_dir = tmp_path / "data"
    _prepare_report_inputs(data_dir, stage_results=COMPLETED)
    _write_bytes(data_dir / "normalized" / DATE / "signals.jsonl", CORRUPTIONS["missing_key"])

    code, _ = _report(tmp_path, data_dir)

    assert code == 0
    assert _corrupt_errors(data_dir, "report") == []


def test_report_rerun_after_fix_clears_corrupt_input(tmp_path: Path):
    data_dir = tmp_path / "data"
    _prepare_report_inputs(data_dir, stage_results=COMPLETED)
    hot_path = data_dir / "runs" / DATE / "hot_candidates.jsonl"
    _write_bytes(hot_path, CORRUPTIONS["bad_json"])
    assert _report(tmp_path, data_dir)[0] == 0
    assert len(_corrupt_errors(data_dir, "report")) == 1

    write_jsonl(hot_path, [_candidate()])
    code, markdown = _report(tmp_path, data_dir)

    assert code == 0
    assert _corrupt_errors(data_dir, "report") == []
    assert "を読めなかったため表示できません" not in markdown


def test_select_hot_records_decoder_value_error(tmp_path: Path):
    data_dir = tmp_path / "data"
    run_dir = data_dir / "runs" / DATE
    record = asdict(_candidate(selected=False))
    record["score"] = "abc"
    write_jsonl(run_dir / "hot_candidates.jsonl", [record])
    (run_dir / "selection_input.json").write_text(
        json.dumps({"assessments": [], "screened_ids": [], "selection_reason": "候補を確認した"}),
        encoding="utf-8",
    )

    assert main(["select-hot", "--date", DATE, "--data-dir", str(data_dir)]) == 1

    [error] = _corrupt_errors(data_dir, "select-hot")
    assert error["message"].startswith(f"{run_dir / 'hot_candidates.jsonl'}:1: invalid record: ")


def test_score_records_unreadable_file_without_line_number(tmp_path: Path):
    data_dir = tmp_path / "data"
    events = data_dir / "events" / DATE / "events.jsonl"
    events.mkdir(parents=True)  # exists but cannot be opened as a file

    assert main(["score", "--date", DATE, "--data-dir", str(data_dir), "--scoring-config", "config/scoring.yaml"]) == 1

    [error] = _corrupt_errors(data_dir, "score")
    assert error["message"].startswith(f"{events}: ")


def test_report_shows_failed_proposals_line_and_note_together(tmp_path: Path):
    data_dir = tmp_path / "data"
    stage_results = dict(COMPLETED)
    stage_results["save-proposals"] = {"status": "failed", "reason": "write_error: disk full"}
    _prepare_report_inputs(data_dir, stage_results=stage_results)
    _write_bytes(data_dir / "runs" / DATE / "article_proposals.jsonl", CORRUPTIONS["bad_json"])

    code, markdown = _report(tmp_path, data_dir)

    assert code == 0
    section = _section(markdown, "選抜HOT")
    assert "記事企画の保存は失敗(write_error: disk full)。" in section
    assert "article_proposals.jsonl を読めなかったため表示できません(Errors を参照)。" in section


def test_save_proposals_reports_structure_error_before_corrupt_hot_candidates(tmp_path: Path):
    data_dir = tmp_path / "data"
    _write_bytes(data_dir / "runs" / DATE / "hot_candidates.jsonl", CORRUPTIONS["bad_json"])
    input_path = tmp_path / "draft_proposals.json"
    input_path.write_text(json.dumps({"schema_version": 2, "proposals": [], "extra": 1}), encoding="utf-8")

    assert main(["save-proposals", "--date", DATE, "--data-dir", str(data_dir), "--input", str(input_path)]) == 1

    assert [e["type"] for e in _state(data_dir)["errors"] if e["source"] == "save-proposals"] == ["invalid_input"]


def test_save_proposals_with_proposals_reports_corrupt_hot_candidates(tmp_path: Path):
    data_dir = tmp_path / "data"
    run_dir = data_dir / "runs" / DATE
    _write_bytes(run_dir / "hot_candidates.jsonl", CORRUPTIONS["bad_json"])
    proposals_path = run_dir / "article_proposals.jsonl"
    _write_bytes(proposals_path, b'{"previous": true}\n')
    proposal = {**asdict(_proposal()), "schema_version": 2, "quality": _quality()}
    input_path = tmp_path / "draft_proposals.json"
    input_path.write_text(json.dumps({"schema_version": 2, "proposals": [proposal]}, ensure_ascii=False), encoding="utf-8")

    assert main(["save-proposals", "--date", DATE, "--data-dir", str(data_dir), "--input", str(input_path)]) == 1

    assert [e["type"] for e in _state(data_dir)["errors"] if e["source"] == "save-proposals"] == ["corrupt_input"]
    assert proposals_path.read_bytes() == b'{"previous": true}\n'
