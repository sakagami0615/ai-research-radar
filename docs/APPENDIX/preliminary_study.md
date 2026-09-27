# AI Research Radar 設計検討まとめ

## 1. 目的

AIエンジニアとして、AI関連の技術情報・ツール・モデル・研究・トレンドを継続的に収集し、以下の用途に活用できる仕組みを構築する。

### 主な目的

* AI全般の最新情報を広く収集する
* 世の中で現在注目されている技術・ツール・モデルを把握する
* 技術記事のネタになりそうなテーマを発見する
* 「今記事を書く価値が高いテーマ」を早期に検知する
* 最新論文や研究テーマを継続的に蓄積する
* 週次・月次・年次でAI技術トレンドを把握する
* 情報の人気度だけでなく、信憑性・勢い・複数情報源での確認状況も評価する
* 将来的にGitHubや別の調査システムと連携できる構造にする

本システムでは、**記事本文の自動執筆そのものは対象外**とする。

対象とするのは、

* 記事ネタの発見
* 記事企画案の生成
* 記事企画案の評価・討論
* 調査テーマの発見
* AI技術トレンドの可視化

までとする。

---

# 2. 基本設計思想

本システムは単なる「AIニュース収集システム」にはしない。

目指す構造は以下。

```text
情報収集
↓
Signal抽出
↓
Event化
↓
Topic化
↓
人気・勢い・信憑性の評価
↓
HOT判定
↓
記事企画候補生成

または

Topic蓄積
↓
時系列分析
↓
週次・月次・年次トレンド分析
↓
HTML / 画像による可視化
```

特に重要なのは、

> 情報をたくさん集めること

ではなく、

> 広く集めた情報から、人間が見る価値の高いものだけを絞り込むこと

である。

---

# 3. 調査対象の範囲

調査対象は限定しすぎず、**AI全般**とする。

対象カテゴリの例：

* LLM
* Reasoning
* Multimodal
* Vision
* Speech / Voice
* Video Generation
* Image Generation
* Robotics
* World Models
* AI Agent
* Coding Agent
* Agent Framework
* Agent Runtime
* Agent Skill
* MCP / A2A / Protocol
* RAG
* Search / Retrieval
* Embedding
* Vector DB
* Knowledge Graph
* AI Memory
* AI Evaluation
* Benchmark
* AI Security
* Guardrails
* Local LLM
* Edge AI
* AI Infrastructure
* Inference
* Model Serving
* Quantization
* Fine-tuning
* Distillation
* Training
* AI Hardware
* Open Source AI
* AI API / Cloud AI
* AI関連ツール
* AI関連ライブラリ
* 研究論文
* 新モデル
* 新API
* 新サービス
* 標準仕様

カテゴリは固定しすぎず、新しい概念を後から追加できるようにする。

---

# 4. システム全体像

```text
                         AI Research Radar
                                │
          ┌─────────────────────┼─────────────────────┐
          ▼                     ▼                     ▼
    Technology Radar      Research Radar      Community / Content
          │                     │                     │
          └─────────────────────┼─────────────────────┘
                                ▼
                            Raw Signals
                                │
                                ▼
                       Normalize / Dedup
                                │
                                ▼
                           Event Builder
                                │
                                ▼
                           Topic Cluster
                                │
                 ┌──────────────┴──────────────┐
                 ▼                             ▼
            HOT Detector                 Trend Store
                 │                             │
                 ▼                             ▼
        Article Ideation                Time-series Analysis
                 │                             │
                 ▼                  ┌──────────┼──────────┐
        Article Proposals           ▼          ▼          ▼
                                  Weekly     Monthly     Yearly
                                                │
                                                ▼
                                         HTML / Image
```

---

# 5. 情報収集Radar

情報源は用途ごとに分類する。

## 5.1 Technology Radar

目的：

> 新しい技術・ツール・モデル・ライブラリ・サービスを発見する。

対象例：

* GitHub
* GitHub Trending
* GitHub Releases
* Hugging Face
* Hugging Face Models
* Hugging Face Spaces
* PyPI
* npm
* OSS Repository
* 各種AI製品リリース
* AI関連公式ブログ

---

## 5.2 Research Radar

目的：

> 最新研究・先行研究・今後技術トレンドになる可能性がある研究を継続的に把握する。

対象例：

* arXiv
* OpenReview
* OpenAlex
* Semantic Scholar
* Hugging Face Daily Papers
* NeurIPS
* ICML
* ICLR
* ACL
* EMNLP
* AAAI
* IEEE
* ACM

Research Radarについては、毎日すべてを通知する必要はない。

原則として蓄積し、

* 週次
* 月次
* 必要時のDeep Research

に利用する。

---

## 5.3 Community Radar

目的：

> 実際にAIエンジニアやユーザーが何を話題にしているかを把握する。

