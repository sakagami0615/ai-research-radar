# agent-daily-run の役割

共通Workflowの設計上の役割。実行手順はリポジトリの `skills/agent-daily-run/SKILL.md` を正本とする。

## agent-daily-run

`ai-radar` のサブコマンドを順に実行し、HOT最終選抜、選抜HOT・注目候補・新モデルリリースの日本語概要、収集Source一覧のSourceごとの「本日の傾向」、記事企画をAgent自身の判断で作る日次ワークフロー。cronから `claude -p` / `codex exec` で直接起動されることを想定する(ラッパースクリプトなし)。判断基準は `hot-detection` / `article-ideation` を参照する。

- `SKILL.md`: 通常の流れ(手順1〜10)。各手順で書くファイルと実行するコマンドを示す。対象日の判定、選抜(`selection_input.json` → `select-hot`)、記事企画(`draft_proposals.json` → `save-proposals`)、概要の補完(`add-summary`)、本日の傾向(`add-source-overview`)、レポート生成(`report`)、レビュー・修正ループ(最大3回)、未解消時の `mark-needs-review` まで。
- `recovery.md`: 失敗したときの対応。エラー種別ごとの直し方、再実行の上限と数え方、壊れた入力(`corrupt_input`)の流し直し、レポート生成前の `stage_results` の確認と補完実行、レビュー指摘を受けたときの修正の仕方。エラー種別の一覧そのものはCLI設計を参照し、Skillには書き写さない。
- 根拠のURLの取得規則(PyPIは `/project/` ページではなくJSON APIで確認し `primary` として記録する、HTTP 200でもbot対策ページなど本文を取得できなければ `unavailable` にするなど)と、取得ログ `data/runs/<date>/evidence_fetch_log.tsv`(列: `url` / `http_status` / `fetched_at` / `content_verified` / `note`)の形式は、`SKILL.md` の手順4で定める。判断日時・確認日時は記録時に実測したUTC時刻とし、推定値で埋めない。
- 入力ファイルの形式はデータ契約(`SelectionInput`、「save-proposals の入力(v2)」)、各コマンドの引数とエラーはCLI設計に従う。
