# 04 検証・受入

要件を満たした証拠を確認する。テスト対象が列挙されていることやコードが存在することだけで受入済みとしない。

1. [テスト方針](test-strategy.md)
2. [要件と設計・検証の対応](requirements-matrix.md)
3. [受入シナリオ](acceptance/README.md)
4. [回帰テスト方針](regression-policy.md)
5. [品質改善の段階別受入](audit-remediation-acceptance.md)

環境準備・実行コマンド・Agent実機確認は [テスト実行ガイド](../../support/01-operations/testing/README.md) を参照する。対象・合格条件は本フォルダ、実行手順は同ガイドを正本とし、重複記載しない。

今回の再編ではアプリのテスト・日次収集を再実行していないため、既存テストへのリンクは確認候補であり現在の合格結果ではない。実行結果は [受入記録](acceptance/results.md) に環境・版・対象・証拠とともに記す。次は [設計判断・変更設計](../05-decisions/README.md)。実行・復旧の手順は [運用](../../support/01-operations/README.md) を参照する。