対象例：

* Hacker News
* Reddit
* GitHub Discussions
* X
* 各種Developer Community

Community情報は原則として、

**根拠情報ではなくTrend Signal**

として扱う。

---

## 5.4 Content Radar

目的：

> どのような技術記事が現在読まれているか、どの分野の記事需要が高いかを見る。

対象例：

* Qiita
* Zenn
* 海外技術ブログ
* 企業Technical Blog

確認したいもの：

* 記事数
* 閲覧数
* Like
* Favorite
* コメント数
* 公開からの経過時間
* 短期間での伸び
* 同一Topicの記事増加数
* 日本語記事の競合状況

Technology RadarとContent Radarは分離する。

例えば、

```text
技術として流行している
```

と、

```text
その技術の記事が読まれている
```

は別の現象である。

---

# 6. 情報単位

収集情報は以下の3段階で扱う。

## Signal

個別サイト上で観測された事象。

例：

```text
GitHub RepositoryのStarsが24時間で急増
```

---

## Event

意味のある出来事としてまとめたもの。

例：

```text
Googleが新しいAgent Runtimeを公開
```

---

## Topic

複数EventやSignalを束ねる技術テーマ。

例：

```text
Agent Runtime
```

関係：

```text
Signal
↓
Event
↓
Topic
```

これにより、

「1件の記事がバズった」

ことと、

「技術トレンド自体が伸びている」

ことを区別する。

---

# 7. Daily / Weekly / Monthly / Yearly

時間軸によって目的を変える。

同じ情報を期間だけ変えて出力する設計にはしない。

---

## 7.1 HOT Alert

目的：

> 今すぐ確認する価値が高い情報を通知する。

対象例：

* 大型モデル公開
* 大型API公開
* 主要OSS公開
* 短時間で急成長しているツール
* 大きな仕様変更
* 新しい標準
* 業界への影響が大きい発表
* 記事化のタイミングが非常に重要なTopic

通知件数は原則少数とする。

目安：

```text
通常：0〜2件 / 日
多い日：最大5件程度
```

件数上限を厳密に制御するというより、

**HOTの閾値を高く設定する**

ことで通知過多を防ぐ。

---

## 7.2 Daily Radar

目的：

> 今日AI業界で何が起きたかを短く確認する。

例：

```text
AI Daily Radar

HOT
- XXX Model公開
- YYY Tool急上昇

Tools
- AAA
- BBB

Models
- CCC

Research
- 17 papers stored

Emerging Topics
- Agent Runtime ↑
- Voice Agent ↑
- Traditional RAG →
```

毎日大量の論文要約などは出さない。

---

## 7.3 Weekly Trend

目的：

> 今週、何が伸びたかを見る。

例：

```text
Agent Runtime       ↑↑
Coding Agent        ↑
World Models        ↑
RAG                 →
Vector DB           ↓
```

重要なのは件数ではなく、

**前週と比較した変化**

を見ること。

---

## 7.4 Monthly Landscape

目的：

> AI技術領域全体がどのように変化しているかを見る。

例：

```text
AI Landscape

LLM
├─ Reasoning
├─ Long Context
└─ Small Models

Agents
├─ Coding Agent
├─ Agent Runtime ↑↑
├─ Skills ↑
└─ MCP →

Multimodal
├─ Video
├─ Voice ↑
└─ Robotics ↑

RAG
├─ Graph RAG
├─ Agentic RAG
└─ Traditional RAG ↓
```

---

## 7.5 Yearly Review

目的：

> 1年間で技術がどの段階まで成熟したかを見る。

Technology Lifecycleを利用する。

例：

```text
Emerging
Growing
Mainstream
Mature
Declining
```

さらに前年との状態遷移を見る。

例：

```text
Coding Agent
Emerging → Mainstream

MCP
Emerging → Growing

Traditional Vector RAG
Mainstream → Mature
```

---

# 8. レポート可視化

Weekly / Monthly / Yearly Reportについては、

**Markdownや文章だけをPrimary Outputにしない。**

人間が短時間で確認できるよう、

* HTML
* グラフ
* 図
* 静的画像

を利用する。

---

# 9. HTMLの役割

HTMLは人間が確認する本体として扱う。

利用例：

* Topic Filter
* Category Filter
* Timeline
* Trend Chart
* Hover Detail
* Source Link
* HOT Event表示
* Topic Drill-down
* Technology Landscape
* Article Opportunity一覧

---

# 10. 画像の役割

Static Imageは共有用途。

例：

```text
Weekly Trend Map.png
AI Landscape Sep-2026.png
2026 AI Technology Radar.png
```

用途：

* SNS
* 技術記事
* プレゼン
* Markdown資料
* 月報

---

# 11. 可視化と分析を分離する

Visualization Skillに技術判断をさせない。

