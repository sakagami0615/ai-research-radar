# 共通Skillの役割と入出力

旧設計書の該当節を分割した資料。現行と移行目標の区別は [文書全体の入口](../../README.md) から確認する。

## 目的

Claude Code / Codexのどちらでも、同じ調査Workflowを参照できるように `skills/` 配下へ共通Skillを置く。

実装ロジックはSkillではなく `src/` に置く。Skillは「何をしたいか」「どう確認するか」を案内するWorkflow文書である。


## Skill一覧

| Skill | 役割 |
| --- | --- |
| `skills/agent-daily-run/SKILL.md`(+ `recovery.md`) | 日次の実行手順。cronから起動されたAgentが従う |
| `skills/review-daily-report/SKILL.md` | 日次の成果物の品質レビュー。`agent-daily-run` が別プロセスのAgentに実行させる |
| `skills/hot-detection/SKILL.md` | HOT選抜の判断基準(上の2つから参照する) |
| `skills/article-ideation/SKILL.md` | 記事企画の観点と `quality` の書き方(上の2つから参照する) |

`ai-radar daily`(決定論経路)の使い方はREADMEと [CLI設計](../cli/README.md) に書き、Skillは置かない。


## 役割の参照先

- [agent-daily-run](agent-daily-run.md)
- [review-daily-report](review-daily-report.md)
- [hot-detection](hot-detection.md)
- [article-ideation](article-ideation.md)
