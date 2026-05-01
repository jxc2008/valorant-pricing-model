"""RED tests for round_events SQLite DDL (CON-round-events-schema).

Pins the 8-column schema from constraints.md before Plan 02-03 writes it.
Must NOT add or remove columns at the row level.

Sources
-------
- CON-round-events-schema (constraints.md)
- 02-CONTEXT.md (frozen schema discipline)
"""

from __future__ import annotations

import sqlite3
from typing import Any

import pytest

probe_mod = pytest.importorskip(
    "scripts.probe_round_events",
    reason="Awaiting Plan 02-03 — scripts/probe_round_events.py",
)

EXPECTED_COLUMNS: tuple[str, ...] = (
    "match_id",
    "map_num",
    "round_num",
    "ts_round_start",
    "ts_first_kill",
    "ts_bomb_plant",
    "ts_round_end",
    "mid_round_states",
)


def test_create_round_events_schema_has_eight_columns(
    in_memory_sqlite: sqlite3.Connection,
) -> None:
    """CON-round-events-schema: exactly 8 columns; no additions, no drops."""
    probe_mod.create_round_events_schema(in_memory_sqlite)
    cols: list[Any] = list(
        in_memory_sqlite.execute("PRAGMA table_info(round_events)").fetchall()
    )
    actual_names = tuple(row[1] for row in cols)
    assert actual_names == EXPECTED_COLUMNS, (
        f"schema drift: expected {EXPECTED_COLUMNS}, got {actual_names}"
    )


def test_create_round_events_schema_has_composite_primary_key(
    in_memory_sqlite: sqlite3.Connection,
) -> None:
    """PK is (match_id, map_num, round_num) per CON-round-events-schema."""
    probe_mod.create_round_events_schema(in_memory_sqlite)
    cols: list[Any] = list(
        in_memory_sqlite.execute("PRAGMA table_info(round_events)").fetchall()
    )
    pk_cols = [row[1] for row in cols if row[5] > 0]
    assert sorted(pk_cols) == ["map_num", "match_id", "round_num"]


def test_create_round_events_schema_has_map_num_index(
    in_memory_sqlite: sqlite3.Connection,
) -> None:
    """Index `idx_round_events_map` on map_num for per-map calibration scans."""
    probe_mod.create_round_events_schema(in_memory_sqlite)
    indexes = list(
        in_memory_sqlite.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='round_events'"
        ).fetchall()
    )
    index_names = {row[0] for row in indexes}
    assert "idx_round_events_map" in index_names


def test_round_events_required_columns_are_not_null(
    in_memory_sqlite: sqlite3.Connection,
) -> None:
    """match_id, map_num, round_num, ts_round_start, ts_round_end, mid_round_states are NOT NULL.
    ts_first_kill and ts_bomb_plant ARE nullable (some rounds have no kill / no plant)."""
    probe_mod.create_round_events_schema(in_memory_sqlite)
    cols: list[Any] = list(
        in_memory_sqlite.execute("PRAGMA table_info(round_events)").fetchall()
    )
    notnull_by_name = {row[1]: row[3] for row in cols}
    for must_be_notnull in (
        "match_id",
        "map_num",
        "round_num",
        "ts_round_start",
        "ts_round_end",
        "mid_round_states",
    ):
        assert notnull_by_name[must_be_notnull] == 1, (
            f"{must_be_notnull} must be NOT NULL"
        )
    for must_be_nullable in ("ts_first_kill", "ts_bomb_plant"):
        assert notnull_by_name[must_be_nullable] == 0, (
            f"{must_be_nullable} must be nullable"
        )
