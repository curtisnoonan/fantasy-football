from __future__ import annotations

import math
from typing import Dict, Iterable, List, Optional, Tuple

from .models import Line, Projection, Recommendation


def _normalize_name(name: str) -> str:
    # Light name normalization for matching: lowercase, strip punctuation/spaces
    import re

    s = name.lower().strip()
    s = re.sub(r"[\.'`-]", "", s)
    s = re.sub(r"\s+", " ", s)
    # Common suffixes
    for suffix in [" jr", " sr", " ii", " iii", " iv"]:
        if s.endswith(suffix):
            s = s[: -len(suffix)].strip()
    return s


def _normalize_category(category: str) -> str:
    return category.strip().lower()


def index_projections(
    projections: Iterable[Projection],
    *,
    team_required: bool,
    position_required: bool,
) -> Dict[Tuple[str, Optional[str], Optional[str]], Projection]:
    idx: Dict[Tuple[str, Optional[str], Optional[str]], Projection] = {}
    for p in projections:
        key = (
            _normalize_name(p.player),
            p.team.upper() if (team_required and p.team) else None,
            p.pos.upper() if (position_required and p.pos) else None,
        )
        idx[key] = p
    return idx


def find_projection(
    idx: Dict[Tuple[str, Optional[str], Optional[str]], Projection],
    line: Line,
    *,
    team_required: bool,
    position_required: bool,
) -> Optional[Projection]:
    name_key = _normalize_name(line.player)
    team_key = line.team.upper() if (team_required and line.team) else None
    pos_key = line.pos.upper() if (position_required and line.pos) else None
    return idx.get((name_key, team_key, pos_key))


def should_recommend(
    projected: float,
    line_value: float,
    *,
    min_diff_abs: float,
    min_diff_pct: float,
    rule: str = "abs_or_pct",
) -> bool:
    diff = projected - line_value
    abs_ok = abs(diff) >= min_diff_abs
    pct = 0.0 if line_value == 0 else abs(diff) / abs(line_value)
    pct_ok = pct >= min_diff_pct

    if rule == "abs_only":
        return abs_ok
    if rule == "pct_only":
        return pct_ok
    # default: abs_or_pct
    return abs_ok or pct_ok


def make_recommendations(
    *,
    lines: Iterable[Line],
    projections: Iterable[Projection],
    stat_category: str,
    team_required: bool,
    position_required: bool,
    min_diff_abs: float,
    min_diff_pct: float,
    rule: str,
) -> List[Recommendation]:
    stat_category = _normalize_category(stat_category)

    # Only consider lines matching the stat category
    filtered_lines = [ln for ln in lines if _normalize_category(ln.stat_category) == stat_category]
    idx = index_projections(projections, team_required=team_required, position_required=position_required)

    recs: List[Recommendation] = []
    for ln in filtered_lines:
        p = find_projection(idx, ln, team_required=team_required, position_required=position_required)
        if p is None:
            continue
        if _normalize_category(p.stat_category) != stat_category:
            continue

        diff = p.projected_value - ln.line_value
        if not should_recommend(
            projected=p.projected_value,
            line_value=ln.line_value,
            min_diff_abs=min_diff_abs,
            min_diff_pct=min_diff_pct,
            rule=rule,
        ):
            continue

        diff_pct = 0.0 if ln.line_value == 0 else diff / ln.line_value
        recs.append(
            Recommendation(
                player=ln.player,
                team=ln.team or p.team,
                pos=ln.pos or p.pos,
                stat_category=stat_category,
                line_value=ln.line_value,
                projection=p.projected_value,
                diff=diff,
                diff_pct=diff_pct,
                recommendation="OVER" if diff > 0 else "UNDER",
                meta={"source": ln.source},
            )
        )

    return recs

