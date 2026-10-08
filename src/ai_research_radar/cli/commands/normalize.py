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
from ai_research_radar.normalization.dedup import deduplicate_signals
from ai_research_radar.normalization.scores import normalize_source_batch
from ai_research_radar.pipeline.events import build_events, cluster_topics
from ai_research_radar.schemas.models import canonical_signal_from_dict
from ai_research_radar.storage.jsonl import JsonlReadError, read_decoded_jsonl, write_jsonl

COMMAND_NAME = "normalize"


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(COMMAND_NAME)
    parser.add_argument("--date", required=True)
    parser.add_argument("--data-dir", default="data")


def run(args: argparse.Namespace) -> int:
    data_dir = Path(args.data_dir)
    date = args.date
    collected_path = data_dir / "collected" / date / "signals.jsonl"
    state = load_run_state(data_dir, date)
    reset_errors_for(state, [COMMAND_NAME])
    if not collected_path.exists():
        add_error(state, "normalize", "missing_input", f"missing collected signals: {collected_path}")
        save_run_state(data_dir, date, state)
        print(f"missing collected signals: {collected_path}")
        return 1

    try:
        signals = read_decoded_jsonl(collected_path, canonical_signal_from_dict)
    except JsonlReadError as exc:
        add_error(state, "normalize", "corrupt_input", str(exc))
        save_run_state(data_dir, date, state)
        print(f"cannot read collected signals: {exc}")
        return 1

    signals = normalize_source_batch(signals)
    deduped = deduplicate_signals(signals)
    events = build_events(deduped)
    topics = cluster_topics(events)

    try:
        write_jsonl(data_dir / "normalized" / date / "signals.jsonl", deduped)
        write_jsonl(data_dir / "events" / date / "events.jsonl", events)
        write_jsonl(data_dir / "topics" / date / "topics.jsonl", topics)
    except Exception as exc:  # noqa: BLE001
        add_error(state, "normalize", "write_error", str(exc))
        save_run_state(data_dir, date, state)
        print(f"failed to write normalize output: {exc}")
        return 1

    state["output_counts"]["signals"] = len(deduped)
    state["output_counts"]["events"] = len(events)
    state["output_counts"]["topics"] = len(topics)
    mark_stage_completed(state, COMMAND_NAME)
    save_run_state(data_dir, date, state)
    return 0
