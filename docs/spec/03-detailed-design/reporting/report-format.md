# 日次レポートの表示契約

旧設計書の該当節を分割した資料。現行と移行目標の区別は [文書全体の入口](../../../README.md) から確認する。

## Daily Markdown Report

`reports/daily/<date>.md` は `render_daily_report()`(`src/ai_research_radar/reporting/markdown.py`)が生成する。構成は次の通り。

- `# AI Daily Radar <date>`
- 要確認の警告(`run_state.json` の `needs_review` が `true` のときだけ、見出しの直後に1行): `> ⚠️ **要確認**: 自動レビューで解消できなかった指摘があります。`<data_dir>/runs/<date>/review_feedback.md` を確認してください。` `report` を再生成しても出る。決定論経路では出ない。
- `## データ欠落`(収集に完全失敗したSourceがある場合のみ出力)
- `## 選抜HOT`: `selected=True` のHotCandidateと、それに紐づくArticleProposal
  - 見出しの直後に、`stage_results` の `select-hot` に応じた状態を1行出す。記録なし(旧データ)は従来どおり、選抜0件のときだけ「本日の選抜HOTはありません。」。`completed` は状態行を出さず選抜HOTを列挙する(選抜HOTが0件(`hot_candidates.jsonl` がない場合を含む)なら「選抜結果が見つかりません(score の再実行などで選抜が消えた可能性があります)。」)。`deferred` は「本日の選抜HOTはありません(保留: <selection_reason>。候補 m件中 n件を確認、未確認 k件)。」(`selection_reason` の末尾の「。」は除いて表示し、理由が空なら「理由未記載」とする)(候補0件の日は「…(保留: <selection_reason>。候補0件)。」)。`deferred` なのに選抜HOTが残っている場合は、この行に「選抜の記録(保留)と選抜結果が一致しません。以下は hot_candidates.jsonl の内容です。」を続けて選抜HOTを列挙する(記事企画の行は `save-proposals` の記録どおり出す)。`not_run` / `failed` は「選抜は未実行(<理由>)。」/「選抜は失敗(<理由>)。」とし(理由が空または「未実行」なら括弧を省く。次の記事企画の行も同じ)、選抜HOTが残っていれば「以下は前回成功時の結果です。」を続けて列挙する。
  - 上の `completed` で選抜0件と `deferred` で選抜ありは、記録と `hot_candidates.jsonl` の食い違いである。判定は `report` が1回だけ行い(`selection_mismatch` を記録する。CLI設計)、`render_daily_report()` は判定結果(`selection_mismatch`)を受け取って文言を選ぶ。レンダラーは候補から食い違いを判定し直さない。
  - 当日の `hot_candidates.jsonl` が読めなかった場合(`report` が `corrupt_input` を記録した場合。CLI設計)は、上の状態行(「選抜結果が見つかりません(…)」や旧データの「本日の選抜HOTはありません。」を含む)を出さず、「hot_candidates.jsonl を読めなかったため表示できません(Errors を参照)。」に置き換える。候補は空として扱うため、選抜HOTと記事企画は出ない。食い違い(上の項目)としては扱わない。
  - 選抜HOTが1件以上あり、`save-proposals` が `not_run` / `failed` のときは、続けて「記事企画は未実行(<理由>)。」/「記事企画の保存は失敗(<理由>)。」を1回出す(企画が残っていれば「表示中の企画は前回の結果です。」を続ける)。`save-proposals` が `deferred` のときは、企画0件のHOTの企画欄を「記事企画なし(保留: <理由、空なら理由未記載>)」にする(理由の末尾の「。」は除く)。`completed` と記録なしのときは従来どおり「記事企画なし」。
  - 当日の `article_proposals.jsonl` が読めなかった場合は、各選抜HOTの企画欄に「記事企画なし」「記事企画なし(保留: …)」の代わりに「article_proposals.jsonl を読めなかったため表示できません(Errors を参照)。」を出す。上の「記事企画は未実行」「記事企画の保存は失敗」の行は `stage_results` のとおり出す。
  - 理由などAgentが書いた文字列は `inline` を通す(下の「表示用のエスケープ」)。
  - 各HOTの見出しは `heading`、Topic / Source Familiesは `span`、Reasonsの各行は `inline` を通す。Evidenceは各URLを `[URL](<URL>)` 形式のリンクにして `, ` でつなぐ(記事企画のEvidenceと同じ)。
  - 各HOTの既存の行(HOT Score / Topic / Source Families / Evidence / Reasons)の後、`#### Article Proposals` の前に、`assessment` がある場合だけ評価ブロックを出す。項目は 判断理由 / 関連性(`<status>(方法: <method> / 一致語: <matched_terms をカンマ区切り、空なら「なし」>)`、`relevance.reason` が空でなければ子項目に出す) / 新規性 / 重要性 / 読者への影響 / 根拠 / 未確認事項。`assessment` が `null` の旧データ(決定論経路を含む)は評価ブロックを出さず、従来どおりReasonsだけを表示する。
    - 評価担当(`assessor`)・判断日時(`assessed_at`)は表示しない。`decision` は選抜HOTでは常に `selected` のため表示しない。
    - 根拠は1件1行で `[URL](<URL>)(<status> / <kind>):<claim>` 形式にする(記事企画の「確認した根拠」行でも同じ形式)。`checked_at` / `target_version` / `note` は表示しない。`claim` が空なら「(主張未記載)」、URLが空なら「(URL未記載)」と出す。根拠が0件なら「- 根拠: なし」、未確認事項が0件なら「- 未確認事項: なし」の1行にする。
    - 判断理由・新規性・重要性・読者への影響が空なら「(未記載)」と出す。
    - 表示する文字列は `inline` を通す。
    - `decode_hot` は `assessment` を検証せずに読むため、表示側は防御的に読む。`assessment` がdictでなければブロックを出さない。`relevance` がdictでなければ「- 関連性: 記録なし」と出す。`evidence` / `unknowns` / `matched_terms` がリストでなければ空として扱い、dictでない根拠の要素は飛ばす。文字列であるべき項目が文字列でなければ空として扱う。
  - 各HOTの見出し直後に `> **概要**: <summary>` の引用ブロックを出す。概要が空の場合は `> **概要**: 概要未作成` と出す。概要は `span` を通す(先頭に `**概要**:` を付けるので、行頭のブロック記号のエスケープは不要)。注目候補の概要も同じ表示・エスケープにする。
  - 各HOTの `#### Article Proposals` には、まず概要表(`# | 企画タイトル | Type | Role | Critique`)を出し、続けて企画ごとに `##### <番号>. <title_idea>` 見出しと2列の詳細表(`項目 | 内容`)を出す。詳細表の行は Type / Target Reader / Role / Critique Score / Critique Notes / Debate / Why Now / Technical Angle / Experiment Plan / Unique Angle / Competition / Traffic Opportunity / Technical Opportunity / Risks / Evidence。企画が0件の場合は `記事企画なし` と出す。
  - Evidence行の後に、`schema_version` が2以上の企画は `quality` の全項目を行として出す: 検証の問い(`question`)/ 既存との差分(`difference`)/ 比較対象と版(`<baseline>(版: <baseline_version>)`)/ 測定方法(`measurement`)/ 入力・環境(`inputs_and_environment`)/ 工数と前提(`<effort>(前提: <effort_assumptions>)`)/ 成功条件(`success_condition`)/ 中止条件(`stop_condition`)/ 指標(`metrics`。`・` 付きの `<br>` 区切り)/ 未確認事項(`unknowns`。同じ形式で、0件なら「なし」)/ 確認した根拠(`evidence`。1件1行を `<br>` でつなぎ、各行は選抜HOTの根拠と同じ `_evidence_check_line` の「URL(status / kind):claim」形式。0件なら「なし」)。値は他のセルと同じエスケープをする。保存データは読み込み時に検証しないため防御的に読み、文字列であるべき値が文字列でなければ空(`-`)、リストであるべき値がリストでなければ空として扱い、dictでない根拠の要素は飛ばす。
  - `schema_version` が1の企画(Issue #11 より前の保存データと、決定論経路 `ai-radar daily` が作る企画)は、`quality` の行の代わりに `| 品質評価 | 旧形式のため未評価 |` の1行を出す(未評価であることを明示する)。
  - `why_now` が決定論的Ideation(`ideation/proposals.py`)の定型文に全体一致する場合だけ、レンダラーが Role / Critique Score / Critique Notes / Debate に分解して表示し、Why Now行は出さない(先頭のHOT score / reasonsは同じHOTセクションに表示済みのため再表示しない)。一致しない自由記述(Agent作成の企画など)は分解せず、Why Now行に全文を出し、概要表のRole / Critiqueは `-` にする。スキーマと保存データは変更しない。
  - 分解した場合、`risks` のうち表示済みのCritique Notes / Debateと完全一致する要素(`軽量Critique: <note>` / `Debate: <debate>`)は重複として除外する。すべて除外された場合は `Critique Notes / Debateと同じ内容` と出す。
  - セルの値は `cell` を通し、リストは `<br>` 区切り(Experiment Planは番号付き、Critique Notes / Risksは `・` 付き)にする。`save-proposals` がリスト型を検証する前(Issue #11 より前)の保存データにはリスト項目に文字列が入っていることがあるため、その場合は1要素として扱う。空の値は `-` にする。企画の見出しは `heading` を通す。Debateは最大3要素(Advocate / Critic / Editor)に分割し、却下候補のタイトルに `; ` が含まれても分割しない。Evidenceは全URLを `[URL](<URL>)` 形式のリンクで出す(リンク先は `url`)。本文中の素のURLは、GFMの自動リンクとして表示されることを許容する。
- `## 注目候補(選抜外)`: 直近3日分のrunで `minimum_score` 以上、またはOfficial overrideで候補化されたが選抜されなかったHotCandidate(Pipeline設計「日次ダイジェスト」参照)。各項目の見出し直後に、選抜HOTと同じ形式で概要を出す。
- `## 新モデルリリース`: 直近3日分のrunで `metadata.model_release` を持つSignalを提供元ごとに列挙したもの(Pipeline設計「日次ダイジェスト」参照)。各項目の行の次に、字下げして `  - 概要: <概要>` を出す(概要がなければ `  - 概要: 概要未作成`)。概要は注目候補と同じく `span` を通す。「ほかN件」の行には概要を付けない。
- `## Run Summary`: RunMetadataのサマリを2列の表(`項目 | 内容`)で出す。行は Run ID / Period / Sources / Input Counts / Output Counts / Selection / Proposals。
  - Run IDは識別子として加工せずそのまま出す。
  - Periodは `since` / `until` を表示用タイムゾーン(`config/runtime.yaml` の `runtime.timezone`。CLI設計参照)に変換し、`YYYY-MM-DD HH:MM 〜 YYYY-MM-DD HH:MM (<略称>)` 形式で出す(例: `2026-10-03 11:09 〜 2026-10-04 11:09 (JST)`)。タイムゾーンなしの日時はUTCとして扱う。`T` を含まない値(日付のみ)や日時として解釈できない値は変換せずそのまま出し、変換時に範囲外となる値(`0001-01-01T00:00:00` など)も同様にそのまま出す。末尾の略称は両端とも変換できた場合だけ、終了時刻のものを1つ付ける。
  - Sourcesは `, ` 区切り、Input / Output Countsは `key: value` を `, ` 区切りで、いずれもRunMetadataの保持順のまま出す。
  - Selectionは `<status>(候補m件 / 確認n件 / 未確認k件 / 選抜s件)`(completed / deferred)または `<status>(<理由>)`(not_run / failed)。Proposalsは `completed(企画n件)`、`deferred(企画n件 / 理由: <理由、空なら理由未記載>)`、`<status>(<理由>)`(理由が空なら `<status>` のみ)。deferredの理由は選抜HOTの節と同じく末尾の「。」を除いて表示する。記録なし(旧データ・決定論経路)は「記録なし」。件数が整数でなければ `?` と出す。
  - セルの値は記事企画の詳細表と同じエスケープ(`|`・`<>`・`[]` など)を行い、空の値は `-` にする。
- `## Errors`: RunMetadataのerrors
- `## 収集Source一覧`: 当日の正規化・重複排除後のSignal(`data/normalized/<date>/signals.jsonl` と同じデータ、Event/Topic集約より前の粒度)をSourceごとに`<details>`で折りたたんだMarkdown表として一覧化したもの。`RunMetadata.sources` の順序で見出しを出し、収集0件のSourceも `(0件)` として明示する。`RunMetadata.sources` に含まれないSourceのSignalは末尾の `other` 見出しに集約する(ただし `other` という名前のSourceが実在する場合は `_other` に退避し、実データと混同しない。該当するSignalがなければ見出しを出さない)。各見出し(`### <source> (N件)`)の直下、`<details>` の外に、Sourceごとの「本日の傾向」を1行で出す(下の「Source Overviews記録」参照)。収集0件のSourceは傾向の代わりに「収集0件」、傾向が未作成のSourceは「傾向未作成」と出す。傾向の本文は `paragraph` を通す(切り詰めない)。`source_overviews.json` を読めない(JSONとして壊れている、オブジェクトでない)場合はレポート生成を止めず、全Sourceを「傾向未作成」とし、節の冒頭に読めなかったファイルとエラーを警告として出す。表のタイトルは `span`、リンク先は `url` を通す。概要列は元データの `summary` の空白・改行を1つの空白に畳んで120文字で切り詰めてから `span` を通す(空なら「(概要なし)」)。
  - 当日の `data/normalized/<date>/signals.jsonl` が読めなかった場合(UTF-8・JSON・オブジェクトとして読めない場合)は、説明文の直後に「signals.jsonl を読めなかったため表示できません(Errors を参照)。」と出し、Sourceごとの見出し・表とSourceごとの「本日の傾向」(`source_overviews.json` の読み込み警告を含む)は出さない(読めていないのに `(0件)` と出すと本当の0件と区別できないため)。

### 表示用のエスケープ

外部Sourceのタイトル・概要・URLとAgentが書いた文字列は、置き場所に応じて `reporting/escape.py` の次の関数を通してから出す(意図しないリンク・HTML・見出し・リスト・表崩れを防ぐ)。新しい表示項目を足すときも、必ずいずれかを通す。

| 関数 | 使う場所 | 処理 |
| --- | --- | --- |
| `span` | 接頭辞の後ろに続く1行の文字列(タイトルのリンクの表示文字列、`> **概要**: …`、`- Topic: …` など) | `\`・`[]`・`\|` をバックスラッシュでエスケープ、`<>` を `&lt;` / `&gt;` に置換、改行と連続する空白を1つの空白に畳む。文字列でない値は空にする |
| `inline` | 行頭に来うる1行の文字列(リストの項目、評価ブロック、Errors・データ欠落の行) | `span` に加え、先頭の1文字が `#` `=` `+` `*` `_` `` ` `` `~` `-` ならエスケープし、`数字.` / `数字)` + 空白で始まる場合は `1\.` のように記号側をエスケープする |
| `heading` | 見出しの文字列 | `span` に加え、末尾の `#` をエスケープする(ATX見出しの閉じ記号にしない) |
| `cell` | 表のセル、Evidence・根拠のURLリンクの表示文字列 | 値を文字列に変換し(`str()`)、`span` と同じ文字をエスケープする(空白は畳まない)。改行を `<br>` に置換し、空なら `-` |
| `paragraph` | 単独の行に置く複数行の文字列(Sourceごとの本日の傾向) | 前後の空白を除き、`span` と同じエスケープ、改行を `<br>` に置換、行頭のブロック記号を `inline` と同じ規則でエスケープ |
| `url` | `[…](<…>)` のリンク先 | `\`・`<>`・`\|`・改行をパーセントエンコードする(HTMLエンティティは使わない) |
