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
  4. DP forward-pass dropped pistol_winner_a updates at the round-1 boundary
     (CR-05 / 01-VERIFICATION.md gaps[0]) → ``_advance_round`` now sets
     ``pistol_winner_a[map_idx] = a_wins`` when (and only when) round 1
     settles AND the slot is currently None. Anti-eco rounds {2, 3, 14, 15}
     in DP recursion now dispatch correctly via round_types.py.

Phase 1 simplifications
-----------------------
A6 / A8 in RESEARCH.md Assumptions Log; the second-half pistol limitation
below is a NEW Phase-1 simplification — Phase-2 follow-up.

- Rounds 1, 13 (pistols): half-rates Bradley-Terry blend (A8). Phase 2 will
  calibrate per-team pistol-only rates from match_round_data and swap them
  in via the round_types.py dispatch — the call shape doesn't change.
- Rounds 3, 15 use the same GUN_WIN_RATE as rounds 2, 14 (A6). Phase 2
  calibration may differentiate (~75% on round 2 vs ~60% on round 3 per
  roadmap §1.3).
- pistol_winner_a SECOND-HALF LIMITATION (NEW Phase-1 simplification;
  Phase-2 follow-up — track separately at the roadmap level if Phase 4
  calibration surfaces it as a need): the
  ``pistol_winner_a: tuple[Optional[bool], ...]`` shape is keyed by ``map_idx``
  ONLY (one slot per map). It records the FIRST-half pistol winner. Rounds
  14/15 (anti-eco for the second-half pistol) currently dispatch on
  ``pistol_winner_a[map_idx]`` — i.e., they re-use the first-half pistol
  winner as a proxy. This is structurally wrong but quantitatively bounded
  for Phase 1: the dispatch produces GUN_WIN_RATE / 1-GUN_WIN_RATE biased
  toward the first-half pistol's outcome. Phase 2
  (REQ-round-event-data-pipeline) will extend the data shape to
  ``tuple[Optional[tuple[bool, bool]], ...]`` per (map, half) and update
  the round_types.py dispatch to consult the appropriate half. NO
  data-shape change in Phase 1 — round_types.py:140 + the defensive 0.5
  fallback at round_types.py:152 cover the gap until Phase 2 lands.

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
    pistol_winner_a: tuple[Optional[bool], ...]  # noqa: UP045 — plan-mandated form (RESEARCH §1)


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
    """Increment the winner's round count; flip side at the round-12 boundary;
    update ``pistol_winner_a[map_idx]`` when round 1 settles.

    CR-05 fix (VERIFICATION.md gaps[0] / 01-REVIEW.md): the DP forward-pass
    MUST update ``pistol_winner_a[map_idx] = a_wins`` when advancing past
    round 1 of the current map. Round 1 completes when the round count was
    ``(0, 0)`` and is now ``(1, 0)`` or ``(0, 1)``. The update fires ONLY when
    the existing slot is ``None`` (don't override an ingested live value if
    already settled — see ``test_dp_advance_round_does_not_override_already_settled_pistol``
    for the regression lock).

    Phase-2 follow-up: ``pistol_winner_a`` is keyed only by ``map_idx``, so
    rounds 14/15 cannot be conditioned on a separately-tracked second-half
    pistol winner. Phase 1 ships rounds 14/15 falling through to the
    half-rates blend in ``round_types.round_p_for_round`` (the dispatch at
    line 140 + the defensive 0.5 at line 152 covers the gap). Per-half pistol
    shape (``tuple[Optional[tuple[bool, bool]], ...]``) is a Phase 2 task —
    see REQ-round-event-data-pipeline.
    """
    new_a_round = state.a_round + (1 if a_wins else 0)
    new_b_round = state.b_round + (0 if a_wins else 1)
    # Within-map sides flip after round 12 (i.e., when total==REGULATION_HALF).
    if new_a_round + new_b_round == REGULATION_HALF:
        new_side_orient = "a_def" if state.side_orient == "a_atk" else "a_atk"
    else:
        new_side_orient = state.side_orient

    # CR-05: update pistol_winner_a when advancing past round 1 of the current
    # map. The trigger is "round count was (0, 0)" — i.e., we are committing
    # the outcome of round 1 (the pistol). Only update if the slot is currently
    # None; do NOT override ingested live values. The rebuild is a tuple
    # comprehension (BO3State stays frozen / slots / hashable; see line 48).
    new_pistol: tuple[Optional[bool], ...] = state.pistol_winner_a  # noqa: UP045
    if state.a_round == 0 and state.b_round == 0:
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


def _clear_pricing_caches() -> None:
    """Reset the closure registry and lru_cache for one-shot pricing calls.

    CR-04 fix (VERIFICATION.md gaps[3]): ``_ROUND_P_FNS`` is append-only and
    ``lru_cache(maxsize=None)`` keys on ``(state, round_p_id)`` so each new
    closure id invalidates reuse anyway. Resetting per-call bounds memory
    without sacrificing real cache hits — the int id changes per call, so
    cross-call hits are already 0%.

    Called by ``LiveTheoEngine.__call__`` from a ``finally`` block so it runs
    even if the underlying ``_live_theo_impl`` raises. Phase 4's continuous
    quoter relies on this to avoid a linear-in-time memory leak; do NOT
    "optimize" by skipping the reset — see CR-04 in 01-REVIEW.md.
    """
    _ROUND_P_FNS.clear()
    _series_value_cached.cache_clear()


# --------------------------------------------------------------------------- #
# 5. DP recursion                                                             #
# --------------------------------------------------------------------------- #


@functools.lru_cache(maxsize=None)  # noqa: UP033 — plan acceptance grep requires lru_cache(maxsize=None)
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
