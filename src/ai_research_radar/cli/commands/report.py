from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import TypeVar

from ai_research_radar.cli.commands.common import (
    add_runtime_arguments,
    data_dir as resolve_data_dir,
    reports_dir as resolve_reports_dir,
    runtime_config,
)
from ai_research_radar.config.settings import resolve_display_timezone
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
from ai_research_radar.storage.files import atomic_write_text
from ai_research_radar.storage.jsonl import JsonlReadError, read_decoded_jsonl, read_jsonl, write_jsonl
from ai_research_radar.storage.run_state import add_error, load_run_state, reset_errors_for, save_run_state

COMMAND_NAME = "report"

T = TypeVar("T")

_STAGE_ORDER = ["collect", "normalize", "score", "select-hot", "save-proposals"]


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(COMMAND_NAME)
    parser.add_argument("--date", required=True)
    add_runtime_arguments(parser, reports_dir=True)
    parser.add_argument(
        "--list-missing-summaries",
        action="store_true",
        help="print displayed notable items and model releases without a summary as JSON Lines, writing nothing",
    )
    parser.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    data_dir = resolve_data_dir(args)
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

    # A broken file of the day is shown as missing data (noted in its section and
    # recorded in errors) instead of stopping the report.
    unreadable: set[str] = set()

    def read_or_empty(path: Path, read: Callable[[Path], list[T]]) -> list[T]:
        if not path.exists():
            return []
        try:
            return read(path)
        except JsonlReadError as exc:
            add_error(state, COMMAND_NAME, "corrupt_input", str(exc))
            unreadable.add(path.name)
            return []

    run_dir = data_dir / "runs" / date
    hot_candidates = read_or_empty(run_dir / "hot_candidates.jsonl", lambda path: read_decoded_jsonl(path, decode_hot))
    proposals = read_or_empty(run_dir / "article_proposals.jsonl", lambda path: read_decoded_jsonl(path, decode_proposal))
    # Displayed through dict.get(), so only UTF-8 / JSON / object errors count, not missing keys.
    signals = read_or_empty(data_dir / "normalized" / date / "signals.jsonl", read_jsonl)

    started_at = datetime.fromisoformat(state["run_id"])
    report_path = resolve_reports_dir(args) / "daily" / f"{date}.md"

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
        display_timezone=resolve_display_timezone(runtime_config(args)),
        unreadable_files=unreadable,
        source_overviews=source_overviews,
        source_overview_warning=source_overview_warning,
        review_feedback_path=_review_feedback_path(state, data_dir, date),
    )

    try:
        atomic_write_text(report_path, markdown)
        save_digest_record(data_dir, date, digest)
    except (OSError, ValueError) as exc:
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


def _review_feedback_path(state: dict, data_dir: Path, date: str) -> str | None:
    """Path shown in the warning banner when `mark-needs-review` recorded needs_review."""
    if state.get("needs_review") is not True:
        return None
    return str(data_dir / "runs" / date / "review_feedback.md")


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
