"""GREEN tests for scripts.calibrate_round_conclusion_v2 (REQ-round-conclusion-lookup).

Three tests pin the v2 calibrator contract per 03-07-PLAN.md Task 2:

  - ``test_v2_keys_are_post_plant_only``: states with ``bomb_planted=False``
    do NOT contribute to any cell; cells_full keys come exclusively from
    bomb_planted=True states.
  - ``test_v2_schema_version_round_trip``: ``to_json`` writes
    ``schema_version=2``; ``from_json`` round-trips cell counts at every tier.
  - ``test_sample_alive_counts_constraint``: 03-SPEC §7 / RESEARCH Pitfall 5
    invariant — ``a_alive + b_alive ≤ 10`` for every state in the synthetic
    dataset.

The synthetic dataset is local to this file (not shared via conftest) — the
v2 calibrator's row shape differs from the v1 conftest fixture's shape, and
duplicating the small factory here keeps the test ergonomic.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from scripts.calibrate_round_conclusion_v2 import (
    _build_lookup_from_rows,
    _derive_keys,
)
from src.config.constants import POST_PLANT_TIMER_S, TIME_BUCKET_WIDTH_S
from src.pricing.round_conclusion import RoundConclusionLookup

# --------------------------------------------------------------------------- #
# Synthetic dataset fixture                                                   #
# --------------------------------------------------------------------------- #


@pytest.fixture
def synthetic_calibration_rows() -> list[dict[str, Any]]:
    """50 rows; mixed bomb_planted / not + varied alive counts.

    Half the rows have a planted state (i % 2 == 0); the other half have a
    NOT-planted state with the same a_alive/b_alive shape — those latter rows
    must NOT contribute to any cell. Outcomes are deterministically biased on
    (att - def_) so calibrator runs without divide-by-zero on the side
    baseline.
    """
    rows: list[dict[str, Any]] = []
    for i in range(50):
        bomb_planted = i % 2 == 0
        side_a = "atk" if i % 4 < 2 else "def"
        a_alive = max(1, 5 - (i % 5))
        b_alive = max(1, 5 - ((i + 2) % 5))
        ts_bomb_plant = 30.0 if bomb_planted else None

        if side_a == "atk":
            att, def_ = a_alive, b_alive
        else:
            att, def_ = b_alive, a_alive
        # A wins when its side+alive-counts favor it: attacking and att>def_
        # OR defending and def_>att. Deterministic — no RNG.
        a_won = bool(att > def_) if side_a == "atk" else bool(def_ > att)

        states: list[dict[str, Any]] = [
            {
                "t_offset": 35.0 if bomb_planted else 20.0,
                "kind": "event",
                "a_alive": a_alive,
                "b_alive": b_alive,
                "bomb_planted": bomb_planted,
                "side": side_a,
            }
        ]
        rows.append(
            {
                "match_id": f"synth-{i:03d}",
                "map_name": "Lotus" if i % 3 == 0 else "Bind",
                "mid_round_states": states,
                "ts_bomb_plant": ts_bomb_plant,
                "round_outcome_a_won": a_won,
                "side_a_this_round": side_a,
            }
        )
    return rows


# --------------------------------------------------------------------------- #
# Tests                                                                       #
# --------------------------------------------------------------------------- #


def test_v2_keys_are_post_plant_only(
    synthetic_calibration_rows: list[dict[str, Any]],
) -> None:
    """Lookup cells contain ONLY keys derived from bomb_planted=True states.

    Drop ``min_cell_n`` to 1 so even a single-sample cell survives, then
    confirm the calibrator built at least one cell (the planted half of the
    dataset has a deterministic Lotus / Bind / side / alive-counts spread).
    """
    lookup = _build_lookup_from_rows(synthetic_calibration_rows, min_cell_n=1)

    # Side baseline must be from planted rows ONLY (the not-planted rows
    # contributed zero to side_totals, so the baseline reflects only the
    # planted-row outcome distribution).
    assert sum(lookup.side_baseline.values()) > 0.0

    total_cells = (
        len(lookup.cells_full)
        + len(lookup.cells_no_time)
        + len(lookup.cells_no_map)
        + len(lookup.cells_minimal)
    )
    assert total_cells > 0, (
        f"calibrator produced 0 cells from "
        f"{sum(1 for r in synthetic_calibration_rows if r['ts_bomb_plant'] is not None)} "
        "bomb_planted rows"
    )

    # Defensive: drop the planted half of the dataset and re-run; cells_full
    # should be EMPTY because no row has a bomb_planted=True state.
    not_planted_only = [
        r for r in synthetic_calibration_rows if r["ts_bomb_plant"] is None
    ]
    lookup_empty = _build_lookup_from_rows(not_planted_only, min_cell_n=1)
    assert len(lookup_empty.cells_full) == 0
    assert len(lookup_empty.cells_no_time) == 0
    assert len(lookup_empty.cells_no_map) == 0
    assert len(lookup_empty.cells_minimal) == 0


def test_v2_schema_version_round_trip(
    synthetic_calibration_rows: list[dict[str, Any]], tmp_path: Any
) -> None:
    """``to_json`` → ``from_json`` round-trips with ``schema_version=2``."""
    lookup = _build_lookup_from_rows(synthetic_calibration_rows, min_cell_n=1)
    out_path = tmp_path / "rc_v2.json"
    lookup.to_json(out_path)

    raw = json.loads(out_path.read_text(encoding="utf-8"))
    assert raw.get("schema_version") == 2

    reloaded = RoundConclusionLookup.from_json(out_path)
    assert reloaded.side_baseline == lookup.side_baseline
    assert len(reloaded.cells_minimal) == len(lookup.cells_minimal)
    assert len(reloaded.cells_no_map) == len(lookup.cells_no_map)
    assert len(reloaded.cells_no_time) == len(lookup.cells_no_time)
    assert len(reloaded.cells_full) == len(lookup.cells_full)


def test_sample_alive_counts_constraint(
    synthetic_calibration_rows: list[dict[str, Any]],
) -> None:
    """SPEC §7 / RESEARCH Pitfall 5: ``a_alive + b_alive ≤ 10`` always."""
    for row in synthetic_calibration_rows:
        for st in row["mid_round_states"]:
            assert 0 <= st["a_alive"] <= 5, st
            assert 0 <= st["b_alive"] <= 5, st
            assert st["a_alive"] + st["b_alive"] <= 10, st


# --------------------------------------------------------------------------- #
# _derive_keys unit tests — pin D-10 time bucket math                         #
# --------------------------------------------------------------------------- #


def test_derive_keys_returns_none_when_not_planted() -> None:
    state = {
        "t_offset": 35.0,
        "a_alive": 3,
        "b_alive": 2,
        "bomb_planted": False,
        "side": "atk",
    }
    assert _derive_keys(state, ts_bomb_plant=30.0, side_a="atk") is None


def test_derive_keys_attacker_perspective_when_side_a_atk() -> None:
    """When team A is attacking, att=a_alive."""
    state = {
        "t_offset": 35.0,
        "a_alive": 4,
        "b_alive": 2,
        "bomb_planted": True,
        "side": "atk",
    }
    keys = _derive_keys(state, ts_bomb_plant=30.0, side_a="atk")
    assert keys is not None
    att, def_, time_bucket, side = keys
    assert att == 4
    assert def_ == 2
    assert side == "atk"
    # 5s elapsed since plant → 40s remaining → bucket = int(40/5) = 8.
    assert time_bucket == 8


def test_derive_keys_defender_perspective_when_side_a_def() -> None:
    """When team A is defending, att=b_alive (the OTHER team is attacking)."""
    state = {
        "t_offset": 35.0,
        "a_alive": 4,
        "b_alive": 2,
        "bomb_planted": True,
        "side": "def",
    }
    keys = _derive_keys(state, ts_bomb_plant=30.0, side_a="def")
    assert keys is not None
    att, def_, _, side = keys
    assert att == 2  # b_alive — team B attacks because team A is defending
    assert def_ == 4
    assert side == "def"


def test_derive_keys_clips_time_bucket_to_8() -> None:
    """Edge case: a state at the exact bomb-plant moment yields bucket 8 (not 9)."""
    state = {
        "t_offset": 30.0,  # exactly at plant — t_remaining = 45.0
        "a_alive": 3,
        "b_alive": 3,
        "bomb_planted": True,
        "side": "atk",
    }
    keys = _derive_keys(state, ts_bomb_plant=30.0, side_a="atk")
    assert keys is not None
    _, _, time_bucket, _ = keys
    # t_remaining = 45.0; int(45/5) = 9; clip to 8.
    assert time_bucket == 8


def test_derive_keys_clips_time_bucket_to_zero_at_timer_expiry() -> None:
    """When >= POST_PLANT_TIMER_S has elapsed, time_bucket=0 (not negative)."""
    state = {
        "t_offset": 30.0 + POST_PLANT_TIMER_S + 5.0,  # 5s past timer
        "a_alive": 1,
        "b_alive": 1,
        "bomb_planted": True,
        "side": "atk",
    }
    keys = _derive_keys(state, ts_bomb_plant=30.0, side_a="atk")
    assert keys is not None
    _, _, time_bucket, _ = keys
    assert time_bucket == 0


def test_time_bucket_width_invariant() -> None:
    """D-10: 9 buckets × 5s = 45s post-plant timer."""
    assert POST_PLANT_TIMER_S / TIME_BUCKET_WIDTH_S == 9.0
