---
phase: 02-round-event-data
plan: 03
subsystem: ingestion
tags: [ribgg, etl, sqlite, scrape, dry-run, checkpoint, path-a]

# Dependency graph
requires:
  - phase: 02-round-event-data
    provides: src/config/constants.RIBGG_* + MID_ROUND_HEARTBEAT_S (Plan 02-01); src/pricing/economy.credits_to_bucket (Plan 02-01); 24 RED tests in tests/calibration/ + 9 fixture tests in tests/probe/ (Plan 02-02)
provides:
  - scripts/probe_round_events.py — Path A rib.gg ETL CLI; canonical entry point for D-01..D-09; ships all helpers (create_round_events_schema, side_for_team_a, synthesize_mid_round_states, transform_match_to_rows, list_tier1_events, get_json, _ribgg_wait, _write_phase_status_fail, main)
  - tests/probe/test_list_tier1_events.py — W10 unit test pinning the VCT division filter via monkeypatched get_json
  - scripts/__init__.py — makes scripts a Python package so `python -m scripts.probe_round_events` and `pytest.importorskip("scripts.probe_round_events")` both resolve
  - All 24 previously-RED Plan 02-02 calibration tests turn GREEN (synthesize_states + side_mapping + round_events_schema)
affects: [02-04, 02-05]

# Tech tracking
tech-stack:
  added: []   # requests / tenacity / tqdm already added by Plan 02-01
  patterns:
    - "Custom tenacity wait function (`_ribgg_wait`) that introspects the most recent retry exception's Retry-After header before falling through to exponential backoff (W6)"
    - "Pre-emit-then-loop heartbeat synthesis: emit t=0 outside the main loop so the strict-less-than condition cannot skip it when the first event coincides with t=0 (W7)"
    - "Perspective-symmetric row doubling with match_id suffixing (`{id}::{ta}`) — keeps CON-round-events-schema PK intact while persisting both team-A perspectives (BLOCKER 4)"
    - "Operator checkpoint via 02-PHASE-STATUS.md sentinel: script writes the FAIL marker on its own when matches < 500, so the orchestrator halts deterministically without re-reading log text (BLOCKER 1)"
    - "Dry-run-by-default CLI per CRule 13 — `--dry-run` prints the recency cutoff and exits without touching the filesystem; `--live` is opt-in"

key-files:
  created:
    - scripts/__init__.py
    - scripts/probe_round_events.py
    - tests/probe/test_list_tier1_events.py
    - .planning/phases/02-round-event-data/02-PHASE-STATUS.md  # CHECKPOINT_PENDING placeholder
    - .planning/phases/02-round-event-data/deferred-items.md  # logs Plan 02-02 ruff residue
  modified: []

key-decisions:
  - "BLOCKER 4 perspective-symmetric row doubling implemented at transform_match_to_rows. Both team perspectives ship as separate rows under match_id suffixes `::1` and `::2`; calibrator must use `substr(match_id, 1, instr(match_id, '::')-1)` for the >=500 distinct-match floor."
  - "W6 _ribgg_wait composes retry-state introspection + exponential fallback in a single 18-line function rather than two stacked tenacity decorators. Avoids the `@retry(retry=retry_if_exception_type(...))` chaining that would split Retry-After-vs-no-Retry-After paths across two attempts."
  - "synthesize_mid_round_states accepts `map_name` to honor the function signature pinned by Plan 02-02 RED tests, but explicitly `del map_name`s it inside the body. D-07 is firm: map_name is row-level metadata, never in mid_round_states[]."
  - "list_tier1_events returns events ordered by rib.gg's startDate-descending sort. Recency cutoff terminates pagination as soon as an entry's startDate falls below the 18-month threshold (RIBGG_RECENCY_MONTHS), short-circuiting the full crawl past the cutoff."

patterns-established:
  - "Operator-driven checkpoints: the script writes its own status sentinel (02-PHASE-STATUS.md) on FAIL with non-zero exit; the orchestrator polls the sentinel rather than parsing log text. Generalizes to any phase with a long-running gate."
  - "TypedDict shapes (_RibEvent, _RibEconomy) document the upstream JSON contract without forcing runtime validation cost. mypy --strict catches mis-typed access at type-check time."
  - "Match-id suffixing for perspective doubling: a clean pattern for storing N perspectives per logical match without altering the locked schema PK."

requirements-completed: []
# Plan 02-03 ships the probe code; REQ-round-event-data-pipeline closes only after
# the operator's --live run produces ≥500 distinct (suffix-stripped) matches AND
# Plan 02-04 calibrator turns the SQLite into models/round_conclusion.json.

# Metrics
duration: ~35min
completed: 2026-05-01
---

# Phase 02 Plan 03: rib.gg Probe ETL — Path A Implementation Summary

**Self-contained Path A scrape CLI with operator-gated `--live` run; Task 1 ships the code GREEN, Task 2 awaits operator action**

## Performance

