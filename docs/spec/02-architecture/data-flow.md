# データの流れ

旧設計書の該当節を分割した資料。現行と移行目標の区別は [文書全体の入口](../../README.md) から確認する。

## 全体像

処理の流れは次のとおり。Agent経路と決定論経路は、収集からHOT候補の作成までを共通の処理で行い、選抜と記事企画の作り方だけが違う。

```text
Source
  |  Source Adapter(取得・RawItem化・CanonicalSignal化)
  v
RawItem JSONL / CanonicalSignal
  |  Source内スコア正規化 → Dedup → Event → Topic
  v
Event / Topic JSONL
  |  HOT Scoring(候補化)
  v
HOT候補
  |  選抜・記事企画(Agent経路: Agentが判断 / 決定論経路: スコア順と定型生成)
  v
選抜HOT・記事企画
  |  日次ダイジェスト(注目候補・新モデルリリース)の集約
  v
Markdownレポート + Run Metadata
```

経路ごとのサブコマンドの順序と担当は [実行経路と責任](workflows.md) を参照する。
