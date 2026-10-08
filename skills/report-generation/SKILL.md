---
name: report-generation
description: Use when 構造化データから日次・将来の各種レポートを生成するとき。
---

# Report Generation

## 目的

JSONLの判断済みデータを人間が確認しやすいレポートへ変換する。

## MVP出力

- Daily Markdown Report

## 将来出力

- Weekly HTML
- Monthly HTML
- Static PNG

## レビュー観点

- Visualization側で技術判断をしていないか
- 根拠Sourceへのリンクが残っているか
- 人間が短時間で確認できる量に絞られているか
- 収集Source一覧のSource見出し順序・0件表示・リンクが崩れていないか
- 収集Source一覧の各Source見出しの直下(`<details>` の外)に、Sourceごとの「本日の傾向」が1行で出ているか。傾向がないSourceは「傾向未作成」、収集0件のSourceは「収集0件」になっているか(傾向は `data/runs/<date>/source_overviews.json`)。傾向の改行が `<br>` になり、`|`・`<>`・行頭の `#` などで表示が崩れていないか、120文字で切り詰められていないか
- 「注目候補(選抜外)」「新モデルリリース」が選抜HOTの後にこの順で並び、該当なしの日も見出しと「該当なし」が出ているか
- 両セクションが直近3日分を集約し、前日以前のレポートに掲載済みの項目・選抜HOTになった項目を再掲していないか(`data/runs/<date>/report_digest.json`)
- 表示上限(注目候補10件、新モデルは提供元ごと10件)を超えた分が「ほかN件」として件数表示されているか
- 選抜HOT・注目候補の各項目の見出し直後に `> **概要**: ...` が1行で出ているか、概要がない項目は「概要未作成」になっているか(注目候補はHotCandidateの `summary`、なければ `data/runs/<date>/digest_summaries.json`)
- 新モデルリリースの各項目の次の行に `  - 概要: ...` が字下げされて1行で出ているか、概要がない項目は「概要未作成」になっているか、「ほかN件」の行には概要が付いていないか(概要は `data/runs/<date>/digest_summaries.json` の、`ModelRelease.key`(正規化済みURL、URLが空なら `signal_id`)をキーとする値)
- 選抜HOTのReasonsの後に、評価ブロック(判断理由 / 関連性 / 新規性 / 重要性 / 読者への影響 / 根拠 / 未確認事項)が出ているか
- 評価ブロックに評価者(`assessor`)・評価日時(`assessed_at`)が出ていないか
- `assessment` のない旧データの選抜HOTでは、評価ブロックが出ずReasonsだけになっているか
- Article Proposalの概要表・詳細表に表崩れがなく、Role / Critique / Debateが別行に分かれ、Evidence URLとRisksが欠落していないか
- 外部由来のタイトルなどに含まれる `[text](url)` や `#`・`|`・改行が、意図しないリンク・見出し・表崩れにならないか(新しい表示項目を足すときはエスケープ経由で出す)
- 選抜HOTセクションの冒頭とRun SummaryのSelection / Proposals行が `run_state.json` の `stage_results` と一致し、保留(deferred)・未実行(not_run)・失敗(failed)・記録なし(旧データ)が区別して表示されているか
- 未確認、保留、legacy、部分失敗、取得範囲とUTC/JSTを表示し、処理エラーなしを品質承認と解釈できる文面にしない。
