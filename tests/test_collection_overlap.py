from datetime import datetime, timezone
from pathlib import Path

import pytest

import ai_research_radar.cli.commands.collect as collect_command
import ai_research_radar.cli.commands.daily as daily_command
from ai_research_radar.cli.main import main
from ai_research_radar.config.settings import SourceConfig
from ai_research_radar.pipeline.daily import run_daily
from ai_research_radar.schemas.models import RawItem
from ai_research_radar.sources.base import SourceAdapter
from ai_research_radar.sources.collection import collect_new_items
from ai_research_radar.sources.fixtures import FixtureAdapter
from ai_research_radar.sources.public import build_adapters
from ai_research_radar.storage.jsonl import read_jsonl, write_jsonl

SINCE = "2026-10-04T00:00:00+00:00"
UNTIL = "2026-10-05T00:00:00+00:00"
RUN_DATE = "2026-10-05"


class RecordingAdapter(SourceAdapter):
    source_name = "official_blogs"
    source_family = "official"

    def __init__(self, raw_ids: list[str], overlap_hours: int = 0) -> None:
        self.raw_ids = raw_ids
        self.overlap_hours = overlap_hours
        self.calls: list[tuple[str, str]] = []

    def collect(self, since: str, until: str) -> list[RawItem]:
        self.calls.append((since, until))
        return [
            RawItem("official_blogs", datetime(2026, 10, 5, tzinfo=timezone.utc), raw_id, f"https://example.com/{raw_id}", {"title": raw_id})
            for raw_id in self.raw_ids
        ]

    def normalize(self, item):
        raise AssertionError("normalize is not used here")


def _write_normalized(data_dir: Path, day: str, *records: dict) -> None:
    write_jsonl(data_dir / "normalized" / day / "signals.jsonl", list(records))


def test_overlap_source_is_collected_from_overlap_hours_before_since(tmp_path: Path):
    adapter = RecordingAdapter(["a"], overlap_hours=48)

    collect_new_items(adapter, SINCE, UNTIL, tmp_path, RUN_DATE, use_overlap=True)

    assert adapter.calls == [("2026-10-02T00:00:00+00:00", UNTIL)]


def test_overlap_drops_items_already_normalized_on_earlier_dates(tmp_path: Path):
    _write_normalized(tmp_path, "2026-10-03", {"signal_id": "official_blogs:a", "metadata": {}})
    _write_normalized(
        tmp_path,
        "2026-10-04",
        {"signal_id": "hackernews:x", "metadata": {"merged_signal_ids": ["hackernews:x", "official_blogs:b"]}},
    )
    # The target date is overwritten by a same-day rerun, so it is not a baseline.
    _write_normalized(tmp_path, "2026-10-05", {"signal_id": "official_blogs:c", "metadata": {}})
    adapter = RecordingAdapter(["a", "b", "c", "d"], overlap_hours=48)

    items = collect_new_items(adapter, SINCE, UNTIL, tmp_path, RUN_DATE, use_overlap=True)

    assert [item.raw_id for item in items] == ["c", "d"]


def test_overlap_keeps_items_that_only_reached_raw(tmp_path: Path):
    # A run stopped after collect: raw exists but nothing was normalized/reported.
    write_jsonl(tmp_path / "raw" / "2026-10-04" / "official_blogs.jsonl", [{"raw_id": "a"}])
    adapter = RecordingAdapter(["a"], overlap_hours=48)

    items = collect_new_items(adapter, SINCE, UNTIL, tmp_path, RUN_DATE, use_overlap=True)

    assert [item.raw_id for item in items] == ["a"]


def test_overlap_ignores_unreadable_normalized_file(tmp_path: Path):
    path = tmp_path / "normalized" / "2026-10-04" / "signals.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text("not json\n", encoding="utf-8")
    adapter = RecordingAdapter(["a"], overlap_hours=48)

    items = collect_new_items(adapter, SINCE, UNTIL, tmp_path, RUN_DATE, use_overlap=True)

    assert [item.raw_id for item in items] == ["a"]


@pytest.mark.parametrize(("overlap_hours", "use_overlap"), [(48, False), (0, True)])
def test_without_overlap_source_is_collected_as_is(tmp_path: Path, overlap_hours: int, use_overlap: bool):
    _write_normalized(tmp_path, "2026-10-04", {"signal_id": "official_blogs:a", "metadata": {}})
    adapter = RecordingAdapter(["a"], overlap_hours=overlap_hours)

    items = collect_new_items(adapter, SINCE, UNTIL, tmp_path, RUN_DATE, use_overlap=use_overlap)

    assert adapter.calls == [(SINCE, UNTIL)]
    assert [item.raw_id for item in items] == ["a"]


