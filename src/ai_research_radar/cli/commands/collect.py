from __future__ import annotations

import argparse
from datetime import date as date_cls
from pathlib import Path

import yaml

from ai_research_radar.cli.commands.run_state import (
    add_error,
    load_run_state,
    mark_stage_completed,
    reset_errors_for,
    save_run_state,
)
from ai_research_radar.config.settings import (
    load_runtime_config,
    load_source_configs,
    resolve_max_lookback_days,
)
from ai_research_radar.periods import (
    DEFAULT_MAX_LOOKBACK_DAYS,
    period_date,
    previous_day_period,
    resolve_default_period,
)
from ai_research_radar.sources.base import SourceError
from ai_research_radar.sources.public import build_adapters
from ai_research_radar.storage.jsonl import write_jsonl

COMMAND_NAME = "collect"


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(COMMAND_NAME)
    parser.add_argument("--since")
    parser.add_argument("--until")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--sources-config", default="config/sources.yaml")
    parser.add_argument("--runtime-config", default="config/runtime.yaml")


def run(args: argparse.Namespace) -> int:
    data_dir = Path(args.data_dir)
    if args.since is None and args.until is None:
        since, until = resolve_default_period(
            data_dir, max_lookback_days=_max_lookback_days(Path(args.runtime_config))
        )
    else:
        until = args.until or date_cls.today().isoformat()
        since = args.since or previous_day_period(until)
    run_date = period_date(until)

    configs = load_source_configs(Path(args.sources_config))
    adapters = build_adapters(configs)

    state = load_run_state(data_dir, run_date)
    state["since"] = since
    state["until"] = until
    state["sources"] = [adapter.source_name for adapter in adapters]
    reset_errors_for(state, [adapter.source_name for adapter in adapters] + ["collect"])

    collected_signals = []
    total_raw_items = 0
    for adapter in adapters:
        try:
            collected = adapter.collect(since=since, until=until)
        except SourceError as exc:
            add_error(state, exc.source, exc.error_type, str(exc))
            continue
        except Exception as exc:  # noqa: BLE001
            add_error(state, adapter.source_name, "unexpected_error", str(exc))
            continue
        for error in getattr(adapter, "partial_errors", []):
            add_error(state, error["source"], error["type"], error["message"])

        state["input_counts"][adapter.source_name] = len(collected)
        total_raw_items += len(collected)
        try:
            write_jsonl(data_dir / "raw" / run_date / f"{adapter.source_name}.jsonl", collected)
        except Exception as exc:  # noqa: BLE001
            add_error(state, adapter.source_name, "raw_write_error", str(exc))

        try:
            normalized_items = [adapter.normalize(item) for item in collected]
        except SourceError as exc:
            add_error(state, exc.source, exc.error_type, str(exc))
            continue
        except Exception as exc:  # noqa: BLE001
            add_error(state, adapter.source_name, "unexpected_error", str(exc))
            continue
        collected_signals.extend(normalized_items)

    state["output_counts"]["raw_items"] = total_raw_items
    try:
        write_jsonl(data_dir / "collected" / run_date / "signals.jsonl", collected_signals)
    except Exception as exc:  # noqa: BLE001
        add_error(state, "collect", "signals_write_error", str(exc))
        save_run_state(data_dir, run_date, state)
        print(str(exc))
        return 1

    mark_stage_completed(state, COMMAND_NAME)
    save_run_state(data_dir, run_date, state)

    print(run_date)
    return 0


def _max_lookback_days(runtime_config: Path) -> int:
    """Collection must not stop over a missing or broken runtime config."""
    try:
        runtime = load_runtime_config(runtime_config)
    except (OSError, ValueError, yaml.YAMLError):
        return DEFAULT_MAX_LOOKBACK_DAYS
    return resolve_max_lookback_days(runtime)
