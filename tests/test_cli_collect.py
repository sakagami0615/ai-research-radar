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


def test_cli_collect_resolves_default_period_from_previous_runs(tmp_path: Path, monkeypatch):
    observed: dict[str, object] = {}

    class CapturingAdapter(FixtureAdapter):
        def collect(self, since: str, until: str):
            observed.update(since=since, until=until)
            return []

    def fake_resolve(data_dir, max_lookback_days):
        observed.update(data_dir=data_dir, max_lookback_days=max_lookback_days)
        return ("2026-10-03T00:00:00+00:00", "2026-10-04T00:00:00+00:00")

    monkeypatch.setattr(collect_command, "resolve_default_period", fake_resolve)
    monkeypatch.setattr(
        collect_command,
        "build_adapters",
        lambda configs: [
            CapturingAdapter(
                source_name="github",
                source_family="technology",
                fixture_path=Path("tests/fixtures/sample_raw_items.jsonl"),
            )
        ],
    )
    runtime_config = tmp_path / "runtime.yaml"
    runtime_config.write_text("collection:\n  max_lookback_days: 3\n", encoding="utf-8")

    assert main(["collect", "--data-dir", str(tmp_path / "data"), "--runtime-config", str(runtime_config)]) == 0
    assert observed == {
        "data_dir": tmp_path / "data",
        "max_lookback_days": 3,
        "since": "2026-10-03T00:00:00+00:00",
        "until": "2026-10-04T00:00:00+00:00",
    }
    assert (tmp_path / "data" / "runs" / "2026-10-04" / "run_state.json").exists()


def test_cli_collect_uses_default_lookback_when_runtime_config_is_missing(tmp_path: Path, monkeypatch):
    observed: dict[str, object] = {}

    def fake_resolve(data_dir, max_lookback_days):
        observed.update(max_lookback_days=max_lookback_days)
        return ("2026-10-03T00:00:00+00:00", "2026-10-04T00:00:00+00:00")

    monkeypatch.setattr(collect_command, "resolve_default_period", fake_resolve)
    monkeypatch.setattr(collect_command, "build_adapters", lambda configs: [])

    exit_code = main(
        ["collect", "--data-dir", str(tmp_path / "data"), "--runtime-config", str(tmp_path / "missing.yaml")]
    )

    assert exit_code == 0
    assert observed == {"max_lookback_days": 7}


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


def test_cli_collect_drops_stale_error_when_source_recovers_on_rerun(tmp_path: Path, monkeypatch):
    from ai_research_radar.sources.base import SourceAdapter, SourceError

    class FailingAdapter(SourceAdapter):
        source_name = "arxiv"
        source_family = "research"

        def collect(self, since: str, until: str):
            raise SourceError("arxiv", "network_error", "timeout")

        def normalize(self, item):
            raise AssertionError("normalize should not be called")

    monkeypatch.setattr(collect_command, "build_adapters", lambda configs: [FailingAdapter()])
    data_dir = tmp_path / "data"
    args = [
        "collect",
        "--since",
        "2026-09-24",
        "--until",
        "2026-09-25",
        "--data-dir",
        str(data_dir),
        "--sources-config",
        "config/sources.yaml",
    ]
    assert main(args) == 0

    monkeypatch.setattr(
        collect_command,
        "build_adapters",
        lambda configs: [
            FixtureAdapter(
                source_name="arxiv",
                source_family="research",
                fixture_path=Path("tests/fixtures/sample_raw_items.jsonl"),
            )
        ],
    )
    assert main(args) == 0

    state = json.loads(
        (data_dir / "runs" / "2026-09-25" / "run_state.json").read_text(encoding="utf-8")
    )
    assert state["errors"] == []


def test_cli_collect_preserves_run_state_when_signals_write_fails(tmp_path: Path, monkeypatch):
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

    data_dir = tmp_path / "data"
    collected_dir = data_dir / "collected" / "2026-09-25"
    collected_dir.parent.mkdir(parents=True)
    # Create a file where write_jsonl expects to mkdir a directory, so its
    # `path.parent.mkdir(parents=True, exist_ok=True)` call fails.
    collected_dir.write_text("not a directory", encoding="utf-8")

    exit_code = main(
        [
            "collect",
            "--since",
            "2026-09-24",
            "--until",
            "2026-09-25",
            "--data-dir",
            str(data_dir),
            "--sources-config",
            "config/sources.yaml",
        ]
    )

    assert exit_code == 1

    state_path = data_dir / "runs" / "2026-09-25" / "run_state.json"
    assert state_path.exists()
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert any(error["type"] == "signals_write_error" for error in state["errors"])
    assert "collect" not in state["stages_completed"]
