---
phase: 01-core-pricing-engine
verified: 2026-04-29T18:00:00Z
status: passed
score: 3/3 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 2/3
  gaps_closed:
    - "CR-05: dp._advance_round now updates pistol_winner_a[map_idx] at the round-1 boundary with don't-override invariant; rounds 2/3 dispatch to GUN_WIN_RATE = 0.822"
    - "WR-06: _within_map_p_a_wins inline state-advance propagates pistol_winner_a through the future-map sub-DP via per-branch tuple-rebuild; memo key extended to include pistol"
  gaps_remaining: []
  regressions: []
  new_findings: []
gaps: []
human_verification: []
---

# Phase 1: Core Pricing Engine Verification Report (Re-verification #3)

**Phase Goal:** Single canonical `live_theo(state) → (theo_series, theo_map, vega, confidence)` with no data dependencies — between-round live pricing works end-to-end.
**Verified:** 2026-04-29T18:00:00Z
**Status:** passed
**Re-verification:** Yes — third pass. The previous re-verification (2026-04-28T23:45) confirmed CR-01..CR-04 closed but flagged CR-05 (BLOCKER) still open. Plan 01-07 has now landed (commits `f4061dd`, `4792ffa`, `47b387b`, `874d26c`, `8215a5a`, `15b822a` — verified present in `git log`) and closes both CR-05 and WR-06.

## Re-verification Summary

This is the third re-verification of Phase 01. The prior re-verification documented one open BLOCKER (CR-05) — `dp._advance_round` and `dp._advance_to_next_map` propagated `pistol_winner_a` verbatim, and `live_theo._within_map_p_a_wins` had the same defect (WR-06) — meaning anti-eco rounds dispatched to the defensive 0.5 fallback instead of `GUN_WIN_RATE = 0.822` for the natural Phase-4 pre-pistol call site, with a documented 9.25pp end-to-end theo_series error at TeamA=0.55/TeamB=0.45.

This re-verification confirms BOTH closures structurally and behaviorally:

1. **CR-01..CR-04 remain closed** — re-confirmed at the source level (`live_theo.py:471-473`, `live_theo.py:533-538`, `live_theo.py:617-634`, `live_theo.py:672-684`).
2. **CR-05 closed** — `src/pricing/dp.py:156-187` now writes `pistol_winner_a[state.map_idx] = a_wins` when round 1 settles AND the slot is currently None. Don't-override guard at line 172 (`existing is None`) preserves ingested live values. Tuple-rebuild preserves BO3State `frozen+slots+hashable` invariants. Runtime probe verified: round 2 dispatch returns `0.8220` (= GUN_WIN_RATE); round 3 dispatch returns `0.8220`; B-wins-pistol returns `0.1780` (= 1 − GUN_WIN_RATE).
3. **WR-06 closed** — `src/pricing/live_theo.py:280-289` mirrors the propagation through the future-map sub-DP's inline state-advance via per-branch `pistol_after_a` / `pistol_after_b` tuples. Memo key extended to `(a_round, b_round, side_orient, pistol)` — well-typed and hashable.
4. **Test count: 147 → 152.** All 5 new tests verified present (`test_dp_anti_eco_uses_gun_win_rate_after_round_1_branch`, `test_dp_anti_eco_returns_complement_after_b_wins_round_1`, `test_dp_advance_round_does_not_override_already_settled_pistol`, `test_within_map_anti_eco_uses_gun_win_rate_after_round_1_branch`, `test_live_theo_asymmetric_pistols_match_unset_pistols_after_dp_propagation`). Defensive-fallback test renamed to `test_anti_eco_with_none_pistol_winner_returns_defensive_05_for_malformed_external_input` (`test_round_types.py:213`).
5. **Phase-2 follow-up documented** — `dp.py:33-47` records the second-half pistol limitation as a NEW Phase-1 simplification: `pistol_winner_a` is keyed only by `map_idx` so rounds 14/15 currently consult the first-half pistol winner. Documented as out-of-scope for Phase 1; deferred to Phase 2 (REQ-round-event-data-pipeline). Tracked downstream as code-review WR-02 (Warning).

