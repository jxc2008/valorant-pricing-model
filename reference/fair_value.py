"""
backend/fair_value.py

Fair value calculations for Kalshi VCT market making.

Two outputs:
  1. Series fair value — vig-removed probability from VLR.gg odds
  2. Map fair values   — derived from series prob via IID BO3 math

──────────────────────────────────────────────────────────────────────────────
IID BO3 series model
──────────────────────────────────────────────────────────────────────────────
If each map is won by team A with probability p (independent of all other maps):

  P(A wins 2-0)  = p²
  P(A wins 2-1)  = 2 · p · (1-p) · p   [win map 1, lose map 2, win map 3]
                   + swap order          [lose map 1, win map 2, win map 3]
                 = 2p²(1-p)

  P(A wins series) = p² + 2p²(1-p) = p²(3-2p)  ≡  S

Inverting: given S, solve  2p³ - 3p² + S = 0  on (0,1) for p.

This gives us the fair-value map win probability, which we use to quote
both Map 1 and Map 2 Kalshi markets.  (Map 3 is conditional on reaching
it, which requires a different calculation — skipped for now.)

Pick/ban adjustment (optional):
  In VCT the favorite typically picks Map 1 (their comfort map) and the
  underdog picks Map 2.  This means Map 1 is slightly more favorable for
  the series favorite and Map 2 slightly more favorable for the underdog.
  We model this with a small additive delta:
      p1 = p + delta   if team A is the series favorite
      p2 = p - delta
  Default delta = 0.04 (empirically reasonable; can be tuned).
  Pass pickban_adjust=False to use raw IID p for both maps.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ── Vig removal ───────────────────────────────────────────────────────────────

def american_to_implied(odds: int) -> float:
    """American odds → raw implied probability (includes vig)."""
    if odds < 0:
        return abs(odds) / (abs(odds) + 100)
    return 100 / (odds + 100)


def series_fair_value(team_a_odds: int, team_b_odds: int) -> float:
    """
    Convert American odds pair to a vig-free probability for team A winning.

    Args:
        team_a_odds: American odds for team A (e.g. -150)
        team_b_odds: American odds for team B (e.g. +120)

    Returns:
        Probability ∈ (0, 1) that team A wins the series.
    """
    p_a_raw = american_to_implied(team_a_odds)
    p_b_raw = american_to_implied(team_b_odds)
    total = p_a_raw + p_b_raw
    if total <= 0:
        raise ValueError(f"Invalid odds: {team_a_odds} / {team_b_odds}")
    return p_a_raw / total


# ── IID BO3 series → map probability ─────────────────────────────────────────

def _bo3_series_prob(p: float) -> float:
    """P(team A wins BO3 series) given per-map win prob p."""
    return p * p * (3 - 2 * p)


def map_prob_from_series(series_prob: float) -> float:
    """
    Solve p²(3-2p) = series_prob for p ∈ (0,1) via bisection.

    Returns:
        Per-map win probability for team A under the IID assumption.
    """
    if not (0.0 < series_prob < 1.0):
        raise ValueError(f"series_prob must be in (0,1), got {series_prob}")

    # Bisect on 2p³ - 3p² + S = 0
    lo, hi = 1e-6, 1.0 - 1e-6
    for _ in range(64):
        mid = (lo + hi) / 2
        if _bo3_series_prob(mid) < series_prob:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


# ── Combined output ───────────────────────────────────────────────────────────

PICKBAN_DELTA = 0.0    # no pick/ban adjustment — unknown who picks which map


def compute_fair_values(
    team_a_odds: int,
    team_b_odds: int,
    pickban_adjust: bool = True,
) -> dict:
    """
    Compute all fair values needed to quote series + map markets.

    Args:
        team_a_odds:    American odds for team A series win.
        team_b_odds:    American odds for team B series win.
        pickban_adjust: If True, nudge map probs by PICKBAN_DELTA to
                        reflect that each team picks their best map.

    Returns dict:
        {
            series_prob:   float,  # vig-free P(A wins series)
            map_iid_prob:  float,  # IID per-map P(A wins any map)
            map1_prob:     float,  # adjusted Map 1 fair value (A's pick)
            map2_prob:     float,  # adjusted Map 2 fair value (B's pick)
            vig_pct:       float,  # bookmaker vig percentage
        }
    """
    series_prob = series_fair_value(team_a_odds, team_b_odds)
    map_p = map_prob_from_series(series_prob)

    # Pick/ban adjustment: favorite's pick (Map 1) skews toward them;
    # underdog's pick (Map 2) skews against them.
    if pickban_adjust:
        if series_prob >= 0.5:
            # team A is the favorite
            map1_prob = min(0.97, map_p + PICKBAN_DELTA)
            map2_prob = max(0.03, map_p - PICKBAN_DELTA)
        else:
            # team B is the favorite, so map 1 is B's pick → bad for A
            map1_prob = max(0.03, map_p - PICKBAN_DELTA)
            map2_prob = min(0.97, map_p + PICKBAN_DELTA)
    else:
        map1_prob = map_p
        map2_prob = map_p

    # Compute vig for informational logging
    p_a_raw = american_to_implied(team_a_odds)
    p_b_raw = american_to_implied(team_b_odds)
    vig_pct = (p_a_raw + p_b_raw - 1.0) * 100

    result = {
        "series_prob": series_prob,
        "map_iid_prob": map_p,
        "map1_prob": map1_prob,
        "map2_prob": map2_prob,
        "vig_pct": vig_pct,
    }

    logger.debug(
        "fair_value: series=%.3f  iid_map=%.3f  map1=%.3f  map2=%.3f  vig=%.2f%%",
        series_prob, map_p, map1_prob, map2_prob, vig_pct,
    )
    return result


def prob_to_cents(prob: float) -> int:
    """Convert probability to Kalshi price in cents (1–99)."""
    return max(1, min(99, round(prob * 100)))


def quote_prices(
    fair_prob: float,
    half_spread_cents: int,
) -> tuple[int, int]:
    """
    Compute bid and ask prices in cents for a given fair value.

    As market maker:
      - Post a YES buy order (bid) below fair value.
      - Post a NO buy order (equivalent to YES sell/ask) above fair value.

    Args:
        fair_prob:          Fair probability ∈ (0,1).
        half_spread_cents:  Half the spread in cents (e.g. 3 → quote 3¢ each side).

    Returns:
        (yes_bid_cents, yes_ask_cents)
        yes_bid:  Price we're willing to buy YES at  (< fair)
        yes_ask:  Price we're willing to sell YES at (> fair)
    """
    mid = prob_to_cents(fair_prob)
    yes_bid = max(1,  mid - half_spread_cents)
    yes_ask = min(99, mid + half_spread_cents)
    return yes_bid, yes_ask


# ── Quick smoke test ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)-8s %(message)s")

    examples = [
        # (team_a_odds, team_b_odds, label)
        (-200, +165, "Heavy favorite -200"),
        (-130, +110, "Slight favorite -130"),
        (-110, -110, "Coin flip -110/-110"),
        (+120, -140, "Underdog +120"),
    ]

    for a_odds, b_odds, label in examples:
        fv = compute_fair_values(a_odds, b_odds)
        bid, ask = quote_prices(fv["series_prob"], half_spread_cents=3)
        print(
            f"{label}: "
            f"series={fv['series_prob']:.3f}  "
            f"iid_map={fv['map_iid_prob']:.3f}  "
            f"map1={fv['map1_prob']:.3f}  "
            f"map2={fv['map2_prob']:.3f}  "
            f"vig={fv['vig_pct']:.2f}%  "
            f"quote={bid}¢/{ask}¢"
        )
