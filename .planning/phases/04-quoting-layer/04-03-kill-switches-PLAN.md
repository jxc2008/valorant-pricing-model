---
phase: 04-quoting-layer
plan: "03"
type: execute
wave: 2
depends_on: ["00", "01"]
files_modified:
  - src/quoting/kill_switches.py
  - src/quoting/__init__.py
  - tests/quoting/test_kill_switches.py
autonomous: true
requirements:
  - REQ-kill-switches
notes: |
  Wave 2 — four pure-predicate kill switches + KillSwitchAggregator.

  DEC-005: all four ALWAYS-ON, NO per-switch disable flag. If any switch is
  too sensitive, recalibrate the threshold in src/config/constants.py — do
  NOT add a `disable_X: bool` knob.

  Predicate style satisfies DEC-005: each kill switch is a pure function
  `(state, theo, market, recent_briers) -> bool` returning True iff the switch
  trips. The aggregator collects them in a list; ANY trip fires
  KalshiOrderManager.cancel_all_orders (plan 04-08 wires the cancel-all
  callback in the e2e test).

  Boundary tests are critical. Phase 03 D-08 same-commit Rule-3 pattern: if
  the kill-switch trip points are off-by-one (e.g., trip at exactly the
  threshold vs strictly above), Phase 5 paper-trade will fire either too many
  spurious trips or miss real bugs. Each predicate gets a trip + non-trip
  boundary test in this plan.

  Pitfall 7 connector: WS reconnect path should set MarketQuote.is_valid =
  False; the kill-switch aggregator treats is_valid=False as a synthetic
  trip (so mode-selector rule 1 returns IDLE during reconnects). This plan
  ships the kill_switch_market_invalid predicate alongside the four named
  in DEC-005.

  Pitfall labelled in RESEARCH §"Common Pitfalls" anti-pattern 4: Brier
  window must NOT include rounds where mode was IDLE. The kill-switch's
  `recent_briers` deque is fed by the bot main loop AFTER a round resolves
  AND when the bot was actively quoting (mode != IDLE). Plan 04-08 wires
  this; Phase 04 ships the pure predicate that ASSUMES the deque is
  correctly populated (test fixtures populate it directly).

  Depends on plan 04-01 because the kill switches consume MarketQuote from
  src/quoting/market_data.py.

must_haves:
  truths:
    - "kill_switch_staleness(state, now=t) trips when (t - state.last_updated_ts) > KILL_SWITCH_STALENESS_S (5.0)"
    - "kill_switch_deviation(theo, market) trips when |theo*100 - market.mid| > KILL_SWITCH_DEVIATION_C (20)"
    - "kill_switch_brier(deque) trips when window is full AND mean(window) > KILL_SWITCH_BRIER_BOUND (0.30)"
    - "kill_switch_brier returns False when len(deque) < KILL_SWITCH_BRIER_WINDOW (50) — no early false positives"
    - "kill_switch_api_error(error_streak) trips when error_streak >= 3 (salvaged from reference/market_maker.py:73)"
    - "kill_switch_market_invalid(market) trips when market.is_valid is False (Pitfall 7 WS reconnect path)"
    - "KillSwitchAggregator.any_tripped(state, theo, market, error_streak) returns (bool, list[str]) where list[str] names the tripped switches"
    - "KillSwitchAggregator owns the recent_briers deque(maxlen=KILL_SWITCH_BRIER_WINDOW); the bot main loop appends after each round resolution where mode != IDLE"
    - "ANY trip causes any_tripped to return True; multiple trips return all names (for logging / alerting)"
  artifacts:
    - path: "src/quoting/kill_switches.py"
      provides: "5 pure predicates (4 from DEC-005 + 1 Pitfall 7 market_invalid) + KillSwitchAggregator"
      min_lines: 100
      contains: "KillSwitchAggregator"
    - path: "tests/quoting/test_kill_switches.py"
      provides: "10+ tests: trip + non-trip boundary per predicate + aggregator semantics"
      contains: "test_aggregator_any_tripped"
  key_links:
    - from: "src/quoting/kill_switches.py imports"
      to: "src.config.constants.KILL_SWITCH_*"
      via: "import (CRule 12 — no magic numbers)"
      pattern: "KILL_SWITCH_STALENESS_S.*KILL_SWITCH_DEVIATION_C.*KILL_SWITCH_BRIER_BOUND"
    - from: "KillSwitchAggregator.recent_briers"
      to: "plan 04-08 round-resolution event handler"
      via: "deque(maxlen=KILL_SWITCH_BRIER_WINDOW); bot loop appends Brier scores after resolution"
      pattern: "deque"
    - from: "kill_switch_market_invalid"
      to: "src/quoting/market_data.MarketQuote.is_valid (set False on WS disconnect)"
      via: "Pitfall 7 propagation"
      pattern: "is_valid"
