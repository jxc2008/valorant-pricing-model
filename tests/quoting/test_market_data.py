"""Plan 04-01 — REQ-kalshi-order-manager WebSocket market data RED-stub tests.

MarketQuote dataclass shape (yes_bid, yes_ask, mid, spread, is_valid); WS
subscribe message shape (orderbook_delta + ticker channels); WS disconnect
invalidates last quote (Pitfall 7).

Source: PRD §5.3 / Plan 04-01 / RESEARCH §"Standard Stack" Kalshi WS endpoints
/ Pitfall 7.
"""
from __future__ import annotations

import pytest


def test_market_quote_dataclass_shape() -> None:
    """MarketQuote exposes yes_bid, yes_ask, mid, spread, is_valid fields."""
    pytest.xfail("Plan 04-01 — src/quoting/market_data.py not yet implemented")


def test_ws_subscribe_message_shape() -> None:
    """Subscribe payload includes orderbook_delta AND ticker channels (RESEARCH
    §"Standard Stack" — both needed: orderbook for spread, ticker for last)."""
    pytest.xfail("Plan 04-01 — src/quoting/market_data.py not yet implemented")


def test_ws_disconnect_marks_invalid() -> None:
    """Pitfall 7: WS disconnect must flip is_valid=False on the cached
    MarketQuote — kill-switch (a) trips downstream."""
    pytest.xfail("Plan 04-01 — src/quoting/market_data.py not yet implemented")
