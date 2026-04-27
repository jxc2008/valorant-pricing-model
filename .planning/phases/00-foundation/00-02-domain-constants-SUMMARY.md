---
phase: 00-foundation
plan: 02
subsystem: config
tags: [python, constants, thresholds, mypy-strict, typing-final, pytest, parametrize]

# Dependency graph
requires:
  - phase: 00-foundation
    plan: 01
    provides: "uv-managed Python 3.11 project, src/config/ as real importable package, mypy --strict override on src.pricing.*, pytest test infra"
provides:
  - "src/config/constants.py: 12 thresholds typed with Final[...], organized into Pricing / Sizing / Kill switches / Mode flip sections"
  - "tests/config/__init__.py + tests/config/test_constants.py: 25 pytest cases (importability + extras + parametrized type check + 10 value invariants)"
  - "Single import surface for downstream phases — DEC-016 / CON-no-magic-numbers / CLAUDE.md rule 12"
  - "Locked KILL_SWITCH_* prefix on the four kill-switch constants per user-resolved CON-domain-constants-baseline (roadmap.md §0.4 wins over CLAUDE.md older KILL_* form)"
affects: [phase-1-pricing, phase-2-round-events, phase-3-ingestion, phase-4-quoting, phase-5-validation, phase-7-operational-maturity]

# Tech tracking
tech-stack:
  added: []  # No new packages — uses typing.Final from stdlib
  patterns:
    - "Final[T] annotations on every module-level constant (mypy --strict catches reassignment)"
    - "Section-banner comments delimit logical groups (Pricing / Sizing / Kill switches / Mode flip)"
    - "Per-constant docstrings cite source DEC-* / CLAUDE.md / PRD section for traceability"
    - "TBD inline comments on PER_MARKET_CAP_FRAC and VEGA_DIRECTIONAL_THRESHOLD per PRD §9 open TBDs"
    - "Parametrized pytest type checks (one logical test, 12 cases) for compactness"
    - "bool-subclass-of-int rejection in type tests (catches stray True/False literal bugs)"

key-files:
  created:
    - "src/config/constants.py"
    - "tests/config/__init__.py"
    - "tests/config/test_constants.py"
  modified: []
  removed: []

key-decisions:
  - "KILL_SWITCH_* prefix locked (NOT KILL_*) — implements user-resolved CON-domain-constants-baseline + DEC-005 corroborating note 2026-04-27; CLAUDE.md still shows older KILL_* form and needs a separate doc-fix PR"
  - "Per-constant docstrings (vs single module-level table) chosen because mypy/IDE hover-help surfaces them on every import site — better cross-phase traceability than a comment block"
  - "Parametrized type test (one @pytest.mark.parametrize over EXPECTED_TYPES dict) chosen over 12 individual test functions — compact and fails-loud on missing/wrong-type entries"
  - "test_no_unexpected_uppercase_names_leak_in added beyond plan spec to catch typo-introduced constants — minor scope expansion within Rule 2 (defensive correctness)"

patterns-established:
  - "src/config/constants.py is the SINGLE canonical home for thresholds — every downstream phase imports from here, never hardcodes"
  - "tests/config/test_constants.py mirrors source path (tests/config/ ↔ src/config/) per CONVENTIONS.md test-naming"
  - "Constants module uses `from __future__ import annotations` consistent with new src/ code (CONVENTIONS.md recommendation)"

requirements-completed: []  # Plan 00-02 has no REQ-IDs in `requirements:` frontmatter (it is foundational config infra). Satisfies CON-domain-constants-baseline + CON-no-magic-numbers + roadmap Phase 0 must-have #3.

# Metrics
duration: 7min
completed: 2026-04-27
---

# Phase 0 Plan 02: Domain Constants Summary

**Single-source-of-truth thresholds module: 12 constants in `src/config/constants.py` typed with `Final[...]`, sectioned (Pricing / Sizing / Kill switches / Mode flip), citing DEC-* sources per docstring; 25 pytest cases validate importability, types, and value invariants — toolchain (`mypy --strict src/pricing/`, `ruff check .`, `pytest`) stays green.**

## Performance

- **Duration:** ~7 min
- **Started:** 2026-04-27T20:56:00Z (worktree spawn time per STATE.md)
- **Completed:** 2026-04-27T21:01:51Z
- **Tasks:** 2
- **Files created:** 3
- **Files modified:** 0
- **Files removed:** 0

