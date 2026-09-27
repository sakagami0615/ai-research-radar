---
name: hot-detection
description: Use when 正規化済みSignalから日次の選抜HOTを判定するとき。
---

# HOT Detection

## 目的

Popularity、Momentum、Credibility、Cross-source Confidenceから日次の選抜HOTを決める。

## 入力

- Event JSONL
- scoring config

## 出力

- HOT Candidate JSONL
- HOT判定理由

## 判断方針

- 通常日は0から2件
- 多い日でも最大5件程度
- 全Candidateをそのまま通知しない
- 重大Official Eventはスコアだけに依存させない

## レビュー観点

- Momentumだけで低Credibility情報を過大評価していないか
- Source Familyが偏っていないか
- 通知疲れする件数になっていないか
