---
phase: 03-live-ingestion-layer
plan: "00"
subsystem: testing
tags: [pytest, pytest-asyncio, aioresponses, mypy, uv, RED-stubs, ingestion]

requires:
  - phase: 02-round-event-data
    provides: round_conclusion.json v1 + round_events.sqlite v1; informs the v2 surface stubs that Wave 2A flips green
provides:
  - Phase 3 dev + runtime deps installed (aiohttp, opencv-python, Pillow, pytesseract, numpy, requests-cache, tweepy + pytest-asyncio, aioresponses)
  - mypy --strict override on src.state.* per CRule 11
  - 13 RED-stub test files (31 xfail tests) covering 8 REQs from VALIDATION.md
  - tests/ingestion/conftest.py with 4 shared fixtures designed to survive Wave 1 atomic move
  - .gitignore catches data/round_events_v2.sqlite + .claude-loop-output.tmp
affects: [03-01-match-state-v2-migration, 03-02-round-conclusion-v2-surface, 03-03-arbiter-and-latency, 03-04-scoreboard-poller, 03-05-ocr-pipeline, 03-06-text-listener, 03-07-etl-rerun-and-calibration, 03-08-e2e-gate]

tech-stack:
  added:
    - "aiohttp 3.13.5 (TaskGroup-compatible async HTTP)"
    - "opencv-python 4.13.0.92 (Otsu threshold + BGR/RGB)"
    - "Pillow 11.3.0 (pytesseract dep)"
    - "pytesseract 0.3.13 (subprocess wrapper, GIL-friendly)"
    - "numpy 2.4.4 (image array shuffling)"
    - "requests-cache 1.3.1 (filesystem backend, ETL re-run cache)"
    - "tweepy 4.16.0 (AsyncStreamingClient for Twitter v2)"
    - "pytest-asyncio 1.3.0 (dev — @pytest.mark.asyncio)"
    - "aioresponses 0.7.8 (dev — context-manager mock for aiohttp)"
  patterns:
    - "RED-stub layout: pytest.xfail() runtime call inside body so collection is GREEN but tests don't pollute CI red"
    - "Shared fixtures return dict[str, Any] payloads to survive Wave 1 atomic move of MatchState"

key-files:
  created:
    - "tests/ingestion/__init__.py"
    - "tests/ingestion/conftest.py"
    - "tests/ingestion/fixtures/.gitkeep"
    - "tests/ingestion/test_match_state.py"
    - "tests/ingestion/test_match_state_jsonl.py"
    - "tests/ingestion/test_scoreboard.py"
    - "tests/ingestion/test_ocr_score.py"
    - "tests/ingestion/test_ocr_bomb.py"
    - "tests/ingestion/test_ocr_round_end.py"
    - "tests/ingestion/test_ocr_alive_widget.py"
    - "tests/ingestion/test_text_listener.py"
    - "tests/ingestion/test_arbiter.py"
    - "tests/ingestion/test_latency.py"
    - "tests/ingestion/test_e2e.py"
    - "tests/pricing/test_round_conclusion_v2.py"
    - "tests/pricing/test_live_theo_dispatch.py"
  modified:
    - "pyproject.toml (deps + mypy override)"
    - "uv.lock (regenerated; 21 new resolved packages)"
    - ".gitignore (data/round_events_v2.sqlite + .claude-loop-output.tmp)"

key-decisions:
  - "Used pytest.xfail() runtime call (per plan body) over @pytest.mark.xfail(strict=False) decorator so the test BODY is the xfail signal — Wave N flips by replacing the body, not removing a marker"
  - "Conftest fixtures return dict[str, Any] (not MatchState dataclass) to survive Wave 1's atomic move of MatchState from src/pricing/data.py to src/state/match_state.py — Wave 1 patches the helper to return the dataclass once it exists"
  - "Added src.state.* mypy strict override block AFTER the existing src.pricing.* override (in the order plan specified); both overrides exist independently"

patterns-established:
  - "Per-REQ test file naming: tests/ingestion/test_<area>.py with one function per VALIDATION.md acceptance criterion"
  - "Module docstrings cite REQ-ID + the wave that flips it green so future executors find the right file fast"

