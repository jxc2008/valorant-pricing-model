---
phase: 01-core-pricing-engine
plan: 02
type: execute
wave: 2
depends_on:
  - 01-01-constants-and-blend
files_modified:
  - src/pricing/dp.py
  - tests/pricing/test_dp.py
autonomous: true
requirements:
  - REQ-bo3-dp-engine
  - REQ-ot-handling
must_haves:
  truths:
    - "Bradley-Terry blend, not arithmetic mean (DEC-003 / CRule 3)"
    - "Conviction clip [0.01, 0.99] uniform (DEC-012 / CRule 6)"
    - "No magic numbers — every threshold in src/config/constants.py (CON-no-magic-numbers / CRule 12)"
    - "mypy --strict on src/pricing/ (CON-mypy-strict-pricing / CRule 11)"
    - "Single canonical entry point: live_theo(state) → TheoOutput (DEC-010 / CRule 1)"
    - "OT explicit hard-stop at total=24 with documented coinflip leaf (DEC-009 / CRule 5)"
    - "BO3 series and per-map theos come from the SAME DP — no parallel models (DEC-002 / CRule 2)"
    - "BO3State is the DP cache key, distinct from MatchState (RESEARCH §1, Pitfall 5)"
    - "lru_cache(maxsize=None) per roadmap §1.1 — Callable cache-key indirection via _ROUND_P_FNS registry (RESEARCH §9)"
    - "_advance_to_next_map takes the next map's starting side as an explicit arg (NOT hardcoded 'a_atk') so live_theo can thread MatchState.map_side_orients through (PRD §12.2 #6 regression-lock; checker BLOCKER #3 fix)"
  outputs:
    - "src/pricing/dp.py exports `BO3State` (frozen dataclass, slots=True, hashable) + `series_value(state, round_p_fn) -> float`"
    - "BO3State fields exactly: map_idx, a_map_score, b_map_score, a_round, b_round, side_orient (str), map_pool (tuple[str, ...]), pistol_winner_a (tuple[Optional[bool], ...])"
    - "DP terminals: a_map_score>=2 → 1.0; b_map_score>=2 → 0.0; a_round>=WIN_THRESHOLD → recurse next-map (a won); b_round>=WIN_THRESHOLD → recurse next-map (b won); a_round+b_round == REGULATION_HALF*2 → OT coinflip leaf"
    - "OT leaf: 0.5 * series_value(after_a_wins_map) + 0.5 * series_value(after_b_wins_map) — collapses entire OT sub-DP into 50/50 (DEC-009 / RESEARCH §5)"
    - "Callable cache-key indirection: _ROUND_P_FNS module-level list; _register_round_p_fn returns int id; @lru_cache(maxsize=None) keys on (BO3State, int)"
    - "Source contains REGULATION_HALF * 2 as the OT-detection literal (NOT bare 24, NOT range(26))"
    - "_advance_to_next_map signature: `_advance_to_next_map(state: BO3State, a_won: bool, next_side_orient: str) -> BO3State` — NO 'a_atk' default literal in source; live_theo (01-05) supplies the arg from MatchState.map_side_orients[next_map_idx]"
    - "tests/pricing/test_dp.py: hypothesis test_dp_value_in_unit_interval (range), test_dp_symmetric_input_matches_closed_form (uses fair_value._bo3_series_prob), test_dp_ot_hardstop_returns_coinflip_leaf, test_dp_terminal_a_clinched / test_dp_terminal_b_clinched, test_dp_no_range26_loop (regression), test_dp_advance_to_next_map_uses_explicit_side_orient (regression-lock for hardcoded side)"
    - "`uv run mypy --strict src/pricing/dp.py` exits 0"
    - "`uv run pytest tests/pricing/test_dp.py -x` exits 0"
    - "`uv run ruff check src/pricing/dp.py tests/pricing/test_dp.py` exits 0"
---

<rationale>
Wave 2 (depends on 01-01 for `REGULATION_HALF`, `WIN_THRESHOLD` — already in Phase 0 — but logically queued after 01-01 because dp.py imports from constants and blend.py is the FIRST consumer-of-constants pattern; ordering 01-02 after 01-01 keeps the test scaffolding stable). DP is the load-bearing piece of Phase 1 — one big plan dedicated to it.

**Why this is a single-task plan (not 2-3):** The DP recursion + OT leaf + callable indirection + property tests form ONE cohesive concern. Splitting them would force the executor to write half a recursion in plan A and the other half in plan B, with the cache-key indirection straddling. RESEARCH.md §1, §2, §5, §9, §11 are tightly coupled. Single task at ~30% context.

**Researcher alternative considered:** Combining DP + round_types into one Wave 2 plan. Rejected because round_types is a pure dispatch (~80 LoC, no recursion) that depends ONLY on blend.py — it can run in parallel with DP. See 01-03 (round_types) — also Wave 2, runs concurrently.

**Files NOT modified here:** `src/pricing/__init__.py` (re-exports land in 01-05); `src/config/constants.py` (no new constants; `OT_TOTAL_HARDSTOP` deliberately not added per RESEARCH §12).

