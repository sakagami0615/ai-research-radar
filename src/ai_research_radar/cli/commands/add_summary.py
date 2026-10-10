from __future__ import annotations

import argparse

from ai_research_radar.cli.commands.common import add_runtime_arguments, data_dir as resolve_data_dir, fail, read_input_object
from ai_research_radar.reporting.digest import build_daily_digest, save_digest_summaries, summarizable_keys
from ai_research_radar.storage.run_state import load_run_state, reset_errors_for, save_run_state

COMMAND_NAME = "add-summary"


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(COMMAND_NAME)
    parser.add_argument("--date", required=True)
    # Checked by run() so that a missing --input is recorded as invalid_input instead of argparse exit 2.
    parser.add_argument("--input", default=None)
    add_runtime_arguments(parser)
    parser.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    """Save summaries for displayed notable items and model releases that have none.

    The input is a JSON object of hot_id or model release key to summary. Not a
    pipeline stage: it only adds data for the report, so it does not mark
    stages_completed.
    """
    data_dir = resolve_data_dir(args)
    date = args.date
    state = load_run_state(data_dir, date)
    reset_errors_for(state, [COMMAND_NAME])

    def failed(error_type: str, message: str) -> int:
        return fail(state, data_dir, date, COMMAND_NAME, error_type, message)

    entries, error = read_input_object(args.input, "summary")
    if error:
        return failed(*error)
    if not entries:
        return failed("invalid_summary", "input file has no summaries")

    known_keys = summarizable_keys(build_daily_digest(data_dir, date))
    summaries: dict[str, str] = {}
    for key, text in entries.items():
        if key not in known_keys:
            return failed("invalid_summary", f"not a displayed item that takes a summary: {key}")
        if not isinstance(text, str) or not text.strip():
            return failed("invalid_summary", f"empty or non-string summary: {key}")
        summaries[key] = text.strip()

    try:
        save_digest_summaries(data_dir, date, summaries)
    except (OSError, ValueError) as exc:
        return failed("write_error", f"failed to save summaries: {exc}")

    save_run_state(data_dir, date, state)
    return 0

