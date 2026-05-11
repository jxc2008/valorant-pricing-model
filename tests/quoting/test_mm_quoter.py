"""Plan 04-05 — REQ-mm-quoter (v2 between-round only) GREEN tests.

DEC-018 v2 spread formula + RESEARCH Pitfall 4 (floor beats Kalshi fee curve).
"""
from __future__ import annotations

import math
from collections.abc import AsyncIterator, Callable
from typing import Any

import aiohttp
import pytest
import pytest_asyncio
from cryptography.hazmat.primitives.asymmetric import rsa
from hypothesis import HealthCheck, given, settings, strategies as st

from src.config.constants import MIN_HALF_SPREAD
from src.pricing.data import TheoOutput
from src.quoting.market_data import make_quote
from src.quoting.mm_quoter import compute_half_spread, quote_mm_between_round
from src.quoting.order_manager import KalshiOrderManager


def _theo(theo_series: float = 0.50, vega: float = 0.0) -> TheoOutput:
    return TheoOutput(
        theo_series=theo_series,
        theo_map=(theo_series,),
        vega=vega,
        confidence=1.0,
    )


@pytest_asyncio.fixture
async def mgr(fake_private_key: rsa.RSAPrivateKey) -> AsyncIterator[KalshiOrderManager]:
    async with aiohttp.ClientSession() as session:
        yield KalshiOrderManager(
            session=session, key_id="K",
            private_key=fake_private_key, dry_run=True,
        )


# ---------------- compute_half_spread ----------------

def test_spread_floor_at_zero_vega() -> None:
    """Zero vega + zero staleness -> MIN_HALF_SPREAD (3c)."""
    assert compute_half_spread(0.0, 0.0) == MIN_HALF_SPREAD


def test_spread_vega_contribution_at_typical_value() -> None:
    """vega=0.01 -> ceil(50 * 0.1) = 5c."""
    assert compute_half_spread(0.01, 0.0) == 5


def test_spread_floor_binds_at_low_vega() -> None:
    """vega=0.001 -> ceil(50 * 0.0316) = 2c < floor -> returns 3c."""
    assert compute_half_spread(0.001, 0.0) == MIN_HALF_SPREAD


def test_spread_staleness_penalty_below_floor() -> None:
    """staleness <= 2s -> no penalty."""
    assert compute_half_spread(0.0, 1.5) == MIN_HALF_SPREAD
    assert compute_half_spread(0.0, 2.0) == MIN_HALF_SPREAD


def test_spread_staleness_penalty_above_2s() -> None:
    """staleness=3s -> +1c penalty; staleness=4.5s -> +2c."""
    assert compute_half_spread(0.0, 3.0) == MIN_HALF_SPREAD + 1
    assert compute_half_spread(0.0, 4.5) == MIN_HALF_SPREAD + 2


def test_spread_handles_negative_vega_defensively() -> None:
    """Negative vega is a programming error; defensively clip to 0."""
    assert compute_half_spread(-0.05, 0.0) == MIN_HALF_SPREAD


@given(
    vega=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    staleness=st.floats(min_value=0.0, max_value=4.99, allow_nan=False),
)
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_spread_floor_invariant(vega: float, staleness: float) -> None:
    """Property: half-spread >= MIN_HALF_SPREAD for all non-negative inputs."""
    assert compute_half_spread(vega, staleness) >= MIN_HALF_SPREAD


def test_spread_floor_beats_fee() -> None:
    """RESEARCH Pitfall 4: MIN_HALF_SPREAD must exceed Kalshi maker fee + 1c slippage.

    At theo=50c (worst case for fee curve):
        maker fee = ceil(0.035 * 0.5 * 0.5 * 100) / 100 = 0.88c
        slippage budget = 1c
        required floor > 1.88c -> MIN_HALF_SPREAD=3c satisfies this.
    """
    # Symbolic worst-case fee at theo=0.5
    p = 0.50
    maker_fee_c = math.ceil(0.035 * p * (1 - p) * 100) / 100
    slippage_c = 1.0
    assert MIN_HALF_SPREAD > maker_fee_c + slippage_c


# ---------------- quote_mm_between_round (dry-run) ----------------

@pytest.mark.asyncio
async def test_places_both_legs(
    mgr: KalshiOrderManager,
    make_match_state: Callable[..., Any],
) -> None:
    state = make_match_state(bomb_planted=False, time_left_s=None, last_updated_ts=1000.0)
    market = make_quote(46, 54)  # mid=50, spread=8
    await quote_mm_between_round(
        state, _theo(0.50, vega=0.005), market, mgr,
        ticker="VAL-T1-WIN", count=10, now=1000.5,
    )
    legs = mgr.active_quotes["VAL-T1-WIN"]
    assert "buy_yes" in legs
    assert "sell_yes" in legs
    # theo=50, vega=0.005 -> ceil(50*sqrt(0.005)) = 4c half-spread
    assert legs["buy_yes"].price == 50 - 4
    assert legs["sell_yes"].price == 50 + 4


