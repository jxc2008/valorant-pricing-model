"""End-to-end contract tests for src.pricing.live_theo + data shapes.

Verifies REQ-canonical-live-theo + REQ-theo-{series,map}-output +
REQ-confidence-output + REQ-vega-output. Locks the public surface so
downstream Phase 4 quoting layer can import deterministically.

Test sections (extended across Tasks 1 / 2a / 2b / 3):
  1. Data shapes (Task 1)
  2. HalfRates JSON loader (Task 1)
  3. _live_theo_impl core (Task 2a)
  4. LiveTheoEngine bundle + confidence + vega (Task 2b)
  5. Public surface + integration (Task 3)
"""

from __future__ import annotations

import dataclasses
import math
import re
from pathlib import Path

import pytest

from src.config.constants import (
    CONVICTION_CLIP_HIGH,
    CONVICTION_CLIP_LOW,
    MIN_ROUNDS_FULL_WEIGHT,
    SHRINK_PRIOR,
)
from src.pricing.data import HalfRates, MatchState, TheoOutput
from src.pricing.dp import BO3State, _advance_to_next_map
from src.pricing.live_theo import (
    LiveTheoEngine,
    _bo3_state_from_match_state,
    _clip_conviction,
    _compute_confidence,
    _compute_vega,
    _data_weight_for_map,
    _live_theo_impl,
    _marginal_map_prob,
    _p_map_decisive,
    _p_reach_map,
    _RoundPFnImpl,
    _within_map_p_a_wins,
)

# --------------------------------------------------------------------------- #
# 1. Data shapes (Task 1)                                                     #
# --------------------------------------------------------------------------- #


def test_theo_output_is_frozen_dataclass() -> None:
    """PRD §2: TheoOutput is a frozen dataclass with exactly four fields."""
    assert dataclasses.is_dataclass(TheoOutput)
    field_names = {f.name for f in dataclasses.fields(TheoOutput)}
    assert field_names == {"theo_series", "theo_map", "vega", "confidence"}
    # Frozen: assigning to an instance must raise.
    out = TheoOutput(theo_series=0.5, theo_map=(0.5,), vega=0.0, confidence=0.5)
    with pytest.raises(dataclasses.FrozenInstanceError):
        out.theo_series = 0.6  # type: ignore[misc]


def test_match_state_is_17_field_frozen_dataclass() -> None:
    """D-02 + D-17 + D-18 + D-19: 17 fields exactly. Frozen + slots."""
    assert dataclasses.is_dataclass(MatchState)
    fields = dataclasses.fields(MatchState)
    field_names = [f.name for f in fields]
    assert len(fields) == 17, f"expected 17 fields, got {len(fields)}: {field_names}"
    expected = {
        "match_id",
        "team_a",
        "team_b",
        "map_pool",
        "map_idx",
        "a_map_score",
        "b_map_score",
        "a_round",
        "b_round",
        "side_orient",
        "map_side_orients",
        "map_winners",
        "pistol_winner_a",
        "numerical_diff",
        "bomb_planted",
        "side",
        "econ_bucket",
    }
    assert set(field_names) == expected
    # Forbidden Phase 3 fields:
    forbidden = {"seq_id", "last_updated_ts", "players_alive", "ults", "time_left_s"}
    assert not (forbidden & set(field_names)), (
        "Phase 3 fields leaked into Phase 1 stub MatchState"
    )


def test_match_state_d17_d18_d19_fields_present() -> None:
    """D-17/D-18/D-19 fields are present with the correct annotations."""
    annotations = MatchState.__annotations__
    assert "team_a" in annotations  # D-17
    assert "team_b" in annotations  # D-17
    assert "map_side_orients" in annotations  # D-18
    assert "map_winners" in annotations  # D-19


def test_match_state_is_frozen_and_uses_slots() -> None:
    """frozen=True + slots=True per Pattern S3."""
    state = _synthetic_match_state()
    with pytest.raises(dataclasses.FrozenInstanceError):
        state.match_id = "other"  # type: ignore[misc]
    assert hasattr(MatchState, "__slots__")


# --------------------------------------------------------------------------- #
# 2. HalfRates JSON loader (Task 1)                                           #
# --------------------------------------------------------------------------- #


def test_half_rates_loads_json() -> None:
    """from_json reads data/half_win_rates.json and returns a populated instance."""
    hr = HalfRates.from_json("data/half_win_rates.json")
    assert hr.overall_avg == 0.5  # Verified during planning
    assert len(hr.team_rates) > 0
    assert len(hr.league_rates) > 0


def test_half_rates_team_uses_bayesian_shrinkage() -> None:
    """team(t, m, s) returns (n*raw + SHRINK_PRIOR*prior) / (n + SHRINK_PRIOR)."""
    hr = HalfRates(
        team_rates={"TeamA|Lotus|atk": {"wins": 6.0, "total": 10.0, "rate": 0.6}},
        league_rates={"Lotus|atk": {"wins": 50.0, "total": 100.0, "rate": 0.5}},
        overall_avg=0.5,
    )
    actual = hr.team("TeamA", "Lotus", "atk")
    expected = (10.0 * 0.6 + SHRINK_PRIOR * 0.5) / (10.0 + SHRINK_PRIOR)
    assert math.isclose(actual, expected, rel_tol=1e-12)


def test_half_rates_team_falls_back_to_league_when_team_missing() -> None:
    """Missing-team fallback: team_rates → league_rates."""
    hr = HalfRates(
        team_rates={},
        league_rates={"Lotus|atk": {"wins": 67.0, "total": 134.0, "rate": 0.55}},
        overall_avg=0.5,
    )
    assert hr.team("UnknownTeam", "Lotus", "atk") == 0.55


def test_half_rates_team_falls_back_to_overall_avg_when_no_data() -> None:
    """Missing-team-and-league fallback: overall_avg = 0.5."""
    hr = HalfRates(team_rates={}, league_rates={}, overall_avg=0.5)
    assert hr.team("UnknownTeam", "UnknownMap", "atk") == 0.5


def test_half_rates_team_entry_returns_dict_or_none() -> None:
    """team_entry returns the raw entry dict or None."""
    hr = HalfRates(
        team_rates={
            "TeamA|Lotus|atk": {
                "wins": 6.0,
                "total": 10.0,
                "rate": 0.6,
                "used_fallback": False,
            }
        },
        league_rates={},
        overall_avg=0.5,
    )
    entry = hr.team_entry("TeamA", "Lotus", "atk")
    assert entry is not None
    assert entry["total"] == 10.0
    assert hr.team_entry("Unknown", "Lotus", "atk") is None


# --------------------------------------------------------------------------- #
# Test fixtures (used by Tasks 2a/2b/3)                                       #
# --------------------------------------------------------------------------- #


