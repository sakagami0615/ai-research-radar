from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ai_research_radar.cli.commands.run_state import (
    add_error,
    load_run_state,
    mark_stage_completed,
    reset_errors_for,
    save_run_state,
    set_stage_result,
)
from ai_research_radar.schemas.models import ArticleProposal
from ai_research_radar.storage.jsonl import read_jsonl, write_jsonl

COMMAND_NAME = "save-proposals"
NO_SELECTION_REASON = "選抜HOTなし"

REQUIRED_FIELDS = {
    "proposal_id",
    "source_hot_id",
    "title_idea",
    "article_type",
    "target_reader",
    "why_now",
    "technical_angle",
    "experiment_plan",
    "competition",
    "traffic_opportunity",
    "technical_opportunity",
    "unique_angle",
    "evidence_links",
    "risks",
}


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(COMMAND_NAME)
    parser.add_argument("--date", required=True)
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--input", required=True)


def _fail(state: dict[str, Any], data_dir: Path, date: str, error_type: str, message: str) -> int:
    add_error(state, COMMAND_NAME, error_type, message)
    set_stage_result(state, COMMAND_NAME, "failed", f"{error_type}: {message}")
    save_run_state(data_dir, date, state)
    print(message)
    return 1


def run(args: argparse.Namespace) -> int:
    data_dir = Path(args.data_dir)
    date = args.date
    hot_path = data_dir / "runs" / date / "hot_candidates.jsonl"
    input_path = Path(args.input)

    state = load_run_state(data_dir, date)
    reset_errors_for(state, [COMMAND_NAME])

    if not hot_path.exists():
        return _fail(state, data_dir, date, "missing_input", f"missing hot candidates: {hot_path}")
    if not input_path.exists():
        return _fail(state, data_dir, date, "missing_input", f"missing input file: {input_path}")
    try:
        records = json.loads(input_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return _fail(state, data_dir, date, "invalid_input", f"input file is not valid JSON: {exc}")
    except (OSError, UnicodeDecodeError) as exc:
        return _fail(state, data_dir, date, "invalid_input", f"cannot read input file {input_path}: {exc}")
    if not isinstance(records, list):
        return _fail(state, data_dir, date, "invalid_input", "input file must contain a JSON array of article proposals")

    selected_ids = {
        record["hot_id"] for record in read_jsonl(hot_path) if record.get("selected") is True
    }

    proposals: list[ArticleProposal] = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            return _fail(state, data_dir, date, "invalid_proposal", f"proposal[{index}] must be an object")
        missing_fields = REQUIRED_FIELDS - set(record.keys())
        if missing_fields:
            return _fail(state, data_dir, date, "invalid_proposal", f"proposal[{index}] missing fields: {', '.join(sorted(missing_fields))}")

        proposal = ArticleProposal(**{key: record[key] for key in REQUIRED_FIELDS})

        if not proposal.evidence_links:
            return _fail(state, data_dir, date, "invalid_proposal", f"proposal[{index}] must include at least one evidence link")
        if proposal.source_hot_id not in selected_ids:
            message = f"proposal[{index}] source_hot_id is not a selected HOT candidate: {proposal.source_hot_id}"
            return _fail(state, data_dir, date, "invalid_proposal", message)

        proposals.append(proposal)

    proposals_path = data_dir / "runs" / date / "article_proposals.jsonl"
    try:
        write_jsonl(proposals_path, proposals)
    except Exception as exc:  # noqa: BLE001
        return _fail(state, data_dir, date, "write_error", f"failed to write article proposals: {exc}")

    if not selected_ids:
        status, reason = "not_run", NO_SELECTION_REASON
    elif proposals:
        status, reason = "completed", ""
    else:
        # deferral_reason is added to the input by #11; until then the reason is empty.
        status, reason = "deferred", ""
    set_stage_result(state, COMMAND_NAME, status, reason, proposal_count=len(proposals))
    state["output_counts"]["article_proposals"] = len(proposals)
    mark_stage_completed(state, COMMAND_NAME)
    save_run_state(data_dir, date, state)
    return 0
