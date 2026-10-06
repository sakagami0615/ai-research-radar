from __future__ import annotations

import argparse
from pathlib import Path

from ai_research_radar.cli.commands.run_state import (
    add_error,
    load_run_state,
    reset_errors_for,
    save_run_state,
)
from ai_research_radar.reporting.digest import (
    build_daily_digest,
    save_digest_summaries,
    summarizable_keys,
)

COMMAND_NAME = "add-summary"


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(COMMAND_NAME)
    parser.add_argument("--date", required=True)
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--summary", action="append", default=[])


def run(args: argparse.Namespace) -> int:
    """Save summaries for displayed notable items whose candidate has none (e.g. from a past day).

    Not a pipeline stage: it only adds data for the report, so it does not mark
    stages_completed.
    """
    data_dir = Path(args.data_dir)
    date = args.date

    state = load_run_state(data_dir, date)
    reset_errors_for(state, [COMMAND_NAME])

    if not args.summary:
        return _fail(data_dir, date, state, "invalid_summary", "no --summary given")
    known_ids = summarizable_keys(build_daily_digest(data_dir, date))

    summaries: dict[str, str] = {}
    for entry in args.summary:
        hot_id, separator, text = entry.partition("=")
        if not separator or hot_id not in known_ids or not text.strip():
            return _fail(data_dir, date, state, "invalid_summary", f"invalid summary entry: {entry}")
        summaries[hot_id] = text.strip()

    try:
        save_digest_summaries(data_dir, date, summaries)
    except (OSError, ValueError) as exc:
        return _fail(data_dir, date, state, "write_error", f"failed to save summaries: {exc}")

    save_run_state(data_dir, date, state)
    return 0


def _fail(data_dir: Path, date: str, state: dict, error_type: str, message: str) -> int:
    add_error(state, COMMAND_NAME, error_type, message)
    save_run_state(data_dir, date, state)
    print(message)
    return 1
