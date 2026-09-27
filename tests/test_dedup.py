from dataclasses import replace
from datetime import datetime, timezone

from ai_research_radar.normalization.dedup import deduplicate_signals
from ai_research_radar.schemas.models import CanonicalSignal


def _signal(
    signal_id: str,
    title: str,
    url: str,
    source: str = "github",
    event_type: str | None = None,
) -> CanonicalSignal:
    source_family = "community" if source == "hackernews" else "technology"
    if source == "official_blog":
        source_family = "official"
    metadata = {}
    if event_type:
        metadata["event_type"] = event_type
    return CanonicalSignal(
        signal_id=signal_id,
        source=source,
        source_family=source_family,
        content_type="tool",
        title=title,
        url=url,
        published_at=None,
        fetched_at=datetime(2026, 9, 25, 8, 0, tzinfo=timezone.utc),
        summary=title,
        categories=["agent"],
        raw_metrics={},
        normalized_scores={"momentum": 90, "popularity": 80, "credibility": 70},
        metadata=metadata,
    )


def test_deduplicate_signals_merges_same_url_with_different_titles():
    signals = [
        _signal("github:a", "Agent Runtime", "https://github.com/owner/repo?utm_source=x"),
        _signal("hn:b", "Agent Runtime discussion", "https://github.com/owner/repo", source="hackernews"),
    ]

    deduped = deduplicate_signals(signals)

    assert len(deduped) == 1
    assert deduped[0].url == "https://github.com/owner/repo"
    assert sorted(deduped[0].metadata["source_families"]) == ["community", "technology"]
    assert sorted(deduped[0].metadata["sources"]) == ["github", "hackernews"]


def test_deduplicate_signals_preserves_major_official_event_type_from_second_signal():
    signals = [
        _signal("github:a", "Major Model Release", "https://example.com/model", source="github"),
        _signal(
            "official:b",
            "Major Model Release",
            "https://example.com/model",
            source="official_blog",
            event_type="major_model_release",
        ),
    ]

    deduped = deduplicate_signals(signals)

    assert deduped[0].metadata["event_type"] == "major_model_release"
    assert "official" in deduped[0].metadata["source_families"]


def test_deduplicate_signals_keeps_all_sources_from_previously_merged_second_signal():
    signals = [
        _signal("official:a", "Major API Release", "https://example.com/api", source="official_blog"),
        replace(
            _signal("github:b", "Major API Release", "https://example.com/api"),
            metadata={
                "sources": ["github", "hackernews"],
                "source_families": ["technology", "community"],
            },
        ),
    ]

    deduped = deduplicate_signals(signals)

    assert deduped[0].metadata["sources"] == ["github", "hackernews", "official_blog"]
    assert deduped[0].metadata["source_families"] == ["community", "official", "technology"]


def test_deduplicate_signals_keeps_different_urls():
    signals = [
        _signal("github:a", "Agent Runtime", "https://github.com/owner/repo-a"),
        _signal("github:b", "Agent Runtime", "https://github.com/owner/repo-b"),
    ]

    assert len(deduplicate_signals(signals)) == 2


def test_deduplicate_signals_preserves_meaningful_query_parameters():
    signals = [
        _signal("hn:one", "First item", "https://example.com/item?id=1"),
        _signal("hn:two", "Second item", "https://example.com/item?id=2"),
    ]

    assert len(deduplicate_signals(signals)) == 2


def test_deduplicate_signals_does_not_merge_empty_urls():
    signals = [
        _signal("github:one", "First item", ""),
        _signal("github:two", "Second item", ""),
    ]

    deduped = deduplicate_signals(signals)

    assert len(deduped) == 2
    assert {signal.signal_id for signal in deduped} == {"github:one", "github:two"}
