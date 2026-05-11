"""Plan 04-03 — REQ-kill-switches GREEN tests (DEC-005 + Pitfall 7).

Four always-on kill switches (CRule 9): Kalshi API error streak / ingestion
staleness > 5s / |theo - market| > 20¢ / rolling Brier > 0.30 over 50 rounds.
Plus a 5th ``kill_switch_market_invalid`` (Pitfall 7 WS reconnect path).
Aggregator returns sorted tripped names; ANY trip cancels all resting orders.

Each predicate gets a TRIP test + a NON-TRIP boundary test (the strict-vs-
non-strict inequality is the most common kill-switch bug per RESEARCH
§"Common Pitfalls" anti-pattern 4).

Source: PRD §5.4 / CRule 9 / DEC-005 / RESEARCH Pitfall 7.
"""
from __future__ import annotations

from collections import deque
from collections.abc import Callable
from typing import Any

from src.config.constants import (
    KILL_SWITCH_BRIER_BOUND,
    KILL_SWITCH_BRIER_WINDOW,
)
from src.pricing.data import TheoOutput
from src.quoting.kill_switches import (
    KillSwitchAggregator,
    kill_switch_api_error,
    kill_switch_brier,
    kill_switch_deviation,
    kill_switch_market_invalid,
    kill_switch_staleness,
)
from src.quoting.market_data import MarketQuote, make_quote


def _theo(theo_series: float = 0.50) -> TheoOutput:
    return TheoOutput(
        theo_series=theo_series,
        theo_map=(theo_series,),
        vega=0.0,
        confidence=1.0,
    )


# ---------------- staleness ----------------


def test_staleness_trip_above_5s(make_match_state: Callable[..., Any]) -> None:
    """KILL_SWITCH_STALENESS_S boundary — > 5.0s trips."""
    state = make_match_state(last_updated_ts=100.0)
    assert kill_switch_staleness(state, now=105.01) is True


def test_staleness_no_trip_at_exactly_5s(make_match_state: Callable[..., Any]) -> None:
    """Boundary — exactly 5s does NOT trip (strict inequality)."""
    state = make_match_state(last_updated_ts=100.0)
    assert kill_switch_staleness(state, now=105.0) is False


def test_staleness_no_trip_under_5s(make_match_state: Callable[..., Any]) -> None:
    """Boundary — just under 5s does NOT trip."""
    state = make_match_state(last_updated_ts=100.0)
    assert kill_switch_staleness(state, now=104.99) is False


# ---------------- deviation ----------------


def test_deviation_trip_above_20c() -> None:
    """theo=0.50 (50c) vs mid=71c → |50 - 71| = 21 > 20 → trip."""
    market = make_quote(yes_bid=70, yes_ask=72)  # mid = 71
    assert kill_switch_deviation(_theo(0.50), market) is True


def test_deviation_no_trip_at_exactly_20c() -> None:
    """theo=0.50 (50c) vs mid=70c → |50 - 70| = 20, NOT > 20 → no trip."""
    market = make_quote(yes_bid=69, yes_ask=71)  # mid = 70
    assert kill_switch_deviation(_theo(0.50), market) is False


# ---------------- brier ----------------


def test_brier_no_trip_window_not_full() -> None:
    """Below KILL_SWITCH_BRIER_WINDOW samples, Brier switch does NOT trip."""
    d: deque[float] = deque(
        [0.99] * (KILL_SWITCH_BRIER_WINDOW - 1),
        maxlen=KILL_SWITCH_BRIER_WINDOW,
    )
    assert kill_switch_brier(d) is False


def test_brier_no_trip_at_exact_threshold() -> None:
    """Boundary — mean == threshold (0.30) does NOT trip (strict inequality)."""
    d: deque[float] = deque(
        [KILL_SWITCH_BRIER_BOUND] * KILL_SWITCH_BRIER_WINDOW,
        maxlen=KILL_SWITCH_BRIER_WINDOW,
    )
    assert kill_switch_brier(d) is False


