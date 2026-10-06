from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


DEFAULT_TIMEZONE = ZoneInfo("Asia/Tokyo")
DEFAULT_MAX_LOOKBACK_DAYS = 7


def _parse(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def resolve_default_period(
    data_dir: Path,
    now: datetime | None = None,
    max_lookback_days: int = DEFAULT_MAX_LOOKBACK_DAYS,
) -> tuple[str, str]:
    """Period used when both --since and --until are omitted.

    Collection resumes from the `until` of the latest run recorded before the
    target date, so days without a run are not lost. It never reaches back
    further than `max_lookback_days`, which is also the first-run period.
    """
    current = now or datetime.now(DEFAULT_TIMEZONE)
    if current.tzinfo is None:
        current = current.replace(tzinfo=DEFAULT_TIMEZONE)
    until = current.astimezone(timezone.utc)
    floor = until - timedelta(days=max_lookback_days)
    previous = _previous_run_until(data_dir, until)
    since = floor if previous is None else max(floor, previous)
    return since.isoformat(), until.isoformat()


def _previous_run_until(data_dir: Path, until: datetime) -> datetime | None:
    # The target date's own run.jsonl is skipped so that a same-day rerun
    # collects the same period again (raw files are overwritten, not merged).
    runs_dir = data_dir / "runs"
    if not runs_dir.is_dir():
        return None
    target = date.fromisoformat(period_date(until.isoformat()))
    days: list[date] = []
    for child in runs_dir.iterdir():
        try:
            day = date.fromisoformat(child.name)
        except ValueError:
            continue
        if day < target:
            days.append(day)
    for day in sorted(days, reverse=True):
        recorded = _recorded_untils(runs_dir / day.isoformat() / "run.jsonl")
        values = [value for value in recorded if value < until]
        if values:
            return max(values)
    return None


def _recorded_untils(path: Path) -> list[datetime]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return []
    values: list[datetime] = []
    for line in lines:
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if isinstance(record, dict):
            value = _record_until(record)
            if value is not None:
                values.append(value)
    return values


def _record_until(record: dict[str, Any]) -> datetime | None:
    value = record.get("until")
    if not isinstance(value, str) or not value:
        return None
    try:
        if "T" in value:
            return _parse(value)
        start = period_start(value)
    except ValueError:
        return None
    # A date-only `until` came from a run whose period ended with that date;
    # when it ran in the JST morning (the previous day in UTC), 00:00Z would
    # leave a gap, so the earlier of the two is used.
    started_at = record.get("started_at")
    try:
        started = _parse(started_at) if isinstance(started_at, str) else None
    except ValueError:
        started = None
    return min(start, started) if started else start


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
