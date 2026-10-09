---
name: agent-daily-run
description: Use when cron等からAgentとして日次調査パイプラインを実行し、HOT最終選抜と記事企画をAgent自身の判断で行うとき。
---

# Agent Daily Run

## 目的

`ai-radar` CLIのサブコマンド(`collect` / `normalize` / `score` / `select-hot` / `save-proposals` / `add-summary` / `add-source-overview` / `report`)を順に呼び出し、HOT最終選抜、選抜HOT・注目候補・新モデルリリースの日本語概要、収集Source一覧のSourceごとの「本日の傾向」、記事企画をAgent自身の判断で作り、日次レポートを完成させる。

`ai-radar daily` は決定論的な一括実行コマンドであり、このSkillでは使わない。

## 前提Skill参照

- HOT選抜の判断基準: [skills/hot-detection/SKILL.md](../hot-detection/SKILL.md) の「判断方針」(通常0〜2件、多い日でも最大5件程度、全Candidateをそのまま通知しない、重大Official Eventはスコアだけに依存させない)を用いる。
- 記事企画の観点: [skills/article-ideation/SKILL.md](../article-ideation/SKILL.md) の「企画観点」(Technical Explainer / Hands-on / Comparison / Benchmark / Critical Review)と「レビュー観点」(Evidence URLなしの主張をしない、「使ってみた」だけに偏らない、日本語記事としての独自性)を用いる。

このSkillはこれらの判断基準を再掲しない。実行前に上記2つのSkillを読むこと。

## 実行手順

実行時は`SelectionInput`と`ProposalQuality`を[03章](../../docs/specs/03-data-model-and-storage.md)の共通契約として使う。選抜0件(`selection_input.json` に `decision: selected` がない)・企画0件(`"proposals": []`。選抜HOTがある日は `deferral_reason` に理由を書く。手順6参照)は未実施または保留の結果として保存し、成功したことに置き換えない。品質レビューは別プロセスのレビュー担当に任せ、`data/runs/<date>/review_feedback.md` の有無だけで承認・要修正を判定する(手順9)。初回を1回目として最大3回まで修正し、レビュー担当の起動失敗や3回後に残った指摘を承認扱いにしない。

コマンドが失敗したとき、ファイルが壊れていたとき、レビューで指摘を受けたときの対応は [recovery.md](recovery.md) にまとめている。**どのコマンドでも終了コード1で終わったとき、または `run_state.json` の `errors` を見てコマンドの再実行を考えたときは、再実行する前に必ず recovery.md を読む**(再実行の回数の上限と、再実行してはいけない場合が書いてある)。各手順で「recovery.md の〜」とある場合も同じ。

1. 対象日を判定する。`date +%F` を実行し、今日の日付(`YYYY-MM-DD`)を取得する。以降の手順ではこの日付を `<date>` として使う。`collect` の `--since` / `--until` は省略し、前回実行の終了時刻から実行時刻までを収集する(最大7日、初回も7日分)。明示的な期間で再実行する必要がある場合だけ、タイムゾーン付きISO 8601日時または日付を指定する。

   ```bash
   ai-radar collect --data-dir data --sources-config config/sources.yaml
   ```

   `--since` / `--until` は省略する(省略時は前回実行から引き継いだ期間。詳細は `docs/specs/06-cli-and-operations.md`)。

   `collect` は特定のSourceの取得に失敗しても終了コード0で終わり、`run_state.json` の `errors` にそのSourceのエラーを残す。この場合は再実行せずに手順2へ進む(recovery.md の「エラー時の自己修正方針」)。

2. 正規化する。

   ```bash
   ai-radar normalize --date <date>
   ```

   失敗したら(終了コード1)、recovery.md の「エラー時の自己修正方針」に従う。

3. HOTスコアを計算する(まだ選抜はしない)。

   ```bash
   ai-radar score --date <date> --scoring-config config/scoring.yaml
   ```

   失敗したら(終了コード1)、recovery.md の「エラー時の自己修正方針」に従う。

