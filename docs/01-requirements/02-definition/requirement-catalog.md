# 要件一覧と管理方法

本一覧は旧コンセプト・品質改善設計・運用ルールの要求を識別可能に整理したもの。新たな性能数値や提供範囲を決定しない。受入条件の正本はリンク先の機能・非機能要件である。

| ID | 必要な結果 | 定義 |
| --- | --- | --- |
| F-01 | 公開情報を対象期間に応じて収集する | [収集](functional/collection.md) |
| F-02 | 情報を共通形式へ正規化し、重複を整理する | [正規化](functional/normalization.md) |
| F-03 | 根拠と判断理由を持つ少数HOTを選抜する | [選抜](functional/hot-selection.md) |
| F-04 | 採否を検討できる具体的な記事企画を作る | [企画](functional/article-ideation.md) |
| F-05 | 日次レポートと判断用データを保存する | [レポート](functional/reporting.md) |
| F-06 | 内容を別担当がレビューし、結果を区別する | [レビュー](functional/review.md) |
| N-01 | Sourceの失敗を他Sourceへ波及させない | [信頼性](non-functional/reliability.md) |
| N-02 | 再実行・修正の回数を制限し、状態を区別する | [信頼性](non-functional/reliability.md) |
| N-03 | 根拠・判断・実行結果を追跡できる | [追跡性](non-functional/traceability.md) |
| N-04 | 旧データと共通Agent運用の互換性を保つ | [互換性](non-functional/compatibility.md) |
| N-05 | 機密情報の記録を避ける | [運用と機密](non-functional/operability.md) |
| N-06 | 手動・cronから実行し、失敗を診断できる | [運用と機密](non-functional/operability.md) |
| N-07 | 成果物を日本語で作成し、変更後にレビューする | [品質運用](non-functional/document-quality.md) |

## 範囲と優先度

すべて既存のMVPまたは承認済み品質改善の要求から整理した必須条件である。ただし、必須であることと、すでに現行経路が満たしていることは別である。各要件では「現行の基準」と「品質改善の目標」を分ける。Agent経路と一括dailyの適用差も明記する。

実装の細かな優先順・日程は未確定。[バックログ](../../06-planning/backlog.md)に依存関係と着手前の確認事項を置く。今回の文書再編から追加の実装着手を推定しない。

## 追跡する情報

要件ID → 基本・詳細設計 → [検証対応表](../../04-verification/requirements-matrix.md) → [適用状況](../../06-planning/requirement-status.md) → 作業IDを追う。適用状況は06に一度だけ持つ。番号は旧章番号ではなく要件の識別子で、ファイルを移しても変更しない。
