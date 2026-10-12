# F-02 共通形式と重複整理

UC-01・UC-04に対応する。Sourceごとの形式差を吸収し、情報を比較・再処理できる共通形式で保存すること。

## 受入条件

- 収集情報をSignal、出来事をEvent、話題をTopicとして扱える。
- URLの意味のある識別情報を残し、追跡パラメータを理由に同一情報が重複しないようにする。
- 品質改善目標として、同一成果・版・観測を区別し、タイトル一致だけで別成果を統合しない。
- 品質改善目標として、関連性・新着・観測済み人気・欠損を区別し、未取得を0と同一視しない。

対象は両経路。品質v2の指標・identityは未実装(未結線だった品質v2モジュールはPR #33で削除済み。[既知課題](../../../../support/02-planning/known-gaps.md))。[データ契約](../../../03-detailed-design/data-models/README.md)、[現行集約](../../../03-detailed-design/pipeline/grouping.md)、[指標・identity変更設計](../../../05-decisions/audit-remediation/metrics-and-identity.md)を参照。
