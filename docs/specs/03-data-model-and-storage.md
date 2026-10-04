# 03. データモデル・保存設計

## v2移行契約

既存レコードは`schema_version=1`として旧スコアと表示互換を保つ。旧読込時に欠損した`quality`を推測で補完しない。新規v2入力は共通decoderと`QualityValidationError`で型・状態・必須文字列を検証し、未知のschema versionは明示的に拒否する。日時はタイムゾーン付きISO 8601、JSONの`null`は未取得として保持する。各v2 dataclassの`quality`は末尾の既定値付きフィールドで後方互換を保つ。

成果物のidentityは`work_id`（同一成果）と`event_key`（版・観測の統合単位）を分ける。DOIがある場合は同一DOIを同一Eventへ統合し、arXivはv番号をEventに残しつつwork_idを共有する。Packageは名前と版をEventキーに含める。自動統合できない同名項目はSourceとsignal_idで分離する。

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

`since` / `until` は日付またはタイムゾーン付きISO 8601日時を保持する。通常の日次実行では、実行時刻から直近24時間の実際の取得範囲を記録する。

Source失敗や後段失敗は `errors` に残す。運用時は `run.jsonl` を最初に確認する。

## Daily Markdown Report

`reports/daily/<date>.md` は `render_daily_report()`(`src/ai_research_radar/reporting/markdown.py`)が生成する。構成は次の通り。

- `# AI Daily Radar <date>`
- `## データ欠落`(収集に完全失敗したSourceがある場合のみ出力)
- `## 選抜HOT`: `selected=True` のHotCandidateと、それに紐づくArticleProposal
  - 各HOTの `#### Article Proposals` には、まず概要表(`# | 企画タイトル | Type | Role | Critique`)を出し、続けて企画ごとに `##### <番号>. <title_idea>` 見出しと2列の詳細表(`項目 | 内容`)を出す。詳細表の行は Type / Target Reader / Role / Critique Score / Critique Notes / Debate / Why Now / Technical Angle / Experiment Plan / Unique Angle / Competition / Traffic Opportunity / Technical Opportunity / Risks / Evidence。企画が0件の場合は `記事企画なし` と出す。
  - `why_now` が決定論的Ideation(`ideation/proposals.py`)の定型文に全体一致する場合だけ、レンダラーが Role / Critique Score / Critique Notes / Debate に分解して表示し、Why Now行は出さない(先頭のHOT score / reasonsは同じHOTセクションに表示済みのため再表示しない)。一致しない自由記述(Agent作成の企画など)は分解せず、Why Now行に全文を出し、概要表のRole / Critiqueは `-` にする。スキーマと保存データは変更しない。
  - 分解した場合、`risks` のうち表示済みのCritique Notes / Debateと完全一致する要素(`軽量Critique: <note>` / `Debate: <debate>`)は重複として除外する。すべて除外された場合は `Critique Notes / Debateと同じ内容` と出す。
  - 表崩れ防止のため、セルの値はバックスラッシュ・`|`・`<>`をエスケープしたうえで改行を `<br>` に置換し、リストは `<br>` 区切り(Experiment Planは番号付き、Critique Notes / Risksは `・` 付き)にする。空の値は `-` にする。見出しは `<>` をエスケープして改行を空白にする。Evidenceは全URLを `[URL](<URL>)` 形式のリンクで出し、リンク先の `<>` と `|` はパーセントエンコードする。
- `## Run Summary`: RunMetadataのサマリ(Run ID、期間、Sources、Input/Output Counts)
- `## Errors`: RunMetadataのerrors
- `## 収集Source一覧`: 当日の正規化・重複排除後のSignal(`data/normalized/<date>/signals.jsonl` と同じデータ、Event/Topic集約より前の粒度)をSourceごとに`<details>`で折りたたんだMarkdown表として一覧化したもの。`RunMetadata.sources` の順序で見出しを出し、収集0件のSourceも `(0件)` として明示する。`RunMetadata.sources` に含まれないSourceのSignalは末尾の `other` 見出しに集約する(ただし `other` という名前のSourceが実在する場合は `_other` に退避し、実データと混同しない)。表の概要列は元データの `summary` をそのまま使うが、表崩れ防止のためバックスラッシュエスケープ・改行除去・`|`エスケープ・120文字切り詰めを行う。
