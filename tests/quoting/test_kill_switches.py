"""Plan 04-03 — REQ-kill-switches RED-stub tests.

Four always-on kill switches (CRule 9): Kalshi API error streak / ingestion
staleness > 5s / |theo - market| > 20¢ / rolling Brier > 0.30 over 50 rounds.
Aggregator returns the tripped names; ANY trip cancels all resting orders.

Source: PRD §5.4 / CRule 9 / DEC-005.
"""
from __future__ import annotations

import pytest


def test_staleness_trip_at_5s(make_match_state) -> None:
    """KILL_SWITCH_STALENESS_S boundary — 5.0s exact trips."""
    pytest.xfail("Plan 04-03 — src/quoting/kill_switches.py not yet implemented")


def test_staleness_no_trip_at_4_99s(make_match_state) -> None:
    """Boundary — just under 5s does NOT trip."""
    pytest.xfail("Plan 04-03 — src/quoting/kill_switches.py not yet implemented")


def test_deviation_trip_at_21c(make_match_state, make_market_quote) -> None:
    """KILL_SWITCH_DEVIATION_C boundary — 21c trips (> 20c)."""
    pytest.xfail("Plan 04-03 — src/quoting/kill_switches.py not yet implemented")


def test_deviation_no_trip_at_19c(make_match_state, make_market_quote) -> None:
    """Boundary — 19c does NOT trip."""
    pytest.xfail("Plan 04-03 — src/quoting/kill_switches.py not yet implemented")


def test_brier_trip_above_0_30() -> None:
    """KILL_SWITCH_BRIER_BOUND — realized rolling Brier > 0.30 trips."""
    pytest.xfail("Plan 04-03 — src/quoting/kill_switches.py not yet implemented")


def test_brier_no_trip_window_not_full() -> None:
    """Below KILL_SWITCH_BRIER_WINDOW samples, Brier switch does NOT trip
    (insufficient evidence)."""
    pytest.xfail("Plan 04-03 — src/quoting/kill_switches.py not yet implemented")


def test_api_error_streak_trip() -> None:
    """Kalshi-API-error streak >= 3 trips the API kill switch."""
    pytest.xfail("Plan 04-03 — src/quoting/kill_switches.py not yet implemented")


def test_api_error_no_trip_at_2() -> None:
    """Streak of 2 errors does NOT trip — boundary."""
    pytest.xfail("Plan 04-03 — src/quoting/kill_switches.py not yet implemented")


def test_aggregator_any_tripped(make_match_state, make_market_quote) -> None:
    """ANY of the four trips returns True + list of tripped switch names."""
    pytest.xfail("Plan 04-03 — src/quoting/kill_switches.py not yet implemented")


def test_aggregator_returns_empty_when_none_tripped(make_match_state, make_market_quote) -> None:
    """Healthy state — aggregator returns (False, [])."""
    pytest.xfail("Plan 04-03 — src/quoting/kill_switches.py not yet implemented")
