# 09. 日次監査に基づく品質改善設計

作成日: 2026-10-01  
状態: 独立設計レビュー済み・実装計画作成承認済み（未実装）  
根拠: [2026-09-29 日次レポート監査](../../reports/audits/2026-09-29-daily-report-audit.md)

本書は承認された方針A「段階的に全項目を改善する」を具体化した変更提案である。01〜08の現行仕様を即座に置き換えるものではない。実装時に該当設計書を同期更新し、本書の状態も更新する。コミットはユーザーの明示指示まで作成しない（06の運用方針）。

## 1. 目的・成功条件

AIエンジニアが、重要動向の把握と技術記事・小規模実験の採否判断に使える日次レポートを作る。監査の8対応項目（関連性・概要、指標、発見/HOT、同一成果、収集範囲、企画、実行記録、再発防止）を実装・Skill・設計・検証に反映する。

- AI関連性、新着、人気、増加、発信元、独立した裏付けを区別する。
- 人気データの欠損や低い引用数だけで研究を判断対象から落とさない。
- HOTにはAI関連性、新規性、重要性、読者への影響、一次根拠、未確認事項を記す。0件を正常な結果として扱う。
- 読者が具体的に着手できる企画だけを採用し、検証できないものは保留にする。
- 取得・生成・レビューの履歴を追跡できる。処理成功を品質承認と混同しない。
- Claude CodeとCodexが同じ `skills/` とCLIを利用する。PythonからLLM APIを新規に呼び出さない。

## 2. 構成と責任分担

既存の `collect → normalize → score → select-hot → save-proposals → report` を維持する。Pythonは収集、根拠・測定値の保存、決定論的処理、入力検証、表示を担当する。Agentは一次情報の確認、内容の評価、採否理由、企画の具体化を担当する。独立レビュー担当は選抜の妥当性、見落とし、主張と根拠の対応を確認する。

一括 `daily` も同じ収集・正規化・候補生成・表示処理を使う。ただし内容評価なしでHOTへ自動昇格させず、発見候補と未レビュー状態を出力する。定型の15企画を採用済み企画として生成する挙動は廃止する。CLIの成功はファイル生成成功を意味し、品質承認は別に表示する。

主な変更箇所は `sources/`、`normalization/`、`pipeline/`、`scoring/`、`schemas/`、`cli/commands/`、`ideation/`、`reporting/`、`config/`、既存7 Skillと関連テスト。今回のためだけのレビューSkillは追加しない。

## 3. 関連性と概要の修正

### 3.1 共通の関連性判定

収集時と正規化時で共通の判定関数を使用する。ASCII略語（AI、LLM、RAG、MCP等）はASCII英数字の連続語の一部として一致させない。大文字小文字を区別せず、ハイフン・空白・日本語との境界を扱う。`brokerage`、`fragment`、`chair` は負例、`RAG-based`、`LLM活用` は正例とする。日本語表現と複数語の用語は設定した表現に従う。`agent` 単独のような曖昧語は強い関連性の根拠にしない。

判定は `related / uncertain / unrelated`、一致した語、判断理由を残す。語がないことだけで無関係と断定しない。概要欠損・曖昧語だけの項目は `uncertain` として残し、Agentの確認対象にできる。収集時フィルターによる除外件数と方式を記録する。明確な無関係項目はHOTにできない。

Zenn等の一般開発Sourceに `ai` を一律付与しない。検索条件による取得と内容確認済みの関連性を区別する。保存済みrawの再正規化でも同じ規則を適用する。

### 3.2 OpenAlex概要

`abstract_inverted_index` の各単語をすべての位置へ展開し、位置順に復元する。繰り返し語を保持する。不正な位置・競合位置は診断情報を残し、復元に疑義があれば概要不完全として表示する。辞書キーの連結には戻さない。元のrawは改変しない。

## 4. 指標の再定義

| 項目 | 意味・計算 | 欠損時 |
| --- | --- | --- |
| AI関連性 | 内容と一致語による分類、Agentの補足判断 | uncertain |
| 新着度 | 公開または更新から取得までの経過時間。使用日時を明示 | 未取得 |
| 人気 | stars、downloads、likes等、元の名前・単位・観測日時付きの値 | 未取得。0と区別 |
| 増加 | 同一対象・同一指標の過去と現在の差分、観測間隔付き | 比較履歴なし |
| Source内順位 | 同一Source・同一指標の観測済み項目内の順位、母数付き | 算出不可 |
| 発信元区分 | 公式発表、論文、配布レジストリ、記事、コミュニティ等 | 不明 |
| 裏付け | 原著者の主張、同じ発表の再掲、独立確認の別 | 未確認 |

