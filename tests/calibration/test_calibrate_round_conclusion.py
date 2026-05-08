"""Synthetic-dataset integration tests for scripts.calibrate_round_conclusion.

REQ-round-event-data-pipeline / D-13 / D-14.

03-02 status: every test in this file is xfailed because the v1 calibrator
(scripts/calibrate_round_conclusion.py + tests/calibration/conftest.py
synthetic dataset) is keyed on the v1 `(numerical_diff, bomb_planted, side,
econ_bucket, map)` cells_full schema. 03-02 rewrites RoundConclusionLookup
to the v2 `(att, def, time_bucket, side, map)` schema and DELETES the v1
`lookup()` method + `cells_no_econ` field. Wave 5 (plan 03-07) rewrites the
calibrator end-to-end against the v2 ETL re-run dataset; until then these
tests exercise dead v1 surface and are xfailed.
"""

from __future__ import annotations

from typing import Any

import pytest

from scripts.calibrate_round_conclusion import calibrate
from src.pricing.round_conclusion import RoundConclusionLookup

_XFAIL_REASON = (
    "03-07 — Phase 2 v1 calibrator dataset will be replaced by v2 ETL re-run"
)


def test_calibrate_returns_round_conclusion_lookup(
    synthetic_round_events: list[dict[str, Any]],
    synthetic_half_rates: dict[str, Any],
) -> None:
    pytest.xfail(_XFAIL_REASON)
    result = calibrate(synthetic_round_events, synthetic_half_rates, min_cell_n=1)
    assert isinstance(result, RoundConclusionLookup)


def test_calibrate_populates_side_baseline(
    synthetic_round_events: list[dict[str, Any]],
    synthetic_half_rates: dict[str, Any],
) -> None:
    pytest.xfail(_XFAIL_REASON)
    result = calibrate(synthetic_round_events, synthetic_half_rates, min_cell_n=1)
    assert "atk" in result.side_baseline
    assert "def" in result.side_baseline
    assert 0.0 <= result.side_baseline["atk"] <= 1.0
    assert 0.0 <= result.side_baseline["def"] <= 1.0


def test_calibrate_populates_cells_minimal(
    synthetic_round_events: list[dict[str, Any]],
    synthetic_half_rates: dict[str, Any],
) -> None:
    pytest.xfail(_XFAIL_REASON)
    result = calibrate(synthetic_round_events, synthetic_half_rates, min_cell_n=1)
    assert len(result.cells_minimal) >= 1


def test_calibrate_drops_cells_below_min_cell_n(
    synthetic_round_events: list[dict[str, Any]],
    synthetic_half_rates: dict[str, Any],
) -> None:
    """min_cell_n=10 drops sparse cells from the synthetic 50-row dataset."""
    pytest.xfail(_XFAIL_REASON)
    result = calibrate(synthetic_round_events, synthetic_half_rates, min_cell_n=10)
    for cell in result.cells_minimal.values():
        assert cell.n >= 10
    for cell in result.cells_no_map.values():
        assert cell.n >= 10
    for cell in result.cells_no_econ.values():
        assert cell.n >= 10
    for cell in result.cells_full.values():
        assert cell.n >= 10


def test_calibrate_idempotent(
    synthetic_round_events: list[dict[str, Any]],
    synthetic_half_rates: dict[str, Any],
) -> None:
    """D-16: re-running on the same input produces the same output."""
    pytest.xfail(_XFAIL_REASON)
    a = calibrate(synthetic_round_events, synthetic_half_rates, min_cell_n=1)
    b = calibrate(synthetic_round_events, synthetic_half_rates, min_cell_n=1)
    assert a.cells_minimal == b.cells_minimal
    assert a.cells_no_map == b.cells_no_map
    assert a.cells_no_econ == b.cells_no_econ
    assert a.cells_full == b.cells_full
    assert a.side_baseline == b.side_baseline


def test_calibrate_extreme_signal_close_to_p_hat(
    synthetic_half_rates: dict[str, Any],
) -> None:
    """A cell where 100/100 rounds were won returns shrunk() close to (but < 1)."""
    pytest.xfail(_XFAIL_REASON)
    rows: list[dict[str, Any]] = [
        {
            "match_id": f"M{i:04d}",
            "map_num": 0,
            "round_num": 1,
            "map_name": "Lotus",
            "round_won_by_a": True,
            "mid_round_states": [
                {
                    "t_offset": 0.0,
                    "kind": "event",
                    "numerical_diff": 2,
                    "bomb_planted": True,
                    "side": "atk",
                    "econ_bucket": "full",
                },
            ],
        }
        for i in range(100)
    ]
    result = calibrate(rows, synthetic_half_rates, min_cell_n=1)
    cell = result.cells_full[(2, True, "atk", "full", "Lotus")]
    val = cell.shrunk()
    assert val > 0.85
    assert val < 1.0  # shrinkage to parent prevents 1.0


def test_calibrate_walk_order_invariant(
    synthetic_round_events: list[dict[str, Any]],
    synthetic_half_rates: dict[str, Any],
) -> None:
    """D-14: every _Cell's parent_p was populated before construction.

    For each cells_full cell, the parent_p equals either the corresponding
    cells_no_econ.shrunk() OR side_baseline[side] (if cells_no_econ absent).
    """
    pytest.xfail(_XFAIL_REASON)
    result = calibrate(synthetic_round_events, synthetic_half_rates, min_cell_n=1)
    for (nd, bp, side, _econ, mp), cell in result.cells_full.items():
        expected = result.cells_no_econ.get((nd, bp, side, mp))
        if expected is not None:
            assert cell.parent_p == pytest.approx(expected.shrunk())
        else:
            # Fall to side_baseline (rare — only if cells_no_econ was filtered)
            assert cell.parent_p == pytest.approx(result.side_baseline.get(side, 0.5))


def test_calibrate_skip_cells_full_yields_empty_full(
    synthetic_round_events: list[dict[str, Any]],
    synthetic_half_rates: dict[str, Any],
) -> None:
    """skip_cells_full=True (D-05) leaves cells_full empty but lower levels filled."""
    pytest.xfail(_XFAIL_REASON)
    result = calibrate(
        synthetic_round_events,
        synthetic_half_rates,
        min_cell_n=1,
        skip_cells_full=True,
    )
    assert result.cells_full == {}
    # Lower levels still populated
    assert len(result.cells_minimal) >= 1
