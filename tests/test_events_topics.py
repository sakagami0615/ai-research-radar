from datetime import datetime, timezone

import pytest

from ai_research_radar.normalization.dedup import deduplicate_signals
from ai_research_radar.pipeline.events import build_events, cluster_topics
from ai_research_radar.scoring.hot import build_hot_candidates_from_events
from ai_research_radar.schemas.models import CanonicalSignal


def _signal(
    signal_id: str,
    title: str,
    family: str,
    event_type: str | None = None,
) -> CanonicalSignal:
    metadata = {"sources": [signal_id.split(":")[0]], "source_families": [family]}
    if event_type:
        metadata["event_type"] = event_type
    return CanonicalSignal(
        signal_id=signal_id,
        source=signal_id.split(":")[0],
        source_family=family,
        content_type="tool",
        title=title,
        url=f"https://example.com/{signal_id}",
        published_at=None,
        fetched_at=datetime(2026, 9, 25, 8, 0, tzinfo=timezone.utc),
        summary=title,
        categories=["agent", "runtime"],
        raw_metrics={},
        normalized_scores={"momentum": 90, "popularity": 80, "credibility": 70},
        metadata=metadata,
    )


def test_build_events_groups_signals_by_topic_key():
    signals = [
        _signal("github:a", "Agent Runtime", "technology"),
        _signal("hn:b", "Agent Runtime", "community"),
    ]

    events = build_events(signals)

    assert len(events) == 1
    assert events[0].event_id == "event:agent-runtime"
    assert sorted(events[0].source_families) == ["community", "technology"]
    assert len(events[0].signals) == 2


def test_cluster_topics_from_events():
    events = build_events([_signal("github:a", "Agent Runtime", "technology")])

    topics = cluster_topics(events)

    assert len(topics) == 1
    assert topics[0].topic_id == "topic:agent-runtime"
    assert topics[0].status == "candidate"
    assert topics[0].events == ["event:agent-runtime"]


@pytest.mark.parametrize("event_type", ["major_model_release", "major_api_release", "major_standard_update"])
def test_build_events_preserves_major_event_type(event_type: str):
    events = build_events([_signal("official:release", "Major Release", "official", event_type)])

    assert events[0].event_type == event_type


def test_deduplicated_official_major_event_receives_hot_override():
    signals = [
        _signal("github:release", "Major API Release", "technology"),
        _signal("official:release", "Major API Release", "official", "major_api_release"),
    ]
    signals[1] = CanonicalSignal(
        **{**signals[1].__dict__, "url": signals[0].url}
    )

    events = build_events(deduplicate_signals(signals))
    candidates = build_hot_candidates_from_events(events, minimum_score=100)

    assert events[0].source_families == ["official", "technology"]
    assert events[0].event_type == "major_api_release"
    assert len(candidates) == 1
    assert "Official override" in candidates[0].reasons
