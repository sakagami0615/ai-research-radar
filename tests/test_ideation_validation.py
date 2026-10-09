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


def _evidence(url: str, claim: str = "主張") -> dict:
    return {"url": url, "checked_at": "2026-10-08T00:00:00+00:00", "target_version": None, "status": "verified", "kind": "primary", "claim": claim, "note": ""}


def _unselected():
    return HotCandidate("h1", "T", "t", 1, [], ["https://example.test"], ["technology"], ["s"], False, 2, {}, None)


def test_unselected_candidate_rejected():
    with pytest.raises(ValueError, match="not a selected HOT candidate"):
        validate_proposals([_proposal()], [_unselected()])


def test_unknown_candidate_rejected():
    proposal = _proposal(); proposal["source_hot_id"] = "missing"
    with pytest.raises(ValueError, match="unknown HOT candidate"):
        validate_proposals([proposal], [_candidate()])


def test_error_message_has_index():
    proposals = [_proposal(), _proposal()]
    proposals[1]["proposal_id"] = "p2"; proposals[1]["source_hot_id"] = "missing"
    with pytest.raises(ValueError, match=r"^proposal\[1\]"):
        validate_proposals(proposals, [_candidate()])


@pytest.mark.parametrize("field", ["title_idea", "risks", "experiment_plan", "evidence_links", "proposal_id"])
def test_missing_required_field_rejected(field):
    proposal = _proposal(); del proposal[field]
    with pytest.raises(ValueError, match="missing fields"):
        validate_proposals([proposal], [_candidate()])


@pytest.mark.parametrize(
    ("field", "value"),
    [("title_idea", ""), ("title_idea", "   "), ("why_now", 1), ("experiment_plan", "手順"), ("risks", [1]), ("evidence_links", "https://example.test")],
)
def test_invalid_field_type_rejected(field, value):
    proposal = _proposal(); proposal[field] = value
    with pytest.raises(ValueError, match=field):
        validate_proposals([proposal], [_candidate()])


def test_missing_quality_rejected():
    proposal = _proposal(); del proposal["quality"]
    with pytest.raises(ValueError, match="quality"):
        validate_proposals([proposal], [_candidate()])


def test_invalid_quality_evidence_rejected():
    proposal = _proposal(); proposal["quality"]["evidence"] = [{"url": "https://example.test"}]
    with pytest.raises(ValueError, match="evidence keys mismatch"):
        validate_proposals([proposal], [_candidate()])


def test_proposal_without_candidate_evidence_rejected():
    proposal = _proposal(); proposal["evidence_links"] = ["https://other.test"]
    proposal["quality"]["evidence"] = [_evidence("https://other.test", "比較対象の仕様")]
    with pytest.raises(ValueError, match="candidate evidence"):
        validate_proposals([proposal], [_candidate()])


def test_additional_url_without_quality_evidence_rejected():
    proposal = _proposal(); proposal["evidence_links"] = ["https://example.test", "https://other.test"]
    with pytest.raises(ValueError, match="https://other.test"):
        validate_proposals([proposal], [_candidate()])


def test_additional_url_with_empty_claim_rejected():
    proposal = _proposal(); proposal["evidence_links"] = ["https://example.test", "https://other.test"]
    proposal["quality"]["evidence"] = [_evidence("https://other.test", "  ")]
    with pytest.raises(ValueError, match="https://other.test"):
        validate_proposals([proposal], [_candidate()])


def test_additional_url_with_claim_accepted():
    proposal = _proposal(); proposal["evidence_links"] = ["https://example.test", "https://other.test"]
    proposal["quality"]["evidence"] = [_evidence("https://other.test", "比較対象 X の仕様")]
    assert validate_proposals([proposal], [_candidate()]) == [proposal]


def test_duplicate_proposal_id_rejected():
    with pytest.raises(ValueError, match="duplicate proposal_id"):
        validate_proposals([_proposal(), _proposal()], [_candidate()])


def test_fourth_proposal_for_same_candidate_rejected():
    proposals = []
    for index in range(4):
        proposal = _proposal(); proposal["proposal_id"] = f"p{index}"; proposals.append(proposal)
    with pytest.raises(ValueError, match="at most three"):
        validate_proposals(proposals, [_candidate()])


@pytest.mark.parametrize("url", ["http:", "http://", "https://[::1"])
def test_evidence_link_without_host_or_malformed_rejected(url):
    proposal = _proposal(); proposal["evidence_links"] = ["https://example.test", url]
    with pytest.raises(ValueError, match="http\\(s\\) URLs"):
        validate_proposals([proposal], [_candidate()])
