"""Phase 2 Wave 3: empirical-Bayes shrinkage calibration of round_conclusion cells.

Reads `data/round_events.sqlite` (Plan 02-03 output) + `data/half_win_rates.json`
(existing Phase-0 input). Walks bottom-up per D-14: side_baseline -> cells_minimal
-> cells_no_map -> cells_no_econ -> cells_full. Persists to
`models/round_conclusion.json` via RoundConclusionLookup.to_json.

Idempotent (D-16): re-running on a refreshed SQLite regenerates the JSON. Cells
with n < MIN_CELL_N are dropped before persistence (Pitfall 5: still serialize
raw n/p_hat/parent_p, never shrunk()). The MIN_CELL_N filter is also the
implementation of D-05's partial-pass policy: when a Path-A pull is missing
bomb_plant events for >50% of rounds, the resulting
cells_full[(...,bomb_planted=True,...)] entries naturally have n < MIN_CELL_N
and get dropped — the fallback chain then walks to cells_no_econ /
cells_no_map / cells_minimal, satisfying D-05's 'populate only cells_no_econ
and cells_no_map' rule. BLOCKER 3 adds an explicit short-circuit: if
02-PROBE-LOG.md records 'D-05 partial-pass triggered: true', the cells_full
population pass is skipped entirely.

Usage:
    python -m scripts.calibrate_round_conclusion \\
        --in-db data/round_events.sqlite \\
        --in-half-rates data/half_win_rates.json \\
        --out-json models/round_conclusion.json

Sources
-------
- 02-RESEARCH.md §"Pattern 3: Bottom-up shrinkage walk" (D-14 verbatim)
- 02-PATTERNS.md §"scripts/calibrate_round_conclusion.py"
- D-13 / D-14 / D-15 / D-16 / D-05 / BLOCKER 2 / BLOCKER 3
- src/pricing/round_conclusion.py (RoundConclusionLookup, _Cell — formula source)
- src/config/constants.py (MIN_CELL_N=5, SHRINK_PRIOR=15.0)
- CRule 12 (no magic numbers) / CRule 2 (single shrinkage formula on _Cell.shrunk)
"""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from src.config.constants import MIN_CELL_N
from src.pricing.round_conclusion import RoundConclusionLookup, _Cell

logger = logging.getLogger(__name__)

# Floor on distinct match_id rows in round_events SQLite. Suffix-stripped
# (rib.gg perspective doubling adds `::1` / `::2` suffixes per Plan 02-03
# BLOCKER 4) so 1000 doubled rows become 500 distinct match_ids.
_MIN_DISTINCT_MATCH_IDS: int = 500
"""Minimum distinct (suffix-stripped) match_ids in round_events.sqlite for
calibration to proceed. Mirrors the must-have #1 acceptance bar in
.planning/phases/02-round-event-data/CONTEXT.md D-03 / 02-04-PLAN.md
preconditions block. Below this floor, calibrator exits 2 (BLOCKER 2)."""


# --------------------------------------------------------------------------- #
# Side baseline derivation                                                    #
# --------------------------------------------------------------------------- #


def _compute_side_baseline(half_rates: dict[str, Any]) -> dict[str, float]:
    """Derive per-side baseline from half_win_rates.json.

    Per-side average across `league_map_side` entries; falls back to
    `overall_avg` (typically 0.5) if no league entries match a side, and to
    0.5 if `overall_avg` is missing or non-numeric.
    """
    league = (
        half_rates.get("league_map_side", {}) if isinstance(half_rates, dict) else {}
    )
    overall_avg_raw = (
        half_rates.get("overall_avg", 0.5) if isinstance(half_rates, dict) else 0.5
    )
    try:
        overall = float(overall_avg_raw)
    except (TypeError, ValueError):
        overall = 0.5
    out: dict[str, float] = {}
    for side in ("atk", "def"):
        rates = [
            float(v["rate"])
            for k, v in league.items()
            if isinstance(v, dict) and k.endswith(f"|{side}") and "rate" in v
        ]
        out[side] = (sum(rates) / len(rates)) if rates else overall
    return out


# --------------------------------------------------------------------------- #
# Bottom-up empirical-Bayes shrinkage walk (D-14)                             #
# --------------------------------------------------------------------------- #


