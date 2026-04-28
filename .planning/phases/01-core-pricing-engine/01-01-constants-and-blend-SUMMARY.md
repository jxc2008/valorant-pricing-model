---
phase: 01-core-pricing-engine
plan: 01
subsystem: pricing

tags: [bradley-terry, constants, blend, mypy-strict, hypothesis, property-tests]

# Dependency graph
requires:
  - phase: 00-foundation
    provides: src/config/constants.py baseline (12 constants), src/pricing/ package, pytest+hypothesis+mypy+ruff toolchain via uv
provides:
  - Four new Phase 1 constants in src/config/constants.py (CONVICTION_CLIP_LOW, CONVICTION_CLIP_HIGH, MIN_ROUNDS_FULL_WEIGHT, BT_BLEND_EPSILON)
  - Bradley-Terry round_p blend in src/pricing/blend.py — single canonical round-win-probability formula (DEC-003)
  - tests/pricing/ test package marker — downstream Phase 1 plans (01-02 dp, 01-03 round-types, 01-04 round-conclusion, 01-05 live_theo) can land test files without scaffolding
affects: [01-02-dp, 01-03-round-types, 01-04-round-conclusion, 01-05-live-theo, 02-round-events, 04-quoting, 05-validation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Final[T] type-annotated constants with `Source:` docstring (extends Phase 0 pattern to four new constants)"
    - "BT input clip on inputs only — output preserves algebraic identity round_p(a,b) + round_p(b,a) == 1 (RESEARCH §3 Pitfall 4)"
    - "tests/pricing/__init__.py one-line docstring marker — mirrors tests/config/__init__.py for downstream test files"
    - "hypothesis property tests for math layer: BT symmetry + range invariant on (0.001, 0.999) and (0.0, 1.0) respectively"
    - "Source-grep regression test (test_blend_source_does_not_contain_arithmetic_mean_form) — locks DEC-003 against future refactor"

key-files:
  created:
    - src/pricing/blend.py
    - tests/pricing/__init__.py
    - tests/pricing/test_blend.py
  modified:
    - src/config/constants.py
    - tests/config/test_constants.py

key-decisions:
  - "Bradley-Terry input-only clip: clipping outputs would break round_p(a,b)+round_p(b,a)==1 symmetry that DP recurrences rely on (RESEARCH §3 Pitfall 4)"
  - "OT_TOTAL_HARDSTOP NOT added: dp.py (01-02) will use REGULATION_HALF*2 inline so the relationship stays explicit (RESEARCH §12 final rec)"
  - "Ruff SIM300 Yoda-condition fix: `pytest.approx(1.0) == X` form preferred over plan's `X == pytest.approx(1.0)` to satisfy lint"

patterns-established:
  - "Phase 1 constants block: CONVICTION_CLIP_LOW/HIGH live in the Pricing section between WIN_THRESHOLD and the Sizing divider, alongside MIN_ROUNDS_FULL_WEIGHT and BT_BLEND_EPSILON"
  - "tests/pricing/test_*.py imports source under test + reads source files directly for grep-based regression tests on forbidden patterns"

requirements-completed: [REQ-bradley-terry-blend]

# Metrics
duration: 14min
completed: 2026-04-28
---

# Phase 01 Plan 01: Constants and Bradley-Terry Blend Summary

**Bradley-Terry log-odds blend `(a*(1-b)) / (a*(1-b) + (1-a)*b)` shipped as `src.pricing.blend.round_p`, replacing the audit engine's arithmetic-mean bug; four Phase 1 constants (CONVICTION_CLIP_LOW=0.01, CONVICTION_CLIP_HIGH=0.99, MIN_ROUNDS_FULL_WEIGHT=15, BT_BLEND_EPSILON=1e-6) locked under `mypy --strict`.**

## Performance

- **Duration:** ~14 min
- **Started:** 2026-04-28T20:10:00Z (approx)
- **Completed:** 2026-04-28T20:24:00Z (approx)
- **Tasks:** 3 (all auto, all TDD)
- **Files modified/created:** 5 (2 modified, 3 created)

## Accomplishments

- Four `Final[...]`-typed Phase 1 constants land in `src/config/constants.py` with `Source:` docstrings: `CONVICTION_CLIP_LOW=0.01`, `CONVICTION_CLIP_HIGH=0.99`, `MIN_ROUNDS_FULL_WEIGHT=15`, `BT_BLEND_EPSILON=1e-6`. `OT_TOTAL_HARDSTOP` deliberately NOT added (RESEARCH §12 final recommendation — `dp.py` will use `REGULATION_HALF*2` inline).
- `src/pricing/blend.py` exports a single function `round_p(a_rate, b_rate_opposite_side) -> float` implementing the Bradley-Terry formula `(a * (1.0 - b)) / (a * (1.0 - b) + (1.0 - a) * b)` with input clip to `[BT_BLEND_EPSILON, 1 - BT_BLEND_EPSILON]`. Output never clipped — preserves BT symmetry `round_p(a,b) + round_p(b,a) == 1`.
- `tests/pricing/__init__.py` exists as a one-line-docstring package marker so downstream test files (`test_dp.py`, `test_round_types.py`, `test_round_conclusion.py`, `test_live_theo.py`) can import cleanly in plans 01-02 through 01-05.
- 8 new tests in `tests/pricing/test_blend.py`: 3 unit cases (coin flip, compounding edge `49/58`, moderate edge `0.36/0.52`), 2 saturation tests (`(1,0)→≈1`, `(0,1)→≈0`), 2 hypothesis property tests (BT symmetry on `[0.001, 0.999]`, range invariant on `[0, 1]`), 1 regression test (source does not contain arithmetic-mean form).
- 3 new tests in `tests/config/test_constants.py` (clip subinterval invariant, MIN_ROUNDS_FULL_WEIGHT positive int, BT_BLEND_EPSILON small positive float). EXPECTED_NAMES + EXPECTED_TYPES extended to lock the four new constants. `test_no_unexpected_uppercase_names_leak_in` continues to pass.
- All commands green: `uv run mypy --strict src/pricing/ src/config/`, `uv run pytest` (51/51 — 32 in test_constants, 8 in test_blend, 10 in test_main, 1 in test_smoke), `uv run ruff check src/pricing/ src/config/ tests/pricing/ tests/config/`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend src/config/constants.py with four Phase 1 constants** — `619121a` (feat)
2. **Task 2 + Task 3: tests/pricing/__init__.py + src/pricing/blend.py + tests/pricing/test_blend.py** — `42f3724` (feat) — combined per plan instructions ("Commit alongside Task 3 (single commit `feat(01-01): add Bradley-Terry blend module + property tests`)")

_Note: Tasks 2 and 3 were folded into one commit as the plan's `<action>` block in Task 2 explicitly directed. TDD RED phase verified test failure for both Task 1 (4 missing constants) and Task 3 (`ModuleNotFoundError: src.pricing.blend`) before GREEN implementations._

## Files Created/Modified

- `src/config/constants.py` — appended four `Final[...]`-typed constants with full `Source:` docstrings between `WIN_THRESHOLD` and the Sizing divider
- `tests/config/test_constants.py` — extended EXPECTED_NAMES (4 entries), EXPECTED_TYPES (4 entries), added 3 new value-invariant tests
- `src/pricing/blend.py` — new module: `round_p` function with module-level docstring documenting the algebraic-mean bug being fixed and the input-only-clip rationale
- `tests/pricing/__init__.py` — new one-line docstring package marker (mirrors `tests/config/__init__.py`)
- `tests/pricing/test_blend.py` — new test file: 8 tests across unit / saturation / hypothesis property / source-regression categories

## Decisions Made

- **OT_TOTAL_HARDSTOP intentionally omitted from constants.** Per RESEARCH §12 final recommendation: `dp.py` (01-02) will use `REGULATION_HALF * 2` inline so the relationship between regulation half length and OT hard-stop stays algebraically explicit at the call site. Adding a derived constant would obscure the dependency.
- **Ruff SIM300 Yoda-condition adjustment.** The plan specified `assert constants.CONVICTION_CLIP_LOW + constants.CONVICTION_CLIP_HIGH == pytest.approx(1.0)`, which ruff flags as a Yoda condition (it wants the literal-like operand on the left). Swapped to `assert pytest.approx(1.0) == constants.CONVICTION_CLIP_LOW + constants.CONVICTION_CLIP_HIGH`. Semantics identical; lint clean. Tracked here so 01-02..01-05 follow the same form.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Ruff SIM300 lint error on Yoda condition**
- **Found during:** Task 1 verification (`uv run ruff check`)
- **Issue:** Plan-specified `constants.CONVICTION_CLIP_LOW + constants.CONVICTION_CLIP_HIGH == pytest.approx(1.0)` triggered SIM300 (Yoda condition detected), blocking the verify command.
- **Fix:** Swapped operand order to `pytest.approx(1.0) == ...`. Semantically equivalent; satisfies ruff. No change to test logic.
- **Files modified:** `tests/config/test_constants.py` (one line)
- **Verification:** `uv run ruff check tests/config/test_constants.py` → "All checks passed!"; `uv run pytest tests/config/test_constants.py` → 32/32 pass
- **Committed in:** `619121a` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking lint error)
**Impact on plan:** Cosmetic; no scope change. Acceptance criteria all met.

