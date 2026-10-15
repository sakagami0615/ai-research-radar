"""Issue #41: `ai-radar progress` records the agent's progress in run_state.json's agent_progress."""

import hashlib
import json
from pathlib import Path

import pytest

import ai_research_radar.cli.commands.collect as collect_command
import ai_research_radar.cli.commands.progress as progress_command
from ai_research_radar.cli.main import main
from ai_research_radar.sources.fixtures import FixtureAdapter
from ai_research_radar.storage.agent_progress import review_artifact_hashes
from ai_research_radar.storage.run_state import load_run_state, run_state_path, save_run_state

DATE = "2026-10-09"


def _setup(tmp_path: Path) -> tuple[Path, Path]:
    data_dir, reports_dir = tmp_path / "data", tmp_path / "reports"
    save_run_state(data_dir, DATE, load_run_state(data_dir, DATE))
    return data_dir, reports_dir


def _progress(data_dir: Path, *args: str, reports_dir: Path | None = None) -> int:
    command, *rest = args
    dirs = ["--data-dir", str(data_dir)]
    if reports_dir is not None:
        dirs += ["--reports-dir", str(reports_dir)]
    return main(["progress", command, "--date", DATE, *rest, *dirs])


def _review(data_dir: Path, reports_dir: Path, attempt: int | str, *flags: str) -> int:
    return _progress(data_dir, "review", "--attempt", str(attempt), *flags, reports_dir=reports_dir)


def _agent_progress(data_dir: Path) -> dict:
    return load_run_state(data_dir, DATE)["agent_progress"]


def _statuses(data_dir: Path) -> list[tuple[int, str]]:
    return [(record["attempt"], record["status"]) for record in _agent_progress(data_dir)["review_attempts"]]


def _last_json(capsys) -> dict:
    return json.loads(capsys.readouterr().out.strip().splitlines()[-1])


# --- progress review --start: review_target.json ---


def test_review_start_records_started_and_writes_hashes_of_the_six_artifacts(tmp_path: Path, capsys):
    data_dir, reports_dir = _setup(tmp_path)
    run_dir = data_dir / "runs" / DATE
    (run_dir / "hot_candidates.jsonl").write_text('{"hot_id": "a"}\n', encoding="utf-8")
    (run_dir / "selection_input.json").write_text("{}", encoding="utf-8")
    (run_dir / "evidence_fetch_log.tsv").write_text("url\tchecked_at\n", encoding="utf-8")
    report = reports_dir / "daily" / f"{DATE}.md"
    report.parent.mkdir(parents=True)
    report.write_text("# report\n", encoding="utf-8")

    assert _review(data_dir, reports_dir, 1, "--start") == 0

    record = _agent_progress(data_dir)["review_attempts"][0]
    assert (record["attempt"], record["status"]) == (1, "started") and "started_at" in record
    assert _last_json(capsys) == {"attempt": 1, "status": "started"}
    target = json.loads((run_dir / "review_target.json").read_text(encoding="utf-8"))
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()  # noqa: E731
    assert target == {
        "attempt": 1,
        "artifacts": {
            "data_dir": {
                f"runs/{DATE}/hot_candidates.jsonl": sha(run_dir / "hot_candidates.jsonl"),
                f"runs/{DATE}/article_proposals.jsonl": None,
                f"runs/{DATE}/selection_input.json": sha(run_dir / "selection_input.json"),
                f"runs/{DATE}/digest_summaries.json": None,
                f"runs/{DATE}/source_overviews.json": None,
            },
            "reports_dir": {f"daily/{DATE}.md": sha(report)},
        },
    }
    # The same function compares the artifacts as they are now (used by `progress show`).
    assert review_artifact_hashes(data_dir, reports_dir, DATE) == target["artifacts"]


def test_review_start_fails_without_recording_when_review_target_cannot_be_written(tmp_path: Path, capsys):
    data_dir, reports_dir = _setup(tmp_path)
    (data_dir / "runs" / DATE / "review_target.json").mkdir()

    assert _review(data_dir, reports_dir, 1, "--start") == 1

    assert "failed to write review_target.json" in capsys.readouterr().err
    assert "agent_progress" not in load_run_state(data_dir, DATE)