@pytest.mark.parametrize(("value", "expected"), [(48, 48), (0, 0), (-1, 0), ("48", 0), (True, 0), (None, 0)])
def test_build_adapters_reads_overlap_hours(value, expected):
    options = {} if value is None else {"overlap_hours": value}
    adapter = build_adapters([SourceConfig("ollama", "technology", "ollama", True, False, options)])[0]

    assert adapter.overlap_hours == expected


class OverlapFixtureAdapter(FixtureAdapter):
    def __init__(self, calls: list[tuple[str, str]]) -> None:
        super().__init__("github", "technology", Path("tests/fixtures/sample_raw_items.jsonl"))
        self.overlap_hours = 48
        self.calls = calls

    def collect(self, since: str, until: str):
        self.calls.append((since, until))
        return super().collect(since, until)


def test_cli_collect_applies_overlap_only_when_period_is_omitted(tmp_path: Path, monkeypatch):
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(collect_command, "build_adapters", lambda configs: [OverlapFixtureAdapter(calls)])
    monkeypatch.setattr("ai_research_radar.periods.resolve_default_period",
        lambda data_dir, max_lookback_days: ("2026-09-25T00:00:00+00:00", "2026-09-26T00:00:00+00:00"),
    )

    assert main(["collect", "--data-dir", str(tmp_path / "data")]) == 0
    assert main(
        ["collect", "--since", "2026-09-25T00:00:00+00:00", "--until", "2026-09-26T00:00:00+00:00", "--data-dir", str(tmp_path / "data")]
    ) == 0

    assert calls == [
        ("2026-09-23T00:00:00+00:00", "2026-09-26T00:00:00+00:00"),
        ("2026-09-25T00:00:00+00:00", "2026-09-26T00:00:00+00:00"),
    ]


def test_cli_collect_drops_items_normalized_on_earlier_dates(tmp_path: Path, monkeypatch):
    data_dir = tmp_path / "data"
    fixture = read_jsonl(Path("tests/fixtures/sample_raw_items.jsonl"))
    fixture_ids = [record["raw_id"] for record in fixture]
    first = fixture[0]
    _write_normalized(data_dir, "2026-09-25", {"signal_id": f"{first['source']}:{first['raw_id']}", "metadata": {}})
    monkeypatch.setattr(collect_command, "build_adapters", lambda configs: [OverlapFixtureAdapter([])])
    monkeypatch.setattr("ai_research_radar.periods.resolve_default_period",
        lambda data_dir, max_lookback_days: ("2026-09-25T00:00:00+00:00", "2026-09-26T00:00:00+00:00"),
    )

    assert main(["collect", "--data-dir", str(data_dir)]) == 0

    raw = read_jsonl(data_dir / "raw" / "2026-09-26" / "github.jsonl")
    assert [record["raw_id"] for record in raw] == fixture_ids[1:]


def test_run_daily_applies_overlap_when_enabled(tmp_path: Path):
    calls: list[tuple[str, str]] = []

    run_daily(
        adapters=[OverlapFixtureAdapter(calls)],
        since="2026-09-25T00:00:00+00:00",
        until="2026-09-26T00:00:00+00:00",
        output_dir=tmp_path / "data",
        report_dir=tmp_path / "reports",
        minimum_score=0,
        use_overlap=True,
    )

    assert calls == [("2026-09-23T00:00:00+00:00", "2026-09-26T00:00:00+00:00")]


def test_cli_daily_applies_overlap_only_when_period_is_omitted(tmp_path: Path, monkeypatch):
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(daily_command, "build_adapters", lambda configs: [OverlapFixtureAdapter(calls)])
    monkeypatch.setattr("ai_research_radar.periods.resolve_default_period",
        lambda data_dir, max_lookback_days: ("2026-09-25T00:00:00+00:00", "2026-09-26T00:00:00+00:00"),
    )
    common = ["--data-dir", str(tmp_path / "data"), "--reports-dir", str(tmp_path / "reports"), "--minimum-score", "0"]

    assert main(["daily", *common]) == 0
    assert main(["daily", "--since", "2026-09-25T00:00:00+00:00", "--until", "2026-09-26T00:00:00+00:00", *common]) == 0

    assert calls == [
        ("2026-09-23T00:00:00+00:00", "2026-09-26T00:00:00+00:00"),
        ("2026-09-25T00:00:00+00:00", "2026-09-26T00:00:00+00:00"),
    ]
