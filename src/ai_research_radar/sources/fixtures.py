from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from ai_research_radar.normalization.scores import (
    is_within_period,
    normalized_scores,
    parse_optional_datetime,
)
from ai_research_radar.schemas.models import CanonicalSignal, RawItem
from ai_research_radar.sources.base import SourceAdapter
from ai_research_radar.storage.jsonl import read_jsonl


class FixtureAdapter(SourceAdapter):
    def __init__(
        self,
        source_name: str,
        source_family: str,
        fixture_path: Path,
        content_type: str = "tool",
    ) -> None:
        self.source_name = source_name
        self.source_family = source_family
        self.fixture_path = fixture_path
        self.content_type = content_type

    def collect(self, since: str, until: str) -> list[RawItem]:
        records = read_jsonl(self.fixture_path)
        items = [
            RawItem(
                source=str(record["source"]),
                fetched_at=_parse_datetime(str(record["fetched_at"])),
                raw_id=str(record["raw_id"]),
                raw_url=str(record["raw_url"]),
                payload={
                    **dict(record["payload"]),
                    "raw": dict(record["payload"]).get("raw", dict(record)),
                },
            )
            for record in records
        ]
        return [
            item
            for item in items
            if is_within_period(
                parse_optional_datetime(
                    item.payload.get("updated_at") or item.payload.get("published_at")
                ),
                since,
                until,
            )
        ]

    def normalize(self, item: RawItem) -> CanonicalSignal:
        payload: dict[str, Any] = item.payload
        metrics = dict(payload.get("metrics", {}))
        return CanonicalSignal(
            signal_id=f"{item.source}:{item.raw_id}",
            source=item.source,
            source_family=self.source_family,
            content_type=self.content_type,
            title=str(payload.get("title", item.raw_id)),
            url=str(payload.get("url", item.raw_url)),
            published_at=parse_optional_datetime(
                payload.get("published_at") or payload.get("updated_at")
            ),
            fetched_at=item.fetched_at,
            summary=str(payload.get("summary", "")),
            categories=list(payload.get("categories", [])),
            raw_metrics=metrics,
            normalized_scores=normalized_scores(
                metrics,
                parse_optional_datetime(payload.get("updated_at") or payload.get("published_at")),
                item.fetched_at,
                credibility=70.0,
            ),
            metadata=dict(payload.get("metadata", {})),
        )


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)
