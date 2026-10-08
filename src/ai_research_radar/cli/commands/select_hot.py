from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from ai_research_radar.cli.commands.run_state import (
    add_error,
    invalidate_proposals_result,
    load_run_state,
    mark_stage_completed,
    reset_errors_for,
    save_run_state,
    set_stage_result,
)
from ai_research_radar.schemas.decoders import decode_hot
from ai_research_radar.scoring.assessments import SelectionError, apply_assessments
from ai_research_radar.storage.jsonl import JsonlReadError, read_decoded_jsonl, write_jsonl

COMMAND_NAME = "select-hot"


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(COMMAND_NAME)
    parser.add_argument("--date", required=True)
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--input", default=None)
    # Parsed by run() so that a non-integer is recorded as invalid_input instead of argparse exit 2.
    parser.add_argument("--limit", default="2")
    # Removed options, accepted only to return a migration error (deprecated_option).
    parser.add_argument("--select", default=None)
    parser.add_argument("--reason", action="append", default=None)
    parser.add_argument("--summary", action="append", default=None)


def _fail(state: dict[str, Any], data_dir: Path, date: str, error_type: str, message: str) -> int:
    add_error(state, COMMAND_NAME, error_type, message)
    set_stage_result(state, COMMAND_NAME, "failed", f"{error_type}: {message}")
    save_run_state(data_dir, date, state)
    print(message)
    return 1


def _summaries_error(summaries: object, known_ids: set[str]) -> str | None:
    if not isinstance(summaries, dict):
        return "summaries must be an object of hot_id to summary"
    for hot_id, text in summaries.items():
        if hot_id not in known_ids:
            return f"summaries has unknown hot_id: {hot_id}"
        if not isinstance(text, str) or not text.strip():
            return f"summaries has an empty or non-string summary: {hot_id}"
    return None


def run(args: argparse.Namespace) -> int:
    data_dir = Path(args.data_dir)
    date = args.date
    run_dir = data_dir / "runs" / date
    hot_path = run_dir / "hot_candidates.jsonl"
    input_path = Path(args.input) if args.input else run_dir / "selection_input.json"

    state = load_run_state(data_dir, date)
    reset_errors_for(state, [COMMAND_NAME])

    deprecated = [name for name, value in (("--select", args.select), ("--reason", args.reason), ("--summary", args.summary)) if value is not None]
    if deprecated:
        message = (
            f"{' / '.join(deprecated)} は廃止しました。{input_path} に assessments / screened_ids / "
            f"selection_reason / summaries を書き、`ai-radar select-hot --date {date}` を実行してください"
        )
        return _fail(state, data_dir, date, "deprecated_option", message)

    try:
        limit = int(args.limit)
    except ValueError:
        return _fail(state, data_dir, date, "invalid_input", f"--limit must be an integer: {args.limit!r}")

    if not hot_path.exists():
        return _fail(state, data_dir, date, "missing_input", f"missing hot candidates: {hot_path}")
    if not input_path.exists():
        return _fail(state, data_dir, date, "missing_input", f"missing selection input: {input_path}")
    try:
        selection = json.loads(input_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return _fail(state, data_dir, date, "invalid_input", f"cannot read selection input {input_path}: {exc}")

    try:
        candidates = read_decoded_jsonl(hot_path, decode_hot)
    except JsonlReadError as exc:
        return _fail(state, data_dir, date, "corrupt_input", str(exc))
    try:
        updated, summary = apply_assessments(candidates, selection, limit=limit)
    except SelectionError as exc:
        return _fail(state, data_dir, date, exc.code, str(exc))

    summaries = selection.get("summaries", {})
    summary_error = _summaries_error(summaries, {candidate.hot_id for candidate in candidates})
    if summary_error:
        return _fail(state, data_dir, date, "invalid_summary", summary_error)
    updated = [
        replace(candidate, summary=summaries[candidate.hot_id].strip()) if candidate.hot_id in summaries else candidate
        for candidate in updated
    ]

    unsummarized = [candidate.hot_id for candidate in updated if not candidate.summary]
    missing_selected = [candidate.hot_id for candidate in updated if candidate.selected and not candidate.summary]
    if missing_selected:
        message = f"selected candidate(s) without summary: {', '.join(missing_selected)}"
        return _fail(state, data_dir, date, "missing_summary", message)
    if unsummarized:
        add_error(
            state,
            COMMAND_NAME,
            "missing_summary_warning",
            f"{len(unsummarized)} unselected candidate(s) without summary: {', '.join(unsummarized)}",
        )
    if summary["unreviewed_count"]:
        add_error(
            state,
            COMMAND_NAME,
            "unreviewed_candidates",
            f"{summary['unreviewed_count']} unreviewed candidate(s): {', '.join(summary['unreviewed_ids'])}",
        )

    try:
        write_jsonl(hot_path, updated)
    except Exception as exc:  # noqa: BLE001
        return _fail(state, data_dir, date, "write_error", f"failed to write hot candidates: {exc}")

    state["output_counts"]["selected_hot"] = summary["selected_count"]
    set_stage_result(
        state,
        COMMAND_NAME,
        "completed" if summary["selected_count"] else "deferred",
        summary["selection_reason"],
        candidate_count=summary["candidate_count"],
        screened_count=summary["screened_count"],
        unreviewed_count=summary["unreviewed_count"],
        selected_count=summary["selected_count"],
    )
    invalidate_proposals_result(state)
    mark_stage_completed(state, COMMAND_NAME)
    save_run_state(data_dir, date, state)
    return 0
