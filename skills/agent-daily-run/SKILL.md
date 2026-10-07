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

実行時は`SelectionInput`と`ProposalQuality`を[03章](../../docs/specs/03-data-model-and-storage.md)の共通契約として使う。選抜0件(`selection_input.json` に `decision: selected` がない)・空の企画`[]`は未実施または保留の結果として保存し、成功したことに置き換えない。レビュー対象は`review_target.json`で固定し、レビュー担当は原成果物を編集せず`review_result.json`だけを返す。初回をattempt 1として最大3回まで修正し、起動失敗・記録なし・3回後の重要指摘は承認しない。

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

4. `data/runs/<date>/hot_candidates.jsonl` を読み、hot-detection Skillの判断方針に従って候補を確認し、判断を `data/runs/<date>/selection_input.json` に書く。

   例(候補を1件確認して選抜した場合。`hot_id` は `hot_candidates.jsonl` の値をそのまま使う):

   ```json
   {
     "assessments": [
       {
         "hot_id": "hot:event:example-model-release",
         "decision": "selected",
         "assessed_at": "2026-10-05T01:23:45+00:00",
         "assessor": "claude-code",
         "relevance": {
           "status": "related",
           "matched_terms": ["LLM", "release"],
           "reason": "汎用LLMの新バージョン公開であり、AIエンジニア向けの調査対象に該当する",
           "method": "agent"
         },
         "novelty": "前バージョンからコンテキスト長と推論性能が更新された",
         "importance": "主要ベンダーの公式リリースで、APIの既定モデルが切り替わる",
         "reader_impact": "既存アプリのモデル指定と料金見積もりの見直しが必要になる",
         "reason": "公式発表で公開事実と変更点を確認でき、読者への影響が大きいため選抜する",
         "evidence": [
           {
             "url": "https://example.com/blog/model-release",
             "checked_at": "2026-10-05T01:20:10+00:00",
             "target_version": "v2.0",
             "status": "verified",
             "kind": "primary",
             "claim": "v2.0を公開し、APIの既定モデルを切り替えた",
             "note": "公式ブログ。HTTP 200、本文で発表内容を確認"
           }
         ],
         "unknowns": ["発表元のベンチマーク値は独立に検証していない"]
       }
     ],
     "screened_ids": ["hot:event:example-model-release"],
     "selection_reason": "1件を確認し、公式発表で変更点を確認できた1件を選抜した",
     "summaries": {
       "hot:event:example-model-release": "Example社の汎用LLMの新バージョン。コンテキスト長と推論性能が更新され、APIの既定モデルが切り替わったと発表している。"
     }
   }
   ```

   トップレベルのキーは `assessments` / `screened_ids` / `selection_reason`(必須)と `summaries`(任意)だけにする(それ以外のキーがあると `invalid_input`)。評価レコードの値は次のとおり。

   - `decision`: `selected`(選抜)/ `deferred`(保留。根拠が取得できない・未確認など)/ `rejected`(除外)のいずれか。
   - `assessor`: 自分の種別(`claude-code` または `codex`)。
   - `relevance`: `status` は `related` / `uncertain` / `unrelated`、`method` は `agent`、`matched_terms` は文字列の配列(なければ `[]`)、`reason` は空にしない。
   - `hot_id` / `assessed_at` / `assessor` / `novelty` / `importance` / `reader_impact` / `reason` は空でない文字列、`unknowns` は文字列の配列(なければ `[]`)。
   - `evidence` の各要素(`EvidenceCheck`)は、`url` / `checked_at` / `target_version` / `status` / `kind` / `claim` / `note` の7キーちょうどにする(過不足があると `invalid_assessment`)。
     - `url`: `http://` または `https://` で始まるURL。
     - `target_version`: 確認した対象のバージョン。特定できなければ `null`。
     - `status`: `verified`(内容を確認できた)/ `unavailable`(取得できなかった)/ `unverified`(取得したが主張を確認できていない)/ `unknown`。
     - `kind`: `primary`(発表元の一次情報)/ `independent`(独立した検証・報道)/ `republication`(転載・まとめ)/ `unknown`。
     - `claim`: そのURLで確認した(または確認しようとした)主張。`note`: 取得結果などの補足(なければ `""`)。

   記録の規則:

   - 内容を確認した候補は、すべて `screened_ids` に入れ、`assessments` に評価レコードを1件ずつ書く。両者の `hot_id` の集合は一致させる(食い違うと `invalid_assessment`)。
   - 確認しきれなかった候補は、`screened_ids` にも `assessments` にも入れない。この場合 `select-hot` は成功し、`unreviewed_candidates` 警告を記録する。確認していない候補を `rejected` として書かない。
   - `decision: selected` の評価レコードには、`status: verified` かつ `kind: primary` の根拠を1件以上含める(ないと `invalid_assessment`)。
   - 選抜は既定で2件まで(超えると `selection_limit_exceeded`)。3件以上選抜する場合は手順5の `--limit` を参照。
   - `selection_reason` は、選抜件数に関係なく常に空でない文字列で書く。選抜0件の日は、保留・除外とした理由を書く。確認しきれなかった候補がある日は、確認した範囲も書く。
   - 候補が0件の日も `{"assessments": [], "screened_ids": [], "selection_reason": "<候補0件の理由>"}` を書き、手順5を必ず実行する。

   判断の記録(`selection_input.json` の評価レコード)に書く日時は、推定や切りのよい値ではなく実測値にする。

   - 根拠の `checked_at`: そのURLを実際に取得した直後に `date -u +%Y-%m-%dT%H:%M:%S+00:00` を実行し、その出力を書く。複数URLをまとめて取得した場合は、それぞれの取得直後の値を使う。
   - 評価の `assessed_at`: その評価の根拠をすべて確認し終えた後、レコードを書く直前に同じコマンドで取得した値を書く(`checked_at` 以降、かつファイル保存前)。
   - 取得時刻を記録し忘れた根拠は、時刻を推定せずに取得し直してから記録する。
   - 取得したURL・HTTPステータス・時刻を、下の「根拠の取得」に従って `data/runs/<date>/evidence_fetch_log.tsv` に残し、記録した時刻をレビュー担当が裏付けられるようにする。

   根拠の取得(手順4〜9でURLを取得するときは、すべてこの規則に従う):

   - 取得方法: HTTPステータスと本文を確認できる `curl` を基本とする。保存先を変数に入れ、取得直後に時刻を取り、そのあと保存した本文を読んで内容を確認する(一般のページの例。冒頭だけで判断できなければ続きも読む)。

     ```bash
     tmp=$(mktemp); code=$(curl -sS -L -o "$tmp" -w '%{http_code}' '<URL>'); date -u +%Y-%m-%dT%H:%M:%S+00:00; echo "$code"; head -c 3000 "$tmp"
     ```

     PyPIのJSON APIは `info.description` が長く、`info.version` が後ろにあるため、`head` で切らずに次のように取り出す:

     ```bash
     python3 -c "import json,sys;i=json.load(open(sys.argv[1]))['info'];print(i['version']);print(i['summary'])" "$tmp"
     ```

   - 根拠(`EvidenceCheck`)は、すべて実際に取得してから記録する。取得していないURLを根拠に書かない。
   - HTTP 200でも、本文がbot対策ページ(「Client Challenge」「Just a moment」「captcha」など)のように本文そのものを取得できなかった場合は、`status` を `unavailable` にし、`note` に理由を書く。HTTPステータスだけを見て `verified` にしない。
   - `target_version` を特定している根拠で、本文は取得できたがその版を確認できなかった場合は、`status` を `unverified` にする(版の概念がない根拠には当てはめない)。
   - PyPIの候補は、`https://pypi.org/project/...` のページ(bot対策ページを返す)ではなく、JSON APIで確認する。
     - 候補のタイトル・URL・`hot_candidates.jsonl` の内容から版を特定できる場合は `https://pypi.org/pypi/<name>/<version>/json`、特定できない場合だけ `https://pypi.org/pypi/<name>/json` を使う。
     - `info.version` で対象の版を、`info.summary`(必要なら `info.description` と `info.project_urls`)で用途を確認する。
     - 版を指定しないAPIの `info.version`(最新版)が対象の版と違う場合は、版付きのAPIで取り直してよい(取り直した結果で記録する)。取り直さない場合は `unverified` にする。
     - 版付きのAPIが404などで取得できない場合は、`unavailable` にし、`note` にHTTPステータスを書く。
     - 根拠の記録: `url` は実際に取得したJSON APIのURL、`kind` は `primary`(配布元である公式レジストリのメタデータのため)、`target_version` は対象の版、`note` は取得した `info.version`(例: `PyPI JSON API, info.version=4.2.8`)。
     - 候補の `evidence_urls`(レポートの見出しや注目候補のリンク)は、人が見る `/project/` ページのままでよい。選抜HOTの評価の根拠の行には、記録したとおりJSON APIのURLが出る。
   - 取得ログ `data/runs/<date>/evidence_fetch_log.tsv`(タブ区切り):
     - ファイルが無いときだけ、ヘッダー行 `url	http_status	fetched_at	content_verified	note` を書く。
     - ヘッダーと各行は、Edit / Writeツールでは書かず(区切りのタブが空白に化けるおそれがあるため)、次のように `printf` で追記する。

       ```bash
       f=data/runs/<date>/evidence_fetch_log.tsv; [ -f "$f" ] || printf 'url\thttp_status\tfetched_at\tcontent_verified\tnote\n' > "$f"; printf '%s\t%s\t%s\t%s\t%s\n' '<URL>' '<http_status>' '<fetched_at>' '<true|false>' '<note>' >> "$f"
       ```

       `<http_status>` には取得時に表示したステータスを書く(`000` は `-`)。`<true|false>` は下の `content_verified` の定義に従う。`note` に `'` を含めない(含む場合は空白に置き換える)。

     - 手順4〜9で行ったURLの取得は、成功・失敗・bot対策ページを問わず、1回につき1行を追記する。根拠の確認、概要を書くための確認、手順5の警告対応、手順8bの概要補完、手順9の修正ループでの再取得を含む。既存の行は上書きしない。
     - `url`: 要求したURL(リダイレクト後の最終URLではない。`EvidenceCheck` の `url` と同じ値)。
     - `http_status`: HTTPステータスコード。接続失敗(`curl` の出力が `000`)や、使ったツールがステータスを返さない場合は `-`。
     - `fetched_at`: 取得直後に `date -u +%Y-%m-%dT%H:%M:%S+00:00` で得た値。根拠に使う場合は、`EvidenceCheck` の `checked_at` と同じ値を書く。
     - `content_verified`: 本文そのもの(bot対策ページやエラーページではない内容)を取得して読めたら `true`、できなければ `false`。版が対象と一致したかは問わない(版の不一致は根拠の `status` で表す)。
     - `note`: 補足。`content_verified` が `false` のときは理由を必ず書く(例: `bot対策ページ(Client Challenge)`)。タブ・改行は空白に置き換える。

   あわせて、`hot_candidates.jsonl` の **全候補**(選抜しない候補も含む)について、レポートに載せる日本語の概要を書き、`summaries` に `hot_id` をキーとして入れる。選抜外の候補も翌日以降まで「注目候補」としてレポートに載るためである。`summaries` に書かなかった候補は前回保存した概要を保持し、書いた候補は置き換わる。`summaries` のキーは `hot_candidates.jsonl` にある `hot_id` に限り、値は空でない文字列にする(違反すると `invalid_summary`)。

   - 内容: 2〜3文、おおむね150字以内で「それが何か」「何が新しい・変わったか」を書く。Reasons(選抜した/しなかった理由)の繰り返しや、タイトルの直訳だけにしない。
   - 根拠: 評価のために読んだ一次情報(Evidence URLの中身)に基づいて書く。一次情報を取得できなかった場合(403など)は、取得できた範囲(報道記事など)で書き、「一次情報未確認」と明記する。PyPI候補では、JSON APIで取得したメタデータが一次情報である。何も取得できなかった場合は「概要未作成(情報取得失敗: HTTP 403)」のように理由を書く。
   - 確認できた事実と、発表元・報道の主張を区別する(例: 「〜と発表している」「〜と報じられている」)。

