---
phase: 04-quoting-layer
plan: "02"
subsystem: sizing
tags: [kelly, portfolio-cap, hypothesis, pure-function, dec-023, req-kelly-sizer]

# Dependency graph
requires:
  - phase: 04-00-test-infrastructure
    provides: tests/sizing/test_kelly_portfolio.py RED stubs (7), SERIES_AGGREGATE_CAP_FRAC + PER_MARKET_CAP_FRAC + KELLY_MULTIPLIER constants, mypy strict overrides for src.sizing.* and src.quoting.*, hypothesis>=6.100 dep
  - phase: 04-01-kalshi-order-manager
    provides: src/quoting/ package skeleton; Plan 04-02's PortfolioState is colocated with the order manager because both feed into the quoter loops
provides:
  - src/sizing/kelly.py — pure kelly_size(theo, market_yes_ask, bankroll, series_id, current_series_exposure) -> int implementing DEC-023 v2 verbatim formula
  - src/quoting/portfolio.py — PortfolioState class with on_place / on_settle / current / snapshot (Pitfall 5 mitigation surface)
  - 30 GREEN tests (17 kelly + 13 portfolio_state) including 4 hypothesis property tests
affects: [04-04-mode-selector, 04-05-mm-quoter, 04-06-directional-taker, 04-07-post-plant-quoter, 04-08-reconciliation, 04-09-e2e-gate]

# Tech tracking
tech-stack:
  added: []  # hypothesis already in pyproject.toml from Plan 04-00
  patterns:
    - "Pure-function sizer + mutable registry split: src/sizing/kelly.kelly_size takes a snapshot dict (caller-owned, NOT mutated); src/quoting/portfolio.PortfolioState owns the dict and exposes on_place/on_settle/snapshot helpers"
    - "Hypothesis property tests for portfolio-Kelly invariants: never-full-Kelly, returns-zero-when-aggregate-exceeded, non-negative-integer, no-mutation-of-exposure"
    - "Three-cap composition order (DEC-023 v2 verbatim): max(0, half-Kelly) -> min(per-market cap) -> min(headroom = aggregate - exposure[s])"
    - "Pitfall 5 grep-discoverability: on_place/on_settle pair is named exactly so `rg \"on_settle\"` from plan 04-08 reconciliation finds the wire-up site"
    - "ValueError on negative fractions for on_place/on_settle — defensive guard against double-flipped sign bugs in the quoter loop"

key-files:
  created:
    - src/sizing/kelly.py
    - src/quoting/portfolio.py
    - tests/quoting/test_portfolio_state.py
  modified:
    - src/sizing/__init__.py
    - src/quoting/__init__.py
    - tests/sizing/test_kelly_portfolio.py

key-decisions:
  - "Pure-function sizer + mutable registry split — kelly_size stays mypy --strict friendly with NO I/O or state; PortfolioState owns the mutable dict and exposes the on_place/on_settle pair that plan 04-08 reconciliation wires"
  - "PortfolioState.on_settle clips at 0.0 instead of raising — protects against double-settlement bugs (resolution event delivered twice); exposure should never go negative under any real-world placement+settlement sequence"
  - "PortfolioState rejects NEGATIVE fractions on both on_place AND on_settle (ValueError) — placements always increase exposure, settlements always decrement; negative fraction means programming error in the caller, not a soft-handled data condition"
  - "snapshot() returns a FRESH dict copy each call so kelly_size cannot accidentally mutate the registry. The pure-function contract is enforceable from BOTH ends (sizer doesn't mutate the dict it gets; registry doesn't share the dict it returns)"
  - "Three-cap composition order verbatim from DEC-023: max(0, half-Kelly) THEN min(per-market cap 0.05) THEN min(headroom = 0.10 - exposure[s]). Reordering would change which constraint binds and break v1 single-market compat when exposure == {}"
  - "Boundary guards return 0 (not raise) for ask <= 0, ask >= 100, bankroll <= 0 — quoter loop reads market_yes_ask straight from MarketQuote which can be stale-zero on WS disconnect (Pitfall 7 from plan 04-01). Raising would crash the loop; returning 0 silently no-ops the placement"

