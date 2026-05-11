"""Plan 04-02 — REQ-kelly-sizer (v2 portfolio-aware) RED-stub tests.

DEC-023 v2: half-Kelly + per-market cap (0.05) + per-series aggregate cap (0.10).
Pure function in src/sizing/kelly.py.
"""
from __future__ import annotations

import pytest


def test_v1_single_market_compat() -> None:
    """Identical to v1 single-market case when current_series_exposure == {}."""
    pytest.xfail("Plan 04-02 — src/sizing/kelly.py not yet implemented")


def test_aggregate_cap_binds_at_exposure_010() -> None:
    pytest.xfail("Plan 04-02 — src/sizing/kelly.py not yet implemented")


def test_returns_zero_when_aggregate_exceeded() -> None:
    pytest.xfail("Plan 04-02 — src/sizing/kelly.py not yet implemented")


def test_per_market_cap_binds_at_005() -> None:
    pytest.xfail("Plan 04-02 — src/sizing/kelly.py not yet implemented")


def test_never_full_kelly() -> None:
    """Property: result <= int(KELLY_MULTIPLIER * f_full * bankroll / ask)."""
    pytest.xfail("Plan 04-02 — src/sizing/kelly.py not yet implemented")


def test_returns_zero_for_negative_edge() -> None:
    """If theo <= ask/100, sizer returns 0."""
    pytest.xfail("Plan 04-02 — src/sizing/kelly.py not yet implemented")


def test_handles_ask_at_boundaries() -> None:
    """ask=0 or ask>=100 returns 0 — defensive guard."""
    pytest.xfail("Plan 04-02 — src/sizing/kelly.py not yet implemented")