5. 選抜結果を確定する。

   ```bash
   ai-radar select-hot --date <date>
   ```

   `data/runs/<date>/selection_input.json` を読み、評価レコードと概要を `hot_candidates.jsonl` に保存する。3件以上選抜する理由があるときだけ `--limit <n>`(最大5)を付ける(例: `ai-radar select-hot --date <date> --limit 3`)。

   `--select` / `--reason` / `--summary` は廃止され、指定すると `deprecated_option` で失敗する。選抜・理由・概要はすべて `selection_input.json` に書く。

   `selection_input.json` はその日の判断の全体を表す。`select-hot` は実行のたびに、このファイルの内容で全候補の `selected` と評価レコードを置き換える(評価レコードがない候補は未選抜・未評価に戻る)。再実行するときは、既存の評価レコードを残したまま追加・修正する。評価を書き直した場合は、`assessed_at` を取り直す。

   終了コード0でも、`data/runs/<date>/run_state.json` の `errors` に次の警告が残る場合がある。それぞれ1回だけ `selection_input.json` を直して手順5を再実行し、それでも残る警告はそのままにして手順6へ進む(警告は失敗ではない)。

   - `missing_summary_warning`: メッセージに出た選抜外の候補の概要を `summaries` に追加する。内容を確認できなかった候補(下の `unreviewed_candidates` の対象)は、推測で書かず「概要未作成(未確認: 時間内に確認できず)」と書く。
   - `unreviewed_candidates`: メッセージに出た未確認の候補を確認し、評価レコードを `assessments` に、`hot_id` を `screened_ids` に追加する。時間内に確認しきれない場合は、確認した範囲(何件中何件を確認したか)を `selection_reason` に書いて警告を残したまま進む。確認していない候補を `rejected` として書いて警告を消してはならない。

   選抜した候補に概要がない場合は `missing_summary` で失敗する。

