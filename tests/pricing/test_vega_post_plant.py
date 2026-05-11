"""Plan 04-04 — REQ-vega-output (DEC-018 v2 second arm) tests.

compute_vega_post_plant returns variance over {kill, defuse, time-out}
post-plant outcomes. Pure function — no I/O.

Mirrors the inline _make_state pattern from tests/pricing/test_live_theo_dispatch.py
(pricing tests construct MatchState directly; the ingestion conftest fixture
is not visible from tests/pricing/).

Source: REQ-vega-output / DEC-018 v2 / 04-RESEARCH §"Open Questions" #2.
"""
from __future__ import annotations

import pytest

from src.pricing.live_theo import compute_vega_post_plant
from src.pricing.round_conclusion import RoundConclusionLookup
from src.state.match_state import MatchState


def _make_state(
    *,
    bomb_planted: bool,
    attackers_alive: int | None = None,
    defenders_alive: int | None = None,
    time_left_s: float | None = None,
    side_orient: str = "atk",
) -> MatchState:
    """Mid-game synthetic MatchState for compute_vega_post_plant isolation."""
    return MatchState(
        match_id="vega-pp-001",
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
        b_round=8,
        side_orient=side_orient,
        bomb_planted=bomb_planted,
        attackers_alive=attackers_alive,
        defenders_alive=defenders_alive,
        time_left_s=time_left_s,
        seq_id=0,
        last_updated_ts=0.0,
    )


@pytest.fixture
def lookup() -> RoundConclusionLookup:
    """Load the calibrated v2 lookup from disk (shipped by plan 03-07)."""
    return RoundConclusionLookup.from_json("models/round_conclusion.json")


def test_returns_zero_when_not_bomb_planted(lookup: RoundConclusionLookup) -> None:
    state = _make_state(bomb_planted=False)
    assert compute_vega_post_plant(state, lookup) == 0.0


def test_returns_zero_when_attackers_alive_none(lookup: RoundConclusionLookup) -> None:
    """Defensive None-guard mirroring Phase 03 D-05."""
    state = _make_state(
        bomb_planted=True,
        attackers_alive=None,
        defenders_alive=3,
        time_left_s=20.0,
    )
    assert compute_vega_post_plant(state, lookup) == 0.0


def test_returns_zero_when_defenders_alive_none(lookup: RoundConclusionLookup) -> None:
    state = _make_state(
        bomb_planted=True,
        attackers_alive=2,
        defenders_alive=None,
        time_left_s=20.0,
    )
    assert compute_vega_post_plant(state, lookup) == 0.0


def test_returns_zero_when_time_left_none(lookup: RoundConclusionLookup) -> None:
    state = _make_state(
        bomb_planted=True,
        attackers_alive=2,
        defenders_alive=3,
        time_left_s=None,
    )
    assert compute_vega_post_plant(state, lookup) == 0.0


def test_returns_non_negative_for_bomb_planted_state(
    lookup: RoundConclusionLookup,
) -> None:
    state = _make_state(
        bomb_planted=True,
        attackers_alive=2,
        defenders_alive=2,
        time_left_s=20.0,
    )
    result = compute_vega_post_plant(state, lookup)
    assert result >= 0.0


def test_pure_function(lookup: RoundConclusionLookup) -> None:
    """Same inputs → same output across multiple calls."""
    state = _make_state(
        bomb_planted=True,
        attackers_alive=3,
        defenders_alive=2,
        time_left_s=15.0,
    )
    results = [compute_vega_post_plant(state, lookup) for _ in range(5)]
    assert all(r == results[0] for r in results)


def test_defenders_dead_low_variance(lookup: RoundConclusionLookup) -> None:
    """When defenders are dead (def=0), no defuse possible → low variance.

    All three outcomes converge near p_now → variance close to 0.
    """
    state = _make_state(
        bomb_planted=True,
        attackers_alive=5,
        defenders_alive=0,
        time_left_s=20.0,
    )
    result = compute_vega_post_plant(state, lookup)
    # Floor: should be very small but non-negative.
    assert 0.0 <= result <= 0.05
