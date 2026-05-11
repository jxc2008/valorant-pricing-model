---
phase: 04-quoting-layer
plan: "04"
subsystem: quoting
tags: [mode-selector, trading-mode, idle, post-plant, directional, mm-between-round, vega-post-plant, dec-001-v2, dec-018-v2, pitfall-3]

# Dependency graph
requires:
  - phase: 04-00-test-infrastructure
    provides: RED-stub tests at tests/quoting/test_mode_selector.py + TAKE_THRESHOLD + MM_MIN_EDGE constants + EXPECTED_NAMES allow-list scaffold
  - phase: 04-01-kalshi-order-manager
    provides: MarketQuote (frozen+slots) + make_quote helper consumed by trading_mode rule 4 and rule 5
  - phase: 04-03-kill-switches
    provides: KillSwitchAggregator.any_tripped()[0] boolean consumed by trading_mode rule 1
  - phase: 03-02-round-conclusion-v2
    provides: RoundConclusionLookup.post_plant_p(att, def, time_bucket, side, map) consumed by compute_vega_post_plant
  - phase: 01-04-live-theo
    provides: TheoOutput shape (theo_series, theo_map, vega, confidence) + LiveTheoEngine bundle pattern (compute_vega_post_plant is a sibling top-level function)
provides:
  - src/quoting/mode_selector.py — pure-function trading_mode + TradingMode Literal type + _is_mid_round helper
  - src/pricing/live_theo.compute_vega_post_plant — DEC-018 v2 second-arm post-plant vega formula
  - Atomic deletion of VEGA_DIRECTIONAL_THRESHOLD across src/config/constants.py + tests/config/test_constants.py
affects: [04-05-mm-between-round, 04-06-directional-taker, 04-07-post-plant-quoter, 04-08-order-lifecycle-e2e]

# Tech tracking
tech-stack:
  added: []  # No new deps; uses stdlib typing.Literal + existing math
  patterns:
    - "Sequence of `if ... return ...` statements for mode-selector rules — literal source-code order IS the priority (RESEARCH Pitfall 3). NO match/dict dispatch — grep-discoverable, single-edit reorderable, tie-break by source order alone."
    - "Pure function over (state, theo, market, vegas, ks_active) — caller passes kill_switch_active as bool so mode_selector doesn't need to know how kill switches are evaluated. Mirrors the kill-switch predicate layering from plan 04-03."
    - "Atomic VEGA_DIRECTIONAL_THRESHOLD deletion across src/config + tests/config in the same commit — same-commit Rule-3 prophylactic carry-forward from Phase 03 D-08 (avoids CI red between split commits)."
    - "Reserved-arg pattern (`del vega_between, vega_post_plant`) — selector signature carries arguments that downstream quoters consume, even though the selector itself doesn't route on them. Keeps the call surface stable when 04-05/06/07 wire in the consumers."
    - "compute_vega_post_plant as a top-level sibling function of LiveTheoEngine (not a method) — mirrors _compute_vega from Phase 1 and keeps the post-plant arm callable without instantiating an engine."
    - "Three-outcome variance with equal 1/3 weights at Phase 04 — explicit TODO(phase-5-calibrate) marker in docstring. The SHAPE matters more than EXACT probabilities at this stage; quote-width sizing consumes the variance."
    - "Defensive None-guards in compute_vega_post_plant mirror Phase 03 D-05 between-round-fn semantics — sparse cells / missing post-plant fields return 0.0 (sentinel), not raise."

key-files:
  created:
    - src/quoting/mode_selector.py
    - tests/pricing/test_vega_post_plant.py
  modified:
    - src/config/constants.py
    - tests/config/test_constants.py
    - src/quoting/__init__.py
    - src/pricing/live_theo.py
    - tests/quoting/test_mode_selector.py

