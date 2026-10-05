import gzip
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError

import pytest

import ai_research_radar.cli.commands.collect as collect_command
import ai_research_radar.sources.public as public_module
from ai_research_radar.cli.main import main
from ai_research_radar.normalization.dedup import deduplicate_signals
from ai_research_radar.schemas.models import CanonicalSignal
from ai_research_radar.sources.base import SourceAdapter
from ai_research_radar.sources.public import (
    HuggingFaceOrgAdapter,
    OfficialFeedsAdapter,
    OllamaBlogAdapter,
)


class _Response:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def read(self) -> bytes:
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _rss(*titles: str) -> bytes:
    items = "".join(
        f"<item><title>{title}</title><link>https://example.com/{index}</link>"
        f"<guid>{index}</guid><pubDate>Thu, 25 Sep 2026 08:00:00 +0000</pubDate></item>"
        for index, title in enumerate(titles)
    )
    return f'<?xml version="1.0"?><rss><channel>{items}</channel></rss>'.encode("utf-8")


def _rss_with_categories(*entries: tuple[str, list[str]]) -> bytes:
    items = "".join(
        f"<item><title>{title}</title><link>https://example.com/{index}</link><guid>{index}</guid>"
        + "".join(f"<category>{category}</category>" for category in categories)
        + "<pubDate>Thu, 25 Sep 2026 08:00:00 +0000</pubDate></item>"
        for index, (title, categories) in enumerate(entries)
    )
    return f'<?xml version="1.0"?><rss><channel>{items}</channel></rss>'.encode("utf-8")


def _openai_feed(model_categories) -> dict:
    feed = {"provider": "OpenAI", "url": "https://feed/openai", "model_keywords": ["gpt-"]}
    if model_categories is not None:
        feed["model_categories"] = model_categories
    return feed


def _model_release_titles(adapter) -> set[str]:
    return {
        item.payload["title"]
        for item in adapter.collect("2026-09-24", "2026-09-25")
        if "model_release" in item.payload["metadata"]
    }


def _no_sleep(monkeypatch) -> None:
    monkeypatch.setattr(public_module, "_sleep", lambda seconds: None)


def test_official_feeds_mark_titles_with_model_keywords_as_model_release(monkeypatch):
    adapter = OfficialFeedsAdapter(
        "official_blogs",
        "official",
        [{"provider": "Google", "url": "https://feed/google", "model_keywords": ["gemini"]}],
    )
    monkeypatch.setattr(
        public_module,
        "urlopen",
        lambda request, timeout: _Response(_rss("Gemini 4 Argon: our next era", "Hallo, Deutschland!")),
    )

    signals = [adapter.normalize(item) for item in adapter.collect("2026-09-24", "2026-09-25")]

    by_title = {signal.title: signal for signal in signals}
    release = by_title["Gemini 4 Argon: our next era"]
    # Keywords only mark the section; they must not widen the HOT Official override.
    assert release.metadata["event_type"] == "observed_signal"
    assert release.metadata["model_release"] == {"provider": "Google", "channel": "official"}
    other = by_title["Hallo, Deutschland!"]
    assert other.metadata["event_type"] == "observed_signal"
    assert "model_release" not in other.metadata


def test_official_feeds_continue_when_one_feed_fails_and_record_partial_error(monkeypatch):
    adapter = OfficialFeedsAdapter(
        "official_blogs",
        "official",
        [{"provider": "A", "url": "https://feed/a"}, {"provider": "B", "url": "https://feed/b"}],
    )

    def fake_urlopen(request, timeout):
        if request.full_url.endswith("/a"):
            raise HTTPError(request.full_url, 404, "Not Found", None, None)
        return _Response(_rss("B news"))

    monkeypatch.setattr(public_module, "urlopen", fake_urlopen)

    items = adapter.collect("2026-09-24", "2026-09-25")

    assert [item.payload["title"] for item in items] == ["B news"]
    assert adapter.partial_errors == [
        {"source": "official_blogs", "type": "partial_feed_error", "message": "https://feed/a: HTTP Error 404: Not Found"}
    ]