6. 記事企画を作成する。

   選抜0件の日(手順5の `select-hot` が成功し、`hot_candidates.jsonl` に `selected: true` の候補がない日)は、企画を作らずに `data/runs/<date>/draft_proposals.json` に空の配列 `[]` を書いて手順7へ進む。手順7は省略しない(`save-proposals` が `run_state.json` の `stage_results` に「選抜HOTなし」を記録し、`report` が `missing_stage` を記録しないようにするため)。

   手順5の `select-hot` が再実行の上限に達して `failed` のまま進む場合は、企画を作らずに `draft_proposals.json` に `[]` を書いて手順7を実行する(`save-proposals` は `hot_candidates.jsonl` の選抜で照合するため、`selection_input.json` の `selected` に対する企画は `invalid_proposal` になる)。

   選抜HOTがあるのに企画を作らない(`[]` を書く)場合、レポートに「記事企画なし(保留: 理由未記載)」と出てレビューで指摘されうるため、作れない理由がない限り各選抜HOTに企画を作る。

   選抜された各候補について、article-ideation Skillの企画観点に従って `ArticleProposal` 形式のJSON配列を作成し、`data/runs/<date>/draft_proposals.json` に書き出す。候補1件あたり1〜3件程度の企画に絞る(既存の決定論的Ideation実装の上限である3件を目安とし、通知疲れを避ける)。

   `ArticleProposal` の必須フィールド: `proposal_id` / `source_hot_id` / `title_idea` / `article_type` / `target_reader` / `why_now` / `technical_angle` / `experiment_plan` / `competition` / `traffic_opportunity` / `technical_opportunity` / `unique_angle` / `evidence_links` / `risks`。

   - `source_hot_id` は手順5で選抜した `hot_id` と一致させる。
   - `evidence_links` は空にしない(選抜候補の `evidence_urls` を引き継ぐ)。

