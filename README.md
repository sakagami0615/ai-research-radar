# AI Research Radar

AI Research Radar は、AI関連の研究、ツール、ライブラリ、公式発表、開発者コミュニティの話題を収集し、技術記事のネタ候補や日次トレンド確認に使うための調査基盤です。

このリポジトリには、日次調査を実行するPythonツール、AIエージェント向けの作業ガイド、設計書、設定ファイルがまとまっています。まずはこのREADMEから全体像をつかみ、必要に応じて詳細資料へ進んでください。

## 何ができるか

- 認証なしで取得できる公開SourceからAI関連Signalを収集する
- 収集データをJSONLとして保存する
- SignalをEvent / Topicへまとめる
- HOT候補を選抜する
- HOT候補から技術記事の企画案を生成する
- 日次Markdownレポートを出力する
- Claude Code / Codex から共通のSkillと設計書を参照して作業できる

## リポジトリ内の主な入口

- 日次レポート作成の役割分担(人・Skill・Pythonコード、1枚図): [日次レポート作成の役割分担](docs/support/03-reference/daily-run-flow.svg)
- 参考資料の入口: [docs/support/03-reference/README.md](docs/support/03-reference/README.md)（調査資料はローカルのAPPENDIXに配置）
- ドキュメント入口・読む順: [docs/README.md](docs/README.md)
- AIエージェント向け作業ルール: [AGENTS.md](AGENTS.md)
- AI Agent向けSkill: [skills/](skills)
- 設定ファイル: [config/](config)
- 将来対応の構想: [docs/support/02-planning/future-works.md](docs/support/02-planning/future-works.md)

## AIエージェントごとの事前準備

### Codex

1. Codexでこのリポジトリを開く
2. [AGENTS.md](AGENTS.md) を読み、作業ルールとレビュー方針を確認する
3. [docs/README.md](docs/README.md) から必要な設計書へ進む
4. 日次実行は [skills/agent-daily-run/SKILL.md](skills/agent-daily-run/SKILL.md)、HOT判定・記事企画の観点は [skills/](skills) 配下のSkill文書を参照する

### Claude Code

1. Claude Codeでこのリポジトリを開く
2. [AGENTS.md](AGENTS.md) を読み、作業ルールとレビュー方針を確認する
3. [docs/README.md](docs/README.md) から必要な設計書へ進む
4. `skills/` 配下のSkill文書を必要に応じて参照する

### GitHub Copilot

GitHub Copilot向けの専用設定はまだ用意していません(対応は [docs/support/02-planning/future-works.md](docs/support/02-planning/future-works.md) に記載)。利用する場合は、以下の資料をコンテキストとして参照してください。

1. [docs/README.md](docs/README.md) から設計書を確認する
2. [AGENTS.md](AGENTS.md) で作業ルールを確認する
3. エディタ側でこのリポジトリ全体をCopilotの参照コンテキストに含める

## セットアップ

Python 3.14.4以上を使います。

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

## 実行方法

日次レポートを実行します。

```bash
ai-radar daily
```

出力先の既定値は `config/runtime.yaml` の `output`(`data` / `reports`)です。期間や出力先を明示する場合:

```bash
ai-radar daily \
  --since 2026-09-24 \
  --until 2026-09-25 \
  --data-dir data \
  --reports-dir reports
```

主な出力:

- `data/`: JSONL形式の構造化データ
- `reports/daily/`: 日次Markdownレポート

## cronでの利用

cronが未インストールの環境では、事前にインストールしてください。

```bash
# cronがインストール済みか確認する
command -v crontab

# 未インストールの場合(Debian/Ubuntu系)
sudo apt-get update && sudo apt-get install -y cron
sudo systemctl enable --now cron

# 未インストールの場合(RHEL/CentOS/Fedora系)
sudo dnf install -y cronie
sudo systemctl enable --now crond
```

### AI Agent(Claude Code / Codex)による日次実行(推奨)