key-decisions:
  - "Six rules implemented as literal `if ... return ...` sequence — source-code order IS priority. DIRECTIONAL_TAKE (rule 4) beats MM_BETWEEN_ROUND (rule 5) on tie because rule 4 is written first. Verified by test_tie_directional_dominates_mm (RESEARCH Pitfall 3 mitigation)."
  - "trading_mode is pure — same inputs always produce same output. No I/O, no hidden state, no class members. Caller passes kill_switch_active as explicit bool. Verified by test_pure_function_no_hidden_state running 10x and asserting identity across results."
  - "vega_between and vega_post_plant args are RESERVED — selector doesn't currently route on them (DEC-018 v2 routes on |theo - mid| / spread, not vega magnitude). They're in the signature so plans 04-05 (MM consumes vega_between) and 04-07 (post-plant quoter consumes vega_post_plant) get a stable call surface. `del` statement makes the unused-argument intent explicit to mypy and grep."
  - "VEGA_DIRECTIONAL_THRESHOLD deletion is ATOMIC across src/config/constants.py + tests/config/test_constants.py (EXPECTED_NAMES + EXPECTED_TYPES + value-invariant test) in a single commit. Phase 03 D-08 same-commit Rule-3 prophylactic carry-forward — splitting would leave CI red between commits. Documentary docstring references in mode_selector.py + constants.py TAKE_THRESHOLD docstring are intentional historical context (no constant declaration; not importable)."
  - "compute_vega_post_plant ships at module bottom (Section 10) of src/pricing/live_theo.py as a TOP-LEVEL function (NOT a method on LiveTheoEngine). Mirrors the existing _compute_vega between-round shape (Section 8) and the module's pattern of top-level functions wrapped by the engine bundle. Phase 4 quoters call it directly via `compute_vega_post_plant(state, lookup)` without instantiating an engine."
  - "Three-outcome equal-weight variance (1/3 each: kill, defuse, time-out) is the Phase 04 simplification. PRD §9.5 / DEC-018 v2 marks the formula TBD; RESEARCH §'Open Questions' #2 recommends 'between-round vega shape, but over post-plant outcomes' as the starting point. Phase 5 calibrates empirical frequencies + transition functions against logged post-plant theo updates. TODO marker in docstring."
  - "Defensive None-guards in compute_vega_post_plant return 0.0 (NOT raise) on bomb_planted=False OR any of attackers_alive/defenders_alive/time_left_s being None. Mirrors Phase 03 D-05 between-round-fn semantics. The mode-selector reads vega_post_plant in IDLE / between-round branches and would otherwise mis-route on a crash from malformed state. Same defensive pattern as _live_theo_impl's between-round fallback when bomb_planted=True with missing post-plant fields."
  - "Inline `_make_state` helper in tests/pricing/test_vega_post_plant.py (instead of make_match_state fixture from tests/ingestion/conftest.py) — tests/pricing/ has NO conftest, and importing fixtures across packages is brittle. Pattern matches the existing tests/pricing/test_live_theo_dispatch.py which also rolls its own _make_state for similar isolation reasons."

patterns-established:
  - "Mode-selector + pure-function + reserved-arg-stable-signature layering — selector takes a complete (state, theo, market, vegas, ks_active) tuple; rules 1-6 read only the subset they need; reserved args document forward contracts to downstream quoters without coupling the selector to their internals."
  - "Same-commit atomic constant deletion — when a constant is removed, the constant declaration + allow-list extension + value-invariant tests + any other test surface ALL land in one commit. Splitting across commits leaves CI red between them; the failure mode is documented in Phase 03 D-08 prophylactic + repeats across Phase 04 plans 04-00 and 04-04."
  - "Reserved-arg `del` pattern for unused but contract-stable function parameters — keeps mypy --strict + ruff clean while documenting the forward contract to downstream consumers."

requirements-completed: [REQ-mode-selector, REQ-vega-output]

# Metrics
duration: 6min
completed: 2026-05-11
---

# Phase 04 Plan 04: Mode-Selector + Post-Plant Vega Summary

