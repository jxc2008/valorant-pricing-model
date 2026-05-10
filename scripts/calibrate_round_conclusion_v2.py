"""Phase 3 v2 calibrator — fills models/round_conclusion.json with post-plant cells.

Reads ``data/round_events_v2.sqlite`` (produced by
``scripts/probe_round_events_v2.py``), filters mid_round_states[] to
``bomb_planted=True`` rows only, derives ``(att, def_, time_bucket, side,
map)`` per 03-CONTEXT.md D-04 / D-10, applies Bayesian shrinkage inheriting
``SHRINK_PRIOR=15``, drops cells with ``n < MIN_CELL_N``, and writes
``schema_version=2`` JSON via ``RoundConclusionLookup.to_json``.

Hierarchy (D-04 / Phase 2 D-13 carry-forward)
---------------------------------------------
``side_baseline`` (per-side empirical mean across all post-plant rows) →
``cells_minimal`` (att, def_) → ``cells_no_map`` (att, def_, side) →
``cells_no_time`` (att, def_, side, map) → ``cells_full`` (att, def_,
time_bucket, side, map). Each tier's parent_p is the parent-tier shrunk
estimate (top-down: minimal first, then no_map, then no_time, then full).

Sources
-------
- 03-CONTEXT.md D-04 (cell key shape), D-06 (schema_version=2),
  D-07 (a_alive/b_alive), D-10 (5s time buckets), D-13 (Bayesian shrinkage)
- 03-RESEARCH.md §"v2 calibrator + atomic-replace" wave decomposition
- 03-07-PLAN.md Task 2 algorithm sketch (interfaces block)
- src/pricing/round_conclusion.py — RoundConclusionLookup v2 surface
- scripts/calibrate_round_conclusion.py — Phase 2 v1 calibrator (carry-forward
  pattern: bottom-up shrinkage walk; v1 keys cells_no_econ which is dropped
  in v2 per CLAUDE.md "Economy buckets — DEPRECATED in v2")
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from src.config.constants import (
    MIN_CELL_N,
    POST_PLANT_TIMER_S,
    ROUND_CONCLUSION_JSON_PATH,
    ROUND_EVENTS_V2_DB_PATH,
    TIME_BUCKET_WIDTH_S,
)
from src.pricing.round_conclusion import RoundConclusionLookup, _Cell

# --------------------------------------------------------------------------- #
# Per-state key derivation (D-10 + D-04)                                      #
# --------------------------------------------------------------------------- #


def _derive_keys(
    state: dict[str, Any],
    ts_bomb_plant: float,
    side_a: str,
) -> tuple[int, int, int, str] | None:
    """Derive ``(att, def_, time_bucket, side)`` from one mid_round_state.

    Returns ``None`` when the state is not bomb_planted (defensive — callers
    should pre-filter, but the double-check keeps the function total).

    The cell's "side" axis is ``side_a``: the side team A is on this round.
    The att / def_ split is taken from ``a_alive`` / ``b_alive`` accordingly:
    when team A is attacking, ``att = a_alive``; when team A is defending,
    ``att = b_alive``.

    Time bucket math (D-10):
        ``t_remaining = clip(POST_PLANT_TIMER_S - (t_offset - ts_bomb_plant),
                              [0, POST_PLANT_TIMER_S])``
        ``time_bucket = min(8, int(t_remaining / TIME_BUCKET_WIDTH_S))``

    The ``min(8, ...)`` clip is structural: ``int(45 / 5) == 9``, but the
    cell axis only has 9 buckets indexed 0..8.
    """
    if not state.get("bomb_planted"):
        return None
    a_alive = int(state["a_alive"])
    b_alive = int(state["b_alive"])
    t_offset = float(state["t_offset"])
    if side_a == "atk":
        att, def_ = a_alive, b_alive
    else:
        att, def_ = b_alive, a_alive
    t_remaining = POST_PLANT_TIMER_S - (t_offset - ts_bomb_plant)
    if t_remaining < 0.0:
        t_remaining = 0.0
    elif t_remaining > POST_PLANT_TIMER_S:
        t_remaining = POST_PLANT_TIMER_S
    time_bucket = min(8, int(t_remaining / TIME_BUCKET_WIDTH_S))
    return att, def_, time_bucket, side_a


# --------------------------------------------------------------------------- #
# Top-down shrinkage walk (D-04 / D-13)                                       #
# --------------------------------------------------------------------------- #


def _build_lookup_from_rows(
    rows: Iterable[dict[str, Any]],
    *,
    min_cell_n: int = MIN_CELL_N,
) -> RoundConclusionLookup:
    """Pure function: aggregate rows into a calibrated RoundConclusionLookup.

    Each row dict carries:
        match_id, map_name, mid_round_states (list[dict] or JSON str),
        ts_bomb_plant (float), round_outcome_a_won (bool/int),
        side_a_this_round (str).

    Aggregation
    -----------
    For each mid_round_state where ``bomb_planted=True``, derive the v2 cell
    key tuple and accumulate at all four tiers (cells_minimal, cells_no_map,
    cells_no_time, cells_full) plus the side baseline. De-dup states within a
    single round via the cells_full tuple — heartbeats can produce identical
    keys 5s apart and we don't want to double-count the same state.

    Bayesian shrinkage walk (top-down):
      1. cells_minimal: parent_p = (atk_baseline + def_baseline) / 2.
      2. cells_no_map:  parent_p = cells_minimal[(att, def_)].shrunk()
                                   if present else side_baseline[side].
      3. cells_no_time: parent_p = cells_no_map[(att, def_, side)].shrunk()
                                   if present else side_baseline[side].
      4. cells_full:    parent_p = cells_no_time[(att, def_, side, map)].shrunk()
                                   if present else side_baseline[side].

    Cells with ``n < min_cell_n`` are dropped before persistence (Phase 2
    calibration policy carry-forward; below this floor _Cell.shrunk() is
    essentially parent_p and the JSON gets noisier without changing runtime
    lookup behavior).
    """
    side_totals: dict[str, list[int]] = {"atk": [0, 0], "def": [0, 0]}
    cells_minimal_raw: dict[tuple[int, int], list[int]] = defaultdict(
        lambda: [0, 0]
    )
    cells_no_map_raw: dict[tuple[int, int, str], list[int]] = defaultdict(
        lambda: [0, 0]
    )
    cells_no_time_raw: dict[tuple[int, int, str, str], list[int]] = defaultdict(
        lambda: [0, 0]
    )
    cells_full_raw: dict[
        tuple[int, int, int, str, str], list[int]
    ] = defaultdict(lambda: [0, 0])

    for row in rows:
        side_a = row["side_a_this_round"]
        ts_bomb_plant = row.get("ts_bomb_plant")
        if ts_bomb_plant is None:
            continue
        ts_bomb_plant_f = float(ts_bomb_plant)
        a_won = 1 if int(row["round_outcome_a_won"]) else 0
        states = row["mid_round_states"]
        if isinstance(states, str):
            states = json.loads(states)
        map_name = row["map_name"]
        seen_full_keys: set[tuple[int, int, int, str, str]] = set()
        for st in states:
            keys = _derive_keys(st, ts_bomb_plant_f, side_a)
            if keys is None:
                continue
            att, def_, time_bucket, side = keys
            tup_full: tuple[int, int, int, str, str] = (
                att,
                def_,
                time_bucket,
                side,
                map_name,
            )
            if tup_full in seen_full_keys:
                continue
            seen_full_keys.add(tup_full)

            side_totals[side][0] += 1
            side_totals[side][1] += a_won
            cells_minimal_raw[(att, def_)][0] += 1
            cells_minimal_raw[(att, def_)][1] += a_won
            cells_no_map_raw[(att, def_, side)][0] += 1
            cells_no_map_raw[(att, def_, side)][1] += a_won
            cells_no_time_raw[(att, def_, side, map_name)][0] += 1
            cells_no_time_raw[(att, def_, side, map_name)][1] += a_won
            cells_full_raw[tup_full][0] += 1
            cells_full_raw[tup_full][1] += a_won

    side_baseline = {
        s: (side_totals[s][1] / side_totals[s][0])
        if side_totals[s][0] > 0
        else 0.5
        for s in ("atk", "def")
    }

    lookup = RoundConclusionLookup(side_baseline=side_baseline)
    side_baseline_mean = (side_baseline["atk"] + side_baseline["def"]) / 2

    # Tier 1: cells_minimal — parent = mean of side_baseline.
    for (att, def_), (n, won) in cells_minimal_raw.items():
        if n < min_cell_n:
            continue
        lookup.cells_minimal[(att, def_)] = _Cell(
            n=n, p_hat=won / n, parent_p=side_baseline_mean
        )

    # Tier 2: cells_no_map — parent = cells_minimal[(att, def_)].shrunk()
    # if present, else side_baseline[side].
    for (att, def_, side), (n, won) in cells_no_map_raw.items():
        if n < min_cell_n:
            continue
        parent_cell = lookup.cells_minimal.get((att, def_))
        parent_p = (
            parent_cell.shrunk()
            if parent_cell is not None
            else side_baseline.get(side, 0.5)
        )
        lookup.cells_no_map[(att, def_, side)] = _Cell(
            n=n, p_hat=won / n, parent_p=parent_p
        )

    # Tier 3: cells_no_time — parent = cells_no_map[(att, def_, side)].shrunk()
    # if present, else side_baseline[side].
    for (att, def_, side, map_name), (n, won) in cells_no_time_raw.items():
        if n < min_cell_n:
            continue
        parent_cell = lookup.cells_no_map.get((att, def_, side))
        parent_p = (
            parent_cell.shrunk()
            if parent_cell is not None
            else side_baseline.get(side, 0.5)
        )
        lookup.cells_no_time[(att, def_, side, map_name)] = _Cell(
            n=n, p_hat=won / n, parent_p=parent_p
        )

    # Tier 4: cells_full — parent = cells_no_time[(att, def_, side, map)].shrunk()
    # if present, else side_baseline[side].
    for (att, def_, time_bucket, side, map_name), (
        n,
        won,
    ) in cells_full_raw.items():
        if n < min_cell_n:
            continue
        parent_cell = lookup.cells_no_time.get((att, def_, side, map_name))
        parent_p = (
            parent_cell.shrunk()
            if parent_cell is not None
            else side_baseline.get(side, 0.5)
        )
        lookup.cells_full[(att, def_, time_bucket, side, map_name)] = _Cell(
            n=n, p_hat=won / n, parent_p=parent_p
        )

    return lookup


# --------------------------------------------------------------------------- #
# SQLite reader                                                               #
# --------------------------------------------------------------------------- #


def _iterate_db(db_path: Path) -> Iterable[dict[str, Any]]:
    """Yield bomb-planted dict rows from data/round_events_v2.sqlite.

    Joins ``round_events_v2`` ↔ ``matches_v2`` on the suffix-encoded
    perspective key (round_events_v2.match_id ends with ``::1`` / ``::2``;
    matches_v2 is keyed on the plain match_id + team_a_team_num). Filters to
    rows where ``ts_bomb_plant IS NOT NULL`` so we don't iterate non-planted
    rounds — saves ~50% of the read volume on Phase 2-shape datasets.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute(
            """
            SELECT re.match_id            AS match_id,
                   re.map_num             AS map_num,
                   re.round_num           AS round_num,
                   re.mid_round_states    AS mid_round_states,
                   re.ts_bomb_plant       AS ts_bomb_plant,
                   m.map_name             AS map_name,
                   m.round_won_by_a       AS round_outcome_a_won,
                   m.side_a_this_round    AS side_a_this_round
            FROM round_events_v2 re
            JOIN matches_v2 m
              ON m.match_id = substr(re.match_id, 1,
                                     instr(re.match_id, '::') - 1)
             AND m.map_num = re.map_num
             AND CAST(m.team_a_team_num AS TEXT) =
                 substr(re.match_id, instr(re.match_id, '::') + 2)
            WHERE re.ts_bomb_plant IS NOT NULL
            """
        )
        for r in cursor:
            yield dict(r)
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Public entry point + CLI                                                    #
# --------------------------------------------------------------------------- #


