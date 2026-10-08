# 06. CLI・運用設計

## CLI

実行入口は `ai-radar` である。

```bash
ai-radar daily
```

`daily` と `collect` は `--since` / `--until` を省略できる。両方を省略した場合は、実行時刻を終了時刻とし、前回実行から引き継いだ期間を対象にする。実行時刻はAsia/Tokyoで扱い、Sourceへはタイムゾーン付きISO 8601日時を渡す。`--since` / `--until` を明示した場合は指定値をそのまま使う。

省略時の開始時刻は次のように決める。実行しなかった日の記事を取りこぼさないためである。

- `data/runs/<日付>/run.jsonl` のうち、日付ディレクトリ名が対象日(実行時刻のAsia/Tokyoの日付)より前のものを新しい順に見て、最初に見つかった有効な記録の `until` を開始時刻にする。対象日の記録を使わないのは、同日再実行で同じ期間を取り直すためである(`raw` は上書き保存)。
- 日付のみの `until`(例: `"2026-10-02"`)は、その日の00:00(UTC)と記録の `started_at` の早いほうとして扱う。取りこぼさない側に倒すため、前回の期間と1日強(JSTの朝に実行された記録では最大で約1日+9時間)重なることがある(重複は日次ダイジェストの表示済み除外で吸収される)。
- 日付でないディレクトリ名、読めない `run.jsonl`、解釈できない・実行時刻以降の `until` は無視して、さらに前の記録を探す。
- 開始時刻は `runtime.yaml` の `collection.max_lookback_days`(既定7)日前より前にしない。前回の記録がない初回も、この日数分を集める。
- 件数上限付きのSource(qiita / arXiv / GitHub / huggingface / npm / PyPI は100件、huggingface_orgs はorgあたり50件)は、期間が長いと取り切れない場合がある。
- 既知の限界:
  - `run.jsonl` が書かれる前に止まった実行(`collect` 後に `report` まで到達しなかった等)は前回実行とみなされず、次回はさらに前の記録から引き継ぐため期間が重なる。その実行はレポートを出していないため実害は小さい。
  - `run.jsonl` は上書き保存のため、検証目的の再実行や `--since` / `--until` を明示した再実行が、その日の記録を置き換える。影響は期間が重なる側に倒れる。
  - あるSourceがその回だけ失敗しても実行全体の `until` は記録されるため、次回はその `until` から再開し、失敗したSourceのその期間は戻らない(従来と同じ)。
  - `overlap_hours` を持つSourceの重ね取得に関する限界は04章「重ね取得と収集済み除外」を参照。

明示指定する場合:

```bash
ai-radar daily \
  --since 2026-09-24 \
  --until 2026-09-25 \
  --data-dir data \
  --reports-dir reports \
  --minimum-score 75 \
  --hot-limit 5
```

### Agent経路のサブコマンド

`agent-daily-run` は `collect` / `normalize` / `score` / `select-hot` / `save-proposals` / `add-summary` / `add-source-overview` / `report` を使う。選抜・記事企画・概要(05章「注目候補・新モデルリリースの概要補完」)・Sourceごとの本日の傾向(05章「Sourceごとの本日の傾向」)に関わる引数は次の通り。

