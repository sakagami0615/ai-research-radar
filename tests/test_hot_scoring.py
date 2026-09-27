from datetime import datetime, timezone

from ai_research_radar.schemas.models import Event
from ai_research_radar.scoring.hot import (
    build_hot_candidates_from_events,
    compute_hot_candidates,
    score_event,
    select_hot_candidates,
)


def _now():
    return datetime(2026, 9, 25, 8, 0, tzinfo=timezone.utc)


def test_score_event_uses_configurable_weights():
    event = Event(
        event_id="event:agent-runtime",
        title="Agent Runtime",
        description="Agent runtime event",
        event_type="observed_signal",
        first_seen_at=_now(),
        last_seen_at=_now(),
        signals=["github:repo"],
        sources=["github", "hackernews"],
        source_families=["technology", "community"],
        scores={"momentum": 100, "popularity": 80, "credibility": 60},
        evidence=["https://github.com/owner/repo"],
    )

    score = score_event(
        event,
        weights={
            "momentum": 0.40,
            "popularity": 0.25,
            "cross_source": 0.20,
            "credibility": 0.15,
        },
    )

    assert score == 83.0


def test_build_hot_candidates_from_events_marks_at_most_limit_as_selected():
    events = [
        Event(
            event_id=f"event:tool-{idx}",
            title=f"Tool {idx}",
            description=f"Tool {idx}",
            event_type="observed_signal",
            first_seen_at=_now(),
            last_seen_at=_now(),
            signals=[f"github:repo-{idx}"],
            sources=["github"],
            source_families=["technology"],
            scores={"momentum": 100 - idx, "popularity": 90, "credibility": 80},
            evidence=[f"https://example.com/{idx}"],
        )
        for idx in range(10)
    ]

    candidates = build_hot_candidates_from_events(events, limit=5, minimum_score=0)

    assert len(candidates) == 10
    assert sum(1 for candidate in candidates if candidate.selected) == 5
    assert all(candidate.selected for candidate in candidates[:5])
    assert all(not candidate.selected for candidate in candidates[5:])
    assert candidates[0].score >= candidates[-1].score


def test_build_hot_candidates_from_events_filters_low_score():
    event = Event(
        event_id="event:quiet",
        title="Quiet Tool",
        description="Quiet Tool",
        event_type="observed_signal",
        first_seen_at=_now(),
        last_seen_at=_now(),
        signals=["github:quiet"],
        sources=["github"],
        source_families=["technology"],
        scores={"momentum": 10, "popularity": 10, "credibility": 80},
        evidence=["https://example.com/quiet"],
    )

    assert build_hot_candidates_from_events([event], limit=5, minimum_score=75) == []


def test_official_major_event_is_candidate_even_with_low_score():
    event = Event(
        event_id="event:major-model-release",
        title="Major Model Release",
        description="Official model release",
        event_type="major_model_release",
        first_seen_at=_now(),
        last_seen_at=_now(),
        signals=["official:model"],
        sources=["official_blog"],
        source_families=["official"],
        scores={"momentum": 10, "popularity": 10, "credibility": 100},
        evidence=["https://example.com/model"],
    )

    candidates = build_hot_candidates_from_events([event], limit=5, minimum_score=75)

    assert len(candidates) == 1
    assert candidates[0].selected is True
    assert "Official override" in candidates[0].reasons


def test_build_hot_candidates_from_events_preserves_event_evidence():
    event = Event(
        event_id="event:agent-runtime",
        title="Agent Runtime",
        description="Agent runtime event",
        event_type="observed_signal",
        first_seen_at=_now(),
        last_seen_at=_now(),
        signals=["github:repo"],
        sources=["github", "hackernews"],
        source_families=["technology", "community"],
        scores={"momentum": 96, "popularity": 90, "credibility": 80},
        evidence=["https://github.com/owner/repo"],
    )

    candidates = build_hot_candidates_from_events([event], limit=5, minimum_score=75)

    assert candidates[0].hot_id == "hot:event:agent-runtime"
    assert candidates[0].evidence_urls == ["https://github.com/owner/repo"]
    assert sorted(candidates[0].source_families) == ["community", "technology"]


def test_score_event_clamps_out_of_range_source_scores():
    event = Event(
        event_id="event:oversized",
        title="Oversized metrics",
        description="Scores must remain a percentage.",
        event_type="observed_signal",
        first_seen_at=_now(),
        last_seen_at=_now(),
        signals=["github:repo"],
        sources=["github"],
        source_families=["technology"],
        scores={"momentum": 10000, "popularity": 1000, "credibility": 999},
        evidence=["https://example.com/oversized"],
    )

    assert score_event(event) <= 100


def test_compute_hot_candidates_marks_all_as_unselected():
    events = [
        Event(
            event_id="event:tool-a",
            title="Tool A",
            description="Tool A",
            event_type="observed_signal",
            first_seen_at=_now(),
            last_seen_at=_now(),
            signals=["github:a"],
            sources=["github"],
            source_families=["technology"],
            scores={"momentum": 90, "popularity": 90, "credibility": 80},
            evidence=["https://example.com/a"],
        )
    ]

    candidates = compute_hot_candidates(events, minimum_score=0)

    assert len(candidates) == 1
    assert candidates[0].selected is False


def test_compute_hot_candidates_drops_events_below_minimum_score():
    events = [
        Event(
            event_id="event:tool-a",
            title="Tool A",
            description="Tool A",
            event_type="observed_signal",
            first_seen_at=_now(),
            last_seen_at=_now(),
            signals=["github:a"],
            sources=["github"],
            source_families=["technology"],
            scores={"momentum": 1, "popularity": 1, "credibility": 1},
            evidence=["https://example.com/a"],
        )
    ]

    candidates = compute_hot_candidates(events, minimum_score=75)

    assert candidates == []


def test_select_hot_candidates_marks_top_n_as_selected():
    events = [
        Event(
            event_id=f"event:tool-{idx}",
            title=f"Tool {idx}",
            description=f"Tool {idx}",
            event_type="observed_signal",
            first_seen_at=_now(),
            last_seen_at=_now(),
            signals=[f"github:{idx}"],
            sources=["github"],
            source_families=["technology"],
            scores={"momentum": 100 - idx, "popularity": 90, "credibility": 80},
            evidence=[f"https://example.com/{idx}"],
        )
        for idx in range(4)
    ]
    candidates = compute_hot_candidates(events, minimum_score=0)

    selected = select_hot_candidates(candidates, limit=2)

    assert [candidate.selected for candidate in selected] == [True, True, False, False]


def test_build_hot_candidates_from_events_matches_compute_then_select():
    events = [
        Event(
            event_id=f"event:tool-{idx}",
            title=f"Tool {idx}",
            description=f"Tool {idx}",
            event_type="observed_signal",
            first_seen_at=_now(),
            last_seen_at=_now(),
            signals=[f"github:{idx}"],
            sources=["github"],
            source_families=["technology"],
            scores={"momentum": 100 - idx, "popularity": 90, "credibility": 80},
            evidence=[f"https://example.com/{idx}"],
        )
        for idx in range(4)
    ]

    combined = build_hot_candidates_from_events(events, limit=2, minimum_score=0)
    computed_then_selected = select_hot_candidates(
        compute_hot_candidates(events, minimum_score=0), limit=2
    )

    assert combined == computed_then_selected
