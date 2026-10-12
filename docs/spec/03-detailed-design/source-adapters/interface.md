# Adapterの責任と共通契約

旧設計書の該当節を分割した資料。現行と移行目標の区別は [文書全体の入口](../../../README.md) から確認する。

## 目的

Source Adapterは、Source固有の取得、期間反映、raw保持、正規化を担当する境界である。PipelineはAdapter Interfaceだけを使い、SourceごとのAPI仕様やRSS形式を知らない。


## Interface

```python
class SourceAdapter:
    source_name: str
    source_family: str
    overlap_hours: int = 0  # sources.yamlのoverlap_hours。collection-periods.md参照

    def collect(self, since: str, until: str) -> list[RawItem]:
        ...

    def normalize(self, item: RawItem) -> CanonicalSignal:
        ...
```


## Adapterの選択

`config/sources.yaml` の各Sourceは、キー名がSource名(`source_name`。保存データの `source` や `signal_id` の接頭辞になる)、`adapter` が使う取得処理の名前である。`build_adapters`(`sources/public.py`)は `adapter` で取得処理を選ぶ。Source名と `adapter` は同じでなくてよく、同じ `adapter` を別名のSourceで複数使える(例: キーワードを変えた `github_mcp`(`adapter: github`))。

- 検索・一覧API型(`github` / `npm` / `hackernews` / `arxiv` / `openalex` / `huggingface` / `qiita` / `zenn`): `_SEARCH_SPECS` の表に、endpoint、クエリの組み立て、期間の指定方法、レスポンスからの要素の取り出し、RawItemへの変換、credibilityを1行ずつ定義する。
- 独自のAdapterクラスを使うもの(`pypi` / `official_blogs` / `huggingface_orgs` / `ollama` / `fixture`): `_ADAPTER_FACTORIES` に生成関数を登録する。
- どちらにもない `adapter` は、Source名と `adapter` を含むエラー(`ValueError`)にする。
- `enabled: false` または `auth_required: true` のSourceは作らない。
- OpenAlexの概要の復元など、取得処理に固有の補正は `adapter` の名前で判定する(`sources/remap.py`)。
- ただし、Source内スコア正規化のPyPI / npm向けの補正([現行スコア](../pipeline/scoring.md)の「Source単位スコア正規化」)はSource名(`pypi` / `npm`)で判定している。これらを別名のSourceで使うと補正されない。

## Source Family

Cross-source Confidenceのため、SourceをFamilyへ分類する。

- `technology`: GitHub、Hugging Face、Hugging Face org、Ollama、PyPI、npm
- `research`: arXiv、OpenAlex
- `community`: Hacker News
- `content`: Qiita、Zenn
- `official`: 公式ブログ
