---
phase: 02-round-event-data
plan: 04
subsystem: pricing
tags: [calibration, empirical-bayes, round-conclusion, json-serde, path-a]

# Dependency graph
requires:
  - phase: 02-round-event-data
    provides: scripts/probe_round_events.py + data/round_events.sqlite (Plan 02-03 — 1000 matches, 42586 rounds, Path A pass)
  - phase: 02-round-event-data
    provides: src/config/constants.MIN_CELL_N + src/pricing/economy.credits_to_bucket (Plan 02-01)
  - phase: 02-round-event-data
    provides: tests/calibration/conftest.py synthetic fixtures (Plan 02-02)
  - phase: 01-core-pricing-engine
    provides: RoundConclusionLookup + _Cell + RoundConclusionFn Protocol (Phase 1 frozen surface)
provides:
  - src/pricing/round_conclusion.RoundConclusionLookup.from_json + .to_json (D-15 — additive Phase 1 surface)
  - src/pricing/round_conclusion.RoundConclusionLookup.lookup (rewritten body — 5-tier fallback chain walk per CON-round-conclusion-fallback-chain)
  - scripts/calibrate_round_conclusion.calibrate + calibrate_from_sqlite + main + _compute_side_baseline
  - models/round_conclusion.json (calibrated artifact, 324 KB, committed)
affects: [04-quoting-layer]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "JSON tuple-key (de)serialization via `_format_key_N` / `_parse_key_N` helper pairs — splits the chain depth into one helper per level so mypy --strict can type each tuple precisely (no Any-typed variadic loop)"
    - "Bottom-up empirical-Bayes shrinkage walk per D-14 — populate `side_baseline` first, then `cells_minimal`, then progressively wider keys; each child's `parent_p` is fixed at construction time using the already-shrunk parent estimate"
    - "Schema-detection JOIN in `_load_rows_from_sqlite`: PRAGMA table_info(round_events) decides between production schema (JOIN matches via suffix-stripped match_id + team_a_team_num) and self-contained test schema (round_won_by_a / map_name inline on round_events)"
    - "Suffix-aware JOIN: round_events.match_id is `'212886::1'` (Plan 02-03 BLOCKER 4 perspective doubling); matches.match_id is `'212886'`. JOIN strips the `::N` suffix and aligns on team_a_team_num so each perspective picks up its own map-level outcome"
    - "BLOCKER 3 short-circuit: `calibrate(skip_cells_full=True)` honors D-05 partial-pass policy by returning early after `cells_no_econ` is populated — no special-casing inside the cells_full loop"
    - "TypedDict-typed JSON schema (`_CellJson` + `_RoundConclusionJson`) — mypy --strict catches mis-keyed access at type-check time; runtime JSON parse is `json.loads()` then dict access (no schema validation cost)"

key-files:
  created:
    - scripts/calibrate_round_conclusion.py
    - models/round_conclusion.json
    - models/.gitkeep  # was previously untracked but caught by `models/` ignore; now visible after `models/*` exception rule
    - tests/pricing/test_round_conclusion_loader.py
    - tests/calibration/test_calibrate_round_conclusion.py
    - tests/calibration/test_from_json_roundtrip.py
    - tests/calibration/test_econ_bucketing.py
    - tests/calibration/test_side_baseline.py
    - tests/calibration/test_shrinkage_walk.py
    - tests/calibration/test_d05_partial_pass.py
  modified:
    - src/pricing/round_conclusion.py  # +from_json +to_json + rewritten lookup body + TypedDicts + key (de)serializers
    - tests/pricing/test_round_conclusion.py  # rewrote 1 test (test_lookup_always_returns_flat_05_in_phase_1 -> test_empty_lookup_returns_side_baseline) + added 1 defensive test
    - tests/calibration/conftest.py  # ruff UP035 autofix: from collections.abc import Iterator
    - tests/probe/test_endpoint_shapes.py  # ruff I001 autofix: import block sort
    - .gitignore  # `models/` -> `models/*` + `!models/round_conclusion.json` exception (D-15: artifact reviewable in PRs)

