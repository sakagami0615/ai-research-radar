from __future__ import annotations

from dataclasses import replace
from typing import Any

from ai_research_radar.schemas.models import HotCandidate
from ai_research_radar.schemas.quality import QualityValidationError, validate_assessment

_ALLOWED_KEYS = frozenset({"assessments", "screened_ids", "selection_reason", "summaries"})
_REQUIRED_KEYS = ("assessments", "screened_ids", "selection_reason")


class SelectionError(ValueError):
    """selection_input.json の検証エラー。code は run_state.json の errors の種別になる。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _check_structure(selection: object) -> dict[str, Any]:
    """トップレベルの形(キーの有無と値の型)を検証する。誤りは invalid_input。"""
    if not isinstance(selection, dict):
        raise SelectionError("invalid_input", "selection input must be a JSON object")
    unknown = sorted(set(selection) - _ALLOWED_KEYS)
    if unknown:
        raise SelectionError("invalid_input", f"unknown top-level key(s): {', '.join(unknown)}")
    missing = [key for key in _REQUIRED_KEYS if key not in selection]
    if missing:
        raise SelectionError("invalid_input", f"missing top-level key(s): {', '.join(missing)}")
    if not isinstance(selection["assessments"], list):
        raise SelectionError("invalid_input", "assessments must be a list")
    screened = selection["screened_ids"]
    if not isinstance(screened, list) or any(not isinstance(item, str) for item in screened):
        raise SelectionError("invalid_input", "screened_ids must be a list of strings")
    if not isinstance(selection["selection_reason"], str):
        raise SelectionError("invalid_input", "selection_reason must be a string")
    return selection


def apply_assessments(candidates: list[HotCandidate], selection: object, *, limit: int = 2) -> tuple[list[HotCandidate], dict[str, Any]]:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 0 <= limit <= 5:
        raise SelectionError("invalid_input", f"limit must be an integer between 0 and 5: {limit!r}")
    value = _check_structure(selection)
    if not value["selection_reason"].strip():
        raise SelectionError("invalid_assessment", "selection_reason must be a non-empty string")

    known = {candidate.hot_id for candidate in candidates}
    screened = value["screened_ids"]
    if len(screened) != len(set(screened)):
        raise SelectionError("invalid_assessment", "screened_ids contains duplicates")
    unknown_screened = sorted(set(screened) - known)
    if unknown_screened:
        raise SelectionError("invalid_assessment", f"screened_ids contains unknown hot_id(s): {', '.join(unknown_screened)}")

    by_id: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(value["assessments"]):
        try:
            validate_assessment(item)
        except QualityValidationError as exc:
            raise SelectionError("invalid_assessment", f"assessments[{index}]: {exc}") from exc
        hot_id = item["hot_id"]
        if hot_id not in known:
            raise SelectionError("invalid_assessment", f"assessments[{index}]: unknown hot_id: {hot_id}")
        if hot_id in by_id:
            raise SelectionError("invalid_assessment", f"assessments[{index}]: duplicate hot_id: {hot_id}")
        by_id[hot_id] = item

    not_assessed = sorted(set(screened) - set(by_id))
    not_screened = sorted(set(by_id) - set(screened))
    if not_assessed or not_screened:
        raise SelectionError(
            "invalid_assessment",
            f"screened_ids and assessments must match: screened without assessment={not_assessed}, assessed but not screened={not_screened}",
        )

    selected = [hot_id for hot_id, item in by_id.items() if item["decision"] == "selected"]
    for hot_id in selected:
        if not any(check["status"] == "verified" and check["kind"] == "primary" for check in by_id[hot_id]["evidence"]):
            raise SelectionError("invalid_assessment", f"selected candidate needs verified primary evidence: {hot_id}")
    if len(selected) > limit:
        raise SelectionError("selection_limit_exceeded", f"selected {len(selected)} candidate(s), limit is {limit}")

    updated = [replace(candidate, selected=candidate.hot_id in selected, assessment=by_id.get(candidate.hot_id)) for candidate in candidates]
    unreviewed = sorted(known - set(screened))
    summary = {
        "selection_reason": value["selection_reason"],
        "candidate_count": len(candidates),
        "screened_count": len(screened),
        "unreviewed_count": len(unreviewed),
        "selected_count": len(selected),
        "unreviewed_ids": unreviewed,
    }
    return updated, summary
