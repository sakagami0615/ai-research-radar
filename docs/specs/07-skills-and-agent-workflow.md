# 07. Skills・Agent Workflow設計

## 目的

Claude Code / Codexのどちらでも、同じ調査Workflowを参照できるように `skills/` 配下へ共通Skillを置く。

実装ロジックはSkillではなく `src/` に置く。Skillは「何をしたいか」「どう確認するか」を案内するWorkflow文書である。

## Skill一覧

- `skills/ai-radar/SKILL.md`
- `skills/agent-daily-run/SKILL.md`
- `skills/review-daily-report/SKILL.md`
- `skills/hot-detection/SKILL.md`
- `skills/article-ideation/SKILL.md`
- `skills/trend-analysis/SKILL.md`
- `skills/report-generation/SKILL.md`

## 役割

### ai-radar

日次AI Radarを実行し、JSONLとMarkdownレポートを生成する入口。

### agent-daily-run

`ai-radar` の6サブコマンド(`collect` / `normalize` / `score` / `select-hot` / `save-proposals` / `report`)を順に実行し、HOT最終選抜と記事企画をAgent自身の判断で行う日次ワークフロー。`scripts/run-agent-daily.sh` からcron経由で起動されることを想定する。判断基準は `hot-detection` / `article-ideation` を参照する。

### review-daily-report

`agent-daily-run` Skillを実行したAgentとは別セッションのAgentとして、その日のHOT選抜・記事企画・レポートの「質」を検証する。問題があれば `data/runs/<date>/review_feedback.md` に指摘を書き、`scripts/run-agent-daily.sh` が元Agentへの修正依頼と再レビューを最大3回まで繰り返す。判断基準は `hot-detection` / `article-ideation` を参照する。

### hot-detection

選抜HOTを判定する観点を共有する。全Candidateを通知せず、少数の確認対象へ絞る。

### article-ideation

選抜HOTから技術記事企画を作る観点を共有する。Evidence URLなしの主張を避ける。

### trend-analysis

週次・月次・年次分析の将来Workflowを定義する。MVPではDaily JSONLを将来入力として残す。

### report-generation

構造化データをMarkdown、将来HTML/PNGへ変換する観点を共有する。

## レビュー運用

AGENTS.mdの方針に従い、成果物を作成した場合はレビューを行う。

基本方針:

- 実装やドキュメント作成後にレビューを実施する。
- 可能な場合は別セッションまたは別サブエージェントでレビューする。
- Critical / Important が残る場合は完了扱いにしない。
- 修正後はscoped re-reviewを行う。
- レビューで得た知見は、必要に応じてSkill、設計書、台帳に反映する。

## 改善ループ

日次運用で失敗や修正要望が出た場合は、以下の順で改善する。

1. `run.jsonl` とMarkdownレポートで失敗内容を確認する。
2. Source固有の問題ならAdapterまたはconfigを修正する。
3. 判定品質の問題ならscoring、dedup、ideationを修正する。
4. 運用手順の問題ならSkillまたは設計書を修正する。
5. 回帰テストを追加する。

## Subagent-driven開発

大きな実装やレビューでは、実装担当とレビュー担当を分ける。コミットは禁止されている場合、差分パッケージとSDD台帳で進捗を管理する。
