---
phase: 03-live-ingestion-layer
plan: "01"
subsystem: state
tags: [matchstate, dataclass, jsonl, replay-log, hypothesis, mypy-strict, frozen-slots, ingestion-foundation]

requires:
  - phase: 03-live-ingestion-layer
    provides: 03-00 RED-stub test scaffolds (test_match_state.py / test_match_state_jsonl.py, conftest.make_match_state, src.state.* mypy strict override)
  - phase: 01-core-pricing-engine
    provides: D-17/D-18/D-19 static MatchState fields (team_a, team_b, map_pool, map_side_orients, map_winners, pistol_winner_a) + LiveTheoEngine state-only call surface
  - phase: 02-round-event-data
    provides: Phase 2 D-08 carry-forward semantics — preserved by `with_update(**only_changed_fields)` 19-field replace
provides:
  - "src/state/match_state.py — frozen+slots MatchState v2 dataclass (19 fields) + pure with_update mutator + commit/quarantine JSONL helpers per D-03 schema"
  - "src/state/__init__.py — re-exports MatchState, commit, quarantine"
  - "Atomic JSONL diff log for state mutations (data/event_log/{match_id}.jsonl) — replay-deterministic in seq_id order"
  - "Single-writer invariant documented at the helper module-docstring level"
  - "mypy --strict src/state/ AND src/pricing/ clean across the migrated import surface"
affects: [03-02-round-conclusion-v2-surface, 03-03-arbiter-and-latency, 03-04-scoreboard-poller, 03-05-ocr-pipeline, 03-06-text-listener, 03-07-etl-rerun-and-calibration, 03-08-e2e-gate]

tech-stack:
  added: []
  patterns:
    - "Pure mutator + decoupled JSONL helper — `with_update` does NO I/O; arbiter calls `commit()`/`quarantine()` to pair the mutation with the disk-side audit line. Unit-testable without tmp_path; dry-run-clean."
    - "10-key commit JSONL schema (seq_id, six timestamps, source, event_type, fields_changed); 7-key quarantine schema (seq_id=null, quarantined=true, quarantine_reason, t_observed, source, event_type, fields_proposed). Replay loop filters seq_id=None lines."
    - "t_state_committed recorded via time.monotonic_ns() BEFORE the synchronous JSONL append — disk write latency excluded from D-03 hot-path budget."

key-files:
  created:
    - "src/state/match_state.py — 19-field frozen+slots MatchState v2 dataclass + with_update + commit + quarantine (~190 LOC)"
  modified:
    - "src/state/__init__.py — re-exports MatchState, commit, quarantine"
    - "src/pricing/data.py — MatchState class deleted; HalfRates + TheoOutput preserved; Task 1 re-export shim deleted in Task 2"
    - "src/pricing/__init__.py — MatchState now imported from src.state.match_state; re-exported on the pricing surface for backward compat"
    - "src/pricing/live_theo.py — MatchState import swapped to src.state.match_state"
    - "src/pricing/round_types.py — TYPE_CHECKING-guarded MatchState import swapped to src.state.match_state"
    - "tests/ingestion/conftest.py — make_match_state fixture upgraded from dict-builder to MatchState(**base) constructor"
    - "tests/ingestion/test_match_state.py — 2 GREEN tests (hypothesis seq_id property + with_update field semantics)"
    - "tests/ingestion/test_match_state_jsonl.py — 3 GREEN tests (replay determinism over 1000 commits + commit-line schema + quarantine-line schema)"
    - "tests/pricing/test_live_theo.py — _synthetic_match_state + 19-field assertion updated for v2; MatchState import swapped"
    - "tests/pricing/test_live_theo_with_calibrated_round_conclusion.py — _synthetic_mid_round_state updated for v2; MatchState import swapped"
    - "tests/pricing/test_round_types.py — source-introspection assertion updated to expect MatchState import from src.state.match_state"
    - "tests/ingestion/test_e2e.py / test_text_listener.py / tests/pricing/test_live_theo_dispatch.py — first-line docstrings shortened (Rule 3 fix; pre-existing E501 from Wave 0)"

