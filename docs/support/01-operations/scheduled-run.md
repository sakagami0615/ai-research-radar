# cronによる日次実行

旧設計書の該当節を分割した資料。現行と移行目標の区別は [文書全体の入口](../../README.md) から確認する。

## cron想定

推奨はcronから `claude -p` / `codex exec` を直接起動するAI Agent(Claude Code / Codex)経由の実行である(ラッパースクリプトは使わない)。渡すプロンプトは `skills/agent-daily-run/SKILL.md` を読ませる `skills/agent-daily-run/entry-prompt.txt` であり、`collect` / `normalize` / `score` / `select-hot` / `save-proposals` / `add-summary` / `add-source-overview` / `report` / `mark-needs-review` の実行、概要の作成・補完、Sourceごとの本日の傾向の作成、対象日の判定、レビュー・修正ループまでAgent自身が判断して行う。

`ai-radar`/`claude`/`codex` はいずれもPATH依存のコマンドであり、cronの実行環境には通常PATHが通っていないため、crontabファイル先頭に `PATH=` 行が必要になる。同日の多重実行(ログが混ざる)を防ぐため `flock -n` で排他制御し、レポート未生成時にcronの失敗通知が機能するよう末尾で `test -f` による確認を行う。

```cron
PATH=/path/to/.pyenv/shims:/path/to/.local/bin:/path/to/.nvm/versions/node/<version>/bin:/usr/local/bin:/usr/bin:/bin

15 8 * * * cd /path/to/ai-research-radar && mkdir -p logs && D="$(date +\%F)" && flock -n logs/.daily.lock -c 'claude -p "$(cat skills/agent-daily-run/entry-prompt.txt)" --permission-mode bypassPermissions >> logs/agent-daily-run-'"$D"'.log 2>&1 && test -f reports/daily/'"$D"'.md'
```

- `codex` で実行する場合は `claude -p "..." --permission-mode bypassPermissions` を `codex exec "..." --sandbox workspace-write` に置き換えた別のcron行を使う(両方を同時に有効化しない)。
- 実行ログは `logs/agent-daily-run-<date>.log` に出力される。
- レポート生成後、Agent自身が別プロセスの `claude -p` / `codex exec` を起動して `skills/review-daily-report/SKILL.md` によるレビューを行わせ、指摘があれば自分自身で修正して再レビューする。レビューの試行は最大3回(初回を1回目とする)。修正は試行の間に行うため最大2回(`skills/agent-daily-run/SKILL.md` 手順9〜10)。3回目の試行の後も指摘が残れば `ai-radar mark-needs-review` で `run_state.json` に `needs_review: true` を記録し、`report` を再実行してレポート冒頭に警告を出す。

上記のレビュー起動(Agent自身が別プロセスの `claude -p` / `codex exec` を起動する手順)はcronからの起動を前提とする。対話セッション(IDE拡張のAuto Modeなど)内で `agent-daily-run` を手動実行する場合、Bash経由で `claude -p ... --permission-mode bypassPermissions` を新規起動しようとすると、そのセッション固有の権限分類器に「Create Unsafe Agents」として拒否されることがある。この場合は同一セッション内のsubagent(Agent機能)へレビューを委譲する代替手段で対応してよい。cronによる本番実行はこの制約を受けない独立プロセスであるため、設計自体は変更不要である。

## 手での起動

手で起動する場合も、cronと同じ `flock -n` で排他制御する(本番の実行と同時に動かさないため)。ロックファイルは、メインチェックアウトの絶対パスの `logs/.daily.lock` を指定する。メインチェックアウトの絶対パスは `git rev-parse --path-format=absolute --git-common-dir` の親ディレクトリであり、メインチェックアウトから起動してもワークツリーから起動しても同じパスになる(相対パスの `logs/.daily.lock` では、ワークツリーから起動したときに本番とロックが共有されない)。ロックを取れない場合(本番の実行中など)は、`flock` が終了コード1で終わり、Agentは起動しない。

