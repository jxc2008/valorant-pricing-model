---
phase: 01-core-pricing-engine
reviewed: 2026-04-28T22:00:00Z
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
  critical: 1
  warning: 3
  info: 3
  total: 7
status: issues_found
---

# Phase 1: Code Review Report (Re-review after 01-06 gap closure)

**Reviewed:** 2026-04-28
**Depth:** standard
**Files Reviewed:** 15
**Status:** issues_found

## Summary

Phase 01-06 closed the four BLOCKERs (CR-01..CR-04) flagged in the prior
01-REVIEW.md. The fixes verify cleanly under a line-by-line trace:

  - **CR-01** (`_p_reach_map_cached` terminal-check order): `live_theo.py:495-500`
    short-circuits on `a_map_score >= 2 or b_map_score >= 2` BEFORE the
    `state.map_idx == m` check. Tests at `test_live_theo.py:515-549` lock
    both A-clinched and B-clinched scenarios.
  - **CR-02** (`_p_map_decisive` BO3 middle-map formula): `live_theo.py:432-436`
    replaces the BO5+ `p_reached * 0.5` placeholder with the correct
    `p_reached * (p_{m-1} * p_m + (1 - p_{m-1}) * (1 - p_m))` formula. The
    law-of-total-probability test at `test_live_theo.py:581-594` provides
    structural lock-in.
  - **CR-03** (`_compute_vega` OT/terminal short-circuits): `live_theo.py:578-596`
    early-returns 0 at series and within-map terminals, and uses the OT
    coinflip-leaf variance at total=24 (DEC-009). Tests at
    `test_live_theo.py:658-750` cover symmetric and asymmetric clinch states.
  - **CR-04** (registry/cache cleanup): `LiveTheoEngine.__call__` wraps
    `_live_theo_impl` in `try/finally` and clears both `_ROUND_P_FNS` and
    `_REACH_MAP_FNS` (plus their respective `lru_cache`s) on every call,
    including on exception. Verified by `test_live_theo.py:782-848`.

The follow-up surface scan turned up one BLOCKER and several
warning/info-tier defects not in the original 01-REVIEW.md scope:

  - **CR-05 (BLOCKER, missed in original review)**: `_advance_round` and
    `_advance_to_next_map` propagate `pistol_winner_a` unchanged through DP
    recursion. When `LiveTheoEngine` is invoked at a pre-pistol state
    (i.e., `state.pistol_winner_a[map_idx] is None`, which is the natural
    state at the start of every map), the DP forward-pass settles round 1
    via the half-rates blend but the recursive successor states still hold
    `pistol_winner_a[map_idx] = None`. `round_types.round_p_for_round`
    therefore dispatches rounds {2, 3, 14, 15} to the **defensive 0.5
    fallback** instead of the proper conditional `GUN_WIN_RATE`/`1-GUN_WIN_RATE`
    expectation. The pistol+anti-eco model (DEC-011 / CRule 4) is silently
    inactive for the bulk of pre-match pricing.

The remaining findings are pre-existing quality issues that the original
review didn't catch; warnings document subtle semantic gaps, info items
flag style/maintainability papercuts.

## Critical Issues

### CR-05: DP forward-pass never updates `pistol_winner_a`; anti-eco dispatch silently dead in DP recursion (MISSED in original review)

**File:** `src/pricing/dp.py:104-122`, `src/pricing/dp.py:125-149`, `src/pricing/round_types.py:147-153`

**Issue:** `_advance_round` (and `_advance_to_next_map`) returns a new `BO3State`
that copies `pistol_winner_a` verbatim from the parent state:

```python
return BO3State(
    map_idx=state.map_idx,
    a_map_score=state.a_map_score,
    ...
    pistol_winner_a=state.pistol_winner_a,  # <-- never updated by branch
)
```

`pistol_winner_a` is intended to record who won round 1 (the pistol) of
each map (DEC-011: rounds 2, 3, 14, 15 dispatch on this). Ingestion writes
this entry once round 1 completes. But during DP forward-simulation from a
pre-pistol live state, the DP advances `state.a_round=0, state.b_round=0
→ a_round=1, state.b_round=0` (taking the "A wins round 1" branch) without
ever populating `pistol_winner_a[map_idx] = True`. The same is true for the
"B wins round 1" branch.

