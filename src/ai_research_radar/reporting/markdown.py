from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone, tzinfo
from typing import Any

from ai_research_radar.reporting.digest import (
    LOOKBACK_DAYS,
    DailyDigest,
    group_model_releases,
)
from ai_research_radar.schemas.models import (
    NOT_RUN_REASON,
    ArticleProposal,
    HotCandidate,
    RunMetadata,
    valid_stage_result,
)


def render_daily_report(
    date: str,
    hot_candidates: list[HotCandidate],
    proposals: list[ArticleProposal],
    run: RunMetadata,
    signals: list[dict[str, Any]],
    digest: DailyDigest | None = None,
    display_timezone: tzinfo | None = None,
) -> str:
    digest = digest or DailyDigest()
    selected_hot = [candidate for candidate in hot_candidates if candidate.selected]
    proposals_by_hot: dict[str, list[ArticleProposal]] = defaultdict(list)
    for proposal in proposals:
        proposals_by_hot[proposal.source_hot_id].append(proposal)

    lines = [f"# AI Daily Radar {date}", ""]
    lines.extend(_data_gaps_section(run))
    lines.extend(["## 選抜HOT", ""])
    lines.extend(_selection_status(_stage_result(run, "select-hot"), bool(selected_hot)))
    proposal_result = _stage_result(run, "save-proposals")
    if selected_hot:
        shown = any(proposals_by_hot.get(candidate.hot_id) for candidate in selected_hot)
        lines.extend(_proposal_status(proposal_result, shown))
    deferral_reason = _deferral_reason(proposal_result)
    for candidate in selected_hot:
        lines.extend(
            [
                f"### {candidate.title}",
                "",
                _summary_quote(candidate.summary),
                "",
                f"- HOT Score: {candidate.score}",
                f"- Topic: {candidate.topic}",
                f"- Source Families: {', '.join(candidate.source_families)}",
                f"- Evidence: {', '.join(candidate.evidence_urls)}",
                "- Reasons:",
            ]
        )
        lines.extend([f"  - {reason}" for reason in candidate.reasons])
        lines.extend(_assessment_section(candidate.assessment))
        lines.extend(["", "#### Article Proposals", ""])
        lines.extend(_article_proposals_section(proposals_by_hot.get(candidate.hot_id, []), deferral_reason))

    lines.extend(_digest_warnings(digest))
    lines.extend(_notable_section(digest))
    lines.extend(_model_release_section(digest))
    lines.extend(_run_summary_section(run, display_timezone or timezone.utc))
    lines.extend(["## Errors", ""])
    if not run.errors:
        lines.append("なし")
    else:
        for error in run.errors:
            lines.append(f"- {error.get('source')}: {error.get('type')} - {error.get('message')}")
    lines.append("")
    lines.extend(_source_appendix_section(run, signals))
    return "\n".join(lines)


def _stage_result(run: RunMetadata, stage: str) -> dict[str, Any] | None:
    results = run.stage_results if isinstance(run.stage_results, dict) else {}
    return valid_stage_result(results.get(stage))


def _stage_reason(result: dict[str, Any]) -> str:
    reason = result.get("reason")
    return reason if isinstance(reason, str) else ""


def _stage_count(result: dict[str, Any], key: str) -> str:
    value = result.get(key)
    return str(value) if isinstance(value, int) and not isinstance(value, bool) else "?"


def _with_reason(text: str, reason: str) -> str:
    """Return "<text>(<reason>)。", omitting the parentheses for the default "未実行" reason."""
    if not reason or reason == NOT_RUN_REASON:
        return f"{text}。"
    return f"{text}({_inline_text(reason)})。"


