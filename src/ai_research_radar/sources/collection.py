from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from ai_research_radar.periods import period_date, period_start
from ai_research_radar.schemas.models import CanonicalSignal, RawItem
from ai_research_radar.sources.base import SourceAdapter, SourceError
from ai_research_radar.storage.jsonl import read_jsonl, write_jsonl


@dataclass
class CollectionResult:
    raw_items: list[RawItem] = field(default_factory=list)
    signals: list[CanonicalSignal] = field(default_factory=list)
    # Only sources whose collect() succeeded have a count; a missing source is a data gap.
    input_counts: dict[str, int] = field(default_factory=dict)
    errors: list[dict[str, str]] = field(default_factory=list)


def collect_sources(
    adapters: list[SourceAdapter],
    since: str,
    until: str,
    data_dir: Path,
    run_date: str,
    use_overlap: bool,
) -> CollectionResult:
    """Collect and normalize every source, saving raw/<run_date>/<source>.jsonl.

    A failing source is recorded in `errors` and the others continue (shared by
    `collect` and `daily`).
    """
    result = CollectionResult()
    for adapter in adapters:
        try:
            collected = collect_new_items(adapter, since, until, data_dir, run_date, use_overlap)
        except Exception as exc:  # noqa: BLE001 - one failing source must not stop the others
            result.errors.append(_source_error(adapter, exc))
            continue
        result.errors.extend(dict(error) for error in getattr(adapter, "partial_errors", []))
        result.input_counts[adapter.source_name] = len(collected)
        result.raw_items.extend(collected)
        try:
            write_jsonl(data_dir / "raw" / run_date / f"{adapter.source_name}.jsonl", collected)
        except Exception as exc:  # noqa: BLE001
            result.errors.append({"source": adapter.source_name, "type": "raw_write_error", "message": str(exc)})
        try:
            signals = [adapter.normalize(item) for item in collected]
        except Exception as exc:  # noqa: BLE001
            result.errors.append(_source_error(adapter, exc))
            continue
        result.signals.extend(signals)
    return result


def _source_error(adapter: SourceAdapter, exc: Exception) -> dict[str, str]:
    if isinstance(exc, SourceError):
        return {"source": exc.source, "type": exc.error_type, "message": str(exc)}
    return {"source": adapter.source_name, "type": "unexpected_error", "message": str(exc)}


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