When the DP recurses into round 2 (`a_round + b_round + 1 == 2`),
`round_p_for_round` correctly identifies the round as anti-eco, looks up
`state.pistol_winner_a[state.map_idx]`, finds `None`, and falls into the
defensive branch (`round_types.py:148-152`):

```python
if pistol_won_by_a is None:
    # Defensive — round 2 implies round 1 is settled, so this shouldn't
    # happen in well-formed states. Returning 0.5 keeps the DP value in
    # range while flagging the malformed input through the test suite.
    return 0.5
```

The comment's premise — *"round 2 implies round 1 is settled"* — is **false
for the DP's own forward simulation** even on well-formed live states.
Whenever the DP starts from a state where `pistol_winner_a[map_idx]` is
unsettled (which is the *normal* condition at the start of every map),
all anti-eco rounds in the recursion silently flatten to 0.5.

**Concrete impact:** For Phase-4 pre-match pricing on a balanced matchup,
the impact on a single anti-eco round is small (because `0.822 * p +
0.178 * (1-p)` evaluates near 0.5 when `p ≈ 0.5`). For asymmetric matchups
(say `p_pistol_A = 0.6`), the proper expectation is `0.822 * 0.6 +
0.178 * 0.4 = 0.564`, vs. the dead-branch fallback's flat `0.5` — a ~6
percentage-point per-round error. Compounded across 4 anti-eco rounds per
map × 3 maps = 12 anti-eco rounds, this materially distorts both
`theo_series` and `theo_map[i]`.

**Why the existing tests miss it:** `test_anti_eco_with_none_pistol_winner_returns_defensive_05`
(`test_round_types.py:213-222`) explicitly asserts the defensive 0.5
fallback, blessing the broken behavior. The DP-level integration tests
(`test_live_theo.py`) use synthetic half-rates that produce `p ≈ 0.5`
across every map/side combo (`_synthetic_half_rates` line 178+: rates of
0.6/0.5/0.4/0.5), masking the asymmetric-matchup magnitude entirely.

**Fix:** The DP must update `pistol_winner_a[map_idx]` when advancing past
round 1 of a map. The simplest implementation:

```python
def _advance_round(state: BO3State, a_wins: bool) -> BO3State:
    new_a_round = state.a_round + (1 if a_wins else 0)
    new_b_round = state.b_round + (0 if a_wins else 1)
    if new_a_round + new_b_round == REGULATION_HALF:
        new_side_orient = "a_def" if state.side_orient == "a_atk" else "a_atk"
    else:
        new_side_orient = state.side_orient

    # Update pistol_winner_a when advancing past round 1 of the current map.
    # Round 1 completes when the round count was (0, 0) and is now (1, 0) or
    # (0, 1). Only update if the entry is currently None (don't override the
    # ingested live value if already settled).
    new_pistol = state.pistol_winner_a
    if state.a_round == 0 and state.b_round == 0:
        # We're committing the outcome of round 1 (pistol).
        existing = state.pistol_winner_a[state.map_idx]
        if existing is None:
            new_pistol = tuple(
                (a_wins if i == state.map_idx else state.pistol_winner_a[i])
                for i in range(len(state.pistol_winner_a))
            )
    return BO3State(
        map_idx=state.map_idx,
        a_map_score=state.a_map_score,
        b_map_score=state.b_map_score,
        a_round=new_a_round,
        b_round=new_b_round,
        side_orient=new_side_orient,
        map_pool=state.map_pool,
        pistol_winner_a=new_pistol,
    )
```

The same logic must also apply at the start of round 13 (second-half
pistol) — `_advance_round` from total=12 → total=13. The current
`pistol_winner_a` data shape (one slot per map) does not record the
second-half pistol outcome separately, so the dispatch in
`round_types.py:140` for round 13 correctly falls back to the half-rates
blend (Phase-1 simplification A8). But for rounds 14 and 15, the logic
relies on a separately-tracked second-half pistol winner. This dispatch
gap is itself a Phase-1 modelling limitation — flag for Phase 2 follow-up
or extend the pistol_winner_a shape to `tuple[Optional[tuple[bool, bool]], ...]`
per (map, half).

Add a regression test that asserts the DP forward-pass produces a non-flat
P(A wins round 2 | A won round 1) under asymmetric pistol_winner_a propagation:

```python
def test_dp_anti_eco_uses_gun_win_rate_after_round_1_branch() -> None:
    """CR-05: DP recursion must update pistol_winner_a when advancing past
    round 1, so anti-eco rounds use GUN_WIN_RATE (not 0.5 fallback).
    """
    hr = _synthetic_half_rates()
    state = _synthetic_match_state(pistol_winner_a={0: None, 1: None, 2: None})
    fn = _RoundPFnImpl(match_state=state, half_rates=hr)
    bo3 = _bo3_state_from_match_state(state)

    # State at round 2 with A having won round 1: a_round=1, b_round=0.
    state_after_round_1_a = _advance_round(bo3, a_wins=True)
    p_round_2 = fn(state_after_round_1_a)
    # Should be GUN_WIN_RATE (0.822), NOT 0.5.
    assert math.isclose(p_round_2, GUN_WIN_RATE, rel_tol=1e-9), (
        f"Anti-eco round 2 should use GUN_WIN_RATE after A won round 1, got {p_round_2}"
    )
```

This test currently FAILS against the codebase as shipped.

---

## Warnings

### WR-06: `_within_map_p_a_wins` does not propagate pistol outcome through its sub-DP — same root cause as CR-05

**File:** `src/pricing/live_theo.py:204-272`

**Issue:** The within-map sub-DP used for future-map marginals (`m > state.map_idx`)
constructs synthetic states that always carry the BO3State's `pistol_winner_a`
(line 250) — which for future maps is necessarily `None`. The recursion at
line 263-267 advances `a_round` and `b_round` but never updates the
synthetic state's `pistol_winner_a`. Same defect as CR-05, scoped to the
future-map sub-DP. After the CR-05 fix to `_advance_round` lands, the
identical update logic must be replicated in the within-map recursion
(or `_within_map_p_a_wins` should be refactored to call `_advance_round`
directly rather than reimplementing state advance inline).

**Fix:** Either share state-advance helpers between dp.py and the within-map
sub-DP, or duplicate the pistol-update logic at lines 253-262 of
`_within_map_p_a_wins`. Add the analogous regression test asserting that
`_within_map_p_a_wins` produces the GUN_WIN_RATE at round 2 of a future map
when A wins round 1 of that map in the recursion.

---

### WR-07: `_within_map_p_a_wins` docstring claims `functools.lru_cache` but implementation uses a plain `dict`

**File:** `src/pricing/live_theo.py:221-227`

**Issue:** The docstring (line 221) says:

> Memoizes the within-map sub-states with functools.lru_cache. The cache is
> keyed by (a_round, b_round, side_orient) only — closure-bound state
> (map_idx, starting_side, etc.) is stable for the call.

But the implementation (line 227) uses `memo: dict[tuple[int, int, str], float] = {}`,
not `functools.lru_cache`. A future maintainer reading the docstring will
either look for an `@lru_cache` decorator that isn't there, or assume the
cache is shared across calls (it isn't — `memo` is freshly constructed
per `_within_map_p_a_wins` invocation). The comment on line 225 explicitly
calls the closure "lightweight," implying intentional non-sharing, which
contradicts the docstring claim.

**Fix:** Update the docstring to match the implementation:

```python
"""...

Memoizes the within-map sub-states with a per-call ``dict``. The cache is
local to each invocation (a fresh ``memo`` is allocated at line 227) so
sub-results are not shared across `_marginal_map_prob` calls — that
non-sharing is intentional, since the closure-bound `match_state` and
`half_rates` differ across callers.
"""
```

---

### WR-08: Per-`m` re-registration in `_p_reach_map` defeats lru_cache reuse across `_compute_confidence` iteration

**File:** `src/pricing/live_theo.py:460-471`

**Issue:** `_p_reach_map` is the public wrapper that registers `round_p_fn`
in `_REACH_MAP_FNS` and dispatches to the `lru_cache`-decorated
`_p_reach_map_cached`. Each call appends to the registry and returns a
fresh int id. `_compute_confidence` (line 539-548) calls
`_p_map_decisive(state, m, half_rates)` for each `m`; for future maps,
`_p_map_decisive` calls `_p_reach_map(bo3, fn, m)` — registering a new
closure id per map. Since `_p_reach_map_cached` is keyed on
`(state, round_p_fn_id, m)`, two consecutive calls with the same
`(state, fn, m)` but different ids miss the cache.

The recursion inside `_p_reach_map_cached` further calls
`series_value(state, fn)` three times per recursion level (root, after_a,
after_b) — each of which does its own `_register_round_p_fn` in dp.py,
adding to `_ROUND_P_FNS`. The `_series_value_cached` lru_cache is therefore
also missed across these three calls within a single
`_p_reach_map_cached` evaluation.

