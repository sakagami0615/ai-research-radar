# 品質改善の既知課題

元の品質改善設計(2026-10-01)の「既知の課題」節をもとに、PR #33の取り込み後の状態に書き直した資料。変更目標と現行実装は区別する。[適用状況](requirement-status.md)で対象ごとの状態を確認する。

## 未結線だった品質v2モジュールの削除

2026-10-03の `/code-review high` で、品質v2のモジュールがCLIから到達不能(`tests/` からのみ呼ばれる)であることと、それら自身に残る不整合を検出し、別タスクとして保留していた。PR #33(全体レビュー指摘のリファクタ)で、使っていないコードは残さない方針により次を削除した。削除前の内容はGitの履歴で確認できる。

- 品質v2パイプライン: `normalize_quality_batch` / `deduplicate_quality_signals` / `build_quality_events` / `normalization/identity.py` / `pipeline/stages.py`(`collect_stage` / `normalize_stage` / `score_stage`)
- `storage/attempts.py`(再実行時の下流無効化)、`storage/provenance.py`(provenance記録)、`reporting/review.py`(レビュー対象のhash固定と結果検証)、`normalization/history.py`(指標の履歴)
- 型 `SignalQuality` / `MetricRecord` / `ReviewResult`、`SourceAdapter.collection_diagnostics`
- `scripts/evaluate_audit.py`、`config/scoring.yaml` の `reference_priority` / `metric_by_source` / `normal_limit`、`config/runtime.yaml` の `continue_on_source_error`、`config/categories.yaml`

これらに対して記録していた不整合(raw変換と期間の扱い、重ね取得の不使用、identityのグルーピング順、機密情報除去の範囲、試行番号の照合、評価スクリプトのprecision計算、hash計算の重複、`_quality_ranks` の計算量)は、対象のコードがなくなったため解消済みとする。品質改善の目標を実装するときは [変更設計](../../spec/05-decisions/audit-remediation/README.md) と [将来対応](future-works.md) から設計し直す。

`apply_assessments`(`select-hot`)と `validate_proposals`(`save-proposals`)はCLIに接続済みのため残っている。

## 現行コードに残る課題

- `sources/public.py::_matches_keywords` は `classify_relevance` の判定結果を一致の有無だけに丸めて捨てる(判定結果を残す案は [将来対応](future-works.md) の「AI関連性の判定結果をデータに残す」)。
- `_strongest_event_type`(Event種別の優先度判定)が `pipeline/events.py` と `normalization/dedup.py` に別々に実装されている(引数の形は異なる)。
- `normalization/scores.py::_rank_popularity` は件数の2乗に比例する計算量である。
- OpenAlexの `abstract_inverted_index` の復元(`restore_abstract`)が、収集時(`sources/public.py`、診断情報は破棄)と正規化時(`sources/remap.py`)の2か所で同じデータに対して実行される。
