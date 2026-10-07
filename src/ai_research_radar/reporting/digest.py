"""Daily digest: 注目候補(選抜外) and 新モデルリリース sections of the daily report.

Both sections are built deterministically from the last few days of run data
(no Agent judgement); only the summaries are written by the Agent
(`data/runs/<date>/digest_summaries.json`). Items already shown in an earlier
day's report are excluded using `data/runs/<date>/report_digest.json`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from datetime import date as date_cls
from datetime import timedelta
from pathlib import Path
from typing import Any

from ai_research_radar.normalization.dedup import canonical_url
from ai_research_radar.schemas.decoders import decode_hot
from ai_research_radar.schemas.models import HotCandidate
from ai_research_radar.storage.jsonl import read_jsonl

LOOKBACK_DAYS = 3
NOTABLE_LIMIT = 10
MODELS_PER_PROVIDER_LIMIT = 10
DIGEST_FILENAME = "report_digest.json"
SUMMARIES_FILENAME = "digest_summaries.json"


@dataclass(frozen=True)
class NotableItem:
    candidate: HotCandidate
    sources: list[str]
    first_seen: str
    # The candidate's own summary, else the one added on the target date; empty if neither.
    summary: str = ""


@dataclass(frozen=True)
class ModelRelease:
    key: str
    provider: str
    channel: str
    title: str
    url: str
    published_at: str | None
    first_seen: str
    # Model names introduced by an article (e.g. an Ollama blog post), if known.
    models: tuple[str, ...] = ()
    # The summary added on the target date (digest_summaries.json); empty if none.
    summary: str = ""


@dataclass(frozen=True)
class DailyDigest:
    notable: list[NotableItem] = field(default_factory=list)
    notable_overflow: int = 0
    model_releases: list[ModelRelease] = field(default_factory=list)
    # Files skipped because they could not be read; the digest is auxiliary, so a
    # broken past run must not break today's report.
    warnings: list[str] = field(default_factory=list)


def build_daily_digest(data_dir: Path, date: str) -> DailyDigest:
    dates = _window_dates(date)
    shown = _previously_shown(data_dir, dates[1:])
    warnings: list[str] = []
    notable = _notable_items(data_dir, dates, shown["notable"], warnings)
    try:
        added = load_digest_summaries(data_dir, date)
    except (OSError, ValueError) as exc:
        warnings.append(f"{data_dir / 'runs' / date / SUMMARIES_FILENAME}: {exc}")
        added = {}
    notable = [replace(item, summary=item.candidate.summary or added.get(item.candidate.hot_id, "")) for item in notable]
    model_releases = [
        replace(release, summary=added.get(release.key, ""))
        for release in _model_releases(data_dir, dates, shown["model_releases"], warnings)
    ]
    return DailyDigest(
        notable=notable[:NOTABLE_LIMIT],
        notable_overflow=max(0, len(notable) - NOTABLE_LIMIT),
        model_releases=model_releases,
        warnings=warnings,
    )


def missing_summaries(digest: DailyDigest) -> list[NotableItem | ModelRelease]:
    """Displayed items that still have no summary: notable items first, then model releases.

    Overflow items are not displayed, so they are not listed.
    """
    notable = [item for item in digest.notable if not item.summary]
    releases = [release for release in displayed_model_releases(digest) if not release.summary]
    return [*notable, *releases]


def summarizable_keys(digest: DailyDigest) -> set[str]:
    """Keys whose summary added on the target date shows up in the report.

    Notable items count only when the candidate has no summary of its own, since
    that takes precedence. Model releases have no summary of their own, so every
    displayed one counts. hot_id starts with "hot:" and a model release key is a
    URL or a "<source>:..." signal_id, so the two never collide.
    """
    notable = {item.candidate.hot_id for item in digest.notable if not item.candidate.summary}
    return notable | {release.key for release in displayed_model_releases(digest)}


def displayed_model_releases(digest: DailyDigest) -> list[ModelRelease]:
    """Model releases shown in the report, in display order (per-provider overflow excluded)."""
    return [release for _, releases, _ in group_model_releases(digest.model_releases) for release in releases]


def load_digest_summaries(data_dir: Path, date: str) -> dict[str, str]:
    path = data_dir / "runs" / date / SUMMARIES_FILENAME
    if not path.exists():
        return {}
    record = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(record, dict):
        raise ValueError(f"{path} is not a JSON object")
    return {str(key): str(value) for key, value in record.items() if value}


def save_digest_summaries(data_dir: Path, date: str, summaries: dict[str, str]) -> None:
    """Merge summaries added on `date` into its digest_summaries.json (the same key is overwritten)."""
    merged = {**load_digest_summaries(data_dir, date), **summaries}
    path = data_dir / "runs" / date / SUMMARIES_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def save_digest_record(data_dir: Path, date: str, digest: DailyDigest) -> None:
    """Record what was shown so later reports can skip it.

    Overflow items (beyond the display limits) are not recorded, so they can
    still surface on a later day.
    """
    record = {
        "notable": [item.candidate.hot_id for item in digest.notable],
        "model_releases": [release.key for release in displayed_model_releases(digest)],
    }
    path = data_dir / "runs" / date / DIGEST_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def group_model_releases(releases: list[ModelRelease]) -> list[tuple[str, list[ModelRelease], int]]:
    """Returns (provider, displayed releases, overflow count), providers sorted by name."""
    by_provider: dict[str, list[ModelRelease]] = {}
    for release in releases:
        by_provider.setdefault(release.provider, []).append(release)
    groups = []
    for provider in sorted(by_provider, key=str.lower):
        items = sorted(by_provider[provider], key=lambda item: (item.published_at or "", item.title), reverse=True)
        groups.append((provider, items[:MODELS_PER_PROVIDER_LIMIT], max(0, len(items) - MODELS_PER_PROVIDER_LIMIT)))
    return groups


def _window_dates(date: str) -> list[str]:
    """The target date first, then the preceding days of the lookback window."""
    target = date_cls.fromisoformat(date)
    return [(target - timedelta(days=offset)).isoformat() for offset in range(LOOKBACK_DAYS)]


def _previously_shown(data_dir: Path, earlier_dates: list[str]) -> dict[str, set[str]]:
    shown: dict[str, set[str]] = {"notable": set(), "model_releases": set()}
    for day in earlier_dates:
        path = data_dir / "runs" / day / DIGEST_FILENAME
        if not path.exists():
            continue
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(record, dict):
            continue
        for key in shown:
            values = record.get(key, [])
            if isinstance(values, list):
                shown[key].update(str(value) for value in values)
    return shown


def _notable_items(data_dir: Path, dates: list[str], shown: set[str], warnings: list[str]) -> list[NotableItem]:
    latest: dict[str, HotCandidate] = {}
    first_seen: dict[str, str] = {}
    selected_ids: set[str] = set()
    # Oldest day first so later days overwrite the candidate (latest score wins)
    # while first_seen keeps the earliest day.
    for day in reversed(dates):
        path = data_dir / "runs" / day / "hot_candidates.jsonl"
        if not path.exists():
            continue
        try:
            day_candidates = [decode_hot(record) for record in read_jsonl(path)]
        except Exception as exc:  # noqa: BLE001 - skip the unreadable day, keep the report
            warnings.append(f"{path}: {exc}")
            continue
        for candidate in day_candidates:
            if candidate.selected:
                selected_ids.add(candidate.hot_id)
                continue
            latest[candidate.hot_id] = candidate
            first_seen.setdefault(candidate.hot_id, day)
    items = [
        NotableItem(candidate, _sources_of(candidate), first_seen[hot_id])
        for hot_id, candidate in latest.items()
        if hot_id not in selected_ids and hot_id not in shown
    ]
    items.sort(key=lambda item: (-item.candidate.score, item.candidate.hot_id))
    return items


def _sources_of(candidate: HotCandidate) -> list[str]:
    sources = {signal_id.split(":", 1)[0] for signal_id in candidate.signals if ":" in signal_id}
    return sorted(sources)


def _model_releases(data_dir: Path, dates: list[str], shown: set[str], warnings: list[str]) -> list[ModelRelease]:
    releases: dict[str, ModelRelease] = {}
    for day in reversed(dates):
        path = data_dir / "normalized" / day / "signals.jsonl"
        if not path.exists():
            continue
        try:
            records = read_jsonl(path)
        except Exception as exc:  # noqa: BLE001 - skip the unreadable day, keep the report
            warnings.append(f"{path}: {exc}")
            continue
        for record in records:
            if not isinstance(record, dict):
                continue
            release = _model_release_from_signal(record, day)
            if release is None or release.key in shown or release.key in releases:
                continue
            releases[release.key] = release
    return list(releases.values())


def _model_release_from_signal(record: dict[str, Any], day: str) -> ModelRelease | None:
    metadata = record.get("metadata")
    if not isinstance(metadata, dict):
        return None
    marker = metadata.get("model_release")
    if not isinstance(marker, dict):
        return None
    url = str(record.get("url") or "")
    key = canonical_url(url) or str(record.get("signal_id", ""))
    if not key:
        return None
    published_at = record.get("published_at")
    return ModelRelease(
        key=key,
        provider=str(marker.get("provider") or "不明"),
        channel=str(marker.get("channel") or ""),
        title=str(record.get("title") or key),
        url=url,
        published_at=str(published_at) if published_at else None,
        first_seen=day,
        models=tuple(str(name) for name in marker.get("models", []) if name),
    )
