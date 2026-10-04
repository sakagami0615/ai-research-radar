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
- Article Proposalの概要表・詳細表に表崩れがなく、Role / Critique / Debateが別行に分かれ、Evidence URLとRisksが欠落していないか
- 未確認、保留、legacy、部分失敗、取得範囲とUTC/JSTを表示し、処理エラーなしを品質承認と解釈できる文面にしない。
