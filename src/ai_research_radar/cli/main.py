from __future__ import annotations

import argparse
import sys

from ai_research_radar.cli.commands import (
    add_source_overview,
    add_summary,
    collect,
    daily,
    normalize,
    report,
    save_proposals,
    score,
    select_hot,
)
from ai_research_radar.storage.run_state import RunStateError

_COMMANDS = (
    daily,
    collect,
    normalize,
    score,
    select_hot,
    save_proposals,
    add_summary,
    add_source_overview,
    report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ai-radar")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in _COMMANDS:
        command.add_subparser(subparsers)

    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code)
    try:
        return args.func(args)
    except RunStateError as exc:
        # Nothing can be recorded in a broken run_state.json, so the error only goes to stderr.
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
