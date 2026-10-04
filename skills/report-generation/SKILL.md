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
- 「注目候補(選抜外)」「新モデルリリース」が選抜HOTの後にこの順で並び、該当なしの日も見出しと「該当なし」が出ているか
- 両セクションが直近3日分を集約し、前日以前のレポートに掲載済みの項目・選抜HOTになった項目を再掲していないか(`data/runs/<date>/report_digest.json`)
- 表示上限(注目候補10件、新モデルは提供元ごと10件)を超えた分が「ほかN件」として件数表示されているか
- Article Proposalの概要表・詳細表に表崩れがなく、Role / Critique / Debateが別行に分かれ、Evidence URLとRisksが欠落していないか
- 外部由来のタイトルなどに含まれる `[text](url)` や `#`・`|`・改行が、意図しないリンク・見出し・表崩れにならないか(新しい表示項目を足すときはエスケープ経由で出す)
- 未確認、保留、legacy、部分失敗、取得範囲とUTC/JSTを表示し、処理エラーなしを品質承認と解釈できる文面にしない。
