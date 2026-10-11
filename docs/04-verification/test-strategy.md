# テスト方針と外部Sourceの確認

旧設計書の該当節を分割した資料。現行と移行目標の区別は [文書全体の入口](../README.md) から確認する。

## テスト方針

MVPでは、外部ネットワークに依存しないテストを中心にする。

主なテスト対象:

- SchemaのJSON化
- JSONL読み書き
- Source Adapter生成
- Fixture Adapter
- public Sourceのmapper、期間query、raw保持
- Source内スコア正規化
- Dedup
- Event / Topic生成
- HOT判定
- Article Ideation
- Markdown Reporting
- Daily Pipeline
- CLI


## 外部Sourceテスト

公開APIやRSSは変更される可能性があるため、通常の自動テストではネットワーク呼び出しを避ける。

代わりに以下を使う。

- fixture JSONL
- mapper単体テスト
- query生成テスト
- XML/JSONのサンプル応答テスト

実運用では、ネットワーク可能な環境で定期的なsmoke testを行う。
