from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from ai_research_radar.config.settings import SourceConfig
from ai_research_radar.normalization.scores import (
    is_within_period,
    normalized_scores,
    parse_optional_datetime,
)
from ai_research_radar.periods import period_date, period_end, period_start
from ai_research_radar.schemas.models import CanonicalSignal, RawItem
from ai_research_radar.normalization.relevance import classify_relevance, restore_abstract
from ai_research_radar.sources.remap import remap_raw_item
from ai_research_radar.sources.base import SourceAdapter
from ai_research_radar.sources.fixtures import FixtureAdapter

RawItemMapper = Callable[[dict[str, Any]], RawItem]
PeriodParams = Callable[[dict[str, str], str, str], dict[str, str]]

USER_AGENT = "ai-research-radar/0.1.0"

# OpenAlex gives requests that identify a contact a higher, less-throttled
# rate limit ("polite pool"). Read from the environment rather than hardcoding
# a contact address in source control.
_OPENALEX_MAILTO_ENV_VAR = "AI_RADAR_OPENALEX_MAILTO"

# Only retry statuses that are typically transient (rate limiting, upstream
# outages). Permanent errors (403/404/406/...) are not retried: retrying them
# just burns the request budget without changing the outcome.
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
_MAX_ATTEMPTS = 3
_BASE_DELAY_SECONDS = 1.0
_MAX_DELAY_SECONDS = 10.0

# Aliased so tests can monkeypatch away the real delay without touching the
# stdlib `time` module.
_sleep = time.sleep


def _build_request(url: str) -> Request:
    return Request(url, headers={"User-Agent": USER_AGENT})


def _open_with_retry(request: Request, timeout: int = 20):
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            return urlopen(request, timeout=timeout)
        except HTTPError as exc:
            if exc.code not in _RETRYABLE_STATUS_CODES or attempt == _MAX_ATTEMPTS:
                raise
            _sleep(_retry_delay(attempt, exc))
        except URLError:
            if attempt == _MAX_ATTEMPTS:
                raise
            _sleep(_retry_delay(attempt, None))
    raise AssertionError("unreachable")  # pragma: no cover


def _read_body(response) -> bytes:
    # Some feeds (e.g. Google DeepMind) answer gzip-compressed even without an
    # Accept-Encoding request header, and urllib does not decode it for us.
    body = response.read()
    if body[:2] == b"\x1f\x8b":
        return gzip.decompress(body)
    return body


def _retry_delay(attempt: int, exc: HTTPError | None) -> float:
    if exc is not None and exc.headers is not None:
        retry_after = exc.headers.get("Retry-After")
        if retry_after is not None:
            try:
                return min(float(retry_after), _MAX_DELAY_SECONDS)
            except ValueError:
                pass
    return min(_BASE_DELAY_SECONDS * (2 ** (attempt - 1)), _MAX_DELAY_SECONDS)


class PublicSearchAdapter(SourceAdapter):
    def __init__(
        self,
        source_name: str,
        source_family: str,
        endpoint: str,
        query_params: dict[str, str],
        item_mapper: RawItemMapper,
        item_selector: Callable[[Any], list[dict[str, Any]]] | None = None,
        period_params: PeriodParams | None = None,
        credibility: float = 60.0,
    ) -> None:
        self.source_name = source_name
        self.source_family = source_family
        self.endpoint = endpoint
        self.query_params = query_params
        self.item_mapper = item_mapper
        self.item_selector = item_selector or _default_items
        self.period_params = period_params or _without_period_params
        self.credibility = credibility

    def collect(self, since: str, until: str) -> list[RawItem]:
        params = self.period_params(dict(self.query_params), since, until)
        url = f"{self.endpoint}?{urlencode(params)}" if params else self.endpoint
        with _open_with_retry(_build_request(url)) as response:
            payload = json.loads(_read_body(response).decode("utf-8"))
        items = [self.item_mapper(item) for item in self.item_selector(payload)]
        return [item for item in items if _item_is_in_period(item, since, until)]

    def normalize(self, item: RawItem) -> CanonicalSignal:
        return _normalize_raw_item(remap_raw_item(item, self.source_name), self.source_family, self.credibility)


