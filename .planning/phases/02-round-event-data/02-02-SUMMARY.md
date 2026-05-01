---
phase: 02-round-event-data
plan: 02
subsystem: testing
tags: [pytest, hypothesis, importorskip, sqlite, json-fixtures, ribgg]

# Dependency graph
requires:
  - phase: 02-round-event-data
    provides: src/config/constants.MID_ROUND_HEARTBEAT_S + ECON_BUCKET_*_FLOOR + RIBGG_*; src/pricing/economy.credits_to_bucket (Plan 02-01 artifacts)
provides:
  - tests/probe/ package — 9 schema tests pinning rib.gg /v1/{events,series,matches/{id}/details} JSON contract via 3 offline fixtures
  - tests/calibration/ package — 24 RED tests (3 modules) gating Plan 02-03's synthesize_mid_round_states / side_for_team_a / create_round_events_schema contracts; SKIP cleanly via pytest.importorskip until 02-03 ships
  - tests/calibration/conftest.py — synthetic_round_events 50-row factory + in_memory_sqlite + synthetic_half_rates fixtures driving Plan 02-04's calibrator tests
  - Match-details fixture coverage exercising plant-then-defuse, plant-then-time, and no-plant termination patterns (Pitfall 4 anchor)
affects: [02-03, 02-04]

# Tech tracking
tech-stack:
  added: []   # all dependencies (pytest, hypothesis) already present from Phase 0
  patterns:
    - "pytest.importorskip skip-gate for forward-declared RED tests (turns green automatically when consumed module exists)"
    - "Offline-fixture schema testing — fixtures hand-authored to match a verified-once API shape; live HTTP only in opt-in manual checkpoint (VALIDATION.md "Manual-Only Verifications")"
    - "Synthetic-data fixtures over real-data dependencies for fast (<5s) CI test runs"
    - "Three-pattern fixture coverage (plant+defuse, plant+time, no-plant) anchoring Pitfall 4 termination semantics"

key-files:
  created:
    - tests/probe/__init__.py
    - tests/probe/conftest.py
    - tests/probe/fixtures/events_response.json
    - tests/probe/fixtures/series_response.json
    - tests/probe/fixtures/match_details.json
    - tests/probe/test_endpoint_shapes.py
    - tests/calibration/__init__.py
    - tests/calibration/conftest.py
    - tests/calibration/test_synthesize_states.py
    - tests/calibration/test_side_mapping.py
    - tests/calibration/test_round_events_schema.py
  modified: []

key-decisions:
  - "Module-level `pytest.importorskip` in calibration RED tests — pytest collection short-circuits to 'N skipped' rather than enumerating individual parametrized cases, but the prompt's <important> block explicitly endorses this skip-gate idiom and success-criterion #6 mandates 'no errors at collection time'. The plan's >=11-collected-tests acceptance criterion is unsatisfiable under this idiom; honored prompt + skip-gate cleanliness over the count."
  - "Synthetic fixtures use src.pricing.economy.credits_to_bucket (Plan 02-01's canonical mapping) rather than hard-coding bucket labels — preserves CRule 2 (single canonical implementation). Drift between calibrator buckets and runtime buckets is now impossible by construction in the test fixtures."
  - "Match-details fixture authored with 3 rounds covering all three termination patterns (plant→defuse, plant→time, no-plant). Pitfall 4 is now test-anchored: any future regression in Plan 02-03's defuse handling would fail test_round_1_defuse_terminates_states_at_defuse_t_offset."

patterns-established:
  - "Offline-fixture-driven schema tests: hand-authored JSON fixtures recorded from a verified-once live probe; tests parse them like the production code will, but no HTTP is exercised in CI."
  - "RED skip-gate via pytest.importorskip: forward-declared tests for unwritten modules SKIP cleanly today, activate automatically when the module exists. Cleaner than pytest.xfail (which requires raising)."
  - "Synthetic dataset factories in conftest.py: pytest fixtures returning list[dict] of canonical-shape rows so calibrator tests do not depend on real probe data."

requirements-completed: []   # Plan 02-02 ships test scaffolds; the requirement REQ-round-event-data-pipeline closes when Plans 02-03/02-04 land.

# Metrics
duration: ~25min
completed: 2026-05-01
---

# Phase 02 Plan 02: Wave-0 Test Scaffolds (RED) Summary

**9 green offline-fixture schema tests + 24 RED skip-gated tests pinning the contracts of Plans 02-03 (probe transform / side mapping / SQLite DDL) and 02-04 (calibrator)**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-05-01T03:14:00Z (approx — after final 02-01 commit)
- **Completed:** 2026-05-01T03:29:30Z
- **Tasks:** 2 of 2 (both `type="auto"` `tdd="true"` per plan frontmatter)
- **Files modified:** 11 (all created)