def _selection_status(result: dict[str, Any] | None, has_selected: bool) -> list[str]:
    """Status line shown under 選抜HOT so a deferred day reads differently from a skipped or failed one."""
    if result is None:
        return [] if has_selected else ["本日の選抜HOTはありません。", ""]
    status = result["status"]
    if status == "completed":
        return [] if has_selected else ["選抜結果が見つかりません(score の再実行などで選抜が消えた可能性があります)。", ""]
    if status == "deferred":
        # The reason is followed by "。", so a trailing one written by the agent is dropped.
        reason = _inline_text(_stage_reason(result)).rstrip("。") or "理由未記載"
        if _stage_count(result, "candidate_count") == "0":
            scope = "候補0件"
        else:
            scope = (
                f"候補 {_stage_count(result, 'candidate_count')}件中 {_stage_count(result, 'screened_count')}件を確認、"
                f"未確認 {_stage_count(result, 'unreviewed_count')}件"
            )
        return [f"本日の選抜HOTはありません(保留: {reason}。{scope})。", ""]
    line = _with_reason("選抜は未実行" if status == "not_run" else "選抜は失敗", _stage_reason(result))
    if has_selected:
        line += "以下は前回成功時の結果です。"
    return [line, ""]


def _proposal_status(result: dict[str, Any] | None, has_proposals: bool) -> list[str]:
    """Shown once under 選抜HOT when proposals were not saved for the current selection."""
    if result is None or result["status"] in {"completed", "deferred"}:
        return []
    if result["status"] == "not_run":
        line = _with_reason("記事企画は未実行", _stage_reason(result))
    else:
        line = _with_reason("記事企画の保存は失敗", _stage_reason(result))
    if has_proposals:
        line += "表示中の企画は前回の結果です。"
    return [line, ""]


def _deferral_reason(result: dict[str, Any] | None) -> str | None:
    """Reason shown in the proposal block of a HOT without proposals, only on a deferred day."""
    if result is None or result["status"] != "deferred":
        return None
    # The reason sits inside "(保留: ...)", so a trailing "。" written by the agent is dropped.
    return _inline_text(_stage_reason(result)).rstrip("。") or "理由未記載"


def _run_summary_section(run: RunMetadata, display_timezone: tzinfo) -> list[str]:
    rows = [
        ("Run ID", run.run_id),
        ("Period", _format_period(run.since, run.until, display_timezone)),
        ("Sources", ", ".join(run.sources)),
        ("Input Counts", _format_counts(run.input_counts)),
        ("Output Counts", _format_counts(run.output_counts)),
    ]
    lines = ["## Run Summary", "", "| 項目 | 内容 |", "| --- | --- |"]
    lines.extend(f"| {label} | {_cell(value)} |" for label, value in rows)
    lines.append("")
    return lines


def _format_counts(counts: dict[str, int]) -> str:
    return ", ".join(f"{key}: {value}" for key, value in counts.items())


def _format_period(since: str, until: str, display_timezone: tzinfo) -> str:
    start = _to_display_time(since, display_timezone)
    end = _to_display_time(until, display_timezone)
    period = f"{_display_or_raw(start, since)} 〜 {_display_or_raw(end, until)}"
    if start is None or end is None:
        return period
    return f"{period} ({end.strftime('%Z')})"


def _to_display_time(value: str, display_timezone: tzinfo) -> datetime | None:
    """Convert an ISO datetime to the display timezone. Date-only,
    unparseable or out-of-range values return None so they are shown verbatim."""
    if "T" not in value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(display_timezone)
    except (ValueError, OverflowError):
        return None


def _display_or_raw(value: datetime | None, raw: str) -> str:
    return value.strftime("%Y-%m-%d %H:%M") if value is not None else raw


_CHANNEL_LABELS = {"official": "公式発表", "huggingface": "Hugging Face", "ollama": "Ollama"}


def _digest_warnings(digest: DailyDigest) -> list[str]:
    if not digest.warnings:
        return []
    lines = ["> ⚠️ 次のファイルを読めなかったため、注目候補・新モデルリリースの集約から除外しました。", ">"]
    lines.extend(f"> - {_sanitize_summary(warning)}" for warning in digest.warnings)
    lines.append("")
    return lines


