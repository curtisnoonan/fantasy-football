from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


def _load_dotenv(path: str = ".env") -> Dict[str, str]:
    values: Dict[str, str] = {}
    if not os.path.exists(path):
        return values
    try:
        # Try python-dotenv if available for robust parsing
        from dotenv import dotenv_values  # type: ignore

        return {k: v for k, v in dotenv_values(path).items() if v is not None}
    except Exception:
        # Fallback: simple KEY=VALUE parsing
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    values[k.strip()] = v.strip().strip('"').strip("'")
    return values


def _load_yaml(path: str = "config.yaml") -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    try:
        import yaml  # type: ignore

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            if not isinstance(data, dict):
                return {}
            return {str(k): v for k, v in data.items()}
    except Exception:
        return {}


@dataclass
class Config:
    league_id: Optional[int] = None
    season: Optional[int] = None
    espn_s2: Optional[str] = None
    swid: Optional[str] = None
    output_dir: str = "data/exports"
    log_dir: str = "logs"
    log_level: str = "INFO"
    extras: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_private(self) -> bool:
        return bool(self.espn_s2 and self.swid)


def load_config(
    config_path: Optional[str] = None,
    overrides: Optional[Dict[str, Any]] = None,
    dotenv_path: Optional[str] = None,
) -> Config:
    # Order of precedence (low -> high): env -> .env -> YAML -> overrides
    merged: Dict[str, Any] = {}

    # Base from environment
    for key in ("LEAGUE_ID", "SEASON", "ESPN_S2", "SWID", "OUTPUT_DIR", "LOG_DIR", "LOG_LEVEL"):
        val = os.environ.get(key)
        if val is not None:
            merged[key] = val

    # .env
    merged.update(_load_dotenv(dotenv_path or ".env"))

    # YAML
    yaml_path = config_path or "config.yaml"
    merged.update(_load_yaml(yaml_path))

    # CLI overrides
    if overrides:
        merged.update({k: v for k, v in overrides.items() if v is not None})

    # Normalize keys to Config fields
    def _pop_any(keys: list[str]) -> Optional[str]:
        for k in keys:
            if k in merged and merged[k] is not None:
                return str(merged.pop(k))
        return None

    league_id_s = _pop_any(["LEAGUE_ID", "league_id"]) or None
    season_s = _pop_any(["SEASON", "season"]) or None
    espn_s2 = _pop_any(["ESPN_S2", "espn_s2"]) or None
    swid = _pop_any(["SWID", "swid"]) or None
    output_dir = _pop_any(["OUTPUT_DIR", "output_dir"]) or "data/exports"
    log_dir = _pop_any(["LOG_DIR", "log_dir"]) or "logs"
    log_level = (_pop_any(["LOG_LEVEL", "log_level"]) or "INFO").upper()

    league_id = int(league_id_s) if league_id_s and league_id_s.isdigit() else None
    season = int(season_s) if season_s and season_s.isdigit() else None

    cfg = Config(
        league_id=league_id,
        season=season,
        espn_s2=espn_s2,
        swid=swid,
        output_dir=output_dir,
        log_dir=log_dir,
        log_level=log_level,
        extras=merged,
    )

    return cfg
