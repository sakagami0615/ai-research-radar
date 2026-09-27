# 06. CLI・運用設計

## CLI

実行入口は `ai-radar` である。

```bash
ai-radar daily
```

`daily` は `--since` / `--until` を省略できる。省略時は、実行日の前日から当日までを対象にする。

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

## 設定ファイル

設定は `config/` 配下に置く。

- `sources.yaml`: Source一覧、family、adapter、keyword、RSS URLなど
- `scoring.yaml`: HOT判定の重み、閾値、選抜数
- `runtime.yaml`: 出力先などの実行時設定
- `categories.yaml`: category定義の予約設定。現行MVPのPipelineはまだ読み込まず、公開SourceのカテゴリはAdapter側で付与する。

CLI引数は設定ファイルより優先される。

## cron想定

例:

```cron
15 8 * * * cd /path/to/ai-research-radar && ai-radar daily >> logs/ai-radar.log 2>&1
```

cronでは、Python環境、PATH、作業ディレクトリ、ログ出力先を明示する。

## 手動実行時の確認順序

1. CLIが終了コード0で終わるか確認する。
2. `data/runs/<date>/run.jsonl` を確認する。
3. `errors` にSource失敗がないか確認する。
4. `reports/daily/<date>.md` を確認する。
5. HOT候補のEvidence URLを確認する。

## 外部ネットワーク制約

DNSやネットワークが利用できない環境では、公開Sourceは失敗する。その場合でもPipelineは失敗をRunMetadataとMarkdownへ記録し、可能な範囲で空の後続JSONLを生成する。

外部Sourceの成功経路は、ネットワーク可能な環境で定期smoke testを実行する。

## 出力の保持

MVPでは出力のローテーションや削除は自動化しない。cron運用では、保存期間、バックアップ、不要データ削除を別途運用で決める。

## コミット運用

このプロジェクトでは、ユーザーが明示するまでコミットを作成しない。作業完了時は、変更内容、検証結果、レビュー状態を報告する。