4. `data/runs/<date>/hot_candidates.jsonl` を読み、hot-detection Skillの判断方針に従って候補を確認し、判断を `data/runs/<date>/selection_input.json` に書く。

   `hot_candidates.jsonl` 自体が壊れていて読めない場合は、自分で直さず、候補0件の内容(下記)で `selection_input.json` を書いて手順5を実行する。`select-hot` が `corrupt_input` を記録するので、recovery.md の「壊れた入力(`corrupt_input`)」に従う。このとき書いた候補0件の `selection_input.json` は仮のものなので、流し直しで作り直した候補に対しては再利用せず、手順4に従って書き直す。

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

     - 手順4〜9で行ったURLの取得は、成功・失敗・bot対策ページを問わず、1回につき1行を追記する。根拠の確認、概要を書くための確認、手順5の警告対応、手順8bの概要補完、手順8cで傾向を書くためのリンク先の確認、手順9の修正ループでの再取得を含む。既存の行は上書きしない。
     - `url`: 要求したURL(リダイレクト後の最終URLではない。根拠に使う場合は `EvidenceCheck` の `url` と同じ値)。
     - `http_status`: HTTPステータスコード。接続失敗(`curl` の出力が `000`)や、使ったツールがステータスを返さない場合は `-`。
     - `fetched_at`: 取得直後に `date -u +%Y-%m-%dT%H:%M:%S+00:00` で得た値。根拠に使う場合は、`EvidenceCheck` の `checked_at` と同じ値を書く。
     - `content_verified`: 本文そのもの(bot対策ページやエラーページではない内容)を取得して読めたら `true`、できなければ `false`。版が対象と一致したかは問わない(版の不一致は根拠の `status` で表す)。
     - `note`: 補足。`content_verified` が `false` のときは理由を必ず書く(例: `bot対策ページ(Client Challenge)`)。タブ・改行は空白に置き換える。

   あわせて、`hot_candidates.jsonl` の **全候補**(選抜しない候補も含む)について、レポートに載せる日本語の概要を書き、`summaries` に `hot_id` をキーとして入れる。選抜外の候補も翌日以降まで「注目候補」としてレポートに載るためである。`summaries` に書かなかった候補は前回保存した概要を保持し、書いた候補は置き換わる。`summaries` のキーは `hot_candidates.jsonl` にある `hot_id` に限り、値は空でない文字列にする(違反すると `invalid_summary`)。

   - 内容: 2〜3文、おおむね150字以内で「それが何か」「何が新しい・変わったか」を書く。Reasons(選抜した/しなかった理由)の繰り返しや、タイトルの直訳だけにしない。
   - 根拠: 評価のために読んだ一次情報(Evidence URLの中身)に基づいて書く。一次情報を取得できなかった場合(403など)は、取得できた範囲(報道記事など)で書き、「一次情報未確認」と明記する。PyPI候補では、JSON APIで取得したメタデータが一次情報である。何も取得できなかった場合は「概要未作成(情報取得失敗: HTTP 403)」のように理由を書く。取得したページの本文は `data/runs/<date>/` に保存しない(上の例のとおり `mktemp` の一時ファイルを使う)。`data/runs/<date>/` に残すのは取得ログ `evidence_fetch_log.tsv` だけである。手順8bでも同じ。
   - 確認できた事実と、発表元・報道の主張を区別する(例: 「〜と発表している」「〜と報じられている」)。