---

<objective>
Build the four DEC-005 kill switches as pure predicates plus a 5th
`kill_switch_market_invalid` (Pitfall 7) and the `KillSwitchAggregator`
that any_tripped()s them on every theo computation. The aggregator owns
the rolling-Brier deque (plan 04-08 appends to it after round resolution
when mode != IDLE — Pitfall 4 in RESEARCH).

Purpose: REQ-kill-switches. Single-purpose, grep-discoverable, unit-testable
risk controls. ANY trip cancels every resting quote (KalshiOrderManager
cancel_all_orders — plan 04-08 wires the cancel callback when it composes
the full pipe).

Output: src/quoting/kill_switches.py + GREEN test_kill_switches.py
(10+ tests covering trip + non-trip boundaries for each predicate +
aggregator semantics).
</objective>

<execution_context>
@C:/Users/Joseph Cheng/.claude/get-shit-done/workflows/execute-plan.md
@C:/Users/Joseph Cheng/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/phases/04-quoting-layer/04-RESEARCH.md
@src/config/constants.py
@src/state/match_state.py
@src/pricing/data.py

<interfaces>
<!-- Phase 03 contracts -->
From src/state/match_state.py:
```python
@dataclass(frozen=True, slots=True)
class MatchState:
    # ... 19 fields total. kill_switch_staleness consumes:
    last_updated_ts: float                          # set by with_update via time.time()
```

From src/pricing/data.py:
```python
@dataclass(frozen=True, slots=True)
class TheoOutput:
    theo_series: float                              # P(team A wins series), [0.01, 0.99]
    theo_map: tuple[float, ...]
    vega: float
    confidence: float
```

<!-- Plan 04-01 surface this plan consumes -->
From src/quoting/market_data.py:
```python
@dataclass(frozen=True, slots=True)
class MarketQuote:
    yes_bid: int
    yes_ask: int
    mid: int                                         # cents
    spread: int
    is_valid: bool                                   # False during WS reconnect (Pitfall 7)
    last_updated_ts: float
```

<!-- Phase 04 constants from plan 04-00 -->
From src/config/constants.py:
```python
KILL_SWITCH_STALENESS_S: Final[float] = 5.0
KILL_SWITCH_DEVIATION_C: Final[int] = 20
KILL_SWITCH_BRIER_BOUND: Final[float] = 0.30
KILL_SWITCH_BRIER_WINDOW: Final[int] = 50
```