@pytest.mark.asyncio
async def test_quotes_tagged_with_strategy_id(
    mgr: KalshiOrderManager,
    make_match_state: Callable[..., Any],
) -> None:
    state = make_match_state(bomb_planted=False, time_left_s=None, last_updated_ts=1000.0)
    market = make_quote(46, 54)
    await quote_mm_between_round(
        state, _theo(0.50), market, mgr,
        ticker="VAL-T1-WIN", count=10, now=1000.5,
    )
    for leg in mgr.active_quotes["VAL-T1-WIN"].values():
        assert leg.strategy_id == "MM_BETWEEN_ROUND"


@pytest.mark.asyncio
async def test_idempotent_on_unchanged_prices(
    mgr: KalshiOrderManager,
    make_match_state: Callable[..., Any],
) -> None:
    """Same theo + market + age < 2s -> no cancel, no re-place."""
    state = make_match_state(bomb_planted=False, time_left_s=None, last_updated_ts=1000.0)
    market = make_quote(46, 54)
    await quote_mm_between_round(
        state, _theo(0.50), market, mgr,
        ticker="VAL-T1-WIN", count=10, now=1000.5,
    )
    first_oids = {leg: q.order_id for leg, q in mgr.active_quotes["VAL-T1-WIN"].items()}
    # Second call with same inputs + age < 2s -> quotes unchanged
    await quote_mm_between_round(
        state, _theo(0.50), market, mgr,
        ticker="VAL-T1-WIN", count=10, now=1001.0,
    )
    second_oids = {leg: q.order_id for leg, q in mgr.active_quotes["VAL-T1-WIN"].items()}
    assert first_oids == second_oids


@pytest.mark.asyncio
async def test_cancels_stale_quotes(
    mgr: KalshiOrderManager,
    make_match_state: Callable[..., Any],
) -> None:
    """Quote placed > 2s ago is treated as stale -> cancel + re-place."""
    state = make_match_state(bomb_planted=False, time_left_s=None, last_updated_ts=1000.0)
    market = make_quote(46, 54)
    await quote_mm_between_round(
        state, _theo(0.50), market, mgr,
        ticker="VAL-T1-WIN", count=10, now=1000.0,
    )
    first_oids = {leg: q.order_id for leg, q in mgr.active_quotes["VAL-T1-WIN"].items()}
    # Second call with now=1005 -> age=5s > 2s -> quotes replaced
    await quote_mm_between_round(
        state, _theo(0.50), market, mgr,
        ticker="VAL-T1-WIN", count=10, now=1005.0,
    )
    second_oids = {leg: q.order_id for leg, q in mgr.active_quotes["VAL-T1-WIN"].items()}
    assert first_oids != second_oids  # New order_ids after re-place


@pytest.mark.asyncio
async def test_cancels_mispriced_quotes(
    mgr: KalshiOrderManager,
    make_match_state: Callable[..., Any],
) -> None:
    """Theo shifted -> buy_yes price changed -> cancel + re-place."""
    state = make_match_state(bomb_planted=False, time_left_s=None, last_updated_ts=1000.0)
    market = make_quote(46, 54)
    await quote_mm_between_round(
        state, _theo(0.50), market, mgr,
        ticker="VAL-T1-WIN", count=10, now=1000.5,
    )
    first_buy_price = mgr.active_quotes["VAL-T1-WIN"]["buy_yes"].price
    # Theo shifts to 0.55 -> buy_yes price moves up
    await quote_mm_between_round(
        state, _theo(0.55), market, mgr,
        ticker="VAL-T1-WIN", count=10, now=1001.0,
    )
    new_buy_price = mgr.active_quotes["VAL-T1-WIN"]["buy_yes"].price
    assert new_buy_price != first_buy_price
    assert new_buy_price == 55 - 3  # theo_c=55, hs=3 floor


@pytest.mark.asyncio
async def test_boundary_guard_skips_when_price_below_1(
    mgr: KalshiOrderManager,
    make_match_state: Callable[..., Any],
) -> None:
    """theo=0.02 -> buy_price = 2 - 3 = -1 (out of bounds) -> skip placement."""
    state = make_match_state(bomb_planted=False, time_left_s=None, last_updated_ts=1000.0)
    market = make_quote(1, 5)
    await quote_mm_between_round(
        state, _theo(0.02), market, mgr,
        ticker="VAL-T1-WIN", count=10, now=1000.5,
    )
    assert "VAL-T1-WIN" not in mgr.active_quotes


@pytest.mark.asyncio
async def test_boundary_guard_skips_when_price_above_99(
    mgr: KalshiOrderManager,
    make_match_state: Callable[..., Any],
) -> None:
    """theo=0.98 -> sell_price = 98 + 3 = 101 (out of bounds) -> skip placement."""
    state = make_match_state(bomb_planted=False, time_left_s=None, last_updated_ts=1000.0)
    market = make_quote(95, 99)
    await quote_mm_between_round(
        state, _theo(0.98), market, mgr,
        ticker="VAL-T1-WIN", count=10, now=1000.5,
    )
    assert "VAL-T1-WIN" not in mgr.active_quotes
