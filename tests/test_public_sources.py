from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit

import pytest

from ai_research_radar.config.settings import SourceConfig, load_source_configs
import ai_research_radar.sources.public as public_module
from ai_research_radar.sources.public import (
    HuggingFaceOrgAdapter,
    OfficialFeedsAdapter,
    OllamaBlogAdapter,
    PublicArxivAdapter,
    PublicFeedAdapter,
    PublicSearchAdapter,
    build_adapters,
)
from ai_research_radar.sources.base import SourceAdapter
from ai_research_radar.sources.public import USER_AGENT


def test_build_adapters_uses_configured_sources():
    configs = load_source_configs(Path("config/sources.yaml"))

    adapters = build_adapters(configs)

    names = {adapter.source_name for adapter in adapters}
    assert "github" in names
    assert "pypi" in names
    assert "npm" in names
    assert "arxiv" in names


def test_default_source_config_builds_public_and_arxiv_adapters():
    configs = load_source_configs(Path("config/sources.yaml"))

    adapters = build_adapters(configs)
    adapters_by_name = {adapter.source_name: adapter for adapter in adapters}

    assert all(isinstance(adapter, SourceAdapter) for adapter in adapters)
    assert isinstance(adapters_by_name["arxiv"], PublicArxivAdapter)


def test_build_adapters_can_create_public_adapter_without_network_call():

    configs = [
        SourceConfig(
            name="github",
            family="technology",
            adapter="github",
            enabled=True,
            auth_required=False,
            options={"keywords": ["agent"], "package_limit": 10},
        )
    ]

    adapters = build_adapters(configs)

    assert isinstance(adapters[0], PublicSearchAdapter)
    assert adapters[0].source_name == "github"


def test_default_sources_use_source_appropriate_public_adapters_and_endpoints():
    adapters = build_adapters(load_source_configs(Path("config/sources.yaml")))
    adapters_by_name = {adapter.source_name: adapter for adapter in adapters}

    assert isinstance(adapters_by_name["official_blogs"], OfficialFeedsAdapter)
    assert adapters_by_name["official_blogs"].feeds
    assert all("github.com" not in feed["url"] for feed in adapters_by_name["official_blogs"].feeds)
    assert isinstance(adapters_by_name["huggingface_orgs"], HuggingFaceOrgAdapter)
    assert isinstance(adapters_by_name["ollama"], OllamaBlogAdapter)
    assert isinstance(adapters_by_name["pypi"], PublicFeedAdapter)
    assert adapters_by_name["pypi"].endpoint == "https://pypi.org/rss/updates.xml"


def test_github_collect_adds_period_to_query_and_normalize_keeps_raw_and_date(monkeypatch):
    adapter = next(
        adapter
        for adapter in build_adapters(load_source_configs(Path("config/sources.yaml")))
        if adapter.source_name == "github"
    )
    captured_urls: list[str] = []

    class Response:
        def read(self) -> bytes:
            return b'{"items":[{"id":1,"full_name":"org/agent","html_url":"https://github.com/org/agent","description":"agent","stargazers_count":1000,"created_at":"2026-09-24T10:00:00Z","updated_at":"2026-09-25T10:00:00Z"}]}'

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(request, timeout: int):
        captured_urls.append(request.full_url)
        return Response()

    monkeypatch.setattr(public_module, "urlopen", fake_urlopen)

    items = adapter.collect(since="2026-09-24", until="2026-09-25")
    signal = adapter.normalize(items[0])

    query = parse_qs(urlsplit(captured_urls[0]).query)
    assert "pushed:2026-09-24..2026-09-25" in query["q"][0]
    assert items[0].payload["raw"]["stargazers_count"] == 1000
    assert signal.published_at == datetime(2026, 9, 24, 10, 0, tzinfo=timezone.utc)
    assert 0 <= signal.normalized_scores["popularity"] <= 100
    assert 0 <= signal.normalized_scores["momentum"] <= 100


def test_pypi_rss_filters_non_ai_entries_and_keeps_raw_entry(monkeypatch):
    adapter = next(
        adapter
        for adapter in build_adapters(load_source_configs(Path("config/sources.yaml")))
        if adapter.source_name == "pypi"
    )
    xml = """<?xml version=\"1.0\"?><rss><channel>
    <item><title>llm-tool 1.0</title><link>https://pypi.org/project/llm-tool/</link><guid>llm-tool</guid><pubDate>Thu, 25 Sep 2026 08:00:00 +0000</pubDate></item>
    <item><title>calendar-widget 1.0</title><link>https://pypi.org/project/calendar-widget/</link><guid>calendar-widget</guid><pubDate>Thu, 25 Sep 2026 08:00:00 +0000</pubDate></item>
    </channel></rss>"""

    class Response:
        def read(self) -> bytes:
            return xml.encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(public_module, "urlopen", lambda url, timeout: Response())

    items = adapter.collect(since="2026-09-24", until="2026-09-25")

    assert [item.raw_id for item in items] == ["llm-tool"]
    assert items[0].payload["raw"]["title"] == "llm-tool 1.0"