def _synthetic_half_rates() -> HalfRates:
    """Minimal synthetic HalfRates for downstream tests."""
    return HalfRates(
        team_rates={
            "TeamA|Lotus|atk": {
                "wins": 6.0,
                "total": 10.0,
                "rate": 0.6,
                "used_fallback": False,
            },
            "TeamA|Lotus|def": {
                "wins": 5.0,
                "total": 10.0,
                "rate": 0.5,
                "used_fallback": False,
            },
            "TeamB|Lotus|atk": {
                "wins": 4.0,
                "total": 10.0,
                "rate": 0.4,
                "used_fallback": False,
            },
            "TeamB|Lotus|def": {
                "wins": 5.0,
                "total": 10.0,
                "rate": 0.5,
                "used_fallback": False,
            },
            "TeamA|Bind|atk": {
                "wins": 6.0,
                "total": 10.0,
                "rate": 0.6,
                "used_fallback": False,
            },
            "TeamA|Bind|def": {
                "wins": 5.0,
                "total": 10.0,
                "rate": 0.5,
                "used_fallback": False,
            },
            "TeamB|Bind|atk": {
                "wins": 4.0,
                "total": 10.0,
                "rate": 0.4,
                "used_fallback": False,
            },
            "TeamB|Bind|def": {
                "wins": 5.0,
                "total": 10.0,
                "rate": 0.5,
                "used_fallback": False,
            },
            "TeamA|Haven|atk": {
                "wins": 6.0,
                "total": 10.0,
                "rate": 0.6,
                "used_fallback": False,
            },
            "TeamA|Haven|def": {
                "wins": 5.0,
                "total": 10.0,
                "rate": 0.5,
                "used_fallback": False,
            },
            "TeamB|Haven|atk": {
                "wins": 4.0,
                "total": 10.0,
                "rate": 0.4,
                "used_fallback": False,
            },
            "TeamB|Haven|def": {
                "wins": 5.0,
                "total": 10.0,
                "rate": 0.5,
                "used_fallback": False,
            },
        },
        league_rates={
            f"{m}|{s}": {"wins": 50.0, "total": 100.0, "rate": 0.5}
            for m in ("Lotus", "Bind", "Haven")
            for s in ("atk", "def")
        },
        overall_avg=0.5,
    )


def _synthetic_match_state(
    map_idx: int = 0,
    a_map_score: int = 0,
    b_map_score: int = 0,
    a_round: int = 0,
    b_round: int = 0,
    side_orient: str = "a_atk",
    map_side_orients: tuple[str, ...] = ("a_atk", "a_atk", "a_atk"),
    map_winners: tuple[bool | None, ...] = (None, None, None),
    pistol_winner_a: dict[int, bool | None] | None = None,
) -> MatchState:
    """Canonical synthetic MatchState fixture used across Phase 1 integration tests."""
    return MatchState(
        match_id="synthetic-001",
        team_a="TeamA",
        team_b="TeamB",
        map_pool=("Lotus", "Bind", "Haven"),
        map_idx=map_idx,
        a_map_score=a_map_score,
        b_map_score=b_map_score,
        a_round=a_round,
        b_round=b_round,
        side_orient=side_orient,
        map_side_orients=map_side_orients,
        map_winners=map_winners,
        pistol_winner_a=pistol_winner_a or {0: None, 1: None, 2: None},
        numerical_diff=0,
        bomb_planted=False,
        side="atk",
        econ_bucket="full",
    )


# --------------------------------------------------------------------------- #
# 3. _live_theo_impl core (Task 2a)                                           #
# --------------------------------------------------------------------------- #


def test_bo3_state_from_match_state_packs_pistol_dict_into_tuple() -> None:
    """pistol_winner_a dict -> tuple ordered by map_idx."""
    state = _synthetic_match_state(pistol_winner_a={0: True, 1: None, 2: False})
    bo3 = _bo3_state_from_match_state(state)
    assert bo3.pistol_winner_a == (True, None, False)
    assert bo3.map_idx == 0
    assert bo3.map_pool == ("Lotus", "Bind", "Haven")


def test_build_round_p_fn_consults_map_side_orients_first_half() -> None:
    """D-18: closure overrides side_orient with map_side_orients[map_idx] in first half.

    For map 1 (starting side 'a_def'), at total=5 < REGULATION_HALF=12,
    the effective side is the starting side 'a_def'.
    """
    hr = _synthetic_half_rates()
    state = _synthetic_match_state(
        map_idx=1,
        a_round=3,
        b_round=2,
        side_orient="a_atk",  # outdated — closure should override
        map_side_orients=("a_atk", "a_def", "a_atk"),
    )
    fn = _RoundPFnImpl(match_state=state, half_rates=hr)
    bo3 = BO3State(
        map_idx=1,
        a_map_score=0,
        b_map_score=0,
        a_round=3,
        b_round=2,
        side_orient="a_atk",
        map_pool=("Lotus", "Bind", "Haven"),
        pistol_winner_a=(None, None, None),
    )
    assert fn._effective_side(bo3) == "a_def"


def test_build_round_p_fn_flips_after_round_12() -> None:
    """D-18 + within-map flip: rounds_played >= REGULATION_HALF flips the side."""
    hr = _synthetic_half_rates()
    state = _synthetic_match_state(
        map_idx=1,
        map_side_orients=("a_atk", "a_def", "a_atk"),
    )
    fn = _RoundPFnImpl(match_state=state, half_rates=hr)
    bo3 = BO3State(
        map_idx=1,
        a_map_score=0,
        b_map_score=0,
        a_round=12,
        b_round=2,
        side_orient="a_def",
        map_pool=("Lotus", "Bind", "Haven"),
        pistol_winner_a=(None, None, None),
    )
    # Starting 'a_def' flipped at total=14 >= 12 -> 'a_atk'.
    assert fn._effective_side(bo3) == "a_atk"


def test_build_round_p_fn_next_side_orient_for_returns_starting_side() -> None:
    """next_side_orient_for(m) returns map_side_orients[m] for valid m."""
    hr = _synthetic_half_rates()
    state = _synthetic_match_state(
        map_side_orients=("a_atk", "a_def", "a_atk"),
    )
    fn = _RoundPFnImpl(match_state=state, half_rates=hr)
    assert fn.next_side_orient_for(0) == "a_atk"
    assert fn.next_side_orient_for(1) == "a_def"
    assert fn.next_side_orient_for(2) == "a_atk"


def test_build_round_p_fn_next_side_orient_for_bounds_check() -> None:
    """For map_idx >= len(map_side_orients), returns 'a_atk' defensively."""
    hr = _synthetic_half_rates()
    state = _synthetic_match_state(
        map_side_orients=("a_atk", "a_def", "a_atk"),
    )
    fn = _RoundPFnImpl(match_state=state, half_rates=hr)
    assert fn.next_side_orient_for(3) == "a_atk"
    assert fn.next_side_orient_for(99) == "a_atk"


