from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional


def _load_yaml_or_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    # Try YAML first if available
    try:
        import yaml  # type: ignore

        return yaml.safe_load(content) or {}
    except Exception:
        pass
    # Fallback: try JSON
    try:
        return json.loads(content)
    except Exception as e:
        raise RuntimeError(
            f"Failed to parse config file at {path}. Ensure PyYAML is installed or use JSON. Error: {e}"
        )


@dataclass
class RecommenderThresholds:
    min_diff_abs: float = 10.0
    min_diff_pct: float = 0.10
    rule: str = "abs_or_pct"  # abs_only | pct_only | abs_or_pct


@dataclass
class APIConfig:
    enabled: bool = False
    endpoint_url: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    cache_path: str = "data/cache/underdog_lines.json"
    cache_ttl_minutes: int = 60
    offline_lines_path: str = "data/lines_sample.json"


@dataclass
class MatchingConfig:
    name_strategy: str = "case_insensitive"
    team_required: bool = False
    position_required: bool = False


@dataclass
class OutputConfig:
    out_path: str = "out/recommended_picks.csv"
    include_no_bet: bool = False


@dataclass
class ProjectionsColumns:
    player_col: Optional[str] = None
    team_col: Optional[str] = None
    pos_col: Optional[str] = None
    proj_col: Optional[str] = None


@dataclass
class Settings:
    stat_category: str = "rushing_yards"
    stat_position_filter: Optional[list[str]] = None
    recommend: RecommenderThresholds = None  # type: ignore
    api: APIConfig = None  # type: ignore
    matching: MatchingConfig = None  # type: ignore
    output: OutputConfig = None  # type: ignore
    projections_columns: ProjectionsColumns = None  # type: ignore

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Settings":
        recommend = d.get("recommend", {})
        api = d.get("api", {})
        matching = d.get("matching", {})
        output = d.get("output", {})
        return Settings(
            stat_category=d.get("stat_category", "rushing_yards"),
            stat_position_filter=d.get("stat_position_filter"),
            recommend=RecommenderThresholds(
                min_diff_abs=float(recommend.get("min_diff_abs", 10.0)),
                min_diff_pct=float(recommend.get("min_diff_pct", 0.10)),
                rule=str(recommend.get("rule", "abs_or_pct")),
            ),
            api=APIConfig(
                enabled=bool(api.get("enabled", False)),
                endpoint_url=api.get("endpoint_url"),
                headers=api.get("headers"),
                cache_path=api.get("cache_path", "data/cache/underdog_lines.json"),
                cache_ttl_minutes=int(api.get("cache_ttl_minutes", 60)),
                offline_lines_path=api.get("offline_lines_path", "data/lines_sample.json"),
            ),
            matching=MatchingConfig(
                name_strategy=matching.get("name_strategy", "case_insensitive"),
                team_required=bool(matching.get("team_required", False)),
                position_required=bool(matching.get("position_required", False)),
            ),
            output=OutputConfig(
                out_path=output.get("out_path", "out/recommended_picks.csv"),
                include_no_bet=bool(output.get("include_no_bet", False)),
            ),
            projections_columns=ProjectionsColumns(
                player_col=(d.get("projections_columns") or {}).get("player_col"),
                team_col=(d.get("projections_columns") or {}).get("team_col"),
                pos_col=(d.get("projections_columns") or {}).get("pos_col"),
                proj_col=(d.get("projections_columns") or {}).get("proj_col"),
            ),
        )


# Provide sensible defaults via a helper, avoiding mutable dataclass defaults
def default_settings() -> Settings:
    return Settings.from_dict({})


def load_settings(path: str) -> Settings:
    cfg = _load_yaml_or_json(path)
    return Settings.from_dict(cfg)


def ensure_dirs(settings: Settings) -> None:
    # Ensure directories exist for cache and output
    cache_dir = os.path.dirname(settings.api.cache_path)
    out_dir = os.path.dirname(settings.output.out_path)
    for d in {cache_dir, out_dir, "data"}:
        if d and not os.path.exists(d):
            os.makedirs(d, exist_ok=True)