- `select-hot --date <date> [--input <path>] [--limit <n>]`: `selection_input.json`(03章「SelectionInput」)を読み込んで検証し、当日の `hot_candidates.jsonl` の `selected` / `assessment` / `summary` を更新する。
  - `--input` を省略した場合は `<data-dir>/runs/<date>/selection_input.json` を読む。明示したパスは、`save-proposals --input` と同じくカレントディレクトリを基準にする。
  - `--limit` は選抜件数の上限で、既定値は2、範囲は0〜5。整数でない値は `invalid_input` にする(argparseの終了コード2ではなく `errors` に記録する)。範囲外も `invalid_input` にする。
  - 旧オプション `--select` / `--reason` / `--summary` は廃止した。指定すると `deprecated_option` として、`selection_input.json` に assessments / screened_ids / selection_reason / summaries を書いて `select-hot --date <date>` を実行するよう促す移行メッセージを返す。
  - `summaries` で指定しなかった候補は既存の `summary` を保持し、指定した候補は(前後の空白を除いた値で)置き換える。`summaries` がdictでない、当日の候補にない `hot_id` がある、値が空または文字列でない場合は `invalid_summary` にする。
  - 選抜した候補に概要がない(`summaries` にも既存データにもない)場合は `missing_summary` にする。選抜外の候補に概要がない場合は、終了コード0のまま `run_state.json` の `errors` に `missing_summary_warning` として件数と `hot_id` を記録する。
  - `screened_ids` に含まれない(未確認の)候補があれば、終了コード0のまま `errors` に `unreviewed_candidates` として件数と `hot_id` を記録する。
  - 実行のはじめに `run_state.json` の `select-hot` のエラー・警告を消すため、再実行すると以前の警告は残らない。成功時は `output_counts.selected_hot` に選抜件数を記録し、`select-hot` を完了段階にして、`run_state.json` の `stage_results` に、選抜1件以上なら `completed`、0件なら `deferred` を、`selection_reason` と件数(候補・確認・未確認・選抜)とともに記録する。あわせて `save-proposals` の記録が初期値以外なら `not_run`(選抜の再実行により無効)に戻す。`errors` に記録して終了コード1にするエラー時は `failed` を記録する。`run_state.json` 自体が読めない場合(`RunStateError`)は `stage_results` を更新しない(03章「RunMetadata」)。
  - エラー時は `run_state.json` の `errors` に記録して終了コード1にし、`hot_candidates.jsonl` は書き換えない。エラー・警告の種別は次の通り。

    | 種別 | 条件 | 終了コード |
    | --- | --- | --- |
    | `deprecated_option` | 旧オプション `--select` / `--reason` / `--summary` を指定した | 1 |
    | `missing_input` | `hot_candidates.jsonl` または `selection_input.json` がない | 1 |
    | `invalid_input` | `--limit` が整数でない・範囲外、`selection_input.json` がJSONとして読めない、トップレベルの構造が不正 | 1 |
    | `invalid_assessment` | 選抜理由が空、ID の重複・不整合、評価レコードの内容が不正、選抜に `verified` かつ `primary` の根拠がない | 1 |
    | `selection_limit_exceeded` | 選抜件数が `--limit` を超える | 1 |
    | `invalid_summary` | `summaries` が不正 | 1 |
    | `missing_summary` | 選抜した候補に概要がない | 1 |
    | `write_error` | `hot_candidates.jsonl` の書き込みに失敗した | 1 |
    | `missing_summary_warning` / `unreviewed_candidates` | 選抜外の候補に概要がない / 未確認の候補がある(警告) | 0 |

