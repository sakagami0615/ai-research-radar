from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import replace
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

from ai_research_radar.schemas.models import CanonicalSignal
from ai_research_radar.periods import period_end, period_start


_POPULARITY_METRICS = (
    "stars",
    "stargazers_count",
    "downloads",
    "download_count",
    "points",
    "likes",
    "reactions",
    "citations",
    "popularity",
    "search_score",
    "npm_search_score",
)
_PACKAGE_DISCOVERY_PROMOTION_LIMIT = 3
_PACKAGE_DISCOVERY_POPULARITY_FLOOR = 75.0


def parse_optional_datetime(value: object) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip()
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            try:
                parsed = parsedate_to_datetime(text)
            except (TypeError, ValueError):
                return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def is_within_period(value: datetime | None, since: str, until: str) -> bool:
    if value is None:
        return False
    normalized = parse_optional_datetime(value)
    return normalized is not None and period_start(since) <= normalized <= period_end(until)


def normalized_scores(
    metrics: dict[str, Any],
    published_at: datetime | None,
    fetched_at: datetime,
    credibility: float,
) -> dict[str, float]:
    popularity_value = _popularity_metric(metrics)
    activity_value = _largest_metric(
        metrics,
        "stars_24h",
        "downloads_24h",
        "points",
        "comments",
        "num_comments",
        "reactions",
    )
    popularity = _log_score(popularity_value, ceiling=10_000.0)
    activity = _log_score(activity_value, ceiling=1_000.0)
    reference = published_at or fetched_at
    age_hours = max(0.0, (fetched_at - reference).total_seconds() / 3600.0)
    freshness = max(0.0, 100.0 - (age_hours / 24.0) * 10.0)
    momentum = 0.7 * freshness + 0.3 * activity
    engagement = _log_score(
        _largest_metric(metrics, "comments", "num_comments", "points", "reactions"),
        ceiling=1_000.0,
    )
    return {
        "popularity": round(_clamp(popularity), 2),
        "momentum": round(_clamp(momentum), 2),
        "engagement": round(_clamp(engagement), 2),
        "credibility": round(_clamp(credibility), 2),
    }


def normalize_source_batch(signals: list[CanonicalSignal]) -> list[CanonicalSignal]:
    """Apply deterministic source-local popularity ranks after collection."""
    grouped: dict[str, list[CanonicalSignal]] = defaultdict(list)
    for signal in signals:
        grouped[signal.source].append(signal)

    normalized: list[CanonicalSignal] = []
    for source in sorted(grouped):
        source_signals = grouped[source]
        metrics = {signal.signal_id: _source_metric(signal) for signal in source_signals}
        popularity_by_id = _rank_popularity(metrics)
        promoted_discovery_ids = _promoted_package_discovery_ids(
            source_signals, popularity_by_id
        )
        for signal in source_signals:
            scores = dict(signal.normalized_scores)
            if len(source_signals) == 1:
                popularity, momentum = _single_signal_fallback(signal, scores)
            else:
                popularity = popularity_by_id[signal.signal_id]
                momentum = _score_percent(scores.get("momentum", 0))
                discovery_momentum = _package_discovery_momentum(signal)
                if discovery_momentum is not None:
                    momentum = max(momentum, discovery_momentum)
                if signal.signal_id in promoted_discovery_ids:
                    popularity = max(popularity, _PACKAGE_DISCOVERY_POPULARITY_FLOOR)
            scores["popularity"] = round(_clamp(popularity), 2)
            scores["momentum"] = round(_clamp(momentum), 2)
            normalized.append(replace(signal, normalized_scores=scores))
    return normalized


def _largest_metric(metrics: dict[str, Any], *names: str) -> float:
    values: list[float] = []
    for name in names:
        try:
            values.append(float(metrics.get(name, 0) or 0))
        except (TypeError, ValueError):
            continue
    return max(values, default=0.0)


def _popularity_metric(metrics: dict[str, Any]) -> float:
    return _largest_metric(metrics, *_POPULARITY_METRICS)