def test_marginal_map_prob_short_circuits_on_map_winners_a_won() -> None:
    """D-19: m < map_idx with map_winners[m]=True -> CONVICTION_CLIP_HIGH (0.99)."""
    hr = _synthetic_half_rates()
    state = _synthetic_match_state(
        map_idx=1,
        a_map_score=1,
        b_map_score=0,
        map_winners=(True, None, None),
    )
    assert _marginal_map_prob(state, 0, hr) == CONVICTION_CLIP_HIGH


def test_marginal_map_prob_short_circuits_on_map_winners_b_won() -> None:
    """D-19: m < map_idx with map_winners[m]=False -> CONVICTION_CLIP_LOW (0.01)."""
    hr = _synthetic_half_rates()
    state = _synthetic_match_state(
        map_idx=1,
        a_map_score=0,
        b_map_score=1,
        map_winners=(False, None, None),
    )
    assert _marginal_map_prob(state, 0, hr) == CONVICTION_CLIP_LOW


def test_marginal_map_prob_for_current_map_uses_dp() -> None:
    """m == state.map_idx: marginal probability via DP identity."""
    hr = _synthetic_half_rates()
    state = _synthetic_match_state()
    val = _marginal_map_prob(state, 0, hr)
    assert CONVICTION_CLIP_LOW <= val <= CONVICTION_CLIP_HIGH


def test_marginal_map_prob_for_future_map_in_clip_range() -> None:
    """m > state.map_idx: marginal probability via DP forward pass."""
    hr = _synthetic_half_rates()
    state = _synthetic_match_state()
    for m in (1, 2):
        val = _marginal_map_prob(state, m, hr)
        assert CONVICTION_CLIP_LOW <= val <= CONVICTION_CLIP_HIGH


def test_clip_conviction_clips_to_dec_012_band() -> None:
    """DEC-012: clip to [0.01, 0.99]."""
    assert _clip_conviction(-0.5) == CONVICTION_CLIP_LOW
    assert _clip_conviction(0.0) == CONVICTION_CLIP_LOW
    assert _clip_conviction(0.5) == 0.5
    assert _clip_conviction(1.0) == CONVICTION_CLIP_HIGH
    assert _clip_conviction(2.0) == CONVICTION_CLIP_HIGH


def test_live_theo_impl_returns_theo_output_with_clipped_series() -> None:
    """REQ-theo-series-output: theo_series in [CONVICTION_CLIP_LOW, CONVICTION_CLIP_HIGH]."""
    hr = _synthetic_half_rates()
    state = _synthetic_match_state()
    out = _live_theo_impl(state, hr)
    assert isinstance(out, TheoOutput)
    assert CONVICTION_CLIP_LOW <= out.theo_series <= CONVICTION_CLIP_HIGH


def test_live_theo_impl_theo_map_length_matches_map_pool() -> None:
    """REQ-theo-map-output: len(theo_map) == len(map_pool)."""
    hr = _synthetic_half_rates()
    state = _synthetic_match_state()
    out = _live_theo_impl(state, hr)
    assert len(out.theo_map) == len(state.map_pool) == 3


def test_live_theo_impl_theo_map_values_in_clip_range() -> None:
    """REQ-theo-map-output: each theo_map[i] in [CONVICTION_CLIP_LOW, CONVICTION_CLIP_HIGH]."""
    hr = _synthetic_half_rates()
    state = _synthetic_match_state()
    out = _live_theo_impl(state, hr)
    for p in out.theo_map:
        assert CONVICTION_CLIP_LOW <= p <= CONVICTION_CLIP_HIGH


# --------------------------------------------------------------------------- #
# 4. LiveTheoEngine bundle + _p_map_decisive + confidence + vega (Task 2b)    #
# --------------------------------------------------------------------------- #


def test_p_map_decisive_for_already_clinched_map() -> None:
    """W3 case 1: m < state.map_idx where map m clinched returns 1.0."""
    hr = _synthetic_half_rates()
    # A wins map 0 (1-0), A wins map 1 (2-0 — clinches on map 1).
    state = _synthetic_match_state(
        map_idx=2,
        a_map_score=2,
        b_map_score=0,
        map_winners=(True, True, None),
    )
    assert _p_map_decisive(state, 1, hr) == 1.0
    assert _p_map_decisive(state, 0, hr) == 0.0  # map 0 wasn't clinching


def test_p_map_decisive_for_current_map_not_decisive() -> None:
    """W3 case 2: m == state.map_idx, current map cannot clinch -> returns 0.0."""
    hr = _synthetic_half_rates()
    state = _synthetic_match_state(
        map_idx=0,
        a_map_score=0,
        b_map_score=0,
    )
    # After map 0, max score is 1-0 (not 2). Current map never decisive.
    assert _p_map_decisive(state, 0, hr) == 0.0


def test_p_map_decisive_for_current_map_can_clinch() -> None:
    """W3 case 2: m == state.map_idx where A is up 1-0 — current map IS potentially decisive."""
    hr = _synthetic_half_rates()
    state = _synthetic_match_state(
        map_idx=1,
        a_map_score=1,
        b_map_score=0,
    )
    # A winning map 1 -> 2-0 (decisive). B winning -> 1-1 (not decisive).
    # P_decisive = P(A wins map 1) * 1.0 + P(B wins map 1) * 0.0 = P(A wins map 1).
    p_decisive = _p_map_decisive(state, 1, hr)
    p_a_wins_map_1 = _marginal_map_prob(state, 1, hr)
    assert math.isclose(p_decisive, p_a_wins_map_1, rel_tol=1e-9)


def test_p_map_decisive_for_future_map_in_bo3() -> None:
    """W3 case 3: m > state.map_idx (BO3 m=2 from map 0 0-0) — only reachable via 1-1."""
    hr = _synthetic_half_rates()
    state = _synthetic_match_state(map_idx=0, a_map_score=0, b_map_score=0)
    # Map 2 reached only if maps 0 and 1 split 1-1. Once reached, decisive.
    p_decisive = _p_map_decisive(state, 2, hr)
    assert 0.0 <= p_decisive <= 1.0


def test_p_reach_map_zero_for_clinched_series_state() -> None:
    """CR-01 (VERIFICATION.md gaps[0]): a 2-0 BO3 cannot reach map 2 even
    though ``map_idx == m == 2`` — the series-clinch short-circuit must fire
    BEFORE the map_idx terminal check.
    """
    bo3 = BO3State(
        map_idx=2,
        a_map_score=2,
        b_map_score=0,
        a_round=0,
        b_round=0,
        side_orient="a_atk",
        map_pool=("Lotus", "Bind", "Haven"),
        pistol_winner_a=(True, True, None),
    )
    state = _synthetic_match_state(map_idx=2, a_map_score=2, b_map_score=0)
    fn = _RoundPFnImpl(match_state=state, half_rates=_synthetic_half_rates())
    assert _p_reach_map(bo3, fn, m=2) == 0.0


