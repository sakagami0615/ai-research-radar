# 取得期間と重ね取得

旧設計書の該当節を分割した資料。現行と移行目標の区別は [文書全体の入口](../../../README.md) から確認する。

## 期間反映

可能なSourceでは、API queryに `since` / `until` を反映する。値は日付またはタイムゾーン付きISO 8601日時を取り得る。日付粒度しか指定できないAPIは、範囲を包含する日付で検索した後、取得済み日時を使って厳密にフィルタする。

API側で完全に期間指定できないSourceでも、取得後に `published_at` または `updated_at` を使って期間フィルタを行う。

### 重ね取得と収集済み除外(`overlap_hours`)

公開日時(pubDate)が実際にfeedへ載った時刻より前に付く記事がある(OpenAIで確認。2026-09-29の実行は、期間内のpubDateを持つ「Introducing GPT-6.1 Sol」を取得できなかった)。期間を隙間なくつないでも、載った時点で既に過ぎた期間の記事として取りこぼすため、`sources.yaml` の各Sourceに任意の `overlap_hours` を設定できる。正の整数以外は0(重ねない)として扱う。

- `--since` / `--until` 省略時に限り、`overlap_hours` を持つSourceは `since - overlap_hours` 〜 `until` で取得する(期間を明示した実行では重ねない)。重ね分は `collection.max_lookback_days` の上限とは別に加算する。
- 取得結果から、対象日より前の日付(`period_date(since - overlap_hours)` の前日から対象日の前日まで)の `normalized/<日付>/signals.jsonl` で、`signal_id` または `metadata.merged_signal_ids` に `"<source>:<raw_id>"` があるものを除外する。`raw` ではなく `normalized` を基準にするのは、`collect` 後に止まった実行で `raw` だけ残った記事を取り直すためである。対象日の `normalized` は同日再実行で上書きされるため基準にしない。読めないファイルは無視する。
- 現在は `official_blogs` と `ollama` に `overlap_hours: 48` を設定している。GitHub / HF のように更新順で取得するSourceは、同じリポジトリの再浮上も新しいSignalとして扱うため設定しない。
- 既知の限界:
  - `normalize` まで終えて `report` 前に止まった実行の記事は除外される。新モデルリリースは直近3日の `normalized` から集約されるため次回レポートに出るが、HOT選抜の対象には戻らない。
  - `ollama` は除外前に記事ページを取得するため、収集済み記事のページ取得に失敗すると、その `partial_feed_error` が残る。
  - 期間判定は `updated_at` を優先するため、Atomの `updated` を持つfeedで古い記事が更新されると再収集される場合がある(現在の対象feedはRSSのpubDateのみ)。
