from __future__ import annotations

from typing import Any

from ai_research_radar.schemas.models import CanonicalSignal, Event, HotCandidate, ArticleProposal, RunMetadata, _parse_datetime, _parse_datetime_or_none
from ai_research_radar.schemas.quality import QualityValidationError, validate_assessment, validate_proposal_quality


def _record(data: object) -> dict[str, Any]:
    if not isinstance(data, dict) or isinstance(data, bool):
        raise QualityValidationError("record must be an object")
    return data


def _version(data: dict[str, Any]) -> int:
    version = data.get("schema_version", 1)
    if not isinstance(version, int) or isinstance(version, bool) or version not in {1, 2}:
        raise QualityValidationError("unsupported schema_version")
    return version


def decode_signal(data: object) -> CanonicalSignal:
    value = _record(data); version = _version(value)
    return CanonicalSignal(signal_id=str(value["signal_id"]), source=str(value["source"]), source_family=str(value["source_family"]), content_type=str(value["content_type"]), title=str(value["title"]), url=str(value["url"]), published_at=_parse_datetime_or_none(value.get("published_at")), fetched_at=_parse_datetime(value["fetched_at"]), summary=str(value["summary"]), categories=list(value["categories"]), raw_metrics=dict(value["raw_metrics"]), normalized_scores=dict(value.get("normalized_scores", {})), metadata=dict(value["metadata"]), schema_version=version, quality=dict(value.get("quality", {})))


def decode_event(data: object) -> Event:
    value = _record(data); version = _version(value)
    return Event(event_id=str(value["event_id"]), title=str(value["title"]), description=str(value["description"]), event_type=str(value["event_type"]), first_seen_at=_parse_datetime(value["first_seen_at"]), last_seen_at=_parse_datetime(value["last_seen_at"]), signals=list(value["signals"]), sources=list(value["sources"]), source_families=list(value["source_families"]), scores=dict(value["scores"]), evidence=list(value["evidence"]), schema_version=version, quality=dict(value.get("quality", {})))


def decode_hot(data: object) -> HotCandidate:
    value = _record(data); version = _version(value)
    return HotCandidate(hot_id=str(value["hot_id"]), title=str(value["title"]), topic=str(value["topic"]), score=float(value["score"]), reasons=list(value["reasons"]), evidence_urls=list(value["evidence_urls"]), source_families=list(value["source_families"]), signals=list(value["signals"]), selected=bool(value["selected"]), schema_version=version, quality=dict(value.get("quality", {})), assessment=value.get("assessment"), summary=str(value.get("summary") or ""))


def decode_proposal(data: object) -> ArticleProposal:
    value = _record(data); version = _version(value)
    return ArticleProposal(**{key: value[key] for key in ("proposal_id", "source_hot_id", "title_idea", "article_type", "target_reader", "why_now", "technical_angle", "experiment_plan", "competition", "traffic_opportunity", "technical_opportunity", "unique_angle", "evidence_links", "risks")}, schema_version=version, quality=dict(value.get("quality", {})))


def decode_run(data: object) -> RunMetadata:
    value = _record(data); version = _version(value)
    return RunMetadata(run_id=str(value["run_id"]), started_at=_parse_datetime(value["started_at"]), finished_at=_parse_datetime_or_none(value.get("finished_at")), mode=str(value["mode"]), since=str(value["since"]), until=str(value["until"]), sources=list(value["sources"]), input_counts=dict(value["input_counts"]), output_counts=dict(value["output_counts"]), errors=list(value["errors"]), report_paths=list(value["report_paths"]), schema_version=version, metadata=dict(value.get("metadata", {})))
