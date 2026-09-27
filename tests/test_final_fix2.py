from datetime import datetime, timezone
from pathlib import Path

import pytest

from ai_research_radar.ideation.proposals import generate_article_proposals
from ai_research_radar.normalization.scores import normalized_scores
from ai_research_radar.pipeline.daily import run_daily
from ai_research_radar.schemas.models import CanonicalSignal, HotCandidate, RawItem
from ai_research_radar.sources.base import SourceAdapter


NOW = datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc)
PUBLISHED = datetime(2026, 9, 25, 8, 0, tzinfo=timezone.utc)


class MetricAdapter(SourceAdapter):
    def __init__(
        self,
        source_name: str,
        items: list[tuple[str, dict[str, float]]],
        published_at: datetime = PUBLISHED,
    ) -> None:
        self.source_name = source_name
        self.source_family = "technology"
        self._published_at = published_at
        self._items = [
            RawItem(
                source=source_name,
                fetched_at=NOW,
                raw_id=raw_id,
                raw_url=f"https://example.com/{source_name}/{raw_id}",
                payload={"metrics": metrics},
            )
            for raw_id, metrics in items
        ]

    def collect(self, since: str, until: str) -> list[RawItem]:
        return self._items

    def normalize(self, item: RawItem) -> CanonicalSignal:
        return CanonicalSignal(
            signal_id=f"{item.source}:{item.raw_id}",
            source=item.source,
            source_family=self.source_family,
            content_type="package",
            title=f"AI {item.raw_id}",
            url=item.raw_url,
            published_at=self._published_at,
            fetched_at=item.fetched_at,
            summary="AI package",
            categories=["ai"],
            raw_metrics=dict(item.payload["metrics"]),
            normalized_scores=normalized_scores(
                item.payload["metrics"], self._published_at, item.fetched_at, credibility=70
            ),
            metadata={"event_type": "observed_signal"},
        )


def _run(adapters: list[SourceAdapter], tmp_path: Path, minimum_score: float = 0):
    return run_daily(
        adapters=adapters,
        since="2026-09-24",
        until="2026-09-25",
        output_dir=tmp_path / "data",
        report_dir=tmp_path / "reports",
        minimum_score=minimum_score,
    )


def test_pipeline_uses_source_local_metric_rank_for_popularity(tmp_path: Path):
    result = _run(
        [MetricAdapter("github", [("popular", {"stars": 200}), ("quiet", {"stars": 5})])],
        tmp_path,
    )

    popularity = {signal.signal_id: signal.normalized_scores["popularity"] for signal in result.signals}

    assert popularity["github:popular"] == 100
    assert popularity["github:quiet"] == 0


def test_pipeline_source_local_scores_prevent_huge_cross_source_raw_metric_from_dominating(
    tmp_path: Path,
):
    result = _run(
        [
            MetricAdapter("github", [("huge", {"stars": 10**12})]),
            MetricAdapter("npm", [("strong", {"popularity": 0.95})]),
        ],
        tmp_path,
    )

    popularity = {signal.source: signal.normalized_scores["popularity"] for signal in result.signals}
    scores = [candidate.score for candidate in result.hot_candidates]

    assert abs(popularity["github"] - popularity["npm"]) <= 10
    assert all(0 <= score <= 100 for score in scores)


@pytest.mark.parametrize(
    ("source", "metrics"),
    [
        ("npm", {"popularity": 0.98}),
        ("pypi", {"ai_keyword_strength": 1.0}),
    ],
)
def test_fresh_strong_ai_package_can_become_hot_from_a_single_source(
    source: str,
    metrics: dict[str, float],
    tmp_path: Path,
):
    result = _run([MetricAdapter(source, [("strong-package", metrics)])], tmp_path, minimum_score=75)

    assert len(result.hot_candidates) == 1
    assert result.hot_candidates[0].selected is True
    assert 75 <= result.hot_candidates[0].score <= 100


def test_weak_single_pypi_keyword_match_does_not_become_hot(tmp_path: Path):
    result = _run(
        [MetricAdapter("pypi", [("generic-agent", {"ai_keyword_strength": 0.65})])],
        tmp_path,
        minimum_score=75,
    )

    assert result.hot_candidates == []


def test_fresh_strong_pypi_item_can_become_hot_within_a_source_batch(tmp_path: Path):
    result = _run(
        [
            MetricAdapter(
                "pypi",
                [
                    ("strong-llm-package", {"ai_keyword_strength": 1.0}),
                    ("generic-agent-package", {"ai_keyword_strength": 0.65}),
                ],
            )
        ],
        tmp_path,
        minimum_score=75,
    )

    assert [candidate.title for candidate in result.hot_candidates] == ["AI strong-llm-package"]


@pytest.mark.parametrize(
    ("source", "metrics"),
    [
        ("pypi", {"ai_keyword_strength": 1.0}),
        ("npm", {"popularity": 0.95}),
    ],
)
def test_fresh_strong_package_batch_promotes_a_capped_deterministic_subset(
    source: str,
    metrics: dict[str, float],
    tmp_path: Path,
):
    result = _run(
        [
            MetricAdapter(
                source,
                [(f"strong-package-{index}", metrics) for index in range(5)],
            )
        ],
        tmp_path,
        minimum_score=75,
    )

    assert [candidate.title for candidate in result.hot_candidates] == [
        "AI strong-package-0",
        "AI strong-package-1",
        "AI strong-package-2",
    ]
    assert all(candidate.score >= 75 for candidate in result.hot_candidates)


def test_weak_or_old_pypi_package_batch_items_do_not_receive_discovery_promotion(
    tmp_path: Path,
):
    result = _run(
        [
            MetricAdapter(
                "pypi",
                [
                    ("weak-package", {"ai_keyword_strength": 0.65}),
                    ("old-strong-package", {"ai_keyword_strength": 1.0}),
                ],
                published_at=datetime(2026, 9, 22, 8, 0, tzinfo=timezone.utc),
            )
        ],
        tmp_path,
        minimum_score=75,
    )

    assert result.hot_candidates == []


def _hot_candidate() -> HotCandidate:
    return HotCandidate(
        hot_id="hot:event:agent-runtime",
        title="Agent Runtime",
        topic="agent-runtime",
        score=88,
        reasons=["Momentum 96", "Popularity 90"],
        evidence_urls=["https://example.com/agent-runtime"],
        source_families=["technology"],
        signals=["github:agent-runtime"],
        selected=True,
    )


def test_role_candidates_are_deduplicated_critiqued_and_debated_before_integration():
    proposals = generate_article_proposals(_hot_candidate(), max_proposals=5)

    assert len(proposals) == 5
    assert len({proposal.title_idea for proposal in proposals}) == len(proposals)
    assert {proposal.article_type for proposal in proposals} >= {
        "Technical Explainer",
        "Hands-on",
        "Comparison",
        "Critical Review",
        "Benchmark",
    }
    assert all("Critique score" in proposal.why_now for proposal in proposals)
    assert all("Debate:" in proposal.why_now for proposal in proposals)
    assert all(any("Critique:" in risk for risk in proposal.risks) for proposal in proposals)
    assert all(any("Debate:" in risk for risk in proposal.risks) for proposal in proposals)