def calibrate(
    rows: list[dict[str, Any]],
    half_rates: dict[str, Any],
    *,
    min_cell_n: int = MIN_CELL_N,
    skip_cells_full: bool = False,
) -> RoundConclusionLookup:
    """Bottom-up empirical-Bayes shrinkage walk per D-14.

    Args:
        rows: List of dicts, each carrying:
            match_id, map_num, round_num, map_name, round_won_by_a (bool/int),
            mid_round_states (list[dict]).
        half_rates: Parsed contents of data/half_win_rates.json.
        min_cell_n: Cells with `n < min_cell_n` are dropped from the result.
        skip_cells_full: BLOCKER 3 / D-05 partial-pass policy — when True, the
            cells_full pass is skipped entirely (only cells_minimal /
            cells_no_map / cells_no_econ are populated).

    Returns:
        A RoundConclusionLookup ready for to_json or live use.
    """
    lookup = RoundConclusionLookup()

    # 1. side_baseline (parent for cells_minimal)
    lookup.side_baseline.update(_compute_side_baseline(half_rates))

    # 2. cells_minimal — keyed (numerical_diff, bomb_planted)
    minimal_agg: dict[tuple[int, bool], list[int]] = defaultdict(lambda: [0, 0])
    for r in rows:
        won = bool(int(r["round_won_by_a"]))
        for s in r["mid_round_states"]:
            key2: tuple[int, bool] = (
                int(s["numerical_diff"]),
                bool(s["bomb_planted"]),
            )
            minimal_agg[key2][0] += int(won)
            minimal_agg[key2][1] += 1
    parent_minimal = (
        lookup.side_baseline.get("atk", 0.5) + lookup.side_baseline.get("def", 0.5)
    ) / 2
    for key2, (w2, n2) in minimal_agg.items():
        if n2 == 0 or n2 < min_cell_n:
            continue
        lookup.cells_minimal[key2] = _Cell(
            n=n2, p_hat=w2 / n2, parent_p=parent_minimal
        )

    # 3. cells_no_map — keyed (numerical_diff, bomb_planted, side)
    no_map_agg: dict[tuple[int, bool, str], list[int]] = defaultdict(lambda: [0, 0])
    for r in rows:
        won = bool(int(r["round_won_by_a"]))
        for s in r["mid_round_states"]:
            key3: tuple[int, bool, str] = (
                int(s["numerical_diff"]),
                bool(s["bomb_planted"]),
                str(s["side"]),
            )
            no_map_agg[key3][0] += int(won)
            no_map_agg[key3][1] += 1
    for key3, (w3, n3) in no_map_agg.items():
        if n3 == 0 or n3 < min_cell_n:
            continue
        nd3, bp3, side3 = key3
        parent3 = lookup.cells_minimal.get((nd3, bp3))
        parent_p3 = (
            parent3.shrunk()
            if parent3 is not None
            else lookup.side_baseline.get(side3, 0.5)
        )
        lookup.cells_no_map[key3] = _Cell(n=n3, p_hat=w3 / n3, parent_p=parent_p3)

    # 4. cells_no_econ — keyed (numerical_diff, bomb_planted, side, map_name)
    no_econ_agg: dict[tuple[int, bool, str, str], list[int]] = defaultdict(
        lambda: [0, 0]
    )
    for r in rows:
        won = bool(int(r["round_won_by_a"]))
        map_name = str(r["map_name"])
        for s in r["mid_round_states"]:
            key4: tuple[int, bool, str, str] = (
                int(s["numerical_diff"]),
                bool(s["bomb_planted"]),
                str(s["side"]),
                map_name,
            )
            no_econ_agg[key4][0] += int(won)
            no_econ_agg[key4][1] += 1
    for key4, (w4, n4) in no_econ_agg.items():
        if n4 == 0 or n4 < min_cell_n:
            continue
        nd4, bp4, side4, _mp4 = key4
        parent4 = lookup.cells_no_map.get((nd4, bp4, side4))
        parent_p4 = (
            parent4.shrunk()
            if parent4 is not None
            else lookup.side_baseline.get(side4, 0.5)
        )
        lookup.cells_no_econ[key4] = _Cell(n=n4, p_hat=w4 / n4, parent_p=parent_p4)

    # 5. cells_full — keyed (numerical_diff, bomb_planted, side, econ_bucket, map_name)
    if skip_cells_full:
        logger.info(
            "D-05 partial-pass: skipping cells_full population (BLOCKER 3)"
        )
        return lookup

    full_agg: dict[tuple[int, bool, str, str, str], list[int]] = defaultdict(
        lambda: [0, 0]
    )
    for r in rows:
        won = bool(int(r["round_won_by_a"]))
        map_name = str(r["map_name"])
        for s in r["mid_round_states"]:
            key5: tuple[int, bool, str, str, str] = (
                int(s["numerical_diff"]),
                bool(s["bomb_planted"]),
                str(s["side"]),
                str(s["econ_bucket"]),
                map_name,
            )
            full_agg[key5][0] += int(won)
            full_agg[key5][1] += 1
    for key5, (w5, n5) in full_agg.items():
        if n5 == 0 or n5 < min_cell_n:
            continue
        nd5, bp5, side5, _econ5, mp5 = key5
        parent5 = lookup.cells_no_econ.get((nd5, bp5, side5, mp5))
        parent_p5 = (
            parent5.shrunk()
            if parent5 is not None
            else lookup.side_baseline.get(side5, 0.5)
        )
        lookup.cells_full[key5] = _Cell(n=n5, p_hat=w5 / n5, parent_p=parent_p5)

    return lookup


