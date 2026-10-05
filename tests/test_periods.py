import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from ai_research_radar.normalization.scores import is_within_period
from ai_research_radar.periods import previous_day_period, resolve_default_period

# 2026-10-05 09:00 JST == 2026-10-05T00:00Z; the target date is 2026-10-05.
NOW = datetime(2026, 10, 5, 9, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
UNTIL = "2026-10-05T00:00:00+00:00"


def _write_run(data_dir: Path, day: str, *lines: str) -> None:
    path = data_dir / "runs" / day / "run.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(line + "\n" for line in lines), encoding="utf-8")


def _run(until: str, started_at: str | None = None) -> str:
    record = {"until": until}
    if started_at is not None:
        record["started_at"] = started_at
    return json.dumps(record)


def test_datetime_period_includes_start_and_excludes_after_end():
    since = "2026-10-03T18:00:00+00:00"
    until = "2026-10-04T18:00:00+00:00"

    assert is_within_period(datetime(2026, 10, 3, 18, 0, tzinfo=timezone.utc), since, until)
    assert is_within_period(datetime(2026, 10, 4, 17, 59, 59, tzinfo=timezone.utc), since, until)
    assert not is_within_period(datetime(2026, 10, 4, 18, 0, 1, tzinfo=timezone.utc), since, until)


def test_date_period_keeps_full_day_compatibility():
    value = datetime(2026, 10, 4, 23, 59, 59, tzinfo=timezone.utc)

    assert is_within_period(value, "2026-10-04", "2026-10-04")


def test_previous_day_period_preserves_explicit_until_only_compatibility():
    assert previous_day_period("2026-10-04") == "2026-10-03"


def test_default_period_resumes_from_previous_run_until(tmp_path: Path):
    _write_run(tmp_path, "2026-10-03", _run("2026-10-02T23:00:00+00:00"))

    assert resolve_default_period(tmp_path, NOW) == ("2026-10-02T23:00:00+00:00", UNTIL)


def test_default_period_uses_latest_run_before_target_date(tmp_path: Path):
    _write_run(tmp_path, "2026-10-01", _run("2026-09-30T23:00:00+00:00"))
    _write_run(tmp_path, "2026-10-03", _run("2026-10-02T23:00:00+00:00"))

    assert resolve_default_period(tmp_path, NOW) == ("2026-10-02T23:00:00+00:00", UNTIL)


def test_default_period_ignores_target_date_run_for_same_day_rerun(tmp_path: Path):
    _write_run(tmp_path, "2026-10-03", _run("2026-10-02T23:00:00+00:00"))
    _write_run(tmp_path, "2026-10-05", _run("2026-10-04T23:00:00+00:00"))

    assert resolve_default_period(tmp_path, NOW) == ("2026-10-02T23:00:00+00:00", UNTIL)


def test_default_period_is_capped_by_max_lookback_days(tmp_path: Path):
    _write_run(tmp_path, "2026-09-20", _run("2026-09-19T23:00:00+00:00"))

    assert resolve_default_period(tmp_path, NOW) == ("2026-09-28T00:00:00+00:00", UNTIL)
    assert resolve_default_period(tmp_path, NOW, max_lookback_days=3) == ("2026-10-02T00:00:00+00:00", UNTIL)


def test_default_period_first_run_collects_max_lookback_days(tmp_path: Path):
    assert resolve_default_period(tmp_path, NOW) == ("2026-09-28T00:00:00+00:00", UNTIL)


def test_default_period_date_only_until_uses_earlier_of_day_start_and_started_at(tmp_path: Path):
    # Run at 08:46 JST on 09-28 == 09-27T23:46Z: 00:00Z of 09-28 would leave a gap.
    _write_run(tmp_path, "2026-09-28", _run("2026-09-28", "2026-09-27T23:46:00+00:00"))

    assert resolve_default_period(tmp_path, NOW) == ("2026-09-28T00:00:00+00:00", UNTIL)
    assert resolve_default_period(tmp_path, NOW, max_lookback_days=30) == ("2026-09-27T23:46:00+00:00", UNTIL)


def test_default_period_date_only_until_without_started_at_uses_day_start(tmp_path: Path):
    _write_run(tmp_path, "2026-10-02", _run("2026-10-02"))

    assert resolve_default_period(tmp_path, NOW) == ("2026-10-02T00:00:00+00:00", UNTIL)


def test_default_period_skips_broken_files_and_non_date_directories(tmp_path: Path):
    _write_run(tmp_path, "2026-10-01", _run("2026-09-30T23:00:00+00:00"))
    _write_run(tmp_path, "2026-10-03", "not json", json.dumps({"until": "garbage"}))
    _write_run(tmp_path, "scratch", _run("2026-10-04T23:00:00+00:00"))
    (tmp_path / "runs" / "2026-10-02").mkdir(parents=True)
    (tmp_path / "runs" / "2026-10-02" / "run.jsonl").write_bytes(b"\xff\xfe\x00garbage")

    assert resolve_default_period(tmp_path, NOW) == ("2026-09-30T23:00:00+00:00", UNTIL)


def test_default_period_ignores_previous_until_not_before_now(tmp_path: Path):
    _write_run(tmp_path, "2026-10-03", _run("2026-10-02T23:00:00+00:00"))
    _write_run(tmp_path, "2026-10-04", _run("2026-10-06T00:00:00+00:00"))

    assert resolve_default_period(tmp_path, NOW) == ("2026-10-02T23:00:00+00:00", UNTIL)


def test_default_period_keeps_short_gap_since_previous_run(tmp_path: Path):
    _write_run(tmp_path, "2026-10-04", _run("2026-10-04T20:00:00+00:00"))

    assert resolve_default_period(tmp_path, NOW) == ("2026-10-04T20:00:00+00:00", UNTIL)


def test_default_period_uses_latest_until_when_file_has_several_records(tmp_path: Path):
    _write_run(tmp_path, "2026-10-04", _run("2026-10-03T20:00:00+00:00"), _run("2026-10-04T20:00:00+00:00"))

    assert resolve_default_period(tmp_path, NOW) == ("2026-10-04T20:00:00+00:00", UNTIL)
