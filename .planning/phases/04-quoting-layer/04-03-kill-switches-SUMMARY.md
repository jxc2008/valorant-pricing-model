---
phase: 04-quoting-layer
plan: "03"
subsystem: quoting
tags: [kill-switches, predicate, aggregator, brier, staleness, deviation, api-error, market-invalid, dec-005, pitfall-7]

# Dependency graph
requires:
  - phase: 04-00-test-infrastructure
    provides: RED-stub tests at tests/quoting/test_kill_switches.py + make_match_state fixture re-export + KILL_SWITCH_* constants
  - phase: 04-01-kalshi-order-manager
    provides: MarketQuote (frozen+slots) + make_quote helper + KalshiOrderManager.error_streak counter
provides:
  - src/quoting/kill_switches.py — 5 pure predicates (4 DEC-005 + 1 Pitfall 7) + KillSwitchAggregator owning recent_briers deque
  - kill_switch_staleness / kill_switch_deviation / kill_switch_brier / kill_switch_api_error / kill_switch_market_invalid public surface
affects: [04-04-mode-selector, 04-08-reconciliation-e2e]

# Tech tracking
tech-stack:
  added: []  # No new deps; uses stdlib collections.deque + math.fsum
  patterns:
    - "Predicate-style kill switches over (state, theo, market, recent_briers, error_streak) — each switch is grep-discoverable + independently unit-testable (RESEARCH §'Pattern 3')"
    - "Strict inequality (`> threshold`) for threshold-style switches (staleness / deviation / brier); non-strict (`>= threshold`) for api_error which encodes 'consecutive errors at trip time'"
    - "math.fsum for rolling-Brier mean computation — naive sum of 50 copies of 0.30 yields 0.30000000000000027 (IEEE 754 drift) which would spuriously trip the strict-inequality boundary"
    - "KillSwitchAggregator.any_tripped returns sorted tripped-name list — deterministic logging across Python runs (carry-forward of Phase 03 D-08 set-iteration-non-determinism prophylactic)"
    - "Recent-Brier deque is a public attribute on the aggregator (not a private field) so plan 04-08 reconciliation can `agg.recent_briers.append(score)` directly after round resolution — Pitfall 4 contract: only append when mode != IDLE"
    - "Docstring paraphrase pattern: documents DEC-005 prohibition WITHOUT using the literal grep-guard substring (Phase 03 D-08 carry-forward — the same self-tripping-guard issue would have hit if the docstring used the canonical 'disable_X' phrasing)"

key-files:
  created:
    - src/quoting/kill_switches.py
  modified:
    - src/quoting/__init__.py
    - tests/quoting/test_kill_switches.py

key-decisions:
  - "Pure predicates over class hierarchy — each switch is a `def kill_switch_X(...) -> bool` taking only the inputs it needs; no shared state, no inheritance. Aggregator is the only class and exists solely to own the recent_briers deque (which is the one piece of state needed at the kill-switch layer)."
  - "kill_switch_brier uses math.fsum (Shewchuk pairwise summation) instead of builtin sum. Naive sum on 50 copies of 0.30 accumulates to 0.30000000000000027 under uv/CPython 3.11 — would spuriously trip the strict-inequality boundary contract from CLAUDE.md / PRD §5.4. Discovered via Rule 1 auto-fix during GREEN test run (test_brier_no_trip_at_exact_threshold failed on first execution)."
  - "Aggregator returns SORTED tripped-name list — deterministic for logging / alerting / replay across Python runs. Phase 03 D-08 carry-forward (set-iteration is non-deterministic under CPython 3.11 randomized hashing)."
  - "kill_switch_api_error uses non-strict `>=` (DEC-005 / market_maker.py:73 salvage) — `error_streak == 3` means three consecutive errors, which IS the trip point. All other switches use strict `>` per CLAUDE.md PRD §5.4 wording ('staleness > 5s', '|theo - market| > 20¢', 'rolling Brier > 0.30')."
  - "5th predicate kill_switch_market_invalid ships alongside the 4 DEC-005 switches — RESEARCH Pitfall 7 (WS reconnect leaves MarketQuote.is_valid=False until next full book). Mode-selector rule 1 (plan 04-04) will read this trip and return IDLE during reconnect gaps."
  - "Docstring uses 'per-switch off-switch flag' / 'per-switch bool knob' paraphrase instead of the canonical 'disable_X' phrasing, so the grep guard `rg disable_ src/quoting/kill_switches.py` returns no matches. The plan's success criterion explicitly checks this."

