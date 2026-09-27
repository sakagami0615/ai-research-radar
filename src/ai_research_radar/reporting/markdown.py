from __future__ import annotations

from collections import defaultdict

from ai_research_radar.schemas.models import ArticleProposal, HotCandidate, RunMetadata


def render_daily_report(
    date: str,
    hot_candidates: list[HotCandidate],
    proposals: list[ArticleProposal],
    run: RunMetadata,
) -> str:
    selected_hot = [candidate for candidate in hot_candidates if candidate.selected]
    proposals_by_hot: dict[str, list[ArticleProposal]] = defaultdict(list)
    for proposal in proposals:
        proposals_by_hot[proposal.source_hot_id].append(proposal)

    lines = [
        f"# AI Daily Radar {date}",
        "",
        "## 選抜HOT",
        "",
    ]
    if not selected_hot:
        lines.extend(["本日の選抜HOTはありません。", ""])
    for candidate in selected_hot:
        lines.extend(
            [
                f"### {candidate.title}",
                "",
                f"- HOT Score: {candidate.score}",
                f"- Topic: {candidate.topic}",
                f"- Source Families: {', '.join(candidate.source_families)}",
                f"- Evidence: {', '.join(candidate.evidence_urls)}",
                "- Reasons:",
            ]
        )
        lines.extend([f"  - {reason}" for reason in candidate.reasons])
        lines.extend(["", "#### Article Proposals", ""])
        for proposal in proposals_by_hot.get(candidate.hot_id, []):
            lines.extend(
                [
                    f"- {proposal.title_idea}",
                    f"  - Type: {proposal.article_type}",
                    f"  - Why Now: {proposal.why_now}",
                    f"  - Evidence: {', '.join(proposal.evidence_links)}",
                ]
            )
        lines.append("")

    lines.extend(["## Run Summary", ""])
    lines.append(f"- Run ID: {run.run_id}")
    lines.append(f"- Period: {run.since} to {run.until}")
    lines.append(f"- Sources: {', '.join(run.sources)}")
    lines.append(f"- Input Counts: {run.input_counts}")
    lines.append(f"- Output Counts: {run.output_counts}")
    lines.extend(["", "## Errors", ""])
    if not run.errors:
        lines.append("なし")
    else:
        for error in run.errors:
            lines.append(f"- {error.get('source')}: {error.get('type')} - {error.get('message')}")
    lines.append("")
    return "\n".join(lines)