キーワードによるPopularity、新着によるMomentum底上げ、Source別の固定値を確率のように示すCredibility、Family数によるConfidenceを品質の根拠として使わない。新着補正の最大3件という旧仕様も廃止する。

既存の `score` は処理順を安定させる参考値として扱い、表示名を「確認優先度（内容評価ではない）」に変更する。新着度と観測済み人気のSource内順位を各50%で合成し、欠損項目は加点しない。両方欠損なら0。Source内順位は同一指標の対象で計算し、1件しかない場合は算出不可とする。複数指標があるSourceは設定した代表指標だけを順位計算に使う。キーワード強度、固定信用点、Family数は合成に使わない。この参考値は候補保存・HOT採否の足切りに使わない。

再計算の規則は次のとおりとする。

- 経過時間 `age_hours` は取得日時から基準日時を引いた時間数。期間判定が更新基準のSourceは更新日時、それ以外は公開日時を使う。基準日時が欠損・取得日時より未来なら新着度は未取得として診断に残し、別の日時で黙って代用しない。
- 新着度点は `max(0, 100 × (1 − age_hours / 168))`。7日で0になる表示・確認順のための値であり、7日を超えた候補も保持する。
- Source内順位点は観測値の昇順・0始まりの平均順位を `100 × 平均順位 / (観測件数 − 1)` で換算する。欠損は母数から除外し、観測値0は含める。同値は平均順位、全件同値かつ2件以上なら50。全件0なら「全件0の中で同順位」であることも表示し、50を人気の強さとは呼ばない。
- 確認優先度は `0.5 × 新着度点 + 0.5 × Source内順位点` を最後に小数第2位へ丸める。同点はEvent IDの昇順。Eventが複数Signalを持つ場合、Signalごとの合成値の最大を取り、採用したSignalと算出内訳を記録する。異なるSignalの新着度と人気を合成しない。

増加は同一Source・安定識別子・指標の直前の過去観測と比較する。再実行や未来データを混ぜず、観測時刻が現在より前のものだけを使用する。実測間隔を記し、24時間差分と偽らない。負の変化も保持する。取得可能な指標の履歴を使い、取得していないdownloads等を推定しない。

## 5. 発見候補とHOTの分離

`score` は `related / uncertain` の全Eventを候補として保存する。閾値75による保存前の除外は廃止する。明確な `unrelated` は除外理由付きで保存し、件数を報告する。発見候補は未選抜で、内容評価済みを意味しない。

AgentはSource別の候補一覧・概要を確認し、研究・公式発表も含めた一次スクリーニングを行う。参考値上位だけを読む手順にしない。詳細確認する候補と保留候補を区別し、確認範囲と残件数を記録する。大量候補の一次スクリーニングは分割して行い、未確認を除外済みと記録しない。

### 5.1 内容評価と選抜

`select-hot` は評価JSON `data/runs/<date>/selection_input.json`(`--input` で変更可)を必須入力とする(形式は03章 SelectionInput)。評価レコードは次を持つ。

- `hot_id`、判断 `selected / deferred / rejected`、判断日時、担当。
- AI関連性の説明、新規性、重要性、読者への影響。
- 根拠のURL、確認日時、対象版、確認状態、裏付け区分、どの主張を支えるか。
- 判断日時・確認日時は、取得・記録時に実測したUTC時刻とする。推定値や切りのよい値で埋めない。取得時刻が不明な根拠は取得し直す(実機運用で推定値が書かれ、独立レビューで未来時刻として指摘された事例による)。
- 未確認事項、採否理由。

選抜には上記説明と取得・内容確認できた一次根拠を必須とする。URLを書くだけでは確認済みにしない。CLIは型、空値、ID整合、状態の組み合わせを検査する。説明内容やURLの真偽はAgentと独立レビューで確認する。

