from __future__ import annotations

import argparse
from pathlib import Path

from ai_research_radar.cli.commands.common import add_runtime_arguments, data_dir as resolve_data_dir, fail
from ai_research_radar.config.settings import load_scoring_config
from ai_research_radar.schemas.decoders import decode_event
from ai_research_radar.scoring.hot import compute_hot_candidates
from ai_research_radar.storage.jsonl import JsonlReadError, read_decoded_jsonl, write_jsonl
from ai_research_radar.storage.run_state import load_run_state, mark_stage_completed, reset_errors_for, save_run_state

COMMAND_NAME = "score"


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(COMMAND_NAME)
    parser.add_argument("--date", required=True)
    parser.add_argument("--scoring-config", default="config/scoring.yaml")
    add_runtime_arguments(parser)
    parser.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    data_dir = resolve_data_dir(args)
    date = args.date
    events_path = data_dir / "events" / date / "events.jsonl"
    state = load_run_state(data_dir, date)
    reset_errors_for(state, [COMMAND_NAME])
    if not events_path.exists():
        return fail(state, data_dir, date, COMMAND_NAME, "missing_input", f"missing events: {events_path}")

    scoring = load_scoring_config(Path(args.scoring_config))
    minimum_score = float(scoring.get("hot_selection", {}).get("minimum_score", 75.0))
    weights = dict(scoring.get("hot_score", {}))
    try:
        events = read_decoded_jsonl(events_path, decode_event)
    except JsonlReadError as exc:
        return fail(state, data_dir, date, COMMAND_NAME, "corrupt_input", str(exc))
    candidates = compute_hot_candidates(events, minimum_score=minimum_score, weights=weights)
    try:
        write_jsonl(data_dir / "runs" / date / "hot_candidates.jsonl", candidates)
    except (OSError, ValueError) as exc:  # ValueError: e.g. text that cannot be encoded
        return fail(state, data_dir, date, COMMAND_NAME, "write_error", f"failed to write hot candidates: {exc}")

    state["output_counts"]["hot_candidates"] = len(candidates)
    mark_stage_completed(state, COMMAND_NAME)
    save_run_state(data_dir, date, state)
    return 0
