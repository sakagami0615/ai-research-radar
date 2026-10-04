from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
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
        lines.extend(_article_proposals_section(proposals_by_hot.get(candidate.hot_id, [])))

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
    sanitized = summary.replace("\\", "\\\\")
    sanitized = sanitized.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
    sanitized = sanitized.replace("<", "&lt;").replace(">", "&gt;")
    sanitized = sanitized.replace("|", "\\|")
    if len(sanitized) > _SUMMARY_MAX_LENGTH:
        sanitized = sanitized[:_SUMMARY_MAX_LENGTH] + "…"
    if not sanitized:
        return "(概要なし)"
    return sanitized


def _sanitize_title(title: str) -> str:
    sanitized = title.replace("\\", "\\\\")
    sanitized = sanitized.replace("<", "&lt;").replace(">", "&gt;")
    sanitized = sanitized.replace("|", "\\|")
    return sanitized.replace("[", "\\[").replace("]", "\\]")


def _sanitize_url(url: str) -> str:
    """Percent-encode angle brackets so a raw '>' cannot terminate the
    surrounding <...> link-destination syntax early. HTML-entity escaping
    (&lt;/&gt;) is deliberately not used here because the URL is a link
    destination, not visible text, and entities would render literally in
    some viewers instead of being resolved as part of the URL."""
    return url.replace("<", "%3C").replace(">", "%3E")


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

    known_sources = set(run.sources)
    other_key = "other"
    while other_key in known_sources:
        other_key = f"_{other_key}"

    by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for signal in signals:
        source = signal.get("source", "")
        key = source if source in known_sources else other_key
        by_source[key].append(signal)

    ordered_sources = list(run.sources)
    if other_key in by_source:
        ordered_sources.append(other_key)

    for source in ordered_sources:
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
            url = _sanitize_url(str(item.get("url", "")))
            summary = _sanitize_summary(str(item.get("summary") or ""))
            lines.append(f"| [{title}](<{url}>) | {summary} |")
    lines.extend(["", "</details>", ""])
    return lines


_DETERMINISTIC_WHY_NOW = re.compile(
    r"HOT score (?P<score>\S+) with reasons: (?P<reasons>.*?)\. "
    r"Role: (?P<role>.+?)\. "
    r"軽量Critique score: (?P<critique_score>[0-9.]+)/100; (?P<notes>.*)\. "
    r"Debate: (?P<debate>.*)",
    re.DOTALL,
)


@dataclass(frozen=True)
class _IdeationTrace:
    role: str
    critique_score: str
    critique_notes: list[str]
    debate: str


def _parse_why_now(why_now: str) -> _IdeationTrace | None:
    """Split the why_now text produced by ideation/proposals.py into its
    labeled parts. Free-text why_now (e.g. written by the agent) does not
    match and is shown as-is instead."""
    match = _DETERMINISTIC_WHY_NOW.fullmatch(why_now)
    if match is None:
        return None
    return _IdeationTrace(
        role=match["role"],
        critique_score=match["critique_score"],
        critique_notes=match["notes"].split(" ; "),
        debate=match["debate"],
    )


def _article_proposals_section(proposals: list[ArticleProposal]) -> list[str]:
    if not proposals:
        return ["記事企画なし", ""]

    traces = [_parse_why_now(proposal.why_now) for proposal in proposals]
    lines = ["| # | 企画タイトル | Type | Role | Critique |", "| --- | --- | --- | --- | --- |"]
    for index, (proposal, trace) in enumerate(zip(proposals, traces), start=1):
        role = _cell(trace.role) if trace else "-"
        critique = f"{trace.critique_score}/100" if trace else "-"
        lines.append(
            f"| {index} | {_cell(proposal.title_idea)} | {_cell(proposal.article_type)} | {role} | {critique} |"
        )
    lines.append("")

    for index, (proposal, trace) in enumerate(zip(proposals, traces), start=1):
        lines.extend([f"##### {index}. {_heading(proposal.title_idea)}", ""])
        lines.extend(["| 項目 | 内容 |", "| --- | --- |"])
        rows = [("Type", _cell(proposal.article_type)), ("Target Reader", _cell(proposal.target_reader))]
        risks_value = _bullets(proposal.risks)
        if trace:
            rows.extend(
                [
                    ("Role", _cell(trace.role)),
                    ("Critique Score", f"{trace.critique_score}/100"),
                    ("Critique Notes", _bullets(trace.critique_notes)),
                    ("Debate", "<br>".join(_cell(part) for part in trace.debate.split("; "))),
                ]
            )
            duplicated = {f"軽量Critique: {note}" for note in trace.critique_notes} | {f"Debate: {trace.debate}"}
            risks = [risk for risk in proposal.risks if risk not in duplicated]
            if proposal.risks and not risks:
                risks_value = "Critique Notes / Debateと同じ内容"
            else:
                risks_value = _bullets(risks)
        else:
            rows.append(("Why Now", _cell(proposal.why_now)))
        rows.extend(
            [
                ("Technical Angle", _cell(proposal.technical_angle)),
                ("Experiment Plan", _numbered(proposal.experiment_plan)),
                ("Unique Angle", _cell(proposal.unique_angle)),
                ("Competition", _cell(proposal.competition)),
                ("Traffic Opportunity", _cell(proposal.traffic_opportunity)),
                ("Technical Opportunity", _cell(proposal.technical_opportunity)),
                ("Risks", risks_value),
                ("Evidence", "<br>".join(_evidence_link(url) for url in proposal.evidence_links) or "-"),
            ]
        )
        lines.extend(f"| {label} | {value} |" for label, value in rows)
        lines.append("")
    return lines


def _escape_text(text: str) -> str:
    escaped = text.replace("\\", "\\\\")
    return escaped.replace("<", "&lt;").replace(">", "&gt;")


def _cell(text: str) -> str:
    """Escape a value for a single table cell. Newlines become <br> after
    escaping so they cannot terminate the table row."""
    escaped = _escape_text(str(text)).replace("|", "\\|")
    escaped = escaped.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br>")
    return escaped or "-"


def _heading(text: str) -> str:
    escaped = _escape_text(str(text))
    return escaped.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")


def _bullets(items: list[str]) -> str:
    return "<br>".join(f"・{_cell(item)}" for item in items) or "-"


def _numbered(items: list[str]) -> str:
    return "<br>".join(f"{index}. {_cell(item)}" for index, item in enumerate(items, start=1)) or "-"


def _evidence_link(url: str) -> str:
    text = _cell(url).replace("[", "\\[").replace("]", "\\]")
    destination = _sanitize_url(url).replace("|", "%7C")
    return f"[{text}](<{destination}>)"
