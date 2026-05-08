"""Shared calibration-test fixtures.

Synthetic round_events row factory + in-memory SQLite engine. NO real probe
data dependency — all calibrator tests in this directory operate on synthetic
data so the test suite runs in <30s in CI.

Sources
-------
- 02-VALIDATION.md (Wave 0: synthetic round_events row factory, in-memory SQLite)
- 02-RESEARCH.md §"Pattern 3: Bottom-up shrinkage walk"
- D-06 / D-07 / D-09 / CON-round-events-schema
- 03-02: src.pricing.economy DELETED per CLAUDE.md "Economy buckets — DEPRECATED in v2".
  Local stub retained so the v1 calibrator test still parses; 03-07 rewrites the calibrator.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from typing import Any

import pytest


def credits_to_bucket(credits: int) -> str:
    # 03-02: src.pricing.economy DELETED per CLAUDE.md "Economy buckets — DEPRECATED in v2".
    # Local stub so this v1 calibrator test still parses; 03-07 rewrites the calibrator.
    if credits >= 20_000:
        return "full"
    if credits >= 10_000:
        return "semi-buy"
    if credits >= 5_000:
        return "semi-eco"
    return "eco"


def _make_state(
    t_offset: float,
    kind: str,
    numerical_diff: int,
    bomb_planted: bool,
    side: str,
    econ_bucket: str,
) -> dict[str, Any]:
    """Build a single mid_round_states[] entry per D-06 / D-07."""
    return {
        "t_offset": t_offset,
        "kind": kind,
        "numerical_diff": numerical_diff,
        "bomb_planted": bomb_planted,
        "side": side,
        "econ_bucket": econ_bucket,
    }


def _make_round_event(
    match_id: str,
    map_num: int,
    round_num: int,
    map_name: str,
    round_won_by_a: bool,
    states: list[dict[str, Any]],
    *,
    ts_round_start: float = 0.0,
    ts_round_end: float = 60.0,
    ts_first_kill: float | None = None,
    ts_bomb_plant: float | None = None,
) -> dict[str, Any]:
    """Build a single round_events row matching CON-round-events-schema."""
    return {
        "match_id": match_id,
        "map_num": map_num,
        "round_num": round_num,
        "map_name": map_name,
        "round_won_by_a": round_won_by_a,
        "ts_round_start": ts_round_start,
        "ts_first_kill": ts_first_kill,
        "ts_bomb_plant": ts_bomb_plant,
        "ts_round_end": ts_round_end,
        "mid_round_states": states,
    }


@pytest.fixture
def synthetic_round_events() -> list[dict[str, Any]]:
    """Deterministic 50-row synthetic round_events dataset across two maps.

    Coverage:
      - 25 rounds on Lotus, 25 on Bind.
      - Both attacker and defender wins (~67% A-win rate; deterministic).
      - Mix of plant, defuse, and no-plant termination patterns.
      - Mix of econ_buckets: full / semi-buy / semi-eco / eco.
      - numerical_diff cycle ∈ {-1, 0, +1} so calibrator's bottom-up walk
        sees populated parent cells across all minimal keys.
    """
    rows: list[dict[str, Any]] = []
    map_names = ["Lotus", "Bind"]
    sides = ["atk", "def"]
    # Use credits_to_bucket on representative loadouts so the synthetic dataset
    # cannot drift from CON-economy-buckets (CRule 2 — single canonical mapping).
    bucket_credits = [25_000, 15_000, 7_500, 2_500]  # full / semi-buy / semi-eco / eco
    nd_cycle = [-1, 0, 1]

    for i in range(50):
        map_num = i // 25
        round_num = (i % 25) + 1
        map_name = map_names[map_num]
        side = sides[i % 2]
        bucket = credits_to_bucket(bucket_credits[i % 4])
        won_by_a = (i % 3) != 0  # ~67% A-win rate; deterministic
        nd = nd_cycle[i % 3]

        states = [
            _make_state(0.0, "heartbeat", 0, False, side, bucket),
            _make_state(5.0, "heartbeat", 0, False, side, bucket),
            _make_state(12.0, "event", nd, False, side, bucket),
            _make_state(15.0, "heartbeat", nd, False, side, bucket),
            _make_state(28.0, "event", nd, True, side, bucket),
        ]
        rows.append(
            _make_round_event(
                match_id=f"M{map_num:03d}",
                map_num=map_num,
                round_num=round_num,
                map_name=map_name,
                round_won_by_a=won_by_a,
                states=states,
                ts_first_kill=12.0,
                ts_bomb_plant=28.0,
            )
        )
    return rows


@pytest.fixture
def in_memory_sqlite() -> Iterator[sqlite3.Connection]:
    """In-memory SQLite connection — no filesystem touched."""
    conn = sqlite3.connect(":memory:")
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def synthetic_half_rates() -> dict[str, Any]:
    """Synthetic half_win_rates.json shape — drives side_baseline derivation."""
    return {
        "team_map_side": {},
        "league_map_side": {
            "Lotus|atk": {"wins": 67, "total": 134, "rate": 0.500},
            "Lotus|def": {"wins": 73, "total": 146, "rate": 0.500},
            "Bind|atk": {"wins": 60, "total": 120, "rate": 0.500},
            "Bind|def": {"wins": 60, "total": 120, "rate": 0.500},
        },
        "overall_avg": 0.5,
    }
