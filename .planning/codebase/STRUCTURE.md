# Codebase Structure

**Analysis Date:** 2026-04-27

> **Implementation status:** As of 2026-04-27, every directory under `src/` contains only a `.gitkeep` placeholder. The structure below mirrors the *intended* layout from `CLAUDE.md` "Repo layout" and `roadmap.md` Phase 0.1, with each PRD concern mapped to its target file.

## Directory Layout

```
valorant-pricing-model/
├── CLAUDE.md                       # Critical rules + module layout (read first)
├── prd.md                          # Full design — locked decisions, audit (§12.2)
├── roadmap.md                      # 8 build phases with dependency graph
├── .gitignore                      # Blocks secrets, build artifacts, generated data
├── src/                            # All runtime code (currently .gitkeep only)
│   ├── pricing/                    # DP, Bradley-Terry, round-conclusion, live_theo
│   ├── state/                      # MatchState (single source of truth, versioned)
│   ├── ingestion/                  # OCR, scoreboard polling, text, arbiter
│   ├── quoting/                    # KalshiOrderManager, MM, directional, kill switches
│   ├── sizing/                     # Half-Kelly + cap
│   └── config/                     # constants, thresholds (constants.py)
├── tests/                          # pytest + hypothesis (currently empty)
├── scripts/                        # one-off probes, calibration runs (currently empty)
├── data/                           # Inputs + generated datasets
│   └── half_win_rates.json         # Salvaged input — pre-match per-team/map/side rates
├── models/                         # Generated artifacts (mmap'd at runtime)
├── logs/                           # Per-run JSONL event logs + structured logs
├── reference/                      # READ-ONLY salvaged code from thunderedge/
│   ├── odds_utils.py               # Salvage as-is (175 lines)
│   ├── fair_value.py               # Salvage as-is (226 lines) — fallback_q baseline
│   ├── theo_engine.py              # DP skeleton ONLY — has documented bugs (426 lines)
│   └── market_maker.py             # Kalshi plumbing extraction target (512 lines)
└── .planning/                      # Planning artifacts (this directory)
    └── codebase/
```

## Directory Purposes

**`src/pricing/` (Planned):**
- Purpose: All math. The single canonical pricing path. Must pass `mypy --strict`.
- Contains (planned files):
  - `dp.py` — Generalized BO3 Markov DP with `lru_cache`, mmap'd to `models/dp_table.pkl`
  - `blend.py` — Bradley-Terry round-win blend (`p = a(1-b) / (a(1-b) + (1-a)b)`)
  - `round_types.py` — Pistol + anti-eco probability inputs for rounds 1, 2, 3, 13, 14, 15
  - `round_conclusion.py` — Hierarchical lookup `(num_diff, bomb, side, econ, map)` with Bayesian shrinkage
  - `live_theo.py` — **The single canonical entry point**: `live_theo(state) → TheoOutput`
  - (probable) `vega.py` — variance-of-next-update computation
- Key files: `live_theo.py` is the only public entry point; everything else is internal.

**`src/state/` (Planned):**
- Purpose: Single source of truth for the active match. In-memory + JSONL event log.
- Contains (planned files):
  - `match_state.py` — `MatchState` dataclass, mutators that bump `seq_id`, JSONL writer
- Key files: `match_state.py` is the entire layer.

**`src/ingestion/` (Planned):**
- Purpose: Convert real-world signals into versioned state updates with provenance.
- Contains (planned files):
  - `ocr.py` — OCR/CV pipeline (port `vision_parser.py` from thunderedge): score banner (250ms), kill feed (100ms), bomb icon (500ms), round-end banner (100ms during round-end window)
  - `scoreboard.py` — rib.gg / bo3.gg / vlr.gg HTTP polling (every 5s)
  - `text.py` — Twitter/Discord match-thread streaming filter (~1–3s, soft signal only)
  - `arbiter.py` — Tiered cross-source confirmation per PRD §5.1
- Key files: `arbiter.py` is the chokepoint — every confirmed update flows through it.

