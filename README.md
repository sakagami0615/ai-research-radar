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

- 設計書入口: [docs/specs/README.md](docs/specs/README.md)
- AIエージェント向け作業ルール: [AGENTS.md](AGENTS.md)
- AI Agent向けSkill: [skills/](skills/)
- 設定ファイル: [config/](config/)

## AIエージェントごとの事前準備

### Codex

1. Codexでこのリポジトリを開く
2. [AGENTS.md](AGENTS.md) を読み、作業ルールとレビュー方針を確認する
3. [docs/specs/README.md](docs/specs/README.md) から必要な設計書へ進む
4. 調査・HOT判定・記事企画では [skills/](skills/) 配下のSkill文書を参照する

### Claude Code

1. Claude Codeでこのリポジトリを開く
2. [AGENTS.md](AGENTS.md) を読み、作業ルールとレビュー方針を確認する
3. [docs/specs/README.md](docs/specs/README.md) から必要な設計書へ進む
4. `skills/` 配下のSkill文書を必要に応じて参照する

### GitHub Copilot

GitHub Copilot向けの専用設定はまだ用意していません。利用する場合は、以下の資料をコンテキストとして参照してください。

1. [docs/specs/README.md](docs/specs/README.md) から設計書を確認する
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

期間や出力先を明示する場合:

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

HOT最終選抜と記事企画をAgent自身の判断で行う場合は、cronから `claude -p` / `codex exec` を直接起動する(ラッパースクリプトは使わない)。渡すプロンプトは `skills/agent-daily-run/SKILL.md` を読ませる `skills/agent-daily-run/entry-prompt.txt` であり、Agentはこれに従って `ai-radar` の各サブコマンド(`collect`/`normalize`/`score`/`select-hot`/`save-proposals`/`add-summary`/`report`)の実行、選抜HOT・注目候補・新モデルリリースの日本語概要の作成、対象日の判定、レビュー・修正ループまで自分の判断で行う。

`ai-radar` はpyenv shims経由のコマンドであり、`claude`/`codex`もPATH依存のため、crontabファイル先頭に `PATH=` 行が必要。同日の多重実行(ログが混ざる原因になる)を防ぐため `flock -n` で排他制御し、レポート未生成時にcronの失敗通知が機能するよう末尾で `test -f` による確認を行う。

```cron
PATH=/path/to/.pyenv/shims:/path/to/.local/bin:/path/to/.nvm/versions/node/<version>/bin:/usr/local/bin:/usr/bin:/bin

# Claude Codeで実行する場合
15 8 * * * cd /path/to/ai-research-radar && mkdir -p logs && D="$(date +\%F)" && flock -n logs/.daily.lock -c 'claude -p "$(cat skills/agent-daily-run/entry-prompt.txt)" --permission-mode bypassPermissions >> logs/agent-daily-run-'"$D"'.log 2>&1 && test -f reports/daily/'"$D"'.md'

# Codexで実行する場合(上記の代わりに使う。両方を同時に有効化しない)
15 8 * * * cd /path/to/ai-research-radar && mkdir -p logs && D="$(date +\%F)" && flock -n logs/.daily.lock -c 'codex exec "$(cat skills/agent-daily-run/entry-prompt.txt)" --sandbox workspace-write >> logs/agent-daily-run-'"$D"'.log 2>&1 && test -f reports/daily/'"$D"'.md'
```

- 実行ログは `logs/agent-daily-run-<date>.log` に出力される。
- ローカルで動作確認したい場合は、`flock ...` と `>> ... 2>&1`、`&& test -f ...` を外し、`cd /path/to/ai-research-radar && claude -p "$(cat skills/agent-daily-run/entry-prompt.txt)" --permission-mode bypassPermissions` をそのまま端末で実行すればよい。cron行と同じコマンドなので、動作確認用に別の手順を覚える必要がない。
- レポート生成後、Agent自身が別プロセスとして `skills/review-daily-report/SKILL.md` に従うAgentを起動し、HOT選抜・記事企画の質をレビューさせる。問題が見つかれば自分自身で修正し、最大3回まで再レビューする(`skills/agent-daily-run/SKILL.md` 手順9〜10)。3回解消できなければ、レポート冒頭に警告バナーを追加し、`data/runs/<date>/run_state.json` に `needs_review: true` を記録する。

### 決定論的な `ai-radar daily` による日次実行(手動・CI向け)

HOT選抜と記事企画を決定論的なロジックのまま実行したい場合(手動確認やCIでの検証など)は、`ai-radar daily` を直接cronに書くこともできる。

```cron
15 8 * * * cd /path/to/ai-research-radar && mkdir -p logs && ai-radar daily >> logs/ai-radar.log 2>&1
```

いずれの方式でも、Python環境、PATH、作業ディレクトリ、ログ出力先を明示してください。

## 詳細資料

より詳しい設計や運用方針は以下を参照してください。

- コンセプト: [docs/specs/01-concept.md](docs/specs/01-concept.md)
- アーキテクチャ: [docs/specs/02-architecture.md](docs/specs/02-architecture.md)
- データモデル・保存: [docs/specs/03-data-model-and-storage.md](docs/specs/03-data-model-and-storage.md)
- Source Adapter: [docs/specs/04-source-adapters.md](docs/specs/04-source-adapters.md)
- Pipeline / Scoring / Ideation: [docs/specs/05-pipeline-scoring-ideation.md](docs/specs/05-pipeline-scoring-ideation.md)
- CLI・運用: [docs/specs/06-cli-and-operations.md](docs/specs/06-cli-and-operations.md)
- Skills・Agent Workflow: [docs/specs/07-skills-and-agent-workflow.md](docs/specs/07-skills-and-agent-workflow.md)
- テスト・拡張: [docs/specs/08-testing-and-extension.md](docs/specs/08-testing-and-extension.md)
