from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _records(source: Path, date: str) -> list[dict]:
    result = []
    for path in sorted((source / "normalized" / date).glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip(): result.append(json.loads(line))
    return result


def prepare(args) -> int:
    source = Path(args.source_data_dir).resolve(); output = Path(args.output_dir).resolve()
    if output == source or source in output.parents: raise ValueError("output must be outside source")
    if output.exists() and any(output.iterdir()): raise ValueError("output must be empty")
    output.mkdir(parents=True, exist_ok=True)
    records = _records(source, args.date)
    manifest = {"date": args.date, "holdout_date": args.holdout_date, "source_data_dir": str(source), "source_hashes": {}, "sample_ids": sorted({str(r.get("signal_id")) for r in records})[:10], "created_at": datetime.now(timezone.utc).isoformat()}
    for path in sorted((source / "normalized" / args.date).glob("*.jsonl")): manifest["source_hashes"][str(path)] = _hash(path)
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "inputs.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records) + ("\n" if records else ""), encoding="utf-8")
    return 0


def evaluate(args) -> int:
    root = Path(args.evaluation_dir); manifest = json.loads((root / "manifest.json").read_text())
    labels = []
    for label_path in args.labels:
        labels.extend(json.loads(line) for line in Path(label_path).read_text().splitlines() if line.strip())
    if len({item.get("signal_id") for item in labels}) != len(labels): raise ValueError("duplicate labels")
    selection = json.loads(Path(args.selection).read_text())
    selected = {item.get("hot_id") for item in selection.get("assessments", []) if item.get("decision") == "selected"}
    evaluation_id = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    result = root / "results" / args.date / evaluation_id; result.mkdir(parents=True)
    metrics = {"precision": None if not selected else 0.0, "selected_count": len(selected), "label_count": len(labels), "manifest_hash": _hash(root / "manifest.json")}
    (result / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    (result / "selection.json").write_text(json.dumps(selection, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(); sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare"); p.add_argument("--source-data-dir", required=True); p.add_argument("--date", required=True); p.add_argument("--holdout-date", required=True); p.add_argument("--output-dir", required=True); p.set_defaults(func=prepare)
    p = sub.add_parser("evaluate"); p.add_argument("--evaluation-dir", required=True); p.add_argument("--date", required=True); p.add_argument("--labels", nargs="+", required=True); p.add_argument("--selection", required=True); p.set_defaults(func=evaluate)
    return args.func(args) if (args := parser.parse_args(argv)) else 1


if __name__ == "__main__": raise SystemExit(main())
