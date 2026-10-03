from datetime import datetime, timezone

from ai_research_radar.schemas.models import RawItem
from ai_research_radar.sources.remap import remap_raw_item


def test_openalex_remap_preserves_identity_dates_and_raw_payload():
    fetched_at = datetime(2026, 9, 29, 12, tzinfo=timezone.utc)
    raw = {"title": "A paper", "abstract_inverted_index": {"a": [0, 2], "test": [1]}}
    item = RawItem("openalex", fetched_at, "W1", "https://example.test", {
        "title": "A paper", "summary": "wrong", "raw": raw,
        "published_at": "2026-09-29T00:00:00+00:00",
    })

    remapped = remap_raw_item(item, "openalex")

    assert remapped.raw_id == item.raw_id
    assert remapped.source == item.source
    assert remapped.fetched_at == item.fetched_at
    assert remapped.payload["raw"] is raw
    assert remapped.payload["summary"] == "a test a"


def test_remap_without_raw_keeps_existing_value_and_reports_diagnostic():
    item = RawItem("openalex", datetime.now(timezone.utc), "W1", "", {"summary": "existing"})
    remapped = remap_raw_item(item, "openalex")
    assert remapped.payload["summary"] == "existing"
    assert remapped.payload["metadata"]["remap_diagnostics"]
