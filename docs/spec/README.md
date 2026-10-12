# 仕様・設計

必要な結果を理解してから実現方式と確認方法へ進む。各フォルダのREADMEからテーマ別の正本を参照する。

1. [要求・要件](01-requirements/README.md)：背景、利用者、スコープ、機能・非機能要件、未決定事項。
2. [基本設計](02-architecture/README.md)：構成、責任分担、データフロー、障害境界。
3. [詳細設計](03-detailed-design/README.md)：データ、CLI、処理、Agentの契約。
4. [検証・受入](04-verification/README.md)：テスト方針、要件との対応、受入シナリオ。
5. [設計判断・変更設計](05-decisions/README.md)：採用理由、変更目標、判断履歴。

変更目標と現行動作は区別し、実装・受入の状態は [適用状況](../support/02-planning/requirement-status.md) で確認する。操作手順や作業計画は [support](../support/README.md) を参照する。テストの準備・実行手順は [テスト実行ガイド](../support/01-operations/testing/README.md) に置き、既存の受入記録は今回は移さない。
