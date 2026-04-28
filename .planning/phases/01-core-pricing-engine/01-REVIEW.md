---
phase: 01-core-pricing-engine
reviewed: 2026-04-28T00:00:00Z
depth: standard
files_reviewed: 15
files_reviewed_list:
  - src/config/constants.py
  - src/pricing/__init__.py
  - src/pricing/blend.py
  - src/pricing/data.py
  - src/pricing/dp.py
  - src/pricing/live_theo.py
  - src/pricing/round_conclusion.py
  - src/pricing/round_types.py
  - tests/config/test_constants.py
  - tests/pricing/__init__.py
  - tests/pricing/test_blend.py
  - tests/pricing/test_dp.py
  - tests/pricing/test_live_theo.py
  - tests/pricing/test_round_conclusion.py
  - tests/pricing/test_round_types.py
findings:
  critical: 4
  warning: 5
  info: 4
  total: 13
status: issues_found
---

# Phase 1: Code Review Report

**Reviewed:** 2026-04-28
**Depth:** standard
**Files Reviewed:** 15
**Status:** issues_found

## Summary

The Phase 1 core pricing engine ships the four locked PRD bug-fix decisions
(Bradley-Terry blend, OT hard-stop, pistol+anti-eco dispatch, conviction clip)
correctly at the surface level — `blend.round_p`, `dp.series_value`, the
round-type dispatcher, and `_clip_conviction` all behave as advertised and the
test suite is dense and well-targeted on those spec lines.

The defects are concentrated in the secondary derived quantities — the
**confidence aggregation** (`_p_reach_map_cached`, `_p_map_decisive`),
the **vega computation** at OT/terminal states, and the **closure-registry
memory model** that backs `series_value`'s memoization. All four BLOCKERs
below produce mathematically-incorrect or operationally-unsafe behavior in
states that the live Phase 4 quoter will reach within a single BO3:

  - CR-01: `_p_reach_map_cached` overcounts unreachable post-clinch paths,
    poisoning every `_compute_confidence` value when any future map is queried.
  - CR-02: `_p_map_decisive` returns the BO5+ placeholder `p_reached * 0.5`
    for the BO3 middle map (`m == state.map_idx + 1`), even though that case
    IS reachable in normal BO3 play.
  - CR-03: `_compute_vega` calls `_advance_round` past the OT hard-stop at
    `total = 24`, silently bypassing the coinflip leaf and producing a
    meaningless squared-deviation against next-map series values.
  - CR-04: `_ROUND_P_FNS` and `_REACH_MAP_FNS` grow unbounded across
    `live_theo` invocations — every call appends new closures (which hold a
    full MatchState + HalfRates) and seeds new `lru_cache(maxsize=None)`
    keyspace. Phase 4's continuous-running quoter will leak memory linearly.

Warnings cover real-but-bounded correctness issues (mutable dict on a frozen
MatchState, `_marginal_map_prob` defensive 0.5 fallthrough swallowing a
denominator-zero contract, missing terminal-state guard on `_compute_vega`,
loose marginalization tolerance). Info items are CRule-12 borderline cases
and minor maintainability concerns.

## Critical Issues

### CR-01: `_p_reach_map_cached` returns 1.0 for already-clinched terminal recursion paths

**File:** `src/pricing/live_theo.py:469-474`
**Issue:** The terminal-check order is wrong. Inside the recursion, `_advance_to_next_map` always increments `map_idx` even when one team has already clinched the series (`a_map_score == 2` or `b_map_score == 2`). When the recursion lands at `state.map_idx == m` AND `state.a_map_score >= 2`, the function returns `1.0` (treating the unreachable path as "reached") because the `state.map_idx == m` check fires BEFORE the clinch check.

This inflates `p_reached` for the last BO3 map: every path through the recursion that reaches `(map_idx=2, a_map_score=2, ...)` or `(map_idx=2, b_map_score=2, ...)` is incorrectly counted as "reaching map 2," even though map 2 is never played in a 2-0 series. `_compute_confidence` then weights `data_w[2]` by an inflated `p_decisive(map=2)`, producing a confidence value that double-counts the clinched paths.

The current test suite never catches this: `test_p_map_decisive_for_future_map_in_bo3` asserts only `0.0 <= p_decisive <= 1.0`, never the actual reachability mass.

