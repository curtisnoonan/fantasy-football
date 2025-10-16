from __future__ import annotations

"""
Analyze fantasy football player data from CSVs and produce insights.

This CLI reads player performance rows (actual and projected points) and
roster assignments, aggregates metrics per player, identifies waiver/buy-low/
sell-high targets, writes a CSV report, and prints a console summary.

Usage example:
    python analyze_players.py \
        --players data/exports/player_stats_2024_YYYYMMDD.csv \
        --rosters data/exports/rosters_2024_YYYYMMDD.csv \
        --out out/analysis_report.csv
"""

import argparse
import csv
import os
import re
import sys
from dataclasses import dataclass
from statistics import pstdev
from typing import Dict, Iterable, List, Optional, Tuple
from collections import Counter, defaultdict


# ----------------------------- Types & Models ------------------------------


@dataclass
class PlayerGame:
    """Single game (row) for a player.

    Attributes:
        actual: Actual fantasy points scored.
        expected: Projected/expected fantasy points for the game.
        order_key: A monotonically increasing key to preserve chronological order.
    """

    actual: float
    expected: float
    order_key: int


@dataclass
class PlayerMetrics:
    """Aggregated metrics for a player across games."""

    name: str
    team: str  # Fantasy team name or "Free Agent"
    total_actual: float
    total_expected: float
    games: int
    avg_actual: float
    recent_avg: float
    stdev_actual: float
    ratio: float
    delta: float  # total_actual - total_expected
    category: str  # "Waiver" / "Buy-Low" / "Sell-High" / "" (may include multiple, semicolon-separated)
    position: str = ""  # primary position (most common)
    positions_all: str = ""  # all observed positions joined (e.g., "WR/RB")


# ----------------------------- Utilities ----------------------------------


def _file_exists_or_die(path: str, desc: str) -> None:
    """Exit with a friendly error if a required file is missing."""

    if not path or not os.path.exists(path):
        print(f"Error: {desc} not found at '{path}'.", file=sys.stderr)
        sys.exit(2)


def _find_col(row_keys: Iterable[str], candidates: Iterable[str]) -> Optional[str]:
    """Find a column in row_keys matching any candidate name (case-insensitive)."""

    lowered = {k.lower(): k for k in row_keys}
    for c in candidates:
        if c.lower() in lowered:
            return lowered[c.lower()]
    return None


def _to_float(val: object, default: float = 0.0) -> float:
    """Safely convert value to float."""

    if val is None:
        return default
    try:
        s = str(val).strip()
        if s == "" or s.lower() == "none":
            return default
        return float(s)
    except Exception:
        return default


def _to_int(val: object, default: int = 0) -> int:
    try:
        return int(str(val).strip())
    except Exception:
        return default


