---
phase: 01-core-pricing-engine
plan: 07
subsystem: pricing
tags: [pistol, anti-eco, dp-propagation, cr-05, wr-06, gap-closure]

# Dependency graph
requires:
  - phase: 01-core-pricing-engine
    provides: 01-06-derived-output-fixes (CR-01..CR-04 closures the 100-call memory-leak invariant + try/finally cleanup + clinch-first ordering + BO3 middle-map decisive formula)
provides:
  - "_advance_round updates pistol_winner_a[map_idx] at the round-1 boundary (CR-05)"
  - "_within_map_p_a_wins propagates pistol_winner_a through future-map sub-DP (WR-06)"
  - "Anti-eco rounds {2, 3} in DP recursion now dispatch to GUN_WIN_RATE / 1-GUN_WIN_RATE based on actual R1 outcome"
  - "End-to-end behavioral integration test locking the post-fix invariant under asymmetric matchup (TeamA=0.55/TeamB=0.45)"
  - "dp.py module docstring documents the second-half pistol Phase-2 follow-up limitation"
affects: [01-validation, 04-quoting, 05-validation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "BO3State.pistol_winner_a updates as a tuple-rebuild (preserves frozen+slots+hashable invariants)"
    - "Don't-override guard: existing settled values immutable through the DP forward-pass; only None -> True/False permitted"
    - "Memo key extension in _within_map_p_a_wins's inner recursion: (a_round, b_round, side_orient, pistol) — hashable + well-typed"

key-files:
  created: []
  modified:
    - "src/pricing/dp.py — _advance_round updates pistol_winner_a[map_idx] at round-1 boundary; module docstring documents CR-05 closure + Phase-1 simplifications + second-half pistol Phase-2 follow-up"
    - "src/pricing/live_theo.py — _within_map_p_a_wins inline state-advance propagates pistol_winner_a through the recursion; memo key extended to include pistol"
    - "tests/pricing/test_dp.py — 3 new CR-05 regression tests (forward-pass pistol propagation invariant)"
    - "tests/pricing/test_live_theo.py — 1 new WR-06 regression test (within-map propagation) + 1 end-to-end behavioral integration test"
    - "tests/pricing/test_round_types.py — re-scoped defensive-fallback test (rename + docstring update; assertion target unchanged)"

key-decisions:
  - "Used Form A (inline rebuild) for WR-06 fix in _within_map_p_a_wins, not Form B (refactor to call dp._advance_round) — preserves the existing memo structure and matches the within-map style"
  - "Per Rule 1 deviation: replaced the plan's literal 'law-of-total-probability decomposition' assertion in two tests (Task 3 WR-06 test, Task 6 integration test) with structural-ordering assertions because the literal decomposition does not hold for the semantics of _within_map_p_a_wins / LiveTheoEngine — forcing pistol=(T,T,T) at root affects ALL R2/R3 dispatches regardless of who actually wins R1 in the recursion's own forward-pass"
  - "Phase-2 follow-up tracked in dp.py module docstring (NEW Phase-1 simplification — not in the original A1..A8 RESEARCH.md Assumptions Log): pistol_winner_a is keyed only by map_idx so rounds 14/15 cannot be conditioned on a separately-tracked second-half pistol winner; track separately at the roadmap level if Phase 4 calibration surfaces it as a need"

patterns-established:
  - "Tuple-rebuild for slotted-frozen dataclass updates: tuple((new_val if i == idx else state.tuple_field[i]) for i in range(len(state.tuple_field))) preserves hashability"
  - "Don't-override guard for live-state propagation: 'if existing is None' before applying derived updates — protects ingested live values from being clobbered by DP forward-pass derivations"
  - "Structural-ordering tests as load-bearing locks: when the literal decomposition equality fails due to recursion semantics, assert strict ordering (X > Y > Z) and meaningful gap (|X - Z| > threshold) — captures broken-vs-fixed behavior without depending on closed-form magnitudes"

requirements-completed: [REQ-pistol-anti-eco-modeling, REQ-bo3-dp-engine, REQ-canonical-live-theo]

# Metrics
duration: ~30min
completed: 2026-04-29
---

# Phase 01 Plan 07: Pistol Anti-Eco DP Propagation Summary

**Closes CR-05 (BLOCKER) and WR-06 — DP forward-pass now updates pistol_winner_a at the round-1 boundary; anti-eco rounds {2, 3} dispatch correctly to GUN_WIN_RATE/1-GUN_WIN_RATE in both series_value (dp.py) and the future-map sub-DP (_within_map_p_a_wins in live_theo.py).**

## Performance

- **Duration:** ~30 min (excluding parallel-execution overhead)
- **Started:** 2026-04-29T16:30Z (approx)
- **Completed:** 2026-04-29T17:00Z (approx)
- **Tasks:** 6 (all completed; 6 atomic commits)
- **Files modified:** 5 (2 source, 3 test)

## Accomplishments

- **CR-05 closed in dp.py**: `_advance_round` now sets `pistol_winner_a[map_idx] = a_wins` when round 1 settles AND the slot is currently None. Tuple-rebuild preserves BO3State frozen+slots+hashable invariants. Anti-eco rounds {2, 3, 14, 15} in DP recursion now dispatch correctly via `round_types.round_p_for_round`, not the defensive 0.5 fallback.
- **WR-06 closed in live_theo.py**: `_within_map_p_a_wins` inline state-advance now propagates `pistol_winner_a` through its inner recursion via per-branch tuple-rebuild at the round-1 boundary. Memo key extended to `(a_round, b_round, side_orient, pistol)` — hashable and well-typed. The original `functools.lru_cache` docstring wording is preserved verbatim per checker fix I-08 (WR-07 stays deferred).
- **Test count: 147 -> 152**. New tests:
  - `test_dp_anti_eco_uses_gun_win_rate_after_round_1_branch` (test_dp.py) — RED on main, GREEN after CR-05 fix
  - `test_dp_anti_eco_returns_complement_after_b_wins_round_1` (test_dp.py) — RED on main, GREEN after CR-05 fix
  - `test_dp_advance_round_does_not_override_already_settled_pistol` (test_dp.py) — invariant lock for the don't-override guard (passes on main by accident; remains GREEN post-fix)
  - `test_within_map_anti_eco_uses_gun_win_rate_after_round_1_branch` (test_live_theo.py) — locks WR-06 closure via structural-ordering invariant
  - `test_live_theo_asymmetric_pistols_match_unset_pistols_after_dp_propagation` (test_live_theo.py) — end-to-end behavioral lock under TeamA=0.55/TeamB=0.45
- **Test renamed**: `test_anti_eco_with_none_pistol_winner_returns_defensive_05` -> `test_anti_eco_with_none_pistol_winner_returns_defensive_05_for_malformed_external_input` (assertion target unchanged; docstring re-scoped to document post-fix invariant).
- **Phase-2 follow-up documented** in `src/pricing/dp.py` module docstring as a NEW Phase-1 simplification: `pistol_winner_a` is keyed only by `map_idx`, so rounds 14/15 second-half pistol modeling is deferred to Phase 2 (REQ-round-event-data-pipeline). NO data-shape change in Phase 1.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add failing CR-05 regression test in test_dp.py (RED)** — `f4061dd` (test)
2. **Task 2: Fix CR-05 in dp._advance_round (GREEN)** — `4792ffa` (fix)
3. **Task 3: Fix WR-06 in live_theo._within_map_p_a_wins (GREEN)** — `47b387b` (fix)
4. **Task 4: Re-scope test_anti_eco_with_none_pistol_winner_returns_defensive_05** — `874d26c` (test)
5. **Task 5: Document second-half pistol Phase-2 follow-up in dp.py** — `8215a5a` (docs)
6. **Task 6: Final smoke gate + asymmetric-matchup integration test** — `15b822a` (test)

## Files Created/Modified

- `src/pricing/dp.py` — `_advance_round` updates `pistol_winner_a[map_idx]` at round-1 boundary via tuple-rebuild with don't-override guard; module docstring grows the bug-fix list with item 4 (CR-05) and adds a Phase 1 simplifications section documenting the second-half pistol Phase-2 follow-up.
- `src/pricing/live_theo.py` — `_within_map_p_a_wins` inline state-advance now propagates `pistol_winner_a` through its inner recursion; per-branch `pistol_after_a` / `pistol_after_b` tuples computed at the round-1 boundary; memo key extended to include the propagated tuple.
- `tests/pricing/test_dp.py` — added imports (`_advance_round`, `GUN_WIN_RATE`, `round_p_for_round`, `dataclass`, `Any`); added duck-typed `_FakeMatchState` / `_FakeHalfRates` fakes; added 3 CR-05 regression tests in section 7.
- `tests/pricing/test_live_theo.py` — added `_within_map_p_a_wins` to imports; added section 6 with 1 WR-06 regression test (structural ordering); added section 7 with 1 end-to-end behavioral integration test under asymmetric matchup.
- `tests/pricing/test_round_types.py` — re-scoped 1 existing test (rename + docstring update; assertion target unchanged); added `# noqa: E501` for the long function name.

## Decisions Made

- **Form A (inline rebuild) over Form B (delegate to `_advance_round`)** for the WR-06 fix in `_within_map_p_a_wins` — preserves the existing memo structure (which keys on per-recursion variables, not full BO3States) and matches the within-map idiom established in 01-05. The plan's preferred form per the action block.
- **Structural-ordering assertion form** for WR-06 and end-to-end tests — see "Deviations from Plan" below for rationale.
- **`# noqa: E501` for the renamed test name** — the function name `test_anti_eco_with_none_pistol_winner_returns_defensive_05_for_malformed_external_input` is 102 chars (>100 col limit). The plan's acceptance grep is exact-match, so the name cannot be shortened. The noqa is local to the def line only.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Replaced literal "law-of-total-probability decomposition" assertion with structural-ordering assertion in two tests**

- **Found during:** Task 3 (WR-06 fix) and Task 6 (end-to-end integration test)
- **Issue:** The plan's literal assertion form (`p_unset == p_round_1 * p_a_pistol + (1 - p_round_1) * p_b_pistol` with `rel_tol=1e-6` for Task 3; `theo_unset == p_round_1 * theo_set_AAA + (1 - p_round_1) * theo_set_BBB` with `rel_tol=1e-3` for Task 6) does not hold for the semantics of `_within_map_p_a_wins` / `LiveTheoEngine`. Calling these functions with `pistol=(None, True, None)` does NOT represent "the marginal conditional on A winning R1 of map 1" — instead, it forces `pistol[1]=True` for ALL R2/R3 dispatches in the recursion's own forward-pass, regardless of who actually wins R1 in either branch. The recursion still plays R1 with the half-rates blend in both branches; only R2..R24 are affected by the pistol assignment. So the decomposition equality is mathematically incorrect.
- **Numerical evidence:**
  - Task 3 (within-map level, `_within_map_p_a_wins` for map_idx=1, asymmetric synthetic half-rates): `p_unset = 0.617`, `p_a_pistol = 0.808`, `p_b_pistol = 0.420`, `p_round_1 = 0.54`. Expected per the plan's decomposition: `0.54 * 0.808 + 0.46 * 0.42 = 0.629`. Actual `p_unset = 0.617`, off by 0.012 — far exceeding `rel_tol=1e-6`.
  - Task 6 (engine level, `LiveTheoEngine` on TeamA=0.55/TeamB=0.45 with total=1e9): `theo_unset = 0.867`, `theo_set_AAA = 0.979`, `theo_set_BBB = 0.672`, `p_round_1 = 0.599`. Expected per the plan's decomposition: `0.599 * 0.979 + 0.401 * 0.672 = 0.856`. Actual `theo_unset = 0.867`, off by 0.011 — far exceeding `rel_tol=1e-3`.
- **Fix:** Replaced both assertions with structural-ordering forms that correctly capture the WR-06 / CR-05 invariant: `p_a_pistol > p_unset > p_b_pistol` (strict) plus a meaningful-gap check (`p_a_pistol - p_b_pistol > 0.05` for Task 3; `theo_set_AAA - theo_set_BBB > 0.1` for Task 6). Pre-fix, all three values converge to a flat-anti-eco baseline (the broken-vs-fixed contrast is captured by the strict inequality, which fails pre-fix).
- **Files modified:** `tests/pricing/test_live_theo.py` (Tasks 3 and 6 test bodies + docstrings).
- **Verification:** Both tests pass post-fix; manual probe confirms `theo_set_AAA = 0.9792 > theo_unset = 0.8675 > theo_set_BBB = 0.6725` with anti-eco swing 0.3067; the swing under symmetric half-rates is bounded by GUN_WIN_RATE - (1-GUN_WIN_RATE) = 0.644 across the two anti-eco rounds (rounds 2, 3), which empirically materializes as ~0.3 at the BO3 series level.
- **Committed in:** `47b387b` (Task 3) and `15b822a` (Task 6).

**2. [Rule 1 - Bug] Loosened plan's CR-05 end-to-end runtime probe (Step 6.3 third probe) — `swing < 0.05` form was unreachable**

- **Found during:** Task 6 (Step 6.3 manual probe)
- **Issue:** The plan's third runtime probe asserted `swing = abs(o_unset.theo_series - o_set.theo_series) < 0.05`. Post-fix, `o_unset = 0.867` and `o_set_AAA = 0.979`, swing = 0.111 — exceeds the assertion. The plan acknowledges in its RATIONALE block that "Hard-coded magnitude bounds like `> 0.96` are unreachable under the actual marginalization", so this assertion was already known to be problematic by the planner.
- **Fix:** Replaced with structural-ordering probe (same form as the integration test): `o_set_a > o_unset > o_set_b` strict ordering + `o_set_a - o_set_b > 0.1` meaningful gap.
- **Verification:** Probe prints `CR-05 end-to-end closed (AAA=0.9792, unset=0.8675, BBB=0.6725, AAA-BBB=0.3067)` and exits 0.
- **Note:** This probe is a manual verification step, not a test in the pytest suite — no commit attached. The structural-ordering assertion in the integration test (Task 6 Step 6.1, commit `15b822a`) is the load-bearing pytest version.

**3. [Rule 3 - Blocking] Cross-task interim failure of `test_p_map_decisive_sum_equals_one_pre_clinch` (resolved by Task 3)**

- **Found during:** Task 2 (Step 2.4 verification)
- **Issue:** After Task 2 fixed CR-05 in `_advance_round`, `_p_map_decisive` summed to 1.0023 (instead of 1.0) at the 0-0 root. The cause: Task 2 fixed CR-05 in `series_value` (current-map marginal) but `_within_map_p_a_wins` (future-map marginal) still had the WR-06 bug. The two paths produced inconsistent marginals, breaking the law-of-total-probability invariant.
- **Fix:** Task 3 closed WR-06 in `_within_map_p_a_wins`, restoring the law-of-total-probability invariant. The pre-existing test `test_p_map_decisive_sum_equals_one_pre_clinch` is GREEN at the end of Task 3 (and remains GREEN through Tasks 4-6).
- **Files modified:** none directly — the fix was Task 3's WR-06 closure.
- **Verification:** Final full-suite run reports 152 passed, including this test.
- **Note:** The plan didn't explicitly anticipate this interim failure; it's a natural consequence of the CR-05/WR-06 split into two tasks. The Task 2 commit message notes the interim failure for traceability.

---

**Total deviations:** 3 auto-fixed (3 Rule-1 / Rule-3 corrections to plan-mandated test assertions and inter-task dependencies)
**Impact on plan:** None of the fixes change the source-code outcome (CR-05 + WR-06 closure achieved exactly as specified). The test-assertion fixes correct mathematically-incorrect decomposition formulas in the plan with the structurally-equivalent ordering form that locks the same invariant. The inter-task dependency (Task 2 -> Task 3) is a natural consequence of the split into atomic commits; the final state at end of Task 3 satisfies all pre-existing test invariants.

## Issues Encountered

- The plan's literal "law-of-total-probability decomposition" form was identified as mathematically incorrect (see Deviation 1 numerical evidence). Resolved by switching to the structural-ordering form documented in the test docstrings.

## Self-Check: PASSED

Verified at end of plan execution:

- All 5 modified files exist on disk: `src/pricing/dp.py`, `src/pricing/live_theo.py`, `tests/pricing/test_dp.py`, `tests/pricing/test_live_theo.py`, `tests/pricing/test_round_types.py` — all FOUND.
- All 6 task commits exist in `git log --oneline -10`: `f4061dd`, `4792ffa`, `47b387b`, `874d26c`, `8215a5a`, `15b822a` — all FOUND.
- `pytest tests/` reports 152 passed, 0 failed.
- `mypy --strict src/pricing/` reports `Success: no issues found in 7 source files`.
- `ruff check src/pricing/ tests/pricing/` reports `All checks passed!`.
- `src.pricing.__all__ == ['LiveTheoEngine', 'TheoOutput', 'MatchState', 'HalfRates']` — public surface contract preserved.
- Forbidden audit-triplet symbols absent from `src/pricing/`.
- All three CR-05 runtime probes pass: round-2 dispatch (`p=0.8220`), round-3 dispatch (`p=0.8220`), end-to-end ordering (AAA>unset>BBB with swing 0.3067).
- CR-04 invariants preserved: `_clear_pricing_caches` in both dp.py and live_theo.py; try/finally in LiveTheoEngine.__call__; `test_no_memory_leak_across_live_theo_calls` STILL passes.

## Next Phase Readiness

**For the Phase 4 planner:** The pistol+anti-eco model is now structurally active in the DP forward-pass for the natural pre-match call site. `VEGA_DIRECTIONAL_THRESHOLD = 0.04` and `KILL_SWITCH_DEVIATION_C = 20¢` operate on accurate `theo_series` values; the previously-systematic 9.25pp bias at TeamA=0.55/TeamB=0.45 between unset-pistols and set-pistols is closed (post-fix unset = 0.867 lies between set_AAA = 0.979 and set_BBB = 0.672, reflecting a true marginalization rather than the pre-fix flat-anti-eco baseline).

**For the Phase 2 planner:** The second-half pistol limitation (rounds 14/15 dispatch on `pistol_winner_a[map_idx]` which is the FIRST-half pistol winner) is documented as a Phase-2 follow-up in `src/pricing/dp.py` module docstring. Phase 2 will extend the data shape to `tuple[Optional[tuple[bool, bool]], ...]` per (map, half) and update the `round_types.py` dispatch to consult the appropriate half. NO data-shape change required in Phase 1.

**Out-of-scope items still deferred** (no scope creep):

- WR-07 (`_within_map_p_a_wins` docstring's `functools.lru_cache` claim — implementation uses dict; docstring still says lru_cache per checker fix I-08)
- WR-08 (per-`m` re-registration in `_p_reach_map` defeats `lru_cache` reuse — perf, out of v1 scope)
- IN-05..IN-07 (style/maintainability papercuts)
- WR-01..WR-05 + IN-01..IN-04 (already deferred per 01-06 plan)
- Extending `pistol_winner_a` to `tuple[Optional[tuple[bool, bool]], ...]` per (map, half) — Phase 2 task; flagged via doc note only in this plan

---
*Phase: 01-core-pricing-engine*
*Plan: 07*
*Completed: 2026-04-29*
