# 障害の切り分け

## 読む記録

実行ログ、`data/runs/<date>/run_state.json`、`run.jsonl`、日次レポートのエラー・データ欠落を確認する。終了コード0でもSource失敗や品質保留がないとは限らない。

## 原因別の参照先

| 状況 | 参照先 | 確認する内容 |
| --- | --- | --- |
| Source取得失敗 | [取得制約](../03-detailed-design/source-adapters/failures.md) | Source単位・endpoint単位の失敗、ネットワーク制約 |
| Agent入力が不正 | [CLI契約](../03-detailed-design/cli/commands.md) | `invalid_input`、評価・企画入力の契約 |
| 上流の保存データが破損 | [日次Skill](../../skills/agent-daily-run/SKILL.md) | `corrupt_input`、補完実行範囲と上限 |
| 保存・レポート生成失敗 | [実行状態](../03-detailed-design/data-models/run-metadata.md) | 書込み失敗、未実行・失敗・保留の区別 |
| レビュー指摘が残る | [日次Skill](../../skills/agent-daily-run/SKILL.md) | 初回を含む最大3回と警告条件 |
| 対話セッションでレビュー起動を拒否 | [cron運用](scheduled-run.md) | 別プロセスとsubagent代替の条件 |

修正手順や回数の分岐は共通Skillを正本とする。実装変更が必要なら要件・設計への影響を確認し、[バックログ](../06-planning/backlog.md)とレビュー運用に従う。
