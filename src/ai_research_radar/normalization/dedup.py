from __future__ import annotations

from dataclasses import replace
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from ai_research_radar.schemas.models import CanonicalSignal


def deduplicate_signals(signals: list[CanonicalSignal]) -> list[CanonicalSignal]:
    by_url: dict[str, CanonicalSignal] = {}
    for signal in signals:
        canonical_url = _canonical_url(signal.url)
        key = canonical_url or f"empty:{signal.source}:{signal.signal_id}"
        normalized_signal = _with_cross_source_metadata(
            replace(signal, url=canonical_url) if canonical_url else signal
        )
        if key not in by_url:
            by_url[key] = normalized_signal
            continue
        by_url[key] = _merge_signals(by_url[key], normalized_signal)
    return list(by_url.values())


def canonical_url(url: str) -> str:
    parts = urlsplit(url)
    if not parts.scheme or not parts.netloc:
        return ""
    query = urlencode(
        [
            (key, value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
            if not _is_tracking_parameter(key)
        ],
        doseq=True,
    )
    return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path.rstrip("/"), query, ""))


_canonical_url = canonical_url


def deduplicate_quality_signals(signals: list[CanonicalSignal]) -> list[CanonicalSignal]:
    from ai_research_radar.normalization.identity import extract_identity
    grouped: dict[str, CanonicalSignal] = {}
    for signal in signals:
        identity = extract_identity(signal)
        key = str(identity["event_key"])
        if key not in grouped:
            grouped[key] = replace(signal, metadata={**signal.metadata, "identity": identity})
        else:
            grouped[key] = _merge_signals(grouped[key], signal)
    return list(grouped.values())


def _is_tracking_parameter(key: str) -> bool:
    return key.lower().startswith("utm_") or key.lower() in {"fbclid", "gclid", "ref"}


def _merge_signals(first: CanonicalSignal, second: CanonicalSignal) -> CanonicalSignal:
    merged_scores = dict(first.normalized_scores)
    for key, value in second.normalized_scores.items():
        merged_scores[key] = max(float(merged_scores.get(key, 0)), float(value))
    merged_metadata = dict(first.metadata)
    merged_metadata.setdefault("merged_signal_ids", [first.signal_id])
    merged_metadata["merged_signal_ids"].append(second.signal_id)
    merged_metadata["sources"] = sorted(
        set(first.metadata.get("sources", []))
        | {first.source}
        | set(second.metadata.get("sources", []))
        | {second.source}
    )
    merged_metadata["source_families"] = sorted(
        set(first.metadata.get("source_families", []))
        | {first.source_family}
        | set(second.metadata.get("source_families", []))
        | {second.source_family}
    )
    merged_metadata["event_type"] = _strongest_event_type(
        str(merged_metadata.get("event_type", "")),
        str(second.metadata.get("event_type", "")),
    )
    return replace(
        first,
        categories=sorted(set(first.categories) | set(second.categories)),
        normalized_scores=merged_scores,
        metadata=merged_metadata,
        quality=_merge_quality(first.quality, second.quality),
    )


def _merge_quality(first: dict, second: dict) -> dict:
    if not first:
        return dict(second)
    if not second:
        return dict(first)
    winner = first if float(first.get("priority") or 0) >= float(second.get("priority") or 0) else second
    merged = dict(winner)
    merged["metrics"] = list(first.get("metrics", [])) + list(second.get("metrics", []))
    return merged


def _with_cross_source_metadata(signal: CanonicalSignal) -> CanonicalSignal:
    metadata = dict(signal.metadata)
    metadata.setdefault("sources", [signal.source])
    metadata.setdefault("source_families", [signal.source_family])
    return replace(signal, metadata=metadata)


def _strongest_event_type(first: str, second: str) -> str:
    priority = {
        "major_model_release": 3,
        "major_api_release": 3,
        "major_standard_update": 3,
        "research_signal": 1,
        "observed_signal": 0,
        "": -1,
    }
    return first if priority.get(first, 0) >= priority.get(second, 0) else second
