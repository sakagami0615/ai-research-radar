"""The agent's progress through the daily run, kept in run_state.json's `agent_progress`.

`ai-radar progress` records review attempts, self-fix reruns, entering step 10
(finalize) and completing the day, so that a run stopped part way (e.g. by a
rate limit) can be resumed on the same day. The counts cover the whole day:
nothing here is cleared by `collect`.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ai_research_radar.storage.files import atomic_write_text
from ai_research_radar.storage.run_state import RunStateError

REVIEW_TARGET_FILENAME = "review_target.json"
REVIEW_FEEDBACK_FILENAME = "review_feedback.md"

MAX_REVIEW_ATTEMPTS = 3
REVIEW_STATUSES = ("started", "approved", "changes_requested", "failed")

FIX = "fix"
CORRUPT_INPUT = "corrupt_input"
# Self-fix reruns allowed per stage over the whole day. The numbers are owned here and by the
# limits table of docs/spec/03-detailed-design/cli/commands.md (recovery.md does not repeat them).
# collect / normalize / score fail for environment reasons that a rerun rarely fixes,
# so they get one rerun (e.g. after correcting a mistyped argument).
FIX_LIMITS = {
    "collect": 1,
    "normalize": 1,
    "score": 1,
    "select-hot": 3,
    "save-proposals": 3,
    "add-summary": 3,
    "add-source-overview": 3,
}
# Rebuilding a corrupt input is allowed once over the whole day, whichever stage it starts from.
CORRUPT_INPUT_LIMIT = 1
# Stages a corrupt input is rebuilt from (the "再実行を始めるステージ" of recovery.md).
CORRUPT_INPUT_STAGES = ("collect", "normalize", "score", "save-proposals")
SELECTION_MISMATCH = "selection_mismatch"
# Rerunning after report's selection_mismatch is allowed once over the whole day,
# counted apart from the corrupt input rebuild (Issue #21).
SELECTION_MISMATCH_LIMIT = 1
# select-hot when the selection is redone (from step 4), score when hot_candidates.jsonl is missing.
SELECTION_MISMATCH_STAGES = ("score", "select-hot")
# Kinds counted over the whole day rather than per stage: limit and the stages a rerun starts from.
DAY_WIDE_KINDS = {
    CORRUPT_INPUT: (CORRUPT_INPUT_LIMIT, CORRUPT_INPUT_STAGES),
    SELECTION_MISMATCH: (SELECTION_MISMATCH_LIMIT, SELECTION_MISMATCH_STAGES),
}


def review_target_path(data_dir: Path, date: str) -> Path:
    return data_dir / "runs" / date / REVIEW_TARGET_FILENAME


def review_feedback_path(data_dir: Path, date: str) -> Path:
    return data_dir / "runs" / date / REVIEW_FEEDBACK_FILENAME


def review_artifact_hashes(data_dir: Path, reports_dir: Path, date: str) -> dict[str, dict[str, str | None]]:
    """SHA-256 of each artifact the review looks at, None for a missing file.

    Paths are relative to data_dir / reports_dir. `progress review --start`
    writes this into review_target.json, and the resume check compares it with
    the artifacts as they are now, so both must use this function.
    evidence_fetch_log.tsv is left out: the agent keeps appending to it.
    """
    data_files = [
        f"runs/{date}/hot_candidates.jsonl",
        f"runs/{date}/article_proposals.jsonl",
        f"runs/{date}/selection_input.json",
        f"runs/{date}/digest_summaries.json",
        f"runs/{date}/source_overviews.json",
    ]
    report_files = [f"daily/{date}.md"]
    return {
        "data_dir": {path: _sha256(data_dir / path) for path in data_files},
        "reports_dir": {path: _sha256(reports_dir / path) for path in report_files},
    }


def _sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_review_target(data_dir: Path, date: str, attempt: int, artifacts: dict[str, dict[str, str | None]]) -> None:
    """`artifacts` is review_artifact_hashes() at the start of the attempt."""
    target = {"attempt": attempt, "artifacts": artifacts}
    atomic_write_text(review_target_path(data_dir, date), json.dumps(target, ensure_ascii=False, sort_keys=True, indent=2))


def agent_progress(state: dict[str, Any]) -> dict[str, Any]:
    """The `agent_progress` of the state, created empty on first use.

    A record that is not in the expected shape raises RunStateError, like a
    broken run_state.json, since the counts can no longer be trusted.
    """
    progress = state.setdefault("agent_progress", {"review_attempts": [], "retries": []})
    if not isinstance(progress, dict):
        raise RunStateError("agent_progress in run_state.json is not an object")
    attempts = progress.setdefault("review_attempts", [])
    retries = progress.setdefault("retries", [])
    if not isinstance(attempts, list) or not all(_valid_attempt(record) for record in attempts):
        raise RunStateError("agent_progress.review_attempts in run_state.json is malformed")
    numbers = [record["attempt"] for record in attempts]
    if numbers != sorted(set(numbers)):
        raise RunStateError("agent_progress.review_attempts in run_state.json is not in ascending order without duplicates")
    if not isinstance(retries, list) or not all(_valid_retry(record) for record in retries):
        raise RunStateError("agent_progress.retries in run_state.json is malformed")
    for key in ("finalized_at", "completed_at"):
        if key in progress and not isinstance(progress[key], str):
            raise RunStateError(f"agent_progress.{key} in run_state.json is not a string")
    return progress


def _valid_attempt(record: object) -> bool:
    if not isinstance(record, dict):
        return False
    attempt, status = record.get("attempt"), record.get("status")
    return (
        type(attempt) is int
        and 1 <= attempt <= MAX_REVIEW_ATTEMPTS
        and isinstance(status, str)
        and status in REVIEW_STATUSES
    )


def _valid_retry(record: object) -> bool:
    if not isinstance(record, dict):
        return False
    stage, kind = record.get("stage"), record.get("kind")
    return isinstance(stage, str) and stage in FIX_LIMITS and isinstance(kind, str) and (kind == FIX or kind in DAY_WIDE_KINDS)


def retry_count(progress: dict[str, Any], stage: str, kind: str) -> int:
    """Reruns recorded so far: per stage for a fix, over the whole day for the other kinds (each apart)."""
    if kind in DAY_WIDE_KINDS:
        return sum(1 for record in progress["retries"] if record["kind"] == kind)
    return sum(1 for record in progress["retries"] if record["kind"] == FIX and record["stage"] == stage)


def retry_limit(stage: str, kind: str) -> int:
    return DAY_WIDE_KINDS[kind][0] if kind in DAY_WIDE_KINDS else FIX_LIMITS[stage]
