# 現行スコアとHOT候補化

旧設計書の該当節を分割した資料。現行と移行目標の区別は [文書全体の入口](../../../README.md) から確認する。

## Source単位スコア正規化

MVPでは、収集バッチ内のSource単位でPopularityを順位ベースに正規化する。

理由:

- GitHub stars、npm search score、RSS更新通知などは尺度が違う。
- 異なるSourceのraw metricを直接比較すると、累積人気の大きいSourceが常に有利になる。
- 初期段階では履歴がないため、Source別の簡易順位を使う。

単独Source itemではfallback scoreを使う。PyPI/npmの強い新着package discoveryは、48時間以内かつ強い信号に限定して補正する。補正はSourceあたり最大3件に制限し、通知量を抑える。


## HOT判定

HOT scoreは以下を使う。

- Momentum
- Popularity
- Cross-source Confidence
- Credibility

標準では、スコアが `minimum_score`(`config/scoring.yaml`、既定75)以上のEventを候補にする。それ未満のEventは候補にせず、`hot_candidates.jsonl` にも保存しない。

例外として、次の両方を満たすEventはスコアに関係なく候補にする(Official override。`scoring/hot.py::_official_event_override`)。候補の理由に `Official override` を付け、並びは他の候補と同じくスコア順である。

- `source_families` に `official` を含む。
- `event_type` が `major_model_release` / `major_api_release` / `major_standard_update` のいずれか。公式ブログ(`official_blogs`)の新モデルリリース(`metadata.model_release.channel == "official"`)は `major_model_release` になる(判定規則は [公開Source](../source-adapters/public-sources.md) の「Official Blogs」)。Hugging Face org・Ollamaで検知したモデルは、family が `technology`(`config/sources.yaml`)で `event_type` も `observed_signal` のため、対象にならない。

`hot_limit` は選抜数を制限する。候補自体は保持し、`selected` でレポート対象かどうかを表す。`hot_limit` は決定論経路(`ai-radar daily`)の選抜数である。Agent経路では `select-hot` が `data/runs/<date>/selection_input.json` の評価レコードで選抜し(データ契約「SelectionInput」参照)、上限は `select-hot --limit`(既定2件、最大5件)である。

選抜HOTのレポート表示では、Agent経路で保存された評価レコード(`assessment`)を評価ブロックとして出す(データ契約「Daily Markdown Report」の `## 選抜HOT` 参照)。評価レコードのない決定論経路・旧データはReasonsだけを表示する。
