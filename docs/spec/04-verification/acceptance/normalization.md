# 正規化・集約の受入

対象: F-02。[正規化要件](../../01-requirements/02-definition/functional/normalization.md)を参照。

1. 重複URL、意味のあるquery、空URL、同名別成果を固定入力として用意する。
2. 現行の重複排除を確認する。同一成果の識別(DOI・arXiv版・パッケージ版・観測の対応)は未実装であり、実装後に確認する。
3. 値0、欠損、不正値、単独観測、同値を分けて、現行スコアの扱いを確認する。品質v2の指標は未実装であり、実装後にCLI出力への反映を確認する。
4. Signal・Event・Topicの保存と根拠対応を確認する。

単体テストの成功と、現行CLIでの確認は別に記録する。詳細な品質改善標本は [監査改善受入](../audit-remediation-acceptance.md) を参照。
