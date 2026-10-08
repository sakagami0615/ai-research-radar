# 03. データモデル・保存設計

## v2移行契約

既存レコードは`schema_version=1`として旧スコアと表示互換を保つ。旧読込時に欠損した`quality`を推測で補完しない。新規v2入力は共通decoderと`QualityValidationError`で型・状態・必須文字列を検証し、未知のschema versionは明示的に拒否する。日時はタイムゾーン付きISO 8601、JSONの`null`は未取得として保持する。各v2 dataclassの`quality`は末尾の既定値付きフィールドで後方互換を保つ。

成果物のidentityは`work_id`（同一成果）と`event_key`（版・観測の統合単位）を分ける。DOIがある場合は同一DOIを同一Eventへ統合し、arXivはv番号をEventに残しつつwork_idを共有する。Packageは名前と版をEventキーに含める。自動統合できない同名項目はSourceとsignal_idで分離する。

## 保存方針

MVPでは、人間が確認しやすく、再処理もしやすい形式を優先する。

- 構造化データ: JSONL
- 人間向けレポート: Markdown
- SQLite: 将来検討

JSONLは1行1レコードとし、日次実行ごとの成果物を日付ディレクトリに保存する。

## ディレクトリ構成

```text
data/
  raw/<date>/<source>.jsonl
  normalized/<date>/signals.jsonl
  events/<date>/events.jsonl
  topics/<date>/topics.jsonl
  runs/<date>/hot_candidates.jsonl
  runs/<date>/selection_input.json
  runs/<date>/summary_input.json
  runs/<date>/article_proposals.jsonl
  runs/<date>/run.jsonl
  runs/<date>/report_digest.json
  runs/<date>/digest_summaries.json
  runs/<date>/evidence_fetch_log.tsv

reports/
  daily/<date>.md
```

`runs/<date>/evidence_fetch_log.tsv` は、実行Agentが手順4〜9で取得したURLの記録(根拠の確認のほか、注目候補・新モデルリリースの概要補完での取得も含む。ヘッダー付きTSV。形式は09章 §5.1と `agent-daily-run` Skillの手順4)。CLIは読み書きしない。

## RawItem

Sourceから取得した未加工データを保持する。

主な項目:

- `source`
- `fetched_at`
- `raw_id`
- `raw_url`
- `payload`

`payload` には、正規化用の派生フィールドに加えて、元レスポンスを `raw` として保持する。これにより、正規化やスコアリングを後から改善して再処理できる。

## CanonicalSignal

Source横断で扱うSignalの共通形式。

主な項目:

- `signal_id`
- `source`
- `source_family`
- `content_type`
- `title`
- `url`
- `published_at`
- `fetched_at`
- `summary`
- `categories`
- `raw_metrics`
- `normalized_scores`
- `metadata`

`normalized_scores` には0から100の正規化済みスコアを入れる。Source内順位補正はPipelineで収集バッチ単位に実施する。

新モデルリリースとして扱うSignalは `metadata.model_release` を持つ。値は `{"provider": <提供元表示名>, "channel": "official" | "huggingface" | "ollama"}` で、記事から紹介モデル名がわかる場合(Ollamaブログ)は `models`(モデル名のリスト)も持つ。Adapterが付与し、Dedupで別Sourceと統合された場合も保持する(04章参照)。

## Event

重複排除後のSignalを、同じ出来事としてまとめた単位。

主な項目:

- `event_id`
- `title`
- `description`
- `event_type`
- `first_seen_at`
- `last_seen_at`
- `signals`
- `sources`
- `source_families`
- `scores`
- `evidence`

HOT判定はEventを入力にする。公式重大発表などは `event_type` と `source_families` を使って低スコアでも候補化できる。

## Topic

Eventを将来のトレンド分析へつなげるための集約単位。

主な項目:

- `topic_id`
- `name`
- `aliases`
- `categories`
- `related_topics`
- `events`
- `trend_history`
- `current_scores`
- `status`

MVPでは日次Topicの最小生成に留める。週次・月次分析ではTopic履歴を使って成長、継続、沈静化を判定する。

## HotCandidate

Eventから生成されるHOT候補。

