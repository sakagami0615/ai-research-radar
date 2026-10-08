# 05. Pipeline・Scoring・Ideation設計

## v2指標とidentity

v2では`freshness_score`（公開日時から取得までの168時間線形値）、Sourceごとの代表的な実測指標の順位、過去観測との差分を別々に保持する。取得できない指標、NaN、Infinity、bool、文字列は人気順位に変換せず`missing`または`invalid`として扱う。キーワード一致、固定信用点、npm検索複合scoreは人気の実測値ではない。Eventが複数Signalを持つ場合、Signalごとの合成値(確認優先度)の最大を取り、採用したSignalと算出内訳を記録する(09章参照、旧仕様の「maxで合成しない」は撤回)。Task 10の切り替えまで旧HOT計算経路は維持する。

## 日次Pipeline

`run_daily` は、日次の収集からレポート生成までを実行する。

主な入力:

- `adapters`
- `since`
- `until`
- `output_dir`
- `report_dir`
- `hot_limit`
- `minimum_score`
- `hot_score_weights`
- `display_timezone`(レポートのPeriod表示用)
- `use_overlap`(`--since` / `--until` 省略時に真。`overlap_hours` を持つSourceの重ね取得と収集済み除外を有効にする。04章)

主な出力:

- `DailyPipelineResult`
- JSONL成果物
- Markdownレポート

## 処理順序

1. Sourceごとに `collect` を実行する(`sources/collection.collect_new_items` 経由。`use_overlap` が真なら `overlap_hours` 分前から取得し、前日以前の `normalized` にある記事を除外する)。
2. raw JSONLをSource別に保存する。
3. `normalize` でCanonicalSignalへ変換する。
4. Source単位のbatch normalizationを行う。
5. dedupで同一Signalを統合する。
6. Eventを生成する。
7. Topicを生成する。
8. EventからHOT候補を生成する。
9. 選抜HOTから記事企画候補を生成する。
10. JSONL成果物を保存する。
11. 日次ダイジェスト(注目候補・新モデルリリース)を集約し、Markdownレポートを生成する。
12. RunMetadataを保存する。

## Source単位スコア正規化

MVPでは、収集バッチ内のSource単位でPopularityを順位ベースに正規化する。

理由:

- GitHub stars、npm search score、RSS更新通知などは尺度が違う。
- 異なるSourceのraw metricを直接比較すると、累積人気の大きいSourceが常に有利になる。
- 初期段階では履歴がないため、Source別の簡易順位を使う。

単独Source itemではfallback scoreを使う。PyPI/npmの強い新着package discoveryは、48時間以内かつ強い信号に限定して補正する。補正はSourceあたり最大3件に制限し、通知量を抑える。

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

Topic ClusterはEventからTopicを作る。MVPでは簡易な日次Topic化に留め、将来のTrend Analysisで履歴を使う。

## HOT判定

HOT scoreは以下を使う。

- Momentum
- Popularity
- Cross-source Confidence
- Credibility

標準では、スコアが `minimum_score` 以上のEventを候補にする。公式重大イベントは低スコアでも候補化できる。

`hot_limit` は選抜数を制限する。候補自体は保持し、`selected` でレポート対象かどうかを表す。`hot_limit` は決定論経路(`ai-radar daily`)の選抜数である。Agent経路では `select-hot` が `data/runs/<date>/selection_input.json` の評価レコードで選抜し(03章「SelectionInput」参照)、上限は `select-hot --limit`(既定2件、最大5件)である。

選抜HOTのレポート表示では、Agent経路で保存された評価レコード(`assessment`)を評価ブロックとして出す(03章「Daily Markdown Report」の `## 選抜HOT` 参照)。評価レコードのない決定論経路・旧データはReasonsだけを表示する。

## 日次ダイジェスト

日次レポートの「注目候補(選抜外)」「新モデルリリース」は、CLIが決定論的に生成する。Agentは項目の選定・並び順に関与しない。ただし、注目候補・新モデルリリースの概要(下記「注目候補・新モデルリリースの概要補完」)だけはAgentが書いた文章を表示する。`ai-radar report`(Agent経路)と `ai-radar daily`(決定論経路)の両方で、同じ集約処理(`reporting/digest.py`)を使う。記事企画は生成しない。

### 集約期間と既掲載除外