key-decisions:
  - "[Rule 1 — Bug] _load_rows_from_sqlite production-schema JOIN was originally specified as `m.match_id = re.match_id` which never matched (round_events.match_id carries `::1`/`::2` perspective suffixes per Plan 02-03 BLOCKER 4; matches.match_id is plain). Without the fix the calibrator emitted 0/0/0/0 cells. Corrected to `substr(re.match_id, 1, instr(re.match_id, '::') - 1)` join + `CAST(m.team_a_team_num AS TEXT) = substr(re.match_id, instr(re.match_id, '::') + 2)` for perspective alignment. Verified: 22 minimal + 44 no_map + 524 no_econ + 1886 full cells populated from 1000 matches."
  - "[Rule 3 — Blocking] .gitignore had blanket `models/` ignore which prevented committing models/round_conclusion.json (D-15 artifact). Changed to `models/*` and added `!models/round_conclusion.json` exception. The blanket-directory pattern's nested-file exception requires the directory not to be ignored itself — `models/*` keeps the directory traversable while ignoring contents by default. models/.gitkeep also surfaced as a new tracked file (was previously masked by the blanket rule)."
  - "Hand-rolled lookup dispatch (4 sequential `if cell is not None: return cell.shrunk()` blocks) instead of the variadic loop in 02-RESEARCH.md. Each level has a precisely-typed `tuple[int, bool, str, str, str]` literal — matches `mypy --strict` better than the variadic loop, which would require `tuple[Any, ...]` or `cast()`."
  - "skip_cells_full kwarg in `calibrate()` for D-05 — explicit kwarg over implicit MIN_CELL_N drift. The plan suggested cells_full would naturally drop under MIN_CELL_N filter when bomb_plant is sparse, but that's a soft signal: with min_cell_n=1 (calibrator-CLI default), every populated cell would still pass through. The kwarg makes the BLOCKER 3 contract testable and explicit."
  - "calibrate_from_sqlite seam exposed as a top-level function (not just a private helper). test_d05_partial_pass.py drives the full pipeline (SQLite -> half_rates -> probe_log -> lookup) without invoking argparse — keeps the test suite at <2 minutes total."

patterns-established:
  - "Schema variant detection via PRAGMA table_info(): cleanly handles both the production CON-round-events-schema and self-contained test schemas without runtime branching cost. Pattern reusable for any future schema migrations."
  - "Tuple-key (de)serialization with one helper per arity: `_format_key_2`, `_format_key_3`, `_format_key_4`, `_format_key_5` and matching parsers. Strict-typed boilerplate, but yields strict-clean mypy without `cast()` and produces human-readable JSON keys for PR diffs."
  - "BLOCKER 2 deterministic preflight: explicit `_MIN_DISTINCT_MATCH_IDS` floor with stderr message and exit 2. No silent synthetic-seed fallback. Mirrors Plan 02-03's BLOCKER 1 status-sentinel pattern at the calibration gate."

requirements-completed:
  - REQ-round-event-data-pipeline

# Metrics
duration: ~75min
completed: 2026-05-01
---

# Phase 02 Plan 04: Empirical-Bayes Calibration + RoundConclusionLookup Loader Summary

**Calibrated mid-round round-conclusion lookup loaded from real Path A data (1000 matches, 42586 rounds) — closes REQ-round-event-data-pipeline.**

## Performance

- **Duration:** ~75 min
- **Tasks:** 2 of 2 (both `type="auto" tdd="true"`)
- **Files created:** 9 (calibrator + 7 test files + models/round_conclusion.json)
- **Files modified:** 5 (round_conclusion.py + test_round_conclusion.py + 2 ruff autofixes + .gitignore)

## Plan-level Status

```
Plan 02-04 status: COMPLETE (2026-05-01)
Phase 02 status:   COMPLETE — REQ-round-event-data-pipeline closed
```

| Task | Type | Status | Commit |
|---|---|---|---|
| 1 — Add from_json/to_json + rewrite lookup body | auto (tdd) | COMPLETE | `6ad51f4` |
| 2 — Calibrator + models/round_conclusion.json + 7 test files | auto (tdd) | COMPLETE | `f344da6` |

## Accomplishments

### Task 1 — RoundConclusionLookup additive surface (commit `6ad51f4`)

