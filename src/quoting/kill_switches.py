"""Four DEC-005 kill switches as pure predicates + KillSwitchAggregator.

DEC-005: all four ALWAYS-ON, NO per-switch off-switch flag (CLAUDE.md CRule 9).
If any switch is too sensitive, recalibrate the threshold in
``src/config/constants.py`` — do NOT add a per-switch bool knob.

The fifth predicate (``kill_switch_market_invalid``) implements RESEARCH
Pitfall 7 — the WS reconnect path leaves ``MarketQuote.is_valid=False`` until
the next FULL book arrives; mode-selector rule 1 must return IDLE during the
gap. Not in DEC-005 (which lists the four-switch baseline) but is implied by
PRD §5.4's intent: "stop trading when the market data is unreliable".

Boundary semantics
------------------
Every threshold-style kill switch trips on STRICT inequality
(``> threshold``, never ``>= threshold``). CLAUDE.md "Domain constants" /
PRD §5.4 state the thresholds; off-by-one would either spam Phase 5
paper-trade with spurious trips or miss real bugs.

Exception: ``kill_switch_api_error`` uses ``>=`` because the threshold encodes
"consecutive errors at trip time" — ``error_streak == 3`` means three errors
in a row, which is exactly the trip point (salvaged from
``reference/market_maker.py:73`` ``_MAX_ERRORS_BEFORE_PAUSE = 3``).

Pitfall 4 contract
------------------
The rolling-Brier deque MUST NOT receive scores from rounds where the bot
was IDLE (RESEARCH §"Common Pitfalls" anti-pattern 4). The aggregator's
``recent_briers`` is populated by plan 04-08 reconciliation AFTER round
resolution AND when the bot was actively quoting (mode != IDLE). This module
ASSUMES the deque is correctly maintained — ``kill_switch_brier`` is a pure
predicate over the deque contents.

Sources
-------
- ``prd.md`` §5.4 ("kill switches always-on")
- ``CLAUDE.md`` CRule 9 / "Domain constants" KILL_SWITCH_* block
- DEC-005 (four-switch baseline)
- ``.planning/phases/04-quoting-layer/04-RESEARCH.md`` §"Pattern 3"
  (predicate-style kill switches with aggregator) + Pitfall 7 (WS reconnect)
"""
from __future__ import annotations

import math
import time
from collections import deque

from src.config.constants import (
    KILL_SWITCH_BRIER_BOUND,
    KILL_SWITCH_BRIER_WINDOW,
    KILL_SWITCH_DEVIATION_C,
    KILL_SWITCH_STALENESS_S,
)
from src.pricing.data import TheoOutput
from src.quoting.market_data import MarketQuote
from src.state.match_state import MatchState

_DEFAULT_API_ERROR_THRESHOLD: int = 3
"""Salvaged from ``reference/market_maker.py:73`` (``_MAX_ERRORS_BEFORE_PAUSE``).

Three consecutive Kalshi API errors trip the API kill switch. The threshold is
exposed as a parameter on ``kill_switch_api_error`` for testability and future
recalibration; production callers use the default.
"""


def kill_switch_staleness(state: MatchState, *, now: float | None = None) -> bool:
    """Trip when ``state.last_updated_ts`` is older than ``KILL_SWITCH_STALENESS_S``.

    ``now`` injected for testability; production passes ``None`` and uses
    ``time.time()``. Strict inequality per PRD §5.4 ("ingestion staleness > 5s").
    """
    n = now if now is not None else time.time()
    return (n - state.last_updated_ts) > KILL_SWITCH_STALENESS_S


def kill_switch_deviation(theo: TheoOutput, market: MarketQuote) -> bool:
    """Trip when ``|theo_cents - market.mid| > KILL_SWITCH_DEVIATION_C`` cents.

    Strict inequality per PRD §5.4 ("|theo - market| > 20¢"). ``theo_series`` is
    a probability in ``[0.01, 0.99]``; converting to cents via ``round(p * 100)``
    matches Kalshi's integer-cents convention.
    """
    theo_c = round(theo.theo_series * 100)
    return abs(theo_c - market.mid) > KILL_SWITCH_DEVIATION_C


