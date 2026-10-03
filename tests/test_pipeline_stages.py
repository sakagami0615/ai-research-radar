from pathlib import Path

import yaml

from ai_research_radar.pipeline.stages import normalize_stage
from ai_research_radar.storage.jsonl import read_jsonl, write_jsonl


def test_normalize_stage_uses_metric_by_source_from_scoring_config(tmp_path: Path):
    record = {
        "signal_id": "pypi:pkg",
        "source": "pypi",
        "source_family": "technology",
        "content_type": "package",
        "title": "pkg",
        "url": "https://pypi.org/project/pkg",
        "fetched_at": "2026-09-29T00:00:00+00:00",
        "summary": "",
        "categories": [],
        "raw_metrics": {"downloads": 42},
        "metadata": {},
    }
    write_jsonl(tmp_path / "raw" / "2026-09-29" / "pypi.jsonl", [record])
    scoring_config = tmp_path / "scoring.yaml"
    scoring_config.write_text(yaml.safe_dump({"metric_by_source": {"pypi": "downloads"}}))

    normalize_stage(tmp_path, "2026-09-29", scoring_config=scoring_config)

    signals = list(read_jsonl(tmp_path / "normalized" / "2026-09-29" / "signals.jsonl"))
    metric = signals[0]["quality"]["metrics"][0]
    assert metric["name"] == "downloads"
    assert metric["status"] == "observed"
    assert metric["value"] == 42
