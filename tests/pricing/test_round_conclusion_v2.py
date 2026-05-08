"""REQ-round-conclusion-lookup — v2 surface tests (03-02 / D-04 / D-06).

Asserts:
  - ``post_plant_p`` walks the 5-tier hierarchy
    cells_full -> cells_no_time -> cells_no_map -> cells_minimal -> side_baseline.
  - ``RoundConclusionLookup.from_json`` HARD-FAILS on schema_version != 2 (D-06).
  - ``between_round_p`` returns the per-side baseline directly (no walk).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.config.constants import SHRINK_PRIOR
from src.pricing.round_conclusion import RoundConclusionLookup, _Cell


def test_post_plant_p_hierarchy() -> None:
    """5-tier walk: full -> no_time -> no_map -> minimal -> side_baseline."""
    lookup = RoundConclusionLookup()
    # Tier 1: cells_full hit
    lookup.cells_full[(3, 2, 0, "atk", "Lotus")] = _Cell(
        n=100, p_hat=0.7, parent_p=0.5
    )
    expected_full = (100 * 0.7 + SHRINK_PRIOR * 0.5) / (100 + SHRINK_PRIOR)
    assert lookup.post_plant_p(3, 2, 0, "atk", "Lotus") == pytest.approx(expected_full)

    # Tier 2: cells_no_time fall-through (different time_bucket; no cells_full match)
    lookup.cells_no_time[(2, 1, "atk", "Lotus")] = _Cell(
        n=50, p_hat=0.6, parent_p=0.5
    )
    expected_no_time = (50 * 0.6 + SHRINK_PRIOR * 0.5) / (50 + SHRINK_PRIOR)
    assert lookup.post_plant_p(2, 1, 5, "atk", "Lotus") == pytest.approx(
        expected_no_time
    )

    # Tier 3: cells_no_map fall-through (different map; no cells_full / cells_no_time)
    lookup.cells_no_map[(1, 1, "def")] = _Cell(n=30, p_hat=0.4, parent_p=0.5)
    expected_no_map = (30 * 0.4 + SHRINK_PRIOR * 0.5) / (30 + SHRINK_PRIOR)
    assert lookup.post_plant_p(1, 1, 0, "def", "Bind") == pytest.approx(
        expected_no_map
    )

    # Tier 4: cells_minimal fall-through (no side / map matches)
    lookup.cells_minimal[(0, 1)] = _Cell(n=10, p_hat=0.3, parent_p=0.5)
    expected_minimal = (10 * 0.3 + SHRINK_PRIOR * 0.5) / (10 + SHRINK_PRIOR)
    assert lookup.post_plant_p(0, 1, 0, "atk", "Bind") == pytest.approx(
        expected_minimal
    )

    # Tier 5: side_baseline fall-through (no cell at any tier matches)
    lookup.side_baseline["atk"] = 0.5256
    assert lookup.post_plant_p(5, 5, 0, "atk", "Bind") == pytest.approx(0.5256)


def test_from_json_rejects_v1(tmp_path: Path) -> None:
    """D-06: from_json HARD-FAILS on missing or non-2 schema_version (raises ValueError)."""
    p = tmp_path / "v1.json"
    # v1 file has no schema_version; v2 gate raises ValueError on load.
    p.write_text(
        json.dumps(
            {
                "side_baseline": {"atk": 0.5, "def": 0.5},
                "cells_full": {},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="schema_version"):
        RoundConclusionLookup.from_json(p)


def test_from_json_rejects_explicit_v1(tmp_path: Path) -> None:
    """D-06: from_json HARD-FAILS even when the file declares schema_version=1."""
    p = tmp_path / "v1_explicit.json"
    p.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "side_baseline": {"atk": 0.5, "def": 0.5},
                "cells_full": {},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="schema_version"):
        RoundConclusionLookup.from_json(p)


def test_between_round_p_returns_side_baseline() -> None:
    """D-04: between_round_p returns side_baseline[side] directly (no walk)."""
    lookup = RoundConclusionLookup(side_baseline={"atk": 0.6, "def": 0.4})
    assert lookup.between_round_p("atk", "Lotus", 5) == 0.6
    assert lookup.between_round_p("def", "Bind", 12) == 0.4
    # Defensive: unknown side defaults to 0.5
    assert lookup.between_round_p("unknown_side", "Haven", 0) == 0.5