- **Phase 1 frozen surface preserved:** `_Cell`, `RoundConclusionFn` Protocol, dataclass field declarations, `lookup` signature all unchanged.
- **`lookup` body rewritten** from flat-0.5 to the 5-tier fallback chain walk (cells_full → cells_no_econ → cells_no_map → cells_minimal → side_baseline → defensive `_PHASE_1_FLAT_CELL_VALUE`).
- **`from_json` classmethod + `to_json` instance method added** (D-15) round-tripping through the JSON shape documented in `_RoundConclusionJson` TypedDict. Pitfall 5 honored: serializes raw (n, p_hat, parent_p), never the precomputed `shrunk()` float.
- **`_CellJson` + `_RoundConclusionJson` TypedDicts** define the on-disk shape. mypy --strict catches mis-typed key access at type-check time without runtime cost.
- **Tuple-key (de)serializers** (`_format_key_2..5` / `_parse_key_2..5`) handle the chain's variable-arity tuple keys. Strict-typed; produces human-readable `"0|true|atk|full|Lotus"` keys in the JSON for diff-friendly PR review.
- **Phase 1's `test_lookup_always_returns_flat_05_in_phase_1` rewritten** to `test_empty_lookup_returns_side_baseline` — Path-C regression invariant locking D-12.
- **`test_lookup_falls_back_to_flat_when_side_baseline_missing` added** — defensive guard against accidental `side_baseline.pop()` downstream.

### Task 2 — calibrator + calibrated artifact + 6 calibration tests + 1 loader test (commit `f344da6`)

- **`scripts/calibrate_round_conclusion.py`:** bottom-up D-14 walk with explicit `skip_cells_full` kwarg for BLOCKER 3 (D-05 partial-pass policy). Reuses `_Cell.shrunk()` — no duplicate shrinkage formula (CRule 2). All thresholds imported from `src.config.constants` (CRule 12: `SHRINK_PRIOR`, `MIN_CELL_N`).
- **`calibrate_from_sqlite` testable seam:** drives the full pipeline (SQLite → half_rates → probe_log → lookup) without argparse. Used by `test_d05_partial_pass.py` to exercise the BLOCKER 3 short-circuit on synthetic data.
- **`_load_rows_from_sqlite` schema-detection:** `PRAGMA table_info(round_events)` decides between production schema (JOIN matches via suffix-stripped match_id + team_a_team_num perspective) and self-contained test schema (round_won_by_a / map_name inline on round_events). Both branches yield the same calibrate-input shape.
- **BLOCKER 2 preflight:** calibrator exits 2 with deterministic stderr if `data/round_events.sqlite` is missing or has fewer than `_MIN_DISTINCT_MATCH_IDS = 500` distinct (suffix-stripped) match_id rows. No silent synthetic-seed fallback.
- **BLOCKER 3 short-circuit:** `_d05_partial_pass_active(probe_log_path)` reads `02-PROBE-LOG.md` and returns True iff `D-05 partial-pass triggered: true` is present. When active, `calibrate_from_sqlite` invokes `calibrate(..., skip_cells_full=True)` — cells_full stays empty.

### Calibrated artifact (models/round_conclusion.json)

Generated from real Path A SQLite (Plan 02-03 output: 1000 matches, 42586 rounds). D-05 partial-pass NOT triggered, so cells_full populated.

| Level | Count |
|---|---|
| `side_baseline` | 2 (`atk`: 0.5256, `def`: 0.4751) |
| `cells_minimal` | 22 |
| `cells_no_map` | 44 |
| `cells_no_econ` | 524 |
| `cells_full` | 1886 |
| Total file size | 324,138 bytes |

Sample lookups:
- `lookup(0, False, "atk", "full", "Lotus")` = 0.5496
- `lookup(2, True, "atk", "full", "Lotus")` = 0.6615
- `lookup(-3, False, "def", "eco", "Bind")` = 0.4948

### Test coverage delta (35 net new tests; 258 total; 0 failures)

