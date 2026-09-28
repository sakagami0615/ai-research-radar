---
name: agent-daily-run
description: Use when cron等からAgentとして日次調査パイプラインを実行し、HOT最終選抜と記事企画をAgent自身の判断で行うとき。
---

# Agent Daily Run

## 目的

`ai-radar` CLIのサブコマンド(`collect` / `normalize` / `score` / `select-hot` / `save-proposals` / `report`)を順に呼び出し、HOT最終選抜と記事企画をAgent自身の判断で行い、日次レポートを完成させる。

`ai-radar daily` は決定論的な一括実行コマンドであり、このSkillでは使わない。

## 前提Skill参照

- HOT選抜の判断基準: [skills/hot-detection/SKILL.md](../hot-detection/SKILL.md) の「判断方針」(通常0〜2件、多い日でも最大5件程度、全Candidateをそのまま通知しない、重大Official Eventはスコアだけに依存させない)を用いる。
- 記事企画の観点: [skills/article-ideation/SKILL.md](../article-ideation/SKILL.md) の「企画観点」(Technical Explainer / Hands-on / Comparison / Benchmark / Critical Review)と「レビュー観点」(Evidence URLなしの主張をしない、「使ってみた」だけに偏らない、日本語記事としての独自性)を用いる。

このSkillはこれらの判断基準を再掲しない。実行前に上記2つのSkillを読むこと。

## 実行手順

1. 対象日を判定する。`date +%F` を実行し、今日の日付(`YYYY-MM-DD`)を取得する。以降の手順ではこの日付を `<date>` として使う。

   ```bash
   ai-radar collect --until <date> --data-dir data --sources-config config/sources.yaml
   ```

   `--since` は省略可(省略時は `<date>` の前日)。

2. 正規化する。

   ```bash
   ai-radar normalize --date <date>
   ```

3. HOTスコアを計算する(まだ選抜はしない)。

   ```bash
   ai-radar score --date <date> --scoring-config config/scoring.yaml
   ```

4. `data/runs/<date>/hot_candidates.jsonl` を読み、hot-detection Skillの判断方針に従って選抜するHOT候補の `hot_id` を決める。

5. 選抜結果を確定する。

   ```bash
   ai-radar select-hot --date <date> --select <id1,id2,...> [--reason <hot_id>=<選抜理由>]
   ```

   `--reason` は複数の候補に理由を付けたい場合、繰り返し指定できる(`--reason id1=理由1 --reason id2=理由2`)。

6. 選抜された各候補について、article-ideation Skillの企画観点に従って `ArticleProposal` 形式のJSON配列を作成し、`data/runs/<date>/draft_proposals.json` に書き出す。候補1件あたり1〜3件程度の企画に絞る(既存の決定論的Ideation実装の上限である3件を目安とし、通知疲れを避ける)。

   `ArticleProposal` の必須フィールド: `proposal_id` / `source_hot_id` / `title_idea` / `article_type` / `target_reader` / `why_now` / `technical_angle` / `experiment_plan` / `competition` / `traffic_opportunity` / `technical_opportunity` / `unique_angle` / `evidence_links` / `risks`。

   - `source_hot_id` は手順5で選抜した `hot_id` と一致させる。
   - `evidence_links` は空にしない(選抜候補の `evidence_urls` を引き継ぐ)。

7. 記事企画を保存する。

   ```bash
   ai-radar save-proposals --date <date> --input data/runs/<date>/draft_proposals.json
   ```

8. レポートを生成する。

   ```bash
   ai-radar report --date <date> --reports-dir reports
   ```

## エラー時の自己修正方針

`select-hot` または `save-proposals` がバリデーションエラー(終了コード1)を返した場合:

1. `data/runs/<date>/run_state.json` の `errors` を読み、エラー種別(`invalid_selection` / `invalid_reason` / `invalid_input` / `invalid_proposal` など)とメッセージを確認する。
2. 原因に応じて選抜IDまたは `draft_proposals.json` を修正し、再実行する。
3. 再実行は最大3回までとする。3回失敗しても諦めて手順8(`report`)に進む。`report` は未完了ステージを `missing_stage` として記録した上で必ず成功する設計になっているため、パイプライン全体が失敗することはない。

`normalize` / `score` が終了コード1を返した場合も、内容を確認し可能なら1回だけ修正・再実行を試みる。それでも解決しない場合は諦めて手順8に進む。

`collect` はSource単位の失敗を継続処理する設計であり、`run_state.json` の `errors` にSource単位のエラー(例: 特定Sourceの HTTP エラー)が記録されていても、`collect` コマンド自体は正常に終了コード0を返す。この場合は**再実行しない**。個別Sourceのエラーは正常な運用結果であり、他のSourceの収集結果はそのまま後続手順(`normalize`以降)に使ってよい。`collect` を再実行してよいのは、コマンド自体が終了コード1を返した場合(`invalid`な引数など、通常は発生しない)のみである。

このSkillが扱うのは構文・スキーマレベルの自己修正のみである。選抜内容や記事企画の「質」の妥当性を判断する別Agentによるレビューは、別のSkill/Workflowで扱う。

## 完了確認

- `report` の標準出力(生成されたレポートのパス)を確認する。
- `data/runs/<date>/run_state.json` の `errors` を確認し、`missing_stage` 以外の重大なエラーが残っていないか確認する。