**Fix:**
```python
@functools.lru_cache(maxsize=None)
def _p_reach_map_cached(
    state: BO3State,
    round_p_fn_id: int,
    m: int,
) -> float:
    # Series clinched BEFORE checking map_idx == m: a clinched series
    # never plays subsequent maps regardless of map_idx advance.
    if state.a_map_score >= 2 or state.b_map_score >= 2:
        return 0.0
    if state.map_idx == m:
        return 1.0
    if state.map_idx > m:
        return 0.0
    # ... rest unchanged
```

Add a regression test:
```python
def test_p_reach_map_zero_for_clinched_series_state() -> None:
    """A 2-0 BO3 cannot reach map 2 even though map_idx may equal 2."""
    bo3 = BO3State(
        map_idx=2, a_map_score=2, b_map_score=0,
        a_round=0, b_round=0, side_orient="a_atk",
        map_pool=("Lotus", "Bind", "Haven"),
        pistol_winner_a=(True, True, None),
    )
    fn = _ConstantRoundPFn(0.5)
    assert _p_reach_map(bo3, fn, m=2) == 0.0
```

---

### CR-02: `_p_map_decisive` uses BO5+ placeholder for BO3 middle map (m=1, map_idx=0)

**File:** `src/pricing/live_theo.py:424-428`
**Issue:** Case 3 (future map) only handles `m == len(map_pool) - 1` correctly. For `m < len(map_pool) - 1` AND `m > state.map_idx`, the code returns `p_reached * 0.5` with the comment "Non-last future map (BO5+ extension). Phase 1 BO3: unreachable branch." But this branch IS reachable in BO3: `state.map_idx=0, m=1` satisfies both `m > state.map_idx` and `m != len(map_pool) - 1` (with `len(map_pool) == 3`).

The actual P(map 1 decisive | state) in a fresh BO3 is `P(map 0 winner also wins map 1) ≠ 0.5` in general. The placeholder `* 0.5` produces an arbitrary value driven by `p_reached` (which is itself ~1.0 under CR-01), severely distorting `_compute_confidence`.

The test suite does not catch this: `test_p_map_decisive_for_future_map_in_bo3` only exercises `m=2`.

**Fix:** Either (a) compute the correct P(decisive | reached) for the middle map by summing per-pre-state probabilities, or (b) reject non-last future maps as unsupported in BO3 with a `raise ValueError`. Recommended (a):
```python
if m == len(state.map_pool) - 1:
    return p_reached  # BO3 last map: always decisive once reached.
# Middle map decisive iff map(m-1) winner also wins map m.
# In BO3, m=1 is decisive iff one team is 2-0 after map 1.
# P(decisive | reached) = P(map 0 winner == map 1 winner | reached map 1).
# For m=1 from map_idx=0, p_reached == 1.0 always.
p_a_wins_m_minus_1 = _marginal_map_prob(state, m - 1, half_rates)
p_a_wins_m = _within_map_p_a_wins(...)  # already used for m-th map marginal
return p_reached * (
    p_a_wins_m_minus_1 * p_a_wins_m + (1 - p_a_wins_m_minus_1) * (1 - p_a_wins_m)
)
```

Add tests covering `m=1` from `state.map_idx=0`.

---

### CR-03: `_compute_vega` bypasses OT hard-stop at `a_round=12, b_round=12`

**File:** `src/pricing/live_theo.py:539-545`
**Issue:** `_compute_vega` calls `_advance_round(root, a_wins=True/False)` unconditionally. At a state with `a_round=12, b_round=12` (regulation OT entry, `total=24`), `_advance_round` produces `(13, 12)` and `(12, 13)` — sums of 25, past the DP's OT hard-stop at total=24. Both advanced states hit the WIN_THRESHOLD map terminal in `_series_value_cached` and recurse into next-map series values, completely skipping the OT-as-coinflip leaf documented in DEC-009 / CRule 5.

The semantic contract for vega — "variance of theo_series implied by next round outcome" — is undefined at total=24 because the DP collapses OT to a single coinflip rather than modeling per-round OT play. The current implementation silently returns a value that conflates "winning one OT round" with "winning the entire OT half plus the map," which is the exact bug class CRule 5 prohibits in the DP.

This propagates into `TheoOutput.vega`, which Phase 4 uses for the directional-mode flip (DEC-001, `VEGA_DIRECTIONAL_THRESHOLD = 0.04`). Spurious large vega at OT entry would force a mode flip on a meaningless signal.