**`src/quoting/` (Planned):**
- Purpose: Translate `TheoOutput` + market data into Kalshi orders. Apply mode + kill switches.
- Contains (planned files):
  - `order_manager.py` — `KalshiOrderManager` (extracted from `reference/market_maker.py`): `Quote` dataclass, `_place_quote`, `_cancel_quote`, `cancel_all_orders`, error-streak retry, dry-run honoring
  - `mode.py` — Pure function `trading_mode(state, vega) → Literal['MM', 'DIRECTIONAL']`
  - `mm.py` — MM quoter: `theo ± vega-scaled spread` with staleness penalty
  - `directional.py` — Lift offer / hit bid when `|theo − market| > TAKE_THRESHOLD`
  - `kill_switches.py` — Four always-on predicates over `(state, theo, market, recent_briers)`
- Key files: `order_manager.py` (Kalshi I/O), `kill_switches.py` (safety layer).

**`src/sizing/` (Planned):**
- Purpose: Position-size computation. Half-Kelly with per-market cap.
- Contains (planned files):
  - `kelly.py` — `kelly_size(theo, market_yes_ask, bankroll) → int`
- Key files: `kelly.py` is the entire layer.

**`src/config/` (Planned):**
- Purpose: Single home for every threshold and magic number.
- Contains (planned files):
  - `constants.py` — All values from `CLAUDE.md` lines 67–87 (`SHRINK_PRIOR`, `SIGNAL_SCALE`, `GUN_WIN_RATE`, `KELLY_MULTIPLIER`, `PER_MARKET_CAP_FRAC`, `KILL_*` switches, `VEGA_DIRECTIONAL_THRESHOLD`)
- Key files: `constants.py` is the entire layer. **No magic numbers anywhere else.**

**`tests/`:**
- Purpose: pytest + hypothesis test suite.
- Currently: `.gitkeep` only.
- Target: 80% line coverage on `src/pricing/` (roadmap §5.1).
- Property tests planned for: DP value ∈ [0, 1] for any state; DP value monotonic in `round_p`; `theo_series` consistent with `theo_map[]`; Bradley-Terry blend symmetric.

**`scripts/`:**
- Purpose: One-off probes, calibration runs, pre-compute jobs.
- Currently: `.gitkeep` only.
- Planned scripts:
  - `probe_round_events.py` — Phase 2.1 API scoping (rib.gg / bo3.gg endpoint discovery)
  - `build_dp_table.py` — Phase 1 DP pre-compute → `models/dp_table.pkl`
  - (likely) calibration scripts for round-conclusion cells, kill-switch threshold tuning

**`data/`:**
- Purpose: Inputs + generated datasets. **`.gitignore` blocks `*.json`, `*.csv`, `*.parquet`, `*.db`, `*.sqlite`** with an explicit allow-list for `half_win_rates.json`.
- Currently contains:
  - `half_win_rates.json` (66 KB) — salvaged input from `thunderedge/worktrees/half-win-rate/`. Per-team/map/side win rates. Direct input to the DP.
- Planned additions (gitignored):
  - `round_events` table (Path A from Phase 2) — 500+ historical matches' round events
  - SQLite cache of pulled match data

**`models/`:**
- Purpose: Generated, runtime-loaded artifacts.
- Currently: `.gitkeep` only. **Entire `models/` directory is `.gitignore`d** except `.gitkeep`.
- Planned artifacts:
  - `dp_table.pkl` (~10 MB) — pre-computed BO3 DP, mmap'd at startup
  - `round_conclusion.json` — hierarchical lookup cells

**`logs/`:**
- Purpose: Runtime JSONL event logs (per-match) + structured stdout logs.
- Currently: `.gitkeep` only. **Entire `logs/` directory is `.gitignore`d** except `.gitkeep`.
- Planned content: per-match JSONL of `MatchState` mutations; per-event timestamps for latency instrumentation.

