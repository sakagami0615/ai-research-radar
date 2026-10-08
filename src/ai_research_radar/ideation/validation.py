from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from ai_research_radar.schemas.quality import QualityValidationError, validate_proposal_quality

# Fields every ArticleProposal must have (stored as-is in article_proposals.jsonl).
REQUIRED_FIELDS = frozenset(
    {
        "proposal_id",
        "source_hot_id",
        "title_idea",
        "article_type",
        "target_reader",
        "why_now",
        "technical_angle",
        "experiment_plan",
        "competition",
        "traffic_opportunity",
        "technical_opportunity",
        "unique_angle",
        "evidence_links",
        "risks",
    }
)
# Fields that are lists of strings; the rest of REQUIRED_FIELDS are non-empty strings.
LIST_FIELDS = frozenset({"experiment_plan", "risks", "evidence_links"})
MAX_PROPOSALS_PER_CANDIDATE = 3


def validate_proposals(records: object, candidates: list[Any]) -> list[dict[str, Any]]:
    """v2 の記事企画を検証する。誤りは `proposal[<index>] ...` の ValueError で送出する。

    candidates は当日の HotCandidate。`source_hot_id` は選抜済み(selected=True)であること。
    """
    if not isinstance(records, list):
        raise ValueError("proposals must be a list")
    known = {candidate.hot_id: candidate for candidate in candidates}
    ids: set[str] = set()
    counts: dict[str, int] = {}
    for index, record in enumerate(records):
        try:
            _validate_one(record, known, ids, counts)
        except ValueError as exc:
            raise ValueError(f"proposal[{index}] {exc}") from exc
    return list(records)


def _is_http_url(url: str) -> bool:
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    return parts.scheme in {"http", "https"} and bool(parts.netloc)


def _validate_one(record: object, known: dict[str, Any], ids: set[str], counts: dict[str, int]) -> None:
    if not isinstance(record, dict):
        raise ValueError("must be an object")
    if type(record.get("schema_version")) is not int or record["schema_version"] != 2:
        raise ValueError("schema_version must be 2")
    missing = REQUIRED_FIELDS - set(record)
    if missing:
        raise ValueError(f"missing fields: {', '.join(sorted(missing))}")
    for field in sorted(REQUIRED_FIELDS):
        value = record[field]
        if field in LIST_FIELDS:
            if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
                raise ValueError(f"{field} must be a list of strings")
        elif not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} must be a non-empty string")

    proposal_id = record["proposal_id"]
    if proposal_id in ids:
        raise ValueError(f"duplicate proposal_id: {proposal_id}")
    ids.add(proposal_id)

    hot_id = record["source_hot_id"]
    candidate = known.get(hot_id)
    if candidate is None:
        raise ValueError(f"source_hot_id is an unknown HOT candidate: {hot_id}")
    if candidate.selected is not True:
        raise ValueError(f"source_hot_id is not a selected HOT candidate: {hot_id}")

    try:
        quality = validate_proposal_quality(record.get("quality"))
    except QualityValidationError as exc:
        raise ValueError(f"invalid quality: {exc}") from exc

    evidence_links = record["evidence_links"]
    for url in evidence_links:
        if not _is_http_url(url):
            raise ValueError(f"evidence_links must be http(s) URLs with a host: {url!r}")
    primary = set(candidate.evidence_urls)
    if not primary.intersection(evidence_links):
        raise ValueError("evidence_links must include at least one of the candidate evidence URLs")
    # A URL added for comparison must state its role in the claim of a quality.evidence entry.
    roles = {item["url"] for item in quality["evidence"] if item["claim"].strip()}
    for url in evidence_links:
        if url not in primary and url not in roles:
            raise ValueError(f"additional evidence link needs a quality.evidence entry with a non-empty claim: {url}")

    counts[hot_id] = counts.get(hot_id, 0) + 1
    if counts[hot_id] > MAX_PROPOSALS_PER_CANDIDATE:
        raise ValueError(f"at most three proposals per candidate: {hot_id}")
