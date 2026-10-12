# N-04 共通Agent運用と保存互換

Claude CodeとCodexが、重複管理せず同じSkill・CLI・設計を参照できること。保存データの移行では、旧形式を読み込める範囲と新形式の契約を明示すること。

## 受入条件

- 同一の資料・Skillを両Agentへ案内する。
- 両環境の手順確認結果を個別に記録し、一方だけの確認で両方を実機確認済みにしない。
- 旧v1データは互換読込し、欠けた品質評価を推測で補完しない。
- 未対応のschema versionを明示的に拒否する。

GitHub Copilot専用対応は希望事項でありMVP必須ではない。[保存版契約](../../../03-detailed-design/data-models/versioning.md)、[共通Skill](../../../03-detailed-design/agent-workflows/README.md)を参照。
