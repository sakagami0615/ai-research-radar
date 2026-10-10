from __future__ import annotations

import argparse

from ai_research_radar.cli.commands.common import add_runtime_arguments, data_dir as resolve_data_dir
from ai_research_radar.storage.run_state import load_run_state, run_state_path, save_run_state

COMMAND_NAME = "mark-needs-review"


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(COMMAND_NAME)
    parser.add_argument("--date", required=True)
    add_runtime_arguments(parser)
    parser.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    """Record that the quality review loop ended with unresolved findings.

    `report` then shows a warning banner pointing to review_feedback.md, also
    when the report is generated again. `collect` clears the flag, since it
    starts the day's run over.
    """
    data_dir = resolve_data_dir(args)
    if not run_state_path(data_dir, args.date).exists():
        # A typo in --date must not create a new run_state.json and look successful.
        print(f"no run_state.json for {args.date} under {data_dir}")
        return 1
    state = load_run_state(data_dir, args.date)
    state["needs_review"] = True
    save_run_state(data_dir, args.date, state)
    return 0