class PublicArxivAdapter(PublicSearchAdapter):
    def collect(self, since: str, until: str) -> list[RawItem]:
        params = self.period_params(dict(self.query_params), since, until)
        url = f"{self.endpoint}?{urlencode(params)}" if params else self.endpoint
        with _open_with_retry(_build_request(url)) as response:
            root = ElementTree.fromstring(_read_body(response).decode("utf-8"))
        namespace = {"atom": "http://www.w3.org/2005/Atom"}
        items = [
            _map_arxiv_entry(_element_to_dict(entry))
            for entry in root.findall("atom:entry", namespace)[:100]
        ]
        return [item for item in items if _item_is_in_period(item, since, until)]


class PublicFeedAdapter(SourceAdapter):
    def __init__(
        self,
        source_name: str,
        source_family: str,
        endpoint: str,
        entry_mapper: RawItemMapper,
        keywords: list[str] | None = None,
        credibility: float = 80.0,
    ) -> None:
        self.source_name = source_name
        self.source_family = source_family
        self.endpoint = endpoint
        self.entry_mapper = entry_mapper
        self.keywords = [keyword.lower() for keyword in keywords or []]
        self.credibility = credibility

    def collect(self, since: str, until: str) -> list[RawItem]:
        with _open_with_retry(_build_request(self.endpoint)) as response:
            root = ElementTree.fromstring(_read_body(response).decode("utf-8"))
        items = [self.entry_mapper(entry) for entry in _feed_entries(root)]
        return [
            item
            for item in items
            if _matches_keywords(item, self.keywords) and _item_is_in_period(item, since, until)
        ]

    def normalize(self, item: RawItem) -> CanonicalSignal:
        return _normalize_raw_item(remap_raw_item(item, self.source_name), self.source_family, self.credibility)


class OfficialFeedsAdapter(SourceAdapter):
    """Reads several vendor RSS/Atom feeds as one `official_blogs` source.

    A failing feed is recorded in `partial_errors` and the remaining feeds are
    still collected; only when every feed fails does `collect` raise.
    """

    def __init__(
        self,
        source_name: str,
        source_family: str,
        feeds: list[dict[str, Any]],
        credibility: float = 95.0,
    ) -> None:
        self.source_name = source_name
        self.source_family = source_family
        self.feeds = feeds
        self.credibility = credibility
        self.partial_errors: list[dict[str, str]] = []

    def collect(self, since: str, until: str) -> list[RawItem]:
        self.partial_errors = []
        items: list[RawItem] = []
        failures: list[Exception] = []
        for feed in self.feeds:
            url = str(feed.get("url") or "")
            if not url:
                failures.append(ValueError(f"feed entry without url: {feed}"))
                self.partial_errors.append(
                    {"source": self.source_name, "type": "config_error", "message": f"feed entry without url: {feed}"}
                )
                continue
            try:
                with _open_with_retry(_build_request(url)) as response:
                    root = ElementTree.fromstring(_read_body(response).decode("utf-8"))
            except Exception as exc:  # noqa: BLE001 - one bad feed must not drop the others
                failures.append(exc)
                self.partial_errors.append(
                    {"source": self.source_name, "type": "partial_feed_error", "message": f"{url}: {exc}"}
                )
                continue
            provider = str(feed.get("provider", "OpenAI"))
            keywords = [str(value).lower() for value in feed.get("model_keywords", [])]
            for entry in _feed_entries(root):
                item = _map_official_feed(entry, provider=provider, model_keywords=keywords)
                if _item_is_in_period(item, since, until):
                    items.append(item)
        if self.feeds and len(failures) == len(self.feeds):
            raise failures[-1]
        return items

    def normalize(self, item: RawItem) -> CanonicalSignal:
        return _normalize_raw_item(item, self.source_family, self.credibility)