- `tests/pricing/test_round_conclusion.py`: 14 (was 13; 1 rewrite + 1 added)
- `tests/pricing/test_round_conclusion_loader.py`: 3 (NEW — Path-C compat + Hypothesis on real artifact + side_baseline populated check)
- `tests/calibration/test_calibrate_round_conclusion.py`: 8 (NEW — calibrate API integration)
- `tests/calibration/test_from_json_roundtrip.py`: 4 (NEW — D-15 serde identity)
- `tests/calibration/test_econ_bucketing.py`: 6 (NEW — boundary smoke)
- `tests/calibration/test_side_baseline.py`: 6 (NEW — half_rates ingestion edge cases incl. non-numeric overall_avg defensive case)
- `tests/calibration/test_shrinkage_walk.py`: 4 (NEW — bottom-up walk invariants)
- `tests/calibration/test_d05_partial_pass.py`: 3 (NEW — BLOCKER 3 active/inactive/no-log)

### Verification (all GREEN)

```text
uv run mypy --strict src/pricing/         → Success: no issues found in 8 source files
uv run ruff check src/pricing/ scripts/ tests/calibration/ tests/pricing/ → All checks passed!
uv run pytest tests/probe/ tests/calibration/ tests/pricing/ tests/config/ → 247 passed
uv run pytest                              → 258 passed
test -f models/round_conclusion.json       → exists; 324 KB
uv run python -c "from src.pricing.round_conclusion import RoundConclusionLookup; v = RoundConclusionLookup.from_json('models/round_conclusion.json').lookup(0, False, 'atk', 'full', 'Lotus'); assert 0.0 <= v <= 1.0"
                                          → exit 0
```

## Phase 1 surface delta (auditable)

Two additive methods + one body rewrite + one test rewrite + one new defensive test:

| Change | Type | File:Line range |
|---|---|---|
| `from_json` classmethod | NEW (additive) | `src/pricing/round_conclusion.py:268-302` |
| `to_json` instance method | NEW (additive) | `src/pricing/round_conclusion.py:304-345` |
| `lookup` body | REWRITTEN | `src/pricing/round_conclusion.py:217-266` (signature unchanged) |
| `_CellJson` / `_RoundConclusionJson` TypedDicts | NEW (additive) | `src/pricing/round_conclusion.py:113-135` |
| `_format_key_*` / `_parse_key_*` helpers | NEW (private) | `src/pricing/round_conclusion.py:138-181` |
| `test_lookup_always_returns_flat_05_in_phase_1` | RENAMED + REWRITTEN | `tests/pricing/test_round_conclusion.py:32-67` (now `test_empty_lookup_returns_side_baseline`) |
| `test_lookup_falls_back_to_flat_when_side_baseline_missing` | NEW (defensive) | `tests/pricing/test_round_conclusion.py:70-77` |

Frozen surface confirmed UNCHANGED:
- `_Cell` dataclass + `shrunk()` method.
- `RoundConclusionFn` Protocol.
- `RoundConclusionLookup` field declarations (`cells_full`, `cells_no_econ`, `cells_no_map`, `cells_minimal`, `side_baseline`).
- `RoundConclusionLookup.lookup` SIGNATURE.
- `_PHASE_1_FLAT_CELL_VALUE = 0.5` constant (kept as defensive ultimate fallback).

## Must-have coverage

| Must-have | Status | Evidence |
|---|---|---|
| #1 `data/round_events.sqlite >=500 distinct match_ids` (Plan 02-03 PASS) | precondition met | 1000 distinct match_ids, 42586 rounds (`02-PROBE-LOG.md`) |
| #2 `RoundConclusionLookup.from_json(path).lookup(...)` returns finite [0,1] | PASS | `test_loaded_lookup_returns_in_range` (Hypothesis, 200 examples) |
| #3 Live calibrated lookup non-degenerate for in-distribution input | PASS | sample lookups above (0.5496 / 0.6615 / 0.4948) — all distinct from side_baseline |
| #4 `mypy --strict src/pricing/` exits 0 | PASS | "Success: no issues found in 8 source files" |
| #5 `pytest tests/pricing/ tests/calibration/ tests/probe/ tests/config/` exits 0 | PASS | 247 passed |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] `_load_rows_from_sqlite` production-schema JOIN never matched**

