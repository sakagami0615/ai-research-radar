from __future__ import annotations

import argparse
from pathlib import Path

from ai_research_radar.cli.commands.common import add_runtime_arguments, data_dir as resolve_data_dir, fail, resolve_period
from ai_research_radar.config.settings import load_source_configs
from ai_research_radar.periods import period_date
from ai_research_radar.sources.collection import collect_sources
from ai_research_radar.sources.public import build_adapters
from ai_research_radar.storage.jsonl import write_jsonl
from ai_research_radar.storage.run_state import add_error, load_run_state, mark_stage_completed, reset_errors_for, save_run_state

COMMAND_NAME = "collect"


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(COMMAND_NAME)
    parser.add_argument("--since")
    parser.add_argument("--until")
    parser.add_argument("--sources-config", default="config/sources.yaml")
    add_runtime_arguments(parser)
    parser.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    data_dir = resolve_data_dir(args)
    since, until, use_overlap = resolve_period(args, data_dir)
    run_date = period_date(until)

    adapters = build_adapters(load_source_configs(Path(args.sources_config)))
    source_names = [adapter.source_name for adapter in adapters]

    state = load_run_state(data_dir, run_date)
    state["since"] = since
    state["until"] = until
    state["sources"] = source_names
    # A new collection starts the day's run over, so an earlier unresolved review no longer applies.
    state.pop("needs_review", None)
    reset_errors_for(state, [*source_names, COMMAND_NAME])

    result = collect_sources(adapters, since, until, data_dir, run_date, use_overlap)
    for error in result.errors:
        add_error(state, error["source"], error["type"], error["message"])
    state["input_counts"].update(result.input_counts)
    state["output_counts"]["raw_items"] = len(result.raw_items)
    try:
        write_jsonl(data_dir / "collected" / run_date / "signals.jsonl", result.signals)
    except (OSError, ValueError) as exc:  # ValueError: e.g. text that cannot be encoded
        return fail(state, data_dir, run_date, COMMAND_NAME, "signals_write_error", str(exc))

    mark_stage_completed(state, COMMAND_NAME)
    save_run_state(data_dir, run_date, state)
    print(run_date)
    return 0
