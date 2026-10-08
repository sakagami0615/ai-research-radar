---
name: review-daily-report
description: Use when 日次パイプラインの成果物(HOT選抜・記事企画・レポート)を、実行したAgentとは別セッションのAgentとして品質検証するとき。
---

# Review Daily Report

## 目的

`agent-daily-run` Skillに従って実行された日次パイプラインの成果物を、実行したAgentとは別セッションのAgentとして検証する。構文・スキーマレベルの妥当性はCLIサブコマンド自体が検証済みであり、このSkillが扱うのは選抜内容・記事企画の「質」の妥当性である。

## 判断基準の参照

- HOT選抜の妥当性: [skills/hot-detection/SKILL.md](../hot-detection/SKILL.md) の「判断方針」「レビュー観点」を用いる。
- 記事企画の妥当性: [skills/article-ideation/SKILL.md](../article-ideation/SKILL.md) の「企画観点」「レビュー観点」を用いる。

このSkillはこれらの判断基準を再掲しない。実行前に上記2つのSkillを読むこと。

## 検証対象

指定された `<date>` について、以下を読む。

- `reports/daily/<date>.md`
- `data/runs/<date>/hot_candidates.jsonl`(`selected` の内訳を含む)
- `data/runs/<date>/selection_input.json`(評価レコード・確認範囲 `screened_ids`・`selection_reason`)
- `data/runs/<date>/article_proposals.jsonl`(存在する場合)
- `data/runs/<date>/digest_summaries.json`(存在する場合。注目候補のうち過去日の候補などに当日補った概要と、新モデルリリースの概要。キーは注目候補が `hot_id`、新モデルリリースが正規化済みURL)
- `data/runs/<date>/evidence_fetch_log.tsv`(実行Agentが取得したURLのログ。根拠があるのにこのファイルが無い場合は、下の検証観点の不備として扱う。レビュー担当は読むだけで追記しない。レビューのために根拠のURLを取得しても記録しない)

## 検証観点

- HOT選抜数が妥当か(通常0〜2件、多くても5件程度)。
- Momentumのみで低Credibility情報を過大評価していないか。
- Source Familyが単一に偏ったまま選抜していないか(cross-source確認なし)。
- 選抜0件の場合、その判断が妥当か(見落としがないか)も確認する。
- 選抜0件の日は、レポートの選抜HOTセクションに保留理由と確認範囲(「本日の選抜HOTはありません(保留: …。候補 m件中 n件を確認、未確認 k件)。」。候補0件の日は「…(保留: …。候補0件)。」)が出ており、Run SummaryのSelection行と食い違っていないか。選抜0件の日は、Run SummaryのProposals行が `not_run(選抜HOTなし)` になるのが正常であり、指摘しない。
- 選抜HOTセクションに「選抜は未実行」「選抜は失敗」、または(選抜HOTがある日に)「記事企画は未実行」「記事企画の保存は失敗」が出ている場合は、保留ではなく実行・保存の漏れとして指摘する。失敗が実行Agentの再実行の上限(`agent-daily-run` の「エラー時の自己修正方針」の項目3)に達して残っている場合も指摘してよい(実行Agentは再実行せず修正不能として扱う)。
- 選抜HOTセクションに「選抜結果が見つかりません(…)」が出ている場合(`select-hot` は `completed` なのに選抜HOTが0件)は、選抜結果の消失として指摘する。
- レポートに「<ファイル名> を読めなかったため表示できません(Errors を参照)。」の注記(選抜HOTセクション・各選抜HOTの企画欄・収集Source一覧)が出ている場合、または `data/runs/<date>/run_state.json` の `errors` に `source: report` の `corrupt_input` がある場合は、当日のファイル(`hot_candidates.jsonl` / `article_proposals.jsonl` / `data/normalized/<date>/signals.jsonl`)の破損として指摘してよい。ただし、実行Agentはレポート生成の直後に1回だけ前のステージから流し直す(`agent-daily-run` の「壊れた入力(`corrupt_input`)」)ため、レビューの時点で残っているものは通常その上限に達しており、実行Agentは修正不能として扱う。`select-hot` / `save-proposals` の `failed` の理由が `corrupt_input: …` の場合も同じ。
- 選抜HOTの評価ブロック(レポートの判断理由・根拠・未確認事項)が、根拠のURLの内容と対応しているか(必要に応じて根拠のURLを確認する)。
- 評価レコードの各根拠について、取得ログに同じURLの行があり、そのいずれかの `fetched_at` が `checked_at` と一致するか(記録した時刻の裏付け。再取得で同じURLの行が複数あるのは正常)。
- `checked_at` と一致した取得ログの行の `content_verified` が `false` なのに、根拠を `status: verified` としていないか(bot対策ページなど)。
- PyPI候補の根拠が、`/project/` ページではなくJSON API(`https://pypi.org/pypi/...`)で確認されているか。`note` の `info.version` と `target_version` が対応しているか(異なるのに `verified` としていないか)。
- 上の3点の不備(根拠があるのに取得ログが無い、`checked_at` と一致する行が無い、内容を確認できなかった取得を `verified` としている、など)は、実行Agentが取り直して直せるため、Importantとして指摘する。
- `selection_reason` と確認範囲が妥当か(`hot_candidates.jsonl` のうち `screened_ids` にない候補は未確認であり、`unreviewed_candidates` の警告対象になる。未確認の候補が残っている場合、確認した範囲が `selection_reason` に書かれているか)。
- 記事企画にEvidence URLなしの主張がないか。
- 各 `article_proposals` の `evidence_links` が、対応するHOT候補(`source_hot_id` が一致するもの)の `evidence_urls` と整合しているか。元のHOT候補にないURL(比較対象など)は、`quality.evidence` の `claim` に書かれた役割とURLの内容が合っているか。
- v2の企画(`schema_version: 2`)の `quality`(レポートの詳細表の 検証の問い / 既存との差分 / 比較対象と版 / 測定方法 / 入力・環境 / 工数と前提 / 成功条件 / 中止条件 / 指標 / 未確認事項 / 確認した根拠)が、企画ごとに具体的か。題名の言い換えや定型文だけになっていないか、比較対象に版または固定日・条件があるか、確認した根拠の内容と企画の主張が対応しているか、確認していないことを未確認事項に書いているか(必要に応じて根拠のURLを確認する)。`quality.evidence` の `checked_at` と取得ログの突き合わせは、選抜HOTの評価レコードの根拠と同じ観点で確認する。
- 競合・読者需要(`competition` / `traffic_opportunity`)を、調べた形跡がないのに「High」などと断定していないか(未調査なら「未調査」と書くのが正しい)。
- 選抜HOTがあるのに企画が0件の場合(レポートの「記事企画なし(保留: <理由>)」、Run SummaryのProposals行の `deferred`)、その理由が妥当か。
- 「品質評価: 旧形式のため未評価」の行は、過去日の旧形式の企画と決定論経路の企画に出る正常な表示であり、指摘しない。当日の `agent-daily-run` で保存した企画は必ずv2であり、この行は出ない。
- 「使ってみた」だけに偏った企画になっていないか、日本語記事としての独自性があるか。
- 選抜HOT・注目候補の概要(レポートの各項目の見出し直後の `> **概要**:`)について:
  - 概要がEvidence URLの内容と食い違っていないか(必要に応じてEvidence URLを確認する)。
  - タイトルの直訳や、Reasons(選抜した/しなかった理由)の繰り返しだけになっておらず、「それが何か」がわかるか。
  - 確認できていない内容(報道ベースの主張、性能値など)を確認済みの事実として断定していないか。一次情報を取得できなかった場合に「一次情報未確認」と明記されているか。
  - 「概要未作成」のまま残っている項目がないか(情報取得失敗・未確認の理由が書かれている場合は除く)。
