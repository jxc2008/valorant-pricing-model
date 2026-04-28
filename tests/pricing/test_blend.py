"""Property + unit tests for src.pricing.blend.

Verifies REQ-bradley-terry-blend acceptance criteria from roadmap §1.2:
  - round_p(0.5, 0.5) == 0.5 (coin flip)
  - round_p(0.7, 0.3) ≈ 0.845 (compounding edge — was 0.70 under audit's arithmetic mean)
  - round_p(1.0, 0.0) ≈ 1.0 (saturated, NaN-free via BT_BLEND_EPSILON clip)
  - Bradley-Terry symmetry: round_p(a, b) + round_p(b, a) == 1.0
  - Output is in [0.0, 1.0] for all valid inputs
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
    assert math.isclose(round_p(a, b), expected, rel_tol=1e-9)


def test_round_p_saturation_high() -> None:
    """round_p(1.0, 0.0) is NaN-free and arbitrarily close to 1.0 (BT_BLEND_EPSILON clip)."""
    out = round_p(1.0, 0.0)
    assert not math.isnan(out)
    assert not math.isinf(out)
    assert out > 1.0 - 1e-6


def test_round_p_saturation_low() -> None:
    """round_p(0.0, 1.0) is NaN-free and arbitrarily close to 0.0."""
    out = round_p(0.0, 1.0)
    assert not math.isnan(out)
    assert not math.isinf(out)
    assert out < 1e-6


# --------------------------------------------------------------------------- #
# 2. Property tests (hypothesis)                                              #
# --------------------------------------------------------------------------- #


@given(
    a=st.floats(min_value=0.001, max_value=0.999),
    b=st.floats(min_value=0.001, max_value=0.999),
)
def test_round_p_bradley_terry_symmetry(a: float, b: float) -> None:
    """REQ-bradley-terry-blend: round_p(a, b) + round_p(b, a) == 1 (BT symmetry)."""
    assert math.isclose(round_p(a, b) + round_p(b, a), 1.0, rel_tol=1e-9)


@given(
    a=st.floats(min_value=0.0, max_value=1.0),
    b=st.floats(min_value=0.0, max_value=1.0),
)
def test_round_p_in_unit_interval(a: float, b: float) -> None:
    """Range invariant: round_p(a, b) ∈ [0.0, 1.0] for all reachable inputs."""
    out = round_p(a, b)
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