## Accomplishments

- `src/config/constants.py` declares all 12 thresholds from CON-domain-constants-baseline with EXACT names and values:
  - **Pricing (5):** `SHRINK_PRIOR=15.0`, `SIGNAL_SCALE=0.10`, `GUN_WIN_RATE=0.822`, `REGULATION_HALF=12`, `WIN_THRESHOLD=13`
  - **Sizing (2):** `KELLY_MULTIPLIER=0.5`, `PER_MARKET_CAP_FRAC=0.05` (TBD)
  - **Kill switches (4):** `KILL_SWITCH_STALENESS_S=5.0`, `KILL_SWITCH_DEVIATION_C=20`, `KILL_SWITCH_BRIER_BOUND=0.30`, `KILL_SWITCH_BRIER_WINDOW=50`
  - **Mode flip (1):** `VEGA_DIRECTIONAL_THRESHOLD=0.04` (TBD)
- Every constant is `typing.Final[float]` or `typing.Final[int]` so `mypy --strict` catches reassignment.
- `KILL_SWITCH_*` prefix used per user-resolved CON-domain-constants-baseline (NOT the older `KILL_*` form in CLAUDE.md "Domain constants").
- `tests/config/test_constants.py` exposes 25 pytest cases:
  - 1 importability check (all 12 names present and non-None)
  - 1 no-extras check (no surprise uppercase names beyond EXPECTED_NAMES)
  - 12 parametrized type checks (each constant matches its declared `Final[float|int]`; rejects `bool` subclass-of-int)
  - 10 value-invariant checks (probabilities in (0,1), Valorant rule `REGULATION_HALF + 1 == WIN_THRESHOLD`, `KELLY_MULTIPLIER == 0.5`, etc.)
- All toolchain commands stay green: `uv run pytest`, `uv run ruff check .`, `uv run mypy --strict src/pricing/`.

## Task Commits

Each task committed atomically with `--no-verify` (parallel-executor convention):

1. **Task 1: Write `src/config/constants.py`** — `8ec55f2` (feat)
2. **Task 2: Add `tests/config/__init__.py` + `tests/config/test_constants.py`** — `d78eca6` (test)

**Plan metadata commit (forthcoming):** SUMMARY.md committed by this agent's final-commit step. STATE.md / ROADMAP.md updates owned by orchestrator after the wave merges.

## Files Created/Modified

### Created

- **`src/config/constants.py`** (145 lines) — module docstring referencing DEC-016 + CON-no-magic-numbers + source-of-truth doc list; `from __future__ import annotations` + `from typing import Final`; four section banners; 12 `Final[T]`-annotated constants each with citation docstring.
- **`tests/config/__init__.py`** (1 line) — `tests.config` subpackage marker.
- **`tests/config/test_constants.py`** (160 lines) — `EXPECTED_NAMES` tuple + `EXPECTED_TYPES` dict + 13 test functions (1 importable + 1 no-extras + 1 parametrized type + 10 invariants); imports module without alias (`from src.config import constants`) and uses `constants.NAME` throughout to comply with ruff N812.

### Modified / Removed

None.

## Resolved Constants (final values)

| Constant | Value | Type | TBD? | Source |
|---|---|---|---|---|
| `SHRINK_PRIOR` | `15.0` | `Final[float]` | — | DEC-007 / CLAUDE.md / reference/theo_engine.py:37 |
| `SIGNAL_SCALE` | `0.10` | `Final[float]` | — | CLAUDE.md / reference/theo_engine.py:38 |
| `GUN_WIN_RATE` | `0.822` | `Final[float]` | — | DEC-011 / CLAUDE.md / PRD §6 Tier 1 |
| `REGULATION_HALF` | `12` | `Final[int]` | — | CLAUDE.md / Valorant rule |
| `WIN_THRESHOLD` | `13` | `Final[int]` | — | CLAUDE.md / Valorant rule |
| `KELLY_MULTIPLIER` | `0.5` | `Final[float]` | — | DEC-004 / CLAUDE.md rule 7 |
| `PER_MARKET_CAP_FRAC` | `0.05` | `Final[float]` | **yes** | DEC-004 / PRD §9.1 (depends on bankroll) |
| `KILL_SWITCH_STALENESS_S` | `5.0` | `Final[float]` | — | DEC-005 / CLAUDE.md rule 9 / PRD §5.4 |
| `KILL_SWITCH_DEVIATION_C` | `20` | `Final[int]` | — | DEC-005 / CLAUDE.md rule 9 / PRD §5.4 |
| `KILL_SWITCH_BRIER_BOUND` | `0.30` | `Final[float]` | — | DEC-005 / CLAUDE.md rule 9 / PRD §5.4 |
| `KILL_SWITCH_BRIER_WINDOW` | `50` | `Final[int]` | — | DEC-005 / CLAUDE.md rule 9 / PRD §5.4 |
| `VEGA_DIRECTIONAL_THRESHOLD` | `0.04` | `Final[float]` | **yes** | DEC-001 / CLAUDE.md / roadmap.md §4.2 (calibrate after 20+ matches) |

