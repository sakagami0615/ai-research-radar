# 実行記録とステージ状態

旧設計書の該当節を分割した資料。現行と移行目標の区別は [文書全体の入口](../../../README.md) から確認する。

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
- `stage_results`

`since` / `until` は日付またはタイムゾーン付きISO 8601日時を保持する。通常の日次実行(`--since` / `--until` 省略時)では、前日以前で最新の `run.jsonl` の `until` から実行時刻までの実際の取得範囲を記録する(最大 `collection.max_lookback_days` 日。前回の記録がない初回も同じ日数。CLI設計)。`overlap_hours` を持つSource(Adapter設計)は、この `since` より前の重ね取得分も取得するが、記録する `since` は変えない。

`overlap_hours` を持つSourceの `input_counts` と `raw/<date>/<source>.jsonl` は、前日以前の `normalized` に既にある記事を除いた件数・内容(その回に新しく収集した分)である。

`stage_results` は `select-hot` / `save-proposals` の結果を、`stages_completed`(処理を実行した事実)とは別の軸で記録する(Issue #12)。`run_state.json` と `run.jsonl` の両方に同じ内容を持つ。

| キー | 内容 |
| --- | --- |
| `status` | `completed`(成果あり) / `deferred`(実行したが使える成果なし=保留) / `not_run`(未実行・無効) / `failed`(終了コード1で失敗) |
| `reason` | 保留・未実行・失敗の理由。`select-hot` は `selection_reason`、`failed` は `<error_type>: <message>` |
| `candidate_count` / `screened_count` / `unreviewed_count` / `selected_count` | `select-hot` の completed / deferred のときだけ持つ |
| `proposal_count` | `save-proposals` の成功時(completed / deferred / 選抜HOTなしの not_run)だけ持つ |

判定ルール:

| ステージ | 条件 | status | reason |
| --- | --- | --- | --- |
| select-hot | 成功・選抜1件以上 | `completed` | `selection_reason` |
| select-hot | 成功・選抜0件(候補0件の日を含む) | `deferred` | `selection_reason` |
| save-proposals | 成功・企画1件以上 | `completed` | 空 |
| save-proposals | 成功・選抜1件以上・企画0件 | `deferred` | 入力の `deferral_reason`(前後の空白を除く) |
| save-proposals | 成功・選抜0件 | `not_run` | 選抜HOTなし |
| いずれも | 未実行 | `not_run` | 未実行 |
| いずれも | 終了コード1で失敗(`errors` に記録したエラー) | `failed` | エラーの種別と内容 |

- 再実行・失敗時はそのステージの記録を上書きする。`select-hot` が成功したときは、`save-proposals` の記録が初期値(未実行)以外なら `not_run`(選抜の再実行により無効)に戻す。古い `article_proposals.jsonl` は削除しない。
- 新しい `run_state.json` は2ステージを `not_run`(未実行)で初期化する。`report` 以外のコマンドは、既存の `run_state.json` に有効な記録がなく、`stages_completed` にも入っていないステージだけを同じ値で補う(実行済みのステージは「記録なし」のまま)。既存の `run_state.json` について `report` は補わない(新規作成する場合は `report` でも2ステージを `not_run` で初期化する)。
- 記録がない・dictでない・`status` が4値以外のステージは「記録なし」として扱う。決定論経路(`ai-radar daily`)は記録せず、`run.jsonl` の `stage_results` は空dictのままである。
- `run_state.json` が壊れたJSON、またはJSONとして正しくてもオブジェクトでない場合、`load_run_state` は `RunStateError` を送出する。この場合は `errors` にも `stage_results` にも記録できないため、`stage_results` は更新されない。CLIは `RunStateError` を捕まえ、標準エラーに `error: <メッセージ>` を出して終了コード1で終わる(トレースバックにしない)。
- 判定用の定数・関数(`STAGE_RESULT_STATUSES` / `valid_stage_result`)と、`reason` に入れる定型の理由の定数(`NOT_RUN_REASON`(未実行)/ `INVALIDATED_REASON`(選抜の再実行により無効)/ `NO_SELECTION_REASON`(選抜HOTなし))は `schemas/models.py` にある。

`run_state.json` の `needs_review` は、品質レビューループが3回目の試行(初回を1回目とする)の後も解消しなかったことを表す(`true` のときだけキーを持つ)。`ai-radar mark-needs-review` が記録し、`collect` が消す。`report` はこれが `true` ならレポートの冒頭に警告を出す([日次レポートの表示契約](../reporting/report-format.md)、[CLIコマンド](../cli/commands.md))。`run.jsonl` には書かない。

Source失敗や後段失敗は `errors` に残す。運用時は `run.jsonl` を最初に確認する。`errors` の各記録は `source` / `type` / `message` を持ち、`corrupt_input` の記録は壊れたファイルの `data_dir` からの相対パス `path` も持つ(Issue #41。それより前の記録は `path` を持たない。[CLIコマンド](../cli/commands.md))。

## agent_progress

`run_state.json` の `agent_progress` は、`agent-daily-run` の途中経過(レビューの試行、自己修正の再実行、手順10への突入、完了)を記録する(Issue #30・#41)。`ai-radar progress` の記録系サブコマンドが書く([CLIコマンド](../cli/commands.md) の「途中経過の記録(`progress`)」)。`run.jsonl` には書かない。

現行: CLIは実装済みだが、まだSkillからは呼ばれないため、通常の実行では記録されない(Skillへの組み込みは #43、記録から再開する手順の判定(`progress show`)は #42)。

```json
{
  "agent_progress": {
    "review_attempts": [
      {"attempt": 1, "status": "changes_requested", "started_at": "<ISO 8601>", "finished_at": "<ISO 8601>"},
      {"attempt": 2, "status": "started", "started_at": "<ISO 8601>"}
    ],
    "retries": [
      {"stage": "select-hot", "kind": "fix", "recorded_at": "<ISO 8601>"},
      {"stage": "score", "kind": "corrupt_input", "recorded_at": "<ISO 8601>"}
    ],
    "finalized_at": "<ISO 8601>",
    "completed_at": "<ISO 8601>"
  }
}
```

| キー | 内容 | 書くコマンド |
| --- | --- | --- |
| `review_attempts` | レビューの試行。記録した順(試行番号順)に並ぶ。`status` は `started`(開始のみ。結果が出る前に止まった試行もこのまま残る)/ `approved` / `changes_requested` / `failed`。`finished_at` は結果を記録したときだけ持つ | `progress review --start` / `--result` |
| `retries` | 自己修正の再実行1回ごとの記録。`kind` は `fix`(エラー時の自己修正)/ `corrupt_input`(壊れた入力の流し直し) | `progress retry` |
| `finalized_at` | 手順10に入った時刻(最後に記録したもの) | `progress finalize` |
| `completed_at` | その日の実行を完了した時刻(最後に記録したもの) | `progress complete` |

- `progress` は `stage_results` を補わない(`agent_progress` だけを書き換える。`report` と同じく旧形式の「記録なし」を保つ)。
- 時刻はUTCのISO 8601。最初の記録のときに `review_attempts` / `retries` を空のリストで作る。`finalized_at` / `completed_at` は記録するまでキーを持たない。
- 回数はその日全体で数え、`collect` を流し直しても消さない。`started` のままの試行も1回と数える。
- 形が壊れている場合(オブジェクトでない、`review_attempts` / `retries` がリストでない、記録がオブジェクトでない、`attempt` が1〜3の整数でない、`attempt` が昇順でない・重複している、`status` / `kind` が上の値以外、`stage` が `progress retry --stage` に指定できるステージでない、`finalized_at` / `completed_at` が文字列でない)、`progress` は `RunStateError` として終了コード1で止まり、何も書き換えない(回数を信用できないため)。
- 判定用の定数・関数(上限 `FIX_LIMITS` / `CORRUPT_INPUT_LIMIT`、回数 `retry_count`、レビュー対象のハッシュ `review_artifact_hashes`)は `storage/agent_progress.py` にある。
