from pathlib import Path

from ai_research_radar.normalization.relevance import classify_relevance
from ai_research_radar.scoring.assessments import apply_assessments, compute_discovery_candidates
from ai_research_radar.schemas.decoders import decode_signal
from ai_research_radar.schemas.models import to_json_dict
from ai_research_radar.pipeline.events import build_quality_events


def test_audit_workflow_contract():
    records = [decode_signal(__import__('json').loads(line)) for line in Path('tests/fixtures/audit/signals.jsonl').read_text().splitlines()]
    assert classify_relevance(records[0].title, records[0].summary, ["rag", "agent"])["status"] == "uncertain"
    candidates = compute_discovery_candidates(build_quality_events(records))
    assert len(candidates) == 2
    updated, summary = apply_assessments(candidates, {"assessments": [], "screened_ids": [], "selection_reason": "根拠確認前"})
    assert not any(item.selected for item in updated)
    assert summary["selected_count"] == 0
    assert all(to_json_dict(item)["schema_version"] == 1 for item in records)
