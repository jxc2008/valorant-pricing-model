---
phase: 03-live-ingestion-layer
plan: "02"
subsystem: pricing
tags: [round-conclusion, post-plant, dispatch, schema-version, mypy-strict, live-theo, v2-surface]

requires:
  - phase: 03-live-ingestion-layer
    provides: 03-00 RED-stub test scaffolds (test_round_conclusion_v2.py / test_live_theo_dispatch.py); 03-01 MatchState v2 19-field set with bomb_planted / attackers_alive / defenders_alive / time_left_s populated when post-plant
  - phase: 02-round-event-data
    provides: Phase 2 D-13 Bayesian shrinkage (SHRINK_PRIOR=15) — preserved verbatim on the v2 _Cell payload
  - phase: 01-core-pricing-engine
    provides: D-20 LiveTheoEngine bundle pattern + state-only call surface (CRule 1 / DEC-010); _RoundPFnImpl between-round closure
provides:
  - "src/pricing/round_conclusion.py — v2 RoundConclusionLookup surface (between_round_p + post_plant_p + BetweenRoundFn + PostPlantFn Protocols + schema_version=2 JSON gate + 5-tier hierarchical walk)"
  - "src/pricing/live_theo.py — _live_theo_impl dispatches on state.bomb_planted (D-05); LiveTheoEngine.round_conclusion now REQUIRED RoundConclusionLookup"
  - "models/round_conclusion.json — v2 schema_version=2 file with empirical Phase 2 side_baseline + one synthetic cells_full cell (3, 2, 0, atk, Lotus) for dispatch test (real ~25k-sample calibration replaces this in 03-07)"
  - "v2 constants in src/config/constants.py — POST_PLANT_TIMER_S=45.0, TIME_BUCKET_WIDTH_S=5.0, ROUND_CONCLUSION_JSON_PATH (Task 1 / commit cc70aa0)"
  - "src/pricing/economy.py DELETED per CLAUDE.md 'Economy buckets — DEPRECATED in v2' (Task 1 / commit cc70aa0)"
affects: [03-03-arbiter-and-latency, 03-04-scoreboard-poller, 03-05-ocr-pipeline, 03-07-etl-rerun-and-calibration, 03-08-e2e-gate]

tech-stack:
  added: []
  patterns:
    - "Two-method round-conclusion surface (D-04): between_round_p (direct side_baseline lookup, no walk) + post_plant_p (5-tier hierarchical walk cells_full -> cells_no_time -> cells_no_map -> cells_minimal -> side_baseline). Cells keyed on (att, def_, time_bucket, side, map_name) — economy bucket dimension cut per CLAUDE.md v2."
    - "schema_version hard-gate (D-06): RoundConclusionLookup.from_json HARD-FAILS on schema_version != 2 (raises ValueError). Atomic-replace migration; v1 file recoverable via git history. _SCHEMA_VERSION_V2 module constant gates both read and write."
    - "live_theo D-05 dispatch: state.bomb_planted=True overrides ONLY the current round's p via post_plant_p; future-round transitions ALWAYS use between-round semantics (no nested post-plant lookups in the recursion). Defensive None-guard for malformed bomb_planted=True states degrades to between-round path with low confidence — Phase 4 mode-selector maps to IDLE."
    - "Phase 1+2 regression strategy: Phase 1+2 LiveTheoEngine tests patched in-place (every LiveTheoEngine(half_rates=hr) callsite passes round_conclusion=RoundConclusionLookup()); calibrator-flavored tests (tests/calibration/test_d05_partial_pass / test_from_json_roundtrip / test_shrinkage_walk) xfailed with TODO 03-07."

