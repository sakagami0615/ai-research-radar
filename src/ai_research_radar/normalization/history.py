from __future__ import annotations

from datetime import datetime
from pathlib import Path

from ai_research_radar.schemas.decoders import decode_signal
from ai_research_radar.schemas.models import CanonicalSignal
from ai_research_radar.storage.jsonl import read_jsonl


def load_metric_history(data_dir: Path, *, before: datetime) -> list[CanonicalSignal]:
    root = data_dir / "normalized"
    if not root.exists():
        return []
    result: list[CanonicalSignal] = []
    for path in sorted(root.glob("*/signals.jsonl")):
        for record in read_jsonl(path):
            signal = decode_signal(record)
            if signal.fetched_at < before:
                result.append(signal)
    return result
