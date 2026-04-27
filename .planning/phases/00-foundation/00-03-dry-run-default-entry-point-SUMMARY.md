---
phase: 00-foundation
plan: 03
subsystem: infra
tags: [cli, argparse, dry-run, safety-default, entry-point]

# Dependency graph
requires:
  - phase: 00-foundation
    plan: 01
    provides: "src/ as importable package, uv toolchain, pytest infra, ruff + mypy strict on src/pricing/"
provides:
  - "src/main.py — CLI entry point exporting DRY_RUN_DEFAULT, build_arg_parser, resolve_dry_run, main"
  - "src/__main__.py — `python -m src` dispatcher to src.main:main"
  - "tests/test_main.py — 10 tests locking the dry-run-default safety contract"
  - "Public API contract Phase 4 will plug into: resolve_dry_run(args) -> bool produced inside main()"
affects: [phase-4-quoting]

# Tech tracking
tech-stack:
  added: []   # No new dependencies — argparse + logging are stdlib; pytest already in dev-deps
  patterns:
    - "CLI flag --live is the SINGLE source of truth for dry-run/live (no constructor arg, no env var, no config-file override) — DEC-022 / CONVENTIONS.md anti-pattern #7"
    - "Double-negative inversion centralized in resolve_dry_run() — downstream sees `dry_run: bool` only, never the flag name"
    - "main(argv: list[str] | None = None) -> int signature for argv-injectable testing without sys.argv pollution"
    - "DRY_RUN_DEFAULT: Final[bool] = True module constant — enforces safety default at import time"
    - "Logging banner convention: `[DRY-RUN]` / `[LIVE]` mode tag prefix on every line for at-a-glance operator visibility"
    - "Phase-0 entry point intentionally has zero trading logic — Phase 4 fans out from main() to KalshiOrderManager + kill switches with the resolved dry_run boolean"

key-files:
  created:
    - "src/main.py"
    - "src/__main__.py"
    - "tests/test_main.py"
  modified: []
  removed: []

key-decisions:
  - "resolve_dry_run reads `args.live` directly (no defensive `getattr(args, 'live', False)`) — argparse `store_true` always sets the attribute, so defensive access would conflict with CLAUDE.md 'terse' preference"
  - "Both `python -m src.main` and `python -m src` invocation paths supported — CLAUDE.md 'Run commands' line documents the former; `__main__.py` makes the latter equivalent (orthogonal entry-point ergonomics, no behavioral split)"
  - "main() is the side-effect boundary; build_arg_parser + resolve_dry_run are pure functions for unit-testability"
  - "logging.basicConfig is gated on `not logging.getLogger().handlers` so importing src.main from a test (which already has a handler from pytest's caplog) does not stomp on existing config"

patterns-established:
  - "Pure-function pricing/business code stays testable; only main() touches stdlib side-effects (logging.basicConfig, sys.argv)"
  - "Tests pass argv explicitly to main() rather than monkeypatching sys.argv — keeps each test pure and independently runnable in any order"
  - "Module-level Final[bool] constant for safety defaults — easier to grep + harder to accidentally mutate than a default argument value"

requirements-completed: []  # Plan 00-03 has no REQ-IDs in `requirements:` frontmatter (it is bootstrap infra)

# Metrics
duration: ~7min
completed: 2026-04-27
---

# Phase 0 Plan 03: Dry-Run-Default Entry Point Summary

**CLI entry point at `src/main.py` locks DEC-022 / CLAUDE.md rule 13 — bot stays in `dry_run=True` unless the operator types `--live` at the command line; tests prove the safety default holds and the flip works in both directions.**

## Performance

- **Duration:** ~7 min
- **Started:** 2026-04-27T20:58:00Z (worktree base reset to post-00-01 HEAD)
- **Completed:** 2026-04-27T21:00:37Z
- **Tasks:** 2
- **Files created:** 3 (src/main.py, src/__main__.py, tests/test_main.py)
- **Files modified:** 0
- **Files removed:** 0
- **Lines added:** 304 (179 source + 125 test)

## Accomplishments

