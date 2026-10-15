"""Where a stopped agent run resumes on the same day (`ai-radar progress show`).

The rows of the table in docs/spec/03-detailed-design/cli/commands.md
("progress show") are applied from the top, and the first match decides the
step. A stage whose self-fix reruns have reached the limit is not returned to
even when its failure is still recorded (the skill moves on at the limit, so
returning would loop on every resume); such rows are listed in `skipped`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ai_research_radar.schemas.decoders import decode_event, decode_hot, decode_proposal, decode_signal
from ai_research_radar.schemas.models import NO_SELECTION_REASON, valid_stage_result
from ai_research_radar.storage.agent_progress import (
    CORRUPT_INPUT,
    DAY_WIDE_KINDS,
    FIX,
    FIX_LIMITS,
    MAX_REVIEW_ATTEMPTS,
    agent_progress,
    retry_count,
    retry_limit,
    review_artifact_hashes,
    review_feedback_path,
    review_target_path,
)
from ai_research_radar.storage.jsonl import JsonlReadError, read_decoded_jsonl, read_jsonl
from ai_research_radar.storage.run_state import load_run_state, run_state_path

# Stages that have no stage_results, judged by stages_completed and errors, with their step.
EARLY_STAGES = (("collect", 1), ("normalize", 2), ("score", 3))
SELECT_HOT_STEP = 4
PROPOSALS_STEP = 6
REPORT_STEP = 8
REVIEW_STEP = 9
FINALIZE_STEP = 10


def _outputs(date: str) -> dict[str, tuple[str, Any]]:
    """A corrupt file (path relative to data_dir) -> the stage that rebuilds it (recovery.md) and its decoder."""
    return {
        f"collected/{date}/signals.jsonl": ("collect", decode_signal),
        f"normalized/{date}/signals.jsonl": ("normalize", decode_signal),
        f"events/{date}/events.jsonl": ("normalize", decode_event),
        f"runs/{date}/hot_candidates.jsonl": ("score", decode_hot),
        f"runs/{date}/article_proposals.jsonl": ("save-proposals", decode_proposal),
    }


class _Corruption:
    """The corrupt_input records of the day, checked against the files as they are now.

    A record whose file reads (and decodes) cleanly now is stale: the file was
    rebuilt after the record, so the writing stage is not returned to, and the
    reading stage has to be run again (not skipped at the rebuild limit, since
    its rerun is part of the rebuild that already used the limit).
    """

    def __init__(self, data_dir: Path, date: str, errors: list[dict[str, Any]]) -> None:
        self._outputs = _outputs(date)
        self._data_dir = data_dir
        self._broken: dict[str, bool] = {}
        self.records = [error for error in errors if error.get("type") == CORRUPT_INPUT]

    def is_broken(self, path: str) -> bool:
        if path not in self._broken:
            target = self._data_dir / path
            try:
                read_decoded_jsonl(target, self._outputs[path][1])
                self._broken[path] = False
            except JsonlReadError:
                # Also a missing file (OSError while opening): it has not been rebuilt.
                self._broken[path] = True
        return self._broken[path]

    def rebuilt_by(self, stage: str) -> bool:
        """Whether a still broken output of `stage` is named by a record (the stage must rebuild it)."""
        return any(
            self._mapped(record) and self._outputs[record["path"]][0] == stage and self.is_broken(record["path"])
            for record in self.records
        )

    def reader_kind(self, source: str) -> str | None:
        """The limit for a stage that failed reading a corrupt input, None if all its inputs are fixed now.

        A record without a known `path` (older records, other days) cannot be checked and keeps the limit.
        """
        own = [record for record in self.records if record.get("source") == source]
        if any(not self._mapped(record) or self.is_broken(record["path"]) for record in own):
            return CORRUPT_INPUT
        return None

    def _mapped(self, record: dict[str, Any]) -> bool:
        return isinstance(record.get("path"), str) and record["path"] in self._outputs


def resume_point(data_dir: Path, reports_dir: Path, date: str) -> dict[str, Any]:
    """The records and the step to resume from, as printed by `progress show`.

    Raises RunStateError when run_state.json or its agent_progress cannot be
    read, and OSError when a review artifact cannot be read for the hash check.
    """
    if not run_state_path(data_dir, date).exists():
        # `ai-radar daily` writes no run_state.json, so a day with only its records lands here too.
        return _result(date, {"review_attempts": [], "retries": []}, _next("resume", "no_run_state", step=1, stage="collect"), [])
    state = load_run_state(data_dir, date, fill_stage_results=False)
    progress = agent_progress(state)
    skipped: list[dict[str, Any]] = []
    return _result(date, progress, _judge(data_dir, reports_dir, date, state, progress, skipped), skipped)


def _judge(
    data_dir: Path,
    reports_dir: Path,
    date: str,
    state: dict[str, Any],
    progress: dict[str, Any],
    skipped: list[dict[str, Any]],
) -> dict[str, Any]:
    report = reports_dir / "daily" / f"{date}.md"
    if "completed_at" in progress and report.exists() and _has_agent_run(data_dir, date):
        return _next("done", "done")

    errors = [error for error in state.get("errors", []) if isinstance(error, dict)] if isinstance(state.get("errors"), list) else []
    completed = state.get("stages_completed") if isinstance(state.get("stages_completed"), list) else []
    corrupt = _Corruption(data_dir, date, errors)
    results = state.get("stage_results") if isinstance(state.get("stage_results"), dict) else {}

    for stage, step in EARLY_STAGES:
        reasons = _early_stage_reasons(stage, completed, errors, corrupt)
        reason = _first_open(progress, stage, reasons, skipped)
        if reason is not None:
            return _next("resume", reason, step=step, stage=stage)

    if "finalized_at" in progress:
        return _next("resume", "finalized", step=FINALIZE_STEP)

    for stage, step, done in (
        ("select-hot", SELECT_HOT_STEP, _select_hot_done),
        ("save-proposals", PROPOSALS_STEP, _proposals_done),
    ):
        reasons = _result_stage_reasons(stage, results, completed, corrupt, done)
        reason = _first_open(progress, stage, reasons, skipped)
        if reason is not None:
            return _next("resume", reason, step=step, stage=stage)

    attempts = progress["review_attempts"]
    last = attempts[-1] if attempts else None
    next_attempt = last["attempt"] + 1 if last else 1
    attempt = next_attempt if next_attempt <= MAX_REVIEW_ATTEMPTS else None
    if not report.exists():
        return _next("resume", "report_missing", step=REPORT_STEP, attempt=attempt)
    target_reason = _review_target_problem(data_dir, reports_dir, date, last)
    if target_reason is not None:
        return _next("resume", target_reason, step=REPORT_STEP, attempt=attempt)
    if last is not None and last["status"] == "approved":
        return _next("complete", "approved")
    if last is not None and last["attempt"] == MAX_REVIEW_ATTEMPTS:
        return _next("resume", "review_attempts_exhausted", step=FINALIZE_STEP)
    # The hashes match, so feedback left by a changes_requested attempt has not been dealt with yet.
    pending = last is not None and last["status"] == "changes_requested" and review_feedback_path(data_dir, date).exists()
    return _next("resume", "next_review", step=REVIEW_STEP, attempt=attempt, feedback_pending=pending)


def _has_agent_run(data_dir: Path, date: str) -> bool:
    path = data_dir / "runs" / date / "run.jsonl"
    if not path.exists():
        return False
    try:
        records = read_jsonl(path)
    except JsonlReadError:
        return False
    return any(record.get("mode") == "agent" for record in records)


def _early_stage_reasons(stage: str, completed: list[Any], errors: list[dict[str, Any]], corrupt: _Corruption) -> list[tuple[str, str | None]]:
    """(reason, kind whose limit lets the row be skipped, or None if it is never skipped), in the order checked."""
    reasons: list[tuple[str, str | None]] = []
    if corrupt.rebuilt_by(stage):
        reasons.append((CORRUPT_INPUT, CORRUPT_INPUT))
    own = [error for error in errors if error.get("source") == stage]
    if own:
        reasons.append(("command_error", _failure_kind(stage, any(error.get("type") == CORRUPT_INPUT for error in own), corrupt)))
    elif stage not in completed:
        reasons.append(("not_completed", None))
    return reasons


def _failure_kind(stage: str, on_corrupt_input: bool, corrupt: _Corruption) -> str | None:
    """A failure on a corrupt input follows the rebuild limit, unless the input reads fine now (see _Corruption)."""
    return corrupt.reader_kind(stage) if on_corrupt_input else FIX


def _result_stage_reasons(stage: str, results: dict[str, Any], completed: list[Any], corrupt: _Corruption, done) -> list[tuple[str, str | None]]:
    reasons: list[tuple[str, str | None]] = []
    if corrupt.rebuilt_by(stage):
        reasons.append((CORRUPT_INPUT, CORRUPT_INPUT))
    result = valid_stage_result(results.get(stage))
    if result is None:
        # The old format ("記録なし": in stages_completed without stage_results) counts as done, as in step 8d.
        if stage not in completed:
            reasons.append(("not_run", None))
    elif not done(result):
        if result["status"] == "failed":
            reason = result.get("reason")
            on_corrupt_input = isinstance(reason, str) and reason.startswith(f"{CORRUPT_INPUT}:")
            reasons.append(("failed", _failure_kind(stage, on_corrupt_input, corrupt)))
        else:
            reasons.append((result["status"], None))
    return reasons


def _select_hot_done(result: dict[str, Any]) -> bool:
    return result["status"] in ("completed", "deferred")


def _proposals_done(result: dict[str, Any]) -> bool:
    return result["status"] in ("completed", "deferred") or (
        result["status"] == "not_run" and result.get("reason") == NO_SELECTION_REASON
    )


def _first_open(progress: dict[str, Any], stage: str, reasons: list[tuple[str, str | None]], skipped: list[dict[str, Any]]) -> str | None:
    """The first reason that still sends the run back to the stage, noting those skipped at the limit."""
    for reason, kind in reasons:
        if kind is None:
            return reason
        count, limit = retry_count(progress, stage, kind), retry_limit(stage, kind)
        if count < limit:
            return reason
        entry = {"stage": stage, "kind": kind, "reason": reason, "count": count, "limit": limit}
        if entry not in skipped:
            skipped.append(entry)
    return None


def _review_target_problem(data_dir: Path, reports_dir: Path, date: str, last: dict[str, Any] | None) -> str | None:
    """Why review_target.json cannot vouch for the artifacts under review, or None if it can."""
    path = review_target_path(data_dir, date)
    if not path.exists():
        return "review_target_missing"
    try:
        target = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return "review_target_unreadable"
    if not isinstance(target, dict):
        return "review_target_unreadable"
    # `progress review --start` writes the file before run_state.json, so a failed save can
    # leave a target for an attempt that agent_progress does not have.
    if last is None or target.get("attempt") != last["attempt"]:
        return "review_target_attempt_mismatch"
    if target.get("artifacts") != review_artifact_hashes(data_dir, reports_dir, date):
        return "review_target_stale"
    return None


def _next(action: str, reason: str, *, step: int | None = None, stage: str | None = None, attempt: int | None = None, feedback_pending: bool = False) -> dict[str, Any]:
    return {
        "action": action,
        "step": step,
        "stage": stage,
        "attempt": attempt,
        "feedback_pending": feedback_pending,
        "reason": reason,
    }


def _retries(progress: dict[str, Any]) -> list[dict[str, Any]]:
    """The counts in the shape of `progress retry`'s output (without `allowed`, which is about one rerun).

    Day-wide kinds have `stage: null`: they are counted over the day whatever
    stage a record names (the stored stage is not checked against the kind).
    """
    rows = []
    for stage in FIX_LIMITS:
        count, limit = retry_count(progress, stage, FIX), retry_limit(stage, FIX)
        rows.append({"stage": stage, "kind": FIX, "count": count, "limit": limit, "limit_reached": count >= limit})
    for kind, (limit, _stages) in DAY_WIDE_KINDS.items():
        count = retry_count(progress, "", kind)
        rows.append({"stage": None, "kind": kind, "count": count, "limit": limit, "limit_reached": count >= limit})
    return rows


def _result(date: str, progress: dict[str, Any], next_step: dict[str, Any], skipped: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "date": date,
        "next": next_step,
        "skipped": skipped,
        "retries": _retries(progress),
        "review_attempts": progress["review_attempts"],
        "finalized_at": progress.get("finalized_at"),
        "completed_at": progress.get("completed_at"),
    }