## Issues Encountered

- `uv` not on the bash login PATH (it's installed under `%APPDATA%\Roaming\Python\Python311\Scripts`, on the Windows user PATH but not bash's). Worked around by prepending `export PATH="/c/Users/josep/AppData/Roaming/Python/Python311/Scripts:$PATH"` for verification commands. Not a code change; just an executor note. STATE.md notes this as well from Phase 0.

## User Setup Required

None — no external service configuration touched.

## Next Phase Readiness

- **01-02 (DP)** unblocked: `BT_BLEND_EPSILON` and `round_p` available; `REGULATION_HALF * 2` is the OT hard-stop expression to use.
- **01-03 (round-types)** unblocked: `GUN_WIN_RATE` (already in Phase 0) + new constants available; `round_p` is the canonical blend.
- **01-04 (round-conclusion)** unblocked: `MIN_ROUNDS_FULL_WEIGHT` (this plan) + `SHRINK_PRIOR` / `SIGNAL_SCALE` (Phase 0) available.
- **01-05 (live_theo)** unblocked: `CONVICTION_CLIP_LOW` / `CONVICTION_CLIP_HIGH` (this plan) available for output clip; `round_p` callable at the leaf of the DP/blend chain.
- `tests/pricing/` package exists; downstream test files import cleanly.
- No pending Phase 1 blockers introduced.

