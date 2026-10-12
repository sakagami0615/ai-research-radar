# 将来の拡張候補

旧設計書の該当節を分割した資料。現行と移行目標の区別は [文書全体の入口](../../README.md) から確認する。

## 拡張方針

### Source追加

Source追加はAdapterとconfigの追加で行う。Pipeline、Scoring、IdeationをSource固有にしない。

- 既存の取得処理で足りる場合は、`config/sources.yaml` にSourceを追加し、`adapter` に既存の取得処理の名前を書く(Source名は自由。例: キーワードを変えた2つ目のGitHub収集)。
- 新しい取得処理が必要な場合は、`sources/public.py` の `_SEARCH_SPECS`(検索・一覧APIの定義表)に追加するか、独自のAdapterクラスと `_ADAPTER_FACTORIES` への登録を追加する([Adapterの責任と共通契約](../../spec/03-detailed-design/source-adapters/interface.md)の「Adapterの選択」)。

Scoring・Ideation・Trend分析の改善案は [将来対応](future-works.md) を参照。
