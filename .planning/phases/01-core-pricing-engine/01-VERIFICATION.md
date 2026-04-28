---
phase: 01-core-pricing-engine
verified: 2026-04-28T21:15:00Z
status: gaps_found
score: 2/3 must-haves verified
overrides_applied: 0
gaps:
  - truth: "Phase 1 must-have #1 — `live_theo(state)` returns `TheoOutput(theo_series, theo_map, vega, confidence)`; no other pricing entry points exist; LiveTheoEngine bundle is the only API surface."
    status: partial
    reason: |
      The single-entry-point surface is correctly locked (LiveTheoEngine is the only public callable; forbidden audit-triplet symbols are absent from src/pricing/; __all__ is exactly the four names; mypy --strict + 137/137 tests pass). However, two of the four TheoOutput fields — `confidence` and `vega` — are computed by derived-output machinery that contains confirmed correctness bugs (CR-01, CR-02, CR-03 from 01-REVIEW.md), so the values populated into TheoOutput are not mathematically correct in a non-trivial portion of the BO3 state space. The PHASE GOAL is "between-round live pricing works end-to-end." The engine runs end-to-end, returns TheoOutput, and the surface contract holds; the values inside two fields are unreliable in OT-entry and future-map states.
    artifacts:
      - path: "src/pricing/live_theo.py:469-474"
        issue: "_p_reach_map_cached terminal-check ordering: returns 1.0 for clinched series at map_idx==m before the a_map_score>=2 / b_map_score>=2 short-circuit fires. Verified at runtime: _p_reach_map(BO3State(map_idx=2,a_map_score=2,...), fn, m=2) returns 1.0 (expected 0.0). Inflates p_decisive(map=2) → poisons _compute_confidence whenever any path through the recursion lands at the post-clinch m-equal-map_idx state."
      - path: "src/pricing/live_theo.py:424-428"
        issue: "_p_map_decisive uses `p_reached * 0.5` BO5+ placeholder for the BO3 middle map (m == state.map_idx + 1 and m != len(map_pool)-1). In a BO3 with map_pool of length 3, state.map_idx=0 and m=1 falls into this branch. Verified at runtime: _p_map_decisive(state at map_idx=0, m=1) returns 0.5 (the placeholder), not the correct P(map 1 is decisive)."
      - path: "src/pricing/live_theo.py:539-545"
        issue: "_compute_vega calls _advance_round(root, ...) unconditionally at OT-entry states (a_round=12, b_round=12, total=24). _advance_round produces (13, 12) and (12, 13) — both past the DP's OT hard-stop. Both advanced states hit the WIN_THRESHOLD map terminal in _series_value_cached, completely skipping the OT-as-coinflip leaf documented in DEC-009 / CRule 5. Verified at runtime: _compute_vega(BO3State(a_round=12, b_round=12, ...), fn) returns ~0.054 (a non-zero squared-deviation against next-map series values rather than the OT-leaf variance)."
    missing:
      - "Reorder _p_reach_map_cached terminal checks so the series-clinch short-circuit (a_map_score>=2 or b_map_score>=2 → 0.0) precedes the map_idx==m check, then add regression test test_p_reach_map_zero_for_clinched_series_state."
      - "Replace the `p_reached * 0.5` BO5+ placeholder in _p_map_decisive case 3 with the correct BO3 middle-map formula `p_reached * (p(prev_winner) * p(curr_winner) + (1 - p(prev_winner)) * (1 - p(curr_winner)))`, or equivalent. Add tests covering m=1 from state.map_idx=0 with non-trivial p values."
      - "Short-circuit _compute_vega at series terminals, within-map terminals, and OT-entry (a_round + b_round >= REGULATION_HALF * 2). At OT-entry, return the variance of the OT coinflip leaf over next-map series outcomes (0.5 * (v_a-mean)^2 + 0.5 * (v_b-mean)^2) rather than calling _advance_round past the hard-stop. Add test_compute_vega_at_ot_entry_uses_coinflip_leaf."
      - "(Operational) Either make _RoundPFnImpl + MatchState fully hashable and drop the _ROUND_P_FNS / _REACH_MAP_FNS registries, OR clear the registries + _series_value_cached + _p_reach_map_cached at the end of every LiveTheoEngine.__call__. CR-04 leak is bounded for Phase 1's between-round single-call use case but breaks Phase 4's continuous-running quoter."
human_verification: []
---

# Phase 1: Core Pricing Engine Verification Report

