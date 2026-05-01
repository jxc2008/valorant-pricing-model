"""Tests for src.pricing.economy — CON-economy-buckets boundary contract.

Verifies the Phase 2 / Phase 3 shared bucketing invariants:
  - Boundary cases at every bucket-floor transition (4999 / 5000 / 9999 / 10000 / 19999 / 20000).
  - Defensive handling of negative inputs (returns "eco").
  - Range closure: output is always one of the four canonical labels.
  - CRule 12 / CON-no-magic-numbers: source body must NOT contain inline 20000 / 10000 / 5000 literals.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from src.pricing.economy import credits_to_bucket

VALID_LABELS: frozenset[str] = frozenset({"full", "semi-buy", "semi-eco", "eco"})


# --------------------------------------------------------------------------- #
# 1. Boundary cases (CON-economy-buckets)                                     #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "credits,expected",
    [
        # full bucket (>= 20000)
        (20_000, "full"),
        (50_000, "full"),
        (1_000_000, "full"),
        # semi-buy bucket [10000, 19999]
        (19_999, "semi-buy"),
        (15_000, "semi-buy"),
        (10_000, "semi-buy"),
        # semi-eco bucket [5000, 9999]
        (9_999, "semi-eco"),
        (7_500, "semi-eco"),
        (5_000, "semi-eco"),
        # eco bucket (< 5000)
        (4_999, "eco"),
        (2_500, "eco"),
        (0, "eco"),
        # defensive: negative → eco (CRule: no precondition needed)
        (-1, "eco"),
        (-1000, "eco"),
    ],
)
def test_credits_to_bucket_boundaries(credits: int, expected: str) -> None:
    """Every boundary transition matches CLAUDE.md 'Domain constants' table."""
    assert credits_to_bucket(credits) == expected


# --------------------------------------------------------------------------- #
# 2. Range closure                                                            #
# --------------------------------------------------------------------------- #


@given(credits=st.integers(min_value=-100_000, max_value=10_000_000))
@settings(max_examples=200, deadline=None)
def test_credits_to_bucket_returns_canonical_label(credits: int) -> None:
    """Output is always one of {full, semi-buy, semi-eco, eco}."""
    assert credits_to_bucket(credits) in VALID_LABELS


# --------------------------------------------------------------------------- #
# 3. CRule 12 — no inline bucket-floor literals in source                     #
# --------------------------------------------------------------------------- #


def test_source_uses_constants_not_inline_literals() -> None:
    """src/pricing/economy.py must not inline 20000 / 10000 / 5000 in the body.

    Mirrors tests/pricing/test_round_conclusion.py:test_source_uses_shrink_prior_constant_not_inline_literal.
    """
    src = Path("src/pricing/economy.py").read_text(encoding="utf-8")
    code_lines: list[str] = []
    in_docstring = False
    for line in src.splitlines():
        stripped = line.strip()
        if stripped.startswith('"""') or stripped.startswith("'''"):
            count = stripped.count('"""') + stripped.count("'''")
            if count == 2:
                continue
            in_docstring = not in_docstring
            continue
        if in_docstring:
            continue
        if stripped.startswith("#"):
            continue
        if not stripped:
            continue
        code_lines.append(line)
    code = "\n".join(code_lines)
    # Forbidden inline literals (CON-no-magic-numbers)
    for forbidden in ("20000", "20_000", "10000", "10_000", " 5000", "5_000"):
        # " 5000" with leading space avoids matching a substring of "15000"
        assert forbidden not in code, (
            f"Bare literal {forbidden!r} found in code; use ECON_BUCKET_*_FLOOR"
        )
    # Required constant references
    assert "ECON_BUCKET_FULL_FLOOR" in code
    assert "ECON_BUCKET_SEMI_BUY_FLOOR" in code
    assert "ECON_BUCKET_SEMI_ECO_FLOOR" in code
