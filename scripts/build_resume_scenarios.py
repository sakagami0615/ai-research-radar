"""再開のシナリオのテスト用データ(tests/fixtures/resume_scenarios/)を、実際のCLIで作り直す。

fixtureのSource(tests/fixtures/sample_raw_items.jsonl)で `collect` 〜 `report` と
`progress` を一時ディレクトリで実行し、シナリオごとに止まった時点の `data/` と
`reports/` をコピーする。スキーマの変更などでfixtureを作り直すときに使う
(既存のfixtureは消して作り直す)。作り直したら tests/test_progress_show.py を実行する。

    PYTHONPATH=src python scripts/build_resume_scenarios.py
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT = REPO_ROOT / "tests" / "fixtures" / "resume_scenarios"
# The fixture's items are published 2026-09-24, so the run covers 2026-09-24 .. 2026-09-25.
DATE = "2026-09-25"
SINCE = "2026-09-24"


def _cli(cwd: Path, *args: str, ok: bool = True) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}
    command = [sys.executable, "-m", "ai_research_radar.cli.main", *args, "--runtime-config", "none.yaml"]
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True)
    if ok and result.returncode != 0:
        raise SystemExit(f"{' '.join(args)}: exit {result.returncode}\n{result.stdout}{result.stderr}")
    return result


def _run_dir(cwd: Path) -> Path:
    return cwd / "data" / "runs" / DATE


def _prepare(cwd: Path) -> None:
    cwd.mkdir(parents=True)
    (cwd / "sources.yaml").write_text(
        "sources:\n"
        "  github:\n"
        "    enabled: true\n"
        "    family: technology\n"
        "    adapter: fixture\n"
        "    auth_required: false\n"
        f"    fixture_path: {REPO_ROOT / 'tests' / 'fixtures' / 'sample_raw_items.jsonl'}\n",
        encoding="utf-8",
    )
    # minimum_score 0 so that the fixture's items become HOT candidates.
    (cwd / "scoring.yaml").write_text(
        "hot_score:\n  momentum: 0.40\n  popularity: 0.25\n  cross_source: 0.20\n  credibility: 0.15\n"
        "hot_selection:\n  max_limit: 5\n  minimum_score: 0\n",
        encoding="utf-8",
    )


def _assessment(hot_id: str) -> dict[str, Any]:
    return {
        "hot_id": hot_id,
        "decision": "rejected",
        "assessed_at": f"{DATE}T01:00:00+00:00",
        "assessor": "agent",
        "relevance": {"status": "related", "matched_terms": ["agent"], "reason": "AIエージェントのツール", "method": "agent"},
        "novelty": "既知の内容",
        "importance": "低い",
        "reader_impact": "小さい",
        "reason": "一次情報で新規性を確認できない",
        "evidence": [],
        "unknowns": [],
    }


def _rejecting_all(hot_text: str) -> dict[str, Any]:
    ids = [json.loads(line)["hot_id"] for line in hot_text.splitlines() if line.strip()]
    return {
        "assessments": [_assessment(hot_id) for hot_id in ids],
        "screened_ids": ids,
        "selection_reason": "一次情報で新規性を確認できる候補がない",
        "summaries": {},
    }


def _select(cwd: Path, selection: dict[str, Any], *, ok: bool = True) -> int:
    (_run_dir(cwd) / "selection_input.json").write_text(json.dumps(selection, ensure_ascii=False, indent=2), encoding="utf-8")
    return _cli(cwd, "select-hot", "--date", DATE, "--data-dir", "data", "--input", f"data/runs/{DATE}/selection_input.json", ok=ok).returncode


def _progress(cwd: Path, *args: str) -> None:
    _cli(cwd, "progress", *args, "--date", DATE, "--data-dir", "data")


def _review(cwd: Path, attempt: int, *, feedback: bool) -> None:
    dirs = ["--data-dir", "data", "--reports-dir", "reports"]
    _cli(cwd, "progress", "review", "--date", DATE, "--attempt", str(attempt), "--start", *dirs)
    feedback_path = _run_dir(cwd) / "review_feedback.md"
    if feedback:
        feedback_path.write_text(f"# レビュー指摘(試行{attempt})\n\n- Important: 本日の傾向が未作成のSourceがある。\n", encoding="utf-8")
    else:
        feedback_path.unlink(missing_ok=True)
    _cli(cwd, "progress", "review", "--date", DATE, "--attempt", str(attempt), "--result", *dirs)


def _upto_score(cwd: Path) -> None:
    _prepare(cwd)
    _cli(cwd, "collect", "--since", SINCE, "--until", DATE, "--sources-config", "sources.yaml", "--data-dir", "data")
    _cli(cwd, "normalize", "--date", DATE, "--data-dir", "data")
    _cli(cwd, "score", "--date", DATE, "--data-dir", "data", "--scoring-config", "scoring.yaml")


def _upto_selection(cwd: Path) -> None:
    _upto_score(cwd)
    _select(cwd, _rejecting_all((_run_dir(cwd) / "hot_candidates.jsonl").read_text(encoding="utf-8")))


def _upto_report(cwd: Path) -> None:
    _upto_selection(cwd)
    (_run_dir(cwd) / "draft_proposals.json").write_text('{"schema_version": 2, "proposals": []}\n', encoding="utf-8")
    _cli(cwd, "save-proposals", "--date", DATE, "--data-dir", "data", "--input", f"data/runs/{DATE}/draft_proposals.json")
    _cli(cwd, "report", "--date", DATE, "--data-dir", "data", "--reports-dir", "reports")


def done(cwd: Path) -> None:
    approved_not_completed(cwd)
    _progress(cwd, "complete")


def deterministic_only(cwd: Path) -> None:
    _prepare(cwd)
    _cli(cwd, "daily", "--since", SINCE, "--until", DATE, "--sources-config", "sources.yaml", "--scoring-config", "scoring.yaml",
         "--data-dir", "data", "--reports-dir", "reports")


def review2_changes_requested(cwd: Path) -> None:
    _upto_report(cwd)
    _review(cwd, 1, feedback=True)
    _review(cwd, 2, feedback=True)


def corrupt_input(cwd: Path) -> None:
    """hot_candidates.jsonl is left cut off part way through a record, and select-hot records corrupt_input."""
    _upto_score(cwd)
    hot = _run_dir(cwd) / "hot_candidates.jsonl"
    text = hot.read_text(encoding="utf-8")
    selection = _rejecting_all(text)
    hot.write_text(text[: len(text) * 2 // 3], encoding="utf-8")
    assert _select(cwd, selection, ok=False) == 1


def retry_limit_reached(cwd: Path) -> None:
    """select-hot fails on an invalid input, and three fix reruns (the limit) fail too."""
    _upto_score(cwd)
    invalid = {"assessments": [], "selection_reason": "", "summaries": {}}
    assert _select(cwd, invalid, ok=False) == 1
    for _ in range(3):
        _progress(cwd, "retry", "--stage", "select-hot")
        assert _select(cwd, invalid, ok=False) == 1


def approved_not_completed(cwd: Path) -> None:
    _upto_report(cwd)
    _review(cwd, 1, feedback=False)


def review3_changes_requested(cwd: Path) -> None:
    review2_changes_requested(cwd)
    _review(cwd, 3, feedback=True)


def finalize_interrupted(cwd: Path) -> None:
    """Stopped in step 10 after `progress finalize` and `mark-needs-review`, before the report is rebuilt."""
    review3_changes_requested(cwd)
    _progress(cwd, "finalize")
    _cli(cwd, "mark-needs-review", "--date", DATE, "--data-dir", "data")


SCENARIOS: dict[str, Callable[[Path], None]] = {
    "01_done": done,
    "02_deterministic_only": deterministic_only,
    "03_after_score": _upto_score,
    "04_after_selection": _upto_selection,
    "05_after_report": _upto_report,
    "06_review2_changes_requested": review2_changes_requested,
    "07_corrupt_input": corrupt_input,
    "08_retry_limit_reached": retry_limit_reached,
    "09_approved_not_completed": approved_not_completed,
    "10_review3_changes_requested": review3_changes_requested,
    "11_finalize_interrupted": finalize_interrupted,
}


def main() -> int:
    # Everything is built first, so a failure part way leaves the current fixtures as they are.
    with tempfile.TemporaryDirectory() as build_dir:
        built = Path(build_dir) / "resume_scenarios"
        for name, build in SCENARIOS.items():
            cwd = Path(build_dir) / "work" / name
            build(cwd)
            for sub in ("data", "reports"):
                if (cwd / sub).exists():
                    shutil.copytree(cwd / sub, built / name / sub)
            print(name)
        if OUT.exists():
            shutil.rmtree(OUT)
        shutil.copytree(built, OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
