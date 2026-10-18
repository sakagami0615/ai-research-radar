# agent-daily-run の役割

共通Workflowの設計上の役割。実行手順はリポジトリの `skills/agent-daily-run/SKILL.md` を正本とする。

## agent-daily-run

`ai-radar` のサブコマンドを順に実行し、HOT最終選抜、選抜HOT・注目候補・新モデルリリースの日本語概要、収集Source一覧のSourceごとの「本日の傾向」、記事企画をAgent自身の判断で作る日次ワークフロー。cronから `claude -p` / `codex exec` で直接起動されることを想定する(ラッパースクリプトなし)。判断基準は `hot-detection` / `article-ideation` を参照する。

- 出力先: `SKILL.md` の冒頭で、起動プロンプトから出力先 `<data_dir>` / `<reports_dir>` を決める。本番(`entry-prompt.txt`)は `data` / `reports`、テストモード(`entry-prompt-test.txt`)は `test_output/data` / `test_output/reports`。すべての `ai-radar` コマンドと `list_source_signals.py` に `--data-dir <data_dir>`、`report` に `--reports-dir <reports_dir>` を本番でも明示し、Agentが直接読み書きするファイルと `--input` のパスも `<data_dir>` 側にする。テストモードは本番の `data/` / `reports/` に書き込まない(手順は [cron運用](../../../support/01-operations/scheduled-run.md) の「テストモード」)。
- 起動プロンプト: `entry-prompt.txt`(本番。cronで使う)と `entry-prompt-test.txt`(テストモード)。`entry-prompt-test.txt` は、`test_output/data` と対象日の `test_output/reports/daily/<date>.md` を消し、メインチェックアウト(`git rev-parse --path-format=absolute --git-common-dir` の親ディレクトリ)の `data/` から、対象日の前日・前々日(暦日。ない日は飛ばす)の `runs/<d>/`(`review_result.json` / `review_target.json` を除く)と `normalized/<d>/`、`run.jsonl` がある最新の過去日の `runs/<d>/run.jsonl` をコピーしてから、最初から実行する(作成済みの判定はしない)。
- `SKILL.md`: 通常の流れ(手順1〜10)。各手順で書くファイルと実行するコマンドを示す。対象日の判定、選抜(`selection_input.json` → `select-hot`)、記事企画(`draft_proposals.json` → `save-proposals`)、概要の補完(`add-summary`)、本日の傾向(`add-source-overview`)、レポート生成(`report`)、レビュー・修正ループ(レビューの試行は最大3回で初回を1回目とし、修正は試行の間に行うため最大2回)、未解消時の `mark-needs-review` まで。
- `recovery.md`: 失敗したときの対応。エラー種別ごとの直し方、再実行の上限と数え方、壊れた入力(`corrupt_input`)の流し直し、レポート生成前の `stage_results` の確認と補完実行、レビュー指摘を受けたときの修正の仕方。エラー種別の一覧そのものはCLI設計を参照し、Skillには書き写さない。
- 根拠のURLの取得規則(PyPIは `/project/` ページではなくJSON APIで確認し `primary` として記録する、HTTP 200でもbot対策ページなど本文を取得できなければ `unavailable` にするなど)と、取得ログ `<data_dir>/runs/<date>/evidence_fetch_log.tsv`(列: `url` / `http_status` / `fetched_at` / `content_verified` / `note`)の形式は、`SKILL.md` の手順4で定める。判断日時・確認日時は記録時に実測したUTC時刻とし、推定値で埋めない。
- 記事企画(手順6)の `quality.evidence` には、`verified` かつ `primary` で `checked_at` が空でない根拠を1件以上含める(`save-proposals` が検証する)。手順4の評価レコードの根拠は、企画の主張を支える場合にそのまま流用してよく、取得し直さなければ取得ログに追記しない。この根拠を確認できない企画は作らず、企画が1件もなくなる日は `deferral_reason` で保留する。規則の詳細は `SKILL.md` の手順6で定める。
- 一次情報を取得できない場合は、取得できた範囲で書いて「一次情報未確認」と明記する(手順4・8b)。例外として、`channel: official` の新モデルリリースの概要(手順8b)は、(1) 記事ページの本文 → (2) 本文を取得できない(HTTPエラー、または取得ログの `content_verified` が `false`)なら `--list-missing-summaries` の `feed_summary`(公式RSSの説明文) → (3) 説明文も空なら「概要未作成(情報取得失敗: <理由>)」の順で使い、報道記事などの二次情報は使わない。説明文から書いた概要は、説明文からわからない項目(規模・ライセンスなど)を書かず、末尾に「(公式RSSの説明文より)」を付け、「一次情報未確認」とは書かない(公式の配信元が出した文章のため)。取得ログには本文の取得に失敗した行を残し、説明文の利用では行を追加しない(#37)。
- 入力ファイルの形式はデータ契約(`SelectionInput`、「save-proposals の入力(v2)」)、各コマンドの引数とエラーはCLI設計に従う。