## Toolchain Verification (the four success-criteria commands)

```text
$ uv run pytest tests/config/test_constants.py -v
============================= test session starts =============================
platform win32 -- Python 3.11.6, pytest-9.0.3, pluggy-1.6.0
configfile: pyproject.toml
plugins: hypothesis-6.152.4, cov-7.1.0
collected 25 items

tests/config/test_constants.py::test_all_expected_constants_are_importable PASSED [  4%]
tests/config/test_constants.py::test_no_unexpected_uppercase_names_leak_in PASSED [  8%]
tests/config/test_constants.py::test_constant_has_expected_type[SHRINK_PRIOR-float] PASSED [ 12%]
tests/config/test_constants.py::test_constant_has_expected_type[SIGNAL_SCALE-float] PASSED [ 16%]
tests/config/test_constants.py::test_constant_has_expected_type[GUN_WIN_RATE-float] PASSED [ 20%]
tests/config/test_constants.py::test_constant_has_expected_type[REGULATION_HALF-int] PASSED [ 24%]
tests/config/test_constants.py::test_constant_has_expected_type[WIN_THRESHOLD-int] PASSED [ 28%]
tests/config/test_constants.py::test_constant_has_expected_type[KELLY_MULTIPLIER-float] PASSED [ 32%]
tests/config/test_constants.py::test_constant_has_expected_type[PER_MARKET_CAP_FRAC-float] PASSED [ 36%]
tests/config/test_constants.py::test_constant_has_expected_type[KILL_SWITCH_STALENESS_S-float] PASSED [ 40%]
tests/config/test_constants.py::test_constant_has_expected_type[KILL_SWITCH_DEVIATION_C-int] PASSED [ 44%]
tests/config/test_constants.py::test_constant_has_expected_type[KILL_SWITCH_BRIER_BOUND-float] PASSED [ 48%]
tests/config/test_constants.py::test_constant_has_expected_type[KILL_SWITCH_BRIER_WINDOW-int] PASSED [ 52%]
tests/config/test_constants.py::test_constant_has_expected_type[VEGA_DIRECTIONAL_THRESHOLD-float] PASSED [ 56%]
tests/config/test_constants.py::test_shrink_prior_positive PASSED        [ 60%]
tests/config/test_constants.py::test_signal_scale_in_unit_interval PASSED [ 64%]
tests/config/test_constants.py::test_gun_win_rate_is_a_probability PASSED [ 68%]
tests/config/test_constants.py::test_regulation_half_and_win_threshold_match_valorant_rules PASSED [ 72%]
tests/config/test_constants.py::test_kelly_multiplier_is_half PASSED     [ 76%]
tests/config/test_constants.py::test_per_market_cap_frac_is_a_small_fraction PASSED [ 80%]
tests/config/test_constants.py::test_kill_switch_staleness_positive_seconds PASSED [ 84%]
tests/config/test_constants.py::test_kill_switch_deviation_positive_cents PASSED [ 88%]
tests/config/test_constants.py::test_kill_switch_brier_bound_in_unit_interval PASSED [ 92%]
tests/config/test_constants.py::test_kill_switch_brier_window_is_positive_int PASSED [ 96%]
tests/config/test_constants.py::test_vega_directional_threshold_in_unit_interval PASSED [100%]

============================= 25 passed in 1.03s ==============================
EXIT: 0

$ uv run mypy --strict src/config/constants.py
Success: no issues found in 1 source file
EXIT: 0

$ uv run mypy --strict src/pricing/
Success: no issues found in 1 source file
EXIT: 0

$ uv run ruff check .
All checks passed!
EXIT: 0

$ uv run python -c "from src.config.constants import KILL_SWITCH_STALENESS_S, KELLY_MULTIPLIER, GUN_WIN_RATE; assert KILL_SWITCH_STALENESS_S == 5.0 and KELLY_MULTIPLIER == 0.5 and GUN_WIN_RATE == 0.822; print('ok')"
ok
EXIT: 0
```

