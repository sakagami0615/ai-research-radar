# 設定の契約と優先順位

旧設計書の該当節を分割した資料。現行と移行目標の区別は [文書全体の入口](../../../README.md) から確認する。

## 設定ファイル

設定は `config/` 配下に置く。

- `sources.yaml`: Source一覧、family、adapter、keyword、RSS URL、新モデル検知の監視対象(公式feed、HF org、Ollama)など
- `scoring.yaml`: HOT判定の重み(`hot_score`)、閾値と決定論経路の選抜数(`hot_selection.minimum_score` / `max_limit`)
- `runtime.yaml`: 出力先(`output`)、レポートの表示用タイムゾーン(`runtime.timezone`、IANA名)、省略時の収集期間の上限日数(`collection.max_lookback_days`)などの実行時設定

CLI引数は設定ファイルより優先される。

`runtime.timezone` は日次レポートのRun Summaryに出すPeriodの表示にだけ使う(期間の計算やファイル名の日付には使わない)。`ai-radar daily` と `ai-radar report` はどちらも `--runtime-config`(既定 `config/runtime.yaml`)から読み込む。ファイルが無い・読めない、`runtime.timezone` が無い、タイムゾーン名が不正のいずれでも止めず、UTCで表示する(表記は `(UTC)`)。

`collection.max_lookback_days` は `ai-radar daily` と `ai-radar collect` が `--runtime-config`(既定 `config/runtime.yaml`)から読み込む。正の整数でない場合は既定値7を使う。ファイルが無い・読めない場合も既定値7で続行する。
