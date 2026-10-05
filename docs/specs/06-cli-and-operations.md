# 06. CLI・運用設計

## CLI

実行入口は `ai-radar` である。

```bash
ai-radar daily
```

`daily` と `collect` は `--since` / `--until` を省略できる。両方を省略した場合は、実行時刻を終了時刻とし、前回実行から引き継いだ期間を対象にする。実行時刻はAsia/Tokyoで扱い、Sourceへはタイムゾーン付きISO 8601日時を渡す。`--since` / `--until` を明示した場合は指定値をそのまま使う。

省略時の開始時刻は次のように決める。実行しなかった日の記事を取りこぼさないためである。

- `data/runs/<日付>/run.jsonl` のうち、日付ディレクトリ名が対象日(実行時刻のAsia/Tokyoの日付)より前のものを新しい順に見て、最初に見つかった有効な記録の `until` を開始時刻にする。対象日の記録を使わないのは、同日再実行で同じ期間を取り直すためである(`raw` は上書き保存)。
- 日付のみの `until`(例: `"2026-10-02"`)は、その日の00:00(UTC)と記録の `started_at` の早いほうとして扱う。
- 日付でないディレクトリ名、読めない `run.jsonl`、解釈できない・実行時刻以降の `until` は無視して、さらに前の記録を探す。
- 開始時刻は `runtime.yaml` の `collection.max_lookback_days`(既定7)日前より前にしない。前回の記録がない初回も、この日数分を集める。
- 件数上限付きのSource(qiita / arXiv / GitHub / huggingface / npm / PyPI は100件、huggingface_orgs はorgあたり50件)は、期間が長いと取り切れない場合がある。
- 前回実行の `run.jsonl` が書かれる前に止まった場合や、あるSourceがその回だけ失敗した場合の扱いは、03章・04章を参照。

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

`agent-daily-run` は `collect` / `normalize` / `score` / `select-hot` / `save-proposals` / `add-summary` / `report` を使う。概要(05章「注目候補の概要補完」)に関わる引数は次の通り。

- `select-hot --summary <hot_id>=<概要>`: 候補の `summary` を保存する。繰り返し指定できる。指定しなかった候補は既存の `summary` を保持し、同じ候補を再指定した場合は置き換える。未知の `hot_id` や空の概要は `invalid_summary` として終了コード1にする。
  - 選抜した候補に概要がない(今回の指定にも既存データにもない)場合は `missing_summary` として終了コード1にし、`hot_candidates.jsonl` を書き換えない。
  - 選抜外の候補に概要がない場合は、終了コード0のまま `run_state.json` の `errors` に `missing_summary_warning` として件数と `hot_id` を記録する。
- `add-summary --date <date> --summary <hot_id>=<概要>`: 当日の注目候補に表示する過去日の候補などの概要を `data/runs/<date>/digest_summaries.json` に保存する。繰り返し指定できる。`hot_id` は当日のレポートに表示される注目候補のうち、候補自身が `summary` を持たないもの(`report --list-missing-summaries` の対象と、すでに `add-summary` で補完済みの項目)に限る。候補自身の `summary` が優先されるため、それ以外への保存は表示に反映されない。対象外の `hot_id`、空の概要、`--summary` の指定なしは `invalid_summary` として終了コード1にする(このときファイルは書き換えない)。パイプラインのステージ(`stages_completed`)としては扱わない。
- `report --list-missing-summaries`: 概要がない注目候補(表示分のみ)をJSON Linesで出力する。レポート・`report_digest.json`・`run.jsonl`・`run_state.json` は書き換えない。

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

推奨はcronから `claude -p` / `codex exec` を直接起動するAI Agent(Claude Code / Codex)経由の実行である(ラッパースクリプトは使わない)。渡すプロンプトは `skills/agent-daily-run/SKILL.md` を読ませる `skills/agent-daily-run/entry-prompt.txt` であり、`collect` / `normalize` / `score` / `select-hot` / `save-proposals` / `add-summary` / `report` の実行、概要の作成・補完、対象日の判定、レビュー・修正ループまでAgent自身が判断して行う。

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
4. `reports/daily/<date>.md` を確認する。選抜HOTの下に「注目候補(選抜外)」「新モデルリリース」が直近3日分の未掲載項目として出る。選抜HOTと注目候補には各項目の見出し直後に日本語の概要が出る(Agent経路のみ。決定論経路では「概要未作成」)。末尾の「収集Source一覧」で、選抜HOTだけでなく当日収集した全Sourceの生一覧(Sourceごとの件数、タイトル、URL、概要)も確認できる。
5. HOT候補のEvidence URLを確認する。

## 外部ネットワーク制約

DNSやネットワークが利用できない環境では、公開Sourceは失敗する。その場合でもPipelineは失敗をRunMetadataとMarkdownへ記録し、可能な範囲で空の後続JSONLを生成する。

外部Sourceの成功経路は、ネットワーク可能な環境で定期smoke testを実行する。

## 出力の保持

MVPでは出力のローテーションや削除は自動化しない。cron運用では、保存期間、バックアップ、不要データ削除を別途運用で決める。

## コミット運用

このプロジェクトでは、ユーザーが明示するまでコミットを作成しない。作業完了時は、変更内容、検証結果、レビュー状態を報告する。