**Phase Goal:** Single canonical `live_theo(state) → (theo_series, theo_map, vega, confidence)` with no data dependencies — between-round live pricing works end-to-end.
**Verified:** 2026-04-28T21:15:00Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #   | Truth                                                                                                                                                                                                                                                                            | Status     | Evidence       |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- | -------------- |
| 1   | Must-have 1: `live_theo(state)` returns a `TheoOutput` dataclass with `theo_series, theo_map, vega, confidence`; no other pricing entry points exist (DEC-010); switching to/from MatchState→TheoOutput is the only API surface for the math layer. | ⚠️ PARTIAL | Surface-level locked: `LiveTheoEngine` exists with `__call__(MatchState) -> TheoOutput`; `src/pricing/__all__ == ["LiveTheoEngine", "TheoOutput", "MatchState", "HalfRates"]`; `grep -RE "^def series_theo\|^def series_theo_no_sides\|^def series_theo_from_map_probs\|^def model_series_prob\|^def _signal_strength" src/pricing/` returns no matches (exit 1, confirmed); end-to-end `engine(state)` runs and returns a `TheoOutput` with all four fields populated and in declared ranges. **However**, the values inside `vega` and `confidence` are computed by buggy derived-output machinery (CR-01, CR-02, CR-03 from 01-REVIEW.md, all confirmed at runtime — see Anti-Patterns section). The "API surface is the only one" half is fully met; the "values are correct" half is not. |
| 2   | Must-have 2: Four documented audit-engine bugs are fixed: Bradley-Terry blend (DEC-003), OT hard-stop at total=24 (DEC-009), pistol/anti-eco modeled with separate inputs (DEC-011), conviction clips at [0.01, 0.99] (DEC-012). | ✓ VERIFIED | (a) BT blend: `src/pricing/blend.py:59` ships `(a * (1.0 - b)) / (a * (1.0 - b) + (1.0 - a) * b)` with input clip; arithmetic-mean form absent (regression-locked by `test_blend_source_does_not_contain_arithmetic_mean_form`). (b) OT hard-stop: `src/pricing/dp.py:207` `if state.a_round + state.b_round == REGULATION_HALF * 2: return _ot_coinflip_leaf(state, round_p_id)`; `range(26)` and `range(WIN_THRESHOLD * 2)` absent from source (regression-locked). (c) Pistol/anti-eco: `src/pricing/round_types.py:140-153` dispatches rounds {1,13} → half-rates blend, {2,3,14,15} → `GUN_WIN_RATE if pistol_won_by_a else 1.0 - GUN_WIN_RATE`, gunrounds → blend; verified at runtime (`round 2 (A won pistol): 0.822`). (d) Conviction clip: `src/pricing/live_theo.py:280-282` `_clip_conviction` clips to `[CONVICTION_CLIP_LOW, CONVICTION_CLIP_HIGH] = [0.01, 0.99]`; applied to theo_series and each theo_map[i]. **Caveat on DEC-009 propagation**: the OT hard-stop is correctly enforced inside `_series_value_cached`, but CR-03 demonstrates `_compute_vega` calls `_advance_round` past the hard-stop without re-checking, so the vega derived output silently bypasses the leaf. The PRIMARY DP recursion correctly hard-stops; a SECONDARY consumer (vega) violates the spirit of the rule. |
| 3   | Must-have 3: Property tests pass — DP value ∈ [0,1] for any state; symmetric inputs match `p²(3−2p)` closed form; Bradley-Terry symmetry `round_p(a, b) == 1 − round_p(b, a)`; `theo_series` consistent with sum over `theo_map[]` outcomes (REQ-unit-and-property-tests subset). | ✓ VERIFIED | `pytest tests/` reports `137 passed`. Specific tests confirmed present and passing: `test_dp_value_in_unit_interval` (hypothesis, max_examples=50), `test_dp_symmetric_input_matches_closed_form` (hypothesis, uses `_bo3_series_prob`), `test_round_p_bradley_terry_symmetry` (hypothesis), `test_live_theo_marginalization_consistency_dec002` (theo_series ↔ theo_map[] consistency under marginalization). `mypy --strict src/pricing/` exits 0 (`Success: no issues found in 7 source files`). |

