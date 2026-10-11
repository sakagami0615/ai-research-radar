# 依存方向

旧設計書の該当節を分割した資料。現行と移行目標の区別は [文書全体の入口](../README.md) から確認する。

## 依存方向

```text
cli
  -> config / periods / sources / normalization / pipeline / scoring / ideation / reporting / storage / schemas

pipeline
  -> sources / normalization / scoring / ideation / reporting / storage / periods / schemas

sources
  -> config / normalization / periods / storage / schemas

reporting
  -> normalization / storage / schemas

normalization
  -> periods / schemas

config
  -> periods

scoring / ideation / storage
  -> schemas
```

- PipelineとCLIはSource Adapterのインターフェースにだけ依存し、Source固有のレスポンス形式はAdapterに閉じ込める。どのAdapterを使うかは `config/sources.yaml` の `adapter` で決まる([Adapterの選択](../03-detailed-design/source-adapters/interface.md))。
- Scoring・Ideation・ReportingはSource固有の実装を知らない。
- CLIのサブコマンドは前の段階の出力ファイルを入力にし、互いのモジュールを直接呼ばない。
