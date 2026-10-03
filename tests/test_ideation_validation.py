import pytest
from ai_research_radar.ideation.validation import validate_proposals
from ai_research_radar.schemas.models import HotCandidate


def _candidate():
    return HotCandidate("h1", "T", "t", 1, [], ["https://example.test"], ["technology"], ["s"], True, 2, {}, None)


def _proposal():
    return {"proposal_id": "p1", "source_hot_id": "h1", "title_idea": "x", "article_type": "comparison", "target_reader": "r", "why_now": "w", "technical_angle": "a", "experiment_plan": ["p"], "competition": "b", "traffic_opportunity": "t", "technical_opportunity": "o", "unique_angle": "u", "evidence_links": ["https://example.test"], "risks": [], "schema_version": 2, "quality": {"question": "q", "difference": "d", "baseline": "b", "baseline_version": "1", "measurement": "m", "inputs_and_environment": "env", "effort": "1d", "effort_assumptions": "a", "success_condition": "s", "stop_condition": "stop", "metrics": ["accuracy"], "evidence": [], "unknowns": []}}


def test_empty_proposals_valid(): assert validate_proposals([], [_candidate()]) == []


def test_placeholder_plan_rejected():
    proposal = _proposal(); proposal["quality"]["metrics"] = []
    with pytest.raises(ValueError): validate_proposals([proposal], [_candidate()])


def test_duplicate_ids_and_fourth_proposal_rejected():
    proposals = [_proposal() for _ in range(4)]
    with pytest.raises(ValueError): validate_proposals(proposals, [_candidate()])


def test_cap_applies_per_candidate_not_globally():
    other = HotCandidate("h2", "T2", "t2", 1, [], ["https://example.test"], ["technology"], ["s"], True, 2, {}, None)
    proposals = []
    for index, hot_id in enumerate(("h1", "h1", "h2", "h2")):
        proposal = _proposal()
        proposal["proposal_id"] = f"p{index}"
        proposal["source_hot_id"] = hot_id
        proposals.append(proposal)
    result = validate_proposals(proposals, [_candidate(), other])
    assert len(result) == 4
