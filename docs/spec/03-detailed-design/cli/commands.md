# Agent経路のサブコマンド契約

旧設計書の該当節を分割した資料。現行と移行目標の区別は [文書全体の入口](../../../README.md) から確認する。

## 共通の引数

- `--data-dir`(全サブコマンド)/ `--reports-dir`(`daily` と `report`): 省略時は `--runtime-config`(既定 `config/runtime.yaml`)の `output.data_dir` / `output.reports_dir`、それも無ければ `data` / `reports`。引数を指定した場合は設定ファイルより優先する。
- `--runtime-config`: `runtime.yaml` のパス。ファイルが無い・読めない場合も止めず、既定値で続ける([設定ファイル](configuration.md))。
- `--date`(`collect` / `daily` 以外): 対象日(`YYYY-MM-DD`)。
- `run_state.json` が壊れている(JSONとして読めない、オブジェクトでない)場合は、どのサブコマンドも記録できないため、標準エラーに `error: <メッセージ>` を出して終了コード1で終わる。

## Agent経路のサブコマンド

入力契約は [HOT選抜](../data-models/hot-selection.md)、[記事企画](../data-models/article-proposals.md)、[補助記録](../reporting/supplement-records.md) を参照。概要・傾向の作成条件は [ダイジェスト設計](../reporting/digest.md) にある。

`agent-daily-run` は `collect` / `normalize` / `score` / `select-hot` / `save-proposals` / `add-summary` / `add-source-overview` / `report` / `mark-needs-review` を使う。各サブコマンドの引数とエラーは次の通り(選抜・記事企画・概要についてはPipeline設計「注目候補・新モデルリリースの概要補完」、Sourceごとの本日の傾向についてはPipeline設計「Sourceごとの本日の傾向」も参照)。

前のステージが出力したjsonlが壊れている場合の扱いは、`normalize` / `score` / `select-hot` / `save-proposals` / `add-source-overview` / `report` で共通である(Issue #18)。

- エラー種別は `corrupt_input`。Agent自身が書いた入力(`selection_input.json` / `draft_proposals.json` / `source_overview_input.json` / CLI引数)の不正である `invalid_input`(入力を書き直せば直る)と区別し、`corrupt_input` は前のステージを再実行すれば直るものに使う。
- 対象: UTF-8として読めないファイル、JSONとして読めない行、オブジェクトでない行、デコーダ(`decode_signal` / `decode_event` / `decode_hot` / `decode_proposal`)が出す `KeyError`(必須キーの欠落)・`TypeError` / `ValueError`(`QualityValidationError` を含む。デコーダが検出できる範囲の型の不正)、ファイルを開けない・読めない(`OSError`)。デコーダが検出できない値の不正(例: `raw_metrics` の値が文字列)は対象外。
- 読み込みは `storage/jsonl.py` の `read_decoded_jsonl(path, decoder)`(デコーダを通さない場合は `read_jsonl(path)`)で行い、上の失敗はすべて `JsonlReadError` になる。メッセージは `<path>:<行番号>: <内容>`(例: `data/runs/2026-10-06/hot_candidates.jsonl:3: missing key 'hot_id'`)。行番号が分からない場合(`OSError`)は `<path>: <内容>`。必須キーの欠落は `missing key '<key>'`、デコーダのそれ以外の失敗は `invalid record: <例外>`、UTF-8の失敗は `invalid UTF-8: <理由>` とする。
- 各コマンドの記録の仕方は下の各項目のとおり。`report` 以外は終了コード1にし、出力ファイルは書き換えない。
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
  - `--input` は `{"schema_version": 2, "proposals": [...], "deferral_reason": "..."}` 形式のJSONファイル。パスはカレントディレクトリを基準にする。Agent経路では `data/runs/<date>/draft_proposals.json` に書く。選抜0件の日も `{"schema_version": 2, "proposals": []}` で実行する。
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


- `add-summary --date <date> --input <path>`: 当日のレポートに表示する注目候補(過去日の候補など)・新モデルリリースの概要を `data/runs/<date>/digest_summaries.json` に保存する。パイプラインのステージ(`stages_completed`)としては扱わない。
  - `--input` は `{"<hot_id または key>": "概要"}` 形式のJSONファイル。パスはカレントディレクトリを基準にする。Agent経路では `data/runs/<date>/summary_input.json` に書く。新モデルリリースの `key` はクエリ文字列(`=` を含む)を持つことがあるため、コマンドライン引数ではなくファイルで渡す。
  - キーは、当日のレポートに表示される注目候補のうち候補自身が `summary` を持たないものの `hot_id`(候補自身の `summary` が優先されるため、それ以外への保存は表示に反映されない)と、表示される新モデルリリースの `key` に限る。`report --list-missing-summaries` の対象と、すでに補完済みの項目がこれに当たる。
  - 値は前後の空白を除いて保存し、同じキーは上書きする。
  - エラー時は `run_state.json` の `errors` に記録して終了コード1にし、`digest_summaries.json` は書き換えない。エラーの種別は次の通り。

    | 種別 | 条件 | 終了コード |
    | --- | --- | --- |
    | `invalid_input` | `--input` の指定がない、ファイルが読めない・UTF-8でない・JSONとして解釈できない、トップレベルがオブジェクトでない | 1 |
    | `missing_input` | `--input` のファイルがない | 1 |
    | `invalid_summary` | 中身が空のオブジェクト、対象外のキーがある、値が文字列でない・空 | 1 |
    | `write_error` | `digest_summaries.json` の読み書きに失敗した(既存ファイルが壊れている場合を含む) | 1 |

- `add-source-overview --date <date> --input <path>`: 収集Source一覧の各見出しに出す「本日の傾向」を `data/runs/<date>/source_overviews.json` に保存する(データ契約「Source Overviews記録」)。パイプラインのステージ(`stages_completed`)としては扱わない(`add-summary` と同じ)。
  - `--input` は `{"<source名>": "本文"}` 形式のJSONファイル。パスはカレントディレクトリを基準にする。Agent経路では `data/runs/<date>/source_overview_input.json` に書く。
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
  - レポートまたは `report_digest.json` の書き込みに失敗した場合は `report_write_error`(`source: report`)を記録し、終了コード1にする。
  - 直近3日分を集約する注目候補・新モデルリリース(Pipeline設計「日次ダイジェスト」)は、読めない日を飛ばして警告に残す。当日の `hot_candidates.jsonl` が壊れている場合は、この警告と上の注記の両方に出る。
  - `run_state.json` の `needs_review` が `true` なら、レポートの見出しの直後に要確認の警告を出す(データ契約「Daily Markdown Report」)。
- `report --list-missing-summaries`: 概要がない注目候補・新モデルリリース(表示分のみ)を、`kind`(`notable` / `model_release`)付きのJSON Linesで出力する(Pipeline設計「注目候補・新モデルリリースの概要補完」参照)。レポート・`report_digest.json`・`run.jsonl`・`run_state.json` は書き換えない。
- `mark-needs-review --date <date>`: 品質レビューループ(`agent-daily-run` 手順9〜10)が3回で解消しなかったことを `run_state.json` に `needs_review: true` として記録する。`report` を実行するとレポートの冒頭に要確認の警告が出る(再生成しても消えない)。記録だけを行い、レポートは書き換えないため、続けて `report` を実行する。`errors` には何も記録しない。その日の `run_state.json` がない場合は(`--date` の打ち間違いで新しく作らないよう)何も書かずに終了コード1にする。`collect` は実行のはじめに `needs_review` を消す(その日の実行をやり直すため)。
