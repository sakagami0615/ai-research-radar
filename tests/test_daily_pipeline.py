from datetime import datetime, timezone
from pathlib import Path

from ai_research_radar.pipeline.daily import run_daily
from ai_research_radar.schemas.models import RawItem
from ai_research_radar.sources.base import SourceAdapter, SourceError
from ai_research_radar.sources.fixtures import FixtureAdapter
from ai_research_radar.storage.jsonl import read_jsonl


class FailingAdapter(SourceAdapter):
    source_name = "arxiv"
    source_family = "research"

    def collect(self, since: str, until: str):
        raise SourceError("arxiv", "network_error", "timeout")

    def normalize(self, item):
        raise AssertionError("normalize should not be called")


class FailingNormalizeAdapter(SourceAdapter):
    source_name = "papers"
    source_family = "research"

    def collect(self, since: str, until: str):
        return [
            RawItem(
                source="papers",
                fetched_at=datetime(2026, 9, 25, tzinfo=timezone.utc),
                raw_id="paper-1",
                raw_url="https://example.com/paper-1",
                payload={},
            )
        ]

    def normalize(self, item):
        raise SourceError("papers", "normalization_error", "invalid payload")


def test_run_daily_writes_jsonl_and_markdown(tmp_path: Path):
    adapter = FixtureAdapter(
        source_name="github",
        source_family="technology",
        fixture_path=Path("tests/fixtures/sample_raw_items.jsonl"),
    )

    result = run_daily(
        adapters=[adapter],
        since="2026-09-24",
        until="2026-09-25",
        output_dir=tmp_path / "data",
        report_dir=tmp_path / "reports",
        hot_limit=5,
        minimum_score=0,
    )

    assert result.report_path.exists()
    assert (tmp_path / "data" / "raw" / "2026-09-25" / "github.jsonl").exists()
    assert (tmp_path / "data" / "normalized" / "2026-09-25" / "signals.jsonl").exists()
    assert (tmp_path / "data" / "events" / "2026-09-25" / "events.jsonl").exists()
    assert (tmp_path / "data" / "topics" / "2026-09-25" / "topics.jsonl").exists()
    raw = read_jsonl(tmp_path / "data" / "raw" / "2026-09-25" / "github.jsonl")
    events = read_jsonl(tmp_path / "data" / "events" / "2026-09-25" / "events.jsonl")
    topics = read_jsonl(tmp_path / "data" / "topics" / "2026-09-25" / "topics.jsonl")
    hot = read_jsonl(tmp_path / "data" / "runs" / "2026-09-25" / "hot_candidates.jsonl")
    assert events[0]["event_id"].startswith("event:")
    assert topics[0]["events"] == [events[0]["event_id"]]
    assert hot[0]["hot_id"].startswith("hot:event:")
    assert raw[0]["payload"]["raw"]["raw_id"] == "owner/agent-runtime"
    assert "AI Daily Radar 2026-09-25" in result.report_path.read_text(encoding="utf-8")
    report_text = result.report_path.read_text(encoding="utf-8")
    assert "## 収集Source一覧" in report_text
    assert "### github (1件)" in report_text
    assert "### other (1件)" in report_text
    assert "## 注目候補(選抜外)" in report_text
    assert "## 新モデルリリース" in report_text
    assert (tmp_path / "data" / "runs" / "2026-09-25" / "report_digest.json").exists()


def test_run_daily_continues_when_source_fails(tmp_path: Path):
    adapter = FixtureAdapter(
        source_name="github",
        source_family="technology",
        fixture_path=Path("tests/fixtures/sample_raw_items.jsonl"),
    )

    result = run_daily(
        adapters=[FailingAdapter(), adapter],
        since="2026-09-24",
        until="2026-09-25",
        output_dir=tmp_path / "data",
        report_dir=tmp_path / "reports",
        hot_limit=5,
        minimum_score=0,
    )

    assert result.run.errors[0]["source"] == "arxiv"
    assert result.report_path.exists()
    report = result.report_path.read_text(encoding="utf-8")
    assert "arxiv" in report
    assert "timeout" in report


def test_run_daily_continues_when_normalization_raises_source_error(tmp_path: Path):
    adapter = FixtureAdapter(
        source_name="github",
        source_family="technology",
        fixture_path=Path("tests/fixtures/sample_raw_items.jsonl"),
    )

    result = run_daily(
        adapters=[FailingNormalizeAdapter(), adapter],
        since="2026-09-24",
        until="2026-09-25",
        output_dir=tmp_path / "data",
        report_dir=tmp_path / "reports",
        minimum_score=0,
    )

    assert result.run.errors[0]["source"] == "papers"
    assert result.events
    assert "invalid payload" in result.report_path.read_text(encoding="utf-8")


def test_run_daily_records_report_write_failure_in_run_metadata(tmp_path: Path):
    adapter = FixtureAdapter(
        source_name="github",
        source_family="technology",
        fixture_path=Path("tests/fixtures/sample_raw_items.jsonl"),
    )
    report_dir = tmp_path / "reports"
    report_dir.write_text("not a directory", encoding="utf-8")

    import pytest

    with pytest.raises(OSError):
        run_daily(
            adapters=[adapter],
            since="2026-09-24",
            until="2026-09-25",
            output_dir=tmp_path / "data",
            report_dir=report_dir,
            minimum_score=0,
        )

    run = read_jsonl(tmp_path / "data" / "runs" / "2026-09-25" / "run.jsonl")[0]
    assert run["errors"][-1]["type"] == "report_write_error"