7. 記事企画を保存する。

   ```bash
   ai-radar save-proposals --date <date> --input data/runs/<date>/draft_proposals.json
   ```

   選抜0件の日も `[]` で実行する。`run_state.json` の `stage_results` に結果(企画あり=`completed`、選抜ありで企画0件=`deferred`、選抜0件=`not_run`(選抜HOTなし))が記録される。入力は企画の配列で渡す。

8. 注目候補の概要を補完してから、レポートを生成する。

   a. レポートの注目候補に表示される項目のうち、概要がないもの(過去日の候補など)を一覧する。何も出力されなければ c へ進む。

      ```bash
      ai-radar report --date <date> --list-missing-summaries
      ```

      出力は1行1件のJSON(`hot_id` / `title` / `first_seen` / `evidence_urls`)。このコマンドは何もファイルを書き換えない。

   b. 一覧の各項目について `evidence_urls` のサイトにアクセスして内容を確認し、手順4と同じ基準で概要を書いて保存する(一次情報を取得できない場合の書き方も手順4と同じ)。取得は手順4の「根拠の取得」に従い、取得ログに1行ずつ追記する。PyPIの項目は `evidence_urls` の `/project/` ページではなく、JSON APIで取得する。

      ```bash
      ai-radar add-summary --date <date> --summary <hot_id>=<概要> [--summary ...]
      ```

      保存後に a を再実行し、何も出力されないことを確認する。

   c. レポートを生成する。

      生成する前に `data/runs/<date>/run_state.json` の `stage_results` を確認する。`select-hot` が `completed` / `deferred`、`save-proposals` が `completed` / `deferred` / `not_run`(理由: 選抜HOTなし)であれば、そのまま生成する。`stage_results` にそのステージの記録がない場合(旧形式の `run_state.json`)も、そのまま生成する。
      - `select-hot` が `not_run`(手順5を実行していない)の場合: `data/runs/<date>/hot_candidates.jsonl` があれば手順4〜7を1回だけ実行してから生成する。`normalize` / `score` の失敗で `hot_candidates.jsonl` がない場合は実行せずにそのまま生成する(レポートに「選抜は未実行」と出る)。
      - `save-proposals` が `not_run`(理由: 選抜の再実行により無効、または未実行)の場合: 手順7だけを再実行してから生成する(`draft_proposals.json` がなければ先に手順6で作る)。ただし、上の項目で手順4〜7を実行した場合、または `hot_candidates.jsonl` がなくそのまま生成へ進む場合は、手順7を重ねて実行しない。手順7の再実行は1回だけとし、失敗した場合は下の `failed` の項目に従う。
      - いずれかが `failed` の場合: 「エラー時の自己修正方針」に従って該当ステージだけを直して再実行する(回数の上限と数え方は同方針の項目3に従う)。上限に達している場合は、再実行せず `failed` を残したまま生成する(レポートに失敗として表示される)。

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
        記事企画・概要の書き直しなど必要な修正を自分自身で行う。修正の仕方は次のとおり。
        - HOT選抜・概要の修正: `selection_input.json` を書き直して `ai-radar select-hot` を再実行し、
          `select-hot` が成功したら続けて必ず手順7の `save-proposals` も再実行する(`select-hot` が成功すると、それまでの記事企画の記録は「選抜の再実行により無効」になるため。概要だけの修正でも同じ)。
          選抜した候補が変わった場合は、`save-proposals` の前に手順6に従って `draft_proposals.json` を作り直す(選抜0件になった場合は `[]`)。
          概要だけの修正で選抜が変わらない場合は、既存の `draft_proposals.json` のまま再実行してよい。
          `select-hot` が再実行の上限に達して `failed` のまま残った場合は、`draft_proposals.json` を書き換えず、`save-proposals` も再実行しない(`select-hot` の失敗では前回の選抜と記事企画の記録はそのまま残るため。手順6の `[]` を書く段落は手順5での失敗だけに当てはまる)。
        - 記事企画だけの修正: `draft_proposals.json` を書き直して手順7の `save-proposals` を再実行する。
        - 手順8bで補完した概要の修正: `add-summary` で同じ `hot_id` を再指定する(上書きされる)。
        - `stage_results` の `failed` が再実行の上限(「エラー時の自己修正方針」の項目3)に達したため残っていることへの指摘: 再実行せず、修正不能として扱う。
          `review_feedback.md` に他の指摘がなければ、手順8・9aに戻らず手順10へ進む。

        いずれの場合も(上の手順10へ進む場合を除く)手順8のa〜c(概要の補完とレポート生成)をやり直して手順9のa(レビュー担当の起動)に戻る。
      - 存在する場合、かつこれが3回目の試行だった場合: 手順10へ進む。

