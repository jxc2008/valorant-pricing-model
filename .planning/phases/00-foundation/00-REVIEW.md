---
phase: 00-foundation
reviewed: 2026-04-27T00:00:00Z
depth: standard
files_reviewed: 19
files_reviewed_list:
  - .gitignore
  - .python-version
  - README.md
  - pyproject.toml
  - src/__init__.py
  - src/__main__.py
  - src/config/__init__.py
  - src/config/constants.py
  - src/ingestion/__init__.py
  - src/main.py
  - src/pricing/__init__.py
  - src/quoting/__init__.py
  - src/sizing/__init__.py
  - src/state/__init__.py
  - tests/__init__.py
  - tests/config/__init__.py
  - tests/config/test_constants.py
  - tests/test_main.py
  - tests/test_smoke.py
findings:
  critical: 0
  warning: 5
  info: 5
  total: 10
status: issues_found
---

# Phase 0: Code Review Report

**Reviewed:** 2026-04-27
**Depth:** standard
**Files Reviewed:** 19
**Status:** issues_found

## Summary

Phase 0 (foundation) lands the toolchain (`pyproject.toml`, uv, ruff, mypy strict on `src/pricing/`), the canonical thresholds module (`src/config/constants.py`), and the dry-run-default CLI entry point (`src/main.py`). The four CLAUDE.md must-have rules in scope for this phase (rule 7 — half-Kelly via constants; rule 9 — kill-switch thresholds; rule 11 — `mypy --strict` on pricing; rule 12 — no magic numbers; rule 13 — dry-run default) are all wired correctly at the structural level, and the test suite genuinely locks the safety invariants rather than tautologically re-importing.

The defects found are not behavior-blockers for Phase 0 because no business logic has shipped yet — but several would silently weaken the very safety contracts Phase 0 exists to establish, and one is a stale documentation claim that contradicts the source of truth it cites. None are CRITICAL (no security holes, no shipped-bug paths, no incorrect math); all are WARNING/INFO. They should be cleaned up before Phase 1 starts importing from these modules.

Highlights:

- **WR-01** — `resolve_dry_run` returns `DRY_RUN_DEFAULT` (a mutable module attribute) on the no-`--live` branch instead of a literal `True`. Anyone editing the module-level `DRY_RUN_DEFAULT` to `False` would silently flip the bot live without `--live`, which is the exact contract the function exists to enforce.
- **WR-02** — `src/config/constants.py` lines 26-29 and the constants module docstring assert that "CLAUDE.md still shows the older `KILL_*` form and will be reconciled in a doc-fix PR." This is false — CLAUDE.md lines 80-83 already use the `KILL_SWITCH_*` prefix. The 00-02-SUMMARY.md repeats the same false claim and recommends an unnecessary doc-fix PR.
- **WR-03** — `pyproject.toml` `[tool.coverage.run] source = ["src/pricing"]` scopes coverage measurement to a single subpackage that is empty in Phase 0, while tests run against `src/main.py` and `src/config/constants.py` (outside that scope). No bug today (Phase 0 has `fail_under = 0`), but Phase 5 will tighten the coverage gate to 80% and discover that none of the current tests are counted.
- **WR-04** — `pyproject.toml` `[tool.mypy] exclude = ["reference/", "models/", "logs/", "scripts/"]` is dead config: `files = ["src", "tests"]` already restricts the run to those two trees, none of which contain `reference/`, `models/`, `logs/`, `scripts/`. Either prune or change to `files = ["."]` if directory-wide exclusion was the intent.
- **WR-05** — `tests/config/test_constants.py::test_no_unexpected_uppercase_names_leak_in` does not filter out names introduced by `from typing import Final` and similar imports robustly; if a future contributor adds e.g. `from typing import TYPE_CHECKING` to the constants module the test will fail-loud for the wrong reason (it is not a "new threshold," it is an import name).

## Warnings

### WR-01: `resolve_dry_run` indirects safety guarantee through a mutable module constant

**File:** `src/main.py:103-105`
**Issue:** The function reads:

```python
if args.live:
    return False
return DRY_RUN_DEFAULT
```

`DRY_RUN_DEFAULT` is a module-level `Final[bool] = True`. `Final` blocks `mypy --strict` reassignment but does NOT prevent runtime mutation — `src.main.DRY_RUN_DEFAULT = False` from any importer, test fixture, or REPL session silently flips the bot to live mode without `--live`. The whole point of `resolve_dry_run` is to guarantee that omitting `--live` always returns `True`; routing that guarantee through a module attribute instead of a literal weakens the contract.

`test_dry_run_default_is_true` asserts the constant is `True` at import time — but the resolver's behavior should be locked even if the constant is later mutated, because the constant exists for documentation, not for branch-control.

**Fix:** Return the literal directly. Keep `DRY_RUN_DEFAULT` as a documentation-only constant and have the resolver assert against it:

