"""保存済みの raw から現在のコードでHOT候補を作り直し、修正の前後で比べる。

収集時に決まる判定(PyPIのAI関連度 `ai_keyword_strength`、公式ブログの `event_type`
など)は `data/raw/` / `data/collected/` に保存されるため、過去日に `score` を
実行し直しても判定の修正は反映されない。このスクリプトは、保存済みの
`raw/<date>/*.jsonl` の `payload.raw` から現在のコードの判定で RawItem を作り直し、
各Adapterの `normalize` で `collected/<date>/signals.jsonl` を一時ディレクトリに
作り、`normalize` → `score` を実行した結果を記録する。

同じスクリプトを、読み込むコード(PYTHONPATH)だけを修正前と修正後に切り替えて
それぞれ実行し、`diff` で比べる。使い方は
docs/support/01-operations/testing/04-hot-candidate-comparison.md。

    PYTHONPATH=src python scripts/compare_hot_candidates.py snapshot \\
        --source-data-dir <data_dir> --date 2026-10-09 --out before.json
    PYTHONPATH=src python scripts/compare_hot_candidates.py diff before.json after.json
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import subprocess
import sys
import tempfile
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import ai_research_radar
from ai_research_radar.cli.main import main as cli_main
from ai_research_radar.config.settings import SourceConfig, load_source_configs
from ai_research_radar.reporting.escape import inline
from ai_research_radar.schemas.models import RawItem
from ai_research_radar.sources import public
from ai_research_radar.sources.base import SourceAdapter
from ai_research_radar.storage.jsonl import read_jsonl, write_jsonl

SNAPSHOT_VERSION = 1

# raw から作り直さず、保存済みの RawItem をそのまま使う adapter。
# ollama は記事ページを取得して model_release を決めるため raw だけでは作り直せず、
# fixture は収集時の判定を持たない(fixture の内容がそのまま RawItem になる)。
_STORED_AS_IS = {"ollama", "fixture"}

# 前後で比べる、収集時に決まる判定。
_JUDGEMENTS = ("event_type", "ai_keyword_strength", "model_release")


def rebuild_raw_item(record: dict[str, Any], config: SourceConfig) -> RawItem:
    """保存済みの raw の1行を、現在のコードの判定で RawItem に作り直す。

    `fetched_at` は保存済みの値を引き継ぐ(現在時刻にすると48時間の判定とスコアが変わるため)。
    """
    stored = _stored_raw_item(record)
    if config.adapter in _STORED_AS_IS:
        return stored
    raw = stored.payload.get("raw")
    if not isinstance(raw, dict):
        raise SystemExit(f"{stored.source}:{stored.raw_id}: payload.raw がない")
    metadata = stored.payload.get("metadata") if isinstance(stored.payload.get("metadata"), dict) else {}
    if config.adapter in public._SEARCH_SPECS:
        item = public._SEARCH_SPECS[config.adapter].mapper(raw, stored.source)
    elif config.adapter == "pypi":
        item = public._map_pypi_feed(raw, stored.source)
    elif config.adapter == "official_blogs":
        # provider がない記事は、OpenAIだけを読んでいた単一フィード時代のもの。
        item = _rebuild_official(raw, str(metadata.get("provider", "OpenAI")), config, stored.source)
    elif config.adapter == "huggingface_orgs":
        release = metadata.get("model_release") if isinstance(metadata.get("model_release"), dict) else {}
        if not release.get("provider"):
            raise SystemExit(f"{stored.source}:{stored.raw_id}: model_release.provider がない")
        item = public._map_huggingface_org(raw, stored.source, str(release["provider"]))
    else:
        raise SystemExit(f"作り直し方が決まっていない adapter: {config.adapter!r}")
    return RawItem(item.source, stored.fetched_at, item.raw_id, item.raw_url, item.payload)


def _rebuild_official(raw: dict[str, Any], provider: str, config: SourceConfig, source: str) -> RawItem:
    # フィードの設定は raw に残らないため、provider から現在の sources.yaml の設定を引く。
    feeds = [feed for feed in public._official_feeds(config) if str(feed.get("provider", "OpenAI")) == provider]
    if len(feeds) != 1:
        raise SystemExit(f"{source}: sources.yaml に provider {provider!r} のフィードが1件ではない({len(feeds)}件)")
    feed = feeds[0]
    # raw に残る category は先頭の1件だけなので、model_categories の判定は近似になる。
    category = raw.get("category")
    return public._map_official_feed(
        raw,
        provider=provider,
        model_keywords=[str(value).lower() for value in feed.get("model_keywords", [])],
        categories=[category] if isinstance(category, str) and category else [],
        model_categories=public._model_categories(feed),
        source=source,
    )


def _stored_raw_item(record: dict[str, Any]) -> RawItem:
    return RawItem(
        source=str(record["source"]),
        fetched_at=datetime.fromisoformat(str(record["fetched_at"])),
        raw_id=str(record["raw_id"]),
        raw_url=str(record.get("raw_url", "")),
        payload=dict(record["payload"]),
    )


def snapshot_date(
    source_data_dir: Path,
    date: str,
    configs: dict[str, SourceConfig],
    adapters: dict[str, SourceAdapter],
    scoring_config: Path,
    work_dir: Path,
) -> dict[str, Any]:
    raw_dir = source_data_dir / "raw" / date
    raw_files = sorted(raw_dir.glob("*.jsonl"))
    if not raw_files:
        raise SystemExit(f"raw がない: {raw_dir}")
    signals = []
    input_counts: dict[str, int] = {}
    for path in raw_files:
        source = path.stem
        if source not in configs or source not in adapters:
            raise SystemExit(f"{path}: sources.yaml に有効な Source {source!r} がない")
        records = read_jsonl(path)
        input_counts[source] = len(records)
        signals.extend(adapters[source].normalize(rebuild_raw_item(record, configs[source])) for record in records)

    write_jsonl(work_dir / "collected" / date / "signals.jsonl", signals)
    for argv in (
        ["normalize", "--date", date, "--data-dir", str(work_dir)],
        ["score", "--date", date, "--data-dir", str(work_dir), "--scoring-config", str(scoring_config)],
    ):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = cli_main(argv)
        if code != 0:
            raise SystemExit(f"{' '.join(argv)} が終了コード {code} で失敗した: {output.getvalue().strip()}")

    collected = _signal_judgements(read_jsonl(work_dir / "collected" / date / "signals.jsonl"))
    candidates = [
        {
            "hot_id": str(record.get("hot_id", "")),
            "title": str(record.get("title", "")),
            "score": record.get("score"),
            "reasons": [str(reason) for reason in record.get("reasons", [])],
        }
        for record in read_jsonl(work_dir / "runs" / date / "hot_candidates.jsonl")
    ]
    return {
        "input_counts": input_counts,
        "signals": collected,
        "hot_candidates": sorted(candidates, key=lambda candidate: candidate["hot_id"]),
        "stored_collected_mismatches": _stored_mismatches(source_data_dir, date, collected),
    }


def _signal_judgements(records: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """signal_id ごとの、収集時に決まる判定(と表示用の title)。"""
    signals = {}
    for record in records:
        metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
        metrics = record.get("raw_metrics") if isinstance(record.get("raw_metrics"), dict) else {}
        signals[str(record["signal_id"])] = {
            "title": str(record.get("title", "")),
            "event_type": str(metadata.get("event_type", "")),
            "ai_keyword_strength": metrics.get("ai_keyword_strength"),
            "model_release": isinstance(metadata.get("model_release"), dict),
        }
    return signals


def _same_judgements(before: dict[str, Any] | None, after: dict[str, Any] | None) -> bool:
    if before is None or after is None:
        return before is after
    return all(before[name] == after[name] for name in _JUDGEMENTS)


def _stored_mismatches(source_data_dir: Path, date: str, rebuilt: dict[str, dict[str, Any]]) -> list[str] | None:
    """保存済みの collected と判定が違う signal_id(collected がない日は None)。

    修正前のコードでの実行で、作り直しが収集時の結果を再現できているかの確認に使う。
    収集した後にコードが変わった判定も、ここに出る。
    """
    path = source_data_dir / "collected" / date / "signals.jsonl"
    if not path.exists():
        return None
    stored = _signal_judgements(read_jsonl(path))
    ids = set(stored) | set(rebuilt)
    return sorted(signal_id for signal_id in ids if not _same_judgements(stored.get(signal_id), rebuilt.get(signal_id)))


def _code_version() -> dict[str, Any]:
    package_dir = Path(ai_research_radar.__file__).resolve().parent
    version: dict[str, Any] = {"package_dir": str(package_dir)}
    try:
        version["commit"] = _git(package_dir, "rev-parse", "HEAD")
        version["dirty"] = bool(_git(package_dir, "status", "--porcelain", "--", "."))
    except (OSError, subprocess.CalledProcessError):
        version["commit"] = None
    return version


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def _config_record(path: Path) -> dict[str, str]:
    return {"path": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def run_snapshot(args: argparse.Namespace) -> int:
    sources_config, scoring_config = Path(args.sources_config), Path(args.scoring_config)
    configs = {config.name: config for config in load_source_configs(sources_config)}
    adapters = {adapter.source_name: adapter for adapter in public.build_adapters(list(configs.values()))}
    dates: dict[str, Any] = {}
    for date in args.date:
        with tempfile.TemporaryDirectory(prefix="compare-hot-") as work_dir:
            dates[date] = snapshot_date(
                Path(args.source_data_dir), date, configs, adapters, scoring_config, Path(work_dir)
            )
    snapshot = {
        "version": SNAPSHOT_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "code": _code_version(),
        "source_data_dir": str(Path(args.source_data_dir).resolve()),
        "sources_config": _config_record(sources_config),
        "scoring_config": _config_record(scoring_config),
        "dates": dates,
    }
    Path(args.out).write_text(json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for date, result in dates.items():
        mismatches = result["stored_collected_mismatches"]
        note = "collectedなし" if mismatches is None else f"保存済みのcollectedと判定が違うSignal {len(mismatches)}件"
        print(f"{date}: HOT候補 {len(result['hot_candidates'])}件({note})")
    return 0


def render_diff(before: dict[str, Any], after: dict[str, Any]) -> str:
    """2つの snapshot の差分を、PRに貼れるMarkdownにする。"""
    lines = [
        "## HOT候補の前後比較",
        "",
        f"- 修正前: {_code_label(before)}",
        f"- 修正後: {_code_label(after)}",
        "",
    ]
    for date in sorted(set(before["dates"]) | set(after["dates"])):
        lines.extend(_render_date(date, before["dates"].get(date), after["dates"].get(date)))
    return "\n".join(lines).rstrip() + "\n"


def _code_label(snapshot: dict[str, Any]) -> str:
    code = snapshot.get("code", {})
    label = f"`{str(code.get('commit') or 'unknown')[:12]}`"
    if code.get("dirty"):
        label += "(未コミットの変更あり)"
    return label


def _render_date(date: str, before: dict[str, Any] | None, after: dict[str, Any] | None) -> list[str]:
    lines = [f"### {date}", ""]
    if before is None or after is None:
        return [*lines, f"- {'修正前' if before is None else '修正後'}の snapshot にこの日がない", ""]
    old = {candidate["hot_id"]: candidate for candidate in before["hot_candidates"]}
    new = {candidate["hot_id"]: candidate for candidate in after["hot_candidates"]}
    kept = sorted(set(old) & set(new))
    lines.append(f"- HOT候補: {len(old)}件 → {len(new)}件")
    lines.extend(
        _list_lines("増えた候補", [_candidate_text(new[hot_id]) for hot_id in sorted(set(new) - set(old))])
    )
    lines.extend(
        _list_lines("減った候補", [_candidate_text(old[hot_id]) for hot_id in sorted(set(old) - set(new))])
    )
    lines.extend(
        _list_lines(
            "スコア・理由が変わった候補",
            [
                _change_text(old[hot_id], new[hot_id])
                for hot_id in kept
                if (old[hot_id]["score"], old[hot_id]["reasons"]) != (new[hot_id]["score"], new[hot_id]["reasons"])
            ],
        )
    )
    lines.extend(_list_lines("判定が変わったSignal", _signal_changes(before["signals"], after["signals"])))
    lines.append("")
    return lines


def _list_lines(label: str, rows: list[str]) -> list[str]:
    if not rows:
        return [f"- {label}: なし"]
    return [f"- {label}: {len(rows)}件", *(f"  - {row}" for row in rows)]


def _candidate_text(candidate: dict[str, Any]) -> str:
    return f"{inline(candidate['title'])}(スコア {_score(candidate['score'])}、理由: {_reasons(candidate['reasons'])})"


def _change_text(before: dict[str, Any], after: dict[str, Any]) -> str:
    parts = []
    if before["score"] != after["score"]:
        parts.append(f"スコア {_score(before['score'])} → {_score(after['score'])}")
    # 理由には数値(例: "Momentum 99.86")が入るため、前後で増えた・減った項目だけを出す。
    added = [reason for reason in after["reasons"] if reason not in before["reasons"]]
    removed = [reason for reason in before["reasons"] if reason not in after["reasons"]]
    if added or removed:
        parts.append("理由 " + " ".join([*(f"+{inline(r)}" for r in added), *(f"-{inline(r)}" for r in removed)]))
    return f"{inline(after['title'])}({'、'.join(parts)})"


def _signal_changes(old: dict[str, dict[str, Any]], new: dict[str, dict[str, Any]]) -> list[str]:
    changes = []
    for signal_id in sorted(set(old) | set(new)):
        before, after = old.get(signal_id), new.get(signal_id)
        if _same_judgements(before, after):
            continue
        if before is None or after is None:
            side = "修正後" if before is None else "修正前"
            changes.append(f"{inline((after or before)['title'])}({inline(signal_id)}): {side}だけにある")
            continue
        fields = [f"{name} {before[name]} → {after[name]}" for name in _JUDGEMENTS if before[name] != after[name]]
        changes.append(f"{inline(after['title'])}({inline(signal_id)}): {'、'.join(fields)}")
    return changes


def _reasons(reasons: list[str]) -> str:
    return " / ".join(inline(reason) for reason in reasons) or "なし"


def _score(value: object) -> str:
    return f"{value:.1f}" if isinstance(value, (int, float)) else str(value)


def run_diff(args: argparse.Namespace) -> int:
    before, after = (json.loads(Path(path).read_text(encoding="utf-8")) for path in (args.before, args.after))
    for snapshot, path in ((before, args.before), (after, args.after)):
        if snapshot.get("version") != SNAPSHOT_VERSION:
            raise SystemExit(f"{path}: snapshot の version が {SNAPSHOT_VERSION} ではない")
    sys.stdout.write(render_diff(before, after))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    subparsers = parser.add_subparsers(dest="command", required=True)
    snapshot = subparsers.add_parser("snapshot", help="現在のコードでHOT候補を作り直して記録する")
    snapshot.add_argument("--source-data-dir", required=True, help="raw/<date>/ を読む data_dir(読むだけで書き換えない)")
    snapshot.add_argument("--date", action="append", required=True, help="対象日。複数回指定できる")
    snapshot.add_argument("--out", required=True)
    snapshot.add_argument("--sources-config", default="config/sources.yaml")
    snapshot.add_argument("--scoring-config", default="config/scoring.yaml")
    snapshot.set_defaults(func=run_snapshot)
    diff = subparsers.add_parser("diff", help="2つの snapshot の差分をMarkdownで出す")
    diff.add_argument("before")
    diff.add_argument("after")
    diff.set_defaults(func=run_diff)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
