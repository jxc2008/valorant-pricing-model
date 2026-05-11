---
phase: 04-quoting-layer
plan: "05"
subsystem: quoting
tags: [mm-quoter, mm-between-round, fill-ledger, dec-018-v2, dec-020-v2, pitfall-4, hypothesis, kalshi-fee-floor, req-mm-quoter]

# Dependency graph
requires:
  - phase: 04-00-test-infrastructure
    provides: RED-stub tests at tests/quoting/test_mm_quoter.py + tests/quoting/test_fill_ledger.py; MIN_HALF_SPREAD constant; tmp_fill_ledger_dir fixture; mypy strict block for src.quoting.*
  - phase: 04-01-kalshi-order-manager
    provides: KalshiOrderManager (place_quote / cancel_quote / active_quotes / dry_run wrapper); Quote dataclass with strategy_id v2 field; MarketQuote + make_quote helper
  - phase: 04-04-mode-selector
    provides: TradingMode Literal alphabet (MM_BETWEEN_ROUND is rule-5 return value); TheoOutput.vega surface (Phase 1 carry-forward) consumed by spread sizing
  - phase: 01-04-live-theo
    provides: TheoOutput.vega (= vega_between_round per DEC-018 D-10/D-11) — the vega input to compute_half_spread
provides:
  - src/quoting/fill_ledger.py — HypotheticalFill (frozen+slots; 11-key JSONL schema) + append_fill (POSIX O_APPEND routed to per-strategy {match_id}.{strategy_lower}.jsonl) + simulate_touched (DEC-020 simple "limit touched" rule) + maybe_record_mm_fill (routes by quote.strategy_id; co-owned by 04-05/04-06/04-07)
  - src/quoting/mm_quoter.py — compute_half_spread(vega_between, staleness_s) + async quote_mm_between_round(state, theo, market, mgr, ticker, count, now=None)
  - src/config/constants.MM_VEGA_SPREAD_K (= 50.0; TBD; DEC-018 v2 k coefficient)
  - 29 GREEN tests: 14 fill_ledger (7 simulate_touched + 4 append/schema/atomic + 3 maybe_record) + 15 mm_quoter (6 spread-formula + 1 hypothesis property + 1 fee-floor + 7 async dry-run)
affects: [04-06-directional-taker, 04-07-post-plant-quoter, 04-08-order-lifecycle-e2e]

# Tech tracking
tech-stack:
  added: []  # All deps (hypothesis, pytest-asyncio, aiohttp, cryptography) already in pyproject.toml from earlier waves
  patterns:
    - "Per-strategy fill-ledger file split (DEC-020 v2): MM_BETWEEN_ROUND -> {match_id}.mm_between_round.jsonl, DIRECTIONAL_TAKE -> {match_id}.directional_take.jsonl, POST_PLANT_QUOTE -> {match_id}.post_plant_quote.jsonl. Combined files would corrupt the promotion gate's per-strategy fill-count evaluation."
    - "Single shared maybe_record_mm_fill helper routes by quote.strategy_id — plan 04-06 directional + plan 04-07 post-plant REUSE the same helper without re-implementing the touched rule."
    - "Atomic POSIX append per (match_id, strategy) pair; line < 4KB guarantees PIPE_BUF atomicity (Phase 03 D-03 single-writer invariant carry-forward; belt + suspenders since we have exactly one writer per pair)."
    - "Half-spread formula floor invariant verified two ways: hypothesis property test (200 examples over vega in [0, 1] x staleness in [0, 4.99]) AND explicit fee-curve inequality (MIN_HALF_SPREAD > Kalshi maker fee at theo=50c + 1c slippage budget)."
    - "Ceiling rather than round on vega contribution — defensive against 3.01c rounding down to 3c and tying the floor exactly; prefer wider than narrower when fee curve is the binding constraint."
    - "Cancel-and-replace on stale OR mispriced quotes (RESEARCH §Pattern 2) — simpler than amend-order; idempotent on unchanged-price + age < 2s. Burns no rate budget on identical replacements."
    - "Async pytest_asyncio.fixture decorator for KalshiOrderManager fixture — pytest-asyncio idiom for AsyncIterator-yielding fixtures (replaces @pytest.fixture on async generator which pytest-asyncio 1.3.0 deprecated)."
    - "Reserved-arg `del market` pattern in quote_mm_between_round — keeps mypy --strict + ruff clean while documenting the forward contract to Phase 5 market-aware sizing (mirrors mode_selector vega_between/vega_post_plant del pattern from plan 04-04)."