構造：

```text
Trend Analyzer
↓
Structured JSON
↓
Visualization Skill
↓
HTML / PNG
```

例：

```json
{
  "period": "2026-W39",
  "topics": [
    {
      "name": "Coding Agent",
      "momentum": 91,
      "direction": "up",
      "events": 17
    }
  ]
}
```

Visualization Skillは、

**判断済みデータを見やすく表示するだけ**

にする。

---

# 12. 人気度をサイト横断で比較する課題

サイトごとの生値を直接比較してはいけない。

例：

```text
Site A
100 views

Site B
150 views
```

だけでは、どちらが人気か判断できない。

なぜなら、

```text
Site Aの平均：20 views
Site Bの平均：3000 views
```

かもしれないため。

したがって、

**サイト内相対値へ変換して比較する。**

---

# 13. Percentile Rank

初期実装では、Popularity正規化にはPercentile Rankを優先する。

例：

```text
GitHub AI Repository
24時間Stars

Repository A：上位1%
Repository B：上位8%
Repository C：上位63%
```

なら、

```text
A = 99
B = 92
C = 37
```

として扱う。

これにより、

```text
GitHub 99
Qiita 97
Zenn 95
```

のように共通尺度へ変換可能になる。

---

# 14. Peer Group

Percentile計算の母集団は、

単純なPlatform単位にしない。

基本単位：

```text
Platform
×
Category
×
Age
```

例：

```text
GitHub
×
AI Agent
×
公開後0〜24時間
```

または、

```text
Zenn
×
LLM
×
公開後0〜72時間
```

これにより、

* カテゴリごとの人気差
* 公開後経過時間
* プラットフォーム規模

を吸収する。

---

# 15. PopularityとMomentum

この2つは分離する。

## Popularity

> 現在どれだけ人気があるか。

例：

```text
Popularity = 91
```

---

## Momentum

> 現在どのくらい急激に伸びているか。

例：

```text
Momentum = 99
```

HOT判定では、

```text
Momentum > Popularity
```

と考える。

---

# 16. Age Normalization

累積人気だけではHOT判定できない。

例：

```text
Repo A
1000 stars
公開30日

Repo B
500 stars
公開8時間
```

この場合、Repo Bの方がHOTである可能性が高い。

そのため、

* Stars / hour
* Stars / day
* Likes / hour
* Views / hour
* Mentions / day

などのVelocityを利用する。

---

# 17. Burst Detection

Topic Trendでは、

「普段よりどれだけ急増したか」

を見る。

利用候補：

* Percentile
* log transform
* robust z-score
* Kleinberg Burst Detection

例：

```text
MCP

先週
GitHub 20
Zenn 3
Qiita 5
HN 2

今週
GitHub 75
Zenn 22
Qiita 31
HN 15
```

単純な件数ではなく、

**通常状態から急激に伸びている**

ことを検出する。

---

# 18. SourceごとのRaw Metric

全サイトで同じ指標を無理に取得しない。

## GitHub

例：

* Stars
* Stars / 24h
* Forks
* Contributors
* Issues
* Commit Activity
* Release Activity

---

## Qiita / Zenn

例：

* Views
* Likes
* Comments
* Publication Age
* Views / hour
* Likes / hour

---

## Hacker News

例：

* Points
* Comments
* Age
* Points / hour

---

## Reddit

例：

* Score
* Comments
* Upvote Ratio
* Score Velocity

---

## Research

例：

* Citation Count
* Citation Velocity
* Citation Acceleration
* Related Paper Growth
* Influential Citation

論文については、一般Contentと別のNormalizationを行う。

---

# 19. 共通Normalized Signal

各サイト固有Metricを以下の共通指標に変換する。

```text
Popularity
Momentum
Engagement
Credibility
Cross-source Confidence
```

これにより、上位SkillがSite固有Metricを理解する必要をなくす。

---

# 20. Cross-source Confidence

単一サイトでのバズと、本当の技術トレンドを区別する。

例：

Topic A：

```text
GitHub      99
HN          97
Reddit      92
Zenn        85
Qiita       83
```

Topic B：

```text
GitHub      100
他          観測なし
```

この場合、

Topic Aの方がトレンドとしての確度は高い可能性がある。

---

# 21. Source Diversity

Cross-sourceでは単純なサイト数だけを数えない。

情報源Familyを考慮する。

例：

```text
Official
Developer
Research
Community
Japanese Content
```

以下のように複数Familyで確認できる場合、

```text
Official ✓
Developer ✓
Community ✓
Japanese Content ✓
```

Cross-source Confidenceを高くする。

同じReddit内で10件出ても、

10 Sourceとして扱わない。

---

# 22. Independent Source

転載や引用の連鎖は独立情報源として扱わない。

例：

