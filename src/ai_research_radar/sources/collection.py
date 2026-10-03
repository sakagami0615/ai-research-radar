from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ai_research_radar.schemas.models import RawItem
from ai_research_radar.sources.base import SourceAdapter


def collect_with_diagnostics(adapter: SourceAdapter, since: str, until: str) -> tuple[list[RawItem], dict[str, Any]]:
    started = datetime.now(timezone.utc).isoformat()
    try:
        items = adapter.collect(since, until)
    except Exception as exc:  # collection boundary records partial source failure
        return [], {"source": adapter.source_name, "since": since, "until": until, "received": 0, "period_kept": 0, "status": "failed", "errors": [{"type": type(exc).__name__, "message": str(exc)}], "started_at": started}
    diagnostics = dict(getattr(adapter, "collection_diagnostics", {}))
    diagnostics.update({"source": adapter.source_name, "since": since, "until": until, "received": len(items), "period_kept": len(items), "status": diagnostics.get("status", "success"), "started_at": diagnostics.get("started_at", started), "finished_at": datetime.now(timezone.utc).isoformat()})
    return items, diagnostics
