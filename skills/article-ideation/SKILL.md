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

- Article Proposal JSONL
- Daily Report内の記事企画候補

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
