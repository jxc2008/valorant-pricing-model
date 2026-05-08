---
phase: 03-live-ingestion-layer
plan: "03"
subsystem: ingestion
tags: [arbiter, deque, jsonl, timestamp-lineage, latency-instrumentation, single-writer, dec-006-v2, dec-024-v2, ingestion-foundation]

requires:
  - phase: 03-live-ingestion-layer
    provides: 03-00 RED-stub test scaffolds (test_arbiter.py / test_latency.py / arbiter_with_stub_sources fixture); 03-01 src.state.commit + src.state.quarantine helpers + MatchState v2 with bomb_planted / attackers_alive / defenders_alive / time_left_s; 03-02 RoundConclusionLookup v2 surface (downstream consumer of arbiter-committed state)
provides:
  - "src/ingestion/arbiter.py — Arbiter class with 3 deques (score_changes, bomb_events, round_end_events) + tick() drain + 3 confirmation rules + JSONL bridge to src.state.commit/quarantine. SOLE writer of MatchState in production."
  - "src/ingestion/timestamps.py — wall_time() / mono_ns() helpers + TimestampRecord TypedDict (6-key schema per D-03)."
  - "src/ingestion/events.py — PendingEvent + ConfirmedEvent dataclasses (frozen+slots) + EventType / SourceName Literal aliases."
  - "src/ingestion/__init__.py — public re-exports: Arbiter, PendingEvent, ConfirmedEvent, EventType, SourceName, TimestampRecord, mono_ns, wall_time."
  - "4 new src/config/constants.py constants: ARBITER_TICK_HZ=20, ARBITER_SCORE_WINDOW_S=2.0, EVENT_LOG_DIR='data/event_log', METRICS_LOG_DIR='data/metrics'."
  - "data/metrics/{match_id}.metrics.jsonl format: 6-stage timestamps + source provenance + fields_changed_keys (sibling of event_log diff line; Phase 4 fills t_theo_computed / t_quote_sent on parallel update keyed by seq_id)."
  - "Single-writer invariant documented at module + method docstrings: Arbiter is the SOLE caller of src.state.commit / src.state.quarantine in production."
affects: [03-04-scoreboard-poller, 03-05-ocr-pipeline, 03-06-text-listener, 03-07-etl-rerun-and-calibration, 03-08-e2e-gate]

tech-stack:
  added: []
  patterns:
    - "3-deque arbiter (DEC-006 v2): score_changes / bomb_events / round_end_events. NO kill_events (DEC-024 v2 cuts kill-feed CV). NO numerical_flips (DEC-024 v2 cuts mid-round economy inference). Grep-verifiable absence in src/ingestion/arbiter.py."
    - "score_change rule: groups events by (sorted) fields_proposed signature; >=2 distinct sources within ARBITER_SCORE_WINDOW_S commits; stale events (older than _DEQUE_MAX_AGE_S=3s) quarantine; otherwise hold via re-queued survivors deque."
    - "bomb_event / round_end rule: 1 OCR source soft-commit immediately; arbiter does NOT roll back even if next score contradicts (Phase 4 mode-selector handles consistency check + maps to IDLE on mismatch)."
    - "Six-stage timestamp lineage: t_observed (wall_time, source) -> t_ingested (mono_ns, source) -> t_arbited (mono_ns, _commit_event right before commit()) -> t_state_committed (mono_ns, src.state.commit right before JSONL write) -> t_theo_computed (Phase 4) -> t_quote_sent (Phase 4)."
    - "Time discipline (RESEARCH Pitfall 3): t_observed uses time.time() ONLY for replay alignment; the other 5 use time.monotonic_ns(). NEVER mix for duration computation."
    - "Sibling JSONL files: data/event_log/{match_id}.jsonl = state replay (commit + quarantine lines); data/metrics/{match_id}.metrics.jsonl = latency analysis (commits only; same 6 timestamps + fields_changed_keys for provenance)."

