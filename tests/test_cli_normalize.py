from pathlib import Path

from ai_research_radar.cli.main import main
from ai_research_radar.sources.fixtures import FixtureAdapter
from ai_research_radar.storage.jsonl import read_jsonl


def _collect_first(tmp_path: Path, monkeypatch) -> None:
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


def test_cli_normalize_builds_events_and_topics(tmp_path: Path, monkeypatch):
    _collect_first(tmp_path, monkeypatch)

    exit_code = main(
        ["normalize", "--date", "2026-09-25", "--data-dir", str(tmp_path / "data")]
    )

    assert exit_code == 0
    events = read_jsonl(tmp_path / "data" / "events" / "2026-09-25" / "events.jsonl")
    topics = read_jsonl(tmp_path / "data" / "topics" / "2026-09-25" / "topics.jsonl")
    assert events[0]["event_id"].startswith("event:")
    assert topics[0]["events"] == [events[0]["event_id"]]


def test_cli_normalize_fails_when_collected_signals_missing(tmp_path: Path):
    exit_code = main(
        ["normalize", "--date", "2026-09-25", "--data-dir", str(tmp_path / "data")]
    )

    assert exit_code == 1


def test_cli_normalize_preserves_run_state_when_write_fails(tmp_path: Path, monkeypatch):
    import json

    _collect_first(tmp_path, monkeypatch)
    data_dir = tmp_path / "data"
    # Pre-create a plain file where the "normalized" output directory needs to go,
    # so write_jsonl's mkdir(parents=True) fails.
    (data_dir / "normalized").mkdir(parents=True)
    (data_dir / "normalized" / "2026-09-25").write_text("not a directory", encoding="utf-8")

    exit_code = main(["normalize", "--date", "2026-09-25", "--data-dir", str(data_dir)])

    assert exit_code == 1
    state = json.loads(
        (data_dir / "runs" / "2026-09-25" / "run_state.json").read_text(encoding="utf-8")
    )
    assert "normalize" not in state["stages_completed"]
    assert any(error["source"] == "normalize" for error in state["errors"])
