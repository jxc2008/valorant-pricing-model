"""Plan 04-01 — REQ-kalshi-order-manager order placement + dry-run tests.

KalshiOrderManager: place_quote / cancel_quote / cancel_all_orders +
dry-run wrapper + error_streak counter + client_order_id UUID (RESEARCH
§"Pattern 2"). Live tests use aioresponses-mocked aiohttp ClientSession.

Source: PRD §5.3 / Plan 04-01 / reference/market_maker.py error-streak logic.
"""
from __future__ import annotations

import pytest
import aiohttp

from src.quoting.order_manager import KalshiOrderManager, Quote


def _make_quote(strategy_id: str = "MM_BETWEEN_ROUND") -> Quote:
    return Quote(
        ticker="VAL-T1",
        side="yes",
        action="buy",
        price=50,
        count=10,
        strategy_id=strategy_id,  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------- dry-run path

@pytest.mark.asyncio
async def test_place_quote_dry_run(fake_private_key) -> None:
    """Dry-run assigns DRY_<uuid8> order_id (len 12), records placed_at,
    no network call."""
    async with aiohttp.ClientSession() as session:
        mgr = KalshiOrderManager(session, "KEY", fake_private_key, dry_run=True)
        q = _make_quote()
        ok = await mgr.place_quote(q)
        assert ok is True
        assert q.order_id is not None
        assert q.order_id.startswith("DRY_")
        assert len(q.order_id) == 12  # "DRY_" + 8 hex chars
        assert q.placed_at is not None
        assert q.client_order_id is not None
        assert len(q.client_order_id) == 32  # uuid4().hex


@pytest.mark.asyncio
async def test_place_quote_dry_run_records_active_quotes(fake_private_key) -> None:
    """After place_quote in dry-run, mgr.active_quotes['VAL-T1']['buy_yes'] == q."""
    async with aiohttp.ClientSession() as session:
        mgr = KalshiOrderManager(session, "KEY", fake_private_key, dry_run=True)
        q = _make_quote()
        await mgr.place_quote(q)
        assert mgr.active_quotes["VAL-T1"]["buy_yes"] is q


@pytest.mark.asyncio
async def test_cancel_all_dry_run(fake_private_key) -> None:
    """cancel_all_orders clears the internal _active_quotes dict in dry-run."""
    async with aiohttp.ClientSession() as session:
        mgr = KalshiOrderManager(session, "KEY", fake_private_key, dry_run=True)
        for i in range(3):
            q = Quote(
                ticker=f"VAL-T{i}",
                side="yes",
                action="buy",
                price=50,
                count=10,
                strategy_id="MM_BETWEEN_ROUND",
            )
            await mgr.place_quote(q)
        assert len(mgr.active_quotes) == 3
        await mgr.cancel_all_orders()
        assert mgr.active_quotes == {}


@pytest.mark.asyncio
async def test_error_streak_zero_on_dry_run(fake_private_key) -> None:
    """Dry-run never increments error_streak (no network calls happen)."""
    async with aiohttp.ClientSession() as session:
        mgr = KalshiOrderManager(session, "KEY", fake_private_key, dry_run=True)
        for _ in range(5):
            await mgr.place_quote(_make_quote())
        assert mgr.error_streak == 0


@pytest.mark.asyncio
async def test_client_order_id_uuid_set(fake_private_key) -> None:
    """RESEARCH §"Pattern 2" — client_order_id is a stable UUID set at place
    time so a Kalshi reconnect/replay doesn't double-place; the order manager
    dedupes by client_order_id."""
    async with aiohttp.ClientSession() as session:
        mgr = KalshiOrderManager(session, "KEY", fake_private_key, dry_run=True)
        q = _make_quote()
        assert q.client_order_id is None
        await mgr.place_quote(q)
        assert q.client_order_id is not None
        assert len(q.client_order_id) == 32  # uuid4().hex


# ---------------------------------------------------------------- live path (mocked)

@pytest.mark.asyncio
async def test_place_quote_live_201_succeeds(fake_private_key, fake_kalshi_session) -> None:
    """201 + payload {'order': {'order_id': 'abc'}} → quote.order_id='abc',
    error_streak resets to 0."""
    async with aiohttp.ClientSession() as session:
        mgr = KalshiOrderManager(session, "KEY", fake_private_key, dry_run=False)
        # Pre-seed an error_streak to verify reset on success.
        mgr._error_streak = 2

        with fake_kalshi_session as m:
            m.post(
                "https://api.elections.kalshi.com/trade-api/v2/portfolio/orders",
                status=201,
                payload={"order": {"order_id": "abc"}},
            )
            q = _make_quote()
            ok = await mgr.place_quote(q)
            assert ok is True
            assert q.order_id == "abc"
            assert mgr.error_streak == 0
            assert mgr.active_quotes["VAL-T1"]["buy_yes"] is q


@pytest.mark.asyncio
async def test_place_quote_live_4xx_increments_error_streak(
    fake_private_key, fake_kalshi_session
) -> None:
    """4xx response → place_quote returns False AND _error_streak ticks up by 1."""
    async with aiohttp.ClientSession() as session:
        mgr = KalshiOrderManager(session, "KEY", fake_private_key, dry_run=False)
        assert mgr.error_streak == 0

        with fake_kalshi_session as m:
            m.post(
                "https://api.elections.kalshi.com/trade-api/v2/portfolio/orders",
                status=400,
                payload={"error": "bad request"},
            )
            ok = await mgr.place_quote(_make_quote())
            assert ok is False
            assert mgr.error_streak == 1


@pytest.mark.asyncio
async def test_cancel_all_uses_batched_path(fake_private_key, fake_kalshi_session) -> None:
    """Live cancel_all_orders posts to /portfolio/orders/batched (2 tokens/order
    rate-budget per RESEARCH §"Pattern 2") rather than per-order DELETE."""
    async with aiohttp.ClientSession() as session:
        mgr = KalshiOrderManager(session, "KEY", fake_private_key, dry_run=False)
        # Pre-populate active_quotes with two live orders.
        q1 = _make_quote()
        q1.order_id = "ord-1"
        q2 = Quote(
            ticker="VAL-T2",
            side="no",
            action="sell",
            price=40,
            count=5,
            strategy_id="DIRECTIONAL_TAKE",
        )
        q2.order_id = "ord-2"
        mgr._active_quotes["VAL-T1"] = {"buy_yes": q1}
        mgr._active_quotes["VAL-T2"] = {"sell_no": q2}

        with fake_kalshi_session as m:
            m.delete(
                "https://api.elections.kalshi.com/trade-api/v2/portfolio/orders/batched",
                status=200,
                payload={"cancelled": ["ord-1", "ord-2"]},
            )
            await mgr.cancel_all_orders()

            # aioresponses records all requests by (method, URL); verify the
            # batched URL was the one used.
            requested_urls = [str(req[1]) for req in m.requests.keys()]
            assert any("batched" in u for u in requested_urls), (
                f"Expected /batched URL in requests, got: {requested_urls}"
            )

        # State cleared after batch DELETE returns 200.
        assert mgr.active_quotes == {}