class HuggingFaceOrgAdapter(SourceAdapter):
    """Detects newly created models of watched Hugging Face organizations."""

    endpoint = "https://huggingface.co/api/models"

    def __init__(
        self,
        source_name: str,
        source_family: str,
        orgs: dict[str, str],
        per_org_limit: int = 50,
        credibility: float = 80.0,
    ) -> None:
        self.source_name = source_name
        self.source_family = source_family
        self.orgs = orgs
        self.per_org_limit = per_org_limit
        self.credibility = credibility
        self.partial_errors: list[dict[str, str]] = []

    def collect(self, since: str, until: str) -> list[RawItem]:
        self.partial_errors = []
        items: list[RawItem] = []
        failures: list[Exception] = []
        for org, provider in self.orgs.items():
            params = {"author": org, "sort": "createdAt", "direction": "-1", "limit": str(self.per_org_limit)}
            url = f"{self.endpoint}?{urlencode(params)}"
            try:
                with _open_with_retry(_build_request(url)) as response:
                    payload = json.loads(_read_body(response).decode("utf-8"))
            except Exception as exc:  # noqa: BLE001 - one bad org must not drop the others
                failures.append(exc)
                self.partial_errors.append(
                    {"source": self.source_name, "type": "partial_feed_error", "message": f"{org}: {exc}"}
                )
                continue
            for model in _default_items(payload):
                item = _map_huggingface_org(model, self.source_name, str(provider))
                # A new release is a repository *created* in the period, not one
                # that was merely modified.
                if is_within_period(parse_optional_datetime(item.payload.get("published_at")), since, until):
                    items.append(item)
        if self.orgs and len(failures) == len(self.orgs):
            raise failures[-1]
        return items

    def normalize(self, item: RawItem) -> CanonicalSignal:
        return _normalize_raw_item(item, self.source_family, self.credibility)


class OllamaBlogAdapter(SourceAdapter):
    """Reads the Ollama blog RSS and marks posts that introduce models.

    The RSS only carries a short description, so each in-period post page is
    fetched and classified by `_ollama_models_in_post` (a mere library link or
    `ollama run` example is not enough). A post page that cannot be fetched is
    kept as a plain signal and recorded in partial_errors.
    """

    def __init__(
        self,
        source_name: str,
        source_family: str,
        endpoint: str = "https://ollama.com/blog/rss.xml",
        credibility: float = 80.0,
    ) -> None:
        self.source_name = source_name
        self.source_family = source_family
        self.endpoint = endpoint
        self.credibility = credibility
        self.partial_errors: list[dict[str, str]] = []

    def collect(self, since: str, until: str) -> list[RawItem]:
        self.partial_errors = []
        with _open_with_retry(_build_request(self.endpoint)) as response:
            root = ElementTree.fromstring(_read_body(response).decode("utf-8"))
        items: list[RawItem] = []
        for entry in _feed_entries(root):
            item = _make_raw_item(self.source_name, entry, entry.get("title"), entry.get("link"), entry.get("description"), entry.get("pubDate"), entry.get("pubDate"), {}, "announcement", raw_id=entry.get("guid") or entry.get("link"))
            if not _item_is_in_period(item, since, until):
                continue
            try:
                with _open_with_retry(_build_request(item.raw_url)) as response:
                    models = _ollama_models_in_post(
                        _read_body(response).decode("utf-8"), str(item.payload["title"]), item.raw_url
                    )
            except Exception as exc:  # noqa: BLE001 - keep the post, just without the model check
                self.partial_errors.append(
                    {"source": self.source_name, "type": "partial_feed_error", "message": f"{item.raw_url}: {exc}"}
                )
                models = []
            if models:
                item.payload["metadata"]["model_release"] = {"provider": "Ollama", "channel": "ollama", "models": models}
            items.append(item)
        return items

    def normalize(self, item: RawItem) -> CanonicalSignal:
        return _normalize_raw_item(item, self.source_family, self.credibility)

def build_adapters(configs: list[SourceConfig]) -> list[SourceAdapter]:
    adapters: list[SourceAdapter] = []
    for config in configs:
        if not config.enabled or config.auth_required:
            continue
        if config.adapter == "fixture":
            adapter: SourceAdapter = FixtureAdapter(
                source_name=config.name,
                source_family=config.family,
                fixture_path=Path(str(config.options["fixture_path"])),
            )
        else:
            adapter = _public_adapter_for(config)
        adapter.overlap_hours = _overlap_hours(config)
        adapters.append(adapter)
    return adapters


def _overlap_hours(config: SourceConfig) -> int:
    value = config.options.get("overlap_hours", 0)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return 0
    return value


