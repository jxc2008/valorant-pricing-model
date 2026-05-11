"""MM_BETWEEN_ROUND quoter — REQ-mm-quoter v2 (DEC-018 v2 first arm).

Active only when trading_mode == "MM_BETWEEN_ROUND" (plan 04-04 rule 5).
Quotes at theo +/- compute_half_spread(...) via KalshiOrderManager from plan
04-01. Hypothetical fills routed to data/fills/{match_id}.mm_between_round.jsonl
via fill_ledger.maybe_record_mm_fill (plan 04-05 task 1) — first-class peer
to DIRECTIONAL_TAKE per DEC-020 v2.

Half-spread formula (DEC-018 v2 + RESEARCH Pitfall 4):
    base = max(MIN_HALF_SPREAD, MM_VEGA_SPREAD_K * sqrt(vega_between))
    penalty = max(0, floor(staleness_s - 2.0))            # 1c/s above 2s
    hs = base + penalty

MIN_HALF_SPREAD = 3 (cents) MUST beat Kalshi maker fee + slippage budget:
  - Kalshi maker fee at theo=50c: ceil(0.035 * 0.5 * 0.5 * 100) / 100 = 0.88c
  - Kalshi taker fee at theo=50c: ceil(0.07 * 0.5 * 0.5 * 100) / 100  = 1.75c
  - We quote post_only=True (maker intent), so we mostly earn the 0.88c
    delta; 3c half-spread - 0.88c maker fee = 2.12c net of fees if theo
    is exact. Covers a 1c model slippage budget AND ~1c arbiter
    staleness slippage budget.
Property test (test_spread_floor_beats_fee) enforces this invariant
hypothesis-style across the Kalshi fee curve.

Staleness handling (PRD §5.4):
    state.last_updated_ts older than 2s -> widen by 1c/s incremental.
    state.last_updated_ts older than 5s -> kill_switch_staleness trips (plan
    04-03); 04-08's cancel-all-on-trip path clears the book entirely. This
    quoter does NOT need to handle the 5s pull case directly — kill switch
    aggregator owns it.

Source: PRD §5.4 / DEC-001 v2 / DEC-018 v2 / ROADMAP §4.3 / RESEARCH
§"Pattern 4" + Pitfall 4.
"""
from __future__ import annotations

import math
import time

from src.config.constants import MIN_HALF_SPREAD, MM_VEGA_SPREAD_K
from src.pricing.data import TheoOutput
from src.quoting.market_data import MarketQuote
from src.quoting.order_manager import KalshiOrderManager, Quote
from src.state.match_state import MatchState

_STALENESS_PENALTY_FLOOR_S: float = 2.0
"""Staleness threshold (seconds) above which we ADD widening cents.

PRD §5.4: "time_since_last_state_update > 2s -> widen or pull". Phase 04
ships the widen branch; the pull-at-5s branch is plan 04-03's
kill_switch_staleness (and plan 04-08's cancel-all-on-trip handler).
"""


def compute_half_spread(
    vega_between: float,
    staleness_s: float,
) -> int:
    """Return MM half-spread in cents per DEC-018 v2 formula.

    Args:
        vega_between: TheoOutput.vega from Phase 1 (= vega_between_round).
        staleness_s: time.time() - state.last_updated_ts.

    Returns:
        Integer cents >= MIN_HALF_SPREAD. Floor invariant verified by
        property test (test_spread_floor_invariant + test_spread_floor_beats_fee).

    The vega contribution is `ceil(MM_VEGA_SPREAD_K * sqrt(vega_between))`
    — ceiling avoids the 1c off-by-one where a vega-driven spread of 3.01c
    would round down to 3c and tie the floor exactly (defensive: prefer to
    quote wider than too narrow when fee curve is the binding constraint).
    """
    if vega_between < 0.0:
        vega_between = 0.0  # defensive — negative vega is a programming error
    vega_cents = math.ceil(MM_VEGA_SPREAD_K * math.sqrt(vega_between))
    base = max(MIN_HALF_SPREAD, vega_cents)
    penalty = max(0, int(math.floor(staleness_s - _STALENESS_PENALTY_FLOOR_S)))
    return base + penalty


async def quote_mm_between_round(
    state: MatchState,
    theo: TheoOutput,
    market: MarketQuote,
    mgr: KalshiOrderManager,
    ticker: str,
    count: int,
    *,
    now: float | None = None,
) -> None:
    """Quote MM_BETWEEN_ROUND ladder (yes-buy at theo_c - hs, yes-sell at theo_c + hs).

    Idempotent: if quotes already exist at the correct prices AND are < 2s
    old, do nothing (avoid burning rate budget on identical replacements).
    On stale-or-mispriced quotes, cancel then place fresh.

    Boundary guards: if theo is near 0.01 or 0.99, the resulting bid/ask
    can fall outside [1, 99] — skip placement entirely (defensive; the
    market would also be near-degenerate at those theos and MM_MIN_EDGE
    likely fails rule 5 of the mode selector anyway).

    Note: `market` is reserved for downstream use (post-cancel re-evaluation,
    market-spread-aware sizing in Phase 5). The MM quoter's spread is
    theo-centered, not market-centered, so `market` is not consumed in the
    current placement path; included in the signature for the stable
    contract per plan 04-08 reconciliation requirements.
    """
    del market  # reserved for downstream consumers (Phase 5 market-aware sizing)
    n = now if now is not None else time.time()
    staleness_s = max(0.0, n - state.last_updated_ts)
    hs = compute_half_spread(theo.vega, staleness_s)
    theo_c = round(theo.theo_series * 100)
    buy_price = theo_c - hs
    sell_price = theo_c + hs

    # Boundary guard: Kalshi cents must be in [1, 99].
    if buy_price < 1 or sell_price > 99:
        return

    existing = mgr.active_quotes.get(ticker, {})
    buy_quote = existing.get("buy_yes")
    sell_quote = existing.get("sell_yes")

    # Cancel stale or mispriced quotes BEFORE placing fresh (per RESEARCH
    # Pattern 2 — cancel-and-replace is simpler than amend-order).
    if buy_quote is not None:
        age = n - (buy_quote.placed_at or 0.0)
        if buy_quote.price != buy_price or age > _STALENESS_PENALTY_FLOOR_S:
            await mgr.cancel_quote(ticker, "buy_yes")
            buy_quote = None
    if sell_quote is not None:
        age = n - (sell_quote.placed_at or 0.0)
        if sell_quote.price != sell_price or age > _STALENESS_PENALTY_FLOOR_S:
            await mgr.cancel_quote(ticker, "sell_yes")
            sell_quote = None

    # Place fresh quotes if missing (idempotent — no-op if cancel was no-op
    # AND existing quote price matched).
    if buy_quote is None:
        await mgr.place_quote(Quote(
            ticker=ticker,
            side="yes",
            action="buy",
            price=buy_price,
            count=count,
            strategy_id="MM_BETWEEN_ROUND",
        ))
    if sell_quote is None:
        await mgr.place_quote(Quote(
            ticker=ticker,
            side="yes",
            action="sell",
            price=sell_price,
            count=count,
            strategy_id="MM_BETWEEN_ROUND",
        ))
