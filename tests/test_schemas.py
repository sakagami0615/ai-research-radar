from datetime import datetime, timezone

from ai_research_radar.schemas.models import (
    ArticleProposal,
    CanonicalSignal,
    Event,
    HotCandidate,
    RawItem,
    RunMetadata,
    canonical_signal_from_dict,
    event_from_dict,
    to_json_dict,
)


def test_raw_item_serializes_datetime_to_iso8601():
    item = RawItem(
        source="github",
        fetched_at=datetime(2026, 9, 25, 8, 0, tzinfo=timezone.utc),
        raw_id="owner/repo",
        raw_url="https://github.com/owner/repo",
        payload={"stars": 42},
    )

    data = to_json_dict(item)

    assert data["source"] == "github"
    assert data["fetched_at"] == "2026-09-25T08:00:00+00:00"
    assert data["payload"]["stars"] == 42


def test_signal_keeps_scores_and_evidence_url():
    signal = CanonicalSignal(
        signal_id="github:owner/repo",
        source="github",
        source_family="technology",
        content_type="tool",
        title="Example Agent Runtime",
        url="https://github.com/owner/repo",
        published_at=None,
        fetched_at=datetime(2026, 9, 25, 8, 0, tzinfo=timezone.utc),
        summary="A tool for agent runtimes.",
        categories=["agent", "runtime"],
        raw_metrics={"stars": 100},
        normalized_scores={"popularity": 91, "momentum": 96, "credibility": 70},
        metadata={"owner": "owner"},
    )

    data = to_json_dict(signal)

    assert data["signal_id"] == "github:owner/repo"
    assert data["normalized_scores"]["momentum"] == 96
    assert data["url"] == "https://github.com/owner/repo"


def test_hot_candidate_and_article_proposal_link_to_evidence():
    candidate = HotCandidate(
        hot_id="hot-1",
        title="Example Agent Runtime is surging",
        topic="agent runtime",
        score=94.5,
        reasons=["Momentum 96", "GitHub and HN evidence"],
        evidence_urls=["https://github.com/owner/repo"],
        source_families=["technology", "community"],
        signals=["github:owner/repo"],
        selected=True,
    )
    proposal = ArticleProposal(
        proposal_id="proposal-1",
        source_hot_id=candidate.hot_id,
        title_idea="Example Agent Runtimeを旧来方式と比較する",
        article_type="Comparison",
        target_reader="AI Engineer",
        why_now="HOT score is high and public evidence exists.",
        technical_angle="Runtime architecture and integration points.",
        experiment_plan=["Install package", "Run sample workflow"],
        competition="Low",
        traffic_opportunity="High",
        technical_opportunity="High",
        unique_angle="Japanese comparison with reproducible examples.",
        evidence_links=candidate.evidence_urls,
        risks=["Metrics are early and may cool down."],
    )

    assert to_json_dict(candidate)["selected"] is True
    assert to_json_dict(proposal)["evidence_links"] == [
        "https://github.com/owner/repo"
    ]


def test_run_metadata_tracks_errors_and_outputs():
    run = RunMetadata(
        run_id="2026-09-25T08:00:00Z",
        started_at=datetime(2026, 9, 25, 8, 0, tzinfo=timezone.utc),
        finished_at=None,
        mode="daily",
        since="2026-09-24",
        until="2026-09-25",
        sources=["github", "arxiv"],
        input_counts={"github": 2},
        output_counts={"signals": 2},
        errors=[{"source": "arxiv", "type": "network_error", "message": "timeout"}],
        report_paths=[],
    )

    assert to_json_dict(run)["errors"][0]["source"] == "arxiv"


def test_canonical_signal_from_dict_round_trips_through_json():
    signal = CanonicalSignal(
        signal_id="github:owner/repo",
        source="github",
        source_family="technology",
        content_type="tool",
        title="Example Agent Runtime",
        url="https://github.com/owner/repo",
        published_at=datetime(2026, 9, 24, 9, 0, tzinfo=timezone.utc),
        fetched_at=datetime(2026, 9, 25, 8, 0, tzinfo=timezone.utc),
        summary="A tool for agent runtimes.",
        categories=["agent", "runtime"],
        raw_metrics={"stars": 100},
        normalized_scores={"popularity": 91, "momentum": 96, "credibility": 70},
        metadata={"owner": "owner"},
    )

    restored = canonical_signal_from_dict(to_json_dict(signal))

    assert restored == signal


def test_canonical_signal_from_dict_handles_missing_published_at():
    signal = CanonicalSignal(
        signal_id="github:owner/repo",
        source="github",
        source_family="technology",
        content_type="tool",
        title="Example Agent Runtime",
        url="https://github.com/owner/repo",
        published_at=None,
        fetched_at=datetime(2026, 9, 25, 8, 0, tzinfo=timezone.utc),
        summary="",
        categories=[],
        raw_metrics={},
        normalized_scores={},
        metadata={},
    )

    restored = canonical_signal_from_dict(to_json_dict(signal))

    assert restored.published_at is None


def test_event_from_dict_round_trips_through_json():
    event = Event(
        event_id="event:agent-runtime",
        title="Agent Runtime",
        description="Agent runtime event",
        event_type="observed_signal",
        first_seen_at=datetime(2026, 9, 25, 8, 0, tzinfo=timezone.utc),
        last_seen_at=datetime(2026, 9, 25, 9, 0, tzinfo=timezone.utc),
        signals=["github:repo"],
        sources=["github"],
        source_families=["technology"],
        scores={"momentum": 90, "popularity": 80, "credibility": 70},
        evidence=["https://github.com/owner/repo"],
    )

    restored = event_from_dict(to_json_dict(event))

    assert restored == event


def test_decode_hot_reads_summary_and_defaults_to_empty_for_legacy_records():
    from dataclasses import asdict

    from ai_research_radar.schemas.decoders import decode_hot

    candidate = HotCandidate("hot:a", "A", "a", 80.0, [], [], [], [], False, summary="概要")
    legacy = asdict(candidate)
    del legacy["summary"]

    assert decode_hot(asdict(candidate)).summary == "概要"
    assert decode_hot(legacy).summary == ""