- `save-proposals --date <date> --input <path>`: 記事企画のJSON配列を検証して `article_proposals.jsonl` に保存する。選抜0件の日も空の配列 `[]` で実行する(#11 完了後はオブジェクト形式)。成功時は `stage_results` に、企画1件以上なら `completed`、選抜ありで企画0件なら `deferred`、選抜0件なら `not_run`(選抜HOTなし)を `proposal_count` とともに記録し、`output_counts.article_proposals` に企画件数を記録して、`save-proposals` を完了段階にする。エラー(`missing_input` / `invalid_input` / `invalid_proposal` / `write_error`。入力がUTF-8でない場合は `invalid_input`、配列の要素がオブジェクトでない場合は `invalid_proposal`)は `errors` に記録して `failed` を記録し、終了コード1にする(`run_state.json` 自体が読めない場合は `stage_results` を更新しない)。`write_error` のメッセージは `failed to write article proposals: <例外>` である。
- `add-summary --date <date> --input <path>`: 当日のレポートに表示する注目候補(過去日の候補など)・新モデルリリースの概要を `data/runs/<date>/digest_summaries.json` に保存する。パイプラインのステージ(`stages_completed`)としては扱わない。
  - `--input` は `{"<hot_id または key>": "概要"}` 形式のJSONファイル。パスはカレントディレクトリを基準にする。Agent経路では `data/runs/<date>/summary_input.json` に書く。新モデルリリースの `key` はクエリ文字列(`=` を含む)を持つことがあるため、コマンドライン引数ではなくファイルで渡す。
  - キーは、当日のレポートに表示される注目候補のうち候補自身が `summary` を持たないものの `hot_id`(候補自身の `summary` が優先されるため、それ以外への保存は表示に反映されない)と、表示される新モデルリリースの `key` に限る。`report --list-missing-summaries` の対象と、すでに補完済みの項目がこれに当たる。
  - 値は前後の空白を除いて保存し、同じキーは上書きする。
  - 旧オプション `--summary` は廃止した。指定すると `deprecated_option` として、JSONファイルに書いて `--input` で渡すよう促す移行メッセージを返す。`--summary` の判定は他の検証より先に行う。
  - エラー時は `run_state.json` の `errors` に記録して終了コード1にし、`digest_summaries.json` は書き換えない。エラーの種別は次の通り。

    | 種別 | 条件 | 終了コード |
    | --- | --- | --- |
    | `deprecated_option` | 旧オプション `--summary` を指定した | 1 |
    | `invalid_summary` | `--input` の指定がない、中身が空のオブジェクト、対象外のキーがある、値が文字列でない・空 | 1 |
    | `missing_input` | `--input` のファイルがない | 1 |
    | `invalid_input` | ファイルが読めない・UTF-8でない・JSONとして解釈できない、トップレベルがオブジェクトでない | 1 |
    | `write_error` | `digest_summaries.json` の読み書きに失敗した(既存ファイルが壊れている場合を含む) | 1 |

- `add-source-overview --date <date> --input <path>`: 収集Source一覧の各見出しに出す「本日の傾向」を `data/runs/<date>/source_overviews.json` に保存する(03章「Source Overviews記録」)。パイプラインのステージ(`stages_completed`)としては扱わない(`add-summary` と同じ)。
  - `--input` は `{"<source名>": "本文"}` 形式のJSONファイル。パスはカレントディレクトリを基準にする。Agent経路では `data/runs/<date>/source_overview_input.json` に書く。
  - Source名は、当日の `run_state.json` の `sources` にあるもの、または `sources` にないSourceのSignalをまとめた見出し(`other`。同じ名前のSourceが実在する場合は `_other`)に限る。レポートの見出しと同じ名前・同じ件数で判定する(`other` / `_other` は該当するSignalがあるときだけ受け付ける)。
  - そのSourceの当日の件数(`data/normalized/<date>/signals.jsonl` の件数。レポートの見出しの件数と同じ)が0件なら受け付けない。
  - 値は前後の空白を除いて保存し、同じSourceは上書きする。文字数は検証しない(レビューで確認する)。
  - 実行のはじめに `run_state.json` の `add-source-overview` のエラーを消す。入力のすべての項目を検証してから保存するため、1つでも不正な項目があれば何も保存しない。
  - エラー時は `run_state.json` の `errors` に記録して終了コード1にし、`source_overviews.json` は書き換えない。エラーの種別は次の通り。

    | 種別 | 条件 | 終了コード |
    | --- | --- | --- |
    | `invalid_input` | `--input` の指定がない、ファイルがない・読めない・UTF-8でない・JSONとして解釈できない、トップレベルがオブジェクトでない。当日の `signals.jsonl` が読めない | 1 |
    | `invalid_overview` | 中身が空のオブジェクト、レポートの見出しにないSource名、本文が文字列でない・空、そのSourceの当日の件数が0件 | 1 |
    | `write_error` | `source_overviews.json` の読み書きに失敗した(既存ファイルが壊れている場合を含む) | 1 |

- `report --list-missing-summaries`: 概要がない注目候補・新モデルリリース(表示分のみ)を、`kind`(`notable` / `model_release`)付きのJSON Linesで出力する(05章「注目候補・新モデルリリースの概要補完」参照)。レポート・`report_digest.json`・`run.jsonl`・`run_state.json` は書き換えない。

## 設定ファイル

設定は `config/` 配下に置く。

- `sources.yaml`: Source一覧、family、adapter、keyword、RSS URL、新モデル検知の監視対象(公式feed、HF org、Ollama)など
- `scoring.yaml`: HOT判定の重み、閾値、選抜数
- `runtime.yaml`: 出力先(`output`)、レポートの表示用タイムゾーン(`runtime.timezone`、IANA名)、省略時の収集期間の上限日数(`collection.max_lookback_days`)などの実行時設定
- `categories.yaml`: category定義の予約設定。現行MVPのPipelineはまだ読み込まず、公開SourceのカテゴリはAdapter側で付与する。

CLI引数は設定ファイルより優先される。

`runtime.timezone` は日次レポートのRun Summaryに出すPeriodの表示にだけ使う(期間の計算やファイル名の日付には使わない)。`ai-radar daily` と `ai-radar report` はどちらも `--runtime-config`(既定 `config/runtime.yaml`)から読み込む。`report` では、ファイルが無い・読めない、`runtime.timezone` が無い、タイムゾーン名が不正のいずれでもレポート生成を止めず、UTCで表示する(表記は `(UTC)`)。`daily` はこれまで通りruntime設定ファイルが無ければエラーになるが、`runtime.timezone` が無い・不正な場合は同じくUTCで表示する。

`collection.max_lookback_days` は `ai-radar daily` と `ai-radar collect` が `--runtime-config`(既定 `config/runtime.yaml`)から読み込む。正の整数でない場合は既定値7を使う。`collect` はファイルが無い・読めない場合も既定値7で続行する(`daily` はruntime設定ファイルが無ければこれまで通りエラー)。

## cron想定

推奨はcronから `claude -p` / `codex exec` を直接起動するAI Agent(Claude Code / Codex)経由の実行である(ラッパースクリプトは使わない)。渡すプロンプトは `skills/agent-daily-run/SKILL.md` を読ませる `skills/agent-daily-run/entry-prompt.txt` であり、`collect` / `normalize` / `score` / `select-hot` / `save-proposals` / `add-summary` / `add-source-overview` / `report` の実行、概要の作成・補完、Sourceごとの本日の傾向の作成、対象日の判定、レビュー・修正ループまでAgent自身が判断して行う。

`ai-radar`/`claude`/`codex` はいずれもPATH依存のコマンドであり、cronの実行環境には通常PATHが通っていないため、crontabファイル先頭に `PATH=` 行が必要になる。同日の多重実行(ログが混ざる)を防ぐため `flock -n` で排他制御し、レポート未生成時にcronの失敗通知が機能するよう末尾で `test -f` による確認を行う。

```cron
PATH=/path/to/.pyenv/shims:/path/to/.local/bin:/path/to/.nvm/versions/node/<version>/bin:/usr/local/bin:/usr/bin:/bin

15 8 * * * cd /path/to/ai-research-radar && mkdir -p logs && D="$(date +\%F)" && flock -n logs/.daily.lock -c 'claude -p "$(cat skills/agent-daily-run/entry-prompt.txt)" --permission-mode bypassPermissions >> logs/agent-daily-run-'"$D"'.log 2>&1 && test -f reports/daily/'"$D"'.md'
```

- `codex` で実行する場合は `claude -p "..." --permission-mode bypassPermissions` を `codex exec "..." --sandbox workspace-write` に置き換えた別のcron行を使う(両方を同時に有効化しない)。
- 実行ログは `logs/agent-daily-run-<date>.log` に出力される。
- レポート生成後、Agent自身が別プロセスの `claude -p` / `codex exec` を起動して `skills/review-daily-report/SKILL.md` によるレビューを行わせ、指摘があれば自分自身で修正して最大3回まで再試行する(`skills/agent-daily-run/SKILL.md` 手順9〜10)。3回解消できなければレポートに警告バナーを追加し `run_state.json` に `needs_review: true` を記録する。

上記のレビュー起動(Agent自身が別プロセスの `claude -p` / `codex exec` を起動する手順)はcronからの起動を前提とする。対話セッション(IDE拡張のAuto Modeなど)内で `agent-daily-run` を手動実行する場合、Bash経由で `claude -p ... --permission-mode bypassPermissions` を新規起動しようとすると、そのセッション固有の権限分類器に「Create Unsafe Agents」として拒否されることがある。この場合は同一セッション内のsubagent(Agent機能)へレビューを委譲する代替手段で対応してよい。cronによる本番実行はこの制約を受けない独立プロセスであるため、設計自体は変更不要である。

決定論的な `ai-radar daily` を直接cronに書く方法も、手動運用・CI向けの代替手段として利用できる。

```cron
15 8 * * * cd /path/to/ai-research-radar && ai-radar daily >> logs/ai-radar.log 2>&1
```

いずれの方式でも、Python環境、PATH、作業ディレクトリ、ログ出力先を明示する。

## 手動実行時の確認順序

1. CLIが終了コード0で終わるか確認する。
2. `data/runs/<date>/run.jsonl` を確認する。
3. `errors` にSource失敗がないか確認する。
4. `reports/daily/<date>.md` を確認する。選抜HOTの下に「注目候補(選抜外)」「新モデルリリース」が直近3日分の未掲載項目として出る。選抜HOTと注目候補には各項目の見出し直後に、新モデルリリースには各項目の次の行に、日本語の概要が出る(Agent経路のみ。決定論経路では「概要未作成」)。末尾の「収集Source一覧」で、選抜HOTだけでなく当日収集した全Sourceの生一覧(Sourceごとの件数、タイトル、URL、概要)も確認できる。各Sourceの見出しの直下には、Sourceごとの「本日の傾向」が日本語で出る(Agent経路のみ。決定論経路では「傾向未作成」。収集0件のSourceは「収集0件」)。
5. HOT候補のEvidence URLを確認する。

## 外部ネットワーク制約

DNSやネットワークが利用できない環境では、公開Sourceは失敗する。その場合でもPipelineは失敗をRunMetadataとMarkdownへ記録し、可能な範囲で空の後続JSONLを生成する。

外部Sourceの成功経路は、ネットワーク可能な環境で定期smoke testを実行する。

## 出力の保持

MVPでは出力のローテーションや削除は自動化しない。cron運用では、保存期間、バックアップ、不要データ削除を別途運用で決める。

## コミット運用

このプロジェクトでは、ユーザーが明示するまでコミットを作成しない。作業完了時は、変更内容、検証結果、レビュー状態を報告する。
