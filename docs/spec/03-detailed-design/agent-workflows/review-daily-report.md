# review-daily-report の役割

共通Workflowの設計上の役割。実行手順はリポジトリの `skills/review-daily-report/SKILL.md` を正本とする。

## review-daily-report

`agent-daily-run` Skillを実行したAgentとは別セッション・別プロセスのAgentとして、その日のHOT選抜・記事企画・レポートの「質」を検証する。判断基準は `hot-detection` / `article-ideation` を参照する。

- 承認・要修正の判定は `data/runs/<date>/review_feedback.md` の有無だけで行う。Critical / Important の指摘があるときだけレビュー担当がこのファイルを書き、なければ書かない(Minorは書かない)。実行側は、ファイルがなければ承認、あれば修正して再レビューを依頼する。レビューの試行は最大3回(初回を1回目とする)。修正は試行の間に行うため最大2回。3回目の試行の後も解消しなければ `mark-needs-review` で記録する。
- レビュー担当は原成果物を編集しない。書くのは `review_feedback.md` だけである。
- 根拠の `checked_at` は取得ログ `evidence_fetch_log.tsv` の `fetched_at` と突き合わせ、内容を確認できなかった取得を `verified` としていないかを確認する(取得ログは読むだけで追記しない)。
- 対象成果物のhashの固定や構造化した結果(`ReviewResult`)は未実装である([将来対応](../../../support/02-planning/future-works.md))。

レポートの「注目候補(選抜外)」「新モデルリリース」はCLIが決定論的に生成し実行Agentが修正できないため、セクションの内容(どの項目が載るか、並び順、スコアなど)は指摘対象にしない(HOT選抜の見落とし判断の材料としては参照してよい)。ただし、概要のうち当日に書かれたものは実行Agentが修正できるため、Evidence・リンク先との整合、タイトルの直訳だけになっていないか、未確認の内容を断定していないかを指摘対象にする。当日に書かれた概要は、選抜HOT・注目候補では当日の `hot_candidates.jsonl` または `digest_summaries.json` にある `hot_id` のもの、新モデルリリースではすべて(概要は当日の `digest_summaries.json` にしかなく、いつでも `add-summary --input` で直せるため)である。過去日の注目候補が自分で持っている概要は当日に修正できないため指摘対象にしない。情報取得失敗・未確認の理由が書かれた「概要未作成」は指摘しない(観点の詳細は `review-daily-report` Skillを参照)。収集Source一覧のSourceごとの「本日の傾向」も、実行Agentが `add-source-overview --input` で修正できるため指摘対象にする(一覧の内容と食い違っていないか、日本語で書かれているか、おおむね200字以内か、収集1件以上のSourceに「傾向未作成」が残っていないか。ただし `run_state.json` に `add-source-overview` のエラーが残っている、つまり再実行の上限に達して保存できなかった場合は指摘しない)。