def _source_metric(signal: CanonicalSignal) -> float:
    popularity = _popularity_metric(signal.raw_metrics)
    if signal.source == "pypi":
        return max(popularity, _largest_metric(signal.raw_metrics, "ai_keyword_strength"))
    return popularity


def _rank_popularity(metrics_by_id: dict[str, float]) -> dict[str, float]:
    ordered = sorted(metrics_by_id.items(), key=lambda item: (item[1], item[0]))
    if len(ordered) == 1:
        return {ordered[0][0]: 100.0}

    ranks: dict[str, float] = {}
    for index, (signal_id, value) in enumerate(ordered):
        matching_indexes = [
            match_index
            for match_index, (_, match_value) in enumerate(ordered)
            if match_value == value
        ]
        average_rank = sum(matching_indexes) / len(matching_indexes)
        ranks[signal_id] = 100.0 * average_rank / (len(ordered) - 1)
    return ranks


def _single_signal_fallback(
    signal: CanonicalSignal,
    scores: dict[str, float],
) -> tuple[float, float]:
    popularity = _score_percent(scores.get("popularity", 0))
    momentum = _score_percent(scores.get("momentum", 0))
    discovery_momentum = _package_discovery_momentum(signal)

    if signal.source == "npm":
        search_score = _largest_metric(
            signal.raw_metrics, "popularity", "search_score", "npm_search_score"
        )
        if discovery_momentum is not None:
            return max(popularity, search_score * 100.0), max(momentum, discovery_momentum)

    if signal.source == "pypi":
        if discovery_momentum is not None:
            return max(popularity, 95.0), max(momentum, discovery_momentum)

    return popularity, momentum


def _package_discovery_momentum(signal: CanonicalSignal) -> float | None:
    age_hours = _age_hours(signal)
    if age_hours > 48:
        return None
    if signal.source == "npm":
        search_score = _largest_metric(
            signal.raw_metrics, "popularity", "search_score", "npm_search_score"
        )
        if 0.85 <= search_score <= 1.0:
            return 100.0 - age_hours
    if signal.source == "pypi" and _largest_metric(
        signal.raw_metrics, "ai_keyword_strength"
    ) >= 0.9:
        return 100.0 - age_hours
    return None


def _promoted_package_discovery_ids(
    signals: list[CanonicalSignal], popularity_by_id: dict[str, float]
) -> set[str]:
    if len(signals) < 2:
        return set()

    eligible = [
        (signal, _package_discovery_strength(signal))
        for signal in signals
    ]
    ranked = sorted(
        (
            (signal, strength)
            for signal, strength in eligible
            if strength is not None
        ),
        key=lambda item: (
            -item[1],
            -popularity_by_id[item[0].signal_id],
            item[0].signal_id,
        ),
    )
    return {
        signal.signal_id
        for signal, _ in ranked[:_PACKAGE_DISCOVERY_PROMOTION_LIMIT]
    }


def _package_discovery_strength(signal: CanonicalSignal) -> float | None:
    if _package_discovery_momentum(signal) is None:
        return None
    if signal.source == "npm":
        return _largest_metric(
            signal.raw_metrics, "popularity", "search_score", "npm_search_score"
        )
    if signal.source == "pypi":
        return _largest_metric(signal.raw_metrics, "ai_keyword_strength")
    return None


def _age_hours(signal: CanonicalSignal) -> float:
    reference = signal.published_at or signal.fetched_at
    return max(0.0, (signal.fetched_at - reference).total_seconds() / 3600.0)


def _score_percent(value: object) -> float:
    try:
        return _clamp(float(value))
    except (TypeError, ValueError):
        return 0.0


def _log_score(value: float, ceiling: float) -> float:
    if value <= 0:
        return 0.0
    return min(100.0, 100.0 * math.log1p(value) / math.log1p(ceiling))


def _clamp(value: float) -> float:
    return min(100.0, max(0.0, value))