patterns-established:
  - "Pure-function math + mutable-state registry split for layers that need both mypy --strict friendliness AND mutable per-series accumulation (sizing/portfolio split mirrors how Phase 03 split pure with_update + module-level commit/quarantine helpers)"
  - "Hypothesis property tests for sizing invariants over the full input domain — augments the per-case unit tests with 200-example shrunk-failure coverage on never-full-Kelly, aggregate-cap-binding, and non-mutation"
  - "ValueError + max(0, ...) clip is the canonical idiom for 'reject programming-error inputs, soft-handle data-condition inputs' in registry-style mutable state"

requirements-completed: [REQ-kelly-sizer]

# Metrics
duration: 4min
completed: 2026-05-11
---

# Phase 04 Plan 02: Portfolio Kelly Summary

**Portfolio-aware half-Kelly sizer (DEC-023 v2) shipped as a pure function in `src/sizing/kelly.py` + a mutable `PortfolioState` registry in `src/quoting/portfolio.py`. The sizer takes a `current_series_exposure: dict[str, float]` snapshot it never mutates; PortfolioState owns the dict and exposes on_place/on_settle (the Pitfall 5 mitigation surface plan 04-08 reconciliation will wire round-resolution callbacks into).**

## Performance

- **Duration:** 4 min
- **Started:** 2026-05-11T19:53:14Z
- **Completed:** 2026-05-11T19:57:34Z
- **Tasks:** 2 (each atomic commit)
- **Files created:** 3 (src/sizing/kelly.py, src/quoting/portfolio.py, tests/quoting/test_portfolio_state.py)
- **Files modified:** 3 (src/sizing/__init__.py, src/quoting/__init__.py, tests/sizing/test_kelly_portfolio.py)
- **Test delta:** 7 RED stubs flipped + 23 new GREEN tests added — net +30 GREEN. Full suite: 356 passed / 63 xfailed (was 326 / 70 at Plan 04-01 close).

## Accomplishments

- **DEC-023 v2 verbatim implementation:** `f = max(0, KELLY_MULTIPLIER * f_full)` → `f = min(f, PER_MARKET_CAP_FRAC)` → `f = min(f, max(0, SERIES_AGGREGATE_CAP_FRAC - exposure[series_id]))`. Returns 0 if any cap binds the fraction to 0. v1 single-market compat preserved when `exposure == {}`.
- **Pure-function discipline:** `kelly_size` is decorated with no state, no I/O, no globals beyond constants. Verified by `test_does_not_mutate_exposure_dict` (unit) + `test_property_does_not_mutate_exposure` (hypothesis over the full input domain).
- **PortfolioState as the integration seam for Pitfall 5:** the class makes the `on_place` / `on_settle` pair grep-discoverable (`rg "on_settle"` from any plan-04-08 task finds the wire-up site). on_settle clips at 0.0 so double-settlement bugs degrade gracefully rather than rolling exposure negative.
- **Property tests cover REQ-kelly-sizer acceptance criteria:** 200-example never-full-Kelly invariant, 100-example aggregate-cap-binding when exposure >= 0.10, 200-example non-negative-integer over `ask in [0, 120]` and `bankroll in [0, 1_000_000]`, 100-example no-mutation property.
- **Public surface ready for downstream consumers:** `from src.sizing import kelly_size` and `from src.quoting import PortfolioState` both resolve cleanly. Integration smoke verified: `ps.on_place('s', 0.05); kelly_size(0.6, 50, 100000, 's', ps.snapshot())` returns `100`.
- **mypy --strict clean across both src/sizing/ (2 files) and src/quoting/ (5 files including the new portfolio.py).**

## Task Commits

Each task was committed atomically:

1. **Task 1: src/sizing/kelly.py + GREEN test_kelly_portfolio.py** — `77362a9` (feat)
2. **Task 2: src/quoting/portfolio.py PortfolioState + test_portfolio_state.py** — `731a013` (feat)

**Plan metadata:** _(this SUMMARY commit, pending)_ (docs)

## Files Created/Modified

### Created (3 files)

