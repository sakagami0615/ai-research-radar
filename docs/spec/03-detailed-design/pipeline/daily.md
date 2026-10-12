# 日次Pipelineの契約と順序

旧設計書の該当節を分割した資料。現行と移行目標の区別は [文書全体の入口](../../../README.md) から確認する。

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
- `display_timezone`(レポートのPeriod表示用)
- `use_overlap`(`--since` / `--until` 省略時に真。`overlap_hours` を持つSourceの重ね取得と収集済み除外を有効にする。Adapter設計)

主な出力:

- `DailyPipelineResult`
- JSONL成果物
- Markdownレポート


## 処理順序

1. Sourceごとに取得し、raw JSONLをSource別に保存して、CanonicalSignalへ変換する(`sources/collection.collect_sources`。`ai-radar collect` と共通。1つのSourceの失敗は `errors` に記録して他のSourceを続ける。`use_overlap` が真なら `overlap_hours` 分前から取得し、前日以前の `normalized` にある記事を除外する)。
2. Source単位のbatch normalizationを行う。
3. dedupで同一Signalを統合する。
4. Eventを生成する。
5. Topicを生成する。
6. EventからHOT候補を生成する。
7. 選抜HOTから記事企画候補を生成する。
8. JSONL成果物を保存する。
9. 日次ダイジェスト(注目候補・新モデルリリース)を集約し、Markdownレポートを生成する。
10. RunMetadataを保存する。


## エラー処理

Source単位の失敗は継続する。後段の保存やレポート生成に失敗した場合は、可能な限りRunMetadataを保存してから例外を再送出する。