<!-- New surfaces this plan creates -->
NEW src/quoting/kill_switches.py public surface:
```python
def kill_switch_staleness(state: MatchState, *, now: float | None = None) -> bool: ...
def kill_switch_deviation(theo: TheoOutput, market: MarketQuote) -> bool: ...
def kill_switch_brier(recent_briers: deque[float]) -> bool: ...
def kill_switch_api_error(error_streak: int, threshold: int = 3) -> bool: ...
def kill_switch_market_invalid(market: MarketQuote) -> bool: ...

class KillSwitchAggregator:
    recent_briers: deque[float]                      # maxlen = KILL_SWITCH_BRIER_WINDOW
    def any_tripped(
        self, state: MatchState, theo: TheoOutput, market: MarketQuote, error_streak: int,
    ) -> tuple[bool, list[str]]: ...
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: src/quoting/kill_switches.py + GREEN test_kill_switches.py</name>
  <files>src/quoting/kill_switches.py, src/quoting/__init__.py, tests/quoting/test_kill_switches.py</files>
  <behavior>
    - kill_switch_staleness(state with last_updated_ts=t) returns True when (now - t) > 5.0 (strictly greater)
    - kill_switch_staleness returns False when (now - t) == 5.0 exactly (boundary — strict inequality per CLAUDE.md "ingestion staleness > 5s")
    - kill_switch_staleness returns False when (now - t) == 4.99
    - kill_switch_deviation(theo with theo_series=0.50, market with mid=70) returns True (|50 - 70| = 20, NOT > 20 — should be False; need > 20, so set theo=0.50, mid=71 -> |50-71|=21 trips)
    - kill_switch_deviation returns False when |theo*100 - mid| == 20 exactly (boundary — strict inequality per CLAUDE.md "|theo - market| > 20¢")
    - kill_switch_brier(deque of 49 zeros) returns False (window not full)
    - kill_switch_brier(deque of 50 zeros) returns False (mean=0 < 0.30)
    - kill_switch_brier(deque of 50 0.40s) returns True (mean=0.40 > 0.30)
    - kill_switch_brier(deque of 50 0.30s) returns False (mean=0.30 == 0.30 — boundary, strict inequality)
    - kill_switch_api_error(0) returns False; (3) returns True; (2) returns False
    - kill_switch_market_invalid(market with is_valid=False) returns True; True is_valid → False
    - KillSwitchAggregator() owns a deque(maxlen=50) at .recent_briers
    - any_tripped returns (False, []) when no switches trip
    - any_tripped returns (True, ["staleness"]) when only staleness trips
    - any_tripped returns (True, ["staleness", "deviation"]) (sorted by name) when multiple trip
    - any_tripped names use the constant set: "staleness", "deviation", "brier", "api_error", "market_invalid"
  </behavior>
  <action>
(A) Create src/quoting/kill_switches.py per RESEARCH §"Pattern 3" Predicate-style
    kill switches with aggregator block. Adapt the example to include the 5th
    market_invalid predicate (Pitfall 7) and import constants from
    src.config.constants:

```python
"""Four DEC-005 kill switches as pure predicates + KillSwitchAggregator.

DEC-005: all four ALWAYS-ON, NO per-switch disable flag. The fifth
predicate (kill_switch_market_invalid) implements RESEARCH Pitfall 7 —
WS reconnect path leaves MarketQuote.is_valid=False until the next FULL
book arrives; mode-selector rule 1 must return IDLE during the gap.

Boundary semantics: every kill switch trips on STRICT inequality
(`> threshold`, never `>= threshold`). CLAUDE.md "Domain constants" /
PRD §5.4 state the thresholds; off-by-one would either spam Phase 5
paper-trade with spurious trips or miss real bugs.

Pitfall 4 (RESEARCH): the rolling-Brier deque MUST NOT receive scores
from rounds where the bot was IDLE. The aggregator's recent_briers is
populated by plan 04-08 reconciliation AFTER round resolution AND when
the bot was actively quoting. This file ASSUMES the deque is correctly
maintained — kill_switch_brier is a pure predicate over the deque
contents.

Source: PRD §5.4 / DEC-005 / ROADMAP §4.7 / RESEARCH §"Pattern 3" + Pitfall 7.
"""
from __future__ import annotations

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
"""Salvaged from reference/market_maker.py:73 (_MAX_ERRORS_BEFORE_PAUSE)."""


