import json
from datetime import datetime, timezone
from pathlib import Path

from ai_research_radar.reporting.digest import (
    DailyDigest,
    ModelRelease,
    build_daily_digest,
    save_digest_record,
)
from ai_research_radar.reporting.markdown import render_daily_report
from ai_research_radar.schemas.models import HotCandidate, RunMetadata
from ai_research_radar.storage.jsonl import write_jsonl


def _hot(hot_id: str, score: float, selected: bool = False, source: str = "pypi") -> HotCandidate:
    return HotCandidate(
        hot_id=hot_id,
        title=hot_id.upper(),
        topic=hot_id,
        score=score,
        reasons=["Momentum 90"],
        evidence_urls=[f"https://example.com/{hot_id}"],
        source_families=["technology"],
        signals=[f"{source}:{hot_id}"],
        selected=selected,
    )


def _write_hot(data_dir: Path, day: str, candidates: list[HotCandidate]) -> None:
    write_jsonl(data_dir / "runs" / day / "hot_candidates.jsonl", candidates)


def _model_signal(url: str, provider: str, channel: str, published_at: str) -> dict:
    return {
        "signal_id": f"x:{url}",
        "source": "huggingface_orgs",
        "source_family": "technology",
        "content_type": "model",
        "title": url.rsplit("/", 1)[-1],
        "url": url,
        "published_at": published_at,
        "fetched_at": "2026-09-25T00:00:00+00:00",
        "summary": "",
        "categories": [],
        "raw_metrics": {},
        "normalized_scores": {},
        "metadata": {"model_release": {"provider": provider, "channel": channel}},
    }


def _write_signals(data_dir: Path, day: str, records: list[dict]) -> None:
    write_jsonl(data_dir / "normalized" / day / "signals.jsonl", records)


def test_notable_aggregates_three_days_with_latest_score_and_first_seen(tmp_path: Path):
    _write_hot(tmp_path, "2026-09-22", [_hot("too-old", 99)])
    _write_hot(tmp_path, "2026-09-23", [_hot("a", 76), _hot("picked-earlier", 90, selected=True)])
    _write_hot(tmp_path, "2026-09-24", [_hot("a", 80), _hot("b", 77)])
    _write_hot(tmp_path, "2026-09-25", [_hot("c", 85, source="hackernews"), _hot("picked-earlier", 91), _hot("today-hot", 95, selected=True)])

    digest = build_daily_digest(tmp_path, "2026-09-25")

    assert [(item.candidate.hot_id, item.candidate.score, item.first_seen) for item in digest.notable] == [
        ("c", 85, "2026-09-25"),
        ("a", 80, "2026-09-23"),
        ("b", 77, "2026-09-24"),
    ]
    assert digest.notable[0].sources == ["hackernews"]


def test_digest_excludes_items_shown_in_earlier_reports_but_not_same_day_rerun(tmp_path: Path):
    _write_hot(tmp_path, "2026-09-24", [_hot("a", 80)])
    _write_hot(tmp_path, "2026-09-25", [_hot("a", 81), _hot("b", 77)])
    _write_signals(tmp_path, "2026-09-24", [_model_signal("https://hf.co/o/m1", "O", "huggingface", "2026-09-24T00:00:00+00:00")])
    _write_signals(tmp_path, "2026-09-25", [_model_signal("https://hf.co/o/m2", "O", "huggingface", "2026-09-25T00:00:00+00:00")])
    save_digest_record(tmp_path, "2026-09-24", build_daily_digest(tmp_path, "2026-09-24"))

    first = build_daily_digest(tmp_path, "2026-09-25")
    save_digest_record(tmp_path, "2026-09-25", first)
    rerun = build_daily_digest(tmp_path, "2026-09-25")

    for digest in (first, rerun):
        assert [item.candidate.hot_id for item in digest.notable] == ["b"]
        assert [release.key for release in digest.model_releases] == ["https://hf.co/o/m2"]


def test_notable_is_limited_to_ten_with_overflow_count_and_overflow_is_not_recorded(tmp_path: Path):
    _write_hot(tmp_path, "2026-09-25", [_hot(f"h{index:02d}", 90 - index) for index in range(12)])

    digest = build_daily_digest(tmp_path, "2026-09-25")
    save_digest_record(tmp_path, "2026-09-25", digest)

    assert len(digest.notable) == 10
    assert digest.notable_overflow == 2
    record = json.loads((tmp_path / "runs" / "2026-09-25" / "report_digest.json").read_text(encoding="utf-8"))
    assert record["notable"] == [f"h{index:02d}" for index in range(10)]


def test_model_releases_dedupe_by_url_keep_first_seen_and_skip_unmarked_signals(tmp_path: Path):
    plain = _model_signal("https://hf.co/o/plain", "O", "huggingface", "2026-09-24T00:00:00+00:00")
    plain["metadata"] = {}
    _write_signals(tmp_path, "2026-09-24", [_model_signal("https://hf.co/o/m1", "O", "huggingface", "2026-09-24T00:00:00+00:00"), plain])
    _write_signals(tmp_path, "2026-09-25", [_model_signal("https://hf.co/o/m1/", "O", "huggingface", "2026-09-24T00:00:00+00:00")])

    digest = build_daily_digest(tmp_path, "2026-09-25")

    assert [(release.key, release.first_seen) for release in digest.model_releases] == [("https://hf.co/o/m1", "2026-09-24")]


