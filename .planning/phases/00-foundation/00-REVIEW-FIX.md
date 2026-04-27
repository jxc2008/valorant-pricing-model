---
phase: 00-foundation
fixed_at: 2026-04-27T18:00:00Z
review_path: .planning/phases/00-foundation/00-REVIEW.md
iteration: 1
findings_in_scope: 5
fixed: 5
skipped: 0
status: all_fixed
---

# Phase 0: Code Review Fix Report

**Fixed at:** 2026-04-27T18:00:00Z
**Source review:** `.planning/phases/00-foundation/00-REVIEW.md`
**Iteration:** 1

**Summary:**

- Findings in scope: 5 (WR-01 through WR-05; Info items IN-01..IN-05 out of scope per `fix_scope = critical_warning`)
- Fixed: 5
- Skipped: 0

All toolchain gates remain green after every fix:

- `uv run pytest` — `36 passed`
- `uv run mypy --strict src/pricing/` — `Success: no issues found in 1 source file`
- `uv run ruff check .` — `All checks passed!`

## Fixed Issues

### WR-01: `resolve_dry_run` indirects safety guarantee through a mutable module constant

**Files modified:** `src/main.py`
**Commit:** `5dcf053`
**Applied fix:** Replaced `return DRY_RUN_DEFAULT` with literal `return True`, and made the explicit two-branch form deliberately survive ruff's SIM103 collapse via an inline `# noqa` annotation. `DRY_RUN_DEFAULT` retained as documentation with an expanded docstring explaining the literal-vs-attribute split, plus a defensive `assert DRY_RUN_DEFAULT is True` at module top so the doc-constant cannot drift out of sync. The dry-run safety contract (CLAUDE.md rule 13 / DEC-022) is now unfakeable: a runtime mutation of `src.main.DRY_RUN_DEFAULT` no longer reaches the resolver.

### WR-02: Constants module docstring makes a false claim about CLAUDE.md

**Files modified:** `src/config/constants.py`
**Commit:** `7aea151`
**Applied fix:** Removed the misleading paragraph claiming CLAUDE.md still uses the older `KILL_*` form. Replaced with a citation noting both `roadmap.md §0.4` and `CLAUDE.md "Domain constants" lines 80-83` use the canonical `KILL_SWITCH_*` prefix. The duplicate claim in `00-02-domain-constants-SUMMARY.md` was left untouched per the prompt's instruction (frozen artifact).

### WR-03: Coverage scope (`source = ["src/pricing"]`) excludes every file Phase 0 actually tests

**Files modified:** `pyproject.toml`
**Commit:** `3afe60d`
**Applied fix:** Broadened `[tool.coverage.run] source` from `["src/pricing"]` to `["src"]` so Phase 0's tested code (`src/main.py`, `src/config/constants.py`) is measured. Added an inline comment citing the Phase 5 80% gate (CON-coverage-target) so future maintainers know why the scope is package-wide.

### WR-04: Dead `[tool.mypy] exclude` entries

**Files modified:** `pyproject.toml`
**Commit:** `d4d78b6`
**Applied fix:** Deleted the `exclude = ["reference/", "models/", "logs/", "scripts/"]` line from `[tool.mypy]`. Replaced with a comment documenting the intentional absence: `files = ["src", "tests"]` already pins the scope, none of the excluded paths are inside that scope, so the exclude was unreachable config. This also removes one root cause of the `unused section(s)` mypy hint documented in `00-02-SUMMARY`.

### WR-05: `test_no_unexpected_uppercase_names_leak_in` is fragile against import-side names

**Files modified:** `tests/config/test_constants.py`
**Commit:** `ff91407`
**Applied fix:** Switched the predicate from `dir(constants)` (which includes imported all-caps names) to `constants.__annotations__`. Every legitimate threshold has a `Final[...]` annotation that lands in `__annotations__`; an `import` statement like `from typing import TYPE_CHECKING` does NOT add to `__annotations__`, so the new predicate is robust against future innocent imports of uppercase names. Verified the new predicate correctly excludes `TYPE_CHECKING` via an isolated simulation. The contract is now redundant-but-tight against the existing `test_constant_has_expected_type` (which already enforces `Final[...]` typing).

---

_Fixed: 2026-04-27T18:00:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
