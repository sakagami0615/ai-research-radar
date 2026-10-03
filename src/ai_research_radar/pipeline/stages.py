from __future__ import annotations

from pathlib import Path
from typing import Any

from ai_research_radar.config.settings import load_scoring_config
from ai_research_radar.normalization.dedup import deduplicate_quality_signals
from ai_research_radar.normalization.scores import normalize_quality_batch
from ai_research_radar.pipeline.events import build_quality_events
from ai_research_radar.schemas.decoders import decode_signal
from ai_research_radar.sources.collection import collect_with_diagnostics
from ai_research_radar.sources.base import SourceAdapter
from ai_research_radar.storage.jsonl import read_jsonl, write_jsonl


def collect_stage(adapters: list[SourceAdapter], since: str, until: str, data_dir: Path, *, mode: str = "split", configs: dict[str, Any] | None = None) -> dict[str, Any]:
    state = {"mode": mode, "since": since, "until": until, "sources": [], "diagnostics": [], "run_id": __import__('uuid').uuid4().hex}
    for adapter in adapters:
        items, diagnostics = collect_with_diagnostics(adapter, since, until)
        state["sources"].append(adapter.source_name); state["diagnostics"].append(diagnostics)
        if items: write_jsonl(data_dir / "raw" / until / f"{adapter.source_name}.jsonl", items)
    return state


def normalize_stage(data_dir: Path, date: str, *, sources_config: Path | None = None, scoring_config: Path | None = None, adapters: dict[str, SourceAdapter] | None = None) -> dict[str, Any]:
    records = []
    for path in sorted((data_dir / "raw" / date).glob("*.jsonl")):
        records.extend(read_jsonl(path))
    # Raw records are remapped by their own adapter when available; unlike a
    # failed source, an old run is never silently reused.
    signals = [decode_signal(record) for record in records if "signal_id" in record]
    metric_by_source = (
        load_scoring_config(scoring_config).get("metric_by_source", {}) if scoring_config else {}
    )
    signals = normalize_quality_batch(signals, metric_by_source=metric_by_source)
    signals = deduplicate_quality_signals(signals)
    events = build_quality_events(signals)
    write_jsonl(data_dir / "normalized" / date / "signals.jsonl", signals)
    write_jsonl(data_dir / "events" / date / "events.jsonl", events)
    return {"signals": len(signals), "events": len(events), "stage": "normalize"}


def score_stage(data_dir: Path, date: str, *, scoring_config: Path | None = None) -> dict[str, Any]:
    return {"stage": "score", "candidate_count": 0, "selection": "not_performed"}