def kill_switch_brier(recent_briers: deque[float]) -> bool:
    """Trip when window is full AND mean > ``KILL_SWITCH_BRIER_BOUND``.

    Returns ``False`` until the window is full (avoids early false positives
    on the first ``KILL_SWITCH_BRIER_WINDOW - 1`` predictions). Strict
    inequality per PRD §5.4 ("rolling Brier > 0.30").

    Pitfall 4 (RESEARCH): the deque must be populated only with rounds where
    mode != IDLE. This predicate does NOT validate that contract — it ASSUMES
    the deque is correctly maintained by plan 04-08 reconciliation.

    Implementation note: uses ``math.fsum`` (Shewchuk pairwise summation)
    instead of builtin ``sum`` to avoid IEEE 754 accumulation drift. With
    naive ``sum``, 50 copies of ``0.30`` accumulate to ``0.30000000000000027``,
    which would spuriously trip the strict-inequality boundary. ``math.fsum``
    sums to exact rounded result (50 * 0.30 / 50 == 0.30 exactly).
    """
    if len(recent_briers) < KILL_SWITCH_BRIER_WINDOW:
        return False
    return (math.fsum(recent_briers) / len(recent_briers)) > KILL_SWITCH_BRIER_BOUND


def kill_switch_api_error(
    error_streak: int,
    threshold: int = _DEFAULT_API_ERROR_THRESHOLD,
) -> bool:
    """Trip when consecutive API errors ``>= threshold`` (default 3).

    Salvaged from ``reference/market_maker.py:73`` (``_MAX_ERRORS_BEFORE_PAUSE = 3``).
    Note non-strict inequality (``>=``) — ``error_streak == 3`` means three errors
    in a row, which is exactly the trip point per PRD §5.4 / DEC-005 #a.

    ``KalshiOrderManager.error_streak`` (Plan 04-01) is the production source.
    """
    return error_streak >= threshold


def kill_switch_market_invalid(market: MarketQuote) -> bool:
    """Trip when ``MarketQuote.is_valid`` is ``False`` (Pitfall 7 WS reconnect path).

    Not in DEC-005's four-switch baseline, but is implied by PRD §5.4's intent:
    "stop trading when the market data is unreliable". Mode-selector rule 1
    returns IDLE during WS reconnect via this trip.
    """
    return not market.is_valid


class KillSwitchAggregator:
    """Owns the rolling-Brier deque; aggregates the 5 predicates.

    Single instance per bot process. The bot main loop calls
    ``.any_tripped(...)`` after every theo computation (RESEARCH §"User
    Constraints" — kill-switch evaluation cadence is "every theo computation");
    ANY trip fires ``KalshiOrderManager.cancel_all_orders`` (plan 04-08 wires
    the cancel-all callback in the e2e test).

    ``recent_briers`` is exposed as a public attribute so plan 04-08
    reconciliation can append Brier scores after round resolution (when mode
    != IDLE — see Pitfall 4 contract above).
    """

    def __init__(self) -> None:
        self.recent_briers: deque[float] = deque(maxlen=KILL_SWITCH_BRIER_WINDOW)

    def any_tripped(
        self,
        state: MatchState,
        theo: TheoOutput,
        market: MarketQuote,
        error_streak: int,
    ) -> tuple[bool, list[str]]:
        """Return ``(any_tripped, sorted_names_of_tripped_switches)``.

        Sorted name list keeps log lines stable across Python runs (set
        iteration is non-deterministic per Phase 03 D-08 carry-forward).
        Possible names: ``"api_error"``, ``"brier"``, ``"deviation"``,
        ``"market_invalid"``, ``"staleness"``.
        """
        tripped: list[str] = []
        if kill_switch_staleness(state):
            tripped.append("staleness")
        if kill_switch_deviation(theo, market):
            tripped.append("deviation")
        if kill_switch_brier(self.recent_briers):
            tripped.append("brier")
        if kill_switch_api_error(error_streak):
            tripped.append("api_error")
        if kill_switch_market_invalid(market):
            tripped.append("market_invalid")
        return (bool(tripped), sorted(tripped))
