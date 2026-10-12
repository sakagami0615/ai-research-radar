# 初期MVPの設計判断

元の設計判断・成功条件を保存した出典資料。現在の要件は [要件定義の入口](../01-requirements/README.md) で確認する。

## 判断方針

AI Research Radar は「大量通知」ではなく「確認する価値が高い少数候補」を出す。通常日は0から数件、多い日でも5件程度の選抜HOTを想定する。

また、外部LLMや認証必須APIに依存しないMVPとするため、初期のJudge / Critique / Debateは決定論的なローカル処理で代替する。認証やコストの方針が固まった時点でLLM Judgeへ差し替える([将来対応](../../support/02-planning/future-works.md))。
