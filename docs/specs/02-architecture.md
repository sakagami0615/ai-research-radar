# 02. アーキテクチャ設計

## 全体像

処理の流れは次のとおり。Agent経路と決定論経路は、収集からHOT候補の作成までを共通の処理で行い、選抜と記事企画の作り方だけが違う。

```text
Source
  |  Source Adapter(取得・RawItem化・CanonicalSignal化)
  v
RawItem JSONL / CanonicalSignal
  |  Source内スコア正規化 → Dedup → Event → Topic
  v
Event / Topic JSONL
  |  HOT Scoring(候補化)
  v
HOT候補
  |  選抜・記事企画(Agent経路: Agentが判断 / 決定論経路: スコア順と定型生成)
  v
選抜HOT・記事企画
  |  日次ダイジェスト(注目候補・新モデルリリース)の集約
  v
Markdownレポート + Run Metadata
```

## 2つの実行経路

### Agent経路(本番の推奨)

cronから `claude -p` / `codex exec` で起動したAgentが、`agent-daily-run` Skillに従ってCLIのサブコマンドを順に実行する。HOTの最終選抜、概要、記事企画、Sourceごとの本日の傾向はAgentが書き、CLIが検証して保存する。

```text
collect → normalize → score → select-hot → save-proposals
        → add-summary / add-source-overview → report
        → (別プロセスのAgentによるレビュー・修正ループ) → mark-needs-review(未解消時のみ)
```

各サブコマンドは、日付ごとの実行状態 `data/runs/<date>/run_state.json` を読み書きして、完了した段階・エラー・選抜と記事企画の結果(`stage_results`)を引き継ぐ(03章「RunMetadata」、06章)。

### 決定論経路(手動確認・CI向け)

`ai-radar daily` が1回の呼び出しで収集からレポートまでを行う。選抜はスコア順、記事企画は定型の生成(05章「Article Ideation」)で、外部LLMやAgentを使わない。`run_state.json` は使わず、`run.jsonl` だけを書く。

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

## 依存方向

```text
cli
  -> config / periods / sources / normalization / pipeline / scoring / ideation / reporting / storage / schemas

pipeline
  -> sources / normalization / scoring / ideation / reporting / storage / periods / schemas

sources
  -> config / normalization / periods / storage / schemas

reporting
  -> normalization / storage / schemas

normalization
  -> periods / schemas

config
  -> periods

scoring / ideation / storage
  -> schemas
```

- PipelineとCLIはSource Adapterのインターフェースにだけ依存し、Source固有のレスポンス形式はAdapterに閉じ込める。どのAdapterを使うかは `config/sources.yaml` の `adapter` で決まる(04章)。
- Scoring・Ideation・ReportingはSource固有の実装を知らない。
- CLIのサブコマンドは前の段階の出力ファイルを入力にし、互いのモジュールを直接呼ばない。

## 例外処理

- Source単位の失敗は `errors` に記録し、他のSourceを続ける。
- Agent経路の各サブコマンドは、入力の不足・破損・不正を `run_state.json` の `errors` に種別付きで記録し、終了コード1で終わる(06章)。`run_state.json` 自体が壊れている場合は記録できないため、標準エラーにメッセージを出して終了コード1で終わる。
- 決定論経路の後段(保存・レポート生成)で失敗した場合は、可能な限り `data/runs/<date>/run.jsonl` に失敗記録を保存してから例外を再送出する。
- 出力先自体が書き込めない場合は実行記録を残せないため、運用上の制約として扱う。
