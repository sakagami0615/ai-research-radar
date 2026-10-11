# 関連性・概要・HOT選抜の変更設計

元の品質改善設計（2026-10-01）を分割して保存した資料。変更目標と現行実装は区別する。[適用状況](../../06-planning/requirement-status.md)で対象ごとの状態を確認する。

## 3. 関連性と概要の修正

### 3.1 共通の関連性判定

収集時と正規化時で共通の判定関数を使用する。ASCII略語（AI、LLM、RAG、MCP等）はASCII英数字の連続語の一部として一致させない。大文字小文字を区別せず、ハイフン・空白・日本語との境界を扱う。`brokerage`、`fragment`、`chair` は負例、`RAG-based`、`LLM活用` は正例とする。日本語表現と複数語の用語は設定した表現に従う。`agent` 単独のような曖昧語は強い関連性の根拠にしない。

判定は `related / uncertain / unrelated`、一致した語、判断理由を残す。語がないことだけで無関係と断定しない。概要欠損・曖昧語だけの項目は `uncertain` として残し、Agentの確認対象にできる。収集時フィルターによる除外件数と方式を記録する。明確な無関係項目はHOTにできない。

Zenn等の一般開発Sourceに `ai` を一律付与しない。検索条件による取得と内容確認済みの関連性を区別する。保存済みrawの再正規化でも同じ規則を適用する。

### 3.2 OpenAlex概要

`abstract_inverted_index` の各単語をすべての位置へ展開し、位置順に復元する。繰り返し語を保持する。不正な位置・競合位置は診断情報を残し、復元に疑義があれば概要不完全として表示する。辞書キーの連結には戻さない。元のrawは改変しない。


## 5. 発見候補とHOTの分離

`score` は `related / uncertain` の全Eventを候補として保存する。閾値75による保存前の除外は廃止する。明確な `unrelated` は除外理由付きで保存し、件数を報告する。発見候補は未選抜で、内容評価済みを意味しない。

AgentはSource別の候補一覧・概要を確認し、研究・公式発表も含めた一次スクリーニングを行う。参考値上位だけを読む手順にしない。詳細確認する候補と保留候補を区別し、確認範囲と残件数を記録する。大量候補の一次スクリーニングは分割して行い、未確認を除外済みと記録しない。

### 5.1 内容評価と選抜

`select-hot` は評価JSON `data/runs/<date>/selection_input.json`(`--input` で変更可)を必須入力とする(形式はデータ契約 SelectionInput)。評価レコードは次を持つ。

- `hot_id`、判断 `selected / deferred / rejected`、判断日時、担当。
- AI関連性の説明、新規性、重要性、読者への影響。
- 根拠のURL、確認日時、対象版、確認状態、裏付け区分、どの主張を支えるか。
- 判断日時・確認日時は、取得・記録時に実測したUTC時刻とする。推定値や切りのよい値で埋めない。取得時刻が不明な根拠は取得し直す(実機運用で推定値が書かれ、独立レビューで未来時刻として指摘された事例による)。
- 未確認事項、採否理由。

選抜には上記説明と取得・内容確認できた一次根拠を必須とする。URLを書くだけでは確認済みにしない。CLIは型、空値、ID整合、状態の組み合わせを検査する。説明内容やURLの真偽はAgentと独立レビューで確認する。

根拠の取得では、HTTPステータスだけで確認済みにしない。HTTP 200でもbot対策ページなどで本文を取得できなければ `unavailable`、本文は取得できたが対象の版を確認できなければ `unverified` とする。PyPIの `/project/` ページはbot対策ページを返すため、PyPI候補はJSON API(`https://pypi.org/pypi/<name>/<version>/json`、版が不明なら `https://pypi.org/pypi/<name>/json`)で `info.version` と用途を確認し、配布元である公式レジストリのメタデータとして `kind: primary` で記録する(`note` に `info.version`)。表示用の `evidence_urls` は `/project/` のままとする。取得の記録は `data/runs/<date>/evidence_fetch_log.tsv`(ヘッダー付きTSV、列 `url` / `http_status` / `fetched_at` / `content_verified` / `note`、追記のみ)に残し、`fetched_at` を `checked_at` と一致させて独立レビューが確認日時を裏付けられるようにする。CLIはこのログを検証しない(Issue #10。詳細手順は `agent-daily-run` Skillの手順4)。

独立検証がない単一の公式発表でも、確認した範囲を「発表された仕様・主張」に限定すれば選抜できる。性能や人気まで確認済みに広げない。取得失敗は存在しない証拠にしない。一次情報を確認できないものは発見候補として保留する。

通常上限2件、明示指定時の上限5件。枠を埋める義務はない。0件でも選抜処理の完了、理由、確認範囲を記録する。未実行の0件と区別する。`select-hot` に選抜を指定する引数はなく、自由文だけで選抜することはできない(旧オプション `--select` / `--reason` / `--summary` の移行案内 `deprecated_option` はPR #33で廃止した)。0件の日の理由・確認範囲は `selection_input.json` の `selection_reason` と `apply_assessments` の集計(確認件数・未確認件数・選抜件数)として扱い、`run_state.json` / `run.jsonl` の `stage_results` に `deferred` として記録する(データ契約「RunMetadata」、#12)。