def _public_adapter_for(config: SourceConfig) -> SourceAdapter:
    if config.name == "pypi":
        return PublicFeedAdapter(
            config.name,
            config.family,
            "https://pypi.org/rss/updates.xml",
            _map_pypi_feed,
            keywords=_keywords(config),
            credibility=70.0,
        )
    if config.name == "official_blogs":
        return OfficialFeedsAdapter(config.name, config.family, _official_feeds(config), credibility=95.0)
    if config.name == "huggingface_orgs":
        return HuggingFaceOrgAdapter(
            config.name,
            config.family,
            {str(org): str(provider) for org, provider in dict(config.options.get("orgs", {})).items()},
            per_org_limit=int(config.options.get("per_org_limit", 50)),
        )
    if config.name == "ollama":
        return OllamaBlogAdapter(config.name, config.family)
    endpoint_by_name = {
        "github": "https://api.github.com/search/repositories",
        "npm": "https://registry.npmjs.org/-/v1/search",
        "hackernews": "https://hn.algolia.com/api/v1/search_by_date",
        "arxiv": "https://export.arxiv.org/api/query",
        "openalex": "https://api.openalex.org/works",
        "huggingface": "https://huggingface.co/api/models",
        "qiita": "https://qiita.com/api/v2/items",
        "zenn": "https://zenn.dev/api/articles",
    }
    adapter_class = PublicArxivAdapter if config.name == "arxiv" else PublicSearchAdapter
    return adapter_class(
        source_name=config.name,
        source_family=config.family,
        endpoint=endpoint_by_name[config.name],
        query_params=_query_params_for(config),
        item_mapper=_map_arxiv_entry if config.name == "arxiv" else _mapper_for(config.name),
        item_selector=_item_selector_for(config.name),
        period_params=_period_params_for(config.name),
        credibility=85.0 if config.name in {"arxiv", "openalex"} else 70.0,
    )


def _official_feeds(config: SourceConfig) -> list[dict[str, Any]]:
    feeds = config.options.get("feeds")
    if isinstance(feeds, list) and feeds:
        # Entries without a url are kept so that collect() reports them as a
        # config error instead of silently shrinking the feed list.
        return [dict(feed) if isinstance(feed, dict) else {} for feed in feeds]
    # Legacy single-feed form.
    return [{"provider": "OpenAI", "url": str(config.options.get("feed_url", "https://openai.com/news/rss.xml"))}]


def _query_params_for(config: SourceConfig) -> dict[str, str]:
    query = " ".join(_keywords(config))
    if config.name == "github":
        return {"q": f"{query} in:name,description", "sort": "updated", "order": "desc"}
    if config.name == "npm":
        return {"text": query, "size": str(config.options.get("package_limit", 100))}
    if config.name == "hackernews":
        return {"query": query, "tags": "story"}
    if config.name == "arxiv":
        return {"search_query": f"all:({query})", "start": "0", "max_results": "100"}
    if config.name == "openalex":
        params = {"search": query, "per-page": "100"}
        mailto = os.environ.get(_OPENALEX_MAILTO_ENV_VAR)
        if mailto:
            params["mailto"] = mailto
        return params
    if config.name == "huggingface":
        return {"search": query, "sort": "lastModified", "direction": "-1", "limit": "100"}
    if config.name == "qiita":
        return {"query": query, "per_page": "100"}
    if config.name == "zenn":
        return {"order": "latest"}
    return {}


def _period_params_for(source_name: str) -> PeriodParams:
    if source_name == "github":
        return lambda params, since, until: {
            **params,
            "q": f"{params['q']} pushed:{period_date(since)}..{period_date(until)}",
        }
    if source_name == "arxiv":
        return lambda params, since, until: {
            **params,
            "search_query": (
                f"{params['search_query']} AND submittedDate:[{period_date(since).replace('-', '')}0000"
                f" TO {period_date(until).replace('-', '')}2359]"
            ),
        }
    if source_name == "hackernews":
        return lambda params, since, until: {
            **params,
            "numericFilters": f"created_at_i>={_epoch_start(since)},created_at_i<={_epoch_end(until)}",
        }
    if source_name == "openalex":
        return lambda params, since, until: {
            **params,
            "filter": f"from_publication_date:{period_date(since)},to_publication_date:{period_date(until)}",
        }
    if source_name == "qiita":
        return lambda params, since, until: {
            **params,
            "query": f"{params['query']} created:>={period_date(since)} created:<={period_date(until)}",
        }
    return _without_period_params


