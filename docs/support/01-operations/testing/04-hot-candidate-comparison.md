# 04 HOT候補の前後比較

収集時に決まる判定(PyPIのAI関連度 `ai_keyword_strength`、公式ブログの `event_type`、新モデルリリースの `model_release` など)を変えたときに、実データの過去日でHOT候補の顔ぶれと件数がどう変わるかを確かめる手順。[#32](https://github.com/sakagami0615/ai-research-radar/issues/32) と [#34](https://github.com/sakagami0615/ai-research-radar/issues/34) の前後比較で使う。

先に [環境準備](01-environment.md) を行う。

## 仕組み

これらの判定は収集時に計算されて `data/raw/` / `data/collected/` に保存されるため、修正後に過去日の `score` を実行し直しても結果は変わらない。[scripts/compare_hot_candidates.py](../../../../scripts/compare_hot_candidates.py) は次のように作り直す。

1. 保存済みの `raw/<date>/*.jsonl` の `payload.raw` から、読み込んだコードの判定で RawItem を作り直す。`fetched_at` は保存済みの値を引き継ぐ(現在時刻にすると48時間の判定とスコアが変わるため)。
2. 各Adapterの `normalize` で `collected/<date>/signals.jsonl` を一時ディレクトリに作る。
3. その一時ディレクトリで `normalize` → `score` を実行し、HOT候補と各Signalの判定を snapshot(JSON)に記録する。

修正前と修正後は、同じスクリプトを、読み込むコード(`PYTHONPATH`)と設定ファイルだけを修正前(main)と修正後(作業ブランチ)に切り替えて実行し、比べる。保存済みの `runs/<date>/hot_candidates.jsonl` とは比べない(収集した後の無関係な変更の差分が混ざるため)。

読み込む data_dir は読むだけで書き換えない。作業用の一時ディレクトリは実行のたびに作って消す。

### 近似になる点・作り直さないもの

- 公式ブログのフィードの設定(`model_keywords` / `model_categories`)は raw に残らないため、記事の `provider` から、実行時の `config/sources.yaml` の設定を引く。収集日以降に設定が変わっていると近似になる。`provider` のフィードが1件でなければ止まる。`provider` がない記事(OpenAIだけを読んでいた単一フィード時代のもの)は OpenAI として扱う。
- 公式ブログの raw に残る category は先頭の1件だけなので、`model_categories` の判定は近似になる。Atom フィードの category(`term` 属性)は raw に残らないため、Atom フィードに `model_categories` を設定すると判定できない(2026-10 時点で設定しているのは RSS の OpenAI だけ)。
- Ollama は記事ページを取得して `model_release` を決めるため、raw から作り直さず、保存済みの RawItem をそのまま使う。#32 の決定では「raw から作り直せない Source は保存済みの `collected/` を使う」としていたが、`collected/` がない日(2026-09-29 など)もあるため、同じ内容を持つ raw の RawItem を使う。
- `config/sources.yaml` に有効な設定がない Source の raw があると止まる。huggingface_orgs の記事に `model_release.provider` がない場合も止まる。

## 実行

スクリプトは作業ブランチのものを使い、修正前は main の worktree の `src/` と `config/` を、修正後は作業ブランチの `src/` と `config/` を読み込ませる(スクリプトを修正前と修正後で同じにするため)。`--source-data-dir` には、過去日の `raw/` がある data_dir を絶対パスで指定する(worktreeには `data/` がないことが多い)。snapshot の出力先はworktreeの外(一時ディレクトリなど)にする。

以下は作業ブランチの worktree のルートで実行する。`<main>` は main の worktree の絶対パス(最新の main に更新しておく)。

```bash
# 修正前(main のコードと設定)
PYTHONPATH=<main>/src python scripts/compare_hot_candidates.py snapshot \
  --source-data-dir <data_dir> \
  --sources-config <main>/config/sources.yaml --scoring-config <main>/config/scoring.yaml \
  --date 2026-09-28 --date 2026-09-29 --date 2026-10-04 --date 2026-10-09 \
  --out <tmp>/before.json

# 修正後(作業ブランチのコードと設定)
PYTHONPATH=src python scripts/compare_hot_candidates.py snapshot \
  --source-data-dir <data_dir> \
  --date 2026-09-28 --date 2026-09-29 --date 2026-10-04 --date 2026-10-09 \
  --out <tmp>/after.json

# 差分(Markdown)
PYTHONPATH=src python scripts/compare_hot_candidates.py diff <tmp>/before.json <tmp>/after.json
```

`--sources-config` / `--scoring-config` を省略すると、カレントディレクトリの `config/sources.yaml` / `config/scoring.yaml` を使う。snapshot には、読み込んだコードの場所とコミット(`src/` の未コミットの変更の有無を含む)、設定ファイルのパスとSHA-256が記録される。修正前の snapshot の `code.package_dir` が `<main>/src` 配下になっていることを確かめる。

## 結果確認

- snapshot の実行は、日ごとにHOT候補の件数と「保存済みのcollectedと判定が違うSignal」の件数を出す。修正前のコードで実行したときにこの件数が0でなければ、作り直しが収集時の結果を再現できていない(または収集後に判定のコードが変わっている)。差分を読む前に原因を確かめる。`collected/` がない日は「collectedなし」と出る。
- `diff` は、日ごとにHOT候補の件数、増えた候補・減った候補(スコアと理由)・スコアか理由が変わった候補(理由は増えた項目に `+`、減った項目に `-` を付けて出す)と、判定(`event_type` / `ai_keyword_strength` / `model_release`)が変わったSignalを出す。この出力をPRに貼り、前後比較の記録とする。