key-decisions:
  - "Re-export shim (not direct delete) for src/pricing/data.py.MatchState across Task 1 → Task 2: keeps the Task 1 commit grep-able and downstream consumers unbroken at the seam, then Task 2 deletes the shim atomically with the helper-additions."
  - "all-positional dataclass fields with NO defaults: forces callers to be explicit about every v2 field — matches Phase 1 idiom and avoids the kw_only/positional default-after-non-default trap."
  - "test_match_state_is_19_field_frozen_dataclass replaced test_match_state_is_17_field_frozen_dataclass (renamed + rebuilt the expected/forbidden sets) — keeps the named regression-lock anchor in the same file, just retuned to v2."
  - "Replay test compares all 18 dataclass fields EXCEPT last_updated_ts — D-02 marks last_updated_ts as informational-only; comparing it across the in-memory vs replay paths would fail because the replay's with_update calls happen later in real time."
  - "commit() mutates the supplied timestamps dict in place to record t_state_committed (RESEARCH §Code Examples pattern). Caller owns the dict, commit reaches in. Tested explicitly in test_commit_line_schema."

patterns-established:
  - "Frozen+slots dataclass at src/state/<name>.py is the canonical home for runtime single-source-of-truth shapes. Pricing/ingestion/quoting layers consume via re-export (`from src.state import <Name>`)."
  - "Mutators stay pure; I/O lives in module-level helpers. Tests for the dataclass itself never touch tmp_path; tests for the helpers do."
  - "Module docstrings cite the D-### CONTEXT decision IDs that produced each field/method so future executors can trace design decisions back through git blame to the planning artifacts."

requirements-completed: [REQ-match-state-engine]

# Metrics
duration: 6h 14m
completed: 2026-05-08
---

# Phase 3 Plan 01: MatchState v2 Migration Summary

**Atomic move of MatchState from src/pricing/data.py to src/state/match_state.py with the v2 19-field set + pure with_update mutator + single-writer commit/quarantine JSONL helpers proven replay-deterministic over 1000 random mutations.**

## Performance

- **Duration:** 6h 14m wall-clock (most of this was a long-running background pytest job; active editing/test/commit time ~30 minutes)
- **Started:** 2026-05-08T05:49:39Z
- **Completed:** 2026-05-08T12:03:19Z
- **Tasks:** 2
- **Files modified:** 14 (1 created — src/state/match_state.py; 13 modified)

## Accomplishments

- **REQ-match-state-engine GREEN.** All three SPEC §1 acceptance criteria pass:
  1. `mypy --strict src/state/` clean (Pitfall 7 — pyproject.toml override active from Wave 0).
  2. `tests/ingestion/test_match_state.py::test_seq_id_strictly_monotonic` GREEN over 50 hypothesis examples × up to 1000 with_update calls each.
  3. `tests/ingestion/test_match_state_jsonl.py::test_replay_determinism` GREEN: 1000 random commits → JSONL → in-order replay reconstructs state byte-for-byte across all 18 dataclass fields except informational `last_updated_ts`.
- **Atomic 5-site import rewrite.** Every `MatchState` import in src/ now resolves to `src.state.match_state` (or `src.state` re-export). `src/pricing/data.py` no longer defines or re-exports MatchState — `grep "class MatchState" src/pricing/data.py` returns 0 hits.
- **Phase 1 + Phase 2 regression GREEN.** 268 passed / 26 xfailed (Waves 2-4 stubs preserved). The `tests/pricing/` suite (Phase 1) and `tests/probe/` + `tests/calibration/` suites (Phase 2) all still pass under the new import path.
- **JSONL line schemas locked.** D-03's 10-key commit schema and 7-key quarantine schema are asserted by dedicated test functions; future executors who change the schema will fail those tests at CI.
- **Single-writer invariant documented.** Module docstring on `src/state/match_state.py` explains why the arbiter (Wave 3A) is the sole caller of `commit`/`quarantine` in production and how the POSIX `O_APPEND` atomicity bound (RESEARCH Pitfall 4) interacts with the Windows-side arbiter `tick()` loop.