- `src/sizing/kelly.py` — pure `kelly_size(theo, market_yes_ask, bankroll, series_id, current_series_exposure) -> int`. Implements DEC-023 v2 verbatim formula with three caps applied in order. Boundary guards: `ask <= 0 or ask >= 100` → 0; `bankroll <= 0` → 0; `theo <= ask/100` → 0 (via `f_full <= 0` → `max(0, neg) = 0`).
- `src/quoting/portfolio.py` — `PortfolioState` class with `__slots__ = ("_exposure",)`. Methods: `on_place(series_id, fraction)` (increments, rejects negatives), `on_settle(series_id, fraction)` (decrements clipped at 0, rejects negatives), `current(series_id) -> float` (0.0 for unknown), `snapshot() -> dict[str, float]` (fresh copy).
- `tests/quoting/test_portfolio_state.py` — 13 GREEN unit tests: empty state, current-unknown, on_place records, accumulation, independent series, settlement decrement, double-settlement clipping (Pitfall 5), settle-unknown-series clipping, snapshot copy semantics (mutation of returned dict doesn't affect state), negative-fraction guards on both methods, zero-fraction edge case, full place→settle lifecycle.

### Modified (3 files)

- `src/sizing/__init__.py` — exports `kelly_size`. `__all__ = ["kelly_size"]`. Module docstring expanded to note DEC-004 + DEC-023 v2 surface.
- `src/quoting/__init__.py` — adds `PortfolioState` to public surface. `from src.quoting import PortfolioState` resolves.
- `tests/sizing/test_kelly_portfolio.py` — 7 RED stubs replaced with 17 GREEN tests: 13 unit + 4 hypothesis property tests. Unit tests cover v1 compat, aggregate cap at 0.10 / above 0.10, per-market cap at 0.05, partial headroom clipping below per-market cap, negative edge, ask boundaries (0, 100, 101, -5), zero bankroll, non-mutation, other-series-exposure isolation. Property tests cover never-full-Kelly, returns-zero-when-aggregate-exceeded, non-negative-integer, no-mutation.

## Decisions Made

- **Pure-function sizer + mutable registry split.** `kelly_size` stays `mypy --strict` clean with NO I/O or state; `PortfolioState` owns the mutable dict. Mirrors Phase 03's pure-`with_update` + module-level-`commit/quarantine` split for the same reason: math layer must type-check cleanly, mutation layer must be auditable.
- **PortfolioState.on_settle clips at 0.0 (does NOT raise).** Protects against double-settlement bugs (resolution event delivered twice from the WS reconciliation path). Exposure should never go negative under any real-world placement+settlement sequence; clipping degrades gracefully rather than crashing.
- **Both on_place AND on_settle reject NEGATIVE fractions via ValueError.** Placements always increase exposure; settlements always decrement. A negative fraction means a programming error in the caller (sign flip), not a soft-handled data condition. Hard-fail surfaces the bug at the call site rather than letting it propagate silently.
- **snapshot() returns a FRESH dict copy each call.** Combined with `kelly_size`'s pure-function contract, this enforces the immutability of the sizing pipeline from BOTH ends. The registry never shares its internal dict; the sizer never mutates the dict it gets.
- **Three-cap composition order verbatim from DEC-023 v2.** `max(0, half-Kelly)` → `min(per-market cap 0.05)` → `min(headroom)`. Reordering would change which constraint binds and break v1 single-market compat when `exposure == {}`. v1 compat is REQ-kelly-sizer acceptance criterion #1.
- **Boundary guards return 0 (do NOT raise) for ask/bankroll degenerate values.** The quoter loop reads `market_yes_ask` straight from `MarketQuote` (Plan 04-01 surface) which can be stale-zero on WS disconnect via the `mark_invalid` path. Raising would crash the loop; returning 0 silently no-ops the placement — same behavior as a negative-edge input.
- **+1 tolerance in `test_never_full_kelly` hypothesis property.** `int()` floor rounding can differ by 1 between the formula computation in the test and the actual implementation when `f * bankroll / ask` lands within ε of an integer. The half-Kelly upper bound is the conceptual invariant; +1 is the implementation-detail floor parity tolerance.

## Deviations from Plan

None - plan executed exactly as written.

All 2 task plans, 2 atomic commits, 30 GREEN tests (17 kelly + 13 portfolio_state), mypy --strict clean across both src/sizing/ and src/quoting/, full suite passes 356/63. The plan's `<action>` blocks for both tasks shipped verbatim with only the test-file additions noted (12+ unit tests in plan, 13 shipped for portfolio_state including a zero-fraction edge case and the on_settle-unknown-series edge case that plan didn't explicitly enumerate but are implied by `<behavior>`).