**Fix:** Short-circuit vega at OT and terminal states:
```python
def _compute_vega(root: BO3State, round_p_fn: RoundPFn) -> float:
    # Series terminal: theo is constant, vega is 0.
    if root.a_map_score >= 2 or root.b_map_score >= 2:
        return 0.0
    # Within-map terminal: map is decided, no per-round vega.
    if root.a_round >= WIN_THRESHOLD or root.b_round >= WIN_THRESHOLD:
        return 0.0
    # OT coinflip leaf: vega is variance of the leaf, not of `_advance_round`.
    if root.a_round + root.b_round >= REGULATION_HALF * 2:
        # Variance of the 50/50 between next-map series outcomes.
        next_side = round_p_fn.next_side_orient_for(root.map_idx + 1)
        v_a = series_value(_advance_to_next_map(root, a_won=True, next_side_orient=next_side), round_p_fn)
        v_b = series_value(_advance_to_next_map(root, a_won=False, next_side_orient=next_side), round_p_fn)
        mean = 0.5 * (v_a + v_b)
        return 0.5 * (v_a - mean) ** 2 + 0.5 * (v_b - mean) ** 2
    # Standard regulation case (existing body):
    state_a_wins = _advance_round(root, a_wins=True)
    ...
```

Add explicit OT-vega regression test.

---

### CR-04: Unbounded growth of `_ROUND_P_FNS` / `_REACH_MAP_FNS` registries — memory leak in long-running quoter

**File:** `src/pricing/dp.py:159-165` and `src/pricing/live_theo.py:433-438`
**Issue:** Every call to `series_value(state, round_p_fn)` invokes `_register_round_p_fn(fn)`, which appends to a module-level `list[RoundPFn]` and returns its index. This list is never pruned. The closure (a `_RoundPFnImpl` holding the full `MatchState` + `HalfRates` references) is therefore retained for the process lifetime. Same defect on `_REACH_MAP_FNS` in `live_theo.py:433-438`.

Compounding this, `lru_cache(maxsize=None)` keys on `(state, round_p_id)`. Each `live_theo` call generates fresh `round_p_id`s (one per nested `series_value` call — `_compute_vega` alone makes three; `_marginal_map_prob` makes more for each map). After N quoter ticks, the cache holds N × O(BO3-state-space) entries that can never be reused (because the int id changed) and can never be evicted (`maxsize=None`).

In a Phase 4 production deployment running through a 90-minute BO3 with sub-second tick cadence, this is a linear-in-time memory leak. The dp.py module docstring states "Cache survives the process; clear via `_series_value_cached.cache_clear()` between unrelated test cases" — that operational note is necessary precisely because the design leaks.

**Fix:** Two viable directions; either is acceptable:

(a) **Make the `RoundPFn` itself the cache key.** Switch `_RoundPFnImpl` to be `frozen=True` AND make its components hashable (replace `MatchState.pistol_winner_a: dict` with a tuple — see WR-04). Then `series_value` can pass the closure directly, drop the registry, and rely on Python's identity hashing for closure stability across calls within one match.

(b) **Reset the registry per `live_theo` call.** Have `LiveTheoEngine.__call__` (or a context-manager wrapper) clear `_ROUND_P_FNS`, `_REACH_MAP_FNS`, `_series_value_cached.cache_clear()`, and `_p_reach_map_cached.cache_clear()` at the end of each invocation. This sacrifices the memoization across calls (which is already useless because the int id changes) but bounds memory.

Add a regression assertion (run after a synthetic 100-call loop):
```python
def test_no_memory_leak_across_live_theo_calls() -> None:
    from src.pricing import dp, live_theo
    initial_dp = len(dp._ROUND_P_FNS)
    initial_reach = len(live_theo._REACH_MAP_FNS)
    hr = _synthetic_half_rates()
    state = _synthetic_match_state()
    engine = LiveTheoEngine(half_rates=hr)
    for _ in range(100):
        engine(state)
    # Some growth is acceptable for caching; unbounded linear growth is not.
    assert len(dp._ROUND_P_FNS) - initial_dp < 100, "Registry leaks per-call"
    assert len(live_theo._REACH_MAP_FNS) - initial_reach < 100
```

## Warnings

### WR-01: `MatchState.pistol_winner_a` is `dict` on a `frozen=True, slots=True` dataclass — defeats immutability contract

**File:** `src/pricing/data.py:101`
**Issue:** `pistol_winner_a: dict[int, Optional[bool]]` is mutable. While `frozen=True` blocks reassigning the field, it does NOT block `state.pistol_winner_a[0] = True`. Any caller can silently mutate the dict, causing:
- Stale `BO3State.pistol_winner_a` tuples in the lru_cache (the tuple was packed at one snapshot, but the source dict drifted).
- Inconsistent `round_p_for_round` results for the same `state` reference across calls.

