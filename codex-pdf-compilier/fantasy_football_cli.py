from __future__ import annotations

import argparse
import logging
import sys
from typing import Optional

from fantasy_football.config import load_config
from fantasy_football.logging_config import setup_logging
from fantasy_football.espn_client import get_league
from fantasy_football.exporters import (
    export_rosters,
    export_standings,
    export_matchups,
    export_player_stats,
    export_free_agents,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Export ESPN Fantasy Football data (rosters, standings, matchups) to CSV.",
    )
    p.add_argument(
        "--mode",
        choices=["roster", "standings", "matchups", "player-stats", "free-agents", "all"],
        required=True,
        help="What to export",
    )
    p.add_argument("--week", type=int, help="Week number (for matchups/player-stats)")
    p.add_argument("--all-weeks", action="store_true", help="For player-stats: export all weeks up to current")
    p.add_argument("--config", type=str, default="config.yaml", help="Path to config.yaml")
    p.add_argument("--league-id", type=int, help="Override league ID")
    p.add_argument("--season", type=int, help="Override season year")
    p.add_argument("--output-dir", type=str, default=None, help="Output directory for CSVs")
    p.add_argument("--log-dir", type=str, default=None, help="Directory for log files")
    p.add_argument(
        "--log-level",
        type=str,
        default=None,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level",
    )
    return p.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)

    cfg = load_config(
        config_path=args.config,
        overrides={
            "LEAGUE_ID": args.league_id,
            "SEASON": args.season,
            "OUTPUT_DIR": args.output_dir,
            "LOG_DIR": args.log_dir,
            "LOG_LEVEL": args.log_level,
        },
    )

    setup_logging(cfg.log_dir, cfg.log_level)
    log = logging.getLogger("fantasy_football.cli")
    log.debug("Loaded config: %s", cfg)

    # Validate required configuration
    if cfg.league_id is None or cfg.season is None:
        log.error("league_id and season are required. Set in .env or config.yaml or CLI flags.")
        return 2

    try:
        league = get_league(cfg)
    except Exception as e:
        log.exception("Failed to create ESPN league client: %s", e)
        return 3

    try:
        if args.mode in ("roster", "all"):
            path = export_rosters(league, cfg.output_dir, cfg.season)
            log.info("Exported rosters -> %s", path)

        if args.mode in ("standings", "all"):
            path = export_standings(league, cfg.output_dir, cfg.season)
            log.info("Exported standings -> %s", path)

        if args.mode in ("matchups", "all"):
            if args.week is None:
                # Try to infer current week; coerce to int if possible
                cw = getattr(league, "current_week", None)
                try:
                    week = int(cw) if cw is not None else None
                except Exception:
                    week = None
                if week is None:
                    log.error("--week is required for matchups (could not infer current week)")
                    return 4
            else:
                week = args.week
            path = export_matchups(league, cfg.output_dir, cfg.season, week)
            log.info("Exported matchups (week %s) -> %s", week, path)

        if args.mode in ("player-stats", "all"):
            # Default to all weeks up to current unless a specific week is provided
            weeks = [args.week] if args.week is not None else None
            p_path = export_player_stats(league, cfg.output_dir, cfg.season, weeks=weeks)
            if weeks is None:
                log.info("Exported player stats (1..current_week) -> %s", p_path)
            else:
                log.info("Exported player stats (weeks=%s) -> %s", weeks, p_path)

        if args.mode in ("free-agents", "all"):
            fa_week = args.week
            # If not provided and in all mode, try current week to snapshot
            if fa_week is None and args.mode == "all":
                cw = getattr(league, "current_week", None)
                if isinstance(cw, int):
                    fa_week = cw
            fa_path = export_free_agents(league, cfg.output_dir, cfg.season, week=fa_week)
            if fa_week is None:
                log.info("Exported free agents (no week) -> %s", fa_path)
            else:
                log.info("Exported free agents (week %s) -> %s", fa_week, fa_path)
    except Exception as e:
        log.exception("Export failed: %s", e)
        return 5

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
