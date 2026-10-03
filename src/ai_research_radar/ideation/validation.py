from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from ai_research_radar.schemas.quality import validate_proposal_quality


def validate_proposals(records: object, candidates: list[Any]) -> list[Any]:
    if not isinstance(records, list): raise ValueError("proposals must be a list")
    known = {candidate.hot_id: candidate for candidate in candidates}
    result = []; ids = set(); counts: dict[str, int] = {}
    for record in records:
        if not isinstance(record, dict): raise ValueError("proposal must be object")
        if record.get("proposal_id") in ids: raise ValueError("duplicate proposal id")
        ids.add(record.get("proposal_id")); hot_id = record.get("source_hot_id")
        if hot_id not in known: raise ValueError("proposal references unknown candidate")
        if record.get("schema_version") != 2: raise ValueError("new proposal must be v2")
        quality = validate_proposal_quality(record.get("quality"))
        evidence_links = record.get("evidence_links")
        if not isinstance(evidence_links, list) or any(not isinstance(url, str) or urlsplit(url).scheme not in {"http", "https"} for url in evidence_links): raise ValueError("invalid evidence_links")
        primary = {item for item in known[hot_id].evidence_urls}
        if not primary.intersection(evidence_links): raise ValueError("proposal must link candidate evidence")
        counts[hot_id] = counts.get(hot_id, 0) + 1
        if counts[hot_id] > 3: raise ValueError("at most three proposals per candidate")
        result.append(record)
    return result
