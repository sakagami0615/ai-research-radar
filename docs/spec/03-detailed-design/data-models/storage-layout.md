# 保存形式とディレクトリ構成

旧設計書の該当節を分割した資料。現行と移行目標の区別は [文書全体の入口](../../../README.md) から確認する。

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
  collected/<date>/signals.jsonl
  normalized/<date>/signals.jsonl
  events/<date>/events.jsonl
  topics/<date>/topics.jsonl
  runs/<date>/run_state.json
  runs/<date>/hot_candidates.jsonl
  runs/<date>/selection_input.json
  runs/<date>/summary_input.json
  runs/<date>/draft_proposals.json
  runs/<date>/article_proposals.jsonl
  runs/<date>/run.jsonl
  runs/<date>/report_digest.json
  runs/<date>/digest_summaries.json
  runs/<date>/source_overview_input.json
  runs/<date>/source_overviews.json
  runs/<date>/evidence_fetch_log.tsv
  runs/<date>/review_feedback.md
  runs/<date>/review_target.json

reports/
  daily/<date>.md
```

`data/` / `reports/` は既定の出力先である(`--data-dir` / `--reports-dir` を省略したときは `config/runtime.yaml` の `output` の値)。Agent経路のSkillは出力先を `<data_dir>` / `<reports_dir>` と書き、本番では `data` / `reports` を、テストモードでは次の `test_output/` を、すべてのコマンドに明示して使う。`test_output/` はGit管理対象外。

```text
test_output/
  data/       # <data_dir>。上と同じ構成
  reports/    # <reports_dir>。daily/<date>.md
  logs/       # テストモードを手で起動したときのログ(agent-daily-run-<date>.log)
```

`runs/<date>/evidence_fetch_log.tsv` は、実行Agentが手順4〜9で取得したURLの記録(根拠の確認のほか、注目候補・新モデルリリースの概要補完での取得も含む。ヘッダー付きTSV。形式は `agent-daily-run` Skillの手順4)。CLIは読み書きしない。

その他のファイルの役割は次のとおり。

- `collected/<date>/signals.jsonl`: `collect` がCanonicalSignalに変換した、重複排除前のSignal。`normalize` の入力。
- `runs/<date>/run_state.json`: Agent経路のサブコマンドが共有する、その日の実行状態([実行記録](run-metadata.md))。決定論経路では作らない。Agentの途中経過(レビューの試行、自己修正の再実行の回数、手順10への突入、完了)は `agent_progress` に持つ([実行記録](run-metadata.md) の「agent_progress」。CLIは実装済みで、Skillからはまだ呼ばれない)。
- `runs/<date>/draft_proposals.json`: Agentが `save-proposals --input` に渡すために書く記事企画の入力([記事企画](article-proposals.md)の「save-proposals の入力(v2)」)。
- `runs/<date>/review_feedback.md`: レビュー担当のAgentが、Critical / Important の指摘があるときだけ書く指摘。ファイルの有無が承認・要修正の判定になる([日次レビュー](../agent-workflows/review-daily-report.md))。CLIは読み書きしない。
- `runs/<date>/review_target.json`: `progress review --start` が書く、レビューの試行を始めた時点のレビュー対象の成果物(6つ)のSHA-256([CLIコマンド](../cli/commands.md) の「`progress review`」)。再開時に、レビュー後に成果物が変わったかを `progress show` が判定するのに使う。Skillからはまだ呼ばれないため、現行の実行では作られない。
