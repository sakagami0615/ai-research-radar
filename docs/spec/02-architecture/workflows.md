# 実行経路と責任

## Agent経路(本番の推奨)

実行Agentは `skills/agent-daily-run/SKILL.md` を読み、収集・正規化・候補生成のCLIを実行する。一次情報を確認して評価・企画・概要・Sourceの傾向をJSON入力にまとめ、CLIが検証・保存する。レポート生成後に別担当が内容をレビューする。

| 担当 | 責任 | 対応要件 |
| --- | --- | --- |
| Python | 収集、正規化、候補化、型・状態・ID検証、保存・表示 | F-01〜F-05、N-01・N-03 |
| 実行Agent | 根拠の内容確認、HOT採否、具体的企画、日本語文章 | F-03〜F-05 |
| 独立担当 | 根拠と主張、見落とし、企画・文章の品質確認 | F-06・N-07 |
| 利用者 | 記事・実験の採否、監視方針、修正要望 | UC-01〜UC-04 |

Pythonが入力を検証したことは、文章の正しさや根拠の真偽を保証しない。型の検証と内容レビューを分ける。

サブコマンドの順序は次のとおり。cronから `claude -p` / `codex exec` で起動したAgentが、Skillに従って順に実行する。

```text
collect → normalize → score → select-hot → save-proposals
        → add-summary / add-source-overview → report
        → (別プロセスのAgentによるレビュー・修正ループ) → mark-needs-review(未解消時のみ)
```

各サブコマンドは、日付ごとの実行状態 `data/runs/<date>/run_state.json` を読み書きして、完了した段階・エラー・選抜と記事企画の結果(`stage_results`)を引き継ぐ([実行記録](../03-detailed-design/data-models/run-metadata.md)、[CLIコマンド](../03-detailed-design/cli/commands.md))。

## 一括daily経路(手動確認・CI向け)

`ai-radar daily` はPythonだけで収集からレポートまで実行する。現行では旧スコアの選抜と旧形式の定型企画を生成する。Agentの内容判断・概要補完・独立品質レビューは含まない。収集からHOT候補の作成まではAgent経路と同じ処理を使い、選抜と記事企画の作り方だけが違う。`run_state.json` は使わず、`run.jsonl` だけを書く。

品質改善では、内容評価なしの自動HOT昇格と採用済み定型企画を廃止する目標があるが、今回の文書再編で動作を変えていない。[変更設計](../05-decisions/audit-remediation/README.md)と [適用状況](../../support/02-planning/requirement-status.md)を参照する。

## 操作・契約の参照先

実行手順は [日次運用](../../support/01-operations/daily-run.md)、Agent入力契約は [データモデル](../03-detailed-design/data-models/README.md)、CLI契約は [CLI詳細](../03-detailed-design/cli/README.md) を正本とする。
