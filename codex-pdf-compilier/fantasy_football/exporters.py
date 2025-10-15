from __future__ import annotations

import csv
import logging
import os
from datetime import datetime
from typing import Any, Iterable, List, Optional, Tuple

logger = logging.getLogger(__name__)


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _write_csv(path: str, rows: Iterable[dict[str, Any]], fieldnames: list[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    logger.info("Wrote %s", path)


def _resolve_attr(obj: Any, name: str, default: Any = None) -> Any:
    """Get attribute and call it if it's callable.

    espn_api sometimes exposes sequences as either properties or methods
    across versions (e.g., standings vs standings()).
    """
    val = getattr(obj, name, default)
    try:
        return val() if callable(val) else val
    except TypeError:
        return val


def export_rosters(league, output_dir: str, season: int) -> str:
    _ensure_dir(output_dir)
    ts = _timestamp()
    out = os.path.join(output_dir, f"rosters_{season}_{ts}.csv")

    rows = []
    teams = _resolve_attr(league, "teams", [])
    for team in teams or []:
        team_id = getattr(team, "team_id", None)
        team_name = getattr(team, "team_name", None)
        roster = _resolve_attr(team, "roster", [])
        for p in roster or []:
            rows.append(
                {
                    "team_id": team_id,
                    "team_name": team_name,
                    "player_name": getattr(p, "name", None),
                    "position": getattr(p, "position", None),
                    "pro_team": getattr(p, "proTeam", None),
                    "injury_status": getattr(p, "injuryStatus", None),
                }
            )

    _write_csv(
        out,
        rows,
        [
            "team_id",
            "team_name",
            "player_name",
            "position",
            "pro_team",
            "injury_status",
        ],
    )
    return out


def export_standings(league, output_dir: str, season: int) -> str:
    _ensure_dir(output_dir)
    ts = _timestamp()
    out = os.path.join(output_dir, f"standings_{season}_{ts}.csv")

    rows = []
    standings = _resolve_attr(league, "standings", [])
    for rank, team in enumerate(standings or [], start=1):
        wins = getattr(team, "wins", 0) or 0
        losses = getattr(team, "losses", 0) or 0
        ties = getattr(team, "ties", 0) or 0
        gp = wins + losses + ties
        win_pct = (wins + 0.5 * ties) / gp if gp else None
        rows.append(
            {
                "rank": rank,
                "team_id": getattr(team, "team_id", None),
                "team_name": getattr(team, "team_name", None),
                "wins": wins,
                "losses": losses,
                "ties": ties,
                "points_for": _resolve_attr(team, "points_for", None),
                "points_against": _resolve_attr(team, "points_against", None),
                "win_pct": round(win_pct, 3) if win_pct is not None else None,
            }
        )

    _write_csv(
        out,
        rows,
        [
            "rank",
            "team_id",
            "team_name",
            "wins",
            "losses",
            "ties",
            "points_for",
            "points_against",
            "win_pct",
        ],
    )
    return out


def export_matchups(league, output_dir: str, season: int, week: int) -> str:
    _ensure_dir(output_dir)
    ts = _timestamp()
    out = os.path.join(output_dir, f"matchups_week{week}_{season}_{ts}.csv")

    rows = []
    try:
        scoreboard = league.scoreboard(week=week)
    except TypeError:
        # Older espn_api versions might use positional args
        scoreboard = league.scoreboard(week)

    for m in scoreboard:
        home = getattr(m, "home_team", None)
        away = getattr(m, "away_team", None)
        winner = getattr(m, "winner", None)
        rows.append(
            {
                "week": week,
                "home_team": getattr(home, "team_name", None),
                "away_team": getattr(away, "team_name", None),
                "home_score": getattr(m, "home_score", None),
                "away_score": getattr(m, "away_score", None),
                "winner": getattr(winner, "team_name", winner) if winner else None,
            }
        )

    _write_csv(
        out,
        rows,
        ["week", "home_team", "away_team", "home_score", "away_score", "winner"],
    )
    return out


def _call_week_fn(obj: Any, name: str, week: int):
    fn = getattr(obj, name, None)
    if not callable(fn):
        return None
    try:
        return fn(week=week)
    except TypeError:
        return fn(week)


def _get_box_scores(league, week: int):
    # Try common variants across espn_api versions
    for name in ("box_scores", "boxscore", "boxScores"):
        try:
            result = _call_week_fn(league, name, week)
            if result is not None:
                return result
        except Exception:
            continue
    return None


def _get_free_agents(league, week: Optional[int] = None, size: int = 5000):
    fn = getattr(league, "free_agents", None)
    if not callable(fn):
        return None
    # Try several signatures across espn_api versions
    if week is None:
        for call in (
            lambda: fn(size=size),
            lambda: fn(),
        ):
            try:
                return call()
            except TypeError:
                continue
    else:
        for call in (
            lambda: fn(week=week, size=size),
            lambda: fn(week),
            lambda: fn(size=size),  # fallback to current if week not supported
        ):
            try:
                return call()
            except TypeError:
                continue
    return None


def _get(obj: Any, names: List[str], default: Any = None) -> Any:
    for n in names:
        if hasattr(obj, n):
            val = getattr(obj, n)
            try:
                return val() if callable(val) else val
            except TypeError:
                return val
    return default


def export_player_stats(league, output_dir: str, season: int, weeks: Optional[List[int]] = None) -> str:
    """Export player-level fantasy points for specified weeks.

    Uses box scores when available. If `weeks` is None, attempts 1..current_week.
    """
    _ensure_dir(output_dir)
    ts = _timestamp()
    out = os.path.join(output_dir, f"player_stats_{season}_{ts}.csv")

    # Determine weeks
    if weeks is None:
        current_week = _resolve_attr(league, "current_week", None)
        try:
            max_week = int(current_week) if current_week is not None else 1
        except Exception:
            max_week = 1
        weeks = list(range(1, max_week + 1))

    rows: List[dict[str, Any]] = []

    for week in weeks:
        box_scores = _get_box_scores(league, week)
        if not box_scores:
            logger.warning("No box scores available for week %s; skipping", week)
            continue

        for bs in box_scores:
            home_team = _get(bs, ["home_team", "homeTeam"]) or {}
            away_team = _get(bs, ["away_team", "awayTeam"]) or {}
            home_name = _get(home_team, ["team_name", "teamName", "name"]) or None
            away_name = _get(away_team, ["team_name", "teamName", "name"]) or None
            home_lineup = _get(bs, ["home_lineup", "homeLineup"]) or []
            away_lineup = _get(bs, ["away_lineup", "awayLineup"]) or []

            def add_lineup(owner_name: Optional[str], opponent_name: Optional[str], lineup: Iterable[Any]):
                for item in lineup or []:
                    # Try to access a nested player object or direct fields
                    player_obj = _get(item, ["player", "athlete"]) or None
                    player_name = (
                        _get(player_obj, ["name", "full_name", "playerName"]) if player_obj else _get(item, ["player_name", "playerName", "name"])
                    )
                    lineup_slot = _get(item, ["slot_position", "lineup_slot", "position"])  # lineup position
                    position = _get(player_obj, ["position"]) if player_obj else None
                    pro_team = _get(player_obj, ["proTeam", "pro_team", "proTeamAbbrev"]) if player_obj else None
                    injury_status = _get(player_obj, ["injuryStatus", "injury_status"]) if player_obj else None
                    points = _get(item, ["points", "applied_total", "total_points", "appliedTotal"]) or 0
                    proj_points = _get(item, ["projected_points", "projected_total", "projectedTotal"]) or None

                    rows.append(
                        {
                            "week": week,
                            "team_name": owner_name,
                            "opponent": opponent_name,
                            "player_name": player_name,
                            "position": position,
                            "lineup_slot": lineup_slot,
                            "pro_team": pro_team,
                            "injury_status": injury_status,
                            "points": points,
                            "projected_points": proj_points,
                        }
                    )

            add_lineup(home_name, away_name, home_lineup)
            add_lineup(away_name, home_name, away_lineup)

    # If no data, still write empty file with headers
    _write_csv(
        out,
        rows,
        [
            "week",
            "team_name",
            "opponent",
            "player_name",
            "position",
            "lineup_slot",
            "pro_team",
            "injury_status",
            "points",
            "projected_points",
        ],
    )
    return out


def export_free_agents(league, output_dir: str, season: int, week: Optional[int] = None) -> str:
    """Export list of free agents (undrafted/unowned) with basic info.

    If week is provided, retrieves free agents for that week (when supported).
    """
    _ensure_dir(output_dir)
    ts = _timestamp()
    suffix = f"_week{week}" if week is not None else ""
    out = os.path.join(output_dir, f"free_agents{suffix}_{season}_{ts}.csv")

    players = _get_free_agents(league, week=week) or []
    rows: List[dict[str, Any]] = []
    for p in players:
        rows.append(
            {
                "week": week,
                "player_name": _get(p, ["name", "full_name", "playerName"]),
                "position": _get(p, ["position"]),
                "pro_team": _get(p, ["proTeam", "pro_team", "proTeamAbbrev"]),
                "injury_status": _get(p, ["injuryStatus", "injury_status"]),
                "status": "FA",
            }
        )

    _write_csv(
        out,
        rows,
        [
            "week",
            "player_name",
            "position",
            "pro_team",
            "injury_status",
            "status",
        ],
    )
    return out