def _notable_section(digest: DailyDigest) -> list[str]:
    lines = [
        "## 注目候補(選抜外)",
        "",
        f"直近{LOOKBACK_DAYS}日分のHOT候補のうち、スコアは閾値以上だが選抜されなかったもの(過去のレポートに掲載済みのものを除く)。",
        "",
    ]
    if not digest.notable:
        lines.extend(["該当なし", ""])
        return lines
    for item in digest.notable:
        candidate = item.candidate
        title = _sanitize_title(candidate.title)
        if candidate.evidence_urls:
            lines.append(f"### [{title}](<{_sanitize_url(candidate.evidence_urls[0])}>)")
        else:
            lines.append(f"### {title}")
        lines.extend(
            [
                "",
                _summary_quote(item.summary),
                "",
                f"- HOT Score: {candidate.score}",
                f"- Source: {', '.join(item.sources) or '不明'}",
                f"- 初出日: {item.first_seen}",
                f"- Reasons: {', '.join(candidate.reasons)}",
                "",
            ]
        )
    if digest.notable_overflow:
        lines.extend([f"ほか{digest.notable_overflow}件(表示上限超過)", ""])
    return lines


def _model_release_section(digest: DailyDigest) -> list[str]:
    lines = [
        "## 新モデルリリース",
        "",
        f"直近{LOOKBACK_DAYS}日分に公式ブログ・Hugging Face・Ollamaブログで検知した新モデル(過去のレポートに掲載済みのものを除く)。",
        "",
    ]
    groups = group_model_releases(digest.model_releases)
    if not groups:
        lines.extend(["該当なし", ""])
        return lines
    for provider, releases, overflow in groups:
        lines.extend([f"### {_sanitize_title(provider)}", ""])
        for release in releases:
            title = _sanitize_title(release.title)
            name = f"[{title}](<{_sanitize_url(release.url)}>)" if release.url else title
            channel = _CHANNEL_LABELS.get(release.channel, release.channel or "不明")
            published = (release.published_at or "")[:10] or "不明"
            models = f" — 紹介モデル: {', '.join(_sanitize_title(model) for model in release.models)}" if release.models else ""
            lines.append(f"- {name} ({channel} / 公開日 {published}){models}")
        if overflow:
            lines.append(f"- ほか{overflow}件(表示上限超過)")
        lines.append("")
    return lines


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


def _summary_quote(summary: str) -> str:
    # The "**概要**:" prefix keeps the text off the line start, so it cannot become a heading or list.
    text = " ".join(_sanitize_title(summary).split())
    return f"> **概要**: {text or '概要未作成'}"


def _sanitize_title(title: str) -> str:
    sanitized = title.replace("\\", "\\\\")
    sanitized = sanitized.replace("<", "&lt;").replace(">", "&gt;")
    sanitized = sanitized.replace("|", "\\|")
    return sanitized.replace("[", "\\[").replace("]", "\\]")


def _sanitize_url(url: str) -> str:
    """Percent-encode angle brackets so a raw '>' cannot terminate the
    surrounding <...> link-destination syntax early, and backslash, '|' and
    newlines so they cannot escape the bracket or break the table row.
    HTML-entity escaping (&lt;/&gt;) is deliberately not used here because the URL is a link
    destination, not visible text, and entities would render literally in
    some viewers instead of being resolved as part of the URL."""
    encoded = url.replace("\\", "%5C").replace("<", "%3C").replace(">", "%3E").replace("|", "%7C")
    return encoded.replace("\r", "%0D").replace("\n", "%0A")


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


def _article_proposals_section(proposals: list[ArticleProposal], deferral_reason: str | None = None) -> list[str]:
    if not proposals:
        if deferral_reason is not None:
            return [f"記事企画なし(保留: {deferral_reason})", ""]
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
                    ("Debate", "<br>".join(_cell(part) for part in trace.debate.split("; ", 2))),
                ]
            )
            duplicated = {f"軽量Critique: {note}" for note in trace.critique_notes} | {f"Debate: {trace.debate}"}
            risks = [risk for risk in _as_list(proposal.risks) if risk not in duplicated]
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
                ("Evidence", "<br>".join(_evidence_link(url) for url in _as_list(proposal.evidence_links)) or "-"),
            ]
        )
        lines.extend(f"| {label} | {value} |" for label, value in rows)
        lines.append("")
    return lines


_ORDERED_MARKER = re.compile(r"^(\d+)([.)])(?=\s)")
# Any leading character that can open a block (heading, list, thematic break, code fence,
# setext underline) is escaped; a backslash before ASCII punctuation always renders as-is.
_BLOCK_MARKER = re.compile(r"^([#=+*_`~-])")


