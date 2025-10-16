from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional

from .models import Line


def _now_seconds() -> int:
    return int(time.time())


def _read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)


def _normalize_category(category: str) -> str:
    return category.strip().lower()


def _extract_lines_normalized(data: Any) -> List[Line]:
    # Expect a normalized shape: list of objects
    # { player_name, team, pos, stat_category, line_value, source }
    lines: List[Line] = []
    if isinstance(data, list):
        for item in data:
            try:
                player = str(item.get("player_name", "")).strip()
                if not player:
                    continue
                team = (item.get("team") or None)
                pos = (item.get("pos") or None)
                stat_category = _normalize_category(str(item.get("stat_category", "")))
                if not stat_category:
                    continue
                line_value = float(item.get("line_value"))
                source = str(item.get("source", "underdog"))
                lines.append(
                    Line(
                        player=player,
                        team=team,
                        pos=pos,
                        stat_category=stat_category,
                        line_value=line_value,
                        source=source,
                    )
                )
            except Exception:
                continue
    return lines


def _map_stat_to_category(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    s = str(raw).lower()
    # Heuristics for common Underdog stat labels
    if "rush" in s and "yard" in s:
        return "rushing_yards"
    if "receiv" in s and "yard" in s:
        return "receiving_yards"
    if ("pass" in s or "throw" in s) and "yard" in s:
        return "passing_yards"
    return None


def _join_name(player: Dict[str, Any]) -> Optional[str]:
    if not isinstance(player, dict):
        return None
    # Try common name fields
    for k in ("name", "full_name", "player_name"):
        if player.get(k):
            return str(player[k])
    first = player.get("first_name")
    last = player.get("last_name")
    if first or last:
        return f"{first or ''} {last or ''}".strip()
    return None


def _lookup_by_id(index: Dict[Any, Dict[str, Any]], key: Any) -> Optional[Dict[str, Any]]:
    try:
        return index.get(key)
    except Exception:
        return None


def _index_by(items: Any, key: str) -> Dict[Any, Dict[str, Any]]:
    idx: Dict[Any, Dict[str, Any]] = {}
    if isinstance(items, list):
        for it in items:
            try:
                idx[it.get(key)] = it
            except Exception:
                continue
    return idx


def normalize_payload(data: Any) -> List[Line]:
    # Try already-normalized first
    lines = _extract_lines_normalized(data)
    if lines:
        return lines

    out: List[Line] = []

    # Pattern: top-level dict with list under a known key
    if isinstance(data, dict):
        # Common UD shapes we attempt: 'over_under_lines', possibly with 'players'/'teams'
        ou_list = None
        for key in ("over_under_lines", "over_unders", "ou_lines", "lines"):
            if isinstance(data.get(key), list):
                ou_list = data.get(key)
                break

        players_idx: Dict[Any, Dict[str, Any]] = {}
        teams_idx: Dict[Any, Dict[str, Any]] = {}

        # Try to find included players/teams arrays
        for pk in ("players", "included_players", "player_list"):
            if isinstance(data.get(pk), list):
                players_idx = _index_by(data.get(pk), "id") or _index_by(data.get(pk), "player_id")
                break
        for tk in ("teams", "included_teams", "team_list"):
            if isinstance(data.get(tk), list):
                teams_idx = _index_by(data.get(tk), "id") or _index_by(data.get(tk), "team_id")
                break

        def process_items(items):
            for item in items:
                try:
                    # Try direct fields
                    value = (
                        item.get("line")
                        or item.get("value")
                        or item.get("stat_value")
                        or (item.get("over_under") or {}).get("value")
                    )
                    if value is None:
                        continue
                    line_value = float(value)

                    # Stat label
                    stat_label = (
                        (item.get("over_under") or {}).get("stat_type")
                        or (item.get("over_under") or {}).get("title")
                        or item.get("stat_type")
                        or item.get("category")
                        or item.get("type")
                    )
                    stat_category = _map_stat_to_category(stat_label) or _normalize_category(str(stat_label or ""))

                    # Player info
                    player_obj = item.get("player")
                    player_name = _join_name(player_obj) if player_obj else None
                    team_abbr = None
                    pos = None

                    # If only IDs present, try lookup
                    pid = item.get("player_id") or (item.get("over_under") or {}).get("player_id")
                    if not player_name and pid is not None:
                        p = _lookup_by_id(players_idx, pid)
                        if p:
                            player_name = _join_name(p)
                            # try derive team/pos
                            pos = p.get("position") or p.get("pos")
                            team_abbr = (
                                (p.get("team") or {}).get("abbr")
                                if isinstance(p.get("team"), dict)
                                else p.get("team_abbr") or p.get("team")
                            )

                    # Team lookup via team_id if needed
                    tid = item.get("team_id") or (item.get("over_under") or {}).get("team_id")
                    if not team_abbr and tid is not None:
                        t = _lookup_by_id(teams_idx, tid)
                        if t:
                            team_abbr = t.get("abbr") or t.get("code") or t.get("name")

                    # More direct fields
                    if player_name is None:
                        player_name = item.get("player_name") or item.get("name")
                    if pos is None:
                        pos = item.get("position") or item.get("pos")
                    if team_abbr is None:
                        team_abbr = item.get("team") or item.get("team_abbr")

                    if not player_name or not stat_category:
                        continue

                    out.append(
                        Line(
                            player=player_name,
                            team=team_abbr,
                            pos=pos,
                            stat_category=_normalize_category(stat_category),
                            line_value=line_value,
                            source="underdog",
                        )
                    )
                except Exception:
                    continue
        if isinstance(ou_list, list):
            process_items(ou_list)

        # Some payloads provide groups with lines nested
        for gk in ("over_under_groups", "ou_groups", "groups"):
            groups = data.get(gk)
            if isinstance(groups, list):
                for g in groups:
                    for lk in ("over_under_lines", "lines", "ou_lines"):
                        inner = g.get(lk)
                        if isinstance(inner, list):
                            process_items(inner)
                break
    return out


def lines_to_normalized_json(lines: List[Line]) -> List[Dict[str, Any]]:
    arr: List[Dict[str, Any]] = []
    for ln in lines:
        arr.append(
            {
                "player_name": ln.player,
                "team": ln.team,
                "pos": ln.pos,
                "stat_category": ln.stat_category,
                "line_value": ln.line_value,
                "source": ln.source,
            }
        )
    return arr


def load_lines_offline(path: str) -> List[Line]:
    data = _read_json(path)
    # If it's already normalized list, use it.
    lines = _extract_lines_normalized(data)
    return lines


def fetch_underdog_lines(
    endpoint_url: str,
    headers: Optional[Dict[str, str]] = None,
) -> Any:
    # Network may be restricted. We use urllib from stdlib and let callers handle failures.
    import urllib.request

    req = urllib.request.Request(endpoint_url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=15) as resp:
        payload = resp.read().decode("utf-8")
        return json.loads(payload)


def get_lines(
    *,
    enabled: bool,
    endpoint_url: Optional[str],
    headers: Optional[Dict[str, str]],
    cache_path: str,
    cache_ttl_minutes: int,
    offline_lines_path: str,
) -> List[Line]:
    # Try cache first if exists and fresh
    try:
        if os.path.exists(cache_path):
            stat = os.stat(cache_path)
            age_sec = _now_seconds() - int(stat.st_mtime)
            if age_sec <= cache_ttl_minutes * 60:
                cached = _read_json(cache_path)
                lines = _extract_lines_normalized(cached)
                if lines:
                    return lines
    except Exception:
        pass

    # Try live fetch if enabled
    if enabled and endpoint_url:
        try:
            raw = fetch_underdog_lines(endpoint_url, headers)
            # Normalize vendor-specific shape if needed
            lines = normalize_payload(raw)
            if lines:
                _write_json(cache_path, lines_to_normalized_json(lines))
                return lines
        except Exception:
            # Fall back to offline path
            pass

    # Fallback: offline
    try:
        offline = _read_json(offline_lines_path)
        lines = _extract_lines_normalized(offline)
        return lines
    except Exception:
        return []
