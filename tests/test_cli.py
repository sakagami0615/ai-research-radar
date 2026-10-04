from pathlib import Path
from datetime import date

import ai_research_radar.cli.main as cli_module
from ai_research_radar.cli.main import main
from ai_research_radar.sources.fixtures import FixtureAdapter


def test_cli_daily_runs_with_fixture_source(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        cli_module,
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
            "daily",
            "--since",
            "2026-09-24",
            "--until",
            "2026-09-25",
            "--data-dir",
            str(tmp_path / "data"),
            "--reports-dir",
            str(tmp_path / "reports"),
            "--sources-config",
            "config/sources.yaml",
            "--minimum-score",
            "0",
        ]
    )

    assert exit_code == 0
    assert (tmp_path / "reports" / "daily" / "2026-09-25.md").exists()


def test_cli_rejects_unknown_command():
    assert main(["unknown"]) == 2


def test_cli_daily_uses_yesterday_to_today_when_period_is_omitted(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        cli_module,
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
            "daily",
            "--data-dir",
            str(tmp_path / "data"),
            "--reports-dir",
            str(tmp_path / "reports"),
            "--minimum-score",
            "0",
        ]
    )

    assert exit_code == 0
    assert (tmp_path / "reports" / "daily" / f"{date.today().isoformat()}.md").exists()


def test_cli_daily_passes_runtime_timezone_to_report(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        cli_module,
        "build_adapters",
        lambda configs: [
            FixtureAdapter(
                source_name="github",
                source_family="technology",
                fixture_path=Path("tests/fixtures/sample_raw_items.jsonl"),
            )
        ],
    )
    runtime_config = tmp_path / "runtime.yaml"
    runtime_config.write_text("runtime:\n  timezone: Asia/Tokyo\n", encoding="utf-8")

    exit_code = main(
        [
            "daily",
            "--since",
            "2026-09-24T00:00:00+00:00",
            "--until",
            "2026-09-25T00:00:00+00:00",
            "--data-dir",
            str(tmp_path / "data"),
            "--reports-dir",
            str(tmp_path / "reports"),
            "--runtime-config",
            str(runtime_config),
            "--minimum-score",
            "0",
        ]
    )

    assert exit_code == 0
    report = (tmp_path / "reports" / "daily" / "2026-09-25.md").read_text(encoding="utf-8")
    assert "| Period | 2026-09-24 09:00 〜 2026-09-25 09:00 (JST) |" in report
