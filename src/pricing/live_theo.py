"""Single canonical pricing entry point: live_theo (via LiveTheoEngine bundle).

Replaces audit-engine series_theo / series_theo_no_sides / series_theo_from_map_probs
triplet (DEC-010 / CRule 1). All four bug fixes documented at the file level:
  1. Bradley-Terry blend (DEC-003)        — via src.pricing.blend
  2. OT hard-stop at total=24 (DEC-009)   — via src.pricing.dp
  3. Pistol/anti-eco modeling (DEC-011)   — via src.pricing.round_types
  4. Conviction clip [0.01, 0.99] (DEC-012) — applied here at output assembly

Phase 1 ships LiveTheoEngine bundle (D-20) preserving PRD §6 / DEC-010 / CRule 1
state-only call surface: ``engine = LiveTheoEngine(half_rates, round_conclusion);
engine(state) -> TheoOutput``. The pure helper ``_live_theo_impl`` is exported for
testability (tests can call it without constructing a bundle).

Phase 1 owns MatchState in src/pricing/data.py (D-14). Phase 3 will move
MatchState to src/state/match_state.py and live_theo.py will re-import from there.

Sources
-------
- prd.md §2 / §6 (state-only call surface)
- DEC-002, DEC-003, DEC-009, DEC-010, DEC-012, DEC-018
- D-08 (confidence semantics), D-09 (data_weight salvage), D-10/D-11 (vega)
- D-12 (forbidden audit triplet), D-18 (map_side_orients), D-19 (map_winners),
  D-20 (LiveTheoEngine bundle)
- 01-RESEARCH.md §7 (confidence forward-pass), §8 (vega), §10 (MatchState surface)
- reference/theo_engine.py:104-129 (data_weight salvage source)
"""

from __future__ import annotations

import functools
from dataclasses import dataclass, replace
from typing import Optional

from src.config.constants import (
    CONVICTION_CLIP_HIGH,
    CONVICTION_CLIP_LOW,
    MIN_ROUNDS_FULL_WEIGHT,
    REGULATION_HALF,
    WIN_THRESHOLD,
)
from src.pricing.data import HalfRates, MatchState, TheoOutput
from src.pricing.dp import (
    BO3State,
    RoundPFn,
    _advance_round,
    _advance_to_next_map,
    series_value,
)
from src.pricing.round_conclusion import RoundConclusionFn
from src.pricing.round_types import round_p_for_round

# --------------------------------------------------------------------------- #
# 1. State conversion (MatchState -> BO3State)                                #
# --------------------------------------------------------------------------- #


def _bo3_state_from_match_state(state: MatchState) -> BO3State:
    """Project the DP-relevant subset of MatchState into a BO3State cache key.

    Packs ``pistol_winner_a: dict[int, Optional[bool]]`` into a tuple keyed by
    map_idx (0..len(map_pool)-1) so BO3State remains hashable for lru_cache.
    """
    pistol_tuple = tuple(
        state.pistol_winner_a.get(i, None) for i in range(len(state.map_pool))
    )
    return BO3State(
        map_idx=state.map_idx,
        a_map_score=state.a_map_score,
        b_map_score=state.b_map_score,
        a_round=state.a_round,
        b_round=state.b_round,
        side_orient=state.side_orient,
        map_pool=state.map_pool,
        pistol_winner_a=pistol_tuple,
    )


# --------------------------------------------------------------------------- #
# 2. RoundPFn closure — threads MatchState through to round_p_for_round       #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class _RoundPFnImpl:
    """Satisfies dp.RoundPFn Protocol (D-18 wiring).

    ``__call__(s)`` resolves the EFFECTIVE side from ``match_state.map_side_orients[s.map_idx]``
    AND applies the within-map round-12 flip. This closes PRD §12.2 #6 audit
    ``series_theo_no_sides`` bug class — the DP no longer hardcodes 'a_atk' for
    next-map roots; live_theo supplies the per-map starting side via this object.

    ``next_side_orient_for(map_idx)`` is consulted by 01-02's
    ``_advance_to_next_map`` and ``_ot_coinflip_leaf`` callsites.
    """

    match_state: MatchState
    half_rates: HalfRates

    def __call__(self, state: BO3State) -> float:
        effective_side = self._effective_side(state)
        s_corrected = replace(state, side_orient=effective_side)
        return round_p_for_round(s_corrected, self.match_state, self.half_rates)

    def _effective_side(self, state: BO3State) -> str:
        if state.map_idx >= len(self.match_state.map_side_orients):
            # Past series-clinch; never consumed but defensive.
            return "a_atk"
        starting_side = self.match_state.map_side_orients[state.map_idx]
        rounds_played = state.a_round + state.b_round
        if rounds_played < REGULATION_HALF:
            return starting_side
        # Rounds 12..23: flipped half. (OT handled by dp's OT coinflip leaf.)
        return "a_def" if starting_side == "a_atk" else "a_atk"

    def next_side_orient_for(self, map_idx: int) -> str:
        if map_idx >= len(self.match_state.map_side_orients):
            return "a_atk"
        return self.match_state.map_side_orients[map_idx]