## Task Commits

1. **Task 1: Create src/state/match_state.py v2 dataclass + with_update; rewrite imports.** — `143b9aa` (feat)
2. **Task 2: Add commit/quarantine JSONL helpers + replay determinism test; delete pricing/data.py shim.** — `0ece084` (feat)

**Plan metadata commit:** to follow (this SUMMARY.md + STATE.md + ROADMAP.md update).

## Files Created/Modified

### Created
- `src/state/match_state.py` — 19-field frozen+slots MatchState v2 dataclass with pure `with_update(**diff)` mutator + module-level `commit(prev, fields_changed, *, source, event_type, timestamps, jsonl_path)` and `quarantine(prev, fields_proposed, *, source, event_type, quarantine_reason, t_observed, jsonl_path)` helpers. Module docstring cites D-01, D-02, D-03, D-14 + RESEARCH Pattern 1 / Pitfall 4 / 7 / 8.

### Modified

**Source code (5 files):**
- `src/state/__init__.py` — re-exports `MatchState`, `commit`, `quarantine`.
- `src/pricing/data.py` — `MatchState` class deleted in Task 1; transition re-export shim deleted in Task 2. Module docstring updated to point at `src.state.match_state` as the canonical home.
- `src/pricing/__init__.py` — `MatchState` import swapped to `src.state.match_state`; package-level re-export preserved (`from src.pricing import MatchState` still works for downstream code).
- `src/pricing/live_theo.py` — `MatchState` import swapped to `src.state.match_state`; `HalfRates`/`TheoOutput` still imported from `src.pricing.data`.
- `src/pricing/round_types.py` — `TYPE_CHECKING`-guarded `MatchState` import swapped to `src.state.match_state`.

**Tests (8 files):**
- `tests/ingestion/conftest.py` — `make_match_state` fixture upgraded from `dict[str, Any]` return to direct `MatchState(**base)` instantiation.
- `tests/ingestion/test_match_state.py` — RED stubs replaced with the hypothesis property test (`test_seq_id_strictly_monotonic`, 50 examples × up to 1000 random with_update calls) plus `test_with_update_field_semantics` (only-changed-fields semantics; seq_id +1; last_updated_ts strictly advances after a 1ms sleep).
- `tests/ingestion/test_match_state_jsonl.py` — RED stubs replaced with `test_replay_determinism` (1000-commit replay determinism over all 18 non-`last_updated_ts` fields), `test_commit_line_schema` (10-key schema + correct types + commit() mutates timestamps in place), `test_quarantine_line_schema` (7-key schema + state-unchanged contract).
- `tests/pricing/test_live_theo.py` — `_synthetic_match_state` rebuilt for v2 (19 fields; v1 fields cut); `test_match_state_is_17_field_frozen_dataclass` renamed and rewritten to `test_match_state_is_19_field_frozen_dataclass`.
- `tests/pricing/test_live_theo_with_calibrated_round_conclusion.py` — `_synthetic_mid_round_state` rebuilt for v2.
- `tests/pricing/test_round_types.py` — `test_source_uses_type_checking_guard_for_circular_imports` updated to assert `from src.state.match_state import MatchState` is the type-only import inside the `TYPE_CHECKING` guard.
- `tests/ingestion/test_e2e.py` / `tests/ingestion/test_text_listener.py` / `tests/pricing/test_live_theo_dispatch.py` — first-line docstrings shortened to fix pre-existing E501 ruff lint (Rule 3 fix; these are RED-stub files that Waves 3A/3D/2A will overwrite anyway, but ruff was failing the plan-level verify gate).

## Decisions Made

