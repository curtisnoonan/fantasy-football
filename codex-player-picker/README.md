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
- Use "Fetch Live Lines" to download and normalize live lines into your chosen `Lines JSON`. Optionally save the raw response for debugging.

Connecting to live Underdog data

- In the GUI, set an endpoint preset (e.g., "Underdog v3 over_under_lines") or paste your endpoint.
- Provide any headers in JSON (example: `{ "User-Agent": "youragent", "Accept": "application/json" }`).
- Click "Fetch Live Lines" to save normalized lines to the `Lines JSON` path; the tool also supports saving the raw JSON for support/normalization tweaks.

Projection column mapping

- If your projections CSV headers differ from the defaults, set them in the GUI under "Projections Column Mapping" or use CLI flags:
  - `--player-col`, `--team-col`, `--pos-col`, `--proj-col`.