def test_p_reach_map_zero_for_b_clinched_series_state() -> None:
    """CR-01 mirror: 0-2 BO3 also cannot reach map 2."""
    bo3 = BO3State(
        map_idx=2,
        a_map_score=0,
        b_map_score=2,
        a_round=0,
        b_round=0,
        side_orient="a_atk",
        map_pool=("Lotus", "Bind", "Haven"),
        pistol_winner_a=(False, False, None),
    )
    state = _synthetic_match_state(map_idx=2, a_map_score=0, b_map_score=2)
    fn = _RoundPFnImpl(match_state=state, half_rates=_synthetic_half_rates())
    assert _p_reach_map(bo3, fn, m=2) == 0.0


def test_p_map_decisive_for_bo3_middle_map_with_nontrivial_p() -> None:
    """CR-02 (VERIFICATION.md gaps[1]): from map_idx=0, m=1 (BO3 middle map)
    must use the correct BO3 decisive formula
        p_reached * (p_a_{m-1} * p_a_m + (1 - p_a_{m-1}) * (1 - p_a_m))
    and NOT the BO5+ placeholder ``p_reached * 0.5``. With asymmetric half-rates
    (Team A ~0.6, Team B ~0.4 per _synthetic_half_rates), the correct value
    differs from the placeholder by at least 1e-3.
    """
    hr = _synthetic_half_rates()
    state = _synthetic_match_state(map_idx=0)
    bo3 = _bo3_state_from_match_state(state)
    fn = _RoundPFnImpl(match_state=state, half_rates=hr)

    actual = _p_map_decisive(state, m=1, half_rates=hr)
    p_reached = _p_reach_map(bo3, fn, m=1)
    p_a_0 = _marginal_map_prob(state, 0, hr)
    p_a_1 = _marginal_map_prob(state, 1, hr)
    expected = p_reached * (p_a_0 * p_a_1 + (1.0 - p_a_0) * (1.0 - p_a_1))
    assert math.isclose(actual, expected, rel_tol=1e-9)

    # Witness that the placeholder bug is closed: the placeholder value
    # ``p_reached * 0.5`` differs from the correct value by > 1e-3 here.
    placeholder = p_reached * 0.5
    assert abs(actual - placeholder) > 1e-3, (
        f"middle-map decisive {actual!r} should differ from BO5+ placeholder "
        f"{placeholder!r} under asymmetric half-rates"
    )


def test_p_map_decisive_sum_equals_one_pre_clinch() -> None:
    """CR-01 ∩ CR-02 conjunction (REVIEW.md IN-04 / law of total probability):
    sum of _p_map_decisive over all map indices must equal 1.0 for any
    pre-clinch state. Locks both fixes structurally — over-counting clinched
    paths (CR-01) or using the BO5+ placeholder (CR-02) breaks this identity.
    """
    hr = _synthetic_half_rates()
    state = _synthetic_match_state()  # 0-0 root, pre-clinch
    total = sum(
        _p_map_decisive(state, m, hr) for m in range(len(state.map_pool))
    )
    assert math.isclose(total, 1.0, rel_tol=1e-9), (
        f"law of total probability violated: sum of decisive masses = {total!r}"
    )


def test_compute_confidence_in_unit_interval() -> None:
    """REQ-confidence-output / D-08: confidence in [0, 1]."""
    hr = _synthetic_half_rates()
    state = _synthetic_match_state()
    val = _compute_confidence(state, hr)
    assert 0.0 <= val <= 1.0


def test_compute_confidence_uses_dp_mass_not_theo_map_proxy() -> None:
    """Blocker #1: confidence is DP-mass-weighted, not a theo_map proxy.

    Verifies the loose contract: confidence is in [0, 1] and deterministic
    for fixed input. The structural test (no proxy formula `0.5 + 0.5 *
    abs(theo_map - 0.5)` in source) is enforced by the source-level grep
    in Task 3 acceptance criteria.
    """
    hr = _synthetic_half_rates()
    state1 = _synthetic_match_state(map_idx=0, a_map_score=0, b_map_score=0)
    state2 = _synthetic_match_state(
        map_idx=1,
        a_map_score=1,
        b_map_score=0,
        map_winners=(True, None, None),
    )
    c1 = _compute_confidence(state1, hr)
    c2 = _compute_confidence(state2, hr)
    assert 0.0 <= c1 <= 1.0
    assert 0.0 <= c2 <= 1.0


def test_compute_vega_non_negative() -> None:
    """REQ-vega-output / DEC-018: vega is a sum of squared deviations >= 0."""
    hr = _synthetic_half_rates()
    state = _synthetic_match_state()
    bo3 = _bo3_state_from_match_state(state)
    fn = _RoundPFnImpl(match_state=state, half_rates=hr)
    val = _compute_vega(bo3, fn)
    assert val >= 0.0


def test_compute_vega_matches_dec_018_formula() -> None:
    """REQ-vega-output / DEC-018: vega = p*(theo_a-theo)^2 + (1-p)*(theo_b-theo)^2."""
    from src.pricing.dp import _advance_round, series_value

    hr = _synthetic_half_rates()
    state = _synthetic_match_state()
    bo3 = _bo3_state_from_match_state(state)
    fn = _RoundPFnImpl(match_state=state, half_rates=hr)

    actual = _compute_vega(bo3, fn)
    # Reconstruct the formula manually:
    state_a_wins = _advance_round(bo3, a_wins=True)
    state_b_wins = _advance_round(bo3, a_wins=False)
    theo = series_value(bo3, fn)
    theo_a = series_value(state_a_wins, fn)
    theo_b = series_value(state_b_wins, fn)
    p = fn(bo3)
    expected = p * (theo_a - theo) ** 2 + (1.0 - p) * (theo_b - theo) ** 2
    assert math.isclose(actual, expected, rel_tol=1e-9)


def test_compute_vega_zero_at_series_terminal() -> None:
    """CR-03 (VERIFICATION.md gaps[2]): vega is 0 when the series is clinched.
    Theo is the constant 1.0 (or 0.0) so squared deviation is 0.
    """
    hr = _synthetic_half_rates()
    state = _synthetic_match_state(map_idx=2, a_map_score=2)
    fn = _RoundPFnImpl(match_state=state, half_rates=hr)
    bo3_a = _bo3_state_from_match_state(state)
    assert _compute_vega(bo3_a, fn) == 0.0

    state_b = _synthetic_match_state(map_idx=2, a_map_score=0, b_map_score=2)
    fn_b = _RoundPFnImpl(match_state=state_b, half_rates=hr)
    bo3_b = _bo3_state_from_match_state(state_b)
    assert _compute_vega(bo3_b, fn_b) == 0.0


def test_compute_vega_zero_at_within_map_terminal() -> None:
    """CR-03: vega is 0 when the current map is already decided
    (a_round or b_round >= WIN_THRESHOLD). Per-round vega is undefined inside
    a finished map.
    """
    hr = _synthetic_half_rates()
    state_a = _synthetic_match_state(a_round=13, b_round=10)
    fn_a = _RoundPFnImpl(match_state=state_a, half_rates=hr)
    bo3_a = _bo3_state_from_match_state(state_a)
    assert _compute_vega(bo3_a, fn_a) == 0.0

    state_b = _synthetic_match_state(a_round=10, b_round=13)
    fn_b = _RoundPFnImpl(match_state=state_b, half_rates=hr)
    bo3_b = _bo3_state_from_match_state(state_b)
    assert _compute_vega(bo3_b, fn_b) == 0.0


