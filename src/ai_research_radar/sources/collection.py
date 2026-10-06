from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ai_research_radar.periods import period_date, period_start
from ai_research_radar.schemas.models import RawItem
from ai_research_radar.sources.base import SourceAdapter
from ai_research_radar.storage.jsonl import read_jsonl


def collect_with_diagnostics(adapter: SourceAdapter, since: str, until: str) -> tuple[list[RawItem], dict[str, Any]]:
    started = datetime.now(timezone.utc).isoformat()
    try:
        items = adapter.collect(since, until)
    except Exception as exc:  # collection boundary records partial source failure
        return [], {"source": adapter.source_name, "since": since, "until": until, "received": 0, "period_kept": 0, "status": "failed", "errors": [{"type": type(exc).__name__, "message": str(exc)}], "started_at": started}
    diagnostics = dict(getattr(adapter, "collection_diagnostics", {}))
    diagnostics.update({"source": adapter.source_name, "since": since, "until": until, "received": len(items), "period_kept": len(items), "status": diagnostics.get("status", "success"), "started_at": diagnostics.get("started_at", started), "finished_at": datetime.now(timezone.utc).isoformat()})
    return items, diagnostics


def collect_new_items(
    adapter: SourceAdapter,
    since: str,
    until: str,
    data_dir: Path,
    run_date: str,
    use_overlap: bool,
) -> list[RawItem]:
    """Collect one source, re-reading `overlap_hours` before `since` when enabled.

    Feeds such as OpenAI's list entries whose pubDate is already in the past
    when they appear, so a source with `overlap_hours` re-reads that margin and
    drops the entries already normalized on an earlier date. The target date's
    own files are not consulted because a same-day rerun overwrites them.
    """
    hours = getattr(adapter, "overlap_hours", 0) if use_overlap else 0
    if hours <= 0:
        return adapter.collect(since=since, until=until)
    widened_since = (period_start(since) - timedelta(hours=hours)).isoformat()
    items = adapter.collect(since=widened_since, until=until)
    first_day = date.fromisoformat(period_date(widened_since)) - timedelta(days=1)
    seen = _normalized_signal_ids(data_dir, first_day, date.fromisoformat(run_date))
    # Same key as normalize() builds for signal_id.
    return [item for item in items if f"{item.source}:{item.raw_id}" not in seen]


def _normalized_signal_ids(data_dir: Path, first_day: date, run_day: date) -> set[str]:
    # normalized (not raw) is the baseline: an item that only reached raw in a
    # run that stopped before normalize must be collected again.
    ids: set[str] = set()
    day = first_day
    while day < run_day:
        path = data_dir / "normalized" / day.isoformat() / "signals.jsonl"
        day += timedelta(days=1)
        if not path.exists():
            continue
        try:
            records = read_jsonl(path)
        except (OSError, ValueError):  # an unreadable day only weakens the dedup
            continue
        for record in records:
            if not isinstance(record, dict):
                continue
            ids.add(str(record.get("signal_id", "")))
            metadata = record.get("metadata")
            merged = metadata.get("merged_signal_ids") if isinstance(metadata, dict) else None
            if isinstance(merged, list):
                ids.update(str(value) for value in merged)
    return ids