def kill_switch_staleness(state: MatchState, *, now: float | None = None) -> bool:
    """Trips when state.last_updated_ts is older than KILL_SWITCH_STALENESS_S.

    `now` injected for testability; production passes None and uses time.time().
    Strict inequality per PRD §5.4 ("ingestion staleness > 5s").
    """
    n = now if now is not None else time.time()
    return (n - state.last_updated_ts) > KILL_SWITCH_STALENESS_S


def kill_switch_deviation(theo: TheoOutput, market: MarketQuote) -> bool:
    """Trips when |theo_cents - market.mid| > KILL_SWITCH_DEVIATION_C cents.

    Strict inequality per PRD §5.4 ("|theo - market| > 20¢").
    """
    theo_c = round(theo.theo_series * 100)
    return abs(theo_c - market.mid) > KILL_SWITCH_DEVIATION_C


def kill_switch_brier(recent_briers: deque[float]) -> bool:
    """Trips when len(deque) == KILL_SWITCH_BRIER_WINDOW AND mean > KILL_SWITCH_BRIER_BOUND.

    Returns False until the window is full (avoids early false positives).
    Strict inequality per PRD §5.4 ("rolling Brier > 0.30").

    Pitfall 4 (RESEARCH): the deque must be populated only with rounds where
    mode != IDLE. This predicate does NOT validate that contract — it ASSUMES
    the deque is correctly maintained by plan 04-08 reconciliation.
    """
    if len(recent_briers) < KILL_SWITCH_BRIER_WINDOW:
        return False
    return (sum(recent_briers) / len(recent_briers)) > KILL_SWITCH_BRIER_BOUND


def kill_switch_api_error(
    error_streak: int,
    threshold: int = _DEFAULT_API_ERROR_THRESHOLD,
) -> bool:
    """Trips when consecutive API errors >= threshold (default 3).

    Salvaged from reference/market_maker.py:73 (_MAX_ERRORS_BEFORE_PAUSE = 3).
    Note non-strict inequality (>=) here — error_streak == 3 means three errors
    in a row, which is exactly the trip point (PRD §5.4 / DEC-005 #a).
    """
    return error_streak >= threshold


def kill_switch_market_invalid(market: MarketQuote) -> bool:
    """Trips when MarketQuote.is_valid is False (Pitfall 7 WS reconnect path).

    Not in DEC-005 (which lists the four-switch baseline) but is implied by
    PRD §5.4's intent: "stop trading when the market data is unreliable".
    Mode-selector rule 1 returns IDLE during WS reconnect via this trip.
    """
    return not market.is_valid


class KillSwitchAggregator:
    """Owns the rolling-Brier deque; aggregates the 5 predicates.

    Single instance per bot process. The bot main loop calls .any_tripped(...)
    after every theo computation (RESEARCH §"User Constraints" — kill-switch
    evaluation cadence is "every theo computation"); ANY trip fires
    KalshiOrderManager.cancel_all_orders (plan 04-08 wires this).

    The deque is exposed as a public attribute so plan 04-08 reconciliation
    can append Brier scores after round resolution (when mode != IDLE — see
    Pitfall 4).
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
        """Return (any_tripped, sorted_names_of_tripped_switches).

        Sorted name list keeps log lines stable across Python runs (set
        iteration is non-deterministic per Phase 03 D-08 carry-forward).
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
```

(B) Update src/quoting/__init__.py to export the 5 predicates + KillSwitchAggregator.

(C) Flip RED stubs in tests/quoting/test_kill_switches.py to GREEN. Required tests:

```python
"""Plan 04-03 — REQ-kill-switches GREEN tests (DEC-005 + Pitfall 7).

Each predicate gets a TRIP test + a NON-TRIP boundary test (the strict-vs-
non-strict inequality is the most common kill-switch bug per RESEARCH §"Common
Pitfalls" anti-pattern 4).
"""
from __future__ import annotations

from collections import deque