# --------------------------------------------------------------------------- #
# SQLite reader                                                               #
# --------------------------------------------------------------------------- #


def _round_events_has_columns(conn: sqlite3.Connection, cols: list[str]) -> bool:
    """True iff round_events has every column in ``cols``."""
    found = {row[1] for row in conn.execute("PRAGMA table_info(round_events)")}
    return all(c in found for c in cols)


def _load_rows_from_sqlite(db_path: Path) -> list[dict[str, Any]]:
    """Read round_events (+ matches if needed) into calibrate's expected shape.

    Two schema variants are supported:

    1. Production schema (Plan 02-03): `round_events` carries CON-round-events-schema
       (no per-round outcome column); `matches` carries `map_name` and the map-level
       `round_won_by_a`. Plan 02-03 BLOCKER 4 (perspective doubling) suffixes
       `round_events.match_id` with `::1` / `::2` to encode which team is "A" for
       that row, while `matches.match_id` stays plain — and `matches.team_a_team_num`
       holds the perspective key. We strip the suffix to match the plain id, AND
       align on `team_a_team_num` so each suffixed row picks up the matching
       perspective's `round_won_by_a`.

    2. Self-contained test schema: `round_events` carries `round_won_by_a` and
       `map_name` directly (used by test_d05_partial_pass.py). We read inline.
    """
    rows: list[dict[str, Any]] = []
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        if _round_events_has_columns(conn, ["round_won_by_a", "map_name"]):
            cursor = conn.execute(
                """SELECT match_id, map_num, round_num, mid_round_states,
                          map_name, round_won_by_a
                   FROM round_events"""
            )
        else:
            # Suffix-aware JOIN: round_events.match_id is e.g. '212886::1';
            # matches.match_id is plain '212886', keyed additionally by
            # team_a_team_num=1 for the team-A perspective. Stripping the
            # suffix on both sides yields the correct (per-perspective) match.
            cursor = conn.execute(
                """SELECT re.match_id, re.map_num, re.round_num,
                          re.mid_round_states, m.map_name, m.round_won_by_a
                   FROM round_events re
                   JOIN matches m
                     ON m.match_id = substr(re.match_id, 1,
                                            instr(re.match_id, '::') - 1)
                    AND m.map_num = re.map_num
                    AND CAST(m.team_a_team_num AS TEXT) =
                        substr(re.match_id, instr(re.match_id, '::') + 2)"""
            )
        for r in cursor:
            try:
                states = json.loads(r["mid_round_states"])
            except (TypeError, ValueError):
                states = []
            rows.append(
                {
                    "match_id": r["match_id"],
                    "map_num": r["map_num"],
                    "round_num": r["round_num"],
                    "map_name": r["map_name"],
                    "round_won_by_a": int(r["round_won_by_a"] or 0),
                    "mid_round_states": states,
                }
            )
    return rows


# --------------------------------------------------------------------------- #
# D-05 partial-pass detection (BLOCKER 3)                                     #
# --------------------------------------------------------------------------- #


def _d05_partial_pass_active(probe_log_path: Path) -> bool:
    """True iff PROBE-LOG records `D-05 partial-pass triggered: true`.

    Tolerates both the markdown-bold variant
    (`**D-05 partial-pass triggered:** true`) and the plain-text variant
    (`D-05 partial-pass triggered: true`) — Plan 02-03's _render_probe_log
    emits the bold form; reviewers may edit either.
    """
    if not probe_log_path.exists():
        return False
    text = probe_log_path.read_text(encoding="utf-8")
    return (
        "D-05 partial-pass triggered: true" in text
        or "D-05 partial-pass triggered:** true" in text
    )


# --------------------------------------------------------------------------- #
# Testable seam — calibrate from on-disk inputs                               #
# --------------------------------------------------------------------------- #


