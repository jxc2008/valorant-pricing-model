---
phase: 01-core-pricing-engine
verified: 2026-04-28T23:45:00Z
status: gaps_found
score: 2/3 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 2/3
  gaps_closed: []
  gaps_remaining:
    - "CR-05: dp._advance_round / _advance_to_next_map / _within_map_p_a_wins all still propagate pistol_winner_a verbatim — REQ-pistol-anti-eco-modeling silently inactive in DP forward-pass for pre-pistol call sites"
  regressions: []
  new_findings: []
gaps:
  - truth: "Phase 1 must-have #2 — Pistol + anti-eco modeled explicitly for rounds {1, 2, 3, 13, 14, 15} using GUN_WIN_RATE=0.822 (DEC-011 / CRule 4). The dispatch in round_types.round_p_for_round is structurally correct, but the DP forward-pass never updates BO3State.pistol_winner_a when round 1 settles, so for the most common Phase 4 call site (pre-pistol pricing where pistol_winner_a[map_idx] is None) all anti-eco rounds in DP recursion silently fall to the defensive 0.5 fallback instead of GUN_WIN_RATE."
    status: partial
    reason: |
      The dispatch logic in `src/pricing/round_types.py:140-153` is correct in
      isolation (rounds {2, 3, 14, 15} return GUN_WIN_RATE if
      `pistol_winner_a[map_idx]` is True, 1-GUN_WIN_RATE if False, defensive 0.5
      if None). The bug is upstream: `dp._advance_round` (lines 104-122) and
      `dp._advance_to_next_map` (lines 125-149) propagate `pistol_winner_a`
      verbatim from the parent BO3State without setting
      `pistol_winner_a[map_idx] = True/False` when round 1 completes. So when
      `LiveTheoEngine` is invoked at a pre-pistol state with
      `pistol_winner_a={0:None,1:None,2:None}` (the natural pre-match condition),
      the DP recursion enters round 2 carrying `pistol_winner_a[0] = None`,
      dispatches to the defensive 0.5 fallback, and the pistol+anti-eco model
      (DEC-011 / CRule 4) is silently inactive for all four anti-eco rounds × 3
      maps = 12 anti-eco rounds in the recursion.

      Independently re-verified at runtime in this verification cycle:
      `_RoundPFnImpl.__call__` on `_advance_round(bo3, a_wins=True)` from a
      fresh `bo3` with `pistol_winner_a=(None,None,None)` returns 0.5 (expected
      GUN_WIN_RATE = 0.822). The same is true for round 3 (a_round=2, b_round=0
      after stepping forward twice with A winning). End-to-end impact under
      asymmetric half-rates (TeamA 0.55 / TeamB 0.45 across all maps/sides,
      total=1e9 to suppress shrinkage): theo_series with
      `pistol_winner_a={0:None,1:None,2:None}` is 0.887, vs theo_series with
      `{0:True,1:True,2:True}` is 0.979 — a 9.25pp swing driven entirely by
      whether the pistol model is active. (At the much stronger 0.6/0.4 the
      conviction clip masks the spread; at 0.55/0.45 the asymmetry is clearly
      observable.)

      This bug was missed in the original 01-VERIFICATION.md and the original
      01-REVIEW.md. It was caught in the re-review at
      `.planning/phases/01-core-pricing-engine/01-REVIEW.md` (2026-04-28T22:00)
      as CR-05 with concrete fix code, was raised in the prior
      01-VERIFICATION.md re-verification (2026-04-28T23:00), and remains
      structurally unaddressed in the codebase as of this re-verification
      (2026-04-28T23:45) — the fix has not been planned or implemented yet.

      The existing test at `tests/pricing/test_round_types.py:213-222`
      (`test_anti_eco_with_none_pistol_winner_returns_defensive_05`) explicitly
      asserts the defensive 0.5 fallback as desired behavior, BLESSING the
      broken dispatch path. This test does not cover the DP-forward-pass case
      where `pistol_winner_a` is None at the call-site root but the recursion
      has settled round 1; it only covers the standalone dispatch.

      The DP-level integration tests use `_synthetic_half_rates()` with rates
      of 0.6/0.5/0.4/0.5, which produce `p ≈ 0.5` after the BT blend across
      maps/sides. At p ≈ 0.5, `0.822 * p + 0.178 * (1-p) ≈ 0.5` so the bug is
      invisible at symmetric matchups; only asymmetric matchups expose the
      magnitude.
    artifacts:
      - path: "src/pricing/dp.py:104-122"
        issue: "_advance_round returns BO3State with `pistol_winner_a=state.pistol_winner_a` verbatim — never updates `pistol_winner_a[map_idx] = a_wins` when advancing past round 1 (state.a_round + state.b_round == 0 → 1)."
      - path: "src/pricing/dp.py:125-149"
        issue: "_advance_to_next_map similarly propagates `pistol_winner_a` unchanged across map boundaries — Phase 1 simplification A8 (rounds 1/13 use half-rates blend) means pistol-winner-of-second-half cannot be inferred from BO3State alone. For map-boundary advance, pistol_winner_a[next_map_idx] should remain None until that map's round 1 settles in recursion."
      - path: "src/pricing/live_theo.py:204-272 (_within_map_p_a_wins)"
        issue: "The within-map sub-DP used for future-map marginals (m > state.map_idx) inlines its own state-advance logic (lines 253-262) without touching pistol_winner_a. Same defect as CR-05 scoped to future-map sub-DP — once the dp.py forward-pass fix lands, the identical update logic must be replicated here OR the sub-DP refactored to call _advance_round directly. WR-06 in the latest 01-REVIEW.md."
    missing:
      - "Update dp._advance_round to set pistol_winner_a[state.map_idx] = a_wins when state.a_round == 0 AND state.b_round == 0 AND state.pistol_winner_a[state.map_idx] is None (don't override ingested live values). Concrete fix code shown in 01-REVIEW.md CR-05 §`Fix:` block."
      - "Update _within_map_p_a_wins (live_theo.py) to apply the same pistol_winner_a update — or refactor to share state-advance helpers with dp.py."
      - "Add regression test: `test_dp_anti_eco_uses_gun_win_rate_after_round_1_branch` — asserts `_RoundPFnImpl(...)(_advance_round(bo3_with_None_pistols, a_wins=True))` equals GUN_WIN_RATE (0.822), not 0.5. Concrete test code in 01-REVIEW.md CR-05 §end."
      - "Update or replace `test_anti_eco_with_none_pistol_winner_returns_defensive_05` in test_round_types.py to clarify that the 0.5 fallback is for malformed external inputs, NOT for DP forward-pass states (which should never reach round_p_for_round with None pistol_winner_a after the fix)."
      - "Document the second-half pistol limitation explicitly: pistol_winner_a is keyed only by map_idx, so rounds 14/15 cannot distinguish pistol-of-second-half winner. Either extend the data shape to `tuple[Optional[tuple[bool, bool]], ...]` per (map, half) OR document the Phase 2 follow-up where rounds 14/15 also fall back to half-rates."