5. 選抜結果を確定する。

   ```bash
   ai-radar select-hot --date <date>
   ```

   失敗したら(終了コード1)、recovery.md の「エラー時の自己修正方針」に従う。

   `data/runs/<date>/selection_input.json` を読み、評価レコードと概要を `hot_candidates.jsonl` に保存する。3件以上選抜する理由があるときだけ `--limit <n>`(最大5)を付ける(例: `ai-radar select-hot --date <date> --limit 3`)。

   選抜・理由・概要はすべて `selection_input.json` に書く(`select-hot` に選抜を指定する引数はない)。

   `selection_input.json` はその日の判断の全体を表す。`select-hot` は実行のたびに、このファイルの内容で全候補の `selected` と評価レコードを置き換える(評価レコードがない候補は未選抜・未評価に戻る)。再実行するときは、既存の評価レコードを残したまま追加・修正する。評価を書き直した場合は、`assessed_at` を取り直す。

   終了コード0でも、`data/runs/<date>/run_state.json` の `errors` に次の警告が残る場合がある。それぞれ1回だけ `selection_input.json` を直して手順5を再実行し、それでも残る警告はそのままにして手順6へ進む(警告は失敗ではない)。

   - `missing_summary_warning`: メッセージに出た選抜外の候補の概要を `summaries` に追加する。内容を確認できなかった候補(下の `unreviewed_candidates` の対象)は、推測で書かず「概要未作成(未確認: 時間内に確認できず)」と書く。
   - `unreviewed_candidates`: メッセージに出た未確認の候補を確認し、評価レコードを `assessments` に、`hot_id` を `screened_ids` に追加する。時間内に確認しきれない場合は、確認した範囲(何件中何件を確認したか)を `selection_reason` に書いて警告を残したまま進む。確認していない候補を `rejected` として書いて警告を消してはならない。

   選抜した候補に概要がない場合は `missing_summary` で失敗する。