Every other field (`map_pool: tuple`, `map_winners: tuple`, `map_side_orients: tuple`) is correctly tuple-typed. `pistol_winner_a` is the outlier.

**Fix:** Promote to a tuple keyed by `map_idx`:
```python
pistol_winner_a: tuple[Optional[bool], ...]  # length == len(map_pool)
```
And in `_bo3_state_from_match_state`:
```python
return BO3State(..., pistol_winner_a=state.pistol_winner_a)  # already a tuple
```
This also unlocks CR-04 fix (a) — `MatchState` becomes hashable.

---

### WR-02: `_marginal_map_prob` swallows denominator-zero with silent 0.5 — masks DP terminal states

**File:** `src/pricing/live_theo.py:171-175`
**Issue:** When `abs(v_after_a - v_after_b) < 1e-12`, the function returns `0.5` defensively. This fires legitimately at series-terminal states (both branches return the same constant) but ALSO fires when `series_value` has memoization-cache pollution from a different closure (CR-04) that returned identical values for both branches by coincidence.

The 0.5 fallback is plausibly wrong: at a state where `state.a_map_score == 2`, the "current map" doesn't exist — A already won — and 0.5 is a meaningless P(A wins map). Phase 4 will consume `theo_map[map_idx]` directly and a 0.5 there masks that the series is over.

**Fix:** Distinguish terminal from numerical degeneracy:
```python
if state.a_map_score >= 2:
    return CONVICTION_CLIP_HIGH
if state.b_map_score >= 2:
    return CONVICTION_CLIP_LOW
# ... rest of m == map_idx logic
denom = v_after_a - v_after_b
if abs(denom) < 1e-12:
    # Genuine numerical degeneracy: log + return 0.5 as last resort.
    return 0.5
```

---

### WR-03: `_p_map_decisive` already-played-map computation reads `state.map_winners[m]` without bounds check

**File:** `src/pricing/live_theo.py:399-410`
**Issue:** For `m < state.map_idx`, the code accesses `state.map_winners[m]` and `state.map_winners[: m + 1]` directly. If `state.map_winners` length is shorter than `state.map_idx + 1` (a malformed MatchState), this raises `IndexError` rather than returning a defensive value. The Phase 1 contract has `map_winners: tuple[Optional[bool], ...]` with no length invariant declared — Phase 3 ingestion could violate it.

Same concern in `_compute_confidence` indirectly via `_p_map_decisive`.

**Fix:** Add a length precondition at the top of `_p_map_decisive`, or document the invariant on MatchState and add a `__post_init__` validator:
```python
@dataclass(frozen=True, slots=True)
class MatchState:
    ...
    def __post_init__(self) -> None:
        if len(self.map_winners) != len(self.map_pool):
            raise ValueError(
                f"map_winners length {len(self.map_winners)} != map_pool length {len(self.map_pool)}"
            )
        if len(self.map_side_orients) != len(self.map_pool):
            raise ValueError(...)
```

---

### WR-04: `_RoundPFnImpl._effective_side` defensive `'a_atk'` literal contradicts CRule 12 / DP design

**File:** `src/pricing/live_theo.py:106-108` and `src/pricing/live_theo.py:117-118`
**Issue:** When `map_idx >= len(self.match_state.map_side_orients)`, the closure returns the literal `"a_atk"`. The DP module went to lengths to forbid hardcoded `'a_atk'` (see `_advance_to_next_map` regression test), and this defensive fallback reintroduces the same literal at the boundary. While the comment says "Past series-clinch; never consumed but defensive," CR-01 demonstrates that "never consumed" assumptions are unsafe when terminal-check ordering changes.

**Fix:** Either raise `IndexError` (fail loud rather than silently default) or reuse the last entry:
```python
def next_side_orient_for(self, map_idx: int) -> str:
    if map_idx >= len(self.match_state.map_side_orients):
        # Unreachable in well-formed series; fail loud to surface bugs early.
        raise IndexError(
            f"map_idx={map_idx} past map_side_orients of len="
            f"{len(self.match_state.map_side_orients)}"
        )
    return self.match_state.map_side_orients[map_idx]
```
Or, if defensive behavior is required, move the fallback constant to `src/config/constants.py` per CRule 12.

---

### WR-05: `test_live_theo_marginalization_consistency_dec002` uses `rel_tol=1e-3, abs_tol=1e-3` — too loose to catch sign errors

