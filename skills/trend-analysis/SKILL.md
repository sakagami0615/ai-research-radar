---
name: trend-analysis
description: Use when JSONL履歴から週次・月次・年次のAIトレンドを分析するとき。
---

# Trend Analysis

## 目的

Signal、Event、Topic履歴を使って、週次・月次・年次のAIトレンドを分析する。

## MVPでの扱い

MVPでは本格実装しない。Daily Pipelineが保存するJSONLを将来の入力として使う。

## 将来出力

- Weekly Trend Report
- Monthly Landscape
- Yearly Review

## レビュー観点

- Daily JSONLだけで後から集計できるか
- Topic履歴に必要な情報が保存されているか
- 旧スコアを新指標へ黙って置換せず、実測値・新着度・過去差分・未取得を別系列として扱う。
