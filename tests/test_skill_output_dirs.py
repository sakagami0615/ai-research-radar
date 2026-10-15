"""Skillの出力先の表記(<data_dir> / <reports_dir>)と、CLIへの明示を確かめる(#40)。

テストモードで本番の data/ / reports/ を書き換えないためには、Skillに書いたパスとコマンドが
すべて出力先の表記を使い、--data-dir / --reports-dir を省略しないことが前提になる。
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DAILY = ROOT / "skills" / "agent-daily-run"
REVIEW = ROOT / "skills" / "review-daily-report"
SKILL_FILES = [
    DAILY / "SKILL.md",
    DAILY / "recovery.md",
    DAILY / "entry-prompt.txt",
    REVIEW / "SKILL.md",
    REVIEW / "entry-prompt.txt",
]

# data/runs/... のように、出力先の表記を通さずに書いた本番のパス
BARE_PATH = re.compile(r"(?<![\w/<{])(?:data/(?:raw|collected|normalized|events|topics|runs)|reports/daily)/")
# コマンドとして書いた ai-radar の呼び出し(引数付き)。行末かバッククォートまで
CLI_CALL = re.compile(r"ai-radar (?!daily\b)[a-z-]+ --[^`\n]*")
SCRIPT_CALL = re.compile(r"list_source_signals\.py <date>[^`\n]*")


@pytest.mark.parametrize("path", SKILL_FILES, ids=lambda p: str(p.relative_to(ROOT)))
def test_skill_paths_use_output_dir_placeholders(path: Path):
    text = path.read_text(encoding="utf-8")
    assert BARE_PATH.findall(text) == []


@pytest.mark.parametrize("path", [DAILY / "SKILL.md", DAILY / "recovery.md"], ids=lambda p: p.name)
def test_every_cli_call_names_the_output_dirs(path: Path):
    text = path.read_text(encoding="utf-8")
    for call in CLI_CALL.findall(text):
        assert "--data-dir <data_dir>" in call, call
        if call.startswith("ai-radar report "):
            assert "--reports-dir <reports_dir>" in call, call
        assert "--input data/" not in call, call


def test_daily_skill_has_cli_calls_to_check():
    calls = CLI_CALL.findall((DAILY / "SKILL.md").read_text(encoding="utf-8"))
    commands = {call.split()[1] for call in calls}
    assert commands >= {
        "collect", "normalize", "score", "select-hot", "save-proposals",
        "add-summary", "add-source-overview", "report", "mark-needs-review",
    }


@pytest.mark.parametrize("path", [DAILY / "SKILL.md", REVIEW / "SKILL.md"], ids=lambda p: p.parent.name)
def test_source_listing_script_gets_data_dir(path: Path):
    calls = SCRIPT_CALL.findall(path.read_text(encoding="utf-8"))
    assert calls
    for call in calls:
        assert "--data-dir <data_dir>" in call, call


def test_review_entry_prompt_has_output_dir_placeholders():
    text = (REVIEW / "entry-prompt.txt").read_text(encoding="utf-8")
    for placeholder in ("{date}", "{data_dir}", "{reports_dir}"):
        assert placeholder in text
    assert "{data_dir}/runs/{date}/review_feedback.md" in text


def test_test_entry_prompt_points_to_test_output():
    text = (DAILY / "entry-prompt-test.txt").read_text(encoding="utf-8")
    assert "test_output/data" in text
    assert "test_output/reports" in text
    assert "git rev-parse --path-format=absolute --git-common-dir" in text
    for excluded in ("review_result.json", "review_target.json"):
        assert excluded in text
