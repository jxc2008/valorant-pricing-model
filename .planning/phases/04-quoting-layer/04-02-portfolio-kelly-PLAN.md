---
phase: 04-quoting-layer
plan: "02"
type: execute
wave: 2
depends_on: ["00"]
files_modified:
  - src/sizing/kelly.py
  - src/sizing/__init__.py
  - src/quoting/portfolio.py
  - src/quoting/__init__.py
  - tests/sizing/test_kelly_portfolio.py
  - tests/quoting/test_portfolio_state.py
autonomous: true
requirements:
  - REQ-kelly-sizer
notes: |
  Wave 2 — pure-function portfolio Kelly sizer + PortfolioState exposure
  registry. Parallelizable with plan 04-01 and 04-03 (no shared files; each
  populates a disjoint subset of src/).

  DEC-023 v2 portfolio Kelly: half-Kelly + per-market cap (PER_MARKET_CAP_FRAC
  = 0.05) + per-series aggregate cap (SERIES_AGGREGATE_CAP_FRAC = 0.10).
  Returns 0 if aggregate cap exceeded. Never returns full-Kelly.

  Architecture split (RESEARCH §"Standard Stack" Don't Hand-Roll table):
  - src/sizing/kelly.py — PURE function. Takes a `current_series_exposure:
    dict[str, float]` snapshot; does NOT mutate. mypy --strict friendly.
  - src/quoting/portfolio.py — PortfolioState class that OWNS the dict and
    exposes `on_place(series_id, fraction)` / `on_settle(series_id, fraction)`
    helpers. Phase 03 metrics JSONL records the seq_id of resolution events;
    plan 04-08 reconciliation wires the on_settle callback (RESEARCH Pitfall 5).

  Pitfall 5 mitigation: aggregate exposure must be DECREMENTED on round
  resolution; if it's never decremented, exposure monotonically grows and
  Kelly returns 0 forever after the first few placements. The PortfolioState
  class makes the on_place / on_settle pair grep-discoverable so plan 04-08
  can wire the settle path correctly.

  Hypothesis property tests cover REQ-kelly-sizer's three acceptance criteria:
  (a) identical to v1 single-market case (when exposure = {}); (b) aggregate
  cap binds at exposure[s] >= SERIES_AGGREGATE_CAP_FRAC; (c) returns 0 if
  aggregate exceeded. Plus the `never_full_kelly` invariant per VALIDATION.md.

must_haves:
  truths:
    - "kelly_size(theo, ask, bankroll, series_id, {}) returns identical contract count to v1 single-market half-Kelly + 5% cap"
    - "kelly_size returns 0 when current_series_exposure[series_id] >= SERIES_AGGREGATE_CAP_FRAC"
    - "kelly_size always returns <= int(KELLY_MULTIPLIER * f_full * bankroll / ask) — property holds for hypothesis-generated inputs"
    - "kelly_size handles ask boundary cases: ask=0 → 0, ask>=100 → 0, theo<=ask/100 → 0"
    - "PortfolioState.on_place(series_id, frac) increments exposure[series_id] by frac"
    - "PortfolioState.on_settle(series_id, frac) decrements exposure[series_id] by frac (clipped at 0)"
    - "PortfolioState.snapshot() returns a frozen dict copy that kelly_size consumes (no mutation)"
  artifacts:
    - path: "src/sizing/kelly.py"
      provides: "Pure kelly_size(theo, market_yes_ask, bankroll, series_id, current_series_exposure) -> int"
      min_lines: 50
      contains: "SERIES_AGGREGATE_CAP_FRAC"
    - path: "src/quoting/portfolio.py"
      provides: "PortfolioState class: on_place / on_settle / snapshot / current"
      min_lines: 50
      contains: "class PortfolioState"
    - path: "tests/sizing/test_kelly_portfolio.py"
      provides: "7+ tests including hypothesis property tests for REQ-kelly-sizer"
      contains: "hypothesis"
  key_links:
    - from: "src/sizing/kelly.py kelly_size"
      to: "src.config.constants.KELLY_MULTIPLIER + PER_MARKET_CAP_FRAC + SERIES_AGGREGATE_CAP_FRAC"
      via: "import — DEC-023 v2 verbatim formula"
      pattern: "SERIES_AGGREGATE_CAP_FRAC"
    - from: "src/quoting/portfolio.py PortfolioState"
      to: "src/sizing/kelly.py kelly_size"
      via: "snapshot() returns dict consumed as current_series_exposure arg"
      pattern: "snapshot"
    - from: "src/quoting/portfolio.py PortfolioState.on_settle"
      to: "plan 04-08 reconciliation (round-resolution event handler)"
      via: "Pitfall 5 — caller must invoke on_settle when round resolves"
      pattern: "on_settle"
---

<objective>
Build the portfolio-aware Kelly sizer (DEC-023 v2) — pure function in
src/sizing/kelly.py + PortfolioState registry in src/quoting/portfolio.py.
The sizer takes a `current_series_exposure: dict[str, float]` snapshot and
returns 0 if the per-series aggregate cap is binding; PortfolioState owns
the dict and exposes on_place / on_settle helpers (Pitfall 5 — exposure
must be decremented on settlement or it grows unbounded).

Purpose: REQ-kelly-sizer (v2 portfolio-aware). Phase 04 directional taker
(plan 04-06) and post-plant quoter (plan 04-07) call kelly_size with a
snapshot from PortfolioState; PortfolioState.on_place fires AT placement
time and on_settle fires when the round resolves (plan 04-08 wires the
on_settle callback).

Output: 2 new src/ modules + 2 new test files (kelly + PortfolioState
unit tests, hypothesis property tests for kelly invariants).
</objective>

<execution_context>
@C:/Users/Joseph Cheng/.claude/get-shit-done/workflows/execute-plan.md
@C:/Users/Joseph Cheng/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/phases/04-quoting-layer/04-RESEARCH.md
@src/config/constants.py
@reference/market_maker.py

<interfaces>
<!-- src.config.constants — Phase 04 additions from plan 04-00 -->
```python
KELLY_MULTIPLIER: Final[float] = 0.5            # half-Kelly per DEC-004
PER_MARKET_CAP_FRAC: Final[float] = 0.05         # per-market cap
SERIES_AGGREGATE_CAP_FRAC: Final[float] = 0.10   # NEW v2 — DEC-023
```

<!-- New surfaces this plan creates that downstream plans (04-06, 04-07, 04-08) consume -->
NEW src/sizing/kelly.py public surface:
```python
def kelly_size(
    theo: float,                                    # P(YES wins) ∈ [0, 1]
    market_yes_ask: int,                            # cents 1-99
    bankroll: int,                                  # cents
    series_id: str,
    current_series_exposure: dict[str, float],      # snapshot — NOT mutated
) -> int: ...                                       # contract count; 0 if any cap binds
```

NEW src/quoting/portfolio.py public surface:
```python
class PortfolioState:
    def __init__(self) -> None: ...
    def on_place(self, series_id: str, fraction: float) -> None: ...
    def on_settle(self, series_id: str, fraction: float) -> None: ...
    def snapshot(self) -> dict[str, float]: ...     # caller-owned copy
    def current(self, series_id: str) -> float: ...
```

<!-- Reference v1 single-market sizing (for v1-compat property test) -->
DEC-004 v1 formula:
    b = (1 - ask) / ask
    f_full = (b * p - q) / b
    f = max(0, KELLY_MULTIPLIER * f_full)
    f = min(f, PER_MARKET_CAP_FRAC)
    return 0 if f == 0 else int(f * bankroll / market_yes_ask)

DEC-023 v2 adds:
    headroom = max(0, SERIES_AGGREGATE_CAP_FRAC - current_series_exposure.get(series_id, 0))
    f = min(f, headroom)                            # NEW v2 line
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: src/sizing/kelly.py + GREEN test_kelly_portfolio.py (incl. hypothesis property tests)</name>
  <files>src/sizing/kelly.py, src/sizing/__init__.py, tests/sizing/test_kelly_portfolio.py</files>
  <behavior>
    - kelly_size(theo=0.6, market_yes_ask=50, bankroll=100_000, series_id="S1", current_series_exposure={}) returns positive integer when there's edge (0.6 > 0.5 and bankroll > 0)
    - kelly_size with current_series_exposure={"S1": 0.10} returns 0 (aggregate cap binding)
    - kelly_size with current_series_exposure={"S1": 0.05} returns headroom-clipped count (5% remaining headroom)
    - kelly_size(theo=0.4, market_yes_ask=50, ...) returns 0 (no edge — q*b > p*b -> f_full < 0 -> max(0, KELLY * negative) = 0)
    - kelly_size(theo=0.5, market_yes_ask=0, ...) returns 0 (ask boundary guard)
    - kelly_size(theo=0.5, market_yes_ask=100, ...) returns 0 (ask boundary guard)
    - Property (hypothesis): for any theo in [0, 1], ask in [1, 99], bankroll in [1, 1_000_000], result <= int(KELLY_MULTIPLIER * f_full * bankroll / ask) when result > 0 (never full-Kelly)
    - Property (hypothesis): for any inputs, result is non-negative integer
    - Property (hypothesis): when current_series_exposure[series_id] >= SERIES_AGGREGATE_CAP_FRAC, result == 0
    - kelly_size does NOT mutate current_series_exposure (test passes a dict, asserts dict unchanged after call)
  </behavior>
  <action>
(A) Create src/sizing/kelly.py — pure function per DEC-023 v2 verbatim formula:

```python
"""Portfolio-aware half-Kelly sizer (DEC-023 v2 / REQ-kelly-sizer).

Pure function. Caller owns `current_series_exposure: dict[str, float]`;
this module does NOT mutate it. The PortfolioState registry at
src/quoting/portfolio.py owns the mutable dict and exposes a snapshot()
method that returns the dict copy this function consumes.

Three caps applied in order (DEC-023 v2 verbatim formula):
    1. Half-Kelly: f = max(0, KELLY_MULTIPLIER * f_full)
    2. Per-market cap: f = min(f, PER_MARKET_CAP_FRAC)        # 0.05
    3. Per-series aggregate cap: f = min(f, headroom)         # 0.10 - exposure[s]

Returns 0 if any cap binds the fraction to 0.

Source: PRD §2.3 + ROADMAP §4.6 + DEC-004 + DEC-023 v2 + RESEARCH §"Code
Examples" "Portfolio Kelly with per-series aggregate cap (DEC-023 v2)"
verbatim block. Pitfall 5 mitigation: this function does NOT touch
exposure tracking; the caller must invoke PortfolioState.on_place at
placement and on_settle at round resolution.
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
    """Return contract count to YES-buy at `market_yes_ask` cents.

    Args:
        theo: P(YES wins) ∈ [0, 1].
        market_yes_ask: Kalshi YES ask (cents 1-99).
        bankroll: Available cents.
        series_id: Stable string identifier for the series (e.g., Kalshi
            event ticker root). All correlated markets within a series
            (moneyline + map handicaps + round handicaps) share the id.
        current_series_exposure: Snapshot of {series_id -> fractional exposure}.
            NOT mutated. Owned by caller (PortfolioState.snapshot()).

    Returns:
        Integer contract count. 0 if any cap binds OR if theo ≤ ask/100.

    Acceptance per REQ-kelly-sizer (v2 portfolio-aware):
        - Identical to v1 single-market case when exposure == {} or 0
          (preserves DEC-004 backward compatibility).
        - Aggregate cap binds when exposure[series_id] ≥ SERIES_AGGREGATE_CAP_FRAC.
        - Never returns full-Kelly sizing (f always ≤ KELLY_MULTIPLIER * f_full).
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
    f = min(f, PER_MARKET_CAP_FRAC)                 # per-market cap (0.05)

    # DEC-023 v2: per-series aggregate cap layered on top.
    headroom = max(
        0.0,
        SERIES_AGGREGATE_CAP_FRAC - current_series_exposure.get(series_id, 0.0),
    )
    f = min(f, headroom)

    if f == 0.0:
        return 0
    return int(f * bankroll / market_yes_ask)
```

(B) src/sizing/__init__.py — export the public surface:
```python
from src.sizing.kelly import kelly_size

__all__ = ["kelly_size"]
```

(C) Flip RED stubs in tests/sizing/test_kelly_portfolio.py to GREEN.
    Use hypothesis for the three property tests:

```python
"""Plan 04-02 — REQ-kelly-sizer (v2 portfolio-aware) GREEN tests.

DEC-023 v2 acceptance per REQUIREMENTS.md:
  - Identical to v1 single-market case when exposure == {}
  - Aggregate cap binds when exposure[series_id] >= 0.10
  - Returns 0 if aggregate cap exceeded
  - Never returns full-Kelly sizing
"""
from __future__ import annotations

from hypothesis import HealthCheck, given, settings, strategies as st

from src.config.constants import (
    KELLY_MULTIPLIER,
    PER_MARKET_CAP_FRAC,
    SERIES_AGGREGATE_CAP_FRAC,
)
from src.sizing.kelly import kelly_size


def test_v1_single_market_compat() -> None:
    """When exposure == {}, sizer matches v1 DEC-004 single-market formula."""
    theo, ask, bankroll = 0.60, 50, 100_000
    p, q, b = theo, 1 - theo, (1 - 0.5) / 0.5  # b = 1.0 at ask=0.5
    f_full = (b * p - q) / b                    # 0.20
    f = max(0.0, KELLY_MULTIPLIER * f_full)     # 0.10
    f = min(f, PER_MARKET_CAP_FRAC)             # 0.05 binds
    expected = int(f * bankroll / ask)           # int(0.05 * 100_000 / 50) = 100
    assert kelly_size(theo, ask, bankroll, "S1", {}) == expected


def test_aggregate_cap_binds_at_exposure_010() -> None:
    """When exposure[s] == SERIES_AGGREGATE_CAP_FRAC, headroom is 0 -> result is 0."""
    assert kelly_size(0.70, 50, 100_000, "S1", {"S1": SERIES_AGGREGATE_CAP_FRAC}) == 0


def test_aggregate_cap_binds_at_exposure_above_010() -> None:
    """When exposure[s] > SERIES_AGGREGATE_CAP_FRAC, headroom is 0 -> result is 0."""
    assert kelly_size(0.70, 50, 100_000, "S1", {"S1": 0.15}) == 0


def test_per_market_cap_binds_at_005() -> None:
    """Strong edge with empty exposure -> per-market cap binds at 0.05."""
    # theo=0.99, ask=50: f_full = (1*0.99 - 0.01) / 1 = 0.98, half = 0.49 -> capped to 0.05
    result = kelly_size(0.99, 50, 100_000, "S1", {})
    expected = int(PER_MARKET_CAP_FRAC * 100_000 / 50)
    assert result == expected


def test_returns_zero_for_negative_edge() -> None:
    """theo <= ask/100 -> f_full <= 0 -> max(0, neg) = 0 -> returns 0."""
    assert kelly_size(0.40, 50, 100_000, "S1", {}) == 0


def test_handles_ask_at_zero() -> None:
    assert kelly_size(0.60, 0, 100_000, "S1", {}) == 0


def test_handles_ask_at_100() -> None:
    assert kelly_size(0.60, 100, 100_000, "S1", {}) == 0


def test_handles_zero_bankroll() -> None:
    assert kelly_size(0.60, 50, 0, "S1", {}) == 0


def test_does_not_mutate_exposure_dict() -> None:
    """Pitfall 5 / RESEARCH §"Common Pitfalls": sizer is pure."""
    exposure = {"S1": 0.03, "S2": 0.07}
    snapshot = dict(exposure)
    kelly_size(0.60, 50, 100_000, "S1", exposure)
    assert exposure == snapshot


def test_partial_headroom_clips_below_per_market_cap() -> None:
    """When headroom < per-market cap, headroom is binding constraint."""
    # exposure[S1] = 0.07 -> headroom = 0.03 (< 0.05 per-market cap)
    result = kelly_size(0.99, 50, 100_000, "S1", {"S1": 0.07})
    expected = int(0.03 * 100_000 / 50)         # 60
    assert result == expected


# --------------------------------------------------------------------------- #
# Property tests (hypothesis)                                                  #
# --------------------------------------------------------------------------- #

@given(
    theo=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    ask=st.integers(min_value=1, max_value=99),
    bankroll=st.integers(min_value=1, max_value=1_000_000),
)
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_never_full_kelly(theo: float, ask: int, bankroll: int) -> None:
    """REQ-kelly-sizer acceptance: result <= half-Kelly upper bound."""
    result = kelly_size(theo, ask, bankroll, "S1", {})
    if result == 0:
        return
    p, q = theo, 1 - theo
    ask_f = ask / 100.0
    b = (1.0 - ask_f) / ask_f
    f_full = max(0.0, (b * p - q) / b)
    half_kelly_count = int(KELLY_MULTIPLIER * f_full * bankroll / ask)
    # result is also bounded by per-market cap and aggregate cap; so
    # result <= half_kelly_count (relaxed bound — never EXCEEDS half-Kelly).
    assert result <= half_kelly_count + 1  # +1 for floor rounding tolerance


@given(
    theo=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    ask=st.integers(min_value=1, max_value=99),
    bankroll=st.integers(min_value=1, max_value=1_000_000),
    exposure_frac=st.floats(min_value=SERIES_AGGREGATE_CAP_FRAC, max_value=1.0,
                              allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_returns_zero_when_aggregate_exceeded(
    theo: float, ask: int, bankroll: int, exposure_frac: float,
) -> None:
    """Property: any exposure >= aggregate cap -> result is 0."""
    assert kelly_size(theo, ask, bankroll, "S1", {"S1": exposure_frac}) == 0


@given(
    theo=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    ask=st.integers(min_value=1, max_value=99),
    bankroll=st.integers(min_value=0, max_value=1_000_000),
)
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_result_is_non_negative_integer(theo: float, ask: int, bankroll: int) -> None:
    result = kelly_size(theo, ask, bankroll, "S1", {})
    assert isinstance(result, int)
    assert result >= 0
```
  </action>
  <verify>
    <automated>uv run pytest tests/sizing/test_kelly_portfolio.py -x --no-cov &amp;&amp; uv run mypy --strict src/sizing/</automated>
  </verify>
  <done>
- src/sizing/kelly.py defines kelly_size implementing DEC-023 v2 verbatim formula.
- All 12+ tests in tests/sizing/test_kelly_portfolio.py pass GREEN (incl. 3 hypothesis property tests).
- mypy --strict src/sizing/ clean.
- src/sizing/__init__.py exports kelly_size.
- Function does NOT mutate `current_series_exposure` (verified by test_does_not_mutate_exposure_dict).
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: src/quoting/portfolio.py PortfolioState + GREEN test_portfolio_state.py</name>
  <files>src/quoting/portfolio.py, src/quoting/__init__.py, tests/quoting/test_portfolio_state.py</files>
  <behavior>
    - PortfolioState() — empty registry; .snapshot() returns {}
    - .on_place("S1", 0.05) — exposure["S1"] becomes 0.05; .snapshot() returns {"S1": 0.05}
    - .on_place("S1", 0.03) on top of 0.05 — exposure["S1"] becomes 0.08
    - .on_place("S2", 0.04) — exposure["S2"] becomes 0.04; "S1" unchanged
    - .on_settle("S1", 0.05) — exposure["S1"] becomes 0.03 (0.08 - 0.05)
    - .on_settle("S1", 0.10) when exposure["S1"] is 0.03 — clipped to 0.0 (never goes negative)
    - .current("S1") returns 0.03 / 0.0 / 0.0 in the above sequence; .current("UNKNOWN") returns 0.0
    - .snapshot() returns a fresh dict copy each call (mutation of the returned dict does NOT affect state)
    - .on_place rejects negative fractions (raises ValueError)
    - .on_settle rejects negative fractions (raises ValueError)
  </behavior>
  <action>
(A) Create src/quoting/portfolio.py:

```python
"""PortfolioState — per-series exposure registry (REQ-kelly-sizer support).

Owns the `dict[series_id, fractional_exposure]` that
src/sizing/kelly.kelly_size consumes via the snapshot() method. Pure-function
sizer + mutable registry split lets the sizer stay mypy-strict without I/O
or state, while the registry exposes the on_place / on_settle pair that the
quoter loops invoke.

Pitfall 5 (RESEARCH §"Common Pitfalls"): exposure must be DECREMENTED on
round resolution. If on_settle is never called, exposure monotonically grows
and kelly_size returns 0 forever after the first few placements. The class
makes the on_place / on_settle pair grep-discoverable (`rg "on_settle"`) so
plan 04-08 reconciliation can wire the round-resolution callback correctly.

Source: PRD §2.3 / DEC-023 v2 / RESEARCH §"Architecture Patterns" Pattern 2.
"""
from __future__ import annotations


class PortfolioState:
    """Registry of per-series fractional exposure.

    Single owner per bot process. Quoters CALL on_place at placement time
    (with the fraction that kelly_size returned divided by bankroll); the
    round-resolution path CALLS on_settle when the series-level position
    settles (Phase 03 metrics JSONL records the seq_id of the resolution
    event; plan 04-08 reconciliation wires the callback).
    """

    def __init__(self) -> None:
        self._exposure: dict[str, float] = {}

    def on_place(self, series_id: str, fraction: float) -> None:
        """Increment exposure[series_id] by fraction.

        Raises:
            ValueError: if fraction < 0 (placements always increase exposure;
                a negative fraction means a programming error).
        """
        if fraction < 0:
            raise ValueError(f"on_place fraction must be non-negative; got {fraction}")
        self._exposure[series_id] = self._exposure.get(series_id, 0.0) + fraction

    def on_settle(self, series_id: str, fraction: float) -> None:
        """Decrement exposure[series_id] by fraction; clip at 0.0.

        Clipping at 0 protects against double-settlement bugs (e.g., resolution
        event delivered twice) — exposure should never go negative under any
        real-world sequence of placements + settlements.

        Raises:
            ValueError: if fraction < 0.
        """
        if fraction < 0:
            raise ValueError(f"on_settle fraction must be non-negative; got {fraction}")
        new_exposure = self._exposure.get(series_id, 0.0) - fraction
        self._exposure[series_id] = max(0.0, new_exposure)

    def current(self, series_id: str) -> float:
        """Return current fractional exposure for series_id; 0.0 if unknown."""
        return self._exposure.get(series_id, 0.0)

    def snapshot(self) -> dict[str, float]:
        """Return a fresh dict copy. kelly_size consumes this; mutation of the
        returned dict does NOT affect this PortfolioState."""
        return dict(self._exposure)
```

(B) Update src/quoting/__init__.py to add PortfolioState export.

(C) Create tests/quoting/test_portfolio_state.py with 8+ unit tests covering
    the behavior block above. Each test asserts ONE behavior; no fixtures
    needed beyond a fresh PortfolioState() instance per test.

```python
"""Plan 04-02 — PortfolioState exposure registry tests."""
from __future__ import annotations

import pytest

from src.quoting.portfolio import PortfolioState


def test_empty_state_snapshot() -> None:
    assert PortfolioState().snapshot() == {}


def test_on_place_records_exposure() -> None:
    s = PortfolioState()
    s.on_place("S1", 0.05)
    assert s.current("S1") == pytest.approx(0.05)
    assert s.snapshot() == {"S1": pytest.approx(0.05)}


def test_on_place_accumulates() -> None:
    s = PortfolioState()
    s.on_place("S1", 0.05)
    s.on_place("S1", 0.03)
    assert s.current("S1") == pytest.approx(0.08)


def test_on_place_independent_series() -> None:
    s = PortfolioState()
    s.on_place("S1", 0.05)
    s.on_place("S2", 0.04)
    assert s.current("S1") == pytest.approx(0.05)
    assert s.current("S2") == pytest.approx(0.04)


def test_on_settle_decrements() -> None:
    s = PortfolioState()
    s.on_place("S1", 0.08)
    s.on_settle("S1", 0.05)
    assert s.current("S1") == pytest.approx(0.03)


def test_on_settle_clips_at_zero() -> None:
    """Pitfall 5 mitigation: double-settlement should not push exposure negative."""
    s = PortfolioState()
    s.on_place("S1", 0.03)
    s.on_settle("S1", 0.10)
    assert s.current("S1") == 0.0


def test_current_unknown_returns_zero() -> None:
    assert PortfolioState().current("UNKNOWN") == 0.0


def test_snapshot_is_a_copy() -> None:
    """Mutation of snapshot dict must NOT affect PortfolioState."""
    s = PortfolioState()
    s.on_place("S1", 0.05)
    snap = s.snapshot()
    snap["S1"] = 999.0
    assert s.current("S1") == pytest.approx(0.05)


def test_on_place_rejects_negative() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        PortfolioState().on_place("S1", -0.01)


def test_on_settle_rejects_negative() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        PortfolioState().on_settle("S1", -0.01)
```

(D) Update src/quoting/__init__.py:
```python
from src.quoting.portfolio import PortfolioState

# Extend __all__ with "PortfolioState"
```
  </action>
  <verify>
    <automated>uv run pytest tests/quoting/test_portfolio_state.py -x --no-cov &amp;&amp; uv run mypy --strict src/quoting/</automated>
  </verify>
  <done>
- src/quoting/portfolio.py defines PortfolioState with on_place / on_settle / snapshot / current methods.
- 10 tests in tests/quoting/test_portfolio_state.py pass GREEN.
- src/quoting/__init__.py exports PortfolioState.
- mypy --strict src/quoting/ clean.
  </done>
</task>

</tasks>

<verification>
1. `uv run pytest tests/sizing/ tests/quoting/test_portfolio_state.py -x --no-cov` — 22+ GREEN.
2. `uv run mypy --strict src/sizing/ src/quoting/` clean.
3. `uv run pytest tests/ -x --no-cov` — Phase 03 + plan 04-01 stay green; remaining Phase 04 stubs xfail.
4. `python -c "from src.sizing import kelly_size; from src.quoting import PortfolioState; ps = PortfolioState(); ps.on_place('s', 0.05); print(kelly_size(0.6, 50, 100000, 's', ps.snapshot()))"` runs without error.
</verification>

<success_criteria>
- kelly_size is a pure function; never mutates current_series_exposure.
- PortfolioState owns the mutable dict; snapshot() returns a fresh copy.
- All 22+ new tests pass GREEN; hypothesis property tests cover REQ-kelly-sizer acceptance criteria.
- The on_place / on_settle pair is grep-discoverable so plan 04-08 reconciliation knows where to wire round-resolution callbacks (Pitfall 5).
</success_criteria>

<output>
After completion, create `.planning/phases/04-quoting-layer/04-02-SUMMARY.md` documenting:
- Files created (src/sizing/kelly.py, src/quoting/portfolio.py, 2 test files).
- DEC-023 v2 formula verbatim implementation confirmation.
- mypy --strict on src/sizing/ + src/quoting/ clean confirmation.
- Forward links: plan 04-06 (directional taker calls kelly_size), plan 04-07 (post-plant quoter calls kelly_size), plan 04-08 (reconciliation wires PortfolioState.on_settle).
</output>
