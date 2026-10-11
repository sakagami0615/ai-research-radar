# HOT候補と選抜入力契約

旧設計書の該当節を分割した資料。現行と移行目標の区別は [文書全体の入口](../../README.md) から確認する。

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
- `assessment`: `selection_input.json` の評価レコード(下記「Assessment」)。`select-hot` が保存する。評価していない候補(未確認・決定論経路)と、この項目を持たない旧データは `null`。
- `summary`: 候補が何かを説明する日本語の概要(2〜3文、おおむね150字以内)。`agent-daily-run` のAgentが一次情報を読んで書き、`selection_input.json` の `summaries` から `select-hot` が保存する。未設定は空文字列で、この項目を持たない既存データも空文字列として読み込む。

`selected=True` の候補のみが日次レポートの中心になる。


## SelectionInput(selection_input.json)

[CLIの検証・エラー契約](../cli/commands.md)と [根拠の共通品質契約](quality-records.md)を併せて参照する。

`data/runs/<date>/selection_input.json` は、Agent経路でAgentがHOT候補を確認・評価した結果を書くJSONファイル。`ai-radar select-hot` が読み込み、検証してから `hot_candidates.jsonl` の `selected` / `assessment` / `summary` に反映する(引数とエラー種別はCLI設計「Agent経路のサブコマンド」参照)。型は `schemas/quality.py` の `SelectionInput`。

```json
{
  "assessments": [{"hot_id": "hot:event:...", "decision": "selected", "...": "..."}],
  "screened_ids": ["hot:event:..."],
  "selection_reason": "当日の選抜方針・確認範囲の説明",
  "summaries": {"hot:event:...": "概要の本文"}
}
```

- `assessments`(必須): 評価レコード(下記「Assessment」)のリスト。
- `screened_ids`(必須): 確認した候補の `hot_id` のリスト。
- `selection_reason`(必須): 選抜全体の理由・確認範囲。0件の日も書く。
- `summaries`(任意): `hot_id` から概要へのdict。省略時は `{}`。
- 上記以外のトップレベルキーはエラーにする(`summary` のような綴り間違いで概要が黙って無視されるのを防ぐため)。

検証は `scoring/assessments.py::apply_assessments` が次の順に行い、最初に見つかった誤りを `SelectionError`(`code` が `run_state.json` の `errors` の種別になる)として送出する。

| 順 | 条件 | 種別 |
| --- | --- | --- |
| 1 | 選抜上限 `limit` が整数でない、または0〜5の範囲外 | `invalid_input` |
| 2 | トップレベルの構造が不正(JSONオブジェクトでない、未知のキーがある、必須キーがない、`assessments` がリストでない、`screened_ids` が文字列のリストでない、`selection_reason` が文字列でない) | `invalid_input` |
| 3 | `selection_reason` が空白だけ | `invalid_assessment` |
| 4 | `screened_ids` が重複している、または当日の候補にない `hot_id` を含む | `invalid_assessment` |
| 5 | `assessments` の要素が `validate_assessment` を通らない(`EvidenceCheck` の検証を含む)、または `hot_id` が当日の候補にない・重複している | `invalid_assessment` |
| 6 | `screened_ids` の集合と評価レコードの `hot_id` の集合が一致しない(評価のない確認済みIDと、確認済みに含まれない評価IDの両方をメッセージに出す) | `invalid_assessment` |
| 7 | `decision: selected` の評価に、`status: verified` かつ `kind: primary` の根拠がない | `invalid_assessment` |
| 8 | 選抜件数が `limit` を超える | `selection_limit_exceeded` |

- 種別の境界: トップレベルの構造(キーの有無と各キーの値の型)の誤りは `invalid_input`、各キーの中身(空の理由、IDの重複・不整合、評価レコードの内容、根拠の条件)の誤りは `invalid_assessment` にする。`validate_assessment` の `QualityValidationError` は `invalid_assessment` に包み直す。
- `summaries` の検証(当日の候補にない `hot_id`、空または文字列でない値は `invalid_summary`)は `apply_assessments` の後に `select-hot` が行う。
- 検証を通った場合、各候補の `selected` は評価の `decision` が `selected` かどうかで決まり、`assessment` に評価レコードがそのまま入る。評価のない候補は `selected=False`、`assessment=null` になる。`screened_ids` に含まれない候補は未確認として件数を数える(CLI設計の `unreviewed_candidates` 警告)。

### Assessment

候補1件の評価レコード。型は `schemas/quality.py` の `Assessment`、検証は `validate_assessment`。

- `hot_id`: 対象候補の `hot_id`(空でない文字列)
- `decision`: `selected` / `deferred` / `rejected`
- `assessed_at`: 判断日時(空でない文字列。記録時に実測したUTC時刻を書き、推定値や切りのよい値で埋めない)
- `assessor`: 評価担当(空でない文字列)
- `relevance`: AI関連性の記録(`RelevanceRecord`)
  - `status`: `related` / `uncertain` / `unrelated`
  - `matched_terms`: 一致語(文字列のリスト。空リスト可)
  - `reason`: 判定理由(空でない文字列)
  - `method`: `keyword` / `agent` / `legacy`
- `novelty` / `importance` / `reader_impact` / `reason`: 新規性・重要性・読者への影響・採否理由(いずれも空でない文字列)
- `evidence`: 根拠(`EvidenceCheck` のリスト。空リスト可。ただし `selected` には `verified` かつ `primary` の根拠が1件以上必要)
- `unknowns`: 未確認事項(文字列のリスト。空リスト可)

根拠と企画品質の型は [共通品質契約](quality-records.md) を参照する。
