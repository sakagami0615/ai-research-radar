---
name: ai-radar
description: Use when 日次AI Radarを実行し、収集結果と日次レポートを確認するとき。
---

# AI Radar

## 目的

AI関連SourceからSignalを収集し、日次HOT検知と記事企画候補生成を実行する。

## 入力

- `--since`: 収集開始日またはタイムゾーン付きISO 8601日時。省略時は`--until`または実行時刻から決まる。
- `--until`: 収集終了日またはタイムゾーン付きISO 8601日時。`--since` / `--until` の両方を省略した場合は、実行時刻から直近24時間。
- `--data-dir`: JSONL保存先
- `--reports-dir`: Markdownレポート保存先

## 実行

```bash
ai-radar daily --since YYYY-MM-DD --until YYYY-MM-DD
```

## 出力

- `data/raw/<date>/<source>.jsonl`
- `data/normalized/<date>/signals.jsonl`
- `data/runs/<date>/run.jsonl`
- `reports/daily/<date>.md`

## レビュー観点

- 選抜HOTが多すぎないか
- HOT判定理由に根拠URLがあるか
- Source失敗がRun Summaryに出ているか
- Popularityは取得できた代表実測値の順位だけを示し、キーワード・固定信用点・新着度を人気として扱わない。HOT0件と選抜未実施を区別する。
