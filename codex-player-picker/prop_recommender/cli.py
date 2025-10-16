from __future__ import annotations

import argparse
import csv
import sys
import os
from typing import List

from .config import Settings, ensure_dirs, load_settings
from .logging_utils import setup_logger
from .models import Recommendation
from .projections import load_projections_csv
from .recommender import make_recommendations
from .underdog import get_lines


def _default_positions_for_stat(stat_category: str) -> List[str]:
    s = stat_category.strip().lower()
    if s == "rushing_yards":
        return ["RB"]
    if s == "receiving_yards":
        return ["WR", "TE"]
    if s == "passing_yards":
        return ["QB"]
    # Fallback: no filter
    return []


def write_recommendations_csv(path: str, recs: List[Recommendation]) -> None:
    fieldnames = [
        "Player",
        "Team",
        "Pos",
        "StatCategory",
        "Line",
        "MyProjection",
        "Diff",
        "DiffPct",
        "Recommendation",
        "Source",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in recs:
            writer.writerow(
                {
                    "Player": r.player,
                    "Team": r.team or "",
                    "Pos": r.pos or "",
                    "StatCategory": r.stat_category,
                    "Line": f"{r.line_value:.1f}",
                    "MyProjection": f"{r.projection:.1f}",
                    "Diff": f"{r.diff:.1f}",
                    "DiffPct": f"{r.diff_pct:.3f}",
                    "Recommendation": r.recommendation,
                    "Source": (r.meta or {}).get("source", ""),
                }
            )


def parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Prop Pick Recommender (MVP)")
    p.add_argument("--config", default="config/settings.yaml", help="Path to settings.yaml or JSON")
    p.add_argument("--projections", default="data/my_projections.csv", help="Path to projections CSV")
    p.add_argument("--player-col", default=None, help="Column name for player in projections CSV")
    p.add_argument("--team-col", default=None, help="Column name for team in projections CSV")
    p.add_argument("--pos-col", default=None, help="Column name for position in projections CSV")
    p.add_argument("--proj-col", default=None, help="Column name for projected value in projections CSV")
    p.add_argument("--stat", default=None, help="Override stat category (e.g., rushing_yards)")
    p.add_argument("--offline-lines", dest="offline_lines", default=None, help="Override offline lines JSON path")
    p.add_argument("--min-diff-abs", dest="min_diff_abs", type=float, default=None, help="Absolute diff threshold")
    p.add_argument("--min-diff-pct", dest="min_diff_pct", type=float, default=None, help="Percent diff threshold (0.10=10%)")
    p.add_argument("--rule", choices=["abs_only", "pct_only", "abs_or_pct"], default=None, help="Threshold rule")
    p.add_argument("--download-lines", action="store_true", help="Fetch live Underdog lines and save to offline JSON before running")
    p.add_argument("--api-endpoint", default=None, help="Override API endpoint URL for fetching lines")
    p.add_argument("--api-headers", default=None, help="Override API headers as JSON string for fetching lines")
    p.add_argument("--verbose", "-v", action="count", default=0, help="Increase verbosity (-v or -vv)")
    return p.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    ns = parse_args(argv or sys.argv[1:])
    logger = setup_logger(ns.verbose)

    settings: Settings = load_settings(ns.config)
    if ns.stat:
        settings.stat_category = ns.stat
    if ns.min_diff_abs is not None:
        settings.recommend.min_diff_abs = ns.min_diff_abs
    if ns.min_diff_pct is not None:
        settings.recommend.min_diff_pct = ns.min_diff_pct
    if ns.rule is not None:
        settings.recommend.rule = ns.rule
    if ns.offline_lines:
        settings.api.offline_lines_path = ns.offline_lines
    if ns.api_endpoint:
        settings.api.endpoint_url = ns.api_endpoint
        settings.api.enabled = True
    if ns.api_headers:
        import json as _json
        try:
            settings.api.headers = _json.loads(ns.api_headers)
        except Exception:
            settings.api.headers = {}

    ensure_dirs(settings)

    # Determine position filter
    pos_filter = settings.stat_position_filter or _default_positions_for_stat(settings.stat_category)
    if pos_filter:
        logger.info(f"Using position filter for {settings.stat_category}: {pos_filter}")

    # Load projections
    logger.info(f"Loading projections from {ns.projections}")
    loader_kwargs = {}
    if ns.player_col:
        loader_kwargs["player_col"] = ns.player_col
    if ns.team_col:
        loader_kwargs["team_col"] = ns.team_col
    if ns.pos_col:
        loader_kwargs["pos_col"] = ns.pos_col
    if ns.proj_col:
        loader_kwargs["proj_col"] = ns.proj_col

    # Build loader kwargs from CLI flags or config defaults
    if not loader_kwargs and getattr(settings, "projections_columns", None):
        pc = settings.projections_columns
        if pc.player_col:
            loader_kwargs["player_col"] = pc.player_col
        if pc.team_col:
            loader_kwargs["team_col"] = pc.team_col
        if pc.pos_col:
            loader_kwargs["pos_col"] = pc.pos_col
        if pc.proj_col:
            loader_kwargs["proj_col"] = pc.proj_col

    projections = load_projections_csv(
        ns.projections,
        stat_category=settings.stat_category,
        filter_positions=pos_filter,
        **loader_kwargs,
    )
    logger.info(f"Loaded {len(projections)} projections")

    # Optionally fetch and save lines first
    if ns.download_lines and settings.api.endpoint_url:
        try:
            from .underdog import fetch_underdog_lines, normalize_payload, lines_to_normalized_json

            logger.info("Fetching live lines from API...")
            raw = fetch_underdog_lines(settings.api.endpoint_url, settings.api.headers)
            live_lines = normalize_payload(raw)
            if live_lines:
                import json as _json
                outp = settings.api.offline_lines_path
                os.makedirs(os.path.dirname(outp) or ".", exist_ok=True)
                with open(outp, "w", encoding="utf-8") as f:
                    _json.dump(lines_to_normalized_json(live_lines), f, indent=2)
                logger.info(f"Saved {len(live_lines)} lines to {outp}")
            else:
                logger.warning("Fetched data but did not detect any lines after normalization.")
        except Exception as e:
            logger.warning(f"Failed to fetch live lines: {e}")

    # Load lines (API or offline)
    logger.info("Loading lines (Underdog or offline)...")
    lines = get_lines(
        enabled=settings.api.enabled,
        endpoint_url=settings.api.endpoint_url,
        headers=settings.api.headers,
        cache_path=settings.api.cache_path,
        cache_ttl_minutes=settings.api.cache_ttl_minutes,
        offline_lines_path=settings.api.offline_lines_path,
    )
    logger.info(f"Loaded {len(lines)} lines")

    # Compute recommendations
    recs = make_recommendations(
        lines=lines,
        projections=projections,
        stat_category=settings.stat_category,
        team_required=settings.matching.team_required,
        position_required=settings.matching.position_required,
        min_diff_abs=settings.recommend.min_diff_abs,
        min_diff_pct=settings.recommend.min_diff_pct,
        rule=settings.recommend.rule,
    )

    # Write output
    write_recommendations_csv(settings.output.out_path, recs)

    # Console summary
    if not recs:
        logger.info("No strong value edges found - no picks recommended today.")
    else:
        over = sum(1 for r in recs if r.recommendation == "OVER")
        under = sum(1 for r in recs if r.recommendation == "UNDER")
        logger.info(
            f"Found {len(recs)} favorable props ({over} Over, {under} Under). "
            f"See {settings.output.out_path} for details."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