key-files:
  created:
    - "src/ingestion/arbiter.py — Arbiter class (~270 LOC) with 3 deques + tick() + per-rule drain methods + commit/quarantine plumbing + metrics-line writer."
    - "src/ingestion/timestamps.py — wall_time, mono_ns, TimestampRecord (~55 LOC)."
    - "src/ingestion/events.py — PendingEvent, ConfirmedEvent, EventType, SourceName (~55 LOC)."
  modified:
    - "src/ingestion/__init__.py — public re-exports for Arbiter + 7 supporting symbols."
    - "src/config/constants.py — appended ingestion-arbiter section with 4 new Final-typed constants."
    - "tests/ingestion/conftest.py — arbiter_with_stub_sources upgraded from SimpleNamespace stub to real Arbiter wired to tmp event_log + metrics paths."
    - "tests/ingestion/test_arbiter.py — 4 GREEN tests (test_score_change_two_source_rule, test_bomb_event_one_source_soft_commit, test_round_end_one_source_soft_commit, test_quarantine_jsonl_format) replacing 4 Wave-0 xfail stubs."
    - "tests/ingestion/test_latency.py — 1 GREEN test (test_six_stage_populated) replacing 1 Wave-0 xfail stub."
    - "tests/config/test_constants.py — added ARBITER_TICK_HZ / ARBITER_SCORE_WINDOW_S / EVENT_LOG_DIR / METRICS_LOG_DIR to EXPECTED_NAMES + EXPECTED_TYPES (Rule-3 blocking auto-fix)."

key-decisions:
  - "score_change holds (re-queues) single-source events for the next tick rather than quarantining them on the first sight. Quarantine only fires when an event ages past _DEQUE_MAX_AGE_S=3s. Rationale: a fresh single-source event will likely cross-confirm in the next 50ms tick once the 2nd source emits; quarantining immediately would miss confirmations on the typical real-world cadence."
  - "Quarantine reason 'stale_in_deque_no_cross_confirm' encodes the reason at the point of quarantine call. Future Phase-5 calibration can grep the JSONL log for this string to count solo-source false-positives."
  - "Metrics file is a SIBLING of the JSONL diff log, not a follow-up line. Two file paths per match (data/event_log/{id}.jsonl AND data/metrics/{id}.metrics.jsonl). Rationale per D-03: event_log is for state replay determinism; metrics is for latency analysis. Coupling them via a single file would force Phase 5 latency analysis to filter out commit/quarantine line semantics; the split keeps each file's reader simple."
  - "Bomb/round_end soft-commit semantics ARE the production contract — arbiter does NOT rollback if subsequent score contradicts. Phase 5 calibration revisits if false-positive rate is too high; arbiter rollback would create a recursive single-writer ordering problem (rolled-back state mutates the seq_id chain)."
  - "score_change t_observed proximity check uses the EARLIEST event's t_observed (broadcast wall-clock) as the commit anchor. Rationale: latency analysis wants to attribute the event to the first source that saw it, not the slowest cross-confirmer."
  - "Source provenance in JSONL line: '|'-joined when 2 sources cross-confirm (e.g., 'ribgg|ocr_score'); single source name when soft-committed. Sorted alphabetically for replay determinism (set order is non-deterministic across Python runs)."

patterns-established:
  - "Arbiter as single-writer + sole-appender: every state mutation flows through Arbiter._commit_event -> src.state.commit -> JSONL append. Every quarantine flows through Arbiter._quarantine_event -> src.state.quarantine. Future ingestion sources (03-04 scoreboard, 03-05 OCR, 03-06 text listener) push PendingEvents into Arbiter deques and NEVER call src.state.commit / src.state.quarantine directly."
  - "Re-queue-via-survivors deque pattern: when a confirmation rule needs to hold events for a future tick, _drain_score_changes builds a fresh `survivors: deque` with the same maxlen and reassigns self.score_changes. Avoids mutating the deque during iteration; preserves the maxlen contract."
  - "Conftest fixture upgrade pattern (Wave 1 -> Wave 3A): Wave 0 ships SimpleNamespace stubs; Wave-N executors replace the stub body with the real implementation in-place. Same fixture name, same call shape (kwargs ignored or honored as appropriate), Wave-N-only feature: real wiring to tmp paths."