def test_official_feeds_raise_when_every_feed_fails(monkeypatch):
    adapter = OfficialFeedsAdapter("official_blogs", "official", [{"provider": "A", "url": "https://feed/a"}])

    def fake_urlopen(request, timeout):
        raise HTTPError(request.full_url, 404, "Not Found", None, None)

    monkeypatch.setattr(public_module, "urlopen", fake_urlopen)

    with pytest.raises(HTTPError):
        adapter.collect("2026-09-24", "2026-09-25")


def test_feed_body_is_gunzipped_when_server_sends_gzip(monkeypatch):
    adapter = OfficialFeedsAdapter("official_blogs", "official", [{"provider": "A", "url": "https://feed/a"}])
    monkeypatch.setattr(public_module, "urlopen", lambda request, timeout: _Response(gzip.compress(_rss("Zipped"))))

    items = adapter.collect("2026-09-24", "2026-09-25")

    assert [item.payload["title"] for item in items] == ["Zipped"]


def test_legacy_single_feed_url_config_is_still_supported():
    from ai_research_radar.config.settings import SourceConfig

    adapter = public_module.build_adapters(
        [SourceConfig("official_blogs", "official", "official_blogs", True, False, {"feed_url": "https://feed/x"})]
    )[0]

    assert isinstance(adapter, OfficialFeedsAdapter)
    assert adapter.feeds == [{"provider": "OpenAI", "url": "https://feed/x"}]


def test_huggingface_org_keeps_only_models_created_in_period(monkeypatch):
    adapter = HuggingFaceOrgAdapter("huggingface_orgs", "technology", {"Qwen": "Qwen"})
    payload = [
        {"id": "Qwen/New", "modelId": "Qwen/New", "createdAt": "2026-09-25T01:00:00.000Z", "downloads": 10, "likes": 2},
        {"id": "Qwen/Old", "modelId": "Qwen/Old", "createdAt": "2026-08-01T01:00:00.000Z", "lastModified": "2026-09-25T01:00:00.000Z"},
    ]
    requested = []

    def fake_urlopen(request, timeout):
        requested.append(request.full_url)
        return _Response(json.dumps(payload).encode("utf-8"))

    monkeypatch.setattr(public_module, "urlopen", fake_urlopen)

    items = adapter.collect("2026-09-24", "2026-09-25")

    assert "author=Qwen" in requested[0] and "sort=createdAt" in requested[0]
    assert [item.raw_id for item in items] == ["Qwen/New"]
    signal = adapter.normalize(items[0])
    assert signal.url == "https://huggingface.co/Qwen/New"
    assert signal.metadata["model_release"] == {"provider": "Qwen", "channel": "huggingface"}


def test_huggingface_org_records_partial_error_for_failing_org(monkeypatch):
    _no_sleep(monkeypatch)
    adapter = HuggingFaceOrgAdapter("huggingface_orgs", "technology", {"bad": "Bad", "good": "Good"})

    def fake_urlopen(request, timeout):
        if "author=bad" in request.full_url:
            raise HTTPError(request.full_url, 404, "Not Found", None, None)
        return _Response(b"[]")

    monkeypatch.setattr(public_module, "urlopen", fake_urlopen)

    assert adapter.collect("2026-09-24", "2026-09-25") == []
    assert [error["type"] for error in adapter.partial_errors] == ["partial_feed_error"]