```text
記事A
↓
記事Aを転載したB
↓
Bを紹介したC
```

は、

3 Source

として数えない。

可能な限り、

```text
Independent Source Count
```

を持たせる。

---

# 23. Credibility

人気と信憑性は完全に分離する。

以下の状態は許容する。

```text
Popularity 99
Credibility 25
```

例：

SNSでバズっているリーク。

逆に、

```text
Popularity 40
Credibility 100
```

例：

公式ドキュメントの重要な更新。

---

# 24. Credibility評価軸

例：

```text
Source Authority
Primary Evidence
Independent Confirmation
Claim Evidence
```

概念的なSource Hierarchy：

```text
Primary Source
公式発表
論文
公式Repository
仕様書

↓

Reliable Secondary Source

↓

Technical Media

↓

Community

↓

Unverified Social Information
```

ただし固定点だけではなく、

「具体的な主張を裏付ける一次情報が存在するか」

も見る。

---

# 25. 最終的な主要Score

現時点では最低限以下の4つを持つ。

```text
Popularity
Momentum
Credibility
Cross-source Confidence
```

すべて0〜100程度の共通尺度に変換する。

---

# 26. HOT Score

初期案：

```text
HOT =
0.40 Momentum
+ 0.25 Popularity
+ 0.20 CrossSource
+ 0.15 Credibility
```

ただし最初から固定しない。

運用結果を見て調整する。

HOTではMomentumを比較的大きく評価する。

---

# 27. HOT例外ルール

すべてスコアだけで判定すると、

公開直後の重大情報を取り逃がす。

例：

```text
新しい大規模モデルが10分前に公開
```

まだPopularityは低い可能性がある。

そのため、

Rule-based Triggerを併用する。

例：

```text
IF
source = Tier1 Official
AND
event_type = Major Model Release
THEN
hot_candidate = true
```

---

# 28. HOT Candidate判定例

```text
A)
Official Major Event

OR

B)
Momentum >= 95
AND Popularity >= 85

OR

C)
Momentum >= 90
AND CrossSource >= 80

OR

D)
Popularity >= 98
AND Novelty >= 80
```

その後、

```text
Statistics
↓
Rules
↓
LLM Judge
```

として、

> 本当にAIエンジニアへ知らせる価値があるか

を判断する。

生データをそのままLLMへ渡して全判断させない。

---

# 29. Article Opportunity

HOTと「記事にする価値」は分ける。

例えば、

```text
HOT = 95
```

でも、日本語記事がすでに大量に存在する場合、

記事Opportunityは低いかもしれない。

記事Opportunityには例えば以下を利用する。

```text
HOT / Momentum
Engineer Interest
Japanese Content Gap
Experimentability
Novel Angle Availability
Technical Depth
Timing
```

---

# 30. Article Opportunityを単一ランキングにしない

「良い記事」の定義は一つではない。

例えば、

* PVが期待できる
* Likeが期待できる
* 最新性が高い
* 技術的に深い
* エンジニアとして学びがある
* 実験できる
* 競合記事が少ない
* 独自性がある

など複数の価値がある。

そのため最終候補を、

```text
Traffic Opportunity
Technical Opportunity
Unique Angle
Trend Bet
```

のような複数カテゴリで提示することを検討する。

---

# 31. HOTから記事企画を作る処理

HOT 1件ごとに、

複数視点から大量の技術記事案を生成する。

単一LLMに、

```text
記事案を5個出して
```

とするだけではなく、

複数の専門Roleで発散させる。

---

# 32. Article Ideation Agent Roles

## Trend Analyst

観点：

* なぜ今書く意味があるか
* 勢い
* 市場・技術トレンド
* 今後の波及

---

## Technical Analyst

観点：

* アーキテクチャ
* 内部実装
* API
* Benchmark
* 技術差分

---

## Hands-on Engineer

観点：

* Getting Started
* 実験
* 比較
* ローカル実行
* Performance
* 再現性

---

## Reader Analyst

観点：

* 読者は何を知りたいか
* 初心者
* 中級者
* AI Engineer
* 実務利用者

---

## Content Strategist

観点：

* 読まれそうか
* タイトルとして強いか
* 日本語競合
* 検索需要
* SNS拡散可能性

---

## Skeptic / Reviewer

観点：

* それは本当に記事になるか
* 公式ドキュメントを読めば終わりではないか
* 競合記事が多すぎないか
* 技術的に薄くないか
* 検証可能か

---

## Wildcard

観点：

* 普通ではない切り口
* 失敗例
* 批判的検証
* 意外な比較
* Benchmark
* Internal Reproduction
* Security
* Cost
* Performance

---

# 33. Agent数について

数十案を生成するからといって、

数十Agentを立てる必要はない。

推奨：

```text
6 Agents
×
5 Ideas

= 30 Ideas
```

