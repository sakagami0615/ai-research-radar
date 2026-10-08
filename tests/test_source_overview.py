import json
from pathlib import Path

import pytest

from ai_research_radar.reporting.source_overview import (
    group_signals_by_source,
    load_source_overviews,
    other_source_key,
    save_source_overviews,
)

DATE = "2026-09-25"


def test_other_source_key_avoids_real_source_names():
    assert other_source_key(["github"]) == "other"
    assert other_source_key(["other"]) == "_other"
    assert other_source_key(["other", "_other"]) == "__other"


def test_group_signals_by_source_keeps_heading_order_and_empty_sources():
    signals = [
        {"source": "arxiv", "title": "a"},
        {"source": "hackernews", "title": "h"},
        {"source": "github", "title": "g"},
        {"title": "no source"},
    ]

    groups = group_signals_by_source(["github", "arxiv", "pypi"], signals)

    assert list(groups) == ["github", "arxiv", "pypi", "other"]
    assert [item["title"] for item in groups["other"]] == ["h", "no source"]
    assert groups["pypi"] == []


def test_group_signals_by_source_omits_other_without_unknown_signals():
    groups = group_signals_by_source(["other"], [{"source": "other", "title": "o"}])

    assert list(groups) == ["other"]


def test_save_source_overviews_merges_and_overwrites_same_source(tmp_path: Path):
    save_source_overviews(tmp_path, DATE, {"github": "最初", "arxiv": "A"})
    save_source_overviews(tmp_path, DATE, {"github": "上書き"})

    assert load_source_overviews(tmp_path, DATE) == {"github": "上書き", "arxiv": "A"}


def test_load_source_overviews_returns_empty_without_file_and_skips_non_text_values(tmp_path: Path):
    assert load_source_overviews(tmp_path, DATE) == {}
    path = tmp_path / "runs" / DATE / "source_overviews.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"github": "傾向", "arxiv": "", "pypi": ["x"], "hf": None}), encoding="utf-8")

    assert load_source_overviews(tmp_path, DATE) == {"github": "傾向"}


def test_load_source_overviews_raises_on_broken_file(tmp_path: Path):
    path = tmp_path / "runs" / DATE / "source_overviews.json"
    path.parent.mkdir(parents=True)
    path.write_text("{broken", encoding="utf-8")
    with pytest.raises(ValueError):
        load_source_overviews(tmp_path, DATE)

    path.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError):
        load_source_overviews(tmp_path, DATE)
