# 共通の根拠・企画品質契約

EvidenceCheckとProposalQualityの正本。選抜は [HOT選抜入力](hot-selection.md)、企画は [記事企画入力](article-proposals.md) から参照する。

## EvidenceCheck

根拠1件の確認記録。型は `schemas/quality.py` の `EvidenceCheck`、検証は `validate_evidence_check` / `validate_evidence_list`。Assessment と ProposalQuality で共通に使う。

キーは次の7つちょうどとし、欠落・余分なキーはエラーにする。

- `url`: 根拠のURL。scheme が `http` / `https` で、ホスト部があること
- `checked_at`: 確認日時(文字列。空文字も型としては許容する)
- `target_version`: 確認対象の版(文字列または `null`)
- `status`: `verified` / `unavailable` / `unverified` / `unknown`
- `kind`: `primary` / `independent` / `republication` / `unknown`
- `claim`: この根拠が支える主張(文字列。空文字も型としては許容する)
- `note`: 補足(文字列。空文字可)

## ProposalQuality

記事企画の品質記録の契約。型は `schemas/quality.py` の `ProposalQuality`、検証は `validate_proposal_quality`。

- `question` / `difference` / `baseline` / `baseline_version` / `measurement` / `inputs_and_environment` / `effort` / `effort_assumptions` / `success_condition` / `stop_condition`: 空でない文字列
- `metrics`: 空でない文字列のリスト(1件以上)
- `evidence`: `EvidenceCheck` のリスト
- `unknowns`: リスト

`save-proposals` は、v2 の企画ごとに `validate_proposals`(`ideation/validation.py`)の中でこの契約を検証する(Issue #11。[記事企画入力](article-proposals.md)参照)。
