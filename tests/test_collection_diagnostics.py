from ai_research_radar.sources.collection import collect_with_diagnostics
from ai_research_radar.sources.base import SourceAdapter
from ai_research_radar.schemas.models import RawItem


class Adapter(SourceAdapter):
    source_name = "fixture"
    source_family = "technology"
    def __init__(self, items=None, error=False): self.items, self.error = items or [], error
    def collect(self, since, until):
        if self.error: raise RuntimeError("429")
        return self.items
    def normalize(self, item): raise NotImplementedError


def test_zero_success_differs_from_failure():
    items, ok = collect_with_diagnostics(Adapter(), "2026-09-29", "2026-09-29")
    assert items == [] and ok["status"] == "success"
    items, failed = collect_with_diagnostics(Adapter(error=True), "2026-09-29", "2026-09-29")
    assert items == [] and failed["status"] == "failed"


def test_custom_adapter_diagnostics_are_preserved():
    adapter = Adapter(); adapter.collection_diagnostics = {"status": "partial", "pages": 2}
    _, diagnostics = collect_with_diagnostics(adapter, "x", "y")
    assert diagnostics["pages"] == 2