本番の手での起動(メインチェックアウトのルートで実行する。cron行と同じく本番の `data/` / `reports/` に書く):

```bash
M="$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")" && D="$(date +%F)" && mkdir -p "$M/logs" && flock -n "$M/logs/.daily.lock" claude -p "$(cat skills/agent-daily-run/entry-prompt.txt)" --permission-mode bypassPermissions >> "$M/logs/agent-daily-run-$D.log" 2>&1 && test -f "reports/daily/$D.md"
```

作成済みの日の判定は #44 で入るまでないため、当日のレポートがある日に本番で実行すると上書きされる。動作確認はテストモードを使う。

## テストモード

動作確認(PRのマージ後の確認など)は、本番の `data/` / `reports/` に影響しないテストモードで行う。起動プロンプトに `skills/agent-daily-run/entry-prompt-test.txt` を使う。

- 出力先: すべての `ai-radar` コマンドと `list_source_signals.py` に `--data-dir test_output/data`、`report` に `--reports-dir test_output/reports` を付けて実行し、Agentが直接書くファイル・レビュー担当の `review_feedback.md` も `test_output/data` 側に書く(Skillの「出力先」)。`test_output/` はGit管理対象外。
- 準備: 起動プロンプトに書いたコマンドで、`test_output/data` と対象日の `test_output/reports/daily/<date>.md` を消し、メインチェックアウトの `data/` から次を `test_output/data` にコピーしてから、最初から実行する(作成済みの判定はしない)。メインチェックアウトの `data/` は読むだけで変更しない。
  - 対象日の前日・前々日(暦日。ない日は飛ばす)の `runs/<d>/` と `normalized/<d>/`。直近3日分の集約に使う。収集の重複除外(`overlap_hours` のあるSourceは、対象日の4日前〜前日の `normalized/` を読む)は前々日より前を読まないため、本番より除外が弱い。v2時代の `review_result.json` / `review_target.json` はコピーしない。
  - `run.jsonl` がある最新の過去日の `runs/<d>/run.jsonl`(2日より前の日のこともある)。収集期間を本番と同じく前回の続きにするため(コピーしないと初回扱いになり、上限の7日分を収集する)。
- ログ: `test_output/logs/` にリダイレクトする。ロックは本番と同じメインチェックアウトの `logs/.daily.lock` を使う。

テストモードの起動(対象のチェックアウトのルートで実行する):

```bash
M="$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")" && D="$(date +%F)" && mkdir -p test_output/logs "$M/logs" && flock -n "$M/logs/.daily.lock" claude -p "$(cat skills/agent-daily-run/entry-prompt-test.txt)" --permission-mode bypassPermissions >> "test_output/logs/agent-daily-run-$D.log" 2>&1 && test -f "test_output/reports/daily/$D.md"
```

- ワークツリーで起動する場合は、`ai-radar` がワークツリーのコードを使うよう、[Agent実機確認](testing/03-agent-smoke-tests.md) のラッパーを置いたbinを `PATH` の先頭に加えて起動する(`PATH='<scratchpad>/bin':"$PATH" PYTHONPATH="$PWD/src" flock -n ...`)。レビュー担当のプロセスは環境変数を引き継ぐため、同じラッパーを使う。
- Codexで起動する場合は、`claude -p "..." --permission-mode bypassPermissions` を `codex exec "..." --sandbox workspace-write` に置き換える。
- テストモードは、本番の `data/` と `reports/` を書き換えないことを前提とする。確認するときは、実行前後でメインチェックアウトの `data/` と `reports/` の全ファイルのハッシュを比べる。

## 決定論経路のcron

決定論的な `ai-radar daily` を直接cronに書く方法も、手動運用・CI向けの代替手段として利用できる。

```cron
15 8 * * * cd /path/to/ai-research-radar && ai-radar daily >> logs/ai-radar.log 2>&1
```

いずれの方式でも、Python環境、PATH、作業ディレクトリ、ログ出力先を明示する。