# --------------------------------------------------------------------------- #
# 3. Per-map marginal probability (with map_winners short-circuit)            #
# --------------------------------------------------------------------------- #


def _marginal_map_prob(
    state: MatchState,
    m: int,
    half_rates: HalfRates,
) -> float:
    """P(team A wins map m | current state).

    Three cases (per D-19 + DEC-002 / CRule 2 marginalization):
      m < state.map_idx:
        Map already played. Indicator value from ``state.map_winners[m]``,
        clipped to [CONVICTION_CLIP_LOW, CONVICTION_CLIP_HIGH] per DEC-012.
        BO3State carries only AGGREGATE map scores and cannot recover this
        — D-19 ensures ``map_winners`` does.
      m == state.map_idx:
        Current map. P(A wins this map) extracted from the DP via the
        marginalization identity:
            series_value(state) =
                P(A wins map m) * series_value(state_after_a_wins_map_m)
              + (1 - P(A wins map m)) * series_value(state_after_b_wins_map_m)
        Solving for P(A wins map m).
      m > state.map_idx:
        Future map. Same identity applied at the within-map root for map m,
        which the DP reaches by recursion. Series-clinch terminals zero out
        contributions from unreachable branches automatically.
    """
    fn = _RoundPFnImpl(match_state=state, half_rates=half_rates)
    if m < state.map_idx:
        # Already-played map: indicator from map_winners.
        winner = state.map_winners[m]
        if winner is True:
            return CONVICTION_CLIP_HIGH
        if winner is False:
            return CONVICTION_CLIP_LOW
        # Defensive: should never be None for m < map_idx; treat as coinflip.
        return 0.5

    if m == state.map_idx:
        bo3 = _bo3_state_from_match_state(state)
        next_side = fn.next_side_orient_for(m + 1)
        state_after_a = _advance_to_next_map(bo3, a_won=True, next_side_orient=next_side)
        state_after_b = _advance_to_next_map(bo3, a_won=False, next_side_orient=next_side)
        v_after_a = series_value(state_after_a, fn)
        v_after_b = series_value(state_after_b, fn)
        v_root = series_value(bo3, fn)
        denom = v_after_a - v_after_b
        if abs(denom) < 1e-12:
            # Map has no marginal effect (e.g., series already decided regardless
            # of this map's outcome) — defensively return 0.5.
            return 0.5
        p_a_wins_map_m = (v_root - v_after_b) / denom
        return max(CONVICTION_CLIP_LOW, min(CONVICTION_CLIP_HIGH, p_a_wins_map_m))

    # m > state.map_idx: future map.
    # P(A wins map m) computed via the WITHIN-MAP sub-DP rooted at
    # (a_round=0, b_round=0) on map m, independent of series-level state.
    # We cannot reuse series_value here because the audit-engine BO3 DP
    # always advances to the NEXT map after a map clinch; for unreachable
    # synthetic roots (e.g., starting BO3 at map_idx=1, a=0, b=0) the
    # advance can land in invalid map_idx beyond len(map_pool). The
    # within-map DP terminates strictly at WIN_THRESHOLD or the OT leaf.
    bo3 = _bo3_state_from_match_state(state)
    starting_side = fn.next_side_orient_for(m)
    return _within_map_p_a_wins(
        map_pool=bo3.map_pool,
        map_idx=m,
        starting_side=starting_side,
        pistol_winner_a=bo3.pistol_winner_a,
        match_state=state,
        half_rates=half_rates,
    )


