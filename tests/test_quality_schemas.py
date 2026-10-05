from datetime import datetime, timezone

import pytest

from ai_research_radar.schemas.decoders import decode_signal, validate_assessment, validate_proposal_quality
from ai_research_radar.schemas.models import to_json_dict
from ai_research_radar.schemas.quality import QualityValidationError, validate_evidence_check, validate_evidence_list


def _signal(**extra):
    return {
        "signal_id": "s1", "source": "github", "source_family": "technology",
        "content_type": "tool", "title": "x", "url": "https://example.test/x",
        "published_at": None, "fetched_at": "2026-09-29T00:00:00+00:00", "summary": "",
        "categories": [], "raw_metrics": {"stars": 1}, "normalized_scores": {"popularity": 1},
        "metadata": {}, **extra,
    }


def test_legacy_records_keep_scores_and_unknown_quality():
    loaded = decode_signal(_signal())
    assert loaded.schema_version == 1
    assert loaded.normalized_scores["popularity"] == 1
    assert loaded.quality == {}


def test_v2_roundtrip_preserves_null():
    data = _signal(schema_version=2, quality={"freshness_score": None, "popularity_rank": None})
    loaded = decode_signal(data)
    assert to_json_dict(loaded)["quality"]["freshness_score"] is None


def test_strict_input_rejects_non_object_and_wrong_types():
    with pytest.raises(QualityValidationError):
        validate_assessment([])
    with pytest.raises(QualityValidationError):
        validate_assessment({"decision": "maybe"})
    with pytest.raises(QualityValidationError):
        validate_proposal_quality({"question": " "})


def _evidence(**overrides):
    record = {
        "url": "https://example.test/release",
        "checked_at": "2026-10-05T00:00:00+00:00",
        "target_version": None,
        "status": "verified",
        "kind": "primary",
        "claim": "リリースを確認",
        "note": "",
    }
    record.update(overrides)
    return record


def _assessment_with(evidence):
    return {
        "hot_id": "hot:x", "decision": "selected", "assessed_at": "2026-10-05T00:00:00+00:00", "assessor": "agent",
        "relevance": {"status": "related", "matched_terms": [], "reason": "r", "method": "agent"},
        "novelty": "n", "importance": "i", "reader_impact": "r", "reason": "reason",
        "evidence": evidence, "unknowns": [],
    }


def _quality_with(evidence):
    return {
        "question": "q", "difference": "d", "baseline": "b", "baseline_version": "1", "measurement": "m",
        "inputs_and_environment": "env", "effort": "1d", "effort_assumptions": "a", "success_condition": "s",
        "stop_condition": "stop", "metrics": ["accuracy"], "evidence": evidence, "unknowns": [],
    }


def test_evidence_check_accepts_valid_record_and_returns_it():
    record = _evidence(target_version="1.2.0", claim="", note="範囲")
    assert validate_evidence_check(record) is record


@pytest.mark.parametrize(
    "record",
    [
        None,
        "https://example.test",
        _evidence(url="ftp://example.test/x"),
        _evidence(url="https://"),
        _evidence(url=123),
        _evidence(url="http://[broken"),
        _evidence(checked_at=None),
        _evidence(claim=1),
        _evidence(note=None),
        _evidence(target_version=1),
        _evidence(status="ok"),
        _evidence(kind="secondary"),
        {key: value for key, value in _evidence().items() if key != "note"},
        _evidence(extra="x"),
    ],
)
def test_evidence_check_rejects_malformed_record(record):
    with pytest.raises(QualityValidationError):
        validate_evidence_check(record)


def test_evidence_list_requires_list():
    with pytest.raises(QualityValidationError):
        validate_evidence_list({"url": "https://example.test"})
    assert validate_evidence_list([]) == []


def test_assessment_and_proposal_quality_reject_malformed_evidence():
    with pytest.raises(QualityValidationError):
        validate_assessment(_assessment_with([_evidence(status="ok")]))
    with pytest.raises(QualityValidationError):
        validate_proposal_quality(_quality_with([None]))
    assert validate_assessment(_assessment_with([_evidence()]))["hot_id"] == "hot:x"
    assert validate_proposal_quality(_quality_with([_evidence()]))["question"] == "q"