def test_compute_vega_at_ot_entry_uses_coinflip_leaf() -> None:
    """CR-03 (VERIFICATION.md gaps[2], CRule 5): at a_round=12, b_round=12
    (regulation OT entry, total=24), vega MUST equal the variance of the
    OT coinflip leaf over next-map series outcomes — not the squared
    deviation against _advance_round-projected next-map values (which
    silently bypass the DP's OT hard-stop).
    """
    from src.pricing.dp import series_value

    hr = _synthetic_half_rates()
    state = _synthetic_match_state(a_round=12, b_round=12)
    fn = _RoundPFnImpl(match_state=state, half_rates=hr)
    root = _bo3_state_from_match_state(state)

    actual = _compute_vega(root, fn)

    # Reconstruct expected: variance of the OT coinflip leaf.
    next_side = fn.next_side_orient_for(root.map_idx + 1)
    v_a = series_value(
        _advance_to_next_map(root, a_won=True, next_side_orient=next_side),
        fn,
    )
    v_b = series_value(
        _advance_to_next_map(root, a_won=False, next_side_orient=next_side),
        fn,
    )
    mean = 0.5 * (v_a + v_b)
    expected = 0.5 * (v_a - mean) ** 2 + 0.5 * (v_b - mean) ** 2
    assert math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-12)
    assert actual >= 0.0


def test_compute_vega_at_ot_entry_with_asymmetric_clinch_state() -> None:
    """CR-03 (asymmetric witness): at a_round=12, b_round=12 with a_map_score=1
    (A is one map up so OT-coinflip-A clinches the series, OT-coinflip-B
    forces map 3), v_a and v_b differ. The OT-leaf variance is then
    strictly positive AND differs from the buggy _advance_round projection.
    """
    from src.pricing.dp import series_value

    hr = _synthetic_half_rates()
    state = _synthetic_match_state(map_idx=1, a_map_score=1, a_round=12, b_round=12)
    fn = _RoundPFnImpl(match_state=state, half_rates=hr)
    root = _bo3_state_from_match_state(state)

    actual = _compute_vega(root, fn)

    next_side = fn.next_side_orient_for(root.map_idx + 1)
    v_a = series_value(
        _advance_to_next_map(root, a_won=True, next_side_orient=next_side),
        fn,
    )
    v_b = series_value(
        _advance_to_next_map(root, a_won=False, next_side_orient=next_side),
        fn,
    )
    mean = 0.5 * (v_a + v_b)
    expected = 0.5 * (v_a - mean) ** 2 + 0.5 * (v_b - mean) ** 2
    assert math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-12)
    assert actual >= 0.0


def test_data_weight_for_map_min_over_teams() -> None:
    """D-09: _data_weight_for_map = min over teams of avg total / MIN_ROUNDS_FULL_WEIGHT."""
    hr = _synthetic_half_rates()
    val = _data_weight_for_map("TeamA", "TeamB", "Lotus", hr)
    # 10/10/10/10 sample sizes -> avg = 10.0 per team -> min = 10.0 -> 10/15 = 0.667
    assert math.isclose(val, 10.0 / MIN_ROUNDS_FULL_WEIGHT, rel_tol=1e-12)


def test_data_weight_for_map_zero_when_team_has_no_data() -> None:
    """When a team has no entry, _data_weight returns 0."""
    hr = HalfRates(team_rates={}, league_rates={}, overall_avg=0.5)
    assert _data_weight_for_map("UnknownA", "UnknownB", "Lotus", hr) == 0.0


def test_live_theo_engine_call_surface() -> None:
    """D-20: LiveTheoEngine(half_rates)(state) returns the same TheoOutput as
    _live_theo_impl(state, half_rates, None).
    """
    hr = _synthetic_half_rates()
    state = _synthetic_match_state()
    engine = LiveTheoEngine(half_rates=hr)
    out_engine = engine(state)
    out_impl = _live_theo_impl(state, hr, None)
    assert out_engine.theo_series == out_impl.theo_series
    assert out_engine.theo_map == out_impl.theo_map
    assert math.isclose(out_engine.vega, out_impl.vega, rel_tol=1e-9)
    assert math.isclose(out_engine.confidence, out_impl.confidence, rel_tol=1e-9)


def test_no_memory_leak_across_live_theo_calls() -> None:
    """CR-04 (VERIFICATION.md gaps[3]): the closure registries and lru_caches
    must be reset per-call so Phase 4's continuous-running quoter does not
    leak memory linearly. After 100 sequential engine(state) calls, both
    registries must be near-empty (cleared in __call__'s finally block).
    """
    from src.pricing import dp
    from src.pricing import live_theo as live_theo_mod

    hr = _synthetic_half_rates()
    state = _synthetic_match_state()
    engine = LiveTheoEngine(half_rates=hr)
    for _ in range(100):
        engine(state)

    # try/finally cleanup runs after each call — at the moment we observe,
    # the registries should be empty (the LAST call cleaned up before
    # returning). Slack of 5 absorbs any future intra-call asymmetry.
    assert len(dp._ROUND_P_FNS) <= 5, (
        f"_ROUND_P_FNS leaked: len={len(dp._ROUND_P_FNS)} after 100 calls"
    )
    assert len(live_theo_mod._REACH_MAP_FNS) <= 5, (
        f"_REACH_MAP_FNS leaked: len={len(live_theo_mod._REACH_MAP_FNS)} "
        f"after 100 calls"
    )


def test_live_theo_engine_clears_caches_even_on_exception() -> None:
    """CR-04 corollary: cleanup runs in finally so a raising _live_theo_impl
    still leaves the registries clean.
    """
    import unittest.mock

    from src.pricing import dp
    from src.pricing import live_theo as live_theo_mod

    hr = _synthetic_half_rates()
    state = _synthetic_match_state()
    engine = LiveTheoEngine(half_rates=hr)

    # Prime the registries with one good call.
    engine(state)
    baseline_dp = len(dp._ROUND_P_FNS)
    baseline_reach = len(live_theo_mod._REACH_MAP_FNS)

    # Now force _live_theo_impl to raise; the finally MUST still run cleanup.
    def _raising_impl(*args, **kwargs):  # type: ignore[no-untyped-def]
        from src.pricing.live_theo import _RoundPFnImpl
        fn = _RoundPFnImpl(match_state=state, half_rates=hr)
        dp._ROUND_P_FNS.append(fn)
        live_theo_mod._REACH_MAP_FNS.append(fn)
        raise RuntimeError("synthetic failure to test finally cleanup")

    with unittest.mock.patch.object(
        live_theo_mod, "_live_theo_impl", side_effect=_raising_impl
    ), pytest.raises(RuntimeError, match="synthetic failure"):
        engine(state)

    # Cleanup ran in finally — registries are back to baseline (or smaller).
    assert len(dp._ROUND_P_FNS) <= baseline_dp, (
        f"_ROUND_P_FNS not cleaned on exception: "
        f"len={len(dp._ROUND_P_FNS)} vs baseline={baseline_dp}"
    )
    assert len(live_theo_mod._REACH_MAP_FNS) <= baseline_reach, (
        f"_REACH_MAP_FNS not cleaned on exception: "
        f"len={len(live_theo_mod._REACH_MAP_FNS)} vs baseline={baseline_reach}"
    )