10. 3回試行しても `data/runs/<date>/review_feedback.md` が残っている場合、または手順9bで修正不能な指摘(上限到達の `failed`)だけが残った場合:

    - `reports/daily/<date>.md` の冒頭に次のバナーを追記する(間に空行を1行挟んで元の内容を続ける):

      ```
      > ⚠️ **要確認**: 自動レビューで解消できなかった指摘があります。`data/runs/<date>/review_feedback.md` を確認してください。
      ```
    - `data/runs/<date>/run_state.json` を読み、`needs_review: true` を追加して書き戻す(既存のキー順・インデント幅など、このパイプラインの他の箇所での `run_state.json` の書式と揃えること)。

## エラー時の自己修正方針

`select-hot` / `save-proposals` / `add-summary` がバリデーションエラー(終了コード1)を返した場合:

1. `data/runs/<date>/run_state.json` の `errors` を読み、エラー種別とメッセージを確認する。種別は次のとおり。
   - `select-hot`: `deprecated_option` / `missing_input` / `invalid_input` / `invalid_assessment` / `selection_limit_exceeded` / `invalid_summary` / `missing_summary` / `write_error`
   - `save-proposals`: `missing_input` / `invalid_input` / `invalid_proposal` / `write_error`
   - `add-summary`: `invalid_summary` / `write_error`