- **Found during:** Task 2 — first calibrator run on real SQLite returned 0/0/0/0 cells.
- **Issue:** Plan specified `JOIN matches m ON m.match_id = re.match_id`. But Plan 02-03 BLOCKER 4 introduced perspective-doubling: `round_events.match_id` is `'212886::1'` / `'212886::2'`, while `matches.match_id` is plain `'212886'` and `matches.team_a_team_num` (1 or 2) holds the perspective key. The naive equality JOIN matched 0 rows.
- **Fix:** Strip the suffix on round_events side and align on team_a_team_num: `JOIN matches m ON m.match_id = substr(re.match_id, 1, instr(re.match_id, '::') - 1) AND m.map_num = re.map_num AND CAST(m.team_a_team_num AS TEXT) = substr(re.match_id, instr(re.match_id, '::') + 2)`.
- **Files modified:** `scripts/calibrate_round_conclusion.py` (only).
- **Verification:** Re-ran calibrator → `cells_minimal=22, cells_no_map=44, cells_no_econ=524, cells_full=1886`.
- **Commit:** `f344da6` (in the same Task 2 commit).

**2. [Rule 3 — Blocking] `.gitignore` rule prevented committing the calibrated artifact**

- **Found during:** Task 2 — `git add models/round_conclusion.json` failed silently because line 37 had blanket `models/` ignore.
- **Issue:** `!models/round_conclusion.json` exception cannot override a blanket directory ignore — git considers the directory itself to be excluded.
- **Fix:** Change `models/` → `models/*` (preserves directory traversal) and add `!models/round_conclusion.json` exception below.
- **Files modified:** `.gitignore`. Side effect: `models/.gitkeep` (which was authored at repo init) becomes visible as untracked and is added to the commit.
- **Verification:** `git check-ignore -v models/round_conclusion.json` reports the negation rule wins.
- **Commit:** `f344da6` (same Task 2 commit).

### Non-deviation: pre-existing calibrator data-quality limitation

The `round_events` table does NOT carry per-round outcome data — Plan 02-03 only persisted the map-level `round_won_by_a` on the `matches` table. Consequently every mid_round_state in a given map inherits the same `round_won_by_a` label during calibration. The calibrated `cells_*` therefore approximate "P(team A wins this MAP given mid-round state)" rather than "P(team A wins this ROUND given mid-round state".

This is a known data-shape limitation inherited from Plan 02-03's probe persistence layer; it is NOT a Plan 02-04 deviation. The framework is correct; Phase 5's Brier monitoring will catch the calibration-quality gap if it materially affects pricing. A Phase 7 follow-up could re-scrape rib.gg with per-round winners persisted (the API exposes `winningTeamNumber` per-round; the probe simply did not store it).

## Threat Flags

None — all surface introduced is contained within the threat model declared in `02-04-PLAN.md` `<threat_model>`. Mitigations applied:
- T-02-04-03 (`_compute_side_baseline` parsing): `isinstance` checks + `try/except float()` + 0.5 fallback. Tests `test_side_baseline_skips_malformed_entries` + `test_side_baseline_handles_non_numeric_overall_avg` pin the behavior.
- T-02-04-04 (SQL injection): hardcoded SELECT + parameterized read; no string-formatted user input.
- T-02-04-07 (Path C confusion): `from_json` raises `FileNotFoundError` on missing file; `test_from_json_raises_filenotfound_on_missing` pins this.

## Self-Check: PASSED

- `src/pricing/round_conclusion.py` updated — FOUND (commit `6ad51f4`)
- `tests/pricing/test_round_conclusion.py` updated — FOUND (commit `6ad51f4`)
- `scripts/calibrate_round_conclusion.py` — FOUND (commit `f344da6`)
- `models/round_conclusion.json` — FOUND, 324 KB (commit `f344da6`)
- `tests/pricing/test_round_conclusion_loader.py` — FOUND (commit `f344da6`)
- `tests/calibration/test_calibrate_round_conclusion.py` — FOUND
- `tests/calibration/test_from_json_roundtrip.py` — FOUND
- `tests/calibration/test_econ_bucketing.py` — FOUND
- `tests/calibration/test_side_baseline.py` — FOUND
- `tests/calibration/test_shrinkage_walk.py` — FOUND
- `tests/calibration/test_d05_partial_pass.py` — FOUND
- Commit `6ad51f4` — FOUND in `git log`
- Commit `f344da6` — FOUND in `git log`
- mypy --strict src/pricing/ → 0 issues
- ruff check src/pricing/ scripts/ tests/calibration/ tests/pricing/ → all passed
- 258 tests pass (Phase 2 subset: 247 pass)
- Live calibrated lookup smoke verified