def test_review_start_reports_an_unreadable_artifact_as_a_read_error(tmp_path: Path, capsys):
    data_dir, reports_dir = _setup(tmp_path)
    (data_dir / "runs" / DATE / "hot_candidates.jsonl").mkdir()

    assert _review(data_dir, reports_dir, 1, "--start") == 1

    assert "failed to read a review artifact" in capsys.readouterr().err
    assert not (data_dir / "runs" / DATE / "review_target.json").exists()
    assert "agent_progress" not in load_run_state(data_dir, DATE)


def test_progress_does_not_fill_in_stage_results(tmp_path: Path):
    """Old data with stages_completed but no stage_results stays "記録なし"."""
    data_dir, _ = _setup(tmp_path)
    path = run_state_path(data_dir, DATE)
    state = json.loads(path.read_text(encoding="utf-8"))
    del state["stage_results"]
    state["stages_completed"] = ["collect", "normalize", "score", "select-hot", "save-proposals"]
    path.write_text(json.dumps(state), encoding="utf-8")

    assert _progress(data_dir, "complete") == 0

    assert "stage_results" not in json.loads(path.read_text(encoding="utf-8"))


def test_review_artifact_hashes_change_when_an_artifact_changes(tmp_path: Path):
    data_dir, reports_dir = _setup(tmp_path)
    before = review_artifact_hashes(data_dir, reports_dir, DATE)
    (data_dir / "runs" / DATE / "evidence_fetch_log.tsv").write_text("appended\n", encoding="utf-8")
    assert review_artifact_hashes(data_dir, reports_dir, DATE) == before

    (data_dir / "runs" / DATE / "source_overviews.json").write_text("{}", encoding="utf-8")
    assert review_artifact_hashes(data_dir, reports_dir, DATE) != before


