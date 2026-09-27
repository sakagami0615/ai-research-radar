from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

from ai_research_radar.cli.commands.run_state import (
    add_error,
    load_run_state,
    mark_stage_completed,
    save_run_state,
)
from ai_research_radar.schemas.models import HotCandidate
from ai_research_radar.storage.jsonl import read_jsonl, write_jsonl

COMMAND_NAME = "select-hot"


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(COMMAND_NAME)
    parser.add_argument("--date", required=True)
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--select", default="")
    parser.add_argument("--reason", action="append", default=[])


def run(args: argparse.Namespace) -> int:
    data_dir = Path(args.data_dir)
    date = args.date
    hot_path = data_dir / "runs" / date / "hot_candidates.jsonl"

    state = load_run_state(data_dir, date)

    if not hot_path.exists():
        add_error(state, "select-hot", "missing_input", f"missing hot candidates: {hot_path}")
        save_run_state(data_dir, date, state)
        print(f"missing hot candidates: {hot_path}")
        return 1

    candidates = [HotCandidate(**record) for record in read_jsonl(hot_path)]
    known_ids = {candidate.hot_id for candidate in candidates}

    selected_ids = {item for item in args.select.split(",") if item}

    unknown_selected = selected_ids - known_ids
    if unknown_selected:
        add_error(
            state,
            "select-hot",
            "invalid_selection",
            f"unknown hot_id(s): {', '.join(sorted(unknown_selected))}",
        )
        save_run_state(data_dir, date, state)
        print(f"unknown hot_id(s): {', '.join(sorted(unknown_selected))}")
        return 1

    reasons_by_id: dict[str, list[str]] = {}
    for entry in args.reason:
        hot_id, separator, text = entry.partition("=")
        if not separator or hot_id not in known_ids or not text.strip():
            add_error(
                state,
                "select-hot",
                "invalid_reason",
                f"invalid reason entry: {entry}",
            )
            save_run_state(data_dir, date, state)
            print(f"invalid reason entry: {entry}")
            return 1
        reasons_by_id.setdefault(hot_id, []).append(text)

    updated_candidates = []
    for candidate in candidates:
        existing = list(candidate.reasons)
        new_texts = [
            text for text in reasons_by_id.get(candidate.hot_id, []) if text not in existing
        ]
        updated_candidates.append(
            replace(
                candidate,
                selected=candidate.hot_id in selected_ids,
                reasons=existing + new_texts,
            )
        )

    try:
        write_jsonl(hot_path, updated_candidates)
    except Exception as exc:  # noqa: BLE001
        add_error(state, "select-hot", "write_error", str(exc))
        save_run_state(data_dir, date, state)
        print(f"failed to write hot candidates: {exc}")
        return 1

    state["output_counts"]["selected_hot"] = len(selected_ids)
    mark_stage_completed(state, COMMAND_NAME)
    save_run_state(data_dir, date, state)
    return 0
