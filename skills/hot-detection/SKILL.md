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
- 重大Official Eventはスコアだけに依存させない。`score` は、family `official` で `event_type` が `major_*` のEvent(公式ブログの新モデルリリースを含む)を、スコアが `minimum_score` 未満でもHOT候補にする(理由に `Official override`)。候補になった後は、他の候補と同じく内容を確認して採否を決める(発表以外の記事なら選抜外にする)。
- HOT候補(`hot_candidates.jsonl`)は、スコアが `minimum_score`(既定75)以上のEventとOfficial overrideのEventだけである。それ未満のEventは候補にも保存されないため、選抜できない。通常の選抜は0〜2件（明示指定時でも最大5件）とする。候補スコアだけで自動選抜しない。
- 選抜には関連性、新規性、重要性、読者影響の説明と確認済み一次Evidenceを付ける。取得不能・未確認は保留とし、単一公式発表は発表事実の範囲に限定する。
- 判断は `selection_input.json` の評価レコード(`Assessment`)として記録する(書式は [skills/agent-daily-run/SKILL.md](../agent-daily-run/SKILL.md) の手順4)。
- `screened_ids` は「内容を確認した候補」の一覧である。確認した候補だけを入れ、確認していない候補は `screened_ids` にも評価レコードにも入れない(除外済み `rejected` として書かない)。
- PyPIのJSON APIで取得したメタデータは、配布元である公式レジストリの一次情報(`primary`)として扱う。HTTP 200でも内容を確認できなかった根拠は確認済みにしない(取得方法と `status` の決め方は [skills/agent-daily-run/SKILL.md](../agent-daily-run/SKILL.md) の手順4「根拠の取得」)。

## レビュー観点

- Momentumだけで低Credibility情報を過大評価していないか
- Source Familyが偏っていないか
- 通知疲れする件数になっていないか
