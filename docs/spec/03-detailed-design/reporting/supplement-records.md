# ダイジェスト・概要・傾向の保存契約

旧設計書の該当節を分割した資料。現行と移行目標の区別は [文書全体の入口](../../../README.md) から確認する。

## Source Overviews記録

`data/runs/<date>/source_overviews.json` は、収集Source一覧の各見出しに出す「本日の傾向」を記録する。Agent経路で実行Agentが書き、`ai-radar add-source-overview` で保存する(CLI設計)。決定論経路(`ai-radar daily`)では作成しない。

```json
{"github": "エージェント実行基盤とMCP関連のリポジトリが多い。...", "other": "..."}
```

- キーはレポートの見出しと同じSource名(`RunMetadata.sources` の値、または未登録Sourceをまとめた `other` / `_other`)。値は傾向の本文(2〜3行、おおむね200字以内の日本語。文字数はCLIでは検証しない)。
- 同じSourceを再度追加した場合は上書きし、それ以外は保持する。
- 読み込み時、空や文字列でない値は未作成として扱う。収集0件のSourceの値は表示しない(「収集0件」と出す)。
- `data/runs/<date>/source_overview_input.json` は、Agentが `add-source-overview --input` に渡すために書く入力ファイル(同じ形式)で、CLIは `--input` で指定されたときだけ読む。


## Report Digest記録

`data/runs/<date>/report_digest.json` は、その日のレポートの「注目候補(選抜外)」「新モデルリリース」に掲載した項目のキーを記録する。翌日以降のレポートで既掲載の項目を除外するために使う。

```json
{"notable": ["hot:event:..."], "model_releases": ["https://huggingface.co/org/model"]}
```

- `notable`: 掲載したHotCandidateの `hot_id`
- `model_releases`: 掲載したSignalの正規化済みURL(URLが空の場合は `signal_id`)

同じ日のレポートを再生成した場合は上書きする。除外判定には対象日より前の日付の記録だけを使う。


## Digest Summaries記録

`data/runs/<date>/digest_summaries.json` は、その日のレポートに表示する項目のうち、Agentが当日に補った概要を記録する。対象は、注目候補のうちHotCandidate自体に `summary` がないもの(過去日の候補や書き漏れ)と、新モデルリリースの全表示項目である。`ai-radar add-summary` が書き込む。

```json
{"hot:event:...": "注目候補の概要", "https://huggingface.co/org/model": "新モデルリリースの概要"}
```

- キーは、注目候補は `hot_id`、新モデルリリースは `ModelRelease.key`(正規化済みURL、URLが空なら `signal_id`)。`hot_id` は `hot:` で始まり、`key` はURLか `<source>:...` 形式なので衝突しない。値は概要の本文。同じキーを再度追加した場合は上書きする。
- 過去日の `hot_candidates.jsonl` は書き換えない(当日の run に「当日補った情報」として残す)。
- 注目候補の概要は、HotCandidateの `summary` を優先し、空の場合に対象日のこのファイルの値を使う。新モデルリリースの概要は、このファイルの値だけを使う。どちらもなければ「概要未作成」と表示する。