2. 原因に応じて `selection_input.json`・`draft_proposals.json`・概要を修正し、再実行する。
   - すでに手順7(`save-proposals`)を実行した後に `select-hot` を再実行して成功した場合は、続けて手順7も再実行する(選抜が変わった場合は先に手順6で `draft_proposals.json` を作り直す)。手順5の時点(まだ手順7を実行していない)では、通常どおり手順6へ進む。
   - `add-summary` が `write_error` で失敗し、メッセージから `data/runs/<date>/digest_summaries.json` が壊れていると分かる場合は、そのファイルを `digest_summaries.json.broken` に名前を変えて退避し、手順8aからやり直す(退避したファイルの概要は失われるため、一覧に出た項目の概要を書き直す)。
3. 再実行は最大3回までとする。「3回」は、同じステージが終了コード1で失敗した後の修正再実行の回数を、その日の実行全体(手順5・7・8c・9bを通算)で数える。9bでレビュー指摘を受けて行う再実行そのものは数えない(9bの試行回数3回で別に上限がある)。ただし、その再実行が失敗した後の修正再実行は数える。上限に達したステージは `failed` を残したまま先へ進む。品質レビュー(手順9)で3回試行しても重要指摘が残る場合の扱いは手順10に従う(この3回は手順9bの試行回数であり、上の再実行回数とは別に数える)。レビュー担当の起動失敗・結果欠損は承認しない。未完了ステージを`missing_stage`として記録しても、保存失敗を成功扱いしない。

`normalize` / `score` が終了コード1を返した場合も、内容を確認し可能なら1回だけ修正・再実行を試みる。それでも解決しない場合は諦めて手順8に進む。

`collect` はSource単位の失敗を継続処理する設計であり、`run_state.json` の `errors` にSource単位のエラー(例: 特定Sourceの HTTP エラー)が記録されていても、`collect` コマンド自体は正常に終了コード0を返す。この場合は**再実行しない**。個別Sourceのエラーは正常な運用結果であり、他のSourceの収集結果はそのまま後続手順(`normalize`以降)に使ってよい。`collect` を再実行してよいのは、コマンド自体が終了コード1を返した場合(`invalid`な引数など、通常は発生しない)のみである。

「エラー時の自己修正方針」が扱うのは構文・スキーマレベルの自己修正のみである。選抜内容や記事企画の「質」の妥当性を判断する別Agentによるレビュー・修正は、手順9〜10(品質レビューループ)で扱う。

## 完了確認

- `report` の標準出力(生成されたレポートのパス)を確認する。
- `data/runs/<date>/run_state.json` の `errors` を確認し、`missing_stage` 以外の重大なエラーが残っていないか確認する。`missing_summary_warning` / `unreviewed_candidates` は警告であり、手順5の対応を済ませ、未確認が残る場合は確認範囲を `selection_reason` に書いていれば、残っていても完了としてよい。
- `data/runs/<date>/run_state.json` の `stage_results` に `failed` が残っている場合は、完了報告にそのステージと理由を書く(手順8cで上限まで再実行しても直らなかったもの)。
- 手順9〜10の品質レビューループが承認済みで終わったか、`needs_review: true` 付きで終わったかを確認する(いずれの場合もパイプライン自体は完了とみなしてよい)。