主な項目:

- `hot_id`
- `title`
- `topic`
- `score`
- `reasons`
- `evidence_urls`
- `source_families`
- `signals`
- `selected`
- `assessment`: `selection_input.json` の評価レコード(下記「Assessment」)。`select-hot` が保存する。評価していない候補(未確認・決定論経路)と、この項目を持たない旧データは `null`。
- `summary`: 候補が何かを説明する日本語の概要(2〜3文、おおむね150字以内)。`agent-daily-run` のAgentが一次情報を読んで書き、`selection_input.json` の `summaries` から `select-hot` が保存する。未設定は空文字列で、この項目を持たない既存データも空文字列として読み込む。

`selected=True` の候補のみが日次レポートの中心になる。

## SelectionInput(selection_input.json)

`data/runs/<date>/selection_input.json` は、Agent経路でAgentがHOT候補を確認・評価した結果を書くJSONファイル。`ai-radar select-hot` が読み込み、検証してから `hot_candidates.jsonl` の `selected` / `assessment` / `summary` に反映する(引数とエラー種別は06章「Agent経路のサブコマンド」参照)。型は `schemas/quality.py` の `SelectionInput`。

```json
{
  "assessments": [{"hot_id": "hot:event:...", "decision": "selected", "...": "..."}],
  "screened_ids": ["hot:event:..."],
  "selection_reason": "当日の選抜方針・確認範囲の説明",
  "summaries": {"hot:event:...": "概要の本文"}
}
```

- `assessments`(必須): 評価レコード(下記「Assessment」)のリスト。
- `screened_ids`(必須): 確認した候補の `hot_id` のリスト。
- `selection_reason`(必須): 選抜全体の理由・確認範囲。0件の日も書く。
- `summaries`(任意): `hot_id` から概要へのdict。省略時は `{}`。
- 上記以外のトップレベルキーはエラーにする(`summary` のような綴り間違いで概要が黙って無視されるのを防ぐため)。

検証は `scoring/assessments.py::apply_assessments` が次の順に行い、最初に見つかった誤りを `SelectionError`(`code` が `run_state.json` の `errors` の種別になる)として送出する。

| 順 | 条件 | 種別 |
| --- | --- | --- |
| 1 | 選抜上限 `limit` が整数でない、または0〜5の範囲外 | `invalid_input` |
| 2 | トップレベルの構造が不正(JSONオブジェクトでない、未知のキーがある、必須キーがない、`assessments` がリストでない、`screened_ids` が文字列のリストでない、`selection_reason` が文字列でない) | `invalid_input` |
| 3 | `selection_reason` が空白だけ | `invalid_assessment` |
| 4 | `screened_ids` が重複している、または当日の候補にない `hot_id` を含む | `invalid_assessment` |
| 5 | `assessments` の要素が `validate_assessment` を通らない(`EvidenceCheck` の検証を含む)、または `hot_id` が当日の候補にない・重複している | `invalid_assessment` |
| 6 | `screened_ids` の集合と評価レコードの `hot_id` の集合が一致しない(評価のない確認済みIDと、確認済みに含まれない評価IDの両方をメッセージに出す) | `invalid_assessment` |
| 7 | `decision: selected` の評価に、`status: verified` かつ `kind: primary` の根拠がない | `invalid_assessment` |
| 8 | 選抜件数が `limit` を超える | `selection_limit_exceeded` |

- 種別の境界: トップレベルの構造(キーの有無と各キーの値の型)の誤りは `invalid_input`、各キーの中身(空の理由、IDの重複・不整合、評価レコードの内容、根拠の条件)の誤りは `invalid_assessment` にする。`validate_assessment` の `QualityValidationError` は `invalid_assessment` に包み直す。
- `summaries` の検証(当日の候補にない `hot_id`、空または文字列でない値は `invalid_summary`)は `apply_assessments` の後に `select-hot` が行う。
- 検証を通った場合、各候補の `selected` は評価の `decision` が `selected` かどうかで決まり、`assessment` に評価レコードがそのまま入る。評価のない候補は `selected=False`、`assessment=null` になる。`screened_ids` に含まれない候補は未確認として件数を数える(06章の `unreviewed_candidates` 警告)。