**Score:** 2/3 truths verified (1 partial counted as gap)

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `src/config/constants.py` | 4 new Phase 1 constants (`CONVICTION_CLIP_LOW`, `CONVICTION_CLIP_HIGH`, `MIN_ROUNDS_FULL_WEIGHT`, `BT_BLEND_EPSILON`) with `Final[...]` annotations | ✓ VERIFIED | Lines 79-107 — all four present with `Final[float]`/`Final[int]` and `Source:` docstrings citing the relevant DEC. |
| `src/pricing/blend.py` | `round_p(a, b)` Bradley-Terry log-odds with `BT_BLEND_EPSILON` input clip | ✓ VERIFIED | 59-line module; formula at line 59. Imported by `src/pricing/round_types.py`. |
| `src/pricing/dp.py` | `BO3State` (frozen+slots, 8 fields), `RoundPFn` Protocol, `series_value`, `_advance_round`, `_advance_to_next_map(state, a_won, next_side_orient)`, `lru_cache`, `_register_round_p_fn` registry, `_ot_coinflip_leaf`, OT detection via `REGULATION_HALF * 2` literal | ✓ VERIFIED | All present. `_advance_to_next_map` signature includes explicit `next_side_orient: str`, no hardcoded `'a_atk'` literal in body. |
| `src/pricing/round_types.py` | `round_p_for_round`, `HalfRates` Protocol, `_team_a_side`, `_team_b_side`, `TYPE_CHECKING` guard around `MatchState` import (no runtime circular) | ✓ VERIFIED | All present. Lines 48-56 use `TYPE_CHECKING` guard for `MatchState` import (retargeted to `src.pricing.data` per D-14 on line 55). |
| `src/pricing/round_conclusion.py` | `RoundConclusionLookup` (frozen+slots, 5 fallback-chain dict fields + `side_baseline`), `_Cell` (Bayesian shrinkage), `RoundConclusionFn` Protocol, `_PHASE_1_FLAT_CELL_VALUE`. `lookup` returns `_PHASE_1_FLAT_CELL_VALUE = 0.5` for all inputs in Phase 1 (D-06). Shrinkage uses imported `SHRINK_PRIOR` (no inline 15). | ✓ VERIFIED | All present (190 lines). Hypothesis test confirms 100-example flat-0.5 invariant; shrinkage formula at line 98-100. |
| `src/pricing/data.py` | `HalfRates` (concrete impl with `from_json`, `team`, `team_entry`), `MatchState` (Phase 1 stub, 17 fields, frozen+slots, includes D-17 team_a/team_b, D-18 map_side_orients, D-19 map_winners), `TheoOutput` (4 fields, frozen+slots) | ✓ VERIFIED | All three dataclasses present. `MatchState` field count = 17 (test_match_state_is_17_field_frozen_dataclass passes). `HalfRates.team` uses `(n*raw + SHRINK_PRIOR*prior) / (n + SHRINK_PRIOR)` with imported `SHRINK_PRIOR`. |
| `src/pricing/live_theo.py` | `LiveTheoEngine` bundle, `_live_theo_impl`, `_RoundPFnImpl` (Protocol-satisfying closure with side-orient resolution + within-map flip), `_marginal_map_prob` (with map_winners short-circuit), `_p_map_decisive` (W3 three-case recurrence), `_compute_confidence` (DP-mass-weighted per D-08), `_compute_vega` (DEC-018 form), `_data_weight_for_map` (D-09 salvage), `_clip_conviction` | ⚠️ HOLLOW | All artifacts exist and are wired (Levels 1-3 pass). Level 4 data-flow trace fails on three derived outputs: `_p_reach_map_cached` (CR-01), `_p_map_decisive` middle-map (CR-02), `_compute_vega` at OT (CR-03). See Data-Flow Trace section. |
| `src/pricing/__init__.py` | Re-exports `LiveTheoEngine, TheoOutput, MatchState, HalfRates`; `__all__` is exactly those four; no re-exports of dp/blend/round_types/round_conclusion. | ✓ VERIFIED | 19 lines; `__all__ = ["LiveTheoEngine", "TheoOutput", "MatchState", "HalfRates"]` on line 19. |
| `tests/pricing/__init__.py` | Package marker present | ✓ VERIFIED | File exists (one-line docstring). |
| `tests/pricing/test_blend.py`, `test_dp.py`, `test_round_types.py`, `test_round_conclusion.py`, `test_live_theo.py` | Property tests + unit tests + regression tests for each module | ✓ VERIFIED | All five test files present; `pytest tests/pricing/` passes 41 + 12 + 20 + 13 + 41 = 127 pricing tests (plus 32 config + 11 smoke/main = 137 total). |