**Pure-function `trading_mode(state, theo, market, vegas, ks_active) -> TradingMode` with six rules in declared source-code order (Pitfall 3 mitigation: literal order IS the priority — DIRECTIONAL beats MM on tie). Atomic deletion of v1 `VEGA_DIRECTIONAL_THRESHOLD` across src/config + tests/config in a single commit (Phase 03 D-08 same-commit Rule-3 prophylactic carry-forward). `compute_vega_post_plant(state, lookup)` ships as the DEC-018 v2 second-arm formula at the bottom of src/pricing/live_theo.py — three-outcome equal-weight variance over {kill, defuse, time-out}, mirroring the Phase 1 between-round vega shape with explicit Phase 5 calibration TODO. 15 GREEN tests (8 mode-selector + 7 vega-post-plant) replace 7 RED stubs; +13 net GREEN, -7 xfailed; 0 regressions.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-05-11T20:16:10Z
- **Completed:** 2026-05-11T20:22:14Z
- **Tasks:** 2 (each its own atomic commit)
- **Files created:** 2 (`src/quoting/mode_selector.py`, `tests/pricing/test_vega_post_plant.py`)
- **Files modified:** 5 (`src/config/constants.py`, `tests/config/test_constants.py`, `src/quoting/__init__.py`, `src/pricing/live_theo.py`, `tests/quoting/test_mode_selector.py`)
- **Test delta:** 7 mode-selector RED stubs flipped to 8 GREEN + 7 new vega-post-plant GREEN tests added. Full suite: 387 passed / 46 xfailed (was 374/53 in 04-03 baseline; +13 GREEN, -7 xfailed, 0 regressions). Net deletion: 1 value-invariant test for VEGA_DIRECTIONAL_THRESHOLD removed (constant no longer exists).

## Accomplishments

- **src/quoting/mode_selector.py** (~105 lines) ships the canonical mode-selector seam between Phase 03 ingestion and Phase 04 quoting/taking layers:
  - `TradingMode = Literal["MM_BETWEEN_ROUND", "DIRECTIONAL_TAKE", "POST_PLANT_QUOTE", "IDLE"]` — DEC-001 v2 four-state finite alphabet.
  - `trading_mode(state, theo, market, vega_between, vega_post_plant, kill_switch_active) -> TradingMode` — pure function, six rules implemented as a literal sequence of `if ... return ...` statements:
    1. `kill_switch_active` → `IDLE`
    2. `state.bomb_planted` → `POST_PLANT_QUOTE`
    3. `_is_mid_round(state) and not state.bomb_planted` → `IDLE`
    4. `abs(round(theo.theo_series * 100) - market.mid) > TAKE_THRESHOLD` → `DIRECTIONAL_TAKE`
    5. `market.spread > MM_MIN_EDGE` → `MM_BETWEEN_ROUND`
    6. fall-through → `IDLE`
  - `_is_mid_round(state)` returns `state.time_left_s is not None` per Phase 03 D-14 carry-forward.
- **Atomic VEGA_DIRECTIONAL_THRESHOLD deletion** in the SAME commit as the mode-selector implementation (commit `4015006`):
  - `src/config/constants.py`: constant + docstring + section header DELETED. TAKE_THRESHOLD + MM_MIN_EDGE in the Phase 4 section are the v2 replacement (already shipped by plan 04-00).
  - `tests/config/test_constants.py`: removed from EXPECTED_NAMES tuple, EXPECTED_TYPES dict, AND the value-invariant test `test_vega_directional_threshold_in_unit_interval` was deleted (constant no longer exists to check).
  - Documentary references remain in two docstrings (mode_selector.py module docstring documenting "REMOVED (DEC-018 v2)" + constants.py TAKE_THRESHOLD docstring noting "replaces VEGA_DIRECTIONAL_THRESHOLD") as intentional historical context — they are NOT constant declarations and do not satisfy `hasattr(constants, "VEGA_DIRECTIONAL_THRESHOLD")`.
- **src/pricing/live_theo.compute_vega_post_plant** (~75 lines including docstring) ships at module bottom as Section 10:
  - Signature: `compute_vega_post_plant(state: MatchState, lookup: RoundConclusionLookup) -> float`.
  - Formula: `var = sum_o P(o) * (theo_after_outcome - theo_now)**2` over three outcomes `{kill, defuse, time-out}` with equal 1/3 weights at Phase 04 (Phase 5 calibrates empirical frequencies).
  - Defensive None-guards return 0.0 on `bomb_planted=False` OR any of `attackers_alive`/`defenders_alive`/`time_left_s` being None (mirrors Phase 03 D-05 between-round-fn semantics).
  - `time_bucket = int(state.time_left_s // TIME_BUCKET_WIDTH_S)` uses the existing constants import — no new import needed beyond what `_live_theo_impl` already pulls.