# --------------------------------------------------------------------------- #
# 3b. Within-map DP (used for future-map marginals only)                      #
# --------------------------------------------------------------------------- #


def _within_map_p_a_wins(
    map_pool: tuple[str, ...],
    map_idx: int,
    starting_side: str,
    pistol_winner_a: tuple[Optional[bool], ...],  # noqa: UP045 — Optional retained for plan-mandated form
    match_state: MatchState,
    half_rates: HalfRates,
) -> float:
    """P(A wins the map at ``map_idx`` | within-map root at (0, 0)).

    Used ONLY by ``_marginal_map_prob`` for ``m > state.map_idx``, where
    feeding the BO3 ``series_value`` DP an unreachable synthetic root would
    push it past ``len(map_pool)`` (audit-engine series_value always advances
    to next map after a within-map clinch). Terminates strictly at
    WIN_THRESHOLD or the explicit OT-as-coinflip leaf (DEC-009 / D-05).
    Output clipped per DEC-012.

    WR-06 fix (VERIFICATION.md gaps[1] / 01-REVIEW.md WR-06 — same root cause
    as CR-05 scoped to the future-map sub-DP): the inline state-advance now
    propagates ``pistol_winner_a`` through the recursion, mirroring
    ``dp._advance_round``. At the round-1 boundary (a_round == 0 and b_round
    == 0), the next sub-state's ``pistol_winner_a[map_idx]`` is set to the
    branch's ``a_wins`` truth IF the slot was previously None (don't override
    ingested live values). The recursion then carries the updated tuple
    forward so round 2 / 3 dispatch hits GUN_WIN_RATE in
    ``round_p_for_round``, not the defensive 0.5 fallback. The cache key
    is extended to ``(a_round, b_round, side_orient, pistol_winner_a)`` — the
    propagated tuple is hashable, so the memo stays well-typed.

    Memoizes the within-map sub-states with functools.lru_cache. The cache is
    cleared between calls via ``_clear_pricing_caches`` (CR-04). Per-call
    allocation is intentional (per-call closure binding of ``match_state`` /
    ``half_rates`` differs across callers).
    """
    # Build a lightweight closure over the within-map state space.
    fn = _RoundPFnImpl(match_state=match_state, half_rates=half_rates)
    memo: dict[
        tuple[int, int, str, tuple[Optional[bool], ...]],  # noqa: UP045
        float,
    ] = {}

    def _p_a_recursive(
        a_round: int,
        b_round: int,
        side_orient: str,
        pistol: tuple[Optional[bool], ...],  # noqa: UP045
    ) -> float:
        cached = memo.get((a_round, b_round, side_orient, pistol))
        if cached is not None:
            return cached
        if a_round >= WIN_THRESHOLD:
            return 1.0
        if b_round >= WIN_THRESHOLD:
            return 0.0
        if a_round + b_round == REGULATION_HALF * 2:
            # OT-as-coinflip leaf per DEC-009. Within-map OT continues with
            # constant p=0.5 until win-by-2; collapsed here to a scalar 0.5
            # because the within-map P(A wins) stays at 0.5 in OT (symmetric).
            return 0.5
        synthetic = BO3State(
            map_idx=map_idx,
            a_map_score=0,
            b_map_score=0,
            a_round=a_round,
            b_round=b_round,
            side_orient=side_orient,
            map_pool=map_pool,
            pistol_winner_a=pistol,
        )
        p_round = fn(synthetic)

        # WR-06: propagate pistol_winner_a at the round-1 boundary, mirroring
        # dp._advance_round (CR-05 fix). Round 1 settles when (a_round, b_round)
        # was (0, 0) on entry — the about-to-recurse sub-states represent
        # post-round-1 states, so we update pistol_winner_a[map_idx] for each
        # branch IF the slot is currently None.
        if a_round == 0 and b_round == 0 and pistol[map_idx] is None:
            pistol_after_a: tuple[Optional[bool], ...] = tuple(  # noqa: UP045
                (True if i == map_idx else pistol[i]) for i in range(len(pistol))
            )
            pistol_after_b: tuple[Optional[bool], ...] = tuple(  # noqa: UP045
                (False if i == map_idx else pistol[i]) for i in range(len(pistol))
            )
        else:
            pistol_after_a = pistol
            pistol_after_b = pistol

        new_a_round = a_round + 1
        if new_a_round + b_round == REGULATION_HALF:
            side_after_a_win = "a_def" if side_orient == "a_atk" else "a_atk"
        else:
            side_after_a_win = side_orient
        new_b_round = b_round + 1
        if a_round + new_b_round == REGULATION_HALF:
            side_after_b_win = "a_def" if side_orient == "a_atk" else "a_atk"
        else:
            side_after_b_win = side_orient
        result = p_round * _p_a_recursive(
            new_a_round, b_round, side_after_a_win, pistol_after_a
        ) + (1.0 - p_round) * _p_a_recursive(
            a_round, new_b_round, side_after_b_win, pistol_after_b
        )
        memo[(a_round, b_round, side_orient, pistol)] = result
        return result

    raw = _p_a_recursive(0, 0, starting_side, pistol_winner_a)
    return max(CONVICTION_CLIP_LOW, min(CONVICTION_CLIP_HIGH, raw))