- **One-line transition shim across Task 1 → Task 2 instead of single-task delete.** Plan picked Task-1-keeps / Task-2-deletes the `from src.state.match_state import MatchState` shim in `src/pricing/data.py`. Trade-off: Task 1 commits stays grep-search-and-replace clean for the import surface; Task 2 commits land the helpers + delete the shim atomically. No long-term residue: by the time Task 2 lands, every in-repo import is on the canonical path.
- **All-positional dataclass fields, no defaults.** Phase 1 idiom; matches what the Phase 1 stub did. Forces every caller to be explicit about every v2 field. The `kw_only=True` / mixed-default-after-non-default trap was avoided entirely.
- **`with_update` returns the same `last_updated_ts` if `time.time()` resolution collides.** RESEARCH Pitfall 8: Windows wall-clock is ~16ms-resolution; multiple back-to-back `with_update` calls inside the same millisecond return the same `last_updated_ts`. The monotonicity primitive is `seq_id` only — `last_updated_ts` is informational. `test_with_update_field_semantics` uses a 1ms sleep to dodge the collision when asserting strict ordering.
- **commit() records t_state_committed BEFORE the JSONL write.** D-03 hot-path budget excludes disk write latency from the bomb-detect → state-commit p50 < 100ms gate. `commit()` mutates the caller-supplied `timestamps` dict in place so the arbiter (Wave 3A) can read `t_state_committed` immediately after `commit()` returns without re-deserializing the JSONL line.
- **Replay test excludes `last_updated_ts` from field-equality.** In-memory and replay paths run `with_update` at different real times — every `last_updated_ts` will differ. Comparing every other field (17 of 18 dynamic fields + the 7 static fields all preserved through replace) catches every actual divergence; comparing `last_updated_ts` would be a perpetual false-fail.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Pre-existing ruff E501 in 4 RED-stub test docstrings was blocking Task 1 verify gate.**
- **Found during:** Task 1 verify (`uv run ruff check src/ tests/`).
- **Issue:** `tests/ingestion/test_e2e.py:1`, `tests/ingestion/test_match_state_jsonl.py:1`, `tests/ingestion/test_text_listener.py:1`, `tests/pricing/test_live_theo_dispatch.py:1` all had >100-char first-line docstrings landed by Wave 0 plan 03-00. Plan 03-01 Task 1's `<verify>` block requires `ruff check` clean, so these pre-existing errors blocked the Task 1 commit gate.
- **Fix:** Shortened the first-line docstring on test_e2e.py, test_text_listener.py, test_live_theo_dispatch.py (e.g., dropped the trailing "acceptance:" word). test_match_state_jsonl.py was rewritten in Task 2 anyway, which trimmed its first line.
- **Files modified:** `tests/ingestion/test_e2e.py`, `tests/ingestion/test_text_listener.py`, `tests/pricing/test_live_theo_dispatch.py`.
- **Verification:** `ruff check src/ tests/` exits clean ("All checks passed!") at the end of Task 2.
- **Committed in:** `143b9aa` (Task 1 commit; test_match_state_jsonl.py first-line trim landed via the rewrite in `0ece084`).

**2. [Rule 3 - Blocking] Pre-existing ruff UP035 (`from typing import Callable`) in tests/ingestion/conftest.py was blocking the verify gate.**
- **Found during:** Task 1 verify.
- **Issue:** Wave 0 conftest.py used `from typing import Callable`. Ruff lint UP035 prefers `from collections.abc import Callable` on Python 3.11.
- **Fix:** Swapped to `from collections.abc import Callable`. Sorted the import block.
- **Files modified:** `tests/ingestion/conftest.py`.
- **Verification:** `ruff check src/ tests/` clean.
- **Committed in:** `143b9aa` (Task 1 commit).

**3. [Rule 3 - Blocking] Plan claimed `src/pricing/dp.py` and `src/pricing/economy.py` had `MatchState` imports to swap; they don't.**
- **Found during:** Task 1 (action step 6).
- **Issue:** Plan listed dp.py and economy.py as files to patch the `from src.pricing.data import MatchState` line. Grep confirmed both files only mention `MatchState` in docstrings — no real imports.
- **Fix:** Skipped patching dp.py / economy.py (they need no change). Documented in the plan-execution context that the planner's import-site list was based on plan-time grep; after the actual grep at execution time, only 5 src-side imports needed swapping (matched the must_haves.key_links count exactly: __init__.py, live_theo.py, round_types.py, data.py shim placement, and the package-level __init__.py re-export).
- **Files modified:** None (the patch was unnecessary).
- **Verification:** `grep -rn 'pricing\.data import.*MatchState' src/` returns 0 hits at end of Task 2; `mypy --strict src/pricing/` clean (would have flagged any missing import).
- **Committed in:** N/A (no patch needed).