- **src/quoting/__init__.py** now re-exports `TradingMode` + `trading_mode` alongside the existing Plan 04-01/02/03 surface; `from src.quoting import trading_mode, TradingMode` resolves cleanly.
- **8 GREEN mode-selector tests** (was 7 RED stubs) cover all 6 rules + tie-break + pure-function determinism:
  - `test_rule_1_kill_switch_dominates_bomb_planted` — kill switch active overrides even bomb-planted state.
  - `test_rule_2_bomb_planted_returns_post_plant_quote` — bomb planted without kill switch → POST_PLANT_QUOTE.
  - `test_rule_3_mid_round_not_planted_returns_idle` — mid-round timer running but no bomb plant → IDLE (overrides theo=0.99 vs mid=50 which would otherwise trigger DIRECTIONAL).
  - `test_rule_4_take_threshold_returns_directional` — theo=50¢ vs mid=42¢ (|diff|=8 > 5) → DIRECTIONAL_TAKE.
  - `test_rule_5_mm_min_edge_returns_mm_between_round` — spread=8 > 4 with no take edge → MM_BETWEEN_ROUND.
  - `test_rule_6_fall_through_returns_idle` — neither rule 4 nor rule 5 fires → IDLE.
  - `test_tie_directional_dominates_mm` — both rule 4 AND rule 5 conditions hold → DIRECTIONAL_TAKE wins (declared-order tie-break per RESEARCH Pitfall 3).
  - `test_pure_function_no_hidden_state` — 10 calls with identical inputs return identical outputs.
- **7 GREEN compute_vega_post_plant tests** in tests/pricing/test_vega_post_plant.py:
  - 4 defensive None-guard tests (bomb_planted=False, attackers_alive=None, defenders_alive=None, time_left_s=None each return 0.0).
  - `test_returns_non_negative_for_bomb_planted_state` — variance is non-negative by construction.
  - `test_pure_function` — 5 calls with identical inputs return identical outputs.
  - `test_defenders_dead_low_variance` — defenders dead (def=0) → all three outcomes converge near p_now → variance bounded by 0.05 (effectively zero given the lookup neighborhood).
- `mypy --strict src/quoting/ src/state/ src/pricing/` clean (Phase 1 + Phase 3 + Phase 4 baseline preserved).

## Task Commits

1. **Task 1: ATOMIC delete VEGA_DIRECTIONAL_THRESHOLD + ship src/quoting/mode_selector.py + GREEN test_mode_selector.py** — `4015006` (feat)
2. **Task 2: src/pricing/live_theo.compute_vega_post_plant + GREEN test_vega_post_plant.py** — `14c605a` (feat)

**Plan metadata:** _(this SUMMARY commit, pending)_ (docs)

## Files Created/Modified

### Created (2 files)

- `src/quoting/mode_selector.py` (~105 lines) — pure-function `trading_mode` + `TradingMode` Literal type + `_is_mid_round` helper. Imports `MM_MIN_EDGE` / `TAKE_THRESHOLD` from `src.config.constants` per CRule 12 (no magic numbers); `TheoOutput` from `src.pricing.data`; `MarketQuote` from `src.quoting.market_data`; `MatchState` from `src.state.match_state`. Module docstring documents the v1 `VEGA_DIRECTIONAL_THRESHOLD` REMOVED status, the source-code-order priority contract (RESEARCH Pitfall 3), and the MM/DIRECTIONAL first-class peers framing per PRD §2.1 v2.
- `tests/pricing/test_vega_post_plant.py` (~120 lines) — 7 GREEN tests with inline `_make_state` helper. Loads the calibrated lookup from `models/round_conclusion.json` via the existing `RoundConclusionLookup.from_json` (Phase 03 plan 03-07 artifact).