- 対象日を含む直近3日分(対象日、前日、前々日)のrunを集約する。存在しない日は読み飛ばす。
- 対象日より前の日の `data/runs/<date>/report_digest.json` に記録された項目は既掲載として除外する。
- 集約結果に掲載した項目は、対象日の `report_digest.json` に記録する。
- 過去日の `hot_candidates.jsonl` / `signals.jsonl` が読めない(JSON破損、必須キー欠落など)場合は、その日のそのファイルだけを集約から外し、レポートの注目候補セクションの直前に警告を表示する。ダイジェストは補助情報であり、当日の選抜HOTレポートの生成を失敗させない。
- レポートの再生成は当日分のみを想定する。過去日を再生成するとその日の `report_digest.json` が上書きされ、翌日以降の除外判定の前提とずれることがある。

### 注目候補(選抜外)

- 入力: 各日の `data/runs/<date>/hot_candidates.jsonl`
- 対象: `selected=False` の候補(`minimum_score` 以上、またはOfficial Overrideで候補化されたもの)。`event_type` による除外はしない。
- 集約期間内のどの日かで `selected=True` になった `hot_id` は除外する。
- 同じ `hot_id` が複数日に出た場合は最新日の候補(スコア)を採用し、初出日は最も古い日とする。
- スコア降順で最大10件を表示し、超過分は件数のみ表示する。
- 表示項目: タイトル(先頭Evidence URLへのリンク)、概要、HOT Score、Source(`signals` の `source:` 接頭辞から復元)、Reasons、初出日

### 注目候補・新モデルリリースの概要補完

- 注目候補の概要は、HotCandidateの `summary` を優先し、空の場合は対象日の `data/runs/<date>/digest_summaries.json` の値を使う(03章「Digest Summaries記録」参照)。HotCandidateは上記のとおり最新日のものを採用するため、最新日の候補の `summary` が空なら、古い日の同じ候補が概要を持っていても使わない(補完対象になる)。
- 過去日の候補が自分で持っている概要は当日に修正できない。その日のレビューで確認済みとして扱う。
- 新モデルリリースの概要は、対象日の `digest_summaries.json` の値(キーは `ModelRelease.key`)だけを使う。対象日のファイルだけを参照するため、過去日に書いた概要は引き継がない(レポートを生成しなかった日に表示された項目が翌日にまた出る場合も、その日に書き直す)。
- 新モデルリリースの概要は1文・おおむね80字以内とし、わかる範囲で「何のモデルか / 規模 / ライセンス / 特徴」を書く。確認できなかった項目は書かない。文字数はCLIでは検証しない(注目候補の150字と同じく、Skillで指示する)。
- `ai-radar report --date <date> --list-missing-summaries` は、レポートやダイジェスト記録を書き出さずに、当日のレポートに **表示される** 項目(注目候補は上限10件、新モデルリリースは提供元ごとに上限10件。「ほかN件」に回る分は含まない)のうち概要がないものを、注目候補 → 新モデルリリース(表示順)の順でJSON Linesとして標準出力に出す。各行は `kind` を持つ。
  - `notable`: `hot_id`・タイトル・初出日・Evidence URL
  - `model_release`: `key`・タイトル・提供元・チャネル・URL・初出日
- Agent経路(`agent-daily-run`)では、`report` の前にこの一覧を確認し、各項目のEvidence URL(新モデルリリースはURL)にアクセスして概要を書き、`ai-radar add-summary --input` で保存する。一次情報を取得できない場合は取得できた範囲で書き、「一次情報未確認」と明記する。何も取得できない場合は「概要未作成(情報取得失敗: <理由>)」と書く。
- 対象の件数に合計の上限は設けない。1日の新モデルリリースの対象が30件を超えたら、上限の追加や表示件数の削減を見直す(Agentが完了報告に件数を書く)。
- 決定論経路(`ai-radar daily`)では概要を補完しないため、概要は「概要未作成」と表示される。

### Sourceごとの本日の傾向

日次レポート末尾の「収集Source一覧」(03章)は1日あたり数百件のSignalを原文のまま並べる。各Signalの概要は翻訳・要約せず(表は従来どおりエスケープと120文字の切り詰めだけ)、その代わりにAgentがSourceごとの「本日の傾向」を日本語で書き、各Sourceの見出しの直下に表示する。