patterns-established:
  - "Pure-predicate + thin-aggregator layering: each kill switch is a function over its inputs, the aggregator is just a `def any_tripped(...) -> tuple[bool, list[str]]` that names which switches tripped"
  - "math.fsum for any rolling-mean comparison against a tight threshold — IEEE 754 accumulation drift will tip the wrong way at exact-equality boundaries"
  - "Grep-guard-safe docstrings — when a CLAUDE.md / DEC rule forbids a specific construct, the docstring documenting the prohibition must paraphrase the forbidden token (same pattern shipped in Phase 03 plan 03-05 for kill_feed / ult_orb)"

requirements-completed: [REQ-kill-switches]

# Metrics
duration: 5min
completed: 2026-05-11
---

# Phase 04 Plan 03: Kill Switches Summary

**Five pure-predicate kill switches (4 DEC-005 + 1 Pitfall 7) + KillSwitchAggregator owning the rolling-Brier deque. Strict inequality boundary semantics verified via 18 unit tests; sorted tripped-name list deterministic across Python runs; math.fsum guards against IEEE 754 drift at the 0.30 Brier boundary.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-05-11T20:02:42Z
- **Completed:** 2026-05-11T20:07:28Z
- **Tasks:** 1 (single atomic commit)
- **Files created:** 1 (`src/quoting/kill_switches.py`)
- **Files modified:** 2 (`src/quoting/__init__.py`, `tests/quoting/test_kill_switches.py`)
- **Test delta:** 10 RED stubs flipped to 18 GREEN (each predicate gets trip + non-trip boundary + 5 aggregator semantics tests). Full suite: 374 passed / 53 xfailed (Plan 04-02 baseline 356 / 63; +18 GREEN, -10 xfailed, 0 regressions).

## Accomplishments

- 5 pure-function kill-switch predicates landed in `src/quoting/kill_switches.py`:
  1. `kill_switch_staleness(state, *, now=None)` — strict `> KILL_SWITCH_STALENESS_S (5.0s)`
  2. `kill_switch_deviation(theo, market)` — strict `> KILL_SWITCH_DEVIATION_C (20¢)`
  3. `kill_switch_brier(recent_briers)` — window-full AND strict `> KILL_SWITCH_BRIER_BOUND (0.30)` using `math.fsum`
  4. `kill_switch_api_error(error_streak, threshold=3)` — non-strict `>= threshold` (salvaged from `reference/market_maker.py:73`)
  5. `kill_switch_market_invalid(market)` — `not market.is_valid` (Pitfall 7 WS reconnect gate)
- `KillSwitchAggregator` owns `recent_briers: deque(maxlen=KILL_SWITCH_BRIER_WINDOW)` for plan 04-08 reconciliation append; `.any_tripped(state, theo, market, error_streak)` returns `(bool, sorted_names: list[str])`.
- Grep guard verified: `rg "disable_" src/quoting/kill_switches.py` returns no matches (DEC-005 absolute — no per-switch off-switch flag in the codebase). Docstring paraphrased to avoid self-tripping the guard (Phase 03 D-08 carry-forward).
- 18 GREEN tests cover trip + non-trip boundary per predicate plus 5 aggregator semantics tests (empty / single-trip / multi-trip-sorted / deque-shape / brier-when-full).
- mypy --strict src/quoting/ clean (6 source files now: kalshi_auth, order_manager, market_data, portfolio, kill_switches, __init__).
- `from src.quoting import KillSwitchAggregator` resolves cleanly; integration smoke verified.

## Task Commits

1. **Task 1: kill switches predicates + aggregator + GREEN tests** — `b47f886` (feat)

**Plan metadata:** _(this SUMMARY commit, pending)_ (docs)

## Files Created/Modified

### Created (1 file)

- `src/quoting/kill_switches.py` — 5 pure predicates (~170 lines including module docstring + per-function docstrings) + KillSwitchAggregator class. Imports KILL_SWITCH_* constants from `src.config.constants` per CRule 12 (no magic numbers); TheoOutput from `src.pricing.data`; MarketQuote from `src.quoting.market_data`; MatchState from `src.state.match_state`.

### Modified (2 files)

