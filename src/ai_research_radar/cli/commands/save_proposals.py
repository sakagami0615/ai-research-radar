from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ai_research_radar.cli.commands.common import add_runtime_arguments, data_dir as resolve_data_dir, fail
from ai_research_radar.storage.run_state import (
    load_run_state,
    mark_stage_completed,
    reset_errors_for,
    save_run_state,
    set_stage_result,
)
from ai_research_radar.ideation.validation import REQUIRED_FIELDS, validate_proposals
from ai_research_radar.schemas.decoders import decode_hot
from ai_research_radar.schemas.models import ArticleProposal
from ai_research_radar.storage.jsonl import JsonlReadError, read_decoded_jsonl, write_jsonl

COMMAND_NAME = "save-proposals"
NO_SELECTION_REASON = "選抜HOTなし"
_ALLOWED_KEYS = frozenset({"schema_version", "proposals", "deferral_reason"})


def _structure_error(payload: object) -> str | None:
    if not isinstance(payload, dict):
        return "input file must contain a JSON object"
    unknown = sorted(set(payload) - _ALLOWED_KEYS)
    if unknown:
        return f"unknown top-level key(s): {', '.join(unknown)}"
    version = payload.get("schema_version")
    if type(version) is not int or version != 2:
        return f"schema_version must be the integer 2: {version!r}"
    if not isinstance(payload.get("proposals"), list):
        return "proposals must be a list"
    return None


def _deferral_error(payload: dict, has_selection: bool) -> str | None:
    """deferral_reason は「選抜HOTあり・企画0件」のときだけ必須で、それ以外は書いてはならない。"""
    required = has_selection and not payload["proposals"]
    if not required:
        if "deferral_reason" in payload:
            return "deferral_reason must not be given unless selected HOT exist and proposals is empty"
        return None
    reason = payload.get("deferral_reason")
    if not isinstance(reason, str) or not reason.strip():
        return "deferral_reason must be a non-empty string when selected HOT exist and proposals is empty"
    return None


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(COMMAND_NAME)
    parser.add_argument("--date", required=True)
    parser.add_argument("--input", required=True)
    add_runtime_arguments(parser)
    parser.set_defaults(func=run)


def _fail(state: dict[str, Any], data_dir: Path, date: str, error_type: str, message: str) -> int:
    return fail(state, data_dir, date, COMMAND_NAME, error_type, message, record_stage_result=True)


def run(args: argparse.Namespace) -> int:
    data_dir = resolve_data_dir(args)
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
        payload = json.loads(input_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return _fail(state, data_dir, date, "invalid_input", f"input file is not valid JSON: {exc}")
    except (OSError, UnicodeDecodeError) as exc:
        return _fail(state, data_dir, date, "invalid_input", f"cannot read input file {input_path}: {exc}")

    structure_error = _structure_error(payload)
    if structure_error:
        return _fail(state, data_dir, date, "invalid_input", structure_error)

    try:
        candidates = read_decoded_jsonl(hot_path, decode_hot)
    except JsonlReadError as exc:
        return _fail(state, data_dir, date, "corrupt_input", str(exc))
    has_selection = any(candidate.selected for candidate in candidates)
    deferral_error = _deferral_error(payload, has_selection)
    if deferral_error:
        return _fail(state, data_dir, date, "invalid_input", deferral_error)

    try:
        records = validate_proposals(payload["proposals"], candidates)
    except ValueError as exc:
        return _fail(state, data_dir, date, "invalid_proposal", str(exc))
    proposals = [
        ArticleProposal(**{key: record[key] for key in REQUIRED_FIELDS}, schema_version=2, quality=record["quality"])
        for record in records
    ]

    proposals_path = data_dir / "runs" / date / "article_proposals.jsonl"
    try:
        write_jsonl(proposals_path, proposals)
    except (OSError, ValueError) as exc:  # ValueError: e.g. text that cannot be encoded
        return _fail(state, data_dir, date, "write_error", f"failed to write article proposals: {exc}")

    if not has_selection:
        status, reason = "not_run", NO_SELECTION_REASON
    elif proposals:
        status, reason = "completed", ""
    else:
        status, reason = "deferred", payload["deferral_reason"].strip()
    set_stage_result(state, COMMAND_NAME, status, reason, proposal_count=len(proposals))
    state["output_counts"]["article_proposals"] = len(proposals)
    mark_stage_completed(state, COMMAND_NAME)
    save_run_state(data_dir, date, state)
    return 0
