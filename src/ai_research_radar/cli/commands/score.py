from __future__ import annotations

import argparse
from pathlib import Path

from ai_research_radar.cli.commands.run_state import (
    add_error,
    load_run_state,
    mark_stage_completed,
    reset_errors_for,
    save_run_state,
)
from ai_research_radar.config.settings import load_scoring_config
from ai_research_radar.schemas.models import event_from_dict
from ai_research_radar.scoring.hot import compute_hot_candidates
from ai_research_radar.storage.jsonl import read_jsonl, write_jsonl

COMMAND_NAME = "score"


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(COMMAND_NAME)
    parser.add_argument("--date", required=True)
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--scoring-config", default="config/scoring.yaml")


def run(args: argparse.Namespace) -> int:
    data_dir = Path(args.data_dir)
    date = args.date
    events_path = data_dir / "events" / date / "events.jsonl"

    state = load_run_state(data_dir, date)
    reset_errors_for(state, [COMMAND_NAME])

    if not events_path.exists():
        add_error(state, "score", "missing_input", f"missing events: {events_path}")
        save_run_state(data_dir, date, state)
        print(f"missing events: {events_path}")
        return 1

    scoring = load_scoring_config(Path(args.scoring_config))
    hot_selection = scoring.get("hot_selection", {})
    minimum_score = float(hot_selection.get("minimum_score", 75.0))
    weights = dict(scoring.get("hot_score", {}))

    events = [event_from_dict(record) for record in read_jsonl(events_path)]
    candidates = compute_hot_candidates(events, minimum_score=minimum_score, weights=weights)

    try:
        write_jsonl(data_dir / "runs" / date / "hot_candidates.jsonl", candidates)
    except Exception as exc:  # noqa: BLE001
        add_error(state, "score", "write_error", str(exc))
        save_run_state(data_dir, date, state)
        print(f"failed to write hot candidates: {exc}")
        return 1

    state["output_counts"]["hot_candidates"] = len(candidates)
    mark_stage_completed(state, COMMAND_NAME)
    save_run_state(data_dir, date, state)
    return 0