6. 記事企画を作成する。

   `data/runs/<date>/draft_proposals.json` に、次の形式(v2)のJSONオブジェクトを書く。配列や、トップレベルに `schema_version: 2` がない入力は手順7が `invalid_input` で、`schema_version: 2` のない企画は `invalid_proposal` で失敗する。

   ```json
   {
     "schema_version": 2,
     "proposals": [ /* 企画(下記) */ ],
     "deferral_reason": "選抜HOTがあるのに企画を作らない理由(その場合だけ書く)"
   }
   ```

   どの形にするかは、`data/runs/<date>/hot_candidates.jsonl` に `selected: true` の候補があるかで決める(`save-proposals` はこのファイルの選抜で照合する)。`hot_candidates.jsonl` が壊れていて読めない場合(`select-hot` が `corrupt_input` で `failed` のまま進む場合)は、選抜HOTがない日として扱う(手順7の `save-proposals` も `corrupt_input` で `failed` になるが、recovery.md の「壊れた入力(`corrupt_input`)」の決まりに従う)。

   - 選抜HOTがない日(手順5の `select-hot` が成功して選抜0件の日、または手順5の `select-hot` が再実行の上限(`corrupt_input` の場合は recovery.md の「壊れた入力(`corrupt_input`)」の流し直しの1回)に達して `failed` のまま進み、`hot_candidates.jsonl` に選抜がない日): 企画を作らずに `{"schema_version": 2, "proposals": []}` を書いて手順7へ進む。`deferral_reason` は書かない(書くと `invalid_input` で失敗する)。手順7は省略しない(`save-proposals` が `run_state.json` の `stage_results` に「選抜HOTなし」を記録し、`report` が `missing_stage` を記録しないようにするため)。`select-hot` が `failed` のときは `selection_input.json` の `selected` に対して企画を作らない(`hot_candidates.jsonl` で選抜されていないため `invalid_proposal` になる)。
   - 選抜HOTがあるのに企画を作らない日: `proposals` を `[]` にし、`deferral_reason` に作らない理由(例: 「一次情報で機能を確認できず、検証の問いを立てられないため保留」)を書く。理由はレポートに「記事企画なし(保留: <理由>)」として出る。作れない理由がない限り各選抜HOTに企画を作る。
   - それ以外(企画を1件以上作る日): `deferral_reason` を書かない(書くと `invalid_input` で失敗する)。

   選抜された各候補について、article-ideation Skillの企画観点に従って企画を作り、`proposals` に入れる。候補1件あたり0〜3件とし、数を埋めず、問いや実験が同じ案は統合する(4件以上は `invalid_proposal`)。

   各企画には次をすべて書く。

   - `schema_version`: `2`(整数)
   - 文字列(空にしない): `proposal_id`(入力内で重複させない)/ `source_hot_id` / `title_idea` / `article_type` / `target_reader` / `why_now` / `technical_angle` / `competition` / `traffic_opportunity` / `technical_opportunity` / `unique_angle`
   - 文字列のリスト: `experiment_plan` / `risks` / `evidence_links`(文字列1つを渡さず、1件でもリストにする)
   - `quality`: 企画の品質記録(形式は [03章「ProposalQuality」](../../docs/specs/03-data-model-and-storage.md)。書き方の観点は article-ideation Skill)
     - 空にしない文字列: `question`(検証の問い)/ `difference`(既存手段との差分)/ `baseline`(比較対象)/ `baseline_version`(比較対象の版。版がなければ固定日や条件)/ `measurement`(測定方法)/ `inputs_and_environment`(入力・環境・手順)/ `effort`(概算工数)/ `effort_assumptions`(工数の前提)/ `success_condition`(成功条件)/ `stop_condition`(中止・保留条件)
     - `metrics`: 測定指標(空にしない文字列のリスト、1件以上)
     - `evidence`: 確認した根拠(`EvidenceCheck` のリスト。キーは `url` / `checked_at` / `target_version` / `status` / `kind` / `claim` / `note` の7つちょうど。書き方は手順4の評価レコードの根拠と同じで、URLを取得したら取得ログに1行追記する)
     - `unknowns`: 未確認事項(文字列のリスト。空リスト可)

   企画1件の例(比較対象のURLを1件追加した場合):

   ```json
   {
     "schema_version": 2,
     "proposal_id": "hot:event:example-model-release:proposal:1",
     "source_hot_id": "hot:event:example-model-release",
     "title_idea": "Example LLM v2.0は長文要約で前版より速くなったか",
     "article_type": "Benchmark",
     "target_reader": "LLMを組み込んだアプリを運用しているAIエンジニア",
     "why_now": "APIの既定モデルがv2.0に切り替わり、既存アプリの挙動が変わるため",
     "technical_angle": "同じ入力でv1.5とv2.0の応答時間と要約の欠落を比べる",
     "experiment_plan": ["公開データセットから長文50件を選ぶ", "v1.5とv2.0で要約を生成する", "応答時間と欠落数を表にする"],
     "competition": "未調査",
     "traffic_opportunity": "未調査",
     "technical_opportunity": "既定モデル切り替えの影響を測定値で示せる",
     "unique_angle": "日本語の長文で測る",
     "evidence_links": ["https://example.com/blog/model-release", "https://example.com/docs/v1.5"],
     "risks": ["API料金がかかる"],
     "quality": {
       "question": "v2.0は日本語の長文要約でv1.5より速く、欠落が少ないか",
       "difference": "公式発表は英語ベンチマークのみで、日本語長文の比較がない",
       "baseline": "Example LLM v1.5",
       "baseline_version": "v1.5",
       "measurement": "50件の応答時間の中央値と、人手で数えた要約の欠落数",
       "inputs_and_environment": "公開データセットXの長文50件、Python 3.13、APIの既定パラメータ",
       "effort": "2日",
       "effort_assumptions": "v1.5が引き続きAPIで指定できる",
       "success_condition": "両版の測定値を同じ条件でそろえられる",
       "stop_condition": "v1.5がAPIで指定できなくなった場合は保留する",
       "metrics": ["応答時間の中央値", "要約の欠落数"],
       "evidence": [
         {"url": "https://example.com/blog/model-release", "checked_at": "2026-10-05T01:20:10+00:00", "target_version": "v2.0", "status": "verified", "kind": "primary", "claim": "v2.0を公開し、APIの既定モデルを切り替えた", "note": ""},
         {"url": "https://example.com/docs/v1.5", "checked_at": "2026-10-05T01:40:02+00:00", "target_version": "v1.5", "status": "verified", "kind": "primary", "claim": "比較対象 v1.5 の仕様(指定方法と提供期限)", "note": ""}
       ],
       "unknowns": ["v1.5の提供終了日"]
     }
   }
   ```

   次の規則を守る(守らないと手順7が `invalid_proposal` で失敗する)。

   - `source_hot_id` は `hot_candidates.jsonl` で `selected: true` の `hot_id` と一致させる。
   - `evidence_links` には、元のHOT候補の `evidence_urls` を1件以上含める。各URLは `http://` または `https://` で始まる完全なURL。
   - 比較対象などのために、元のHOT候補の `evidence_urls` にないURLを `evidence_links` に追加した場合は、同じURLの根拠を `quality.evidence` に書き、その `claim` に役割を書く(例: 「比較対象 X の仕様」)。`claim` を空にしない。
   - 競合や読者需要(`competition` / `traffic_opportunity`)を調べていない場合は「未調査」と書く。HOT点数から一律に「High」などと推定しない。

