---
phase: 04-quoting-layer
plan: "00"
subsystem: testing
tags: [pytest, mypy, uv, kalshi, cryptography, websockets, tdd, red-stub]

# Dependency graph
requires:
  - phase: 03-live-ingestion-layer
    provides: MatchState v2 dataclass + tests/ingestion/conftest.make_match_state fixture (re-exported) + Arbiter + live_theo post-plant dispatch
provides:
  - 13 RED-stub test files (tests/quoting/ + tests/sizing/) collecting under pytest with 0 errors / 58 xfailed
  - shared fixtures in tests/quoting/conftest.py — make_market_quote, fake_private_key, fake_kalshi_session, tmp_fill_ledger_dir; re-exports make_match_state
  - 9 new constants in src/config/constants.py (TAKE_THRESHOLD, MM_MIN_EDGE, POST_PLANT_TAKE_THRESHOLD, MIN_HALF_SPREAD, SERIES_AGGREGATE_CAP_FRAC, RELATIVE_BRIER_EDGE_MIN, MIN_FILLS_PER_MATCH, KALSHI_BASE_URL, KALSHI_WS_URL)
  - 5 new declared deps in pyproject.toml (cryptography>=42, websockets>=12, python-dotenv>=1, async-lru>=2 [Rule-3 unpin], oauthlib>=3.2 [Rule-3 unpin])
  - [[tool.mypy.overrides]] strict blocks for src.quoting.* + src.sizing.* (CRule 11 extension)
  - .gitignore exclusion + data/fills/.gitkeep marker for per-strategy hypothetical-fill ledgers
affects: [04-01-kalshi-order-manager, 04-02-portfolio-kelly, 04-03-kill-switches, 04-04-mode-selector, 04-05-mm-quoter, 04-06-directional-taker, 04-07-post-plant-quoter, 04-08-e2e-gate]

# Tech tracking
tech-stack:
  added: [cryptography 45.0.7, websockets 13.1, python-dotenv 1.2.2, async-lru 2.3.0 (Rule-3 unpin), oauthlib 3.3.1 (Rule-3 unpin)]
  patterns:
    - "RED-stub xfail body (NOT decorator) — Wave-N executors flip stubs by replacing the body; decorator removal would leave dead xfail-call lines (Phase 03 D-01 carry-forward)"
    - "Same-commit Rule-3 prophylactic: new constants in src/config/constants.py AND test_constants.py EXPECTED_NAMES/EXPECTED_TYPES allow-list ship in the SAME commit (Phase 03 D-08)"
    - "Glob-then-allow-list .gitignore pattern: `data/fills/*` + explicit `!data/fills/.gitkeep` (Git PATTERN FORMAT 'two consequences' caveat)"
    - "mypy strict module-override extension: pyproject.toml [[tool.mypy.overrides]] blocks ensure CI runs strict, not just CLI invocations (RESEARCH Pitfall 7 carry-forward)"

key-files:
  created:
    - tests/quoting/__init__.py
    - tests/quoting/conftest.py
    - tests/quoting/test_kalshi_auth.py
    - tests/quoting/test_order_manager.py
    - tests/quoting/test_market_data.py
    - tests/quoting/test_mode_selector.py
    - tests/quoting/test_mm_quoter.py
    - tests/quoting/test_directional_taker.py
    - tests/quoting/test_post_plant_quoter.py
    - tests/quoting/test_kill_switches.py
    - tests/quoting/test_fill_ledger.py
    - tests/quoting/test_reconciliation.py
    - tests/quoting/test_e2e.py
    - tests/sizing/__init__.py
    - tests/sizing/test_kelly_portfolio.py
    - data/fills/.gitkeep
  modified:
    - pyproject.toml
    - uv.lock
    - src/config/constants.py
    - tests/config/test_constants.py
    - .gitignore