### Modified (5 files)

- `src/config/constants.py` — `VEGA_DIRECTIONAL_THRESHOLD` constant + docstring + "Mode flip" section header DELETED (lines 165-174 from pre-state). Section header gone because the v2 replacement (TAKE_THRESHOLD + MM_MIN_EDGE) already lives in the "Phase 4 — quoting layer thresholds" section (added by plan 04-00). Documentary docstring reference in TAKE_THRESHOLD's docstring ("replaces VEGA_DIRECTIONAL_THRESHOLD") preserved as intentional historical context.
- `tests/config/test_constants.py` — `"VEGA_DIRECTIONAL_THRESHOLD"` removed from EXPECTED_NAMES tuple + EXPECTED_TYPES dict; `test_vega_directional_threshold_in_unit_interval` test function DELETED (constant no longer exists, so the test has nothing to assert against). All 86 remaining tests pass.
- `src/quoting/__init__.py` — adds `TradingMode` + `trading_mode` to the `from src.quoting.mode_selector import ...` block + `__all__` list. 11 names in the public surface now.
- `src/pricing/live_theo.py` — adds Section 10 with the new top-level `compute_vega_post_plant` function (~75 lines including docstring). No new imports; reuses existing `TIME_BUCKET_WIDTH_S` import that was already pulled for the bomb_planted dispatch path in `_live_theo_impl`.
- `tests/quoting/test_mode_selector.py` — 7 RED stubs replaced with 8 GREEN tests. Test file body now contains a `_theo(theo_series)` factory + 8 test functions; the consume-fixture signatures still accept `make_match_state` + `make_market_quote` (the latter signature kept for fixture-discovery uniformity even though the test bodies use `make_quote(yes_bid, yes_ask)` directly).

## Decisions Made

