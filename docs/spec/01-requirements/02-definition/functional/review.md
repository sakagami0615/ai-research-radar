# F-06 独立した内容レビュー

UC-01・UC-04に対応する。Agent経路の成果物は、作成担当とは別の担当が根拠・選抜・企画・文章を確認し、指摘を修正できること。

## 受入条件

- 別担当が内容を確認し、問題があれば作成担当へ返す。
- レビューの試行は最大3回(初回を1回目とする)。修正は試行の間に行うため最大2回。起動失敗・記録欠落を承認扱いしない。
- 上限後の未解消指摘や修正不能の場合、警告と `needs_review` を残す。
- 品質改善目標としてレビュー対象と結果を対応させ、対象の変更後に古い承認を有効と扱わない。

対象はAgent経路。一括dailyの生成だけでは独立レビュー済みとしない。現行は `review_feedback.md` の有無で判定するSkill手順であり、hash対応のレビュー記録は未実装(未結線だった品質v2モジュールはPR #33で削除済み。[既知課題](../../../../support/02-planning/known-gaps.md))。状態は [適用状況](../../../../support/02-planning/requirement-status.md) で確認する。[運用](../../../../support/01-operations/review-and-improvement.md)と [変更設計](../../../05-decisions/audit-remediation/execution-and-reporting.md)を参照。
