# ドキュメント移行対応表と検証記録

日付: 2026-10-10。対象はユーザー承認済みの番号付きフォルダへの再編。旧ファイルの本文をテーマ別に移し、参照を更新した。コード・設定・Skillの実行分岐は変更しない。

## 旧資料の移動先

| 旧資料 | 主な移動先 | 分割したテーマ |
| --- | --- | --- |
| 01 コンセプト | [要求・要件](../../spec/01-requirements/README.md)、[初期判断](../../spec/05-decisions/initial-mvp-policy.md) | 背景、範囲、初期成功条件、方式の理由 |
| 02 アーキテクチャ | [基本設計](../../spec/02-architecture/README.md) | 構成要素、データの流れ、依存、障害境界 |
| 03 データ・保存 | [データ契約](../../spec/03-detailed-design/data-models/README.md)、[表示契約](../../spec/03-detailed-design/reporting/README.md) | 版、保存、Signal、Event・Topic、選抜、共通品質、企画、実行、表示、補助記録 |
| 04 Adapter | [Source設計](../../spec/03-detailed-design/source-adapters/README.md) | Interface、公開Source、期間、raw・追加、障害 |
| 05 Pipeline | [Pipeline](../../spec/03-detailed-design/pipeline/README.md)、[digest](../../spec/03-detailed-design/reporting/digest.md) | 日次、旧スコア、集約、企画、ダイジェスト(品質v2の移行状況はPR #33の取り込みで削除) |
| 06 CLI・運用 | [CLI](../../spec/03-detailed-design/cli/README.md)、[運用](../01-operations/README.md) | 期間解決、コマンド、設定、cron、結果確認、ネットワーク・保持、コミット |
| 07 Skill | [Agent詳細](../../spec/03-detailed-design/agent-workflows/README.md)、[改善運用](../01-operations/review-and-improvement.md) | 共通の役割、Skillごとの責任、レビュー・改善 |
| 08 テスト・拡張 | [検証](../../spec/04-verification/README.md)、[将来拡張](future-extensions.md)、[既知制約](../01-operations/known-limitations.md) | テスト、回帰、拡張、制約 |
| 09 監査改善 | [変更設計](../../spec/05-decisions/audit-remediation/README.md)、[受入](../../spec/04-verification/audit-remediation-acceptance.md)、[既知課題](known-gaps.md) | 問題と目標、関連性・根拠、指標・identity、収集・企画、実行・表示、段階別検証、承認履歴 |
| APPENDIX | [参考調査](../03-reference/README.md) | 既存予備調査、全体図、設計手法調査、初回評価 |

## 追加した入口

要求と要件ID、利用場面、未決定事項、要件→設計→検証の対応、受入シナリオ、適用状況、未達からのバックログを追加した。旧内容にある方針から整理しており、新たな数値目標や将来機能を確定していない。

旧章の参照番号は資料名へ変更し、本文・README・AGENTS.md・Skill・図の参照先を更新した。旧 `docs/specs` と `docs/APPENDIX` のファイルは新しい正本へ移しており、同じ本文の互換コピーは保持しない。Gitの履歴と本表で移動前を追える。

## 既存の未配置資料

旧監査原本 `reports/audits/2026-09-29-daily-report-audit.md` と旧Git管理対象外の実装計画は、このworktreeで参照できない場合がある。参照の存在を捏造せず、所在・未確認を変更設計と計画入口へ記した。

## 検証・レビュー

対象は文書の構成、分割時の情報保持、相対リンク、旧参照、要件ID対応、Agentの参照先解決。アプリの全件テスト・外部収集・日次Agent実行の受入は今回の対象外。

- ローカルMarkdownリンク488件を確認し、欠落0件。コード内の表示例はリンクと分けて確認した。
- 旧specs01〜09の全見出しが移動先に残ることを確認。独立担当は旧長文段落を正規化照合し、実質的な情報欠落を検出しなかった。
- 要件13件が要件一覧・検証対応表・適用状況のすべてに存在することを確認。各文書フォルダにREADMEがあること、README・AGENTS・Skillの能動的参照に旧パスが残らないことを確認した。
- Claude CodeをRead／Glob／Grepのみで起動し、SelectionInput、ProposalQuality、save-proposals v2、cronの対話制約、F-03の正本と必須条件を回答できた。終了コード0、権限拒否なし。日次処理は実行していない。Codexでは本セッションの静的確認を行い、独立したCodex実機ナビゲーション試験は実施していない。
- 独立担当 `review_document_reorganization` が構成・リンク・情報保持・要件から計画への対応をレビュー。初回は期間契約への導線にMinor1件、Critical／Important0件。直接リンクへ修正後、再レビューで全指摘0件。
- `git diff --check` を確認。コミットは作成していない。
- 移動後のSVGはXML構文を検証し、Chromeで文言更新後の表示を確認した。

レビューで得た維持規則として、フォルダREADMEは読む順を持たせ、Skillの必須契約・条件分岐に必要な参照は、一覧だけでなく該当の正本へ直接つなぐ。図の文言は今回移動先へ更新したが、システムの構成変更はない。

## 要求・要件フォルダの追加整理

ユーザー承認の案1を反映し、01-requirements直下はREADMEだけにした。要求整理は01-needs、要件一覧と機能・非機能要件は02-definition、未決定事項は03-open-questionsへ移動した。初期MVPの成功条件は07-decisionsの出典資料へ移した。

要件ID・受入条件は変更せず、移動先の相対リンクと外部からの参照を更新した。要件関連リンク100件の欠落0、要件13件の一覧・検証対応・適用状況での保持、各要件フォルダのREADMEを確認した。旧functional／non-functionalの空フォルダは削除したが、本文は新配置に保持している。

今回は要求・要件の配置を検証した。参考資料のAPPENDIXへの別途移動に伴う既存リンク欠落21件は今回の対象外とし、上記の要件関連リンク確認や先の全体再編時の検証結果と区別する。アプリ実行・日次Agent実行は行っていない。

独立担当 `review_requirements_structure` が新配置、読む順、リンク、要件から検証・状態への整合を確認し、Critical／Important／Minorとも0件。移動前の要件資料のスナップショットがないため、本文の完全一致は独立には証明していない。今回の編集は移動・参照更新・分類の説明に限定した。

## main(PR #33)の取り込み

2026-10-11、文書再編の作業中にmainへマージされたPR #33(未使用コード削除・CLI共通化・設計書とSkillの整理)を取り込んだ。PR #33は旧 `docs/specs/` を更新・一部削除し、未実装の構想を `docs/future-works.md` に集めていた。ユーザーの判断により、文書は本再編の構成(07の変更設計・06の計画)を維持し、PR #33の内容を次のように反映した。

- 旧specs 01〜08へのPR #33の変更は、本表の移動先の該当ページへ反映した。旧 `docs/specs/` は残さない。
- `docs/future-works.md` は [将来対応](future-works.md) として06へ移した。AGENTS.mdの将来対応のルールも移動先に合わせた。
- PR #33で削除されたSkill(`ai-radar` / `trend-analysis` / `report-generation`)と品質v2の移行状況のページを削除した。CLIに未結線だった品質v2モジュールの削除に合わせ、要件・検証・計画・変更設計の「未接続」の記述を「未実装(削除済み)」に改め、[既知課題](known-gaps.md)を書き直した。
- `skills/` はPR #33の内容を正とし、設計書へのリンクだけを本再編の構成に合わせた。
