# 05. Pipeline・Scoring・Ideation設計

## v2指標とidentity

v2では`freshness_score`（公開日時から取得までの168時間線形値）、Sourceごとの代表的な実測指標の順位、過去観測との差分を別々に保持する。取得できない指標、NaN、Infinity、bool、文字列は人気順位に変換せず`missing`または`invalid`として扱う。キーワード一致、固定信用点、npm検索複合scoreは人気の実測値ではない。Eventが複数Signalを持つ場合、Signalごとの合成値(確認優先度)の最大を取り、採用したSignalと算出内訳を記録する(09章参照、旧仕様の「maxで合成しない」は撤回)。Task 10の切り替えまで旧HOT計算経路は維持する。

## 日次Pipeline

`run_daily` は、日次の収集からレポート生成までを実行する。

主な入力:

- `adapters`
- `since`
- `until`
- `output_dir`
- `report_dir`
- `hot_limit`
- `minimum_score`
- `hot_score_weights`

主な出力:

- `DailyPipelineResult`
- JSONL成果物
- Markdownレポート

## 処理順序

1. Sourceごとに `collect` を実行する。
2. raw JSONLをSource別に保存する。
3. `normalize` でCanonicalSignalへ変換する。
4. Source単位のbatch normalizationを行う。
5. dedupで同一Signalを統合する。
6. Eventを生成する。
7. Topicを生成する。
8. EventからHOT候補を生成する。
9. 選抜HOTから記事企画候補を生成する。
10. JSONL成果物を保存する。
11. Markdownレポートを生成する。
12. RunMetadataを保存する。

## Source単位スコア正規化

MVPでは、収集バッチ内のSource単位でPopularityを順位ベースに正規化する。

理由:

- GitHub stars、npm search score、RSS更新通知などは尺度が違う。
- 異なるSourceのraw metricを直接比較すると、累積人気の大きいSourceが常に有利になる。
- 初期段階では履歴がないため、Source別の簡易順位を使う。

単独Source itemではfallback scoreを使う。PyPI/npmの強い新着package discoveryは、48時間以内かつ強い信号に限定して補正する。補正はSourceあたり最大3件に制限し、通知量を抑える。

## Dedup

DedupはURLを主キーに近い形で扱う。ただし、queryを全削除しない。

- `utm_*`, `fbclid`, `gclid`, `ref` など追跡パラメータだけ除去する。
- `item?id=1` のような意味のあるqueryは保持する。
- 空URLは `source:signal_id` を含むkeyで扱い、空URL同士を統合しない。

統合時は以下を保持する。

- `sources`
- `source_families`
- `event_type`
- `merged_signal_ids`
- 最大normalized score

## Event / Topic生成

Event BuilderはSignalからEventを作る。EventにはHOT判定に必要な `source_families`, `scores`, `evidence`, `event_type` を残す。

Topic ClusterはEventからTopicを作る。MVPでは簡易な日次Topic化に留め、将来のTrend Analysisで履歴を使う。

## HOT判定

HOT scoreは以下を使う。

- Momentum
- Popularity
- Cross-source Confidence
- Credibility

標準では、スコアが `minimum_score` 以上のEventを候補にする。公式重大イベントは低スコアでも候補化できる。

`hot_limit` は選抜数を制限する。候補自体は保持し、`selected` でレポート対象かどうかを表す。

## Article Ideation

MVPでは外部LLMを使わず、決定論的な工程で記事企画を生成する。

工程:

1. Role別候補生成
2. 類似タイトルのDedup / Cluster
3. Critique scoreとCritique notes付与
4. Advocate / Critic / Editorの1 round Debate代替
5. `max_proposals` 件へ統合

ArticleProposalのスキーマは変えず、以下に判断結果を残す。

- `why_now`
- `technical_angle`
- `unique_angle`
- `risks`

Evidence URLがないHOT候補からは記事企画を生成しない。

## エラー処理

Source単位の失敗は継続する。後段の保存やレポート生成に失敗した場合は、可能な限りRunMetadataを保存してから例外を再送出する。
