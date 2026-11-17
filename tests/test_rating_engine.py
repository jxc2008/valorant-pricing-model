"""Rating engine (research) — invariants the evaluation relies on."""
from __future__ import annotations

import pytest

from src.rating.dp_table import MapTable, dp_map_p
from src.rating.engine import Engine, EngineParams, Team

A = Team(1, (1, 2, 3, 4, 5), "emea")
B = Team(2, (6, 7, 8, 9, 10), "emea")
C = Team(3, (11, 12, 13, 14, 15), "pacific")


def test_fresh_engine_is_symmetric() -> None:
    e = Engine()
    d, _, _, _ = e.predict_map(A, B, "Ascent", 0.0, 2024)
    assert d == pytest.approx(0.0)


def test_winner_rating_rises_and_loser_falls() -> None:
    e = Engine()
    e.update_map(A, B, "Ascent", 0.0, 2024, a_atk=(9, 12), a_def=(4, 6))  # A won 13-5
    d, _, _, _ = e.predict_map(A, B, "Ascent", 1.0, 2024)
    assert d > 0
    assert e.players[1].mu > 0 > e.players[6].mu
    d2, _, _, _ = e.predict_map(B, A, "Ascent", 1.0, 2024)
    assert d2 == pytest.approx(-d)


def test_same_region_offset_cancels_cross_region_moves() -> None:
    e = Engine()
    e.update_map(A, B, "Bind", 0.0, 2024, a_atk=(8, 12), a_def=(5, 12))
    assert "emea" not in e.regions or e.regions["emea"].mu == pytest.approx(0.0)
    e.update_map(A, C, "Bind", 1.0, 2024, a_atk=(9, 12), a_def=(4, 5))
    assert e.regions["emea"].mu > 0 > e.regions["pacific"].mu


def test_variance_inflates_with_time_and_offseason() -> None:
    p = EngineParams(q_player=1e-5, v_offseason=0.005)
    e = Engine(p)
    for _ in range(40):  # an established player: variance well below the new-player cap
        e.update_map(A, B, "Bind", 0.0, 2024, a_atk=(6, 12), a_def=(6, 12))
    v_now = e._peek("player", e.players[1], 0.0, 2024)[1]
    v_later = e._peek("player", e.players[1], 100.0, 2024)[1]
    v_next_season = e._peek("player", e.players[1], 100.0, 2025)[1]
    assert v_now < v_later < v_next_season


def test_dp_table_matches_production_dp() -> None:
    t = MapTable()
    for a, d in ((0.0, 0.0), (0.4, -0.2), (-1.1, 0.7)):
        assert float(t(a, d)) == pytest.approx(dp_map_p(a, d), abs=1e-3)
    assert float(t(0.0, 0.0)) == pytest.approx(0.5, abs=1e-9)
