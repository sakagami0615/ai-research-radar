# 記事企画と入力契約

旧設計書の該当節を分割した資料。現行と移行目標の区別は [文書全体の入口](../../README.md) から確認する。

## ArticleProposal

共通の品質項目は [ProposalQuality・EvidenceCheck](quality-records.md) を参照する。保存CLIの検証順序・エラーは [CLI契約](../cli/commands.md) にある。

HOT候補から生成される記事企画案。

主な項目:

- `proposal_id`
- `source_hot_id`
- `title_idea`
- `article_type`
- `target_reader`
- `why_now`
- `technical_angle`
- `experiment_plan`
- `competition`
- `traffic_opportunity`
- `technical_opportunity`
- `unique_angle`
- `evidence_links`
- `risks`
- `schema_version`: v2 の企画は `2`。旧形式(Issue #11 より前の保存データと、決定論経路 `ai-radar daily` が作る企画)は `1`(キーがない旧データも `1` として読む)
- `quality`: v2 の企画の品質記録(`ProposalQuality`)。旧形式は空のdict

決定論経路(`ai-radar daily`)はMVPのまま外部LLMを使わず、決定論的なRole生成、Critique、Debate代替で v1 の企画を作成する。Agent経路(`agent-daily-run`)の企画は `save-proposals` で v2 として保存する。

### save-proposals の入力(v2)

```json
{"schema_version": 2, "proposals": [ /* v2 の ArticleProposal */ ], "deferral_reason": "選抜HOTがあるのに企画が0件の場合の理由"}
```

- トップレベルのキーは `schema_version` / `proposals` / `deferral_reason` だけ(それ以外のキーは `invalid_input`)。`schema_version` は整数の `2`、`proposals` はリスト。
- `deferral_reason` は、選抜HOT(`hot_candidates.jsonl` の `selected: true`)が1件以上あり、`proposals` が0件のときだけ必須(空白以外を含む文字列)。前後の空白を除いて `stage_results["save-proposals"].reason` に記録する。企画が1件以上ある日、または選抜HOTが0件の日にキーがあれば(値によらず)`invalid_input`。
- 選抜HOTが0件の日は `{"schema_version": 2, "proposals": []}` を渡す。
- v2 でない入力は失敗する。トップレベルが配列などオブジェクトでない場合と、トップレベルの `schema_version` が整数の `2` でない(キーがない場合を含む)場合は `invalid_input`、企画の `schema_version` が整数の `2` でない(キーがない場合を含む)場合は `invalid_proposal`。
- 判定の順序とエラーの種別(壊れた `hot_candidates.jsonl` の `corrupt_input` を含む)はCLI設計の `save-proposals` の表を参照。
- 各企画は `validate_proposals` で次を検証する(誤りは `invalid_proposal`、メッセージは `proposal[<番号>] ...`)。
  - 上記の14項目(`REQUIRED_FIELDS`)がそろうこと。`experiment_plan` / `risks` / `evidence_links` は文字列のリスト(空リスト可)、それ以外は空白以外を含む文字列。
  - `proposal_id` が入力内で重複しないこと。
  - `source_hot_id` が当日の HOT候補にあり、選抜済み(`selected: true`)であること。
  - `quality` が `ProposalQuality` の契約(`validate_proposal_quality`。`quality.evidence` の各要素は `EvidenceCheck`)を満たすこと。
  - `evidence_links` の各要素が http(s) のURL(ホスト部があること)で、元のHOT候補の `evidence_urls` を1件以上含むこと。
  - 元のHOT候補の `evidence_urls` にない `evidence_links`(比較対象などのために追加したURL)は、`quality.evidence` に同じURLのエントリがあり、その `claim` が空白以外を含むこと(`claim` に役割を書く。例: 「比較対象 X の仕様」)。
  - 1つのHOTあたり3件まで。
- 保存するのは14項目と `schema_version`(`2`)・`quality` だけで、それ以外のキーは保存しない。
- 保存済みの旧 `article_proposals.jsonl`(v1)は `decode_proposal` で引き続き読み込める(読み込み時は検証しない)。
