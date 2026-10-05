---
name: agent-daily-run
description: Use when cron等からAgentとして日次調査パイプラインを実行し、HOT最終選抜と記事企画をAgent自身の判断で行うとき。
---

# Agent Daily Run

## 目的

`ai-radar` CLIのサブコマンド(`collect` / `normalize` / `score` / `select-hot` / `save-proposals` / `add-summary` / `report`)を順に呼び出し、HOT最終選抜、選抜HOT・注目候補の日本語概要、記事企画をAgent自身の判断で作り、日次レポートを完成させる。

`ai-radar daily` は決定論的な一括実行コマンドであり、このSkillでは使わない。

## 前提Skill参照

- HOT選抜の判断基準: [skills/hot-detection/SKILL.md](../hot-detection/SKILL.md) の「判断方針」(通常0〜2件、多い日でも最大5件程度、全Candidateをそのまま通知しない、重大Official Eventはスコアだけに依存させない)を用いる。
- 記事企画の観点: [skills/article-ideation/SKILL.md](../article-ideation/SKILL.md) の「企画観点」(Technical Explainer / Hands-on / Comparison / Benchmark / Critical Review)と「レビュー観点」(Evidence URLなしの主張をしない、「使ってみた」だけに偏らない、日本語記事としての独自性)を用いる。

このSkillはこれらの判断基準を再掲しない。実行前に上記2つのSkillを読むこと。

## 実行手順

実行時は`SelectionInput`と`ProposalQuality`を03の共通契約として使う。空の選抜`[]`・空の企画`[]`は未実施または保留の結果として保存し、成功したことに置き換えない。レビュー対象は`review_target.json`で固定し、レビュー担当は原成果物を編集せず`review_result.json`だけを返す。初回をattempt 1として最大3回まで修正し、起動失敗・記録なし・3回後の重要指摘は承認しない。

1. 対象日を判定する。`date +%F` を実行し、今日の日付(`YYYY-MM-DD`)を取得する。以降の手順ではこの日付を `<date>` として使う。`collect` の `--since` / `--until` は省略し、前回実行の終了時刻から実行時刻までを収集する(最大7日、初回も7日分)。明示的な期間で再実行する必要がある場合だけ、タイムゾーン付きISO 8601日時または日付を指定する。

   ```bash
   ai-radar collect --data-dir data --sources-config config/sources.yaml
   ```

   `--since` / `--until` は省略する(省略時は前回実行から引き継いだ期間。詳細は `docs/specs/06-cli-and-operations.md`)。

2. 正規化する。

   ```bash
   ai-radar normalize --date <date>
   ```

3. HOTスコアを計算する(まだ選抜はしない)。

   ```bash
   ai-radar score --date <date> --scoring-config config/scoring.yaml
   ```

4. `data/runs/<date>/hot_candidates.jsonl` を読み、hot-detection Skillの判断方針に従って選抜するHOT候補の `hot_id` を決める。

   判断の記録(`selection_input.json` の評価レコード)に書く日時は、推定や切りのよい値ではなく実測値にする。

   - 根拠の `checked_at`: そのURLを実際に取得した直後に `date -u +%Y-%m-%dT%H:%M:%S+00:00` を実行し、その出力を書く。複数URLをまとめて取得した場合は、それぞれの取得直後の値を使う。
   - 評価の `assessed_at`: その評価の根拠をすべて確認し終えた後、レコードを書く直前に同じコマンドで取得した値を書く(`checked_at` 以降、かつファイル保存前)。
   - 取得時刻を記録し忘れた根拠は、時刻を推定せずに取得し直してから記録する。
   - 取得時のコマンド出力(URL・HTTPステータス・時刻)を `data/runs/<date>/` 配下に残し、記録した時刻をレビュー担当が裏付けられるようにする。

   あわせて、`hot_candidates.jsonl` の **全候補**(選抜しない候補も含む)について、レポートに載せる日本語の概要を書く。選抜外の候補も翌日以降まで「注目候補」としてレポートに載るためである。

   - 内容: 2〜3文、おおむね150字以内で「それが何か」「何が新しい・変わったか」を書く。Reasons(選抜した/しなかった理由)の繰り返しや、タイトルの直訳だけにしない。
   - 根拠: 評価のために読んだ一次情報(Evidence URLの中身)に基づいて書く。一次情報を取得できなかった場合(403など)は、取得できた範囲(報道記事、PyPIの説明など)で書き、「一次情報未確認」と明記する。何も取得できなかった場合は「概要未作成(情報取得失敗: HTTP 403)」のように理由を書く。
   - 確認できた事実と、発表元・報道の主張を区別する(例: 「〜と発表している」「〜と報じられている」)。