human_verification: []
---

# Phase 1: Core Pricing Engine Verification Report (Re-verification #2)

**Phase Goal:** Single canonical `live_theo(state) → (theo_series, theo_map, vega, confidence)` with no data dependencies — between-round live pricing works end-to-end.
**Verified:** 2026-04-28T23:45:00Z
**Status:** gaps_found
**Re-verification:** Yes — confirmation pass after the prior 2026-04-28T23:00 re-verification surfaced CR-05. CR-01..CR-04 still pass; CR-05 still unaddressed in the codebase.

## Re-verification Summary

This is the second re-verification of Phase 01. The first re-verification (2026-04-28T23:00) confirmed the four BLOCKERs from the original verification (CR-01..CR-04) were CLOSED by the 01-06 gap-closure plan, AND surfaced CR-05 (a fifth BLOCKER missed in the original review and re-introduced as a new finding by the post-01-06 code review at `01-REVIEW.md`). This second re-verification re-runs every probe against the current `main` (commit 9bf91d8 + 01-06 closure commits) to confirm:

1. **CR-01..CR-04 remain closed** — yes, all four fixes are structurally locked at the source level and exercised by regression tests in `tests/pricing/test_live_theo.py:515-848`. 147 tests pass; mypy --strict on `src/pricing/` is clean; ruff is clean.
2. **CR-05 status** — the bug is **still present in the codebase** at `src/pricing/dp.py:121` and `src/pricing/dp.py:148`. No 01-07 plan has landed to fix it. Runtime probe reproduces the dispatch failure: P(A wins round 2 | A won round 1) = 0.5 (expected GUN_WIN_RATE = 0.822). End-to-end theo_series swing of 9.25pp at TeamA=0.55/TeamB=0.45 between unset and set `pistol_winner_a`, driven entirely by whether the anti-eco branch fires.

The phase status remains `gaps_found`. The single open gap (CR-05) is the same as in the prior re-verification, with identical scope, fix pattern, and missing items.

## Goal Achievement

### Observable Truths

