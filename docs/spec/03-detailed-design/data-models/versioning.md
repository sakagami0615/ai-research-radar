# 保存データの版と移行契約

旧設計書の該当節を分割した資料。現行と移行目標の区別は [文書全体の入口](../../../README.md) から確認する。

## スキーマ版と読み込み

以下はv2の契約を含む。v2の入力検証と、収集・正規化・identity全体の本番接続は別であり、すべての新規レコードが現行CLIからv2で作られることを意味しない。[適用状況](../../../support/02-planning/requirement-status.md)を確認する。

- 各レコードは `schema_version` を持つ(`1` または `2`。キーがない旧データは `1` として読む)。それ以外の値は読み込みエラーにする。`2` を書くのは、Agent経路で検証済みの記事企画(`ArticleProposal`)だけである。
- 保存済みのJSONLは `schemas/decoders.py` の `decode_signal` / `decode_event` / `decode_hot` / `decode_proposal` で読む。必須キーの欠落や型の誤りは読み込みエラーになり、CLIは `corrupt_input` として記録する([CLIコマンド](../cli/commands.md))。
- 旧データにない項目(`quality`、`assessment`、`summary` など)は、推測で補わず既定値(空のdict、`null`、空文字列)として読む。
- Agentが書く入力(`selection_input.json`、`save-proposals` の入力)は `schemas/quality.py` で型・状態・必須文字列を検証し、誤りは `QualityValidationError` になる。
- 日時はタイムゾーン付きISO 8601で保存し、JSONの `null` は未取得を表す。
