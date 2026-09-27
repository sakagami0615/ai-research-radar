# 02. アーキテクチャ設計

## 全体像

```text
Source
  |
  v
Source Adapter
  |
  v
RawItem JSONL
  |
  v
CanonicalSignal
  |
  v
Source-local score normalization
  |
  v
Deduplication
  |
  v
Event Builder
  |
  v
Topic Cluster
  |
  v
HOT Scoring
  |
  v
Article Ideation
  |
  v
Markdown Report + Run Metadata
```

## 主要コンポーネント

### Source Adapter

Sourceごとの取得、raw保持、CanonicalSignalへの正規化を担当する。上位PipelineはSource固有のレスポンス形式を知らない。

実装場所:

- `src/ai_research_radar/sources/base.py`
- `src/ai_research_radar/sources/public.py`
- `src/ai_research_radar/sources/fixtures.py`

### Schema

Pipeline全体で共有するデータ構造を定義する。dataclassを使い、JSONL保存時は `to_json_dict` でdatetimeをISO文字列へ変換する。

実装場所:

- `src/ai_research_radar/schemas/models.py`

### Storage

JSONLの読み書きを担当する。MarkdownレポートはPipeline内でファイルとして保存する。

実装場所:

- `src/ai_research_radar/storage/jsonl.py`

### Normalization

重複排除とSource内スコア正規化を担当する。

実装場所:

- `src/ai_research_radar/normalization/dedup.py`
- `src/ai_research_radar/normalization/scores.py`

### Pipeline

Source Adapterから日次の収集、正規化、保存、HOT判定、記事企画、レポート生成までをつなぐ。

実装場所:

- `src/ai_research_radar/pipeline/daily.py`
- `src/ai_research_radar/pipeline/events.py`

### Scoring / Ideation / Reporting

HOT候補化、記事企画生成、Markdownレンダリングを担当する。

実装場所:

- `src/ai_research_radar/scoring/hot.py`
- `src/ai_research_radar/ideation/proposals.py`
- `src/ai_research_radar/reporting/markdown.py`

## 依存方向

依存方向は、CLIを入口として実装の責務ごとに分離する。

```text
cli
  -> config
  -> sources
  -> pipeline

pipeline
  -> sources
  -> normalization
  -> scoring
  -> ideation
  -> reporting
  -> storage
  -> schemas

sources
  -> config
  -> normalization.scores
  -> schemas
  -> storage

normalization / scoring / ideation / reporting / storage
  -> schemas
```

CLIは設定読込、Adapter構築、Pipeline呼び出しを組み合わせる。PipelineはSource Adapter Interfaceに依存し、Source固有レスポンスの詳細はAdapter内へ閉じ込める。

公開Adapterは初期スコア計算と日時処理のため `normalization.scores` に依存する。Fixture AdapterはJSONL fixtureを読むため `storage` に依存する。ScoringやIdeationはSource固有の実装を知らない。

## 例外処理

Source単位の失敗はRun Metadataの `errors` に記録し、他Sourceを継続する。

Pipeline後段の保存やレポート生成で失敗した場合も、可能な限り `data/runs/<date>/run.jsonl` に失敗記録を保存してから例外を再送出する。出力先自体が書き込めない場合はRun Metadataを残せないため、運用上の制約として扱う。
