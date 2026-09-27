from pathlib import Path

from ai_research_radar.sources.fixtures import FixtureAdapter


def test_fixture_adapter_collects_raw_items():
    adapter = FixtureAdapter(
        source_name="github",
        source_family="technology",
        fixture_path=Path("tests/fixtures/sample_raw_items.jsonl"),
    )

    items = adapter.collect(since="2026-09-24", until="2026-09-25")

    assert len(items) == 2
    assert items[0].source == "github"
    assert items[0].payload["title"] == "Agent Runtime"


def test_fixture_adapter_normalizes_to_signal():
    adapter = FixtureAdapter(
        source_name="github",
        source_family="technology",
        fixture_path=Path("tests/fixtures/sample_raw_items.jsonl"),
    )
    item = adapter.collect(since="2026-09-24", until="2026-09-25")[0]

    signal = adapter.normalize(item)

    assert signal.signal_id == "github:owner/agent-runtime"
    assert signal.source_family == "technology"
    assert signal.title == "Agent Runtime"
    assert signal.raw_metrics["stars_24h"] == 320
    assert signal.normalized_scores["momentum"] > 0
