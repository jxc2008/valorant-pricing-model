"""Bottom-up walk invariant: every _Cell.parent_p was populated before construction.

D-14: walk-order discipline. Each child cell's parent_p is FIXED at construction
time. The parent must be populated AND shrunk before the child is built.

03-02 status: xfail — scripts/calibrate_round_conclusion.py uses the v1
``cells_no_econ`` surface that 03-02 deletes. 03-07 (calibrator rewrite)
restores these tests against the v2 ETL re-run dataset.
"""

from __future__ import annotations

from typing import Any

import pytest

_XFAIL_REASON = (
    "03-07 — v1 calibrator + cells_no_econ deleted; v2 calibrator rewrite pending"
)


def test_walk_order_no_orphan_cells_in_full(
    synthetic_round_events: list[dict[str, Any]],
    synthetic_half_rates: dict[str, Any],
) -> None:
    pytest.xfail(_XFAIL_REASON)


def test_walk_order_no_orphan_cells_in_no_econ(
    synthetic_round_events: list[dict[str, Any]],
    synthetic_half_rates: dict[str, Any],
) -> None:
    pytest.xfail(_XFAIL_REASON)


def test_walk_order_no_orphan_cells_in_no_map(
    synthetic_round_events: list[dict[str, Any]],
    synthetic_half_rates: dict[str, Any],
) -> None:
    pytest.xfail(_XFAIL_REASON)


def test_walk_order_minimal_parent_is_average_of_side_baseline(
    synthetic_round_events: list[dict[str, Any]],
    synthetic_half_rates: dict[str, Any],
) -> None:
    pytest.xfail(_XFAIL_REASON)
