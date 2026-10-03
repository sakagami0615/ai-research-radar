import pytest
from ai_research_radar.scoring.assessments import apply_assessments, compute_discovery_candidates
from ai_research_radar.schemas.models import Event


def _event(name="e1"):
    return Event(name, "Title", "desc", "observed_signal", __import__('datetime').datetime.now(__import__('datetime').timezone.utc), __import__('datetime').datetime.now(__import__('datetime').timezone.utc), ["s"], ["x"], ["technology"], {}, ["https://example.test"])


def _assessment(hot_id, decision="selected"):
    return {"hot_id": hot_id, "decision": decision, "assessed_at": "2026-09-29T00:00:00+00:00", "assessor": "agent", "relevance": {"status": "related", "matched_terms": ["llm"], "reason": "r", "method": "agent"}, "novelty": "n", "importance": "i", "reader_impact": "r", "reason": "reason", "evidence": [{"url": "https://example.test", "checked_at": "2026-09-29T00:00:00+00:00", "target_version": None, "status": "verified", "kind": "primary", "claim": "claim", "note": "scope"}], "unknowns": []}


def test_zero_priority_research_preserved():
    assert len(compute_discovery_candidates([_event()])) == 1


def test_no_evidence_cannot_select():
    candidate = compute_discovery_candidates([_event()])[0]
    bad = _assessment(candidate.hot_id); bad["evidence"] = []
    with pytest.raises(ValueError): apply_assessments([candidate], {"assessments": [bad], "screened_ids": [candidate.hot_id], "selection_reason": "x"})


def test_non_dict_assessment_entry_raises_value_error():
    candidate = compute_discovery_candidates([_event()])[0]
    with pytest.raises(ValueError):
        apply_assessments([candidate], {"assessments": [None], "screened_ids": [candidate.hot_id], "selection_reason": "x"})


def test_selection_limit():
    candidates = compute_discovery_candidates([_event("a"), _event("b")])
    with pytest.raises(ValueError): apply_assessments(candidates, {"assessments": [_assessment(c.hot_id) for c in candidates], "screened_ids": [c.hot_id for c in candidates], "selection_reason": "x"}, limit=0)
