"""Plan 04-02 — REQ-kelly-sizer (v2 portfolio-aware) GREEN tests.

DEC-023 v2 acceptance per REQUIREMENTS.md:
  - Identical to v1 single-market case when exposure == {}
  - Aggregate cap binds when exposure[series_id] >= 0.10
  - Returns 0 if aggregate cap exceeded
  - Never returns full-Kelly sizing

Property tests via hypothesis cover the three acceptance criteria across
the full input domain (theo, ask, bankroll, exposure).
"""
from __future__ import annotations

from hypothesis import HealthCheck, given, settings, strategies as st

from src.config.constants import (
    KELLY_MULTIPLIER,
    PER_MARKET_CAP_FRAC,
    SERIES_AGGREGATE_CAP_FRAC,
)
from src.sizing.kelly import kelly_size


# --------------------------------------------------------------------------- #
# Unit tests                                                                  #
# --------------------------------------------------------------------------- #


def test_v1_single_market_compat() -> None:
    """When exposure == {}, sizer matches v1 DEC-004 single-market formula."""
    theo, ask, bankroll = 0.60, 50, 100_000
    # b = (1 - 0.5) / 0.5 = 1.0
    p, q, b = theo, 1 - theo, 1.0
    f_full = (b * p - q) / b                  # 0.20
    f = max(0.0, KELLY_MULTIPLIER * f_full)   # 0.10
    f = min(f, PER_MARKET_CAP_FRAC)           # 0.05 binds
    expected = int(f * bankroll / ask)        # int(0.05 * 100_000 / 50) = 100
    assert kelly_size(theo, ask, bankroll, "S1", {}) == expected


def test_aggregate_cap_binds_at_exposure_010() -> None:
    """exposure[s] == SERIES_AGGREGATE_CAP_FRAC ⇒ headroom is 0 ⇒ result is 0."""
    assert kelly_size(0.70, 50, 100_000, "S1", {"S1": SERIES_AGGREGATE_CAP_FRAC}) == 0


def test_aggregate_cap_binds_above_010() -> None:
    """exposure[s] > SERIES_AGGREGATE_CAP_FRAC ⇒ headroom is 0 ⇒ result is 0."""
    assert kelly_size(0.70, 50, 100_000, "S1", {"S1": 0.15}) == 0


def test_per_market_cap_binds_at_005() -> None:
    """Strong edge with empty exposure ⇒ per-market cap binds at 0.05."""
    # theo=0.99, ask=50: f_full = (1 * 0.99 - 0.01) / 1 = 0.98,
    # half = 0.49 ⇒ capped to 0.05 by PER_MARKET_CAP_FRAC.
    result = kelly_size(0.99, 50, 100_000, "S1", {})
    expected = int(PER_MARKET_CAP_FRAC * 100_000 / 50)
    assert result == expected


def test_returns_zero_for_negative_edge() -> None:
    """theo < ask/100 ⇒ f_full < 0 ⇒ max(0, neg) = 0 ⇒ returns 0."""
    assert kelly_size(0.40, 50, 100_000, "S1", {}) == 0


def test_returns_zero_when_aggregate_exceeded() -> None:
    """Hard zero when current_series_exposure > SERIES_AGGREGATE_CAP_FRAC."""
    assert kelly_size(0.99, 50, 100_000, "S1", {"S1": 0.20}) == 0


def test_handles_ask_at_zero() -> None:
    assert kelly_size(0.60, 0, 100_000, "S1", {}) == 0


def test_handles_ask_at_100() -> None:
    assert kelly_size(0.60, 100, 100_000, "S1", {}) == 0


def test_handles_ask_at_boundaries() -> None:
    """ask=0 or ask>=100 returns 0 — defensive guard."""
    assert kelly_size(0.60, 0, 100_000, "S1", {}) == 0
    assert kelly_size(0.60, 100, 100_000, "S1", {}) == 0
    assert kelly_size(0.60, 101, 100_000, "S1", {}) == 0
    assert kelly_size(0.60, -5, 100_000, "S1", {}) == 0


def test_handles_zero_bankroll() -> None:
    assert kelly_size(0.60, 50, 0, "S1", {}) == 0


