"""Loader integration tests for src.pricing.round_conclusion.

Verifies that RoundConclusionLookup.from_json("models/round_conclusion.json")
returns a usable lookup whose `lookup(...)` returns finite floats in [0, 1].
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from src.pricing.round_conclusion import RoundConclusionLookup

MODEL_PATH: Path = Path("models/round_conclusion.json")


@pytest.mark.skipif(
    not MODEL_PATH.exists(),
    reason="models/round_conclusion.json not yet generated (Path C deferred)",
)
@given(
    numerical_diff=st.integers(min_value=-4, max_value=4),
    bomb_planted=st.booleans(),
    side=st.sampled_from(["atk", "def"]),
    econ_bucket=st.sampled_from(["full", "semi-buy", "semi-eco", "eco"]),
    map_name=st.sampled_from(
        ["Lotus", "Bind", "Haven", "Ascent", "Pearl", "Split", "Sunset"]
    ),
)
@settings(max_examples=200, deadline=None)
def test_loaded_lookup_returns_in_range(
    numerical_diff: int,
    bomb_planted: bool,
    side: str,
    econ_bucket: str,
    map_name: str,
) -> None:
    lookup = RoundConclusionLookup.from_json(MODEL_PATH)
    val = lookup.lookup(numerical_diff, bomb_planted, side, econ_bucket, map_name)
    assert 0.0 <= val <= 1.0
    assert not math.isnan(val)


@pytest.mark.skipif(
    not MODEL_PATH.exists(),
    reason="models/round_conclusion.json not yet generated",
)
def test_loaded_lookup_has_populated_side_baseline() -> None:
    lookup = RoundConclusionLookup.from_json(MODEL_PATH)
    assert "atk" in lookup.side_baseline
    assert "def" in lookup.side_baseline


def test_phase_c_compatibility_default_construction() -> None:
    """Path C: when models/round_conclusion.json doesn't exist, callers fall
    back to RoundConclusionLookup() and lookup returns side_baseline[side]
    (== 0.5 for both atk and def by default).
    """
    lookup = RoundConclusionLookup()
    assert lookup.lookup(0, False, "atk", "full", "Lotus") == 0.5
    assert lookup.lookup(0, False, "def", "full", "Lotus") == 0.5
