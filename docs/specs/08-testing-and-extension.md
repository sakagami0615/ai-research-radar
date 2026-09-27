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

### Scoring改善

初期実装は取得バッチ内のSource単位順位を使う。将来は以下を検討する。

- Platform x Category x Age Bucketの履歴Peer Group
- Source別の閾値config化
- 通知件数を見た自動調整
- 人間レビュー結果を使った重み調整

### Ideation改善

MVPでは決定論的なRole / Critique / Debate代替を使う。将来は以下を検討する。

- LLM Judge
- 複数Role生成の本格化
- 競合記事調査
- 記事化後の反応フィードバック

### Trend分析

Daily JSONLを蓄積し、週次・月次・年次分析に使う。

将来の分析観点:

- Topicの継続期間
- Source Familyの広がり
- HOT化頻度
- 研究から実装への遷移
- 公式発表とコミュニティ反応のタイムラグ

## 既知制約

- 公開APIやRSSは提供側変更に影響される。
- PyPI RSSは更新通知ベースであり、全Package検索ではない。
- Official Blogの重大発表判定はタイトル規則に依存する。
- Source内順位は取得バッチ単位であり、履歴ベースPeer Groupではない。
- 出力先自体が書き込めない場合、Run Metadataを保存できない。