7. 記事企画を保存する。

   ```bash
   ai-radar save-proposals --date <date> --input data/runs/<date>/draft_proposals.json
   ```

   失敗したら(終了コード1)、recovery.md の「エラー時の自己修正方針」に従う。

   選抜HOTがない日も `{"schema_version": 2, "proposals": []}` で実行する。`run_state.json` の `stage_results` に結果(企画あり=`completed`、選抜ありで企画0件=`deferred`(理由は `deferral_reason`)、選抜0件=`not_run`(選抜HOTなし))が記録される。

8. 注目候補・新モデルリリースの概要を補完し、Sourceごとの「本日の傾向」を書いてから、レポートを生成する。

   a. レポートに表示される注目候補・新モデルリリースのうち、概要がないもの(過去日の注目候補、当日の新モデルリリースなど)を一覧する。何も出力されなければ c へ進む。

      ```bash
      ai-radar report --date <date> --list-missing-summaries
      ```

      出力は1行1件のJSONで、`kind` で種類を見分ける。このコマンドは何もファイルを書き換えない。

      - `"kind": "notable"`(注目候補): `hot_id` / `title` / `first_seen` / `evidence_urls`
      - `"kind": "model_release"`(新モデルリリース): `key` / `title` / `provider` / `channel` / `url` / `first_seen`

      1回の実行の中で最初に実行した8aの出力で、`model_release` の行が30件を超えた場合は、その件数を控えておき、完了報告に書く(上限の追加や表示件数の削減を見直すきっかけにするため。手順9bから戻ったときの8aでは数え直さない)。

   b. 一覧の各項目の内容を確認して概要を書き、保存する。

      - 注目候補: `evidence_urls` のサイトにアクセスし、手順4と同じ基準で書く。
      - 新モデルリリース: `url` のサイトにアクセスし、1文・おおむね80字以内で書く。わかる範囲で「何のモデルか / 規模(パラメータ数など)/ ライセンス / 特徴」を書き、確認できなかった項目は書かない(推測で埋めない)。`url` が空の項目は `title` から推測せず、「概要未作成(情報取得失敗: URLなし)」と書く。
      - どちらも、URLの取得は手順4の「根拠の取得」に従い、1回ごとに取得ログ `data/runs/<date>/evidence_fetch_log.tsv` に1行追記する。PyPIの注目候補は、`evidence_urls` の `/project/` ページではなくJSON APIで取得する。
      - どちらも、一次情報を取得できない場合の書き方は手順4と同じ(取得できた範囲で書いて「一次情報未確認」と明記する。何も取得できなければ「概要未作成(情報取得失敗: HTTP 403)」のように理由を書く)。

      書いた概要は、`hot_id`(注目候補)または `key`(新モデルリリース)をキーとするJSONオブジェクトとして `data/runs/<date>/summary_input.json` に書き(既存の内容は今回の分で置き換えてよい)、保存する。キーは一覧の値をそのまま使う(新モデルリリースの `key` は正規化済みURLなので、`url` とは一致しないことがある)。

      ```json
      {"hot:event:...": "注目候補の概要", "https://huggingface.co/org/model": "新モデルリリースの概要"}
      ```

      ```bash
      ai-radar add-summary --date <date> --input data/runs/<date>/summary_input.json
      ```

      保存後に a を1回だけ再実行して、何も出力されないことを確認する。それでも残る項目は、推測で書かずに「概要未作成(未確認: 時間内に確認できず)」と書いて同じ方法で保存し、a を再実行せずに c へ進む。この回数は、手順9bから手順8に戻るたびと、recovery.md の「壊れた入力(`corrupt_input`)」の流し直しで手順8に戻ったときに数え直す。

   c. 収集Source一覧のSourceごとに「本日の傾向」を書き、保存する。

      レポート末尾の「収集Source一覧」は、各Signalのタイトル・概要を原文のまま並べる(翻訳・要約はしない)。その代わりに、各Sourceの見出し(`### <source> (N件)`)の直下に出す日本語の傾向を、収集1件以上のSourceごとに書く。

      まず、見出しと同じ名前・件数でSourceの一覧を出す(`run_state.json` の `sources` にないSourceのSignalは `other`、同じ名前のSourceが実在する場合は `_other` にまとめる)。

      ```bash
      python3 skills/agent-daily-run/list_source_signals.py <date>
      ```

      このスクリプトが「signals.jsonl を読めません」と出して終了コード1で終わった場合は、`data/normalized/<date>/signals.jsonl` が壊れている。ファイルを手で直したり、傾向を推測で書いたりせず、この手順cを飛ばして d へ進む(d の後の確認で `source: report` の `corrupt_input` として見つかり、recovery.md の「壊れた入力(`corrupt_input`)」に従って流し直す。流し直しの上限に達していれば、そのまま手順9へ進む。レポートの収集Source一覧は注記だけになり、傾向は表示されない)。

      続けて、件数が1件以上のSourceごとに、そのSourceの各Signalを `- タイトル | 概要(先頭200字) | URL` の形で出して読む(Source名は上の出力の見出しから `(N件)` を除いた名前)。

      ```bash
      python3 skills/agent-daily-run/list_source_signals.py <date> '<Source名>'
      ```

      - 対象: 件数が1件以上のSource。収集0件のSourceは書かない(レポートには「収集0件」と出る。0件のSourceを入力に含めると `invalid_overview` で全体が保存されない)。
      - 内容: 2〜3行(2〜3文)、おおむね200字以内で、「どんなテーマが多いか」「目立った項目」を書く。原文が英語以外(タイ語など)であっても日本語で書く。文の間に改行は入れなくてよい(入れた改行はレポートで `<br>` として表示される)。
      - 根拠: そのSourceの一覧(タイトル・概要)をすべて読んだうえで書く。タイトルと概要だけでは内容がわからない目立った項目は、必要ならリンク先を確認する(取得は手順4の「根拠の取得」に従い、取得ログに1行追記する)。一覧から読み取れない内容を推測で断定しない。

      書いた傾向は、Source名(見出しの `(N件)` を除いた名前)をキーとするJSONオブジェクトとして `data/runs/<date>/source_overview_input.json` に書き(既存の内容は今回の分で置き換えてよい)、保存する。保存したSourceの傾向は上書きされ、入力に含めなかったSourceの保存済みの傾向は残る。

      ```json
      {"github": "エージェント実行基盤とMCP関連のリポジトリが多い。...", "arxiv": "..."}
      ```

      ```bash
      ai-radar add-source-overview --date <date> --input data/runs/<date>/source_overview_input.json
      ```

      手順9bから戻ってきた場合は、保存済みの傾向を書き直さなくてよい(指摘されたSourceは手順9bで直す)。`data/runs/<date>/source_overviews.json` にない、収集1件以上のSourceがあれば、それだけを書いて保存する。ただし、recovery.md の「壊れた入力(`corrupt_input`)」の流し直しで `collect` または `normalize` から流し直した後(手順9bの中で起きた場合を含む)は、Signalと件数が変わっているため、保存済みの傾向も含めて収集1件以上のすべてのSourceについて書き直して保存する。

      書くSourceが1つもない場合(収集1件以上のSourceがない日、または手順9bから戻って未保存のSourceがない場合)は、`add-source-overview` を実行せずに d へ進む(空のオブジェクト `{}` を渡すと `invalid_overview` で失敗する)。

      `add-source-overview` が失敗した場合は recovery.md の「エラー時の自己修正方針」に従う(`corrupt_input` は同じファイルの「壊れた入力(`corrupt_input`)」に従う)。再実行・流し直しの上限に達した場合は、保存できなかったSourceは「傾向未作成」のまま d へ進む。

   d. レポートを生成する。

      生成する前に `data/runs/<date>/run_state.json` の `stage_results` を確認する。`select-hot` が `completed` / `deferred`、`save-proposals` が `completed` / `deferred` / `not_run`(理由: 選抜HOTなし)であれば(記録がない旧形式の `run_state.json` も)、そのまま生成する。それ以外の場合は、[recovery.md](recovery.md) の「レポート生成前の補完実行」に従ってから生成する。

      ```bash
      ai-radar report --date <date> --reports-dir reports
      ```

      生成した後、`data/runs/<date>/run_state.json` の `errors` に `source: report` かつ `type: corrupt_input` の記録があるか確認する。`report` は当日の `hot_candidates.jsonl` / `article_proposals.jsonl` / `data/normalized/<date>/signals.jsonl` が壊れていても、終了コード0でレポートを生成する(該当セクションに「<ファイル名> を読めなかったため表示できません(Errors を参照)。」と出る)ため、終了コードだけでは気づけない。`report` は実行のたびに自分の記録(`source: report`)を消して記録し直すため、ここで見える記録は直前の `report` の実行で見つかったものである。
      - 記録があり、recovery.md の「壊れた入力(`corrupt_input`)」の流し直しをまだ行っていない場合: それに従って流し直し(手順8のa〜dのやり直しを含む)、この確認をもう一度行う。
      - 記録があり、流し直しを行った後の場合(上限到達): 何もせず、記録を残したまま手順9へ進む。

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
        記事企画・概要の書き直しなど必要な修正を自分自身で行う。修正の仕方は [recovery.md](recovery.md) の「レビュー指摘の直し方」に従う。

        recovery.md で手順10へ進むとされた場合を除き、手順8のa〜d(概要の補完、本日の傾向の作成、レポート生成)をやり直して手順9のa(レビュー担当の起動)に戻る。
      - 存在する場合、かつこれが3回目の試行だった場合: 手順10へ進む。