## Self-Check: PASSED

- Files created exist:
  - `src/pricing/blend.py` — FOUND
  - `tests/pricing/__init__.py` — FOUND
  - `tests/pricing/test_blend.py` — FOUND
- Files modified exist:
  - `src/config/constants.py` — FOUND (four new constants, grep-confirmed)
  - `tests/config/test_constants.py` — FOUND (3 new tests + extended EXPECTED_NAMES/TYPES)
- Commits exist on branch:
  - `619121a` (Task 1) — FOUND in `git log`
  - `42f3724` (Tasks 2+3) — FOUND in `git log`
- Verification commands all exit 0:
  - `uv run mypy --strict src/pricing/blend.py src/config/constants.py` → "Success: no issues found in 2 source files"
  - `uv run pytest tests/pricing/test_blend.py tests/config/test_constants.py -x` → 40/40 pass
  - `uv run ruff check src/pricing/ src/config/ tests/pricing/ tests/config/` → "All checks passed!"
  - Full suite `uv run pytest` → 51/51 (Phase 0 regression-clean)
  - Sanity prints: `round_p(0.5, 0.5) == 0.5`, `round_p(0.7, 0.3) == 0.8448275862068965` (= `49/58` to float precision; matches `math.isclose(rel_tol=1e-9)` against `49.0/58.0`)

---
*Phase: 01-core-pricing-engine*
*Completed: 2026-04-28*