requirements-completed: []
# Plan 03-00 ships RED-stub scaffolds for all 8 Phase 3 REQs (frontmatter
# `requirements:` field), but the REQs themselves are NOT complete here —
# they're completed when Waves 1-4 flip xfails to real assertions.
# REQ-match-state-engine completes in 03-01.
# REQ-round-conclusion-lookup completes in 03-02.
# REQ-cross-source-arbiter + REQ-latency-instrumentation complete in 03-03.
# REQ-scoreboard-polling completes in 03-04.
# REQ-ocr-pipeline completes in 03-05.
# REQ-text-listener completes in 03-06.
# REQ-end-to-end-latency completes in 03-08.

duration: 8 min
completed: 2026-05-07
---

# Phase 3 Plan 00: Test Infrastructure Summary

**Wave 0 RED scaffold — 13 test files (31 xfail tests) covering all 8 Phase 3 REQs, plus 9 new deps (7 runtime + 2 dev) and the src.state.* mypy strict override — landed atomically across 3 commits.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-05-07T15:46:58Z
- **Completed:** 2026-05-07T15:54:48Z
- **Tasks:** 3
- **Files modified:** 16 (3 modified + 13 new test files + conftest + __init__ + .gitkeep)

## Accomplishments

- All 9 Phase 3 deps installed and verified importable in one uv sync (aiohttp, opencv-python, Pillow, pytesseract, numpy, requests-cache, tweepy + pytest-asyncio, aioresponses).
- `[[tool.mypy.overrides]]` block for `src.state.*` strict added to pyproject.toml; `mypy src/state/` runs cleanly (empty module, 0 issues).
- Every Phase 3 REQ now has at least one RED-stub test file with the test function names from VALIDATION.md — Wave 1-4 executors can run `pytest -k <name>` per VALIDATION.md without first creating the file.
- conftest.py provides `make_match_state`, `tmp_event_log_path`, `synthetic_frame_factory`, `arbiter_with_stub_sources` — designed so Wave 1 only patches `make_match_state` to swap from dict-builder to MatchState-constructor.
- Phase 1 + Phase 2 regression suite GREEN: `pytest tests/ -x --no-cov` -> 263 passed, 31 xfailed (the 31 new stubs), 0 errors.

## Task Commits

1. **Task 1: Add Phase 3 deps + mypy strict override** — `95031ce` (chore)
2. **Task 2: tests/ingestion/ package + conftest with shared fixtures** — `888f5c6` (test)
3. **Task 3: 13 RED-stub test files** — `c8e82f6` (test)

**Plan metadata commit:** to follow (this SUMMARY.md + STATE.md + ROADMAP.md update).

## Files Created/Modified

### Created
- `tests/ingestion/__init__.py` — package marker
- `tests/ingestion/conftest.py` — 4 shared fixtures
- `tests/ingestion/fixtures/.gitkeep` — tracks dir for Wave 3C synthetic OCR frames
- `tests/ingestion/test_match_state.py` — 2 xfails (REQ-match-state-engine, W1)
- `tests/ingestion/test_match_state_jsonl.py` — 3 xfails (REQ-match-state-engine, W1)
- `tests/ingestion/test_scoreboard.py` — 2 xfails (REQ-scoreboard-polling, W3B)
- `tests/ingestion/test_ocr_score.py` — 2 xfails (REQ-ocr-pipeline, W3C)
- `tests/ingestion/test_ocr_bomb.py` — 2 xfails (REQ-ocr-pipeline, W3C)
- `tests/ingestion/test_ocr_round_end.py` — 2 xfails (REQ-ocr-pipeline, W3C)
- `tests/ingestion/test_ocr_alive_widget.py` — 2 xfails (REQ-ocr-pipeline, W3C)
- `tests/ingestion/test_text_listener.py` — 3 xfails (REQ-text-listener, W3D)
- `tests/ingestion/test_arbiter.py` — 4 xfails (REQ-cross-source-arbiter, W3A)
- `tests/ingestion/test_latency.py` — 1 xfail (REQ-latency-instrumentation, W3A)
- `tests/ingestion/test_e2e.py` — 3 xfails (REQ-end-to-end-latency, W4)
- `tests/pricing/test_round_conclusion_v2.py` — 3 xfails (REQ-round-conclusion-lookup, W2A)
- `tests/pricing/test_live_theo_dispatch.py` — 2 xfails (REQ-round-conclusion-lookup, W2A)

