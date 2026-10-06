from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class RawItem:
    source: str
    fetched_at: datetime
    raw_id: str
    raw_url: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class CanonicalSignal:
    signal_id: str
    source: str
    source_family: str
    content_type: str
    title: str
    url: str
    published_at: datetime | None
    fetched_at: datetime
    summary: str
    categories: list[str]
    raw_metrics: dict[str, Any]
    normalized_scores: dict[str, float]
    metadata: dict[str, Any]
    schema_version: int = 1
    quality: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Event:
    event_id: str
    title: str
    description: str
    event_type: str
    first_seen_at: datetime
    last_seen_at: datetime
    signals: list[str]
    sources: list[str]
    source_families: list[str]
    scores: dict[str, float]
    evidence: list[str]
    schema_version: int = 1
    quality: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Topic:
    topic_id: str
    name: str
    aliases: list[str]
    categories: list[str]
    related_topics: list[str]
    events: list[str]
    trend_history: list[dict[str, Any]]
    current_scores: dict[str, float]
    status: str


@dataclass(frozen=True)
class HotCandidate:
    hot_id: str
    title: str
    topic: str
    score: float
    reasons: list[str]
    evidence_urls: list[str]
    source_families: list[str]
    signals: list[str]
    selected: bool
    schema_version: int = 1
    quality: dict[str, Any] = field(default_factory=dict)
    assessment: dict[str, Any] | None = None
    # Japanese overview written by the Agent (`summaries` in selection_input.json); empty if not written.
    summary: str = ""


@dataclass(frozen=True)
class ArticleProposal:
    proposal_id: str
    source_hot_id: str
    title_idea: str
    article_type: str
    target_reader: str
    why_now: str
    technical_angle: str
    experiment_plan: list[str]
    competition: str
    traffic_opportunity: str
    technical_opportunity: str
    unique_angle: str
    evidence_links: list[str]
    risks: list[str]
    schema_version: int = 1
    quality: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RunMetadata:
    run_id: str
    started_at: datetime
    finished_at: datetime | None
    mode: str
    since: str
    until: str
    sources: list[str]
    input_counts: dict[str, int]
    output_counts: dict[str, int]
    errors: list[dict[str, str]]
    report_paths: list[str]
    schema_version: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)


def to_json_dict(value: Any) -> dict[str, Any]:
    if is_dataclass(value):
        value = asdict(value)
    return _json_ready(value)


def _json_ready(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value


def canonical_signal_from_dict(data: dict[str, Any]) -> CanonicalSignal:
    from ai_research_radar.schemas.decoders import decode_signal
    return decode_signal(data)


def event_from_dict(data: dict[str, Any]) -> Event:
    from ai_research_radar.schemas.decoders import decode_event
    return decode_event(data)


def _parse_datetime(value: Any) -> datetime:
    return datetime.fromisoformat(str(value))


def _parse_datetime_or_none(value: Any) -> datetime | None:
    if value is None:
        return None
    return _parse_datetime(value)