# --------------------------------------------------------------------------- #
# 4. Output clipping                                                          #
# --------------------------------------------------------------------------- #


def _clip_conviction(theo: float) -> float:
    """Clip to [CONVICTION_CLIP_LOW, CONVICTION_CLIP_HIGH] per DEC-012 / CRule 6."""
    return max(CONVICTION_CLIP_LOW, min(CONVICTION_CLIP_HIGH, theo))


# --------------------------------------------------------------------------- #
# 5. _live_theo_impl scaffold (vega + confidence stubs — Task 2b finalizes)   #
# --------------------------------------------------------------------------- #


def _live_theo_impl(
    state: MatchState,
    half_rates: HalfRates,
    round_conclusion: Optional[RoundConclusionFn] = None,  # noqa: UP045 — Optional for plan-mandated form
) -> TheoOutput:
    """Pure functional core of LiveTheoEngine. Importable for tests.

    Args:
        state: Phase 1 stub MatchState (D-01 / D-02 + D-17/D-18/D-19).
        half_rates: HalfRates instance (typically loaded from data/half_win_rates.json).
        round_conclusion: Optional mid-round-conclusion lookup. Phase 1 returns
            flat 0.5 from RoundConclusionLookup; absent -> not consumed in Phase 1
            because the DP is between-rounds.

    Returns:
        TheoOutput with theo_series, theo_map (per-map marginals), vega
        (DEC-018), and confidence (DP-mass-weighted per D-08).
    """
    # NOTE: round_conclusion is reserved for mid-round vega refinement in
    # Phase 5 (D-11). Currently unused by the orchestrator; pass-through
    # preserved for D-20 bundle.
    _ = round_conclusion  # silence unused-argument lint until Phase 5 wires it

    bo3 = _bo3_state_from_match_state(state)
    fn = _RoundPFnImpl(match_state=state, half_rates=half_rates)

    theo_series_raw = series_value(bo3, fn)
    theo_series = _clip_conviction(theo_series_raw)
    theo_map = tuple(
        _marginal_map_prob(state, m, half_rates) for m in range(len(state.map_pool))
    )

    # Vega + confidence finalized in Task 2b; placeholder values here so
    # ``_live_theo_impl`` is end-to-end callable for Task 2a tests.
    vega = _compute_vega(bo3, fn)
    confidence = _compute_confidence(state, half_rates)

    return TheoOutput(
        theo_series=theo_series,
        theo_map=theo_map,
        vega=vega,
        confidence=confidence,
    )


# --------------------------------------------------------------------------- #
# 5b. _data_weight_for_map (verbatim salvage from reference/theo_engine.py)    #
# --------------------------------------------------------------------------- #


def _data_weight_for_map(
    team_a: str,
    team_b: str,
    map_name: str,
    half_rates: HalfRates,
) -> float:
    """Audit-engine min-over-teams data weight per D-09.

    Source: reference/theo_engine.py:104-129 — salvage verbatim, retyped for
    mypy strict. Used in confidence aggregation to weight maps by how much
    empirical data backs the per-team rates on that map.
    """
    team_weights: list[float] = []
    for team in (team_a, team_b):
        team_total = 0.0
        team_count = 0
        for side in ("atk", "def"):
            entry = half_rates.team_entry(team, map_name, side)
            if entry and not entry.get("used_fallback", False):
                team_total += float(entry.get("total", 0))
                team_count += 1
        if team_count == 0:
            return 0.0
        team_weights.append(team_total / team_count)
    # Min-over-teams normalized by MIN_ROUNDS_FULL_WEIGHT (D-09 / Acceptance lock).
    return min(1.0, min(team_weights) / MIN_ROUNDS_FULL_WEIGHT)


