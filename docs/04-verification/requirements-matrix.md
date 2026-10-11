# 要件と設計・検証の対応

受入条件は [要件一覧](../01-requirements/02-definition/requirement-catalog.md) のリンク先を正本とする。ここでは設計と確認方法への入口を対応づける。既存テストは検証候補であり、リンクの存在は今回の合格証拠ではない。

| 要件 | 主な設計 | 確認候補・受入シナリオ |
| --- | --- | --- |
| F-01 | [Adapter](../03-detailed-design/source-adapters/README.md) | [収集受入](acceptance/collection.md)、[収集CLIテスト](../../tests/test_cli_collect.py)、[公開Sourceテスト](../../tests/test_public_sources.py) |
| F-02 | [データ](../03-detailed-design/data-models/README.md)、[集約](../03-detailed-design/pipeline/grouping.md) | [集約受入](acceptance/normalization.md)、[重複排除](../../tests/test_dedup.py) |
| F-03 | [選抜入力](../03-detailed-design/data-models/hot-selection.md) | [選抜受入](acceptance/selection-and-proposals.md)、[評価検証](../../tests/test_assessments.py)、[選抜CLI](../../tests/test_cli_select_hot.py) |
| F-04 | [企画入力](../03-detailed-design/data-models/article-proposals.md) | [企画受入](acceptance/selection-and-proposals.md)、[企画検証](../../tests/test_ideation_validation.py)、[保存CLI](../../tests/test_cli_save_proposals.py) |
| F-05 | [表示と集約](../03-detailed-design/reporting/README.md) | [表示受入](acceptance/reporting-and-review.md)、[Markdown](../../tests/test_reporting.py)、[digest](../../tests/test_digest.py) |
| F-06 | [レビュー運用](../05-operations/review-and-improvement.md) | [レビュー受入](acceptance/reporting-and-review.md)、[要確認の記録](../../tests/test_cli_common.py)、Agent実機 |
| N-01 | [障害境界](../02-architecture/failure-boundaries.md) | [収集受入](acceptance/collection.md)、[Pipeline](../../tests/test_daily_pipeline.py) |
| N-02 | [実行状態](../03-detailed-design/data-models/run-metadata.md) | [復旧受入](acceptance/operations-and-compatibility.md)、[状態](../../tests/test_run_state.py) |
| N-03 | [実行記録変更](../07-decisions/audit-remediation/execution-and-reporting.md) | [追跡受入](acceptance/operations-and-compatibility.md)、取得ログ照合、設定・コード・hash確認 |
| N-04 | [保存版](../03-detailed-design/data-models/versioning.md)、[共通Skill](../03-detailed-design/agent-workflows/README.md) | [互換受入](acceptance/operations-and-compatibility.md)、[スキーマ](../../tests/test_quality_schemas.py)、両Agentの実機 |
| N-05 | [機密管理の目標](../07-decisions/audit-remediation/execution-and-reporting.md) | [機密受入](acceptance/operations-and-compatibility.md)、記録ファイルの検査 |
| N-06 | [定期実行](../05-operations/scheduled-run.md) | [運用受入](acceptance/operations-and-compatibility.md)、[CLI](../../tests/test_cli.py)、cron環境の確認 |
| N-07 | [文書品質](../01-requirements/02-definition/non-functional/document-quality.md) | 独立レビュー、リンク・参照・仕様同期、変更したAgent手順の実機 |

各要件の適用範囲と未実装箇所は [適用状況](../06-planning/requirement-status.md) で確認する。モジュールの単体テストだけで本番経路(CLI)の受入を完了しない。
