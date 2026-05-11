"""KalshiOrderManager — async REST plumbing for Kalshi order lifecycle.

Owns:
  - aiohttp.ClientSession (caller-supplied so a single session is reused
    across the order manager + market-data WS + reconciliation pollers)
  - In-memory active quotes dict (rebuildable from Kalshi via plan 04-08
    reconciliation)
  - error_streak counter for the API-error kill switch (DEC-005 #a)
  - dry_run wrapper (DEC-022 / CLAUDE.md rule 13 — `dry_run` MUST come from
    src.main.resolve_dry_run; do NOT default to a module attribute)

Salvaged structurally from reference/market_maker.py per DEC-013:
  - Quote dataclass shape (with strategy_id added v2)
  - _MAX_ERRORS_BEFORE_PAUSE = 3 / _ERROR_PAUSE_SECONDS = 60 names
  - cancel_all_orders intent + dry-run shortcut

NEW v2:
  - strategy_id field on Quote so plan 04-05/04-06/04-07 hypothetical-fill
    ledgers route to the right per-strategy JSONL file (DEC-020 v2)
  - batched DELETE for cancel_all_orders (2 tokens/order budget) per
    RESEARCH §"Pattern 2" rate-budget note
  - aiohttp instead of sync requests (Phase 03 went async-native)
  - cryptography RSA-PSS instead of KalshiClient SDK (skip per RESEARCH
    §"Standard Stack" Alternatives Considered)

Source: REQ-kalshi-order-manager / DEC-013 / RESEARCH §"Pattern 2".
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Literal

import aiohttp
from cryptography.hazmat.primitives.asymmetric import rsa

from src.config.constants import KALSHI_BASE_URL
from src.quoting.kalshi_auth import sign_request

StrategyId = Literal["MM_BETWEEN_ROUND", "DIRECTIONAL_TAKE", "POST_PLANT_QUOTE"]


@dataclass(slots=True)
class Quote:
    """One resting limit order — Phase 04 v2 surface.

    Salvaged shape from reference/market_maker.py:36-46 with strategy_id
    added (DEC-020 v2 — fills ledger routing).
    """
    ticker: str
    side: Literal["yes", "no"]
    action: Literal["buy", "sell"]
    price: int                           # cents 1-99
    count: int
    strategy_id: StrategyId              # NEW v2 — required for fill-ledger routing
    order_id: str | None = None
    placed_at: float | None = None
    client_order_id: str | None = None   # uuid4 hex; generated at place time if None


_MAX_ERRORS_BEFORE_PAUSE: int = 3
"""Salvaged from reference/market_maker.py:73. Triggers kill_switch_api_error."""


class KalshiOrderManager:
    """Async Kalshi REST + dry-run wrapper for order placement / cancellation.

    Single source of truth for the dry-run wrapper (DEC-022 / CLAUDE.md
    rule 13). Mode-specific quoters (MM, DIRECTIONAL, POST_PLANT) consume
    this single class; they do NOT each implement their own dry-run
    shortcut.
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        key_id: str,
        private_key: rsa.RSAPrivateKey,
        *,
        dry_run: bool,
    ) -> None:
        self._session = session
        self._key_id = key_id
        self._private_key = private_key
        self._dry_run = dry_run
        self._active_quotes: dict[str, dict[str, Quote]] = {}
        self._error_streak: int = 0

    @property
    def active_quotes(self) -> dict[str, dict[str, Quote]]:
        """Read-only view; mutation only via place/cancel methods."""
        return self._active_quotes

    @property
    def error_streak(self) -> int:
        return self._error_streak

    @property
    def dry_run(self) -> bool:
        return self._dry_run

    async def place_quote(self, quote: Quote) -> bool:
        """Place a limit order; track in _active_quotes on success.

        In dry-run: assigns DRY_<uuid8> order_id, records placed_at, returns True.
        In live: signs and POSTs /portfolio/orders, sets order_id from response.
        On 4xx/5xx: increments _error_streak and returns False.
        """
        client_oid = quote.client_order_id or uuid.uuid4().hex
        quote.client_order_id = client_oid

        if self._dry_run:
            quote.order_id = f"DRY_{client_oid[:8]}"
            quote.placed_at = time.time()
            self._active_quotes.setdefault(quote.ticker, {})
            leg_key = f"{quote.action}_{quote.side}"
            self._active_quotes[quote.ticker][leg_key] = quote
            return True

        body: dict[str, object] = {
            "ticker": quote.ticker,
            "side": quote.side,
            "action": quote.action,
            "count": quote.count,
            "yes_price": quote.price if quote.side == "yes" else None,
            "no_price": quote.price if quote.side == "no" else None,
            "client_order_id": client_oid,
            "post_only": True,
            "time_in_force": "good_till_canceled",
        }
        path = "/trade-api/v2/portfolio/orders"
        headers = sign_request(self._key_id, self._private_key, "POST", path)
        try:
            async with self._session.post(
                KALSHI_BASE_URL + "/portfolio/orders",
                json=body,
                headers=headers,
            ) as r:
                if r.status == 201:
                    data = await r.json()
                    quote.order_id = data["order"]["order_id"]
                    quote.placed_at = time.time()
                    self._active_quotes.setdefault(quote.ticker, {})
                    leg_key = f"{quote.action}_{quote.side}"
                    self._active_quotes[quote.ticker][leg_key] = quote
                    self._error_streak = 0
                    return True
                self._error_streak += 1
                return False
        except aiohttp.ClientError:
            self._error_streak += 1
            return False

    async def cancel_quote(self, ticker: str, leg_key: str) -> bool:
        """Cancel one resting quote. Plan 04-08 reconciliation calls this for ghosts."""
        legs = self._active_quotes.get(ticker, {})
        quote = legs.get(leg_key)
        if quote is None or quote.order_id is None:
            return False

        if self._dry_run:
            del legs[leg_key]
            if not legs:
                del self._active_quotes[ticker]
            return True

        path = f"/trade-api/v2/portfolio/orders/{quote.order_id}"
        headers = sign_request(self._key_id, self._private_key, "DELETE", path)
        try:
            async with self._session.delete(
                KALSHI_BASE_URL + f"/portfolio/orders/{quote.order_id}",
                headers=headers,
            ) as r:
                success = r.status in (200, 204)
                if success:
                    del legs[leg_key]
                    if not legs:
                        del self._active_quotes[ticker]
                else:
                    self._error_streak += 1
                return success
        except aiohttp.ClientError:
            self._error_streak += 1
            return False

    async def cancel_all_orders(self) -> None:
        """Batch-cancel every resting order. Used by kill switches and POST_PLANT_QUOTE.

        Live path uses DELETE /portfolio/orders/batched (2 tokens/order vs
        10/order individual) per RESEARCH §"Pattern 2" rate-budget note.
        """
        order_ids = [
            q.order_id for legs in self._active_quotes.values() for q in legs.values()
            if q.order_id
        ]
        if not order_ids:
            return

        if self._dry_run:
            self._active_quotes.clear()
            return

        body = {"order_ids": order_ids}
        path = "/trade-api/v2/portfolio/orders/batched"
        headers = sign_request(self._key_id, self._private_key, "DELETE", path)
        try:
            async with self._session.delete(
                KALSHI_BASE_URL + "/portfolio/orders/batched",
                json=body,
                headers=headers,
            ) as r:
                if r.status not in (200, 204):
                    self._error_streak += 1
        except aiohttp.ClientError:
            self._error_streak += 1
        finally:
            # Clear local state EVEN on cancel failure (Pitfall 4 — cancel_all
            # that swallows network errors leaves us believing we are flat
            # while resting orders still exist; downstream API-error kill
            # switch trip + reconciliation will surface the divergence).
            self._active_quotes.clear()
