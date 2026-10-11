# N-01／N-02 信頼性と復旧

## N-01 Sourceの障害分離

一つのSource取得失敗で他Sourceの処理を止めず、失敗を記録する。完全な取得失敗はレポートでデータ欠落として確認できることを受入条件とする。保存先が書込み不能の場合は記録を残せない制約を明示する。

## N-02 再実行と状態

Agentが再実行するときは、同じ原因で無制限に反復せず、成果なし・未実行・失敗を区別する。回数の定義と例外は共通Skillを正本とする。品質改善目標として、上流の再実行が依存する下流成果物・レビューを失効させ、旧試行を追えることを受入条件とする。

現行の選抜再実行による企画状態の失効と、Pipeline全体の履歴・失効目標は適用範囲が異なる。[実行状態契約](../../../03-detailed-design/data-models/run-metadata.md)、[変更設計](../../../07-decisions/audit-remediation/execution-and-reporting.md)、[日次Skill](../../../../skills/agent-daily-run/SKILL.md)を参照。
