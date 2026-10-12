# 01 テスト環境の準備

## 対象コードとPython環境

1. テスト対象のチェックアウト／worktreeのルートへ移動する。以下のコマンドはすべてそのルートで実行する。
2. [セットアップ](../setup.md) に従いPython環境を用意する。バージョンと依存の正本は [pyproject.toml](../../../../pyproject.toml) にある。
3. `git rev-parse --show-toplevel`、`git rev-parse HEAD`、`git status --short`、`python --version` を確認し、対象の作業ディレクトリ・版・未コミット変更・環境を記録する。
4. 次のコマンドで読み込まれるCLIが、この作業ディレクトリの `src/` 配下にあることを確認する。

```bash
PYTHONPATH=src python -c 'from pathlib import Path; import ai_research_radar.cli.main as cli; target = Path(cli.__file__).resolve(); expected = (Path.cwd() / "src").resolve(); print(target); assert target.is_relative_to(expected), "テスト対象外のコードを読み込んでいます"'
```

この環境ではメインチェックアウトにeditable installされているため、worktreeで通常の `python -m pytest` を実行すると、メイン側のコードを読み込んだまま全件成功するおそれがある。対象確認に失敗した場合は実行を止め、作業ディレクトリ・Python環境・PYTHONPATHを修正する。

## 入力データと出力先

通常の自動テストは [テスト方針](../../../spec/04-verification/test-strategy.md) に従いfixtureを使い、外部ネットワークやメインチェックアウトの実データを前提としない。

Agent経路で直近3日分の集約などを確認する場合は、`data/` がGit管理対象外でworktreeに存在しないことがある。必要な過去日のデータだけをメインチェックアウトから対象worktreeへコピーする。コピー前に両方の絶対パス、対象日、必要なファイル、既存ファイルの有無を確認し、元データは変更しない。上書きが必要な場合は利用者に確認する。

CLI実行を伴う確認では、対象日・入力・外部アクセスの有無・data／reports／logsの出力先を先に定める。日次Skillは相対パスの `data/`・`reports/` などを使うため、対象worktreeの既存成果物を上書きしない状態を準備する。安全な入力・出力先を用意できない場合は、その実行を保留して理由を記録する。

Agentのシェル呼び出しは作業ディレクトリや変数を次の呼び出しへ引き継がない前提とする。各呼び出しで対象ルートと必要な環境変数を指定する。