All commands exit 0.

Note on a benign mypy emission: when running `mypy --strict src/config/constants.py` directly, mypy prints `pyproject.toml: note: unused section(s): module = ['src.pricing.*']`. This is a config-level note about the `[[tool.mypy.overrides]]` block from Plan 00-01 not matching the targeted file (constants.py is in `src.config`, not `src.pricing`). Exit code is still 0 and `mypy --strict src/pricing/` continues to find the override correctly. No action — would require modifying Plan 00-01 toolchain config which is out of scope.

## Decisions Made

- **`KILL_SWITCH_*` prefix locked** — implemented `KILL_SWITCH_STALENESS_S`, `KILL_SWITCH_DEVIATION_C`, `KILL_SWITCH_BRIER_BOUND`, `KILL_SWITCH_BRIER_WINDOW` per user-resolved CON-domain-constants-baseline (2026-04-27). CLAUDE.md "Domain constants" section still shows the older shorter form (`KILL_API_*`, `KILL_STALENESS_*`, etc.) and should be reconciled in a separate doc-fix PR — flagging for project owner. **Action item for downstream:** update `CLAUDE.md` "Domain constants" code block lines 80-83 to use `KILL_SWITCH_*` prefix to match `src/config/constants.py` and roadmap.md §0.4. **Not done in this plan** because the plan scope is "this plan only writes code" per `<interfaces>`.
- **Per-constant docstrings** (Python `"""…"""` immediately following each `Final[...]` assignment) chosen over a single module-level value table — surfaces in IDE hover help at every import site and makes the source citation visible during downstream development.
- **Parametrized type test with `EXPECTED_TYPES` dict** chosen over 12 individual `def test_*_is_float` functions — single source of truth for the type contract; adding/removing a constant requires updating one place.
- **`test_no_unexpected_uppercase_names_leak_in`** added beyond the plan's explicit test list — provides a one-time alarm if a future contributor adds a new UPPER_CASE name without registering it in `EXPECTED_NAMES`. Defensive correctness (Rule 2 minor scope addition within "auto-add missing critical functionality").

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Replaced `from src.config import constants as C` with `from src.config import constants`**

- **Found during:** Task 2 ruff verification.
- **Issue:** The plan-mandated test code uses `from src.config import constants as C` (alias `C`). Ruff's `pep8-naming` rule `N812` flags this as `Lowercase 'constants' imported as non-lowercase 'C'`. The plan also requires `uv run ruff check tests/config/` to exit 0, so the plan-mandated alias is internally inconsistent with the plan's success criteria.
- **Fix:** Removed the alias; replaced every `C.` with `constants.` and every `getattr(C, …)` / `dir(C)` with `getattr(constants, …)` / `dir(constants)`. All test logic preserved verbatim — same assertions, same parametrize, same invariants.
- **Files modified:** `tests/config/test_constants.py` (Task 2 commit, pre-commit fix).
- **Verification:** `uv run ruff check tests/config/` exits 0; all 25 pytest cases still pass.
- **Committed in:** `d78eca6` (Task 2 commit — fix folded in before commit).

**2. [Rule 1 - Bug] Collapsed extra blank line between import block and first section banner (ruff `--fix` for `I001`)**

