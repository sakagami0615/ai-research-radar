# システム境界

利用者はAIエンジニア。公開Source、AI Research RadarのPython CLI、実行Agent、独立レビュー担当、ローカル保存先をつなぐ構成である。

日次レポート作成での人・Skill・Pythonコードの分担は [日次レポート作成の役割分担](../../support/03-reference/daily-run-flow.svg) を参照する。

外部Sourceは認証なしの公開API・RSS等を利用する。取得成功や網羅性は提供側の制約に依存する。AgentはCLIの外から起動し、共通Skillに従う。Python内部からLLM APIを呼ぶ構成ではない。

構造化データはローカル `data/`、利用者向けの日次Markdownは `reports/daily/` に保存する。記事執筆・公開、本格Web UI、週次以上の分析は現在のMVP範囲外。F-01〜F-06、N-04・N-06を実現する境界の概要である。
