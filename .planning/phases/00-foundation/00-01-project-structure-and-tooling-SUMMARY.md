---
phase: 00-foundation
plan: 01
subsystem: infra
tags: [python, uv, pyproject, ruff, mypy, pytest, hypothesis, hatchling]

# Dependency graph
requires:
  - phase: bootstrap
    provides: ".planning/ scaffolding, codebase map, intel/decisions.md (DEC-014, DEC-019)"
provides:
  - "pyproject.toml with Python 3.11 pin, uv-managed dev deps (pytest, pytest-cov, hypothesis, ruff, mypy), [tool.mypy] strict override on src.pricing.*"
  - ".python-version pinning 3.11"
  - "uv.lock (committed for reproducibility — Phase 6 inherits)"
  - "src/__init__.py + src/{pricing,state,ingestion,quoting,sizing,config}/__init__.py — every src/* is a real importable Python package"
  - "tests/__init__.py + tests/test_smoke.py — pytest sentinel so --collect-only exits 0 on the empty skeleton"
  - "data/, models/, logs/, scripts/ all retain .gitkeep placeholders"
  - ".gitignore extended with .uv/, models/dp_table.pkl, data/round_events*, .tox/, .nox/"
  - "Toolchain contract: `uv sync && uv run mypy --strict src/pricing/ && uv run ruff check . && uv run pytest --collect-only` is green from a clean clone"
affects: [phase-1-pricing, phase-2-round-events, phase-3-ingestion, phase-4-quoting, phase-5-validation, phase-6-deployment, phase-0-plan-02-constants, phase-0-plan-03-entry-point]

# Tech tracking
tech-stack:
  added: ["uv 0.11.8", "pytest 9.0.3", "pytest-cov 7.1.0", "hypothesis 6.152.4", "ruff 0.15.12", "mypy 1.20.2", "hatchling (PEP 517 backend)"]
  patterns:
    - "uv-managed venv with package = true (project installed editable into .venv)"
    - "PEP 735 [dependency-groups] for dev deps (uv-default install target)"
    - "[tool.mypy.overrides] strict = true ONLY on src.pricing.* — gradual elsewhere"
    - "pytest sentinel pattern: tests/test_smoke.py prevents pytest exit-5 on empty skeleton"
    - "uv.lock committed (application-project convention, not library)"

key-files:
  created:
    - "pyproject.toml"
    - ".python-version"
    - "uv.lock"
    - "README.md (stub — required by hatchling readme metadata)"
    - "src/__init__.py + src/{pricing,state,ingestion,quoting,sizing,config}/__init__.py"
    - "tests/__init__.py"
    - "tests/test_smoke.py"
    - "data/.gitkeep"
  modified:
    - ".gitignore (extended; uv.lock NOT added — committed)"
  removed:
    - "src/pricing/.gitkeep, src/state/.gitkeep, src/ingestion/.gitkeep, src/quoting/.gitkeep, src/sizing/.gitkeep, src/config/.gitkeep (superseded by __init__.py)"

key-decisions:
  - "uv.lock committed (not gitignored) per uv application-project convention — Phase 6 deployment inherits deterministic build"
  - "[tool.mypy.overrides] applies strict mode to src.pricing.* only; other layers gradual per CON-mypy-strict-pricing scope"
  - "tests/test_smoke.py sentinel chosen over `--collect-only --noconftest` workaround — explicit + safe to delete once real tests land"
  - "README.md stub created (Rule 3 deviation: hatchling readme metadata blocks `uv sync` without it)"

patterns-established:
  - "Single canonical pyproject.toml — no setup.py / setup.cfg / requirements.txt mix"
  - "Strict typing scoped to math layer only (src.pricing.*); elsewhere ignore_missing_imports=true allows iteration without type-noise"
  - "data/, models/, logs/ are gitignored at directory level, with allow-list overrides (data/half_win_rates.json, *.gitkeep) — explicit artifact ignores in addition serve as documentation"

requirements-completed: []  # Plan 00-01 has no REQ-IDs in `requirements:` frontmatter (it is bootstrap infra).

# Metrics
duration: 6min
completed: 2026-04-27
---

# Phase 0 Plan 01: Project Structure and Tooling Summary

**uv-managed Python 3.11 project with `mypy --strict` on `src/pricing/`, ruff lint, pytest+hypothesis test infra, and a real Python package skeleton — toolchain is green on the empty skeleton from a clean clone.**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-04-27T20:48:00Z
- **Completed:** 2026-04-27T20:53:29Z
- **Tasks:** 2
- **Files created:** 13
- **Files modified:** 1 (`.gitignore`)
- **Files removed:** 6 (`src/*/.gitkeep` superseded by `__init__.py`)

## Accomplishments

