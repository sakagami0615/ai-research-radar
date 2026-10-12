# 重複排除とEvent・Topic生成

旧設計書の該当節を分割した資料。現行と移行目標の区別は [文書全体の入口](../../../README.md) から確認する。

## Dedup

DedupはURLを主キーに近い形で扱う。ただし、queryを全削除しない。

- `utm_*`, `fbclid`, `gclid`, `ref` など追跡パラメータだけ除去する。
- `item?id=1` のような意味のあるqueryは保持する。
- 空URLは `source:signal_id` を含むkeyで扱い、空URL同士を統合しない。

統合時は以下を保持する。

- `sources`
- `source_families`
- `event_type`
- `merged_signal_ids`
- 最大normalized score


## Event / Topic生成

Event BuilderはSignalからEventを作る。EventにはHOT判定に必要な `source_families`, `scores`, `evidence`, `event_type` を残す。

Topic ClusterはEventからTopicを作る。MVPでは簡易な日次Topic化に留める(Topic履歴を使う週次・月次分析は [将来対応](../../../support/02-planning/future-works.md))。