def test_brier_trip_above_threshold() -> None:
    """KILL_SWITCH_BRIER_BOUND — realized rolling Brier > 0.30 trips."""
    d: deque[float] = deque(
        [KILL_SWITCH_BRIER_BOUND + 0.10] * KILL_SWITCH_BRIER_WINDOW,
        maxlen=KILL_SWITCH_BRIER_WINDOW,
    )
    assert kill_switch_brier(d) is True


# ---------------- api_error ----------------


def test_api_error_trip_at_3() -> None:
    """Kalshi-API-error streak >= 3 trips the API kill switch."""
    assert kill_switch_api_error(3) is True


def test_api_error_no_trip_at_2() -> None:
    """Streak of 2 errors does NOT trip — boundary."""
    assert kill_switch_api_error(2) is False


def test_api_error_trip_above_3() -> None:
    """Streak well above threshold also trips (>= semantics)."""
    assert kill_switch_api_error(10) is True


# ---------------- market_invalid (Pitfall 7) ----------------


def test_market_invalid_trip() -> None:
    """MarketQuote.is_valid=False trips (WS reconnect path)."""
    market = MarketQuote(
        yes_bid=48, yes_ask=52, mid=50, spread=4,
        is_valid=False, last_updated_ts=0.0,
    )
    assert kill_switch_market_invalid(market) is True


def test_market_invalid_no_trip_when_valid() -> None:
    """Healthy market quote does NOT trip."""
    assert kill_switch_market_invalid(make_quote(48, 52)) is False


# ---------------- aggregator ----------------


def test_aggregator_returns_empty_when_none_tripped(
    make_match_state: Callable[..., Any],
) -> None:
    """Healthy state — aggregator returns (False, [])."""
    agg = KillSwitchAggregator()
    state = make_match_state(last_updated_ts=9e12)  # very recent
    market = make_quote(48, 52)
    tripped, names = agg.any_tripped(state, _theo(0.50), market, error_streak=0)
    assert tripped is False
    assert names == []


def test_aggregator_single_trip(make_match_state: Callable[..., Any]) -> None:
    """Single trip (staleness) returns (True, ['staleness'])."""
    agg = KillSwitchAggregator()
    state = make_match_state(last_updated_ts=0.0)  # very stale
    market = make_quote(48, 52)
    tripped, names = agg.any_tripped(state, _theo(0.50), market, error_streak=0)
    assert tripped is True
    assert "staleness" in names


def test_aggregator_any_tripped(make_match_state: Callable[..., Any]) -> None:
    """ANY of the four trips returns True + sorted list of tripped names."""
    agg = KillSwitchAggregator()
    state = make_match_state(last_updated_ts=0.0)  # staleness trip
    market = MarketQuote(
        yes_bid=70, yes_ask=72, mid=71, spread=2,
        is_valid=False, last_updated_ts=0.0,
    )
    # deviation trip (|50 - 71| > 20) AND market_invalid trip AND api_error
    tripped, names = agg.any_tripped(state, _theo(0.50), market, error_streak=5)
    assert tripped is True
    # Sorted alphabetically per Phase 03 D-08 set-iteration determinism
    assert names == sorted(names)
    assert {"staleness", "deviation", "market_invalid", "api_error"} <= set(names)


def test_aggregator_recent_briers_is_deque() -> None:
    """Aggregator owns a deque(maxlen=50) at .recent_briers."""
    agg = KillSwitchAggregator()
    assert isinstance(agg.recent_briers, deque)
    assert agg.recent_briers.maxlen == KILL_SWITCH_BRIER_WINDOW


def test_aggregator_brier_appendable_and_trips_when_full(
    make_match_state: Callable[..., Any],
) -> None:
    """Plan 04-08 will append Brier scores; verify the deque accumulates and trips."""
    agg = KillSwitchAggregator()
    for _ in range(KILL_SWITCH_BRIER_WINDOW):
        agg.recent_briers.append(0.50)  # mean = 0.50 > 0.30
    state = make_match_state(last_updated_ts=9e12)
    tripped, names = agg.any_tripped(
        state, _theo(0.50), make_quote(48, 52), error_streak=0,
    )
    assert tripped is True
    assert "brier" in names