## Accomplishments

- `tests/probe/` package shipped with 3 offline JSON fixtures (events / series / match-details) mirroring the rib.gg `be-prod.rib.gg/v1/` contract verified live 2026-04-30 (RESEARCH.md Pattern 1).
- 9 schema-parser tests passing green, including a coverage check that the match-details fixture exercises all three round-termination patterns (plant-then-defuse, plant-then-time, no-plant) — Pitfall 4 anchor.
- `tests/calibration/` package shipped with `synthetic_round_events` (50-row factory across Lotus/Bind, all 4 econ buckets, ~67% A-win rate, deterministic), `in_memory_sqlite`, and `synthetic_half_rates` fixtures.
- 24 RED tests across 3 modules pinning Plan 02-03's contracts:
  - 6 `test_synthesize_states` cases (defuse termination, plant carry-through, no-plant rounds, heartbeat cadence, carry-forward `numerical_diff`, ascending time-order).
  - 14 `test_side_mapping` parametrized cases (round-13 half-flip across `attacking_first_team_num` × `team_a_team_num` combinations).
  - 4 `test_round_events_schema` cases (8-column CON-round-events-schema, composite PK, `idx_round_events_map` index, NOT NULL discipline).
- All RED tests SKIP cleanly via `pytest.importorskip("scripts.probe_round_events", reason="Awaiting Plan 02-03 …")` — no errors at collection time.
- Phase 0/1 + Plan 02-01 baseline (178 tests) still green; total runtime <5s for new tests; no flakiness.

## Task Commits

1. **Task 1: tests/probe/ offline fixtures + endpoint shape tests** — `6560e6b` (test)
2. **Task 2: tests/calibration/ synthetic factories + RED contract tests** — `abd01a5` (test)

## Files Created/Modified

- `tests/probe/__init__.py` — empty package marker (matches `tests/pricing/__init__.py` pattern).
- `tests/probe/conftest.py` — session-scoped `events_response`, `series_response`, `match_details` fixtures loading from `tests/probe/fixtures/*.json` via `Path(...).read_text(encoding="utf-8")`.
- `tests/probe/fixtures/events_response.json` — 3-event sample (2 VCT divisions, 1 VCL) with required fields (`id`, `name`, `divisions`, `seriesCount`, `startDate`, `vctRegions`).
- `tests/probe/fixtures/series_response.json` — 1 series, 2 matches (Lotus, Bind) with embedded `matches[]` array carrying `mapId`, `map.name`, `attackingFirstTeamNumber`, `winningTeamNumber`, scores, `team1PlayerIds`, `team2PlayerIds`, `lengthMillis`.
- `tests/probe/fixtures/match_details.json` — 3 rounds covering all three termination patterns + 30 `economies[]` entries (loadout values exercising semi-eco / semi-buy buckets).
- `tests/probe/test_endpoint_shapes.py` — 9 schema tests + `VALID_EVENT_TYPES` closure check.
- `tests/calibration/__init__.py` — empty package marker.
- `tests/calibration/conftest.py` — `synthetic_round_events` (50 rows, deterministic, uses `credits_to_bucket` not literals) + `in_memory_sqlite` + `synthetic_half_rates` fixtures.
- `tests/calibration/test_synthesize_states.py` — 6 RED tests against Plan 02-03's `synthesize_mid_round_states`.
- `tests/calibration/test_side_mapping.py` — 14 parametrized RED cases against Plan 02-03's `side_for_team_a`.
- `tests/calibration/test_round_events_schema.py` — 4 RED tests against Plan 02-03's `create_round_events_schema(conn)`.

## Decisions Made

