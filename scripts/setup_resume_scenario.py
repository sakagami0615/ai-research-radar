"""再開のシナリオのテスト用データを、テスト用の出力先(`test_output/`)に配置する。

`tests/fixtures/resume_scenarios/<シナリオ名>/` の `data/` と `reports/` を、
`<output-dir>/data` と `<output-dir>/reports` にコピーする。fixtureの対象日
(`2026-09-25`)が `--date`(省略時は今日)になるよう、ファイル名と中身の日付
(`YYYY-MM-DD`)をすべて同じ日数だけずらす(収集期間などの前後関係を保つため)。
`agent-daily-run` は対象日に `date +%F` を使うため、今日の日付で配置しないと
再開の確認ができない。

日付を置き換えるとレビュー対象の成果物のハッシュが変わるため、`review_target.json`
は配置後の成果物から計算し直す(fixtureの `review_target.json` は、どれも
レビューの開始時から成果物が変わっていない状態を表す)。

配置の前に `<output-dir>/data` を消し、`<output-dir>/reports/daily/<date>.md` も消す
(前回のテストのデータが判定に混ざらないようにするため)。本番の `data/` と
`reports/` には書かない(配置先がチェックアウトのルート、またはその `data/` /
`reports/` の中なら止める)。使い方は
docs/support/01-operations/testing/03-agent-smoke-tests.md の「再開の確認」。

    PYTHONPATH=src python scripts/setup_resume_scenario.py 06_review2_changes_requested
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import date as date_cls
from datetime import timedelta
from pathlib import Path

from ai_research_radar.storage.agent_progress import review_artifact_hashes, review_target_path
from ai_research_radar.storage.files import atomic_write_text

REPO_ROOT = Path(__file__).resolve().parents[1]
SCENARIOS_DIR = REPO_ROOT / "tests" / "fixtures" / "resume_scenarios"
FIXTURE_DATE = "2026-09-25"
_DATE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")


def scenario_names() -> list[str]:
    return sorted(path.name for path in SCENARIOS_DIR.iterdir() if path.is_dir())


def setup(scenario: str, target_date: str, output_dir: Path) -> None:
    source = SCENARIOS_DIR / scenario
    data_dir, reports_dir = output_dir / "data", output_dir / "reports"
    if data_dir.exists():
        shutil.rmtree(data_dir)
    (reports_dir / "daily" / f"{target_date}.md").unlink(missing_ok=True)
    shift = date_cls.fromisoformat(target_date) - date_cls.fromisoformat(FIXTURE_DATE)
    for name, destination in (("data", data_dir), ("reports", reports_dir)):
        _copy_tree(source / name, destination, shift)
    target = review_target_path(data_dir, target_date)
    if target.exists():
        recorded = json.loads(target.read_text(encoding="utf-8"))
        recorded["artifacts"] = review_artifact_hashes(data_dir, reports_dir, target_date)
        atomic_write_text(target, json.dumps(recorded, ensure_ascii=False, sort_keys=True, indent=2))


def _shift_dates(text: str, shift: timedelta) -> str:
    def replace(match: re.Match[str]) -> str:
        try:
            return (date_cls.fromisoformat(match.group(0)) + shift).isoformat()
        except ValueError:  # not a calendar date
            return match.group(0)

    return _DATE.sub(replace, text)


def _copy_tree(source: Path, destination: Path, shift: timedelta) -> None:
    if not source.exists():
        return
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        output = destination / _shift_dates(path.relative_to(source).as_posix(), shift)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(_shift_dates(path.read_text(encoding="utf-8"), shift), encoding="utf-8")


def production_dir_problem(output_dir: Path) -> str | None:
    """Why `output_dir` could overwrite a checkout's data/ or reports/, None if it cannot."""
    for checkout in (output_dir, *output_dir.parents):
        if not (checkout / ".git").exists():
            continue
        if output_dir == checkout:
            return f"{output_dir} is a checkout root"
        for name in ("data", "reports"):
            if output_dir.is_relative_to(checkout / name):
                return f"{output_dir} is inside {checkout / name}"
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="再開のシナリオのテスト用データを配置する")
    parser.add_argument("scenario", choices=scenario_names())
    parser.add_argument("--date", default=date_cls.today().isoformat(), help="対象日(省略時は今日)")
    parser.add_argument("--output-dir", default=str(REPO_ROOT / "test_output"), help="配置先(省略時はリポジトリの test_output)")
    args = parser.parse_args(argv)
    try:
        valid = date_cls.fromisoformat(args.date).isoformat() == args.date
    except ValueError:
        valid = False
    if not valid:  # fromisoformat also accepts e.g. 20261016
        parser.error(f"--date must be YYYY-MM-DD: {args.date!r}")
    output_dir = Path(args.output_dir).resolve()
    problem = production_dir_problem(output_dir)
    if problem is not None:
        print(f"error: --output-dir would overwrite production data: {problem}", file=sys.stderr)
        return 1
    setup(args.scenario, args.date, output_dir)
    print(output_dir / "data")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
