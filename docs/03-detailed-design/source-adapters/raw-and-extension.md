# raw保持・Fixture・Source追加

旧設計書の該当節を分割した資料。現行と移行目標の区別は [文書全体の入口](../../README.md) から確認する。

## raw保持

`RawItem.payload` には以下を入れる。

- 正規化で使う派生値
- `metrics`
- `metadata`
- `raw`: 元レスポンスのdict、またはRSS/Atom entry相当のdict

rawを保持する理由は、後から正規化ルールやスコア計算を改善して再処理できるようにするためである。

関連性は取得条件（キーワードによる候補化）と内容評価を分離する。ASCIIの短い語は英数字境界で判定し、曖昧語・概要欠損・一致なしを自動的に`unrelated`とはしない。OpenAlexの`abstract_inverted_index`は位置を復元して概要化し、復元不能時は既存概要を保持したうえで診断を残す。再マップは`raw_id`、Source、取得日時、元rawを変更しない。


## Fixture Adapter

Fixture Adapterはテストとローカル検証用である。外部ネットワークに依存しないテストではFixtureを使う。

Fixtureは `tests/fixtures/` 配下のJSONLを読み、RawItemを返す。


## 追加Sourceの実装手順

1. `config/sources.yaml` にSource設定を追加する。
2. Source Familyを決める。
3. 認証不要か、利用規約・Rate Limitを確認する。
4. `public.py` または専用Adapterにendpoint、item selector、mapper、period paramsを追加する。
5. raw保持とpublished_at変換のテストを追加する。
6. networkなしで動くfixture/モックテストを追加する。