key-files:
  created:
    - src/quoting/fill_ledger.py
    - src/quoting/mm_quoter.py
  modified:
    - src/config/constants.py
    - tests/config/test_constants.py
    - src/quoting/__init__.py
    - tests/quoting/test_fill_ledger.py
    - tests/quoting/test_mm_quoter.py

key-decisions:
  - "Per-strategy fill-ledger file split (DEC-020 v2) — MM, DIRECTIONAL, POST_PLANT in DIFFERENT files. Plan 04-08 promotion gate evaluates each ledger independently via fill-count gate; combined writes would corrupt the count and force the promoter to filter post-hoc by strategy field (introduces a forensic-reader-coupled invariant that's easy to violate)."
  - "Single shared maybe_record_mm_fill helper used by MM/DIRECTIONAL/POST_PLANT — the strategy routing is automatic via quote.strategy_id (Quote dataclass field added in plan 04-01). Plan 04-06 + 04-07 import the helper rather than re-implement the touched rule."
  - "Half-spread formula uses ceiling on the vega contribution: hs = max(MIN_HALF_SPREAD, ceil(MM_VEGA_SPREAD_K * sqrt(vega_between))) + floor(max(0, staleness_s - 2.0)). Ceiling defends against the 3.01c rounding-down trap that would tie the 3c floor and silently violate the Pitfall 4 fee-floor invariant."
  - "Boundary guard returns early without placement when theo near 0.01 or 0.99 would push the buy_price/sell_price outside Kalshi's [1, 99] cents. Defensive — at those theos MM_MIN_EDGE rule-5 in the mode selector likely returns IDLE anyway, but the guard makes the MM quoter robust to upstream bugs."
  - "Idempotent quoting (no cancel + no re-place) on unchanged-price + age < 2s. Burns no rate budget on identical replacements; cancels stale OR mispriced quotes BEFORE placing fresh (RESEARCH §Pattern 2 cancel-and-replace simpler than amend-order)."
  - "MM_VEGA_SPREAD_K=50.0 (TBD) added atomically with tests/config/test_constants.py allow-list extension (Phase 03 D-08 same-commit Rule-3 prophylactic). Splitting across commits would leave CI red between them. Initial guess scales Phase 1's typical vega_between range [0.001, 0.01] into a [1.5c, 5c] vega-driven band on top of the 3c floor."
  - "Negative-vega defensive clip to 0.0 (not raise) — keeps the floor invariant hypothesis-property-test clean across the full input domain. Negative vega is a programming error (variance can't be negative); defensive degradation is safer than crashing the quoter loop."
  - "`del market` in quote_mm_between_round body documents the reserved-arg contract — `market` is in the signature for the stable plan-04-08 reconciliation contract (Phase 5 may consume it for market-spread-aware sizing) without polluting the placement path now. Mirrors mode_selector.trading_mode `del vega_between, vega_post_plant` pattern (plan 04-04 D-03)."

patterns-established:
  - "TDD RED -> GREEN cycle within each Task: 1) write test file with concrete asserts, 2) verify ImportError-driven RED, 3) write src/ implementation, 4) verify GREEN, 5) commit atomic — same pattern Phase 03 used for arbiter/poller, now standardized across quoting layer plans."
  - "Shared fill-ledger helper with strategy-routed file split — the canonical pattern for promotion gates that evaluate per-strategy. Plan 04-06 and 04-07 wire into the same maybe_record_mm_fill helper without re-implementing; ledger filename is derived from quote.strategy_id at write time."
  - "Hypothesis property test + explicit fee-curve inequality test = belt + suspenders coverage for the spread-floor invariant. The property test catches drift across the full input domain; the inequality test documents the Pitfall 4 reasoning symbolically (maker_fee_c = ceil(0.035 * p * (1-p) * 100) / 100) so a future reader can audit the floor against the live Kalshi fee schedule."

