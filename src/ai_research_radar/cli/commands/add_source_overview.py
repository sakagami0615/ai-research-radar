from __future__ import annotations

import argparse

from ai_research_radar.cli.commands.common import add_runtime_arguments, data_dir as resolve_data_dir, fail, read_input_object
from ai_research_radar.reporting.source_overview import group_signals_by_source, save_source_overviews
from ai_research_radar.storage.jsonl import JsonlReadError, read_jsonl
from ai_research_radar.storage.run_state import load_run_state, reset_errors_for, save_run_state

COMMAND_NAME = "add-source-overview"


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(COMMAND_NAME)
    parser.add_argument("--date", required=True)
    # Checked by run() so that a missing --input is recorded as invalid_input instead of argparse exit 2.
    parser.add_argument("--input", default=None)
    add_runtime_arguments(parser)
    parser.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    """Save the per-source "本日の傾向" shown under each heading of the report's source appendix.

    The input is a JSON object of source heading to overview text. Not a
    pipeline stage: it only adds data for the report, so it does not mark
    stages_completed.
    """
    data_dir = resolve_data_dir(args)
    date = args.date
    state = load_run_state(data_dir, date)
    reset_errors_for(state, [COMMAND_NAME])

    def failed(error_type: str, message: str) -> int:
        return fail(state, data_dir, date, COMMAND_NAME, error_type, message)

    entries, error = read_input_object(args.input, "overview")
    if error:
        return failed(*error)
    if not entries:
        return failed("invalid_overview", "input file has no overviews")

    sources = [source for source in state.get("sources", []) if isinstance(source, str)]
    signals_path = data_dir / "normalized" / date / "signals.jsonl"
    try:
        signals = read_jsonl(signals_path) if signals_path.exists() else []
    except JsonlReadError as exc:
        # A broken pipeline output, recorded like the other commands do (corrupt_input).
        return failed("corrupt_input", f"cannot read signals: {exc}")
    # The same headings and counts as the report, including the "other" heading when it has signals.
    counts = {source: len(items) for source, items in group_signals_by_source(sources, signals).items()}

    overviews: dict[str, str] = {}
    for source, text in entries.items():
        if source not in counts:
            return failed("invalid_overview", f"not a source heading of the report: {source}")
        if not isinstance(text, str) or not text.strip():
            return failed("invalid_overview", f"empty or non-string overview: {source}")
        if counts[source] == 0:
            return failed("invalid_overview", f"source has no signals today: {source}")
        overviews[source] = text.strip()

    try:
        save_source_overviews(data_dir, date, overviews)
    except (OSError, ValueError) as exc:
        return failed("write_error", f"failed to save source overviews: {exc}")

    save_run_state(data_dir, date, state)
    return 0
