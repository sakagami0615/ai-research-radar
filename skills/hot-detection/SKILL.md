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
- 全候補を発見候補として保存し、通常の選抜は0〜2件（明示指定時でも最大5件）とする。候補スコアだけで自動選抜しない。
- 選抜には関連性、新規性、重要性、読者影響の説明と確認済み一次Evidenceを付ける。取得不能・未確認は保留とし、単一公式発表は発表事実の範囲に限定する。
- 判断は `selection_input.json` の評価レコード(`Assessment`)として記録する(書式は [skills/agent-daily-run/SKILL.md](../agent-daily-run/SKILL.md) の手順4)。
- `screened_ids` は「内容を確認した候補」の一覧である。確認した候補だけを入れ、確認していない候補は `screened_ids` にも評価レコードにも入れない(除外済み `rejected` として書かない)。

## レビュー観点

- Momentumだけで低Credibility情報を過大評価していないか
- Source Familyが偏っていないか
- 通知疲れする件数になっていないか
