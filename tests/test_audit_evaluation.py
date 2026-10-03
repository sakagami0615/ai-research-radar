import json
from pathlib import Path

from scripts.evaluate_audit import main


def test_evaluation_never_mutates_source(tmp_path: Path):
    data = tmp_path / "data"; (data / "normalized" / "2026-09-29").mkdir(parents=True)
    (data / "normalized" / "2026-09-29" / "signals.jsonl").write_text(json.dumps({"signal_id": "s1", "source": "x"}) + "\n")
    before = (data / "normalized" / "2026-09-29" / "signals.jsonl").read_bytes()
    out = tmp_path / "eval"
    assert main(["prepare", "--source-data-dir", str(data), "--date", "2026-09-29", "--holdout-date", "2026-09-28", "--output-dir", str(out)]) == 0
    assert (data / "normalized" / "2026-09-29" / "signals.jsonl").read_bytes() == before


def test_sample_selection_is_stable(tmp_path: Path):
    data = tmp_path / "data"; (data / "normalized" / "2026-09-29").mkdir(parents=True)
    for i in range(12):
        with (data / "normalized" / "2026-09-29" / "signals.jsonl").open("a") as handle: handle.write(json.dumps({"signal_id": f"s{i}", "source": "x"}) + "\n")
    out = tmp_path / "eval"; main(["prepare", "--source-data-dir", str(data), "--date", "2026-09-29", "--holdout-date", "2026-09-28", "--output-dir", str(out)])
    assert len(json.loads((out / "manifest.json").read_text())["sample_ids"]) == 10


def test_zero_selection_precision_is_null(tmp_path: Path):
    data = tmp_path / "data"; (data / "normalized" / "2026-09-29").mkdir(parents=True)
    (data / "normalized" / "2026-09-29" / "signals.jsonl").write_text(json.dumps({"signal_id": "s", "source": "x"}) + "\n")
    out = tmp_path / "eval"; main(["prepare", "--source-data-dir", str(data), "--date", "2026-09-29", "--holdout-date", "2026-09-28", "--output-dir", str(out)])
    labels = tmp_path / "labels.jsonl"; labels.write_text(json.dumps({"signal_id": "s", "selected": False}) + "\n")
    selection = tmp_path / "selection.json"; selection.write_text(json.dumps({"assessments": [], "screened_ids": [], "selection_reason": "none"}))
    assert main(["evaluate", "--evaluation-dir", str(out), "--date", "2026-09-29", "--labels", str(labels), "--selection", str(selection)]) == 0
    results = list((out / "results").rglob("metrics.json")); assert json.loads(results[0].read_text())["precision"] is None