The CR-04 cleanup correctly bounds the lifetime of these registrations to
a single `live_theo` call, so this is not a memory leak. But the design's
caching infrastructure provides essentially zero benefit during a single
call because the int ids constantly change. **Performance is out of v1
scope per review rules; flagging here as a quality concern because the
cache infrastructure is non-trivial and contributes false confidence
("memoization is in place") that doesn't match runtime behavior.**

**Fix:** Two options post-Phase-1:

(a) Hoist `round_p_fn` registration above the per-`m` and per-recursion
    calls. `_compute_confidence` can register the closure once and pass
    the int id down through `_p_map_decisive` → `_p_reach_map_cached` and
    through `series_value`'s API.

(b) Make `RoundPFn` closures themselves hashable (requires WR-01 from the
    prior review — pistol_winner_a → tuple) and drop the registry
    indirection entirely. CR-04's docstring suggests this was the
    deliberately deferred path.

No regression test required — this is a quality finding, not a
correctness defect.

---

## Info

### IN-05: `LiveTheoEngine.__call__` performs `import` inside the hot path

**File:** `src/pricing/live_theo.py:641`

**Issue:** `__call__` runs `from src.pricing import dp as _dp` on every
invocation. The module is already imported at file top (line 43:
`from src.pricing.dp import (...)`); this re-import only fetches the
already-loaded module reference. Python caches the import, so the
performance cost is small, but the placement is unusual and signals
"defensive against circular import" without actually being needed (no
circular dependency exists between live_theo.py and dp.py).

**Fix:** Hoist to module top alongside the existing import:

```python
from src.pricing import dp as _dp
from src.pricing.dp import (
    BO3State,
    RoundPFn,
    _advance_round,
    _advance_to_next_map,
    series_value,
)
```

---

### IN-06: `_RoundPFnImpl._effective_side` line-118 default `"a_atk"` is the same `'a_atk'` literal `_advance_to_next_map` was hardened against

**File:** `src/pricing/live_theo.py:106-108` and `:117-119`

**Issue:** The DP regression test at `test_dp.py:386-431` asserts that
`_advance_to_next_map` does NOT contain a hardcoded `'a_atk'` literal,
locking PRD §12.2 #6 against the audit-engine bug. But
`_RoundPFnImpl._effective_side` (line 108) and
`_RoundPFnImpl.next_side_orient_for` (line 118) BOTH hardcode `"a_atk"`
as the defensive default when `map_idx >= len(map_side_orients)`. While
these branches are dead in well-formed series (the DP terminal checks
fire first), the literal is exactly the form the regression test was
designed to forbid one indirection layer up.

The previous review's WR-04 covered this for `next_side_orient_for`; this
note extends it to `_effective_side` (the read path is even more exposed,
called per round during DP recursion).

**Fix:** Either route through a constants lookup (see WR-04 in
`01-REVIEW.md` history) or raise on out-of-bounds (fail loud rather than
silently return a literal). Out of scope for this re-review since WR-04
was deferred from prior review.

---

### IN-07: CR-04 defensive comment in `dp._clear_pricing_caches` overstates the safety guarantee

**File:** `src/pricing/dp.py:168-184`

**Issue:** The CR-04 docstring claims:

> Resetting per-call bounds memory without sacrificing real cache hits — the
> int id changes per call, so cross-call hits are already 0%.

This is true for cross-`live_theo`-call hits (each call registers a fresh
closure → fresh int id → no shared lru_cache key). But it understates the
**within-call** caching loss documented in WR-08: each `series_value(...)`
inside one `_compute_confidence` call also gets a fresh int id, so the
lru_cache misses across the multiple `series_value` invocations within
one call too. The "0% cross-call" framing implies "100% within-call,"
which is not accurate.

**Fix:** Rephrase the comment to scope the claim:

```python
# The int id changes per `series_value(...)` invocation, so cross-call
# hits are already 0% AND within-call hits across separate
# series_value(...) call sites are also 0%. The lru_cache only shares
# state across recursive sub-calls of a single _series_value_cached
# evaluation tree (which still provides substantial benefit for the BO3
# state space).
```

This is a documentation-only fix; no behavior change.

---

_Reviewed: 2026-04-28_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
