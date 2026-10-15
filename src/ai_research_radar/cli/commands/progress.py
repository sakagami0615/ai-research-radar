from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from typing import Any

from ai_research_radar.cli.commands.common import (
    add_runtime_arguments,
    data_dir as resolve_data_dir,
    reports_dir as resolve_reports_dir,
)
from ai_research_radar.storage.agent_progress import (
    DAY_WIDE_KINDS,
    FIX,
    FIX_LIMITS,
    MAX_REVIEW_ATTEMPTS,
    agent_progress,
    review_artifact_hashes,
    retry_count,
    retry_limit,
    review_feedback_path,
    write_review_target,
)
from ai_research_radar.storage.run_state import load_run_state, run_state_path, save_run_state

COMMAND_NAME = "progress"


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(COMMAND_NAME)
    actions = parser.add_subparsers(dest="progress_command", required=True)

    review = actions.add_parser("review")
    review.add_argument("--date", required=True)
    # Parsed by _review() so that a non-integer ends with exit code 1 like an out-of-range number.
    review.add_argument("--attempt", required=True)
    phase = review.add_mutually_exclusive_group(required=True)
    phase.add_argument("--start", action="store_true")
    phase.add_argument("--result", action="store_true")
    review.add_argument("--launch-failed", action="store_true")
    add_runtime_arguments(review, reports_dir=True)
    review.set_defaults(func=_run(_review))

    retry = actions.add_parser("retry")
    retry.add_argument("--date", required=True)
    retry.add_argument("--stage", required=True, choices=list(FIX_LIMITS))
    retry.add_argument("--kind", choices=list(DAY_WIDE_KINDS))
    add_runtime_arguments(retry)
    retry.set_defaults(func=_run(_retry))

    for name, key in (("finalize", "finalized_at"), ("complete", "completed_at")):
        marker = actions.add_parser(name)
        marker.add_argument("--date", required=True)
        add_runtime_arguments(marker)
        marker.set_defaults(func=_run(_marker(key)))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _error(message: str) -> int:
    print(f"error: {message}", file=sys.stderr)
    return 1


def _run(record):
    """Load run_state.json, let `record` update agent_progress, and save it when it returns 0.

    A missing run_state.json is an error rather than a new run (a typo in
    --date must not look successful). An unreadable one raises RunStateError,
    which main() turns into exit code 1.
    """

    def run(args: argparse.Namespace) -> int:
        data_dir = resolve_data_dir(args)
        if not run_state_path(data_dir, args.date).exists():
            return _error(f"no run_state.json for {args.date} under {data_dir}")
        # stage_results is not filled in: progress only changes agent_progress.
        state = load_run_state(data_dir, args.date, fill_stage_results=False)
        code = record(args, state, agent_progress(state))
        if code == 0:
            save_run_state(data_dir, args.date, state)
        return code

    return run


def _review(args: argparse.Namespace, state: dict[str, Any], progress: dict[str, Any]) -> int:
    # Only plain ASCII digits: int() would also accept "２", "+1" or " 1".
    attempt = int(args.attempt) if args.attempt.isascii() and args.attempt.isdigit() else 0
    if not 1 <= attempt <= MAX_REVIEW_ATTEMPTS:
        return _error(f"--attempt must be an integer from 1 to {MAX_REVIEW_ATTEMPTS}: {args.attempt!r}")
    attempts = progress["review_attempts"]
    last = attempts[-1] if attempts else None

    if args.start:
        if args.launch_failed:
            return _error("--launch-failed is given with --result, not with --start")
        if any(record["attempt"] == attempt for record in attempts):
            return _error(f"review attempt {attempt} has already been started")
        expected = last["attempt"] + 1 if last else 1
        if attempt != expected:
            return _error(f"the next review attempt is {expected}, not {attempt}")
        data_dir = resolve_data_dir(args)
        try:
            artifacts = review_artifact_hashes(data_dir, resolve_reports_dir(args), args.date)
        except OSError as exc:
            return _error(f"failed to read a review artifact: {exc}")
        try:
            write_review_target(data_dir, args.date, attempt, artifacts)
        except OSError as exc:
            return _error(f"failed to write review_target.json: {exc}")
        record = {"attempt": attempt, "status": "started", "started_at": _now()}
        attempts.append(record)
    else:
        if last is None or last["attempt"] != attempt:
            if any(record["attempt"] == attempt for record in attempts):
                return _error(f"review attempt {attempt} is not the last attempt")
            return _error(f"review attempt {attempt} has not been started (run --start first)")
        if last["status"] != "started":
            return _error(f"review attempt {attempt} already has a result: {last['status']}")
        record = last
        if args.launch_failed:
            record["status"] = "failed"
        elif review_feedback_path(resolve_data_dir(args), args.date).exists():
            record["status"] = "changes_requested"
        else:
            record["status"] = "approved"
        record["finished_at"] = _now()
    print(json.dumps({"attempt": record["attempt"], "status": record["status"]}, ensure_ascii=False))
    return 0


def _retry(args: argparse.Namespace, state: dict[str, Any], progress: dict[str, Any]) -> int:
    kind = args.kind or FIX
    if kind in DAY_WIDE_KINDS and args.stage not in (stages := DAY_WIDE_KINDS[kind][1]):
        return _error(f"a {kind} rerun starts from {' / '.join(stages)}, not from {args.stage}")
    # Recorded even past the limit; whether to stop is up to the skill.
    progress["retries"].append({"stage": args.stage, "kind": kind, "recorded_at": _now()})
    count, limit = retry_count(progress, args.stage, kind), retry_limit(args.stage, kind)
    # allowed: this rerun is within the limit. limit_reached: no more reruns after this one
    # (the stage is no longer returned to on resume).
    result = {
        "stage": args.stage,
        "kind": kind,
        "count": count,
        "limit": limit,
        "allowed": count <= limit,
        "limit_reached": count >= limit,
    }
    print(json.dumps(result, ensure_ascii=False))
    return 0


def _marker(key: str):
    def record(args: argparse.Namespace, state: dict[str, Any], progress: dict[str, Any]) -> int:
        # Overwritten when step 10 or the completion is recorded again (e.g. after a resume).
        progress[key] = _now()
        return 0

    return record
