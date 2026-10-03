from datetime import datetime, timezone
from pathlib import Path

from ai_research_radar.normalization.history import load_metric_history
from ai_research_radar.normalization.scores import normalize_quality_batch
from ai_research_radar.schemas.models import CanonicalSignal, to_json_dict
from ai_research_radar.storage.jsonl import write_jsonl


def _signal(fetched, value):
    return CanonicalSignal("s", "github", "technology", "tool", "x", "https://x", fetched, fetched, "", [], {"stars": value}, {}, {})


def test_history_uses_prior_observation():
    old = datetime(2026, 9, 28, tzinfo=timezone.utc)
    current = datetime(2026, 9, 29, 12, tzinfo=timezone.utc)
    result = normalize_quality_batch([_signal(current, 80)], history=[_signal(old, 100)])
    metric = result[0].quality["metrics"][0]
    assert metric["delta"] == -20
    assert metric["interval_hours"] == 36


def test_missing_current_value_with_prior_history_does_not_crash():
    old = datetime(2026, 9, 28, tzinfo=timezone.utc)
    current = datetime(2026, 9, 29, 12, tzinfo=timezone.utc)
    missing_now = CanonicalSignal("s", "github", "technology", "tool", "x", "https://x", current, current, "", [], {}, {}, {})
    result = normalize_quality_batch([missing_now], history=[_signal(old, 100)])
    metric = result[0].quality["metrics"][0]
    assert metric["status"] == "missing"
    assert "delta" not in metric


def test_history_loader_reads_only_dates_before_cutoff(tmp_path: Path):
    path = tmp_path / "normalized" / "2026-09-28" / "signals.jsonl"
    write_jsonl(path, [_signal(datetime(2026, 9, 28, tzinfo=timezone.utc), 100)])
    assert len(load_metric_history(tmp_path, before=datetime(2026, 9, 29, tzinfo=timezone.utc))) == 1