**Revision note (checker BLOCKER #3 / WARNING #9):** The original plan hardcoded `side_orient="a_atk"` inside `_advance_to_next_map`, which would silently re-introduce the audit `series_theo_no_sides` bug class (PRD §12.2 #6) once the OT/map-boundary recursion fires for non-`a_atk` starting sides. This revision refactors `_advance_to_next_map` to accept the next map's starting side as an explicit `next_side_orient: str` argument, threaded from `live_theo._build_round_p_fn` (01-05) via the round_p_fn closure that reads `MatchState.map_side_orients[next_map_idx]`. The OT leaf and the in-recursion next-map call sites both pass this through. Source-level grep gates and a regression test verify the side is no longer hardcoded.
</rationale>

<objective>
Implement the generalized BO3 dynamic-programming engine in `src/pricing/dp.py` — the load-bearing piece of Phase 1's pricing math. Replace the audit engine's bug-laden `_markov_map_win` (reference/theo_engine.py:168-206) with a single recursion `series_value(state, round_p_fn)` over a frozen `BO3State` dataclass, fixing the OT-iterates-past-24 bug (DEC-009) and the constant-`p1`/`p2`-per-half bug (DEC-011 — feeds in via the `round_p_fn` injection point implemented in 01-03).

Purpose: Same DP serves both `theo_series` and per-map marginals (DEC-002 / CRule 2 — no parallel models). The DP is generalized to the full BO3 BO3State (not separate per-map and per-series functions like the audit triplet), which eliminates the "two-model disagreement" bug class (DEC-010).
Output: `BO3State` dataclass, `series_value` public entry, `_register_round_p_fn` callable indirection, `_ot_coinflip_leaf` helper, full hypothesis property test suite (range, symmetric-input closed form, OT hard-stop, terminals).
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@.planning/phases/01-core-pricing-engine/01-CONTEXT.md
@.planning/phases/01-core-pricing-engine/01-RESEARCH.md
@.planning/phases/01-core-pricing-engine/01-PATTERNS.md
@.planning/phases/01-core-pricing-engine/01-01-constants-and-blend-SUMMARY.md
@CLAUDE.md
@prd.md
@roadmap.md
@src/config/constants.py
@src/pricing/blend.py
@reference/theo_engine.py
@reference/fair_value.py

<interfaces>
<!-- DP engine code skeletons from RESEARCH §1, §2, §5, §9 — ship verbatim with no exploration. -->

From src/config/constants.py (verified Phase 0 + 01-01):
```python
REGULATION_HALF: Final[int] = 12
WIN_THRESHOLD: Final[int] = 13
```

From reference/fair_value.py:77-79 (closed-form fixture for symmetric-input test):
```python
def _bo3_series_prob(p: float) -> float:
    """P(team A wins BO3 series) given per-map win prob p."""
    return p * p * (3 - 2 * p)
```

From reference/theo_engine.py:168-206 (the audit `_markov_map_win` — DROP these specific lines per the salvage delta):
- Line 179: `for total in range(WIN_THRESHOLD * 2)` — runs to 26 → REPLACE with hard-stop at 24
- Lines 189-194: `if total < REGULATION_HALF: p = p1` else `p = p2` — REPLACE with `_ROUND_P_FNS[round_p_id](state)` per round
- Bottom-up `dp` dict (lines 196-204) — flip to top-down recursion with `lru_cache`

The DP recursion (RESEARCH §2, lines 513-558 — ship verbatim with helper expansion; `_advance_to_next_map` calls take an explicit `next_side_orient` arg per Blocker #3 fix):
```python
@functools.lru_cache(maxsize=None)
def _series_value_cached(state: BO3State, round_p_id: int) -> float:
    if state.a_map_score >= 2:
        return 1.0
    if state.b_map_score >= 2:
        return 0.0
    if state.a_round >= WIN_THRESHOLD:
        return _series_value_cached(
            _advance_to_next_map(state, a_won=True, next_side_orient=_ROUND_P_FNS[round_p_id].next_side_orient_for(state.map_idx + 1)),
            round_p_id,
        )
    if state.b_round >= WIN_THRESHOLD:
        return _series_value_cached(
            _advance_to_next_map(state, a_won=False, next_side_orient=_ROUND_P_FNS[round_p_id].next_side_orient_for(state.map_idx + 1)),
            round_p_id,
        )
    if state.a_round + state.b_round == REGULATION_HALF * 2:
        return _ot_coinflip_leaf(state, round_p_id)
    p = _ROUND_P_FNS[round_p_id](state)
    return (
        p * _series_value_cached(_advance_round(state, a_wins=True), round_p_id)
        + (1.0 - p) * _series_value_cached(_advance_round(state, a_wins=False), round_p_id)
    )
```

NOTE on the `next_side_orient_for` accessor: the round_p_fn registered in `_ROUND_P_FNS` is NOT a bare `Callable[[BO3State], float]` — it is a small object with two members: `__call__(state) -> float` AND `next_side_orient_for(map_idx: int) -> str`. live_theo's `_build_round_p_fn` (01-05) constructs this object and binds the side-orient lookup to `MatchState.map_side_orients[map_idx]` with bounds-checking. Type signature: `Protocol RoundPFn { __call__(BO3State) -> float; next_side_orient_for(int) -> str }`. The DP module declares the Protocol; live_theo implements it.

OT leaf (RESEARCH §5, lines 668-678 — also threads next_side_orient through):
```python
def _ot_coinflip_leaf(state: BO3State, round_p_id: int) -> float:
    """At total=24, OT-as-coinflip collapses entire OT sub-DP into 50/50 series leaf."""
    next_side = _ROUND_P_FNS[round_p_id].next_side_orient_for(state.map_idx + 1)
    return (
        0.5 * _series_value_cached(_advance_to_next_map(state, a_won=True, next_side_orient=next_side), round_p_id)
        + 0.5 * _series_value_cached(_advance_to_next_map(state, a_won=False, next_side_orient=next_side), round_p_id)
    )
```

Callable cache-key indirection (RESEARCH §9, lines 836-850 — extended with the side-orient accessor):
```python
class RoundPFn(Protocol):
    """The closure stored in _ROUND_P_FNS — callable AND side-orient-aware."""
    def __call__(self, state: BO3State) -> float: ...
    def next_side_orient_for(self, map_idx: int) -> str: ...

_ROUND_P_FNS: list[RoundPFn] = []

def _register_round_p_fn(fn: RoundPFn) -> int:
    _ROUND_P_FNS.append(fn)
    return len(_ROUND_P_FNS) - 1

def series_value(state: BO3State, round_p_fn: RoundPFn) -> float:
    return _series_value_cached(state, _register_round_p_fn(round_p_fn))
```

BO3State (RESEARCH §1, lines 487-497):
```python
@dataclass(frozen=True, slots=True)
class BO3State:
    map_idx: int
    a_map_score: int
    b_map_score: int
    a_round: int
    b_round: int
    side_orient: str
    map_pool: tuple[str, ...]
    pistol_winner_a: tuple[Optional[bool], ...]
```

Within-map side flip (RESEARCH §2 helper `_advance_round`):
- If `a_round + b_round == REGULATION_HALF` (i.e., just finished round 12), flip `side_orient` (a_atk ↔ a_def). Otherwise leave unchanged.

Map advance (RESEARCH §2 helper `_advance_to_next_map`):
- `map_idx += 1`, increment winning side's map_score, reset `a_round = b_round = 0`, set `side_orient` to the EXPLICIT `next_side_orient` arg (NO 'a_atk' default — see Blocker #3 fix in `<rationale>`). live_theo's `_build_round_p_fn` (01-05) supplies the arg from `MatchState.map_side_orients[map_idx + 1]`.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Implement src/pricing/dp.py with full BO3 DP recursion + OT leaf + property tests</name>
  <files>src/pricing/dp.py, tests/pricing/test_dp.py</files>

  <read_first>
    - src/config/constants.py (verify REGULATION_HALF=12, WIN_THRESHOLD=13 are exported — from Phase 0)
    - src/pricing/blend.py (verify `round_p` exists — from 01-01; not directly imported by dp.py but the closure in 01-05 will use it)
    - .planning/phases/01-core-pricing-engine/01-RESEARCH.md §1 "DP state representation" (lines 482-506), §2 "DP recursion code shape" (lines 510-570), §5 "OT coinflip leaf math" (lines 660-684), §9 "DP cache strategy" (lines 829-861), §11 "Property-test fixture sources" (lines 922-953)
    - .planning/phases/01-core-pricing-engine/01-PATTERNS.md "src/pricing/dp.py (math, new)" section (lines 167-264) and "tests/pricing/test_dp.py (test, new)" section (lines 697-768)
    - .planning/phases/01-core-pricing-engine/01-CONTEXT.md D-03, D-04, D-05, D-16 — DP state extensions, OT leaf semantics, cache strategy
    - reference/theo_engine.py:168-206 — the DP loop being replaced (study the structure at lines 175-177, 196-204; understand the bugs at lines 179, 189-194 — DROP those, do NOT salvage)
    - reference/fair_value.py:77-79 — closed-form fixture imported as `from reference.fair_value import _bo3_series_prob`
    - prd.md §12.2 #3 (the OT bug being fixed), §12.2 #5 (the constant-p1/p2 bug — fed in via round_p_fn from 01-03 / 01-05), and §12.2 #6 (the side-orient bug class — Blocker #3 fix here forbids hardcoded next-map side)
    - CLAUDE.md Critical Rules 2 (same DP for series + map), 5 (OT hard-stop), 11 (mypy --strict)
  </read_first>

  <behavior>
    - Test 1 (range, hypothesis): For any `p ∈ [0.0, 1.0]` and constant `round_p_fn = lambda _s: p`, `0.0 ≤ series_value(root, fn) ≤ 1.0` for the canonical 3-map root state
    - Test 2 (symmetric closed form, hypothesis): For `p ∈ [0.05, 0.95]`, `series_value(root, lambda _s: p) ≈ _bo3_series_prob(p) = p²(3-2p)` within `rel_tol=1e-9`
    - Test 3 (OT hard-stop): `series_value` of state at `a_round=12, b_round=12` (12-12 in regulation) under `round_p_fn = lambda _s: 0.5` returns 0.5 exactly (by symmetry — both sides of the OT leaf are equally weighted recurrences into next-map root states)
    - Test 4 (OT hard-stop, asymmetric): `series_value` of state at `a_round=12, b_round=12, a_map_score=1, b_map_score=0` (A is up 1-0 in maps, this map decides between A-clinch-2-0 vs B-equalizes-1-1) under `lambda _s: 0.5` is `0.5 * 1.0 + 0.5 * series_value(state_after_b_takes_this_map_to_1-1)`. Verifies the leaf RECURSES into next-map states (DEC-009 / D-05 asymmetric leaf semantic), not flat 0.5.
    - Test 5 (terminals): `series_value(state with a_map_score=2, ...)` returns 1.0; `series_value(state with b_map_score=2, ...)` returns 0.0
    - Test 6 (regression — no range(26) loop): source does NOT contain `range(26)` or `range(WIN_THRESHOLD * 2)` as a loop bound (would silently iterate past total=24 — PRD §12.2 #3 bug)
    - Test 7 (regression — no constant p1/p2 dispatch): source does NOT contain the audit pattern `if total < REGULATION_HALF: p = p1` (constant per-half — PRD §12.2 #5 bug)
    - Test 8 (cache hit verifies memoization): repeated `series_value(root, same_fn)` with `lambda _s: 0.6` increments `_series_value_cached.cache_info().hits` (cold call → cache miss; second call → cache hit)
    - Test 9 (regression — `_advance_to_next_map` requires explicit `next_side_orient`, no hardcoded literal): source does NOT contain a hardcoded `'a_atk'` or `"a_atk"` literal inside the `_advance_to_next_map` function body (the side comes from a parameter, not a default). Source-level grep verifies a `next_side_orient: str` parameter is in the function signature (Blocker #3 / Warning #9 regression-lock).
    - Test 10 (OT path side-orient is read from RoundPFn): for two `round_p_fn` closures whose `next_side_orient_for(1)` returns `'a_atk'` vs `'a_def'`, the OT leaf at a state forced into the OT branch produces different next-map-state side_orient values. (Verified by a thin spy that records the BO3State observed at the next round_p_fn call after the OT leaf fires.)
  </behavior>

  <action>
Create `src/pricing/dp.py` with the following content (ship as one cohesive module — RESEARCH §1, §2, §5, §9 all required for the recursion to be functional and testable):

```python
"""Generalized BO3 DP (`series_value`).

Replaces audit-engine `_markov_map_win` (reference/theo_engine.py:168-206) with
a single top-down memoized recursion over the full BO3 ``BO3State`` (DEC-002 —
same DP for series and per-map; no parallel models). Fixes documented bugs:

  1. OT-as-coinflip via ``range(26)`` (PRD §12.2 #3) → explicit hard-stop at
     ``total = REGULATION_HALF * 2`` with documented coinflip leaf (DEC-009).
  2. Constant ``p1``/``p2`` per half (PRD §12.2 #5) → ``round_p_fn(state)``
     called per-round (the round-type-aware closure ships in
     src/pricing/round_types.py + src/pricing/live_theo.py).
  3. Hardcoded `'a_atk'` start-of-next-map side (PRD §12.2 #6) → next-map
     side comes from `RoundPFn.next_side_orient_for(map_idx)` which live_theo
     binds to `MatchState.map_side_orients[map_idx]`. NO 'a_atk' default
     literal lives in this module.

Cache strategy
--------------
Per roadmap §1.1 + RESEARCH §9: ``@functools.lru_cache(maxsize=None)`` over the
private ``_series_value_cached(BO3State, int)`` function. The ``int`` is a
registry id assigned by ``_register_round_p_fn`` because ``Callable`` is not
stably hashable. The ``models/dp_table.pkl`` warm cache is intentionally
deferred per D-16 — Phase 1 ships in-process memoization only; pickle-warm is
a Phase 5/6 optimization unless profiling (01-05) shows the < 500 ms latency
budget is breached.

BO3State vs MatchState
----------------------
``BO3State`` is the DP cache key — ONLY DP-relevant fields. Live-state fields
(``seq_id``, ``last_updated_ts``, ``players_alive``, ``ults``, ``time_left_s``)
are absent on purpose (Pitfall 5: caching on full MatchState defeats memoization).
``live_theo.py`` extracts the BO3State from MatchState per call.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass
from typing import Optional, Protocol

from src.config.constants import REGULATION_HALF, WIN_THRESHOLD


# --------------------------------------------------------------------------- #
# 1. BO3State — DP cache key                                                  #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class BO3State:
    """DP cache key. Hashable; suitable for @lru_cache.

    All fields are hashable atoms (int, str, tuple of hashables).
    Distinct from ``MatchState`` (Phase 1 stub in live_theo.py): BO3State
    holds ONLY DP-relevant fields. Live-state fields do NOT belong here.

    Field semantics
    ---------------
    map_idx: 0-based index into ``map_pool`` for the current map.
    a_map_score, b_map_score: maps already won (0, 1, or terminal 2).
    a_round, b_round: rounds team A / B has won in the CURRENT map.
    side_orient: 'a_atk' or 'a_def' — current half's side for team A.
        Flips at the within-map round-12-completed boundary.
    map_pool: frozen tuple of map names; constant within a series.
    pistol_winner_a: per-map; ``None`` pre-pistol, ``True`` if A won the map's
        pistol round, ``False`` if B did. Length must equal ``len(map_pool)``.
        Used by round_types.py for rounds {2, 3, 14, 15} dispatch.
    """

    map_idx: int
    a_map_score: int
    b_map_score: int
    a_round: int
    b_round: int
    side_orient: str
    map_pool: tuple[str, ...]
    pistol_winner_a: tuple[Optional[bool], ...]


# --------------------------------------------------------------------------- #
# 2. RoundPFn Protocol — callable + side-orient lookup                        #
# --------------------------------------------------------------------------- #


class RoundPFn(Protocol):
    """Closure protocol stored in `_ROUND_P_FNS`.

    Two responsibilities:
      - `__call__(state) -> float`: P(team A wins this round) under MatchState.
      - `next_side_orient_for(map_idx) -> str`: 'a_atk' | 'a_def' starting
        side for the map at index ``map_idx``. live_theo's `_build_round_p_fn`
        binds this to `MatchState.map_side_orients[map_idx]` (Blocker #3 fix —
        DP no longer hardcodes 'a_atk' for next-map roots).
    """

    def __call__(self, state: BO3State) -> float: ...
    def next_side_orient_for(self, map_idx: int) -> str: ...


# --------------------------------------------------------------------------- #
# 3. State-advance helpers                                                    #
# --------------------------------------------------------------------------- #


def _advance_round(state: BO3State, a_wins: bool) -> BO3State:
    """Increment the winner's round count; flip side at the round-12 boundary."""
    new_a_round = state.a_round + (1 if a_wins else 0)
    new_b_round = state.b_round + (0 if a_wins else 1)
    # Within-map sides flip after round 12 (i.e., when total==REGULATION_HALF).
    if new_a_round + new_b_round == REGULATION_HALF:
        new_side_orient = "a_def" if state.side_orient == "a_atk" else "a_atk"
    else:
        new_side_orient = state.side_orient
    return BO3State(
        map_idx=state.map_idx,
        a_map_score=state.a_map_score,
        b_map_score=state.b_map_score,
        a_round=new_a_round,
        b_round=new_b_round,
        side_orient=new_side_orient,
        map_pool=state.map_pool,
        pistol_winner_a=state.pistol_winner_a,
    )


def _advance_to_next_map(
    state: BO3State,
    a_won: bool,
    next_side_orient: str,
) -> BO3State:
    """Move to the next map's root state with the winning side credited.

    The `next_side_orient` parameter MUST be supplied by the caller — there is
    NO 'a_atk' default literal here (Blocker #3 / Warning #9 regression-lock
    for PRD §12.2 #6 audit `series_theo_no_sides` bug class). live_theo's
    `_build_round_p_fn` (01-05) sources the value from
    `MatchState.map_side_orients[state.map_idx + 1]` (with bounds-checking for
    series-clinch states). The DP recursion threads it through the
    `_ROUND_P_FNS[round_p_id].next_side_orient_for(...)` accessor.
    """
    return BO3State(
        map_idx=state.map_idx + 1,
        a_map_score=state.a_map_score + (1 if a_won else 0),
        b_map_score=state.b_map_score + (0 if a_won else 1),
        a_round=0,
        b_round=0,
        side_orient=next_side_orient,
        map_pool=state.map_pool,
        pistol_winner_a=state.pistol_winner_a,
    )


# --------------------------------------------------------------------------- #
# 4. Callable cache-key indirection                                           #
# --------------------------------------------------------------------------- #
# lru_cache requires hashable keys; Callables aren't stably hashable.
# Module-level registry keyed on int id is the established pattern.
# RESEARCH §9.

_ROUND_P_FNS: list[RoundPFn] = []


def _register_round_p_fn(fn: RoundPFn) -> int:
    """Append the closure to the registry; return its int id for cache keying."""
    _ROUND_P_FNS.append(fn)
    return len(_ROUND_P_FNS) - 1


# --------------------------------------------------------------------------- #
# 5. DP recursion                                                             #
# --------------------------------------------------------------------------- #


@functools.lru_cache(maxsize=None)
def _series_value_cached(state: BO3State, round_p_id: int) -> float:
    """Top-down memoized recursion. Terminals + within-map recurrence + OT leaf.

    Cache key: (state, round_p_id) — int id resolves to the round_p_fn closure
    via _ROUND_P_FNS lookup at call time.
    """
    fn = _ROUND_P_FNS[round_p_id]

    # Terminal: series clinched
    if state.a_map_score >= 2:
        return 1.0
    if state.b_map_score >= 2:
        return 0.0

    # Map terminal: someone hit WIN_THRESHOLD rounds in this map.
    # Next-map starting side comes from the closure's side-orient accessor —
    # NO 'a_atk' literal (Blocker #3).
    if state.a_round >= WIN_THRESHOLD:
        next_side = fn.next_side_orient_for(state.map_idx + 1)
        return _series_value_cached(
            _advance_to_next_map(state, a_won=True, next_side_orient=next_side),
            round_p_id,
        )
    if state.b_round >= WIN_THRESHOLD:
        next_side = fn.next_side_orient_for(state.map_idx + 1)
        return _series_value_cached(
            _advance_to_next_map(state, a_won=False, next_side_orient=next_side),
            round_p_id,
        )

    # OT hard-stop at total=24 (DEC-009 / CRule 5).
    # FIX for reference/theo_engine.py:179 `for total in range(WIN_THRESHOLD * 2)`
    # which silently iterated past total=24 with p=0.5.
    if state.a_round + state.b_round == REGULATION_HALF * 2:
        return _ot_coinflip_leaf(state, round_p_id)

    # Within-map recurrence (FIX for theo_engine.py:189-194 constant p1/p2).
    p = fn(state)
    return (
        p * _series_value_cached(_advance_round(state, a_wins=True), round_p_id)
        + (1.0 - p) * _series_value_cached(_advance_round(state, a_wins=False), round_p_id)
    )


def _ot_coinflip_leaf(state: BO3State, round_p_id: int) -> float:
    """At total=24 (12-12 in regulation), OT is a coinflip per DEC-009.

    Collapses the entire OT sub-DP into a 50/50 over next-map series outcomes.
    Each side of the leaf recurses into the next-map root state with the
    next map's starting side fetched from the registered closure (NO 'a_atk'
    literal here either — Blocker #3 / Warning #9 fix). Asymmetric downstream
    values (e.g., A is already 1-0 in maps so winning the OT clinches the
    series) are captured because the leaf RECURSES into series-value, not a
    flat constant. RESEARCH §5 / D-05.
    """
    fn = _ROUND_P_FNS[round_p_id]
    next_side = fn.next_side_orient_for(state.map_idx + 1)
    return (
        0.5 * _series_value_cached(
            _advance_to_next_map(state, a_won=True, next_side_orient=next_side),
            round_p_id,
        )
        + 0.5 * _series_value_cached(
            _advance_to_next_map(state, a_won=False, next_side_orient=next_side),
            round_p_id,
        )
    )


# --------------------------------------------------------------------------- #
# 6. Public entry                                                             #
# --------------------------------------------------------------------------- #


def series_value(
    state: BO3State,
    round_p_fn: RoundPFn,
) -> float:
    """P(team A wins the BO3 series | current state) under round_p_fn.

    Args:
        state: Current BO3State. Reachable from any series root via the helpers
            in this module; the caller (typically live_theo.py) constructs the
            root from MatchState.
        round_p_fn: Closure satisfying the RoundPFn Protocol. Must be both
            callable (returns P(A wins this round | state)) AND expose
            `next_side_orient_for(map_idx)` so the DP can fetch the next map's
            starting side without hardcoding 'a_atk'. round_types.py +
            live_theo.py supply the canonical implementation.

    Returns:
        Float in ``[0.0, 1.0]``. NEVER clipped here — output clipping to
        ``[CONVICTION_CLIP_LOW, CONVICTION_CLIP_HIGH]`` happens in live_theo.py
        on the FINAL theo_series, not on intermediate DP values.

    Notes:
        Memoization is via the private cached function; one closure registration
        per call. Cache survives the process; clear via
        ``_series_value_cached.cache_clear()`` between unrelated test cases if
        the cache distorts measurements.
    """
    round_p_id = _register_round_p_fn(round_p_fn)
    return _series_value_cached(state, round_p_id)
```

Then create `tests/pricing/test_dp.py`:

```python
"""Property tests for src.pricing.dp — REQ-bo3-dp-engine + REQ-ot-handling.

Verifies acceptance criteria from roadmap §1.1, §1.4, §5.1:
  - DP value ∈ [0, 1] for any reachable state (range invariant).
  - Symmetric inputs → DP value == p²(3-2p) (closed form from fair_value).
  - OT hard-stop: DP returns coinflip leaf at total=24, never iterates past.
  - Map terminals (a_map_score>=2 → 1.0, b_map_score>=2 → 0.0).
  - No range(26) loop or constant-p1/p2 dispatch (regression vs PRD §12.2 #3, #5).
  - `_advance_to_next_map` requires explicit `next_side_orient` arg; no
    hardcoded 'a_atk' literal (Blocker #3 / Warning #9 — regression vs PRD §12.2 #6).
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

# Importing the salvage closed form via reference/ — confirm reference is on
# sys.path (Phase 0 pyproject.toml `[tool.hatch.build] sources` includes it).
from reference.fair_value import _bo3_series_prob

from src.pricing.dp import (
    BO3State,
    _series_value_cached,
    series_value,
)


# --------------------------------------------------------------------------- #
# Test helpers — RoundPFn closures with explicit side-orient accessors        #
# --------------------------------------------------------------------------- #


class _ConstantRoundPFn:
    """Test fixture satisfying the RoundPFn Protocol with constant p, all-a_atk maps."""

    def __init__(self, p: float, side_orients: tuple[str, ...] = ("a_atk", "a_atk", "a_atk")) -> None:
        self._p = p
        self._sides = side_orients

    def __call__(self, state: BO3State) -> float:
        return self._p

    def next_side_orient_for(self, map_idx: int) -> str:
        if map_idx >= len(self._sides):
            return "a_atk"  # past series-clinch; never read but defensive
        return self._sides[map_idx]


def _root() -> BO3State:
    """Canonical 3-map root state used across tests."""
    return BO3State(
        map_idx=0,
        a_map_score=0,
        b_map_score=0,
        a_round=0,
        b_round=0,
        side_orient="a_atk",
        map_pool=("Lotus", "Bind", "Haven"),
        pistol_winner_a=(None, None, None),
    )


# --------------------------------------------------------------------------- #
# 1. Range invariant                                                          #
# --------------------------------------------------------------------------- #


@given(p=st.floats(min_value=0.0, max_value=1.0, allow_nan=False))
@settings(max_examples=50, deadline=None)
def test_dp_value_in_unit_interval(p: float) -> None:
    """REQ-bo3-dp-engine acceptance: DP value ∈ [0, 1] for any reachable state."""
    val = series_value(_root(), _ConstantRoundPFn(p))
    assert 0.0 <= val <= 1.0
    assert not math.isnan(val)


# --------------------------------------------------------------------------- #
# 2. Symmetric input matches p²(3-2p) closed form                              #
# --------------------------------------------------------------------------- #


@given(p=st.floats(min_value=0.05, max_value=0.95))
@settings(max_examples=50, deadline=None)
def test_dp_symmetric_input_matches_closed_form(p: float) -> None:
    """REQ-bo3-dp-engine acceptance: symmetric round_p → DP == p²(3-2p).

    The closed form assumes IID maps + IID rounds. A constant round_p_fn that
    ignores state matches that assumption exactly.
    """
    actual = series_value(_root(), _ConstantRoundPFn(p))
    expected = _bo3_series_prob(p)
    assert math.isclose(actual, expected, rel_tol=1e-9)


# --------------------------------------------------------------------------- #
# 3. OT hard-stop                                                             #
# --------------------------------------------------------------------------- #


def test_dp_ot_hardstop_returns_coinflip_leaf_symmetric() -> None:
    """At total=24 with p=0.5 and 0-0 in maps, DP returns 0.5 by symmetry.

    DEC-009 / CRule 5: OT collapses to 50/50 on next-map series outcomes.
    """
    state = BO3State(
        map_idx=0,
        a_map_score=0,
        b_map_score=0,
        a_round=12,
        b_round=12,
        side_orient="a_def",
        map_pool=("Lotus", "Bind", "Haven"),
        pistol_winner_a=(True, None, None),
    )
    val = series_value(state, _ConstantRoundPFn(0.5))
    assert math.isclose(val, 0.5, rel_tol=1e-9)


def test_dp_ot_hardstop_recurses_into_next_map_for_asymmetric_state() -> None:
    """At total=24 with A up 1-0 in maps, OT leaf is NOT flat 0.5 — it must
    recurse into asymmetric next-map series states.

    State: A is 1-0 in maps, this map is 12-12 (OT). If A wins OT, series
    goes to 2-0 (A clinches). If B wins OT, series goes to 1-1 (decider on map 3).

    Under p=0.5 in the decider (map 3 from 0-0), P(A wins decider) = 0.5
    (closed form: p²(3-2p) at p=0.5 gives 0.5; for a single decider map
    starting fresh at 0-0, P(A wins map) under constant p=0.5 is 0.5).
    So the OT leaf returns 0.5 * 1.0 + 0.5 * 0.5 = 0.75.
    """
    state = BO3State(
        map_idx=0,
        a_map_score=1,
        b_map_score=0,
        a_round=12,
        b_round=12,
        side_orient="a_def",
        map_pool=("Lotus", "Bind", "Haven"),
        pistol_winner_a=(True, None, None),
    )
    val = series_value(state, _ConstantRoundPFn(0.5))
    # 0.5*P(A wins | map_score=2-0) + 0.5*P(A wins | map_score=1-1, decider at 0-0 under p=0.5)
    # = 0.5 * 1.0 + 0.5 * 0.5 = 0.75
    assert math.isclose(val, 0.75, rel_tol=1e-9)


def test_dp_ot_path_consults_round_p_fn_next_side_orient() -> None:
    """Blocker #3 / Warning #9: the OT path threads next_side_orient through the
    round_p_fn closure. Different `next_side_orient_for` values produce different
    BO3States at the next-map root. Verified by spying on the BO3State observed
    by `__call__` after the OT leaf fires.

    State construction: 12-12 in regulation on map 0, A up 1-0. The OT leaf
    advances to map 1; we then do at least ONE within-map round in map 1 (the
    `__call__` is invoked there with a state whose `side_orient` is the result
    of `next_side_orient_for(1)`).
    """
    seen_atk: list[BO3State] = []
    seen_def: list[BO3State] = []

    class _Spy:
        def __init__(self, observed: list[BO3State], next_sides: tuple[str, ...]) -> None:
            self._observed = observed
            self._next_sides = next_sides

        def __call__(self, state: BO3State) -> float:
            self._observed.append(state)
            return 0.5

        def next_side_orient_for(self, map_idx: int) -> str:
            if map_idx >= len(self._next_sides):
                return "a_atk"
            return self._next_sides[map_idx]

    state = BO3State(
        map_idx=0,
        a_map_score=1,
        b_map_score=0,
        a_round=12,
        b_round=12,
        side_orient="a_def",
        map_pool=("Lotus", "Bind", "Haven"),
        pistol_winner_a=(True, None, None),
    )
    # Clear cache so the OT recursion actually invokes __call__ on freshly-rooted
    # next-map states (caching across the two runs would short-circuit the spy).
    _series_value_cached.cache_clear()
    series_value(state, _Spy(seen_atk, next_sides=("a_atk", "a_atk", "a_atk")))
    _series_value_cached.cache_clear()
    series_value(state, _Spy(seen_def, next_sides=("a_atk", "a_def", "a_atk")))

    # In the b_won-OT-branch path, the next-map root must inherit the supplied side.
    # Under "a_atk" everywhere: every observed state at map_idx=1 has side_orient='a_atk'
    # at round=0 (i.e., before any within-map flip).
    atk_map1_root_sides = {
        s.side_orient for s in seen_atk
        if s.map_idx == 1 and s.a_round + s.b_round == 0
    }
    def_map1_root_sides = {
        s.side_orient for s in seen_def
        if s.map_idx == 1 and s.a_round + s.b_round == 0
    }
    assert atk_map1_root_sides == {"a_atk"}, atk_map1_root_sides
    assert def_map1_root_sides == {"a_def"}, def_map1_root_sides


# --------------------------------------------------------------------------- #
# 4. Terminals                                                                #
# --------------------------------------------------------------------------- #


def test_dp_terminal_a_clinched_returns_1() -> None:
    state = BO3State(
        map_idx=2,
        a_map_score=2,
        b_map_score=0,
        a_round=0,
        b_round=0,
        side_orient="a_atk",
        map_pool=("Lotus", "Bind", "Haven"),
        pistol_winner_a=(True, True, None),
    )
    assert series_value(state, _ConstantRoundPFn(0.5)) == 1.0


def test_dp_terminal_b_clinched_returns_0() -> None:
    state = BO3State(
        map_idx=2,
        a_map_score=0,
        b_map_score=2,
        a_round=0,
        b_round=0,
        side_orient="a_atk",
        map_pool=("Lotus", "Bind", "Haven"),
        pistol_winner_a=(False, False, None),
    )
    assert series_value(state, _ConstantRoundPFn(0.5)) == 0.0


# --------------------------------------------------------------------------- #
# 5. Memoization sanity                                                       #
# --------------------------------------------------------------------------- #


def test_dp_lru_cache_records_hits_on_repeat_call() -> None:
    """Repeated series_value with the same fn should hit the cache.

    NOTE: each series_value call registers a fresh round_p_id, so the cache key
    differs across calls. Hits accumulate WITHIN a single recursion (the same
    call recurses into many sub-states that share the round_p_id). Verify
    hits > 0 after a single root call.
    """
    _series_value_cached.cache_clear()
    series_value(_root(), _ConstantRoundPFn(0.6))
    info = _series_value_cached.cache_info()
    # A 3-map BO3 with within-map alternating recurrences produces hundreds of
    # state visits with substantial reuse — hits MUST be > 0.
    assert info.hits > 0
    assert info.currsize > 0


# --------------------------------------------------------------------------- #
# 6. Regression — DEC-009 / DEC-011 / PRD §12.2 #6 bug fixes                  #
# --------------------------------------------------------------------------- #


def _executable_dp_source() -> str:
    """Strip comments from src/pricing/dp.py for source-level regression checks."""
    src = Path("src/pricing/dp.py").read_text(encoding="utf-8")
    code_lines = [
        line for line in src.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    return "\n".join(code_lines)


def test_dp_source_does_not_loop_past_24() -> None:
    """DEC-009 / PRD §12.2 #3: must not contain `range(26)` or
    `range(WIN_THRESHOLD * 2)` as a loop bound that iterates past total=24.
    """
    code = _executable_dp_source()
    assert "range(26)" not in code
    assert "range(WIN_THRESHOLD * 2)" not in code


def test_dp_source_uses_explicit_ot_hardstop_constant() -> None:
    """DEC-009: OT hard-stop must use REGULATION_HALF * 2, not bare 24.

    CON-no-magic-numbers (CRule 12) — inline `24` is forbidden in business logic.
    """
    src = Path("src/pricing/dp.py").read_text(encoding="utf-8")
    assert "REGULATION_HALF * 2" in src


def test_dp_source_does_not_use_constant_p1_p2_dispatch() -> None:
    """DEC-011 / PRD §12.2 #5: must not contain audit-engine's
    `if total < REGULATION_HALF: p = p1` constant-per-half dispatch.
    """
    code = _executable_dp_source()
    # The audit engine's signature pattern (lines 189-194):
    assert "p = p1" not in code
    assert "p = p2" not in code


def test_dp_advance_to_next_map_takes_explicit_next_side_orient() -> None:
    """Blocker #3 / Warning #9 / PRD §12.2 #6: `_advance_to_next_map` must take
    `next_side_orient` as an explicit parameter — NO hardcoded 'a_atk' default
    inside the function body.

    Two-part verification:
      (a) function signature contains `next_side_orient: str` parameter.
      (b) function body does NOT assign side_orient to a literal 'a_atk' or 'a_def'.
    """
    src = Path("src/pricing/dp.py").read_text(encoding="utf-8")
    # (a) Signature includes the explicit parameter.
    assert "next_side_orient: str" in src

    # (b) Locate the _advance_to_next_map function body and confirm no literal
    # side assignment lurks inside it.
    lines = src.splitlines()
    in_fn = False
    fn_body: list[str] = []
    for line in lines:
        if line.startswith("def _advance_to_next_map"):
            in_fn = True
            continue
        if in_fn:
            # Function body ends at the next top-level `def` or end-of-file.
            if line.startswith("def ") or (line and not line.startswith((" ", "\t"))):
                break
            fn_body.append(line)
    body_text = "\n".join(fn_body)
    # Strip comments from body before searching.
    body_code = "\n".join(
        ln for ln in body_text.splitlines()
        if ln.strip() and not ln.lstrip().startswith("#")
    )
    assert "side_orient=\"a_atk\"" not in body_code
    assert "side_orient='a_atk'" not in body_code
    assert "side_orient=\"a_def\"" not in body_code
    assert "side_orient='a_def'" not in body_code
    # Body MUST forward the parameter through:
    assert "side_orient=next_side_orient" in body_code
```

Note on the `reference/fair_value.py` import: Phase 0 placed `reference/` at the repo root and `pyproject.toml` configures `tool.hatch.build` to include it. If the import fails at test time (because `reference` is not a package), the executor MUST add `reference/__init__.py` as a one-line empty module marker. This is documented as a fallback, not a planned action — most likely `reference/` is already importable since `tests/test_smoke.py` from Phase 0 used a similar pattern.

Commit with message `feat(01-02): implement BO3 DP engine + OT hard-stop + property tests`.
  </action>

  <verify>
    <automated>uv run mypy --strict src/pricing/dp.py &amp;&amp; uv run pytest tests/pricing/test_dp.py -x &amp;&amp; uv run ruff check src/pricing/dp.py tests/pricing/test_dp.py</automated>
  </verify>

  <acceptance_criteria>
    - `test -f src/pricing/dp.py`
    - `grep -q "@dataclass(frozen=True, slots=True)" src/pricing/dp.py` (BO3State is frozen + slots)
    - `grep -q "class BO3State:" src/pricing/dp.py`
    - `grep -q "class RoundPFn(Protocol):" src/pricing/dp.py` (Blocker #3 — Protocol with side-orient accessor)
    - `grep -q "def next_side_orient_for(self, map_idx: int) -> str" src/pricing/dp.py`
    - `grep -q "def series_value(" src/pricing/dp.py` (public entry)
    - `grep -q "@functools.lru_cache(maxsize=None)" src/pricing/dp.py`
    - `grep -q "def _ot_coinflip_leaf(" src/pricing/dp.py`
    - `grep -q "REGULATION_HALF \* 2" src/pricing/dp.py` (OT detection uses the constant relationship, not bare 24)
    - `grep -q "_register_round_p_fn" src/pricing/dp.py` (Callable indirection present)
    - `grep -q "_ROUND_P_FNS: list\[RoundPFn\]" src/pricing/dp.py`
    - `grep -q "next_side_orient: str" src/pricing/dp.py` (Blocker #3 — explicit parameter on `_advance_to_next_map`)
    - `grep -q "side_orient=next_side_orient" src/pricing/dp.py` (Blocker #3 — parameter forwarded, not hardcoded)
    - Comment-stripped source check: `! (grep -v "^[[:space:]]*#" src/pricing/dp.py | grep -E "range\(26\)|range\(WIN_THRESHOLD \* 2\)")` (no broken OT loop)
    - Comment-stripped source check: `! (grep -v "^[[:space:]]*#" src/pricing/dp.py | grep -E "p = p1|p = p2")` (no constant-per-half dispatch)
    - Comment-stripped source check: `! (grep -v "^[[:space:]]*#" src/pricing/dp.py | grep -E "side_orient=[\"']a_atk[\"']|side_orient=[\"']a_def[\"']")` (Blocker #3 — no hardcoded next-map side literal)
    - `test -f tests/pricing/test_dp.py`
    - `grep -q "test_dp_value_in_unit_interval" tests/pricing/test_dp.py`
    - `grep -q "test_dp_symmetric_input_matches_closed_form" tests/pricing/test_dp.py`
    - `grep -q "test_dp_ot_hardstop_returns_coinflip_leaf_symmetric" tests/pricing/test_dp.py`
    - `grep -q "test_dp_ot_hardstop_recurses_into_next_map_for_asymmetric_state" tests/pricing/test_dp.py`
    - `grep -q "test_dp_ot_path_consults_round_p_fn_next_side_orient" tests/pricing/test_dp.py` (Blocker #3 / Warning #9)
    - `grep -q "test_dp_terminal_a_clinched_returns_1" tests/pricing/test_dp.py`
    - `grep -q "test_dp_terminal_b_clinched_returns_0" tests/pricing/test_dp.py`
    - `grep -q "test_dp_lru_cache_records_hits_on_repeat_call" tests/pricing/test_dp.py`
    - `grep -q "test_dp_advance_to_next_map_takes_explicit_next_side_orient" tests/pricing/test_dp.py` (Blocker #3 source-grep regression)
    - `grep -q "_bo3_series_prob" tests/pricing/test_dp.py` (closed-form fixture wired)
    - `uv run mypy --strict src/pricing/dp.py` exits 0
    - `uv run pytest tests/pricing/test_dp.py -x` exits 0 (all 11 tests pass)
    - `uv run ruff check src/pricing/dp.py tests/pricing/test_dp.py` exits 0
  </acceptance_criteria>

  <done>
    `src/pricing/dp.py` exports `BO3State` (frozen+slots dataclass), `RoundPFn` (Protocol with `__call__` + `next_side_orient_for`), and `series_value(state, round_p_fn) -> float`. The DP terminates correctly on all five terminal cases (a_map_score>=2, b_map_score>=2, a_round>=WIN_THRESHOLD, b_round>=WIN_THRESHOLD, total==REGULATION_HALF*2). OT leaf collapses to 50/50 over next-map series states with the next map's starting side fetched from `RoundPFn.next_side_orient_for` (NO hardcoded 'a_atk' anywhere — Blocker #3 fix). Asymmetric leaf semantics verified (test 4 gives 0.75 for the 1-0 + 12-12 case). All 11 hypothesis property + regression tests pass. `mypy --strict`, `pytest`, `ruff` all green. The three PRD §12.2 audit-bugs (#3 OT iteration, #5 constant per-half, #6 hardcoded next-map side) are regression-locked by source greps.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| `series_value` ↔ caller | The `round_p_fn` closure is supplied by the caller (`live_theo.py` in 01-05). The DP must not panic on any valid float in `[0.0, 1.0]` returned from the closure. |
| BO3State construction | Caller (live_theo) builds BO3State from MatchState. Invalid states (e.g., `a_map_score=3`) are not validated by the DP — caller is responsible for invariants. |
| `_ROUND_P_FNS` registry | Module-level mutable list — append-only. Cache grows for the lifetime of the process. |
| RoundPFn closure side-orient lookup | Caller's `next_side_orient_for(map_idx)` may be called with `map_idx >= len(map_pool)` for series-clinch states; caller must handle defensively (return any value — DP will not consume it because of the terminal short-circuit). |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-01-02-01 | Tampering | `_series_value_cached` (NaN propagation if round_p_fn returns NaN) | mitigate | `series_value` itself does not introduce NaN; the round_p_fn closure (built in 01-05 via blend.round_p) clips inputs and never returns NaN. Property test `test_dp_value_in_unit_interval` covers all `p ∈ [0, 1]`. |
| T-01-02-02 | DoS | `_ROUND_P_FNS` registry growing unboundedly across calls | accept | Each `live_theo` call appends one closure; at ~50-100 calls/match → ~100 entries/match → ~10K/day worst case. Memory bounded for any realistic workload. Phase 5 may add `cache_clear()` between matches. |
| T-01-02-03 | Tampering | Silent OT iteration past total=24 (PRD §12.2 #3 regression) | mitigate | `test_dp_source_does_not_loop_past_24` regression-locks; explicit hard-stop at `total == REGULATION_HALF * 2`; `test_dp_ot_hardstop_recurses_into_next_map_for_asymmetric_state` verifies leaf semantics |
| T-01-02-04 | Tampering | Constant `p1`/`p2`-per-half regression (PRD §12.2 #5) | mitigate | `test_dp_source_does_not_use_constant_p1_p2_dispatch` regression-locks; the architectural seam is `round_p_fn` injection (per-round resolver lives in `round_types.py` in 01-03) |
| T-01-02-05 | Tampering | `BO3State` cache key collision via mutable field | mitigate | `frozen=True, slots=True` enforces immutability; `tuple` (not `list`) for `map_pool` and `pistol_winner_a` (Pitfall 1); `mypy --strict` blocks reassignment |
| T-01-02-06 | Tampering | Hardcoded `'a_atk'` next-map side regression (PRD §12.2 #6 audit `series_theo_no_sides` bug class) | mitigate | `test_dp_advance_to_next_map_takes_explicit_next_side_orient` regression-locks BOTH the signature parameter AND the body's lack of hardcoded literal; `test_dp_ot_path_consults_round_p_fn_next_side_orient` verifies live wiring across the OT path. |
</threat_model>

<verification>
After Task 1 completes:

```bash
uv run mypy --strict src/pricing/dp.py
uv run pytest tests/pricing/test_dp.py -x -v
uv run ruff check src/pricing/dp.py tests/pricing/test_dp.py
```

All MUST exit 0. Test count: 11 tests, all pass (including 2 hypothesis property tests with at least 50 examples each, plus the OT-path side-orient regression test).

Sanity check (manual):
```bash
uv run python -c "
from src.pricing.dp import BO3State, series_value

class _Fn:
    def __init__(self, p): self._p = p
    def __call__(self, _s): return self._p
    def next_side_orient_for(self, _i): return 'a_atk'

root = BO3State(0, 0, 0, 0, 0, 'a_atk', ('Lotus','Bind','Haven'), (None,None,None))
print('p=0.5:', series_value(root, _Fn(0.5)))
print('p=0.6:', series_value(root, _Fn(0.6)))
print('p=0.7:', series_value(root, _Fn(0.7)))
"
```
Expected output:
- `p=0.5: 0.5` (BO3 with each-side-50% gives 50% series win)
- `p=0.6: 0.648` (matches `0.6**2 * (3 - 2*0.6) = 0.36 * 1.8 = 0.648`)
- `p=0.7: 0.784` (matches `0.7**2 * (3 - 2*0.7) = 0.49 * 1.6 = 0.784`)
</verification>

<success_criteria>
- `BO3State` dataclass exists, is frozen + slots, hashable (works with `lru_cache`)
- `RoundPFn` Protocol exists with `__call__(BO3State) -> float` and `next_side_orient_for(int) -> str` methods
- `series_value(state, round_p_fn)` returns the BO3 series win probability under the supplied per-round closure
- DP terminates correctly on all five terminal cases; recursion never iterates past `total = REGULATION_HALF * 2`
- OT leaf is the 50/50 collapse onto next-map series states (asymmetric leaf semantics verified — D-05) with next-map side sourced from the `RoundPFn` closure (Blocker #3)
- `_advance_to_next_map` signature includes explicit `next_side_orient: str` parameter; body does NOT hardcode `'a_atk'` or `'a_def'` (Blocker #3 / Warning #9)
- `lru_cache(maxsize=None)` is used; Callable indirection via `_register_round_p_fn` works (Cache hits > 0 on repeat call)
- All 11 tests in `tests/pricing/test_dp.py` pass under `mypy --strict`
- Source contains no `range(26)`, no `range(WIN_THRESHOLD * 2)`, no `p = p1`/`p = p2` constant dispatch, no hardcoded `'a_atk'`/`'a_def'` literal in `_advance_to_next_map` body (regression vs PRD §12.2 #3, #5, #6)
- Source uses `REGULATION_HALF * 2` literal (CON-no-magic-numbers — no inline `24`)
- `tests/test_smoke.py`, `tests/test_main.py`, `tests/config/test_constants.py`, `tests/pricing/test_blend.py` (from Phase 0 + 01-01) still pass — no regressions
</success_criteria>

<output>
After completion, create `.planning/phases/01-core-pricing-engine/01-02-bo3-dp-engine-SUMMARY.md`.

The SUMMARY must record:
- BO3State field set as shipped (8 fields, frozen+slots)
- RoundPFn Protocol surface as shipped (`__call__`, `next_side_orient_for` — Blocker #3 fix)
- `_advance_to_next_map` signature as shipped (3 params, no default for `next_side_orient`)
- The 5 terminal cases and their values
- The OT leaf math (formula + recursion target + how next-map side is fetched from closure)
- The Callable indirection mechanism (registry + int id)
- Test count: 11 tests including 2 hypothesis property tests with example counts and the OT-path side-orient regression test
- Cache behavior on the canonical 3-map root: `(hits, currsize)` after `series_value(root, _ConstantRoundPFn(0.6))` for downstream profiling reference (01-05's D-16 decision)
- Confirmation that NO 'a_atk' or 'a_def' literal exists inside `_advance_to_next_map` body — Blocker #3 / Warning #9 fix is live
- Commit SHA for the single atomic commit
</output>
