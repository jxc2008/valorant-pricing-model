"""Property + unit tests for src.pricing.blend.

Verifies REQ-bradley-terry-blend acceptance criteria from roadmap §1.2:
  - round_p(0.5, 0.5, 0.5) == 0.5 (coin flip)
  - round_p(0.7, 0.3, 0.5) ≈ 0.845 (compounding edge — was 0.70 under audit's arithmetic mean)
  - round_p(1.0, 0.0, L) ≈ 1.0 (saturated, NaN-free via BT_BLEND_EPSILON clip)
  - Symmetry: round_p(a, b, L) + round_p(b, a, 1-L) == 1.0
  - Output is in [0.0, 1.0] for all valid inputs
Side-baseline fix (log5 against league side rate):
  - league-average teams return the league rate: round_p(L, 1-L, L) == L
  - side advantage counted once, not twice
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from src.pricing.blend import round_p

# --------------------------------------------------------------------------- #
# 1. Unit cases (REQ-bradley-terry-blend acceptance)                          #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "a,b,expected",
    [
        (0.5, 0.5, 0.5),                   # coin flip
        (0.7, 0.3, 49.0 / 58.0),           # 0.84482... — compounding edge
        (0.6, 0.4, 0.36 / 0.52),           # 0.69230... — moderate edge
    ],
)
def test_round_p_unit_cases(a: float, b: float, expected: float) -> None:
    """REQ-bradley-terry-blend acceptance: known-value cases from roadmap §1.2."""
    assert math.isclose(round_p(a, b, 0.5), expected, rel_tol=1e-9)


def test_round_p_saturation_high() -> None:
    """round_p(1.0, 0.0) is NaN-free and arbitrarily close to 1.0 (BT_BLEND_EPSILON clip)."""
    out = round_p(1.0, 0.0, 0.55)
    assert not math.isnan(out)
    assert not math.isinf(out)
    assert out > 1.0 - 1e-6


def test_round_p_saturation_low() -> None:
    """round_p(0.0, 1.0) is NaN-free and arbitrarily close to 0.0."""
    out = round_p(0.0, 1.0, 0.45)
    assert not math.isnan(out)
    assert not math.isinf(out)
    assert out < 1e-6


# --------------------------------------------------------------------------- #
# 2. Property tests (hypothesis)                                              #
# --------------------------------------------------------------------------- #


_rate = st.floats(min_value=0.001, max_value=0.999)


@given(a=_rate, b=_rate, lg=_rate)
def test_round_p_symmetry(a: float, b: float, lg: float) -> None:
    """Swapping teams flips the side, so L -> 1-L: probabilities sum to 1."""
    assert math.isclose(round_p(a, b, lg) + round_p(b, a, 1.0 - lg), 1.0, rel_tol=1e-9)


@given(lg=st.floats(min_value=0.01, max_value=0.99))
def test_league_average_teams_return_league_rate(lg: float) -> None:
    """round_p(L, 1-L, L) == L: two league-average teams reproduce the side baseline."""
    assert math.isclose(round_p(lg, 1.0 - lg, lg), lg, rel_tol=1e-9)


def test_side_advantage_not_double_counted() -> None:
    """Concrete regression: 55% attack map, both teams league-average.

    The old two-argument form returned odds(0.55)^2 -> 0.599; correct is 0.55.
    """
    assert math.isclose(round_p(0.55, 0.45, 0.55), 0.55, rel_tol=1e-12)
    old = (0.55 * 0.55) / (0.55 * 0.55 + 0.45 * 0.45)
    assert old > 0.59


@given(a=_rate, b=_rate)
def test_reduces_to_bradley_terry_at_half(a: float, b: float) -> None:
    """With L = 0.5 the formula is exactly Bradley-Terry a(1-b)/(a(1-b)+(1-a)b)."""
    bt = a * (1 - b) / (a * (1 - b) + (1 - a) * b)
    assert math.isclose(round_p(a, b, 0.5), bt, rel_tol=1e-9)


@given(
    a=st.floats(min_value=0.0, max_value=1.0),
    b=st.floats(min_value=0.0, max_value=1.0),
    lg=st.floats(min_value=0.0, max_value=1.0),
)
def test_round_p_in_unit_interval(a: float, b: float, lg: float) -> None:
    """Range invariant: round_p(a, b, L) ∈ [0.0, 1.0] for all reachable inputs."""
    out = round_p(a, b, lg)
    assert 0.0 <= out <= 1.0
    assert not math.isnan(out)


# --------------------------------------------------------------------------- #
# 3. Regression — DEC-003 forbids arithmetic mean                             #
# --------------------------------------------------------------------------- #


def test_blend_source_does_not_contain_arithmetic_mean_form() -> None:
    """DEC-003 / CRule 3: arithmetic-mean blend (a + (1-b)) / 2 is forbidden."""
    src = Path("src/pricing/blend.py").read_text(encoding="utf-8")
    # Strip comments/docstrings: only check executable lines.
    code_lines = [
        line for line in src.splitlines()
        if line.strip() and not line.lstrip().startswith(("#", '"""', "'''"))
    ]
    code = "\n".join(code_lines)
    assert "(a_rate + (1.0 - b_rate)) / 2" not in code
    assert "(a + (1 - b)) / 2" not in code
    assert "(a_rate + (1 - b_rate)) / 2" not in code
