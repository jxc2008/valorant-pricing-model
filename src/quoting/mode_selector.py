"""Pure-function mode selector — REQ-mode-selector v2 (DEC-001 v2).

Six rules in declared order; literal source-code order IS the priority.
DO NOT use match statements, dict dispatch, or "highest priority wins"
tables — RESEARCH Pitfall 3 demands a sequence of ``if ... return ...``
statements so the priority is grep-discoverable.

The function is PURE: same inputs always produce the same output. No I/O,
no hidden state, no class members. The caller passes the kill-switch
result (KillSwitchAggregator.any_tripped()[0]) explicitly so this module
doesn't need to know how kill switches are evaluated.

MM_BETWEEN_ROUND and DIRECTIONAL_TAKE are FIRST-CLASS PEERS per PRD §2.1
v2 — the "DIRECTIONAL evaluated before MM" ordering is a tie-break, not a
priority ranking. Paper trade decides which (or both) survives via the
fill-count gate (DEC-020 v2).

VEGA_DIRECTIONAL_THRESHOLD from v1 is REMOVED (DEC-018 v2) — DIRECTIONAL_TAKE
triggers on ``|theo - market_mid|``, not vega magnitude.

Source: PRD §2.1 / DEC-001 v2 / ROADMAP §4.2 / RESEARCH §"Pattern 1" + Pitfall 3.
"""
from __future__ import annotations

from typing import Literal

from src.config.constants import MM_MIN_EDGE, TAKE_THRESHOLD
from src.pricing.data import TheoOutput
from src.quoting.market_data import MarketQuote
from src.state.match_state import MatchState

TradingMode = Literal[
    "MM_BETWEEN_ROUND",
    "DIRECTIONAL_TAKE",
    "POST_PLANT_QUOTE",
    "IDLE",
]


def trading_mode(
    state: MatchState,
    theo: TheoOutput,
    market: MarketQuote,
    vega_between: float,
    vega_post_plant: float,
    kill_switch_active: bool,
) -> TradingMode:
    """Return the trading mode for the current (state, theo, market) triple.

    Rules (literal source-code order is priority — RESEARCH Pitfall 3):
        1. kill_switch_active → IDLE
        2. state.bomb_planted → POST_PLANT_QUOTE
        3. mid-round and not bomb_planted → IDLE
        4. |theo - market_mid| > TAKE_THRESHOLD → DIRECTIONAL_TAKE
        5. market.spread > MM_MIN_EDGE → MM_BETWEEN_ROUND
        6. fall-through → IDLE

    Args:
        vega_between: theo.vega (= vega_between_round per DEC-018 D-10/D-11).
            Reserved for the MM_BETWEEN_ROUND quoter; selector currently does
            not use it for routing (DEC-001 v2 routes on |theo - mid| /
            spread, not vega).
        vega_post_plant: variance over {kill, defuse, time-out} outcomes
            computed via compute_vega_post_plant. Reserved for the
            POST_PLANT_QUOTE quoter; selector does not use it for routing.
    """
    del vega_between, vega_post_plant  # reserved for downstream quoter consumption

    # Rule 1: kill-switch dominates everything else.
    if kill_switch_active:
        return "IDLE"

    # Rule 2: bomb-planted → POST_PLANT branch (latency-critical 200ms budget).
    if state.bomb_planted:
        return "POST_PLANT_QUOTE"

    # Rule 3: mid-round-not-planted → IDLE (no general mid-round path per DEC-007 v2).
    if _is_mid_round(state) and not state.bomb_planted:
        return "IDLE"

    # Rules 4 & 5: between-round — DIRECTIONAL evaluated BEFORE MM (declared order).
    theo_cents = round(theo.theo_series * 100)
    if abs(theo_cents - market.mid) > TAKE_THRESHOLD:
        return "DIRECTIONAL_TAKE"
    if market.spread > MM_MIN_EDGE:
        return "MM_BETWEEN_ROUND"

    # Rule 6: fall-through.
    return "IDLE"


def _is_mid_round(state: MatchState) -> bool:
    """Mid-round means a round is in progress with the timer running.

    Phase 03 D-14 carry-forward: state.time_left_s is None except when
    bomb_planted=True OR a separate timer source has populated it. For
    Phase 04 we treat ``time_left_s is not None`` as the mid-round signal.
    Phase 5 calibration may refine if false-positives prove material.

    NOTE — when bomb_planted=True, both attackers_alive/defenders_alive AND
    time_left_s are populated, but rule 2 (state.bomb_planted) fires first
    and routes to POST_PLANT_QUOTE before this helper is reached.
    """
    return state.time_left_s is not None