_OLLAMA_RSS = b"""<?xml version="1.0"?><rss><channel>
<item><title>NVIDIA Nemotron 3.5 Lightning</title><link>https://ollama.com/blog/nemotron</link>
<guid>https://ollama.com/blog/nemotron</guid><pubDate>Thu, 25 Sep 2026 00:00:00 +0000</pubDate></item>
<item><title>Ollama's transparent pricing</title><link>https://ollama.com/blog/pricing</link>
<guid>https://ollama.com/blog/pricing</guid><pubDate>Thu, 25 Sep 2026 00:00:00 +0000</pubDate></item>
<item><title>Old model post</title><link>https://ollama.com/blog/old</link>
<guid>https://ollama.com/blog/old</guid><pubDate>Mon, 10 Aug 2026 00:00:00 +0000</pubDate></item>
</channel></rss>"""

_OLLAMA_POSTS = {
    "https://ollama.com/blog/nemotron": (
        '<a href="https://ollama.com/library/nemotron-3.5-lightning">model</a>'
        "<pre>ollama run nemotron-3.5-lightning:30b</pre><p>Try ollama run tev1.</p>"
    ),
    "https://ollama.com/blog/pricing": "<p>Pricing is now simpler. Example: ollama run my-model</p>",
}


def _ollama_urlopen(fetched: list[str]):
    def fake_urlopen(request, timeout):
        fetched.append(request.full_url)
        if request.full_url.endswith("rss.xml"):
            return _Response(_OLLAMA_RSS)
        return _Response(_OLLAMA_POSTS[request.full_url].encode("utf-8"))

    return fake_urlopen


def test_ollama_blog_marks_model_posts_and_ignores_run_examples(monkeypatch):
    adapter = OllamaBlogAdapter("ollama", "technology")
    fetched: list[str] = []
    monkeypatch.setattr(public_module, "urlopen", _ollama_urlopen(fetched))

    signals = {signal.title: signal for signal in map(adapter.normalize, adapter.collect("2026-09-24", "2026-09-25"))}

    assert set(signals) == {"NVIDIA Nemotron 3.5 Lightning", "Ollama's transparent pricing"}
    assert signals["NVIDIA Nemotron 3.5 Lightning"].metadata["model_release"] == {
        "provider": "Ollama",
        "channel": "ollama",
        # tev1 is only in an `ollama run` example and not in the title/URL, so it is not trusted.
        "models": ["nemotron-3.5-lightning"],
    }
    assert "model_release" not in signals["Ollama's transparent pricing"].metadata
    # Out-of-period posts are not fetched at all.
    assert "https://ollama.com/blog/old" not in fetched


def test_ollama_blog_keeps_post_when_page_fetch_fails(monkeypatch):
    adapter = OllamaBlogAdapter("ollama", "technology")

    def fake_urlopen(request, timeout):
        if request.full_url.endswith("rss.xml"):
            return _Response(_OLLAMA_RSS)
        raise HTTPError(request.full_url, 404, "Not Found", None, None)

    monkeypatch.setattr(public_module, "urlopen", fake_urlopen)

    items = adapter.collect("2026-09-24", "2026-09-25")

    assert len(items) == 2
    assert all("model_release" not in item.payload["metadata"] for item in items)
    assert [error["type"] for error in adapter.partial_errors] == ["partial_feed_error", "partial_feed_error"]


def _signal(signal_id: str, source: str, metadata: dict) -> CanonicalSignal:
    return CanonicalSignal(
        signal_id=signal_id,
        source=source,
        source_family="technology",
        content_type="model",
        title="org/model",
        url="https://huggingface.co/org/model",
        published_at=None,
        fetched_at=datetime(2026, 9, 25, tzinfo=timezone.utc),
        summary="",
        categories=[],
        raw_metrics={},
        normalized_scores={},
        metadata=metadata,
    )


def test_dedup_keeps_model_release_marker_from_second_signal():
    marker = {"provider": "Org", "channel": "huggingface"}
    merged = deduplicate_signals(
        [
            _signal("huggingface:org/model", "huggingface", {"event_type": "observed_signal"}),
            _signal("huggingface_orgs:org/model", "huggingface_orgs", {"event_type": "observed_signal", "model_release": marker}),
        ]
    )

    assert len(merged) == 1
    assert merged[0].metadata["model_release"] == marker


