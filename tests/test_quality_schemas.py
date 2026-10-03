from datetime import datetime, timezone

import pytest

from ai_research_radar.schemas.decoders import decode_signal, validate_assessment, validate_proposal_quality
from ai_research_radar.schemas.models import to_json_dict
from ai_research_radar.schemas.quality import QualityValidationError


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
