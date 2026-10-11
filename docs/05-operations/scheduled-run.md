# cronによる日次実行

旧設計書の該当節を分割した資料。現行と移行目標の区別は [文書全体の入口](../README.md) から確認する。

## cron想定

推奨はcronから `claude -p` / `codex exec` を直接起動するAI Agent(Claude Code / Codex)経由の実行である(ラッパースクリプトは使わない)。渡すプロンプトは `skills/agent-daily-run/SKILL.md` を読ませる `skills/agent-daily-run/entry-prompt.txt` であり、`collect` / `normalize` / `score` / `select-hot` / `save-proposals` / `add-summary` / `add-source-overview` / `report` / `mark-needs-review` の実行、概要の作成・補完、Sourceごとの本日の傾向の作成、対象日の判定、レビュー・修正ループまでAgent自身が判断して行う。

`ai-radar`/`claude`/`codex` はいずれもPATH依存のコマンドであり、cronの実行環境には通常PATHが通っていないため、crontabファイル先頭に `PATH=` 行が必要になる。同日の多重実行(ログが混ざる)を防ぐため `flock -n` で排他制御し、レポート未生成時にcronの失敗通知が機能するよう末尾で `test -f` による確認を行う。

```cron
PATH=/path/to/.pyenv/shims:/path/to/.local/bin:/path/to/.nvm/versions/node/<version>/bin:/usr/local/bin:/usr/bin:/bin

15 8 * * * cd /path/to/ai-research-radar && mkdir -p logs && D="$(date +\%F)" && flock -n logs/.daily.lock -c 'claude -p "$(cat skills/agent-daily-run/entry-prompt.txt)" --permission-mode bypassPermissions >> logs/agent-daily-run-'"$D"'.log 2>&1 && test -f reports/daily/'"$D"'.md'
```

- `codex` で実行する場合は `claude -p "..." --permission-mode bypassPermissions` を `codex exec "..." --sandbox workspace-write` に置き換えた別のcron行を使う(両方を同時に有効化しない)。
- 実行ログは `logs/agent-daily-run-<date>.log` に出力される。
- レポート生成後、Agent自身が別プロセスの `claude -p` / `codex exec` を起動して `skills/review-daily-report/SKILL.md` によるレビューを行わせ、指摘があれば自分自身で修正して最大3回まで再試行する(`skills/agent-daily-run/SKILL.md` 手順9〜10)。3回解消できなければ `ai-radar mark-needs-review` で `run_state.json` に `needs_review: true` を記録し、`report` を再実行してレポート冒頭に警告を出す。

上記のレビュー起動(Agent自身が別プロセスの `claude -p` / `codex exec` を起動する手順)はcronからの起動を前提とする。対話セッション(IDE拡張のAuto Modeなど)内で `agent-daily-run` を手動実行する場合、Bash経由で `claude -p ... --permission-mode bypassPermissions` を新規起動しようとすると、そのセッション固有の権限分類器に「Create Unsafe Agents」として拒否されることがある。この場合は同一セッション内のsubagent(Agent機能)へレビューを委譲する代替手段で対応してよい。cronによる本番実行はこの制約を受けない独立プロセスであるため、設計自体は変更不要である。

決定論的な `ai-radar daily` を直接cronに書く方法も、手動運用・CI向けの代替手段として利用できる。

```cron
15 8 * * * cd /path/to/ai-research-radar && ai-radar daily >> logs/ai-radar.log 2>&1
```

いずれの方式でも、Python環境、PATH、作業ディレクトリ、ログ出力先を明示する。