from src.config.constants import (
    KILL_SWITCH_BRIER_BOUND,
    KILL_SWITCH_BRIER_WINDOW,
    KILL_SWITCH_DEVIATION_C,
    KILL_SWITCH_STALENESS_S,
)
from src.pricing.data import TheoOutput
from src.quoting.kill_switches import (
    KillSwitchAggregator,
    kill_switch_api_error,
    kill_switch_brier,
    kill_switch_deviation,
    kill_switch_market_invalid,
    kill_switch_staleness,
)
from src.quoting.market_data import MarketQuote, make_quote


def _theo(theo_series: float = 0.50) -> TheoOutput:
    return TheoOutput(theo_series=theo_series, theo_map=(theo_series,), vega=0.0, confidence=1.0)


# ---------------- staleness ----------------

def test_staleness_trip_above_5s(make_match_state) -> None:
    state = make_match_state(last_updated_ts=100.0)
    assert kill_switch_staleness(state, now=105.01) is True


def test_staleness_no_trip_at_exactly_5s(make_match_state) -> None:
    state = make_match_state(last_updated_ts=100.0)
    assert kill_switch_staleness(state, now=105.0) is False


def test_staleness_no_trip_under_5s(make_match_state) -> None:
    state = make_match_state(last_updated_ts=100.0)
    assert kill_switch_staleness(state, now=104.99) is False


# ---------------- deviation ----------------

def test_deviation_trip_above_20c() -> None:
    """theo=0.50 (50c) vs mid=71c → |50 - 71| = 21 > 20 → trip."""
    market = make_quote(yes_bid=70, yes_ask=72)  # mid = 71
    assert kill_switch_deviation(_theo(0.50), market) is True


def test_deviation_no_trip_at_exactly_20c() -> None:
    """theo=0.50 (50c) vs mid=70c → |50 - 70| = 20, NOT > 20 → no trip."""
    market = make_quote(yes_bid=69, yes_ask=71)  # mid = 70
    assert kill_switch_deviation(_theo(0.50), market) is False


# ---------------- brier ----------------

def test_brier_no_trip_window_not_full() -> None:
    d: deque[float] = deque([0.99] * (KILL_SWITCH_BRIER_WINDOW - 1),
                              maxlen=KILL_SWITCH_BRIER_WINDOW)
    assert kill_switch_brier(d) is False


def test_brier_no_trip_at_exact_threshold() -> None:
    d: deque[float] = deque([KILL_SWITCH_BRIER_BOUND] * KILL_SWITCH_BRIER_WINDOW,
                              maxlen=KILL_SWITCH_BRIER_WINDOW)
    assert kill_switch_brier(d) is False  # mean == threshold, NOT > threshold


def test_brier_trip_above_threshold() -> None:
    d: deque[float] = deque([KILL_SWITCH_BRIER_BOUND + 0.10] * KILL_SWITCH_BRIER_WINDOW,
                              maxlen=KILL_SWITCH_BRIER_WINDOW)
    assert kill_switch_brier(d) is True


# ---------------- api_error ----------------

def test_api_error_trip_at_3() -> None:
    assert kill_switch_api_error(3) is True


def test_api_error_no_trip_at_2() -> None:
    assert kill_switch_api_error(2) is False


def test_api_error_trip_above_3() -> None:
    assert kill_switch_api_error(10) is True


# ---------------- market_invalid (Pitfall 7) ----------------

def test_market_invalid_trip() -> None:
    market = MarketQuote(yes_bid=48, yes_ask=52, mid=50, spread=4,
                          is_valid=False, last_updated_ts=0.0)
    assert kill_switch_market_invalid(market) is True


def test_market_invalid_no_trip_when_valid() -> None:
    assert kill_switch_market_invalid(make_quote(48, 52)) is False


# ---------------- aggregator ----------------

def test_aggregator_no_trip(make_match_state) -> None:
    agg = KillSwitchAggregator()
    state = make_match_state(last_updated_ts=999_999_999.0)  # very recent
    market = make_quote(48, 52)
    tripped, names = agg.any_tripped(state, _theo(0.50), market, error_streak=0)
    assert tripped is False
    assert names == []