- `src/main.py` exposes the four-symbol public contract Phase 4 will plug into:
  - `DRY_RUN_DEFAULT: Final[bool] = True` (module-level safety constant)
  - `build_arg_parser() -> argparse.ArgumentParser` (registers `--match` required + `--live` store_true)
  - `resolve_dry_run(args) -> bool` (inverts `--live` opt-in into `dry_run` opt-out; reads `args.live` directly)
  - `main(argv: list[str] | None = None) -> int` (argv-injectable for testing; logs mode banner; returns 0)
- `src/__main__.py` makes `python -m src` an equivalent invocation to `python -m src.main`.
- `tests/test_main.py` provides 10 tests covering the constant, argparse semantics, `resolve_dry_run` inversion in both directions, `main()` exit-zero + log-line assertions for both `[DRY-RUN]` and `[LIVE]` (including the DEC-020 promotion-gate warning), and `SystemExit(2)` on missing `--match`.
- CLI smoke verified: `python -m src.main --match TEST` logs `[DRY-RUN]`; `python -m src --match TEST --live` logs `[LIVE]` plus the promotion-gate warning. Both exit 0.
- `mypy --strict src/pricing/` regression passes (Plan 01's strict scope unaffected by main.py since main.py is in `src/`, not `src/pricing/`).
- `ruff check .` passes the whole repo.

## Final file contents

### `src/main.py`

```python
"""CLI entry point — Valorant live pricing bot.

Implements the dry-run-default safety contract per CLAUDE.md rule 13 and
DEC-022 (CON-dry-run-default).

Usage
-----
    python -m src.main --match <kalshi_ticker>          # dry-run (default)
    python -m src.main --match <kalshi_ticker> --live   # live trading

The ``--live`` flag is the SINGLE source of truth for the dry-run/live
distinction. Do not introduce a constructor argument, env var, or config-file
override that can flip this — CONVENTIONS.md anti-pattern #7
(``dry_run as a constructor argument``) is explicitly disallowed.

Phase 0 scope
-------------
This module currently only parses arguments, resolves the dry-run state, and
logs which mode it is in. The actual quoting / trading wiring lives in Phase 4
(``src/quoting/`` + ``src/sizing/``) and will receive the resolved ``dry_run``
boolean from this entry point.

Promotion to live
-----------------
Per DEC-020, the bot must NOT be invoked with ``--live`` until the paper-trade
promotion gate is satisfied (>=1 full event of paper-trading with Brier < 0.22
and zero kill-switch trips for ingestion bugs).
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Final

logger = logging.getLogger(__name__)

DRY_RUN_DEFAULT: Final[bool] = True
"""The safety default: bot is in dry-run unless explicitly told otherwise.

Promotion to live trading requires the operator to type ``--live`` at the
command line. There is no other way to flip this.
"""


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the argparse parser for the bot CLI.

    Returns
    -------
    argparse.ArgumentParser
        Parser with ``--match`` (required str) and ``--live`` (store_true).
    """
    parser = argparse.ArgumentParser(
        prog="valorant-pricing-bot",
        description=(
            "Live pricing engine for Valorant BO3 series + per-map Kalshi "
            "markets. Defaults to dry-run; pass --live to trade with capital."
        ),
    )
    parser.add_argument(
        "--match",
        required=True,
        type=str,
        metavar="TICKER",
        help="Kalshi market ticker for the match to price (e.g. KXVALORANT-25APR27-FNCxNAVI-1).",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        default=False,
        help=(
            "Trade with REAL capital. Without this flag, the bot runs in "
            "dry-run mode (computes theos and logs would-be orders, but "
            "places nothing). Live trading is gated by the paper-trade "
            "promotion gate per DEC-020."
        ),
    )
    return parser


def resolve_dry_run(args: argparse.Namespace) -> bool:
    """Resolve the dry-run flag from parsed args.

    Returns ``True`` (dry-run) unless ``args.live`` is explicitly truthy.
    Inverts the ``--live`` opt-in into the ``dry_run`` opt-out used downstream.

    Parameters
    ----------
    args : argparse.Namespace
        Result of ``build_arg_parser().parse_args(...)``.

    Returns
    -------
    bool
        ``True`` if the bot should run in dry-run mode, else ``False``.
    """
    # The double-negative here is intentional: --live is opt-IN to live
    # trading, dry_run is opt-OUT of safety. Centralizing the inversion
    # in one function means downstream code only sees ``dry_run: bool`` and
    # never has to reason about the CLI flag name.
    if args.live:
        return False
    return DRY_RUN_DEFAULT


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Parses arguments, resolves dry-run state, logs the mode, and returns 0.

    Phase 0 scope: NO trading logic. Phase 4 will extend ``main`` to construct
    ``KalshiOrderManager``, instantiate the kill switches, and start the
    event loop -- passing ``dry_run`` down explicitly.

    Parameters
    ----------
    argv : list[str] | None
        Optional argv list (excluding program name). Defaults to ``sys.argv[1:]``
        when ``None``. Pass an explicit list from tests.

    Returns
    -------
    int
        Process exit code. ``0`` on success.
    """
    # Configure logging only when invoked as a script -- never from library code
    # (CONVENTIONS.md Logging note on basicConfig).
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)-8s %(name)s :: %(message)s",
        )

    parser = build_arg_parser()
    args = parser.parse_args(argv)
    dry_run = resolve_dry_run(args)

    mode_tag = "DRY-RUN" if dry_run else "LIVE"
    logger.info(
        "[%s] Bot starting :: match=%s :: dry_run=%s",
        mode_tag,
        args.match,
        dry_run,
    )

    if dry_run:
        logger.info(
            "[DRY-RUN] No orders will be placed. Pass --live to trade with capital."
        )
    else:
        logger.warning(
            "[LIVE] Live trading is enabled. Verify the paper-trade promotion "
            "gate (DEC-020) has been satisfied before proceeding in production."
        )

    # Phase 0 stops here. Phase 4 will wire:
    #   from src.quoting.order_manager import KalshiOrderManager
    #   from src.quoting.kill_switches import all_switches
    #   ... and start the event loop, passing `dry_run` to the order manager.
    logger.info(
        "[%s] Phase 0 entry point complete (no trading logic wired yet).", mode_tag
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### `src/__main__.py`

```python
"""Allow ``python -m src`` to dispatch to ``src.main:main``."""

from __future__ import annotations

import sys

from src.main import main

if __name__ == "__main__":
    sys.exit(main())
```

### `tests/test_main.py`

```python
"""Tests for src.main — entry point dry-run-default safety.

Locks the contract from CLAUDE.md rule 13 / DEC-022 / CON-dry-run-default:
without ``--live``, the bot is in dry-run; with ``--live``, the bot is in
live mode. ``--match`` is required.
"""

from __future__ import annotations

import logging

import pytest

from src.main import (
    DRY_RUN_DEFAULT,
    build_arg_parser,
    main,
    resolve_dry_run,
)

# --------------------------------------------------------------------------- #
# DRY_RUN_DEFAULT module constant                                             #
# --------------------------------------------------------------------------- #


def test_dry_run_default_is_true() -> None:
    """The module-level safety default MUST be True (CLAUDE.md rule 13)."""
    assert DRY_RUN_DEFAULT is True


# --------------------------------------------------------------------------- #
# build_arg_parser                                                            #
# --------------------------------------------------------------------------- #


def test_parser_requires_match() -> None:
    """Omitting --match must cause argparse to exit with a non-zero code."""
    parser = build_arg_parser()
    with pytest.raises(SystemExit) as excinfo:
        parser.parse_args([])
    # argparse exits with code 2 on usage error.
    assert excinfo.value.code == 2


def test_parser_accepts_match_only() -> None:
    parser = build_arg_parser()
    args = parser.parse_args(["--match", "TEST-TICKER"])
    assert args.match == "TEST-TICKER"
    assert args.live is False


def test_parser_accepts_match_and_live() -> None:
    parser = build_arg_parser()
    args = parser.parse_args(["--match", "TEST-TICKER", "--live"])
    assert args.match == "TEST-TICKER"
    assert args.live is True


def test_live_flag_default_is_false() -> None:
    """Without --live present in argv, the parsed namespace must have args.live == False."""
    parser = build_arg_parser()
    args = parser.parse_args(["--match", "TEST-TICKER"])
    assert args.live is False


# --------------------------------------------------------------------------- #
# resolve_dry_run                                                             #
# --------------------------------------------------------------------------- #


def test_resolve_dry_run_true_when_live_absent() -> None:
    """The single source of truth for safety: no --live → dry_run=True."""
    parser = build_arg_parser()
    args = parser.parse_args(["--match", "TEST-TICKER"])
    assert resolve_dry_run(args) is True


def test_resolve_dry_run_false_when_live_passed() -> None:
    """--live opt-in → dry_run=False."""
    parser = build_arg_parser()
    args = parser.parse_args(["--match", "TEST-TICKER", "--live"])
    assert resolve_dry_run(args) is False


# --------------------------------------------------------------------------- #
# main()                                                                      #
# --------------------------------------------------------------------------- #


def test_main_returns_zero_on_dry_run(caplog: pytest.LogCaptureFixture) -> None:
    """main() with no --live should log [DRY-RUN] and exit 0."""
    with caplog.at_level(logging.INFO, logger="src.main"):
        rc = main(["--match", "TEST-TICKER"])
    assert rc == 0
    # The mode tag MUST appear in at least one log record.
    assert any("DRY-RUN" in record.getMessage() for record in caplog.records), (
        "Expected at least one '[DRY-RUN]' log line, got: "
        f"{[r.getMessage() for r in caplog.records]}"
    )
    assert not any(
        "[LIVE]" in record.getMessage() for record in caplog.records
    ), "Did not expect any '[LIVE]' log line in dry-run mode."


def test_main_returns_zero_on_live(caplog: pytest.LogCaptureFixture) -> None:
    """main() with --live should log [LIVE] (incl. the promotion-gate warning) and exit 0."""
    with caplog.at_level(logging.INFO, logger="src.main"):
        rc = main(["--match", "TEST-TICKER", "--live"])
    assert rc == 0
    assert any("[LIVE]" in record.getMessage() for record in caplog.records), (
        "Expected at least one '[LIVE]' log line, got: "
        f"{[r.getMessage() for r in caplog.records]}"
    )
    # The promotion-gate warning must surface when --live is set, so a sleepy
    # operator gets a visible reminder.
    assert any(
        "promotion" in record.getMessage().lower() for record in caplog.records
    ), "Expected the promotion-gate warning under --live."


def test_main_missing_match_raises_systemexit() -> None:
    """main() without --match should propagate argparse's SystemExit(2)."""
    with pytest.raises(SystemExit) as excinfo:
        main([])
    assert excinfo.value.code == 2
```

## Task Commits

Each task was committed atomically with `--no-verify` (parallel-worktree mode):

1. **Task 1: src/main.py + src/__main__.py — dry-run-default CLI** — `ed6bd43` (feat)
2. **Task 2: tests/test_main.py — 10 tests locking the safety contract** — `6ba2372` (test)

**Plan metadata commit (forthcoming):** SUMMARY.md committed by the executor's final-commit step (orchestrator handles STATE.md / ROADMAP.md updates after wave merge).

## CLI smoke output

```text
$ uv run python -m src.main --match KXVALORANT-TEST
2026-04-27 16:59:24,538 INFO     __main__ :: [DRY-RUN] Bot starting :: match=KXVALORANT-TEST :: dry_run=True
2026-04-27 16:59:24,539 INFO     __main__ :: [DRY-RUN] No orders will be placed. Pass --live to trade with capital.
2026-04-27 16:59:24,539 INFO     __main__ :: [DRY-RUN] Phase 0 entry point complete (no trading logic wired yet).
EXIT: 0

$ uv run python -m src --match KXVALORANT-TEST --live
2026-04-27 16:59:26,390 INFO     src.main :: [LIVE] Bot starting :: match=KXVALORANT-TEST :: dry_run=False
2026-04-27 16:59:26,390 WARNING  src.main :: [LIVE] Live trading is enabled. Verify the paper-trade promotion gate (DEC-020) has been satisfied before proceeding in production.
2026-04-27 16:59:26,390 INFO     src.main :: [LIVE] Phase 0 entry point complete (no trading logic wired yet).
EXIT: 0

$ uv run python -m src.main      # no --match
usage: valorant-pricing-bot [-h] --match TICKER [--live]
valorant-pricing-bot: error: the following arguments are required: --match
EXIT: 2
```

Note: the `__main__` logger name in the dry-run smoke is from `python -m src.main` invocation (Python sets `__name__ = "__main__"` for the module entered with `-m`); the live smoke uses `python -m src`, which routes through `__main__.py → src.main`, so the logger is registered under its qualified module name `src.main`. Both paths log the mode banner correctly — this is just a Python `__name__` quirk, not a behavioral difference.

## pytest output (whole suite)

```text
$ uv run pytest -v
============================= test session starts =============================
platform win32 -- Python 3.11.6, pytest-9.0.3, pluggy-1.6.0
configfile: pyproject.toml
testpaths: tests
plugins: hypothesis-6.152.4, cov-7.1.0
collected 11 items

tests/test_main.py::test_dry_run_default_is_true PASSED                  [  9%]
tests/test_main.py::test_parser_requires_match PASSED                    [ 18%]
tests/test_main.py::test_parser_accepts_match_only PASSED                [ 27%]
tests/test_main.py::test_parser_accepts_match_and_live PASSED            [ 36%]
tests/test_main.py::test_live_flag_default_is_false PASSED               [ 45%]
tests/test_main.py::test_resolve_dry_run_true_when_live_absent PASSED    [ 54%]
tests/test_main.py::test_resolve_dry_run_false_when_live_passed PASSED   [ 63%]
tests/test_main.py::test_main_returns_zero_on_dry_run PASSED             [ 72%]
tests/test_main.py::test_main_returns_zero_on_live PASSED                [ 81%]
tests/test_main.py::test_main_missing_match_raises_systemexit PASSED     [ 90%]
tests/test_smoke.py::test_smoke PASSED                                   [100%]

============================= 11 passed in 0.25s ==============================
```

10 new tests in `test_main.py` + 1 sentinel from Plan 01. **Note:** Plan 02 (`tests/config/test_constants.py`) is being executed by a parallel worktree agent and will land in this branch via the orchestrator's wave merge — the union of the two worktrees' test outputs is what closes Phase 0 Wave 2. Within this worktree alone the suite is 11/11 green.

## Toolchain regression (Plan 01 contracts)

```text
$ uv run mypy --strict src/pricing/
Success: no issues found in 1 source file
EXIT: 0

$ uv run ruff check .
All checks passed!
EXIT: 0
```

Plan 01's two regression contracts (mypy strict on `src/pricing/`, ruff clean repo-wide) both pass after this plan's changes.

## Phase 4 contract (forward-looking)

This plan's public API is the contract Phase 4 quoting will plug into. When Phase 4 lands, it will:

1. **Inside `main()`**, after `dry_run = resolve_dry_run(args)`, instantiate `KalshiOrderManager(dry_run=dry_run, ...)` — passing the resolved boolean down EXPLICITLY (not from a constructor default, not from an env var).
2. **Instantiate the four kill switches** (`KILL_SWITCH_*` constants from `src/config/constants.py` — produced by Plan 02) and register them with the order manager.
3. **Start the event loop** that consumes `MatchState` from `src/state/` (Phase 1+) and emits orders through the order manager.

What MUST NOT change without updating Phase 4's plan:

- The four-symbol public API of `src.main`: `DRY_RUN_DEFAULT`, `build_arg_parser`, `resolve_dry_run`, `main`.
- The `main(argv: list[str] | None = None) -> int` signature (Phase 4 may add side effects inside, but must keep the argv-injectable signature for testability).
- The CLI surface: `--match TICKER` (required) and `--live` (store_true, no default flip).
- The fact that `--live` is the SINGLE source of truth for live/dry-run (no Phase 4 escape hatches).

CLAUDE.md "Run commands" already documents both invocations:

```bash
python -m src.main --match <ticker>            # dry-run (default)
python -m src.main --match <ticker> --live     # only after paper-trade gate
```

This plan satisfies that documented contract.

## Decisions Made

- **`resolve_dry_run` reads `args.live` directly** — argparse `store_true` always sets the attribute, so `getattr(args, "live", False)` would be defensive paranoia. Avoiding it is consistent with CLAUDE.md "terse" + "no enterprise patterns" preference.
- **Logging is `basicConfig`-gated** — `if not logging.getLogger().handlers:` ensures the test harness's root-logger (or any future library-mode caller) does not get its config stomped. caplog's per-test handler still picks up records because we attach to the named logger `src.main`.
- **Both `python -m src.main` and `python -m src` supported** — CLAUDE.md "Run commands" documents the former; `__main__.py` adds the latter for ergonomic parity with stdlib (`python -m http.server`, `python -m venv`). Both routes hit the same `main()` so there is no behavioral split.
- **Promotion-gate warning emitted at `WARNING` level under `--live`** — INFO would be visually drowned by routine startup chatter; WARNING ensures the DEC-020 reminder surfaces in the operator's eyeline before any order is placed (the warning is the operator's last visual checkpoint between dev and prod).
- **`from __future__ import annotations` in main.py** — keeps the `list[str] | None` type hint valid even though Python 3.11 supports it natively. Consistency with Plan 01's `src/__init__.py` style; cheap insurance against a future Python-version downshift.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Lint] ruff import-block ordering on tests/test_main.py**
- **Found during:** Task 2 verify step (`uv run ruff check tests/test_main.py`).
- **Issue:** Ruff's isort rules (rule `I001`) wanted no blank line between the `# --- DRY_RUN_DEFAULT ---` comment block and the trailing line of the import block above. The plan's exact test source had a blank line there.
- **Fix:** `uv run ruff check --fix tests/test_main.py` — autofix removed one blank line.
- **Files modified:** `tests/test_main.py` (1-line whitespace change).
- **Verification:** `ruff check tests/test_main.py` exits 0; all 10 tests still pass after the fix.
- **Committed in:** `6ba2372` (Task 2 commit; the autofixed file was committed directly — no separate fix commit).

**Total deviations:** 1 auto-fixed (Rule 1 lint formatting). 0 architectural changes — no Rule 4 checkpoint needed.
**Impact on plan:** Cosmetic. The test file's logical structure and all assertions are identical to the plan; only one blank line of whitespace was removed.

## Issues Encountered

**Worktree base reset (pre-Task 1).** The worktree was created from `b7b6db6` (the project bootstrap commit), but the orchestrator required base `84a07f0` (post-Plan-01 HEAD). Per the worktree-branch-check protocol, ran `git reset --hard 84a07f0` before any work. Confirmed via `git rev-parse HEAD`. No data loss (fresh worktree, no user changes).

## User Setup Required

None.

## Next Phase Readiness

- Phase 0 Wave 2 closure is gated on the parallel worktree (Plan 00-02 — domain constants) completing. After both worktrees merge, Phase 0 is done and Phases 1, 2, 3 unblock for parallel planning.
- Phase 4 will plug into the public API documented above; nothing further is required from this plan.
- No blockers.

## Self-Check: PASSED

- `src/main.py` exists (179 lines).
- `src/__main__.py` exists (10 lines).
- `tests/test_main.py` exists (124 lines after ruff autofix).
- `DRY_RUN_DEFAULT: Final[bool] = True` present in src/main.py (verified by `grep`).
- `build_arg_parser`, `resolve_dry_run`, `main` all defined (verified by `grep`).
- `if args.live:` present; `getattr(args` absent (verified by `grep` + `! grep`).
- `from src.main import main` present in src/__main__.py.
- Public API import smoke: `python -c "from src.main import DRY_RUN_DEFAULT, build_arg_parser, resolve_dry_run, main; assert DRY_RUN_DEFAULT is True"` exits 0.
- CLI smoke: `python -m src.main --match TEST` logs `[DRY-RUN]`, exits 0.
- CLI smoke: `python -m src --match TEST --live` logs `[LIVE]` + promotion-gate warning, exits 0.
- CLI smoke: `python -m src.main` (no --match) exits 2.
- `uv run pytest -v` → 11 passed (10 test_main + 1 test_smoke).
- `uv run mypy --strict src/pricing/` → 0 issues.
- `uv run ruff check .` → all checks passed.
- Commit `ed6bd43` (feat: src/main.py + src/__main__.py) exists on branch.
- Commit `6ba2372` (test: tests/test_main.py) exists on branch.

```text
$ git log --oneline -5
6ba2372 test(00-03): add tests for dry-run-default entry point
ed6bd43 feat(00-03): add dry-run-default CLI entry point
84a07f0 docs(00-01): complete project-structure-and-tooling plan
83b00b0 feat(00-01): convert src/* to real Python packages + pytest sentinel
91a6419 chore(00-01): bootstrap pyproject.toml + uv toolchain (Python 3.11)
```

---
*Phase: 00-foundation*
*Plan: 03-dry-run-default-entry-point*
*Completed: 2026-04-27*