- **Found during:** Task 2 ruff verification (after fix #1).
- **Issue:** With the alias removed, ruff `I001` (`Import block is un-sorted or un-formatted`) still flagged the file because there were two blank lines between `from src.config import constants` and the `# 1. Importability` section banner. Ruff's isort wants a single blank line at the end of the import block.
- **Fix:** Ran `uv run ruff check --fix tests/config/test_constants.py`, which auto-collapsed one blank line.
- **Files modified:** `tests/config/test_constants.py` (Task 2 commit, pre-commit fix).
- **Verification:** `uv run ruff check tests/config/` exits 0.
- **Committed in:** `d78eca6` (Task 2 commit — fix folded in before commit).

---

**Total deviations:** 2 auto-fixed (both Rule 1 — code that wouldn't pass the plan's own success criteria as literally written). 0 architectural changes (no Rule 4 checkpoint needed). Both deviations preserved 100% of test logic; only the import expression style changed.

**Impact on plan:** None — the constants exported, the values asserted, and the invariants checked are exactly as the plan specified. The plan's verification commands all pass after the deviations.

## Issues Encountered

None beyond the two Rule 1 fixes above. The mypy "unused section(s)" note is a Plan 00-01 config artifact (out of scope) and does not affect exit codes.

## Naming Reconciliation Flag for Project Owner

CLAUDE.md "Domain constants" section (project root, lines 80-83) still uses the OLDER `KILL_*` prefix form:

```
KILL_API_*           = ...    # CLAUDE.md still says this
KILL_STALENESS_S     = ...
KILL_DEVIATION_C     = ...
KILL_BRIER_BOUND     = ...
KILL_BRIER_WINDOW    = ...
```

`src/config/constants.py` (this plan) and `roadmap.md §0.4` and `intel/constraints.md` (CON-domain-constants-baseline) and `intel/decisions.md` (DEC-005 corroborating note 2026-04-27) all use the LOCKED `KILL_SWITCH_*` form. **Recommended doc-fix PR:** update CLAUDE.md "Domain constants" block to match. **Not done here** — the plan explicitly states "this plan only writes code" (in `<interfaces>` naming-prefix note).

## User Setup Required

None. Constants are pure data; tests run via existing `uv run pytest`.

## Downstream Plan Confirmation

- **Phase 1 pricing engine** (DP, Bradley-Terry blend, round-conclusion lookup, `live_theo`) **must import** `from src.config.constants import SHRINK_PRIOR, SIGNAL_SCALE, GUN_WIN_RATE, REGULATION_HALF, WIN_THRESHOLD` — never hardcode these values. `mypy --strict src/pricing/` will enforce the `Final[float|int]` contract.
- **Phase 4 quoting** must import `KELLY_MULTIPLIER`, `PER_MARKET_CAP_FRAC`, `VEGA_DIRECTIONAL_THRESHOLD`, and the four `KILL_SWITCH_*` constants.
- **Phase 5 calibration** is the only place where the TBD-marked constants (`PER_MARKET_CAP_FRAC`, `VEGA_DIRECTIONAL_THRESHOLD`) — and possibly the four `KILL_SWITCH_*` thresholds — should be re-tuned. Updates must edit BOTH `src/config/constants.py` AND `tests/config/test_constants.py` invariants.
- **`test_no_unexpected_uppercase_names_leak_in`** will fail-loud if a future plan adds a new UPPER_CASE constant without registering it in `EXPECTED_NAMES`. This is intentional — forces explicit acknowledgement of new threshold additions.

## Next Phase Readiness

- Phase 0 Wave 2 plan 00-02 (this plan) complete. Plan 00-03 (dry-run-default entry point) running in parallel in a sibling worktree; its merge will close out Phase 0.
- After Phase 0 merges: Phase 1 (pricing) is unblocked and can begin importing from `src.config.constants`.
- No blockers.

## Self-Check: PASSED

- `src/config/constants.py` exists at `src/config/constants.py`.
- All 12 expected names found via `grep "^${name}: Final\[" src/config/constants.py`.
- `tests/config/__init__.py` exists.
- `tests/config/test_constants.py` exists.
- `uv run pytest tests/config/test_constants.py` reports `25 passed`.
- `uv run mypy --strict src/config/constants.py` exits 0.
- `uv run mypy --strict src/pricing/` exits 0 (regression check).
- `uv run ruff check .` exits 0.
- Commit `8ec55f2` (Task 1) found via `git log --oneline -3`.
- Commit `d78eca6` (Task 2) found via `git log --oneline -3`.
- Post-commit deletion check: 0 unexpected deletions on either commit.

```text
$ git log --oneline -3
d78eca6 test(00-02): add tests/config/test_constants.py with 25 sanity checks
8ec55f2 feat(00-02): add canonical thresholds module src/config/constants.py
84a07f0 docs(00-01): complete project-structure-and-tooling plan
```

---
*Phase: 00-foundation*
*Plan: 02-domain-constants*
*Completed: 2026-04-27*