### Assessment

候補1件の評価レコード。型は `schemas/quality.py` の `Assessment`、検証は `validate_assessment`。

- `hot_id`: 対象候補の `hot_id`(空でない文字列)
- `decision`: `selected` / `deferred` / `rejected`
- `assessed_at`: 判断日時(空でない文字列。記録時に実測したUTC時刻を書く。09章§5.1参照)
- `assessor`: 評価担当(空でない文字列)
- `relevance`: AI関連性の記録(`RelevanceRecord`)
  - `status`: `related` / `uncertain` / `unrelated`
  - `matched_terms`: 一致語(文字列のリスト。空リスト可)
  - `reason`: 判定理由(空でない文字列)
  - `method`: `keyword` / `agent` / `legacy`
- `novelty` / `importance` / `reader_impact` / `reason`: 新規性・重要性・読者への影響・採否理由(いずれも空でない文字列)
- `evidence`: 根拠(`EvidenceCheck` のリスト。空リスト可。ただし `selected` には `verified` かつ `primary` の根拠が1件以上必要)
- `unknowns`: 未確認事項(文字列のリスト。空リスト可)

### EvidenceCheck

根拠1件の確認記録。型は `schemas/quality.py` の `EvidenceCheck`、検証は `validate_evidence_check` / `validate_evidence_list`。Assessment と ProposalQuality で共通に使う。

キーは次の7つちょうどとし、欠落・余分なキーはエラーにする。

- `url`: 根拠のURL。scheme が `http` / `https` で、ホスト部があること
- `checked_at`: 確認日時(文字列。空文字も型としては許容する)
- `target_version`: 確認対象の版(文字列または `null`)
- `status`: `verified` / `unavailable` / `unverified` / `unknown`
- `kind`: `primary` / `independent` / `republication` / `unknown`
- `claim`: この根拠が支える主張(文字列。空文字も型としては許容する)
- `note`: 補足(文字列。空文字可)

### ProposalQuality

記事企画の品質記録の契約。型は `schemas/quality.py` の `ProposalQuality`、検証は `validate_proposal_quality`。

- `question` / `difference` / `baseline` / `baseline_version` / `measurement` / `inputs_and_environment` / `effort` / `effort_assumptions` / `success_condition` / `stop_condition`: 空でない文字列
- `metrics`: 空でない文字列のリスト(1件以上)
- `evidence`: `EvidenceCheck` のリスト
- `unknowns`: リスト

現在 `save-proposals` はこの契約を使っておらず、独自の必須項目チェックで企画を保存する。`save-proposals` への結線は Issue #11 で行う予定である。

## ArticleProposal

HOT候補から生成される記事企画案。

主な項目:

- `proposal_id`
- `source_hot_id`
- `title_idea`
- `article_type`
- `target_reader`
- `why_now`
- `technical_angle`
- `experiment_plan`
- `competition`
- `traffic_opportunity`
- `technical_opportunity`
- `unique_angle`
- `evidence_links`
- `risks`

MVPでは外部LLMを使わず、決定論的なRole生成、Critique、Debate代替で作成する。

## RunMetadata

1回の実行結果を記録する。

主な項目:

- `run_id`
- `started_at`
- `finished_at`
- `mode`
- `since`
- `until`
- `sources`
- `input_counts`
- `output_counts`
- `errors`
- `report_paths`
- `stage_results`

`since` / `until` は日付またはタイムゾーン付きISO 8601日時を保持する。通常の日次実行(`--since` / `--until` 省略時)では、前日以前で最新の `run.jsonl` の `until` から実行時刻までの実際の取得範囲を記録する(最大 `collection.max_lookback_days` 日。前回の記録がない初回も同じ日数。06章)。`overlap_hours` を持つSource(04章)は、この `since` より前の重ね取得分も取得するが、記録する `since` は変えない。

`overlap_hours` を持つSourceの `input_counts` と `raw/<date>/<source>.jsonl` は、前日以前の `normalized` に既にある記事を除いた件数・内容(その回に新しく収集した分)である。