key-decisions:
  - "RED-stub xfail body pattern carried forward verbatim from Phase 03 D-01 — every stub function calls pytest.xfail(...) inside its body, no @pytest.mark.xfail decorator"
  - "Phase 04 constants land as a single atomic commit alongside their test_constants.py allow-list extension (Phase 03 D-08 same-commit Rule-3 prophylactic)"
  - "mypy strict block extension for src.quoting.* AND src.sizing.* added at the pyproject.toml level (RESEARCH Pitfall 7) — CI runs strict, not just CLI"
  - "Stand-in _StubMarketQuote dataclass in conftest.py lets Phase 04 tests be written BEFORE plan 04-01 ships the real src/quoting/market_data.py — Wave 2+ swaps the import in-place"
  - "async-lru and oauthlib unpinned in [project].dependencies (Rule-3 deviation): tweepy.asynchronous lazily imports both at module load; previous environments had them as undeclared transitives that uv sync removed"
  - "VEGA_DIRECTIONAL_THRESHOLD NOT deleted here — that deletion is atomic with the mode-selector implementation in plan 04-04 along with its tests/config allow-list update (avoids CI red between phases)"

patterns-established:
  - "Wave-1 scaffold: every per-REQ test file lays down BEFORE business code, so Wave-2+ executor verify commands are plain `pytest -k` invocations on pre-existing files (no test-runner race)"
  - "Stand-in dataclass in conftest.py as a forward-compat shim — sized to swap with the real import in one Edit per Wave-2+ executor"

requirements-completed: [REQ-kalshi-order-manager, REQ-mode-selector, REQ-mm-quoter, REQ-directional-taker, REQ-post-plant-quoter, REQ-kelly-sizer, REQ-kill-switches, REQ-order-lifecycle-reconciliation]
# Note: This Wave-1 scaffold lays the RED stubs for all 8 Phase 04 requirements;
# Waves 2-8 (plans 04-01..04-08) implement the corresponding source modules and
# flip stubs to GREEN. The frontmatter `requirements-completed` enumerates the
# REQ IDs SCAFFOLDED by this plan, matching the PLAN.md `requirements` field
# verbatim — actual GREEN promotion happens in downstream waves.

# Metrics
duration: 7min
completed: 2026-05-11
---

# Phase 04 Plan 00: Test Infrastructure Summary

**Wave-1 RED-stub scaffolding for the entire Phase 04 quoting layer: 13 per-REQ test files (58 xfailed stubs), populated conftest with 5 shared fixtures, 9 new Phase 04 constants atomically gated by tests/config allow-list, 5 new dev/runtime deps (cryptography, websockets, python-dotenv + Rule-3 unpinning of async-lru and oauthlib), and mypy strict overrides extended to src.quoting.* + src.sizing.*.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-05-11T19:28:58Z
- **Completed:** 2026-05-11T19:35:47Z
- **Tasks:** 2 (both atomic commits)
- **Files modified:** 5 (pyproject.toml, uv.lock, src/config/constants.py, tests/config/test_constants.py, .gitignore)
- **Files created:** 16 (13 test files + 2 __init__.py + 1 conftest + data/fills/.gitkeep)

## Accomplishments

- Every Phase 04 requirement now has a per-REQ test file laid as RED stubs — Waves 2-8 land GREEN tests by replacing function bodies, no new file plumbing required
- All 9 new Phase 04 constants land in the same commit as their test_constants.py allow-list (Phase 03 D-08 same-commit Rule-3 prophylactic — skips the post-hoc fix loop)
- mypy strict coverage extended from src/state/ + src/pricing/ to ALSO include src/quoting/ + src/sizing/ via pyproject.toml `[[tool.mypy.overrides]]` blocks (CRule 11 carry-forward; RESEARCH Pitfall 7 — must declare overrides at TOML level so CI runs strict)
- Auto-fixed silent Phase 03 regression: tweepy.asynchronous lazily imports async-lru + oauthlib at module load; `uv sync` had been silently relying on those as undeclared transitives. Explicit pinning in `[project].dependencies` makes the install reproducible
- Per-strategy hypothetical-fill ledger directory (data/fills/) carved out with glob-then-allow-list .gitignore pattern (Phase 03 directory-pattern caveat carry-forward)

## Task Commits

1. **Task 1: dev deps + 9 constants + mypy overrides + .gitignore + test_constants allow-list** — `019a596` (chore)
2. **Task 2: 13 RED-stub test files + conftest + 2 __init__.py + async-lru/oauthlib Rule-3 unpin** — `070380f` (test)

