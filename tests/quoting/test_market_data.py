"""Plan 04-01 — REQ-kalshi-order-manager MarketQuote + MarketDataSource tests.

MarketQuote dataclass shape (yes_bid, yes_ask, mid, spread, is_valid,
last_updated_ts); make_quote helper auto-derives mid + spread.
SyntheticMarketData (dry-run / tests) round-trips via push() / latest().
KalshiWsMarketData skeleton: dry-run returns; live raises NotImplementedError
(operator gate 2 + Phase 6 deployment work).
mark_invalid (Pitfall 7) flips cached quotes to is_valid=False on disconnect.

Source: PRD §5.3 / Plan 04-01 / RESEARCH §"Standard Stack" Kalshi WS endpoints
/ Pitfalls 7 + 8.
"""
from __future__ import annotations

import asyncio

import pytest

from src.quoting.market_data import (
    KalshiWsMarketData,
    MarketDataSource,
    MarketQuote,
    SyntheticMarketData,
    make_quote,
)


def test_market_quote_dataclass_shape() -> None:
    """make_quote(48, 52) auto-derives mid=50, spread=4, is_valid=True."""
    q = make_quote(48, 52)
    assert q.yes_bid == 48
    assert q.yes_ask == 52
    assert q.mid == 50
    assert q.spread == 4
    assert q.is_valid is True
    assert q.last_updated_ts > 0


def test_synthetic_market_data_push_latest(make_market_quote) -> None:
    """push() / latest() round-trips on the same ticker."""
    src = SyntheticMarketData()
    q = make_quote(48, 52)
    src.push("VAL-T1-WIN", q)
    assert src.latest("VAL-T1-WIN") == q


def test_synthetic_market_data_latest_unknown_returns_none() -> None:
    src = SyntheticMarketData()
    assert src.latest("UNKNOWN") is None


@pytest.mark.asyncio
async def test_synthetic_market_data_run_is_noop() -> None:
    """SyntheticMarketData.run() is a no-op coroutine — returns immediately."""
    src = SyntheticMarketData()
    await asyncio.wait_for(src.run(), 0.1)


@pytest.mark.asyncio
async def test_kalshi_ws_market_data_dry_run_returns(fake_private_key) -> None:
    """KalshiWsMarketData.run() with dry_run=True returns None immediately."""
    ws = KalshiWsMarketData("KEY", fake_private_key, dry_run=True)
    result = await asyncio.wait_for(ws.run(), 0.1)
    assert result is None


@pytest.mark.asyncio
async def test_kalshi_ws_market_data_live_raises_not_implemented(fake_private_key) -> None:
    """Skeleton contract: dry_run=False path raises NotImplementedError pending
    Phase 6 deployment work (RESEARCH Pitfall 8 — operator-gated)."""
    ws = KalshiWsMarketData("KEY", fake_private_key, dry_run=False)
    with pytest.raises(NotImplementedError, match="operator-gated"):
        await ws.run()


def test_market_data_source_protocol_runtime_check() -> None:
    """SyntheticMarketData satisfies the MarketDataSource Protocol structurally."""
    assert isinstance(SyntheticMarketData(), MarketDataSource)


def test_mark_invalid_flips_cached_quotes(fake_private_key) -> None:
    """Pitfall 7: WS disconnect handler flips cached quote.is_valid=False so
    mode-selector kill_switch_active treats it as a trip downstream."""
    ws = KalshiWsMarketData("KEY", fake_private_key, dry_run=True)
    ws._quotes["VAL-T1"] = make_quote(48, 52)
    assert ws.latest("VAL-T1") is not None
    cached = ws.latest("VAL-T1")
    assert cached is not None
    assert cached.is_valid is True

    ws.mark_invalid()

    after = ws.latest("VAL-T1")
    assert after is not None
    assert after.is_valid is False
    # Other fields preserved
    assert after.yes_bid == 48
    assert after.yes_ask == 52
    assert isinstance(after, MarketQuote)