| #   | Truth                                                                                                                                                                                                                                                                            | Status     | Evidence       |
| --- | ---------- | ----- | ----- |
| 1   | Must-have 1: `live_theo(state)` returns a `TheoOutput` dataclass with `theo_series, theo_map, vega, confidence`; no other pricing entry points exist (DEC-010); LiveTheoEngine bundle is the only API surface for the math layer. | ✓ VERIFIED | `LiveTheoEngine` is the only public callable; `src/pricing/__init__.py:19` declares `__all__ = ['LiveTheoEngine', 'TheoOutput', 'MatchState', 'HalfRates']`; `grep -RE "^def series_theo\|^def series_theo_no_sides\|^def series_theo_from_map_probs\|^def model_series_prob\|^def _signal_strength" src/pricing/` returns no matches; end-to-end `engine(state)` runs and returns a `TheoOutput` with all four fields populated and in valid ranges. The four BLOCKERs that previously corrupted `vega` and `confidence` derived outputs are confirmed closed (CR-01..CR-04 — re-verification probes pass). |
| 2   | Must-have 2: Four documented audit-engine bugs are fixed: Bradley-Terry blend (DEC-003), OT hard-stop at total=24 (DEC-009), pistol/anti-eco modeled with separate inputs (DEC-011), conviction clips at [0.01, 0.99] (DEC-012). | ✗ FAILED | (a) BT blend ✓ (verified — `src/pricing/blend.py:59`, regression-locked). (b) OT hard-stop ✓ (verified — `src/pricing/dp.py:225`, no `range(26)`/`range(WIN_THRESHOLD * 2)`; `_compute_vega` honors hard-stop via CR-03 fix at `live_theo.py:585`). (c) **Pistol/anti-eco ✗ FAILED** — dispatch in `round_types.py:140-153` is correct, but `dp._advance_round` (line 121) / `_advance_to_next_map` (line 148) never update `BO3State.pistol_winner_a` when round 1 settles, so for the natural pre-match call site (pistol_winner_a all None) all anti-eco rounds in DP recursion fall to the defensive 0.5 fallback instead of GUN_WIN_RATE. Verified at runtime: `_RoundPFnImpl(...)(_advance_round(bo3_with_None_pistols, a_wins=True)) == 0.5` (expected 0.822). End-to-end impact: 9.25pp theo_series swing at TeamA=0.55/TeamB=0.45 between unset and set `pistol_winner_a`. CR-05 in `01-REVIEW.md`, missed in the original review, surfaced in the prior re-verification, still unaddressed. (d) Conviction clip ✓ (verified — `_clip_conviction` clips to `[0.01, 0.99]` at `live_theo.py:280-282`). |
| 3   | Must-have 3: Property tests pass — DP value ∈ [0,1] for any state; symmetric inputs match `p²(3−2p)` closed form; Bradley-Terry symmetry; `theo_series` consistent with sum over `theo_map[]` outcomes. | ✓ VERIFIED | `pytest tests/` reports `147 passed in 14.09s`. Property tests pass: `test_dp_value_in_unit_interval` (hypothesis), `test_dp_symmetric_input_matches_closed_form` (hypothesis vs `_bo3_series_prob`), `test_round_p_bradley_terry_symmetry` (hypothesis), `test_live_theo_marginalization_consistency_dec002`. The new sum-over-m == 1 test from CR-02 closure (`test_p_map_decisive_sum_equals_one_pre_clinch` at `test_live_theo.py:581-594`) reinforces the marginalization invariant structurally. mypy --strict on `src/pricing/` exits 0; ruff exits 0 on `src/pricing/` and `tests/pricing/`. |