def test_aggregator_single_trip(make_match_state) -> None:
    agg = KillSwitchAggregator()
    state = make_match_state(last_updated_ts=0.0)  # very stale; will trip staleness
    market = make_quote(48, 52)
    tripped, names = agg.any_tripped(state, _theo(0.50), market, error_streak=0)
    assert tripped is True
    assert "staleness" in names


def test_aggregator_multiple_trips_returns_sorted_names(make_match_state) -> None:
    agg = KillSwitchAggregator()
    state = make_match_state(last_updated_ts=0.0)  # staleness trip
    market = MarketQuote(yes_bid=70, yes_ask=72, mid=71, spread=2,
                          is_valid=False, last_updated_ts=0.0)
    # deviation trip (|50 - 71| > 20) AND market_invalid trip
    tripped, names = agg.any_tripped(state, _theo(0.50), market, error_streak=5)
    assert tripped is True
    # Sorted alphabetically per Phase 03 D-08 set-iteration determinism
    assert names == sorted(names)
    assert {"staleness", "deviation", "market_invalid", "api_error"} <= set(names)


def test_aggregator_recent_briers_is_deque() -> None:
    agg = KillSwitchAggregator()
    assert isinstance(agg.recent_briers, deque)
    assert agg.recent_briers.maxlen == KILL_SWITCH_BRIER_WINDOW


def test_aggregator_brier_appendable_and_trips_when_full(make_match_state) -> None:
    """Plan 04-08 will append Brier scores; verify the deque accumulates."""
    agg = KillSwitchAggregator()
    for _ in range(KILL_SWITCH_BRIER_WINDOW):
        agg.recent_briers.append(0.50)  # mean = 0.50 > 0.30
    state = make_match_state(last_updated_ts=999_999_999.0)
    tripped, names = agg.any_tripped(state, _theo(0.50), make_quote(48, 52),
                                       error_streak=0)
    assert tripped is True
    assert "brier" in names
```
  </action>
  <verify>
    <automated>uv run pytest tests/quoting/test_kill_switches.py -x --no-cov &amp;&amp; uv run mypy --strict src/quoting/</automated>
  </verify>
  <done>
- src/quoting/kill_switches.py defines 5 predicates + KillSwitchAggregator.
- All 18+ tests pass GREEN.
- src/quoting/__init__.py exports the 5 predicates + KillSwitchAggregator.
- Boundary semantics verified: strict inequality (> threshold) for staleness/deviation/brier; non-strict (>=) for api_error.
- mypy --strict src/quoting/ clean.
  </done>
</task>

</tasks>

<verification>
1. `uv run pytest tests/quoting/test_kill_switches.py -x --no-cov` — 18+ GREEN.
2. `uv run mypy --strict src/quoting/` clean.
3. `uv run pytest tests/ -x --no-cov` — Phase 03 + plan 04-01 + plan 04-02 + plan 04-03 stay green; remaining stubs (04, 05, 06, 07, 08) xfail.
4. `rg "disable_X|disable_kill_switch|kill_switch_disable" src/quoting/` returns empty (DEC-005 — no disable flag).
</verification>

<success_criteria>
- 5 pure predicates + KillSwitchAggregator are grep-discoverable, independently unit-testable.
- Boundary tests cover trip + non-trip for each predicate.
- Aggregator returns sorted names (deterministic logging).
- DEC-005 absolute: no per-switch disable flag in source code.
</success_criteria>

<output>
After completion, create `.planning/phases/04-quoting-layer/04-03-SUMMARY.md` documenting:
- src/quoting/kill_switches.py file contents (5 predicates + aggregator).
- 18+ test results.
- Forward link: plan 04-04 (mode-selector consumes kill_switch_active boolean from KillSwitchAggregator.any_tripped()[0]); plan 04-08 (reconciliation appends Brier scores to KillSwitchAggregator.recent_briers and wires cancel_all_orders on trip).
</output>