- **Skip-gate over xfail.** `pytest.importorskip` was chosen over `pytest.xfail` because the prompt's `<important>` block explicitly mandates it ("RED tests use `pytest.importorskip` so the test file exists but skips collection until 02-03 ships the module"). `xfail` would require raising an actual exception each test invocation; `importorskip` short-circuits at module import.
- **Fixtures use `credits_to_bucket`.** Synthetic dataset factory in `tests/calibration/conftest.py` calls `src.pricing.economy.credits_to_bucket(...)` rather than hard-coding bucket strings. CRule 2 (single canonical implementation) is now enforced even at the test-data layer — calibrator tests cannot drift bucket labels independently of runtime.
- **Match-details fixture: 3 rounds, not more.** The fixture is hand-authored and committed source; size is a tax on every git operation. Three rounds is the minimum that exercises Pitfall 4's three patterns. Plan 02-03's manual probe checkpoint is where larger real-data samples are recorded.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Plan acceptance criterion contradicts the prompt's mandated skip-gate idiom**
- **Found during:** Task 2 verification.
- **Issue:** The plan's acceptance criteria for Task 2 included `uv run pytest tests/calibration/ --collect-only 2>&1 | grep -c 'test_'` returns `>= 11`. With module-level `pytest.importorskip`, pytest 9.x short-circuits collection (output: `collected 0 items / 3 skipped`), so only 3 lines match `test_` (the SKIPPED entry filenames). The plan's `<important>` block in the executor prompt explicitly endorses the `importorskip` pattern and the prompt's success-criterion #6 mandates "tests skip cleanly via importorskip (no errors at collection time)" — these two requirements are mutually exclusive under pytest's collection semantics.
- **Fix:** Honored the prompt's explicit guidance + the documented pytest idiom. Tests SKIP cleanly with reason "Awaiting Plan 02-03 — scripts/probe_round_events.py" exactly as the prompt specifies. Documented the divergence here so Plan 02-03's executor sees the contract precisely: 24 RED tests are present in the source files (6 + 14 parametrized + 4); they will activate automatically when `scripts/probe_round_events.py` lands and `pytest.importorskip` succeeds.
- **Verification:** `uv run pytest tests/calibration/ -x -q -rs` reports `3 skipped` with the documented reason; no errors. `uv run pytest tests/probe/ tests/calibration/` reports `9 passed, 3 skipped`. Phase 0/1 + Plan 02-01 baseline still green (178 passed).
- **Files modified:** None — semantic deviation only, no code change.
- **Committed in:** N/A — documented here per Rule 1 deviation reporting.

---

**Total deviations:** 1 auto-fixed (1 plan/prompt contradiction documented)
**Impact on plan:** No scope change. The RED test source content is exactly what the plan's `<behavior>` block prescribes; only the collection-count metric is unsatisfiable under the mandated idiom.

## Issues Encountered

- None — both tasks executed exactly as specified by the plan body, modulo the documented deviation above.
- The match-details fixture's economy values were tuned to map cleanly through `credits_to_bucket`: round 1 (800 credits/player → 4000 team total → "eco"), round 2 attackers (4500 → 22500 → "full"), round 2 defenders (1200 → 6000 → "semi-eco"). These values match the audit-engine economy distribution per CON-economy-buckets.

## User Setup Required

None — pure test scaffolding; no external services, env vars, or dashboard changes.

## Next Phase Readiness

**Plan 02-03 (probe ETL — Wave 1) gates:**
- The 24 RED tests in `tests/calibration/` will activate automatically when `scripts/probe_round_events.py` defines:
  - `synthesize_mid_round_states(round_events, round_team_a_players, round_team_b_players, round_loadouts, side_a_this_round, map_name) -> list[dict]`
  - `side_for_team_a(round_num, attacking_first_team_num, team_a_team_num) -> str`
  - `create_round_events_schema(conn: sqlite3.Connection) -> None`
- Plan 02-03's executor must run `uv run pytest tests/probe/ tests/calibration/ -x -q` after each commit and observe SKIPs flipping to PASSes (or actual fails to fix) as the module's symbols come online.

**Plan 02-04 (calibrator — Wave 2) gates:**
- `tests/calibration/conftest.py` provides `synthetic_round_events` and `synthetic_half_rates` for the bottom-up shrinkage walk tests Plan 02-04 will add. The synthetic dataset is small (50 rows) and deterministic — no Hypothesis flakiness, no real-data dependency.

**Pitfall 4 anchored.** Defuse semantics are now contractually enforced via `test_round_1_defuse_terminates_states_at_defuse_t_offset`. Any Plan 02-03 implementation that emits phantom post-defuse states will fail that test.

## Self-Check: PASSED

Files verified:
- `tests/probe/__init__.py` — FOUND
- `tests/probe/conftest.py` — FOUND
- `tests/probe/fixtures/events_response.json` — FOUND
- `tests/probe/fixtures/series_response.json` — FOUND
- `tests/probe/fixtures/match_details.json` — FOUND
- `tests/probe/test_endpoint_shapes.py` — FOUND
- `tests/calibration/__init__.py` — FOUND
- `tests/calibration/conftest.py` — FOUND
- `tests/calibration/test_synthesize_states.py` — FOUND
- `tests/calibration/test_side_mapping.py` — FOUND
- `tests/calibration/test_round_events_schema.py` — FOUND

Commits verified:
- `6560e6b` (Task 1) — FOUND in `git log`
- `abd01a5` (Task 2) — FOUND in `git log`

Test runs verified:
- `tests/probe/`: 9 passed in 0.36s
- `tests/calibration/`: 3 skipped (module-level `importorskip`) — documented per deviation 1
- `tests/probe/ tests/calibration/`: 9 passed, 3 skipped in 0.36s
- `tests/config/ tests/pricing/` (baseline): 178 passed in 56.72s — no regressions

---
*Phase: 02-round-event-data*
*Completed: 2026-05-01*