10. 3回試行しても `data/runs/<date>/review_feedback.md` が残っている場合、または手順9bで修正不能な指摘(上限到達の `failed` / `corrupt_input`)だけが残った場合は、未解消であることを記録し、レポートを生成し直す。

    ```bash
    ai-radar mark-needs-review --date <date>
    ```

    ```bash
    ai-radar report --date <date> --reports-dir reports
    ```

    `mark-needs-review` は `run_state.json` に `needs_review: true` を記録する。`report` はこれを読み、レポートの冒頭に「⚠️ 要確認」の警告と `review_feedback.md` の場所を出す。レポートや `run_state.json` を手で編集しない。

## 完了確認

- `report` の標準出力(生成されたレポートのパス)を確認する。
- `data/runs/<date>/run_state.json` の `errors` を確認し、`missing_stage` 以外の重大なエラーが残っていないか確認する。`missing_summary_warning` / `unreviewed_candidates` は警告であり、手順5の対応を済ませ、未確認が残る場合は確認範囲を `selection_reason` に書いていれば、残っていても完了としてよい。
- `data/runs/<date>/run_state.json` の `stage_results` に `failed` が残っている場合は、完了報告にそのステージと理由を書く(手順8dで上限まで再実行しても直らなかったもの)。
- `errors` に `corrupt_input` が残っている場合は、完了報告に壊れたファイルのパスとメッセージを書く(recovery.md の「壊れた入力(`corrupt_input`)」の流し直しでも直らなかったもの)。
- `errors` に `add-source-overview` のエラーが残っている場合、または手順8cを飛ばした場合は、「傾向未作成」のまま残ったSourceとその理由を完了報告に書く。
- 手順9〜10の品質レビューループが承認済みで終わったか、`needs_review: true` 付きで終わったかを確認する(いずれの場合もパイプライン自体は完了とみなしてよい)。
- 手順8aで控えた新モデルリリースの対象件数が30件を超えていた場合は、その件数を完了報告に含める。
