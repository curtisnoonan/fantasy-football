Prop Pick Recommender (MVP)

A simple Python CLI that recommends player prop picks (over/under) by comparing your personal projections to live (or cached) lines from Underdog Fantasy. Designed for personal use, clarity, and easy extension.

Quick start

- Place your projections in `data/my_projections.csv` (sample included).
- Adjust `config/settings.yaml` (sample included) for the stat category and thresholds.
- Run the CLI:

  - `python -m prop_recommender.cli --config config/settings.yaml --projections data/my_projections.csv`

- Launch the GUI:
  - Double-click `start_prop_recommender_gui.bat` on Windows, or run `python -m prop_recommender.gui`.

Key features

- Uses a local projections file (CSV).
- Fetches Underdog lines or loads from an offline JSON file.
- Caches API responses to avoid frequent requests.
- Safe defaults: skips players with missing or ambiguous data.
- Outputs recommended picks to `out/recommended_picks.csv` and prints a summary.

Config overview (config/settings.yaml)

- `stat_category`: Which stat to target, e.g. `rushing_yards`.
- `recommend.min_diff_abs`: Absolute diff threshold in units (e.g., yards).
- `recommend.min_diff_pct`: Percentage diff threshold (0.10 = 10%).
- `recommend.rule`: How to evaluate thresholds: `abs_or_pct` (default), `abs_only`, or `pct_only`.
- `api.enabled`: If true, try fetching from Underdog; otherwise use `offline_lines_path`.
- `api.offline_lines_path`: Path to a local lines JSON file (sample included).
- `matching`: Name matching behavior (case-insensitive with light normalization).

Input formats

- Projections CSV (sample fields):
  - Player, Team, Pos, ProjYards

- Offline lines JSON (normalized sample):
  - Array of objects with: player_name, team, pos, stat_category, line_value, source

Notes

- If PyYAML isn’t available, the tool will attempt to parse the config as JSON or exit with a helpful message.
- Network access may be disabled; use the offline sample to test end-to-end.

GUI tips

- Use "Load Config" to load JSON/YAML settings, "Save Config" to persist current GUI values back to disk.
- Use "Prepare Folders & Samples" to create folders, copy sample projections/lines to your chosen paths if missing, and save config.
- Click "Run" to compute recommendations; "Save CSV" to export the current table.
- Use endpoint presets in the GUI to prefill a common Underdog Pick'em endpoint.
- Use "Header Preset" to quickly apply a browser-like User-Agent and Accept headers, or switch to minimal/custom.
- Use "Test Fetch" to validate connectivity and see how many lines normalize (all sports vs. your Sport Filter) without writing files.
- Use "Fetch Live Lines" to download and normalize live lines into your chosen `Lines JSON`. Optionally save the raw response for debugging.

Underdog Pick'em API

- Endpoint: `https://api.underdogfantasy.com/beta/v5/over_under_lines` returns current pick’em (higher/lower) prop lines across sports.
- Auth: No API key required for public data. Include basic headers to mimic a browser.
  - Headers example: `{ "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Accept": "application/json" }`
- Filtering NFL: Use the GUI "Sport Filter" (default `NFL`) or CLI `--sport NFL`. The normalizer links over_under_lines -> appearances -> players and filters by players with `sport_id == "NFL"`.
- Rate limiting: Be respectful. Fetch infrequently and use the cached/offline JSON for development.

Example calls

- curl:

  `curl "https://api.underdogfantasy.com/beta/v5/over_under_lines" -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)" -H "Accept: application/json"`

- Python (requests):

  ```python
  import requests

  url = "https://api.underdogfantasy.com/beta/v5/over_under_lines"
  headers = {
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
      "Accept": "application/json",
  }
  resp = requests.get(url, headers=headers, timeout=15)
  data = resp.json()

  # Example NFL filter (v5 shape):
  players = {p["id"]: p for p in data.get("players", []) if p.get("sport_id") == "NFL"}
  apps = {a["id"]: a for a in data.get("appearances", [])}
  lines = []
  for item in data.get("over_under_lines", []):
      app_id = ((item.get("over_under") or {}).get("appearance_stat") or {}).get("appearance_id")
      app = apps.get(app_id)
      if not app or app.get("player_id") not in players:
          continue
      player = players[app["player_id"]]
      stat_label = ((item.get("over_under") or {}).get("appearance_stat") or {}).get("display_stat")
      value = item.get("stat_value")
      lines.append((player.get("full_name") or f"{player.get('first_name','')} {player.get('last_name','')}", stat_label, value))
  ```

Connecting to live Underdog data

- In the GUI, set an endpoint preset (e.g., "Underdog v3 over_under_lines") or paste your endpoint.
- Provide any headers in JSON (example: `{ "User-Agent": "youragent", "Accept": "application/json" }`).
- Click "Fetch Live Lines" to save normalized lines to the `Lines JSON` path; the tool also supports saving the raw JSON for support/normalization tweaks.

Projection column mapping

- If your projections CSV headers differ from the defaults, set them in the GUI under "Projections Column Mapping" or use CLI flags:
  - `--player-col`, `--team-col`, `--pos-col`, `--proj-col`.
