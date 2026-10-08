import importlib.util
import json
from pathlib import Path

from ai_research_radar.cli.commands.run_state import load_run_state, save_run_state
from ai_research_radar.reporting.source_overview import group_signals_by_source
from ai_research_radar.storage.jsonl import write_jsonl

SCRIPT = Path(__file__).resolve().parents[1] / "skills" / "agent-daily-run" / "list_source_signals.py"
DATE = "2026-09-25"


def _load_script():
    spec = importlib.util.spec_from_file_location("list_source_signals", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SIGNALS = [
    {"source": "other", "title": "o1", "url": "https://example.com/o1", "summary": "x"},
    {"source": "hackernews", "title": "h1", "url": "https://example.com/h1", "summary": ""},
    {"title": "no source", "url": "https://example.com/n", "summary": None},
    {"source": "github", "title": "g\n1", "url": "https://example.com/g1", "summary": "line1\nline2 " + "あ" * 300},
]


def test_skill_listing_groups_signals_like_the_report_headings():
    script = _load_script()
    for sources in (["github", "other", "pypi"], ["github"], [], ["other", "_other"]):
        assert script.group_signals(sources, SIGNALS) == group_signals_by_source(sources, SIGNALS), sources


def _setup(tmp_path: Path) -> Path:
    data_dir = tmp_path / "data"
    state = load_run_state(data_dir, DATE)
    state["sources"] = ["github", "other", "pypi"]
    save_run_state(data_dir, DATE, state)
    write_jsonl(data_dir / "normalized" / DATE / "signals.jsonl", SIGNALS)
    return data_dir


def test_skill_listing_prints_headings_or_items_of_one_source(tmp_path: Path, capsys):
    script = _load_script()
    data_dir = _setup(tmp_path)

    assert script.main([DATE, "--data-dir", str(data_dir)]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "### github (1件)",
        "### other (1件)",
        "### pypi (0件)",
        "### _other (2件)",
    ]

    assert script.main([DATE, "github", "--data-dir", str(data_dir)]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "### github (1件)",
        "- g 1 | line1 line2 " + "あ" * 188 + " | https://example.com/g1",
    ]

    assert script.main([DATE, "unknown", "--data-dir", str(data_dir)]) == 1
