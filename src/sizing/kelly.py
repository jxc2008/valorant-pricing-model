"""Portfolio-aware half-Kelly sizer (DEC-023 v2 / REQ-kelly-sizer).

Pure function. Caller owns ``current_series_exposure: dict[str, float]``; this
module does NOT mutate it. The PortfolioState registry at
``src/quoting/portfolio.py`` owns the mutable dict and exposes a
``snapshot()`` method that returns the dict copy this function consumes.

Three caps applied in order (DEC-023 v2 verbatim formula):

    1. Half-Kelly:                f = max(0, KELLY_MULTIPLIER * f_full)
    2. Per-market cap:            f = min(f, PER_MARKET_CAP_FRAC)         # 0.05
    3. Per-series aggregate cap:  f = min(f, headroom)                    # 0.10 - exposure[s]

Returns 0 if any cap binds the fraction to 0.

Source: PRD §2.3 + ROADMAP §4.6 + DEC-004 + DEC-023 v2 + RESEARCH §"Code
Examples" "Portfolio Kelly with per-series aggregate cap (DEC-023 v2)"
verbatim block. Pitfall 5 mitigation: this function does NOT touch exposure
tracking; the caller must invoke ``PortfolioState.on_place`` at placement
and ``on_settle`` at round resolution (plan 04-08 wires the latter).
"""
from __future__ import annotations

from src.config.constants import (
    KELLY_MULTIPLIER,
    PER_MARKET_CAP_FRAC,
    SERIES_AGGREGATE_CAP_FRAC,
)


def kelly_size(
    theo: float,
    market_yes_ask: int,
    bankroll: int,
    series_id: str,
    current_series_exposure: dict[str, float],
) -> int:
    """Return contract count to YES-buy at ``market_yes_ask`` cents.

    Args:
        theo: ``P(YES wins)`` in [0, 1].
        market_yes_ask: Kalshi YES ask, cents 1-99.
        bankroll: Available bankroll in cents.
        series_id: Stable string identifier for the series (e.g., Kalshi event
            ticker root). All correlated markets within a series (moneyline +
            map handicaps + round handicaps) share the id.
        current_series_exposure: Snapshot of ``{series_id -> fractional exposure}``.
            NOT mutated. Owned by caller (``PortfolioState.snapshot()``).

    Returns:
        Integer contract count. 0 if any cap binds OR if ``theo <= ask/100``
        OR if ``market_yes_ask`` / ``bankroll`` is at a degenerate boundary.

    Acceptance per REQ-kelly-sizer (v2 portfolio-aware):
        - Identical to v1 single-market case when ``exposure == {}`` or 0
          (preserves DEC-004 backward compatibility).
        - Aggregate cap binds when
          ``exposure[series_id] >= SERIES_AGGREGATE_CAP_FRAC``.
        - Never returns full-Kelly sizing
          (``f`` always ``<= KELLY_MULTIPLIER * f_full``).
    """
    # Boundary guards — degenerate ask values can't produce a real Kelly fraction.
    if market_yes_ask <= 0 or market_yes_ask >= 100:
        return 0
    if bankroll <= 0:
        return 0

    ask = market_yes_ask / 100.0
    p = theo
    q = 1.0 - p
    b = (1.0 - ask) / ask

    f_full = (b * p - q) / b
    f = max(0.0, KELLY_MULTIPLIER * f_full)        # half-Kelly per DEC-004
    f = min(f, PER_MARKET_CAP_FRAC)                # per-market cap (0.05)

    # DEC-023 v2: per-series aggregate cap layered on top.
    headroom = max(
        0.0,
        SERIES_AGGREGATE_CAP_FRAC - current_series_exposure.get(series_id, 0.0),
    )
    f = min(f, headroom)

    if f == 0.0:
        return 0
    return int(f * bankroll / market_yes_ask)
