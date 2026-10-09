# 07. Skills・Agent Workflow設計

## 目的

Claude Code / Codexのどちらでも、同じ調査Workflowを参照できるように `skills/` 配下へ共通Skillを置く。

実装ロジックはSkillではなく `src/` に置く。Skillは「何をしたいか」「どう確認するか」を案内するWorkflow文書である。

## Skill一覧

| Skill | 役割 |
| --- | --- |
| `skills/agent-daily-run/SKILL.md`(+ `recovery.md`) | 日次の実行手順。cronから起動されたAgentが従う |
| `skills/review-daily-report/SKILL.md` | 日次の成果物の品質レビュー。`agent-daily-run` が別プロセスのAgentに実行させる |
| `skills/hot-detection/SKILL.md` | HOT選抜の判断基準(上の2つから参照する) |
| `skills/article-ideation/SKILL.md` | 記事企画の観点と `quality` の書き方(上の2つから参照する) |

`ai-radar daily`(決定論経路)の使い方はREADMEと06章に書き、Skillは置かない。

## 役割

### agent-daily-run

`ai-radar` のサブコマンドを順に実行し、HOT最終選抜、選抜HOT・注目候補・新モデルリリースの日本語概要、収集Source一覧のSourceごとの「本日の傾向」、記事企画をAgent自身の判断で作る日次ワークフロー。cronから `claude -p` / `codex exec` で直接起動されることを想定する(ラッパースクリプトなし)。判断基準は `hot-detection` / `article-ideation` を参照する。

- `SKILL.md`: 通常の流れ(手順1〜10)。各手順で書くファイルと実行するコマンドを示す。対象日の判定、選抜(`selection_input.json` → `select-hot`)、記事企画(`draft_proposals.json` → `save-proposals`)、概要の補完(`add-summary`)、本日の傾向(`add-source-overview`)、レポート生成(`report`)、レビュー・修正ループ(最大3回)、未解消時の `mark-needs-review` まで。
- `recovery.md`: 失敗したときの対応。エラー種別ごとの直し方、再実行の上限と数え方、壊れた入力(`corrupt_input`)の流し直し、レポート生成前の `stage_results` の確認と補完実行、レビュー指摘を受けたときの修正の仕方。エラー種別の一覧そのものは06章を参照し、Skillには書き写さない。
- 根拠のURLの取得規則(PyPIは `/project/` ページではなくJSON APIで確認し `primary` として記録する、HTTP 200でもbot対策ページなど本文を取得できなければ `unavailable` にするなど)と、取得ログ `data/runs/<date>/evidence_fetch_log.tsv`(列: `url` / `http_status` / `fetched_at` / `content_verified` / `note`)の形式は、`SKILL.md` の手順4で定める。判断日時・確認日時は記録時に実測したUTC時刻とし、推定値で埋めない。
- 入力ファイルの形式は03章(`SelectionInput`、「save-proposals の入力(v2)」)、各コマンドの引数とエラーは06章に従う。

### review-daily-report

`agent-daily-run` Skillを実行したAgentとは別セッション・別プロセスのAgentとして、その日のHOT選抜・記事企画・レポートの「質」を検証する。判断基準は `hot-detection` / `article-ideation` を参照する。

- 承認・要修正の判定は `data/runs/<date>/review_feedback.md` の有無だけで行う。Critical / Important の指摘があるときだけレビュー担当がこのファイルを書き、なければ書かない(Minorは書かない)。実行側は、ファイルがなければ承認、あれば修正して再レビューを依頼する(最大3回)。3回で解消しなければ `mark-needs-review` で記録する。
- レビュー担当は原成果物を編集しない。書くのは `review_feedback.md` だけである。
- 根拠の `checked_at` は取得ログ `evidence_fetch_log.tsv` の `fetched_at` と突き合わせ、内容を確認できなかった取得を `verified` としていないかを確認する(取得ログは読むだけで追記しない)。
- 対象成果物のhashの固定や構造化した結果(`ReviewResult`)は未実装である([future-works](../future-works.md))。

レポートの「注目候補(選抜外)」「新モデルリリース」はCLIが決定論的に生成し実行Agentが修正できないため、セクションの内容(どの項目が載るか、並び順、スコアなど)は指摘対象にしない(HOT選抜の見落とし判断の材料としては参照してよい)。ただし、概要のうち当日に書かれたものは実行Agentが修正できるため、Evidence・リンク先との整合、タイトルの直訳だけになっていないか、未確認の内容を断定していないかを指摘対象にする。当日に書かれた概要は、選抜HOT・注目候補では当日の `hot_candidates.jsonl` または `digest_summaries.json` にある `hot_id` のもの、新モデルリリースではすべて(概要は当日の `digest_summaries.json` にしかなく、いつでも `add-summary --input` で直せるため)である。過去日の注目候補が自分で持っている概要は当日に修正できないため指摘対象にしない。情報取得失敗・未確認の理由が書かれた「概要未作成」は指摘しない(観点の詳細は `review-daily-report` Skillを参照)。収集Source一覧のSourceごとの「本日の傾向」も、実行Agentが `add-source-overview --input` で修正できるため指摘対象にする(一覧の内容と食い違っていないか、日本語で書かれているか、おおむね200字以内か、収集1件以上のSourceに「傾向未作成」が残っていないか。ただし `run_state.json` に `add-source-overview` のエラーが残っている、つまり再実行の上限に達して保存できなかった場合は指摘しない)。

### hot-detection

選抜HOTを判定する観点を共有する。全Candidateを通知せず、少数の確認対象へ絞る。

### article-ideation

選抜HOTから技術記事企画を作る観点と、v2 の企画で書く `quality`(検証の問い・比較対象と版・測定方法・成功/中止条件・根拠など)の書き方を共有する。Evidence URLなしの主張を避け、比較対象などのために追加したURLには `quality.evidence` の `claim` に役割を書く。

## レビュー運用

AGENTS.mdの方針に従い、成果物を作成した場合はレビューを行う。

基本方針:

- 実装やドキュメント作成後にレビューを実施する。
- 可能な場合は別セッションまたは別サブエージェントでレビューする。
- Critical / Important が残る場合は完了扱いにしない。
- 修正後はscoped re-reviewを行う。
- レビューで得た知見は、必要に応じてSkill、設計書、AGENTS.mdに反映する。

## 改善ループ

日次運用で失敗や修正要望が出た場合は、以下の順で改善する。

1. `run.jsonl` とMarkdownレポートで失敗内容を確認する。
2. Source固有の問題ならAdapterまたはconfigを修正する。
3. 判定品質の問題ならscoring、dedup、ideationを修正する。
4. 運用手順の問題ならSkillまたは設計書を修正する。
5. 回帰テストを追加する。

## Subagent-driven開発

大きな実装やレビューでは、実装担当とレビュー担当を分ける。コミット・プッシュはユーザーの承認後に行う(06章「コミット運用」)。
