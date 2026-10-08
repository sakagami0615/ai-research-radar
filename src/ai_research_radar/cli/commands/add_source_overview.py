from __future__ import annotations

import argparse
import json
from pathlib import Path

from ai_research_radar.cli.commands.run_state import (
    add_error,
    load_run_state,
    reset_errors_for,
    save_run_state,
)
from ai_research_radar.reporting.source_overview import group_signals_by_source, save_source_overviews
from ai_research_radar.storage.jsonl import read_jsonl

COMMAND_NAME = "add-source-overview"


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(COMMAND_NAME)
    parser.add_argument("--date", required=True)
    parser.add_argument("--data-dir", default="data")
    # Checked by run() so that a missing --input is recorded as invalid_input instead of argparse exit 2.
    parser.add_argument("--input", default=None)


def run(args: argparse.Namespace) -> int:
    """Save the per-source "本日の傾向" shown under each heading of the report's source appendix.

    The input is a JSON object of source heading to overview text. Not a
    pipeline stage: it only adds data for the report, so it does not mark
    stages_completed.
    """
    data_dir = Path(args.data_dir)
    date = args.date

    state = load_run_state(data_dir, date)
    reset_errors_for(state, [COMMAND_NAME])

    if not args.input:
        return _fail(data_dir, date, state, "invalid_input", "no --input given")
    input_path = Path(args.input)
    if not input_path.exists():
        return _fail(data_dir, date, state, "invalid_input", f"missing input file: {input_path}")
    try:
        entries = json.loads(input_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return _fail(data_dir, date, state, "invalid_input", f"cannot read input file {input_path}: {exc}")
    if not isinstance(entries, dict):
        return _fail(data_dir, date, state, "invalid_input", "input file must contain a JSON object of source to overview")
    if not entries:
        return _fail(data_dir, date, state, "invalid_overview", "input file has no overviews")

    sources = [source for source in state.get("sources", []) if isinstance(source, str)]
    signals_path = data_dir / "normalized" / date / "signals.jsonl"
    try:
        signals = read_jsonl(signals_path) if signals_path.exists() else []
    except (OSError, ValueError) as exc:
        return _fail(data_dir, date, state, "invalid_input", f"cannot read signals {signals_path}: {exc}")
    # The same headings and counts as the report, including the "other" heading when it has signals.
    counts = {source: len(items) for source, items in group_signals_by_source(sources, signals).items()}

    overviews: dict[str, str] = {}
    for source, text in entries.items():
        if source not in counts:
            return _fail(data_dir, date, state, "invalid_overview", f"not a source heading of the report: {source}")
        if not isinstance(text, str) or not text.strip():
            return _fail(data_dir, date, state, "invalid_overview", f"empty or non-string overview: {source}")
        if counts[source] == 0:
            return _fail(data_dir, date, state, "invalid_overview", f"source has no signals today: {source}")
        overviews[source] = text.strip()

    try:
        save_source_overviews(data_dir, date, overviews)
    except (OSError, ValueError) as exc:
        return _fail(data_dir, date, state, "write_error", f"failed to save source overviews: {exc}")

    save_run_state(data_dir, date, state)
    return 0


def _fail(data_dir: Path, date: str, state: dict, error_type: str, message: str) -> int:
    add_error(state, COMMAND_NAME, error_type, message)
    save_run_state(data_dir, date, state)
    print(message)
    return 1