key-files:
  created:
    - "tests/pricing/test_live_theo_dispatch.py — 3 GREEN tests (test_dispatch_bomb_planted, test_dispatch_between_round, test_dispatch_bomb_planted_with_missing_post_plant_fields_falls_back) replacing 2 RED-stub xfails from Wave 0"
  modified:
    - "src/pricing/round_conclusion.py — wholesale rewrite to v2 surface (~370 LOC; v1 RoundConclusionFn / lookup() / cells_no_econ DELETED; between_round_p + post_plant_p + BetweenRoundFn + PostPlantFn + _SCHEMA_VERSION_V2 ADDED)"
    - "src/pricing/live_theo.py — bomb_planted dispatch in _live_theo_impl per D-05; LiveTheoEngine.round_conclusion type changed from Optional[RoundConclusionLookup] to required RoundConclusionLookup; POST_PLANT_TIMER_S + TIME_BUCKET_WIDTH_S imported"
    - "models/round_conclusion.json — atomic-replaced with schema_version=2 + side_baseline {atk: 0.5256, def: 0.4751} (Phase 2 empirical) + one synthetic cells_full cell at (3, 2, 0, atk, Lotus) for dispatch test"
    - "tests/pricing/test_round_conclusion.py — rewritten in-place to v2 surface (cells_full hierarchy walks rekeyed; v1 cell counts removed; round-trip + Path-C compat preserved under v2 schema)"
    - "tests/pricing/test_round_conclusion_v2.py — 4 GREEN tests (test_post_plant_p_hierarchy + test_from_json_rejects_v1 + test_from_json_rejects_explicit_v1 + test_between_round_p_returns_side_baseline) replacing 3 RED-stub xfails from Wave 0"
    - "tests/pricing/test_round_conclusion_loader.py — rewritten to v2 post_plant_p surface; new test_loaded_v2_lookup_has_synthetic_lotus_cell asserts the synthetic Lotus cell shifts off baseline"
    - "tests/pricing/test_live_theo.py — every LiveTheoEngine(half_rates=hr) callsite patched to pass round_conclusion=RoundConclusionLookup(); _live_theo_impl(state, hr, None) -> _live_theo_impl(state, hr, RoundConclusionLookup()); test renamed test_live_theo_engine_accepts_optional_round_conclusion -> test_live_theo_engine_accepts_round_conclusion_lookup"
    - "tests/pricing/test_live_theo_with_calibrated_round_conclusion.py — engine constructor passes lookup directly (not lookup.lookup); test_calibrated_lookup_returns_finite_value_for_in_distribution_key rekeyed to v2 post_plant_p with synthetic-cell hit assertion"
    - "tests/calibration/test_d05_partial_pass.py / test_from_json_roundtrip.py / test_shrinkage_walk.py — xfailed in-place with TODO 03-07 (v1 cells_no_econ + 5-key cells_full deleted; v2 calibrator + ETL re-run rewrite is 03-07's scope)"

key-decisions:
  - "v2 cells_full key shape (D-04): (att, def_, time_bucket, side, map_name). Cuts economy bucket dimension per CLAUDE.md 'Economy buckets — DEPRECATED in v2' and adds time_bucket per D-10 (5s buckets across 45s post-plant timer; 9 buckets total)."
  - "Field order on RoundConclusionLookup dataclass: side_baseline FIRST (positional). Lets callers construct RoundConclusionLookup({'atk': 0.6, 'def': 0.4}) without keyword arguments — matches the test_dispatch_between_round + test_between_round_p_returns_side_baseline call sites in the plan."
  - "schema_version=2 hard-fail (D-06) instead of soft-migrate: from_json raises ValueError on missing or non-2 schema_version; v1 file recoverable via git history. Atomic-replace at same path keeps the lookup-load contract simple — Phase 4's engine init does not need a multi-version dispatcher."
  - "Future-round transitions in the bomb_planted branch use between-round fn closure, NOT nested post-plant lookups (D-05). A nested post-plant lookup would (a) require alive-counts at every future round (impossible — those are post-plant-event state) and (b) blow up the cache key space. The single current-round override matches DEC-018's one-step branch composition pattern."
  - "Defensive None-guard for malformed bomb_planted=True states: when attackers_alive / defenders_alive / time_left_s are None despite bomb_planted=True (data race or arbiter bug), _live_theo_impl falls back to the between-round path. The mode-selector in Phase 4 reads the resulting low confidence and maps to IDLE — no production trades fire on malformed state."
  - "Asymmetric HalfRates fixture in test_dispatch_bomb_planted: under symmetric rates the DP delivers v(state_after_a_wins) == v(state_after_b_wins) by symmetry, so the dispatch override (p_round != p_internal) becomes structurally invisible (p*v + (1-p)*v == v). The fixture uses TeamA at 0.6 / TeamB at 0.4 to break the symmetry; the documentation is inline so future executors don't try to revert to symmetric rates."
  - "Direction of bp_theo vs br_theo not load-bearing: the dispatch sign depends on whether the cell's shrunk p is greater or less than the DP's between-round p_round_internal. With cell.p_hat=0.95 > internal_blend(0.6, 0.4) ~0.69, bp_theo > br_theo — but if a future calibration shipped cells with p_hat below internal_blend, the sign would flip. The test asserts |bp_theo - br_theo| > 1e-3 (the 03-08 E2E gate's >=1¢ post-plant-shifts-theo criterion)."