- `src/quoting/__init__.py` — now exports `KillSwitchAggregator`, `kill_switch_api_error`, `kill_switch_brier`, `kill_switch_deviation`, `kill_switch_market_invalid`, `kill_switch_staleness` alongside the existing Plan 04-01/02 surface.
- `tests/quoting/test_kill_switches.py` — 10 RED stubs replaced with 18 GREEN tests. Boundary coverage: staleness (5.01s trips, 5.0s doesn't, 4.99s doesn't), deviation (mid=71→21c trips, mid=70→20c doesn't), brier (49 zeros: no trip; 50×0.30: no trip; 50×0.40: trips), api_error (3 trips, 2 doesn't, 10 trips), market_invalid (False trips, True doesn't), aggregator (empty / single staleness / multi-trip sorted / deque shape / brier-accumulated).

## Decisions Made

- **Pure-function predicates over class hierarchy** — each switch takes only the inputs it actually consumes (state for staleness, theo+market for deviation, deque for brier, int for api_error, market for market_invalid). The aggregator is the ONLY class, and it exists solely to own the `recent_briers` deque (the one piece of mutable state at the kill-switch layer; everything else is derived per-call). Mirrors Phase 1's pure-pricing layering.
- **`math.fsum` for the Brier mean** — Rule 1 auto-fix discovered during GREEN test run. Naive `sum([0.30] * 50)` produces `15.000000000000004` (FP accumulation), giving mean `0.30000000000000027` which spuriously trips the strict-inequality boundary. `math.fsum` (Shewchuk pairwise summation) produces the exact rounded result `15.0` → mean `0.30` → `> 0.30` is `False` as the boundary contract requires.
- **Sorted tripped-name list** — Phase 03 D-08 carry-forward (set-iteration-non-determinism under CPython 3.11 randomized hashing). The aggregator returns `(bool, sorted(tripped))` so log lines / alerts / replay traces are stable across Python runs.
- **`kill_switch_api_error` uses non-strict `>=`** while the other three threshold switches use strict `>`. This matches:
  - PRD §5.4 / CLAUDE.md prose ("staleness > 5s", "deviation > 20¢", "rolling Brier > 0.30")
  - The api_error threshold semantic ("trip after this many consecutive errors" — 3 means "the third error trips")
  - `reference/market_maker.py:73` `_MAX_ERRORS_BEFORE_PAUSE = 3` salvage source
- **5th predicate `kill_switch_market_invalid` ships alongside the 4 DEC-005 switches** — not in DEC-005's four-switch baseline but is implied by PRD §5.4's "stop trading when the market data is unreliable" intent. The Pitfall 7 carry-forward from RESEARCH: WS reconnect leaves `MarketQuote.is_valid=False` until the next full book; plan 04-04 mode-selector rule 1 reads this trip and returns IDLE during reconnect gaps.
- **Docstring paraphrase to dodge the grep guard** — first-draft module docstring used the literal phrase "do NOT add a `disable_X: bool` knob" which would self-trip the success-criterion grep `rg "disable_" src/quoting/kill_switches.py`. Rewrote as "per-switch off-switch flag / per-switch bool knob" — same prohibition, no forbidden token. Same pattern shipped in Phase 03 plan 03-05 for `kill_feed` / `ult_orb`.
- **Aggregator's `recent_briers` is a PUBLIC attribute (not a private field)** — plan 04-08 reconciliation needs to `agg.recent_briers.append(score)` directly after each round resolution (when mode != IDLE per Pitfall 4 contract). Private-with-getter/setter would be ceremony for no protection benefit; the contract is documented in the class docstring.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] math.fsum for Brier mean to avoid IEEE 754 drift**
- **Found during:** Task 1 GREEN test run
- **Issue:** `test_brier_no_trip_at_exact_threshold` failed on first execution. Plan contract states `kill_switch_brier(deque of 50 0.30s)` returns `False` (mean=0.30 == 0.30 — boundary, strict inequality). But naive `sum([0.30] * 50) / 50` returns `0.30000000000000027` due to IEEE 754 accumulation drift, which IS `> 0.30` and would trip.
- **Fix:** Replaced `sum(recent_briers)` with `math.fsum(recent_briers)` (Shewchuk pairwise exact summation). `math.fsum([0.30] * 50) == 15.0` exactly → mean `0.30` → `> 0.30` is `False` as the boundary contract requires.
- **Files modified:** `src/quoting/kill_switches.py` (added `import math`; swapped `sum` → `math.fsum`; added implementation-note paragraph in `kill_switch_brier` docstring documenting the rationale)
- **Verification:** All 18 GREEN tests pass; specifically `test_brier_no_trip_at_exact_threshold` now passes.
- **Committed in:** `b47f886` (Task 1 commit — same-commit Rule-1 fix prophylactic carry-forward from Phase 03)

**2. [Rule 1 - Bug] Docstring paraphrase to avoid self-tripping the grep guard**
- **Found during:** Task 1 grep-guard verification (`rg "disable_" src/quoting/`)
- **Issue:** Module docstring first draft used the literal phrase "do NOT add a `disable_X: bool` knob" to document the DEC-005 prohibition. This self-tripped the success-criterion grep `rg "disable_" src/quoting/kill_switches.py` which must return zero matches.
- **Fix:** Paraphrased to "per-switch off-switch flag / per-switch bool knob" — same prohibition documented, no forbidden substring. Identical pattern to Phase 03 D-08 carry-forward (plan 03-05 had to paraphrase the documentation of cut-kill-feed / cut-ult-tracking guards for the same reason).
- **Files modified:** `src/quoting/kill_switches.py` (lines 5-7 of module docstring)
- **Verification:** `rg "disable_" src/quoting/kill_switches.py` returns empty; `rg "disable_X|disable_kill_switch|kill_switch_disable" src/quoting/` returns empty.
- **Committed in:** `b47f886` (Task 1 commit — landed atomically with the implementation)

---

**Total deviations:** 2 auto-fixed (2 Rule 1 - Bug; same-commit prophylactic for both)
**Impact on plan:** Both auto-fixes essential for the strict-inequality + grep-guard success criteria. Plan body otherwise executed exactly as written.

## Issues Encountered

None - all 18 GREEN tests passed after the two Rule-1 fixes above; mypy --strict clean from the first pass; full suite +18 GREEN with 0 regressions.

## Authentication Gates

None - kill switches are pure predicates over in-process state; no external service calls.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `from src.quoting import KillSwitchAggregator, kill_switch_staleness, kill_switch_deviation, kill_switch_brier, kill_switch_api_error, kill_switch_market_invalid` all resolve cleanly.
- Forward link to **plan 04-04 (mode-selector):** consumes `KillSwitchAggregator.any_tripped(state, theo, market, error_streak)[0]` as the boolean `kill_switch_active` input to mode-selector rule 1 — when True, return IDLE regardless of other rules.
- Forward link to **plan 04-08 (reconciliation + E2E):** wires the round-resolution event handler to `agg.recent_briers.append(score)` AFTER round resolution AND when mode != IDLE (Pitfall 4 contract documented in the aggregator class docstring); also wires the cancel-all callback so ANY trip fires `KalshiOrderManager.cancel_all_orders` per CRule 9.
- Plan 04-04 (mode-selector) is next — Wave 3 sibling. Pre-existing RED stubs at `tests/quoting/test_mode_selector.py` covering the 6 selection rules (kill_switch_active → IDLE / bomb_planted → POST_PLANT_QUOTE / mid_round_not_planted → IDLE / take_threshold → DIRECTIONAL_TAKE / mm_min_edge → MM_BETWEEN_ROUND / fall-through → IDLE).

**Recommended next command:** `/gsd:execute-phase 04` to run plan 04-04.

**Verification command:**
```
python -m uv run pytest tests/quoting/test_kill_switches.py --no-cov
# Expected: 18 passed (10 RED stubs flipped to 18 GREEN)

python -m uv run pytest tests/ --no-cov
# Expected: 374 passed, 53 xfailed (was 356/63 in Plan 04-02 baseline; +18 GREEN, -10 xfailed)

python -m uv run mypy --strict src/quoting/
# Expected: Success: no issues found in 6 source files

rg "disable_" src/quoting/kill_switches.py
# Expected: no matches (DEC-005 — no per-switch off-switch flag)
```

---
*Phase: 04-quoting-layer*
*Completed: 2026-05-11*

## Self-Check: PASSED

- `src/quoting/kill_switches.py` exists on disk (170 lines).
- `src/quoting/__init__.py` exists and exports all 6 new public names (5 predicates + KillSwitchAggregator).
- `tests/quoting/test_kill_switches.py` exists and contains 18 GREEN tests (was 10 RED stubs).
- `.planning/phases/04-quoting-layer/04-03-kill-switches-SUMMARY.md` exists (this file).
- Commit `b47f886` (feat(04-03): kill switches as pure predicates + KillSwitchAggregator) found in `git log --oneline --all`.
- `from src.quoting import KillSwitchAggregator, kill_switch_staleness, kill_switch_deviation, kill_switch_brier, kill_switch_api_error, kill_switch_market_invalid` resolves cleanly.
- `rg "disable_" src/quoting/kill_switches.py` returns NO matches (DEC-005 grep guard).
- `rg "disable_X|disable_kill_switch|kill_switch_disable" src/quoting/` returns NO matches.
- `python -m uv run pytest tests/quoting/test_kill_switches.py --no-cov` → 18 passed.
- `python -m uv run pytest tests/ --no-cov` → 374 passed / 53 xfailed (Plan 04-02 baseline 356/63; +18 GREEN, -10 xfailed, 0 regressions).
- `python -m uv run mypy --strict src/quoting/` → Success: no issues found in 6 source files.
