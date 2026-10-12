# 初期MVPの成功条件（出典）

元の設計判断・成功条件を保存した出典資料。現在の要件は [要件定義の入口](../01-requirements/README.md) で確認する。

## 成功条件

- `ai-radar daily` で日次Pipelineを実行できる。
- Source失敗があっても他Sourceの処理を継続し、Run Metadataにエラーを残せる。
- JSONLから、raw、signals、events、topics、hot candidates、article proposals、run metadataを確認できる。
- Markdownレポートに `選抜HOT`、記事企画、実行サマリ、エラーが出力される。
- HOT判定と記事企画に根拠URLが残る。
- すべての成果物作成後にレビューが実施され、Critical / Importantが残らない。
