from __future__ import annotations

from dataclasses import replace
from typing import Any

from ai_research_radar.schemas.models import Event, HotCandidate
from ai_research_radar.schemas.quality import validate_assessment


def compute_discovery_candidates(events: list[Event]) -> list[HotCandidate]:
    result = []
    for event in events:
        priority = float(event.quality.get("priority", 0)) if event.quality else 0.0
        result.append(HotCandidate(f"hot:{event.event_id}", event.title, event.event_id.removeprefix("event:"), priority, ["discovery candidate; human/agent assessment required"], list(event.evidence), list(event.source_families), list(event.signals), False, 2, {**event.quality, "candidate_status": "discovery"}, None))
    return result


def apply_assessments(candidates: list[HotCandidate], selection: dict[str, Any], *, limit: int = 2) -> tuple[list[HotCandidate], dict[str, Any]]:
    if not 0 <= limit <= 5: raise ValueError("limit must be between 0 and 5")
    known = {item.hot_id for item in candidates}; screened = selection.get("screened_ids", [])
    if not isinstance(screened, list) or len(screened) != len(set(screened)) or not set(screened) <= known: raise ValueError("invalid screened_ids")
    assessments = selection.get("assessments", [])
    if not isinstance(assessments, list) or any(not isinstance(item, dict) for item in assessments): raise ValueError("invalid assessments")
    if len({item.get("hot_id") for item in assessments}) != len(assessments): raise ValueError("duplicate assessments")
    by_id = {}
    for item in assessments:
        validate_assessment(item); hot_id = item["hot_id"]
        if hot_id not in known: raise ValueError("unknown hot_id")
        if item["decision"] == "selected" and not any(e.get("status") == "verified" and e.get("kind") == "primary" for e in item["evidence"]): raise ValueError("selected candidate needs verified primary evidence")
        by_id[hot_id] = item
    selected = [key for key, item in by_id.items() if item["decision"] == "selected"]
    if len(selected) > limit: raise ValueError("selection limit exceeded")
    updated = [replace(candidate, selected=candidate.hot_id in selected, assessment=by_id.get(candidate.hot_id)) for candidate in candidates]
    summary = {"selection_reason": selection.get("selection_reason", ""), "screened_ids": screened, "unreviewed_ids": sorted(known - set(screened)), "selected_count": len(selected), "candidate_count": len(candidates)}
    return updated, summary
