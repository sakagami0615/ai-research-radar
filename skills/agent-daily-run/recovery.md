# Agent Daily Run: 失敗・やり直しの対応

[SKILL.md](SKILL.md) の手順で、コマンドが失敗したとき、ファイルが壊れていたとき、レビューで指摘を受けたときの対応。手順の番号(手順1〜10、8a〜8d、9a・9b)は `SKILL.md` のもの。エラー種別の条件は [06章](../../docs/specs/06-cli-and-operations.md) にあり、ここには書き写さない。

## エラー時の自己修正方針

`select-hot` / `save-proposals` / `add-summary` / `add-source-overview` が終了コード1を返した場合:

1. `data/runs/<date>/run_state.json` の `errors` を読み、エラー種別とメッセージを確認する。種別ごとの条件は [06章「Agent経路のサブコマンド」](../../docs/specs/06-cli-and-operations.md) の各コマンドの表を見る。
   - `invalid_proposal` のメッセージの `proposal[<番号>]` は、`proposals` の何番目(0始まり)の企画かを示す。
   - `select-hot` / `save-proposals` / `add-source-overview` の `corrupt_input` は自分が書いた入力ではなく、前のステージが出力したjsonl(`select-hot` / `save-proposals` は `hot_candidates.jsonl`、`add-source-overview` は `data/normalized/<date>/signals.jsonl`)の破損である。項目2・3ではなく、下の「壊れた入力(`corrupt_input`)」に従う。
2. 原因に応じて `selection_input.json`・`draft_proposals.json`・`summary_input.json`・`source_overview_input.json` を修正し、再実行する。
   - すでに手順7(`save-proposals`)を実行した後に `select-hot` を再実行して成功した場合は、続けて手順7も再実行する(選抜が変わった場合は先に手順6で `draft_proposals.json` を作り直す)。手順5の時点(まだ手順7を実行していない)では、通常どおり手順6へ進む。
   - `add-summary` が `write_error` で失敗し、メッセージから `data/runs/<date>/digest_summaries.json` が壊れていると分かる場合は、そのファイルを `digest_summaries.json.broken` に名前を変えて退避し、手順8aからやり直す(退避したファイルの概要は失われるため、一覧に出た項目の概要を書き直す)。
   - `add-source-overview` が `write_error` で失敗し、メッセージから `data/runs/<date>/source_overviews.json` が壊れていると分かる場合は、そのファイルを `source_overviews.json.broken` に名前を変えて退避し、手順8cの最初から(収集1件以上のすべてのSourceについて)傾向を書き直して保存する。
3. 再実行は最大3回までとする(`corrupt_input` を除く。`corrupt_input` は下の「壊れた入力(`corrupt_input`)」の1回の上限に従い、この3回には数えない)。「3回」は、同じステージが終了コード1で失敗した後の修正再実行の回数を、その日の実行全体(手順5・7・8b・8c・8d・9bを通算)で数える。ステージではない `add-summary`(手順8b)・`add-source-overview`(手順8c)の失敗も同じく数え、上限に達したら、保存できなかった項目は概要未作成・傾向未作成のまま次の手順(8bは8c、8cは8d)へ進む。9bでレビュー指摘を受けて行う再実行そのものは数えない(9bの試行回数3回で別に上限がある)。ただし、その再実行が失敗した後の修正再実行は数える。上限に達したステージは `failed` を残したまま先へ進む。品質レビュー(手順9)で3回試行しても重要指摘が残る場合の扱いは手順10に従う(この3回は手順9bの試行回数であり、上の再実行回数とは別に数える)。レビュー担当の起動失敗・結果欠損は承認しない。未完了ステージを`missing_stage`として記録しても、保存失敗を成功扱いしない。

`normalize` / `score` が終了コード1を返した場合も、内容を確認し可能なら1回だけ修正・再実行を試みる。それでも解決しない場合は諦めて手順8に進む。`errors` の種別が `corrupt_input` の場合は、下の「壊れた入力(`corrupt_input`)」に従う。

`collect` はSource単位の失敗を継続処理する設計であり、`run_state.json` の `errors` にSource単位のエラー(例: 特定Sourceの HTTP エラー)が記録されていても、`collect` コマンド自体は正常に終了コード0を返す。この場合は**再実行しない**。個別Sourceのエラーは正常な運用結果であり、他のSourceの収集結果はそのまま後続手順(`normalize`以降)に使ってよい。`collect` を再実行してよいのは、コマンド自体が終了コード1を返した場合(`invalid`な引数など、通常は発生しない)と、下の「壊れた入力(`corrupt_input`)」で `data/collected/<date>/signals.jsonl` が壊れていた場合のみである。

「エラー時の自己修正方針」が扱うのは構文・スキーマレベルの自己修正のみである。選抜内容や記事企画の「質」の妥当性を判断する別Agentによるレビュー・修正は、手順9〜10(品質レビューループ)で扱う。