- **Duration:** ~35 min (Task 1 only; Task 2 blocked at checkpoint)
- **Started:** 2026-05-01T03:30:00Z
- **Completed (Task 1):** 2026-05-01T04:05:00Z
- **Tasks:** 1 of 2 (`type="auto" tdd="true"` Task 1 done; `type="checkpoint:human-verify"` Task 2 CHECKPOINT_PENDING)
- **Files modified:** 5 (all created)

## Plan-level Status

```
Plan 02-03 status: COMPLETE (Task 1 + Task 2 both shipped 2026-05-01)
```

| Task | Type | Status | Commit |
|---|---|---|---|
| 1 — Implement scripts/probe_round_events.py + tests/probe/test_list_tier1_events.py | auto (tdd) | COMPLETE | 56f807d |
| 2 — Operator runs `--live` probe; verifies PROBE-LOG.md and SQLite output | checkpoint:human-verify | COMPLETE (Pass: YES) | (operator-run; PROBE-LOG.md committed) |

### Task 2 result (2026-05-01T20:58Z)

Two in-flight bugs surfaced and were fixed mid-run before Pass: YES:

- **fafa6ae** — `hasSeries=true` URL param caused 30s server timeouts on every page (rib.gg backend issue, not a request shape we ever caught in fixtures). Also discovered `divisions[]=VCT` is silently ignored server-side. Both server-side filters dropped; client-side filtering at line 417 is sufficient.
- **fafa6ae** — `transform_match_to_rows` blew up on first match because rib.gg ships null rosters for cancelled / forfeited / not-yet-played matches in the series payload. Defensive `.get()` + early return; caller hardened with try/except so unknown schema drift can't kill multi-hour scrapes.

Final metrics:

| Metric | Value | Pass criterion |
|---|---|---|
| Matches inserted | 1000 | ≥500 floor / 1000 target ✅ |
| Rounds inserted | 42,586 | — |
| Series fetched | 552 | — |
| `ts_round_start` coverage | 100.0% | required ✅ |
| `ts_round_end` coverage | 100.0% | required ✅ |
| `ts_first_kill` coverage | 95.3% | — |
| `ts_bomb_plant` coverage | 59.6% | partial (only plant rounds) |
| **D-05 partial-pass triggered** | **false** | calibrator can populate `cells_full` ✅ |
| Matches skipped (null rosters) | 552 | handled by `fafa6ae` defensive fix |
| Wall-clock | ~28 min | — |

## Accomplishments — Task 1

### Probe script (scripts/probe_round_events.py)

- 800+ line single-file CLI implementing the rib.gg `/v1/{events,series,matches/{id}/details}` chain.
- Public symbols (consumed by tests/calibration/ via `pytest.importorskip`):
  - `get_json(url)` — `@retry(stop=stop_after_attempt(5), wait=_ribgg_wait)`-decorated `requests.get`.
  - `_ribgg_wait(retry_state)` — W6: honors `Retry-After` header (cap 60s), exponential fallback (cap 30s).
  - `create_round_events_schema(conn)` — installs the 8-column CON-round-events-schema verbatim plus the companion `matches` metadata table keyed by `(match_id, team_a_team_num)` for the BLOCKER 4 doubled rows.
  - `side_for_team_a(round_num, attacking_first_team_num, team_a_team_num)` — Pitfall 3 round-13 half-flip handler.
  - `synthesize_mid_round_states(...)` — D-06 hybrid event+heartbeat list emitter with W7 t=0 pre-emit, D-08 carry-forward, and Pitfall 4 defuse termination.
  - `transform_match_to_rows(match_meta, details, map_num)` — BLOCKER 4: yields two rows per round (one per team perspective) with negated `numerical_diff` and flipped `side` in the mirror row.
  - `list_tier1_events(recency_iso)` — VCT division filter with 18-month recency cutoff and pagination short-circuit.
  - `_write_phase_status_fail(status_path, reason)` — BLOCKER 1: writes 02-PHASE-STATUS.md FAIL marker.
  - `main(argv=None)` — argparse CLI with `--live`, `--dry-run`, `--target`, `--out-db`, `--probe-log`, `--phase-status`. Defaults to dry-run per CRule 13.

### CRule compliance

- **CRule 12 (no magic numbers):** `RIBGG_BASE_URL`, `RIBGG_RECENCY_MONTHS`, `RIBGG_TARGET_MATCH_COUNT`, `RIBGG_TIER_FILTER`, `RIBGG_RATE_LIMIT_RPS`, `MID_ROUND_HEARTBEAT_S` all imported from `src.config.constants`. The 500-match acceptance floor is the only inline literal (acceptance bar; lives in this script as the orchestrator-visible threshold).
- **CRule 2 (single canonical bucketing):** `from src.pricing.economy import credits_to_bucket` — no inline `>= 20000` / `>= 10000` / `>= 5000` literals (grep gate clean).
- **CRule 13 (dry-run by default):** `python -m scripts.probe_round_events` with no flags returns 0 and prints `DRY-RUN: target=1000 recency_cutoff=...`. No SQLite, no HTTP, no PROBE-LOG.

