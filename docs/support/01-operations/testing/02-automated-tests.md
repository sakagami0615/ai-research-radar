# 02 自動テストの実行

先に [環境準備](01-environment.md) を行い、対象の `src/` が読み込まれることを確認する。以下は対象チェックアウト／worktreeのルートで実行する。

## 全件実行

```bash
PYTHONPATH=src python -m pytest -q
```

## 対象を絞った実行

変更に関係する既存テストを選び、実際のパスを指定する。例としてCLIのテストを実行する場合：

```bash
PYTHONPATH=src python -m pytest -q tests/test_cli.py
```

絞った実行だけを行った場合は対象範囲を記録し、全件成功とは報告しない。

## CLIの確認

worktreeのコードでCLIを確認するときも、インストール済みの `ai-radar` ではなくモジュール経由で実行する。次の例はヘルプ表示だけで、収集や成果物の生成は行わない。

```bash
PYTHONPATH=src python -m ai_research_radar.cli.main --help
```

処理を実行する場合は [CLI契約](../../../spec/03-detailed-design/cli/commands.md) の引数を指定し、環境準備で決めた対象日・入力・出力先を使う。

## 結果確認

終了コードとpytestの集計を確認し、成功・失敗・skipを分けて記録する。収集エラー、未実行、対象コードの不一致は成功扱いにしない。失敗した場合は対象テストとエラーを記録し、修正後の再実行結果を前の結果と区別する。

テスト対象・合格条件は [テスト方針](../../../spec/04-verification/test-strategy.md)、[回帰テスト方針](../../../spec/04-verification/regression-policy.md)、[要件対応表](../../../spec/04-verification/requirements-matrix.md) を参照する。記録項目は [テスト実行ガイド](README.md#結果の扱い) に従う。
