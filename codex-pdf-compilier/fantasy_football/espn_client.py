from __future__ import annotations

import logging
from typing import Optional

from .config import Config

logger = logging.getLogger(__name__)


def get_league(cfg: Config):
    """Create and return an espn_api League instance.

    Note: Requires `espn_api` package installed.
    """
    try:
        from espn_api.football import League  # type: ignore
    except Exception as e:  # pragma: no cover - import path/runtime dependent
        raise RuntimeError(
            "espn_api is required. Install with `pip install espn_api`."
        ) from e

    if not cfg.league_id or not cfg.season:
        raise ValueError("league_id and season are required in configuration")

    kwargs = {
        "league_id": cfg.league_id,
        "year": cfg.season,
    }
    if cfg.espn_s2 and cfg.swid:
        kwargs.update({"espn_s2": cfg.espn_s2, "swid": cfg.swid})
    else:
        logger.warning("Using public league access (ESPN_S2/SWID not provided)")

    league = League(**kwargs)
    return league

