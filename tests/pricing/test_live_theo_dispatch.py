"""REQ-round-conclusion-lookup — D-05 dispatch (bomb_planted vs between-round).

03-02 Wave 2A: GREEN tests for the live_theo bomb_planted dispatch path.
``state.bomb_planted=True`` invokes ``round_conclusion.post_plant_p`` for the
current round and runs the rest of the DP via between-round semantics.
``state.bomb_planted=False`` runs the entire DP via between-round semantics
(side baseline / half-rates blend) — bit-identical to the Phase 1+2 path.
"""

from __future__ import annotations

from src.pricing.data import HalfRates
from src.pricing.live_theo import LiveTheoEngine
from src.pricing.round_conclusion import RoundConclusionLookup, _Cell
from src.state.match_state import MatchState


def _make_half_rates() -> HalfRates:
    """Asymmetric HalfRates — TeamA dominates so v_a > v_b downstream of the dispatch.

    With symmetric rates the DP delivers v(state_after_a_wins) == v(state_after_b_wins)
    by symmetry — the bomb_planted dispatch override (p_round != 0.5) becomes
    structurally invisible because ``p * v + (1-p) * v == v`` for any p. We need
    asymmetry so v_a != v_b and the dispatch override translates into a measurable
    theo shift.
    """
    return HalfRates(
        team_rates={
            f"{t}|{m}|{s}": {
                "wins": (0.6 if t == "A" else 0.4) * 1000.0,
                "total": 1000.0,
                "rate": 0.6 if t == "A" else 0.4,
                "used_fallback": False,
            }
            for t in ("A", "B")
            for m in ("Lotus", "Bind", "Haven")
            for s in ("atk", "def")
        },
        league_rates={
            f"{m}|{s}": {"wins": 50.0, "total": 100.0, "rate": 0.5}
            for m in ("Lotus", "Bind", "Haven")
            for s in ("atk", "def")
        },
        overall_avg=0.5,
    )


def _make_state(
    *,
    bomb_planted: bool,
    attackers_alive: int | None = None,
    defenders_alive: int | None = None,
    time_left_s: float | None = None,
) -> MatchState:
    """Mid-game synthetic MatchState for dispatch isolation.

    side_orient="atk" matches the lookup-key shape (bare side string, not the
    Phase-1 "a_atk"/"a_def" encoding). map_side_orients carries the Phase-1
    encoding so ``_RoundPFnImpl._effective_side`` resolves correctly.
    """
    return MatchState(
        match_id="dispatch-001",
        team_a="A",
        team_b="B",
        map_pool=("Lotus", "Bind", "Haven"),
        map_side_orients=("a_atk", "a_def", "a_atk"),
        map_winners=(None, None, None),
        pistol_winner_a={0: None, 1: None, 2: None},
        map_idx=0,
        a_map_score=0,
        b_map_score=0,
        a_round=10,
        b_round=8,  # mid-game state
        side_orient="atk",
        bomb_planted=bomb_planted,
        attackers_alive=attackers_alive,
        defenders_alive=defenders_alive,
        time_left_s=time_left_s,
        seq_id=0,
        last_updated_ts=0.0,
    )


def test_dispatch_bomb_planted() -> None:
    """When bomb_planted=True, live_theo invokes post_plant_p (verified by populated-cell shift).

    The lookup has one cells_full hit at (att=3, def=2, time_bucket=0,
    side="atk", map="Lotus") with shrunk = (100*0.95 + 15*0.5)/115 = 0.8913 —
    well above the half-rates between-round dispatch p (which under TeamA's
    0.6 empirical rate produces a Bradley-Terry blend p_round_internal ~0.69).
    The bp dispatch overrides ONLY the current round's p with the post_plant
    cell value; the rest of the DP runs at the between-round p_round_internal.
    The resulting theo difference is the load-bearing signal that the
    dispatch is exercised — direction is not load-bearing because it depends
    on the relative magnitudes of p_round_post_plant vs p_round_internal at
    the symmetric mid-game state.
    """
    lookup = RoundConclusionLookup()
    lookup.cells_full[(3, 2, 0, "atk", "Lotus")] = _Cell(
        n=100, p_hat=0.95, parent_p=0.5
    )
    engine = LiveTheoEngine(half_rates=_make_half_rates(), round_conclusion=lookup)

    bp_state = _make_state(
        bomb_planted=True, attackers_alive=3, defenders_alive=2, time_left_s=43.0
    )
    bp_out = engine(bp_state)

    br_state = _make_state(bomb_planted=False)
    br_out = engine(br_state)

    # Dispatch was exercised: theo_series differs between the two states.
    # The difference can ONLY come from the post_plant_p override on round 1
    # of the dispatch path.
    assert bp_out.theo_series != br_out.theo_series
    # Magnitude floor: the difference must be > 1e-3 (the 03-08 E2E gate's
    # post-plant-shifts-theo-by-1c criterion). With cell.p_hat=0.95 vs DP's
    # internal p~0.69, the override moves p by ~0.2 on a single round —
    # propagates to a theo shift well above 1e-3.
    assert abs(bp_out.theo_series - br_out.theo_series) > 1e-3


def test_dispatch_between_round() -> None:
    """When bomb_planted=False, live_theo uses between-round semantics (DP-only path)."""
    lookup = RoundConclusionLookup()  # empty; default side_baseline = 0.5/0.5
    engine = LiveTheoEngine(half_rates=_make_half_rates(), round_conclusion=lookup)

    state = _make_state(bomb_planted=False)
    out = engine(state)

    # Asymmetric half-rates (TeamA at 0.6) at mid-game — theo_series is a
    # well-defined float in (0, 1) that reflects TeamA's edge.
    assert 0.0 < out.theo_series < 1.0
    # TeamA's empirical edge propagates through the between-round DP — theo
    # should be > 0.5 (TeamA dominant under the symmetric league fallback).
    assert out.theo_series > 0.5


def test_dispatch_bomb_planted_with_missing_post_plant_fields_falls_back() -> None:
    """Defensive: bomb_planted=True with missing alive/time fields falls back to between-round.

    D-05 contract: malformed bomb_planted=True states (None on attackers_alive,
    defenders_alive, or time_left_s) degrade to the between-round path with
    degraded confidence — Phase 4's mode selector maps low confidence to IDLE.
    """
    lookup = RoundConclusionLookup()
    lookup.cells_full[(3, 2, 0, "atk", "Lotus")] = _Cell(
        n=100, p_hat=0.7, parent_p=0.5
    )
    engine = LiveTheoEngine(half_rates=_make_half_rates(), round_conclusion=lookup)

    # bomb_planted=True but all post-plant fields are None — degrade gate.
    malformed = _make_state(bomb_planted=True)
    out_malformed = engine(malformed)

    # Should match the between-round theo bit-for-bit, since the DP runs the
    # same series_value(bo3, fn) path.
    br_state = _make_state(bomb_planted=False)
    out_between = engine(br_state)
    assert out_malformed.theo_series == out_between.theo_series