**`reference/` (READ-ONLY):**
- Purpose: Salvageable code from sibling `thunderedge/worktrees/market-maker/`. **Inputs to Phase 1 / Phase 4 work, NOT runtime architecture.**
- Currently contains:
  - `odds_utils.py` (175 lines) — American↔implied prob conversion, vig removal. **Salvage as-is, reuse unchanged.**
  - `fair_value.py` (226 lines) — IID BO3 closed-form `p²(3-2p)`. **Salvage as-is, used as `fallback_q` baseline for no-data states.**
  - `theo_engine.py` (426 lines) — Pre-match Markov DP. **Skeleton only.** Has 7 documented bugs (PRD §12.2): docstring drift, three-entry-point sprawl, silent OT coinflip, arithmetic-mean blend, ignored pistols, side-averaging, hardcoded conviction clips. **Do not import; rewrite into `src/pricing/`.**
  - `market_maker.py` (512 lines) — **Extract Kalshi plumbing only** (`Quote` dataclass, `_place_quote`, `_cancel_quote`, `cancel_all_orders`, error-streak retry, close-time guard, dry-run mode) into `src/quoting/order_manager.py`. Skip the rest (10s poll loop, single quoting mode, pre-veto var mutation are obsolete).
- **Rule:** No runtime imports from `reference/`. Salvage by copying + fixing.

## Key File Locations

**Documentation (read first):**
- `CLAUDE.md` — Critical rules + module layout
- `prd.md` — Full design with locked decisions and audit
- `roadmap.md` — 8 phases with implementation guidance

**Entry Points (Planned):**
- `src/main.py` — `python -m src.main --match <ticker>` (dry-run default)
- `src/main.py` with `--live` flag — only after paper-trade promotion gate (PRD §5.5)
- `scripts/build_dp_table.py` — offline DP pre-compute
- `scripts/probe_round_events.py` — Phase 2.1 API scoping

**Configuration:**
- `src/config/constants.py` (Planned) — every threshold and magic number
- `.env` (gitignored) — Kalshi credentials, non-sensitive config
- `.gitignore` — blocks secrets (`.env`, `*.key`, `*.pem`, `valorant*.txt`), build artifacts, generated data

**Core Logic (all Planned):**
- `src/pricing/live_theo.py` — **THE** canonical pricing entry point
- `src/pricing/dp.py` — generalized BO3 Markov DP
- `src/pricing/blend.py` — Bradley-Terry round-win blend
- `src/pricing/round_types.py` — pistol + anti-eco round modeling
- `src/pricing/round_conclusion.py` — hierarchical mid-round lookup
- `src/state/match_state.py` — `MatchState` (single source of truth)
- `src/quoting/order_manager.py` — `KalshiOrderManager`
- `src/quoting/kill_switches.py` — four always-on predicates
- `src/sizing/kelly.py` — half-Kelly + cap

**Salvaged Inputs (read-only):**
- `reference/odds_utils.py` — reuse as-is
- `reference/fair_value.py` — reuse as-is (`fallback_q` baseline)
- `reference/theo_engine.py` — DP skeleton only, has documented bugs
- `reference/market_maker.py` — extract Kalshi plumbing only
- `data/half_win_rates.json` — pre-match per-team/map/side rates

**Testing (Planned):**
- `tests/pricing/` — unit + property tests on `src/pricing/` (target 80% coverage)
- `tests/state/` — `MatchState` mutator + seq_id monotonicity tests
- `tests/quoting/` — kill-switch predicate tests, mode-flip tests, order reconciliation tests
- `tests/ingestion/` — arbiter tiered-confirmation tests

## Naming Conventions

**Files:**
- `snake_case.py` for Python modules: `live_theo.py`, `match_state.py`, `kill_switches.py`, `order_manager.py`
- One module per concept (CLAUDE.md "Preferences" — one canonical implementation per concept)

**Directories:**
- `snake_case` for Python packages: `src/pricing/`, `src/quoting/`
- Lowercase no-separator for top-level non-package dirs: `data/`, `models/`, `logs/`, `scripts/`, `reference/`, `tests/`

**Constants (per CLAUDE.md lines 67–87):**
- `UPPER_SNAKE_CASE`: `SHRINK_PRIOR`, `GUN_WIN_RATE`, `KELLY_MULTIPLIER`, `PER_MARKET_CAP_FRAC`, `KILL_STALENESS_S`, `VEGA_DIRECTIONAL_THRESHOLD`
- Units suffixed where ambiguous: `_S` for seconds, `_C` for cents, `_FRAC` for fraction-of-bankroll, `_BOUND` for thresholds

