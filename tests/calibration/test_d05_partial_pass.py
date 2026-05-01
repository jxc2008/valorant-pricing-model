"""BLOCKER 3 regression: when 02-PROBE-LOG.md records 'D-05 partial-pass triggered: true',
the calibrator MUST skip the cells_full population pass and yield empty cells_full
while populating cells_no_econ / cells_no_map / cells_minimal normally.

Source: 02-CONTEXT.md D-05; checker pass-2 BLOCKER 3 fix.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from scripts.calibrate_round_conclusion import calibrate_from_sqlite
from src.pricing.round_conclusion import RoundConclusionLookup


def _write_synthetic_sparse_db(db_path: Path, n_rounds: int = 50) -> None:
    """Write n_rounds rows where 70% have ts_bomb_plant=NULL (sparse mid-round event class).

    Schema includes round_won_by_a + map_name inline on round_events so the
    self-contained test schema branch in _load_rows_from_sqlite triggers (no
    join with matches needed).
    """
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE round_events ("
        "match_id TEXT NOT NULL, map_num INTEGER NOT NULL, round_num INTEGER NOT NULL, "
        "ts_round_start REAL NOT NULL, ts_first_kill REAL, ts_bomb_plant REAL, "
        "ts_round_end REAL NOT NULL, mid_round_states TEXT NOT NULL, "
        "round_won_by_a INTEGER NOT NULL, map_name TEXT NOT NULL, "
        "PRIMARY KEY (match_id, map_num, round_num))"
    )
    for i in range(n_rounds):
        plant_ts = None if (i % 10) < 7 else 30.0  # 70% sparse
        states = json.dumps(
            [
                {
                    "t_offset": 0.0,
                    "kind": "heartbeat",
                    "numerical_diff": 0,
                    "bomb_planted": False,
                    "side": "atk" if i % 2 == 0 else "def",
                    "econ_bucket": "full",
                },
            ]
        )
        conn.execute(
            "INSERT INTO round_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                f"M{i:03d}",
                0,
                (i % 25) + 1,
                0.0,
                5.0,
                plant_ts,
                90.0,
                states,
                i % 2,
                "Lotus",
            ),
        )
    conn.commit()
    conn.close()


def test_d05_active_yields_empty_cells_full(tmp_path: Path) -> None:
    """D-05 partial-pass triggered: cells_full MUST be empty; cells_no_econ populated."""
    db = tmp_path / "round_events.sqlite"
    _write_synthetic_sparse_db(db)

    probe_log = tmp_path / "02-PROBE-LOG.md"
    probe_log.write_text(
        "# Phase 2 Probe Log\n\n## Event Coverage (D-05 partial-pass policy)\n"
        "- Rounds with ts_bomb_plant: 30% (15/50)\n"
        "- **D-05 partial-pass triggered:** true\n",
        encoding="utf-8",
    )

    half_rates_path = tmp_path / "half_win_rates.json"
    half_rates_path.write_text(
        json.dumps(
            {
                "league_map_side": {
                    "Lotus|atk": {"rate": 0.471, "wins": 47, "total": 100},
                    "Lotus|def": {"rate": 0.529, "wins": 53, "total": 100},
                }
            }
        ),
        encoding="utf-8",
    )

    lookup: RoundConclusionLookup = calibrate_from_sqlite(
        events_db=db,
        half_rates_path=half_rates_path,
        probe_log_path=probe_log,
        min_cell_n=1,
    )

    assert lookup.cells_full == {}, (
        "D-05 active: cells_full MUST be empty (calibrator skipped the pass per "
        "partial-pass policy)"
    )
    # cells_minimal should still populate from the same data
    assert len(lookup.cells_minimal) > 0, (
        "cells_minimal must populate even under D-05"
    )


def test_d05_inactive_populates_cells_full(tmp_path: Path) -> None:
    """Without the D-05 flag, the calibrator runs the full bottom-up walk."""
    db = tmp_path / "round_events.sqlite"
    _write_synthetic_sparse_db(db, n_rounds=80)

    probe_log = tmp_path / "02-PROBE-LOG.md"
    probe_log.write_text(
        "# Phase 2 Probe Log\n\n## Event Coverage\n"
        "- Rounds with ts_bomb_plant: 80% (64/80)\n"
        "- **D-05 partial-pass triggered:** false\n",
        encoding="utf-8",
    )

    half_rates_path = tmp_path / "half_win_rates.json"
    half_rates_path.write_text(
        json.dumps({"league_map_side": {}}), encoding="utf-8"
    )

    lookup: RoundConclusionLookup = calibrate_from_sqlite(
        events_db=db,
        half_rates_path=half_rates_path,
        probe_log_path=probe_log,
        min_cell_n=1,
    )

    assert len(lookup.cells_full) > 0, "D-05 inactive: cells_full must populate"


def test_d05_no_probe_log_defaults_to_full_walk(tmp_path: Path) -> None:
    """Missing probe_log_path -> not active, full walk runs."""
    db = tmp_path / "round_events.sqlite"
    _write_synthetic_sparse_db(db, n_rounds=80)

    half_rates_path = tmp_path / "half_win_rates.json"
    half_rates_path.write_text(
        json.dumps({"league_map_side": {}}), encoding="utf-8"
    )

    lookup: RoundConclusionLookup = calibrate_from_sqlite(
        events_db=db,
        half_rates_path=half_rates_path,
        probe_log_path=None,
        min_cell_n=1,
    )

    assert len(lookup.cells_full) > 0