def _without_period_params(params: dict[str, str], since: str, until: str) -> dict[str, str]:
    return params


def _epoch_start(value: str) -> int:
    return int(period_start(value).timestamp())


def _epoch_end(value: str) -> int:
    return int(period_end(value).timestamp())


def _item_selector_for(source_name: str) -> Callable[[Any], list[dict[str, Any]]]:
    if source_name == "hackernews":
        return lambda payload: _list_from_dict(payload, "hits")
    if source_name == "openalex":
        return lambda payload: _list_from_dict(payload, "results")
    if source_name == "npm":
        return lambda payload: _list_from_dict(payload, "objects")
    if source_name == "zenn":
        return lambda payload: _list_from_dict(payload, "articles")
    return _default_items


def _default_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return _list_from_dict(payload, "items")


def _list_from_dict(payload: Any, key: str) -> list[dict[str, Any]]:
    if not isinstance(payload, dict) or not isinstance(payload.get(key), list):
        return []
    return [item for item in payload[key] if isinstance(item, dict)]


def _mapper_for(source_name: str) -> RawItemMapper:
    return {
        "github": _map_github,
        "huggingface": _map_huggingface,
        "npm": _map_npm,
        "hackernews": _map_hackernews,
        "qiita": _map_qiita,
        "zenn": _map_zenn,
        "openalex": _map_openalex,
    }[source_name]


def _map_github(item: dict[str, Any]) -> RawItem:
    return _make_raw_item("github", item, item.get("full_name"), item.get("html_url"), item.get("description"), item.get("created_at"), item.get("updated_at"), {"stars": item.get("stargazers_count"), "forks": item.get("forks_count")}, "tool")


def _map_huggingface(item: dict[str, Any]) -> RawItem:
    model_id = item.get("modelId") or item.get("id")
    return _make_raw_item("huggingface", item, model_id, f"https://huggingface.co/{model_id}" if model_id else "", item.get("pipeline_tag"), item.get("createdAt"), item.get("lastModified"), {"downloads": item.get("downloads"), "likes": item.get("likes")}, "model")


def _map_npm(item: dict[str, Any]) -> RawItem:
    package = item.get("package") if isinstance(item.get("package"), dict) else item
    links = package.get("links", {}) if isinstance(package.get("links"), dict) else {}
    score = item.get("score", {}) if isinstance(item.get("score"), dict) else {}
    return _make_raw_item(
        "npm", item, package.get("name"), links.get("npm"), package.get("description"),
        package.get("date"), package.get("date"),
        {
            "popularity": score.get("final", 0),
            "npm_search_score": score.get("final", 0),
            "quality": score.get("detail", {}).get("quality", 0)
            if isinstance(score.get("detail"), dict) else 0,
        },
        "tool",
    )


def _map_hackernews(item: dict[str, Any]) -> RawItem:
    url = item.get("url") or f"https://news.ycombinator.com/item?id={item.get('objectID', '')}"
    return _make_raw_item("hackernews", item, item.get("title"), url, item.get("story_text"), item.get("created_at"), item.get("created_at"), {"points": item.get("points"), "comments": item.get("num_comments")}, "discussion")


def _map_qiita(item: dict[str, Any]) -> RawItem:
    return _make_raw_item("qiita", item, item.get("title"), item.get("url"), item.get("body"), item.get("created_at"), item.get("updated_at"), {"likes": item.get("likes_count"), "reactions": item.get("reactions_count")}, "article")


def _map_zenn(item: dict[str, Any]) -> RawItem:
    path = item.get("path", "")
    return _make_raw_item("zenn", item, item.get("title"), f"https://zenn.dev{path}" if path else item.get("url"), item.get("excerpt"), item.get("published_at"), item.get("updated_at"), {"likes": item.get("liked_count")}, "article")


def _map_openalex(item: dict[str, Any]) -> RawItem:
    location = item.get("primary_location") if isinstance(item.get("primary_location"), dict) else {}
    return _make_raw_item("openalex", item, item.get("title"), location.get("landing_page_url") or item.get("doi"), item.get("abstract_inverted_index"), item.get("publication_date"), item.get("updated_date"), {"citations": item.get("cited_by_count")}, "paper")