def test_does_not_mutate_exposure_dict() -> None:
    """Pitfall 5 mitigation: sizer is PURE — never mutates the snapshot dict."""
    exposure = {"S1": 0.03, "S2": 0.07}
    snapshot = dict(exposure)
    kelly_size(0.60, 50, 100_000, "S1", exposure)
    assert exposure == snapshot


def test_partial_headroom_clips_below_per_market_cap() -> None:
    """When headroom < per-market cap, headroom is the binding constraint."""
    # exposure[S1] = 0.07 ⇒ headroom = 0.10 - 0.07 = 0.03 (< 0.05).
    # Strong-edge inputs (theo=0.99) push half-Kelly fraction far above 0.05,
    # so the per-market cap and then the headroom dominate in sequence.
    result = kelly_size(0.99, 50, 100_000, "S1", {"S1": 0.07})
    expected = int(0.03 * 100_000 / 50)        # 60
    assert result == expected


def test_other_series_exposure_does_not_affect_size() -> None:
    """Aggregate cap is per series_id; exposure on a sibling series ignored."""
    result_alone = kelly_size(0.99, 50, 100_000, "S1", {})
    result_with_other = kelly_size(0.99, 50, 100_000, "S1", {"S2": 0.99})
    assert result_alone == result_with_other


# --------------------------------------------------------------------------- #
# Property tests (hypothesis)                                                 #
# --------------------------------------------------------------------------- #


@given(
    theo=st.floats(
        min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False
    ),
    ask=st.integers(min_value=1, max_value=99),
    bankroll=st.integers(min_value=1, max_value=1_000_000),
)
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_never_full_kelly(theo: float, ask: int, bankroll: int) -> None:
    """REQ-kelly-sizer acceptance: result <= int(half-Kelly * bankroll / ask).

    The half-Kelly upper bound is the loosest non-trivial bound the sizer must
    respect; per-market cap and aggregate cap can only tighten it further.
    """
    result = kelly_size(theo, ask, bankroll, "S1", {})
    assert isinstance(result, int)
    assert result >= 0
    if result == 0:
        return
    p, q = theo, 1 - theo
    ask_f = ask / 100.0
    b = (1.0 - ask_f) / ask_f
    f_full = max(0.0, (b * p - q) / b)
    half_kelly_count = int(KELLY_MULTIPLIER * f_full * bankroll / ask)
    # +1 tolerance for int() floor rounding parity between formulas.
    assert result <= half_kelly_count + 1


@given(
    theo=st.floats(
        min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False
    ),
    ask=st.integers(min_value=1, max_value=99),
    bankroll=st.integers(min_value=1, max_value=1_000_000),
    exposure_frac=st.floats(
        min_value=SERIES_AGGREGATE_CAP_FRAC,
        max_value=1.0,
        allow_nan=False,
        allow_infinity=False,
    ),
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property_returns_zero_when_aggregate_exceeded(
    theo: float, ask: int, bankroll: int, exposure_frac: float
) -> None:
    """Property: any exposure >= SERIES_AGGREGATE_CAP_FRAC ⇒ result is 0."""
    assert kelly_size(theo, ask, bankroll, "S1", {"S1": exposure_frac}) == 0


@given(
    theo=st.floats(
        min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False
    ),
    ask=st.integers(min_value=0, max_value=120),
    bankroll=st.integers(min_value=0, max_value=1_000_000),
)
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_result_is_non_negative_integer(
    theo: float, ask: int, bankroll: int
) -> None:
    """Property: result is always a non-negative int across the full domain."""
    result = kelly_size(theo, ask, bankroll, "S1", {})
    assert isinstance(result, int)
    assert result >= 0


@given(
    theo=st.floats(
        min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False
    ),
    ask=st.integers(min_value=1, max_value=99),
    bankroll=st.integers(min_value=1, max_value=1_000_000),
    exposure_frac=st.floats(
        min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False
    ),
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property_does_not_mutate_exposure(
    theo: float, ask: int, bankroll: int, exposure_frac: float
) -> None:
    """Property: kelly_size never mutates its current_series_exposure arg."""
    exposure = {"S1": exposure_frac, "S2": 0.04}
    snapshot = dict(exposure)
    kelly_size(theo, ask, bankroll, "S1", exposure)
    assert exposure == snapshot