- `pyproject.toml` declares Python 3.11, uv-managed dev deps (pytest 9.0.3, pytest-cov 7.1.0, hypothesis 6.152.4, ruff 0.15.12, mypy 1.20.2), ruff line-length 100 / py311 target, pytest testpaths=tests, and a `[[tool.mypy.overrides]]` block applying `strict = true` to `src.pricing.*` only (CON-mypy-strict-pricing).
- Every `src/*/` is a real Python package (has `__init__.py`); `src` is installed editable into `.venv` via `[tool.uv] package = true`, so downstream imports like `from src.config.constants import GUN_WIN_RATE` will resolve in Plan 02.
- `tests/__init__.py` + `tests/test_smoke.py` provide a passing pytest sentinel so `pytest --collect-only` exits 0 (not 5) on an otherwise-empty test suite.
- `uv.lock` committed for reproducibility (uv application-project convention) — Phase 6 Docker build will inherit deterministic dep resolution.
- `.gitignore` extended with `.uv/`, `models/dp_table.pkl`, `data/round_events*`, `data/round_events.sqlite`, `.tox/`, `.nox/`. Existing `data/half_win_rates.json` allow-list preserved. `uv.lock` is NOT in `.gitignore`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Create pyproject.toml + .python-version + uv.lock + README stub** — `91a6419` (chore)
2. **Task 2: Convert src/* to real Python packages + pytest sentinel + .gitignore extensions** — `83b00b0` (feat)

**Plan metadata commit (forthcoming):** SUMMARY.md + STATE.md + ROADMAP.md updates committed by the executor's final-commit step.

## Files Created/Modified

### Created

- `pyproject.toml` — Python 3.11 + uv project config; dev-deps; ruff config; pytest config; mypy default + strict override on `src.pricing.*`; hatchling build backend with `packages = ["src"]`
- `.python-version` — single line `3.11` for uv venv pin
- `uv.lock` — 266-line lock file resolving 17 packages; **committed** (not gitignored)
- `README.md` — minimal stub (4 lines); required because `pyproject.toml [project] readme = "README.md"` makes hatchling validate file existence on `build_editable`
- `src/__init__.py` — top-level package marker, references DEC-010 (single canonical `live_theo`) and DEC-016 (constants policy)
- `src/pricing/__init__.py` — math-layer marker; doc reminds future code to source thresholds from `src.config.constants`
- `src/state/__init__.py`, `src/ingestion/__init__.py`, `src/quoting/__init__.py`, `src/sizing/__init__.py`, `src/config/__init__.py` — one-line module docstrings each
- `tests/__init__.py` — pytest test-suite package marker
- `tests/test_smoke.py` — `def test_smoke() -> None: assert True` sentinel; pytest collects 1 test → exit 0
- `data/.gitkeep` — placeholder (sibling of `data/half_win_rates.json`)

### Modified

- `.gitignore` — appended `.uv/`, `models/dp_table.pkl`, `data/round_events*`, `data/round_events.sqlite`, `.tox/`, `.nox/`. No existing rules removed or reordered.

### Removed

- `src/pricing/.gitkeep`, `src/state/.gitkeep`, `src/ingestion/.gitkeep`, `src/quoting/.gitkeep`, `src/sizing/.gitkeep`, `src/config/.gitkeep` — superseded by `__init__.py` files. (Note: git detected `data/.gitkeep` as a rename from `src/config/.gitkeep` because both are empty; this is benign — the new `data/.gitkeep` is independent.)

## Resolved Dependency Versions (`uv pip list`)

| Package | Version |
|---|---|
| colorama | 0.4.6 |
| coverage | 7.13.5 |
| hypothesis | 6.152.4 |
| iniconfig | 2.3.0 |
| librt | 0.9.0 |
| mypy | 1.20.2 |
| mypy-extensions | 1.1.0 |
| packaging | 26.2 |
| pathspec | 1.1.1 |
| pluggy | 1.6.0 |
| pygments | 2.20.0 |
| pytest | 9.0.3 |
| pytest-cov | 7.1.0 |
| ruff | 0.15.12 |
| sortedcontainers | 2.4.0 |
| typing-extensions | 4.15.0 |
| valorant-pricing-model | 0.1.0 (editable, this repo) |

uv tool itself: `uv 0.11.8 (0e961dd9a 2026-04-27 x86_64-pc-windows-msvc)`.

## Toolchain Verification (the four commands the plan promised)

```text
$ uv sync
Resolved 18 packages in 1ms
Checked 17 packages in 2ms
EXIT: 0

$ uv run mypy --strict src/pricing/
Success: no issues found in 1 source file
EXIT: 0

$ uv run ruff check .
All checks passed!
EXIT: 0

$ uv run pytest --collect-only
============================= test session starts =============================
platform win32 -- Python 3.11.6, pytest-9.0.3, pluggy-1.6.0
rootdir: C:\Users\josep\OneDrive\Desktop\Thunderedge\valorant-pricing-model
configfile: pyproject.toml
testpaths: tests
plugins: hypothesis-6.152.4, cov-7.1.0
collected 1 item

<Dir valorant-pricing-model>
  <Package tests>
    <Module test_smoke.py>
      <Function test_smoke>

========================== 1 test collected in 1.02s ==========================
EXIT: 0
```

All four exit 0. Package skeleton imports cleanly:
```text
$ uv run python -c "import src; import src.pricing; import src.state; import src.ingestion; import src.quoting; import src.sizing; import src.config; print('ok')"
ok
```

## Decisions Made

- **uv install via `pip install --user uv`** (rather than pipx — pipx not present on host) — installed `uv 0.11.8` to `%APPDATA%\Roaming\Python\Python311\Scripts\`; future executor sessions need this dir on PATH (or use uv's installer for system-wide install).
- **No top-level `[tool.uv].dev-dependencies` block** — used PEP 735 `[dependency-groups].dev` instead, which is uv's default `--group dev` install target and the plan's explicit instruction.
- **`fail_under = 0` for coverage** in Phase 0 — Phase 5 (CON-coverage-target = 80%) will tighten this when real tests land.
- **`disallow_any_explicit = false` in the strict pricing override** — keeps the door open for `Any` in narrow, explicitly-written places per the plan instruction; `warn_return_any = true` still catches accidental `Any` returns.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed `uv` via `pip install --user uv`**
- **Found during:** Pre-Task 1 environment check.
- **Issue:** `uv` was not on PATH; the plan assumes the four `uv run …` commands are runnable.
- **Fix:** `pip install --user uv` (uv 0.11.8). Used inline `PATH` extension `export PATH="/c/Users/josep/AppData/Roaming/Python/Python311/Scripts:$PATH"` for each shell call.
- **Files modified:** None in repo (uv installed to user-site `Scripts/`).
- **Verification:** `uv --version` → `uv 0.11.8`.
- **Committed in:** N/A (no in-repo files affected).

**2. [Rule 3 - Blocking] Created `README.md` stub (4 lines)**
- **Found during:** Task 1 (initial `uv sync`).
- **Issue:** `pyproject.toml` declares `readme = "README.md"`. Hatchling's `build_editable` raised `OSError: Readme file does not exist: README.md` and `uv sync` failed before installing any deps. The plan's exact `pyproject.toml` text mandates `readme = "README.md"`, so removing the line would deviate further from the plan than creating the stub.
- **Fix:** Wrote a 4-line `README.md` pointing to `prd.md`, `roadmap.md`, `CLAUDE.md` for design intent.
- **Files modified:** `README.md` (new).
- **Verification:** `uv sync` re-run, succeeded; built editable wheel and installed all 17 packages.
- **Committed in:** `91a6419` (Task 1 commit).

---

**Total deviations:** 2 auto-fixed (both Rule 3 blocking). 0 architectural changes — no Rule 4 checkpoint needed.
**Impact on plan:** Both deviations were pre-conditions for the plan's verification commands to run. Neither expands scope nor modifies the locked decisions. The `README.md` stub will be replaced with real content in a later plan (or as part of Phase 7 operational maturity); it is intentionally minimal.

## Issues Encountered

None beyond the two Rule 3 deviations above. Git's automatic rename detection identified `data/.gitkeep` as a rename of `src/config/.gitkeep` because both files are empty — this is cosmetic in `git log --stat` output and does not affect correctness.

## User Setup Required

None. The toolchain installs locally via `uv sync` from a clean clone (assumes Python 3.11 + uv on PATH; uv install is a one-time host-level setup).

## Downstream Plan Confirmation (per plan §output)

- Plan 00-02 (domain constants) **can rely on** `from src.config.constants import GUN_WIN_RATE` resolving once the file is created — `src.config` is now an importable package and the project is editable-installed under `.venv`.
- Plan 00-03 (dry-run-default entry point) **can rely on** `from src.* import …` resolving for any subpackage it lands in.
- `mypy --strict src/pricing/` will continue to pass as long as Plan 02+ keep their `src.pricing.*` modules fully type-annotated. The override block is in place; no further config changes are needed for strict-mode enforcement.

## Next Phase Readiness

- Phase 0 Wave 2 (Plans 00-02 and 00-03) is unblocked and can run in parallel.
- After Phase 0 completes, Phases 1, 2, 3 are unblocked for parallel planning per the roadmap dependency graph.
- No blockers.

## Self-Check: PASSED

- `pyproject.toml` exists at repo root.
- `.python-version` exists, contains `3.11`.
- `uv.lock` exists (266 lines, 17 packages).
- `README.md` exists (stub).
- All seven `__init__.py` files exist (`src/`, `src/pricing/`, `src/state/`, `src/ingestion/`, `src/quoting/`, `src/sizing/`, `src/config/`).
- `tests/__init__.py` and `tests/test_smoke.py` exist.
- `data/.gitkeep`, `models/.gitkeep`, `logs/.gitkeep`, `scripts/.gitkeep`, `tests/.gitkeep` all exist.
- No leftover `.gitkeep` in any `src/*/` subdir.
- `.gitignore` does NOT contain `^uv\.lock$` (uv.lock committed); does contain `data/round_events`.
- Commits `91a6419` and `83b00b0` exist on `main`.

```text
$ git log --oneline -3
83b00b0 feat(00-01): convert src/* to real Python packages + pytest sentinel
91a6419 chore(00-01): bootstrap pyproject.toml + uv toolchain (Python 3.11)
097fdf1 docs(00-foundation): plan Phase 0 (3 plans, 2 waves)
```

---
*Phase: 00-foundation*
*Plan: 01-project-structure-and-tooling*
*Completed: 2026-04-27*
