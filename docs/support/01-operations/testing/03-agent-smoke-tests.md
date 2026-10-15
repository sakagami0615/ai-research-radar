# 03 Agent実機確認

## 確認範囲を決める

SKILL.mdやプロンプトテンプレートなど、Agent自身が解釈する手順書を変更した場合は、diffの静的レビューに加え、可能であれば実際にAgentを起動して手順どおりに動くか確認する。ループ回数、分岐の飛び先、再試行・終了条件には、読むだけでは分からない解釈違いが生じうる。

先に [環境準備](01-environment.md) を行い、変更内容に応じて次の範囲を選ぶ。

- 参照先だけの変更：読み取り専用で参照をたどり、正本と必要な条件を答えられるか確認する。
- 手順・分岐の変更：安全な入力・出力先を用意し、変更した経路を実行して確認する。参照確認だけで動作確認済みとはしない。

使ったAgent、プロンプト、確認した分岐、結果、未確認の分岐を記録する。Claude Code・Codexは同じ資料とSkillを使い、Agent別の手順書は複製しない。一方で確認した結果を、もう一方でも確認済みとみなさない。

## 読み取り専用の参照確認

Claude Codeでの例（対象ルートで実行）：

```bash
claude -p 'AGENTS.mdを読み、テスト実行前に読むべき資料をたどってください。worktreeでのテストコマンド、対象コードの確認方法、Agent実機確認時のCLI対策、権限制約時の代替手段を日本語で答えてください。ファイル変更・コマンド実行・日次処理は行わず、資料を読むだけにしてください。' --tools Read,Glob,Grep --allowedTools Read Glob Grep --max-turns 12
```

変更した資料を読むようプロンプトに指定し、参照先・必須条件を実際の資料と照合する。CLIを呼ばない確認では、下記のCLIラッパーは不要である。

## worktreeでSkill内のCLIを実行する場合

Skill内の `ai-radar` はメインチェックアウト側のインストールを指すことがある。scratchpadの専用 `bin/ai-radar` に次のラッパーを置き、実行権限を付ける。`<worktree>` は対象ルートの絶対パスに置き換える。

```sh
#!/bin/sh
PYTHONPATH='<worktree>/src' exec python -m ai_research_radar.cli.main "$@"
```

Agent起動時は、このbinをPATHの先頭へ追加する。Pythonが対象環境のものか、ラッパーのモジュールが対象worktreeのものかを確認してから起動する。次は起動方法の形を示す例であり、プレースホルダーを置き換え、実行範囲・入力・出力先を確定してから使う。

```bash
cd '<worktree>' && PATH='<scratchpad>/bin':"$PATH" PYTHONPATH='<worktree>/src' claude -p '<確認するSkill・分岐・入力・出力先・完了条件を指定したプロンプト>'
```

日次処理の正本は [agent-daily-run](../../../../skills/agent-daily-run/SKILL.md)、Agent起動とレビューの運用は [cron運用](../scheduled-run.md) を参照する。これは検証用のCLIラッパーであり、本番cron起動用ラッパーを追加するものではない。

日次処理を実データで通すときは、本番の `data/` / `reports/` に書かない [cron運用](../scheduled-run.md) の「テストモード」を使う。

## 再開の確認

途中で止まった日の再開(Issue #30)は、止まった時点ごとのテスト用データ(`tests/fixtures/resume_scenarios/<シナリオ名>/`)をテスト用の出力先に置いてから確認する。対象のチェックアウトのルートで実行する。

```bash
PYTHONPATH=src python scripts/setup_resume_scenario.py <シナリオ名>
PYTHONPATH=src python -m ai_research_radar.cli.main progress show --date "$(date +%F)" --data-dir test_output/data --reports-dir test_output/reports
```

- `test_output/data` を消し、`test_output/reports/daily/<対象日>.md` を消してから配置する。対象日は `--date`(省略時は今日。Skillは `date +%F` を対象日にするため)。fixtureの対象日(`2026-09-25`)が対象日になるよう、ファイル名と中身の日付をすべて同じ日数だけずらし、`review_target.json` のハッシュは配置後の成果物から計算し直す。`--output-dir` にチェックアウトのルート、またはその `data/` / `reports/` の中を指定した場合は終了コード1で止まる(本番の `data/` / `reports/` を書き換えないため)。
- データは `scripts/build_resume_scenarios.py` が実際のCLI(fixtureのSource、`collect` 〜 `report` と `progress`)で作ったもので、HOT候補は全件見送り(`select-hot` が `deferred`)、記事企画は0件である。スキーマの変更などで作り直すときは `PYTHONPATH=src python scripts/build_resume_scenarios.py` を実行し、`tests/test_progress_show.py` で判定を確かめる。
- Agentでの再開の確認(`entry-prompt-test-resume.txt`)は、Skillへの組み込み(#44)の後に行う。それまでは `progress show` の判定だけを確かめる(自動テスト `tests/test_progress_show.py` と同じ判定)。

| シナリオ名 | 止まった時点 | `progress show` の判定 |
| --- | --- | --- |
| `01_done` | 作成済みの日 | `done` |
| `02_deterministic_only` | 決定論経路(`ai-radar daily`)の記録だけがある日 | 手順1から |
| `03_after_score` | `score` の後 | 手順4から |
| `04_after_selection` | 選抜の後、企画の前 | 手順6から |
| `05_after_report` | レポート生成の後、レビューの前 | 手順8から(`review_target.json` がないため。次のレビューは1回目) |
| `06_review2_changes_requested` | レビューの2回目で修正を求められた後 | 手順9から(指摘を直してから3回目) |
| `07_corrupt_input` | `hot_candidates.jsonl` が壊れたまま(`select-hot` が `corrupt_input`) | 手順3(`score`)から |
| `08_retry_limit_reached` | `select-hot` の再実行が上限(3回)に達し `failed` のまま | 手順6から(`select-hot` は `skipped`) |
| `09_approved_not_completed` | レビューで承認された後、`progress complete` の前 | `progress complete` を記録して終了 |
| `10_review3_changes_requested` | レビューの3回目で修正を求められた後 | 手順10から |
| `11_finalize_interrupted` | 手順10の途中(`progress finalize` と `mark-needs-review` の後) | 手順10をやり直す |

## 権限制約と終了条件

IDE拡張のAuto Modeなどの対話セッションで日次Skillを手動実行すると、レビュー用の別プロセス（`claude -p ... --permission-mode bypassPermissions` など）の起動が「Create Unsafe Agents」として拒否される場合がある。この場合は制約を回避せず、利用可能な同一セッション内のsubagentへレビューを委譲する。代替手段が使えない場合は、レビュー未実施として理由を記録する。

cronからの本番起動は独立プロセスで、上記の対話セッション固有の制約とは区別する。具体的な起動手順はcron運用を正本とし、試験のためにcron設定を変更しない。

Agentの終了コードだけで合格にせず、指定した参照・分岐・成果物・レビュー結果を照合する。入力不足、権限拒否、ターン上限などで確認できなかった範囲を明記する。結果の記録項目は [テスト実行ガイド](README.md#結果の扱い) を参照する。
