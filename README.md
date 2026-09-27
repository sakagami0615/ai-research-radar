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

例:

```cron
15 8 * * * cd /path/to/ai-research-radar && mkdir -p logs && ai-radar daily >> logs/ai-radar.log 2>&1
```

cronで使う場合は、Python環境、PATH、作業ディレクトリ、ログ出力先を明示してください。

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
