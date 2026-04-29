---
phase: 01-core-pricing-engine
reviewed: 2026-04-29T00:00:00Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - src/pricing/dp.py
  - src/pricing/live_theo.py
  - tests/pricing/test_dp.py
  - tests/pricing/test_live_theo.py
  - tests/pricing/test_round_types.py
findings:
  critical: 0
  warning: 3
  info: 4
  total: 7
status: issues_found
---

# Phase 1: Code Review Report (Post-gap-closure re-review for plan 01-07)

**Reviewed:** 2026-04-29
**Depth:** standard
**Files Reviewed:** 5
**Status:** issues_found (no BLOCKERs; warnings + info only)
**Supersedes:** prior 01-REVIEW.md (CR-01..CR-04 closed by 01-06; CR-05 / WR-06 closed by 01-07)

## Summary

This re-review re-evaluates the five source/test files in scope for plan
**01-07-pistol-anti-eco-dp-propagation** (BLOCKER CR-05 + WARNING WR-06
closure). Both CR-05 and WR-06 verify cleanly under a line-by-line trace:

  - **CR-05** (`dp._advance_round` pistol propagation):
    `src/pricing/dp.py:156-187` now writes
    `pistol_winner_a[state.map_idx] = a_wins` when (and only when) round 1
    settles AND the existing slot is `None`. The don't-override invariant
    is enforced by the `existing is None` guard on line 172. Regression
    coverage at `tests/pricing/test_dp.py:476-583` includes both the
    forward-propagation lock (rounds 2/3 dispatch to GUN_WIN_RATE after
    round 1 settles) and the immutability lock (already-set
    `pistol_winner_a[map_idx]` is not overridden on subsequent advances).
  - **WR-06** (`_within_map_p_a_wins` future-map sub-DP propagation):
    `src/pricing/live_theo.py:280-289` propagates the same logic into the
    inline within-map state-advance for future maps. The strict-ordering
    structural test at `tests/pricing/test_live_theo.py:1083-1178`
    (`p_a_pistol > p_unset > p_b_pistol`) is the load-bearing post-fix
    invariant; pre-fix all three values collapse to the same number.
  - **End-to-end behavioral lock** at
    `tests/pricing/test_live_theo.py:1186-1295` asserts the same strict
    ordering through the public `LiveTheoEngine` surface under asymmetric
    half-rates with `total=1e9` (no shrinkage).

The CR-05 fix correctly distinguishes:
  - **Round-1 boundary trigger** (`state.a_round == 0 and state.b_round == 0`)
    — fires for the first round of every map (rounds 1 of map 0, 1 of map 1,
    1 of map 2). Rounds 13 (second-half pistol) are NOT triggered, which is
    the documented Phase-1 limitation per `dp.py:33-47` and intentional.
  - **Don't-override invariant** (`existing is None`) — preserves
    ingestion-driven `True`/`False` across DP recursion.

CR-01..CR-04 (closed by plan 01-06) remain closed in the current
`live_theo.py` / `dp.py`:

  - **CR-01**: `_p_reach_map_cached` (`live_theo.py:533-538`) checks
    `a_map_score >= 2 or b_map_score >= 2` BEFORE the
    `state.map_idx == m` check.
  - **CR-02**: `_p_map_decisive` (`live_theo.py:471-473`) uses the BO3
    middle-map formula
    `p_a_{m-1} * p_a_m + (1 - p_a_{m-1}) * (1 - p_a_m)`.
  - **CR-03**: `_compute_vega` (`live_theo.py:617-634`) early-returns 0 at
    series + within-map terminals and uses the OT coinflip-leaf variance
    at total=24.
  - **CR-04**: `LiveTheoEngine.__call__` (`live_theo.py:672-684`) wraps
    `_live_theo_impl` in `try/finally` and clears both `_ROUND_P_FNS` and
    `_REACH_MAP_FNS` registries plus their lru_caches on every call,
    including on exception.

Findings below are pre-existing quality concerns surfaced during the
re-review trace. **Zero BLOCKERs.** All flagged items are warnings or
info-tier defects that don't compromise correctness for Phase 1's
documented scope.

## Warnings

### WR-01: `_within_map_p_a_wins` duplicates `dp._advance_round` state-advance logic — high regression risk for Phase 2

**File:** `src/pricing/live_theo.py:245-307`, `src/pricing/dp.py:136-187`

**Issue:** Plan 01-07 closed CR-05 in `dp._advance_round` AND closed WR-06
in `_within_map_p_a_wins._p_a_recursive` by **duplicating the
pistol-propagation + side-flip logic** rather than extracting a shared
helper. The two implementations are now structurally identical:

