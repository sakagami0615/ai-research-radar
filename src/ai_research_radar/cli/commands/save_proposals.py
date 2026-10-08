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
from ai_research_radar.ideation.validation import REQUIRED_FIELDS, validate_proposals
from ai_research_radar.schemas.decoders import decode_hot
from ai_research_radar.schemas.models import ArticleProposal
from ai_research_radar.storage.jsonl import read_jsonl, write_jsonl

COMMAND_NAME = "save-proposals"
NO_SELECTION_REASON = "選抜HOTなし"
_ALLOWED_KEYS = frozenset({"schema_version", "proposals", "deferral_reason"})
_MIGRATION_MESSAGE = (
    "入力が v2 形式ではありません(旧形式など)。{\"schema_version\": 2, \"proposals\": [...], \"deferral_reason\": \"...\"} の"
    "オブジェクト形式にし、各企画に \"schema_version\": 2 と quality を書いてください"
    "(deferral_reason は選抜HOTがあり企画が0件のときだけ書く)"
)


def _is_v2(value: dict) -> bool:
    version = value.get("schema_version")
    return type(version) is int and version == 2


def _legacy_reason(payload: object) -> str | None:
    """旧形式(v2への移行が必要)なら理由を返す。v2の判定ができない形は invalid_input に任せる。"""
    if isinstance(payload, list):
        return "input is a JSON array"
    if not isinstance(payload, dict):
        return None
    if not _is_v2(payload):
        return f"top-level schema_version is not 2: {payload.get('schema_version')!r}"
    proposals = payload.get("proposals")
    if isinstance(proposals, list):
        for index, record in enumerate(proposals):
            if isinstance(record, dict) and not _is_v2(record):
                return f"proposal[{index}] schema_version is not 2: {record.get('schema_version')!r}"
    return None


def _structure_error(payload: object) -> str | None:
    if not isinstance(payload, dict):
        return "input file must contain a JSON object"
    unknown = sorted(set(payload) - _ALLOWED_KEYS)
    if unknown:
        return f"unknown top-level key(s): {', '.join(unknown)}"
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
        payload = json.loads(input_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return _fail(state, data_dir, date, "invalid_input", f"input file is not valid JSON: {exc}")
    except (OSError, UnicodeDecodeError) as exc:
        return _fail(state, data_dir, date, "invalid_input", f"cannot read input file {input_path}: {exc}")

    legacy = _legacy_reason(payload)
    if legacy:
        return _fail(state, data_dir, date, "deprecated_input", f"{_MIGRATION_MESSAGE}: {legacy}")
    structure_error = _structure_error(payload)
    if structure_error:
        return _fail(state, data_dir, date, "invalid_input", structure_error)

    candidates = [decode_hot(record) for record in read_jsonl(hot_path)]
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
    except Exception as exc:  # noqa: BLE001
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
