from __future__ import annotations

import argparse

from ai_research_radar.cli.commands.common import add_runtime_arguments, data_dir as resolve_data_dir, fail
from ai_research_radar.normalization.dedup import deduplicate_signals
from ai_research_radar.normalization.scores import normalize_source_batch
from ai_research_radar.pipeline.events import build_events, cluster_topics
from ai_research_radar.schemas.decoders import decode_signal
from ai_research_radar.storage.jsonl import JsonlReadError, read_decoded_jsonl, write_jsonl
from ai_research_radar.storage.run_state import load_run_state, mark_stage_completed, reset_errors_for, save_run_state

COMMAND_NAME = "normalize"


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(COMMAND_NAME)
    parser.add_argument("--date", required=True)
    add_runtime_arguments(parser)
    parser.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    data_dir = resolve_data_dir(args)
    date = args.date
    collected_path = data_dir / "collected" / date / "signals.jsonl"
    state = load_run_state(data_dir, date)
    reset_errors_for(state, [COMMAND_NAME])
    if not collected_path.exists():
        return fail(state, data_dir, date, COMMAND_NAME, "missing_input", f"missing collected signals: {collected_path}")
    try:
        signals = read_decoded_jsonl(collected_path, decode_signal)
    except JsonlReadError as exc:
        return fail(state, data_dir, date, COMMAND_NAME, "corrupt_input", str(exc))

    deduped = deduplicate_signals(normalize_source_batch(signals))
    events = build_events(deduped)
    topics = cluster_topics(events)
    try:
        write_jsonl(data_dir / "normalized" / date / "signals.jsonl", deduped)
        write_jsonl(data_dir / "events" / date / "events.jsonl", events)
        write_jsonl(data_dir / "topics" / date / "topics.jsonl", topics)
    except (OSError, ValueError) as exc:  # ValueError: e.g. text that cannot be encoded
        return fail(state, data_dir, date, COMMAND_NAME, "write_error", f"failed to write normalize output: {exc}")

    state["output_counts"]["signals"] = len(deduped)
    state["output_counts"]["events"] = len(events)
    state["output_counts"]["topics"] = len(topics)
    mark_stage_completed(state, COMMAND_NAME)
    save_run_state(data_dir, date, state)
    return 0
