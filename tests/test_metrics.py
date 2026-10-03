from datetime import datetime, timedelta, timezone

from ai_research_radar.normalization.scores import normalize_quality_batch
from ai_research_radar.schemas.models import CanonicalSignal


def _signal(name, published, fetched, metrics):
    return CanonicalSignal(name, "github", "technology", "tool", name, "https://x/" + name, published, fetched, "", [], metrics, {}, {})


def test_freshness_boundaries():
    fetched = datetime(2026, 9, 29, tzinfo=timezone.utc)
    signals = [_signal(str(hours), fetched - timedelta(hours=hours), fetched, {}) for hours in (0, 84, 168)]
    result = normalize_quality_batch(signals)
    assert [item.quality["freshness_score"] for item in result] == [100.0, 50.0, 0.0]


def test_rank_missing_and_ties():
    fetched = datetime(2026, 9, 29, tzinfo=timezone.utc)
    signals = [_signal(str(i), fetched, fetched, {"stars": value}) for i, value in enumerate((0, 0, 10, None))]
    result = normalize_quality_batch(signals)
    assert [item.quality["popularity_rank"] for item in result] == [25.0, 25.0, 100.0, None]


def test_invalid_metrics_never_rank():
    fetched = datetime(2026, 9, 29, tzinfo=timezone.utc)
    result = normalize_quality_batch([_signal(str(i), fetched, fetched, {"stars": value}) for i, value in enumerate((float("nan"), float("inf"), True, "bad"))])
    assert all(item.quality["popularity_rank"] is None for item in result)
    assert all(item.quality["metrics"][0]["status"] == "invalid" for item in result)


def test_keyword_has_no_popularity():
    fetched = datetime(2026, 9, 29, tzinfo=timezone.utc)
    result = normalize_quality_batch([_signal("x", fetched, fetched, {"ai_keyword_strength": 1.0})])
    assert result[0].quality["popularity_rank"] is None


def test_future_and_missing_date_have_unknown_freshness():
    fetched = datetime(2026, 9, 29, tzinfo=timezone.utc)
    assert normalize_quality_batch([_signal("future", fetched + timedelta(hours=1), fetched, {})])[0].quality["freshness_score"] is None
