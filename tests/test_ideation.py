from ai_research_radar.ideation.proposals import generate_article_proposals
from ai_research_radar.schemas.models import HotCandidate


def test_generate_article_proposals_keeps_evidence_links():
    candidate = HotCandidate(
        hot_id="hot:github:repo",
        title="Agent Runtime is surging",
        topic="agent runtime",
        score=92,
        reasons=["Momentum 96"],
        evidence_urls=["https://github.com/owner/repo"],
        source_families=["technology"],
        signals=["github:repo"],
        selected=True,
    )

    proposals = generate_article_proposals(candidate, max_proposals=3)

    assert len(proposals) == 3
    assert all(proposal.evidence_links == ["https://github.com/owner/repo"] for proposal in proposals)
    assert {proposal.article_type for proposal in proposals} == {
        "Technical Explainer",
        "Hands-on",
        "Comparison",
    }


def test_generate_article_proposals_limits_count():
    candidate = HotCandidate(
        hot_id="hot:github:repo",
        title="Agent Runtime is surging",
        topic="agent runtime",
        score=92,
        reasons=["Momentum 96"],
        evidence_urls=["https://github.com/owner/repo"],
        source_families=["technology"],
        signals=["github:repo"],
        selected=True,
    )

    assert len(generate_article_proposals(candidate, max_proposals=2)) == 2


def test_generate_article_proposals_rejects_candidate_without_evidence():
    candidate = HotCandidate(
        hot_id="hot:unsupported",
        title="Unsupported trend",
        topic="unsupported",
        score=95,
        reasons=["Momentum 95"],
        evidence_urls=[],
        source_families=["technology"],
        signals=["github:unsupported"],
        selected=True,
    )

    assert generate_article_proposals(candidate) == []


def test_generate_article_proposals_records_deterministic_lightweight_critique():
    candidate = HotCandidate(
        hot_id="hot:github:repo",
        title="Agent Runtime is surging",
        topic="agent runtime",
        score=92,
        reasons=["Momentum 96"],
        evidence_urls=["https://github.com/owner/repo"],
        source_families=["technology"],
        signals=["github:repo"],
        selected=True,
    )

    proposals = generate_article_proposals(candidate, max_proposals=1)

    assert "軽量Critique" in proposals[0].why_now
    assert any("軽量Critique" in risk for risk in proposals[0].risks)
