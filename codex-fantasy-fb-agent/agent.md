# Agent: Salary Cap Max-Bid MVP (Personal Tool)

## Goal
Build a **simple, reliable** Python CLI that outputs the **maximum bid** (“max salary I’d pay”) for players on an editable draft list, under a **$200** cap. Prioritize correctness, tests, and transparent logging. No external services. Local, personal use.

## Constraints
- Hard cap: **$200** total budget.
- Must **never** produce a plan that exceeds the remaining cap after $1 is reserved per unfilled roster spot.
- Defensive default: if inputs are incomplete or malformed, produce safe, conservative max bids and clear warnings in logs and CLI output.
- Deterministic (no randomness).

## Inputs
- `data/draft_list.csv` (MVP schema):
  - `Player` (str, required)
  - `Pos` (str, required; e.g., RB, WR, QB, TE, DST, K, FLEX optional)
  - `Tier` (int, optional; default 5 if missing)
  - `Note` (str, optional)
- Optional config in `config/settings.yaml`
  - `total_cap`: defaults to 200
  - `roster_slots`: defaults to {"QB":1,"RB":2,"WR":2,"TE":1,"FLEX":1,"DST":1,"K":1,"BENCH":6}
  - `tier_budget_pct`: map tier->% of **remaining** spend *upper bound* per player (e.g., {1:0.35, 2:0.25, 3:0.15, 4:0.08, 5:0.04})
  - `min_bid`: 1
  - `max_players`: optional guard-rail (defaults from roster)
- The CSV can be edited freely between runs.

## Output
- `out/max_bids.csv` with columns:
  - `Player, Pos, Tier, MaxBid, Reason`
- Console summary of total planned spend, remaining dollars, and validation checks.
- Logs in `logs/app_YYYYMMDD_HHMMSS.log`.
- A running `CHANGELOG.md` appended each iteration.

## Logic (MVP)
1. Reserve $1 for each remaining roster spot, always.
2. For each player row (in CSV order):
   - compute `cap_after_reserve = remaining_budget - $1 * remaining_roster_spots`
   - pick tier (%) from config; default to Tier 5 if missing/out-of-range
   - `candidate = floor(cap_after_reserve * tier_pct)`
   - clamp: `max_bid = max(min_bid, candidate)`
   - never exceed `remaining_budget - (remaining_roster_spots * min_bid)`
   - track position counts vs roster slots (don’t allocate if position is “full” unless FLEX permits)
3. Provide clear `Reason` strings (e.g., “Tier 2 @ 25% remaining, reserved $X for Y spots”).
4. Validation: sums never exceed 200; every `MaxBid >= 1` if you plan to roster the player.

## Quality
- Unit tests for:
  - cap never exceeded
  - reserve-$1 invariant
  - tiers monotonicity (tier1 >= tier2 >= ... is *not* required globally, but candidate should respect pct)
  - position slot accounting & FLEX fallback
  - config overrides
- Type hints, docstrings, black/ruff compliant (MVP: black only).
- Fail-fast on schema errors with friendly messages.

## Project Structure
salary-cap-mvp/
app/
init.py
cli.py
logic.py
config.py
io.py
validators.py
version.py
config/
settings.yaml
data/
draft_list.csv
logs/ # generated at runtime
out/ # generated
tests/
test_logic.py
test_io.py
test_validators.py
CHANGELOG.md
README.md
requirements.txt
pyproject.toml # black


## Iteration Plan
- **Iter 0**: Scaffold, requirements, pyproject, README, CHANGELOG entry.
- **Iter 1**: Core logic (budget math + tier clamp) + tests + logging init.
- **Iter 2**: CSV I/O + validators + CLI `--config` `--in` `--out`.
- **Iter 3**: Config defaults & overrides; sample data & golden tests.
- **Iter 4**: Polishing: helpful messages, summary table, error handling hardening.

## Logging & Changelog
- Every iteration appends to `CHANGELOG.md`.
- Each run writes to `logs/app_YYYYMMDD_HHMMSS.log`.
- Include: config used, counts, final sums, warnings.

## Run
python -m app.cli --in data/draft_list.csv --out out/max_bids.csv --config config/settings.yaml