requirements-completed: [REQ-cross-source-arbiter, REQ-latency-instrumentation]

# Metrics
duration: 7 min
completed: 2026-05-08
---

# Phase 3 Plan 03: Arbiter and Latency Summary

**DEC-006 v2 cross-source arbiter (3 deques: score_changes / bomb_events / round_end_events; 0 deques cut: kill_events / numerical_flips per DEC-024 v2) with single-writer state mutation through src.state.commit/quarantine, six-stage timestamp lineage (t_observed -> t_ingested -> t_arbited -> t_state_committed; t_theo_computed / t_quote_sent reserved for Phase 4), and sibling JSONL files (data/event_log/{match_id}.jsonl for state replay + data/metrics/{match_id}.metrics.jsonl for latency analysis) — REQ-cross-source-arbiter and REQ-latency-instrumentation GREEN.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-05-08T19:13:46Z
- **Completed:** 2026-05-08T19:20:27Z
- **Tasks:** 3
- **Files modified:** 8 (3 created — arbiter.py, timestamps.py, events.py; 5 modified — __init__.py, constants.py, conftest.py, test_arbiter.py, test_latency.py + 1 regression-fix in test_constants.py)

## Accomplishments

- **REQ-cross-source-arbiter GREEN.** SPEC §5 acceptance #5 satisfied: 3 deques exist (score_changes / bomb_events / round_end_events); per-event-type rule fires (>=2 sources within window for score; 1 OCR source soft-commit for bomb/round_end); quarantined events appear in JSONL with seq_id=null + quarantined=true + quarantine_reason populated.
- **REQ-latency-instrumentation GREEN.** SPEC §6 acceptance #6 satisfied: every confirmed event JSONL line + metrics line carries all 6 timestamps; t_observed is a float wall-clock, t_ingested / t_arbited / t_state_committed are mono_ns ints with monotonic ordering; t_theo_computed / t_quote_sent reserved as None for Phase 4.
- **DEC-006 v2 grep guard PASSED.** `grep -E "kill_events|numerical_flips" src/ingestion/arbiter.py` returns 0 hits — DEC-024 v2 cuts (kill-feed CV, mid-round economy inference) are structurally absent from the arbiter file.
- **Single-writer invariant documented + structurally enforced.** Module docstring + class docstring + method docstrings explicitly mark the arbiter as SOLE writer of MatchState in production. Every src.state.commit / src.state.quarantine call site in the codebase outside the arbiter is in tests only.
- **mypy --strict src/state/ + src/pricing/ STILL clean.** Mypy on src/ingestion/ (gradual mode per pyproject.toml — new code is fully annotated) clean. Ruff src/ + tests/ + scripts/ clean.
- **Phase 1 + Phase 2 + 03-01 + 03-02 regression GREEN under the new module structure.** 259 passed / 27 xfailed (xfails: scoreboard / OCR / text-listener / E2E for waves 4B/4C/4D/wave-6; calibrator-flavored tests pointing at 03-07).

## Task Commits

1. **Task 1: Add src/ingestion timestamp + event types + 4 arbiter constants** — `f344130` (feat)
2. **Task 2: Arbiter (3 deques + tick + commit/quarantine bridge) per DEC-006 v2** — `a2b4226` (feat)
3. **Task 3: Six-stage timestamp lineage assertion (REQ-latency-instrumentation)** — `2356661` (test)

**Plan metadata commit:** to follow (this SUMMARY.md + STATE.md + ROADMAP.md update).

## Files Created/Modified

