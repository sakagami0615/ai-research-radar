from datetime import datetime, timezone

import pytest

from ai_research_radar.schemas.models import Event
from ai_research_radar.scoring.assessments import SelectionError, apply_assessments, compute_discovery_candidates


def _event(name="e1"):
    now = datetime.now(timezone.utc)
    return Event(name, "Title", "desc", "observed_signal", now, now, ["s"], ["x"], ["technology"], {}, ["https://example.test"])


def _evidence(**overrides):
    record = {"url": "https://example.test", "checked_at": "2026-09-29T00:00:00+00:00", "target_version": None, "status": "verified", "kind": "primary", "claim": "claim", "note": "scope"}
    record.update(overrides)
    return record


def _assessment(hot_id, decision="selected", **overrides):
    record = {"hot_id": hot_id, "decision": decision, "assessed_at": "2026-09-29T00:00:00+00:00", "assessor": "agent", "relevance": {"status": "related", "matched_terms": ["llm"], "reason": "r", "method": "agent"}, "novelty": "n", "importance": "i", "reader_impact": "r", "reason": "reason", "evidence": [_evidence()], "unknowns": []}
    record.update(overrides)
    return record


def _candidates(*names):
    return compute_discovery_candidates([_event(name) for name in names])


def _selection(assessments, screened, reason="理由", **extra):
    return {"assessments": assessments, "screened_ids": screened, "selection_reason": reason, **extra}


def _code(candidates, selection, **kwargs):
    with pytest.raises(SelectionError) as info:
        apply_assessments(candidates, selection, **kwargs)
    return info.value.code


def test_zero_priority_research_preserved():
    assert len(compute_discovery_candidates([_event()])) == 1


def test_applies_assessments_and_returns_counts():
    a, b, c = _candidates("a", "b", "c")
    selection = _selection([_assessment(a.hot_id), _assessment(b.hot_id, "rejected")], [a.hot_id, b.hot_id], summaries={a.hot_id: "概要"})

    updated, summary = apply_assessments([a, b, c], selection)

    by_id = {item.hot_id: item for item in updated}
    assert by_id[a.hot_id].selected is True
    assert by_id[a.hot_id].assessment == selection["assessments"][0]
    assert by_id[b.hot_id].selected is False
    assert by_id[b.hot_id].assessment["decision"] == "rejected"
    assert by_id[c.hot_id].selected is False
    assert by_id[c.hot_id].assessment is None
    assert summary == {"selection_reason": "理由", "candidate_count": 3, "screened_count": 2, "unreviewed_count": 1, "selected_count": 1, "unreviewed_ids": [c.hot_id]}


def test_selection_error_is_value_error():
    assert issubclass(SelectionError, ValueError)


@pytest.mark.parametrize("limit", [-1, 6, "2", True])
def test_invalid_limit_is_invalid_input(limit):
    assert _code(_candidates("a"), _selection([], []), limit=limit) == "invalid_input"


@pytest.mark.parametrize(
    "selection",
    [
        [],
        {"assessments": [], "screened_ids": []},
        {"assessments": [], "selection_reason": "x"},
        {"screened_ids": [], "selection_reason": "x"},
        _selection([], [], summary={}),
        _selection({}, []),
        _selection([], "hot:a"),
        _selection([], [1]),
        _selection([], [], reason=None),
    ],
)
def test_malformed_structure_is_invalid_input(selection):
    assert _code(_candidates("a"), selection) == "invalid_input"


def test_blank_selection_reason_is_invalid_assessment():
    assert _code(_candidates("a"), _selection([], [], reason="  ")) == "invalid_assessment"


def test_screened_ids_duplicates_or_unknown_are_invalid_assessment():
    (a,) = _candidates("a")
    assert _code([a], _selection([_assessment(a.hot_id)], [a.hot_id, a.hot_id])) == "invalid_assessment"
    assert _code([a], _selection([], ["hot:unknown"])) == "invalid_assessment"


def test_invalid_assessment_records_are_invalid_assessment():
    (a,) = _candidates("a")
    assert _code([a], _selection([None], [a.hot_id])) == "invalid_assessment"
    assert _code([a], _selection([_assessment(a.hot_id, evidence=[_evidence(url="ftp://x")])], [a.hot_id])) == "invalid_assessment"
    assert _code([a], _selection([_assessment("hot:unknown")], [])) == "invalid_assessment"
    assert _code([a], _selection([_assessment(a.hot_id), _assessment(a.hot_id)], [a.hot_id])) == "invalid_assessment"


def test_screened_ids_must_match_assessments():
    a, b = _candidates("a", "b")
    with pytest.raises(SelectionError) as info:
        apply_assessments([a, b], _selection([_assessment(b.hot_id, "rejected")], [a.hot_id]))
    assert info.value.code == "invalid_assessment"
    assert a.hot_id in str(info.value) and b.hot_id in str(info.value)


def test_selected_without_verified_primary_evidence_is_invalid_assessment():
    (a,) = _candidates("a")
    for evidence in ([], [_evidence(status="unverified")], [_evidence(kind="independent")]):
        assert _code([a], _selection([_assessment(a.hot_id, evidence=evidence)], [a.hot_id])) == "invalid_assessment"


def test_deferred_without_evidence_is_allowed():
    (a,) = _candidates("a")
    updated, summary = apply_assessments([a], _selection([_assessment(a.hot_id, "deferred", evidence=[])], [a.hot_id]))
    assert updated[0].selected is False and summary["selected_count"] == 0


def test_selection_limit():
    candidates = _candidates("a", "b")
    selection = _selection([_assessment(c.hot_id) for c in candidates], [c.hot_id for c in candidates])
    assert _code(candidates, selection, limit=1) == "selection_limit_exceeded"
    assert apply_assessments(candidates, selection, limit=2)[1]["selected_count"] == 2
