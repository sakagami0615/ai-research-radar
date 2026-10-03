from datetime import datetime, timezone

from ai_research_radar.normalization.identity import extract_identity
from ai_research_radar.normalization.dedup import deduplicate_quality_signals
from ai_research_radar.pipeline.events import build_quality_events
from ai_research_radar.schemas.models import CanonicalSignal


def _signal(name, title, url, source="arxiv", metadata=None, quality=None):
    return CanonicalSignal(name, source, "research" if source == "arxiv" else "technology", "paper", title, url, None, datetime(2026, 9, 29, tzinfo=timezone.utc), title, [], {}, {}, metadata or {}, 2, quality or {"priority": 50})


def test_same_title_different_identity_stays_separate():
    signals = [_signal("a", "Same", "https://doi.org/10.1/a"), _signal("b", "Same", "https://doi.org/10.1/b")]
    assert len(build_quality_events(signals)) == 2


def test_arxiv_versions_share_work_not_event():
    one = _signal("a", "Paper", "https://arxiv.org/abs/2309.12345v1", metadata={"version": "v1"})
    two = _signal("b", "Paper", "https://arxiv.org/abs/2309.12345v2", metadata={"version": "v2"})
    assert extract_identity(one)["work_id"] == extract_identity(two)["work_id"]
    assert len(build_quality_events([one, two])) == 2


def test_arxiv_different_papers_never_collide_on_trailing_digits():
    one = _signal("a", "Paper A", "https://arxiv.org/abs/2309.12345", metadata={"version": "v1"})
    two = _signal("b", "Paper B", "https://arxiv.org/abs/2309.67890", metadata={"version": "v1"})
    assert extract_identity(one)["work_id"] != extract_identity(two)["work_id"]


def test_same_package_url_different_versions_survive_dedup():
    one = _signal("a", "pkg", "https://pypi.org/project/pkg/", source="pypi", metadata={"version": "1.0"})
    two = _signal("b", "pkg", "https://pypi.org/project/pkg/", source="pypi", metadata={"version": "2.0"})
    assert len(deduplicate_quality_signals([one, two])) == 2


def test_dedup_merge_keeps_metrics_from_both_signals():
    one = _signal("a", "Paper", "https://doi.org/10.1/a", quality={"priority": 100, "metrics": [{"name": "stars"}]})
    two = _signal("b", "Paper", "https://doi.org/10.1/a", quality={"priority": 0, "metrics": [{"name": "downloads"}]})
    merged = deduplicate_quality_signals([one, two])
    assert len(merged) == 1
    names = {metric["name"] for metric in merged[0].quality["metrics"]}
    assert names == {"stars", "downloads"}


def test_scores_take_max_not_average_between_members():
    one = _signal("a", "Paper", "https://doi.org/10.1/a", quality={"priority": 100})
    two = _signal("b", "Paper", "https://doi.org/10.1/a", quality={"priority": 0})
    event = build_quality_events([one, two])[0]
    assert event.quality["priority"] == 100
    assert event.quality["representative_signal_id"] == "a"
