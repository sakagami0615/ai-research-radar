# 公開Sourceと新モデル検知

旧設計書の該当節を分割した資料。現行と移行目標の区別は [文書全体の入口](../../README.md) から確認する。

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
- Hugging Face org別モデル一覧(`huggingface_orgs`)
- Ollama Blog RSS(`ollama`、モデル紹介判定のため記事本文HTMLも取得する)

PyPIは全Package検索ではなく、更新RSSをAI関連keywordで絞る。npmは検索scoreを利用する。Official BlogsはGitHub検索ではなくRSS/Atomとして扱う。


## 新モデルリリース検知Source

日次レポートの「新モデルリリース」セクション用に、次の3 Sourceでモデルの新規公開を検知する。いずれも通常のSignalとしてHOTスコアリングにも流す。検知したSignalには `metadata.model_release`(`provider` / `channel`)を付与する。

### Official Blogs(`official_blogs`)

`feeds` に提供元ごとのRSS/Atomを複数登録できる。各要素は `provider`(表示名)、`url`、`model_keywords`(モデル系列名)、任意の `model_categories`(新モデル判定に使うcategoryの許可リスト)を持つ。旧形式の単一 `feed_url` も引き続き受け付け、その場合の `provider` は `OpenAI` とする。

- 1つのfeedの取得に失敗しても他のfeedは継続する。失敗したfeedは `partial_feed_error`、`url` のない設定エントリは `config_error` としてerrorsに記録する。全feedが失敗した場合のみSource全体の失敗とする。
- Accept-Encodingを送っていなくてもgzip圧縮で返すfeedがある(DeepMindで確認)。このため、レスポンス本文がgzipのマジックバイト(`1f 8b`)で始まる場合は展開してから解析する(ヘッダーは見ない)。
- 次のいずれかを満たすエントリに `metadata.model_release`(`channel=official`)を付与し、「新モデルリリース」の対象にする。
  - タイトルに、そのfeedの `model_keywords` のいずれかが単語として含まれる。大文字小文字は区別しない。語頭は常に単語境界で判定し、語末はkeywordが英数字で終わる場合のみ単語境界で判定する(`gpt-` は "GPT-6" に一致し、`veo` は "Coveo" に一致しない)。
    - ただし `model_categories` を設定したfeedでは、keyword一致はエントリのcategory(RSSの `category` 要素のテキスト、Atomの `category` 要素の `term` 属性)のいずれかが `model_categories` に一致する場合に限る。比較は前後空白を除き大文字小文字を区別しない。categoryのないエントリは対象外とする。空リストやリスト以外の値は未設定として扱う。OpenAIは顧客事例(`Startup` / `Company` / categoryなし)がモデル名をタイトルに含むため、`[Product, Research, Release]` を設定している。許可外categoryのモデル発表(例: `Company` の「Introducing GPT-5.4 mini and nano」)は検知されず、許可category内の発表以外の記事(例: 「Better prompt caching for GPT-6」)は検知される。
    - category は official_blogs 専用の経路で読み取る。汎用RSS・Ollamaの `payload.raw` は変えない。
  - タイトルにrelease/launch系の語と "model" を含む(従来規則。この場合は `event_type=major_model_release` にもなる)。
- `model_keywords` への一致は `event_type` を変えない。HOTのOfficial Override(Pipeline設計)は従来のタイトル規則だけで決まり、keyword追加によって候補化の母集団が広がらないようにする。
- 提供元名そのもの(例: "Mistral")はkeywordにしない。提携や拠点開設の記事まで誤検知するためである。
- Meta、Anthropic、xAIは公式RSSを提供していないため登録しない(2026-10時点で確認)。Metaのオープンウェイトは `huggingface_orgs`(`meta-llama` / `meta-models`。2026年のモデルは `meta-models`)で拾う。
- Qwenのブログ(`qwenlm.github.io`)は `qwen.ai/research` へ移転し、RSSがないため登録しない(2026-10時点で確認。旧feedは2025-09で更新停止)。Qwenのモデルは `huggingface_orgs` の `Qwen` で拾う。

### Hugging Face org(`huggingface_orgs`)

`orgs` に「HF org名: 提供元表示名」を登録する。org単位で `https://huggingface.co/api/models?author=<org>&sort=createdAt&direction=-1&limit=<per_org_limit>` を取得し、`createdAt` が期間内のモデルだけを新規リリースとして残す(`lastModified` は使わない)。

- 既存の `huggingface` Source(keyword検索・更新順)とは別Sourceである。同じURLのモデルがDedupで統合されても、`metadata.model_release` は保持する。
- org単位の失敗は `partial_feed_error` として記録して継続し、全org失敗時のみSource全体の失敗とする。
- family は `technology`、`event_type` は `observed_signal` とする。量子化版などの派生リポジトリが大量に出るため、Official Overrideの対象にはしない。

### Ollama(`ollama`)

Ollamaブログの公式RSS `https://ollama.com/blog/rss.xml` を取得し、期間内の記事をSignalにする。RSSにはタイトルと短い説明文しかないため、期間内の記事についてだけ記事ページのHTMLを取得し、モデル紹介記事かどうかを判定する。

- ライブラリ一覧(`ollama.com/library?sort=newest`)は使わない。作成日が公開されておらず、古いモデルが更新されただけで新着扱いになる誤検知を防げないためである(2026-10の実データで確認)。
- 記事本文から `ollama.com/library/<model>`(相対リンク `/library/<model>` を含む)と `ollama run <model>` のモデル名を抽出し、タグ(`:30b` など)は除く。
- 次の規則で紹介モデルを決め、1件以上あれば `metadata.model_release`(`provider=Ollama`、`channel=ollama`、`models=[...]`)を付与する。機能紹介やチュートリアル記事も例示としてlibraryへのリンクや `ollama run` を含むため、言及だけでは採用しない。
  1. 名前(英数字のみに正規化)が記事タイトルまたはURLに含まれるモデルを採用する(例: "MiniMax M2" と `minimax-m2`)。
  2. 1で該当がなく、タイトルに複数形の "models" を含む場合は、libraryへリンクしているモデルを採用する(例: "New coding models & integrations")。
  3. それ以外はモデル紹介記事とみなさない(例: "New model scheduling"、OpenClawのチュートリアル)。
- 記事ページの取得に失敗した場合は、その記事をモデル判定なしのSignalとして残し、`partial_feed_error` を記録する。RSS自体の取得失敗はSource全体の失敗とする。
- 2025-08〜2026-10の全記事で判定を確認した。モデル紹介記事10件をすべて検出し、誤検知はなかった。
- ブログ記事がない小規模なライブラリ追加は拾えない(主要モデルの紹介記事に絞る方針)。
