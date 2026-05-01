"""half_win_rates.json ingestion: present file, missing file, zero-coverage file.

D-14: side_baseline derivation must gracefully handle every input shape.
"""

from __future__ import annotations

from typing import Any

import pytest

from scripts.calibrate_round_conclusion import _compute_side_baseline


def test_side_baseline_present_file() -> None:
    half_rates: dict[str, Any] = {
        "league_map_side": {
            "Lotus|atk": {"rate": 0.47, "wins": 47, "total": 100},
            "Lotus|def": {"rate": 0.53, "wins": 53, "total": 100},
            "Bind|atk": {"rate": 0.45, "wins": 45, "total": 100},
            "Bind|def": {"rate": 0.55, "wins": 55, "total": 100},
        },
        "overall_avg": 0.5,
    }
    out = _compute_side_baseline(half_rates)
    assert out["atk"] == pytest.approx(0.46)
    assert out["def"] == pytest.approx(0.54)


def test_side_baseline_empty_dict_falls_back_to_overall_avg() -> None:
    """Empty half_rates -> fallback to overall_avg = 0.5."""
    out = _compute_side_baseline({})
    assert out["atk"] == 0.5
    assert out["def"] == 0.5


def test_side_baseline_no_league_falls_back_to_overall() -> None:
    """league_map_side empty but overall_avg present -> use overall_avg."""
    out = _compute_side_baseline({"overall_avg": 0.48, "league_map_side": {}})
    assert out["atk"] == pytest.approx(0.48)
    assert out["def"] == pytest.approx(0.48)


def test_side_baseline_handles_missing_overall_avg() -> None:
    """No overall_avg, no league entries -> 0.5."""
    out = _compute_side_baseline({"league_map_side": {}})
    assert out["atk"] == 0.5
    assert out["def"] == 0.5


def test_side_baseline_skips_malformed_entries() -> None:
    """Defensive: entries without `rate` are ignored."""
    half_rates: dict[str, Any] = {
        "league_map_side": {
            "Lotus|atk": {"wins": 47},  # missing rate -> skip
            "Lotus|def": {"rate": 0.6},
        },
        "overall_avg": 0.5,
    }
    out = _compute_side_baseline(half_rates)
    assert out["atk"] == 0.5  # no usable atk entries -> fallback overall_avg
    assert out["def"] == pytest.approx(0.6)


def test_side_baseline_handles_non_numeric_overall_avg() -> None:
    """overall_avg='foo' -> fallback to 0.5 instead of crashing."""
    out = _compute_side_baseline({"overall_avg": "not-a-number"})
    assert out["atk"] == 0.5
    assert out["def"] == 0.5