- 内容: 2〜3行、おおむね200字以内で、「どんなテーマが多いか」「目立った項目」を書く。原文が英語以外であっても日本語で書く。そのSourceの一覧(タイトル・概要・必要ならリンク先)を読んだうえで書く。文字数はCLIでは検証せず、レビュー(`review-daily-report`)で確認する。
- 対象: レポートの見出しと同じSource(`run_state.json` の `sources` と、未登録Sourceをまとめた `other` / `_other`)のうち、当日の `data/normalized/<date>/signals.jsonl` の件数(見出しの件数)が1件以上のもの。収集0件のSourceは「収集0件」と表示し、傾向は書かない。
- 保存: `data/runs/<date>/source_overviews.json`(03章「Source Overviews記録」)。Agent経路(`agent-daily-run`)では `report` の前に書き、`ai-radar add-source-overview --input` で保存する(06章)。
- 表示: 傾向がないSourceは「傾向未作成」と表示する。決定論経路(`ai-radar daily`)では傾向を作成しないため、すべて「傾向未作成」になる。
- 傾向を保存した後に `collect` / `normalize` をやり直して件数が変わっても、CLIは保存済みの傾向を無効にしない(0件になったSourceは表示時に「収集0件」になる)。
- Agentが読むSourceごとの一覧は、`skills/agent-daily-run/list_source_signals.py` が見出しと同じまとめ方・件数で出す(`reporting/source_overview.py` の `group_signals_by_source` と同じ規則。テストで一致を確認する)。

### 新モデルリリース

- 入力: 各日の `data/normalized/<date>/signals.jsonl`
- 対象: `metadata.model_release` を持つSignal
- 正規化済みURL(空なら `signal_id`)で重複を除き、初出日は最も古い日とする。
- 提供元(`provider`)ごとにグループ化し、提供元は名前順、各提供元内は公開日の新しい順に並べる。各提供元は最大10件を表示し、超過分は件数のみ表示する。
- 初版では、同じモデルが公式ブログ・HF・Ollamaに別々に出てもSource別の項目として表示する(名前揺れの統合はしない)。
- 表示項目: モデル名または記事タイトル(リンク)、チャネル(公式発表 / Hugging Face / Ollama)、公開日。`models` がある場合は「紹介モデル: ...」を併記する。次の行に字下げして概要を出す(上記「注目候補・新モデルリリースの概要補完」参照)。

## Article Ideation

記事企画の経路は2つある。

- Agent経路(`agent-daily-run`): Agentが選抜HOTごとに0〜3件の企画を作り、v2 の契約(各企画に `schema_version: 2` と `quality` を持たせる)で `save-proposals` に渡す。`save-proposals` は `validate_proposals` で型・必須値・選抜ID・Evidence対応を検証して保存する(03章「save-proposals の入力(v2)」)。比較対象などのために追加したURLは、`quality.evidence` の `claim` に役割を書くことで、HOTの主張を支えるURLと区別して許容する(09章 §8)。
- 決定論経路(`ai-radar daily`): 以下の工程で v1 の企画(`quality` なし)を作る。v2 化は対象外であり、レポートでは旧形式と同じく「品質評価: 旧形式のため未評価」と表示する。

決定論経路はMVPのまま外部LLMを使わず、決定論的な工程で記事企画を生成する。

工程:

1. Role別候補生成
2. 類似タイトルのDedup / Cluster
3. Critique scoreとCritique notes付与
4. Advocate / Critic / Editorの1 round Debate代替
5. `max_proposals` 件へ統合

ArticleProposalのスキーマは変えず、以下に判断結果を残す。

- `why_now`
- `technical_angle`
- `unique_angle`
- `risks`

`why_now` の定型文(`HOT score ... with reasons: .... Role: .... 軽量Critique score: N/100; <notes>. Debate: <debate>`)は、日次レポートのレンダラーがRole / Critique / Debateの表示行に分解するために使う。文言を変える場合は `reporting/markdown.py` の分解パターンと、生成結果を分解するテスト(`tests/test_reporting.py`)を合わせて更新する。

Evidence URLがないHOT候補からは記事企画を生成しない。

## エラー処理

Source単位の失敗は継続する。後段の保存やレポート生成に失敗した場合は、可能な限りRunMetadataを保存してから例外を再送出する。