```python
def resolve_dry_run(args: argparse.Namespace) -> bool:
    # SAFETY: the literal True here is the dry-run safety contract
    # (CLAUDE.md rule 13 / DEC-022). Do NOT replace with DRY_RUN_DEFAULT —
    # that constant is documentation, not control flow.
    if args.live:
        return False
    return True
```

Optionally add `assert DRY_RUN_DEFAULT is True` at module top to keep the doc-constant honest.

### WR-02: Constants module docstring + 00-02-SUMMARY make a false claim about CLAUDE.md

**File:** `src/config/constants.py:26-29`
**Issue:** The module docstring states:

```
the shorter ``KILL_*`` form in CLAUDE.md "Domain constants" is the older form and
will be reconciled in a doc-fix PR.
```

CLAUDE.md lines 80-83 (the very block this docstring cites) already uses `KILL_SWITCH_STALENESS_S`, `KILL_SWITCH_DEVIATION_C`, `KILL_SWITCH_BRIER_BOUND`, `KILL_SWITCH_BRIER_WINDOW` — i.e., the canonical prefix this module already uses. There is no `KILL_*` form in CLAUDE.md to reconcile; the doc-fix PR the comment recommends would be a no-op.

The same false claim is duplicated in `.planning/phases/00-foundation/00-02-domain-constants-SUMMARY.md` lines 224-235 ("Naming Reconciliation Flag for Project Owner"). This will mislead future maintainers into doing unnecessary work and erode trust in the SUMMARY.md format as a record of truth.

**Fix:** Remove the misleading paragraph from the docstring (delete `src/config/constants.py:26-29`) and update or remove the corresponding SUMMARY section. If there ever was an older form somewhere, cite the actual file/line where it appears (e.g., `roadmap.md`) rather than CLAUDE.md.

### WR-03: Coverage scope (`source = ["src/pricing"]`) excludes every file Phase 0 actually tests

**File:** `pyproject.toml:71-73`
**Issue:**

```toml
[tool.coverage.run]
source = ["src/pricing"]
branch = true
```

Phase 0 has zero source files in `src/pricing/` (only `__init__.py`). The actual tested code lives in `src/main.py` (`tests/test_main.py`, 10 cases) and `src/config/constants.py` (`tests/config/test_constants.py`, 25 cases). With this `source` scope, `pytest --cov` reports 0% coverage for `src/pricing/__init__.py` and reports nothing about `src/main.py` or `src/config/constants.py`.

This is harmless today because `fail_under = 0` (line 76), but Phase 5 will set the gate to 80% (per the comment on line 76) and discover that the coverage report has no signal — main and constants will never be measured under the current scope.

**Fix:** Either expand the source scope to the whole package now:

```toml
[tool.coverage.run]
source = ["src"]
branch = true
```

…or leave the narrow scope but add a TODO citing the Phase 5 gate change:

```toml
# TODO Phase 5 (CON-coverage-target = 80%): expand source = ["src"]
# before raising fail_under, otherwise the coverage gate measures only
# the math layer and silently passes for every other module.
source = ["src/pricing"]
```

The first option is preferable — coverage scope should match the test scope.

### WR-04: Dead `[tool.mypy] exclude` entries — paths are not under `files = ["src", "tests"]`

**File:** `pyproject.toml:83-84`
**Issue:**

```toml
files = ["src", "tests"]
exclude = ["reference/", "models/", "logs/", "scripts/"]
```

mypy's `files` already constrains the run to `src/` and `tests/`. None of `reference/`, `models/`, `logs/`, `scripts/` are inside those trees — so listing them in `exclude` is unreachable config that gives a false sense of defensive scoping.

If the intent is "in case someone runs `mypy .`, skip those directories", that requires `files = ["."]` (or omitting `files` entirely so the user-supplied path takes effect) for the exclude to apply.

This is also why `mypy --strict src/config/constants.py` prints `pyproject.toml: note: unused section(s): module = ['src.pricing.*']` (mentioned in 00-02-SUMMARY.md): the override block matches no module when the user names a path outside `src.pricing.*`. The same dead-config pattern.

**Fix:** Either trim the exclude list to match reality:

```toml
files = ["src", "tests"]
# exclude removed — files already restricts scope.
```

…or expand `files` so the exclude has effect:

```toml
files = ["."]
exclude = ["reference/", "models/", "logs/", "scripts/", ".venv/", "build/", "dist/"]
```

Pick one. The current state is internally inconsistent.

### WR-05: `test_no_unexpected_uppercase_names_leak_in` is fragile against import-side names

**File:** `tests/config/test_constants.py:54-66`
**Issue:** The test guards against new uppercase names being added to `constants.py` without registration in `EXPECTED_NAMES`:

```python
actual_uppercase = {
    n
    for n in dir(constants)
    if n.isupper() and not n.startswith("_") and not callable(getattr(constants, n))
}
```

This filters out double-underscore dunders and callable attributes, but does NOT filter out non-callable uppercase names introduced by imports. Today `from typing import Final` is fine because `Final` is mixed-case. But a future innocent edit like `from typing import TYPE_CHECKING` (constant, all-uppercase, not callable in some typing-stubs distributions) would fail this test for the wrong reason — TYPE_CHECKING is not a new threshold, it is an import.