**Score:** 2/3 truths verified (must-have #2 FAILED on the pistol/anti-eco sub-clause; CR-05 is a BLOCKER for DEC-011 enforcement at the natural Phase-4 call site).

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `src/config/constants.py` | 4 new Phase 1 constants (`CONVICTION_CLIP_LOW`, `CONVICTION_CLIP_HIGH`, `MIN_ROUNDS_FULL_WEIGHT`, `BT_BLEND_EPSILON`) with `Final[...]` annotations | ✓ VERIFIED | Lines 79-107 — all four present with `Final[...]` + Source docstrings. |
| `src/pricing/blend.py` | Bradley-Terry log-odds blend with input clip | ✓ VERIFIED | 60-line module; formula at line 59; input clip at 57-58. |
| `src/pricing/dp.py` | BO3State, RoundPFn Protocol, `series_value`, helpers, OT detection via `REGULATION_HALF * 2`, `_clear_pricing_caches` (CR-04) | ⚠️ HOLLOW (CR-05) | All artifacts exist; OT hard-stop at line 225 and CR-04 helper at line 168 present. **However, `_advance_round` (line 121) and `_advance_to_next_map` (line 148) propagate `pistol_winner_a` verbatim and never update it when round 1 settles — REQ-pistol-anti-eco-modeling silently broken for the most common Phase-4 call site.** |
| `src/pricing/round_types.py` | round_p_for_round dispatch, HalfRates Protocol, side helpers, TYPE_CHECKING guard | ✓ VERIFIED | Dispatch correct in isolation; defensive 0.5 fallback at line 152 fires due to upstream CR-05 bug, not a defect in this module. |
| `src/pricing/round_conclusion.py` | RoundConclusionLookup skeleton, _Cell shrinkage, RoundConclusionFn Protocol, _PHASE_1_FLAT_CELL_VALUE | ✓ VERIFIED | All present (190 lines); flat-0.5 invariant locked by hypothesis test. |
| `src/pricing/data.py` | HalfRates concrete impl, MatchState (17 fields), TheoOutput (4 fields) | ✓ VERIFIED | All three dataclasses present at lines 32-169. |
| `src/pricing/live_theo.py` | LiveTheoEngine bundle, _live_theo_impl, _RoundPFnImpl, _marginal_map_prob, _p_map_decisive (BO3 middle-map formula CR-02), _compute_confidence (DP-mass-weighted), _compute_vega (with terminal/OT short-circuits CR-03), _data_weight_for_map, _clip_conviction, _p_reach_map_cached (clinch-first ordering CR-01), _clear_pricing_caches helper, try/finally in __call__ (CR-04) | ⚠️ HOLLOW (CR-05) | All four CR-01..CR-04 fixes verified at line-by-line and runtime level (CR-01 at 495-500, CR-02 at 435, CR-03 at 578-596, CR-04 at 449-457 + 634-646). **However, `_within_map_p_a_wins` (lines 204-272) inlines state-advance logic at 253-262 with the same `pistol_winner_a` propagation defect as `dp._advance_round`** (WR-06 in latest review) — once CR-05 fix lands in dp.py, the same logic must be replicated or refactored here. |
| `src/pricing/__init__.py` | Re-exports LiveTheoEngine, TheoOutput, MatchState, HalfRates; `__all__` exactly those four | ✓ VERIFIED | 19 lines; `__all__` matches. Helpers `_clear_pricing_caches` stay private (verified — no leak into `__all__`). |
| `tests/pricing/{test_blend, test_dp, test_round_types, test_round_conclusion, test_live_theo}.py` | Property + unit + regression tests | ✓ VERIFIED (with caveat) | 147 tests pass. **Caveat:** `test_anti_eco_with_none_pistol_winner_returns_defensive_05` (test_round_types.py:213-222) blesses the CR-05 broken behavior by asserting the 0.5 fallback as desired output; the DP-forward-pass case (where `pistol_winner_a` is None at root but should be set after round 1 settles) is not covered. Asymmetric matchups are not exercised in the integration tests. |

### Key Link Verification

| From | To  | Via | Status | Details |
| ---- | --- | --- | ------ | ------- |
| `src.pricing.__init__` | `LiveTheoEngine` | `from src.pricing.live_theo import LiveTheoEngine` | ✓ WIRED | Confirmed at runtime. |
| `LiveTheoEngine.__call__` | `_live_theo_impl` (with try/finally cleanup) | direct call wrapped in try/finally | ✓ WIRED | CR-04 fix landed at lines 634-646; cleanup runs in `finally`. |
| `LiveTheoEngine.__call__` | `dp._clear_pricing_caches` + `live_theo._clear_pricing_caches` | local import + finally-block calls | ✓ WIRED | Memory leak regression test (`test_no_memory_leak_across_live_theo_calls`) confirms registries reset to 0 after 100 calls (re-verified inline this run). |
| `_live_theo_impl` | `dp.series_value` (theo_series) | direct call | ✓ WIRED | Verified line 316 + clip on line 317. |
| `_live_theo_impl` | `_marginal_map_prob` (theo_map) | per-map comprehension | ✓ WIRED | Lines 318-320; uses BO3 marginalization identity (DEC-002). |
| `_compute_confidence` | `_p_map_decisive` (with CR-01 fix) + `_data_weight_for_map` | iteration over map_pool | ✓ WIRED | CR-01 fix (line 495 precedes line 497) ensures `_p_reach_map_cached` returns 0.0 for clinched series; sum-over-m == 1 test confirms law of total probability. |
| `_p_map_decisive case 3` | `_marginal_map_prob(state, m-1)` + `_marginal_map_prob(state, m)` | BO3 middle-map formula at line 435 | ✓ WIRED | CR-02 fix landed; BO5+ placeholder absent (`grep p_reached \* 0.5` returns nothing); `_p_map_decisive(state at map_idx=0, m=1)` returns the correct BO3 formula value under asymmetric half-rates. |
| `_compute_vega` | early-return guards at series terminal, within-map terminal, OT entry | three early-return blocks at lines 579, 582, 585 | ✓ WIRED | CR-03 fix landed; vega at OT-entry returns the OT coinflip-leaf variance (per the 01-06 SUMMARY's empirical observation, ~0.0625 for 0-0 1-map root, matches manual reconstruction). |
| `dp._advance_round` | `pistol_winner_a` update on round-1 completion | (no link — propagates verbatim) | ✗ NOT_WIRED | **CR-05 BLOCKER** — line 121 has `pistol_winner_a=state.pistol_winner_a` with no conditional update for the round-1 boundary. |
| `dp._advance_to_next_map` | `pistol_winner_a` reset for next map | (no link — propagates verbatim) | ✗ NOT_WIRED | **CR-05 BLOCKER** — line 148 has `pistol_winner_a=state.pistol_winner_a` with no map-boundary reset/conditional update. |
| `_within_map_p_a_wins` | `pistol_winner_a` update in inline state advance | (no link — inline at lines 253-262) | ✗ NOT_WIRED | **WR-06 (CR-05 scoped to future-map sub-DP)** — same defect as dp._advance_round. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| `theo_series` (TheoOutput field) | `series_value(bo3, fn)` clipped | `dp.series_value` (correct OT hard-stop) — but underlying DP recursion uses CR-05-broken round_p for anti-eco rounds | ⚠️ Partially | ⚠️ HOLLOW (CR-05) — value is mathematically off by ~9-13pp in asymmetric matchups because anti-eco rounds dispatch to 0.5 fallback. |
| `theo_map` (TheoOutput field) | `_marginal_map_prob(state, m, half_rates)` for each m | `dp.series_value` via marginalization identity (current map) and `_within_map_p_a_wins` (future maps) | ⚠️ Partially | ⚠️ HOLLOW (CR-05 + WR-06) — same root cause; per-map marginal also uses the broken DP/sub-DP. |
| `vega` (TheoOutput field) | `_compute_vega(bo3, fn)` with terminal/OT guards | `series_value` calls now honor OT hard-stop via early-return at line 585; CR-03 fix landed | ✓ Yes (where vega is non-zero) | ✓ FLOWING (CR-03 closed) — minor caveat: in regulation states the vega depends on `round_p_fn(root)` which inherits the CR-05 anti-eco bug for anti-eco rounds. |
| `confidence` (TheoOutput field) | `_compute_confidence` → `_p_map_decisive` → `_p_reach_map_cached` (CR-01-fixed clinch ordering) + `_data_weight_for_map` | CR-01 + CR-02 fixes landed; sum-over-m == 1 test passes | ✓ Yes (structural law of total probability holds) | ✓ FLOWING (CR-01, CR-02 closed) — minor caveat: the `_p_map_decisive` middle-map formula uses `_marginal_map_prob` which inherits the CR-05 bug; numerical value of confidence is therefore approximately correct but has the same upstream error budget as theo_series. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Full pricing test suite | `.venv/Scripts/python.exe -m pytest tests/ --tb=line` | `147 passed in 14.09s` | ✓ PASS |
| mypy strict on src/pricing | `.venv/Scripts/python.exe -m mypy --strict src/pricing/` | `Success: no issues found in 7 source files` | ✓ PASS |
| ruff on src/pricing/ + tests/pricing/ | `.venv/Scripts/python.exe -m ruff check src/pricing/ tests/pricing/` | `All checks passed!` | ✓ PASS |
| Forbidden symbol absence (CRule 1 / DEC-010) | `grep -RE "^def series_theo\|^def series_theo_no_sides\|^def series_theo_from_map_probs\|^def model_series_prob\|^def _signal_strength" src/pricing/` | exit 1 (no matches) | ✓ PASS |
| Public surface contract | `python -c "import src.pricing as p; p.__all__"` | `['LiveTheoEngine', 'TheoOutput', 'MatchState', 'HalfRates']` | ✓ PASS |
| CR-01 clinch reach-map structural | `inspect.getsource(_p_reach_map_cached)` — clinch guard line precedes `state.map_idx == m` line | clinch at body-line 21, map_idx == m at body-line 23, ordered correctly | ✓ PASS |
| CR-02 BO3 middle-map formula structural | grep `p_a_wins_m_minus_1 * p_a_wins_m + (1.0 - p_a_wins_m_minus_1) * (1.0 - p_a_wins_m)` AND grep `p_reached * 0.5` is absent | formula present (line 435); placeholder absent | ✓ PASS |
| CR-03 vega three early-return guards | inspect `_compute_vega` for series terminal, within-map terminal, OT-entry guards | all three guards present at lines 579, 582, 585 | ✓ PASS |
| CR-04 cleanup helpers + try/finally | inspect `LiveTheoEngine.__call__` for `try/finally` and both `_clear_pricing_caches` calls | try/finally present; both `_clear_pricing_caches()` and `_dp._clear_pricing_caches()` called in finally | ✓ PASS |
| CR-04 registry-leak (per-call growth) | 100 sequential `engine(state)` calls; check `len(_ROUND_P_FNS)` and `len(_REACH_MAP_FNS)` | both 0 (re-verified inline this run) | ✓ PASS |
| **CR-05** — DP forward-pass anti-eco dispatch | inline probe — `_RoundPFnImpl(state with pistol_winner_a={0:None,1:None,2:None}, hr)(_advance_round(bo3, a_wins=True))` | returns `0.5` (defensive fallback); expected `GUN_WIN_RATE = 0.822` per DEC-011. Re-confirmed at runtime this cycle. | ✗ FAIL (CR-05 confirmed at runtime) |
| **CR-05** — Round 3 forward-pass | Step DP forward A wins R1 → A wins R2; check `_RoundPFnImpl` returns for round 3 | returns `0.5` (expected `0.822`); `pistol_winner_a` still `(None, None, None)` after both advances | ✗ FAIL (CR-05) |
| **CR-05** — End-to-end theo_series swing | `LiveTheoEngine` on TeamA=0.55/TeamB=0.45 with total=1e9 (no shrinkage), `pistol_winner_a={0:None,1:None,2:None}` vs `{0:True,1:True,2:True}` | unset: `theo_series=0.887`; set: `theo_series=0.979`; delta = 9.25pp | ✗ FAIL (material impact on Phase-4 trading; ~9-13pp depending on rate spread, 13pp at 0.6/0.4 from prior verification) |

### Requirements Coverage

All 10 phase requirement IDs declared across plan frontmatter cross-reference cleanly to REQUIREMENTS.md.

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| REQ-bo3-dp-engine | 01-02 | Generalized BO3 DP `series_value(state, round_p_fn) → float`; memoized; range-invariant; matches p²(3-2p) closed form | ✓ SATISFIED | DP recursion at `dp.py:191-233` + `lru_cache(maxsize=None)` + property tests `test_dp.py`; OT hard-stop at line 225 confirmed. |
| REQ-bradley-terry-blend | 01-01 | `(a*(1-b)) / (a*(1-b) + (1-a)*b)` with input clip; symmetry holds | ✓ SATISFIED | `src/pricing/blend.py:59`; `test_round_p_bradley_terry_symmetry` (hypothesis) in `test_blend.py`. |
| REQ-pistol-anti-eco-modeling | 01-03 | Rounds {1, 13} pistol; {2, 3, 14, 15} anti-eco using GUN_WIN_RATE=0.822; others gunround | ✗ BLOCKED | Dispatch logic correct in `round_types.py:140-153` IN ISOLATION, but **CR-05** means the DP forward-pass never sets pistol_winner_a after round 1 settles, so the anti-eco branch silently dispatches to 0.5 fallback for the most common Phase-4 call site. REQ acceptance criterion ("empirical conversion rate ~75% on round 2 and ~60% on round 3 from a pistol win") cannot be tested end-to-end because the DP never threads a pistol-set state through anti-eco rounds. |
| REQ-ot-handling | 01-02, 01-06 | DP hard-stop at total=24 with OT-as-coinflip leaf | ✓ SATISFIED | DP recursion `dp.py:225` + `_ot_coinflip_leaf` `dp.py:236-258`; CR-03 closure ensures `_compute_vega` also honors the hard-stop at `live_theo.py:585`. Verified at runtime: vega at 12-12 returns OT-leaf variance, not buggy `_advance_round` projection. |
| REQ-round-conclusion-lookup (skeleton) | 01-04 | 5-tier hierarchical fallback chain skeleton; flat 0.5 in Phase 1; SHRINK_PRIOR-imported Bayesian shrinkage | ✓ SATISFIED | All artifacts present in `round_conclusion.py`; flat-0.5 invariant locked by hypothesis test in `test_round_conclusion.py`. |
| REQ-canonical-live-theo | 01-05, 01-06 | Single function (LiveTheoEngine bundle) `live_theo(state) → TheoOutput`; no audit triplet | ✓ SATISFIED | LiveTheoEngine is the only public callable; `__all__` matches; audit triplet absent (grep returns nothing for forbidden symbols). |
| REQ-theo-series-output | 01-05 | `theo_series ∈ [0, 1]` for all reachable states | ✓ SATISFIED (range invariant) | `_clip_conviction` ensures range; hypothesis property tests pass. (Numerical value carries CR-05 ~9-13pp error budget but range invariant holds.) |
| REQ-theo-map-output | 01-05 | Per-map `theo_map[i] ∈ [0, 1]`; consistent with theo_series under marginalization | ✓ SATISFIED (DEC-002 marginalization holds at FP precision) | `test_live_theo_marginalization_consistency_dec002` passes. |
| REQ-confidence-output | 01-05, 01-06 | confidence ∈ [0, 1]; DP-mass-weighted per D-08 | ✓ SATISFIED | CR-01 + CR-02 closure ensures law of total probability holds (sum-over-m == 1 test passes). |
| REQ-vega-output | 01-05, 01-06 | `vega = round_p × (theo_a − theo)² + (1 − round_p) × (theo_b − theo)²` per DEC-018 | ✓ SATISFIED | CR-03 closure ensures vega is structurally correct in regulation (DEC-018 formula at line 604), at series terminals (0), at within-map terminals (0), and at OT entry (OT-leaf variance, not buggy `_advance_round` projection). |

**Summary:** 9/10 satisfied; 1 BLOCKED (REQ-pistol-anti-eco-modeling). No orphaned requirements (all 10 IDs from ROADMAP.md cross-reference cleanly to REQUIREMENTS.md and to plan frontmatter).

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| `src/pricing/dp.py` | 121 | `_advance_round` returns `pistol_winner_a=state.pistol_winner_a` verbatim — no conditional update for round-1 completion. The anti-eco model in `round_types.py:140-153` dispatches by `pistol_winner_a[map_idx]`, which is None throughout DP recursion when the call site starts pre-pistol. | 🛑 Blocker (CR-05) | REQ-pistol-anti-eco-modeling silently inactive for the natural Phase-4 call site (pre-match pricing). End-to-end theo_series error budget is ~9-13pp under asymmetric matchups. The dispatch in round_types.py is correct in isolation; the bug is the DP forward-pass never feeding it a settled `pistol_winner_a`. |
| `src/pricing/dp.py` | 148 | `_advance_to_next_map` similarly propagates `pistol_winner_a` verbatim — `pistol_winner_a[next_map_idx]` correctly stays None at the map boundary, but the same defect applies when round 1 settles on the new map within the recursion (because round-1 settlement is the responsibility of `_advance_round`, which does NOT update). | 🛑 Blocker (CR-05 — same root cause) | Compounding: 12 anti-eco rounds across 3 maps × per-round error → distorts both theo_series and theo_map[i]. |
| `src/pricing/live_theo.py` | 253-262 | `_within_map_p_a_wins` inlines its own state-advance (does not call `_advance_round`), so the same `pistol_winner_a` propagation defect applies in the future-map sub-DP. | ⚠️ Warning (WR-06 — same root cause as CR-05, scoped to future-map marginals) | Future-map P(A wins map m) uses uncalibrated anti-eco rounds. After CR-05 fix lands in dp.py, the same logic must be replicated here OR the sub-DP refactored to call `_advance_round`. |
| `tests/pricing/test_round_types.py` | 213-222 | `test_anti_eco_with_none_pistol_winner_returns_defensive_05` blesses the broken behavior (asserts the 0.5 fallback as desired output). | ⚠️ Warning (test-level regression risk) | Existing test must be updated or replaced after CR-05 fix to clarify the 0.5 fallback is for malformed external inputs only, not for DP forward-pass states. |
| `tests/pricing/test_live_theo.py` | (synthetic_half_rates) | `_synthetic_half_rates()` uses 0.6/0.5/0.4/0.5 rates that produce p ≈ 0.5 after BT blend — masking asymmetric anti-eco effects. | ⚠️ Warning (coverage gap) | DP-level integration tests cannot detect CR-05 because the anti-eco dispatch error magnitude collapses to ~0 at p ≈ 0.5. |
| (unchanged from prior verification) | — | WR-01..WR-05 + IN-01..IN-04 from original 01-REVIEW.md plus IN-05..IN-07 from latest 01-REVIEW.md still pending — out of scope for the original gap closure (01-06). | ⚠️/ℹ️ | Documented in 01-06-derived-output-fixes-PLAN.md as deferred. |

### Human Verification Required

(none — all checks completable programmatically)

### Gaps Summary

The four BLOCKERs from the original 01-VERIFICATION.md (CR-01..CR-04) remain **CLOSED** at the implementation level (re-confirmed this re-verification cycle):

- **CR-01** ✓ closed: `_p_reach_map_cached` series-clinch short-circuit precedes the `map_idx == m` terminal check at `live_theo.py:495-500`. Regression tests at `test_live_theo.py:515-549` lock both A-clinched and B-clinched cases.
- **CR-02** ✓ closed: BO3 middle-map decisive formula `p_a_wins_m_minus_1 * p_a_wins_m + (1 - p_a_wins_m_minus_1) * (1 - p_a_wins_m)` at `live_theo.py:435`. Law-of-total-probability test at `test_live_theo.py:581-594` provides structural lock-in.
- **CR-03** ✓ closed: three early-return guards in `_compute_vega` at `live_theo.py:578-596`. OT-entry returns the variance of the next-map coinflip leaf, not the buggy `_advance_round` projection. Tests at `test_live_theo.py:658-750` cover symmetric and asymmetric clinch states.
- **CR-04** ✓ closed: `LiveTheoEngine.__call__` wraps `_live_theo_impl` in try/finally; both `_clear_pricing_caches` helpers run on every exit including exceptions. Memory-leak regression test at `test_live_theo.py:782-848` confirms registries reset to 0 after 100 calls (re-confirmed at runtime this cycle: both registries == 0).

**The single open BLOCKER remains CR-05 — same as the prior re-verification.**

`dp._advance_round` and `dp._advance_to_next_map` propagate `BO3State.pistol_winner_a` verbatim through DP recursion. For the natural Phase-4 call site — a pre-match or pre-round-1 state where `pistol_winner_a[map_idx] is None` — the DP recursion never updates `pistol_winner_a[map_idx] = a_wins` when round 1 settles. The result: when DP recursion enters round 2 (`a_round + b_round + 1 == 2`), `round_types.round_p_for_round` correctly identifies the round as anti-eco, looks up `state.pistol_winner_a[state.map_idx]`, finds `None`, and falls into the defensive `return 0.5` branch (round_types.py:148-152). The premise of that branch — *"round 2 implies round 1 is settled, so this shouldn't happen in well-formed states"* — is **false for the DP's own forward simulation** even on well-formed live states.

**Concrete runtime impact (re-confirmed this cycle):**

- Round 2 P(A wins | A won round 1) at fresh BO3 root with `pistol_winner_a=(None,None,None)`: returns `0.5`, expected `GUN_WIN_RATE=0.822`.
- Round 3 same after stepping DP forward twice: returns `0.5`, expected `0.822`. State after both advances still has `pistol_winner_a == (None, None, None)`.
- End-to-end theo_series swing under asymmetric matchups (TeamA 0.55 / TeamB 0.45 across all maps/sides, total=1e9 to suppress shrinkage): unset pistols `0.887` vs set pistols `0.979` — a `9.25pp` swing driven entirely by whether the pistol model is active. (At stronger asymmetry the conviction clip masks; at the prior cycle's TeamA 0.6/TeamB 0.4 the swing was reported as 13pp.)
- Phase 4's `VEGA_DIRECTIONAL_THRESHOLD = 0.04` and `KILL_SWITCH_DEVIATION_C = 20¢` thresholds operate on these series probabilities; a 9-13pp systematic bias would force unintended mode flips and risk false kill-switch trips.

**Goal-impact assessment:**

- ROADMAP must-have #2 explicitly enumerates DEC-011 (pistol/anti-eco modeled with separate inputs) as one of the four audit-engine bug fixes that MUST be locked. CR-05 demonstrates this fix is structurally satisfied only for the narrow case where `pistol_winner_a` is pre-populated by external ingestion before LiveTheoEngine is invoked. For the dominant Phase-4 use case (pre-match pricing with all pistol_winner_a None), the model is silently inactive.
- The CLAUDE.md "Critical Rules" section makes the same claim mandatory ("Pistol + anti-eco modeled explicitly. Rounds 1, 2, 3, 13, 14, 15 use separate probability inputs derived from `match_round_data` and `GUN_WIN_RATE = 0.822`. Constant `p1`/`p2` per half is wrong."). The current implementation violates this rule for the DP forward-pass.
- The fix is mechanical (~15 lines in `dp.py`, mirrored in `live_theo.py`'s `_within_map_p_a_wins`) per the concrete code in `01-REVIEW.md` CR-05 §`Fix:`. Plus one regression test + one updated existing test.

**Recommendation:** route to `/gsd-plan-phase --gaps` with this VERIFICATION.md as input. The single gap (CR-05) is tightly scoped — fix in `dp.py` + `live_theo.py`, add the regression test, update or replace `test_anti_eco_with_none_pistol_winner_returns_defensive_05`. The fix should also document the second-half-pistol limitation (rounds 14/15 cannot be properly conditioned on second-half pistol winner under the current `pistol_winner_a` data shape — flag for Phase 2 or extend the shape to per-half).

Items NOT in the new gap list (intentionally deferred — documented in `01-06-derived-output-fixes-PLAN.md` and `01-REVIEW.md`):

- WR-06 (CR-05 scoped to `_within_map_p_a_wins`) — bundled into the CR-05 fix in this VERIFICATION.md's `missing` list.
- WR-07 (`_within_map_p_a_wins` docstring claims `lru_cache` but uses dict) — documentation papercut, deferred.
- WR-08 (per-`m` re-registration in `_p_reach_map` defeats lru_cache reuse) — performance, out of v1 scope.
- IN-05..IN-07 from latest 01-REVIEW.md — style/maintainability papercuts.
- WR-01..WR-05 + IN-01..IN-04 from original 01-REVIEW.md — already deferred per 01-06 plan.

---

_Re-verified: 2026-04-28T23:45:00Z_
_Verifier: Claude (gsd-verifier, Opus 4.7 1M context)_
_Re-verification mode (#2): CR-01..CR-04 still closed (re-confirmed at source + runtime); CR-05 still open (re-confirmed at runtime: round 2 dispatches to 0.5 instead of GUN_WIN_RATE; end-to-end theo_series swing 9.25pp at TeamA=0.55/TeamB=0.45). No 01-07 plan has landed since the prior re-verification._