def _map_arxiv_entry(entry: dict[str, Any]) -> RawItem:
    return _make_raw_item("arxiv", entry, entry.get("title"), entry.get("link"), entry.get("summary"), entry.get("published"), entry.get("updated"), {}, "paper", raw_id=entry.get("id"))


def _map_pypi_feed(entry: dict[str, Any]) -> RawItem:
    return _make_raw_item(
        "pypi", entry, entry.get("title"), entry.get("link"), entry.get("description"),
        entry.get("pubDate"), entry.get("pubDate"),
        {"ai_keyword_strength": _ai_keyword_strength(entry)},
        "package", raw_id=entry.get("guid"),
    )


def _map_official_feed(
    entry: dict[str, Any], provider: str = "OpenAI", model_keywords: list[str] | None = None
) -> RawItem:
    title = str(entry.get("title") or "")
    event_type = _official_event_type(title)
    item = _make_raw_item("official_blogs", entry, title, entry.get("link"), entry.get("description") or entry.get("summary"), entry.get("published") or entry.get("pubDate"), entry.get("updated") or entry.get("pubDate"), {}, "announcement", raw_id=entry.get("id") or entry.get("guid"), event_type=event_type)
    item.payload["metadata"]["provider"] = provider
    # model_keywords only mark the entry for the 新モデルリリース section. They do
    # not change event_type, so the Official override for HOT keeps using the
    # stricter title rule below.
    if event_type == "major_model_release" or _mentions_any(title, model_keywords or []):
        item.payload["metadata"]["model_release"] = {"provider": provider, "channel": "official"}
    return item


def _mentions_any(text: str, keywords: list[str]) -> bool:
    lowered = text.lower()
    for keyword in keywords:
        keyword = keyword.lower()
        if not keyword:
            continue
        # Word-start boundary always; word-end boundary only when the keyword
        # ends with an alphanumeric (so "gpt-" still matches "gpt-6").
        tail = r"(?![a-z0-9])" if keyword[-1].isalnum() else ""
        if re.search(rf"(?<![a-z0-9]){re.escape(keyword)}{tail}", lowered):
            return True
    return False


def _official_event_type(title: str) -> str:
    normalized_title = title.lower()
    is_release = any(word in normalized_title for word in ("release", "launch"))
    if not is_release:
        return "observed_signal"
    if "api" in normalized_title:
        return "major_api_release"
    if "model" in normalized_title:
        return "major_model_release"
    return "observed_signal"


def _map_huggingface_org(item: dict[str, Any], source: str, provider: str) -> RawItem:
    model_id = item.get("modelId") or item.get("id")
    raw_item = _make_raw_item(source, item, model_id, f"https://huggingface.co/{model_id}" if model_id else "", item.get("pipeline_tag"), item.get("createdAt"), item.get("createdAt"), {"downloads": item.get("downloads"), "likes": item.get("likes")}, "model", raw_id=model_id)
    raw_item.payload["metadata"]["model_release"] = {"provider": provider, "channel": "huggingface"}
    return raw_item


_OLLAMA_LIBRARY_LINK = re.compile(r'(?:ollama\.com|href=")/library/([A-Za-z0-9._\-]+)')
_OLLAMA_RUN = re.compile(r"ollama run ([A-Za-z0-9._\-/]+)")


def _ollama_models_in_post(page: str, title: str, url: str) -> list[str]:
    """Model names (without tags) a blog post introduces; empty for other posts.

    Feature/tutorial posts also link to library pages or show `ollama run`
    examples, so a mention alone is not enough:
    - models whose name appears in the post title or URL are adopted;
    - otherwise, when the title talks about "models" (e.g. "New coding models"),
      the models it links to in the library are adopted;
    - anything else is treated as a non-model post.
    """
    linked = {_ollama_model_name(name) for name in _OLLAMA_LIBRARY_LINK.findall(page)}
    run = {_ollama_model_name(name) for name in _OLLAMA_RUN.findall(page)}
    context = _alnum(f"{title} {url}")
    named = {name for name in linked | run if _alnum(name) and _alnum(name) in context}
    if named:
        return sorted(named)
    if re.search(r"\bmodels\b", title.lower()):
        return sorted(name for name in linked if name)
    return []