### Key Link Verification

| From | To  | Via | Status | Details |
| ---- | --- | --- | ------ | ------- |
| `src.pricing.__init__` | `src.pricing.live_theo.LiveTheoEngine` | `from src.pricing.live_theo import LiveTheoEngine` | ✓ WIRED | Confirmed by `from src.pricing import LiveTheoEngine` succeeding in runtime smoke. |
| `LiveTheoEngine.__call__` | `_live_theo_impl` | direct call in `__call__` body (line 576) | ✓ WIRED | Returns `_live_theo_impl(state, self.half_rates, self.round_conclusion)`. |
| `_live_theo_impl` | `dp.series_value` (theo_series) | direct call after `_RoundPFnImpl` construction (line 316) | ✓ WIRED | `theo_series_raw = series_value(bo3, fn)`, then clipped. |
| `_live_theo_impl` | `_marginal_map_prob` (theo_map) | per-map comprehension (line 318-320) | ✓ WIRED | `theo_map = tuple(_marginal_map_prob(state, m, half_rates) for m in range(len(state.map_pool)))`. |
| `_RoundPFnImpl.__call__` | `round_p_for_round` | side-corrected BO3State delegation (line 100-103) | ✓ WIRED | Reads `match_state.map_side_orients[s.map_idx]`, applies within-map round-12 flip, delegates to `round_p_for_round`. Verified by `test_build_round_p_fn_consults_map_side_orients_first_half` and `test_build_round_p_fn_flips_after_round_12`. |
| `_marginal_map_prob (m < map_idx)` | `state.map_winners[m]` (D-19 short-circuit) | direct indexing (line 153-161) | ✓ WIRED | Returns `CONVICTION_CLIP_HIGH`/`CONVICTION_CLIP_LOW`/`0.5` from `map_winners[m]`. Verified by both short-circuit tests. |
| `_compute_confidence` | `_p_map_decisive` + `_data_weight_for_map` | iteration over map_pool (line 511-518) | ⚠️ DOWNSTREAM_BUG | Wiring is correct (`_compute_confidence` correctly calls `_p_map_decisive` for each map and weights by `_data_weight_for_map`); the BUG is downstream in `_p_map_decisive` (CR-01 / CR-02). The link itself is wired but the data flowing through it is corrupt. |
| `_compute_vega` | `_advance_round` + `series_value` | direct calls (line 539-545) | ⚠️ INCOMPLETE_GUARD | Wired but missing terminal/OT short-circuit (CR-03). At OT entry (`total == 24`), `_advance_round` is called past the OT hard-stop; the resulting vega is the variance of `_advance_round`-projected next-map series values rather than the OT coinflip leaf variance. |
| `_p_map_decisive (case 3, m > map_idx)` | `_p_reach_map` | call at line 423 | ⚠️ DOWNSTREAM_BUG | Wired; `_p_reach_map` is correctly invoked but `_p_reach_map_cached` has terminal-check ordering bug (CR-01) that returns 1.0 for clinched series at `map_idx==m`. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| `theo_series` (TheoOutput field) | `series_value(bo3, fn)` clipped | `dp.series_value` (correct DP recursion with OT hard-stop) | ✓ Yes | ✓ FLOWING |
| `theo_map` (TheoOutput field) | `_marginal_map_prob(state, m, half_rates)` for each m | `dp.series_value` via marginalization identity (current map) and `_within_map_p_a_wins` (future maps); short-circuits on `map_winners[m]` (already-played) | ✓ Yes | ✓ FLOWING (current map verified by DEC-002 marginalization-consistency test, pre-clip identity holds to FP precision) |
| `vega` (TheoOutput field) | `_compute_vega(bo3, fn)` | `series_value` after `_advance_round` — but `_advance_round` is called past OT hard-stop at `total == 24` | ✗ Partially (correct in regulation; bypasses OT leaf in OT-entry states) | ⚠️ STATIC (CR-03: at OT entry returns squared-deviation against next-map series values rather than OT-leaf variance — confirmed: 0.054 at a_round=12 b_round=12) |
| `confidence` (TheoOutput field) | `_compute_confidence` → `_p_map_decisive` → `_p_reach_map_cached` | `_p_reach_map_cached` returns 1.0 for already-clinched terminal recursion paths (CR-01); `_p_map_decisive` uses BO5+ placeholder for BO3 middle map (CR-02) | ✗ No (mathematically incorrect for any state where future-map decisive mass is computed) | ⚠️ HOLLOW (the field is populated but the value is mathematically corrupt for any non-trivial BO3 state — confirmed: `confidence=0.0` for the synthetic 0-0 state because empty half_rates → data_w=0; the bugs surface as soon as half_rates has data and any future-map mass is queried) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Full pricing test suite | `.venv/Scripts/python.exe -m pytest tests/ --tb=line` | `137 passed in 3.98s` | ✓ PASS |
| mypy strict on src/pricing | `.venv/Scripts/python.exe -m mypy --strict src/pricing/` | `Success: no issues found in 7 source files` | ✓ PASS |
| LiveTheoEngine end-to-end with empty half_rates | inline `python -c` script with synthetic state at (0,0,0,0) | `theo_series=0.5, theo_map=(0.5,0.5,0.5), vega=0.001624, confidence=0.0` | ✓ PASS (engine returns TheoOutput with all four fields populated and in valid ranges) |
| Forbidden symbol absence | `grep -RE "^def series_theo\\|^def series_theo_no_sides\\|^def series_theo_from_map_probs\\|^def model_series_prob\\|^def _signal_strength" src/pricing/` | exit 1 (no matches) | ✓ PASS |
| CR-01 clinch reach-map regression | inline `python -c` invoking `_p_reach_map(BO3State(map_idx=2, a_map_score=2, ...), fn, m=2)` | returns `1.0` (expected `0.0`) | ✗ FAIL (bug confirmed) |
| CR-02 BO3 middle-map decisive | inline `python -c` invoking `_p_map_decisive(state at map_idx=0, m=1)` | returns `0.5` (placeholder, not the correct BO3 formula) | ✗ FAIL (bug confirmed) |
| CR-03 vega at OT entry | inline `python -c` invoking `_compute_vega(BO3State(a_round=12, b_round=12, ...), fn)` | returns `0.054` (non-zero squared-deviation against next-map series rather than OT-leaf variance) | ✗ FAIL (bug confirmed; `_advance_round` is called past `total == 24` without OT short-circuit) |
| CR-04 registry-leak (per-call growth) | 10 sequential `engine(state)` calls; check `len(_ROUND_P_FNS)` and `len(_REACH_MAP_FNS)` | `_ROUND_P_FNS` grew by 220, `_REACH_MAP_FNS` grew by 20 — each call appends ~22 closures and 2 reach-map closures, never pruned | ✗ FAIL (bug confirmed; bounded for Phase 1 but will leak linearly under Phase 4's continuous quoter) |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| REQ-bo3-dp-engine | 01-02 | Generalized BO3 DP `series_value(state, round_p_fn) → float` over BO3State; memoized; range-invariant; matches `p²(3-2p)` closed form | ✓ SATISFIED | `src/pricing/dp.py` ships `BO3State` (frozen+slots, 8 fields) + `series_value` + `lru_cache`. Property tests `test_dp_value_in_unit_interval` and `test_dp_symmetric_input_matches_closed_form` pass. |
| REQ-bradley-terry-blend | 01-01 | `round_p(a, b) → (a*(1-b)) / (a*(1-b) + (1-a)*b)` with BT_BLEND_EPSILON input clip; symmetry holds | ✓ SATISFIED | `src/pricing/blend.py:59` ships the formula; `test_round_p_bradley_terry_symmetry` (hypothesis) confirms `round_p(a,b) + round_p(b,a) == 1` to rel_tol=1e-9. |
| REQ-pistol-anti-eco-modeling | 01-03 | Rounds {1,13} pistol path, {2,3,14,15} anti-eco using GUN_WIN_RATE=0.822, others gunround | ✓ SATISFIED | `src/pricing/round_types.py:140-153` dispatches correctly; tests `test_anti_eco_returns_gun_win_rate_when_a_won_pistol`, `test_anti_eco_returns_complement_when_b_won_pistol`, `test_round_1_pistol_uses_half_rates_blend`, `test_gunround_uses_half_rates_blend` all pass. Phase 1 simplification (A8: rounds 1/13 use half-rates blend; A6: rounds 3/15 use same as 2/14) documented and acceptable for Phase 1 scope. |
| REQ-ot-handling | 01-02 | DP hard-stops at total=24 with OT-as-coinflip leaf | ⚠️ PARTIALLY SATISFIED | The DP itself correctly hard-stops (`src/pricing/dp.py:207`); the explicit `_ot_coinflip_leaf` recurses into next-map series values per DEC-009. Test `test_dp_ot_hardstop_returns_coinflip_leaf_symmetric` passes. **Caveat**: CR-03 demonstrates `_compute_vega` does not honor the same hard-stop — it calls `_advance_round` past total=24, silently bypassing the leaf. The DP-level requirement is met; the vega-derived-output level is not. |
| REQ-round-conclusion-lookup (skeleton only) | 01-04 | 5-tier hierarchical fallback chain skeleton; flat 0.5 in Phase 1; SHRINK_PRIOR-imported Bayesian shrinkage in `_Cell.shrunk()` | ✓ SATISFIED | `src/pricing/round_conclusion.py` ships `RoundConclusionLookup` (5 dict fields + side_baseline), `_Cell.shrunk()` uses imported SHRINK_PRIOR, `_PHASE_1_FLAT_CELL_VALUE = 0.5`. Hypothesis test `test_lookup_always_returns_flat_05_in_phase_1` runs 100 examples. |
| REQ-canonical-live-theo | 01-05 | Single function (or bundle) `live_theo(state) → TheoOutput` returning all four fields; no `series_theo` triplet | ✓ SATISFIED | `LiveTheoEngine` is the only public entry; `src/pricing/__all__` is exactly the four canonical names; `grep -RE "^def series_theo\b\\|^def series_theo_no_sides\b\\|^def series_theo_from_map_probs\b" src/pricing/` returns no matches. |
| REQ-theo-series-output | 01-05 | `theo_series ∈ [0, 1]` for all reachable states; equals DP value at root | ✓ SATISFIED | `_live_theo_impl` returns `_clip_conviction(series_value(bo3, fn))`. `test_live_theo_impl_returns_theo_output_with_clipped_series` and the hypothesis property test `test_live_theo_property_invariants_hypothesis` (30 examples) confirm the range invariant. |
| REQ-theo-map-output | 01-05 | `theo_map[i] ∈ [0, 1]` for each map; consistent with theo_series under marginalization (DEC-002) | ✓ SATISFIED | `_live_theo_impl` populates `theo_map` via `_marginal_map_prob`. `test_live_theo_impl_theo_map_length_matches_map_pool`, `test_live_theo_impl_theo_map_values_in_clip_range`, and `test_live_theo_marginalization_consistency_dec002` all pass. (WR-05 from REVIEW notes the tolerance is loose at `1e-3`, but the test does pass and the pre-clip identity is structurally correct.) |
| REQ-confidence-output | 01-05 | `confidence ∈ [0, 1]` representing data-weight | ⚠️ PARTIALLY SATISFIED | The field is in [0, 1] (range invariant holds via `max(0.0, min(1.0, weighted_sum / mass_sum))` clip on line 522). The VALUE is mathematically corrupt due to CR-01 + CR-02 — `_p_reach_map_cached` over-counts and `_p_map_decisive` middle-map uses BO5+ placeholder. The interface contract holds; the underlying math does not. |
| REQ-vega-output | 01-05 | `vega = round_p × (theo_a − theo)² + (1−round_p) × (theo_b − theo)²` per DEC-018 | ⚠️ PARTIALLY SATISFIED | The formula is correctly implemented for regulation states (`_compute_vega` lines 539-545; verified by `test_compute_vega_matches_dec_018_formula` to rel_tol=1e-9). At OT-entry states the formula bypasses the OT hard-stop (CR-03) and produces a meaningless squared-deviation. Vega ≥ 0 invariant still holds (sum of squares is non-negative); the value is just structurally wrong at OT entry. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| `src/pricing/live_theo.py` | 469-474 | Terminal-check ordering bug: `_p_reach_map_cached` checks `state.map_idx == m` before the `a_map_score >= 2 / b_map_score >= 2` clinch short-circuit. A clinched-series recursion that lands at the target `map_idx` returns 1.0 (treated as "reached") instead of 0.0 (the series never plays subsequent maps). | 🛑 Blocker (REVIEW CR-01) | Inflates `p_decisive(map=m)` for any state where the recursion reaches `(map_idx=m, a_map_score>=2, ...)` or `(map_idx=m, b_map_score>=2, ...)`. `_compute_confidence` then double-counts clinched paths in the data-weight numerator. |
| `src/pricing/live_theo.py` | 424-428 | BO5+ placeholder branch (`return p_reached * 0.5`) fires for the BO3 middle map (`m == 1` from `state.map_idx == 0`). The comment claims "Phase 1 BO3: unreachable branch" but BO3 with `len(map_pool) == 3` makes `m=1, len-1=2, m != len-1` true. | 🛑 Blocker (REVIEW CR-02) | `_p_map_decisive(state, 1)` returns `p_reached * 0.5 = 0.5` (since `_p_reach_map(state at map_idx=0, m=1) == 1.0`) regardless of the actual P(map 1 is decisive). Tests only exercise `m=2`. |
| `src/pricing/live_theo.py` | 539-545 | `_compute_vega` calls `_advance_round(root, ...)` unconditionally; missing terminal/OT short-circuit. At `(a_round=12, b_round=12)` the advanced states are `(13, 12)` and `(12, 13)` (sums of 25), past the DP's OT hard-stop at total=24. Both hit the WIN_THRESHOLD map terminal in `_series_value_cached`, completely skipping the OT-as-coinflip leaf. | 🛑 Blocker (REVIEW CR-03) | `vega` at OT entry conflates "winning one OT round" with "winning the entire OT half plus the map" — exactly the bug class CRule 5 prohibits in the DP. Phase 4's mode-flip uses vega; spurious OT vega could force an unintended directional flip. |
| `src/pricing/live_theo.py` | 433-438; `src/pricing/dp.py` | 159-165 | Module-level closure registries (`_REACH_MAP_FNS`, `_ROUND_P_FNS`) are append-only with no pruning; `lru_cache(maxsize=None)` keys on `(state, int)` so each new closure id invalidates reuse. Each `LiveTheoEngine.__call__` appends ~22 closures to `_ROUND_P_FNS` and ~2 to `_REACH_MAP_FNS`. | 🛑 Blocker (REVIEW CR-04) — operational | Confirmed at runtime: 10 calls grew `_ROUND_P_FNS` by 220. Bounded for Phase 1's between-round single-call use case but breaks Phase 4's continuous-running quoter (linear-in-time memory leak). |
| `src/pricing/data.py` | 101 | `pistol_winner_a: dict[int, Optional[bool]]` on a `frozen=True, slots=True` dataclass. `frozen` blocks reassignment but not dict mutation; the BO3State tuple is packed at one snapshot but the source dict can drift. | ⚠️ Warning (REVIEW WR-01) | Caller-driven mutation risk; could cause stale `BO3State.pistol_winner_a` tuples in lru_cache. Bounded by Phase 1 caller discipline; rates W-stage closure for Phase 3. |
| `src/pricing/live_theo.py` | 172-175 | `_marginal_map_prob` returns `0.5` defensively when `abs(v_after_a - v_after_b) < 1e-12`. Fires legitimately at series-terminals AND mistakenly when `series_value` cache pollution returns identical values for both branches. | ⚠️ Warning (REVIEW WR-02) | At `state.a_map_score == 2`, the "current map" doesn't exist — A already won — and 0.5 is meaningless. Phase 4 may consume `theo_map[map_idx]` directly. |
| `src/pricing/live_theo.py` | 399-410 | `_p_map_decisive` reads `state.map_winners[m]` and `state.map_winners[: m + 1]` without bounds check; raises `IndexError` if `map_winners` length < `state.map_idx + 1` (no MatchState invariant declared). | ⚠️ Warning (REVIEW WR-03) | Phase 1 internal callers honor the invariant; Phase 3 ingestion could violate. |
| `src/pricing/live_theo.py` | 106-118 | Defensive `'a_atk'` literal in `_RoundPFnImpl._effective_side` and `next_side_orient_for` for `map_idx >= len(self.match_state.map_side_orients)`. The DP module went to lengths to forbid hardcoded `'a_atk'` (regression test exists); this defensive fallback reintroduces the same literal at a boundary. | ⚠️ Warning (REVIEW WR-04) | "Never consumed" assumptions are unsafe given CR-01's terminal-ordering bug. |
| `tests/pricing/test_live_theo.py` | (test file, ~721) | `test_live_theo_marginalization_consistency_dec002` uses `rel_tol=1e-3, abs_tol=1e-3` — too loose to catch sign errors at edge states near 0.5. | ⚠️ Warning (REVIEW WR-05) | The DEC-002 / CRule 2 acceptance test could pass even with `theo_map[map_idx]` reporting P(B wins) instead of P(A wins) at certain states. |
| `src/pricing/live_theo.py` | 172, 486, 520 | Recurring `1e-12` numerical-tolerance literal at three call sites without a named constant. CRule 12 borderline. | ℹ️ Info (REVIEW IN-01) | Maintainability; suggest `DENOM_DEGENERACY_TOL` in `constants.py`. |
| (multiple) | (info-level — see REVIEW.md) | `_within_map_p_a_wins` reconstructs closure per call (IN-02); `_p_map_decisive` recomputes `_marginal_map_prob` (IN-03); `_compute_confidence` divides by `mass_sum` even though it's analytically 1.0 (IN-04). | ℹ️ Info | Performance + missing structural assertions. Out of v1 scope. |

### Human Verification Required

(none — all checks completable programmatically)

### Gaps Summary

The phase goal — "single canonical `live_theo(state) → (theo_series, theo_map, vega, confidence)` with no data dependencies; between-round live pricing works end-to-end" — is met at the **interface and surface-fix level** but not at the **derived-output correctness level**.

What works (verified, not on faith):

- The single-entry-point public surface is locked: `LiveTheoEngine` is the only callable; `__all__ == ["LiveTheoEngine", "TheoOutput", "MatchState", "HalfRates"]`; the audit-engine triplet is fully absent from source.
- The four primary audit-engine bug fixes (Bradley-Terry blend, OT hard-stop in the DP, pistol/anti-eco dispatch, conviction clip) are correctly implemented at their primary call sites and regression-tested.
- The DP, blend, round-types, round-conclusion skeleton, and MatchState/TheoOutput/HalfRates dataclasses all exist with the expected shapes.
- The mandated property tests pass: DP value ∈ [0,1], symmetric input matches `p²(3-2p)` closed form, BT symmetry, theo_series ↔ theo_map[] marginalization consistency.
- 137/137 tests pass; `mypy --strict src/pricing/` is clean.

What is broken (independently verified at runtime, matches REVIEW.md findings 1-4):

- **CR-01**: `_p_reach_map_cached` returns 1.0 for already-clinched series at the target map index. Confirmed: `_p_reach_map(BO3State(map_idx=2, a_map_score=2, ...), fn, m=2)` returns 1.0.
- **CR-02**: `_p_map_decisive` uses the BO5+ placeholder `p_reached * 0.5` for the BO3 middle map. Confirmed: `_p_map_decisive(state at map_idx=0, m=1)` returns 0.5 unconditionally.
- **CR-03**: `_compute_vega` calls `_advance_round` past the OT hard-stop at `total = 24`. Confirmed: at `a_round=12, b_round=12` returns 0.054 (a meaningless squared-deviation against next-map series values, bypassing the OT coinflip leaf documented in DEC-009).
- **CR-04**: `_ROUND_P_FNS` and `_REACH_MAP_FNS` registries grow unbounded. Confirmed: 10 calls grew `_ROUND_P_FNS` by 220.

Goal-impact assessment:

- The phase goal qualifies "between-round live pricing works end-to-end." The engine DOES run end-to-end and DOES return TheoOutput with all four fields populated, so a strict reading of "works" is met. But two of the four fields (`vega`, `confidence`) are populated with mathematically incorrect values for a non-trivial portion of the state space (any state involving future-map decisive mass for confidence; any OT-entry state for vega).
- These bugs are NOT cosmetic. Phase 4 consumes `vega` to drive the MM↔directional mode flip (`VEGA_DIRECTIONAL_THRESHOLD = 0.04`). A spurious 0.054 at OT entry would force an unintended mode flip on a meaningless signal. `confidence` feeds the kill-switch and quote-width logic in Phase 4.
- The bugs are localized in derived-output machinery (~50 lines across `_p_reach_map_cached`, `_p_map_decisive` case 3, `_compute_vega`). Closure is mechanical: reorder terminal checks, replace placeholder with the correct BO3 middle-map formula, add OT/terminal short-circuit to vega. Each fix has an REVIEW-suggested test in REVIEW.md.

Recommendation: route to `/gsd-plan-phase --gaps` for a focused gap-closure plan. The four fixes are tightly coupled (they all operate on the BO3 forward-pass + DEC-009 boundary semantics) and should land in a single revision plan. CR-04 (registry leak) is operationally necessary for Phase 4 readiness but does not block Phase 1's stated goal of "between-round pricing works"; it can be split into a follow-up if the phase-1 gap closure scope is constrained to correctness-only.

---

_Verified: 2026-04-28T21:15:00Z_
_Verifier: Claude (gsd-verifier)_