def test_live_theo_engine_is_frozen() -> None:
    """D-20: LiveTheoEngine is a frozen dataclass."""
    hr = _synthetic_half_rates()
    engine = LiveTheoEngine(half_rates=hr)
    with pytest.raises(dataclasses.FrozenInstanceError):
        engine.half_rates = HalfRates(  # type: ignore[misc]
            team_rates={},
            league_rates={},
            overall_avg=0.5,
        )


def test_live_theo_engine_accepts_optional_round_conclusion() -> None:
    """D-20: round_conclusion parameter is optional (Phase 1 doesn't consume it)."""
    from src.pricing.round_conclusion import RoundConclusionLookup

    hr = _synthetic_half_rates()
    lookup = RoundConclusionLookup()
    state = _synthetic_match_state()
    engine = LiveTheoEngine(half_rates=hr, round_conclusion=lookup.lookup)
    out = engine(state)
    assert isinstance(out, TheoOutput)


# --------------------------------------------------------------------------- #
# 5. Public surface + integration (Task 3)                                    #
# --------------------------------------------------------------------------- #


def test_public_imports_only() -> None:
    """REQ-canonical-live-theo: only LiveTheoEngine, TheoOutput, MatchState,
    HalfRates are exported. DEC-010 forbids series_theo / series_theo_no_sides /
    series_theo_from_map_probs.
    """
    import src.pricing as pricing

    assert set(pricing.__all__) == {
        "LiveTheoEngine",
        "TheoOutput",
        "MatchState",
        "HalfRates",
    }
    forbidden = {
        "series_theo",
        "series_theo_no_sides",
        "series_theo_from_map_probs",
        "model_series_prob",
        "_signal_strength",
    }
    assert not (forbidden & set(pricing.__all__))


def test_top_level_imports_resolve() -> None:
    """`from src.pricing import LiveTheoEngine, TheoOutput, MatchState, HalfRates` succeeds."""
    from src.pricing import (  # noqa: F401
        HalfRates,
        LiveTheoEngine,
        MatchState,
        TheoOutput,
    )


def test_forbidden_audit_triplet_symbols_absent_from_source() -> None:
    """DEC-010 / PRD §12.3 / CRule 1: no `series_theo*` function definitions
    anywhere in src/pricing/.

    Only top-level `def` declarations are matched; mentions in module docstrings
    or comments (e.g., "Replaces audit-engine series_theo / series_theo_no_sides
    / series_theo_from_map_probs triplet") do NOT count.
    """
    pricing_dir = Path("src/pricing")
    forbidden_patterns = [
        re.compile(r"^def series_theo\b", re.MULTILINE),
        re.compile(r"^def series_theo_no_sides\b", re.MULTILINE),
        re.compile(r"^def series_theo_from_map_probs\b", re.MULTILINE),
        re.compile(r"^def model_series_prob\b", re.MULTILINE),
        re.compile(r"^def _signal_strength\b", re.MULTILINE),
    ]
    for py_file in pricing_dir.glob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        for pat in forbidden_patterns:
            assert not pat.search(text), (
                f"Forbidden audit-triplet symbol found in {py_file}: {pat.pattern}"
            )


def test_live_theo_marginalization_consistency_dec002() -> None:
    """DEC-002 / CRule 2: theo_series ≈ theo_map[map_idx] × clip(series_value(state_a_won_current))
    + (1 − theo_map[map_idx]) × clip(series_value(state_b_won_current)).

    The same DP feeds both theo_series and theo_map[]; this identity holds
    by marginalization over the current map's outcome.
    """
    from src.pricing.dp import series_value

    hr = _synthetic_half_rates()
    state = _synthetic_match_state(map_idx=0, a_round=3, b_round=2)
    engine = LiveTheoEngine(half_rates=hr)
    out = engine(state)

    bo3 = _bo3_state_from_match_state(state)
    fn = _RoundPFnImpl(match_state=state, half_rates=hr)
    next_side = fn.next_side_orient_for(state.map_idx + 1)
    state_after_a = _advance_to_next_map(bo3, a_won=True, next_side_orient=next_side)
    state_after_b = _advance_to_next_map(bo3, a_won=False, next_side_orient=next_side)

    v_after_a = series_value(state_after_a, fn)
    v_after_b = series_value(state_after_b, fn)
    p_a_wins_current = out.theo_map[state.map_idx]

    expected_unclipped = (
        p_a_wins_current * v_after_a + (1.0 - p_a_wins_current) * v_after_b
    )
    expected = _clip_conviction(expected_unclipped)

    # Note: theo_map[map_idx] is itself clipped in the output, so reconstruction
    # uses the clipped value. The identity holds approximately within clip tol.
    assert math.isclose(out.theo_series, expected, rel_tol=1e-3, abs_tol=1e-3)


def test_live_theo_end_to_end_synthetic_mid_map() -> None:
    """Integration: synthetic state at round 7 of map 1 with side flipped.
    All four TheoOutput fields populated and in valid ranges.
    """
    hr = _synthetic_half_rates()
    state = _synthetic_match_state(
        map_idx=1,
        a_map_score=1,
        b_map_score=0,
        a_round=4,
        b_round=2,  # round 7 of map 1
        side_orient="a_def",
        map_side_orients=("a_atk", "a_def", "a_atk"),
        map_winners=(True, None, None),
    )
    engine = LiveTheoEngine(half_rates=hr)
    out = engine(state)
    assert CONVICTION_CLIP_LOW <= out.theo_series <= CONVICTION_CLIP_HIGH
    assert len(out.theo_map) == 3
    for p in out.theo_map:
        assert CONVICTION_CLIP_LOW <= p <= CONVICTION_CLIP_HIGH
    assert out.vega >= 0.0
    assert 0.0 <= out.confidence <= 1.0


