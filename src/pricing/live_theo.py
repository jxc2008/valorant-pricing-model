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

from dataclasses import dataclass, replace
from typing import Optional

from src.config.constants import (
    CONVICTION_CLIP_HIGH,
    CONVICTION_CLIP_LOW,
    REGULATION_HALF,
    WIN_THRESHOLD,
)
from src.pricing.data import HalfRates, MatchState, TheoOutput
from src.pricing.dp import (
    BO3State,
    RoundPFn,
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

    Memoizes the within-map sub-states with functools.lru_cache. The cache is
    keyed by (a_round, b_round, side_orient) only — closure-bound state
    (map_idx, starting_side, etc.) is stable for the call.
    """
    # Build a lightweight closure over the within-map state space.
    fn = _RoundPFnImpl(match_state=match_state, half_rates=half_rates)
    memo: dict[tuple[int, int, str], float] = {}

    def _p_a_recursive(a_round: int, b_round: int, side_orient: str) -> float:
        cached = memo.get((a_round, b_round, side_orient))
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
            pistol_winner_a=pistol_winner_a,
        )
        p_round = fn(synthetic)
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
            new_a_round, b_round, side_after_a_win
        ) + (1.0 - p_round) * _p_a_recursive(
            a_round, new_b_round, side_after_b_win
        )
        memo[(a_round, b_round, side_orient)] = result
        return result

    raw = _p_a_recursive(0, 0, starting_side)
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


# Stubs filled in Task 2b — keep signatures stable so Task 2a tests pass.
def _compute_vega(root: BO3State, round_p_fn: RoundPFn) -> float:
    """Stub: Task 2b implements DEC-018 form. Returns 0.0 here so Task 2a tests pass."""
    _ = (root, round_p_fn)
    return 0.0


def _compute_confidence(state: MatchState, half_rates: HalfRates) -> float:
    """Stub: Task 2b implements TRUE DP-mass-weighted formula per D-08 / W3."""
    _ = (state, half_rates)
    return 0.0
