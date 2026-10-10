"""Helpers shared by the `ai-radar` subcommands."""

from __future__ import annotations

import argparse
import json
from datetime import date as date_cls
from pathlib import Path
from typing import Any

from ai_research_radar.config.settings import load_runtime_config_or_default, resolve_max_lookback_days, resolve_output_dir
from ai_research_radar import periods
from ai_research_radar.storage.run_state import add_error, save_run_state, set_stage_result

DEFAULT_RUNTIME_CONFIG = "config/runtime.yaml"


def add_runtime_arguments(parser: argparse.ArgumentParser, *, reports_dir: bool = False) -> None:
    """--data-dir (and --reports-dir) default to `output` in runtime.yaml, read from --runtime-config."""
    parser.add_argument("--data-dir")
    if reports_dir:
        parser.add_argument("--reports-dir")
    parser.add_argument("--runtime-config", default=DEFAULT_RUNTIME_CONFIG)


def runtime_config(args: argparse.Namespace) -> dict[str, Any]:
    return load_runtime_config_or_default(Path(args.runtime_config))


def data_dir(args: argparse.Namespace) -> Path:
    return Path(args.data_dir) if args.data_dir else resolve_output_dir(runtime_config(args), "data_dir", "data")


def reports_dir(args: argparse.Namespace) -> Path:
    return Path(args.reports_dir) if args.reports_dir else resolve_output_dir(runtime_config(args), "reports_dir", "reports")


def fail(
    state: dict[str, Any],
    data_dir: Path,
    date: str,
    command: str,
    error_type: str,
    message: str,
    *,
    record_stage_result: bool = False,
) -> int:
    """Record the error in run_state.json, print it and return exit code 1.

    `record_stage_result` also records the stage as failed in stage_results
    (select-hot / save-proposals).
    """
    add_error(state, command, error_type, message)
    if record_stage_result:
        set_stage_result(state, command, "failed", f"{error_type}: {message}")
    save_run_state(data_dir, date, state)
    print(message)
    return 1


def read_input_object(input_arg: str | None, value_name: str) -> tuple[dict[str, Any], tuple[str, str] | None]:
    """Read the --input JSON object of key to text, or return ({}, (error_type, message)).

    Shared by add-summary and add-source-overview: no --input or an unreadable
    or non-object file is invalid_input, a missing file is missing_input.
    """
    if not input_arg:
        return {}, ("invalid_input", "no --input given")
    path = Path(input_arg)
    if not path.exists():
        return {}, ("missing_input", f"missing input file: {path}")
    try:
        entries = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {}, ("invalid_input", f"cannot read input file {path}: {exc}")
    if not isinstance(entries, dict):
        return {}, ("invalid_input", f"input file must contain a JSON object of key to {value_name}")
    return entries, None


def resolve_period(args: argparse.Namespace, data_dir: Path) -> tuple[str, str, bool]:
    """(since, until, use_overlap). Both omitted: resume from the previous run (shared with `daily`)."""
    if args.since is None and args.until is None:
        since, until = periods.resolve_default_period(
            data_dir, max_lookback_days=resolve_max_lookback_days(runtime_config(args))
        )
        return since, until, True
    until = args.until or date_cls.today().isoformat()
    return args.since or periods.previous_day_period(until), until, False
