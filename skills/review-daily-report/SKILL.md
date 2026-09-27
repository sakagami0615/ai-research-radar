---
name: review-daily-report
description: Use when 日次パイプラインの成果物(HOT選抜・記事企画・レポート)を、実行したAgentとは別セッションのAgentとして品質検証するとき。
---

# Review Daily Report

## 目的

`agent-daily-run` Skillに従って実行された日次パイプラインの成果物を、実行したAgentとは別セッションのAgentとして検証する。構文・スキーマレベルの妥当性はCLIサブコマンド自体が検証済みであり、このSkillが扱うのは選抜内容・記事企画の「質」の妥当性である。

## 判断基準の参照

- HOT選抜の妥当性: [skills/hot-detection/SKILL.md](../hot-detection/SKILL.md) の「判断方針」「レビュー観点」を用いる。
- 記事企画の妥当性: [skills/article-ideation/SKILL.md](../article-ideation/SKILL.md) の「企画観点」「レビュー観点」を用いる。

このSkillはこれらの判断基準を再掲しない。実行前に上記2つのSkillを読むこと。

## 検証対象

指定された `<date>` について、以下を読む。

- `reports/daily/<date>.md`
- `data/runs/<date>/hot_candidates.jsonl`(`selected` の内訳を含む)
- `data/runs/<date>/article_proposals.jsonl`(存在する場合)

## 検証観点

- HOT選抜数が妥当か(通常0〜2件、多くても5件程度)。
- Momentumのみで低Credibility情報を過大評価していないか。
- Source Familyが単一に偏ったまま選抜していないか(cross-source確認なし)。
- 選抜0件の場合、その判断が妥当か(見落としがないか)も確認する。
- 記事企画にEvidence URLなしの主張がないか。
- 各 `article_proposals` の `evidence_links` が、対応するHOT候補(`source_hot_id` が一致するもの)の `evidence_urls` と整合しているか。
- 「使ってみた」だけに偏った企画になっていないか、日本語記事としての独自性があるか。

## 出力

1. 上記観点で明確な誤り(根拠のない選抜・Evidence URLのない主張など、Critical)や、妥当性に疑問があり確認が必要な問題(Important)がなければ、`data/runs/<date>/review_feedback.md` が存在しないことを保証する(存在していれば削除する)。
2. 該当する問題があれば、`data/runs/<date>/review_feedback.md` に自然文で具体的に書く。該当箇所・理由・修正方針を含めること。
3. 表現の好みなどMinor相当の指摘は `review_feedback.md` に書かない。Critical/Importantのみを対象とする(Minorまで指摘すると、修正ループが実質的に終わらなくなるため)。

`review_feedback.md` の存在有無だけが、呼び出し元スクリプトにとっての「承認/要修正」の判定基準になる。この基準を厳密に守ること。