**File:** `tests/pricing/test_live_theo.py:721`
**Issue:** The DEC-002 / CRule 2 marginalization identity is the load-bearing acceptance test for "BO3 series and per-map theos come from the same DP." A 1e-3 absolute tolerance would pass even if `theo_map[map_idx]` had a sign error (e.g., reporting P(B wins) instead of P(A wins)) at edge states where the true value is close to 0.5.

The pre-clip identity holds to floating-point precision (the two sides differ only by clipping). The test could assert the pre-clip identity at `1e-9` and a separate clipped identity at `1e-3`.

**Fix:**
```python
def test_live_theo_marginalization_consistency_dec002() -> None:
    ...
    # Pre-clip identity must hold to fp precision:
    expected_unclipped = (
        p_a_wins_current * v_after_a + (1.0 - p_a_wins_current) * v_after_b
    )
    # Reconstruct the clipped theo_series from the unclipped DP root:
    raw_theo_series = series_value(bo3, fn)
    assert math.isclose(raw_theo_series, expected_unclipped, rel_tol=1e-9)
    # Then verify clipping was applied on the output:
    assert out.theo_series == _clip_conviction(raw_theo_series)
```

## Info

### IN-01: `1e-12` numerical-tolerance literal recurs in business logic without a named constant

**File:** `src/pricing/live_theo.py:172, 486, 520`
**Issue:** Three call sites use `1e-12` as the denominator-degeneracy threshold or mass-sum cutoff. CRule 12 / CON-no-magic-numbers covers thresholds and tunables; numerical-tolerance constants are a borderline case but recurring `1e-12` is a smell.

**Fix:** Add `DENOM_DEGENERACY_TOL: Final[float] = 1e-12` to `src/config/constants.py` (with a docstring stating it's a numerical-degeneracy cutoff, not a tunable threshold), and import where used.

---

### IN-02: `_within_map_p_a_wins` reconstructs a fresh `_RoundPFnImpl` and `memo` dict on every call

**File:** `src/pricing/live_theo.py:226-227`
**Issue:** Every `_marginal_map_prob` call for a future map reconstructs a `_RoundPFnImpl` (line 226) and a fresh `memo` dict (line 227). The within-map state space is small enough that this is functionally correct, but it means there is no cache reuse across the three+ calls inside `_compute_confidence` -> `_p_map_decisive` -> `_marginal_map_prob` for the same future map. (Performance is out of v1 scope; flagged as info because the duplication suggests a missed seam.)

**Fix:** Defer to Phase 5 profiling; if hot, hoist the closure construction.

---

### IN-03: `_p_map_decisive` recomputes `_marginal_map_prob` for the current map case via a separate code path

**File:** `src/pricing/live_theo.py:413-417`
**Issue:** Case 2 calls `_marginal_map_prob(state, m, half_rates)`, which itself runs the DP. Then `_compute_confidence` later iterates over `range(len(state.map_pool))` and may invoke `_marginal_map_prob` again indirectly via `_p_map_decisive`. The `theo_map` tuple in the same `TheoOutput` is also computed via `_marginal_map_prob`. Three independent invocations per map per `live_theo` call. Threaded with CR-04, each invocation registers a new closure id.

**Fix:** Compute `theo_map` once in `_live_theo_impl`, pass it into `_compute_confidence`, and have `_p_map_decisive` accept a precomputed `theo_map` tuple.

---

### IN-04: `_compute_confidence` divides by `mass_sum` even though `mass_sum == 1.0` always holds analytically

**File:** `src/pricing/live_theo.py:520-522`
**Issue:** By the law of total probability, `sum_m P(map m decisive | state)` equals 1 for any pre-clinch state in a BO3 (some map IS the clinching map). Dividing by `mass_sum` is therefore a no-op in the common case but masks bugs where `_p_map_decisive` returns inconsistent values across maps (e.g., CR-02's `* 0.5` bug). The defensive `< 1e-12 -> 0.0` branch hides this misbehavior.

**Fix:** After fixing CR-01 and CR-02, add an assertion in tests:
```python
def test_p_map_decisive_sum_equals_one_pre_clinch() -> None:
    hr = _synthetic_half_rates()
    state = _synthetic_match_state()  # 0-0 root
    total = sum(_p_map_decisive(state, m, hr) for m in range(len(state.map_pool)))
    assert math.isclose(total, 1.0, rel_tol=1e-9)
```
This locks in CR-01 / CR-02 fixes structurally.

---

_Reviewed: 2026-04-28_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
