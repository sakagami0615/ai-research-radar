# RawItemとCanonicalSignal

旧設計書の該当節を分割した資料。現行と移行目標の区別は [文書全体の入口](../../README.md) から確認する。

## RawItem

Sourceから取得した未加工データを保持する。

主な項目:

- `source`
- `fetched_at`
- `raw_id`
- `raw_url`
- `payload`

`payload` には、正規化用の派生フィールドに加えて、元レスポンスを `raw` として保持する。これにより、正規化やスコアリングを後から改善して再処理できる。


## CanonicalSignal

Source横断で扱うSignalの共通形式。

主な項目:

- `signal_id`
- `source`
- `source_family`
- `content_type`
- `title`
- `url`
- `published_at`
- `fetched_at`
- `summary`
- `categories`
- `raw_metrics`
- `normalized_scores`
- `metadata`

`normalized_scores` には0から100の正規化済みスコアを入れる。Source内順位補正はPipelineで収集バッチ単位に実施する。

新モデルリリースとして扱うSignalは `metadata.model_release` を持つ。値は `{"provider": <提供元表示名>, "channel": "official" | "huggingface" | "ollama"}` で、記事から紹介モデル名がわかる場合(Ollamaブログ)は `models`(モデル名のリスト)も持つ。Adapterが付与し、Dedupで別Sourceと統合された場合も保持する(Adapter設計参照)。