### 壊れた入力(`corrupt_input`)

`corrupt_input` は、前のステージが出力したjsonlが壊れている(UTF-8として読めない、JSONとして読めない行・オブジェクトでない行がある、必須キーが欠けているなど)ことを表す。自分が書いた入力(`selection_input.json` / `draft_proposals.json` / `source_overview_input.json`)の不正である `invalid_input` とは違い、入力を書き直しても直らない。前のステージを再実行して、壊れたファイルを作り直す。

- 気づく場面: `normalize` / `score` / `select-hot` / `save-proposals` / `add-source-overview` が終了コード1で `corrupt_input` を記録した場合、または手順8dの後の確認で `source: report` の `corrupt_input` が見つかった場合(`report` は終了コード0のまま)。
- 壊れたファイルは、`errors` のメッセージの先頭のパス(`<path>:<行番号>: <内容>` または `<path>: <内容>`)で分かる。壊れたファイルを手で直したり削除したりせず、次の表の「再実行を始めるステージ」から流し直す。

  | 壊れたファイル | 再実行を始めるステージ | 続けて流すステージ |
  | --- | --- | --- |
  | `data/collected/<date>/signals.jsonl` | `collect`(手順1と同じコマンド。`--since` / `--until` は省略してよい(当日の記録は前回実行として使わないため、同じ期間を取り直し、当日のファイルは上書きされる)。上の「`collect` は再実行しない」の段落の例外として認める) | `normalize` → `score` → 手順4〜7 → 手順8 |
  | `data/normalized/<date>/signals.jsonl`、`data/events/<date>/events.jsonl` | `normalize`(手順2) | `score` → 手順4〜7 → 手順8 |
  | `data/runs/<date>/hot_candidates.jsonl` | `score`(手順3) | 手順4〜7 → 手順8 |
  | `data/runs/<date>/article_proposals.jsonl` | `save-proposals`(手順7。既存の `draft_proposals.json` のまま) | 手順8 |

- `score` を再実行すると `hot_candidates.jsonl` が作り直され、選抜(`selected` / 評価レコード / 概要)が消える。このため `score` から後を流すときは、手順4〜7(候補の確認、`selection_input.json`、`select-hot`、記事企画、`save-proposals`)をやり直す。既存の `selection_input.json` は再利用してよいが(手順4で `hot_candidates.jsonl` が読めずに書いた候補0件の仮のものは再利用せず、書き直す)、作り直した候補とIDが合わずに `select-hot` が `invalid_assessment` になれば、手順4に従って書き直す(この書き直しは通常の自己修正(項目2・3)として数える)。
- いつ気づいたかによって、流し直す範囲が変わる。
  - 初回の手順2〜7の途中(下流のステージをまだ実行していない): 再実行を始めるステージから、手順どおり先へ進む。
  - 手順8dの後の確認、手順8c・9bの中での `add-source-overview` の失敗、または手順8d(生成前の補完実行)・9bの中での `select-hot` / `save-proposals` の失敗: 表の「続けて流すステージ」をすべて流してから、手順8のa〜dをやり直す。
- 複数のファイルが壊れている場合は、表で最も上流のステージから1回だけ流し直す(下流のファイルも作り直される)。
- 流し直しの途中で `collect` / `normalize` / `score` が失敗した場合(再び `corrupt_input` になるなど)は、その失敗を残したまま、残りのステージは流さずに手順8へ進む。手順4〜7の途中の `select-hot` / `save-proposals` の失敗は、手順5〜7の既存の決まりに従う(自分の入力の誤り(`invalid_assessment` など)は項目2・3で直す。`select-hot` が再び `corrupt_input` で `failed` になった場合は上限に達しているため、手順6の「再実行の上限に達して `failed` のまま進む場合」に従う。このとき手順7の `save-proposals` も同じファイルを読むため `corrupt_input` で `failed` になるが、再実行せずに手順8へ進む)。
- `collect` から流し直した結果、`collect` の標準出力に出る日付が `<date>` と違う場合(日付をまたいだ場合)は、`<date>` のファイルは作り直されていないため、残りのステージは流さずに手順8へ進み、その旨を完了報告に書く(流し直しの1回は使い切ったものとする)。
- 上限: 流し直しは、その日の実行全体で **1回まで** とする(`normalize` / `score` の1回の決まりに揃える)。項目3の3回には数えない。流し直した後も `corrupt_input` が残る場合は、破損が繰り返す環境の問題の可能性が高いため、それ以上流し直さない。ステージの失敗(`failed`)や `report` の記録を残したまま先へ進み、レポートを生成する。
- 上限に達して残った `corrupt_input` は修正不能として扱う。手順9bでレビューの指摘を受けても流し直さない(下の「レビュー指摘の直し方」の修正不能の項目に従う)。完了報告に、壊れたファイルのパスとメッセージを書く。

## レポート生成前の補完実行