程度。

これにより、

* コスト
* Context
* 重複
* 管理
* 再現性

を改善する。

---

# 34. Article Ideation Workflow

## Phase 1: Divergence

```text
HOT
 │
 ├─ Trend Agent       5 ideas
 ├─ Technical Agent   5 ideas
 ├─ Hands-on Agent    5 ideas
 ├─ Reader Agent      5 ideas
 ├─ Content Agent     5 ideas
 └─ Wildcard Agent    5 ideas
                ↓
             30 ideas
```

---

## Phase 2: Dedup / Cluster

類似案を統合する。

例：

```text
XXXを使ってみた
XXX入門
XXX Getting Started
```

↓

```text
Hands-on Introduction
```

30案から、

```text
10〜15案
```

程度まで削減する。

---

## Phase 3: Critique

各案を複数視点でレビュー。

評価例：

* Technical Depth
* Novelty
* Timeliness
* Audience Fit
* Experimentability
* Competition
* Effort
* Evidence Availability

ただし単純合計点だけで落とさない。

---

## Phase 4: Debate

全30案を議論させるのではなく、

絞り込まれた6〜8案程度を対象とする。

Role例：

```text
Advocate
なぜ書くべきか

Critic
なぜ書くべきではないか

Technical Reviewer
技術記事として成立するか

Audience Reviewer
誰が読むのか

Editor
どう改善すれば強くなるか
```

---

## Debate Round 2

必要な場合のみ、

```text
Advocate Rebuttal
Critic Rebuttal
Editor Synthesis
```

まで行う。

基本2Round程度で十分とする。

---

# 35. Debateの目的

単純な「勝者決定」にはしない。

異なる記事Angleを残す。

例：

新しいモデルが出た場合、

```text
1. Breaking News
「何が変わったのか」

2. Benchmark
「旧モデルと比較」

3. Architecture
「新機能の仕組み」

4. Production
「移行する価値があるか」

5. Critical Review
「Benchmark改善は本当か」
```

のように異なる記事方向性を残す。

---

# 36. Article Archetype

自由発想だけにすると、

```text
XXXを使ってみた
```

ばかりになる可能性がある。

そのためArticle Archetypeを定義する。

候補：

```text
Breaking News
Technical Explainer
Hands-on
Benchmark
Comparison
Architecture Deep Dive
Migration Guide
Best Practice
Failure Analysis
Reproduction
Paper → Implementation
Opinion / Analysis
Security Analysis
Performance Analysis
Tutorial
```

HOTごとに、

> どのArchetypeが適切か

を判断させる。

---

# 37. Article Gap

最も重要な分析の一つ。

見るべきもの：

```text
世間の関心
×
記事数
×
記事品質
×
記事種類
```

例：

```text
関心：HIGH
紹介記事：MANY
比較記事：ZERO
実験記事：ZERO
```

なら、

> 紹介記事ではなく比較・実験記事を書く

という提案が可能。

---

# 38. Article Ideation最終出力

HOT 1件あたり、

```text
30〜50 Ideas
↓
10〜15 Clusters
↓
6〜8 Serious Candidates
↓
Debate
↓
3〜5 Proposals
```

程度を目安とする。

ユーザーには最終Proposalのみ提示する。

---

# 39. 最終Article Proposal例

```text
HOT
新モデル XXX 公開

Article Proposal

Title Idea
XXXを旧モデルと実測比較

Article Type
Benchmark / Comparison

Target Reader
AI Engineer

Why Now
公開直後で比較記事が少ない

Experiment
- Coding
- RAG
- Structured Output
- Latency

Competition
Low

Traffic Opportunity
High

Technical Opportunity
High

Unique Angle
Medium
```

---

# 40. 情報源追加の設計

重要な設計判断：

**サイトごとにSkillを作らない。**

代わりに、

```text
Skill
↓
Common Collector Layer
↓
Source Adapter
```

という構造にする。

---

# 41. SkillとSource Adapterの責務

## Skill

「何をしたいか」で分ける。

例：

```text
ai-radar
hot-detector
trend-analyzer
article-ideation
weekly-report
monthly-report
yearly-report
```

---

## Source Adapter

「どのサイトから取得するか」を担当。

例：

```text
github.py
hackernews.py
reddit.py
qiita.py
zenn.py
huggingface.py
arxiv.py
openalex.py
openreview.py
```

---

# 42. サイトごとにSkillを作らない理由

以下の処理が重複するため。

* Date Range
* AI関連判定
* Dedup
* Popularity Normalization
* Momentum Calculation
* Schema Conversion
* Retry
* Error Handling

サイトごとにSkill化すると、

同じロジックが大量に複製される。

---

# 43. Source Adapter Interface

概念例：

```python
class SourceAdapter:
    def collect(self, since, until):
        ...

    def normalize(self, item):
        ...

    def get_metrics(self, item):
        ...
```