def _run() -> RunMetadata:
    return RunMetadata(
        run_id="run-1",
        started_at=datetime(2026, 9, 25, tzinfo=timezone.utc),
        finished_at=None,
        mode="agent",
        since="2026-09-24",
        until="2026-09-25",
        sources=[],
        input_counts={},
        output_counts={},
        errors=[],
        report_paths=[],
    )


def test_report_renders_notable_then_model_sections_after_selected_hot(tmp_path: Path):
    _write_hot(tmp_path, "2026-09-25", [_hot("pkg", 77)])
    _write_signals(
        tmp_path,
        "2026-09-25",
        [
            _model_signal("https://ollama.com/library/new", "Ollama", "ollama", "2026-09-25T06:00:00+00:00"),
            _model_signal("https://hf.co/google/gemma-9", "Google", "huggingface", "2026-09-25T01:00:00+00:00"),
            _model_signal("https://deepmind.google/gemini-4", "Google", "official", "2026-09-25T02:00:00+00:00"),
        ],
    )

    markdown = render_daily_report("2026-09-25", [], [], _run(), [], build_daily_digest(tmp_path, "2026-09-25"))

    hot = markdown.index("## 選抜HOT")
    notable = markdown.index("## 注目候補(選抜外)")
    models = markdown.index("## 新モデルリリース")
    summary = markdown.index("## Run Summary")
    assert hot < notable < models < summary
    assert "### [PKG](<https://example.com/pkg>)" in markdown
    assert "- HOT Score: 77" in markdown
    assert "- Source: pypi" in markdown
    assert "- 初出日: 2026-09-25" in markdown
    google = markdown.index("### Google")
    ollama = markdown.index("### Ollama")
    assert google < ollama
    assert markdown.index("gemini-4") < markdown.index("gemma-9")
    assert "- [gemini-4](<https://deepmind.google/gemini-4>) (公式発表 / 公開日 2026-09-25)" in markdown
    assert "(Ollama / 公開日 2026-09-25)" in markdown


def test_report_lists_models_introduced_by_an_article(tmp_path: Path):
    record = _model_signal("https://ollama.com/blog/nemotron", "Ollama", "ollama", "2026-09-25T00:00:00+00:00")
    record["metadata"]["model_release"]["models"] = ["nemotron-3.5-lightning", "tev1"]
    _write_signals(tmp_path, "2026-09-25", [record])

    markdown = render_daily_report("2026-09-25", [], [], _run(), [], build_daily_digest(tmp_path, "2026-09-25"))

    assert "(Ollama / 公開日 2026-09-25) — 紹介モデル: nemotron-3.5-lightning, tev1" in markdown


def test_report_shows_empty_digest_sections_and_per_provider_overflow():
    empty = render_daily_report("2026-09-25", [], [], _run(), [])
    assert "## 注目候補(選抜外)\n\n直近3日分" in empty
    assert empty.count("該当なし") == 2

    releases = [
        ModelRelease(f"https://hf.co/u/m{index:02d}", "Unsloth", "huggingface", f"m{index:02d}", f"https://hf.co/u/m{index:02d}", f"2026-09-25T00:{index:02d}:00+00:00", "2026-09-25")
        for index in range(12)
    ]
    markdown = render_daily_report("2026-09-25", [], [], _run(), [], DailyDigest(model_releases=releases))
    assert markdown.count("](<https://hf.co/u/m") == 10
    assert "- ほか2件(表示上限超過)" in markdown


def test_unreadable_past_day_is_skipped_with_warning_instead_of_failing(tmp_path: Path):
    (tmp_path / "runs" / "2026-09-24").mkdir(parents=True)
    (tmp_path / "runs" / "2026-09-24" / "hot_candidates.jsonl").write_text("{broken\n", encoding="utf-8")
    (tmp_path / "normalized" / "2026-09-23").mkdir(parents=True)
    (tmp_path / "normalized" / "2026-09-23" / "signals.jsonl").write_text('{"no_metadata": true}\nnot json\n', encoding="utf-8")
    _write_hot(tmp_path, "2026-09-23", [])
    (tmp_path / "runs" / "2026-09-23" / "hot_candidates.jsonl").write_text('{"hot_id": "missing-keys"}\n', encoding="utf-8")
    _write_hot(tmp_path, "2026-09-25", [_hot("ok", 80)])

    digest = build_daily_digest(tmp_path, "2026-09-25")

    assert [item.candidate.hot_id for item in digest.notable] == ["ok"]
    assert len(digest.warnings) == 3
    markdown = render_daily_report("2026-09-25", [], [], _run(), [], digest)
    assert "読めなかったため" in markdown
    assert markdown.index("読めなかったため") < markdown.index("## 注目候補(選抜外)")
