# 収集・障害分離の受入

対象: F-01・N-01。受入条件は [収集要件](../../01-requirements/02-definition/functional/collection.md)と [信頼性](../../01-requirements/02-definition/non-functional/reliability.md)を参照。

1. 正常なSourceと失敗するSourceを固定fixtureで用意し、隔離出力先で両経路を実行する。
2. 正常なSourceのデータが残り、失敗Sourceと理由が実行記録に残ることを確認する。
3. 完全失敗を日次レポートのデータ欠落として確認する。
4. 品質改善の診断が接続された時点で、部分取得・件数上限・期間基準・打ち切り不明を確認する。
5. 外部Sourceの到達性は別にsmoke testを行い、実際に確認したSource・日時・結果を残す。

外部取得を行えなければ未検証として記録する。fixtureの成功を外部到達性の証拠にしない。