新しいサイトを追加する場合、

新しいAdapterを追加する。

---

# 44. Source Registry

設定ファイルで情報源を管理する。

例：

```yaml
sources:

  github:
    enabled: true
    family: technology
    adapter: github

  arxiv:
    enabled: true
    family: research
    adapter: arxiv

  qiita:
    enabled: true
    family: content
    adapter: qiita
```

これにより、

```text
GitHubだけOFF

Research Sourceだけ収集

Content Sourceだけ収集
```

などが可能。

---

# 45. Source Family

情報源をFamily化する。

例：

```text
Technology
├─ GitHub
├─ Hugging Face
├─ PyPI
└─ npm

Research
├─ arXiv
├─ OpenReview
├─ OpenAlex
└─ Semantic Scholar

Community
├─ Hacker News
├─ Reddit
└─ X

Content
├─ Qiita
├─ Zenn
└─ Technical Blogs

Official
├─ OpenAI
├─ Anthropic
├─ Google
├─ Meta
└─ Microsoft
```

Cross-source Confidenceで利用する。

---

# 46. Canonical Schema

Adapter出口ではすべて共通フォーマットへ変換する。

例：

```yaml
source: github

source_family: technology

content_type: tool

title: XXX

url: XXX

published_at: XXX

category:
  - agent

metrics:
  raw:
    stars: 1520
    stars_24h: 800

metadata:
  owner: XXX
```

---

# 47. Normalization Pipeline

```text
Source-specific Raw Metrics
↓
Source Adapter
↓
Canonical Schema
↓
Platform-specific Normalization
↓
Global Signal
```

共通Signal：

```text
Popularity
Momentum
Engagement
Credibility
```

---

# 48. Skill側はSite固有情報を知らない

例えばhot-detectorが直接、

```text
GitHub Stars
Qiita Likes
Reddit Score
```

を見ない。

代わりに、

```yaml
popularity: 92
momentum: 97
credibility: 85
cross_source: 91
```

を見る。

これによりSource追加時にSkill変更を最小化できる。

---

# 49. Source追加

新しいSource追加時の基本作業：

```text
1. Source Adapter追加
2. Raw Metrics Mapping追加
3. Normalization設定追加
4. Registryへ追加
```

Radar Skill自体は原則変更しない。

---

# 50. 将来的なAdapter Generator

将来的には、

```text
Source Adapter Generator Skill
```

を用意することも検討可能。

入力：

* URL
* API仕様
* 取得したいMetric

出力：

* Adapter雛形
* Canonical Schema Mapping
* Metrics Mapping
* Test Code

これにより情報源拡張を容易にする。

---

# 51. Skill構成案

```text
skills/

radar/
  ai-radar

processing/
  hot-detection
  trend-analysis

article/
  article-ideation

report/
  weekly-report
  monthly-report
  yearly-report

visualization/
  trend-dashboard
  technology-landscape
```

細かい処理をすべてSkill化しすぎない。

---

# 52. Skillと実装コードの境界

基本原則：

```text
Skill
=
Workflow / Reasoning

Script / Adapter
=
Implementation
```

例えば、

```text
GitHub Collector
```

はSkillではなくAdapter / Script。

```text
今日のAI HOT Topicを抽出する
```

はSkill。

---

# 53. ディレクトリ構成案

```text
ai-research-radar/

├─ skills/
│  ├─ ai-radar/
│  ├─ hot-detection/
│  ├─ article-ideation/
│  ├─ trend-analysis/
│  └─ report-generation/
│
├─ sources/
│  ├─ base.py
│  ├─ github.py
│  ├─ hackernews.py
│  ├─ reddit.py
│  ├─ qiita.py
│  ├─ zenn.py
│  ├─ huggingface.py
│  ├─ arxiv.py
│  └─ openalex.py
│
├─ normalization/
│  ├─ popularity.py
│  ├─ momentum.py
│  ├─ credibility.py
│  └─ cross_source.py
│
├─ schemas/
│  ├─ signal.py
│  ├─ event.py
│  └─ topic.py
│
├─ config/
│  ├─ sources.yaml
│  ├─ categories.yaml
│  └─ scoring.yaml
│
├─ data/
│
├─ reports/
│
└─ tests/
```

---

# 54. データ保存

初期段階で大規模なシステムは不要。

候補：

```text
JSONL
SQLite
Markdown
```

初期MVPではSQLite程度でも十分。

保存対象：

* Raw Signal
* Event
* Topic
* Daily Score
* Popularity
* Momentum
* Credibility
* Cross-source
* HOT判定
* Article Opportunity
* Topic History

---

# 55. Topic Memory

Topicごとに継続状態を保持する。

例：