- **Six rules implemented as literal `if ... return ...` sequence — source-code order IS priority** (RESEARCH Pitfall 3). Verified by `test_tie_directional_dominates_mm`: when BOTH rule 4 (theo=0.60 vs mid=45, |diff|=15 > 5) AND rule 5 (spread=10 > 4) conditions hold, the function returns `DIRECTIONAL_TAKE` because rule 4 is written first in the source. DO NOT refactor to match/dict dispatch — Pitfall 3 explicitly warns "Mode flips between MM and DIRECTIONAL on the same `(state, theo, market)` across runs" if the priority isn't grep-discoverable in source order.
- **`trading_mode` is pure** — same inputs always produce same output. No I/O, no hidden state, no class members. Caller passes `kill_switch_active: bool` explicitly (computed via `KillSwitchAggregator.any_tripped(state, theo, market, error_streak)[0]` at the call site) so this module doesn't need to know how kill switches are evaluated. Mirrors plan 04-03's pure-predicate kill-switch layering.
- **`vega_between` and `vega_post_plant` arguments are RESERVED** — selector doesn't currently route on them (DEC-018 v2 routes on `|theo - mid|` / `spread`, not vega magnitude). They're in the signature so downstream consumers (plan 04-05 MM quoter reads `vega_between` for spread sizing per DEC-018 D-10/D-11; plan 04-07 post-plant quoter reads `vega_post_plant` for quote-width sizing) get a stable call surface. The `del vega_between, vega_post_plant` statement in the function body makes the unused-argument intent explicit to mypy and grep (avoids `unused-argument` warnings without suppressing them).
- **VEGA_DIRECTIONAL_THRESHOLD deletion is ATOMIC** across src/config/constants.py + tests/config/test_constants.py (EXPECTED_NAMES + EXPECTED_TYPES + value-invariant test) in commit `4015006`. Phase 03 D-08 same-commit Rule-3 prophylactic carry-forward — splitting would leave CI red between commits (constants.py would have the constant gone but EXPECTED_NAMES would still expect it). Two documentary docstring references remain in src/ (mode_selector.py module docstring documenting "REMOVED (DEC-018 v2)" + constants.py TAKE_THRESHOLD docstring noting "replaces VEGA_DIRECTIONAL_THRESHOLD") as intentional historical context — they're not constant declarations and don't satisfy `hasattr(constants, "VEGA_DIRECTIONAL_THRESHOLD")` (the actual import gate).
- **`compute_vega_post_plant` ships at module bottom (Section 10) of `src/pricing/live_theo.py` as a TOP-LEVEL function** (NOT a method on `LiveTheoEngine`). Mirrors the existing `_compute_vega` between-round function (Section 8) and the module's pattern of top-level functions wrapped by the engine bundle. Phase 4 quoters call it directly via `compute_vega_post_plant(state, lookup)` without instantiating an engine. The cache-clear `finally` in `LiveTheoEngine.__call__` doesn't apply to the post-plant vega computation because the function makes 4 deterministic lookup hits without entering the DP/cache path.
- **Three-outcome equal-weight variance (1/3 each: kill, defuse, time-out)** is the Phase 04 simplification. PRD §9.5 / DEC-018 v2 marks the formula TBD; RESEARCH §"Open Questions" #2 recommends "between-round vega shape, but over post-plant outcomes" as the recommended starting point. Phase 5 calibrates empirical frequencies + transition functions against logged post-plant theo updates by minimizing realized vega-vs-spread tracking error. `TODO(phase-5-calibrate)` marker in docstring; the SHAPE matters more than the EXACT probabilities at this stage (quote-width sizing consumes the variance, not the probabilities directly).
- **Defensive None-guards in `compute_vega_post_plant` return 0.0 (NOT raise)** on `bomb_planted=False` OR any of `attackers_alive`/`defenders_alive`/`time_left_s` being None. Mirrors Phase 03 D-05 between-round-fn semantics — the mode-selector reads `vega_post_plant` in IDLE / between-round branches and would otherwise mis-route on a crash from malformed state. Same defensive pattern as `_live_theo_impl`'s between-round fallback when `bomb_planted=True` with missing post-plant fields.
- **Inline `_make_state` helper in tests/pricing/test_vega_post_plant.py** (instead of `make_match_state` fixture from `tests/ingestion/conftest.py`) — `tests/pricing/` has NO conftest.py, and re-exporting fixtures across packages is brittle (would require either creating `tests/pricing/conftest.py` or adding `pytest_plugins` declarations). Pattern matches the existing `tests/pricing/test_live_theo_dispatch.py` which also rolls its own `_make_state` for the same isolation reasons. The fixture pattern in the original plan body assumed the fixture was visible from `tests/pricing/`; that assumption was incorrect and a one-line `_make_state` helper is the cleaner fix.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Inline `_make_state` helper in tests/pricing/test_vega_post_plant.py instead of `make_match_state` fixture**
- **Found during:** Task 2 (test file creation)
- **Issue:** The plan body's test snippet assumed `make_match_state` was visible from `tests/pricing/`, but the fixture is defined in `tests/ingestion/conftest.py` (re-exported in `tests/quoting/conftest.py`) — `tests/pricing/` has no conftest and no re-export, so the fixture would not be discovered there.
- **Fix:** Wrote an inline `_make_state(*, bomb_planted, attackers_alive, defenders_alive, time_left_s, side_orient)` helper at the top of the test file. Pattern matches the existing `tests/pricing/test_live_theo_dispatch.py::_make_state` helper used for the same isolation reason. Avoids creating a new conftest.py or pytest_plugins declaration just for this one test file.
- **Files modified:** `tests/pricing/test_vega_post_plant.py` (helper defined locally; signature mirrors the fixture's kwarg shape so a future cross-package conftest move is mechanical).
- **Verification:** All 7 GREEN tests pass; pattern matches existing convention.
- **Committed in:** `14c605a` (Task 2 commit — landed atomically with the implementation).

**2. [Rule 1 - Bug] Deleted `test_vega_directional_threshold_in_unit_interval` from tests/config/test_constants.py**
- **Found during:** Task 1 (atomic VEGA_DIRECTIONAL_THRESHOLD deletion)
- **Issue:** The plan body mentioned removing the constant from EXPECTED_NAMES + EXPECTED_TYPES, but did not explicitly call out the value-invariant test `test_vega_directional_threshold_in_unit_interval` which still asserted `0.0 < constants.VEGA_DIRECTIONAL_THRESHOLD <= 0.25`. With the constant deleted, this test would fail at `AttributeError: module has no attribute 'VEGA_DIRECTIONAL_THRESHOLD'`.
- **Fix:** Deleted the test function entirely (the constant no longer exists, so there's nothing to assert against). The atomic deletion contract is preserved — the test surface tracking the constant's existence is removed alongside the constant.
- **Files modified:** `tests/config/test_constants.py`
- **Verification:** All 86 remaining tests pass; the deletion is atomic across constants.py + EXPECTED_NAMES + EXPECTED_TYPES + value-invariant test in a single commit.
- **Committed in:** `4015006` (Task 1 commit — landed atomically with the constant deletion and mode_selector implementation).

**3. [Rule 1 - Bug] `del vega_between, vega_post_plant` to suppress unused-argument warnings without lying about the contract**
- **Found during:** Task 1 (mode_selector.py drafting)
- **Issue:** The plan body's reference implementation had `vega_between` and `vega_post_plant` in the signature but did NOT reference them in the function body. Under ruff + mypy strict, unused arguments would either trigger warnings OR (worse) tempt a future maintainer to delete them from the signature — breaking the forward contract to plans 04-05 (MM consumes vega_between) and 04-07 (post-plant quoter consumes vega_post_plant).
- **Fix:** Added `del vega_between, vega_post_plant  # reserved for downstream quoter consumption` as the first line of the function body. Documents the reservation in code (greppable + survives refactors) without suppressing via `# noqa` or `# type: ignore`. Mirrors the existing pattern in `src/pricing/round_conclusion.py::between_round_p` (`del map_name, round_idx  # reserved for future baselines`).
- **Files modified:** `src/quoting/mode_selector.py`
- **Verification:** `mypy --strict src/quoting/` clean; rule body still reads top-to-bottom in declared order.
- **Committed in:** `4015006` (Task 1 commit).

---

**Total deviations:** 3 auto-fixed (1 Rule 3 - Blocking, 2 Rule 1 - Bug)
**Impact on plan:** All three deviations preserve the plan's intent verbatim. The blocking fix (#1) replaced an unworkable cross-package fixture import with an inline helper matching existing convention. The bug fixes (#2, #3) closed gaps in the plan's atomic-deletion contract and the unused-argument contract that would have surfaced as CI red OR future-maintainer footguns. No scope creep.

## Issues Encountered

None - all 15 GREEN tests passed on the first execution after the 3 auto-fixes above; mypy --strict clean from the first pass; full suite +13 GREEN with 0 regressions.

## Authentication Gates

None - mode_selector + compute_vega_post_plant are pure functions over in-process state; no external service calls.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `from src.quoting import trading_mode, TradingMode` resolves cleanly (Literal type printable as `typing.Literal['MM_BETWEEN_ROUND', 'DIRECTIONAL_TAKE', 'POST_PLANT_QUOTE', 'IDLE']`).
- `from src.pricing.live_theo import compute_vega_post_plant` resolves cleanly.
- Forward link to **plan 04-05 (MM-between-round quoter):** consumes `theo.vega` (= `vega_between` per DEC-018 D-10/D-11) for spread sizing; mode-selector returns `MM_BETWEEN_ROUND` when rule 5 fires. The MM quoter's quote-width formula is `spread = max(MIN_HALF_SPREAD, k * sqrt(vega_between)) + staleness_penalty` per the existing MIN_HALF_SPREAD docstring in constants.py.
- Forward link to **plan 04-06 (directional taker):** consumes the mode-selector return value directly; takes when `trading_mode(...) == "DIRECTIONAL_TAKE"`. The take size comes from `kelly_size(theo, market_yes_ask, bankroll, series_id, current_series_exposure)` via plan 04-02's portfolio Kelly sizer.
- Forward link to **plan 04-07 (post-plant quoter):** consumes `compute_vega_post_plant(state, lookup)` for quote-width sizing in the POST_PLANT_QUOTE branch; mode-selector returns `POST_PLANT_QUOTE` when rule 2 fires. The post-plant quoter has the 100ms bomb-detect → quote-pull p50 budget (PRD §5.4 / RESEARCH Pitfall 6); the pure-function shape of `compute_vega_post_plant` (4 deterministic lookup hits, no DP recursion) keeps the call cost well under that budget.
- Forward link to **plan 04-08 (order lifecycle reconciliation + E2E):** composes the full pipe — Arbiter commits state → LiveTheoEngine computes theo → KillSwitchAggregator.any_tripped() → trading_mode(...) → mode-specific quoter (one of MM_BETWEEN_ROUND / DIRECTIONAL_TAKE / POST_PLANT_QUOTE / IDLE-noop). E2E latency budget < 500ms median per PRD §1; bomb-detect → quote-pull p50 < 200ms (Phase 03's 100ms + Phase 04's 100ms = 200ms total).
- Plan 04-05 (MM-between-round quoter) is next — Wave 4. Pre-existing RED stubs at `tests/quoting/test_mm_between_round.py` cover the per-round quote refresh + spread sizing + post_only=True maker-fee gate.

**Recommended next command:** `/gsd:execute-phase 04` to run plan 04-05.

**Verification command:**
```
python -m uv run pytest tests/quoting/test_mode_selector.py tests/pricing/test_vega_post_plant.py --no-cov
# Expected: 15 passed (8 mode-selector + 7 vega-post-plant; 7 RED stubs flipped, 8 new tests added)

python -m uv run pytest tests/ --no-cov
# Expected: 387 passed, 46 xfailed (was 374/53 in Plan 04-03 baseline; +13 GREEN, -7 xfailed)

python -m uv run mypy --strict src/quoting/ src/state/ src/pricing/
# Expected: Success: no issues found in 16 source files

python -c "from src.quoting import trading_mode, TradingMode; print(TradingMode)"
# Expected: typing.Literal['MM_BETWEEN_ROUND', 'DIRECTIONAL_TAKE', 'POST_PLANT_QUOTE', 'IDLE']

python -c "from src.pricing.live_theo import compute_vega_post_plant; print(compute_vega_post_plant.__name__)"
# Expected: compute_vega_post_plant

rg "VEGA_DIRECTIONAL_THRESHOLD" src/ tests/
# Expected: 1 match in src/quoting/mode_selector.py (module docstring documenting REMOVED status)
#           1 match in src/config/constants.py (TAKE_THRESHOLD docstring noting it replaces the v1 constant)
#           0 matches under tests/ (allow-list + value-invariant test cleanly removed)
```

---
*Phase: 04-quoting-layer*
*Completed: 2026-05-11*

## Self-Check: PASSED

- `src/quoting/mode_selector.py` exists on disk (~105 lines).
- `tests/pricing/test_vega_post_plant.py` exists on disk (~120 lines).
- `.planning/phases/04-quoting-layer/04-04-mode-selector-SUMMARY.md` exists (this file).
- Commit `4015006` (feat(04-04): mode-selector pure function + atomic VEGA_DIRECTIONAL_THRESHOLD deletion) found in `git log --oneline --all`.
- Commit `14c605a` (feat(04-04): compute_vega_post_plant — DEC-018 v2 second-arm vega formula) found in `git log --oneline --all`.
- `from src.quoting import trading_mode, TradingMode` resolves cleanly.
- `from src.pricing.live_theo import compute_vega_post_plant` resolves cleanly.
- `rg "VEGA_DIRECTIONAL_THRESHOLD" src/` returns 2 documentary matches (mode_selector.py module docstring + constants.py TAKE_THRESHOLD docstring); 0 matches under `tests/` — atomic deletion verified.
- `python -m uv run pytest tests/quoting/test_mode_selector.py tests/pricing/test_vega_post_plant.py --no-cov` → 15 passed.
- `python -m uv run pytest tests/ --no-cov` → 387 passed / 46 xfailed (Plan 04-03 baseline 374/53; +13 GREEN, -7 xfailed, 0 regressions).
- `python -m uv run mypy --strict src/quoting/ src/state/ src/pricing/` → Success: no issues found in 16 source files.
