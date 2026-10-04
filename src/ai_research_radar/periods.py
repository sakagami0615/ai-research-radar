from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo


DEFAULT_TIMEZONE = ZoneInfo("Asia/Tokyo")


def _parse(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def default_period(now: datetime | None = None) -> tuple[str, str]:
    current = now or datetime.now(DEFAULT_TIMEZONE)
    if current.tzinfo is None:
        current = current.replace(tzinfo=DEFAULT_TIMEZONE)
    current = current.astimezone(timezone.utc)
    return (current - timedelta(hours=24)).isoformat(), current.isoformat()


def period_start(value: str) -> datetime:
    return _parse(value if "T" in value else f"{value}T00:00:00+00:00")


def period_end(value: str) -> datetime:
    return _parse(value if "T" in value else f"{value}T23:59:59.999999+00:00")


def period_date(value: str) -> str:
    if "T" not in value:
        return date.fromisoformat(value).isoformat()
    return _parse(value).astimezone(DEFAULT_TIMEZONE).date().isoformat()


def previous_day_period(value: str) -> str:
    if "T" in value:
        return (period_start(value) - timedelta(days=1)).isoformat()
    return (date.fromisoformat(value) - timedelta(days=1)).isoformat()
