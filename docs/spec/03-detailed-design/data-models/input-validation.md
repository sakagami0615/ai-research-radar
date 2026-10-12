# AgentのJSON入力検証

Agentが書くJSON（`selection_input.json` など）を受け取る処理の共通契約。各入力の許容値・必須項目は [HOT選抜入力](hot-selection.md)、[記事企画入力](article-proposals.md)、[共通品質](quality-records.md) の契約を参照する。

## 型確認と許容値の照合

文字列の値を許容値の集合と照合するときは、先に `isinstance(value, str)` を確認する。リストやdictをそのまま `value in {...}` へ渡すと `TypeError` になり、CLIが所定のエラー種別を記録できずトレースバックで終わるおそれがある。

実装例は [schemas/quality.py](../../../../src/ai_research_radar/schemas/quality.py) の `_is_one_of`：

```python
return isinstance(value, str) and value in allowed
```

型不正と許容値外は検証失敗として扱い、呼び出し元で [CLI契約](../cli/commands.md) に定めたエラーへ変換する。入力を暗黙に文字列化して許容しない。

## 変更時の確認

許容値、未知の文字列、リスト、dict、nullなどを区別して確認し、不正値が未処理の `TypeError` を起こさないことを検証する。手順は [テスト実行ガイド](../../../support/01-operations/testing/README.md) を参照する。
