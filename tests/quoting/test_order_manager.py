"""Plan 04-01 — REQ-kalshi-order-manager order placement + dry-run RED-stub tests.

KalshiOrderManager: place_quote / cancel_all / error-streak tracking /
client_order_id UUID survives reconnect (RESEARCH §"Pattern 2").

Source: PRD §5.3 / Plan 04-01 / reference/market_maker.py error-streak logic.
"""
from __future__ import annotations

import pytest


def test_place_quote_dry_run(make_match_state, make_market_quote) -> None:
    """Dry-run records DRY_<uuid> order_id; no network call (verified via
    fake_kalshi_session not being touched)."""
    pytest.xfail("Plan 04-01 — src/quoting/order_manager.py not yet implemented")


def test_cancel_all_dry_run(make_match_state, make_market_quote) -> None:
    """cancel_all clears the internal _active_quotes dict in dry-run."""
    pytest.xfail("Plan 04-01 — src/quoting/order_manager.py not yet implemented")


def test_error_streak_increments_on_failed_place(fake_kalshi_session) -> None:
    """Salvaged from reference/market_maker.py — error_streak counter ticks on
    aiohttp.ClientError; resets on success. Used by Kalshi-API-error kill switch."""
    pytest.xfail("Plan 04-01 — src/quoting/order_manager.py not yet implemented")


def test_client_order_id_uuid_set() -> None:
    """RESEARCH §"Pattern 2" — client_order_id is a stable UUID set at construction
    so a Kalshi reconnect/replay doesn't double-place; the order manager dedupes
    by client_order_id."""
    pytest.xfail("Plan 04-01 — src/quoting/order_manager.py not yet implemented")
