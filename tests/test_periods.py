from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from ai_research_radar.normalization.scores import is_within_period
from ai_research_radar.periods import default_period, previous_day_period


def test_default_period_is_the_previous_24_hours_in_jst():
    since, until = default_period(datetime(2026, 10, 4, 9, 0, tzinfo=ZoneInfo("Asia/Tokyo")))

    assert since == "2026-10-03T00:00:00+00:00"
    assert until == "2026-10-04T00:00:00+00:00"


def test_datetime_period_includes_start_and_excludes_after_end():
    since = "2026-10-03T18:00:00+00:00"
    until = "2026-10-04T18:00:00+00:00"

    assert is_within_period(datetime(2026, 10, 3, 18, 0, tzinfo=timezone.utc), since, until)
    assert is_within_period(datetime(2026, 10, 4, 17, 59, 59, tzinfo=timezone.utc), since, until)
    assert not is_within_period(datetime(2026, 10, 4, 18, 0, 1, tzinfo=timezone.utc), since, until)


def test_date_period_keeps_full_day_compatibility():
    value = datetime(2026, 10, 4, 23, 59, 59, tzinfo=timezone.utc)

    assert is_within_period(value, "2026-10-04", "2026-10-04")


def test_previous_day_period_preserves_explicit_until_only_compatibility():
    assert previous_day_period("2026-10-04") == "2026-10-03"