```
Logic                              dp._advance_round       _within_map_p_a_wins
                                   (lines 156-187)         (lines 291-300)
─────────────────────────────────────────────────────────────────────────────
Increment winner's round count     ✓                       ✓
Side flip at total == 12           ✓                       ✓ (split a/b branches)
pistol[map_idx] update on round 1  ✓ (lines 170-176)       ✓ (lines 280-286)
Don't-override (existing is None)  ✓                       ✓
```

This is exactly the parallel-models defect class PRD §12.2 #6 was
hardened against (`series_theo` / `series_theo_no_sides` /
`series_theo_from_map_probs` triplet, DEC-010). Phase 2 will extend
`pistol_winner_a` to `tuple[Optional[tuple[bool, bool]], ...]` per (map,
half) — at that point both implementations must be updated in lockstep
or they will diverge. The previous review's WR-06 fix description
explicitly listed *"share state-advance helpers between dp.py and the
within-map sub-DP, or duplicate the pistol-update logic"* as the two
options; the implementation chose to duplicate.

**Why it's not a BLOCKER right now:** The two implementations agree
behaviorally as of this review — verified by
`test_within_map_anti_eco_uses_gun_win_rate_after_round_1_branch` plus
the end-to-end `test_live_theo_asymmetric_pistols_match_unset_pistols_after_dp_propagation`
test. The bug is **latent**, not active.

**Fix:** Extract a shared `_advance_round_inline(a_round, b_round,
side_orient, pistol, map_idx, a_wins)` helper that returns the new
4-tuple, and call it from both `dp._advance_round` and
`_within_map_p_a_wins._p_a_recursive`. Alternatively, refactor
`_within_map_p_a_wins` to call `dp._advance_round` directly on a synthetic
BO3State and unpack the relevant fields — the latter is more invasive but
eliminates the duplication entirely.

```python
# src/pricing/dp.py — extract pure helper from _advance_round:
def _advance_round_fields(
    a_round: int,
    b_round: int,
    side_orient: str,
    pistol: tuple[Optional[bool], ...],
    map_idx: int,
    a_wins: bool,
) -> tuple[int, int, str, tuple[Optional[bool], ...]]:
    new_a = a_round + (1 if a_wins else 0)
    new_b = b_round + (0 if a_wins else 1)
    new_side = (
        ("a_def" if side_orient == "a_atk" else "a_atk")
        if new_a + new_b == REGULATION_HALF
        else side_orient
    )
    new_pistol = pistol
    if a_round == 0 and b_round == 0 and pistol[map_idx] is None:
        new_pistol = tuple(
            (a_wins if i == map_idx else pistol[i]) for i in range(len(pistol))
        )
    return new_a, new_b, new_side, new_pistol
```

Both call sites then thin to a single helper invocation. Add a regression
test asserting the two implementations produce identical state
trajectories on a small sample (e.g., 20 random reachable states).

---

### WR-02: Rounds 14 / 15 dispatch on first-half pistol winner — silent semantic bug, documented but not gated

**File:** `src/pricing/dp.py:33-47` (docstring), `src/pricing/round_types.py:146-153`

**Issue:** `pistol_winner_a` is keyed by `map_idx` only — one slot per map.
It records the FIRST-half pistol winner. Rounds 14/15 (anti-eco for the
SECOND-half pistol) currently dispatch on `pistol_winner_a[map_idx]` —
i.e., they re-use the first-half pistol winner as a proxy for the
second-half pistol winner. This is structurally wrong: the second-half
pistol is a separate event with no necessary correlation to the first-half
pistol. The docstring at `dp.py:33-47` explicitly acknowledges this:

> rounds 14/15 currently dispatch on `pistol_winner_a[map_idx]` — i.e.,
> they re-use the first-half pistol winner as a proxy. **This is
> structurally wrong but quantitatively bounded for Phase 1**: the
> dispatch produces GUN_WIN_RATE / 1-GUN_WIN_RATE biased toward the
> first-half pistol's outcome.

**Concrete impact:** In a 50/50 first-half pistol, rounds 14/15 should be
~50/50 too (because the second-half pistol is also ~50/50). The current
dispatch hard-couples them: if A won the first-half pistol, rounds 14/15
return GUN_WIN_RATE = 0.822 — implying A is also ~82% likely to win the
post-pistol anti-eco rounds in the second half, which is unjustified. For
asymmetric matchups the bias is similar magnitude.