def _strip_ir_suffix(name: str) -> str:
    """Remove trailing IR annotation from a name, e.g., "Name (IR - 3w)" -> "Name".

    Keeps internal spaces and trims the result.
    """
    if not isinstance(name, str):
        return name
    s = name.strip()
    # Match variants like: (IR), (IR-3w), (IR - 3w), (IR - until Wk 10)
    m = re.match(r"^(.*?)(?:\s*\(IR\s*(?:-\s*[^\)]*)?\))\s*$", s, flags=re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return s


# ----------------------------- Data Loading --------------------------------


def load_rosters(rosters_csv: str) -> Dict[str, str]:
    """Load roster assignments mapping player name -> fantasy team name.

    Expects columns like: player_name, team_name (from project exporters).
    Falls back to common variants if needed.
    """

    ownership: Dict[str, str] = {}
    with open(rosters_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            return ownership
        p_col = _find_col(reader.fieldnames, ["player_name", "player", "name"])
        t_col = _find_col(reader.fieldnames, ["team_name", "team", "fantasy_team"])
        if not p_col or not t_col:
            return ownership
        for row in reader:
            raw_name = (row.get(p_col) or "").strip()
            pname = _strip_ir_suffix(raw_name)
            tname = (row.get(t_col) or "").strip()
            if pname:
                ownership[pname.lower()] = tname or "Free Agent"
    return ownership


def load_player_games(players_csv: str) -> Dict[str, List[PlayerGame]]:
    """Load player performance rows and group them by player name.

    Tries to detect columns:
      - player: player_name | name | player
      - actual points: points | actual | total_points
      - expected points: projected_points | expected_points | expected | projection
      - chronological key: week | date (week preferred, numeric)
    If no chronological column is found, preserves file order.
    """

    games: Dict[str, List[PlayerGame]] = {}
    order_counter = 0

    with open(players_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            return games

        p_col = _find_col(reader.fieldnames, ["player_name", "player", "name"])
        a_col = _find_col(reader.fieldnames, ["points", "actual", "total_points"])  # actual
        e_col = _find_col(reader.fieldnames, [
            "projected_points",
            "expected_points",
            "expected",
            "projection",
        ])
        w_col = _find_col(reader.fieldnames, ["week", "date"])  # optional, for ordering
        bye_col = _find_col(reader.fieldnames, ["bye_week", "byeWeek"])  # optional, to skip byes

        for row in reader:
            name = (row.get(p_col) or "").strip() if p_col else ""
            if not name:
                continue
            # Determine if the row is a bye week for this player
            wk_val = row.get(w_col) if w_col else None
            bye_val = row.get(bye_col) if bye_col else None
            try:
                if wk_val is not None and bye_val is not None and str(wk_val).strip() != "" and str(bye_val).strip() != "":
                    if int(str(wk_val).strip()) == int(str(bye_val).strip()):
                        # Skip bye weeks from aggregates
                        continue
            except Exception:
                pass

            actual = _to_float(row.get(a_col), 0.0) if a_col else 0.0
            expected = _to_float(row.get(e_col), 0.0) if e_col else 0.0

            # Determine order key (prefer numeric week)
            if w_col and row.get(w_col) not in (None, ""):
                wk = row.get(w_col)
                ok = _to_int(wk, order_counter)
            else:
                order_counter += 1
                ok = order_counter

            games.setdefault(name, []).append(PlayerGame(actual=actual, expected=expected, order_key=ok))

    # Sort each player's games by order_key
    for glist in games.values():
        glist.sort(key=lambda g: g.order_key)
    return games


def load_player_positions(players_csv: str) -> Dict[str, List[str]]:
    """Load observed positions per player from the players CSV.

    Returns a dict mapping lower(name) -> list of observed positions (may include duplicates).
    Uses 'position' column if available; falls back to 'lineup_slot' when needed.
    """

    pos_map: Dict[str, List[str]] = defaultdict(list)
    with open(players_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            return {}

        p_col = _find_col(reader.fieldnames, ["player_name", "player", "name"])
        pos_col = _find_col(reader.fieldnames, ["position"])  # player position
        slot_col = _find_col(reader.fieldnames, ["lineup_slot", "slot_position"])  # lineup slot

        for row in reader:
            raw_name = (row.get(p_col) or "").strip() if p_col else ""
            if not raw_name:
                continue
            name = _strip_ir_suffix(raw_name)
            # Prefer explicit player position (single token)
            pos = (row.get(pos_col) or "").strip() if pos_col else ""
            # Clean up any multi-token eligible position strings like 'RB/WR/TE'
            if "/" in pos:
                # pick the first token heuristically (shouldn't occur with export fix)
                pos = pos.split("/")[0].strip()
            if not pos and slot_col:
                slot = (row.get(slot_col) or "").strip().upper()
                if slot in ("QB", "RB", "WR", "TE", "K", "D/ST", "DST"):
                    pos = "D/ST" if slot in ("D/ST", "DST") else slot
                # ignore IR/Bench/Flex for primary position
            if pos:
                pos_map[name.lower()].append(pos)

    return dict(pos_map)


# ----------------------------- Calculations --------------------------------


def compute_metrics(name: str, team: str, glist: List[PlayerGame]) -> PlayerMetrics:
    """Compute aggregated metrics for a single player."""

    actuals = [g.actual for g in glist]
    expecteds = [g.expected for g in glist]
    games = len(glist)
    total_actual = sum(actuals)
    total_expected = sum(expecteds)
    avg_actual = total_actual / games if games else 0.0

    # Recent average: last 3 games or all if fewer
    recent_slice = actuals[-3:] if games >= 3 else actuals
    recent_avg = (sum(recent_slice) / len(recent_slice)) if recent_slice else 0.0

    # Use population standard deviation to be defined for N=1 (returns 0.0)
    stdev_actual = pstdev(actuals) if actuals else 0.0

    # Performance ratio (handle division by zero)
    ratio = (total_actual / total_expected) if total_expected > 0 else 0.0
    delta = total_actual - total_expected

    return PlayerMetrics(
        name=name,
        team=team or "Free Agent",
        position="",
        positions_all="",
        total_actual=total_actual,
        total_expected=total_expected,
        games=games,
        avg_actual=avg_actual,
        recent_avg=recent_avg,
        stdev_actual=stdev_actual,
        ratio=ratio,
        delta=delta,
        category="",
    )


def tag_categories(metrics: List[PlayerMetrics]) -> Tuple[List[PlayerMetrics], Dict[str, List[PlayerMetrics]]]:
    """Determine top categories and annotate category tags on copies of metrics.

    Returns a tuple of (annotated_metrics, categories_dict)
    where categories_dict has keys: 'waiver', 'buy_low', 'sell_high'.
    """

    # Work on copies to avoid mutating input
    data = [PlayerMetrics(**vars(m)) for m in metrics]

    # Waiver: free agents sorted by recent_avg desc
    free_agents = [m for m in data if (m.team.strip() == "" or m.team.strip().lower() == "free agent")]
    waiver_top = sorted(free_agents, key=lambda m: (m.recent_avg, m.avg_actual), reverse=True)[:5]
    for m in waiver_top:
        m.category = ";".join([c for c in [m.category, "Waiver"] if c])

    # Buy-low: rostered with ratio < 1, sort by ratio asc then delta asc
    rostered = [m for m in data if m.team.strip() and m.team.strip().lower() != "free agent"]
    buy_low_pool = [m for m in rostered if m.total_expected > 0 and m.ratio < 1.0]
    buy_low_top = sorted(buy_low_pool, key=lambda m: (m.ratio, m.delta))[:5]
    for m in buy_low_top:
        m.category = ";".join([c for c in [m.category, "Buy-Low"] if c])

    # Sell-high: rostered with ratio > 1, sort by ratio desc then delta desc
    sell_high_pool = [m for m in rostered if m.total_expected > 0 and m.ratio > 1.0]
    sell_high_top = sorted(sell_high_pool, key=lambda m: (m.ratio, m.delta), reverse=True)[:5]
    for m in sell_high_top:
        m.category = ";".join([c for c in [m.category, "Sell-High"] if c])

    cats = {
        "waiver": waiver_top,
        "buy_low": buy_low_top,
        "sell_high": sell_high_top,
    }
    return data, cats


# ----------------------------- Output --------------------------------------


def write_report(out_csv: str, metrics: List[PlayerMetrics]) -> None:
    """Write the aggregated player metrics to a CSV report."""

    out_dir = os.path.dirname(os.path.abspath(out_csv))
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    fieldnames = [
        "player_name",
        "team",
        "position",
        "positions_all",
        "recommendation",
        "games",
        "total_points",
        "expected_points",
        "avg_points",
        "recent_avg",
        "stdev",
        "ratio",
        "delta",
        "category",
    ]

    # Sort report by team then player name for readability
    metrics_sorted = sorted(metrics, key=lambda m: (m.team or "Free Agent", m.name))

    def _recommendation(m: PlayerMetrics) -> str:
        cat = (m.category or "").lower()
        score = 0
        if "waiver" in cat:
            score += 3
        if "buy-low" in cat:
            score += 2
        if "sell-high" in cat:
            score -= 3
        try:
            recent = float(m.recent_avg or 0)
        except Exception:
            recent = 0
        try:
            ratio = float(m.ratio or 0)
        except Exception:
            ratio = 0
        if (m.team or "").strip().lower() == "free agent":
            if recent >= 8:
                score += 1
            elif recent <= 3:
                score -= 1
        if m.total_expected > 0 and ratio < 0.85:
            score += 1
        if m.total_expected > 0 and ratio > 1.2:
            score -= 1
        return "GREEN" if score >= 2 else "RED"

    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for m in metrics_sorted:
            writer.writerow({
                "player_name": m.name,
                "team": m.team or "Free Agent",
                "position": m.position,
                "positions_all": m.positions_all,
                "recommendation": _recommendation(m),
                "games": m.games,
                "total_points": round(m.total_actual, 3),
                "expected_points": round(m.total_expected, 3),
                "avg_points": round(m.avg_actual, 3),
                "recent_avg": round(m.recent_avg, 3),
                "stdev": round(m.stdev_actual, 3),
                "ratio": round(m.ratio, 3) if m.total_expected > 0 else "",
                "delta": round(m.delta, 3),
                "category": m.category,
            })


def print_summary(total_players: int, cats: Dict[str, List[PlayerMetrics]], out_csv: str) -> None:
    """Print console summary of analysis and top categories."""

    print(f"Analyzed players: {total_players}")

    def fmt_ratio(m: PlayerMetrics) -> str:
        pct = (m.ratio * 100.0) if m.total_expected > 0 else 0.0
        return f"{round(m.total_actual, 1)} of {round(m.total_expected, 1)} pts ({round(pct, 1)}%)"

    # Waiver
    waiver = cats.get("waiver", [])
    if waiver:
        print("Top Waiver Targets:")
        for m in waiver:
            print(f"  - {m.name}: recent {round(m.recent_avg, 1)} ppg")
    else:
        print("Top Waiver Targets: (none)")

    # Buy-Low
    buy_low = cats.get("buy_low", [])
    if buy_low:
        print("Top Buy-Low Targets:")
        for m in buy_low:
            print(f"  - {m.name} ({m.team}): {fmt_ratio(m)}")
    else:
        print("Top Buy-Low Targets: (none)")

    # Sell-High
    sell_high = cats.get("sell_high", [])
    if sell_high:
        print("Top Sell-High Targets:")
        for m in sell_high:
            print(f"  - {m.name} ({m.team}): {fmt_ratio(m)}")
    else:
        print("Top Sell-High Targets: (none)")

    if total_players == 0:
        print("Warning: No player data found.")

    print(f"Report written to: {os.path.abspath(out_csv)}")


# ----------------------------- CLI -----------------------------------------


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse CLI arguments for analysis."""

    p = argparse.ArgumentParser(
        description="Analyze fantasy football player data and identify targets.",
    )
    p.add_argument(
        "--players",
        required=True,
        help="Path to players CSV with actual and projected points (e.g., export_player_stats).",
    )
    p.add_argument(
        "--rosters",
        required=True,
        help="Path to rosters CSV mapping players to fantasy teams (e.g., export_rosters).",
    )
    p.add_argument(
        "--out",
        required=True,
        help="Path to output CSV report (will be created).",
    )
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)

    _file_exists_or_die(args.players, "Players CSV")
    _file_exists_or_die(args.rosters, "Rosters CSV")

    # Load data
    ownership = load_rosters(args.rosters)
    games = load_player_games(args.players)
    positions_map = load_player_positions(args.players)

    # Aggregate metrics
    metrics: List[PlayerMetrics] = []
    for name, glist in games.items():
        # Match using stripped name for robustness when CSVs contain IR annotations
        base_name = _strip_ir_suffix(name)
        team = ownership.get(base_name.lower(), "Free Agent")
        m = compute_metrics(name, team, glist)
        # Populate player position fields from observed positions
        pos_list = positions_map.get(base_name.lower(), [])
        if pos_list:
            counts = Counter([p.strip() for p in pos_list if p and p.strip()])
            if counts:
                # primary position = most frequent observed, tie-break by alpha
                m.position = max(counts.items(), key=lambda kv: (kv[1], kv[0]))[0]
                m.positions_all = m.position
        metrics.append(m)

    annotated, cats = tag_categories(metrics)

    # Write report
    write_report(args.out, annotated)

    # Console summary
    print_summary(total_players=len(annotated), cats=cats, out_csv=args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