# --------------------------------------------------------------------------- #
# 6. _p_map_decisive — TRUE DP-mass forward pass per W3                       #
# --------------------------------------------------------------------------- #


def _p_map_decisive(
    state: MatchState,
    m: int,
    half_rates: HalfRates,
) -> float:
    """P(map m is the map that closes the series | current state).

    Three cases (per W3 / RESEARCH §7):

    For m < state.map_idx:
        Indicator: 1.0 if map m clinched the series in the historical record
        (one team reached 2 wins exactly at map m), else 0.0. Derivable from
        state.map_winners[0..state.map_idx-1].

    For m == state.map_idx:
        P(current map is decisive) =
            P(A wins map m) * (1 if a_map_score+1 == 2 else 0) +
            (1 - P(A wins map m)) * (1 if b_map_score+1 == 2 else 0).

    For m > state.map_idx:
        P(reach map m AND map m is decisive). For BO3, this requires no team
        clinches on maps state.map_idx..m-1 AND map m itself clinches. We
        compute P_reached via the forward-pass DP, and for the BO3 last map
        decisiveness given reached is 1.0.
    """
    # Case 1: already-played map.
    if m < state.map_idx:
        a_through_m = sum(1 for w in state.map_winners[: m + 1] if w is True)
        b_through_m = sum(1 for w in state.map_winners[: m + 1] if w is False)
        a_before = a_through_m - (1 if state.map_winners[m] is True else 0)
        b_before = b_through_m - (1 if state.map_winners[m] is False else 0)
        # Map m was decisive if the score after map m hit 2 for either team
        # AND the score before map m was at most 1 for both.
        if (a_through_m == 2 and a_before == 1) or (
            b_through_m == 2 and b_before == 1
        ):
            return 1.0
        return 0.0

    # Case 2: current map.
    if m == state.map_idx:
        p_a_wins = _marginal_map_prob(state, m, half_rates)
        a_decisive = 1.0 if state.a_map_score + 1 == 2 else 0.0
        b_decisive = 1.0 if state.b_map_score + 1 == 2 else 0.0
        return p_a_wins * a_decisive + (1.0 - p_a_wins) * b_decisive

    # Case 3: future map. P(reached) × P(decisive | reached).
    bo3 = _bo3_state_from_match_state(state)
    fn = _RoundPFnImpl(match_state=state, half_rates=half_rates)

    p_reached = _p_reach_map(bo3, fn, m)
    if m == len(state.map_pool) - 1:
        # Last map of the BO3 — always decisive once reached.
        return p_reached
    # Middle future map (BO3: m == state.map_idx + 1, m != len-1). CR-02 fix:
    # decisive iff the same team wins both the previous map and this one.
    # P(decisive | reached) = P(prev_winner == m_winner)
    #                       = p_a_{m-1} * p_a_m + (1 - p_a_{m-1}) * (1 - p_a_m)
    # Reuses _marginal_map_prob so the same canonical DP backs both terms
    # (CRule 1 / DEC-002 / DEC-010 — no parallel math).
    p_a_wins_m_minus_1 = _marginal_map_prob(state, m - 1, half_rates)
    p_a_wins_m = _marginal_map_prob(state, m, half_rates)
    p_decisive_given_reached = p_a_wins_m_minus_1 * p_a_wins_m + (1.0 - p_a_wins_m_minus_1) * (1.0 - p_a_wins_m)  # noqa: E501 — plan acceptance grep requires single-line BO3 decisive formula
    return p_reached * p_decisive_given_reached


# Registry indirection for lru_cache — RoundPFn closures aren't reliably
# hashable (MatchState carries a dict). Mirrors dp.py's _ROUND_P_FNS pattern.
_REACH_MAP_FNS: list[RoundPFn] = []


def _register_reach_map_fn(fn: RoundPFn) -> int:
    _REACH_MAP_FNS.append(fn)
    return len(_REACH_MAP_FNS) - 1