The phase status is now `passed`. All three must-haves are verified.

## Goal Achievement

### Observable Truths

| #   | Truth | Status     | Evidence       |
| --- | ----- | ---------- | -------------- |
| 1   | Must-have 1: `live_theo(state)` returns a `TheoOutput` dataclass with `theo_series, theo_map, vega, confidence`; no other pricing entry points exist (DEC-010); LiveTheoEngine bundle is the only API surface for the math layer. | ✓ VERIFIED | `LiveTheoEngine` is the only public callable; `src/pricing/__init__.py:19` declares `__all__ == ['LiveTheoEngine', 'TheoOutput', 'MatchState', 'HalfRates']` (verified at runtime); forbidden-symbol grep `^def (series_theo\|series_theo_no_sides\|series_theo_from_map_probs\|model_series_prob\|_signal_strength)` over `src/pricing/` returns no matches (exit=1). End-to-end `engine(state)` returns `TheoOutput` with all four fields populated. |
| 2   | Must-have 2: Four documented audit-engine bugs are fixed: Bradley-Terry blend (DEC-003), OT hard-stop at total=24 (DEC-009), pistol/anti-eco modeled with separate inputs (DEC-011), conviction clips at [0.01, 0.99] (DEC-012). | ✓ VERIFIED | (a) BT blend ✓ (`src/pricing/blend.py:59` formula; symmetry hypothesis test). (b) OT hard-stop ✓ (`src/pricing/dp.py:290` total=`REGULATION_HALF * 2` triggers `_ot_coinflip_leaf`; CR-03 `_compute_vega` honors hard-stop at `live_theo.py:623`). (c) **Pistol/anti-eco ✓ NOW VERIFIED** — `dp._advance_round` (lines 169-176) and `_within_map_p_a_wins` (lines 280-289) propagate `pistol_winner_a` through DP recursion. Runtime probe: `_RoundPFnImpl(...)(_advance_round(bo3_with_None_pistols, a_wins=True))` returns `0.8220` (= GUN_WIN_RATE), not the previous broken 0.5. The defensive 0.5 fallback at `round_types.py:152` is now reserved for malformed external input only (test renamed to reflect this). (d) Conviction clip ✓ (`_clip_conviction` at `live_theo.py:318-320`). |
| 3   | Must-have 3: Property tests pass — DP value ∈ [0,1] for any state; symmetric inputs match `p²(3−2p)` closed form; Bradley-Terry symmetry; theo_series consistent with sum over theo_map[] outcomes. | ✓ VERIFIED | `pytest tests/` reports `152 passed in 83.44s`. Property tests pass: `test_dp_value_in_unit_interval` (hypothesis), `test_dp_symmetric_input_matches_closed_form` (hypothesis vs `_bo3_series_prob`), `test_round_p_bradley_terry_symmetry` (hypothesis), `test_live_theo_marginalization_consistency_dec002`. New invariant: `test_p_map_decisive_sum_equals_one_pre_clinch` (CR-02 lock at `test_live_theo.py:581-594`). End-to-end behavioral lock: `test_live_theo_asymmetric_pistols_match_unset_pistols_after_dp_propagation` asserts `theo_set_AAA > theo_unset > theo_set_BBB` with meaningful gap > 0.1 — RED on main, GREEN post-01-07. mypy --strict on `src/pricing/` exits 0 (`Success: no issues found in 7 source files`); ruff exits 0 on `src/pricing/` and `tests/pricing/` (`All checks passed!`). |

