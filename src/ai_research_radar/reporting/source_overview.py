"""Per-source "本日の傾向" (today's overview) shown in the report's source appendix.

The agent writes one short overview per source heading and saves it with
`ai-radar add-source-overview` into `data/runs/<date>/source_overviews.json`
(`{"<source>": "本文"}`). The headings are shared with the report so that the
names and item counts the CLI validates are the ones the reader sees.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ai_research_radar.storage.files import atomic_write_text

SOURCE_OVERVIEWS_FILENAME = "source_overviews.json"


def other_source_key(sources: list[str]) -> str:
    """Heading for signals whose source is not in `sources`; prefixed with "_" while it clashes with a real one."""
    known = set(sources)
    key = "other"
    while key in known:
        key = f"_{key}"
    return key


def group_signals_by_source(sources: list[str], signals: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Signals per report heading, in heading order.

    Every source in `sources` gets a heading (even with 0 items). Signals of
    other sources go under the `other_source_key` heading, which is last and
    only present when it has items.
    """
    groups: dict[str, list[dict[str, Any]]] = {source: [] for source in sources}
    other_key = other_source_key(sources)
    other: list[dict[str, Any]] = []
    for signal in signals:
        source = signal.get("source", "")
        if source in groups:
            groups[source].append(signal)
        else:
            other.append(signal)
    if other:
        groups[other_key] = other
    return groups


def load_source_overviews(data_dir: Path, date: str) -> dict[str, str]:
    """Saved overviews; empty or non-string values are ignored. Raises ValueError for a broken file."""
    path = data_dir / "runs" / date / SOURCE_OVERVIEWS_FILENAME
    if not path.exists():
        return {}
    record = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(record, dict):
        raise ValueError(f"{path} is not a JSON object")
    return {str(key): value for key, value in record.items() if isinstance(value, str) and value.strip()}


def save_source_overviews(data_dir: Path, date: str, overviews: dict[str, str]) -> None:
    """Merge overviews into source_overviews.json (the same source is overwritten)."""
    merged = {**load_source_overviews(data_dir, date), **overviews}
    atomic_write_text(data_dir / "runs" / date / SOURCE_OVERVIEWS_FILENAME, json.dumps(merged, ensure_ascii=False, indent=2) + "\n")