This is the DEC-011 / CRule 4 model (rounds 13/14/15 should be modeled
explicitly, not constant `p1`/`p2`) — but the implementation only models
the first-half pistol explicitly. Round 13 falls through to half-rates
blend (acceptable Phase-1 simplification A8); rounds 14/15 fall through
to the first-half pistol's GUN_WIN_RATE expectation (NOT acceptable as a
silent default).

**Why it's not a BLOCKER:** The bias is bounded — both teams' biases are
mirrored, so the series-level theo error partially cancels. PRD §6 doesn't
require Phase 1 to be live-trading-ready, and Phase 2
(REQ-round-event-data-pipeline) extends the data shape per the
documented follow-up.

**Fix (Phase 2 — out of scope for this re-review's hot fix):** Extend
`pistol_winner_a` to `tuple[Optional[tuple[bool, bool]], ...]` per (map,
half) and update `round_types.round_p_for_round` to consult the
appropriate half. The `dp._advance_round` trigger must also fire at the
round-13 boundary (`state.a_round + state.b_round == REGULATION_HALF`,
which is the same condition currently used for the side flip). Until
then, add a defensive guard in `round_types.round_p_for_round` that logs
or asserts when a round-14/15 dispatch consults the first-half pistol
slot, so Phase 4 paper-trading data quantifies the bias.

**Phase-1 mitigation:** Either (a) hard-code rounds 14/15 to the
half-rates blend (matching round 13's Phase-1 fallback) instead of
dispatching on `pistol_winner_a`, OR (b) widen the test
`test_anti_eco_returns_gun_win_rate_when_a_won_pistol` to flag rounds
14/15 as Phase-2 deferred (currently it asserts GUN_WIN_RATE for those
rounds, which locks in the structurally-wrong dispatch as a regression
fixture).

---

### WR-03: Per-`m` `_p_reach_map` re-registration defeats `lru_cache` reuse across `_compute_confidence` iteration (carry-over from prior review's WR-08)

**File:** `src/pricing/live_theo.py:498-509`

**Issue:** `_p_reach_map` is the public wrapper that registers
`round_p_fn` in `_REACH_MAP_FNS` and dispatches to the
`lru_cache`-decorated `_p_reach_map_cached`. Each call appends to the
registry and returns a fresh int id. `_compute_confidence`
(`live_theo.py:564-586`) calls `_p_map_decisive(state, m, half_rates)`
for each `m`; for future maps, `_p_map_decisive` calls
`_p_reach_map(bo3, fn, m)` — registering a new closure id per map. Since
`_p_reach_map_cached` is keyed on `(state, round_p_fn_id, m)`, two
consecutive calls with the same `(state, fn, m)` but different ids miss
the cache.

Inside `_p_reach_map_cached`, `series_value(...)` is called three times
per recursion level (root, after_a, after_b) — each triggering its own
`_register_round_p_fn` in `dp.py`. The `_series_value_cached` lru_cache
is therefore also missed across these three calls within a single
`_p_reach_map_cached` evaluation.

The CR-04 cleanup correctly bounds the lifetime of these registrations
to a single `live_theo` call, so this is not a memory leak. Performance
is out of v1 scope per the review rules; this is flagged as a **quality**
concern: the cache infrastructure is non-trivial (`lru_cache(maxsize=None)`
+ registry indirection + per-call clear) but provides essentially zero
benefit during a single call because the int ids constantly change. The
CR-04 docstring (`dp.py:233-248`) implies "0% cross-call hits" implies
"100% within-call hits," which is misleading.

**Fix (post-Phase-1):** Hoist `round_p_fn` registration above the
per-`m` and per-recursion calls. `_compute_confidence` registers the
closure once and threads the int id down through `_p_map_decisive`
→ `_p_reach_map_cached` and through `series_value`'s API. Alternatively,
make `RoundPFn` closures hashable (`MatchState` is a frozen dataclass —
the only barrier was the historical `pistol_winner_a: dict` field, but
the current `_RoundPFnImpl` already wraps it; extending `MatchState` to
make `pistol_winner_a` a tuple inside the dataclass and updating the
ingestion layer is the cleaner fix). No regression test required — this
is a quality finding, not a correctness defect.

---

## Info

### IN-01: `LiveTheoEngine.__call__` performs `import` inside the hot path (carry-over from prior review's IN-05)

**File:** `src/pricing/live_theo.py:679`

**Issue:** `__call__` runs `from src.pricing import dp as _dp` on every
invocation. The import is cached by Python so the cost per call is small
(~1µs), but the placement is unusual and signals "defensive against
circular import" without actually being needed (no circular dependency
exists — `dp.py` does not import `live_theo.py`).

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

Then drop line 679.

---

### IN-02: `_RoundPFnImpl._effective_side` and `next_side_orient_for` hardcode `"a_atk"` literal — same form `_advance_to_next_map` was hardened against (carry-over from prior review's IN-06)

**File:** `src/pricing/live_theo.py:106-108`, `:117-119`

**Issue:** The DP regression test at `tests/pricing/test_dp.py:423-468`
asserts that `_advance_to_next_map` does NOT contain a hardcoded
`'a_atk'` literal, locking PRD §12.2 #6 against the audit-engine bug. But
`_RoundPFnImpl._effective_side` (line 108) and
`_RoundPFnImpl.next_side_orient_for` (line 118) BOTH hardcode `"a_atk"`
as the defensive default when `map_idx >= len(map_side_orients)`.

These branches are dead in well-formed series (the DP terminal checks
fire first), but the literal is exactly the form the regression test was
designed to forbid one indirection layer up. Plus, `_effective_side` is
called per-round during DP recursion — the read path is more exposed
than `next_side_orient_for`.

**Fix:** Either route through a constants lookup or raise on
out-of-bounds (fail loud rather than silently return a literal):

```python
def _effective_side(self, state: BO3State) -> str:
    if state.map_idx >= len(self.match_state.map_side_orients):
        raise IndexError(
            f"map_idx {state.map_idx} out of range for "
            f"map_side_orients length {len(self.match_state.map_side_orients)}"
        )
    ...
```

The series-clinch terminal in `dp._series_value_cached` short-circuits
before any defensive branch executes, so raising here surfaces real bugs
without breaking happy-path behavior.

---

### IN-03: CR-04 docstring in `dp._clear_pricing_caches` overstates the safety guarantee (carry-over from prior review's IN-07)

**File:** `src/pricing/dp.py:236-246`

**Issue:** The CR-04 docstring claims:

> Resetting per-call bounds memory without sacrificing real cache hits —
> the int id changes per call, so cross-call hits are already 0%.

This is true for cross-`live_theo`-call hits (each call registers a
fresh closure → fresh int id → no shared lru_cache key). But it
understates the **within-call** caching loss documented in WR-03:
each `series_value(...)` inside one `_compute_confidence` call also gets
a fresh int id, so the lru_cache misses across the multiple
`series_value` invocations within one call too. The "0% cross-call"
framing implies "100% within-call," which is not accurate.

**Fix:** Rephrase the comment to scope the claim:

```python
# The int id changes per series_value(...) invocation, so cross-call
# hits are 0% AND within-call hits across separate series_value(...)
# call sites are 0%. The lru_cache only shares state across recursive
# sub-calls of a single _series_value_cached evaluation tree — which
# still provides substantial benefit for the BO3 state space.
```

This is a documentation-only fix; no behavior change.

---

### IN-04: `_within_map_p_a_wins` tracks `side_orient` redundantly — `_RoundPFnImpl.__call__` overrides it on every call

**File:** `src/pricing/live_theo.py:245-307`

**Issue:** `_within_map_p_a_wins._p_a_recursive` tracks `side_orient`
through the recursion (lines 248, 251, 269, 292-300, 306) and passes it
into the synthetic BO3State on line 269. But `_RoundPFnImpl.__call__`
(line 100-103) IGNORES the carried side_orient — it computes the
effective side from `match_state.map_side_orients[state.map_idx]` plus
the within-map round-12 flip:

```python
def __call__(self, state: BO3State) -> float:
    effective_side = self._effective_side(state)
    s_corrected = replace(state, side_orient=effective_side)
    return round_p_for_round(s_corrected, self.match_state, self.half_rates)
```

The two computations agree by design (same starting side, same flip
condition), so there's no behavioral bug. But the recursion's
`side_orient` tracking is dead code semantically — it only affects the
memoization key (line 251) and contributes to local debugging noise.
Future maintainers reading
`tests/pricing/test_live_theo.py:340-359` (`test_build_round_p_fn_flips_after_round_12`)
might assume the tracked side flows through, which it doesn't.

**Fix (low priority):** Drop `side_orient` from the recursion's local
state. Pass the synthetic BO3State with `side_orient=starting_side`
unchanged (or even `side_orient="a_atk"` — `_RoundPFnImpl` will override
either way). Update the memo key to `(a_round, b_round, pistol)` only.
This shrinks the state space modestly and removes the dead-code maintenance
hazard. Add a comment: `# side_orient on synthetic state is ignored by
_RoundPFnImpl.__call__ — see _RoundPFnImpl._effective_side.`

---

_Reviewed: 2026-04-29_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