手順8dでレポートを生成する前に `stage_results` を確認し、`select-hot` / `save-proposals` が正常な状態(`select-hot` が `completed` / `deferred`、`save-proposals` が `completed` / `deferred` / `not_run`(理由: 選抜HOTなし)、または記録なし)でなかった場合に、ここに従う。

- `select-hot` が `not_run`(手順5を実行していない)の場合: `data/runs/<date>/hot_candidates.jsonl` があれば手順4〜7を1回だけ実行してから生成する。`normalize` / `score` の失敗で `hot_candidates.jsonl` がない場合は実行せずにそのまま生成する(レポートに「選抜は未実行」と出る)。
- `save-proposals` が `not_run`(理由: 選抜の再実行により無効、または未実行)の場合: 手順7だけを再実行してから生成する(`draft_proposals.json` がなければ先に手順6で作る)。ただし、上の項目で手順4〜7を実行した場合、または `hot_candidates.jsonl` がなくそのまま生成へ進む場合は、手順7を重ねて実行しない。手順7の再実行は1回だけとし、失敗した場合は下の `failed` の項目に従う。
- いずれかが `failed` の場合: 上の「エラー時の自己修正方針」に従って該当ステージだけを直して再実行する(回数の上限と数え方は同方針の項目3に従う)。上限に達している場合は、再実行せず `failed` を残したまま生成する(レポートに失敗として表示される)。ただし、理由が `corrupt_input: ...` の `failed` は、項目3ではなく同方針の「壊れた入力(`corrupt_input`)」に従う(流し直しは1回まで。上限に達していれば `failed` を残したまま生成する)。

## レビュー指摘の直し方

手順9bで `review_feedback.md` があり、3回目の試行でない場合の直し方。直したあとは、ここで手順10へ進むとした場合を除き、`SKILL.md` の手順9bのとおり手順8のa〜dをやり直して手順9aに戻る。

- HOT選抜・手順4で書いた概要の修正: `selection_input.json` を書き直して `ai-radar select-hot` を再実行し、
  `select-hot` が成功したら続けて必ず手順7の `save-proposals` も再実行する(`select-hot` が成功すると、それまでの記事企画の記録は「選抜の再実行により無効」になるため。概要だけの修正でも同じ)。
  選抜した候補が変わった場合は、`save-proposals` の前に手順6に従って `draft_proposals.json` を作り直す(選抜0件になった場合は `{"schema_version": 2, "proposals": []}` にし、`deferral_reason` を消す)。
  概要だけの修正で選抜が変わらない場合は、既存の `draft_proposals.json` のまま再実行してよい。
  `select-hot` が再実行の上限に達して `failed` のまま残った場合は、`draft_proposals.json` を書き換えず、`save-proposals` も再実行しない(`select-hot` の失敗では前回の選抜と記事企画の記録はそのまま残るため。手順6の `select-hot` が `failed` の場合の記述は手順5での失敗だけに当てはまる)。
- 記事企画だけの修正: `draft_proposals.json` を手順6の形式(v2)のまま書き直して手順7の `save-proposals` を再実行する。企画を0件にした・0件から作った場合は、手順6に従って `deferral_reason` を書く・消す。
- 手順8bで補完した概要の修正: `summary_input.json` に直す項目のキーと新しい概要だけを書いて `add-summary --input` を再実行する(上書きされる)。キーは `data/runs/<date>/digest_summaries.json` にあるもの(または `--list-missing-summaries` の `hot_id` / `key`)を使い、レポート上のURLをそのまま使わない(新モデルリリースのキーは正規化済みURLで、レポートのリンクとは一致しないことがあるため)。HOT選抜のやり直しなどで今はレポートに表示されていない項目のキーは書かない(1つでも含むと `invalid_summary` で全体が保存されない)。
- 手順8cで書いた本日の傾向の修正: `source_overview_input.json` に直すSourceと新しい傾向だけを書いて `add-source-overview --input` を再実行する(上書きされる)。Source名はレポートの見出しから `(N件)` を除いた名前(`other` / `_other` を含む)を使う。`add-source-overview` が再実行の上限(「エラー時の自己修正方針」の項目3。`corrupt_input` は同方針の「壊れた入力(`corrupt_input`)」の1回)に達して保存できず「傾向未作成」が残っていることへの指摘は、再実行せず、下の修正不能の項目と同じく扱う。
- `stage_results` の `failed` が再実行の上限(「エラー時の自己修正方針」の項目3、`corrupt_input` の `failed` は同方針の「壊れた入力(`corrupt_input`)」の1回)に達したため残っていることへの指摘、または上限に達して残った `corrupt_input`(`source: report` の記録やレポートの「…を読めなかったため表示できません」の注記)への指摘: 再実行せず、修正不能として扱う。
  `review_feedback.md` に他の指摘がなければ、手順8・9aに戻らず手順10へ進む。他に直せる指摘があれば、それは従来どおり修正する。
