# セットアップ

Python環境とインストール手順は [リポジトリREADME](../../README.md) を参照する。バージョン下限の正本は `pyproject.toml`、プロジェクトの利用方針は [AGENTS.md](../../AGENTS.md) にある。本再編ではパッケージの追加や更新は行わない。

Claude CodeとCodexは [文書入口](../README.md) と共通 `skills/` を参照する。CLIの公開Source設定は [設定契約](../03-detailed-design/cli/configuration.md) を確認する。

worktreeではeditable installの参照先に注意し、CLIとテストを `PYTHONPATH=src` で実行する。Agentによる実機確認時のCLIラッパーとデータ配置はAGENTS.mdの既知注意点に従う。