**Total deviations:** 0
**Impact on plan:** No deviations needed. RESEARCH Pitfall 5 (Pitfall surface — on_settle wire-up) is pre-mitigated by the class structure; downstream plan 04-08 inherits a grep-discoverable wire-up site.

## Issues Encountered

None - all verifications passed on first run.

## Authentication Gates

None - this plan is pure-function math + in-memory registry. No external services, no credentials.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `from src.sizing import kelly_size` and `from src.quoting import PortfolioState` both resolve. Plans 04-05 (MM quoter) / 04-06 (directional taker) / 04-07 (post-plant quoter) can call `kelly_size(theo, ask, bankroll, series_id, portfolio_state.snapshot())` directly.
- **Pitfall 5 wire-up site for plan 04-08 reconciliation:** `rg "on_settle"` returns `src/quoting/portfolio.py` as the canonical decrement path. Plan 04-08 task should call `portfolio_state.on_settle(series_id, fraction_placed)` from the round-resolution event handler.
- mypy --strict block on src.sizing.* / src.quoting.* (Plan 04-00) is now exercising real code; both packages stay clean.
- Forward links per plan output:
  - Plan 04-06 directional taker: calls `kelly_size(theo_cents/100, market.yes_ask, bankroll, ticker_series_root, ps.snapshot())` when `|theo - market.mid| > TAKE_THRESHOLD`.
  - Plan 04-07 post-plant quoter: same call shape with `POST_PLANT_TAKE_THRESHOLD`.
  - Plan 04-08 reconciliation: wires `PortfolioState.on_settle(series_id, fraction)` to the round-resolution event handler (the metrics JSONL emits the seq_id; the reconciliation reads + dispatches).

**Recommended next command:** `/gsd:execute-phase 04` to run plan 04-03 (kill-switches) — independent of this plan's outputs and parallelizable with the remaining Wave 2 work.

**Verification commands:**
```
.venv/Scripts/python.exe -m pytest tests/sizing/test_kelly_portfolio.py tests/quoting/test_portfolio_state.py -x --no-cov
# Expected: 30 passed (17 kelly + 13 portfolio_state)

.venv/Scripts/python.exe -m pytest tests/ --no-cov
# Expected: 356 passed / 63 xfailed (was 326/70 in Plan 04-01 baseline)

.venv/Scripts/python.exe -m mypy --strict src/sizing/ src/quoting/
# Expected: Success: no issues found in 7 source files
```

---
*Phase: 04-quoting-layer*
*Completed: 2026-05-11*

## Self-Check: PASSED

- All 3 created files exist on disk: `src/sizing/kelly.py`, `src/quoting/portfolio.py`, `tests/quoting/test_portfolio_state.py`.
- All 3 modified files exist: `src/sizing/__init__.py`, `src/quoting/__init__.py`, `tests/sizing/test_kelly_portfolio.py`.
- Both task commits found in git log: `77362a9` (feat — kelly_size pure function + GREEN tests), `731a013` (feat — PortfolioState registry + GREEN tests).
- `from src.sizing import kelly_size` resolves; `from src.quoting import PortfolioState` resolves.
- Integration smoke verified: `ps.on_place('s', 0.05); kelly_size(0.6, 50, 100000, 's', ps.snapshot())` returns `100`.
- Plan 04-02 test files: 30 passed / 0 xfailed (was 7 xfailed in Plan 04-00 RED-stub baseline + 0 portfolio_state stubs since it's a new file).
- Full suite: 356 passed / 63 xfailed (Plan 04-01 baseline was 326/70; 30 GREEN, 0 regressions).
- mypy --strict src/sizing/ + src/quoting/ clean (7 source files total).