patterns-established:
  - "v2-decisive surface migration: when an upstream design pivot makes a v1 surface schema-incompatible, the v1 method is DELETED in the same atomic commit as the v2 surface lands. Frozen-surface contracts (Phase 2 D-15) are intentionally broken — there is no value in keeping a v1 method against a v2 schema. v1 fall-out (deprecated calibrator tests) gets xfailed with a TODO pointer to the wave that resurfaces them."
  - "Bayesian shrinkage payload (n, p_hat, parent_p) is RE-USABLE across schema rekeys. _Cell unchanged from v1 — only the dict key tuples change. SHRINK_PRIOR=15 imported from src.config.constants (CRule 12); the formula stays in one place."

requirements-completed: [REQ-round-conclusion-lookup]

# Metrics
duration: 6h 49m wall-clock (~30 min active work; spawn happened mid-day with idle gaps between Task 1 and Tasks 2-3)
completed: 2026-05-08
---

# Phase 3 Plan 02: Round-Conclusion v2 Surface Summary

**Wholesale rewrite of RoundConclusionLookup to the v2 (att, def, time_bucket, side, map) keying with two callable methods (between_round_p + post_plant_p), live_theo bomb_planted dispatch per D-05, and atomic schema_version=2 migration of models/round_conclusion.json — REQ-round-conclusion-lookup GREEN.**

## Performance

- **Duration:** 6h 49m wall-clock (Task 1 cc70aa0 landed at 08:15 EDT; Tasks 2+3 actively worked 14:43–15:04 EDT, ~21 min). Most of the wall-clock was idle between Task 1 (yesterday session) and Tasks 2/3 (today session).
- **Started:** 2026-05-08T12:15:11Z (Task 1 commit cc70aa0)
- **Completed:** 2026-05-08T19:04:40Z (Task 3 commit a519023)
- **Tasks:** 3
- **Files modified:** 14 (1 created — tests/pricing/test_live_theo_dispatch.py was upgraded from xfail stub to GREEN; 13 modified across src/, tests/, models/)

## Accomplishments

- **REQ-round-conclusion-lookup GREEN.** SPEC §7 acceptance criteria satisfied:
  1. v2 schema_version=2 file lives at `models/round_conclusion.json` and HARD-FAILS load on any other schema_version (test_from_json_rejects_v1 + test_from_json_rejects_explicit_v1).
  2. `RoundConclusionLookup.between_round_p(side, map, round_idx)` and `.post_plant_p(att, def_, time_bucket, side, map)` are callable, type-checked under `mypy --strict src/pricing`.
  3. v1 `lookup()` method + `RoundConclusionFn` Protocol + `cells_no_econ` field DELETED — no remaining call sites in src/.
  4. `live_theo` dispatches on `state.bomb_planted` per D-05 (test_dispatch_bomb_planted + test_dispatch_between_round + test_dispatch_bomb_planted_with_missing_post_plant_fields_falls_back).
- **DEC-007 v2 two-path round-conclusion implemented; CRule 6a "two clean code paths in live_theo" satisfied.** Between-round path uses `series_value(bo3, fn)` with the standard between-round closure. Post-plant path overrides the current round's p with `post_plant_p(...)`, then composes `p_round * series_value(state_after_a, fn) + (1 - p_round) * series_value(state_after_b, fn)` — future-round transitions ALWAYS use between-round semantics.
- **Atomic-replace JSON migration.** `models/round_conclusion.json` carries `schema_version: 2`, the empirical side_baseline from Phase 2 (`{atk: 0.5256, def: 0.4751}`), and one synthetic populated cell at `(3, 2, 0, atk, Lotus)` (`shrunk = (100*0.7 + 15*0.5256)/115 = 0.6817`). 03-07 (calibrator + ETL re-run) replaces the synthetic cell with the real ~25k-sample v2 calibration.
- **Phase 1+2 regression GREEN under v2 surface.** All 250 tests pass / 40 xfailed (was 243 / 34 at the start of plan 03-02; +7 net GREEN tests across test_round_conclusion_v2 + test_round_conclusion + test_round_conclusion_loader + test_live_theo_dispatch; +6 xfails across tests/calibration/ for the v1 calibrator-flavored tests pointing at 03-07 rewrite).
- **Single canonical pricing entry point preserved.** `LiveTheoEngine(half_rates, round_conclusion)(state) → TheoOutput` per D-20 / DEC-010 / CRule 1. The only call-surface change is that `round_conclusion` is now REQUIRED (no Optional default).