def test_cli_collect_records_partial_errors(tmp_path: Path, monkeypatch):
    class PartialAdapter(SourceAdapter):
        source_name = "official_blogs"
        source_family = "official"
        partial_errors = [{"source": "official_blogs", "type": "partial_feed_error", "message": "https://feed/a: boom"}]

        def collect(self, since, until):
            return []

        def normalize(self, item):
            raise AssertionError("no items")

    monkeypatch.setattr(collect_command, "build_adapters", lambda configs: [PartialAdapter()])

    assert main(["collect", "--until", "2026-09-25", "--data-dir", str(tmp_path / "data")]) == 0

    state = json.loads((tmp_path / "data" / "runs" / "2026-09-25" / "run_state.json").read_text(encoding="utf-8"))
    assert state["errors"] == PartialAdapter.partial_errors
    assert state["input_counts"]["official_blogs"] == 0


def test_official_feed_keywords_match_on_word_boundaries_and_legacy_rule_still_applies():
    from ai_research_radar.sources.public import _map_official_feed

    def marked(title: str, keywords: list[str]) -> bool:
        entry = {"title": title, "link": "https://e/x", "guid": title, "pubDate": "Thu, 25 Sep 2026 08:00:00 +0000"}
        return "model_release" in _map_official_feed(entry, "P", keywords).payload["metadata"]

    assert marked("Introducing GPT-6.1 Sol", ["gpt-"])
    assert not marked("Coveo search update", ["veo"])
    assert marked("Veo 4 is here", ["veo"])
    assert marked("Mistral Large 3", ["mistral large"])
    assert not marked("Hallo, Deutschland!", ["mistral large"])
    legacy = _map_official_feed({"title": "We launch a new model", "guid": "g"}, "P", [])
    assert legacy.payload["metadata"]["event_type"] == "major_model_release"
    assert "model_release" in legacy.payload["metadata"]
    api = _map_official_feed({"title": "Gemini API launch", "guid": "g"}, "P", ["gemini"])
    assert api.payload["metadata"]["event_type"] == "major_api_release"


def test_official_feeds_report_entries_without_url_as_config_error(monkeypatch):
    adapter = OfficialFeedsAdapter(
        "official_blogs", "official", [{"provider": "A"}, {"provider": "B", "url": "https://feed/b"}]
    )
    monkeypatch.setattr(public_module, "urlopen", lambda request, timeout: _Response(_rss("B news")))

    assert len(adapter.collect("2026-09-24", "2026-09-25")) == 1
    assert [error["type"] for error in adapter.partial_errors] == ["config_error"]


def test_run_daily_records_partial_errors(tmp_path: Path):
    from ai_research_radar.pipeline.daily import run_daily

    class PartialAdapter(SourceAdapter):
        source_name = "official_blogs"
        source_family = "official"
        partial_errors = [{"source": "official_blogs", "type": "partial_feed_error", "message": "https://feed/a: boom"}]

        def collect(self, since, until):
            return []

        def normalize(self, item):
            raise AssertionError("no items")

    result = run_daily([PartialAdapter()], "2026-09-24", "2026-09-25", tmp_path / "data", tmp_path / "reports")

    assert PartialAdapter.partial_errors[0] in result.run.errors


