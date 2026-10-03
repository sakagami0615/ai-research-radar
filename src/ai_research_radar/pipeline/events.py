from __future__ import annotations

from collections import defaultdict

from ai_research_radar.schemas.models import CanonicalSignal, Event, Topic


def build_quality_events(signals: list[CanonicalSignal]) -> list[Event]:
    from ai_research_radar.normalization.identity import extract_identity
    grouped: dict[str, list[CanonicalSignal]] = defaultdict(list)
    for signal in signals:
        grouped[str(extract_identity(signal)["event_key"])].append(signal)
    events = []
    for key, items in grouped.items():
        breakdown = sorted(
            ({"signal_id": item.signal_id, "priority": float(item.quality.get("priority", 0))} for item in items),
            key=lambda entry: (-entry["priority"], entry["signal_id"]),
        )
        representative_signal_id = breakdown[0]["signal_id"]
        representative = next(item for item in items if item.signal_id == representative_signal_id)
        identity = extract_identity(representative)
        events.append(Event(event_id=f"event:{key}", title=representative.title, description=representative.summary, event_type="observed_signal", first_seen_at=min(item.fetched_at for item in items), last_seen_at=max(item.fetched_at for item in items), signals=[item.signal_id for item in items], sources=sorted({item.source for item in items}), source_families=sorted({item.source_family for item in items}), scores={}, evidence=[item.url for item in items], schema_version=2, quality={"relevance": representative.quality.get("relevance"), "members": [{"signal_id": item.signal_id, "source": item.source, "url": item.url, "published_at": item.published_at.isoformat() if item.published_at else None, "fetched_at": item.fetched_at.isoformat(), "quality": item.quality} for item in items], "representative_signal_id": representative_signal_id, "priority": round(breakdown[0]["priority"], 2), "priority_breakdown": breakdown, "work_ids": [identity["work_id"]], "relations": []}))
    return events


def build_events(signals: list[CanonicalSignal]) -> list[Event]:
    grouped: dict[str, list[CanonicalSignal]] = defaultdict(list)
    for signal in signals:
        grouped[_topic_key(signal.title)].append(signal)

    events: list[Event] = []
    for key, items in grouped.items():
        events.append(
            Event(
                event_id=f"event:{key}",
                title=items[0].title,
                description=items[0].summary,
                event_type=_strongest_event_type(
                    [str(item.metadata.get("event_type", "observed_signal")) for item in items]
                ),
                first_seen_at=min(item.fetched_at for item in items),
                last_seen_at=max(item.fetched_at for item in items),
                signals=[item.signal_id for item in items],
                sources=sorted(
                    {
                        source
                        for item in items
                        for source in item.metadata.get("sources", [item.source])
                    }
                ),
                source_families=sorted(
                    {
                        family
                        for item in items
                        for family in item.metadata.get("source_families", [item.source_family])
                    }
                ),
                scores={
                    score: max(float(item.normalized_scores.get(score, 0)) for item in items)
                    for score in ("momentum", "popularity", "credibility")
                },
                evidence=[item.url for item in items],
            )
        )
    return events


def cluster_topics(events: list[Event]) -> list[Topic]:
    return [
        Topic(
            topic_id=f"topic:{event.event_id.removeprefix('event:')}",
            name=event.title,
            aliases=[],
            categories=[],
            related_topics=[],
            events=[event.event_id],
            trend_history=[],
            current_scores=event.scores,
            status="candidate",
        )
        for event in events
    ]


def _topic_key(title: str) -> str:
    return "-".join(title.lower().strip().split())


def _strongest_event_type(event_types: list[str]) -> str:
    priority = {
        "major_model_release": 3,
        "major_api_release": 3,
        "major_standard_update": 3,
        "research_signal": 1,
        "observed_signal": 0,
    }
    return max(event_types or ["observed_signal"], key=lambda value: priority.get(value, 0))