### Created
- `src/ingestion/arbiter.py` — Arbiter class (~270 LOC) implementing DEC-006 v2: 3 deques, tick() drain method, 3 per-event-type confirmation rules (`_drain_score_changes` / `_drain_bomb_events` / `_drain_round_end_events`), commit / quarantine plumbing (`_commit_event` / `_quarantine_event`), metrics-line writer (`_write_metrics_line`). Module + class + method docstrings cite DEC-006 v2 / DEC-024 v2 / D-02 / D-03 / RESEARCH Pitfall 3 / Pitfall 4.
- `src/ingestion/timestamps.py` — `wall_time() -> float` / `mono_ns() -> int` / `TimestampRecord` TypedDict (~55 LOC). Module docstring documents RESEARCH Pitfall 3 time discipline.
- `src/ingestion/events.py` — `PendingEvent` + `ConfirmedEvent` frozen+slots dataclasses + `EventType` + `SourceName` Literal aliases (~55 LOC). Module docstring cites DEC-006 v2 cuts.

### Modified
- `src/ingestion/__init__.py` — public re-exports: `Arbiter`, `PendingEvent`, `ConfirmedEvent`, `EventType`, `SourceName`, `TimestampRecord`, `mono_ns`, `wall_time`.
- `src/config/constants.py` — appended "Phase 3 — ingestion arbiter + event logs (DEC-006 v2 / D-03)" section: `ARBITER_TICK_HZ: Final[int] = 20`, `ARBITER_SCORE_WINDOW_S: Final[float] = 2.0`, `EVENT_LOG_DIR: Final[str] = "data/event_log"`, `METRICS_LOG_DIR: Final[str] = "data/metrics"`. All Final-typed per CRule 12.
- `tests/ingestion/conftest.py` — `arbiter_with_stub_sources` fixture upgraded from Wave-0 SimpleNamespace stub to real `Arbiter` instance wired to `tmp_path / "event_log"` + `tmp_path / "metrics"`. Imports updated (`Arbiter` added; SimpleNamespace + deque imports removed).
- `tests/ingestion/test_arbiter.py` — 4 GREEN tests replacing 4 Wave-0 xfail stubs. Each test uses a per-test `Arbiter` (not the conftest fixture) to permit per-test match-id parameterization for JSONL line shape assertions.
- `tests/ingestion/test_latency.py` — 1 GREEN test (`test_six_stage_populated`) replacing 1 Wave-0 xfail stub. Uses the conftest `arbiter_with_stub_sources` fixture; asserts both metrics and JSONL files carry all 6 timestamp keys + correct types + monotonic ordering of the Phase-3-owned stages + None reservations for Phase 4 stages + same `t_state_committed` across both files (cross-file consistency anchor).
- `tests/config/test_constants.py` — added 4 new constants to `EXPECTED_NAMES` + `EXPECTED_TYPES`. Pre-existing `test_no_unexpected_uppercase_names_leak_in` was failing because Task 1 added the constants but didn't update this allow-list (Rule-3 blocking auto-fix).

## Decisions Made