- 新モデルリリースの概要(レポートの各項目の次の行の `  - 概要:`)について:
  - 概要がリンク先の内容と食い違っていないか(必要に応じてリンク先を確認する)。
  - 確認できていない項目(規模・ライセンスなど)を推測で書いていないか。一次情報を取得できなかった場合に「一次情報未確認」と明記されているか。
  - 「概要未作成」のまま残っている項目がないか(情報取得失敗・未確認の理由が書かれている場合は除く)。
  - 指摘するときは、項目のタイトルとURLを書く。

レポートの「注目候補(選抜外)」「新モデルリリース」セクションはCLIが決定論的に生成するものであり、実行Agentには修正手段がない。このため、これらのセクションの内容そのもの(どの項目が載るか、並び順、スコアなど)を `review_feedback.md` の指摘対象にしない(指摘すると修正ループが解消されないまま3回で終わる)。ただし、概要のうち当日に書かれたものは実行Agentが修正できるため、上記の概要の観点で指摘対象にする。

- 注目候補: `hot_id` が当日の `hot_candidates.jsonl` または `digest_summaries.json` にあるもの。当日の `hot_candidates.jsonl` にある候補は `selection_input.json` の `summaries` を書き直して `select-hot` を再実行し(続けて `save-proposals` も再実行する)、`digest_summaries.json` にある項目は `summary_input.json` に書いて `add-summary --input` を再実行して修正する。過去日の候補が自分で持っている概要(当日のどちらのファイルにもない `hot_id`)はその日のレビューで確認済みで、当日には修正できないため指摘対象にしない。
- 新モデルリリース: 概要は当日の `digest_summaries.json` にしかなく、いつでも `add-summary --input` で直せるため、すべて指摘対象にする(理由なく「概要未作成」のまま残っている項目も含む。情報取得失敗・未確認の理由が書かれた「概要未作成」は、上の観点のとおり指摘しない)。

また、選抜0件の妥当性や見落としを判断する材料として参照するのはよい(例: 注目候補にある項目を選抜すべきだった、という指摘はHOT選抜への指摘として扱う)。

## 出力

1. 上記観点で明確な誤り(根拠のない選抜・Evidence URLのない主張など、Critical)や、妥当性に疑問があり確認が必要な問題(Important)がなければ、`data/runs/<date>/review_feedback.md` が存在しないことを保証する(存在していれば削除する)。
2. 該当する問題があれば、`data/runs/<date>/review_feedback.md` に自然文で具体的に書く。該当箇所・理由・修正方針を含めること。
3. 表現の好みなどMinor相当の指摘は `review_feedback.md` に書かない。Critical/Importantのみを対象とする(Minorまで指摘すると、修正ループが実質的に終わらなくなるため)。

`review_feedback.md` の存在有無だけが、`agent-daily-run` Skillを実行しているAgentにとっての「承認/要修正」の判定基準になる。この基準を厳密に守ること。

新経路では`ReviewResult`を検証し、対象hash不一致は`stale`、起動失敗や結果欠損は`failed`とする。`approved`にCritical/Important指摘を含めない。原成果物を修正せず、結果JSONとfeedbackだけを出力する。