**Plan metadata:** _(this SUMMARY commit, pending)_ (docs: complete plan)

## Files Created/Modified

### Created (16 files)

- `tests/quoting/__init__.py` — empty package marker
- `tests/quoting/conftest.py` — 5 shared fixtures: re-exported `make_match_state`, plus new `make_market_quote` (stand-in `_StubMarketQuote` dataclass), `fake_private_key` (cryptography 2048-bit RSA), `fake_kalshi_session` (aioresponses wrapper), `tmp_fill_ledger_dir`
- `tests/quoting/test_kalshi_auth.py` — 3 RED stubs for REQ-kalshi-order-manager RSA-PSS sign_request (Pitfalls 1+2 covered)
- `tests/quoting/test_order_manager.py` — 4 RED stubs: place_quote dry-run, cancel_all, error_streak, client_order_id UUID
- `tests/quoting/test_market_data.py` — 3 RED stubs: dataclass shape, WS subscribe payload, WS disconnect invalidates (Pitfall 7)
- `tests/quoting/test_mode_selector.py` — 7 RED stubs for REQ-mode-selector (6 rules + tie-break per Pitfall 3)
- `tests/quoting/test_mm_quoter.py` — 4 RED stubs: spread formula, fee-floor property (Pitfall 4), MM ledger isolation, 2s staleness pull
- `tests/quoting/test_directional_taker.py` — 3 RED stubs: take threshold, kelly_size consumption, separate ledger
- `tests/quoting/test_post_plant_quoter.py` — 4 RED stubs: defensive pull, repricing path, take-or-quote branch, 100ms p50 (Pitfall 6)
- `tests/quoting/test_kill_switches.py` — 10 RED stubs for all 4 always-on switches with boundary cases + aggregator
- `tests/quoting/test_fill_ledger.py` — 6 RED stubs: per-strategy separation, 3× DEC-020 touched-fill cases, 10-key JSONL schema, directional isolation
- `tests/quoting/test_reconciliation.py` — 4 RED stubs: orphans, ghosts, dry-run no-op, Pitfall 1 re-asserted at reconcile site
- `tests/quoting/test_e2e.py` — 3 RED stubs owned by plan 04-08 (full pipe, kill-switch cancel-all, separate ledgers)
- `tests/sizing/__init__.py` — empty package marker
- `tests/sizing/test_kelly_portfolio.py` — 7 RED stubs for REQ-kelly-sizer DEC-023 v2 portfolio Kelly
- `data/fills/.gitkeep` — directory marker for the otherwise-gitignored hypothetical-fill ledger dir

### Modified (5 files)

- `pyproject.toml` — +5 deps (cryptography>=42,<46, websockets>=12,<14, python-dotenv>=1, async-lru>=2.0 [Rule-3], oauthlib>=3.2 [Rule-3]); +2 mypy overrides (src.quoting.*, src.sizing.*)
- `uv.lock` — regenerated with new resolution graph
- `src/config/constants.py` — +9 Phase 04 constants in a new "Phase 4 — quoting layer" section block with `Final[...]` annotations and `TODO(phase-5-calibrate)` markers
- `tests/config/test_constants.py` — `EXPECTED_NAMES` + `EXPECTED_TYPES` allow-lists extended with the 9 new Phase 04 names + types in the same commit (D-08 prophylactic)
- `.gitignore` — `data/fills/*` + `!data/fills/.gitkeep` pair (Phase 03 directory-pattern caveat carry-forward)

## Decisions Made

