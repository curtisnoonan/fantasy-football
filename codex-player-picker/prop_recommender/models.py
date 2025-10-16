from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class Projection:
    player: str
    team: Optional[str]
    pos: Optional[str]
    stat_category: str
    projected_value: float


@dataclass
class Line:
    player: str
    team: Optional[str]
    pos: Optional[str]
    stat_category: str
    line_value: float
    source: str = "underdog"


@dataclass
class Recommendation:
    player: str
    team: Optional[str]
    pos: Optional[str]
    stat_category: str
    line_value: float
    projection: float
    diff: float
    diff_pct: float
    recommendation: str  # OVER | UNDER
    meta: Optional[Dict[str, Any]] = None

