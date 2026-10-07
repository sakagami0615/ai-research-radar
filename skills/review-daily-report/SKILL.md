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
- 選抜HOTの評価ブロック(レポートの判断理由・根拠・未確認事項)が、根拠のURLの内容と対応しているか(必要に応じて根拠のURLを確認する)。
- 評価レコードの各根拠について、取得ログに同じURLの行があり、そのいずれかの `fetched_at` が `checked_at` と一致するか(記録した時刻の裏付け。再取得で同じURLの行が複数あるのは正常)。
- `checked_at` と一致した取得ログの行の `content_verified` が `false` なのに、根拠を `status: verified` としていないか(bot対策ページなど)。
- PyPI候補の根拠が、`/project/` ページではなくJSON API(`https://pypi.org/pypi/...`)で確認されているか。`note` の `info.version` と `target_version` が対応しているか(異なるのに `verified` としていないか)。
- 上の3点の不備(根拠があるのに取得ログが無い、`checked_at` と一致する行が無い、内容を確認できなかった取得を `verified` としている、など)は、実行Agentが取り直して直せるため、Importantとして指摘する。
- `selection_reason` と確認範囲が妥当か(`hot_candidates.jsonl` のうち `screened_ids` にない候補は未確認であり、`unreviewed_candidates` の警告対象になる。未確認の候補が残っている場合、確認した範囲が `selection_reason` に書かれているか)。
- 記事企画にEvidence URLなしの主張がないか。
- 各 `article_proposals` の `evidence_links` が、対応するHOT候補(`source_hot_id` が一致するもの)の `evidence_urls` と整合しているか。
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

- 注目候補: `hot_id` が当日の `hot_candidates.jsonl` または `digest_summaries.json` にあるもの。当日の `hot_candidates.jsonl` にある候補は `selection_input.json` の `summaries` を書き直して `select-hot` を再実行し、`digest_summaries.json` にある項目は `summary_input.json` に書いて `add-summary --input` を再実行して修正する。過去日の候補が自分で持っている概要(当日のどちらのファイルにもない `hot_id`)はその日のレビューで確認済みで、当日には修正できないため指摘対象にしない。
- 新モデルリリース: 概要は当日の `digest_summaries.json` にしかなく、いつでも `add-summary --input` で直せるため、すべて指摘対象にする(理由なく「概要未作成」のまま残っている項目も含む。情報取得失敗・未確認の理由が書かれた「概要未作成」は、上の観点のとおり指摘しない)。

また、選抜0件の妥当性や見落としを判断する材料として参照するのはよい(例: 注目候補にある項目を選抜すべきだった、という指摘はHOT選抜への指摘として扱う)。

## 出力

1. 上記観点で明確な誤り(根拠のない選抜・Evidence URLのない主張など、Critical)や、妥当性に疑問があり確認が必要な問題(Important)がなければ、`data/runs/<date>/review_feedback.md` が存在しないことを保証する(存在していれば削除する)。
2. 該当する問題があれば、`data/runs/<date>/review_feedback.md` に自然文で具体的に書く。該当箇所・理由・修正方針を含めること。
3. 表現の好みなどMinor相当の指摘は `review_feedback.md` に書かない。Critical/Importantのみを対象とする(Minorまで指摘すると、修正ループが実質的に終わらなくなるため)。

`review_feedback.md` の存在有無だけが、`agent-daily-run` Skillを実行しているAgentにとっての「承認/要修正」の判定基準になる。この基準を厳密に守ること。

新経路では`ReviewResult`を検証し、対象hash不一致は`stale`、起動失敗や結果欠損は`failed`とする。`approved`にCritical/Important指摘を含めない。原成果物を修正せず、結果JSONとfeedbackだけを出力する。
