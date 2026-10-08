---
name: article-ideation
description: Use when 選抜HOTから技術記事の企画候補を作るとき。
---

# Article Ideation

## 目的

選抜HOTをもとに、技術記事として成立する企画候補を生成する。

## 入力

- HOT Candidate
- HOT判定理由
- Evidence URL

## 出力

- Article Proposal(v2。`schema_version: 2` と `quality` を持つ。`save-proposals` の入力形式と検証内容は [03章「save-proposals の入力(v2)」](../../docs/specs/03-data-model-and-storage.md)、Agent経路での書き方は [agent-daily-run Skill](../agent-daily-run/SKILL.md) の手順6)
- Daily Report内の記事企画候補(v2の企画は `quality` の全項目も表示される)

## quality の書き方

企画ごとに次を具体的に書く。定型文や題名の言い換えで埋めない。

- 検証の問い(`question`)と既存手段との差分(`difference`)。
- 比較対象(`baseline`)と版(`baseline_version`)。比較対象に版がなければ固定日や条件を書く。
- 測定方法(`measurement`)、測定指標(`metrics`、1件以上)、入力・環境・手順(`inputs_and_environment`)。解説記事でも、仕様比較などの確認方法を書く。
- 概算工数(`effort`)とその前提(`effort_assumptions`)、成功条件(`success_condition`)、中止・保留条件(`stop_condition`)。
- 確認した根拠(`evidence`)と未確認事項(`unknowns`)。主張に対応する一次情報を根拠にし、確認できなかったことは未確認事項に書く。
- 比較対象などのために、元のHOT候補の Evidence URL にないURLを `evidence_links` に加えた場合は、同じURLの根拠を `evidence` に書き、`claim` にそのURLの役割(例: 「比較対象 X の仕様」)を書く。HOTの主張を支えるURLと区別するためで、役割がないと保存できない。
- 競合や読者需要を調べていない場合は「未調査」と書く。技術機会・流入機会を一律にHighとしたり、HOT点数から推定したりしない。
- 機能を確認できない場合は企画を作らず保留する(保留理由は `deferral_reason` に書く)。

## 企画観点

- Technical Explainer
- Hands-on
- Comparison
- Benchmark
- Critical Review

## レビュー観点

- Evidence URLなしの主張をしていないか
- 「使ってみた」だけに偏っていないか
- 日本語記事としての独自性があるか
- 企画は1候補あたり0〜3件。固有の問い、比較対象、測定指標、入力環境、概算工数、成功条件、中止条件を必須とし、定型文だけの企画を保存しない。
- 追加したURLに役割(`claim`)が書かれ、HOTの主張を支える根拠と区別できるか。