**4. [Rule 1 - Bug] Initial implementation of `test_seq_id_strictly_monotonic` used `zip(strict=True)` which falsely required `seq_ids` and `seq_ids[1:]` to be equal length.**
- **Found during:** Task 1 first pytest run.
- **Issue:** `seq_ids[1:]` is by construction one shorter than `seq_ids`; `zip(seq_ids, seq_ids[1:], strict=True)` raises `ValueError: zip() argument 2 is shorter than argument 1` on every diff list.
- **Fix:** Changed to `zip(seq_ids[:-1], seq_ids[1:], strict=True)` — pair adjacent elements. Both slices are guaranteed equal length so the `strict=True` clause that the ruff B905 lint requires is satisfied without forcing the zip to error on natural offset.
- **Files modified:** `tests/ingestion/test_match_state.py`.
- **Verification:** `pytest tests/ingestion/test_match_state.py::test_seq_id_strictly_monotonic -x` GREEN over 50 hypothesis examples.
- **Committed in:** `143b9aa` (Task 1 commit).

---

**Total deviations:** 4 auto-fixed (3 blocking, 1 bug).
**Impact on plan:** All four were either pre-existing wave-0 oversights surfaced by Task 1's `ruff check` verify gate (1, 2) or one-shot bugs introduced in Task 1 RED that were caught by the next pytest run (4). Deviation 3 was a plan-time vs execution-time grep mismatch — the plan's must_haves.key_links was already correct (5 sites); the action-step prose just over-listed. No scope creep; no architectural change.

## Authentication Gates

None — no external services touched.

## Issues Encountered

None blocking. The transition shim path (`src/pricing/data.py` → re-export shim in Task 1, deleted in Task 2) bridged the import-rewrite seam cleanly. Phase 1 + Phase 2 regression suite stayed GREEN at every commit.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

Plan 03-02 (round_conclusion v2 surface) is unblocked:
- Wave 2A consumes `state.bomb_planted | attackers_alive | defenders_alive | time_left_s` directly — all four fields exist on the new MatchState v2 with the right types (bool / Optional[int] / Optional[int] / Optional[float]).
- `from src.state import MatchState` works; the live_theo dispatch refactor (D-05) reads from this surface.

Plan 03-03 (arbiter + latency) is unblocked:
- Wave 3A calls `commit()` and `quarantine()` directly. The single-writer invariant is documented at the helper module-docstring level so the arbiter implementation has a clear "you are the sole caller of this in production" anchor.
- Six-stage timestamp lineage is half-built: `commit()` records `t_state_committed`; `t_observed`/`t_ingested`/`t_arbited` are populated by the arbiter; `t_theo_computed`/`t_quote_sent` are populated by Phase 4 (and are nullable in the JSONL line schema accordingly).

All 9 src-side import sites in tests/ + src/ resolve correctly under the new import path. mypy strict scope expanded (Wave 0 added the override; this plan landed strict-clean code into it).

## Self-Check: PASSED

- src/state/match_state.py exists on disk (verified via Read).
- src/state/__init__.py re-exports MatchState, commit, quarantine.
- src/pricing/data.py has no `class MatchState` (`grep -E "class MatchState" src/pricing/data.py` exit=1).
- Both task commits reachable on git: `143b9aa` (Task 1) and `0ece084` (Task 2).
- `pytest tests/` 268 passed / 26 xfailed.
- `mypy --strict src/state/ src/pricing/` clean.
- `ruff check src/ tests/` clean ("All checks passed!").

---
*Phase: 03-live-ingestion-layer*
*Completed: 2026-05-08*
