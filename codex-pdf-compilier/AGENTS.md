# Repository Guidelines

This guide aligns contributors on the Fantasy Football Data Manager CLI that exports ESPN league data to CSV.

## Project Structure & Module Organization
- CLI: `fantasy_football_cli.py` (entrypoint and argument parsing).
- Package: `fantasy_football/` (API access, config, exporters, utils).
- Config: `.env` and/or `config.yaml` for `ESPN_S2`, `SWID`, `LEAGUE_ID`, `SEASON`.
- Data & Logs: `data/exports/` for timestamped CSVs; `logs/` for rotating logs.
- Tests: `tests/` mirrors the package; fixtures under `tests/fixtures/`.

## Build, Test, and Development Commands
- Setup: `pip install -r requirements.txt` (use a virtualenv).
- Run CLI: `python fantasy_football_cli.py --mode standings`
- Matchups by week: `python fantasy_football_cli.py --mode matchups --week 3`
- Tests: `pytest -q`
- Lint/format: `ruff check . && black .`

## Coding Style & Naming Conventions
- Python 3.10+, 4-space indentation, UTF-8 files.
- Naming: `snake_case` for modules/functions, `PascalCase` for classes, constants `UPPER_SNAKE`.
- Type hints where practical; docstrings for public functions.
- No prints in library code—use `logging`.

## Testing Guidelines
- Pytest-based; name files `test_*.py` and functions `test_*`.
- Prefer fast, deterministic unit tests; mock `espn_api` calls and use local fixtures.
- Aim for ≥80% coverage on exporters, parsing, and CLI argument handling.
- Example: `pytest --maxfail=1 --cov=fantasy_football`

## Commit & Pull Request Guidelines
- Conventional Commits (e.g., `feat(cli): add matchups week flag`).
- PRs must include: summary, linked issues (`Fixes #123`), sample command + output path, and screenshots or CSV snippet when relevant.
- Keep changes focused; update docs/tests with code.

## Security & Configuration Tips
- Never commit secrets or real exports; keep `.env` and `data/exports/` ignored; provide `.env.example`.
- Validate config before running; redact tokens in logs.
- For schedulers (cron/Task Scheduler), run the CLI with the correct working directory and activated environment.
