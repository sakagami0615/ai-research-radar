# Agent経路のサブコマンド契約

旧設計書の該当節を分割した資料。現行と移行目標の区別は [文書全体の入口](../../../README.md) から確認する。

## 共通の引数

- `--data-dir`(全サブコマンド)/ `--reports-dir`(`daily` と `report` と `progress review`): 省略時は `--runtime-config`(既定 `config/runtime.yaml`)の `output.data_dir` / `output.reports_dir`、それも無ければ `data` / `reports`。引数を指定した場合は設定ファイルより優先する。
  - Agent経路(`agent-daily-run`)はすべてのコマンドに `--data-dir`(`report` には `--reports-dir` も)を明示するため、`runtime.yaml` の `output` はAgent経路には効かない(#40 以降の本番の挙動。本番は `data` / `reports` を明示する)。`output` が効くのは、引数を省略した手動実行と決定論経路(`daily`)である。
- `--runtime-config`: `runtime.yaml` のパス。ファイルが無い・読めない場合も止めず、既定値で続ける([設定ファイル](configuration.md))。
- `--date`(`collect` / `daily` 以外。`progress` は各サブコマンドに付ける): 対象日(`YYYY-MM-DD`)。
- `run_state.json` が壊れている(JSONとして読めない、オブジェクトでない)場合は、どのサブコマンドも記録できないため、標準エラーに `error: <メッセージ>` を出して終了コード1で終わる。

## Agent経路のサブコマンド

入力契約は [HOT選抜](../data-models/hot-selection.md)、[記事企画](../data-models/article-proposals.md)、[補助記録](../reporting/supplement-records.md) を参照。概要・傾向の作成条件は [ダイジェスト設計](../reporting/digest.md) にある。

`agent-daily-run` は `collect` / `normalize` / `score` / `select-hot` / `save-proposals` / `add-summary` / `add-source-overview` / `report` / `mark-needs-review` を使う(`progress` は実装済みだが、まだSkillから呼ばれない。下の「途中経過の記録(`progress`)」)。各サブコマンドの引数とエラーは次の通り(選抜・記事企画・概要についてはPipeline設計「注目候補・新モデルリリースの概要補完」、Sourceごとの本日の傾向についてはPipeline設計「Sourceごとの本日の傾向」も参照)。

前のステージが出力したjsonlが壊れている場合の扱いは、`normalize` / `score` / `select-hot` / `save-proposals` / `add-source-overview` / `report` で共通である(Issue #18)。

- エラー種別は `corrupt_input`。Agent自身が書いた入力(`selection_input.json` / `draft_proposals.json` / `source_overview_input.json` / CLI引数)の不正である `invalid_input`(入力を書き直せば直る)と区別し、`corrupt_input` は前のステージを再実行すれば直るものに使う。
- 対象: UTF-8として読めないファイル、JSONとして読めない行、オブジェクトでない行、デコーダ(`decode_signal` / `decode_event` / `decode_hot` / `decode_proposal`)が出す `KeyError`(必須キーの欠落)・`TypeError` / `ValueError`(`QualityValidationError` を含む。デコーダが検出できる範囲の型の不正)、ファイルを開けない・読めない(`OSError`)。デコーダが検出できない値の不正(例: `raw_metrics` の値が文字列)は対象外。
- 読み込みは `storage/jsonl.py` の `read_decoded_jsonl(path, decoder)`(デコーダを通さない場合は `read_jsonl(path)`)で行い、上の失敗はすべて `JsonlReadError` になる。メッセージは `<path>:<行番号>: <内容>`(例: `data/runs/2026-10-06/hot_candidates.jsonl:3: missing key 'hot_id'`)。行番号が分からない場合(`OSError`)は `<path>: <内容>`。必須キーの欠落は `missing key '<key>'`、デコーダのそれ以外の失敗は `invalid record: <例外>`、UTF-8の失敗は `invalid UTF-8: <理由>` とする。
- 各コマンドの記録の仕方は下の各項目のとおり。`report` 以外は終了コード1にし、出力ファイルは書き換えない。
- `corrupt_input` の `errors` の記録には、`source` / `type` / `message` に加えて、壊れたファイルの `data_dir` からの相対パス `path`(例: `runs/2026-10-06/hot_candidates.jsonl`)を持たせる(Issue #41)。`corrupt_input` は読んだ側のコマンド名(`source`)で記録されるため、再開時に戻るステージは `path` で判定する。`path` を追加する前に書かれた記録は `path` を持たない(読むときは `path` がない記録も受け付ける)。
- CLIのコマンドを追加・変更して前のステージのjsonlを読むときも、`read_jsonl` の結果を個別にデコードせず `read_decoded_jsonl` を使い(`report` の `signals.jsonl` のようにデコーダを通さないファイルは `read_jsonl` のままでよい)、どちらの場合も `JsonlReadError` を捕まえて `corrupt_input` として記録する。捕まえないとトレースバックで終わり、`run_state.json` に何も残らない(Issue #18 の不具合)。

- `normalize --date <date>`: `data/collected/<date>/signals.jsonl` を `decode_signal` で読む。ファイルがなければ `missing_input`、読めなければ `corrupt_input` を `errors`(`source: normalize`)に記録して終了コード1にする。出力の書き込みに失敗した場合は `write_error`。`stage_results` の対象外である。
- `score --date <date>`: `data/events/<date>/events.jsonl` を `decode_event` で読む。エラーの種別と記録は `normalize` と同じ(`missing_input` / `corrupt_input` / `write_error`、`source: score`)。

- `select-hot --date <date> [--input <path>] [--limit <n>]`: `selection_input.json`(データ契約「SelectionInput」)を読み込んで検証し、当日の `hot_candidates.jsonl` の `selected` / `assessment` / `summary` を更新する。
  - `--input` を省略した場合は `<data-dir>/runs/<date>/selection_input.json` を読む。明示したパスは、`save-proposals --input` と同じくカレントディレクトリを基準にする。
  - `--limit` は選抜件数の上限で、既定値は2、範囲は0〜5。整数でない値は `invalid_input` にする(argparseの終了コード2ではなく `errors` に記録する)。範囲外も `invalid_input` にする。
  - `summaries` で指定しなかった候補は既存の `summary` を保持し、指定した候補は(前後の空白を除いた値で)置き換える。`summaries` がdictでない、当日の候補にない `hot_id` がある、値が空または文字列でない場合は `invalid_summary` にする。
  - 選抜した候補に概要がない(`summaries` にも既存データにもない)場合は `missing_summary` にする。選抜外の候補に概要がない場合は、終了コード0のまま `run_state.json` の `errors` に `missing_summary_warning` として件数と `hot_id` を記録する。
  - `screened_ids` に含まれない(未確認の)候補があれば、終了コード0のまま `errors` に `unreviewed_candidates` として件数と `hot_id` を記録する。
  - 実行のはじめに `run_state.json` の `select-hot` のエラー・警告を消すため、再実行すると以前の警告は残らない。成功時は `output_counts.selected_hot` に選抜件数を記録し、`select-hot` を完了段階にして、`run_state.json` の `stage_results` に、選抜1件以上なら `completed`、0件なら `deferred` を、`selection_reason` と件数(候補・確認・未確認・選抜)とともに記録する。あわせて `save-proposals` の記録が初期値以外なら `not_run`(選抜の再実行により無効)に戻す。`errors` に記録して終了コード1にするエラー時は `failed` を記録する。`run_state.json` 自体が読めない場合(`RunStateError`)は `stage_results` を更新しない(データ契約「RunMetadata」)。
  - エラー時は `run_state.json` の `errors` に記録して終了コード1にし、`hot_candidates.jsonl` は書き換えない。エラー・警告の種別は次の通り。

    | 種別 | 条件 | 終了コード |
    | --- | --- | --- |
    | `missing_input` | `hot_candidates.jsonl` または `selection_input.json` がない | 1 |
    | `invalid_input` | `--limit` が整数でない・範囲外、`selection_input.json` がJSONとして読めない、トップレベルの構造が不正 | 1 |
    | `corrupt_input` | `hot_candidates.jsonl` が読めない(UTF-8でない、JSONとして読めない行・オブジェクトでない行がある、`decode_hot` でデコードできない) | 1 |
    | `invalid_assessment` | 選抜理由が空、ID の重複・不整合、評価レコードの内容が不正、選抜に `verified` かつ `primary` の根拠がない | 1 |
    | `selection_limit_exceeded` | 選抜件数が `--limit` を超える | 1 |
    | `invalid_summary` | `summaries` が不正 | 1 |
    | `missing_summary` | 選抜した候補に概要がない | 1 |
    | `write_error` | `hot_candidates.jsonl` の書き込みに失敗した | 1 |
    | `missing_summary_warning` / `unreviewed_candidates` | 選抜外の候補に概要がない / 未確認の候補がある(警告) | 0 |

- `save-proposals --date <date> --input <path>`: 記事企画(v2)を検証して `article_proposals.jsonl` に保存する。入力の形式と検証内容はデータ契約「save-proposals の入力(v2)」を参照。`hot_candidates.jsonl` は `decode_hot` で読み、`selected` の候補と企画を照合する。
  - `--input` は `{"schema_version": 2, "proposals": [...], "deferral_reason": "..."}` 形式のJSONファイル。パスはカレントディレクトリを基準にする。Agent経路では `<data-dir>/runs/<date>/draft_proposals.json` に書く(`<data-dir>` はSkillの出力先。本番は `data`、テストモードは `test_output/data`)。選抜0件の日も `{"schema_version": 2, "proposals": []}` で実行する。
  - 保留理由 `deferral_reason` をCLI引数にしないのは、長い日本語をシェル引数で渡すことによるエスケープ事故を避けるため(選抜HOTの概要を `selection_input.json`、注目候補などの概要を `add-summary --input` のファイルで渡すのと同じ考え方)。
  - 成功時は `stage_results` に、企画1件以上なら `completed`、選抜ありで企画0件なら `deferred`(理由は `deferral_reason`)、選抜0件なら `not_run`(選抜HOTなし)を `proposal_count` とともに記録し、`output_counts.article_proposals` に企画件数を記録して、`save-proposals` を完了段階にする。
  - エラーは `errors` に記録して `failed` を記録し、終了コード1にする(`run_state.json` 自体が読めない場合は `stage_results` を更新しない)。`article_proposals.jsonl` は書き換えない。エラーの種別は次の通り(上から順に判定する)。

    | 種別 | 条件 | 終了コード |
    | --- | --- | --- |
    | `missing_input` | `hot_candidates.jsonl` または `--input` のファイルがない | 1 |
    | `invalid_input` | ファイルが読めない・UTF-8でない・JSONとして解釈できない | 1 |
    | `invalid_input` | トップレベルがオブジェクトでない(配列など)、未知のキーがある、`schema_version` が整数の `2` でない・ない、`proposals` がない・リストでない | 1 |
    | `corrupt_input` | `hot_candidates.jsonl` が読めない(UTF-8でない、JSONとして読めない行・オブジェクトでない行がある、`decode_hot` でデコードできない) | 1 |
    | `invalid_input` | `deferral_reason` の欠落(選抜ありで企画0件なのにない・空・文字列でない)・余分(企画がある日・選抜0件の日にある) | 1 |
    | `invalid_proposal` | 企画の内容が不正(`proposals` の要素がオブジェクトでない、企画の `schema_version` が整数の `2` でない・ない、必須項目の欠落・型の不正、`quality` の欠落・不正、選抜していないHOTへの企画、元の根拠URLを含まない、役割(`claim`)のない追加URL、HOTあたり4件以上、`proposal_id` の重複) | 1 |
    | `write_error` | `article_proposals.jsonl` の書き込みに失敗した(メッセージは `failed to write article proposals: <例外>`) | 1 |


- `add-summary --date <date> --input <path>`: 当日のレポートに表示する注目候補(過去日の候補など)・新モデルリリースの概要を `<data-dir>/runs/<date>/digest_summaries.json`(既定は `data`)に保存する。パイプラインのステージ(`stages_completed`)としては扱わない。
  - `--input` は `{"<hot_id または key>": "概要"}` 形式のJSONファイル。パスはカレントディレクトリを基準にする。Agent経路では `<data-dir>/runs/<date>/summary_input.json` に書く(`<data-dir>` はSkillの出力先。本番は `data`、テストモードは `test_output/data`)。新モデルリリースの `key` はクエリ文字列(`=` を含む)を持つことがあるため、コマンドライン引数ではなくファイルで渡す。
  - キーは、当日のレポートに表示される注目候補のうち候補自身が `summary` を持たないものの `hot_id`(候補自身の `summary` が優先されるため、それ以外への保存は表示に反映されない)と、表示される新モデルリリースの `key` に限る。`report --list-missing-summaries` の対象と、すでに補完済みの項目がこれに当たる。
  - 値は前後の空白を除いて保存し、同じキーは上書きする。
  - エラー時は `run_state.json` の `errors` に記録して終了コード1にし、`digest_summaries.json` は書き換えない。エラーの種別は次の通り。

    | 種別 | 条件 | 終了コード |
    | --- | --- | --- |
    | `invalid_input` | `--input` の指定がない、ファイルが読めない・UTF-8でない・JSONとして解釈できない、トップレベルがオブジェクトでない | 1 |
    | `missing_input` | `--input` のファイルがない | 1 |
    | `invalid_summary` | 中身が空のオブジェクト、対象外のキーがある、値が文字列でない・空 | 1 |
    | `write_error` | `digest_summaries.json` の読み書きに失敗した(既存ファイルが壊れている場合を含む) | 1 |

- `add-source-overview --date <date> --input <path>`: 収集Source一覧の各見出しに出す「本日の傾向」を `<data-dir>/runs/<date>/source_overviews.json`(既定は `data`)に保存する(データ契約「Source Overviews記録」)。パイプラインのステージ(`stages_completed`)としては扱わない(`add-summary` と同じ)。
  - `--input` は `{"<source名>": "本文"}` 形式のJSONファイル。パスはカレントディレクトリを基準にする。Agent経路では `<data-dir>/runs/<date>/source_overview_input.json` に書く(`<data-dir>` はSkillの出力先。本番は `data`、テストモードは `test_output/data`)。
  - Source名は、当日の `run_state.json` の `sources` にあるもの、または `sources` にないSourceのSignalをまとめた見出し(`other`。同じ名前のSourceが実在する場合は `_other`)に限る。レポートの見出しと同じ名前・同じ件数で判定する(`other` / `_other` は該当するSignalがあるときだけ受け付ける)。
  - そのSourceの当日の件数(`data/normalized/<date>/signals.jsonl` の件数。レポートの見出しの件数と同じ)が0件なら受け付けない。
  - 値は前後の空白を除いて保存し、同じSourceは上書きする。文字数は検証しない(レビューで確認する)。
  - 実行のはじめに `run_state.json` の `add-source-overview` のエラーを消す。入力のすべての項目を検証してから保存するため、1つでも不正な項目があれば何も保存しない。
  - エラー時は `run_state.json` の `errors` に記録して終了コード1にし、`source_overviews.json` は書き換えない。エラーの種別は次の通り。

    | 種別 | 条件 | 終了コード |
    | --- | --- | --- |
    | `invalid_input` | `--input` の指定がない、ファイルが読めない・UTF-8でない・JSONとして解釈できない、トップレベルがオブジェクトでない | 1 |
    | `missing_input` | `--input` のファイルがない | 1 |
    | `corrupt_input` | 当日の `data/normalized/<date>/signals.jsonl` が読めない(UTF-8・JSON・オブジェクトとして読めない、開けない。デコーダは通さない)。前のステージ(`normalize`)の出力の破損であり、入力ファイルを直しても解消しない | 1 |
    | `invalid_overview` | 中身が空のオブジェクト、レポートの見出しにないSource名、本文が文字列でない・空、そのSourceの当日の件数が0件 | 1 |
    | `write_error` | `source_overviews.json` の読み書きに失敗した(既存ファイルが壊れている場合を含む) | 1 |

- `report --date <date>`: 当日の `hot_candidates.jsonl`(`decode_hot`)/ `article_proposals.jsonl`(`decode_proposal`)/ `data/normalized/<date>/signals.jsonl`(デコーダを通さない。表示は生のdictを `.get()` で読むため、UTF-8・JSON・オブジェクトとして読めない場合だけが対象)を読み、日次レポートと `run.jsonl` を生成する。
  - 実行のはじめに `errors` の `source: pipeline` / `report` を消して記録し直す。前のステージが完了していなければ `missing_stage`(`source: pipeline`)を記録する。
  - 上の3ファイルのいずれかが読めない場合は、そのファイルを欠けたデータ(空)として扱い、`corrupt_input`(`source: report`)を記録してレポートを生成する。該当するセクションの先頭に「<ファイル名> を読めなかったため表示できません(Errors を参照)。」と注記し、本当の0件と区別する(表示の詳細はデータ契約「Daily Markdown Report」)。終了コードは、レポートを書けた場合は0のまま(`missing_stage` と同じ扱い)。ファイルを直して再実行すれば記録は消える。どのステージの出力が壊れているかはメッセージのパスで分かる。
  - `stage_results` の `select-hot` と `hot_candidates.jsonl` の選抜(`selected: true`)が食い違う場合は、`selection_mismatch`(`source: report`)の警告を記録してレポートを生成する(終了コード0)。対象は、`deferred` なのに選抜HOTがある場合と、`completed` なのに選抜HOTが0件の場合(`hot_candidates.jsonl` がない場合も選抜0件として扱う)。メッセージには `select-hot` の状態、ファイルのパス、ファイル中の選抜件数(ファイルがなければその旨)を入れる。判定は `report` で1回だけ行い、`run.jsonl` の組み立て前に記録する(レポートの Errors 欄にも出る)。レポートの表示はこの判定結果を使う(データ契約「Daily Markdown Report」)。`hot_candidates.jsonl` が読めない場合は `corrupt_input` だけを記録し、判定しない。`stage_results` がない旧データと、`completed` の `selected_count` とファイル中の選抜件数がどちらも1以上で異なる場合は対象外。`report` は食い違いを直さない(`hot_candidates.jsonl` を書き換えない)。
  - レポートまたは `report_digest.json` の書き込みに失敗した場合は `report_write_error`(`source: report`)を記録し、終了コード1にする。
  - 直近3日分を集約する注目候補・新モデルリリース(Pipeline設計「日次ダイジェスト」)は、読めない日を飛ばして警告に残す。当日の `hot_candidates.jsonl` が壊れている場合は、この警告と上の注記の両方に出る。
  - `run_state.json` の `needs_review` が `true` なら、レポートの見出しの直後に要確認の警告を出す(データ契約「Daily Markdown Report」)。
- `report --list-missing-summaries`: 概要がない注目候補・新モデルリリース(表示分のみ)を、`kind`(`notable` / `model_release`)付きのJSON Linesで出力する(Pipeline設計「注目候補・新モデルリリースの概要補完」参照)。レポート・`report_digest.json`・`run.jsonl`・`run_state.json` は書き換えない。
- `mark-needs-review --date <date>`: 品質レビューループ(`agent-daily-run` 手順9〜10)が3回目の試行(初回を1回目とする)の後も解消しなかったことを `run_state.json` に `needs_review: true` として記録する。`report` を実行するとレポートの冒頭に要確認の警告が出る(再生成しても消えない)。記録だけを行い、レポートは書き換えないため、続けて `report` を実行する。`errors` には何も記録しない。その日の `run_state.json` がない場合は(`--date` の打ち間違いで新しく作らないよう)何も書かずに終了コード1にする。`collect` は実行のはじめに `needs_review` を消す(その日の実行をやり直すため)。

## 途中経過の記録(`progress`)

`agent-daily-run` が途中で止まった日を当日中に再開できるよう、途中経過を `run_state.json` の `agent_progress` に記録する(Issue #30・#41。記録の形式は [実行記録](../data-models/run-metadata.md) の「agent_progress」)。

現行: 記録系のサブコマンド(`review` / `retry` / `finalize` / `complete`)は実装済みだが、まだSkillからは呼ばれない(Skillへの組み込みは #43、記録から再開する手順を判定する `progress show` は #42)。

共通の動作:

- すべて `--date` と `--data-dir` / `--runtime-config` を受け付ける(`review` は `--reports-dir` も)。
- その日の `run_state.json` がない場合は(`--date` の打ち間違いで新しく作らないよう)何も書かずに、標準エラーに `error: <メッセージ>` を出して終了コード1にする。`run_state.json` が読めない場合、`agent_progress` の形が壊れている場合([実行記録](../data-models/run-metadata.md) の「agent_progress」)も同じく終了コード1にし、何も書き換えない。
- 引数の検証で止める場合も、標準エラーに `error: <メッセージ>` を出して終了コード1にし、何も書かない。`errors` には記録しない(パイプラインのエラーではないため)。argparseが受け付けない引数(`--start` / `--result` の両方・どちらもなし、`--stage` / `--kind` の対象外の値)は終了コード2。
- 回数はその日全体で数える(止まった後の再開をまたいで引き継ぐ)。`collect` は `agent_progress` を消さない。

### `progress review --date <date> --attempt <n> --start|--result [--launch-failed]`

品質レビュー(`agent-daily-run` 手順9)の試行を記録する。試行は最大3回(初回を1回目とする)。

- `--start`: 試行の開始を `status: started` で記録し、`<data-dir>/runs/<date>/review_target.json` を書く(上書き)。成果物を読めなかった場合(`failed to read a review artifact: ...`)、`review_target.json` を書けなかった場合(`failed to write review_target.json: ...`)は、試行を記録せずに終了コード1にする。標準出力に `{"attempt": <n>, "status": "started"}` を出す。
- `--result`: 試行の結果を記録し、標準出力に `{"attempt": <n>, "status": "<status>"}` を出す。status はAgentが渡さず、次の順で決める。
  1. `--launch-failed` がある(レビュー担当の起動に失敗した): `failed`
  2. `<data-dir>/runs/<date>/review_feedback.md` がある: `changes_requested`
  3. ない: `approved`
- 試行番号の検証(終了コード1):

  | 条件 | 例 |
  | --- | --- |
  | `--attempt` が1〜3の整数でない | `0`、`4`、`x` |
  | `--start`: その試行がすでに記録されている(同じ試行の2回目の `--start`) | 1回目を2回始める |
  | `--start`: 最後に記録した試行の次の番号でない | 記録がないのに2回目を始める |
  | `--result`: その試行の `--start` がない | 1回目を始めずに結果を記録する |
  | `--result`: その試行が最後に記録した試行でない、またはすでに結果がある(`started` でない) | 2回目を始めた後に1回目の結果を記録する |
  | `--start` に `--launch-failed` を付けた | |

  `started` のまま(結果が出る前に止まった)試行の次の試行を始めることは許す(止まった後の再開で起こるため)。`started` のままの試行も1回と数える。

`review_target.json` の形式:

```json
{
  "attempt": 1,
  "artifacts": {
    "data_dir": {
      "runs/<date>/hot_candidates.jsonl": "<SHA-256>",
      "runs/<date>/article_proposals.jsonl": "<SHA-256>",
      "runs/<date>/selection_input.json": "<SHA-256>",
      "runs/<date>/digest_summaries.json": null,
      "runs/<date>/source_overviews.json": "<SHA-256>"
    },
    "reports_dir": {
      "daily/<date>.md": "<SHA-256>"
    }
  }
}
```

- `artifacts` はレビュー対象の6つの成果物のSHA-256(16進の小文字)。パスは `data_dir` / `reports_dir` からの相対。存在しないファイルは `null`。`evidence_fetch_log.tsv` は追記され続けるため含めない。
- 計算は `storage/agent_progress.py` の `review_artifact_hashes` で行う。再開時に今の成果物と比べる判定(#42)も同じ関数を使う。

### `progress retry --date <date> --stage <stage> [--kind corrupt_input|selection_mismatch]`

自己修正の再実行を1回記録する。上限を超えても記録して終了コード0で終え、標準出力に次のJSONを出す(止めるかどうかはSkillが判断する)。

```json
{"stage": "score", "kind": "fix", "count": 2, "limit": 1, "allowed": false, "limit_reached": true}
```

- 呼ぶ順番: Skillは再実行の **直前** に `progress retry` を呼び、`allowed` が `false` なら再実行しない(記録は残る)。

- `kind`: `--kind` を付けなければ `fix`(エラー時の自己修正)。`--kind corrupt_input` は壊れた入力の流し直し、`--kind selection_mismatch` は `report` が記録した `selection_mismatch`(選抜の記録と `hot_candidates.jsonl` の食い違い)を直すための再実行。
- `count`: この記録を含む回数。`fix` はステージごと、`corrupt_input` / `selection_mismatch` はステージによらずその日全体で数える。`fix` / `corrupt_input` / `selection_mismatch` はそれぞれ別に数える。
- `limit`: 下の表の上限。
- `allowed`: `count` が `limit` 以下(この再実行は上限内)。例: `normalize` の1回目は `allowed: true`、2回目は `allowed: false`。
- `limit_reached`: `count` が `limit` 以上(この後は再実行しない。再開時の判定(#42)の「上限に達したステージには戻さない」と同じ意味)。上限内の最後の再実行では `allowed` と `limit_reached` がどちらも `true` になる。`corrupt_input` / `selection_mismatch` の `limit_reached` は、その種類の再実行をその日もう行わないことを表し、ステージ単位の判定ではない。

上限(`skills/agent-daily-run/recovery.md` の決まりに対応する数値の正本。実装は `storage/agent_progress.py` の `FIX_LIMITS` / `CORRUPT_INPUT_LIMIT` / `SELECTION_MISMATCH_LIMIT`):

| `--stage` | `fix` の上限(ステージごと) | `--kind corrupt_input` | `--kind selection_mismatch` |
| --- | --- | --- | --- |
| `collect` | 1 | 指定できる | 指定できない |
| `normalize` | 1 | 指定できる | 指定できない |
| `score` | 1 | 指定できる | 指定できる |
| `select-hot` | 3 | 指定できない | 指定できる |
| `save-proposals` | 3 | 指定できる | 指定できない |
| `add-summary` | 3 | 指定できない | 指定できない |
| `add-source-overview` | 3 | 指定できない | 指定できない |

- `collect` / `normalize` / `score` の `fix` を1回にしているのは、失敗の原因が環境(設定ファイル・ディスク・`run_state.json` の破損)にあることが多く、流し直しても結果が変わらないため。Agentが直せるのは引数の書き間違いで、1回の修正で足りる。`collect` のSource単位の失敗は終了コード0のため再実行しない(通信の一時的な失敗はSourceの中で再試行している)。引数の誤りでargparseが終了コード2で終わった場合も、同じ `fix` の1回として数える。
- `corrupt_input` の流し直しの上限は、その日全体で1回。`--stage` には流し直しを始めるステージ(`recovery.md` の「壊れた入力(`corrupt_input`)」の表の「再実行を始めるステージ」)を指定する。それ以外のステージに `--kind corrupt_input` を付けた場合は終了コード1。
- `selection_mismatch` の再実行の上限も、その日全体で1回(`corrupt_input` の流し直しの1回とは別に数える。Issue #21)。`--stage` には再実行を始めるステージを指定する: 選抜をやり直す場合(`deferred` なのに選抜あり、`completed` なのに選抜0件。後者は手順4の選抜の判断からやり直すが、最初に実行するステージは `select-hot`)は `select-hot`、`hot_candidates.jsonl` がない場合は `score`。それ以外のステージに付けた場合は終了コード1。
- `--stage` に指定できるのは上の7つ(`add-summary` / `add-source-overview` はステージではないが、再実行の回数を数える対象)。
- 記録は `{"stage": ..., "kind": ..., "recorded_at": ...}` を `agent_progress.retries` に追加する。

### `progress finalize --date <date>` / `progress complete --date <date>`

- `finalize`: 手順10(`mark-needs-review` → `report` の作り直し → `progress complete`)に入ったことを `agent_progress.finalized_at` に記録する。
- `complete`: その日の実行の完了(手順9で承認された時点、または手順10を終えた時点)を `agent_progress.completed_at` に記録する。`needs_review` は記録しない(従来どおり `mark-needs-review` で記録する)。
- どちらも、再び実行すると時刻を上書きする(手順10は途中で止まったら最初からやり直すため)。標準出力には何も出さない。
