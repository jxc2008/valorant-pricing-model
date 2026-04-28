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

import pytest

from src.config.constants import SHRINK_PRIOR
from src.pricing.data import HalfRates, MatchState, TheoOutput

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