```yaml
topic: coding-agent

related_topics:
  - agent-skill
  - mcp
  - harness-engineering

known_tools:
  - XXX

open_questions:
  - XXX

trend_history:
  - ...
```

これにより毎回ゼロから調査せず、

```text
前回
↓
今回
↓
差分
```

を見ることができる。

---

# 56. Topic自動拡張

検索キーワードを固定しすぎない。

構造：

```text
Seed Topics
↓
New Keywords
↓
Candidate Topic
↓
Human / Rule Approval
↓
Monitoring Target
```

例：

```yaml
topic: agent-harness

discovered_from:
  - github
  - technical-blog

related_to:
  - coding-agent
  - agent-engineering

confidence: 0.82
```

最初から自動で本監視対象に追加せず、

Candidate Topicとして保持する。

---

# 57. Daily Processing

```text
Daily

Source Collection
↓
Normalize
↓
Deduplicate
↓
Event Build
↓
Topic Cluster
↓
Popularity / Momentum
↓
Cross-source
↓
Credibility
↓
HOT Judge
```

HOTの場合：

```text
HOT
↓
Article Ideation
↓
3〜5 Article Proposals
↓
User Notification
```

HOTでないもの：

```text
Store
↓
Trend Analysis用時系列データ
```

---

# 58. Weekly Processing

```text
7日分データ
↓
Topic Aggregation
↓
Momentum Change
↓
Burst Detection
↓
Emerging Topic Detection
↓
Weekly Trend
↓
HTML / Image
```

Research情報についても週次でまとめる。

---

# 59. Monthly Processing

```text
4〜5週分
↓
Technology Landscape
↓
Category Trend
↓
Topic Lifecycle
↓
Major Tool / Model / Research
↓
Monthly Report
↓
HTML / Image
```

---

# 60. Yearly Processing

```text
12か月
↓
Long-term Trend
↓
Lifecycle Transition
↓
Technologies that Emerged
↓
Technologies that Matured
↓
Technologies that Declined
↓
Annual AI Technology Radar
```

---

# 61. 初期MVP

最初から全機能を実装しない。

Phase 1として推奨：

```text
ai-radar
Source Adapters
Normalizer
HOT Detector
Article Ideation
Simple Data Store
```

Sourceも初期は絞る。

候補：

```text
GitHub
Hugging Face
Hacker News
Qiita
Zenn
arXiv
OpenAlex
Official Blogs
```

---

# 62. MVPで確認すること

最低2〜4週間程度実際に動かし、

以下を確認する。

* HOTが多すぎないか
* HOTを取り逃していないか
* Popularity Percentileが妥当か
* Momentumが過敏でないか
* 特定Sourceに偏っていないか
* Community Noiseが多すぎないか
* Article Ideaに重複が多くないか
* Article Ideaが「使ってみた」に偏っていないか
* 日本語記事Gapを正しく捉えられているか
* Source追加が容易か

---

# 63. スコア調整

初期段階から複雑なML Rankingは利用しない。

最初は、

```text
Explainable Rule
+
Percentile
+
Momentum
+
Cross-source
+
Credibility
```

を利用する。

3〜6か月程度データが蓄積した後、

```text
HOT判定結果
↓
実際に後から大きなトレンドになったか
```

を比較する。

そのデータを使い、

* Weight調整
* Threshold調整
* Feature追加
* Ranking Model

を検討する。

---

# 64. Explainability

スコアそのもの以上に、

> なぜHOTと判定されたか

を説明できることが重要。

例：

```text
HOT 96

理由：

Momentum
GitHub AI Agentカテゴリ上位1%

Cross-source
GitHub / HN / Reddit / Zennで確認

Credibility
Official Repositoryあり

Article Opportunity
日本語比較記事ほぼなし
```

この情報はArticle Ideation Agentにもそのまま渡せる。

---

# 65. 非推奨設計

以下は避ける。

## AIニュースをそのまま大量に要約する

```text
RSS
↓
LLM
↓
AIニュース30件
```

人間が見なくなる可能性が高い。

---

## サイトごとにSkillを作る

ロジックが重複し、管理困難になる。

---

## LLMだけでHOTを判断する

再現性が低く、数字の扱いも不安定。

---

## Raw View / Like / Starsを直接比較する

サイト規模・年齢・カテゴリが違うため意味が薄い。

---

## PopularityとCredibilityを統合してしまう

バズっている誤情報を高品質情報と誤認する。

---

## 全Candidateを即通知する

通知疲れを起こす。

---

## 全記事Ideaを全Agentで自由討論する

計算量・Context・コストが急増する。

---

## Visualization Agentに分析させる

見た目と分析責務が混在する。

---

## 最初からVector DB / Graph DB / LangGraphなどを大量導入する

初期規模では過剰設計となる可能性が高い。

---

# 66. 推奨アーキテクチャまとめ

