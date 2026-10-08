import json
from pathlib import Path

from ai_research_radar.cli.commands.run_state import load_run_state, save_run_state
from ai_research_radar.cli.main import main
from ai_research_radar.reporting.source_overview import load_source_overviews
from ai_research_radar.storage.jsonl import write_jsonl

DATE = "2026-09-25"


def _signal(source: str, title: str) -> dict:
    return {"source": source, "title": title, "url": f"https://example.com/{title}", "summary": ""}


def _setup(tmp_path: Path, sources: list[str] | None = None, signals: list[dict] | None = None) -> Path:
    data_dir = tmp_path / "data"
    state = load_run_state(data_dir, DATE)
    state["sources"] = sources if sources is not None else ["github", "arxiv"]
    state["stages_completed"] = ["collect", "normalize"]
    save_run_state(data_dir, DATE, state)
    write_jsonl(
        data_dir / "normalized" / DATE / "signals.jsonl",
        signals if signals is not None else [_signal("github", "g1"), _signal("github", "g2"), _signal("hackernews", "h1")],
    )
    return data_dir


def _input(tmp_path: Path, content: object, name: str = "source_overview_input.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")
    return path


def _add(data_dir: Path, *extra: str) -> int:
    return main(["add-source-overview", "--date", DATE, "--data-dir", str(data_dir), *extra])


def _state(data_dir: Path) -> dict:
    return json.loads((data_dir / "runs" / DATE / "run_state.json").read_text(encoding="utf-8"))


def _errors(data_dir: Path) -> list[dict]:
    return [error for error in _state(data_dir).get("errors", []) if error["source"] == "add-source-overview"]


def test_add_source_overview_merges_overviews_without_marking_a_stage(tmp_path: Path):
    data_dir = _setup(tmp_path)

    assert _add(data_dir, "--input", str(_input(tmp_path, {"github": " 最初の傾向 ", "other": "未登録Sourceの傾向"}))) == 0
    assert _add(data_dir, "--input", str(_input(tmp_path, {"github": "上書きした傾向"}))) == 0

    assert load_source_overviews(data_dir, DATE) == {"github": "上書きした傾向", "other": "未登録Sourceの傾向"}
    assert _state(data_dir)["stages_completed"] == ["collect", "normalize"]
    assert _errors(data_dir) == []


def test_add_source_overview_accepts_renamed_other_heading_when_other_is_a_real_source(tmp_path: Path):
    data_dir = _setup(
        tmp_path,
        sources=["other"],
        signals=[_signal("other", "o1"), _signal("hackernews", "h1")],
    )

    assert _add(data_dir, "--input", str(_input(tmp_path, {"other": "実在Source", "_other": "未登録Source"}))) == 0

    assert load_source_overviews(data_dir, DATE) == {"other": "実在Source", "_other": "未登録Source"}


def test_add_source_overview_records_error_types_without_changing_saved_overviews(tmp_path: Path):
    data_dir = _setup(tmp_path)
    assert _add(data_dir, "--input", str(_input(tmp_path, {"github": "最初の傾向"}))) == 0
    broken = tmp_path / "broken.json"
    broken.write_text("{broken", encoding="utf-8")
    not_utf8 = tmp_path / "not_utf8.json"
    not_utf8.write_bytes(b"\xff\xfe")

    cases = [
        ([], "invalid_input"),
        (["--input", str(tmp_path / "missing.json")], "invalid_input"),
        (["--input", str(broken)], "invalid_input"),
        (["--input", str(not_utf8)], "invalid_input"),
        (["--input", str(_input(tmp_path, ["github"], "list.json"))], "invalid_input"),
        (["--input", str(_input(tmp_path, {}, "empty.json"))], "invalid_overview"),
        (["--input", str(_input(tmp_path, {"github": "上書き", "unknown": "傾向"}, "unknown.json"))], "invalid_overview"),
        (["--input", str(_input(tmp_path, {"_other": "傾向"}, "renamed_other.json"))], "invalid_overview"),
        (["--input", str(_input(tmp_path, {"github": " \n "}, "blank.json"))], "invalid_overview"),
        (["--input", str(_input(tmp_path, {"github": ["傾向"]}, "nonstr.json"))], "invalid_overview"),
        (["--input", str(_input(tmp_path, {"github": "上書き", "arxiv": "0件のSource"}, "zero.json"))], "invalid_overview"),
    ]
    for extra, error_type in cases:
        assert _add(data_dir, *extra) == 1, extra
        assert [error["type"] for error in _errors(data_dir)] == [error_type], extra

    assert load_source_overviews(data_dir, DATE) == {"github": "最初の傾向"}


def test_add_source_overview_rejects_other_without_unknown_source_signals(tmp_path: Path):
    data_dir = _setup(tmp_path, signals=[_signal("github", "g1")])

    assert _add(data_dir, "--input", str(_input(tmp_path, {"other": "傾向"}))) == 1

    assert [error["type"] for error in _errors(data_dir)] == ["invalid_overview"]


def test_add_source_overview_clears_its_previous_error_on_success(tmp_path: Path):
    data_dir = _setup(tmp_path)
    assert _add(data_dir, "--input", str(_input(tmp_path, {"unknown": "傾向"}))) == 1

    assert _add(data_dir, "--input", str(_input(tmp_path, {"github": "傾向"}))) == 0

    assert _errors(data_dir) == []


def test_add_source_overview_records_write_error_when_saved_overviews_are_broken(tmp_path: Path):
    data_dir = _setup(tmp_path)
    saved = data_dir / "runs" / DATE / "source_overviews.json"
    saved.write_text("{broken", encoding="utf-8")

    assert _add(data_dir, "--input", str(_input(tmp_path, {"github": "傾向"}))) == 1

    assert [error["type"] for error in _errors(data_dir)] == ["write_error"]
    assert saved.read_text(encoding="utf-8") == "{broken"


def test_add_source_overview_records_corrupt_input_when_signals_are_broken(tmp_path: Path):
    data_dir = _setup(tmp_path)
    signals_path = data_dir / "normalized" / DATE / "signals.jsonl"
    # A broken pipeline output (as in #18), not a problem of the agent's input file.
    for content in (b'{"source": "github"}\n{broken\n', b'{"source": "github"}\n\xff\xfe\n'):
        signals_path.write_bytes(content)

        assert _add(data_dir, "--input", str(_input(tmp_path, {"github": "傾向"}))) == 1

        assert [error["type"] for error in _errors(data_dir)] == ["corrupt_input"]
        assert "signals.jsonl:2" in _errors(data_dir)[0]["message"]
        assert load_source_overviews(data_dir, DATE) == {}