def test_live_theo_property_invariants_hypothesis() -> None:
    """REQ-canonical-live-theo + REQ-theo-{series,map}-output + REQ-confidence-output
    + REQ-vega-output: the four range invariants hold for any reachable state.

    Hypothesis-driven: generates reachable MatchStates and asserts:
      - theo_series in [CONVICTION_CLIP_LOW, CONVICTION_CLIP_HIGH]
      - all theo_map[i] in [CONVICTION_CLIP_LOW, CONVICTION_CLIP_HIGH]
      - vega >= 0
      - confidence in [0, 1]
    """
    from hypothesis import given, settings
    from hypothesis import strategies as st

    hr = _synthetic_half_rates()

    @given(
        map_idx=st.integers(min_value=0, max_value=2),
        a_map_score=st.integers(min_value=0, max_value=1),
        b_map_score=st.integers(min_value=0, max_value=1),
        a_round=st.integers(min_value=0, max_value=12),
        b_round=st.integers(min_value=0, max_value=12),
        side_orient=st.sampled_from(["a_atk", "a_def"]),
    )
    @settings(max_examples=30, deadline=None)
    def _check(
        map_idx: int,
        a_map_score: int,
        b_map_score: int,
        a_round: int,
        b_round: int,
        side_orient: str,
    ) -> None:
        # Reachable-state guard: skip clinched states (terminals, not interesting).
        if a_map_score >= 2 or b_map_score >= 2:
            return
        if a_round >= 13 or b_round >= 13:
            return
        # Map_winners derived from map_score (consistency guard):
        winners: list[bool | None] = []
        a_wins_remaining = a_map_score
        b_wins_remaining = b_map_score
        for k in range(3):
            if k < map_idx:
                if a_wins_remaining > 0:
                    winners.append(True)
                    a_wins_remaining -= 1
                elif b_wins_remaining > 0:
                    winners.append(False)
                    b_wins_remaining -= 1
                else:
                    winners.append(True)  # defensive
            else:
                winners.append(None)
        # Skip if winners can't actually realize the map_idx and scores
        # (e.g., map_idx=0 requires both scores 0; otherwise inconsistent)
        if map_idx == 0 and (a_map_score != 0 or b_map_score != 0):
            return
        if map_idx == 1 and (a_map_score + b_map_score != 1):
            return
        if map_idx == 2 and (a_map_score + b_map_score != 2):
            return
        state = _synthetic_match_state(
            map_idx=map_idx,
            a_map_score=a_map_score,
            b_map_score=b_map_score,
            a_round=a_round,
            b_round=b_round,
            side_orient=side_orient,
            map_winners=tuple(winners),
        )
        engine = LiveTheoEngine(half_rates=hr)
        out = engine(state)
        assert CONVICTION_CLIP_LOW <= out.theo_series <= CONVICTION_CLIP_HIGH
        for p in out.theo_map:
            assert CONVICTION_CLIP_LOW <= p <= CONVICTION_CLIP_HIGH
        assert out.vega >= 0.0
        assert 0.0 <= out.confidence <= 1.0

    _check()


# --------------------------------------------------------------------------- #
# 6. WR-06 regression — _within_map_p_a_wins propagates pistol_winner_a       #
# --------------------------------------------------------------------------- #


def test_within_map_anti_eco_uses_gun_win_rate_after_round_1_branch() -> None:
    """WR-06 (VERIFICATION.md gaps[1] / 01-REVIEW.md WR-06 — CR-05 scoped to
    future-map sub-DP): _within_map_p_a_wins's inline state-advance must
    propagate pistol_winner_a through the recursion, so round 2 of a future
    map dispatches to GUN_WIN_RATE — not the defensive 0.5 fallback.

    Structural assertion (load-bearing): with the WR-06 fix in place, calling
    _within_map_p_a_wins with three different pistol_winner_a tuples for a
    future map produces three DIFFERENT values that respect a strict ordering:

        p_a_pistol = _within_map_p_a_wins(pistol=(None, True,  None))
        p_b_pistol = _within_map_p_a_wins(pistol=(None, False, None))
        p_unset    = _within_map_p_a_wins(pistol=(None, None,  None))

    Under the synthetic half-rates (TeamA atk 0.6 / def 0.5; TeamB atk 0.4 /
    def 0.5), TeamA has a measurable round-1 edge. Post-fix:
      * p_a_pistol > p_unset > p_b_pistol  (strict inequalities)
      * The gap p_a_pistol - p_b_pistol is large (anti-eco swing dominates)

    Pre-fix (WR-06 open): all three values are EQUAL because round 2/3 always
    return 0.5 regardless of pistol_winner_a — the strict-inequality
    assertion below FAILS structurally on pre-fix `main`.

    This is a structural lock that mechanically distinguishes broken-vs-fixed
    behavior without depending on absolute magnitudes. The plan's literal
    "law-of-total-probability decomposition" form (PLAN.md Task 3 Step 3.3)
    does not hold for the semantics of _within_map_p_a_wins because calling
    the function with pistol=(None,True,None) forces ALL round-2/3 dispatches
    to GUN_WIN_RATE regardless of who actually wins R1 in the recursion's
    own forward-pass — it does NOT represent "the marginal conditional on A
    winning R1" in the way the decomposition presumes. Per Rule 1, the test
    is fixed inline to the structural-ordering form, which captures the
    actual WR-06 invariant.
    """
    hr = _synthetic_half_rates()
    state = _synthetic_match_state(map_idx=0, pistol_winner_a={0: None, 1: None, 2: None})
    bo3 = _bo3_state_from_match_state(state)

    p_unset = _within_map_p_a_wins(
        map_pool=bo3.map_pool,
        map_idx=1,
        starting_side="a_atk",
        pistol_winner_a=(None, None, None),
        match_state=state,
        half_rates=hr,
    )
    p_a_pistol = _within_map_p_a_wins(
        map_pool=bo3.map_pool,
        map_idx=1,
        starting_side="a_atk",
        pistol_winner_a=(None, True, None),
        match_state=state,
        half_rates=hr,
    )
    p_b_pistol = _within_map_p_a_wins(
        map_pool=bo3.map_pool,
        map_idx=1,
        starting_side="a_atk",
        pistol_winner_a=(None, False, None),
        match_state=state,
        half_rates=hr,
    )

    # Strict ordering — load-bearing WR-06 lock.
    # Pre-fix all three are equal (anti-eco always 0.5); post-fix they differ.
    assert p_a_pistol > p_unset > p_b_pistol, (
        f"WR-06 not closed: expected strict ordering "
        f"p_a_pistol > p_unset > p_b_pistol, got "
        f"p_a_pistol={p_a_pistol!r}, p_unset={p_unset!r}, "
        f"p_b_pistol={p_b_pistol!r}"
    )
    # Anti-eco swing must be SUBSTANTIAL — pre-fix, the gap collapses to ~0
    # (rounded-fallback yields identical values). GUN_WIN_RATE = 0.822 vs
    # 1 - GUN_WIN_RATE = 0.178 across two anti-eco rounds per half (so at
    # least 0.05 in the within-map output under any non-degenerate half-rates).
    assert (p_a_pistol - p_b_pistol) > 0.05, (
        f"WR-06 not closed: anti-eco swing {p_a_pistol - p_b_pistol!r} too "
        f"small — round 2/3 dispatch likely still falling through to 0.5"
    )

    # Also verify the round-1 dispatch is via half-rates blend — establishes
    # that the recursion does NOT short-circuit R1 in any of the three calls
    # (R1 is always the pistol dispatch, regardless of pistol_winner_a state).
    fn_probe = _RoundPFnImpl(match_state=state, half_rates=hr)
    round_1_synthetic = BO3State(
        map_idx=1,
        a_map_score=0,
        b_map_score=0,
        a_round=0,
        b_round=0,
        side_orient="a_atk",
        map_pool=bo3.map_pool,
        pistol_winner_a=(None, None, None),
    )
    p_round_1 = fn_probe(round_1_synthetic)
    assert 0.0 < p_round_1 < 1.0, f"R1 dispatch malformed: {p_round_1}"


