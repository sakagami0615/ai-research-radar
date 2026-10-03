from __future__ import annotations

import hashlib
import json
from typing import Any


def build_review_target(files: dict[str, str]) -> dict[str, Any]:
    return {"hashes": {key: hashlib.sha256(value.encode("utf-8")).hexdigest() for key, value in files.items()}, "keys": sorted(files)}


def validate_review_result(data: object) -> dict[str, Any]:
    if not isinstance(data, dict): raise ValueError("review result must be object")
    if data.get("status") not in {"approved", "changes_requested", "failed"}: raise ValueError("invalid review status")
    if not isinstance(data.get("attempt_number"), int) or not 1 <= data["attempt_number"] <= 3: raise ValueError("invalid attempt number")
    findings = data.get("findings", [])
    if not isinstance(findings, list): raise ValueError("findings must be list")
    if data["status"] == "approved" and any(item.get("severity") in {"critical", "important"} for item in findings if isinstance(item, dict)): raise ValueError("approved result has important findings")
    return data