### Revision-feedback fixes

| Tag | Description | Where in code |
|---|---|---|
| BLOCKER 1 | FAIL writes 02-PHASE-STATUS.md and exits 2 | `main()` final branch + `_write_phase_status_fail` |
| BLOCKER 3 | PROBE-LOG includes Event Coverage section + `D-05 partial-pass triggered: {true|false}` | `_render_probe_log` Event Coverage block |
| BLOCKER 4 | Perspective-symmetric row doubling (2× rows; match_id suffixes `::1`/`::2`) | `transform_match_to_rows` two-perspective loop + `insert_match` suffix routing |
| W6 | `Retry-After` header honored | `_ribgg_wait` |
| W7 | t=0 heartbeat pre-emitted before loop | `synthesize_mid_round_states` (line ~250) |
| W10 | VCT-only filter test (monkeypatch `get_json`) | `tests/probe/test_list_tier1_events.py` |

### W10 test (tests/probe/test_list_tier1_events.py)

- Monkeypatches `scripts.probe_round_events.get_json` to return the events_response.json fixture (3 events: 5832 / 5833 VCT, 5900 VCL).
- Disables `_throttle` to keep the test instant.
- Asserts `5832, 5833 ∈ out_ids`, `5900 ∉ out_ids`, and every yielded event has `"VCT" in divisions`.

### Verification (all GREEN)

```text
uv run mypy --strict src/pricing/         → Success: no issues found in 8 source files
uv run ruff check scripts/probe_round_events.py tests/probe/test_list_tier1_events.py → All checks passed!
uv run pytest -x -q                        → 223 passed in 82.25s
uv run pytest tests/calibration/test_synthesize_states.py tests/calibration/test_side_mapping.py tests/calibration/test_round_events_schema.py
                                           → 24 passed (Plan 02-02 RED → GREEN)
uv run pytest tests/probe/                 → 10 passed
uv run python -m scripts.probe_round_events --dry-run → exit 0; no files written
```

## Task 2 — CHECKPOINT_PENDING

Operator action required. The plan's frontmatter declares `autonomous: false`; per VALIDATION.md "Manual-Only Verifications" the `--live` run requires:

- Network egress to `https://be-prod.rib.gg/v1/`.
- ~30–60 minutes wall-clock at 2 rps.
- Local `data/` directory write capacity (~50–200 MB SQLite).

The script handles 503 retry (W6 Retry-After + Pitfall 2 exponential fallback) but cannot guarantee Heroku availability or that rib.gg's schema hasn't drifted. The operator visually confirms `Pass: YES` in PROBE-LOG.md before resuming execute-phase.

### Operator runbook

```bash
# Smoke (no network):
uv run python -m scripts.probe_round_events --dry-run
# Live (multi-minute):
uv run python -m scripts.probe_round_events --live
```

### Resume signal

- `"approved"` → continue to Wave 3 (Plan 02-04 + 02-05).
- `"FAIL"` → halt the phase; 02-PHASE-STATUS.md is on disk; run `/gsd-insert-phase 02.5-path-b-ocr` to plan Path B.

## Deviations from Plan

None — plan executed exactly as written for Task 1.

### Auto-fixed issues

- Ruff autofix applied (UP035, UP017, I001) in `scripts/probe_round_events.py` and `tests/probe/test_list_tier1_events.py`:
  - `from collections.abc import Iterable` instead of `from typing import Iterable`.
  - `from datetime import UTC` and `datetime.now(tz=UTC)` instead of `timezone.utc`.
  - Import block sorted (`isort`).
- Above were applied via `uv run ruff check --fix`; the plan body's verbatim code samples used the older `timezone.utc` form. The fixed form is semantically equivalent and is what ruff (project-config) enforces.

## Deferred Issues

Logged to `.planning/phases/02-round-event-data/deferred-items.md`:

- `tests/calibration/conftest.py:18` — pre-existing `UP035` (Iterator import) shipped by Plan 02-02.
- `tests/probe/test_endpoint_shapes.py:13` — pre-existing `I001` (un-sorted import block) shipped by Plan 02-02.

These were detected by `uv run ruff check .` (full-tree mode) but are NOT caused by Plan 02-03's changes. Plan 02-04 author should run `uv run ruff check --fix tests/` as a one-line maintenance fix at the start of execution.

## Self-Check: PASSED

- `scripts/__init__.py` — FOUND
- `scripts/probe_round_events.py` — FOUND
- `tests/probe/test_list_tier1_events.py` — FOUND
- `.planning/phases/02-round-event-data/02-PHASE-STATUS.md` — FOUND (CHECKPOINT_PENDING)
- `.planning/phases/02-round-event-data/deferred-items.md` — FOUND
- Commit `56f807d` — FOUND in git log
- All 24 Plan 02-02 RED tests turn GREEN — verified
- W10 test passes — verified
- mypy --strict src/pricing/ clean — verified
- ruff check on new files clean — verified
- python -m scripts.probe_round_events --dry-run exits 0 with no filesystem changes — verified
