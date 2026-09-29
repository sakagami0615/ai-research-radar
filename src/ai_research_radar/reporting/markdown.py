from __future__ import annotations

from collections import defaultdict
from typing import Any

from ai_research_radar.schemas.models import ArticleProposal, HotCandidate, RunMetadata


def render_daily_report(
    date: str,
    hot_candidates: list[HotCandidate],
    proposals: list[ArticleProposal],
    run: RunMetadata,
    signals: list[dict[str, Any]],
) -> str:
    selected_hot = [candidate for candidate in hot_candidates if candidate.selected]
    proposals_by_hot: dict[str, list[ArticleProposal]] = defaultdict(list)
    for proposal in proposals:
        proposals_by_hot[proposal.source_hot_id].append(proposal)

    lines = [f"# AI Daily Radar {date}", ""]
    lines.extend(_data_gaps_section(run))
    lines.extend(["## 選抜HOT", ""])
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
    lines.extend(_source_appendix_section(run, signals))
    return "\n".join(lines)


def _data_gaps_section(run: RunMetadata) -> list[str]:
    """Call out sources that produced zero items so a reader can't mistake an
    incomplete run (e.g. every request to a source failed) for a quiet day."""
    missing_sources = [source for source in run.sources if source not in run.input_counts]
    if not missing_sources:
        return []

    errors_by_source: dict[str, str] = {}
    for error in run.errors:
        source = error.get("source")
        if source in missing_sources and source not in errors_by_source:
            errors_by_source[source] = f"{error.get('type')} - {error.get('message')}"

    lines = [
        "## データ欠落",
        "",
        "以下のSourceは本runで収集に完全に失敗しており、"
        "これらのSourceにおける発表やHOT候補は本レポートに反映されていません。",
        "",
    ]
    for source in missing_sources:
        reason = errors_by_source.get(source, "reason unknown")
        lines.append(f"- {source}: {reason}")
    lines.append("")
    return lines


_SUMMARY_MAX_LENGTH = 120


def _sanitize_summary(summary: str) -> str:
    sanitized = summary.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
    sanitized = sanitized.replace("|", "\\|")
    if len(sanitized) > _SUMMARY_MAX_LENGTH:
        sanitized = sanitized[:_SUMMARY_MAX_LENGTH] + "…"
    if not sanitized:
        return "(概要なし)"
    return sanitized


def _sanitize_title(title: str) -> str:
    sanitized = title.replace("|", "\\|")
    return sanitized.replace("[", "\\[").replace("]", "\\]")


def _source_appendix_section(run: RunMetadata, signals: list[dict[str, Any]]) -> list[str]:
    lines = [
        "## 収集Source一覧",
        "",
        "本日収集し正規化・重複排除まで完了したSignal(Event/Topic集約より前の粒度)を"
        "Sourceごとに一覧化したものです。",
        "",
    ]
    if not run.sources:
        lines.append("本日は収集Signalがありません。")
        lines.append("")
        return lines

    by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for signal in signals:
        by_source[signal.get("source", "")].append(signal)

    for source in run.sources:
        items = by_source.get(source, [])
        lines.extend(_source_subsection(source, items))
    return lines


def _source_subsection(source: str, items: list[dict[str, Any]]) -> list[str]:
    lines = [
        f"### {source} ({len(items)}件)",
        "",
        "<details>",
        "<summary>一覧を表示</summary>",
        "",
    ]
    if not items:
        lines.append("該当Signalなし")
    else:
        lines.append("| タイトル | 概要 |")
        lines.append("| --- | --- |")
        for item in items:
            title = _sanitize_title(str(item.get("title", "")))
            url = str(item.get("url", ""))
            summary = _sanitize_summary(str(item.get("summary") or ""))
            lines.append(f"| [{title}](<{url}>) | {summary} |")
    lines.extend(["", "</details>", ""])
    return lines
