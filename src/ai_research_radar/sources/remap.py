from __future__ import annotations

from typing import Any

from ai_research_radar.normalization.relevance import restore_abstract
from ai_research_radar.schemas.models import RawItem


def remap_raw_item(item: RawItem, adapter_kind: str) -> RawItem:
    if adapter_kind != "openalex":
        return item
    payload = dict(item.payload)
    raw = payload.get("raw")
    if isinstance(raw, dict) and "abstract_inverted_index" in raw:
        summary, diagnostics = restore_abstract(raw.get("abstract_inverted_index"))
        if summary:
            payload["summary"] = summary
        if diagnostics:
            metadata = dict(payload.get("metadata", {}))
            metadata["remap_diagnostics"] = diagnostics
            payload["metadata"] = metadata
    else:
        metadata = dict(payload.get("metadata", {}))
        metadata["remap_diagnostics"] = ["openalex_raw_abstract_unavailable"]
        payload["metadata"] = metadata
    return RawItem(item.source, item.fetched_at, item.raw_id, item.raw_url, payload)