5. 選抜結果を確定する。

   ```bash
   ai-radar select-hot --date <date> --select <id1,id2,...> [--reason <hot_id>=<選抜理由>] --summary <hot_id>=<概要> [--summary ...]
   ```

   `--reason` は複数の候補に理由を付けたい場合、繰り返し指定できる(`--reason id1=理由1 --reason id2=理由2`)。

   `--summary` には手順4で書いた概要を、全候補分繰り返し指定する。指定しなかった候補は前回保存した概要を保持し、同じ候補を再指定すると置き換わる。選抜した候補に概要がないと `missing_summary` で失敗する。選抜外の候補に概要がない場合は成功するが、`run_state.json` の `errors` に `missing_summary_warning` が記録されるので、その候補の概要を追加して再実行する。

6. 選抜された各候補について、article-ideation Skillの企画観点に従って `ArticleProposal` 形式のJSON配列を作成し、`data/runs/<date>/draft_proposals.json` に書き出す。候補1件あたり1〜3件程度の企画に絞る(既存の決定論的Ideation実装の上限である3件を目安とし、通知疲れを避ける)。

   `ArticleProposal` の必須フィールド: `proposal_id` / `source_hot_id` / `title_idea` / `article_type` / `target_reader` / `why_now` / `technical_angle` / `experiment_plan` / `competition` / `traffic_opportunity` / `technical_opportunity` / `unique_angle` / `evidence_links` / `risks`。

   - `source_hot_id` は手順5で選抜した `hot_id` と一致させる。
   - `evidence_links` は空にしない(選抜候補の `evidence_urls` を引き継ぐ)。

7. 記事企画を保存する。

   ```bash
   ai-radar save-proposals --date <date> --input data/runs/<date>/draft_proposals.json
   ```

8. 注目候補の概要を補完してから、レポートを生成する。

   a. レポートの注目候補に表示される項目のうち、概要がないもの(過去日の候補など)を一覧する。何も出力されなければ c へ進む。

      ```bash
      ai-radar report --date <date> --list-missing-summaries
      ```

      出力は1行1件のJSON(`hot_id` / `title` / `first_seen` / `evidence_urls`)。このコマンドは何もファイルを書き換えない。

   b. 一覧の各項目について `evidence_urls` のサイトにアクセスして内容を確認し、手順4と同じ基準で概要を書いて保存する(一次情報を取得できない場合の書き方も手順4と同じ)。

      ```bash
      ai-radar add-summary --date <date> --summary <hot_id>=<概要> [--summary ...]
      ```

      保存後に a を再実行し、何も出力されないことを確認する。

   c. レポートを生成する。

      ```bash
      ai-radar report --date <date> --reports-dir reports
      ```

