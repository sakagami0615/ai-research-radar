# 08. テスト・拡張設計

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

## 回帰テスト方針

レビューで見つかった問題は、同じ指摘を再発させないように回帰テストを追加する。

例:

- PyPI/npmの強い新着信号が既定閾値を超える。
- 弱いkeyword matchや古いitemは昇格しない。
- query付きURLをdedupで壊さない。
- Source失敗時にRun Metadataへエラーが残る。
- `ai-radar daily` が期間引数なしで動く。

## 拡張方針

### Source追加

Source追加はAdapterとconfigの追加で行う。Pipeline、Scoring、IdeationをSource固有にしない。

- 既存の取得処理で足りる場合は、`config/sources.yaml` にSourceを追加し、`adapter` に既存の取得処理の名前を書く(Source名は自由。例: キーワードを変えた2つ目のGitHub収集)。
- 新しい取得処理が必要な場合は、`sources/public.py` の `_SEARCH_SPECS`(検索・一覧APIの定義表)に追加するか、独自のAdapterクラスと `_ADAPTER_FACTORIES` への登録を追加する(04章)。

Scoring・Ideation・Trend分析の改善案は [docs/future-works.md](../future-works.md) を参照。

## 既知制約

- 公開APIやRSSは提供側変更に影響される。
- PyPI RSSは更新通知ベースであり、全Package検索ではない。
- Official Blogの重大発表判定はタイトル規則(`model_keywords` を含む)に依存する。
- Ollama Sourceのモデル紹介判定は記事本文のリンク・`ollama run` 記法とタイトル規則に依存する。記事の書き方が変わると、モデル紹介記事を通常記事として扱う(取りこぼす)ことがある。また名前はタイトル/URLへの部分一致で判定するため、基底モデル名(例: "Qwen3.5" の記事内の `qwen3`)が紹介モデルに混ざることがある。
- 新モデルリリースは名前揺れを統合しないため、同じモデルが公式・HF・Ollamaに別項目で出ることがある。
- `unsloth` / `lmstudio-community` などのHF orgは量子化版などの派生リポジトリを大量に作るため、新モデルリリース(提供元ごと上限10件)やHOT母集団のノイズになりうる。運用状況を見て監視対象を見直す。
- 公式feedの `model_keywords` はタイトル一致のため、モデル名に言及した事例紹介記事なども「新モデルリリース」に出ることがある。OpenAIは `model_categories` で顧客事例を除いているが、許可category内の発表以外の記事(例: 「Better prompt caching for GPT-6」)は残り、許可外category(`Company`)のモデル発表は取りこぼす。categoryを持たないfeed(Google / Mistral)には適用できない。
- PyPIのバージョン更新がHOTスコア75以上になりやすく、「注目候補(選抜外)」がパッケージ更新で埋まることがある(スコア計算側の課題として未対応。AI関連度の部分一致の不具合は [Issue #32](https://github.com/sakagami0615/ai-research-radar/issues/32))。
- Source内順位は取得バッチ単位であり、履歴ベースPeer Groupではない。
- 出力先自体が書き込めない場合、Run Metadataを保存できない。