- **RED-stub xfail body pattern carried forward verbatim from Phase 03 D-01.** Every stub function calls `pytest.xfail("Plan 04-NN — ...")` inside its body — NOT `@pytest.mark.xfail` decorator. Wave-N executors flip stubs by replacing the function body in one edit; decorator removal would leave dead xfail-call lines.
- **Phase 04 constants land as a SINGLE atomic commit alongside their test_constants.py allow-list extension** (Phase 03 D-08 same-commit Rule-3 prophylactic). Splitting across commits would leave CI red between them (`test_no_unexpected_uppercase_names_leak_in` would fire on the new constants until the allow-list catches up).
- **mypy strict block extension for src.quoting.* AND src.sizing.* added at the `pyproject.toml` level**, not via CLI override. RESEARCH Pitfall 7 carry-forward: CI runs strict only if the override is declared at TOML level. CLI-only invocations would let CI ship loose strictness silently.
- **Stand-in `_StubMarketQuote` dataclass in conftest.py.** Lets Phase 04 tests be written BEFORE plan 04-01 ships the real `src/quoting/market_data.py`. Wave 2+ swaps the import in-place (`from src.quoting.market_data import MarketQuote`) when the real type lands.
- **`async-lru` and `oauthlib` unpinned explicitly in `[project].dependencies` (Rule-3 deviation).** tweepy.asynchronous lazily imports both at module load (`raise TweepyException(...)` else); previous environments had them as undeclared transitives that `uv sync` removed in this plan. Pinning them makes the install reproducible across machines.
- **`VEGA_DIRECTIONAL_THRESHOLD` NOT deleted here.** Its deletion is atomic with the mode-selector implementation in plan 04-04, along with its tests/config allow-list removal. Deleting now would leave the mode-selector codepath dangling at HEAD~N.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Unpinned async-lru and oauthlib as explicit deps after uv sync uninstalled async-lru**
- **Found during:** Task 2 first `pytest tests/quoting/ tests/sizing/` run
- **Issue:** `uv sync --all-extras --dev` removed `async-lru==2.3.0` (it had been installed only as an undeclared transitive of an earlier resolution). On import, `tweepy.asynchronous.__init__` raises `TweepyException("tweepy.asynchronous requires aiohttp, async_lru, and oauthlib to be installed")` because tweepy 4.16 LAZY-imports those and won't bootstrap without them. Phase 03's `tests/ingestion/conftest.py` imports `from src.ingestion import Arbiter` which imports `text_listener` which imports `tweepy.asynchronous.AsyncStreamingClient` — collapsing the entire test runner with `ImportError while loading conftest`.
- **Fix:** Added `async-lru>=2.0` and `oauthlib>=3.2` to `[project].dependencies` in `pyproject.toml`. Re-ran `python -m uv sync` and pytest. `oauthlib` had already been installed as a transitive of `requests-oauthlib`/`requests-cache`; pinning it makes the install graph deterministic.
- **Files modified:** pyproject.toml, uv.lock
- **Verification:** `python -m uv run pytest tests/` → 306 passed, 80 xfailed (22 Phase 03 baseline + 58 new Phase 04 stubs), 0 errors.
- **Committed in:** `070380f` (part of Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Necessary for the test runner to load `tests/ingestion/conftest.py` (re-exported by `tests/quoting/conftest.py`) at all. Without the fix, every Phase 03 ingestion test AND every new Phase 04 stub test errors out at collection. No scope creep — both deps were already used implicitly by Phase 03 production code.

## Issues Encountered

None — Task 1 verifications were clean on first run; Task 2 hit the blocking issue documented above and was resolved automatically.

## User Setup Required

None — no external service configuration required by this plan. (Plans 04-01 will introduce KALSHI_KEY_ID / KALSHI_KEY_PATH env vars when KalshiOrderManager ships.)

## Next Phase Readiness

- All test scaffolds in place for Wave 2 — plans 04-01 (kalshi auth + order manager), 04-02 (portfolio Kelly sizer), 04-03 (kill switches), and 04-04 (mode selector) can each drop GREEN tests into pre-existing files without racing the test runner.
- 5 shared fixtures (`make_match_state`, `make_market_quote`, `fake_private_key`, `fake_kalshi_session`, `tmp_fill_ledger_dir`) ready for downstream consumption.
- 9 new constants importable; mypy strict gates src/quoting/ and src/sizing/ from first source file landing.

**Verification command for Wave 2 sampling rate (per VALIDATION.md):**
```
python -m uv run pytest tests/quoting/ tests/sizing/ -x --no-cov
# Expected before any Wave 2 work: 58 xfailed, 0 errors
# After plan 04-NN ships, K of those flip to passed.
```

---
*Phase: 04-quoting-layer*
*Completed: 2026-05-11*

## Self-Check: PASSED

- All 16 created files exist on disk (verified via `[ -f ]` check on every path in `key-files.created`).
- Both task commits found in git log: `019a596` (chore) + `070380f` (test).