requirements-completed: [REQ-mm-quoter]

# Metrics
duration: 6min
completed: 2026-05-11
---

# Phase 04 Plan 05: MM-Between-Round Quoter Summary

**MM_BETWEEN_ROUND quoter (REQ-mm-quoter v2) + shared per-strategy fill ledger. compute_half_spread implements DEC-018 v2 formula (max(MIN_HALF_SPREAD, ceil(MM_VEGA_SPREAD_K * sqrt(vega_between))) + max(0, floor(staleness_s - 2.0))) with hypothesis-property + explicit-inequality coverage of the Pitfall 4 fee-floor invariant. quote_mm_between_round is idempotent on unchanged inputs, cancels stale (age > 2s) OR mispriced quotes before re-placing, tags every Quote with strategy_id="MM_BETWEEN_ROUND" so DEC-020 v2 per-strategy ledger routing lands fills exclusively in data/fills/{match_id}.mm_between_round.jsonl. The shared maybe_record_mm_fill helper (routes by quote.strategy_id) is co-owned by plan 04-06 directional + 04-07 post-plant — they import without re-implementing.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-05-11T20:34:26Z
- **Completed:** 2026-05-11T20:40:24Z
- **Tasks:** 2 (each its own atomic commit)
- **Files created:** 2 (src/quoting/fill_ledger.py, src/quoting/mm_quoter.py)
- **Files modified:** 5 (src/config/constants.py, tests/config/test_constants.py, src/quoting/__init__.py, tests/quoting/test_fill_ledger.py, tests/quoting/test_mm_quoter.py)
- **Test delta:** 29 GREEN tests (14 fill_ledger + 15 mm_quoter) replacing 10 RED stubs (6 fill_ledger + 4 mm_quoter) — net +30 GREEN, -10 xfailed. Full suite: 417 passed / 36 xfailed (was 387/46 in 04-04 baseline; 0 regressions).

## Accomplishments