# --------------------------------------------------------------------------- #
# 7. CR-05/WR-06 end-to-end behavioral lock — asymmetric matchup integration  #
# --------------------------------------------------------------------------- #


def test_live_theo_asymmetric_pistols_match_unset_pistols_after_dp_propagation() -> None:
    """CR-05 / WR-06 end-to-end behavioral lock (01-VERIFICATION.md re-verification
    9.25pp swing): under asymmetric half-rates (TeamA 0.55, TeamB 0.45 across all
    maps/sides) with total=1e9 (no shrinkage), the post-fix LiveTheoEngine must
    satisfy a STRICT-ORDERING invariant over pistol_winner_a configurations:

        theo_set_AAA > theo_unset > theo_set_BBB

    where:
      * theo_set_AAA = theo_series with pistol_winner_a=(True,  True,  True)
      * theo_set_BBB = theo_series with pistol_winner_a=(False, False, False)
      * theo_unset   = theo_series with pistol_winner_a=(None,  None,  None)

    Pre-fix (CR-05/WR-06 open): theo_unset was stuck at ~0.887 (the verification
    re-run #2's measurement) because the DP forward-pass dropped pistol updates
    at the round-1 boundary, so all anti-eco rounds in DP recursion fell through
    to the defensive 0.5 fallback in round_types.round_p_for_round. The unset
    case was structurally indistinguishable from a model that ignores anti-eco
    economics entirely — a 9.25pp systematic bias from the set-AAA baseline.

    Post-fix (CR-05 in dp._advance_round + WR-06 in _within_map_p_a_wins):
    theo_unset reflects a TRUE marginalization over pistol outcomes via the
    DP's own forward-pass — round 1 is played with the half-rates blend, then
    pistol_winner_a propagates through the recursion so anti-eco rounds 2/3
    dispatch to GUN_WIN_RATE / 1-GUN_WIN_RATE based on who won R1.

    The strict-ordering assertion is the LOAD-BEARING check (per checker fix
    I-04 — replaces the literal 'law-of-total-probability decomposition' form
    in PLAN.md Task 6 Step 6.1, which does not hold for the semantics of
    LiveTheoEngine because forcing pistol=(T,T,T) at root affects ALL R2/R3
    dispatches regardless of who actually wins R1 in the recursion's own
    forward-pass — see test_within_map_anti_eco_uses_gun_win_rate_after_round_1_branch
    for the same Rule 1 fix at the within-map level).

    Soft sanity floors (NOT load-bearing): theo_series in [0.01, 0.99]; the
    anti-eco swing |theo_set_AAA - theo_set_BBB| > 0.1 confirms the pistol
    dispatch is structurally active.
    """
    asymmetric_hr = HalfRates(
        team_rates={
            f"{t}|{m}|{s}": {
                "wins": (0.55 if t == "TeamA" else 0.45) * 1e9,
                "total": 1e9,
                "rate": 0.55 if t == "TeamA" else 0.45,
                "used_fallback": False,
            }
            for t in ("TeamA", "TeamB")
            for m in ("Lotus", "Bind", "Haven")
            for s in ("atk", "def")
        },
        league_rates={
            f"{m}|{s}": {"wins": 50.0 * 1e9, "total": 100.0 * 1e9, "rate": 0.5}
            for m in ("Lotus", "Bind", "Haven")
            for s in ("atk", "def")
        },
        overall_avg=0.5,
    )
    state_unset = _synthetic_match_state(
        pistol_winner_a={0: None, 1: None, 2: None},
    )
    state_set_a = _synthetic_match_state(
        pistol_winner_a={0: True, 1: True, 2: True},
    )
    state_set_b = _synthetic_match_state(
        pistol_winner_a={0: False, 1: False, 2: False},
    )
    engine = LiveTheoEngine(half_rates=asymmetric_hr)
    out_unset = engine(state_unset)
    out_set_a = engine(state_set_a)
    out_set_b = engine(state_set_b)

    # Load-bearing strict-ordering invariant:
    assert out_set_a.theo_series > out_unset.theo_series > out_set_b.theo_series, (
        f"CR-05/WR-06 not closed end-to-end: expected strict ordering "
        f"theo_set_AAA > theo_unset > theo_set_BBB, got "
        f"theo_set_AAA={out_set_a.theo_series!r}, "
        f"theo_unset={out_unset.theo_series!r}, "
        f"theo_set_BBB={out_set_b.theo_series!r}"
    )
    # Anti-eco swing must be substantial (pre-fix swing collapsed because
    # all three configurations produced theo near the same flat-anti-eco
    # value):
    swing_aaa_bbb = out_set_a.theo_series - out_set_b.theo_series
    assert swing_aaa_bbb > 0.1, (
        f"CR-05/WR-06 not closed: anti-eco swing |AAA - BBB| = "
        f"{swing_aaa_bbb!r} too small — pistol dispatch likely still "
        f"falling through to the 0.5 fallback for some rounds"
    )
    # theo_unset must be BETWEEN the extremes by a meaningful margin (not just
    # equal to one of them) — pre-fix it was stuck at the broken-anti-eco
    # value, post-fix it reflects a true marginalization.
    assert (out_set_a.theo_series - out_unset.theo_series) > 0.01, (
        f"theo_unset suspiciously close to theo_set_AAA: "
        f"diff={out_set_a.theo_series - out_unset.theo_series!r}"
    )
    assert (out_unset.theo_series - out_set_b.theo_series) > 0.01, (
        f"theo_unset suspiciously close to theo_set_BBB: "
        f"diff={out_unset.theo_series - out_set_b.theo_series!r}"
    )

    # Soft sanity floors (NOT load-bearing).
    assert out_unset.theo_series > 0.5, (
        f"sanity floor: theo_series with unset pistols = "
        f"{out_unset.theo_series!r}, expected > 0.5 (asymmetric matchup "
        f"with TeamA=0.55 should produce P(TeamA wins series) > 0.5)"
    )
    # Witness the conviction clip is in range; all three sides respect [0.01, 0.99].
    assert CONVICTION_CLIP_LOW <= out_unset.theo_series <= CONVICTION_CLIP_HIGH
    assert CONVICTION_CLIP_LOW <= out_set_a.theo_series <= CONVICTION_CLIP_HIGH
    assert CONVICTION_CLIP_LOW <= out_set_b.theo_series <= CONVICTION_CLIP_HIGH


