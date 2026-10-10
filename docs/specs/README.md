# AI Research Radar 設計書インデックス

このディレクトリは、AI Research Radar を開発・保守するための一般設計書を分割して配置する。

## ドキュメント構成

- [01-concept.md](01-concept.md): プロジェクトの目的、MVP範囲、成功条件
- [02-architecture.md](02-architecture.md): 全体アーキテクチャ、主要コンポーネント、依存方向
- [03-data-model-and-storage.md](03-data-model-and-storage.md): データモデル、JSONL/Markdown保存方針、日次レポートの構成
- [04-source-adapters.md](04-source-adapters.md): Source Adapter、公開Source、Fixture、期間取得、raw保持
- [05-pipeline-scoring-ideation.md](05-pipeline-scoring-ideation.md): 日次Pipeline、正規化、HOT判定、記事企画生成
- [06-cli-and-operations.md](06-cli-and-operations.md): CLI、cron想定、設定ファイル、運用上の注意
- [07-skills-and-agent-workflow.md](07-skills-and-agent-workflow.md): Claude Code / Codex共通Skills、レビュー運用、改善ループ
- [08-testing-and-extension.md](08-testing-and-extension.md): テスト方針、既知制約、Source・Scoring追加時の拡張方針

このディレクトリの設計書は現在の実装を説明する(実装と乖離させない)。未実装の構想・将来対応は [docs/future-works.md](../future-works.md) に書く。

## 設計原則

- Source固有処理はAdapterへ閉じ込める。
- PipelineはSource固有レスポンスを直接扱わず、RawItemとCanonicalなデータモデルを扱う。
- 保存は人間が確認しやすいJSONLとMarkdownを基本にする。
- 外部認証なしで動くMVPを優先する。
- HOT判定と記事企画は、根拠URLとレビュー可能な理由を必ず残す。
- Claude Code / Codexのどちらでも同じWorkflowを参照できるようにする。
