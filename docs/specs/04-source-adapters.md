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

可能なSourceでは、API queryに `since` / `until` を反映する。値は日付またはタイムゾーン付きISO 8601日時を取り得る。日付粒度しか指定できないAPIは、範囲を包含する日付で検索した後、取得済み日時を使って厳密にフィルタする。

API側で完全に期間指定できないSourceでも、取得後に `published_at` または `updated_at` を使って期間フィルタを行う。

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

## リトライ方針

一時的な障害(429 Too Many Requests、5xx系)のみ最大3回まで指数バックオフでリトライする(`Retry-After`ヘッダーがあれば尊重)。403/404/406などの恒久的なエラーは即座に失敗させ、無駄なリトライを行わない。

OpenAlexは環境変数 `AI_RADAR_OPENALEX_MAILTO` にcontact先メールアドレスを設定すると、リクエストに`mailto`パラメータを付与し、OpenAlex側のpolite pool(レート制限が緩いプール)を利用できる。個人のメールアドレスをリポジトリに埋め込まないための設計であり、未設定時は付与しない。

## 注意点

- Sourceの累積指標をそのままHOT scoreに使わない。
- GitHub stars、npm search score、PyPI keyword strengthなどはSource内で正規化する。
- RSS/Atom形式は提供側変更に弱いため、実運用では定期的なsmoke testを行う。
- Sourceが完全に収集失敗した場合(0件かつSource単位エラーあり)、日次レポートの「データ欠落」セクションに自動的に明示される。arxivの406はこのプロジェクトのネットワーク環境固有のCDN/IPレベルのブロックであり、ヘッダーやリトライでは解決しないことを確認済み。