### Modified
- `pyproject.toml` — 7 runtime + 2 dev deps appended (alphabetical); new `[[tool.mypy.overrides]]` block for `src.state.*` strict
- `uv.lock` — regenerated (46 packages resolved, 21 new)
- `.gitignore` — `data/round_events_v2.sqlite` + `.claude-loop-output.tmp` added

## Decisions Made

- **xfail signal pattern:** `pytest.xfail("Wave N — pending")` runtime call inside body (per plan body); Wave-N executors replace the call with real assertions. Decorator-based `@pytest.mark.xfail(strict=False)` would have left the call dead after marker removal — the body-call form makes the swap atomic.
- **Conftest dict-vs-dataclass return:** `make_match_state` returns `dict[str, Any]`, not `MatchState(...)`, so the same conftest survives Wave 1's atomic move of MatchState from `src/pricing/data.py` to `src/state/match_state.py`. Wave 1's first task patches the helper.
- **uv install bootstrap:** `uv` was not pre-installed in this environment; bootstrapped via `pip install uv` (Python 3.12 system pip), then `python -m uv lock && python -m uv sync --all-extras --dev` provisioned `.venv/` + Python 3.11 download. Subsequent calls use `python -m uv` (uv shim binary not on PATH).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] uv binary not on PATH; bootstrapped via pip and `python -m uv` invocation**
- **Found during:** Task 1 (uv lock + sync)
- **Issue:** Plan says `uv lock && uv sync --all-extras --dev` but `uv` was not installed and not on PATH on this Windows environment.
- **Fix:** `pip install uv` (ran via PowerShell — installed uv 0.11.11). Subsequent uv invocations use `python -m uv` since the shim binary isn't on PATH.
- **Files modified:** None (deps installed via uv into .venv only)
- **Verification:** `python -m uv --version` returns `uv 0.11.11`; `python -m uv sync` succeeds; `python -m uv run python -c "import aiohttp,..."` prints `all imports ok`.
- **Committed in:** N/A (environment setup; not part of repo state)

**2. [Rule 1 - Bug] .gitignore had partial Phase 3 ignores from prior commit; only added missing entries**
- **Found during:** Task 2 (.gitignore append)
- **Issue:** Plan's append block had 4 of 5 entries already in .gitignore from commit `d5e20d6` (Phase 3 generated artifacts already gitignored). Re-appending would duplicate.
- **Fix:** Verified existing entries; only appended `.claude-loop-output.tmp` and `data/round_events_v2.sqlite` (the .sqlite suffix wasn't covered by the prefix-only `data/round_events_v2*` entry).
- **Files modified:** `.gitignore`
- **Verification:** `git status` shows `.claude-loop-output.tmp` no longer untracked-listed in subsequent operations.
- **Committed in:** `888f5c6` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug — defensive, not regression)
**Impact on plan:** Both auto-fixes preserve plan intent. uv bootstrap unblocks all subsequent Wave 1-4 work that depends on the dev environment. .gitignore dedup avoids double-ignore noise.

## Issues Encountered

None blocking. Note: pytest-asyncio 1.3.0 was installed (newer than the `>=0.23` floor); pytest 9.0.3 was installed (newer than `>=8.0` floor). All compatible with the plan's intent — newer minor versions only.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

Wave 1 (plan 03-01-match-state-v2-migration) is unblocked:
- Conftest `make_match_state` exists and produces v2 dict shape; Wave 1's first task patches it to return `MatchState` dataclass instances once `src/state/match_state.py` exists.
- `tests/ingestion/test_match_state.py` and `tests/ingestion/test_match_state_jsonl.py` exist with the right function names — Wave 1 swaps xfail bodies for hypothesis property tests + JSONL replay tests.
- `mypy --strict src/state/` runs cleanly today (empty module, override active); Wave 1 lands strict-clean code into the same package.

All Wave 2-4 plans are likewise unblocked: every `<automated>` verify in their plan files now resolves to a test function on disk (currently xfail), so executors swap stubs for assertions atomically.

## Self-Check: PASSED

All 16 created files exist on disk. All 3 task commits (`95031ce`, `888f5c6`, `c8e82f6`) reachable via `git log --oneline --all`.

---
*Phase: 03-live-ingestion-layer*
*Completed: 2026-05-07*
