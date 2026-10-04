from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from ai_research_radar.cli.commands import add_summary as add_summary_command
from ai_research_radar.cli.commands import collect as collect_command
from ai_research_radar.cli.commands import normalize as normalize_command
from ai_research_radar.cli.commands import report as report_command
from ai_research_radar.cli.commands import save_proposals as save_proposals_command
from ai_research_radar.cli.commands import score as score_command
from ai_research_radar.cli.commands import select_hot as select_hot_command
from ai_research_radar.config.settings import (
    load_runtime_config,
    load_scoring_config,
    load_source_configs,
    resolve_display_timezone,
)
from ai_research_radar.pipeline.daily import run_daily
from ai_research_radar.periods import default_period, previous_day_period
from ai_research_radar.sources.public import build_adapters


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ai-radar")
    subparsers = parser.add_subparsers(dest="command", required=True)
    daily = subparsers.add_parser("daily")
    daily.add_argument("--since")
    daily.add_argument("--until")
    daily.add_argument("--data-dir")
    daily.add_argument("--reports-dir")
    daily.add_argument("--sources-config", default="config/sources.yaml")
    daily.add_argument("--scoring-config", default="config/scoring.yaml")
    daily.add_argument("--runtime-config", default="config/runtime.yaml")
    daily.add_argument("--minimum-score", type=float)
    daily.add_argument("--hot-limit", type=int)

    collect_command.add_subparser(subparsers)
    normalize_command.add_subparser(subparsers)
    score_command.add_subparser(subparsers)
    select_hot_command.add_subparser(subparsers)
    save_proposals_command.add_subparser(subparsers)
    add_summary_command.add_subparser(subparsers)
    report_command.add_subparser(subparsers)

    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code)

    if args.command == "daily":
        if args.since is None and args.until is None:
            since, until = default_period()
        else:
            until = args.until or date.today().isoformat()
            since = args.since or previous_day_period(until)
        configs = load_source_configs(Path(args.sources_config))
        scoring = load_scoring_config(Path(args.scoring_config))
        runtime = load_runtime_config(Path(args.runtime_config))
        hot_selection = scoring.get("hot_selection", {})
        output = runtime.get("output", {})
        adapters = build_adapters(configs)
        result = run_daily(
            adapters=adapters,
            since=since,
            until=until,
            output_dir=Path(args.data_dir or output.get("data_dir", "data")),
            report_dir=Path(args.reports_dir or output.get("reports_dir", "reports")),
            hot_limit=(
                args.hot_limit
                if args.hot_limit is not None
                else int(hot_selection.get("max_limit", 5))
            ),
            minimum_score=(
                args.minimum_score
                if args.minimum_score is not None
                else float(hot_selection.get("minimum_score", 75.0))
            ),
            hot_score_weights=dict(scoring.get("hot_score", {})),
            display_timezone=resolve_display_timezone(runtime),
        )
        print(result.report_path)
        return 0
    if args.command == collect_command.COMMAND_NAME:
        return collect_command.run(args)
    if args.command == normalize_command.COMMAND_NAME:
        return normalize_command.run(args)
    if args.command == score_command.COMMAND_NAME:
        return score_command.run(args)
    if args.command == select_hot_command.COMMAND_NAME:
        return select_hot_command.run(args)
    if args.command == save_proposals_command.COMMAND_NAME:
        return save_proposals_command.run(args)
    if args.command == add_summary_command.COMMAND_NAME:
        return add_summary_command.run(args)
    if args.command == report_command.COMMAND_NAME:
        return report_command.run(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
