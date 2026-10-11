# N-03 根拠・判断・実行の追跡性

選抜・企画の根拠URLと判断理由、実行日時・取得期間・Source・件数・エラーを保存し、人間が判断の出典へ戻れること。

## 受入条件

- 選抜と企画を対象IDと根拠へ対応させられる。
- Agentによる根拠確認日時を実測取得ログと照合でき、未確認を確認済みと扱わない。
- 品質改善目標として、コード版・設定・生成経路・試行別成果物・レビュー対象を対応させる。
- 機密管理の条件はN-05に従う。

[実行データ契約](../../../03-detailed-design/data-models/run-metadata.md)、[取得ログと評価の変更設計](../../../07-decisions/audit-remediation/relevance-and-evidence.md)、[試行履歴の変更設計](../../../07-decisions/audit-remediation/execution-and-reporting.md)を参照。
