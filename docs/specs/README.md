# AI Research Radar 設計書インデックス

このディレクトリは、AI Research Radar を開発・保守するための一般設計書を分割して配置する。

## ドキュメント構成

- [01-concept.md](01-concept.md): プロジェクトの目的、MVP範囲、成功条件
- [02-architecture.md](02-architecture.md): 全体アーキテクチャ、主要コンポーネント、依存方向
- [03-data-model-and-storage.md](03-data-model-and-storage.md): データモデル、JSONL/Markdown保存方針、将来のSQLite検討
- [04-source-adapters.md](04-source-adapters.md): Source Adapter、公開Source、Fixture、期間取得、raw保持
- [05-pipeline-scoring-ideation.md](05-pipeline-scoring-ideation.md): 日次Pipeline、正規化、HOT判定、記事企画生成
- [06-cli-and-operations.md](06-cli-and-operations.md): CLI、cron想定、設定ファイル、運用上の注意
- [07-skills-and-agent-workflow.md](07-skills-and-agent-workflow.md): Claude Code / Codex共通Skills、レビュー運用、改善ループ
- [08-testing-and-extension.md](08-testing-and-extension.md): テスト方針、既知制約、拡張方針
- [09-audit-remediation-design.md](09-audit-remediation-design.md): 日次監査に基づく品質改善設計（実装計画作成承認済み・未実装）

対応する[実装計画](../superpowers/plans/2026-10-01-audit-remediation.md)は、ユーザーによるモデル切り替え後に実行する。`docs/superpowers/` はGit管理対象外のため、別worktreeへの引き継ぎ時は計画ファイルもコピーする。

## 設計原則

- Source固有処理はAdapterへ閉じ込める。
- PipelineはSource固有レスポンスを直接扱わず、RawItemとCanonicalなデータモデルを扱う。
- 保存は人間が確認しやすいJSONLとMarkdownを基本にする。
- 外部認証なしで動くMVPを優先する。
- HOT判定と記事企画は、根拠URLとレビュー可能な理由を必ず残す。
- Claude Code / Codexのどちらでも同じWorkflowを参照できるようにする。