def test_zenn_adapter_reads_articles_response_shape():
    adapter = next(
        adapter
        for adapter in build_adapters(load_source_configs(Path("config/sources.yaml")))
        if adapter.source_name == "zenn"
    )

    assert adapter.item_selector({"articles": [{"id": 1}]}) == [{"id": 1}]


def test_official_blog_update_is_not_automatically_a_major_release(monkeypatch):
    adapter = next(
        adapter
        for adapter in build_adapters(load_source_configs(Path("config/sources.yaml")))
        if adapter.source_name == "official_blogs"
    )
    xml = """<?xml version=\"1.0\"?><rss><channel><item>
    <title>Company update</title><link>https://example.com/update</link><guid>update</guid>
    <pubDate>Thu, 25 Sep 2026 08:00:00 +0000</pubDate>
    </item></channel></rss>"""

    class Response:
        def read(self) -> bytes:
            return xml.encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(public_module, "urlopen", lambda url, timeout: Response())

    item = adapter.collect(since="2026-09-24", until="2026-09-25")[0]

    assert adapter.normalize(item).metadata["event_type"] == "observed_signal"


def test_search_adapter_collect_sends_user_agent_header(monkeypatch):
    adapter = next(
        adapter
        for adapter in build_adapters(load_source_configs(Path("config/sources.yaml")))
        if adapter.source_name == "github"
    )
    captured_requests = []

    class Response:
        def read(self) -> bytes:
            return b'{"items":[]}'

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(request, timeout: int):
        captured_requests.append(request)
        return Response()

    monkeypatch.setattr(public_module, "urlopen", fake_urlopen)

    adapter.collect(since="2026-09-24", until="2026-09-25")

    assert captured_requests[0].get_header("User-agent") == USER_AGENT


def test_arxiv_adapter_collect_sends_user_agent_header(monkeypatch):
    adapter = next(
        adapter
        for adapter in build_adapters(load_source_configs(Path("config/sources.yaml")))
        if adapter.source_name == "arxiv"
    )
    captured_requests = []
    xml = '<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"></feed>'

    class Response:
        def read(self) -> bytes:
            return xml.encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(request, timeout: int):
        captured_requests.append(request)
        return Response()

    monkeypatch.setattr(public_module, "urlopen", fake_urlopen)

    adapter.collect(since="2026-09-24", until="2026-09-25")

    assert captured_requests[0].get_header("User-agent") == USER_AGENT


def test_feed_adapter_collect_sends_user_agent_header(monkeypatch):
    adapter = next(
        adapter
        for adapter in build_adapters(load_source_configs(Path("config/sources.yaml")))
        if adapter.source_name == "official_blogs"
    )
    captured_requests = []
    xml = "<?xml version=\"1.0\"?><rss><channel></channel></rss>"

    class Response:
        def read(self) -> bytes:
            return xml.encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(request, timeout: int):
        captured_requests.append(request)
        return Response()

    monkeypatch.setattr(public_module, "urlopen", fake_urlopen)

    adapter.collect(since="2026-09-24", until="2026-09-25")

    assert captured_requests[0].get_header("User-agent") == USER_AGENT


def test_search_adapter_collect_retries_on_429_then_succeeds(monkeypatch):
    adapter = next(
        adapter
        for adapter in build_adapters(load_source_configs(Path("config/sources.yaml")))
        if adapter.source_name == "github"
    )

    class Response:
        def read(self) -> bytes:
            return b'{"items":[]}'

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    attempts = {"count": 0}

    def fake_urlopen(request, timeout: int):
        attempts["count"] += 1
        if attempts["count"] < 2:
            raise HTTPError(request.full_url, 429, "Too Many Requests", None, None)
        return Response()

    monkeypatch.setattr(public_module, "urlopen", fake_urlopen)
    monkeypatch.setattr(public_module, "_sleep", lambda seconds: None)

    items = adapter.collect(since="2026-09-24", until="2026-09-25")

    assert items == []
    assert attempts["count"] == 2


def test_search_adapter_collect_does_not_retry_permanent_errors(monkeypatch):
    adapter = next(
        adapter
        for adapter in build_adapters(load_source_configs(Path("config/sources.yaml")))
        if adapter.source_name == "arxiv"
    )
    attempts = {"count": 0}
    slept = {"called": False}

    def fake_urlopen(request, timeout: int):
        attempts["count"] += 1
        raise HTTPError(request.full_url, 406, "Not Acceptable", None, None)

    def fake_sleep(seconds: float) -> None:
        slept["called"] = True

    monkeypatch.setattr(public_module, "urlopen", fake_urlopen)
    monkeypatch.setattr(public_module, "_sleep", fake_sleep)

    try:
        adapter.collect(since="2026-09-24", until="2026-09-25")
    except HTTPError as exc:
        assert exc.code == 406
    else:
        raise AssertionError("expected HTTPError to propagate")

    assert attempts["count"] == 1
    assert slept["called"] is False