def _ollama_model_name(name: str) -> str:
    return name.split(":", 1)[0].rstrip(".")


def _alnum(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _make_raw_item(source: str, raw: dict[str, Any], title: object, url: object, summary: object, published_at: object, updated_at: object, metrics: dict[str, Any], content_type: str, raw_id: object | None = None, event_type: str = "observed_signal") -> RawItem:
    identifier = str(raw_id or raw.get("id") or raw.get("objectID") or title or _stable_id(raw))
    raw_url = str(url or "")
    return RawItem(source, datetime.now(timezone.utc), identifier, raw_url, {
        "title": str(title or identifier), "summary": _summary_text(summary), "url": raw_url,
        "published_at": _date_text(published_at), "updated_at": _date_text(updated_at),
        "content_type": content_type, "categories": ["ai"],
        "metrics": {key: value for key, value in metrics.items() if value is not None},
        "metadata": {"event_type": event_type, "source_payload_keys": sorted(raw.keys())},
        "raw": raw,
    })


def _normalize_raw_item(item: RawItem, source_family: str, credibility: float) -> CanonicalSignal:
    payload = item.payload
    metrics = dict(payload.get("metrics", {}))
    published_at = parse_optional_datetime(payload.get("published_at") or payload.get("updated_at"))
    score_timestamp = parse_optional_datetime(payload.get("updated_at") or payload.get("published_at"))
    return CanonicalSignal(
        signal_id=f"{item.source}:{item.raw_id}", source=item.source, source_family=source_family,
        content_type=str(payload.get("content_type", "tool")), title=str(payload.get("title", item.raw_id)),
        url=str(payload.get("url", item.raw_url)), published_at=published_at, fetched_at=item.fetched_at,
        summary=str(payload.get("summary", "")), categories=list(payload.get("categories", [])),
        raw_metrics=metrics, normalized_scores=normalized_scores(metrics, score_timestamp, item.fetched_at, credibility),
        metadata=dict(payload.get("metadata", {})),
    )


def _item_is_in_period(item: RawItem, since: str, until: str) -> bool:
    return is_within_period(parse_optional_datetime(item.payload.get("updated_at") or item.payload.get("published_at")), since, until)


def _matches_keywords(item: RawItem, keywords: list[str]) -> bool:
    if not keywords:
        return True
    result = classify_relevance(str(item.payload.get("title", "")), str(item.payload.get("summary", "")), keywords)
    return bool(result["matched_terms"])


def _ai_keyword_strength(entry: dict[str, Any]) -> float:
    text = f"{entry.get('title', '')} {entry.get('description', '')}".lower()
    strong_terms = (
        "llm", "rag", "mcp", "artificial intelligence", "machine learning",
        "deep learning", "generative ai", "generative-ai",
    )
    if any(term in text for term in strong_terms):
        return 1.0
    if "agent" in text:
        return 0.65
    return 0.0


def _feed_entries(root: ElementTree.Element) -> list[dict[str, Any]]:
    rss_items = root.findall("./channel/item")
    if rss_items:
        return [_element_to_dict(item) for item in rss_items]
    atom = {"atom": "http://www.w3.org/2005/Atom"}
    return [_element_to_dict(entry) for entry in root.findall("atom:entry", atom)]


def _element_to_dict(element: ElementTree.Element) -> dict[str, Any]:
    entry: dict[str, Any] = {}
    for child in element:
        name = child.tag.rsplit("}", 1)[-1]
        if name == "link":
            entry[name] = child.attrib.get("href") or child.text or ""
        elif name not in entry:
            entry[name] = (child.text or "").strip()
    return entry


def _keywords(config: SourceConfig) -> list[str]:
    return [str(value) for value in config.options.get("keywords", ["ai"])]


def _date_text(value: object) -> str | None:
    parsed = parse_optional_datetime(value)
    return parsed.isoformat() if parsed else None


def _summary_text(value: object) -> str:
    if isinstance(value, dict):
        restored, _ = restore_abstract(value)
        return restored
    return str(value or "")


def _stable_id(value: dict[str, Any]) -> str:
    encoded = json.dumps(value, ensure_ascii=True, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]