def _clear_pricing_caches() -> None:
    """Reset the closure registry and lru_cache for one-shot pricing calls.

    CR-04 fix companion (VERIFICATION.md gaps[3]). Same rationale as
    ``dp._clear_pricing_caches``: ``_REACH_MAP_FNS`` is append-only and the
    cache key includes the int id so cross-call cache hits are already 0%.
    """
    _REACH_MAP_FNS.clear()
    _p_reach_map_cached.cache_clear()


def _p_reach_map(
    state: BO3State,
    round_p_fn: RoundPFn,
    m: int,
) -> float:
    """P(reach map m starting from ``state`` under round_p_fn).

    Indirection wrapper: registers the closure with int-keyed registry so
    the cached helper can hash on (BO3State, int, int).
    """
    fn_id = _register_reach_map_fn(round_p_fn)
    return _p_reach_map_cached(state, fn_id, m)


@functools.lru_cache(maxsize=None)  # noqa: UP033 — plan acceptance grep requires lru_cache(maxsize=None)
def _p_reach_map_cached(
    state: BO3State,
    round_p_fn_id: int,
    m: int,
) -> float:
    """Memoized P(reach map m starting from ``state``).

    Terminal-check order (CR-01 fix — VERIFICATION.md gaps[0]): the series-clinch
    short-circuit MUST fire BEFORE the ``state.map_idx == m`` check. Otherwise an
    unreachable post-clinch recursion path that lands at ``map_idx == m`` returns
    1.0 (treated as "reached") instead of 0.0 (the series never plays subsequent
    maps once a team hits 2 wins).

    Recursive on BO3State.map_idx:
      - a_map_score >= 2 or b_map_score >= 2: return 0.0 (clinched, never reach m)
      - state.map_idx == m: return 1.0 (reached)
      - state.map_idx > m: return 0.0 (past target without reaching — defensive)
      - else: recurse on (state_after_a_wins_current, state_after_b_wins_current)
        weighted by the within-map P(A wins).
    """
    if state.a_map_score >= 2 or state.b_map_score >= 2:
        return 0.0
    if state.map_idx == m:
        return 1.0
    if state.map_idx > m:
        return 0.0  # Past target without reaching — defensive.

    fn = _REACH_MAP_FNS[round_p_fn_id]
    next_side = fn.next_side_orient_for(state.map_idx + 1)
    state_after_a = _advance_to_next_map(state, a_won=True, next_side_orient=next_side)
    state_after_b = _advance_to_next_map(state, a_won=False, next_side_orient=next_side)
    v_after_a = series_value(state_after_a, fn)
    v_after_b = series_value(state_after_b, fn)
    v_root = series_value(state, fn)
    denom = v_after_a - v_after_b
    p_a = (
        0.5
        if abs(denom) < 1e-12
        else max(0.0, min(1.0, (v_root - v_after_b) / denom))
    )

    return p_a * _p_reach_map_cached(state_after_a, round_p_fn_id, m) + (
        1.0 - p_a
    ) * _p_reach_map_cached(state_after_b, round_p_fn_id, m)


# --------------------------------------------------------------------------- #
# 7. _compute_confidence (DP-mass-weighted per D-08 — replaces Task 2a stub)  #
# --------------------------------------------------------------------------- #


def _compute_confidence(state: MatchState, half_rates: HalfRates) -> float:
    """confidence = sum_m (data_w(m) × P(map m decisive | state)) / sum_m P(...).

    Per D-08: weight each map's _data_weight by the probability that map is
    the one closing the series. Maps the series is unlikely to reach
    contribute less. State-dependent — confidence changes round-to-round
    even with no new data. Phase 4 kill-switch logic must accept that.

    Returns 0.0 if denominator is < 1e-12 (defensive: series effectively
    decided already; no map is "decisive" because terminals fired).
    """
    weighted_sum = 0.0
    mass_sum = 0.0
    for m in range(len(state.map_pool)):
        map_name = state.map_pool[m]
        data_w = _data_weight_for_map(state.team_a, state.team_b, map_name, half_rates)
        p_decisive = _p_map_decisive(state, m, half_rates)
        weighted_sum += data_w * p_decisive
        mass_sum += p_decisive

    if mass_sum < 1e-12:
        return 0.0
    return max(0.0, min(1.0, weighted_sum / mass_sum))


# --------------------------------------------------------------------------- #
# 8. _compute_vega (DEC-018 — replaces Task 2a stub)                          #
# --------------------------------------------------------------------------- #


