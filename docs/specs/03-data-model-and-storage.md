# 03. データモデル・保存設計

## 保存方針

MVPでは、人間が確認しやすく、再処理もしやすい形式を優先する。

- 構造化データ: JSONL
- 人間向けレポート: Markdown
- SQLite: 将来検討

JSONLは1行1レコードとし、日次実行ごとの成果物を日付ディレクトリに保存する。

## ディレクトリ構成

```text
data/
  raw/<date>/<source>.jsonl
  normalized/<date>/signals.jsonl
  events/<date>/events.jsonl
  topics/<date>/topics.jsonl
  runs/<date>/hot_candidates.jsonl
  runs/<date>/article_proposals.jsonl
  runs/<date>/run.jsonl

reports/
  daily/<date>.md
```

## RawItem

Sourceから取得した未加工データを保持する。

主な項目:

- `source`
- `fetched_at`
- `raw_id`
- `raw_url`
- `payload`

`payload` には、正規化用の派生フィールドに加えて、元レスポンスを `raw` として保持する。これにより、正規化やスコアリングを後から改善して再処理できる。

## CanonicalSignal

Source横断で扱うSignalの共通形式。

主な項目:

- `signal_id`
- `source`
- `source_family`
- `content_type`
- `title`
- `url`
- `published_at`
- `fetched_at`
- `summary`
- `categories`
- `raw_metrics`
- `normalized_scores`
- `metadata`

`normalized_scores` には0から100の正規化済みスコアを入れる。Source内順位補正はPipelineで収集バッチ単位に実施する。

## Event

重複排除後のSignalを、同じ出来事としてまとめた単位。

主な項目:

- `event_id`
- `title`
- `description`
- `event_type`
- `first_seen_at`
- `last_seen_at`
- `signals`
- `sources`
- `source_families`
- `scores`
- `evidence`

HOT判定はEventを入力にする。公式重大発表などは `event_type` と `source_families` を使って低スコアでも候補化できる。

## Topic

Eventを将来のトレンド分析へつなげるための集約単位。

主な項目:

- `topic_id`
- `name`
- `aliases`
- `categories`
- `related_topics`
- `events`
- `trend_history`
- `current_scores`
- `status`

MVPでは日次Topicの最小生成に留める。週次・月次分析ではTopic履歴を使って成長、継続、沈静化を判定する。

## HotCandidate

Eventから生成されるHOT候補。

主な項目:

- `hot_id`
- `title`
- `topic`
- `score`
- `reasons`
- `evidence_urls`
- `source_families`
- `signals`
- `selected`

`selected=True` の候補のみが日次レポートの中心になる。

## ArticleProposal

HOT候補から生成される記事企画案。

主な項目:

- `proposal_id`
- `source_hot_id`
- `title_idea`
- `article_type`
- `target_reader`
- `why_now`
- `technical_angle`
- `experiment_plan`
- `competition`
- `traffic_opportunity`
- `technical_opportunity`
- `unique_angle`
- `evidence_links`
- `risks`

MVPでは外部LLMを使わず、決定論的なRole生成、Critique、Debate代替で作成する。

## RunMetadata

1回の実行結果を記録する。

主な項目:

- `run_id`
- `started_at`
- `finished_at`
- `mode`
- `since`
- `until`
- `sources`
- `input_counts`
- `output_counts`
- `errors`
- `report_paths`

Source失敗や後段失敗は `errors` に残す。運用時は `run.jsonl` を最初に確認する。
