# 日次実行の入口

## Agentによる実行

`skills/agent-daily-run/entry-prompt.txt` から [共通日次Skill](../../../skills/agent-daily-run/SKILL.md) を読ませる。対象日、一次情報の確認、JSON入力、CLI実行、レビュー・修正・完了条件の正本はこのSkillである。ここに手順を複製しない。

入力を作る時点で、[選抜契約](../../spec/03-detailed-design/data-models/hot-selection.md)と [企画契約](../../spec/03-detailed-design/data-models/article-proposals.md)を確認する。定期起動のコマンドは [cron運用](scheduled-run.md) を参照する。

## 決定論的な実行

手動・CIでは `ai-radar daily` を使える。詳細引数と期間解決は [CLI入口](../../spec/03-detailed-design/cli/period-resolution.md) を参照。内容判断を含むAgent経路との差は [基本設計](../../spec/02-architecture/workflows.md) を確認する。

実行後は [結果確認](result-checks.md) へ進む。