def calibrate(
    db_path: Path,
    output_path: Path,
    *,
    min_cell_n: int = MIN_CELL_N,
) -> None:
    """End-to-end: read SQLite → build lookup → atomic-replace JSON.

    Prints a per-tier cell count summary on completion (matches Phase 2
    calibrator's stdout shape so operator logs stay diff-friendly).
    """
    rows = list(_iterate_db(db_path))
    print(f"loaded {len(rows)} bomb-planted rows from {db_path}")
    lookup = _build_lookup_from_rows(rows, min_cell_n=min_cell_n)
    print(f"side_baseline = {lookup.side_baseline}")
    print(f"cells_minimal: {len(lookup.cells_minimal)}")
    print(f"cells_no_map:  {len(lookup.cells_no_map)}")
    print(f"cells_no_time: {len(lookup.cells_no_time)}")
    print(f"cells_full:    {len(lookup.cells_full)}")
    lookup.to_json(output_path)
    print(f"wrote {output_path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db",
        type=Path,
        default=Path(ROUND_EVENTS_V2_DB_PATH),
        help=f"v2 SQLite path (default {ROUND_EVENTS_V2_DB_PATH}).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(ROUND_CONCLUSION_JSON_PATH),
        help=f"v2 round_conclusion.json output (default {ROUND_CONCLUSION_JSON_PATH}).",
    )
    parser.add_argument(
        "--min-cell-n",
        type=int,
        default=MIN_CELL_N,
        help=f"Drop cells with n < this (default {MIN_CELL_N}).",
    )
    args = parser.parse_args(argv)
    calibrate(args.db, args.output, min_cell_n=args.min_cell_n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
