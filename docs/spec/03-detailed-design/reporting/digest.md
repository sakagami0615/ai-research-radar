# 日次ダイジェストの集約と概要

旧設計書の該当節を分割した資料。現行と移行目標の区別は [文書全体の入口](../../../README.md) から確認する。

## 日次ダイジェスト

概要・傾向の保存形式は [補助記録](supplement-records.md)、表示は [レポート形式](report-format.md)、保存操作は [CLI契約](../cli/commands.md) にある。

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

- 注目候補の概要は、HotCandidateの `summary` を優先し、空の場合は対象日の `data/runs/<date>/digest_summaries.json` の値を使う(データ契約「Digest Summaries記録」参照)。HotCandidateは上記のとおり最新日のものを採用するため、最新日の候補の `summary` が空なら、古い日の同じ候補が概要を持っていても使わない(補完対象になる)。
- 過去日の候補が自分で持っている概要は当日に修正できない。その日のレビューで確認済みとして扱う。
- 新モデルリリースの概要は、対象日の `digest_summaries.json` の値(キーは `ModelRelease.key`)だけを使う。対象日のファイルだけを参照するため、過去日に書いた概要は引き継がない(レポートを生成しなかった日に表示された項目が翌日にまた出る場合も、その日に書き直す)。
- 新モデルリリースの概要は1文・おおむね80字以内とし、わかる範囲で「何のモデルか / 規模 / ライセンス / 特徴」を書く。確認できなかった項目は書かない。文字数はCLIでは検証しない(注目候補の150字と同じく、Skillで指示する)。
- `ai-radar report --date <date> --list-missing-summaries` は、レポートやダイジェスト記録を書き出さずに、当日のレポートに **表示される** 項目(注目候補は上限10件、新モデルリリースは提供元ごとに上限10件。「ほかN件」に回る分は含まない)のうち概要がないものを、注目候補 → 新モデルリリース(表示順)の順でJSON Linesとして標準出力に出す。各行は `kind` を持つ。
  - `notable`: `hot_id`・タイトル・初出日・Evidence URL
  - `model_release`: `key`・タイトル・提供元・チャネル・URL・初出日。チャネルが `official`(公式ブログ)の行は `feed_summary` も持つ。
    - `feed_summary` は公式RSSの説明文で、初出日の正規化済みSignalの `summary`。説明文が空でも `""` として出す(キーを省かない)。
    - 整形は空白・改行を1つの空白にまとめるだけで、HTMLタグ・実体参照の除去はしない(設定済みの公式RSSの説明文はプレーンテキストのため)。
    - Hugging Face(Signalの `summary` はモデルの `pipeline_tag` で説明文ではない)・Ollamaの行には出さない。
    - `ModelRelease.summary`(当日に追加した概要)と取り違えないよう、別の名前にしている。
- Agent経路(`agent-daily-run`)では、`report` の前にこの一覧を確認し、各項目のEvidence URL(新モデルリリースはURL)にアクセスして概要を書き、`ai-radar add-summary --input` で保存する。一次情報を取得できない場合は取得できた範囲で書き、「一次情報未確認」と明記する。何も取得できない場合は「概要未作成(情報取得失敗: <理由>)」と書く。
  - 例外: `channel: official` の新モデルリリースで記事ページの本文を取得できない場合(HTTPエラー、または取得ログの `content_verified` が `false`)は、報道記事などの二次情報を使わず、`feed_summary` から書く。説明文からわからない項目は書かず、末尾に「(公式RSSの説明文より)」を付け、「一次情報未確認」とは書かない(公式の配信元が出した文章のため)。`feed_summary` も空なら「概要未作成(情報取得失敗: <理由>)」と書く。手順の正本は `agent-daily-run` の手順8b。
- 対象の件数に合計の上限は設けない。1日の新モデルリリースの対象が30件を超えたら、上限の追加や表示件数の削減を見直す(Agentが完了報告に件数を書く)。
- 決定論経路(`ai-radar daily`)では概要を補完しないため、概要は「概要未作成」と表示される。

### Sourceごとの本日の傾向

日次レポート末尾の「収集Source一覧」(データ契約)は1日あたり数百件のSignalを原文のまま並べる。各Signalの概要は翻訳・要約せず(表は従来どおりエスケープと120文字の切り詰めだけ)、その代わりにAgentがSourceごとの「本日の傾向」を日本語で書き、各Sourceの見出しの直下に表示する。

- 内容: 2〜3行、おおむね200字以内で、「どんなテーマが多いか」「目立った項目」を書く。原文が英語以外であっても日本語で書く。そのSourceの一覧(タイトル・概要・必要ならリンク先)を読んだうえで書く。文字数はCLIでは検証せず、レビュー(`review-daily-report`)で確認する。
- 対象: レポートの見出しと同じSource(`run_state.json` の `sources` と、未登録Sourceをまとめた `other` / `_other`)のうち、当日の `data/normalized/<date>/signals.jsonl` の件数(見出しの件数)が1件以上のもの。収集0件のSourceは「収集0件」と表示し、傾向は書かない。
- 保存: `data/runs/<date>/source_overviews.json`(データ契約「Source Overviews記録」)。Agent経路(`agent-daily-run`)では `report` の前に書き、`ai-radar add-source-overview --input` で保存する(CLI設計)。
- 表示: 傾向がないSourceは「傾向未作成」と表示する。決定論経路(`ai-radar daily`)では傾向を作成しないため、すべて「傾向未作成」になる。
- 傾向を保存した後に `collect` / `normalize` をやり直して件数が変わっても、CLIは保存済みの傾向を無効にしない(0件になったSourceは表示時に「収集0件」になる)。
- Agentが読むSourceごとの一覧は、`skills/agent-daily-run/list_source_signals.py` が見出しと同じまとめ方・件数で出す(`reporting/source_overview.py` の `group_signals_by_source` と同じ規則。テストで一致を確認する)。`signals.jsonl` が読めない(UTF-8・JSON・オブジェクトとして読めない)場合は「signals.jsonl を読めません」と出して終了コード1で終わり、Agentは傾向を書かずにレポート生成へ進む(`report` が `corrupt_input` を記録し、収集Source一覧は注記だけになる。その後の流し直しは `agent-daily-run` の「壊れた入力(`corrupt_input`)」に従う)。

### 新モデルリリース

- 入力: 各日の `data/normalized/<date>/signals.jsonl`
- 対象: `metadata.model_release` を持つSignal
- 正規化済みURL(空なら `signal_id`)で重複を除き、初出日は最も古い日とする。
- 提供元(`provider`)ごとにグループ化し、提供元は名前順、各提供元内は公開日の新しい順に並べる。各提供元は最大10件を表示し、超過分は件数のみ表示する。
- 初版では、同じモデルが公式ブログ・HF・Ollamaに別々に出てもSource別の項目として表示する(名前揺れの統合はしない)。
- 表示項目: モデル名または記事タイトル(リンク)、チャネル(公式発表 / Hugging Face / Ollama)、公開日。`models` がある場合は「紹介モデル: ...」を併記する。次の行に字下げして概要を出す(上記「注目候補・新モデルリリースの概要補完」参照)。
