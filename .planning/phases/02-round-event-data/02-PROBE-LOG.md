# Phase 2 — Probe Log

**Run completed:** 2026-05-01T20:58:16.286309+00:00
**Decision:** Path A passed

## Path A — be-prod.rib.gg/v1/ (primary)

- Events fetched: 83
- Series fetched: 552
- Matches inserted: 1000 (target 1000)
- Rounds inserted: 42586
- Matches skipped (no events): 552

## Event Coverage (D-05 partial-pass policy)

- Rounds total: 21293
- Rounds with `ts_round_start`: 100.0% (21293)
- Rounds with `ts_first_kill`: 95.3% (20289)
- Rounds with `ts_round_end`: 100.0% (21293)
- Rounds with `ts_bomb_plant`: 59.6% (12691)
- **D-05 partial-pass triggered:** false
  - If true: calibrator MUST populate only `cells_no_econ` and `cells_no_map`; `cells_full` will be empty.

## Sources considered, rejected

- (2) `valorantr` R-package — R not installed on this Windows host; redundant with direct Python `requests` against the same `/v1/` endpoints.
- (3) `FlynV/RIB.GG-Web-Scraper` — Windows-binary Discord-bot tool, no Python library.
- (4) `bo3.gg` — match-level metadata only (no per-round events); useful as cross-confirm only.

## Acceptance evaluation (D-02)

- Target: 1000 matches.
- Achieved: 1000 matches.
- Floor for must-have #1: 500 matches.
- Pass: YES
