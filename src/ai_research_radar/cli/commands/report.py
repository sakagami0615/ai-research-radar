from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from datetime import datetime, timezone, tzinfo
from pathlib import Path

import yaml

from ai_research_radar.cli.commands.run_state import (
    add_error,
    load_run_state,
    reset_errors_for,
    save_run_state,
)
from ai_research_radar.config.settings import load_runtime_config, resolve_display_timezone
from ai_research_radar.reporting.digest import (
    ModelRelease,
    NotableItem,
    build_daily_digest,
    missing_summaries,
    save_digest_record,
)
from ai_research_radar.reporting.markdown import render_daily_report
from ai_research_radar.reporting.source_overview import SOURCE_OVERVIEWS_FILENAME, load_source_overviews
from ai_research_radar.schemas.decoders import decode_hot, decode_proposal
from ai_research_radar.schemas.models import RunMetadata
from ai_research_radar.storage.jsonl import read_jsonl, write_jsonl

COMMAND_NAME = "report"

_STAGE_ORDER = ["collect", "normalize", "score", "select-hot", "save-proposals"]


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(COMMAND_NAME)
    parser.add_argument("--date", required=True)
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--reports-dir", default="reports")
    parser.add_argument("--runtime-config", default="config/runtime.yaml")
    parser.add_argument(
        "--list-missing-summaries",
        action="store_true",
        help="print displayed notable items and model releases without a summary as JSON Lines, writing nothing",
    )


def run(args: argparse.Namespace) -> int:
    data_dir = Path(args.data_dir)
    date = args.date

    if args.list_missing_summaries:
        return _list_missing_summaries(data_dir, date)

    state = load_run_state(data_dir, date, fill_stage_results=False)
    reset_errors_for(state, ["pipeline", COMMAND_NAME])

    stages_completed = state.get("stages_completed", [])
    for stage in _STAGE_ORDER:
        if stage not in stages_completed:
            add_error(
                state,
                "pipeline",
                "missing_stage",
                f"{stage} was not completed before report",
            )

    hot_path = data_dir / "runs" / date / "hot_candidates.jsonl"
    hot_candidates = (
        [decode_hot(record) for record in read_jsonl(hot_path)] if hot_path.exists() else []
    )

    proposals_path = data_dir / "runs" / date / "article_proposals.jsonl"
    proposals = (
        [decode_proposal(record) for record in read_jsonl(proposals_path)]
        if proposals_path.exists()
        else []
    )

    signals_path = data_dir / "normalized" / date / "signals.jsonl"
    signals = read_jsonl(signals_path) if signals_path.exists() else []

    started_at = datetime.fromisoformat(state["run_id"])
    report_path = Path(args.reports_dir) / "daily" / f"{date}.md"

    run_without_report = RunMetadata(
        run_id=state["run_id"],
        started_at=started_at,
        finished_at=datetime.now(timezone.utc),
        mode="agent",
        since=state.get("since", date),
        until=state.get("until", date),
        sources=list(state.get("sources", [])),
        input_counts=dict(state.get("input_counts", {})),
        output_counts=dict(state.get("output_counts", {})),
        errors=list(state.get("errors", [])),
        report_paths=[],
        stage_results=dict(state["stage_results"]) if isinstance(state.get("stage_results"), dict) else {},
    )

    digest = build_daily_digest(data_dir, date)
    source_overviews, source_overview_warning = _load_source_overviews(data_dir, date)
    markdown = render_daily_report(
        date,
        hot_candidates,
        proposals,
        run_without_report,
        signals,
        digest,
        display_timezone=_display_timezone(Path(args.runtime_config)),
        source_overviews=source_overviews,
        source_overview_warning=source_overview_warning,
    )

    try:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(markdown, encoding="utf-8")
        save_digest_record(data_dir, date, digest)
    except OSError as exc:
        add_error(state, "report", "report_write_error", str(exc))
        save_run_state(data_dir, date, state)
        run_with_error = replace(run_without_report, errors=list(state["errors"]))
        write_jsonl(data_dir / "runs" / date / "run.jsonl", [run_with_error])
        return 1

    final_run = replace(run_without_report, report_paths=[str(report_path)])
    save_run_state(data_dir, date, state)
    write_jsonl(data_dir / "runs" / date / "run.jsonl", [final_run])
    print(report_path)
    return 0


def _load_source_overviews(data_dir: Path, date: str) -> tuple[dict[str, str], str | None]:
    """A broken source_overviews.json only hides the overviews (with a warning in the report)."""
    try:
        return load_source_overviews(data_dir, date), None
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        path = data_dir / "runs" / date / SOURCE_OVERVIEWS_FILENAME
        return {}, f"{path}: {exc}"


def _display_timezone(runtime_config: Path) -> tzinfo:
    """The timezone only affects how the period is displayed, so an unreadable
    runtime config falls back to UTC instead of blocking the report."""
    try:
        runtime = load_runtime_config(runtime_config)
    except (OSError, ValueError, yaml.YAMLError):
        return timezone.utc
    return resolve_display_timezone(runtime)


def _list_missing_summaries(data_dir: Path, date: str) -> int:
    digest = build_daily_digest(data_dir, date)
    for warning in digest.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    for item in missing_summaries(digest):
        print(json.dumps(_missing_summary_record(item), ensure_ascii=False))
    return 0


def _missing_summary_record(item: NotableItem | ModelRelease) -> dict[str, object]:
    if isinstance(item, ModelRelease):
        return {
            "kind": "model_release",
            "key": item.key,
            "title": item.title,
            "provider": item.provider,
            "channel": item.channel,
            "url": item.url,
            "first_seen": item.first_seen,
        }
    return {
        "kind": "notable",
        "hot_id": item.candidate.hot_id,
        "title": item.candidate.title,
        "first_seen": item.first_seen,
        "evidence_urls": list(item.candidate.evidence_urls),
    }