- **score_change holds, doesn't quarantine, on first sight of single-source events.** A fresh single-source PendingEvent typically cross-confirms within the next 50ms tick once the 2nd source emits; quarantining on the first tick would miss the typical real-world confirmation cadence. Stale-after-3s quarantine is the only path to seq_id=null for score_change events. The 3s threshold (constant `_DEQUE_MAX_AGE_S` in arbiter.py — local-to-the-file because the arbiter is its sole consumer) trades off "miss the late confirmer" against "let the deque grow unbounded if a source dies".
- **Bomb / round_end soft-commit is the production contract.** Arbiter does NOT roll back if a subsequent score commit contradicts the soft-committed state. Rationale: rolling back would mutate the seq_id chain (subsequent commits would have seq_ids that leapfrog or reuse), breaking replay determinism (Phase 3 D-03 / 03-01 test_replay_determinism). The mode-selector in Phase 4 reads the resulting state mismatch and maps quoting to IDLE per DEC-001 v2 — quoting suppression handles the false-positive case without state corruption.
- **score_change commit anchor is the EARLIEST t_observed across the cross-confirming sources.** Latency analysis attributes the event to the first source that saw it (typically the broadcast-stream OCR), not the slowest cross-confirmer (typically rib.gg's 5s poll). Picking the latest would penalize fast sources in p50 latency stats.
- **Sibling JSONL files (event_log + metrics), not a single combined file.** event_log = state replay (commit + quarantine lines); metrics = latency analysis (commits only with fields_changed_keys for provenance, NO field values). Coupling them would force Phase 5 latency analysis to filter out quarantine-line semantics; the split keeps each reader simple.
- **'|'-joined source provenance in JSONL with sorted alphabetical order.** Set iteration order is non-deterministic across Python runs (set hashing is randomized by default in CPython 3.11). Replay determinism requires the source string to be identical across runs of the same input — `tuple(sorted(distinct_sources))` guarantees this.
- **Local `_DEQUE_MAX_AGE_S = 3.0` constant in arbiter.py rather than a public src.config.constants entry.** The arbiter is the sole consumer; promoting it to constants.py would add a public API surface that no other module reads. CRule 12 says "no magic numbers in business logic" — this 3s threshold is internal arbiter implementation detail (the only public threshold for confirmation is `ARBITER_SCORE_WINDOW_S`, which IS in constants.py). Reasonable trade-off; if Phase 5 calibration tunes the value, promote at that point.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Pre-existing `tests/config/test_constants.py::test_no_unexpected_uppercase_names_leak_in` failed after Task 1 added 4 new constants.**
- **Found during:** Task 3 verify (full regression suite run).
- **Issue:** Task 1's plan body added `ARBITER_TICK_HZ`, `ARBITER_SCORE_WINDOW_S`, `EVENT_LOG_DIR`, `METRICS_LOG_DIR` to `src/config/constants.py` but did not update `tests/config/test_constants.py::EXPECTED_NAMES` + `EXPECTED_TYPES`. The smoke test `test_no_unexpected_uppercase_names_leak_in` is designed to catch typos / accidental leaks by comparing `constants.__annotations__` against the EXPECTED_NAMES allow-list — a deliberate-but-undocumented allow-list update was required.
- **Fix:** Added the 4 new constants to `EXPECTED_NAMES` (with section header `# Phase 3 — ingestion arbiter + event logs (DEC-006 v2 / D-03)`) and to `EXPECTED_TYPES` (`int`, `float`, `str`, `str` respectively). Verified `pytest tests/config/test_constants.py` passes 56/56.
- **Files modified:** `tests/config/test_constants.py`.
- **Verification:** `pytest tests/config/ -x` passes; `pytest tests/ -x -k "not test_calibrate_round_conclusion"` returns 259 passed / 27 xfailed (no FAIL).
- **Committed in:** `2356661` (Task 3 commit, alongside test_latency.py rewrite).

**2. [Rule 3 - Blocking] Initial `test_latency.py` had `SIX_KEYS` as a function-local UPPER_CASE name — ruff N806 flagged it.**
- **Found during:** Task 3 verify (`ruff check`).
- **Issue:** ruff lint N806 ("Variable in function should be lowercase") flagged the local `SIX_KEYS` tuple inside `test_six_stage_populated`. Promoting to a module-level constant is the canonical fix.
- **Fix:** Promoted `SIX_KEYS` to a module-level constant defined right after the imports.
- **Files modified:** `tests/ingestion/test_latency.py`.
- **Verification:** `ruff check src/ tests/ scripts/` clean.
- **Committed in:** `2356661` (Task 3 commit).

---

**Total deviations:** 2 auto-fixed (2 blocking).
**Impact on plan:** Both deviations were one-shot blocking issues surfaced by the verify gates. Deviation 1 was a plan-body oversight (constants added to source but not to the smoke-test allow-list); deviation 2 was a stylistic lint issue introduced by the test body's inline tuple. Neither indicates a design issue; both fixes preserve plan intent.

## Authentication Gates

None — no external services touched.

## Issues Encountered

None blocking. The arbiter design from the plan body landed straight to GREEN on the first pytest run; no rule-logic bugs surfaced.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

Plan 03-04 (scoreboard poller) is unblocked:
- `from src.ingestion import Arbiter, PendingEvent, mono_ns, wall_time` resolves; the scoreboard poller pushes `PendingEvent(source="ribgg", event_type="score_change", ...)` into `arb.score_changes`.
- `ARBITER_SCORE_WINDOW_S=2.0` is defined; the scoreboard poller's emission cadence and the arbiter's window are now coupled in code, not magic numbers.

Plan 03-05 (OCR pipeline) is unblocked:
- Push `PendingEvent(source="ocr_score", event_type="score_change", ...)` into `arb.score_changes` for cross-confirmation against ribgg.
- Push `PendingEvent(source="ocr_bomb", event_type="bomb_plant", ...)` into `arb.bomb_events` for soft-commit.
- Push `PendingEvent(source="ocr_round_end", event_type="round_end", ...)` into `arb.round_end_events` for soft-commit.
- Push `PendingEvent(source="ocr_post_plant_alive", event_type="post_plant_alive", ...)` into `arb.bomb_events` for the alive-widget refresh during the 45s post-plant window.

Plan 03-06 (text listener) is unblocked:
- Push `PendingEvent(source="twitter", event_type="score_change", ...)` into `arb.score_changes` as a soft cross-confirm. Twitter NEVER sole-sources a score commit because the arbiter requires >=2 distinct sources within ARBITER_SCORE_WINDOW_S.

Plan 03-08 (E2E gate) is unblocked:
- The synthetic E2E test in `tests/ingestion/test_e2e.py` drives fake rib.gg + fake OCR + fake Twitter through `Arbiter` -> `MatchState` -> `live_theo`; the arbiter's commit pipeline is the central spine of that test.
- Latency assertions can read `arb.metrics_path` for p50 latencies (event -> state-commit < 500ms; bomb_plant -> < 100ms).
- Six-stage lineage is structurally proven by `test_six_stage_populated`; the E2E test extends to multi-event sequences but doesn't need to re-prove the per-line schema.

## Self-Check: PASSED

- src/ingestion/arbiter.py exists on disk (verified via Bash `ls`).
- src/ingestion/timestamps.py exists on disk.
- src/ingestion/events.py exists on disk.
- src/ingestion/__init__.py re-exports `Arbiter` (verified via `python -c "from src.ingestion import Arbiter; print(Arbiter)"` -> `<class 'src.ingestion.arbiter.Arbiter'>`).
- src/config/constants.py declares ARBITER_TICK_HZ=20, ARBITER_SCORE_WINDOW_S=2.0, EVENT_LOG_DIR, METRICS_LOG_DIR (verified via importable smoke command).
- All 3 task commits reachable on git: `f344130` (Task 1), `a2b4226` (Task 2), `2356661` (Task 3).
- `pytest tests/ingestion/test_arbiter.py tests/ingestion/test_latency.py -v` -> 5 passed, 0 failed.
- `pytest tests/ -x -k "not test_calibrate_round_conclusion"` -> 259 passed / 27 xfailed (clean regression).
- `mypy --strict src/state/ src/pricing/` clean (9 source files).
- `mypy src/ingestion/` clean (4 source files; gradual mode is the project default per pyproject.toml).
- `ruff check src/ tests/ scripts/` clean ("All checks passed!").
- DEC-006 v2 grep guard: `grep -E "kill_events|numerical_flips" src/ingestion/arbiter.py` exit 1 = no matches (PASS).

---
*Phase: 03-live-ingestion-layer*
*Completed: 2026-05-08*