```text
                     ┌─────────────────┐
                     │    AI Radar     │
                     └────────┬────────┘
                              │
                     Collector Layer
                              │
             ┌────────────────┼────────────────┐
             ▼                ▼                ▼
        Technology        Research         Community
         Sources           Sources           Sources
             │                │                │
             └────────────────┼────────────────┘
                              ▼
                     Source Adapters
                              │
                              ▼
                     Canonical Schema
                              │
                              ▼
                        Normalizer
                              │
                              ▼
                    Signal / Event / Topic
                              │
             ┌────────────────┴────────────────┐
             ▼                                 ▼
        HOT Detection                    Trend Store
             │                                 │
             ▼                                 ▼
       Article Ideation                 Time-series
             │                                 │
             ▼                      ┌──────────┼──────────┐
      Article Proposals             ▼          ▼          ▼
                                  Weekly     Monthly     Yearly
                                    │          │          │
                                    └──────────┼──────────┘
                                               ▼
                                         Visualization
                                               │
                                     ┌─────────┴─────────┐
                                     ▼                   ▼
                                    HTML                PNG
```

---

# 67. 現時点で採用する主要方針

1. AI全般を広く監視する。

2. 情報収集と人間への通知を分離する。

3. HOTは原則0〜数件程度に絞る。

4. 重大Official Eventはスコアだけに依存せず即時候補化する。

5. PopularityはPlatform × Category × Ageで正規化する。

6. Raw MetricではなくPercentileを中心に扱う。

7. PopularityとMomentumを分離する。

8. 信憑性はPopularityとは別軸で保持する。

9. 複数独立情報源で確認されたTopicを高く評価する。

10. SiteごとにSkillを作らずSource Adapter化する。

11. Skillは用途・Workflow単位で分割する。

12. HOTごとに複数Roleで記事案を大量生成する。

13. Article IdeaはCluster → Critique → Debate → Synthesisの順で絞る。

14. 記事候補は単一ランキングにせず複数価値軸で提示する。

15. Weekly / Monthly / Yearlyはそれぞれ異なる分析目的を持つ。

16. レポートはHTML / ImageをPrimary Visualizationとする。

17. VisualizationとTrend Analysisは分離する。

18. 最初は単純で説明可能なルールベースから始める。

19. 数か月の実績データからScoreを後で最適化する。

20. 長期的には新Sourceを追加しやすいPlug-in型構造にする。

---

# 68. 今後詰める必要がある事項

## 情報源

* 初期監視Sourceの確定
* API利用可否
* RSS利用可否
* Web取得方式
* Rate Limit
* 認証
* 利用規約
* Crawl制限

---

## Canonical Schema

* Signal Schema
* Event Schema
* Topic Schema
* Article Proposal Schema

---

## Normalization

* PlatformごとのRaw Metric
* Peer Group定義
* Percentile計算方法
* Age Bucket
* Category Bucket
* log normalization
* robust z-score

---

## HOT

* Weight
* Threshold
* Official Override Rule
* Notification Rule
* Notification Channel

---

## Credibility

* Source Tier
* Authority Score
* Primary Evidence判定
* Independent Source判定
* Claim Verification

---

## Article Opportunity

* Engineer Interest
* Japanese Content Gap
* Experimentability
* Timing
* Novelty
* Technical Depth
* Article Archetype
* Traffic Opportunity
* Technical Opportunity
* Unique Angle

---

## Article Debate

* Agent Role
* Idea件数
* Cluster方式
* Critique方式
* Debate Round数
* Final Proposal数

---

## Trend Analysis

* Weekly Momentum
* Monthly Landscape
* Lifecycle判定
* Burst Detection
* Emerging Topic
* Declining Topic

---

## Visualization

* HTML Dashboard構成
* Weekly Template
* Monthly Template
* Yearly Template
* Technology Landscape
* Static Image

---

## Persistence

* JSONL / SQLite
* Data Retention
* Topic History
* Signal History
* Raw Data保持期間
* Report保存形式

---

## Execution

* Claude Code
* Codex
* Skill
* Scripts
* Scheduler
* Local Execution
* 必要に応じた外部API

---

# 69. 次フェーズ

次はこの設計案をそのまま実装するのではなく、

以下の順番で具体化する。

```text
1. Requirements
↓
2. Source Selection
↓
3. Data Model
↓
4. Scoring Design
↓
5. Skill Boundary
↓
6. Directory / Architecture
↓
7. MVP Scope
↓
8. Implementation Plan
↓
9. Test Strategy
↓
10. Operation Design
```

このMarkdownを設計検討のベースドキュメントとし、VS Code上で、

```text
requirements.md
architecture.md
data-model.md
scoring.md
skills.md
implementation-plan.md
```

などへ必要に応じて分割していく。