def test_search_adapter_collect_gives_up_after_max_attempts_on_persistent_429(monkeypatch):
    adapter = next(
        adapter
        for adapter in build_adapters(load_source_configs(Path("config/sources.yaml")))
        if adapter.source_name == "openalex"
    )
    attempts = {"count": 0}

    def fake_urlopen(request, timeout: int):
        attempts["count"] += 1
        raise HTTPError(request.full_url, 429, "Too Many Requests", None, None)

    monkeypatch.setattr(public_module, "urlopen", fake_urlopen)
    monkeypatch.setattr(public_module, "_sleep", lambda seconds: None)

    try:
        adapter.collect(since="2026-09-24", until="2026-09-25")
    except HTTPError as exc:
        assert exc.code == 429
    else:
        raise AssertionError("expected HTTPError to propagate")

    assert attempts["count"] == public_module._MAX_ATTEMPTS


def test_feed_adapter_collect_retries_on_503_then_succeeds(monkeypatch):
    adapter = next(
        adapter
        for adapter in build_adapters(load_source_configs(Path("config/sources.yaml")))
        if adapter.source_name == "pypi"
    )
    xml = "<?xml version=\"1.0\"?><rss><channel></channel></rss>"

    class Response:
        def read(self) -> bytes:
            return xml.encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    attempts = {"count": 0}

    def fake_urlopen(request, timeout: int):
        attempts["count"] += 1
        if attempts["count"] < 2:
            raise HTTPError(request.full_url, 503, "Service Unavailable", None, None)
        return Response()

    monkeypatch.setattr(public_module, "urlopen", fake_urlopen)
    monkeypatch.setattr(public_module, "_sleep", lambda seconds: None)

    adapter.collect(since="2026-09-24", until="2026-09-25")

    assert attempts["count"] == 2


def test_arxiv_adapter_collect_retries_on_network_error(monkeypatch):
    adapter = next(
        adapter
        for adapter in build_adapters(load_source_configs(Path("config/sources.yaml")))
        if adapter.source_name == "arxiv"
    )
    xml = '<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"></feed>'

    class Response:
        def read(self) -> bytes:
            return xml.encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    attempts = {"count": 0}

    def fake_urlopen(request, timeout: int):
        attempts["count"] += 1
        if attempts["count"] < 2:
            raise URLError("connection reset")
        return Response()

    monkeypatch.setattr(public_module, "urlopen", fake_urlopen)
    monkeypatch.setattr(public_module, "_sleep", lambda seconds: None)

    adapter.collect(since="2026-09-24", until="2026-09-25")

    assert attempts["count"] == 2


def test_openalex_query_includes_mailto_when_env_var_set(monkeypatch):
    monkeypatch.setenv("AI_RADAR_OPENALEX_MAILTO", "radar@example.com")
    adapter = next(
        adapter
        for adapter in build_adapters(load_source_configs(Path("config/sources.yaml")))
        if adapter.source_name == "openalex"
    )

    assert adapter.query_params["mailto"] == "radar@example.com"


def test_openalex_query_omits_mailto_when_env_var_unset(monkeypatch):
    monkeypatch.delenv("AI_RADAR_OPENALEX_MAILTO", raising=False)
    adapter = next(
        adapter
        for adapter in build_adapters(load_source_configs(Path("config/sources.yaml")))
        if adapter.source_name == "openalex"
    )

    assert "mailto" not in adapter.query_params


def test_build_adapters_chooses_by_adapter_key_so_a_source_can_be_renamed(monkeypatch):
    configs = [SourceConfig("github_mcp", "technology", "github", True, False, {"keywords": ["mcp"]})]
    (adapter,) = build_adapters(configs)

    class Response:
        def read(self) -> bytes:
            return b'{"items":[{"id":1,"full_name":"org/mcp","html_url":"https://github.com/org/mcp","description":"mcp","stargazers_count":5,"created_at":"2026-09-24T10:00:00Z","updated_at":"2026-09-25T10:00:00Z"}]}'

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    captured: list[str] = []
    monkeypatch.setattr(public_module, "urlopen", lambda request, timeout: captured.append(request.full_url) or Response())

    items = adapter.collect(since="2026-09-24", until="2026-09-25")
    signal = adapter.normalize(items[0])

    assert captured[0].startswith("https://api.github.com/search/repositories?")
    assert parse_qs(urlsplit(captured[0]).query)["q"][0].startswith("mcp in:name,description")
    assert items[0].source == "github_mcp"
    assert signal.signal_id == "github_mcp:1"


def test_build_adapters_rejects_unknown_adapter():
    with pytest.raises(ValueError, match="unknown adapter 'nope' for source 'x'"):
        build_adapters([SourceConfig("x", "technology", "nope", True, False, {})])
