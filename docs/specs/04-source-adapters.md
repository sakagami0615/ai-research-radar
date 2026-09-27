# 04. Source Adapter設計

## 目的

Source Adapterは、Source固有の取得、期間反映、raw保持、正規化を担当する境界である。PipelineはAdapter Interfaceだけを使い、SourceごとのAPI仕様やRSS形式を知らない。

## Interface

```python
class SourceAdapter:
    source_name: str
    source_family: str

    def collect(self, since: str, until: str) -> list[RawItem]:
        ...

    def normalize(self, item: RawItem) -> CanonicalSignal:
        ...
```

## Source Family

Cross-source Confidenceのため、SourceをFamilyへ分類する。

- `technology`: GitHub、Hugging Face、PyPI、npm
- `research`: arXiv、OpenAlex
- `community`: Hacker News
- `content`: Qiita、Zenn
- `official`: 公式ブログ

## 公開Source

MVPでは認証なしで取得可能なSourceを対象にする。

- GitHub Search API
- Hugging Face public API
- PyPI RSS updates
- npm public search
- Hacker News Algolia API
- Qiita public API
- Zenn articles API
- arXiv Atom API
- OpenAlex works API
- Official Blogs RSS/Atom

PyPIは全Package検索ではなく、更新RSSをAI関連keywordで絞る。npmは検索scoreを利用する。Official BlogsはGitHub検索ではなくRSS/Atomとして扱う。

現行設定のOfficial BlogsはOpenAIのRSS 1件である。複数の公式ブログを横断する場合は、`config/sources.yaml` の設定拡張またはSource追加が必要になる。

## 期間反映

可能なSourceでは、API queryに `since` / `until` を反映する。

API側で完全に期間指定できないSourceでも、取得後に `published_at` または `updated_at` を使って期間フィルタを行う。

## raw保持

`RawItem.payload` には以下を入れる。

- 正規化で使う派生値
- `metrics`
- `metadata`
- `raw`: 元レスポンスのdict、またはRSS/Atom entry相当のdict

rawを保持する理由は、後から正規化ルールやスコア計算を改善して再処理できるようにするためである。

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

## 注意点

- Sourceの累積指標をそのままHOT scoreに使わない。
- GitHub stars、npm search score、PyPI keyword strengthなどはSource内で正規化する。
- RSS/Atom形式は提供側変更に弱いため、実運用では定期的なsmoke testを行う。