9. `report` 完了後、成果物の質を別セッションのAgentにレビューさせる。

   a. 自分自身が起動されているのと同じCLIで、新しいプロセスとして
      `skills/review-daily-report/entry-prompt.txt` の内容(`{date}` は
      手順1で判定した `<date>` に置換したもの)を渡して起動する。
      cronの各行はclaude/codexいずれか一方を直接起動するため、実行中のAgentは
      自分がどちらであるか自明である。

      - 自分がClaude Codeの場合: `claude -p "<prompt>" --permission-mode bypassPermissions`
      - 自分がCodexの場合: `codex exec "<prompt>" --sandbox workspace-write`

   b. `data/runs/<date>/review_feedback.md` の有無を確認する。

      - 存在しない場合: 承認。品質レビューループを終了し、完了確認へ進む。
      - 存在する場合、かつこれが3回目の試行でない場合: 内容を読み、HOT選抜のやり直しや
        記事企画・概要の書き直しなど必要な修正を自分自身で行った上で、`ai-radar select-hot` /
        `save-proposals` を再実行し、手順8のa〜c(概要の補完とレポート生成)をやり直してから、
        手順9のa(レビュー担当の起動)に戻る。
        手順8bで補完した概要の修正は、`add-summary` で同じ `hot_id` を再指定すると上書きされる。
      - 存在する場合、かつこれが3回目の試行だった場合: 手順10へ進む。

10. 3回試行しても `data/runs/<date>/review_feedback.md` が残っている場合:

    - `reports/daily/<date>.md` の冒頭に次のバナーを追記する(間に空行を1行挟んで元の内容を続ける):

      ```
      > ⚠️ **要確認**: 自動レビューで解消できなかった指摘があります。`data/runs/<date>/review_feedback.md` を確認してください。
      ```
    - `data/runs/<date>/run_state.json` を読み、`needs_review: true` を追加して書き戻す(既存のキー順・インデント幅など、このパイプラインの他の箇所での `run_state.json` の書式と揃えること)。

## エラー時の自己修正方針

`select-hot` / `save-proposals` / `add-summary` がバリデーションエラー(終了コード1)を返した場合:

1. `data/runs/<date>/run_state.json` の `errors` を読み、エラー種別(`invalid_selection` / `invalid_reason` / `invalid_summary` / `missing_summary` / `invalid_input` / `invalid_proposal` など)とメッセージを確認する。
2. 原因に応じて選抜ID・概要・`draft_proposals.json` を修正し、再実行する。
   - `add-summary` が `write_error` で失敗し、メッセージから `data/runs/<date>/digest_summaries.json` が壊れていると分かる場合は、そのファイルを `digest_summaries.json.broken` に名前を変えて退避し、手順8aからやり直す(退避したファイルの概要は失われるため、一覧に出た項目の概要を書き直す)。
3. 再実行は最大3回までとする。3回後も重要指摘が残る場合は`needs_review`として停止し、起動失敗・結果欠損は`failed`として承認しない。未完了ステージを`missing_stage`として記録しても、保存失敗を成功扱いしない。

`normalize` / `score` が終了コード1を返した場合も、内容を確認し可能なら1回だけ修正・再実行を試みる。それでも解決しない場合は諦めて手順8に進む。

`collect` はSource単位の失敗を継続処理する設計であり、`run_state.json` の `errors` にSource単位のエラー(例: 特定Sourceの HTTP エラー)が記録されていても、`collect` コマンド自体は正常に終了コード0を返す。この場合は**再実行しない**。個別Sourceのエラーは正常な運用結果であり、他のSourceの収集結果はそのまま後続手順(`normalize`以降)に使ってよい。`collect` を再実行してよいのは、コマンド自体が終了コード1を返した場合(`invalid`な引数など、通常は発生しない)のみである。

「エラー時の自己修正方針」が扱うのは構文・スキーマレベルの自己修正のみである。選抜内容や記事企画の「質」の妥当性を判断する別Agentによるレビュー・修正は、手順9〜10(品質レビューループ)で扱う。

## 完了確認

- `report` の標準出力(生成されたレポートのパス)を確認する。
- `data/runs/<date>/run_state.json` の `errors` を確認し、`missing_stage` 以外の重大なエラーが残っていないか確認する。
- 手順9〜10の品質レビューループが承認済みで終わったか、`needs_review: true` 付きで終わったかを確認する(いずれの場合もパイプライン自体は完了とみなしてよい)。