## Task Commits

1. **Task 1: Add v2 round-conclusion constants + delete economy.py per CLAUDE.md** — `cc70aa0` (feat) — already landed before this plan-execution session.
2. **Task 2: Rewrite RoundConclusionLookup to v2 surface + atomic-replace round_conclusion.json (D-04/D-06)** — `3005709` (feat).
3. **Task 3: live_theo bomb_planted dispatch (D-05) + Phase 1+2 regression patch** — `a519023` (feat).

**Plan metadata commit:** to follow (this SUMMARY.md + STATE.md + ROADMAP.md update).

## Files Created/Modified

### Created
- `tests/pricing/test_live_theo_dispatch.py` — 3 GREEN tests for the D-05 dispatch (replaces the 2-test xfail stub from Wave 0; one extra defensive None-guard test added).

### Modified

**Source code (3 files):**
- `src/pricing/round_conclusion.py` — wholesale rewrite to v2 surface (~370 LOC); v1 `RoundConclusionFn` Protocol + 5-arg `lookup()` method + `cells_no_econ` field + `_PHASE_1_FLAT_CELL_VALUE` constant + v1 key (de)serializers DELETED; v2 surface (`BetweenRoundFn` + `PostPlantFn` Protocols + `between_round_p` + `post_plant_p` methods + `cells_no_time` field + `_SCHEMA_VERSION_V2` constant + new key (de)serializers) ADDED.
- `src/pricing/live_theo.py` — `_live_theo_impl` dispatches on `state.bomb_planted` per D-05; `LiveTheoEngine.round_conclusion` is now required `RoundConclusionLookup` (Optional default removed); imports `POST_PLANT_TIMER_S`, `TIME_BUCKET_WIDTH_S` from constants.
- `models/round_conclusion.json` — atomic-replaced with v2 file (schema_version=2, empirical side_baseline, one synthetic cells_full cell).

**Tests (8 files):**
- `tests/pricing/test_round_conclusion.py` — rewritten in-place to v2 surface; v1 lookup tests renamed to `test_post_plant_p_*` and rekeyed; round-trip + Path-C compat preserved.
- `tests/pricing/test_round_conclusion_v2.py` — 4 GREEN tests replacing 3 RED-stubs from Wave 0.
- `tests/pricing/test_round_conclusion_loader.py` — `test_loaded_lookup_post_plant_returns_in_range` (v2 hypothesis); `test_loaded_v2_lookup_has_synthetic_lotus_cell` (synthetic-cell shift assertion).
- `tests/pricing/test_live_theo.py` — every `LiveTheoEngine(half_rates=hr)` callsite patched to pass `round_conclusion=RoundConclusionLookup()`; `_live_theo_impl(state, hr, None)` patched to pass an empty lookup; test rename `test_live_theo_engine_accepts_optional_round_conclusion` → `test_live_theo_engine_accepts_round_conclusion_lookup`.
- `tests/pricing/test_live_theo_with_calibrated_round_conclusion.py` — engine constructor passes lookup directly (not `lookup.lookup`); calibrated-lookup integration test rekeyed to v2 `post_plant_p` with synthetic-cell hit assertion.
- `tests/calibration/test_d05_partial_pass.py` — every test xfailed with TODO 03-07 (v1 calibrator + cells_no_econ deleted; v2 calibrator rewrite pending).
- `tests/calibration/test_from_json_roundtrip.py` — every test xfailed with TODO 03-07 (v2 round-trip coverage relocated to tests/pricing/test_round_conclusion.py).
- `tests/calibration/test_shrinkage_walk.py` — every test xfailed with TODO 03-07.

## Decisions Made

