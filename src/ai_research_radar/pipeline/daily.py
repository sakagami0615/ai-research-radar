from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ai_research_radar.ideation.proposals import generate_article_proposals
from ai_research_radar.normalization.dedup import deduplicate_signals
from ai_research_radar.normalization.scores import normalize_source_batch
from ai_research_radar.pipeline.events import build_events, cluster_topics
from ai_research_radar.reporting.markdown import render_daily_report
from ai_research_radar.schemas.models import (
    ArticleProposal,
    CanonicalSignal,
    Event,
    HotCandidate,
    RawItem,
    RunMetadata,
    Topic,
)
from ai_research_radar.scoring.hot import build_hot_candidates_from_events
from ai_research_radar.sources.base import SourceAdapter, SourceError
from ai_research_radar.storage.jsonl import write_jsonl


@dataclass(frozen=True)
class DailyPipelineResult:
    run: RunMetadata
    raw_items: list[RawItem]
    signals: list[CanonicalSignal]
    events: list[Event]
    topics: list[Topic]
    hot_candidates: list[HotCandidate]
    proposals: list[ArticleProposal]
    report_path: Path


def run_daily(
    adapters: list[SourceAdapter],
    since: str,
    until: str,
    output_dir: Path,
    report_dir: Path,
    hot_limit: int = 5,
    minimum_score: float = 75.0,
    hot_score_weights: dict[str, float] | None = None,
) -> DailyPipelineResult:
    started_at = datetime.now(timezone.utc)
    date = until
    raw_items: list[RawItem] = []
    signals: list[CanonicalSignal] = []
    errors: list[dict[str, str]] = []
    input_counts: dict[str, int] = {}

    for adapter in adapters:
        try:
            collected = adapter.collect(since=since, until=until)
        except SourceError as exc:
            errors.append({"source": exc.source, "type": exc.error_type, "message": str(exc)})
            continue
        except Exception as exc:
            errors.append(
                {
                    "source": adapter.source_name,
                    "type": "unexpected_error",
                    "message": str(exc),
                }
            )
            continue

        input_counts[adapter.source_name] = len(collected)
        raw_items.extend(collected)
        try:
            write_jsonl(output_dir / "raw" / date / f"{adapter.source_name}.jsonl", collected)
        except Exception as exc:
            errors.append(
                {
                    "source": adapter.source_name,
                    "type": "raw_write_error",
                    "message": str(exc),
                }
            )
        try:
            normalized_items = [adapter.normalize(item) for item in collected]
        except SourceError as exc:
            errors.append({"source": exc.source, "type": exc.error_type, "message": str(exc)})
            continue
        except Exception as exc:
            errors.append(
                {
                    "source": adapter.source_name,
                    "type": "unexpected_error",
                    "message": str(exc),
                }
            )
            continue
        signals.extend(normalized_items)

    deduped_signals: list[CanonicalSignal] = []
    events: list[Event] = []
    topics: list[Topic] = []
    hot_candidates: list[HotCandidate] = []
    selected_hot: list[HotCandidate] = []
    proposals: list[ArticleProposal] = []
    report_path = report_dir / "daily" / f"{date}.md"
    try:
        signals = normalize_source_batch(signals)
        deduped_signals = deduplicate_signals(signals)
        events = build_events(deduped_signals)
        topics = cluster_topics(events)
        hot_candidates = build_hot_candidates_from_events(
            events,
            limit=hot_limit,
            minimum_score=minimum_score,
            weights=hot_score_weights,
        )
        selected_hot = [candidate for candidate in hot_candidates if candidate.selected]
        for candidate in selected_hot:
            proposals.extend(generate_article_proposals(candidate, max_proposals=3))
        write_jsonl(output_dir / "normalized" / date / "signals.jsonl", deduped_signals)
        write_jsonl(output_dir / "events" / date / "events.jsonl", events)
        write_jsonl(output_dir / "topics" / date / "topics.jsonl", topics)
        write_jsonl(output_dir / "runs" / date / "hot_candidates.jsonl", hot_candidates)
        write_jsonl(output_dir / "runs" / date / "article_proposals.jsonl", proposals)
    except Exception as exc:
        errors.append({"source": "pipeline", "type": "pipeline_error", "message": str(exc)})
        failed_run = _run_metadata(
            started_at, since, until, adapters, input_counts, raw_items, deduped_signals,
            events, topics, hot_candidates, selected_hot, proposals, errors, [],
        )
        _persist_run_metadata(output_dir, date, failed_run)
        raise

    run = _run_metadata(
        started_at, since, until, adapters, input_counts, raw_items, deduped_signals,
        events, topics, hot_candidates, selected_hot, proposals, errors, [],
    )
    try:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            render_daily_report(date, hot_candidates, proposals, run), encoding="utf-8"
        )
    except Exception as exc:
        errors.append({"source": "report", "type": "report_write_error", "message": str(exc)})
        failed_run = _run_metadata(
            started_at, since, until, adapters, input_counts, raw_items, deduped_signals,
            events, topics, hot_candidates, selected_hot, proposals, errors, [],
        )
        _persist_run_metadata(output_dir, date, failed_run)
        raise

    final_run = _run_metadata(
        started_at, since, until, adapters, input_counts, raw_items, deduped_signals,
        events, topics, hot_candidates, selected_hot, proposals, errors, [str(report_path)],
    )
    _persist_run_metadata(output_dir, date, final_run)
    return DailyPipelineResult(
        run=final_run,
        raw_items=raw_items,
        signals=deduped_signals,
        events=events,
        topics=topics,
        hot_candidates=hot_candidates,
        proposals=proposals,
        report_path=report_path,
    )


def _run_metadata(
    started_at: datetime,
    since: str,
    until: str,
    adapters: list[SourceAdapter],
    input_counts: dict[str, int],
    raw_items: list[RawItem],
    signals: list[CanonicalSignal],
    events: list[Event],
    topics: list[Topic],
    hot_candidates: list[HotCandidate],
    selected_hot: list[HotCandidate],
    proposals: list[ArticleProposal],
    errors: list[dict[str, str]],
    report_paths: list[str],
) -> RunMetadata:
    return RunMetadata(
        run_id=started_at.isoformat(),
        started_at=started_at,
        finished_at=datetime.now(timezone.utc),
        mode="daily",
        since=since,
        until=until,
        sources=[adapter.source_name for adapter in adapters],
        input_counts=input_counts,
        output_counts={
            "raw_items": len(raw_items),
            "signals": len(signals),
            "events": len(events),
            "topics": len(topics),
            "hot_candidates": len(hot_candidates),
            "selected_hot": len(selected_hot),
            "article_proposals": len(proposals),
        },
        errors=list(errors),
        report_paths=report_paths,
    )


def _persist_run_metadata(output_dir: Path, date: str, run: RunMetadata) -> None:
    try:
        write_jsonl(output_dir / "runs" / date / "run.jsonl", [run])
    except Exception:
        pass