根拠の取得では、HTTPステータスだけで確認済みにしない。HTTP 200でもbot対策ページなどで本文を取得できなければ `unavailable`、本文は取得できたが対象の版を確認できなければ `unverified` とする。PyPIの `/project/` ページはbot対策ページを返すため、PyPI候補はJSON API(`https://pypi.org/pypi/<name>/<version>/json`、版が不明なら `https://pypi.org/pypi/<name>/json`)で `info.version` と用途を確認し、配布元である公式レジストリのメタデータとして `kind: primary` で記録する(`note` に `info.version`)。表示用の `evidence_urls` は `/project/` のままとする。取得の記録は `data/runs/<date>/evidence_fetch_log.tsv`(ヘッダー付きTSV、列 `url` / `http_status` / `fetched_at` / `content_verified` / `note`、追記のみ)に残し、`fetched_at` を `checked_at` と一致させて独立レビューが確認日時を裏付けられるようにする。CLIはこのログを検証しない(Issue #10。詳細手順は `agent-daily-run` Skillの手順4)。

独立検証がない単一の公式発表でも、確認した範囲を「発表された仕様・主張」に限定すれば選抜できる。性能や人気まで確認済みに広げない。取得失敗は存在しない証拠にしない。一次情報を確認できないものは発見候補として保留する。

通常上限2件、明示指定時の上限5件。枠を埋める義務はない。0件でも選抜処理の完了、理由、確認範囲を記録する。未実行の0件と区別する。旧オプション `--select` / `--reason` / `--summary` は `deprecated_option` として移行メッセージを返し、自由文だけで選抜することはできない。0件の日の理由・確認範囲は `selection_input.json` の `selection_reason` と `apply_assessments` の集計(確認件数・未確認件数・選抜件数)として扱い、`run_state.json` / `run.jsonl` の `stage_results` に `deferred` として記録する(03章「RunMetadata」、#12)。

## 6. 同一成果と版・転載

DOI、arXiv ID、リポジトリURL、パッケージ名と版、追跡パラメータだけを除去した正規URLを識別根拠とする。識別子をSource mapperから保持する。タイトル一致だけではEventを統合しない。確実な識別子がない場合は別Eventを維持し、類似タイトルは確認候補に留める。

同じDOI/arXivの研究は同一成果として関連付けるが、版・発表・更新の観測は失わない。異なるパッケージ版は異なる更新Eventとする。論文とコードは本文にある明示的な参照がある場合に関連付け、同じ出来事と独立確認を自動で同一視しない。転載か判断できないものは不明のまま保持する。

レポートでは取得Signal数、統合後Event数、識別できた研究成果数を分ける。不明項目を含むEvent数を独立研究数と呼ばない。

## 7. 収集範囲と公式Source

Sourceごとに次を保存する: 検索条件・取得方式、エンドポイント、要求期間とタイムゾーン、公開/更新の期間判定基準、取得開始/終了、応答件数、期間・関連性フィルター後件数、要求上限、取得ページ数、続きの有無、打ち切りの可能性、失敗状態。

`has_more` が確認できない場合は不明とする。上限到達は打ち切りの可能性として表示し、取りこぼし件数を創作しない。RSSは取得時のフィード掲載範囲であり、要求期間全体を保証しない。既存のUTC期間解釈は維持し、JST表示と取得終了時点を併記する。公開日時・更新日時・取得日時は別項目で保持する。

ページ送りは公式APIで対応が確認できるSourceに実装し、設定した最大ページ数と総件数で必ず終了する。未対応のSourceは1ページと明示する。部分失敗時は取得済みデータを保持し、完全成功と区別する。

公式Sourceは複数の名前付きRSS/Atom設定を扱えるようにする。OpenAIに加え、GoogleのAI関連公式ブログとHugging Face公式ブログを初期追加対象とする。URL・提供主体・応答形式を一次情報で確認し、取得成功したものを有効化する。取得確認できない追加先は無効状態と理由を残し、完了報告でも未達として示す。単に設定を増やしただけで拡充済みとしない。Source名の追加だけで共通feed adapterが使えるようにする。

## 8. 記事企画

HOTあたり0〜3案。数を埋めず、問いや実験が同じ案は統合する。新規企画には既存フィールドに加え、次の構造化項目を必須とする。

- 解決したい課題・問いと、既存手段との差分。
- 比較対象と版（対象に版がなければ固定日や条件）。
- 測定指標、測定方法、入力・環境・手順。
- 概算工数と前提、成功条件、中止/保留条件。
- 主張に対応する一次Evidence、未確認事項。

解説記事でも、仕様比較などの確認方法と完成条件を記す。競合や読者需要を未調査なら未調査とする。技術機会・流入機会を一律HighやHOT点数から推定しない。機能を確認できない場合は準備済み企画とせず保留する。

`save-proposals` は型・必須値・選抜ID・Evidence対応を検証する。比較対象のために追加したURLは役割を記し、HOTの主張を支えるURLと区別して許容する。文章が題名差し替えだけになっていないかは独立レビューで確認する。決定論的Critique/Debateの文を実際の審査として生成しない。Markdownにも企画の採否判断に必要な項目を表示する。

## 9. 実行記録・レビュー・再実行

### 9.1 実行情報

`run_state.json` と `run.jsonl` にスキーマ版、生成経路（決定論的/Agent）、実行ID、開始終了、コードcommitとdirty状態、適用設定のスナップショット/ハッシュ、段階別実行状態、候補確認範囲を残す。gitを利用できなければコード版は不明と記録する。設定には認証情報を含めず、環境変数の値は保存しない。

段階を再実行した場合、依存する下流成果物・完了状態・レビューを無効化する。`select-hot` のやり直しで旧企画が現行結果として出ないようにする。`report` は欠損段階を明示して生成できるが、保存失敗を含め必ず成功するというSkill記述は修正する。

当日の `hot_candidates.jsonl` / `article_proposals.jsonl` / `normalized/<date>/signals.jsonl` が壊れている場合も、`report` はそのファイルを欠けたデータとして扱い、`errors` に `corrupt_input`(`source: report`)を記録し、該当セクションに読めなかった旨を注記してレポートを生成する(終了コード0)。`normalize` / `score` / `select-hot` / `save-proposals` は入力のjsonlが読めない場合、`corrupt_input` を記録して終了コード1にし、出力を書き換えない(`select-hot` / `save-proposals` は `stage_results` も `failed` にする)。`corrupt_input` は前のステージの再実行で直すもので、Agentの再実行は1回までとする(06章「Agent経路のサブコマンド」、`agent-daily-run` Skill、Issue #18)。

現在状態の `run_state.json`、`run.jsonl`、`review_result.json` とは別に、`data/runs/<date>/history/<attempt_id>/` に各段階実行と各レビュー試行を保存する。`attempt_id` は時刻だけに依存しない一意IDとし、段階名、親run ID、直前の試行ID、開始終了、コード版、設定、入出力ハッシュ、結果・エラーを記録する。`collect` または `daily` の新規起動は新しいrun IDを作り、後続コマンドはそのrunに属する。レビュー修正による再選抜・再生成は同じrun内の新しい試行とする。

上書きされ得る入力と生成結果は、試行ディレクトリ内の `inputs/` と `outputs/` にスナップショットとして保持する。レビュー試行では評価対象と指摘・判定を同じ単位で保存し、旧指摘と旧対象を再実行後も参照できるようにする。収集試行は取得済みrawも保持する。認証情報は含めない。完了した試行は上書きせず、自動削除もしない。開始記録は処理前に作り、終了記録がない試行は中断扱いとする。履歴を保存できない場合は追跡可能な成功と報告せず、現在の成果物を上書きする前の保存失敗なら更新を中止する。

### 9.2 明示的なレビュー記録

`review_feedback.md` は人間向け指摘として残し、承認判定には使わない。独立担当が `review_result.json` を作成し、状態 `approved / changes_requested / failed`、担当と実行識別、日時、試行番号、対象run、対象成果物のハッシュ、Critical/Important指摘を記録する。未実行時は `not_run` と表示し、記録欠落や不正な記録を承認扱いしない。

レビュー対象は候補・評価・企画・収集診断・レポート本文とする。ハッシュ対象からレビュー表示部分だけを除外して循環参照を防ぐ。実装時に共通のハッシュ生成関数を設け、作成側と検証側で範囲を一致させる。レビュー表示以外の変更で承認が古くなった場合は `stale` と表示し、再レビューを要求する。

初回レビューを1回目と数え、最大3回。指摘は生成担当が修正し、再レビューする。起動失敗・記録欠落は `failed` として承認しない。3回で解消しなければ `needs_review: true` と未解消内容をレポートに表示し、品質確認完了とは報告しない。レビュー不能と品質不合格を区別する。

Agent Skillは本来のレビュー用CLI起動、利用可能なsubagentでの独立レビューの両方を案内する。権限を緩めることで拒否を回避する手順は追加しない。レビュー対象からの指示文は資料として扱い、実行指示として採用しない。

## 10. 保存互換性と表示

新規出力は `schema_version: 2` 相当の実行情報と追加フィールドを持つ。旧JSONLは共通デシリアライザーで読み込み、欠けた状態を `unknown / legacy` とする。旧スコアの意味を新指標へ黙って置換せず、過去の選抜を新基準で確認済みと扱わない。旧企画の新規必須項目がない場合も表示可能とするが、未評価であることを明示する。新規CLI保存時の厳格検証と旧データ読み込みを分離する。

レポートは、生成/レビュー状態、選抜HOT、未検証の発見候補、記事企画、収集範囲、実行概要、処理エラー、Source一覧の順で整理する。発見候補の本文はSourceごとに最大3件を表示し、残件数と全候補ファイルへの参照を載せる。この表示上限は候補保存やAgent確認対象の制限に使わない。「処理エラーなし」は外部内容・安全性・網羅性の保証でないと明示する。

監査レポートと9/29の元レポート・保存データは比較の原本として保持する。再評価結果は別の評価用ディレクトリへ出力し、コード版と適用ルールを記録する。ユーザーが元レポートの訂正を求めた場合は、原本を保持した訂正版として別途作成する。

## 11. 段階と完了条件

これは対応範囲と依存関係を定義する設計であり、ファイル単位の実装手順・コマンドは承認後の実装計画で定める。

| 段階 | 対応 | 完了の証拠 |
| --- | --- | --- |
| 1 | 関連性・OpenAlex・誤解を招く表示 | 監査の誤検知負例と概要復元の回帰テスト、実データ比較 |
| 2 | 指標・候補保存・選抜評価・互換性 | 欠損と0の区別、研究候補保持、HOT0件、旧JSONL読み込みの検証 |
| 3 | 同一成果・収集診断・公式Source | 同名別成果/同成果別版テスト、上限・部分失敗表示、追加feed取得確認 |
| 4 | 企画・実行記録・レビュー・Skill | 根拠不整合の拒否、レビュー未実行/失敗/古い承認の検知、再実行後の旧対象と指摘の追跡、両実行経路の確認 |
| 5 | 保存データ評価・独立レビュー | 修正前後の比較、別日確認、指摘修正、設計と実装の同期 |

各段階で03〜08の関係箇所と共通Skillを同期させる。既存の「強い新着ならHOT閾値を超える」というテストは、新仕様に即して置き換える。全Sourceの人気指標を同一尺度とみなすようなテストを残さない。

### 11.1 保存データによる評価

9/29の全525 Signalの処理件数と除外・保留・候補化の内訳を確認する。意味評価はSourceごとに最大10件を安定ID順で抽出し、旧HOT5件と監査の誤検知例を追加して標本を固定する。2担当が独立に関連性・新規性・検証可能性・採否を判断し、不一致を記録する。評価者の合意を絶対的な真実とは扱わない。

保存rawの派生summaryやkeyword強度をそのまま信用せず、元レスポンスから再マッピングする。再構築不能な項目は理由を記録する。外部再取得結果は当日保存資料と区別する。

別日データは評価ルール調整に使わず、同じ方式で確認する。存在する保存日のうち9/29に最も近い別日を使い、なければ別日収集を行う。ネットワーク制約等で実データを得られない場合は未検証として残し、fixtureテストを別日実データ評価の代用として完了扱いしない。

適合率、標本内の重要項目の見落とし、Source分布、確認不能件数を比較する。選抜0件では適合率を100%にせず算出不可とする。世界全体の網羅率は測定したと主張しない。必須条件は `brokerage` の誤昇格ゼロ、研究が参考値だけで除外されないこと、根拠欠損でのHOT昇格ゼロ、原著者の主張と確認済み事実の区別、企画の具体的な着手条件である。

### 11.2 実行・レビュー検証

ネットワーク不要の自動テストを基本とし、追加Sourceの外部確認は別記する。Agent手順は固定fixtureと隔離出力先で実行し、HOT0件、確認可能な1件、一次根拠取得不能、レビュー起動失敗、重要指摘の修正、3回上限を確認する。Claude Code/Codexのうち実際に確認した環境と未確認環境を明記する。

同日再実行とレビュー修正を行った後も、旧試行の入出力・設定・指摘が保持され、記録ハッシュと一致することを確認する。履歴保存失敗・途中中断でも承認済みに見えないことを検証する。確認優先度は日時欠損、未来日時、7日境界、単独観測、同値、0、欠損混在を固定例で検証する。

独立担当のレビューを必須とし、Critical/Importantを解消する。指摘により発見した再発条件を関係Skill・設計・テストへ残す。

## 11.3 既知の課題(未解決・別タスク対応予定)

2026-10-03、コミット前の `/code-review high` を2回(修正前・修正後)実行して検出し、ユーザー確認のうえ別タスクとして保留した事項。本節は実装の現状を正確に開示する目的で記載し、意図的な欠陥ではない。

### CLI未結線(本番パイプラインから到達不能)

以下のモジュールは現在 `tests/` からのみ呼ばれ、`collect` / `normalize` / `score` / `select-hot` / `save-proposals` / `report` のいずれのCLIサブコマンドからも呼ばれていない。本番の`ai-radar`コマンドは今も旧実装(`normalization.dedup.deduplicate_signals` / `normalization.scores.normalize_source_batch` / `pipeline.events.build_events`)のみで動作する。

- 品質v2パイプライン: `normalize_quality_batch` / `deduplicate_quality_signals` / `build_quality_events` / `normalization/identity.py` / `normalization/relevance.py` / `pipeline/stages.py`(`collect_stage` / `normalize_stage` / `score_stage`)
- `storage/attempts.py`(`begin_attempt` / `finish_attempt` / `invalidate_after`、再実行時の下流無効化)
- `storage/provenance.py::capture_provenance`
- `reporting/review.py`(`build_review_target` / `validate_review_result`)

これらを結線するには、本番CLIの入出力契約変更と関連Skill・運用手順の同時更新が必要であり、別タスクとする(`apply_assessments` は Issue #7 で `select-hot` に、`validate_proposals` は Issue #11 で `save-proposals` に結線済み)。

### 上記モジュール自身に残る不整合(結線時に合わせて解消が必要)

- `pipeline/stages.py::normalize_stage` は `raw/<date>/*.jsonl` のレコードを `"signal_id" in record` で絞り込むが、`collect_stage` が実際に書き出す`RawItem`(`source` / `fetched_at` / `raw_id` / `raw_url` / `payload`)には`signal_id`キーが存在しない。結線時はこのままだと常に0件になる。`adapter.normalize()`(RawItem→CanonicalSignal変換)を呼ぶ処理が未実装。
- `pipeline/stages.py::collect_stage` は `collect_with_diagnostics` 経由で `adapter.collect` を直接呼ぶため、本番の `collect` / `daily` が使う `sources/collection.py::collect_new_items`(`overlap_hours` による重ね取得と収集済み除外、04章)を通らない。期間の既定値も `periods.resolve_default_period`(前回実行からの引き継ぎ、06章)を使っていない。また raw の保存先が `raw/<until>/` で、本番の `raw/<period_date(until)>/` と食い違う。結線時はこれらを本番経路に合わせないと、未実行日や公開日時の遡りによる取りこぼし(Issue #15)が再発する。
- `deduplicate_quality_signals`(`normalization/dedup.py`)と`build_quality_events`(`pipeline/events.py`)は同じ`extract_identity(...)["event_key"]`でグルーピングするため、`normalize_stage`の呼び出し順(dedup→build_quality_events)では`build_quality_events`に渡る時点で同一event_keyのSignalは既に1件に統合済みとなり、`build_quality_events`側の複数member集計(`priority_breakdown` / `representative_signal_id` / `members`)は本番経路では実質発火しない。実際の挙動は`dedup.py::_merge_quality`(優先度が高い側を採用し`metrics`のみ連結、他フィールドは勝者のみ保持)が支配する。
- `sources/public.py::_matches_keywords`が`classify_relevance`の判定結果を`bool(result["matched_terms"])`に丸めて捨てるため、収集後に作られる`CanonicalSignal.quality`は常に空`{}`になる。その結果`normalize_quality_batch`は常にハードコードされた`{"status": "uncertain", ..., "method": "legacy"}`を`quality.relevance`に書き込み、実際のタイトル・概要に基づく関連性判定が反映されない。
- `config/scoring.yaml`の`reference_priority`(`freshness_weight` / `popularity_weight` / `window_hours`)は`normalize_quality_batch`から一切読まれず、同じ値(`168.0` / `0.5` / `0.5`)がコード側にハードコードされている。`pipeline/stages.py::normalize_stage`は`metric_by_source`のみを読み込み渡している。
- `storage/provenance.py::capture_provenance`の機密情報除去はトップレベルのキー名(`key`/`token`/`password`を含むか)と`user:pass@host`形式のURLしか見ておらず、ネストしたdict内の機密情報やURL形式でない裸のトークン文字列は`manifest.json`にそのまま書き込まれる。
- `reporting/review.py::validate_review_result`は`attempt_number`(1〜3)を単独の範囲チェックのみ行い、実際に永続化された実行履歴と突き合わせない。また`findings`内の非dict要素は`isinstance(item, dict)`フィルタで静かに無視されるため、不正形式のfindingに重大指摘が混ざっていても検出できない。さらに、`status`の`not in`判定と、`status`が`approved`のときの`findings`要素の`severity`の`in`判定は、型を確かめずに許容値の集合と照合しているため、値がリストやdictだと`TypeError`になり`ValueError`として扱えない(`approved`以外では`severity`は検証されずに通る。`schemas/quality.py`の`_is_one_of`と同じく、先に文字列であることを確認する必要がある。Issue #7 のレビューで判明)。
- `scripts/evaluate_audit.py::evaluate`の`precision`計算はラベル(`labels`、`signal_id`+正解の`selected`真偽)と実際の選抜(`selected`、`hot_id`)を比較しておらず、`selected`が空でなければ常に`0.0`を返す(空なら`None`で「算出不可」は正しい)。`hot_id`と`signal_id`の対応関係(どのHOT候補がどのSignalに由来するか)を評価に含める設計・実装が別途必要。

### 重複・簡素化(コード品質、動作への影響なし)

- `hashlib.sha256(...).hexdigest()`相当の実装が`scripts/evaluate_audit.py` / `storage/attempts.py` / `storage/provenance.py` / `reporting/review.py`の4箇所に個別に存在し、共通ヘルパーがない。
- `_strongest_event_type`(優先度表: major_model_release等=3, research_signal=1, observed_signal=0)が`pipeline/events.py`と`normalization/dedup.py`の両方にほぼ同一の実装で存在する。
- `normalization/scores.py::_quality_ranks`はO(n²)(既存の`_rank_popularity`と同じ非効率パターンを踏襲)。
- OpenAlexの`abstract_inverted_index`復元(`restore_abstract`)が収集時(`sources/public.py::_summary_text`、診断情報は破棄)と正規化時(`sources/remap.py::remap_raw_item`)の2箇所で同一データに対して重複実行される。
- 新規追加モジュール(`scripts/evaluate_audit.py` / `scoring/assessments.py` / `ideation/validation.py` / `schemas/decoders.py` / `pipeline/stages.py`等)は、セミコロン連結・1行に複数文を詰め込む密な記述スタイルで、既存コードベース(例: `ideation/proposals.py`)の1文1行スタイルと一貫していない。

## 12. 今回の対象外

週次/月次/年次レポートの新実装、研究論文の完全追試、記事の執筆・公開、ユーザー環境へのパッケージ導入実験、無制限のWebクロール、LLM API基盤の新設は含めない。監査の記憶方式比較やLLM審査校正は、今回の修正自体とは別の実験候補として保持する。

## 13. 設計レビュー記録

- 作成者確認: 監査の8対応項目との対応、未確認と0の区別、旧データ互換性、両実行経路、再実行時の失効、検証範囲を確認。
- 独立レビュー: 別サブエージェント `review_audit_design` が監査8項目との対応を確認。初回Criticalなし。Importantの試行履歴保持方式とMinorの確認優先度算式を本書に反映し、再レビューで両指摘の解消と新規指摘なしを確認。設計承認へ提示可能と判定。
- レビュー範囲: 本設計書・インデックスと監査・既存実装の静的照合。未実装コードの動作、外部Source取得、Agent実機、保存データ再評価は未検証。
- ユーザーによる書面承認: 2026-10-01、設計提示後に「実装計画だけ立てて」と指示を受領。実装計画の作成まで承認済み。
- 実装着手の承認: 2026-10-03、ユーザーへ確認し、実装(1〜4段階相当)は別途承認済みであることを確認。本項の記載更新が漏れていたため追記。
