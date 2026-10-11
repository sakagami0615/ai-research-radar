# 記事企画の二つの生成経路

旧設計書の該当節を分割した資料。現行と移行目標の区別は [文書全体の入口](../../README.md) から確認する。

## Article Ideation

記事企画の経路は2つある。

- Agent経路(`agent-daily-run`): Agentが選抜HOTごとに0〜3件の企画を作り、v2 の契約(各企画に `schema_version: 2` と `quality` を持たせる)で `save-proposals` に渡す。`save-proposals` は `validate_proposals` で型・必須値・選抜ID・Evidence対応を検証して保存する(データ契約「save-proposals の入力(v2)」)。比較対象などのために追加したURLは、`quality.evidence` の `claim` に役割を書くことで、HOTの主張を支えるURLと区別して許容する。
- 決定論経路(`ai-radar daily`): 以下の工程で v1 の企画(`quality` なし)を作る。v2 化は対象外であり、レポートでは旧形式と同じく「品質評価: 旧形式のため未評価」と表示する。

決定論経路はMVPのまま外部LLMを使わず、決定論的な工程で記事企画を生成する。

工程:

1. Role別候補生成
2. 類似タイトルのDedup / Cluster
3. Critique scoreとCritique notes付与
4. Advocate / Critic / Editorの1 round Debate代替
5. `max_proposals` 件へ統合

ArticleProposalのスキーマは変えず、以下に判断結果を残す。

- `why_now`
- `technical_angle`
- `unique_angle`
- `risks`

`why_now` の定型文(`HOT score ... with reasons: .... Role: .... 軽量Critique score: N/100; <notes>. Debate: <debate>`)は、日次レポートのレンダラーがRole / Critique / Debateの表示行に分解するために使う。文言を変える場合は `reporting/markdown.py` の分解パターンと、生成結果を分解するテスト(`tests/test_reporting.py`)を合わせて更新する。

Evidence URLがないHOT候補からは記事企画を生成しない。
