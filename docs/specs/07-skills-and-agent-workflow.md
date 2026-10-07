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

`ai-radar` のサブコマンド(`collect` / `normalize` / `score` / `select-hot` / `save-proposals` / `add-summary` / `report`)を順に実行し、HOT最終選抜、選抜HOT・注目候補・新モデルリリースの日本語概要の作成、記事企画をAgent自身の判断で行う日次ワークフロー。cronから `claude -p` / `codex exec` で直接起動されることを想定する(ラッパースクリプトなし)。HOT最終選抜は `data/runs/<date>/selection_input.json` に評価レコードを書き、`select-hot` で検証・保存する(形式は03章「SelectionInput」参照)。対象日の判定、および`review-daily-report`を使ったレビュー・修正ループ(最大3回)もこのSkillの手順内でAgent自身が行う。判断基準は `hot-detection` / `article-ideation` を参照する。根拠のURLの取得規則(PyPIは `/project/` ページではなくJSON APIで確認し `primary` として記録する、HTTP 200でもbot対策ページなど本文を取得できなければ `unavailable` にする)と、取得ログ `data/runs/<date>/evidence_fetch_log.tsv`(列: `url` / `http_status` / `fetched_at` / `content_verified` / `note`)の形式も、このSkillの手順4で定める。注目候補・新モデルリリースの概要補完(手順8b)でのURLの取得も、この規則と取得ログに従う。

### review-daily-report

`agent-daily-run` Skillを実行したAgentとは別セッション・別プロセスのAgentとして、その日のHOT選抜・記事企画・レポートの「質」を検証する。対象hashを固定し、問題があれば`ReviewResult`と人間向けfeedbackを別保存する。最大3回まで再レビューし、起動失敗・記録欠落・hash不一致を承認扱いしない。判断基準は`hot-detection` / `article-ideation`を参照する。根拠の `checked_at` は取得ログ `evidence_fetch_log.tsv` の `fetched_at` と突き合わせ、内容を確認できなかった取得を `verified` としていないかを確認する(取得ログは読むだけで追記しない)。

レポートの「注目候補(選抜外)」「新モデルリリース」はCLIが決定論的に生成し実行Agentが修正できないため、セクションの内容(どの項目が載るか、並び順、スコアなど)は指摘対象にしない(HOT選抜の見落とし判断の材料としては参照してよい)。ただし、概要のうち当日に書かれたものは実行Agentが修正できるため、Evidence・リンク先との整合、タイトルの直訳だけになっていないか、未確認の内容を断定していないかを指摘対象にする。当日に書かれた概要は、選抜HOT・注目候補では当日の `hot_candidates.jsonl` または `digest_summaries.json` にある `hot_id` のもの、新モデルリリースではすべて(概要は当日の `digest_summaries.json` にしかなく、いつでも `add-summary --input` で直せるため)である。過去日の注目候補が自分で持っている概要は当日に修正できないため指摘対象にしない。情報取得失敗・未確認の理由が書かれた「概要未作成」は指摘しない(観点の詳細は `review-daily-report` Skillを参照)。

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
