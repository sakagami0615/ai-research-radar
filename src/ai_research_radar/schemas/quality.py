from __future__ import annotations

from typing import Any, Literal, TypedDict


class QualityValidationError(ValueError):
    """v2の外部入力が契約に適合しない。"""


class RelevanceRecord(TypedDict):
    status: Literal["related", "uncertain", "unrelated"]
    matched_terms: list[str]
    reason: str
    method: Literal["keyword", "agent", "legacy"]


class EvidenceCheck(TypedDict):
    url: str
    checked_at: str
    target_version: str | None
    status: Literal["verified", "unavailable", "unverified", "unknown"]
    kind: Literal["primary", "independent", "republication", "unknown"]
    claim: str
    note: str


class ProposalQuality(TypedDict):
    question: str
    difference: str
    baseline: str
    baseline_version: str
    measurement: str
    inputs_and_environment: str
    effort: str
    effort_assumptions: str
    success_condition: str
    stop_condition: str
    metrics: list[str]
    evidence: list[EvidenceCheck]
    unknowns: list[str]


class MetricRecord(TypedDict, total=False):
    name: str
    value: float | None
    unit: str
    observed_at: str
    status: Literal["observed", "missing", "invalid"]
    delta: float | None
    interval_hours: float | None
    previous_observed_at: str | None


class SignalQuality(TypedDict, total=False):
    relevance: RelevanceRecord
    updated_at: str | None
    period_basis: Literal["published_at", "updated_at"]
    metrics: list[MetricRecord]
    freshness_score: float | None
    popularity_rank: float | None
    rank_population: int
    rank_all_zero: bool
    priority: float
    diagnostics: list[str]
    identity: dict[str, Any]
    source_kind: str


class Assessment(TypedDict):
    hot_id: str
    decision: Literal["selected", "deferred", "rejected"]
    assessed_at: str
    assessor: str
    relevance: RelevanceRecord
    novelty: str
    importance: str
    reader_impact: str
    reason: str
    evidence: list[EvidenceCheck]
    unknowns: list[str]


class SelectionInput(TypedDict):
    assessments: list[Assessment]
    screened_ids: list[str]
    selection_reason: str


class ReviewResult(TypedDict):
    status: Literal["approved", "changes_requested", "failed"]
    run_id: str
    reviewer: str
    reviewer_run_id: str
    reviewed_at: str
    attempt_number: int
    target_hashes: dict[str, str]
    findings: list[dict[str, Any]]


def _object(data: object) -> dict[str, Any]:
    if not isinstance(data, dict) or isinstance(data, bool):
        raise QualityValidationError("quality input must be an object")
    return data


def _required_text(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise QualityValidationError(f"{key} must be a non-empty string")
    return value


def validate_relevance(data: object) -> RelevanceRecord:
    value = _object(data)
    status = value.get("status")
    method = value.get("method")
    terms = value.get("matched_terms")
    if status not in {"related", "uncertain", "unrelated"} or method not in {"keyword", "agent", "legacy"}:
        raise QualityValidationError("invalid relevance status or method")
    if not isinstance(terms, list) or any(not isinstance(item, str) for item in terms):
        raise QualityValidationError("matched_terms must be a string list")
    return {"status": status, "matched_terms": terms, "reason": _required_text(value, "reason"), "method": method}


def validate_assessment(data: object) -> dict[str, Any]:
    value = _object(data)
    if value.get("decision") not in {"selected", "deferred", "rejected"}:
        raise QualityValidationError("invalid assessment decision")
    for key in ("hot_id", "assessed_at", "assessor", "novelty", "importance", "reader_impact", "reason"):
        _required_text(value, key)
    validate_relevance(value.get("relevance"))
    evidence = value.get("evidence")
    if not isinstance(evidence, list):
        raise QualityValidationError("evidence must be a list")
    if not isinstance(value.get("unknowns"), list) or any(not isinstance(item, str) for item in value["unknowns"]):
        raise QualityValidationError("unknowns must be a string list")
    return value


def validate_proposal_quality(data: object) -> ProposalQuality:
    value = _object(data)
    text_keys = ("question", "difference", "baseline", "baseline_version", "measurement", "inputs_and_environment", "effort", "effort_assumptions", "success_condition", "stop_condition")
    for key in text_keys:
        _required_text(value, key)
    if not isinstance(value.get("metrics"), list) or not value["metrics"] or any(not isinstance(item, str) or not item.strip() for item in value["metrics"]):
        raise QualityValidationError("metrics must be a non-empty string list")
    if not isinstance(value.get("evidence"), list) or not isinstance(value.get("unknowns"), list):
        raise QualityValidationError("evidence and unknowns must be lists")
    return value  # type: ignore[return-value]