def test_review_start_reads_reports_dir_from_runtime_config(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runtime = tmp_path / "runtime.yaml"
    runtime.write_text("output:\n  data_dir: custom_data\n  reports_dir: custom_reports\n", encoding="utf-8")
    data_dir = tmp_path / "custom_data"
    save_run_state(data_dir, DATE, load_run_state(data_dir, DATE))
    report = tmp_path / "custom_reports" / "daily" / f"{DATE}.md"
    report.parent.mkdir(parents=True)
    report.write_text("# report\n", encoding="utf-8")

    command = ["progress", "review", "--date", DATE, "--attempt", "1", "--start", "--runtime-config", str(runtime)]
    assert main(command) == 0

    target = json.loads((data_dir / "runs" / DATE / "review_target.json").read_text(encoding="utf-8"))
    assert target["artifacts"]["reports_dir"][f"daily/{DATE}.md"] == hashlib.sha256(report.read_bytes()).hexdigest()


# --- progress review --result: status ---


@pytest.mark.parametrize(
    ("feedback", "flags", "status"),
    [
        (False, [], "approved"),
        (True, [], "changes_requested"),
        (False, ["--launch-failed"], "failed"),
        (True, ["--launch-failed"], "failed"),
    ],
    ids=["no-feedback", "feedback", "launch-failed", "launch-failed-with-stale-feedback"],
)
def test_review_result_status_from_feedback_and_launch_failure(
    tmp_path: Path, capsys, feedback: bool, flags: list[str], status: str
):
    data_dir, reports_dir = _setup(tmp_path)
    assert _review(data_dir, reports_dir, 1, "--start") == 0
    if feedback:
        (data_dir / "runs" / DATE / "review_feedback.md").write_text("## Important\n", encoding="utf-8")

    assert _review(data_dir, reports_dir, 1, "--result", *flags) == 0

    record = _agent_progress(data_dir)["review_attempts"][0]
    assert record["status"] == status and "finished_at" in record
    assert _last_json(capsys) == {"attempt": 1, "status": status}


def test_review_attempts_are_counted_over_the_day_including_started(tmp_path: Path):
    data_dir, reports_dir = _setup(tmp_path)
    feedback = data_dir / "runs" / DATE / "review_feedback.md"
    feedback.write_text("## Important\n", encoding="utf-8")
    assert _review(data_dir, reports_dir, 1, "--start") == 0
    assert _review(data_dir, reports_dir, 1, "--result") == 0
    # Attempt 2 stops before its result (e.g. a rate limit); the resumed run starts attempt 3.
    assert _review(data_dir, reports_dir, 2, "--start") == 0
    assert _review(data_dir, reports_dir, 3, "--start") == 0
    feedback.unlink()
    assert _review(data_dir, reports_dir, 3, "--result") == 0

    assert _statuses(data_dir) == [(1, "changes_requested"), (2, "started"), (3, "approved")]
    target = json.loads((data_dir / "runs" / DATE / "review_target.json").read_text(encoding="utf-8"))
    assert target["attempt"] == 3


@pytest.mark.parametrize("attempt", ["0", "4", "x", "1.0", "２", "+1", " 1"])
def test_review_rejects_attempt_outside_1_to_3(tmp_path: Path, capsys, attempt: str):
    data_dir, reports_dir = _setup(tmp_path)

    assert _review(data_dir, reports_dir, attempt, "--start") == 1

    assert capsys.readouterr().err.startswith("error: --attempt")
    assert "agent_progress" not in load_run_state(data_dir, DATE)
    assert not (data_dir / "runs" / DATE / "review_target.json").exists()


def test_review_rejects_second_start_of_the_same_attempt(tmp_path: Path, capsys):
    data_dir, reports_dir = _setup(tmp_path)
    assert _review(data_dir, reports_dir, 1, "--start") == 0
    target = data_dir / "runs" / DATE / "review_target.json"
    written = target.read_bytes()
    (data_dir / "runs" / DATE / "hot_candidates.jsonl").write_text("{}\n", encoding="utf-8")

    assert _review(data_dir, reports_dir, 1, "--start") == 1

    assert "already been started" in capsys.readouterr().err
    assert _statuses(data_dir) == [(1, "started")]
    assert target.read_bytes() == written


def test_review_rejects_a_fourth_attempt_after_the_third_stopped_as_started(tmp_path: Path, capsys):
    """#30 scenario 10: no 4th review even when the 3rd attempt stopped before its result."""
    data_dir, reports_dir = _setup(tmp_path)
    for attempt in (1, 2, 3):
        assert _review(data_dir, reports_dir, attempt, "--start") == 0

    assert _review(data_dir, reports_dir, 4, "--start") == 1

    assert capsys.readouterr().err.startswith("error: --attempt")
    assert _statuses(data_dir) == [(1, "started"), (2, "started"), (3, "started")]


def test_review_rejects_start_that_skips_an_attempt(tmp_path: Path, capsys):
    data_dir, reports_dir = _setup(tmp_path)

    assert _review(data_dir, reports_dir, 2, "--start") == 1

    assert "the next review attempt is 1" in capsys.readouterr().err


def test_review_rejects_result_without_start(tmp_path: Path, capsys):
    data_dir, reports_dir = _setup(tmp_path)

    assert _review(data_dir, reports_dir, 1, "--result") == 1
    assert "has not been started" in capsys.readouterr().err

    assert _review(data_dir, reports_dir, 1, "--start") == 0
    assert _review(data_dir, reports_dir, 2, "--result") == 1
    assert "has not been started" in capsys.readouterr().err
    assert _statuses(data_dir) == [(1, "started")]


def test_review_rejects_second_result_and_result_of_an_earlier_attempt(tmp_path: Path, capsys):
    data_dir, reports_dir = _setup(tmp_path)
    assert _review(data_dir, reports_dir, 1, "--start") == 0
    assert _review(data_dir, reports_dir, 1, "--result") == 0
    (data_dir / "runs" / DATE / "review_feedback.md").write_text("## Important\n", encoding="utf-8")

    assert _review(data_dir, reports_dir, 1, "--result") == 1
    assert "already has a result" in capsys.readouterr().err

    assert _review(data_dir, reports_dir, 2, "--start") == 0
    assert _review(data_dir, reports_dir, 1, "--result") == 1
    assert "not the last attempt" in capsys.readouterr().err
    assert _statuses(data_dir) == [(1, "approved"), (2, "started")]


def test_review_rejects_launch_failed_with_start(tmp_path: Path, capsys):
    data_dir, reports_dir = _setup(tmp_path)

    assert _review(data_dir, reports_dir, 1, "--start", "--launch-failed") == 1

    assert "--launch-failed" in capsys.readouterr().err
    assert "agent_progress" not in load_run_state(data_dir, DATE)


@pytest.mark.parametrize("flags", [[], ["--start", "--result"]], ids=["neither", "both"])
def test_review_needs_exactly_one_of_start_and_result(tmp_path: Path, flags: list[str]):
    data_dir, reports_dir = _setup(tmp_path)

    assert _review(data_dir, reports_dir, 1, *flags) == 2


# --- progress retry: counts and limits ---


@pytest.mark.parametrize(
    ("stage", "limit"),
    [
        ("collect", 1),
        ("normalize", 1),
        ("score", 1),
        ("select-hot", 3),
        ("save-proposals", 3),
        ("add-summary", 3),
        ("add-source-overview", 3),
    ],
)
def test_retry_counts_per_stage_and_records_past_the_limit(tmp_path: Path, capsys, stage: str, limit: int):
    data_dir, _ = _setup(tmp_path)

    outputs = []
    for _ in range(limit + 1):
        assert _progress(data_dir, "retry", "--stage", stage) == 0
        outputs.append(_last_json(capsys))

    assert [(output["count"], output["allowed"], output["limit_reached"]) for output in outputs] == [
        (count, count <= limit, count >= limit) for count in range(1, limit + 2)
    ]
    assert all(output["stage"] == stage and output["kind"] == "fix" and output["limit"] == limit for output in outputs)
    retries = _agent_progress(data_dir)["retries"]
    assert [(record["stage"], record["kind"]) for record in retries] == [(stage, "fix")] * (limit + 1)
    assert all("recorded_at" in record for record in retries)


def test_retry_allows_the_last_rerun_within_the_limit(tmp_path: Path, capsys):
    """The skill calls retry right before rerunning: the 1st normalize rerun is allowed but the last one."""
    data_dir, _ = _setup(tmp_path)

    assert _progress(data_dir, "retry", "--stage", "normalize") == 0
    first = _last_json(capsys)
    assert _progress(data_dir, "retry", "--stage", "normalize") == 0
    second = _last_json(capsys)

    assert (first["allowed"], first["limit_reached"]) == (True, True)
    assert (second["allowed"], second["limit_reached"]) == (False, True)


def test_retry_counts_each_stage_separately(tmp_path: Path, capsys):
    data_dir, _ = _setup(tmp_path)
    assert _progress(data_dir, "retry", "--stage", "select-hot") == 0
    assert _progress(data_dir, "retry", "--stage", "select-hot") == 0

    assert _progress(data_dir, "retry", "--stage", "save-proposals") == 0

    assert _last_json(capsys)["count"] == 1


def test_retry_corrupt_input_is_counted_over_the_day_apart_from_fixes(tmp_path: Path, capsys):
    data_dir, _ = _setup(tmp_path)
    assert _progress(data_dir, "retry", "--stage", "score") == 0
    capsys.readouterr()

    assert _progress(data_dir, "retry", "--stage", "score", "--kind", "corrupt_input") == 0
    assert _last_json(capsys) == {
        "stage": "score", "kind": "corrupt_input", "count": 1, "limit": 1, "allowed": True, "limit_reached": True
    }

    # Another stage still counts towards the same once-a-day limit.
    assert _progress(data_dir, "retry", "--stage", "collect", "--kind", "corrupt_input") == 0
    assert _last_json(capsys) == {
        "stage": "collect", "kind": "corrupt_input", "count": 2, "limit": 1, "allowed": False, "limit_reached": True
    }

    # The corrupt input reruns do not count towards the stage's own fix limit.
    assert _progress(data_dir, "retry", "--stage", "score") == 0
    assert _last_json(capsys)["count"] == 2


@pytest.mark.parametrize("stage", ["select-hot", "add-summary", "add-source-overview"])
def test_retry_corrupt_input_only_from_a_stage_that_rebuilds_the_file(tmp_path: Path, capsys, stage: str):
    data_dir, _ = _setup(tmp_path)

    assert _progress(data_dir, "retry", "--stage", stage, "--kind", "corrupt_input") == 1

    assert capsys.readouterr().err.startswith("error: a corrupt_input rerun starts from")
    assert "agent_progress" not in load_run_state(data_dir, DATE)


def test_retry_selection_mismatch_is_counted_over_the_day_apart_from_other_kinds(tmp_path: Path, capsys):
    """Issue #21: once a day, counted apart from the corrupt input rebuild and the stage's own fixes."""
    data_dir, _ = _setup(tmp_path)
    assert _progress(data_dir, "retry", "--stage", "score", "--kind", "corrupt_input") == 0
    assert _progress(data_dir, "retry", "--stage", "select-hot") == 0
    capsys.readouterr()

    assert _progress(data_dir, "retry", "--stage", "select-hot", "--kind", "selection_mismatch") == 0
    assert _last_json(capsys) == {
        "stage": "select-hot", "kind": "selection_mismatch", "count": 1, "limit": 1, "allowed": True, "limit_reached": True
    }

    # Another stage still counts towards the same once-a-day limit.
    assert _progress(data_dir, "retry", "--stage", "score", "--kind", "selection_mismatch") == 0
    assert _last_json(capsys) == {
        "stage": "score", "kind": "selection_mismatch", "count": 2, "limit": 1, "allowed": False, "limit_reached": True
    }

    # The other kinds are not counted with it.
    assert _progress(data_dir, "retry", "--stage", "score", "--kind", "corrupt_input") == 0
    assert _last_json(capsys)["count"] == 2
    assert _progress(data_dir, "retry", "--stage", "select-hot") == 0
    assert _last_json(capsys)["count"] == 2
    kinds = [record["kind"] for record in load_run_state(data_dir, DATE)["agent_progress"]["retries"]]
    assert kinds.count("selection_mismatch") == 2


@pytest.mark.parametrize("stage", ["collect", "normalize", "save-proposals", "add-summary", "add-source-overview"])
def test_retry_selection_mismatch_only_from_score_or_select_hot(tmp_path: Path, capsys, stage: str):
    data_dir, _ = _setup(tmp_path)

    assert _progress(data_dir, "retry", "--stage", stage, "--kind", "selection_mismatch") == 1

    assert capsys.readouterr().err.startswith("error: a selection_mismatch rerun starts from score / select-hot")
    assert "agent_progress" not in load_run_state(data_dir, DATE)


@pytest.mark.parametrize("args", [["--stage", "report"], ["--stage", "score", "--kind", "invalid_input"]])
def test_retry_rejects_unknown_stage_or_kind(tmp_path: Path, args: list[str]):
    data_dir, _ = _setup(tmp_path)

    assert _progress(data_dir, "retry", *args) == 2


# --- progress finalize / complete ---


@pytest.mark.parametrize(("command", "key"), [("finalize", "finalized_at"), ("complete", "completed_at")])
def test_finalize_and_complete_record_the_time_again_on_each_call(
    tmp_path: Path, monkeypatch, capsys, command: str, key: str
):
    data_dir, _ = _setup(tmp_path)
    monkeypatch.setattr(progress_command, "_now", lambda: "2026-10-09T01:00:00+00:00")
    assert _progress(data_dir, command) == 0
    assert capsys.readouterr().out == ""
    assert _agent_progress(data_dir)[key] == "2026-10-09T01:00:00+00:00"

    monkeypatch.setattr(progress_command, "_now", lambda: "2026-10-09T02:00:00+00:00")
    assert _progress(data_dir, command) == 0

    assert _agent_progress(data_dir)[key] == "2026-10-09T02:00:00+00:00"
    assert load_run_state(data_dir, DATE).get("needs_review") is None


# --- run_state.json ---


@pytest.mark.parametrize(
    "args",
    [["review", "--attempt", "1", "--start"], ["retry", "--stage", "score"], ["finalize"], ["complete"]],
    ids=["review", "retry", "finalize", "complete"],
)
def test_progress_fails_without_run_state_of_the_date(tmp_path: Path, capsys, args: list[str]):
    data_dir = tmp_path / "data"

    assert _progress(data_dir, *args) == 1

    assert "no run_state.json" in capsys.readouterr().err
    assert not run_state_path(data_dir, DATE).exists()


@pytest.mark.parametrize("content", [b"{broken", b"\xff\xfe{", b"[]"], ids=["json", "utf8", "not-object"])
def test_progress_fails_with_broken_run_state(tmp_path: Path, capsys, content: bytes):
    data_dir = tmp_path / "data"
    path = run_state_path(data_dir, DATE)
    path.parent.mkdir(parents=True)
    path.write_bytes(content)

    assert _progress(data_dir, "complete") == 1

    assert capsys.readouterr().err.startswith("error: ")
    assert path.read_bytes() == content


@pytest.mark.parametrize(
    "agent_progress",
    [
        [],
        {"review_attempts": {}, "retries": []},
        {"review_attempts": [{"attempt": "1", "status": "started"}], "retries": []},
        {"review_attempts": [{"attempt": 1, "status": ["started"]}], "retries": []},
        {"review_attempts": [], "retries": [{"stage": "score", "kind": None}]},
        {"review_attempts": [], "retries": [{"stage": "score", "kind": "bogus"}]},
        {"review_attempts": [], "retries": ["score"]},
        {"review_attempts": [{"attempt": 4, "status": "started"}], "retries": []},
        {"review_attempts": [{"attempt": 2, "status": "approved"}, {"attempt": 1, "status": "started"}], "retries": []},
        {"review_attempts": [{"attempt": 1, "status": "approved"}, {"attempt": 1, "status": "started"}], "retries": []},
        {"review_attempts": [], "retries": [{"stage": "report", "kind": "fix"}]},
        {"review_attempts": [], "retries": [], "finalized_at": 1},
        {"review_attempts": [], "retries": [], "completed_at": None},
    ],
    ids=[
        "not-object",
        "attempts-not-list",
        "attempt-not-int",
        "status-not-str",
        "kind-null",
        "kind-unknown",
        "retry-not-object",
        "attempt-out-of-range",
        "attempts-not-ascending",
        "attempts-duplicated",
        "stage-unknown",
        "finalized-not-str",
        "completed-not-str",
    ],
)
def test_progress_fails_with_malformed_agent_progress(tmp_path: Path, capsys, agent_progress):
    data_dir, _ = _setup(tmp_path)
    state = load_run_state(data_dir, DATE)
    state["agent_progress"] = agent_progress
    save_run_state(data_dir, DATE, state)
    before = run_state_path(data_dir, DATE).read_bytes()

    assert _progress(data_dir, "retry", "--stage", "score") == 1

    assert capsys.readouterr().err.startswith("error: agent_progress")
    assert run_state_path(data_dir, DATE).read_bytes() == before


def test_progress_keeps_old_errors_without_path(tmp_path: Path):
    """corrupt_input records written before `path` was added are still read as they are.

    Only reading is checked here; how a record without `path` is judged on resume is checked in test_progress_show.py.
    """
    data_dir, _ = _setup(tmp_path)
    state = load_run_state(data_dir, DATE)
    old = {"source": "score", "type": "corrupt_input", "message": f"data/events/{DATE}/events.jsonl:1: bad"}
    state["errors"] = [old]
    save_run_state(data_dir, DATE, state)

    assert _progress(data_dir, "finalize") == 0

    assert load_run_state(data_dir, DATE)["errors"] == [old]


def test_collect_keeps_agent_progress(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        collect_command,
        "build_adapters",
        lambda configs: [FixtureAdapter("github", "technology", Path("tests/fixtures/sample_raw_items.jsonl").resolve())],
    )
    data_dir = tmp_path / "data"
    date = "2026-09-25"
    save_run_state(data_dir, date, load_run_state(data_dir, date))
    assert main(["progress", "retry", "--date", date, "--stage", "normalize", "--data-dir", str(data_dir)]) == 0
    recorded = load_run_state(data_dir, date)["agent_progress"]

    assert main(["collect", "--since", "2026-09-24", "--until", date, "--data-dir", str(data_dir)]) == 0

    assert load_run_state(data_dir, date)["agent_progress"] == recorded