- **v2 surface DELETES v1 in the same commit** (no compatibility shim). Phase 2's frozen-surface contract (D-15) is broken intentionally — there is no value in keeping a v1 5-arg `lookup()` against a v2 (att, def_, time_bucket, side, map) schema. The PRD/CONTEXT explicitly reject parallel models (CRule 1 / DEC-010).
- **Field order on `RoundConclusionLookup`: side_baseline first, positional with default_factory.** Lets callers construct `RoundConclusionLookup({"atk": 0.6, "def": 0.4})` without keyword arguments — matches the test_dispatch_between_round + test_between_round_p_returns_side_baseline call shape from the plan body.
- **Future-round transitions ALWAYS use between-round semantics in the bomb_planted branch** (D-05). Nested post-plant lookups would require alive-counts at every future round (impossible — those are post-plant event state, not predictable from bo3 state) and would blow up the cache key space.
- **Defensive None-guard, not a hard error.** `bomb_planted=True` with missing `attackers_alive`/`defenders_alive`/`time_left_s` falls back to the between-round path with degraded confidence; Phase 4's mode-selector reads the low confidence and maps to IDLE per DEC-001 v2. A hard error would crash the live engine on data races between the OCR worker and the arbiter; quiet fallback is safer.
- **Direction of bp_theo vs br_theo not asserted in test_dispatch_bomb_planted.** The dispatch sign depends on whether the cell's shrunk p is greater or less than the DP's between-round p_round_internal. The test asserts only `|bp_theo - br_theo| > 1e-3` (the 03-08 E2E gate's ≥1¢ post-plant-shifts-theo criterion). This is robust to future calibrations that ship cells with arbitrary directional bias.
- **Asymmetric HalfRates fixture documented inline.** The pre-Task-3 attempt used symmetric rates, and the test failed because `v(state_after_a_wins) == v(state_after_b_wins)` by symmetry → `p * v + (1-p) * v == v` → dispatch override invisible. The fixture switched to TeamA at 0.6 / TeamB at 0.4 to break that symmetry. Comment block in `_make_half_rates` flags the trap so future executors don't revert.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Pre-existing v1-surface tests block Task 2 verify gate.**
- **Found during:** Task 2 verify (broader pytest run).
- **Issue:** `tests/pricing/test_round_conclusion_loader.py`, `tests/calibration/test_d05_partial_pass.py`, `tests/calibration/test_from_json_roundtrip.py`, `tests/calibration/test_shrinkage_walk.py` all referenced the deleted v1 surface (`lookup.lookup(...)` 5-arg call, `cells_no_econ` field). The plan's regression strategy explicitly called out the calibrator-flavored tests for xfail; the loader test was rewritten to v2.
- **Fix:** Rewrote `tests/pricing/test_round_conclusion_loader.py` to v2 `post_plant_p` surface (3 GREEN tests + 1 new `test_loaded_v2_lookup_has_synthetic_lotus_cell`). Replaced `tests/calibration/test_d05_partial_pass.py` body with xfail stubs (3 tests). Replaced `tests/calibration/test_from_json_roundtrip.py` body with xfail stubs (4 tests). Replaced `tests/calibration/test_shrinkage_walk.py` body with xfail stubs (4 tests).
- **Files modified:** see list above.
- **Verification:** Task 2 commit's `pytest tests/pricing/ tests/calibration/` returns 169 passed / 21 xfailed (was 161 passed / 13 xfailed before plan 03-02).
- **Committed in:** `3005709` (Task 2 commit).

**2. [Rule 1 - Bug] Initial test_dispatch_bomb_planted fixture used symmetric HalfRates and the dispatch was structurally invisible.**
- **Found during:** Task 3 first pytest run.
- **Issue:** With `HalfRates(team_rates={}, league_rates={}, overall_avg=0.5)`, the DP delivers `v(state_after_a) == v(state_after_b)` by symmetry. The dispatch override changes only the weighting between two equal values → `p*v + (1-p)*v == v` for any p → bp_theo and br_theo collapse to the same value (0.63671875 in the failing run).
- **Fix:** Switched the fixture to asymmetric rates (TeamA 0.6 / TeamB 0.4 with 1000 samples). The DP now produces `v_a != v_b` and the dispatch override translates into a measurable theo shift. Documented the trap inline in `_make_half_rates` so future executors don't revert. Also relaxed the direction-of-shift assertion (cell.p_hat=0.95 vs internal_blend ~0.69 means bp_theo could be either greater or less than br_theo depending on calibration; the test asserts only `|diff| > 1e-3`, which matches the 03-08 E2E gate).
- **Files modified:** `tests/pricing/test_live_theo_dispatch.py`.
- **Verification:** All 3 dispatch tests GREEN.
- **Committed in:** `a519023` (Task 3 commit).

**3. [Rule 3 - Blocking] Test name `test_live_theo_engine_accepts_optional_round_conclusion` falsely advertised "optional" parameter.**
- **Found during:** Task 3 (`round_conclusion` made required).
- **Issue:** The test name and docstring described an optional parameter; Task 3 made `round_conclusion` REQUIRED on `LiveTheoEngine`. Leaving the misleading name would lie about the contract.
- **Fix:** Renamed `test_live_theo_engine_accepts_optional_round_conclusion` → `test_live_theo_engine_accepts_round_conclusion_lookup`. Docstring rewritten to describe the now-required parameter.
- **Files modified:** `tests/pricing/test_live_theo.py`.
- **Verification:** test passes; ruff clean.
- **Committed in:** `a519023` (Task 3 commit).

---

**Total deviations:** 3 auto-fixed (2 blocking, 1 bug — symmetric-fixture invisibility).
**Impact on plan:** Deviations 1 + 3 are pre-existing technical debt surfaced by the v1-surface deletion; both are anticipated by the plan's regression strategy (xfail calibrator tests pointing at 03-07; rewrite Phase 2 LiveTheoEngine integration tests to v2). Deviation 2 was a one-shot test bug caught by the first GREEN run. No scope creep; no architectural change.

## Authentication Gates

None — no external services touched.

## Issues Encountered

None blocking. The plan's regression-strategy preview was accurate: v1-surface tests bifurcated into "rewrite to v2" (LiveTheoEngine integration tests, `test_round_conclusion_loader.py`) vs "xfail with TODO 03-07" (calibrator-script integration tests). The rib.gg/Phase 2 calibrated-lookup tests work GREEN under the synthetic v2 file because the loader skips path-not-exists cases automatically.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

Plan 03-03 (arbiter + latency) is unblocked:
- Wave 3A's arbiter consumes `state.bomb_planted` + `state.attackers_alive` + `state.defenders_alive` + `state.time_left_s` — all four fields exist on MatchState v2 (03-01) and are consumed by `_live_theo_impl`'s D-05 dispatch path (this plan).
- The synthetic v2 cell at `(3, 2, 0, atk, Lotus)` produces a measurable theo shift, so the 03-08 E2E gate's "post-plant shifts theo by ≥1¢" acceptance has a structurally-witnessed lower bound (~0.16 off baseline at the populated cell; the dispatch test asserts >1e-3 in the integrated theo).

Plan 03-04 / 03-05 / 03-06 (scoreboard / OCR / text listener) are likewise unblocked — they only need a stable `RoundConclusionLookup` import surface, which this plan provides.

Plan 03-07 (ETL re-run + v2 calibration) is unblocked AND has the explicit xfail TODOs to clear:
- `tests/calibration/test_calibrate_round_conclusion.py` (8 tests xfailed in Task 1).
- `tests/calibration/test_d05_partial_pass.py` (3 tests xfailed in Task 2).
- `tests/calibration/test_from_json_roundtrip.py` (4 tests xfailed in Task 2).
- `tests/calibration/test_shrinkage_walk.py` (4 tests xfailed in Task 2).
03-07 rewrites the calibrator end-to-end against the v2 ETL re-run dataset and clears these xfails.

Plan 03-08 (E2E gate) is unblocked — the dispatch path is exercised, the synthetic cell gives a measurable theo shift, and the integration test scaffold (`tests/ingestion/test_e2e.py`) is RED-stubbed from Wave 0 ready for Wave 4 to flip to GREEN.

## Self-Check: PASSED

- src/pricing/round_conclusion.py exists with v2 surface (verified via Grep: `between_round_p`, `post_plant_p`, `_SCHEMA_VERSION_V2`, `cells_no_time` all present; v1 surface mentioned only in deletion-history docstring lines).
- src/pricing/live_theo.py imports POST_PLANT_TIMER_S + TIME_BUCKET_WIDTH_S; `state.bomb_planted` dispatch present; `LiveTheoEngine.round_conclusion: RoundConclusionLookup` (no Optional default).
- models/round_conclusion.json has schema_version=2 + the synthetic Lotus cell (verified via `python -c "from src.pricing.round_conclusion import RoundConclusionLookup; rc = RoundConclusionLookup.from_json('models/round_conclusion.json'); assert (3, 2, 0, 'atk', 'Lotus') in rc.cells_full"`).
- All 3 task commits reachable via `git log --oneline --all`: `cc70aa0` (Task 1), `3005709` (Task 2), `a519023` (Task 3).
- `pytest tests/` 250 passed / 40 xfailed.
- `mypy --strict src/pricing src/state` clean.
- `ruff check src tests scripts` clean.

---
*Phase: 03-live-ingestion-layer*
*Completed: 2026-05-08*