def _inline_text(value: object) -> str:
    """Escape agent-written text for one line of a Markdown list item.

    Non-strings (hand-edited records) become empty, newlines collapse to spaces,
    and a leading block marker is escaped so it stays plain text.
    """
    text = value if isinstance(value, str) else ""
    escaped = " ".join(_escape_text(text).replace("|", "\\|").split())
    escaped = _ORDERED_MARKER.sub(r"\1\\\2", escaped, count=1)
    return _BLOCK_MARKER.sub(r"\\\1", escaped, count=1)


def _list_of(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _evidence_check_line(check: dict[str, Any]) -> str:
    """One EvidenceCheck as "URL(status / kind):claim" (shared with #11's proposal evidence)."""
    url = check.get("url")
    link = _evidence_link(url) if isinstance(url, str) and url else "(URL未記載)"
    claim = _inline_text(check.get("claim")) or "(主張未記載)"
    return f"{link}({_inline_text(check.get('status'))} / {_inline_text(check.get('kind'))}):{claim}"


def _assessment_section(assessment: object) -> list[str]:
    """Agent assessment of a selected HOT, except assessor and assessed_at."""
    if not isinstance(assessment, dict):
        return []
    lines = [f"- 判断理由: {_inline_text(assessment.get('reason')) or '(未記載)'}"]
    relevance = assessment.get("relevance")
    if isinstance(relevance, dict):
        terms = ", ".join(term for term in (_inline_text(item) for item in _list_of(relevance.get("matched_terms"))) if term)
        lines.append(
            f"- 関連性: {_inline_text(relevance.get('status'))}"
            f"(方法: {_inline_text(relevance.get('method'))} / 一致語: {terms or 'なし'})"
        )
        relevance_reason = _inline_text(relevance.get("reason"))
        if relevance_reason:
            lines.append(f"  - {relevance_reason}")
    else:
        lines.append("- 関連性: 記録なし")
    lines.extend(
        [
            f"- 新規性: {_inline_text(assessment.get('novelty')) or '(未記載)'}",
            f"- 重要性: {_inline_text(assessment.get('importance')) or '(未記載)'}",
            f"- 読者への影響: {_inline_text(assessment.get('reader_impact')) or '(未記載)'}",
        ]
    )
    evidence = [item for item in _list_of(assessment.get("evidence")) if isinstance(item, dict)]
    if evidence:
        lines.append("- 根拠:")
        lines.extend(f"  - {_evidence_check_line(item)}" for item in evidence)
    else:
        lines.append("- 根拠: なし")
    unknowns = [text for text in (_inline_text(item) for item in _list_of(assessment.get("unknowns"))) if text]
    if unknowns:
        lines.append("- 未確認事項:")
        lines.extend(f"  - {text}" for text in unknowns)
    else:
        lines.append("- 未確認事項: なし")
    return lines


def _escape_text(text: str) -> str:
    escaped = text.replace("\\", "\\\\")
    escaped = escaped.replace("[", "\\[").replace("]", "\\]")
    return escaped.replace("<", "&lt;").replace(">", "&gt;")


def _cell(text: str) -> str:
    """Escape a value for a single table cell. Newlines become <br> after
    escaping so they cannot terminate the table row."""
    escaped = _escape_text(str(text)).replace("|", "\\|")
    escaped = escaped.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br>")
    return escaped or "-"


def _heading(text: str) -> str:
    escaped = _escape_text(str(text))
    escaped = escaped.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
    if escaped.endswith("#"):
        # A trailing "#" would be consumed as the ATX heading's closing sequence.
        escaped = escaped[:-1] + "\\#"
    return escaped


def _as_list(items: list[str] | str) -> list[str]:
    """save-proposals does not type-check list fields, so an agent may pass a
    plain string; treat it as one item instead of iterating characters."""
    return [items] if isinstance(items, str) else list(items)


def _bullets(items: list[str] | str) -> str:
    items = _as_list(items)
    return "<br>".join(f"・{_cell(item)}" for item in items) or "-"


def _numbered(items: list[str] | str) -> str:
    items = _as_list(items)
    return "<br>".join(f"{index}. {_cell(item)}" for index, item in enumerate(items, start=1)) or "-"


def _evidence_link(url: str) -> str:
    text = _cell(url)
    return f"[{text}](<{_sanitize_url(url)}>)"
