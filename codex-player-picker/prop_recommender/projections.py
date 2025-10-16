from __future__ import annotations

import csv
from typing import Iterable, List, Optional

from .models import Projection


def _normalize_category(category: str) -> str:
    return category.strip().lower()


def load_projections_csv(
    path: str,
    stat_category: str,
    player_col: str = "Player",
    team_col: str = "Team",
    pos_col: str = "Pos",
    proj_col: str = "ProjYards",
    filter_positions: Optional[Iterable[str]] = None,
) -> List[Projection]:
    results: List[Projection] = []
    stat_category = _normalize_category(stat_category)
    pos_filter = set(p.strip().upper() for p in (filter_positions or []))

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                player = (row.get(player_col) or "").strip()
                if not player:
                    continue
                team = (row.get(team_col) or "").strip() or None
                pos = (row.get(pos_col) or "").strip() or None
                if pos:
                    pos = pos.upper()
                if pos_filter and pos and pos not in pos_filter:
                    continue

                proj_raw = row.get(proj_col)
                if proj_raw is None or str(proj_raw).strip() == "":
                    continue
                projected_value = float(proj_raw)

                results.append(
                    Projection(
                        player=player,
                        team=team,
                        pos=pos,
                        stat_category=stat_category,
                        projected_value=projected_value,
                    )
                )
            except Exception:
                # Skip malformed rows silently by design (safe defaults)
                continue

    return results