- **src/quoting/fill_ledger.py** (~120 lines) ships the canonical hypothetical-fill ledger module co-owned by plans 04-05/04-06/04-07:
  - `HypotheticalFill` (frozen+slots; 11-key JSONL schema: seq_id, strategy, ticker, side, action, price_c, count, theo_c_at_fill, market_mid_c_at_fill, realized_outcome | None, pnl_cents | None). realized_outcome + pnl_cents populated by Phase 5 backtest replay, NOT at write time (RESEARCH anti-pattern #2 — round resolution is a Phase 03 event AFTER the fill).
  - `append_fill(fill, ledger_dir, match_id)` routes to `{match_id}.{strategy_lower}.jsonl`:
    - MM_BETWEEN_ROUND -> mm_between_round.jsonl
    - DIRECTIONAL_TAKE -> directional_take.jsonl
    - POST_PLANT_QUOTE -> post_plant_quote.jsonl
  - `simulate_touched(quote_price_c, quote_action, last_mid_c, next_mid_c)` implements the DEC-020 simple "limit touched" rule:
    - buy at P fills iff `next_mid_c < quote_price_c <= last_mid_c`
    - sell at P fills iff `last_mid_c <= quote_price_c < next_mid_c`
    - no movement (last_mid == next_mid) returns False under both branches
  - `maybe_record_mm_fill(quote, last_mid_c, next_mid_c, seq_id, theo_c, ledger_dir, match_id) -> bool` is the integration helper — same function is called by MM quoter (04-05), directional taker (04-06), and post-plant quoter (04-07); strategy routing is automatic via `quote.strategy_id`.
- **src/quoting/mm_quoter.py** (~140 lines including docstring) ships the MM_BETWEEN_ROUND quoter:
  - `compute_half_spread(vega_between, staleness_s) -> int` implementing DEC-018 v2 verbatim formula. Returns integer cents >= MIN_HALF_SPREAD. Floor invariant verified by hypothesis property test (200 examples) + explicit Pitfall 4 fee-curve inequality test.
  - `quote_mm_between_round(state, theo, market, mgr, ticker, count, *, now=None) -> None` async coroutine that:
    1. Computes half-spread from `theo.vega` + `time.time() - state.last_updated_ts` staleness.
    2. Cancels stale (age > 2s) OR mispriced existing quotes via `mgr.cancel_quote(ticker, leg_key)`.
    3. Places fresh yes-buy at `theo_c - hs` + yes-sell at `theo_c + hs` via `mgr.place_quote(Quote(..., strategy_id="MM_BETWEEN_ROUND"))`.
    4. Idempotent on unchanged-price + age < 2s (no cancel, no re-place).
    5. Boundary guard: skips placement if buy_price < 1 or sell_price > 99.
- **MM_VEGA_SPREAD_K=50.0** added to `src/config/constants.py` AND `tests/config/test_constants.py` allow-list (EXPECTED_NAMES + EXPECTED_TYPES) in commit `d693112` — same-commit Rule-3 prophylactic per Phase 03 D-08.
- **29 GREEN tests** replacing 10 RED stubs:
  - 14 fill_ledger: 7 simulate_touched edge cases (buy crossed, buy boundary, buy not crossed, sell crossed, sell boundary, sell not crossed, no movement) + 1 append_fill round-trip + 1 per-strategy-separate-files (`test_per_strategy_ledger_separate_files`) + 1 11-key schema + 1 atomic-append-order + 3 maybe_record_mm_fill (crossed-returns-True, not-crossed-returns-False, uses-quote-strategy-id routes to directional).
  - 15 mm_quoter: 6 compute_half_spread unit tests (floor at zero vega, vega contribution at typical 0.01, floor binds at low vega, staleness penalty below 2s, staleness penalty above 2s, negative-vega defensive clip) + 1 hypothesis floor-invariant property test (200 examples over vega in [0, 1] x staleness in [0, 4.99]) + 1 `test_spread_floor_beats_fee` (MIN_HALF_SPREAD > ceil(0.035 * 0.5 * 0.5 * 100) / 100 + 1c slippage) + 7 quote_mm_between_round async dry-run tests (places both legs, strategy_id tagged, idempotent on unchanged prices, cancels stale, cancels mispriced, boundary guard below 1, boundary guard above 99).
- `mypy --strict src/quoting/` clean (9 source files: kalshi_auth, order_manager, market_data, portfolio, kill_switches, mode_selector, fill_ledger, mm_quoter, __init__).

## Task Commits

Each task was committed atomically:

1. **Task 1: src/quoting/fill_ledger.py + MM_VEGA_SPREAD_K constant + GREEN test_fill_ledger.py** — `d693112` (feat)
2. **Task 2: src/quoting/mm_quoter.py + GREEN test_mm_quoter.py (incl. spread-floor-beats-fee property test)** — `3bc3f9c` (feat)

**Plan metadata:** _(this SUMMARY commit, pending)_ (docs)

## Files Created/Modified

### Created (2 files)

- `src/quoting/fill_ledger.py` (~120 lines) — HypotheticalFill dataclass (frozen+slots, 11-key schema), append_fill (POSIX O_APPEND with per-strategy filename routing), simulate_touched (DEC-020 "limit touched" rule), maybe_record_mm_fill (strategy-routed integration helper co-owned by plans 04-05/04-06/04-07).
- `src/quoting/mm_quoter.py` (~140 lines including docstring) — compute_half_spread (pure function, DEC-018 v2 formula with ceiling on vega contribution + floor on staleness penalty), quote_mm_between_round (async coroutine: idempotent place/cancel-stale/cancel-mispriced ladder at theo +/- hs).

### Modified (5 files)

- `src/config/constants.py` — added `MM_VEGA_SPREAD_K: Final[float] = 50.0` to the Phase 4 quoting-layer thresholds section (after MIN_HALF_SPREAD). Docstring includes calibration TODO + numerical worked examples at vega in {0.001, 0.005, 0.01}.
- `tests/config/test_constants.py` — added `"MM_VEGA_SPREAD_K"` to EXPECTED_NAMES tuple AND EXPECTED_TYPES dict (type: float). Atomic same-commit Rule-3 per Phase 03 D-08.
- `src/quoting/__init__.py` — re-exports HypotheticalFill, append_fill, simulate_touched, maybe_record_mm_fill (Task 1); compute_half_spread, quote_mm_between_round (Task 2). `__all__` now contains 27 names.
- `tests/quoting/test_fill_ledger.py` — 6 RED stubs replaced with 14 GREEN tests. Inline `_quote(action, price, strategy)` factory builds Quote objects with the required v2 strategy_id field; tests cover the full simulate_touched truth table, append_fill round-trip, per-strategy file routing, JSONL schema keys, atomic append order, and maybe_record_mm_fill strategy routing.
- `tests/quoting/test_mm_quoter.py` — 4 RED stubs replaced with 15 GREEN tests. `pytest_asyncio.fixture` decorator on async `mgr` fixture (replaces deprecated `@pytest.fixture` on async generator; pytest-asyncio 1.3.0 requires the explicit decorator). Hypothesis property test for floor invariant (200 examples); explicit Pitfall 4 fee-floor inequality test documenting the symbolic Kalshi fee curve.

## Decisions Made

- **Per-strategy fill-ledger file split (DEC-020 v2):** MM, DIRECTIONAL, POST_PLANT each get their OWN `{match_id}.{strategy_lower}.jsonl` file. Combined writes would corrupt the plan-04-08 promotion gate's per-strategy fill-count evaluation (MM can be cut while DIRECTIONAL promotes per DEC-020 v2). Verified by `test_per_strategy_ledger_separate_files` — pushes one fill per strategy and asserts the three expected filenames exist.
- **Single shared `maybe_record_mm_fill` helper routes by `quote.strategy_id`** — plans 04-06 (directional) + 04-07 (post-plant) import this helper rather than re-implement. The strategy routing is automatic via the Quote dataclass field added in plan 04-01. Verified by `test_maybe_record_uses_quote_strategy_id` — passing a DIRECTIONAL_TAKE quote routes fills to directional_take.jsonl (NOT mm_between_round.jsonl).
- **Ceiling on the vega contribution** in `compute_half_spread`: `ceil(MM_VEGA_SPREAD_K * sqrt(vega_between))`. Round-half-up would let a 3.01c vega-driven spread round down to 3c and TIE the floor exactly, silently violating the Pitfall 4 invariant that the floor must STRICTLY exceed Kalshi maker fee + slippage. Ceiling guarantees the vega contribution is always at least 1c wider than the raw `k * sqrt(vega)` magnitude when there's any non-zero vega.
- **Boundary guard skips placement** when theo near 0.01/0.99 would push buy_price < 1 or sell_price > 99. Defensive; at those theos MM_MIN_EDGE rule-5 in the mode selector likely returns IDLE anyway, but the guard makes the MM quoter robust to upstream bugs. Verified by two tests — theo=0.02 boundary (buy_price = 2 - 3 = -1) and theo=0.98 boundary (sell_price = 98 + 3 = 101).
- **Idempotent quoting:** if existing quotes are at the correct price AND age < 2s, do nothing (no cancel, no re-place). Verified by `test_idempotent_on_unchanged_prices` — second call with identical inputs + age < 2s preserves the same `order_id` values (no replacement happened). Cancels happen only when stale (age > 2s, verified by `test_cancels_stale_quotes`) OR mispriced (verified by `test_cancels_mispriced_quotes`).
- **MM_VEGA_SPREAD_K=50.0 (TBD)** added atomically with the allow-list extension in the same commit (Phase 03 D-08 prophylactic). Splitting would leave CI red between commits. Initial value scales Phase 1's typical vega_between range [0.001, 0.01] into a [1.5c, 5c] vega-driven band on top of the 3c floor. Phase 5 calibration tunes from observed fill distributions (TODO marker in docstring).
- **Negative-vega defensive clip to 0.0 (not raise)** in `compute_half_spread`. Variance can't be negative; negative input is a programming error. Defensive clip keeps the floor-invariant hypothesis property test clean across the full input domain. Verified by `test_spread_handles_negative_vega_defensively`.
- **`del market` reserved-arg pattern** in `quote_mm_between_round`. The `market: MarketQuote` parameter is in the signature for the stable plan-04-08 reconciliation contract (Phase 5 may consume it for market-spread-aware sizing) without polluting the current placement path. Mirrors mode_selector.trading_mode `del vega_between, vega_post_plant` pattern (plan 04-04 D-03). Keeps mypy --strict + ruff clean without `# noqa` or `# type: ignore`.
- **`pytest_asyncio.fixture` decorator** on the async `mgr` fixture (replaces deprecated `@pytest.fixture` on async generator). pytest-asyncio 1.3.0 emits a DeprecationWarning for the old idiom; the explicit decorator is the canonical 2026-era replacement. Same pattern will land in plan 04-06/04-07 test files.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `pytest_asyncio.fixture` instead of `@pytest.fixture` on async generator**
- **Found during:** Task 2 (test file creation)
- **Issue:** The plan body's mgr fixture used `@pytest.fixture` on `async def mgr(...) -> KalshiOrderManager:` with `yield`. pytest-asyncio 1.3.0 (the version pinned in pyproject.toml from plan 04-00) emits a DeprecationWarning for this pattern and recommends `@pytest_asyncio.fixture` for async generator fixtures.
- **Fix:** Replaced `@pytest.fixture` with `@pytest_asyncio.fixture` and added `import pytest_asyncio`. Return type annotation upgraded to `AsyncIterator[KalshiOrderManager]` to make the async-generator contract explicit (consistent with mypy --strict expectations).
- **Files modified:** `tests/quoting/test_mm_quoter.py`
- **Verification:** All 15 tests pass with 0 deprecation warnings; mypy --strict clean (`pytest_asyncio.fixture` is correctly typed in the stubs shipped with pytest-asyncio 1.3.0).
- **Committed in:** `3bc3f9c` (Task 2 commit).

**2. [Rule 3 - Blocking] `del market` to suppress unused-argument warnings without breaking the reserved-arg contract**
- **Found during:** Task 2 (mm_quoter.py drafting)
- **Issue:** The plan body's `quote_mm_between_round` signature included `market: MarketQuote` but the function body did NOT reference it (spread is theo-centered, not market-centered). Under ruff + mypy strict, unused arguments would either trigger warnings OR tempt a future maintainer to delete it from the signature — breaking the plan-04-08 reconciliation contract.
- **Fix:** Added `del market  # reserved for downstream consumers (Phase 5 market-aware sizing)` as the first line of the function body. Documents the reservation in code (greppable + survives refactors) without suppressing via `# noqa` or `# type: ignore`. Mirrors `mode_selector.trading_mode` `del vega_between, vega_post_plant` pattern (plan 04-04 D-03) and `round_conclusion.between_round_p` `del map_name, round_idx` pattern.
- **Files modified:** `src/quoting/mm_quoter.py`
- **Verification:** `mypy --strict src/quoting/` clean; function body still reads top-to-bottom in declared order.
- **Committed in:** `3bc3f9c` (Task 2 commit).

---

**Total deviations:** 2 auto-fixed (1 Rule 1 - Bug, 1 Rule 3 - Blocking)
**Impact on plan:** Both deviations preserve the plan's intent verbatim. The bug fix (#1) upgrades the test fixture decorator to the 2026-era pytest-asyncio idiom; the blocking fix (#2) closes a gap in the reserved-arg contract that would have surfaced as ruff warnings or future-maintainer footguns. No scope creep.

## Issues Encountered

None - all 29 GREEN tests passed on the first execution after the 2 auto-fixes above; mypy --strict clean from the first pass; full suite +30 GREEN with 0 regressions.

## Authentication Gates

None - mm_quoter operates against a dry-run KalshiOrderManager in tests (the order manager's own dry-run wrapper handles the network-elision per DEC-022). No external service calls.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `from src.quoting import compute_half_spread, quote_mm_between_round, HypotheticalFill, simulate_touched, maybe_record_mm_fill, append_fill` resolves cleanly.
- **Forward link to plan 04-06 (directional taker):** REUSES `maybe_record_mm_fill` helper — strategy routing is automatic via `quote.strategy_id="DIRECTIONAL_TAKE"`. The directional taker imports `from src.quoting.fill_ledger import maybe_record_mm_fill` (NOT a renamed helper) and the JSONL lands in `{match_id}.directional_take.jsonl` automatically.
- **Forward link to plan 04-07 (post-plant quoter):** REUSES the same `maybe_record_mm_fill` helper — `quote.strategy_id="POST_PLANT_QUOTE"` routes fills to `{match_id}.post_plant_quote.jsonl`. The post-plant quoter has the 100ms bomb-detect -> quote-pull p50 budget (PRD §5.4 / RESEARCH Pitfall 6); the pure-function shape of `compute_half_spread` keeps the per-cycle cost well under that budget.
- **Forward link to plan 04-08 (E2E test):** asserts MM + DIRECTIONAL + POST_PLANT fills land in SEPARATE files. The synthetic E2E harness pumps three quotes (one per strategy) through the same `maybe_record_mm_fill` helper and asserts three distinct JSONL files exist under `data/fills/`. The promotion gate's per-strategy fill-count evaluation can then be exercised on the three independent ledgers.
- **Forward link to Phase 5 (paper-trade promotion gate):** `cat data/fills/{id}.mm_between_round.jsonl | python -c "..."` is the canonical Brier(model) vs Brier(market_mid) computation — no filtering required because the ledger split is structural. MM strategy is cut from production if hypothetical fills per match average below `MIN_FILLS_PER_MATCH` (= 3 initially) per DEC-020 v2; DIRECTIONAL_TAKE and POST_PLANT_QUOTE promote independently.
- Plan 04-06 (directional taker) is next — Wave 4, parallelizable with 04-07 per the depends_on graph in plan 04-05's frontmatter.

**Recommended next command:** `/gsd:execute-phase 04` to run plan 04-06.

**Verification commands:**
```
python -m uv run pytest tests/quoting/test_fill_ledger.py tests/quoting/test_mm_quoter.py --no-cov
# Expected: 29 passed (14 fill_ledger + 15 mm_quoter; 10 RED stubs flipped, 19 new tests added)

python -m uv run pytest tests/ --no-cov
# Expected: 417 passed, 36 xfailed (was 387/46 in Plan 04-04 baseline; +30 GREEN, -10 xfailed)

python -m uv run mypy --strict src/quoting/
# Expected: Success: no issues found in 9 source files

python -c "from src.quoting import compute_half_spread, quote_mm_between_round, HypotheticalFill, simulate_touched, maybe_record_mm_fill, append_fill; print('ok')"
# Expected: ok

rg "directional_take|post_plant_quote" src/quoting/mm_quoter.py
# Expected: no matches (mm_quoter writes only to MM ledger via Quote.strategy_id)

rg "MM_VEGA_SPREAD_K" tests/config/test_constants.py
# Expected: 2 matches (EXPECTED_NAMES tuple + EXPECTED_TYPES dict)
```

---
*Phase: 04-quoting-layer*
*Completed: 2026-05-11*

## Self-Check: PASSED

- `src/quoting/fill_ledger.py` exists on disk (~120 lines).
- `src/quoting/mm_quoter.py` exists on disk (~140 lines).
- `.planning/phases/04-quoting-layer/04-05-mm-between-round-SUMMARY.md` exists (this file).
- Commit `d693112` (feat — per-strategy fill ledger + MM_VEGA_SPREAD_K constant) found in `git log --oneline --all`.
- Commit `3bc3f9c` (feat — MM_BETWEEN_ROUND quoter + spread-floor property tests) found in `git log --oneline --all`.
- `from src.quoting import compute_half_spread, quote_mm_between_round, HypotheticalFill, simulate_touched, maybe_record_mm_fill, append_fill` resolves cleanly.
- `rg "directional_take|post_plant_quote" src/quoting/mm_quoter.py` returns 0 matches — mm_quoter writes only to MM ledger via Quote.strategy_id="MM_BETWEEN_ROUND".
- `rg "MM_VEGA_SPREAD_K" tests/config/test_constants.py` returns 2 matches (EXPECTED_NAMES + EXPECTED_TYPES) — allow-list extended atomically.
- `python -m uv run pytest tests/quoting/test_fill_ledger.py tests/quoting/test_mm_quoter.py --no-cov` -> 29 passed.
- `python -m uv run pytest tests/ --no-cov` -> 417 passed / 36 xfailed (Plan 04-04 baseline 387/46; +30 GREEN, -10 xfailed, 0 regressions).
- `python -m uv run mypy --strict src/quoting/` -> Success: no issues found in 9 source files.
