import json
from pathlib import Path

from ai_research_radar.cli.main import main
from ai_research_radar.sources.fixtures import FixtureAdapter
from ai_research_radar.storage.jsonl import read_jsonl


def _write_scoring_config(tmp_path: Path) -> Path:
    path = tmp_path / "scoring.yaml"
    path.write_text(
        "hot_score:\n"
        "  momentum: 0.40\n"
        "  popularity: 0.25\n"
        "  cross_source: 0.20\n"
        "  credibility: 0.15\n"
        "hot_selection:\n"
        "  max_limit: 5\n"
        "  minimum_score: 0\n",
        encoding="utf-8",
    )
    return path


def _collect_and_normalize(tmp_path: Path, monkeypatch) -> None:
    import ai_research_radar.cli.commands.collect as collect_command

    monkeypatch.setattr(
        collect_command,
        "build_adapters",
        lambda configs: [
            FixtureAdapter(
                source_name="github",
                source_family="technology",
                fixture_path=Path("tests/fixtures/sample_raw_items.jsonl"),
            )
        ],
    )
    assert (
        main(
            [
                "collect",
                "--since",
                "2026-09-24",
                "--until",
                "2026-09-25",
                "--data-dir",
                str(tmp_path / "data"),
                "--sources-config",
                "config/sources.yaml",
            ]
        )
        == 0
    )
    assert main(["normalize", "--date", "2026-09-25", "--data-dir", str(tmp_path / "data")]) == 0


def test_cli_score_writes_all_candidates_as_unselected(tmp_path: Path, monkeypatch):
    _collect_and_normalize(tmp_path, monkeypatch)
    scoring_config = _write_scoring_config(tmp_path)

    exit_code = main(
        [
            "score",
            "--date",
            "2026-09-25",
            "--data-dir",
            str(tmp_path / "data"),
            "--scoring-config",
            str(scoring_config),
        ]
    )

    assert exit_code == 0
    candidates = read_jsonl(tmp_path / "data" / "runs" / "2026-09-25" / "hot_candidates.jsonl")
    assert len(candidates) >= 1
    assert all(candidate["selected"] is False for candidate in candidates)
    state = json.loads(
        (tmp_path / "data" / "runs" / "2026-09-25" / "run_state.json").read_text(encoding="utf-8")
    )
    assert state["stages_completed"][-1] == "score"
    assert state["output_counts"]["hot_candidates"] == len(candidates)


def test_cli_score_fails_and_persists_error_when_events_missing(tmp_path: Path):
    exit_code = main(["score", "--date", "2026-09-25", "--data-dir", str(tmp_path / "data")])

    assert exit_code == 1
    state = json.loads(
        (tmp_path / "data" / "runs" / "2026-09-25" / "run_state.json").read_text(encoding="utf-8")
    )
    assert any(
        error["source"] == "score" and error["type"] == "missing_input"
        for error in state["errors"]
    )


def test_cli_score_preserves_run_state_when_write_fails(tmp_path: Path, monkeypatch):
    _collect_and_normalize(tmp_path, monkeypatch)
    scoring_config = _write_scoring_config(tmp_path)
    data_dir = tmp_path / "data"
    (data_dir / "runs" / "2026-09-25").mkdir(parents=True, exist_ok=True)
    (data_dir / "runs" / "2026-09-25" / "hot_candidates.jsonl").mkdir()

    exit_code = main(
        [
            "score",
            "--date",
            "2026-09-25",
            "--data-dir",
            str(data_dir),
            "--scoring-config",
            str(scoring_config),
        ]
    )

    assert exit_code == 1
    state = json.loads(
        (data_dir / "runs" / "2026-09-25" / "run_state.json").read_text(encoding="utf-8")
    )
    assert "score" not in state["stages_completed"]
    assert any(error["source"] == "score" for error in state["errors"])