**Functions (inferred from roadmap signatures):**
- `snake_case`: `series_value(state, round_p_fn)`, `round_p(a_rate, b_rate)`, `kelly_size(theo, market_yes_ask, bankroll)`, `trading_mode(state, vega)`, `live_theo(state)`
- Private helpers prefixed with `_`: `_markov_map_win` (existing in `reference/`), `_signal_strength`, `_compute_quotes`

**Types / Dataclasses:**
- `PascalCase`: `MatchState`, `BO3State`, `TheoOutput`, `Quote`, `KalshiOrderManager`

**Markets / tickers:**
- Kalshi ticker strings as opaque identifiers, passed as `str`. No special parsing convention required by PRD.

## Where to Add New Code

**New pricing primitive (e.g., new round-type model):**
- Primary code: `src/pricing/<concept>.py`
- Must be type-checked by `mypy --strict`
- All thresholds → `src/config/constants.py`
- Tests: `tests/pricing/test_<concept>.py`
- Wire into `live_theo.py` — do **not** create a parallel pricing entry point

**New ingestion source:**
- Primary code: `src/ingestion/<source>.py`
- Must emit events to the arbiter, not directly to `MatchState`
- Update tiered-confirmation rules in `src/ingestion/arbiter.py` if introducing a new event type
- Tests: `tests/ingestion/test_<source>.py`

**New quoting strategy:**
- Primary code: `src/quoting/<strategy>.py`
- Must consume `TheoOutput` + `MatchState`, never re-derive theo
- Must route orders through `KalshiOrderManager` — do not call Kalshi client directly
- Must respect dry-run flag from CLI entry point
- Tests: `tests/quoting/test_<strategy>.py`

**New kill switch:**
- Append to `src/quoting/kill_switches.py` as a pure predicate over `(state, theo, market, recent_briers)`
- Threshold value → `src/config/constants.py`
- Always-on; no flag to disable (CLAUDE.md rule #9)
- Tests: `tests/quoting/test_kill_switches.py`

**New constant / threshold:**
- Add to `src/config/constants.py` only
- Document the value's source (empirical / TBD-pending-calibration / inherited-from-CLAUDE.md)

**New utility (shared across layers):**
- If used by exactly one layer, place inside that layer (`src/pricing/util.py` etc.)
- If used by ≥2 layers, create `src/util/` (not currently present in CLAUDE.md layout — add only if needed and document the deviation)

**One-off script / calibration job:**
- `scripts/<verb>_<noun>.py`: `scripts/build_dp_table.py`, `scripts/probe_round_events.py`, `scripts/calibrate_brier.py`
- Not part of the runtime; can import from `src/`

**New test:**
- Mirror the source path: `tests/<layer>/test_<module>.py`
- Property tests via `hypothesis` for math invariants (`tests/pricing/`)

**Generated artifact (DP table, calibration output):**
- Write to `models/<artifact>.<ext>`
- Confirm `.gitignore` covers it (currently `models/` is fully gitignored except `.gitkeep`)

**Match-time event log:**
- Write to `logs/<match_id>.jsonl`
- `logs/` is gitignored except `.gitkeep`

## Special Directories

**`reference/`:**
- Purpose: Read-only salvaged code from sibling `thunderedge/` repo
- Generated: No (manually copied during repo bootstrap)
- Committed: Yes (4 files, 1339 lines total)
- **Rule:** No runtime imports. Salvage by copying + fixing into `src/`.

**`models/`:**
- Purpose: Generated runtime artifacts (DP table, lookup cells)
- Generated: Yes (by `scripts/build_dp_table.py` and Phase 2 calibration scripts)
- Committed: No (gitignored except `.gitkeep`)

**`logs/`:**
- Purpose: Per-match JSONL event logs + structured stdout logs
- Generated: Yes (by every live/paper-trading run)
- Committed: No (gitignored except `.gitkeep`)

**`data/`:**
- Purpose: Inputs (committed) + generated datasets (gitignored)
- Generated: Mixed
- Committed: Only `half_win_rates.json` (explicit allow-list in `.gitignore` line 44)

**`.planning/`:**
- Purpose: Planning artifacts including this codebase map
- Generated: Yes (by `/gsd-map-codebase`)
- Committed: Per repo discretion

---

*Structure analysis: 2026-04-27*
