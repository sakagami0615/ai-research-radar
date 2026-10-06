from __future__ import annotations

import argparse
import json
from pathlib import Path

from ai_research_radar.cli.commands.run_state import (
    add_error,
    load_run_state,
    reset_errors_for,
    save_run_state,
)
from ai_research_radar.reporting.digest import (
    build_daily_digest,
    save_digest_summaries,
    summarizable_keys,
)

COMMAND_NAME = "add-summary"


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(COMMAND_NAME)
    parser.add_argument("--date", required=True)
    parser.add_argument("--data-dir", default="data")
    # Checked by run() so that a missing --input is recorded as invalid_summary instead of argparse exit 2.
    parser.add_argument("--input", default=None)
    # Removed option, accepted only to return a migration error (deprecated_option).
    parser.add_argument("--summary", action="append", default=None)


def run(args: argparse.Namespace) -> int:
    """Save summaries for displayed notable items and model releases that have none.

    The input is a JSON object of hot_id or model release key to summary. Not a
    pipeline stage: it only adds data for the report, so it does not mark
    stages_completed.
    """
    data_dir = Path(args.data_dir)
    date = args.date

    state = load_run_state(data_dir, date)
    reset_errors_for(state, [COMMAND_NAME])

    if args.summary is not None:
        example = data_dir / "runs" / date / "summary_input.json"
        message = (
            f"--summary は廃止しました。{example} などに "
            '{"<hot_id または key>": "概要"} 形式のJSONを書き、'
            f"`ai-radar add-summary --date {date} --input <ファイル>` を実行してください"
        )
        return _fail(data_dir, date, state, "deprecated_option", message)
    if not args.input:
        return _fail(data_dir, date, state, "invalid_summary", "no --input given")

    input_path = Path(args.input)
    if not input_path.exists():
        return _fail(data_dir, date, state, "missing_input", f"missing input file: {input_path}")
    try:
        entries = json.loads(input_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return _fail(data_dir, date, state, "invalid_input", f"input file is not valid JSON: {exc}")
    if not isinstance(entries, dict):
        return _fail(data_dir, date, state, "invalid_input", "input file must contain a JSON object of key to summary")
    if not entries:
        return _fail(data_dir, date, state, "invalid_summary", "input file has no summaries")

    known_keys = summarizable_keys(build_daily_digest(data_dir, date))
    summaries: dict[str, str] = {}
    for key, text in entries.items():
        if key not in known_keys:
            return _fail(data_dir, date, state, "invalid_summary", f"not a displayed item that takes a summary: {key}")
        if not isinstance(text, str) or not text.strip():
            return _fail(data_dir, date, state, "invalid_summary", f"empty or non-string summary: {key}")
        summaries[key] = text.strip()

    try:
        save_digest_summaries(data_dir, date, summaries)
    except (OSError, ValueError) as exc:
        return _fail(data_dir, date, state, "write_error", f"failed to save summaries: {exc}")

    save_run_state(data_dir, date, state)
    return 0


def _fail(data_dir: Path, date: str, state: dict, error_type: str, message: str) -> int:
    add_error(state, COMMAND_NAME, error_type, message)
    save_run_state(data_dir, date, state)
    print(message)
    return 1
