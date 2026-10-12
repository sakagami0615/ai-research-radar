# 構成要素と責任

旧設計書の該当節を分割した資料。現行と移行目標の区別は [文書全体の入口](../../README.md) から確認する。

## 主要コンポーネント

| パッケージ | 責務 | 主なモジュール |
| --- | --- | --- |
| `cli` | `ai-radar` の入口。引数の解釈、既定値(`config/runtime.yaml`)の解決、各段階の呼び出しとエラーの記録 | `cli/main.py`、`cli/commands/*.py`(1サブコマンド1ファイル)、`cli/commands/common.py`(既定ディレクトリ・エラー記録・入力ファイル読み込みの共通処理) |
| `config` | YAML設定の読み込み | `config/settings.py` |
| `sources` | Sourceごとの取得、RawItem化、CanonicalSignalへの変換。上位はSource固有の形式を知らない | `sources/base.py`(Adapterのインターフェース)、`sources/public.py`(公開Source。`adapter` ごとの定義表)、`sources/fixtures.py`、`sources/collection.py`(全Sourceの収集、重ね取得)、`sources/remap.py`(保存済みrawの取得処理別の補正) |
| `normalization` | Source内スコア正規化、重複排除、AI関連性のキーワード判定 | `normalization/scores.py`、`normalization/dedup.py`、`normalization/relevance.py` |
| `pipeline` | Event / Topicの生成、決定論経路の一括実行 | `pipeline/events.py`、`pipeline/daily.py` |
| `scoring` | HOT候補の作成、Agentの評価レコードの検証と適用 | `scoring/hot.py`、`scoring/assessments.py` |
| `ideation` | 記事企画の定型生成(決定論経路)と、Agentが書いた企画(v2)の検証 | `ideation/proposals.py`、`ideation/validation.py` |
| `reporting` | Markdownレポートの生成、日次ダイジェスト、Sourceごとの本日の傾向、表示用のエスケープ | `reporting/markdown.py`、`reporting/digest.py`、`reporting/source_overview.py`、`reporting/escape.py` |
| `storage` | ファイルの読み書き。すべての書き込みは一時ファイルからの置き換え(原子的書き込み) | `storage/files.py`、`storage/jsonl.py`、`storage/run_state.py` |
| `schemas` | 共通のデータ構造(dataclass)、保存データの読み込み(decoder)、Agent入力の検証 | `schemas/models.py`、`schemas/decoders.py`、`schemas/quality.py` |
| `periods` | 収集期間の解決(前回実行からの引き継ぎ)と日付の変換 | `periods.py` |