def calibrate_from_sqlite(
    events_db: Path,
    half_rates_path: Path,
    *,
    probe_log_path: Path | None = None,
    min_cell_n: int = MIN_CELL_N,
) -> RoundConclusionLookup:
    """End-to-end seam: reads inputs, applies D-05 short-circuit, returns lookup.

    The CLI `main()` is a thin wrapper around this; tests
    (`test_d05_partial_pass.py`) call it directly to avoid argparse boilerplate.
    """
    rows = _load_rows_from_sqlite(events_db)
    half_rates = json.loads(half_rates_path.read_text(encoding="utf-8"))
    skip_full = (
        _d05_partial_pass_active(probe_log_path) if probe_log_path is not None else False
    )
    return calibrate(
        rows, half_rates, min_cell_n=min_cell_n, skip_cells_full=skip_full
    )


# --------------------------------------------------------------------------- #
# CLI                                                                         #
# --------------------------------------------------------------------------- #


_DEFAULT_PROBE_LOG: Path = Path(
    ".planning/phases/02-round-event-data/02-PROBE-LOG.md"
)


def _count_distinct_match_ids(db_path: Path) -> int:
    """Count distinct (suffix-stripped) match_id rows in round_events.

    rib.gg perspective doubling appends `::1` / `::2` suffixes per Plan 02-03
    BLOCKER 4. Strip the suffix before counting so 1000 doubled rows count as
    500 distinct logical matches.
    """
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            "SELECT COUNT(DISTINCT substr(match_id, 1, instr(match_id, '::')-1)) "
            "FROM round_events WHERE instr(match_id, '::') > 0"
        )
        suffixed = int(cur.fetchone()[0])
        if suffixed > 0:
            return suffixed
        # Fall back: tests may use plain match_ids without suffix.
        cur = conn.execute("SELECT COUNT(DISTINCT match_id) FROM round_events")
        return int(cur.fetchone()[0])


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for the calibrator.

    Exits 2 (config error) when:
      - --in-db does not exist (BLOCKER 2: no silent synthetic-seed fallback).
      - --in-half-rates does not exist.
      - round_events.sqlite has fewer than _MIN_DISTINCT_MATCH_IDS distinct
        (suffix-stripped) match_id rows.
    Exits 0 on success.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--in-db",
        type=Path,
        default=Path("data/round_events.sqlite"),
        help="Input SQLite produced by Plan 02-03.",
    )
    parser.add_argument(
        "--in-half-rates",
        type=Path,
        default=Path("data/half_win_rates.json"),
        help="Input half_win_rates.json (Phase 0 artifact).",
    )
    parser.add_argument(
        "--out-json",
        type=Path,
        default=Path("models/round_conclusion.json"),
        help="Output calibrated lookup.",
    )
    parser.add_argument(
        "--min-cell-n",
        type=int,
        default=MIN_CELL_N,
        help=f"Drop cells with n < this (default {MIN_CELL_N}).",
    )
    parser.add_argument(
        "--probe-log",
        type=Path,
        default=_DEFAULT_PROBE_LOG,
        help="Path to 02-PROBE-LOG.md for D-05 partial-pass detection.",
    )
    args = parser.parse_args(argv)

    # BLOCKER 2: deterministic preflight, no silent synthetic-seed fallback.
    if not args.in_db.exists():
        print(
            f"ERROR: {args.in_db} does not exist. Run scripts/probe_round_events.py "
            f"--live first (Path A), or plan phase 02.5 for Path B "
            f"via `/gsd-insert-phase 02.5 --slug path-b-ocr`.",
            file=sys.stderr,
        )
        return 2

    if not args.in_half_rates.exists():
        print(f"ERROR: {args.in_half_rates} not found.", file=sys.stderr)
        return 2

    n_matches = _count_distinct_match_ids(args.in_db)
    if n_matches < _MIN_DISTINCT_MATCH_IDS:
        print(
            f"ERROR: round_events.sqlite has only {n_matches} distinct match_id "
            f"rows; need >={_MIN_DISTINCT_MATCH_IDS} per CONTEXT.md D-03 coverage "
            f"bar. Re-run probe or plan 02.5.",
            file=sys.stderr,
        )
        return 2

    lookup = calibrate_from_sqlite(
        events_db=args.in_db,
        half_rates_path=args.in_half_rates,
        probe_log_path=args.probe_log,
        min_cell_n=args.min_cell_n,
    )
    lookup.to_json(args.out_json)

    print(
        f"Calibrated. side_baseline={lookup.side_baseline} "
        f"cells_minimal={len(lookup.cells_minimal)} "
        f"cells_no_map={len(lookup.cells_no_map)} "
        f"cells_no_econ={len(lookup.cells_no_econ)} "
        f"cells_full={len(lookup.cells_full)} "
        f"-> {args.out_json}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