**Score:** 3/3 truths verified.

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `src/config/constants.py` | 4 Phase 1 constants (`CONVICTION_CLIP_LOW`, `CONVICTION_CLIP_HIGH`, `MIN_ROUNDS_FULL_WEIGHT`, `BT_BLEND_EPSILON`) with `Final[...]`; `GUN_WIN_RATE = 0.822` | ✓ VERIFIED | Lines 79-107 (Phase-1 additions); `GUN_WIN_RATE` at line 58. |
| `src/pricing/blend.py` | Bradley-Terry log-odds blend with input clip | ✓ VERIFIED | Formula at line 59; input clip at lines 57-58. |
| `src/pricing/dp.py` | BO3State, RoundPFn Protocol, `series_value`, helpers, OT hard-stop, `_clear_pricing_caches`, **CR-05 pistol_winner_a propagation in `_advance_round`** | ✓ VERIFIED | All artifacts present. CR-05 fix at lines 169-176 (don't-override guard at line 172); module docstring at lines 33-47 documents the Phase-2 follow-up for the second-half pistol limitation. OT hard-stop at line 290; `_clear_pricing_caches` at line 233. |
| `src/pricing/round_types.py` | round_p_for_round dispatch, HalfRates Protocol, side helpers, TYPE_CHECKING guard | ✓ VERIFIED | Dispatch correct in isolation; defensive 0.5 fallback at line 152 now reserved for malformed external input only (test re-scoped + renamed). |
| `src/pricing/round_conclusion.py` | RoundConclusionLookup skeleton, _Cell shrinkage, RoundConclusionFn Protocol, _PHASE_1_FLAT_CELL_VALUE | ✓ VERIFIED | All present; flat-0.5 invariant locked by hypothesis test. |
| `src/pricing/data.py` | HalfRates concrete impl, MatchState (17 fields), TheoOutput (4 fields) | ✓ VERIFIED | All three dataclasses present at lines 32-169. |
| `src/pricing/live_theo.py` | LiveTheoEngine, _live_theo_impl, _RoundPFnImpl, _marginal_map_prob, _p_map_decisive (CR-02), _compute_confidence, _compute_vega (CR-03), _data_weight_for_map, _clip_conviction, _p_reach_map_cached (CR-01), _clear_pricing_caches, try/finally (CR-04), **WR-06 pistol_winner_a propagation in `_within_map_p_a_wins`** | ✓ VERIFIED | All CR-01..CR-04 fixes still present (verified line-by-line). WR-06 fix at lines 280-289 (per-branch tuple-rebuild + extended memo key at line 251). |
| `src/pricing/__init__.py` | Re-exports LiveTheoEngine, TheoOutput, MatchState, HalfRates; `__all__` exactly those four | ✓ VERIFIED | 19 lines; `__all__` matches verbatim. |
| `tests/pricing/{test_blend, test_dp, test_round_types, test_round_conclusion, test_live_theo}.py` | Property + unit + regression tests (152 total) | ✓ VERIFIED | 152 tests collected; 152 pass. New CR-05 / WR-06 regression tests verified present in `test_dp.py` and `test_live_theo.py`. |

### Key Link Verification

| From | To  | Via | Status | Details |
| ---- | --- | --- | ------ | ------- |
| `src.pricing.__init__` | `LiveTheoEngine` | `from src.pricing.live_theo import LiveTheoEngine` | ✓ WIRED | Confirmed at runtime. |
| `LiveTheoEngine.__call__` | `_live_theo_impl` (try/finally cleanup) | direct call wrapped in try/finally | ✓ WIRED | CR-04 fix at lines 672-684; cleanup runs in `finally`. |
| `LiveTheoEngine.__call__` | `dp._clear_pricing_caches` + `live_theo._clear_pricing_caches` | local import + finally-block calls | ✓ WIRED | Memory-leak regression test confirms registries reset to 0 after 100 calls. |
| `_live_theo_impl` | `dp.series_value` (theo_series) | direct call | ✓ WIRED | Verified line 354 + clip on line 355. |
| `_live_theo_impl` | `_marginal_map_prob` (theo_map) | per-map comprehension | ✓ WIRED | Lines 356-358; uses BO3 marginalization identity (DEC-002). |
| `_compute_confidence` | `_p_map_decisive` (CR-01 fixed) + `_data_weight_for_map` | iteration over map_pool | ✓ WIRED | CR-01 fix at line 533 ensures `_p_reach_map_cached` returns 0.0 for clinched series. |
| `_p_map_decisive` case 3 | `_marginal_map_prob(state, m-1)` + `_marginal_map_prob(state, m)` | BO3 middle-map formula at line 473 | ✓ WIRED | CR-02 fix landed; test_p_map_decisive_sum_equals_one_pre_clinch passes. |
| `_compute_vega` | early-return guards at series terminal, within-map terminal, OT entry | three early-return blocks at lines 617, 620, 623 | ✓ WIRED | CR-03 fix landed. |
| `dp._advance_round` | `pistol_winner_a` update on round-1 completion | tuple-rebuild at lines 169-176 with `existing is None` guard | ✓ WIRED | **CR-05 closed.** Runtime probe: `_advance_round(bo3_with_None_pistols, a_wins=True).pistol_winner_a == (True, None, None)`. Don't-override invariant verified: `_advance_round(bo3_with_pistol_set_to_False, a_wins=True).pistol_winner_a[0] == False`. |
| `_within_map_p_a_wins` | `pistol_winner_a` propagation in inline state advance | per-branch tuple-rebuild at lines 280-289 + memo-key extension at 251 | ✓ WIRED | **WR-06 closed.** Strict-ordering test `test_within_map_anti_eco_uses_gun_win_rate_after_round_1_branch` passes. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| `theo_series` (TheoOutput field) | `series_value(bo3, fn)` clipped | `dp.series_value` (correct OT hard-stop, CR-05-fixed anti-eco dispatch) | ✓ Yes | ✓ FLOWING — runtime probe confirms theo_series is non-degenerate under asymmetric matchups (post-fix unset = 0.867 lies between set_AAA = 0.979 and set_BBB = 0.672, reflecting a true marginalization). |
| `theo_map` (TheoOutput field) | `_marginal_map_prob(state, m, half_rates)` for each m | `dp.series_value` (current map) and `_within_map_p_a_wins` (future maps) | ✓ Yes | ✓ FLOWING — both paths now correctly propagate `pistol_winner_a` (CR-05 in dp.py + WR-06 in live_theo.py). |
| `vega` (TheoOutput field) | `_compute_vega(bo3, fn)` with terminal/OT guards | `series_value` calls honor OT hard-stop via early-return at line 623 | ✓ Yes | ✓ FLOWING — CR-03 closed; underlying `round_p_fn(root)` now correctly dispatches anti-eco rounds via the CR-05/WR-06 fix. |
| `confidence` (TheoOutput field) | `_compute_confidence` → `_p_map_decisive` → `_p_reach_map_cached` (CR-01-fixed) + `_data_weight_for_map` | CR-01 + CR-02 fixes landed; sum-over-m == 1 test passes | ✓ Yes | ✓ FLOWING — structural law of total probability holds; underlying `_marginal_map_prob` calls now use the CR-05/WR-06-fixed DP. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Full pricing test suite | `.venv/Scripts/python.exe -m pytest tests/ -q --tb=short` | `152 passed in 83.44s` | ✓ PASS |
| mypy strict on src/pricing | `.venv/Scripts/python.exe -m mypy --strict src/pricing/` | `Success: no issues found in 7 source files` | ✓ PASS |
| ruff on src/pricing/ + tests/pricing/ | `.venv/Scripts/python.exe -m ruff check src/pricing/ tests/pricing/` | `All checks passed!` | ✓ PASS |
| Forbidden-symbol absence (CRule 1 / DEC-010) | `grep -RE "^def (series_theo\|series_theo_no_sides\|series_theo_from_map_probs\|model_series_prob\|_signal_strength)" src/pricing/` | exit=1 (no matches) | ✓ PASS |
| Public surface contract | `python -c "import src.pricing as p; print(p.__all__)"` | `['LiveTheoEngine', 'TheoOutput', 'MatchState', 'HalfRates']` | ✓ PASS |
| **CR-05 R2 dispatch** | `_RoundPFnImpl(...)(_advance_round(bo3_with_None_pistols, a_wins=True))` | returns `0.8220` (= GUN_WIN_RATE) | ✓ PASS |
| **CR-05 R3 dispatch** | step DP forward A wins R1+R2, then dispatch | returns `0.8220`; `pistol_winner_a == (True, None, None)` after first advance | ✓ PASS |
| **CR-05 B-wins-pistol** | `_RoundPFnImpl(...)(_advance_round(bo3_with_None_pistols, a_wins=False))` | returns `0.1780` (= 1 − GUN_WIN_RATE) | ✓ PASS |
| **CR-05 don't-override** | `_advance_round(bo3_with_pistol[0]=False, a_wins=True).pistol_winner_a[0]` | returns `False` (preserved) | ✓ PASS |
| **CR-05 + WR-06 regression tests** | `pytest -k "anti_eco or pistol or asymmetric"` | 8 passed (5 new tests + 3 carry-over) | ✓ PASS |
| Test count | `pytest tests/ --collect-only -q` | `152 tests collected` (was 147 pre-01-07) | ✓ PASS |
| 6 task commits present | `git log --oneline` | `f4061dd, 4792ffa, 47b387b, 874d26c, 8215a5a, 15b822a` all present | ✓ PASS |

### Requirements Coverage

All 10 phase requirement IDs declared across plan frontmatter cross-reference cleanly to REQUIREMENTS.md.

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| REQ-bo3-dp-engine | 01-02, 01-07 | Generalized BO3 DP `series_value(state, round_p_fn) → float`; memoized; range-invariant; matches p²(3-2p) closed form | ✓ SATISFIED | DP recursion at `dp.py:256-298` + `lru_cache(maxsize=None)` + property tests; OT hard-stop at line 290 confirmed; CR-05 closure ensures the recursion now correctly dispatches anti-eco rounds. |
| REQ-bradley-terry-blend | 01-01 | `(a*(1-b)) / (a*(1-b) + (1-a)*b)` with input clip; symmetry holds | ✓ SATISFIED | `src/pricing/blend.py:59`; `test_round_p_bradley_terry_symmetry` (hypothesis). |
| REQ-pistol-anti-eco-modeling | 01-03, 01-07 | Rounds {1, 13} pistol; {2, 3, 14, 15} anti-eco using GUN_WIN_RATE=0.822; others gunround | ✓ SATISFIED | Dispatch logic correct in `round_types.py:140-153`; **CR-05/WR-06 closure** means the DP forward-pass now propagates `pistol_winner_a` through recursion via `dp._advance_round` (lines 169-176) and `_within_map_p_a_wins` (lines 280-289). Runtime probe: `0.8220` for round 2 dispatch (= GUN_WIN_RATE). End-to-end behavioral test (`test_live_theo_asymmetric_pistols_match_unset_pistols_after_dp_propagation`) locks the post-fix invariant. Phase-1 simplification: rounds 14/15 dispatch on first-half pistol (Phase-2 follow-up documented in `dp.py:33-47`). |
| REQ-ot-handling | 01-02, 01-06 | DP hard-stop at total=24 with OT-as-coinflip leaf | ✓ SATISFIED | DP recursion `dp.py:290` + `_ot_coinflip_leaf` `dp.py:301-323`; CR-03 closure ensures `_compute_vega` honors the hard-stop at `live_theo.py:623`. |
| REQ-round-conclusion-lookup (skeleton) | 01-04 | 5-tier hierarchical fallback chain skeleton; flat 0.5 in Phase 1; SHRINK_PRIOR-imported Bayesian shrinkage | ✓ SATISFIED | All artifacts present; flat-0.5 invariant locked by hypothesis test. |
| REQ-canonical-live-theo | 01-05, 01-06, 01-07 | Single function (LiveTheoEngine bundle) `live_theo(state) → TheoOutput`; no audit triplet | ✓ SATISFIED | LiveTheoEngine is the only public callable; `__all__` matches; audit triplet absent. |
| REQ-theo-series-output | 01-05 | `theo_series ∈ [0, 1]` for all reachable states | ✓ SATISFIED | `_clip_conviction` ensures range; hypothesis property tests pass. Numerical value now correctly reflects pistol+anti-eco model after CR-05/WR-06 closure. |
| REQ-theo-map-output | 01-05 | Per-map `theo_map[i] ∈ [0, 1]`; consistent with theo_series under marginalization | ✓ SATISFIED | `test_live_theo_marginalization_consistency_dec002` passes; `test_p_map_decisive_sum_equals_one_pre_clinch` locks law of total probability post-fix. |
| REQ-confidence-output | 01-05, 01-06 | confidence ∈ [0, 1]; DP-mass-weighted per D-08 | ✓ SATISFIED | CR-01 + CR-02 closure ensures law of total probability holds. |
| REQ-vega-output | 01-05, 01-06 | `vega = round_p × (theo_a − theo)² + (1 − round_p) × (theo_b − theo)²` per DEC-018 | ✓ SATISFIED | CR-03 closure ensures vega is structurally correct in regulation, at series terminals (0), at within-map terminals (0), and at OT entry (OT-leaf variance). |

**Summary:** 10/10 requirements SATISFIED. No orphaned requirements.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| `src/pricing/dp.py` | 33-47 | Phase-1 simplification documented in module docstring: `pistol_winner_a` is keyed only by `map_idx`, so rounds 14/15 dispatch on FIRST-half pistol winner as a proxy. | ℹ️ Info (carry-forward) | Phase-2 follow-up tracked in roadmap (REQ-round-event-data-pipeline). Quantitatively bounded for Phase 1 — both teams' biases are symmetric. Not a Phase-1 BLOCKER (acknowledged in code review WR-02). |
| `src/pricing/live_theo.py` + `dp.py` | 245-307 / 136-187 | `_within_map_p_a_wins` and `dp._advance_round` duplicate the pistol-propagation + side-flip state-advance logic rather than sharing a helper. | ⚠️ Warning (latent regression risk per code review WR-01) | Both implementations agree behaviorally as of this review — verified by `test_within_map_anti_eco_uses_gun_win_rate_after_round_1_branch` and the end-to-end integration test. Phase 2 will extend `pistol_winner_a` to per-half — at that point both implementations must be updated in lockstep. Not a Phase-1 BLOCKER. |
| `src/pricing/live_theo.py` | 498-509 | Per-`m` `_p_reach_map` re-registration defeats `lru_cache` reuse across `_compute_confidence` iteration (carry-over from prior review's WR-08, now WR-03). | ⚠️ Warning (perf, carry-forward) | Out of v1 scope. CR-04 cleanup bounds memory; cache infrastructure underutilized but not broken. |
| `src/pricing/live_theo.py` | 106-119 | `_RoundPFnImpl._effective_side` and `next_side_orient_for` hardcode `"a_atk"` defensive default (carry-over from IN-02). | ℹ️ Info | Dead branches in well-formed series. Style/defensiveness papercut. |
| `src/pricing/live_theo.py` | 679 | `LiveTheoEngine.__call__` runs `from src.pricing import dp as _dp` inside the hot path (carry-over from IN-01). | ℹ️ Info | Cached import — ~1µs cost; no behavioral impact. |

No BLOCKER anti-patterns. All warnings are documented carry-forwards from the post-01-06 / post-01-07 code review (`01-REVIEW.md` 2026-04-29).

### Human Verification Required

(none — all checks completed programmatically)

### Gaps Summary

**No gaps.** All five BLOCKERs from the original verification chain (CR-01..CR-05) are now closed at the implementation level, with regression-test lock-in:

- **CR-01** ✓ closed by 01-06: `_p_reach_map_cached` series-clinch short-circuit precedes `map_idx == m` terminal at `live_theo.py:533`. Regression tests at `test_live_theo.py:515-549`.
- **CR-02** ✓ closed by 01-06: BO3 middle-map decisive formula at `live_theo.py:471-473`. Law-of-total-probability test at `test_live_theo.py:581-594`.
- **CR-03** ✓ closed by 01-06: three early-return guards in `_compute_vega` at `live_theo.py:617-634`. OT-entry returns variance of next-map coinflip leaf, not buggy `_advance_round` projection.
- **CR-04** ✓ closed by 01-06: `LiveTheoEngine.__call__` wraps `_live_theo_impl` in try/finally; both `_clear_pricing_caches` helpers run on every exit. Memory-leak regression test at `test_live_theo.py:782-848`.
- **CR-05** ✓ closed by 01-07: `dp._advance_round` updates `pistol_winner_a[map_idx] = a_wins` at the round-1 boundary with `existing is None` don't-override guard at `dp.py:172`. Tuple-rebuild preserves BO3State frozen+slots+hashable invariants. Runtime probe verified: round 2 dispatch returns `0.8220` (= GUN_WIN_RATE = 0.822), round 3 dispatch returns `0.8220`, B-wins-pistol returns `0.1780` (= 1 − 0.822). Don't-override invariant verified: `_advance_round(state_with_pistol[0]=False, a_wins=True).pistol_winner_a[0] == False`.
- **WR-06** ✓ closed by 01-07: `_within_map_p_a_wins` inline state-advance propagates `pistol_winner_a` through the future-map sub-DP via per-branch tuple-rebuild at `live_theo.py:280-289`. Memo key extended to `(a_round, b_round, side_orient, pistol)` at line 251 — hashable and well-typed.

The phase goal — **"single canonical `live_theo(state) → (theo_series, theo_map, vega, confidence)` with no data dependencies — between-round live pricing works end-to-end"** — is achieved:

- Single canonical entry point: `LiveTheoEngine` is the only public callable (`__all__ == ['LiveTheoEngine', 'TheoOutput', 'MatchState', 'HalfRates']`); audit triplet absent.
- Returns `TheoOutput` dataclass with all four fields populated and in valid ranges.
- All four documented audit-engine bugs fixed (DEC-003, DEC-009, DEC-011, DEC-012).
- Property tests pass (152/152); hypothesis invariants locked.
- mypy --strict clean (`Success: no issues found in 7 source files`).
- ruff clean (`All checks passed!`).
- 6 atomic 01-07 commits verified present in git history.

**Phase 4 readiness:** The pistol+anti-eco model is now structurally active in the DP forward-pass for the natural pre-match call site. `VEGA_DIRECTIONAL_THRESHOLD = 0.04` and `KILL_SWITCH_DEVIATION_C = 20¢` operate on accurate `theo_series` values; the previously-systematic 9.25pp bias at TeamA=0.55/TeamB=0.45 between unset-pistols and set-pistols is closed (post-fix unset = 0.867 lies between set_AAA = 0.979 and set_BBB = 0.672, reflecting a true marginalization rather than the pre-fix flat-anti-eco baseline).

**Deferred items** (intentionally out of Phase 1 scope, tracked downstream):

- Code-review WR-01 (state-advance duplication between `dp._advance_round` and `_within_map_p_a_wins`) — Phase 2 mandatory lockstep update.
- Code-review WR-02 (rounds 14/15 dispatch on first-half pistol winner) — Phase 2 (REQ-round-event-data-pipeline) extends `pistol_winner_a` to per-half.
- Code-review WR-03 (per-`m` `_p_reach_map` re-registration defeats lru_cache reuse) — perf, post-Phase-1.
- IN-01..IN-04 from latest 01-REVIEW.md — style/maintainability papercuts.
- WR-01..WR-05 + IN-01..IN-04 from original 01-REVIEW.md — already deferred per 01-06 plan.

---

_Re-verified: 2026-04-29T18:00:00Z_
_Verifier: Claude (gsd-verifier, Opus 4.7 1M context)_
_Re-verification mode (#3): CR-01..CR-04 still closed (re-confirmed at source); CR-05 + WR-06 newly closed by plan 01-07 (re-confirmed at source AND runtime). 152/152 tests pass; mypy/ruff clean; public surface contract preserved; forbidden audit-triplet symbols absent. Phase 1 goal achieved._