The test as written also does not exclude `__future__.annotations` or `Final` from `dir()`, but those happen to not match the predicate. It works by luck of import naming.

**Fix:** Tighten the predicate to only consider names actually defined in the module (`__all__` or `vars(constants)` filtered to module-locals):

```python
def test_no_unexpected_uppercase_names_leak_in() -> None:
    module_locals = {
        name
        for name, value in vars(constants).items()
        if name.isupper()
        and not name.startswith("_")
        and not callable(value)
        and getattr(value, "__module__", constants.__name__) == constants.__name__
    }
    extras = module_locals - set(EXPECTED_NAMES)
    assert not extras, f"Unexpected UPPER_CASE names: {extras}"
```

Or simply add an `__all__` to `constants.py` and assert `set(constants.__all__) == set(EXPECTED_NAMES)`. The current implementation is correct today but brittle.

## Info

### IN-01: `--live` argparse `default=False` is redundant with `store_true`

**File:** `src/main.py:69-79`
**Issue:** `argparse.add_argument("--live", action="store_true", default=False)` — `store_true` already implies `default=False`. The explicit `default=False` is harmless documentation but suggests the author wasn't sure of `store_true` semantics, which can invite incorrect future edits like `default=True` (which `store_true` would silently override on `--live`, but would set `args.live = True` when `--live` is omitted, breaking `resolve_dry_run`).

**Fix:** Drop the redundant default, OR keep it and add an inline comment:

```python
parser.add_argument(
    "--live",
    action="store_true",
    # default=False is redundant with store_true; spelled out for clarity.
    default=False,
    help=...
)
```

### IN-02: `.gitignore` has a project-specific `valorant*.txt` rule with no documentation

**File:** `.gitignore:7`
**Issue:** Line 7 has `valorant*.txt` under the "Secrets — NEVER commit" section. There is no comment explaining what `valorant*.txt` is — presumably a local dev token / API key file the operator generates, but a future contributor cannot tell from this rule alone what file pattern it protects or whether it is still needed.

**Fix:** Add an inline comment:

```
valorant*.txt   # local Kalshi RSA-key working files (per CLAUDE.md / .env.example)
```

…or document the convention in `CLAUDE.md` "Data sources" so the rule is referenced from somewhere.

### IN-03: `data/half_win_rates.json` allow-list rule placed below the `data/*.json` ignore — git ordering is correct, but visual ordering is fragile

**File:** `.gitignore:32, 44`
**Issue:** Line 32 ignores `data/*.json`; line 44 re-includes `!data/half_win_rates.json`. Git's negation pattern requires the negation to appear AFTER the ignore — this is correctly ordered. But the two related rules are 12 lines apart with unrelated patterns between them. A reorder by a contributor "tidying" the file could easily break the allow-list.

**Fix:** Co-locate the two rules with a shared comment:

```
# Generated / large
data/*.csv
data/*.parquet
data/*.db
data/*.sqlite
# Half-win-rates is salvaged input — keep it (negation MUST follow data/*.json above)
data/*.json
!data/half_win_rates.json
```

### IN-04: `disallow_any_explicit = false` and `warn_return_any = true` in the strict-pricing override are redundant relative to `strict = true`

**File:** `pyproject.toml:91-96`
**Issue:** `strict = true` already sets `disallow_any_explicit = false` (the default; only `disallow_any_unimported` etc. are turned on by strict) and `warn_return_any = true`. Spelling them out doesn't hurt, but it suggests the author may have intended to override strict-mode defaults that are not actually changed here. The 00-01-SUMMARY (line 188) explains the intent — keep `Any` available in narrow places — but the spelled-out value is the same as the strict default.

**Fix:** Either remove the redundant lines (cleaner) or add a comment noting they are explicit-but-default-aligned, so a future maintainer doesn't second-guess them.

### IN-05: `src/__main__.py` and `src/main.py` both expose an `if __name__ == "__main__": sys.exit(main())` block, but only one is documented in CLAUDE.md "Run commands"

**File:** `src/__main__.py:1-10`, `src/main.py:168-169`
**Issue:** CLAUDE.md "Run commands" lists `python -m src.main --match <ticker>` only. `src/__main__.py` adds an equivalent `python -m src --match <ticker>` invocation that is documented only in the 00-03-SUMMARY (decision section). New operators reading CLAUDE.md will not know about the `python -m src` route. This is mild documentation drift, not a defect.

**Fix:** Update CLAUDE.md "Run commands" to mention both invocations, OR remove `src/__main__.py` and rely on a single canonical entry point per CLAUDE.md preferences ("One canonical implementation per concept"). The CLAUDE.md preference suggests removing `__main__.py` is more in line with project conventions — having two equivalent entry points violates the "one canonical implementation per concept" rule even though the behavior is identical.

---

_Reviewed: 2026-04-27_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
