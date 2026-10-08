"""収集Source一覧の見出しと同じ名前・件数で、当日のSignalをSourceごとに出す(agent-daily-run 手順8c)。

使い方: python3 skills/agent-daily-run/list_source_signals.py <date> [<Source名>] [--data-dir data]

- Source名を省略すると、見出し(`### <source> (N件)`)だけを出す。
- Source名を渡すと、そのSourceの各Signalを `- タイトル | 概要(先頭200字) | URL` の形で出す。

`ai_research_radar` パッケージをimportせずに動くよう標準ライブラリだけで書いている。見出しのまとめ方は
`ai_research_radar.reporting.source_overview.group_signals_by_source` と同じにする(テストで一致を確認する)。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def group_signals(sources: list[str], signals: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {source: [] for source in sources}
    other_key = "other"
    while other_key in groups:
        other_key = f"_{other_key}"
    other: list[dict] = []
    for signal in signals:
        source = signal.get("source", "")
        if source in groups:
            groups[source].append(signal)
        else:
            other.append(signal)
    if other:
        groups[other_key] = other
    return groups


def _read_signals(path: Path) -> list[dict]:
    if not path.exists():
        return []
    signals = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        record = json.loads(line)
        if not isinstance(record, dict):
            raise ValueError(f"line {line_number}: not a JSON object")
        signals.append(record)
    return signals


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("date")
    parser.add_argument("source", nargs="?", default="")
    parser.add_argument("--data-dir", default="data")
    args = parser.parse_args(argv)

    data_dir = Path(args.data_dir)
    state = json.loads((data_dir / "runs" / args.date / "run_state.json").read_text(encoding="utf-8"))
    sources = [source for source in state.get("sources", []) if isinstance(source, str)]
    signals_path = data_dir / "normalized" / args.date / "signals.jsonl"
    try:
        signals = _read_signals(signals_path)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        # A broken pipeline output: the Skill skips step 8c and lets report record corrupt_input.
        print(f"signals.jsonl を読めません: {signals_path}: {exc}")
        return 1

    groups = group_signals(sources, signals)
    if args.source and args.source not in groups:
        print(f"見出しにないSource名です: {args.source}")
        return 1
    for name, items in groups.items():
        if args.source and name != args.source:
            continue
        print(f"### {name} ({len(items)}件)")
        if args.source:
            for signal in items:
                summary = " ".join(str(signal.get("summary") or "").split())[:200]
                title = " ".join(str(signal.get("title") or "").split())
                print(f"- {title} | {summary} | {signal.get('url', '')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