`stage_results` は `select-hot` / `save-proposals` の結果を、`stages_completed`(処理を実行した事実)とは別の軸で記録する(Issue #12)。`run_state.json` と `run.jsonl` の両方に同じ内容を持つ。

| キー | 内容 |
| --- | --- |
| `status` | `completed`(成果あり) / `deferred`(実行したが使える成果なし=保留) / `not_run`(未実行・無効) / `failed`(終了コード1で失敗) |
| `reason` | 保留・未実行・失敗の理由。`select-hot` は `selection_reason`、`failed` は `<error_type>: <message>` |
| `candidate_count` / `screened_count` / `unreviewed_count` / `selected_count` | `select-hot` の completed / deferred のときだけ持つ |
| `proposal_count` | `save-proposals` の成功時(completed / deferred / 選抜HOTなしの not_run)だけ持つ |

判定ルール:

| ステージ | 条件 | status | reason |
| --- | --- | --- | --- |
| select-hot | 成功・選抜1件以上 | `completed` | `selection_reason` |
| select-hot | 成功・選抜0件(候補0件の日を含む) | `deferred` | `selection_reason` |
| save-proposals | 成功・企画1件以上 | `completed` | 空 |
| save-proposals | 成功・選抜1件以上・企画0件 | `deferred` | 入力の `deferral_reason`(#11 完了までは空) |
| save-proposals | 成功・選抜0件 | `not_run` | 選抜HOTなし |
| いずれも | 未実行 | `not_run` | 未実行 |
| いずれも | 終了コード1で失敗(`errors` に記録したエラー) | `failed` | エラーの種別と内容 |

- 再実行・失敗時はそのステージの記録を上書きする。`select-hot` が成功したときは、`save-proposals` の記録が初期値(未実行)以外なら `not_run`(選抜の再実行により無効)に戻す。古い `article_proposals.jsonl` は削除しない。
- 新しい `run_state.json` は2ステージを `not_run`(未実行)で初期化する。`report` 以外のコマンドは、既存の `run_state.json` に有効な記録がなく、`stages_completed` にも入っていないステージだけを同じ値で補う(実行済みのステージは「記録なし」のまま)。既存の `run_state.json` について `report` は補わない(新規作成する場合は `report` でも2ステージを `not_run` で初期化する)。
- 記録がない・dictでない・`status` が4値以外のステージは「記録なし」として扱う。`decode_run` は `stage_results` のない旧 `run.jsonl` を空dictとして読む。決定論経路(`ai-radar daily`)は記録せず、`run.jsonl` の `stage_results` は空dictのままである。
- `run_state.json` が壊れたJSON、またはJSONとして正しくてもオブジェクトでない場合、`load_run_state` は `RunStateError` を送出する。この場合は `errors` にも `stage_results` にも記録できないため、`stage_results` は更新されない。
- 判定用の定数・関数(`STAGE_RESULT_STATUSES` / `NOT_RUN_REASON` / `valid_stage_result`)は `schemas/models.py` にある。

Source失敗や後段失敗は `errors` に残す。運用時は `run.jsonl` を最初に確認する。

## Daily Markdown Report

`reports/daily/<date>.md` は `render_daily_report()`(`src/ai_research_radar/reporting/markdown.py`)が生成する。構成は次の通り。

- `# AI Daily Radar <date>`
- `## データ欠落`(収集に完全失敗したSourceがある場合のみ出力)
- `## 選抜HOT`: `selected=True` のHotCandidateと、それに紐づくArticleProposal
  - 見出しの直後に、`stage_results` の `select-hot` に応じた状態を1行出す。記録なし(旧データ)は従来どおり、選抜0件のときだけ「本日の選抜HOTはありません。」。`completed` は状態行を出さず選抜HOTを列挙する(選抜HOTが0件なら「選抜結果が見つかりません(score の再実行などで選抜が消えた可能性があります)。」)。`deferred` は「本日の選抜HOTはありません(保留: <selection_reason>。候補 m件中 n件を確認、未確認 k件)。」(`selection_reason` の末尾の「。」は除いて表示し、理由が空なら「理由未記載」とする)(候補0件の日は「…(保留: <selection_reason>。候補0件)。」)。`not_run` / `failed` は「選抜は未実行(<理由>)。」/「選抜は失敗(<理由>)。」とし(理由が空または「未実行」なら括弧を省く。次の記事企画の行も同じ)、選抜HOTが残っていれば「以下は前回成功時の結果です。」を続けて列挙する。
  - 当日の `hot_candidates.jsonl` が読めなかった場合(`report` が `corrupt_input` を記録した場合。06章)は、上の状態行(「選抜結果が見つかりません(…)」や旧データの「本日の選抜HOTはありません。」を含む)を出さず、「hot_candidates.jsonl を読めなかったため表示できません(Errors を参照)。」に置き換える。候補は空として扱うため、選抜HOTと記事企画は出ない。
  - 選抜HOTが1件以上あり、`save-proposals` が `not_run` / `failed` のときは、続けて「記事企画は未実行(<理由>)。」/「記事企画の保存は失敗(<理由>)。」を1回出す(企画が残っていれば「表示中の企画は前回の結果です。」を続ける)。`save-proposals` が `deferred` のときは、企画0件のHOTの企画欄を「記事企画なし(保留: <理由、空なら理由未記載>)」にする(理由の末尾の「。」は除く)。`completed` と記録なしのときは従来どおり「記事企画なし」。
  - 当日の `article_proposals.jsonl` が読めなかった場合は、各選抜HOTの企画欄に「記事企画なし」「記事企画なし(保留: …)」の代わりに「article_proposals.jsonl を読めなかったため表示できません(Errors を参照)。」を出す。上の「記事企画は未実行」「記事企画の保存は失敗」の行は `stage_results` のとおり出す。
  - 理由などAgentが書いた文字列は `_inline_text` を通す。
  - 各HOTの既存の行(HOT Score / Topic / Source Families / Evidence / Reasons)の後、`#### Article Proposals` の前に、`assessment` がある場合だけ評価ブロックを出す(`_assessment_section`)。項目は 判断理由 / 関連性(`<status>(方法: <method> / 一致語: <matched_terms をカンマ区切り、空なら「なし」>)`、`relevance.reason` が空でなければ子項目に出す) / 新規性 / 重要性 / 読者への影響 / 根拠 / 未確認事項。`assessment` が `null` の旧データ(決定論経路を含む)は評価ブロックを出さず、従来どおりReasonsだけを表示する。
    - 評価担当(`assessor`)・判断日時(`assessed_at`)は表示しない。`decision` は選抜HOTでは常に `selected` のため表示しない。
    - 根拠は1件1行で `[URL](<URL>)(<status> / <kind>):<claim>` 形式にする(`_evidence_check_line`。#11 の企画の根拠でも使う予定)。`checked_at` / `target_version` / `note` は表示しない。`claim` が空なら「(主張未記載)」、URLが空なら「(URL未記載)」と出す。根拠が0件なら「- 根拠: なし」、未確認事項が0件なら「- 未確認事項: なし」の1行にする。
    - 判断理由・新規性・重要性・読者への影響が空なら「(未記載)」と出す。
    - 表示する文字列は `_inline_text` を通す。バックスラッシュ・`[]`・`<>`・`|` をエスケープし、改行と連続する空白を1つの空白に畳む。さらに、先頭の1文字が `#` `=` `+` `*` `_` `` ` `` `~` `-` のいずれかなら常にバックスラッシュでエスケープし、`数字.` / `数字)` + 空白で始まる場合は `1\.` のように記号側をエスケープする(見出し・リスト・区切り線・コードフェンス・setext下線として解釈されるのを防ぐ)。
    - `decode_hot` は `assessment` を検証せずに読むため、表示側は防御的に読む。`assessment` がdictでなければブロックを出さない。`relevance` がdictでなければ「- 関連性: 記録なし」と出す。`evidence` / `unknowns` / `matched_terms` がリストでなければ空として扱い、dictでない根拠の要素は飛ばす。文字列であるべき項目が文字列でなければ空として扱う。
  - 各HOTの見出し直後に `> **概要**: <summary>` の引用ブロックを出す。概要が空の場合は `> **概要**: 概要未作成` と出す。概要はバックスラッシュ・`[]`・`<>`・`|` をエスケープし、改行を空白にする(先頭に `**概要**:` を付けるので、概要の先頭文字が見出し・リスト記号として解釈されることはない)。注目候補の概要も同じ表示・エスケープにする。
  - 各HOTの `#### Article Proposals` には、まず概要表(`# | 企画タイトル | Type | Role | Critique`)を出し、続けて企画ごとに `##### <番号>. <title_idea>` 見出しと2列の詳細表(`項目 | 内容`)を出す。詳細表の行は Type / Target Reader / Role / Critique Score / Critique Notes / Debate / Why Now / Technical Angle / Experiment Plan / Unique Angle / Competition / Traffic Opportunity / Technical Opportunity / Risks / Evidence。企画が0件の場合は `記事企画なし` と出す。
  - `why_now` が決定論的Ideation(`ideation/proposals.py`)の定型文に全体一致する場合だけ、レンダラーが Role / Critique Score / Critique Notes / Debate に分解して表示し、Why Now行は出さない(先頭のHOT score / reasonsは同じHOTセクションに表示済みのため再表示しない)。一致しない自由記述(Agent作成の企画など)は分解せず、Why Now行に全文を出し、概要表のRole / Critiqueは `-` にする。スキーマと保存データは変更しない。
  - 分解した場合、`risks` のうち表示済みのCritique Notes / Debateと完全一致する要素(`軽量Critique: <note>` / `Debate: <debate>`)は重複として除外する。すべて除外された場合は `Critique Notes / Debateと同じ内容` と出す。
  - 表崩れと意図しないリンクを防ぐため、セルの値はバックスラッシュ・`[]`・`|`・`<>`をエスケープしたうえで改行を `<br>` に置換し、リストは `<br>` 区切り(Experiment Planは番号付き、Critique Notes / Risksは `・` 付き)にする。`save-proposals` はリスト型を検証しないため、リスト項目に文字列が入っていた場合は1要素として扱う。空の値は `-` にする。見出しはバックスラッシュ・`[]`・`<>`をエスケープし、改行を空白にし、末尾の `#` はATX見出しの閉じ記号にならないようエスケープする。Debateは最大3要素(Advocate / Critic / Editor)に分割し、却下候補のタイトルに `; ` が含まれても分割しない。Evidenceは全URLを `[URL](<URL>)` 形式のリンクで出し、リンク先の `\`・`<>`・`|`・改行はパーセントエンコードする(リンク先のエンコードは収集Source一覧と共通の `_sanitize_url`)。本文中の素のURLは、GFMの自動リンクとして表示されることを許容する。
- `## 注目候補(選抜外)`: 直近3日分のrunで `minimum_score` 以上だが選抜されなかったHotCandidate(05章「日次ダイジェスト」参照)。各項目の見出し直後に、選抜HOTと同じ形式で概要を出す。
- `## 新モデルリリース`: 直近3日分のrunで `metadata.model_release` を持つSignalを提供元ごとに列挙したもの(05章「日次ダイジェスト」参照)。各項目の行の次に、字下げして `  - 概要: <概要>` を出す(概要がなければ `  - 概要: 概要未作成`)。概要は注目候補と同じエスケープをし、改行・連続する空白を1つの空白に畳む(行頭が `概要:` になるため、`_inline_text` のブロック記号のエスケープは不要)。「ほかN件」の行には概要を付けない。
- `## Run Summary`: RunMetadataのサマリを2列の表(`項目 | 内容`)で出す。行は Run ID / Period / Sources / Input Counts / Output Counts / Selection / Proposals。
  - Run IDは識別子として加工せずそのまま出す。
  - Periodは `since` / `until` を表示用タイムゾーン(`config/runtime.yaml` の `runtime.timezone`。06章参照)に変換し、`YYYY-MM-DD HH:MM 〜 YYYY-MM-DD HH:MM (<略称>)` 形式で出す(例: `2026-10-03 11:09 〜 2026-10-04 11:09 (JST)`)。タイムゾーンなしの日時はUTCとして扱う。`T` を含まない値(日付のみ)や日時として解釈できない値は変換せずそのまま出し、変換時に範囲外となる値(`0001-01-01T00:00:00` など)も同様にそのまま出す。末尾の略称は両端とも変換できた場合だけ、終了時刻のものを1つ付ける。
  - Sourcesは `, ` 区切り、Input / Output Countsは `key: value` を `, ` 区切りで、いずれもRunMetadataの保持順のまま出す。
  - Selectionは `<status>(候補m件 / 確認n件 / 未確認k件 / 選抜s件)`(completed / deferred)または `<status>(<理由>)`(not_run / failed)。Proposalsは `completed(企画n件)`、`deferred(企画n件 / 理由: <理由、空なら理由未記載>)`、`<status>(<理由>)`(理由が空なら `<status>` のみ)。deferredの理由は選抜HOTの節と同じく末尾の「。」を除いて表示する。記録なし(旧データ・決定論経路)は「記録なし」。件数が整数でなければ `?` と出す。
  - セルの値は記事企画の詳細表と同じエスケープ(`|`・`<>`・`[]` など)を行い、空の値は `-` にする。
- `## Errors`: RunMetadataのerrors
- `## 収集Source一覧`: 当日の正規化・重複排除後のSignal(`data/normalized/<date>/signals.jsonl` と同じデータ、Event/Topic集約より前の粒度)をSourceごとに`<details>`で折りたたんだMarkdown表として一覧化したもの。`RunMetadata.sources` の順序で見出しを出し、収集0件のSourceも `(0件)` として明示する。`RunMetadata.sources` に含まれないSourceのSignalは末尾の `other` 見出しに集約する(ただし `other` という名前のSourceが実在する場合は `_other` に退避し、実データと混同しない)。表の概要列は元データの `summary` をそのまま使うが、表崩れ防止のためバックスラッシュエスケープ・改行除去・`|`エスケープ・120文字切り詰めを行う。リンク先URLは `\`・`<>`・`|`・改行をパーセントエンコードする。
  - 当日の `data/normalized/<date>/signals.jsonl` が読めなかった場合(UTF-8・JSON・オブジェクトとして読めない場合)は、説明文の直後に「signals.jsonl を読めなかったため表示できません(Errors を参照)。」と出し、Sourceごとの見出し・表は出さない(読めていないのに `(0件)` と出すと本当の0件と区別できないため)。

## Report Digest記録

`data/runs/<date>/report_digest.json` は、その日のレポートの「注目候補(選抜外)」「新モデルリリース」に掲載した項目のキーを記録する。翌日以降のレポートで既掲載の項目を除外するために使う。

```json
{"notable": ["hot:event:..."], "model_releases": ["https://huggingface.co/org/model"]}
```

- `notable`: 掲載したHotCandidateの `hot_id`
- `model_releases`: 掲載したSignalの正規化済みURL(URLが空の場合は `signal_id`)

同じ日のレポートを再生成した場合は上書きする。除外判定には対象日より前の日付の記録だけを使う。

## Digest Summaries記録

`data/runs/<date>/digest_summaries.json` は、その日のレポートに表示する項目のうち、Agentが当日に補った概要を記録する。対象は、注目候補のうちHotCandidate自体に `summary` がないもの(過去日の候補や書き漏れ)と、新モデルリリースの全表示項目である。`ai-radar add-summary` が書き込む。

```json
{"hot:event:...": "注目候補の概要", "https://huggingface.co/org/model": "新モデルリリースの概要"}
```

- キーは、注目候補は `hot_id`、新モデルリリースは `ModelRelease.key`(正規化済みURL、URLが空なら `signal_id`)。`hot_id` は `hot:` で始まり、`key` はURLか `<source>:...` 形式なので衝突しない。値は概要の本文。同じキーを再度追加した場合は上書きする。
- 過去日の `hot_candidates.jsonl` は書き換えない(当日の run に「当日補った情報」として残す)。
- 注目候補の概要は、HotCandidateの `summary` を優先し、空の場合に対象日のこのファイルの値を使う。新モデルリリースの概要は、このファイルの値だけを使う。どちらもなければ「概要未作成」と表示する。
