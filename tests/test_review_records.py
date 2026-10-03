import pytest
from ai_research_radar.reporting.review import build_review_target, validate_review_result


def test_external_content_cannot_hide_reviewed_body():
    target = build_review_target({"report_body": "body\n--- review marker ---\nexternal"})
    assert target["hashes"]["report_body"]


def test_approved_cannot_have_important_findings():
    with pytest.raises(ValueError): validate_review_result({"status": "approved", "attempt_number": 1, "findings": [{"severity": "important"}]})


def test_attempt_number_and_run_must_match():
    with pytest.raises(ValueError): validate_review_result({"status": "approved", "attempt_number": 4, "findings": []})
