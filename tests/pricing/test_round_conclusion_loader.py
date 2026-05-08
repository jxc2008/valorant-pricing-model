"""Loader integration tests for src.pricing.round_conclusion (v2 surface).

Verifies that ``RoundConclusionLookup.from_json("models/round_conclusion.json")``
returns a usable v2 lookup whose ``post_plant_p(...)`` returns finite floats
in [0, 1].

03-02 rewrites this file in-place from the v1 5-arg ``lookup(...)`` surface to
the v2 ``post_plant_p(att, def_, time_bucket, side, map_name)`` surface.
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
    reason="models/round_conclusion.json not yet generated",
)
@given(
    att=st.integers(min_value=0, max_value=5),
    def_=st.integers(min_value=0, max_value=5),
    time_bucket=st.integers(min_value=0, max_value=8),
    side=st.sampled_from(["atk", "def"]),
    map_name=st.sampled_from(
        ["Lotus", "Bind", "Haven", "Ascent", "Pearl", "Split", "Sunset"]
    ),
)
@settings(max_examples=200, deadline=None)
def test_loaded_lookup_post_plant_returns_in_range(
    att: int,
    def_: int,
    time_bucket: int,
    side: str,
    map_name: str,
) -> None:
    """v2 post_plant_p over the loaded lookup returns finite values in [0, 1]."""
    lookup = RoundConclusionLookup.from_json(MODEL_PATH)
    val = lookup.post_plant_p(att, def_, time_bucket, side, map_name)
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
    """Path-C-equivalent: empty lookup + default side_baseline returns 0.5
    on post_plant_p for both sides.
    """
    lookup = RoundConclusionLookup()
    assert lookup.post_plant_p(0, 0, 0, "atk", "Lotus") == 0.5
    assert lookup.post_plant_p(0, 0, 0, "def", "Lotus") == 0.5


def test_loaded_v2_lookup_has_synthetic_lotus_cell() -> None:
    """The 03-02 synthetic v2 file populates one cells_full cell at
    (att=3, def=2, time_bucket=0, side='atk', map='Lotus'). 03-07 replaces
    the synthetic file with the real ~25k-sample v2 calibration.
    """
    if not MODEL_PATH.exists():
        pytest.skip("models/round_conclusion.json not yet generated")
    lookup = RoundConclusionLookup.from_json(MODEL_PATH)
    # The synthetic cell exists; verify post_plant_p hits it (off baseline).
    val = lookup.post_plant_p(3, 2, 0, "atk", "Lotus")
    baseline = lookup.side_baseline.get("atk", 0.5)
    assert abs(val - baseline) > 0.01, (
        f"synthetic Lotus cell should shift post_plant_p off baseline; "
        f"got {val} vs baseline {baseline}"
    )
