import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from ai_research_radar.config.settings import SourceConfig
from ai_research_radar.sources import public
from ai_research_radar.storage.jsonl import read_jsonl, write_jsonl

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "compare_hot_candidates.py"
_spec = importlib.util.spec_from_file_location("compare_hot_candidates", _SCRIPT)
compare = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(compare)

_FETCHED_AT = datetime(2026, 10, 9, 14, 0, tzinfo=timezone.utc)

_OFFICIAL = SourceConfig(
    name="official_blogs",
    family="official",
    adapter="official_blogs",
    enabled=True,
    auth_required=False,
    options={
        "feeds": [
            {
                "provider": "OpenAI",
                "url": "https://example.com/rss.xml",
                "model_keywords": ["gpt-"],
                "model_categories": ["Release"],
            }
        ]
    },
)
_PYPI = SourceConfig(name="pypi", family="technology", adapter="pypi", enabled=True, auth_required=False, options={})


def _stored_record(item) -> dict:
    """A raw/<date>/*.jsonl line as collect writes it, with the saved fetched_at."""
    return {
        "source": item.source,
        "fetched_at": _FETCHED_AT.isoformat(),
        "raw_id": item.raw_id,
        "raw_url": item.raw_url,
        "payload": item.payload,
    }


def _official_entry(title: str, category: str = "Release") -> dict:
    return {
        "title": title,
        "link": f"https://example.com/{title.replace(' ', '-')}",
        "guid": f"https://example.com/{title.replace(' ', '-')}",
        "pubDate": "Fri, 09 Oct 2026 07:00:00 GMT",
        "description": "desc",
        "category": category,
    }


def test_rebuild_official_recomputes_judgements_with_current_feed_settings():
    entry = _official_entry("Release of GPT-9 API")
    stored = public._map_official_feed(entry, provider="OpenAI", source="official_blogs")
    record = _stored_record(stored)
    # Simulate judgements made by older code at collection time.
    record["payload"]["metadata"]["event_type"] = "stale"
    record["payload"]["metadata"].pop("model_release", None)

    rebuilt = compare.rebuild_raw_item(record, _OFFICIAL)

    expected = public._map_official_feed(
        entry,
        provider="OpenAI",
        model_keywords=["gpt-"],
        categories=["Release"],
        model_categories={"release"},
        source="official_blogs",
    )
    assert rebuilt.fetched_at == _FETCHED_AT
    assert rebuilt.raw_id == expected.raw_id
    assert rebuilt.payload["metadata"] == expected.payload["metadata"]
    assert rebuilt.payload["metadata"]["model_release"] == {"provider": "OpenAI", "channel": "official"}


def test_rebuild_official_stops_when_provider_has_no_feed_setting():
    record = _stored_record(public._map_official_feed(_official_entry("GPT-9"), provider="Google", source="official_blogs"))

    with pytest.raises(SystemExit, match="Google"):
        compare.rebuild_raw_item(record, _OFFICIAL)


def test_rebuild_official_uses_the_saved_first_category_for_model_categories():
    entry = _official_entry("GPT-9 customer story", category="Stories")
    record = _stored_record(public._map_official_feed(entry, provider="OpenAI", source="official_blogs"))

    rebuilt = compare.rebuild_raw_item(record, _OFFICIAL)

    assert "model_release" not in rebuilt.payload["metadata"]


def test_rebuild_pypi_recomputes_ai_keyword_strength():
    entry = {"title": "agent-kit 1.0", "link": "https://pypi.org/project/agent-kit/1.0/", "description": "", "pubDate": "Fri, 09 Oct 2026 07:00:00 GMT", "guid": "agent-kit 1.0"}
    record = _stored_record(public._map_pypi_feed(entry, "pypi"))
    record["payload"]["metrics"]["ai_keyword_strength"] = 0.0

    rebuilt = compare.rebuild_raw_item(record, _PYPI)

    assert rebuilt.payload["metrics"]["ai_keyword_strength"] == public._ai_keyword_strength(entry)


def test_snapshot_date_rebuilds_collected_and_scores_without_touching_source(tmp_path):
    source_dir = tmp_path / "data"
    entry = {"title": "rag-kit 1.0", "link": "https://pypi.org/project/rag-kit/1.0/", "description": "", "pubDate": "Fri, 09 Oct 2026 07:00:00 GMT", "guid": "rag-kit 1.0"}
    item = public._map_pypi_feed(entry, "pypi")
    write_jsonl(source_dir / "raw" / "2026-10-09" / "pypi.jsonl", [_stored_record(item)])
    adapter = public.build_adapters([_PYPI])[0]
    stored_signal = adapter.normalize(item)
    write_jsonl(source_dir / "collected" / "2026-10-09" / "signals.jsonl", [stored_signal])
    before = sorted(path.relative_to(source_dir) for path in source_dir.rglob("*"))
    scoring = tmp_path / "scoring.yaml"
    scoring.write_text("hot_selection:\n  minimum_score: 0\n", encoding="utf-8")

    result = compare.snapshot_date(
        source_dir, "2026-10-09", {"pypi": _PYPI}, {"pypi": adapter}, scoring, tmp_path / "work"
    )

    assert result["input_counts"] == {"pypi": 1}
    assert result["stored_collected_mismatches"] == []
    assert [candidate["title"] for candidate in result["hot_candidates"]] == ["rag-kit 1.0"]
    assert result["signals"]["pypi:rag-kit 1.0"]["ai_keyword_strength"] == public._ai_keyword_strength(entry)
    assert sorted(path.relative_to(source_dir) for path in source_dir.rglob("*")) == before
    assert read_jsonl(tmp_path / "work" / "runs" / "2026-10-09" / "hot_candidates.jsonl")


