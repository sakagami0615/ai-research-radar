from __future__ import annotations

from ai_research_radar.schemas.models import Event, HotCandidate


def compute_hot_candidates(
    events: list[Event],
    minimum_score: float = 75.0,
    weights: dict[str, float] | None = None,
) -> list[HotCandidate]:
    candidates: list[HotCandidate] = []
    for event in events:
        score = score_event(event, weights=weights)
        override = _official_event_override(event)
        if score < minimum_score and not override:
            continue
        reasons = [
            f"Momentum {event.scores.get('momentum', 0)}",
            f"Popularity {event.scores.get('popularity', 0)}",
            f"Credibility {event.scores.get('credibility', 0)}",
            f"Source families {len(event.source_families)}",
        ]
        if override:
            reasons.append("Official override")
        candidates.append(
            HotCandidate(
                hot_id=f"hot:{event.event_id}",
                title=event.title,
                topic=event.event_id.removeprefix("event:"),
                score=score,
                reasons=reasons,
                evidence_urls=list(event.evidence),
                source_families=list(event.source_families),
                signals=list(event.signals),
                selected=False,
            )
        )
    candidates.sort(key=lambda item: item.score, reverse=True)
    return candidates


def select_hot_candidates(candidates: list[HotCandidate], limit: int) -> list[HotCandidate]:
    return [
        HotCandidate(
            hot_id=candidate.hot_id,
            title=candidate.title,
            topic=candidate.topic,
            score=candidate.score,
            reasons=candidate.reasons,
            evidence_urls=candidate.evidence_urls,
            source_families=candidate.source_families,
            signals=candidate.signals,
            selected=index < limit,
        )
        for index, candidate in enumerate(candidates)
    ]


def build_hot_candidates_from_events(
    events: list[Event],
    limit: int = 5,
    minimum_score: float = 75.0,
    weights: dict[str, float] | None = None,
) -> list[HotCandidate]:
    candidates = compute_hot_candidates(events, minimum_score=minimum_score, weights=weights)
    return select_hot_candidates(candidates, limit)


def score_event(event: Event, weights: dict[str, float] | None = None) -> float:
    weights = weights or {
        "momentum": 0.40,
        "popularity": 0.25,
        "cross_source": 0.20,
        "credibility": 0.15,
    }
    cross_source = min(
        100.0, 40.0 + max(0, len(event.source_families) - 1) * 30.0
    )
    score = (
        float(weights["momentum"]) * _score_percent(event.scores.get("momentum", 0))
        + float(weights["popularity"]) * _score_percent(event.scores.get("popularity", 0))
        + float(weights["cross_source"]) * cross_source
        + float(weights["credibility"]) * _score_percent(event.scores.get("credibility", 0))
    )
    return round(min(100.0, max(0.0, score)), 2)


def _score_percent(value: object) -> float:
    try:
        return min(100.0, max(0.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _official_event_override(event: Event) -> bool:
    return "official" in set(event.source_families) and event.event_type in {
        "major_model_release",
        "major_api_release",
        "major_standard_update",
    }