def _compute_vega(root: BO3State, round_p_fn: RoundPFn) -> float:
    """vega = round_p × (theo_a − theo)² + (1 − round_p) × (theo_b − theo)².

    Per DEC-018 / D-10 / D-11. Computed at every live_theo invocation
    (D-11 — Phase 1 doesn't gate to round boundaries). Uses two extra
    series_value lookups (state_a_wins, state_b_wins) plus the root value.

    Always >= 0 by construction (sum of squared deviations weighted by probs).

    Terminal short-circuits (CR-03 fix — VERIFICATION.md gaps[2], CRule 5):

      - Series terminal (a_map_score >= 2 or b_map_score >= 2): theo is the
        constant 1.0 or 0.0; vega is 0.
      - Within-map terminal (a_round or b_round >= WIN_THRESHOLD): the map is
        decided; per-round vega is 0 (the next "round" doesn't exist within
        this map).
      - OT entry (a_round + b_round >= REGULATION_HALF * 2): _advance_round
        would push past the DP's OT hard-stop at total=24 (DEC-009 / CRule 5),
        silently bypassing _ot_coinflip_leaf. Instead, vega here is the
        VARIANCE of the OT coinflip leaf over next-map series outcomes —
        consistent with the DP's own OT semantics.
    """
    # Series terminal: theo is constant, vega is 0.
    if root.a_map_score >= 2 or root.b_map_score >= 2:
        return 0.0
    # Within-map terminal: map is decided, no per-round vega.
    if root.a_round >= WIN_THRESHOLD or root.b_round >= WIN_THRESHOLD:
        return 0.0
    # OT coinflip leaf: vega is variance of the leaf, not of _advance_round.
    if root.a_round + root.b_round >= REGULATION_HALF * 2:
        next_side = round_p_fn.next_side_orient_for(root.map_idx + 1)
        v_a = series_value(
            _advance_to_next_map(root, a_won=True, next_side_orient=next_side),
            round_p_fn,
        )
        v_b = series_value(
            _advance_to_next_map(root, a_won=False, next_side_orient=next_side),
            round_p_fn,
        )
        mean = 0.5 * (v_a + v_b)
        return 0.5 * (v_a - mean) ** 2 + 0.5 * (v_b - mean) ** 2
    # Standard regulation case (existing body):
    state_a_wins = _advance_round(root, a_wins=True)
    state_b_wins = _advance_round(root, a_wins=False)
    theo = series_value(root, round_p_fn)
    theo_a = series_value(state_a_wins, round_p_fn)
    theo_b = series_value(state_b_wins, round_p_fn)
    p = round_p_fn(root)
    return p * (theo_a - theo) ** 2 + (1.0 - p) * (theo_b - theo) ** 2


# --------------------------------------------------------------------------- #
# 9. LiveTheoEngine bundle (D-20)                                             #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class LiveTheoEngine:
    """Single canonical pricing entry point — bundle pattern per D-20.

    Preserves PRD §6 / DEC-010 / CRule 1's state-only call surface:
        engine = LiveTheoEngine(half_rates)
        engine(state) -> TheoOutput

    Phase 4 instantiates once per match. When Phase 4 needs additional
    dependencies (e.g., MetricsEmitter), they're added as constructor
    arguments without changing the per-call __call__ signature.

    Usage:
        from src.pricing import LiveTheoEngine, HalfRates
        half_rates = HalfRates.from_json("data/half_win_rates.json")
        engine = LiveTheoEngine(half_rates)
        out = engine(state)  # state: MatchState
    """

    half_rates: HalfRates
    round_conclusion: Optional[RoundConclusionFn] = None  # noqa: UP045 — Optional retained

    def __call__(self, state: MatchState) -> TheoOutput:
        # CR-04: bound memory by clearing the per-call closure registries +
        # lru_caches at the END of every call, even on exception. The
        # cross-call cache hit rate is already 0% (each call registers a new
        # closure id; lru_cache keys on (state, int) so old ids are dead
        # weight). Phase 4's continuous quoter REQUIRES this — see 01-REVIEW.md
        # CR-04 and 01-VERIFICATION.md gaps[3]. Do NOT remove this finally.
        from src.pricing import dp as _dp
        try:
            return _live_theo_impl(state, self.half_rates, self.round_conclusion)
        finally:
            _clear_pricing_caches()
            _dp._clear_pricing_caches()
