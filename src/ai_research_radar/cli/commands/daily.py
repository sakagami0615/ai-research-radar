from __future__ import annotations

import argparse
from pathlib import Path

from ai_research_radar.cli.commands.common import add_runtime_arguments, data_dir as resolve_data_dir, reports_dir, resolve_period, runtime_config
from ai_research_radar.config.settings import load_scoring_config, load_source_configs, resolve_display_timezone
from ai_research_radar.pipeline.daily import run_daily
from ai_research_radar.sources.public import build_adapters

COMMAND_NAME = "daily"


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(COMMAND_NAME)
    parser.add_argument("--since")
    parser.add_argument("--until")
    parser.add_argument("--sources-config", default="config/sources.yaml")
    parser.add_argument("--scoring-config", default="config/scoring.yaml")
    parser.add_argument("--minimum-score", type=float)
    parser.add_argument("--hot-limit", type=int)
    add_runtime_arguments(parser, reports_dir=True)
    parser.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    scoring = load_scoring_config(Path(args.scoring_config))
    hot_selection = scoring.get("hot_selection", {})
    data_dir = resolve_data_dir(args)
    since, until, use_overlap = resolve_period(args, data_dir)
    result = run_daily(
        adapters=build_adapters(load_source_configs(Path(args.sources_config))),
        since=since,
        until=until,
        output_dir=data_dir,
        report_dir=reports_dir(args),
        hot_limit=args.hot_limit if args.hot_limit is not None else int(hot_selection.get("max_limit", 5)),
        minimum_score=(
            args.minimum_score if args.minimum_score is not None else float(hot_selection.get("minimum_score", 75.0))
        ),
        hot_score_weights=dict(scoring.get("hot_score", {})),
        display_timezone=resolve_display_timezone(runtime_config(args)),
        use_overlap=use_overlap,
    )
    print(result.report_path)
    return 0