HOT最終選抜と記事企画をAgent自身の判断で行う場合は、cronから `claude -p` / `codex exec` を直接起動する(ラッパースクリプトは使わない)。渡すプロンプトは `skills/agent-daily-run/SKILL.md` を読ませる `skills/agent-daily-run/entry-prompt.txt` であり、Agentはこれに従って `ai-radar` の各サブコマンド(`collect`/`normalize`/`score`/`select-hot`/`save-proposals`/`add-summary`/`add-source-overview`/`report`/`mark-needs-review`)の実行、選抜HOT・注目候補・新モデルリリースの日本語概要の作成、収集Source一覧のSourceごとの「本日の傾向」の作成、対象日の判定、レビュー・修正ループまで自分の判断で行う。

`ai-radar` はpyenv shims経由のコマンドであり、`claude`/`codex`もPATH依存のため、crontabファイル先頭に `PATH=` 行が必要。同日の多重実行(ログが混ざる原因になる)を防ぐため `flock -n` で排他制御し、レポート未生成時にcronの失敗通知が機能するよう末尾で `test -f` による確認を行う。

```cron
PATH=/path/to/.pyenv/shims:/path/to/.local/bin:/path/to/.nvm/versions/node/<version>/bin:/usr/local/bin:/usr/bin:/bin

# Claude Codeで実行する場合
15 8 * * * cd /path/to/ai-research-radar && mkdir -p logs && D="$(date +\%F)" && flock -n logs/.daily.lock -c 'claude -p "$(cat skills/agent-daily-run/entry-prompt.txt)" --permission-mode bypassPermissions >> logs/agent-daily-run-'"$D"'.log 2>&1 && test -f reports/daily/'"$D"'.md'

# Codexで実行する場合(上記の代わりに使う。両方を同時に有効化しない)
15 8 * * * cd /path/to/ai-research-radar && mkdir -p logs && D="$(date +\%F)" && flock -n logs/.daily.lock -c 'codex exec "$(cat skills/agent-daily-run/entry-prompt.txt)" --sandbox workspace-write >> logs/agent-daily-run-'"$D"'.log 2>&1 && test -f reports/daily/'"$D"'.md'
```

- 実行ログは `logs/agent-daily-run-<date>.log` に出力される。
- 手で起動する場合も `flock -n` は外さない(本番の実行と同時に動かさないため)。ロックファイルはメインチェックアウトの絶対パスの `logs/.daily.lock` を指定する(ワークツリーから起動しても本番とロックを共有するため)。動作確認は、本番の `data/` / `reports/` に影響しないテストモード(`skills/agent-daily-run/entry-prompt-test.txt`。出力先は `test_output/`)で行う。本番の手での起動では、作成済みの日の判定は #44 で入るまでないため、当日のレポートがある日に本番で実行すると上書きされる。手での起動コマンドとテストモードの詳細は [cronによる日次実行](docs/support/01-operations/scheduled-run.md) を参照。
- レポート生成後、Agent自身が別プロセスとして `skills/review-daily-report/SKILL.md` に従うAgentを起動し、HOT選抜・記事企画の質をレビューさせる。問題が見つかれば自分自身で修正して再レビューする。レビューの試行は最大3回(初回を1回目とする)。修正は試行の間に行うため最大2回(`skills/agent-daily-run/SKILL.md` 手順9〜10)。3回目の試行の後も指摘が残れば、`ai-radar mark-needs-review` で `<data_dir>/runs/<date>/run_state.json`(本番は `data`、テストモードは `test_output/data`)に `needs_review: true` を記録し、`report` を再実行してレポート冒頭に警告を出す。

### 決定論的な `ai-radar daily` による日次実行(手動・CI向け)

HOT選抜と記事企画を決定論的なロジックのまま実行したい場合(手動確認やCIでの検証など)は、`ai-radar daily` を直接cronに書くこともできる。

```cron
15 8 * * * cd /path/to/ai-research-radar && mkdir -p logs && ai-radar daily >> logs/ai-radar.log 2>&1
```

いずれの方式でも、Python環境、PATH、作業ディレクトリ、ログ出力先を明示してください。

## 詳細資料

より詳しい設計や運用方針は以下を参照してください。

- [仕様・設計](docs/spec/README.md)：01 要求・要件 → 02 基本設計 → 03 詳細設計 → 04 検証・受入 → 05 設計判断。
- [開発・運用支援](docs/support/README.md)：01 運用 → 02 計画・適用状況 → 03 参考調査。
- 将来対応: [docs/support/02-planning/future-works.md](docs/support/02-planning/future-works.md)
