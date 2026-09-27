from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from ai_research_radar.config.settings import load_source_configs
import ai_research_radar.sources.public as public_module
from ai_research_radar.schemas.models import RawItem
from ai_research_radar.sources.public import (
    PublicArxivAdapter,
    PublicFeedAdapter,
    PublicSearchAdapter,
    build_adapters,
)
from ai_research_radar.sources.base import SourceAdapter


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
    from ai_research_radar.config.settings import SourceConfig
    from ai_research_radar.sources.public import PublicSearchAdapter

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

    assert isinstance(adapters_by_name["official_blogs"], PublicFeedAdapter)
    assert "github.com" not in adapters_by_name["official_blogs"].endpoint
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

    def fake_urlopen(url: str, timeout: int):
        captured_urls.append(url)
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
