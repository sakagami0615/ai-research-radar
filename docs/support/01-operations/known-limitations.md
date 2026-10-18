# 現行設計に記載された既知制約

旧設計書の該当節を分割した資料。現行と移行目標の区別は [文書全体の入口](../../README.md) から確認する。

## 既知制約

- 公開APIやRSSは提供側変更に影響される。
- PyPI RSSは更新通知ベースであり、全Package検索ではない。
- Official Blogの重大発表判定(HOTのOfficial override)はタイトル規則と `model_keywords` / `model_categories` に依存する。新モデルリリースに当たる記事はスコアに関係なくHOT候補になるため、モデル名を含む発表以外の記事(例: 「A model guide for the GPT-6 family」)もHOT候補になる(Agentの評価で選抜外にする)。逆に `model_keywords` の語頭境界に当たらない発表(例: 「EmbeddingGemma 2: …」は `gemma` に一致しない)は、新モデルリリースにもOfficial overrideの対象にもならない。
- Ollama Sourceのモデル紹介判定は記事本文のリンク・`ollama run` 記法とタイトル規則に依存する。記事の書き方が変わると、モデル紹介記事を通常記事として扱う(取りこぼす)ことがある。また名前はタイトル/URLへの部分一致で判定するため、基底モデル名(例: "Qwen3.5" の記事内の `qwen3`)が紹介モデルに混ざることがある。
- 新モデルリリースは名前揺れを統合しないため、同じモデルが公式・HF・Ollamaに別項目で出ることがある。
- `unsloth` / `lmstudio-community` などのHF orgは量子化版などの派生リポジトリを大量に作るため、新モデルリリース(提供元ごと上限10件)やHOT母集団のノイズになりうる。運用状況を見て監視対象を見直す。
- 公式feedの `model_keywords` はタイトル一致のため、モデル名に言及した事例紹介記事なども「新モデルリリース」とHOT候補(Official override)に出ることがある。OpenAIは `model_categories` で顧客事例を除いているが、許可category内の発表以外の記事(例: 「A model guide for the GPT-6 family」)は残り、許可外category(`Company`)のモデル発表は取りこぼす(タイトル規則で `major_model_release` / `major_api_release` になるものを除き、Official overrideの対象にもならない)。categoryを持たないfeed(Google / Mistral)には適用できない。
- PyPIのバージョン更新がHOTスコア75以上になりやすく、「注目候補(選抜外)」がパッケージ更新で埋まることがある(スコア計算側の課題として未対応)。
- Source内順位は取得バッチ単位であり、履歴ベースPeer Groupではない。
- 出力先自体が書き込めない場合、Run Metadataを保存できない。
