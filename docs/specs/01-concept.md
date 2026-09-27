# 01. コンセプト設計

## 目的

AI Research Radar は、AI関連の研究、ツール、モデル、ライブラリ、開発者コミュニティ、公式発表を継続的に収集し、技術記事のネタ候補やAIトレンド把握に使う調査基盤である。

記事本文を自動執筆することは目的ではない。目的は、記事化する価値がありそうなTopicを見つけ、根拠URLと判断理由を残し、人間が短時間で確認できる日次レポートへまとめることである。

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

これらは将来拡張として扱う。MVPのデータ保存とTopic履歴は、将来の週次・月次分析に再利用できる形にする。

## 成功条件

- `ai-radar daily` で日次Pipelineを実行できる。
- Source失敗があっても他Sourceの処理を継続し、Run Metadataにエラーを残せる。
- JSONLから、raw、signals、events、topics、hot candidates、article proposals、run metadataを確認できる。
- Markdownレポートに `選抜HOT`、記事企画、実行サマリ、エラーが出力される。
- HOT判定と記事企画に根拠URLが残る。
- すべての成果物作成後にレビューが実施され、Critical / Importantが残らない。

## 判断方針

AI Research Radar は「大量通知」ではなく「確認する価値が高い少数候補」を出す。通常日は0から数件、多い日でも5件程度の選抜HOTを想定する。

また、外部LLMや認証必須APIに依存しないMVPとするため、初期のJudge / Critique / Debateは決定論的なローカル処理で代替する。将来、認証やコストの方針が固まった時点でLLM Judgeへ差し替える。
