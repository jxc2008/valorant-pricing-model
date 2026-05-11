"""Plan 04-02 — PortfolioState exposure registry tests.

Pitfall 5 mitigation surface (RESEARCH §"Common Pitfalls"): exposure MUST be
decremented on round resolution. Tests verify both the placement path
(monotonic accumulation) and the settlement path (clipped-at-zero
decrement). The pair is the integration seam plan 04-08 reconciliation
wires the round-resolution callback into.
"""
from __future__ import annotations

import pytest

from src.quoting.portfolio import PortfolioState


def test_empty_state_snapshot() -> None:
    assert PortfolioState().snapshot() == {}


def test_empty_state_current_returns_zero() -> None:
    assert PortfolioState().current("UNKNOWN") == 0.0


def test_on_place_records_exposure() -> None:
    s = PortfolioState()
    s.on_place("S1", 0.05)
    assert s.current("S1") == pytest.approx(0.05)
    snap = s.snapshot()
    assert snap == {"S1": pytest.approx(0.05)}


def test_on_place_accumulates() -> None:
    s = PortfolioState()
    s.on_place("S1", 0.05)
    s.on_place("S1", 0.03)
    assert s.current("S1") == pytest.approx(0.08)


def test_on_place_independent_series() -> None:
    s = PortfolioState()
    s.on_place("S1", 0.05)
    s.on_place("S2", 0.04)
    assert s.current("S1") == pytest.approx(0.05)
    assert s.current("S2") == pytest.approx(0.04)


def test_on_settle_decrements() -> None:
    s = PortfolioState()
    s.on_place("S1", 0.08)
    s.on_settle("S1", 0.05)
    assert s.current("S1") == pytest.approx(0.03)


def test_on_settle_clips_at_zero() -> None:
    """Pitfall 5: double-settlement should not push exposure negative."""
    s = PortfolioState()
    s.on_place("S1", 0.03)
    s.on_settle("S1", 0.10)
    assert s.current("S1") == 0.0


def test_on_settle_unknown_series_clips_at_zero() -> None:
    """Settling a never-placed series is a no-op (exposure stays 0)."""
    s = PortfolioState()
    s.on_settle("S1", 0.05)
    assert s.current("S1") == 0.0


def test_snapshot_is_a_copy() -> None:
    """Mutation of snapshot dict must NOT affect PortfolioState."""
    s = PortfolioState()
    s.on_place("S1", 0.05)
    snap = s.snapshot()
    snap["S1"] = 999.0
    snap["NEW"] = 0.42
    assert s.current("S1") == pytest.approx(0.05)
    assert s.current("NEW") == 0.0


def test_on_place_rejects_negative() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        PortfolioState().on_place("S1", -0.01)


def test_on_settle_rejects_negative() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        PortfolioState().on_settle("S1", -0.01)


def test_on_place_zero_fraction_no_op() -> None:
    """Zero is non-negative — records a 0.0 key, exposure unchanged in effect."""
    s = PortfolioState()
    s.on_place("S1", 0.0)
    assert s.current("S1") == 0.0


def test_lifecycle_place_settle_resnap_for_kelly_sizer() -> None:
    """End-to-end shape: snapshot is the contract kelly_size consumes."""
    s = PortfolioState()
    s.on_place("S1", 0.04)
    s.on_place("S2", 0.06)
    snap1 = s.snapshot()
    assert snap1 == {"S1": pytest.approx(0.04), "S2": pytest.approx(0.06)}

    s.on_settle("S1", 0.04)
    snap2 = s.snapshot()
    assert snap2 == {"S1": 0.0, "S2": pytest.approx(0.06)}
