"""Bottom-up walk invariant: every _Cell.parent_p was populated before construction.

D-14: walk-order discipline. Each child cell's parent_p is FIXED at construction
time. The parent must be populated AND shrunk before the child is built.
"""

from __future__ import annotations

import math
from typing import Any

from scripts.calibrate_round_conclusion import calibrate


def test_walk_order_no_orphan_cells_in_full(
    synthetic_round_events: list[dict[str, Any]],
    synthetic_half_rates: dict[str, Any],
) -> None:
    """Every cells_full cell's parent_p is a finite float in [0, 1]."""
    result = calibrate(synthetic_round_events, synthetic_half_rates, min_cell_n=1)
    for cell in result.cells_full.values():
        assert 0.0 <= cell.parent_p <= 1.0
        assert not math.isnan(cell.parent_p)


def test_walk_order_no_orphan_cells_in_no_econ(
    synthetic_round_events: list[dict[str, Any]],
    synthetic_half_rates: dict[str, Any],
) -> None:
    result = calibrate(synthetic_round_events, synthetic_half_rates, min_cell_n=1)
    for cell in result.cells_no_econ.values():
        assert 0.0 <= cell.parent_p <= 1.0
        assert not math.isnan(cell.parent_p)


def test_walk_order_no_orphan_cells_in_no_map(
    synthetic_round_events: list[dict[str, Any]],
    synthetic_half_rates: dict[str, Any],
) -> None:
    result = calibrate(synthetic_round_events, synthetic_half_rates, min_cell_n=1)
    for cell in result.cells_no_map.values():
        assert 0.0 <= cell.parent_p <= 1.0
        assert not math.isnan(cell.parent_p)


def test_walk_order_minimal_parent_is_average_of_side_baseline(
    synthetic_round_events: list[dict[str, Any]],
    synthetic_half_rates: dict[str, Any],
) -> None:
    """cells_minimal parent_p is the average of side_baseline values."""
    result = calibrate(synthetic_round_events, synthetic_half_rates, min_cell_n=1)
    expected_parent = (
        result.side_baseline["atk"] + result.side_baseline["def"]
    ) / 2
    for cell in result.cells_minimal.values():
        assert cell.parent_p == expected_parent
