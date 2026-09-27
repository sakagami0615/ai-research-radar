from __future__ import annotations

import argparse
import json
from pathlib import Path

from ai_research_radar.cli.commands.run_state import (
    add_error,
    load_run_state,
    mark_stage_completed,
    save_run_state,
)
from ai_research_radar.schemas.models import ArticleProposal
from ai_research_radar.storage.jsonl import read_jsonl, write_jsonl

COMMAND_NAME = "save-proposals"

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


def run(args: argparse.Namespace) -> int:
    data_dir = Path(args.data_dir)
    date = args.date
    hot_path = data_dir / "runs" / date / "hot_candidates.jsonl"
    input_path = Path(args.input)

    state = load_run_state(data_dir, date)

    if not hot_path.exists():
        add_error(state, COMMAND_NAME, "missing_input", f"missing hot candidates: {hot_path}")
        save_run_state(data_dir, date, state)
        print(f"missing hot candidates: {hot_path}")
        return 1

    if not input_path.exists():
        add_error(state, COMMAND_NAME, "missing_input", f"missing input file: {input_path}")
        save_run_state(data_dir, date, state)
        print(f"missing input file: {input_path}")
        return 1

    with input_path.open("r", encoding="utf-8") as handle:
        records = json.load(handle)

    if not isinstance(records, list):
        add_error(
            state,
            COMMAND_NAME,
            "invalid_input",
            "input file must contain a JSON array of article proposals",
        )
        save_run_state(data_dir, date, state)
        print("input file must contain a JSON array of article proposals")
        return 1

    selected_ids = {
        record["hot_id"] for record in read_jsonl(hot_path) if record.get("selected") is True
    }

    proposals: list[ArticleProposal] = []
    for index, record in enumerate(records):
        missing_fields = REQUIRED_FIELDS - set(record.keys())
        if missing_fields:
            message = f"proposal[{index}] missing fields: {', '.join(sorted(missing_fields))}"
            add_error(state, COMMAND_NAME, "invalid_proposal", message)
            save_run_state(data_dir, date, state)
            print(message)
            return 1

        proposal = ArticleProposal(**{key: record[key] for key in REQUIRED_FIELDS})

        if not proposal.evidence_links:
            message = f"proposal[{index}] must include at least one evidence link"
            add_error(state, COMMAND_NAME, "invalid_proposal", message)
            save_run_state(data_dir, date, state)
            print(message)
            return 1

        if proposal.source_hot_id not in selected_ids:
            message = (
                f"proposal[{index}] source_hot_id is not a selected HOT candidate: "
                f"{proposal.source_hot_id}"
            )
            add_error(state, COMMAND_NAME, "invalid_proposal", message)
            save_run_state(data_dir, date, state)
            print(message)
            return 1

        proposals.append(proposal)

    proposals_path = data_dir / "runs" / date / "article_proposals.jsonl"
    try:
        write_jsonl(proposals_path, proposals)
    except Exception as exc:  # noqa: BLE001
        add_error(state, COMMAND_NAME, "write_error", str(exc))
        save_run_state(data_dir, date, state)
        print(f"failed to write article proposals: {exc}")
        return 1

    state["output_counts"]["article_proposals"] = len(proposals)
    mark_stage_completed(state, COMMAND_NAME)
    save_run_state(data_dir, date, state)
    return 0
