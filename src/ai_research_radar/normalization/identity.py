from __future__ import annotations

import re
from urllib.parse import urlsplit

from ai_research_radar.normalization.dedup import canonical_url
from ai_research_radar.schemas.models import CanonicalSignal


def extract_identity(signal: CanonicalSignal) -> dict[str, object]:
    url = canonical_url(signal.url)
    doi = signal.metadata.get("doi") or (url.lower().removeprefix("https://doi.org/") if "doi.org/" in url.lower() else None)
    version = signal.metadata.get("version")
    if doi:
        return {"work_id": f"doi:{str(doi).lower()}", "event_key": f"doi:{str(doi).lower()}", "version": version, "explicit_links": []}
    if signal.source == "arxiv":
        match = re.search(r"arxiv\.org/(?:abs|pdf)/([^/?#]+)", url, re.IGNORECASE)
        identifier = match.group(1) if match else signal.signal_id
        version_suffix = None
        base, marker, suffix = identifier.rpartition("v")
        if marker and suffix.isdigit():
            identifier, version_suffix = base, f"v{suffix}"
        return {"work_id": f"arxiv:{identifier}", "event_key": f"arxiv:{identifier}:{version_suffix or version or 'unknown'}", "version": version or version_suffix, "explicit_links": []}
    if signal.source in {"pypi", "npm"}:
        package = urlsplit(url).path.strip("/").split("/")[-1] or signal.title.lower()
        return {"work_id": f"{signal.source}:{package}", "event_key": f"{signal.source}:{package}:{version or 'unknown'}", "version": version, "explicit_links": []}
    return {"work_id": f"{signal.source}:{signal.signal_id}", "event_key": f"{signal.source}:{signal.signal_id}", "version": version, "explicit_links": list(signal.metadata.get("explicit_links", []))}
