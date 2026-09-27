import json
from pathlib import Path

import ai_research_radar.cli.commands.collect as collect_command
from ai_research_radar.cli.main import main
from ai_research_radar.sources.fixtures import FixtureAdapter
from ai_research_radar.storage.jsonl import read_jsonl


def test_cli_collect_writes_raw_and_collected_signals(tmp_path: Path, monkeypatch, capsys):
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

    exit_code = main(
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

    assert exit_code == 0
    assert (tmp_path / "data" / "raw" / "2026-09-25" / "github.jsonl").exists()
    signals = read_jsonl(tmp_path / "data" / "collected" / "2026-09-25" / "signals.jsonl")
    assert len(signals) == 2

    state = json.loads(
        (tmp_path / "data" / "runs" / "2026-09-25" / "run_state.json").read_text(encoding="utf-8")
    )
    assert state["stages_completed"] == ["collect"]
    assert state["output_counts"]["raw_items"] == 2
    assert state["input_counts"]["github"] == 2

    captured = capsys.readouterr()
    assert captured.out.strip() == "2026-09-25"


def test_cli_collect_records_source_error_and_continues(tmp_path: Path, monkeypatch):
    from ai_research_radar.sources.base import SourceAdapter, SourceError

    class FailingAdapter(SourceAdapter):
        source_name = "arxiv"
        source_family = "research"

        def collect(self, since: str, until: str):
            raise SourceError("arxiv", "network_error", "timeout")

        def normalize(self, item):
            raise AssertionError("normalize should not be called")

    monkeypatch.setattr(collect_command, "build_adapters", lambda configs: [FailingAdapter()])

    exit_code = main(
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

    assert exit_code == 0
    state = json.loads(
        (tmp_path / "data" / "runs" / "2026-09-25" / "run_state.json").read_text(encoding="utf-8")
    )
    assert state["errors"][0]["source"] == "arxiv"
    assert state["errors"][0]["type"] == "network_error"
