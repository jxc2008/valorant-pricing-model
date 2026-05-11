"""MarketQuote + MarketDataSource Protocol (REQ-kalshi-order-manager market-data
arm).

Two implementations:
  - SyntheticMarketData: dry-run / test backend; quotes injected via push().
    Default for Phase 04 paper-trade; the dev .env doesn't have KALSHI_KEY_PATH
    populated and the WS path requires it.
  - KalshiWsMarketData: live backend; subscribes to orderbook_delta + ticker
    channels per Kalshi docs. Skeleton in this plan; full WS book maintenance
    is operator-gated (operator gate 2 + Phase 6 deployment work).

Source: RESEARCH §"Architecture Patterns" Pattern 2 + §"Code Examples" Kalshi
WS subscribe + §"Open Questions" #3 SyntheticMarketData/KalshiWsMarketData
split.

Pitfall 7 mitigation: on WS disconnect, the KalshiWsMarketData implementation
flips is_valid=False on cached MarketQuotes; mode-selector kill_switch_active
treats is_valid=False as a synthetic kill-switch trip (plan 04-03 wires this).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from cryptography.hazmat.primitives.asymmetric import rsa


@dataclass(frozen=True, slots=True)
class MarketQuote:
    """Snapshot of one Kalshi market's top-of-book.

    Cents-encoded per Kalshi convention. `is_valid=False` signals stale book
    (e.g., during WS reconnect — Pitfall 7); kill_switch_active in plan 04-03
    treats this as a trip.
    """

    yes_bid: int          # cents 1-99
    yes_ask: int          # cents 1-99
    mid: int              # int((yes_bid + yes_ask) / 2)
    spread: int           # yes_ask - yes_bid
    is_valid: bool
    last_updated_ts: float


def make_quote(yes_bid: int, yes_ask: int, *, is_valid: bool = True) -> MarketQuote:
    """Convenience constructor; auto-computes mid + spread."""
    return MarketQuote(
        yes_bid=yes_bid,
        yes_ask=yes_ask,
        mid=(yes_bid + yes_ask) // 2,
        spread=yes_ask - yes_bid,
        is_valid=is_valid,
        last_updated_ts=time.time(),
    )


@runtime_checkable
class MarketDataSource(Protocol):
    """Structural protocol every market-data backend satisfies.

    Consumers (mode-selector, quoters, kill switches) call .latest(ticker);
    backends call .run() once at startup to enter their event loop (no-op for
    SyntheticMarketData, WS subscribe + book loop for KalshiWsMarketData).
    """

    def latest(self, ticker: str) -> MarketQuote | None: ...
    async def run(self) -> None: ...


@dataclass
class SyntheticMarketData:
    """In-memory MarketDataSource for dry-run + tests.

    Quoters retrieve quotes via .latest(); test fixtures (or live state-engine
    handlers) inject quotes via .push().
    """

    _quotes: dict[str, MarketQuote] = field(default_factory=dict)

    def push(self, ticker: str, quote: MarketQuote) -> None:
        self._quotes[ticker] = quote

    def latest(self, ticker: str) -> MarketQuote | None:
        return self._quotes.get(ticker)

    async def run(self) -> None:
        """No-op event loop; keeps the protocol surface uniform."""
        return None


class KalshiWsMarketData:
    """Live Kalshi WebSocket market-data backend.

    SKELETON — full WS connect + subscribe + book maintenance is operator-gated
    (the dev .env doesn't have KALSHI_KEY_PATH; the smoke test in
    scripts/kalshi_auth_smoke.py exercises the auth path independently).

    Pitfall 7: on WS disconnect handler, set every cached MarketQuote.is_valid
    to False; resume only after the next FULL book arrives via the
    orderbook_delta `snapshot` message.
    """

    def __init__(
        self,
        key_id: str,
        private_key: rsa.RSAPrivateKey,
        *,
        dry_run: bool,
    ) -> None:
        self._key_id = key_id
        self._private_key = private_key
        self._dry_run = dry_run
        self._quotes: dict[str, MarketQuote] = {}
        self._connected = False

    def latest(self, ticker: str) -> MarketQuote | None:
        return self._quotes.get(ticker)

    async def run(self) -> None:
        """WS connect + subscribe + book maintenance loop.

        SKELETON — operator gate 2 (RESEARCH Pitfall 8) covers auth; the full
        WS implementation is Phase 6 deployment work. For Phase 04 paper-trade,
        SyntheticMarketData is the default.
        """
        if self._dry_run:
            return None
        raise NotImplementedError(
            "KalshiWsMarketData.run live path is operator-gated; ship in Phase 6 "
            "deployment work after operator-gate-2 smoke test passes."
        )

    def mark_invalid(self) -> None:
        """Flip every cached quote's is_valid to False (Pitfall 7 disconnect path)."""
        for ticker, q in list(self._quotes.items()):
            self._quotes[ticker] = MarketQuote(
                yes_bid=q.yes_bid,
                yes_ask=q.yes_ask,
                mid=q.mid,
                spread=q.spread,
                is_valid=False,
                last_updated_ts=q.last_updated_ts,
            )
