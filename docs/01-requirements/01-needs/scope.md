# 対象範囲と対象外

初期MVPの対象範囲を引き継ぐ。以下の処理名には当初の方式も含まれるため、必要な結果は [要件一覧](../02-definition/requirement-catalog.md)、現行の方式は [基本設計](../../02-architecture/README.md) を参照する。

## MVPの範囲

MVPでは、日次実行を対象にする。

- 認証なしで取得可能な公開Sourceから情報を収集する。
- Source固有データを共通のCanonical Signalへ正規化する。
- 重複を排除し、EventとTopicへ集約する。
- Popularity、Momentum、Credibility、Cross-source ConfidenceでHOT候補を判定する。
- 選抜HOTから記事企画候補を生成する。
- 構造化データをJSONL、日次レポートをMarkdownとして保存する。
- CLIから手動実行でき、cronからも呼び出せる入口を持つ。
- Claude Code / Codexで共通利用できるSkill定義を持つ。


## MVPで扱わないこと

- 記事本文の自動執筆
- 認証必須APIを前提にしたSource連携
- 投稿・配信の完全自動化
- 本格的なWeb UI
- Vector DB / Graph DBの導入
- 週次・月次・年次分析の本格実装

このうち将来検討するものは [将来対応](../../06-planning/future-works.md) にまとめる。MVPのデータ保存とTopic履歴は、週次・月次分析に再利用できる形にする。