def test_ollama_post_classification_rules():
    from ai_research_radar.sources.public import _ollama_models_in_post

    # run-only model whose name is in the title/URL
    assert _ollama_models_in_post("<pre>ollama run minimax-m2:cloud</pre>", "MiniMax M2", "https://ollama.com/blog/minimax-m2") == ["minimax-m2"]
    # feature post with an `ollama run` example
    assert _ollama_models_in_post("<pre>ollama run gemma4</pre>", "Faster on MLX", "https://ollama.com/blog/mlx-performance") == []
    # "models" in the title adopts linked library models
    assert _ollama_models_in_post('<a href="/library/tev1">x</a><a href="/library/nimble">y</a>', "Ollama now supports decision models", "https://ollama.com/blog/x") == ["nimble", "tev1"]
    # tutorial that links many library models without introducing them
    assert _ollama_models_in_post('<a href="https://ollama.com/library/glm-5">x</a>', "The fastest way to setup OpenClaw", "https://ollama.com/blog/openclaw") == []
    # singular "model" is not enough
    assert _ollama_models_in_post('<a href="/library/llama3">x</a>', "New model scheduling", "https://ollama.com/blog/new-model-scheduling") == []


def test_official_feed_model_categories_limit_keyword_matches(monkeypatch):
    adapter = OfficialFeedsAdapter("official_blogs", "official", [_openai_feed(["Product", "Research", "Release"])])
    body = _rss_with_categories(
        ("Introducing GPT-7", [" product "]),
        ("Introducing gpt-oss", ["RELEASE"]),
        ("A model guide for the GPT-6 family", ["Company", "Product"]),
        ("Basis completes a tax workbook 2x faster with GPT-6 Astra", []),
        ("Harvey turns legal context into stronger drafts with GPT-6 Astra", ["Startup"]),
    )
    monkeypatch.setattr(public_module, "urlopen", lambda request, timeout: _Response(body))

    assert _model_release_titles(adapter) == {
        "Introducing GPT-7",
        "Introducing gpt-oss",
        "A model guide for the GPT-6 family",
    }


@pytest.mark.parametrize("model_categories", [None, [], "Product"])
def test_official_feed_without_valid_model_categories_uses_keywords_only(monkeypatch, model_categories):
    adapter = OfficialFeedsAdapter("official_blogs", "official", [_openai_feed(model_categories)])
    body = _rss_with_categories(("Basis completes a tax workbook 2x faster with GPT-6 Astra", []))
    monkeypatch.setattr(public_module, "urlopen", lambda request, timeout: _Response(body))

    assert _model_release_titles(adapter) == {"Basis completes a tax workbook 2x faster with GPT-6 Astra"}


def test_official_feed_title_release_rule_ignores_model_categories(monkeypatch):
    adapter = OfficialFeedsAdapter("official_blogs", "official", [_openai_feed(["Product"])])
    body = _rss_with_categories(("We launch a new reasoning model", ["Startup"]))
    monkeypatch.setattr(public_module, "urlopen", lambda request, timeout: _Response(body))

    items = adapter.collect("2026-09-24", "2026-09-25")

    assert items[0].payload["metadata"]["event_type"] == "major_model_release"
    assert "model_release" in items[0].payload["metadata"]


def test_official_feed_reads_atom_category_term(monkeypatch):
    adapter = OfficialFeedsAdapter("official_blogs", "official", [_openai_feed(["Product"])])
    body = (
        '<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">'
        '<entry><title>Introducing GPT-7</title><link href="https://example.com/a"/><id>a</id>'
        '<updated>2026-09-25T08:00:00Z</updated><category term="Product"/></entry>'
        '<entry><title>Story with GPT-7</title><link href="https://example.com/b"/><id>b</id>'
        '<updated>2026-09-25T08:00:00Z</updated><category term="Startup"/></entry></feed>'
    ).encode("utf-8")
    monkeypatch.setattr(public_module, "urlopen", lambda request, timeout: _Response(body))

    assert _model_release_titles(adapter) == {"Introducing GPT-7"}


def test_shared_feed_entries_keep_first_category_only():
    from xml.etree import ElementTree

    root = ElementTree.fromstring(_rss_with_categories(("Title", ["Product", "Research"])))

    entry = public_module._feed_entries(root)[0]

    # Generic RSS / Ollama payload.raw must not change with the official category rule.
    assert entry["category"] == "Product"
    assert sorted(entry) == ["category", "guid", "link", "pubDate", "title"]