def test_rebuild_huggingface_orgs_keeps_provider():
    model = {"modelId": "Qwen/Qwen9", "createdAt": "2026-10-09T01:00:00.000Z", "pipeline_tag": "text-generation"}
    config = SourceConfig("huggingface_orgs", "technology", "huggingface_orgs", True, False, {})
    record = _stored_record(public._map_huggingface_org(model, "huggingface_orgs", "Qwen"))

    rebuilt = compare.rebuild_raw_item(record, config)

    assert rebuilt.payload["metadata"]["model_release"] == {"provider": "Qwen", "channel": "huggingface"}


def test_rebuild_ollama_keeps_stored_item_because_model_release_needs_the_post_page():
    config = SourceConfig("ollama", "technology", "ollama", True, False, {})
    record = _stored_record(public._make_raw_item("ollama", {"title": "t"}, "t", "https://ollama.com/blog/t", "", None, None, {}, "announcement"))
    record["payload"]["metadata"]["model_release"] = {"provider": "Ollama", "channel": "ollama", "models": ["m"]}

    rebuilt = compare.rebuild_raw_item(record, config)

    assert rebuilt.payload == record["payload"]
    assert rebuilt.fetched_at == _FETCHED_AT


def test_rebuild_openalex_restores_abstract_through_normalize():
    work = {"id": "W1", "title": "Paper", "abstract_inverted_index": {"hello": [0], "world": [1]}, "publication_date": "2026-10-09"}
    config = SourceConfig("openalex", "research", "openalex", True, False, {})
    record = _stored_record(public._map_openalex(work, "openalex"))
    adapter = public.build_adapters([config])[0]

    signal = adapter.normalize(compare.rebuild_raw_item(record, config))

    assert signal.summary == "hello world"


def test_rebuild_stops_without_raw_payload_or_for_unknown_adapter():
    record = _stored_record(public._map_pypi_feed({"title": "x 1.0", "guid": "x 1.0"}, "pypi"))
    record["payload"].pop("raw")
    with pytest.raises(SystemExit, match="payload.raw"):
        compare.rebuild_raw_item(record, _PYPI)

    unknown = SourceConfig("pypi", "technology", "unknown", True, False, {})
    with pytest.raises(SystemExit, match="unknown"):
        compare.rebuild_raw_item(_stored_record(public._map_pypi_feed({"title": "x 1.0"}, "pypi")), unknown)


def _snapshot(commit: str, candidates: list[dict], signals: dict) -> dict:
    return {
        "version": compare.SNAPSHOT_VERSION,
        "code": {"commit": commit, "dirty": False},
        "dates": {"2026-10-09": {"input_counts": {}, "hot_candidates": candidates, "signals": signals, "stored_collected_mismatches": None}},
    }


def test_render_diff_lists_added_removed_rescored_and_changed_signals():
    signal = {"title": "# storage-utils", "event_type": "observed_signal", "ai_keyword_strength": 1.0, "model_release": False}
    before = _snapshot(
        "a" * 40,
        [
            {"hot_id": "hot:1", "title": "kept", "score": 80.0, "reasons": ["Momentum"]},
            {"hot_id": "hot:2", "title": "# storage-utils", "score": 77.2, "reasons": ["Package discovery"]},
        ],
        {"pypi:storage-utils": signal},
    )
    after = _snapshot(
        "b" * 40,
        [
            {"hot_id": "hot:1", "title": "kept", "score": 80.0, "reasons": ["Momentum", "Official override"]},
            {"hot_id": "hot:3", "title": "GPT-9", "score": 45.0, "reasons": ["Official override"]},
        ],
        {"pypi:storage-utils": {**signal, "ai_keyword_strength": 0.0}, "official_blogs:new": {**signal, "title": "new"}},
    )

    text = compare.render_diff(before, after)

    assert "- 修正前: `aaaaaaaaaaaa`" in text
    assert "- HOT候補: 2件 → 2件" in text
    assert "- 増えた候補: 1件\n  - GPT-9(スコア 45.0、理由: Official override)" in text
    # Titles are escaped so that a leading "#" does not become a heading.
    assert "- 減った候補: 1件\n  - \\# storage-utils(スコア 77.2、理由: Package discovery)" in text
    assert "- スコア・理由が変わった候補: 1件\n  - kept(理由 +Official override)" in text
    assert "ai_keyword_strength 1.0 → 0.0" in text
    assert "new(official_blogs:new): 修正後だけにある" in text


def test_render_diff_reports_a_date_missing_on_one_side():
    before = _snapshot("a" * 40, [], {})
    after = {**before, "dates": {}}

    assert "- 修正後の snapshot にこの日がない" in compare.render_diff(before, after)


def test_main_diff_rejects_unknown_snapshot_version(tmp_path):
    path = tmp_path / "old.json"
    path.write_text(json.dumps({"version": 0, "dates": {}}), encoding="utf-8")
    with pytest.raises(SystemExit, match="version"):
        compare.main(["diff", str(path), str(path)])
