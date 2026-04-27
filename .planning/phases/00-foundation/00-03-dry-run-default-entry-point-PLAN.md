---
phase: 00-foundation
plan: 03
type: execute
wave: 2
depends_on: [01]
files_modified:
  - src/main.py
  - src/__main__.py
  - tests/test_main.py
autonomous: true
requirements: []
must_haves:
  truths:
    - "DEC-022 / CON-dry-run-default — bot stays in `dry_run=True` unless `--live` is passed at the CLI"
    - "DEC-022 — `--live` is the SINGLE switch that flips the safety; no constructor argument, no env var, no config-file override"
    - "CLAUDE.md rule 13 — dry-run is enforced via CLI flag, not constructor arg (CONVENTIONS.md anti-pattern #7)"
    - "Entry point is reachable as both `python -m src.main` (CLAUDE.md 'Run commands' line 1) and `python -m src` (alternate via `__main__.py`)"
    - "Entry point logs the active mode (`DRY-RUN` vs `LIVE`) clearly so an operator sees safety state at first glance (CONVENTIONS.md Logging — `[DRY-RUN]` prefix convention)"
    - "Entry point performs NO actual trading logic in Phase 0 — it parses `--match` + `--live`, prints/logs which mode it's in, and exits 0. Trading wiring lives in Phase 4."
  artifacts:
    - path: "src/main.py"
      provides: "CLI entry point — argparse for `--match <ticker>` + `--live`; resolves dry-run state; logs mode; main() returns int exit-code for testability"
      exports:
        - "DRY_RUN_DEFAULT"
        - "build_arg_parser"
        - "resolve_dry_run"
        - "main"
      contains: "DRY_RUN_DEFAULT: Final[bool] = True; main(argv: list[str] | None = None) -> int signature"
    - path: "src/__main__.py"
      provides: "Allows `python -m src` to dispatch to `src.main:main`"
      contains: "from src.main import main; raise SystemExit(main())"
    - path: "tests/test_main.py"
      provides: "Tests asserting dry-run-default behavior + --live flip + --match parsing"
      contains: "test_default_is_dry_run, test_live_flag_disables_dry_run, test_match_required, test_main_exits_zero_on_dry_run"
  key_links:
    - from: "src/main.py argparse"
      to: "DRY_RUN_DEFAULT"
      via: "store_true action on --live defaults dry_run to True; resolve_dry_run inverts the flag"
      pattern: "store_true"
    - from: "src/__main__.py"
      to: "src.main.main"
      via: "import + SystemExit dispatch"
      pattern: "from src.main import main"
    - from: "tests/test_main.py"
      to: "src.main"
      via: "imports build_arg_parser + resolve_dry_run + main; calls main with synthetic argv lists"
      pattern: "from src.main import"
---

<objective>
Create the CLI entry point with the dry-run-default safety enforcement: `src/main.py` parses `--match <ticker>` and `--live`, the bot stays in `dry_run=True` unless `--live` is explicitly passed, and the Phase 0 implementation only logs which mode it is in (no trading logic — that's Phase 4). Add `tests/test_main.py` proving the safety default holds.

Purpose: Locks in CLAUDE.md rule 13 / DEC-022 / CON-dry-run-default at the entry point BEFORE any trading code exists. Phase 4 will wire actual quoting through the dry-run boolean that this entry point computes; if the safety default is wrong here, every downstream phase inherits the bug. CONVENTIONS.md anti-pattern #7 ("`dry_run` as a constructor argument") is explicitly avoided by making the CLI flag the single source of truth.

Output: `python -m src.main --match KXVALORANT-25APR27-FNCxNAVI-1` runs in dry-run mode and prints/logs `[DRY-RUN]` mode banner. Adding `--live` flips to LIVE and logs `[LIVE]`. Tests prove the flip works in both directions.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/intel/constraints.md
@.planning/intel/decisions.md
@.planning/codebase/CONVENTIONS.md
@.planning/codebase/STRUCTURE.md
@CLAUDE.md
@roadmap.md
@.planning/phases/00-foundation/00-01-SUMMARY.md

<interfaces>
<!-- This plan defines the CLI contract that Phase 4 quoting will plug into.
     Phase 4 will import `from src.main import resolve_dry_run` (or pass the bool
     down from main()) — do NOT change the signatures listed below without
     updating Phase 4's plan. -->

CLI surface contract:
```
$ python -m src.main --match <kalshi_ticker>           # dry-run (default)
$ python -m src.main --match <kalshi_ticker> --live    # live trading
$ python -m src                                        # equivalent dispatch
```

Public Python API (from `src.main`):
```python
DRY_RUN_DEFAULT: Final[bool] = True

def build_arg_parser() -> argparse.ArgumentParser: ...
def resolve_dry_run(args: argparse.Namespace) -> bool: ...
def main(argv: list[str] | None = None) -> int: ...
```

Behavior contract:
- `build_arg_parser()` registers `--match` (required, str) and `--live` (store_true, default False).
- `resolve_dry_run(args)` returns `True` UNLESS `args.live` is explicitly truthy.
- `main(argv)` parses argv (defaulting to sys.argv[1:]), resolves dry_run, logs the mode, returns 0.
- Phase 0 main() does NO trading. Phase 4 will fan out from main() into KalshiOrderManager + the four kill switches.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Write src/main.py + src/__main__.py implementing dry-run-default CLI</name>
  <files>src/main.py, src/__main__.py</files>
  <read_first>
    - CLAUDE.md (Critical rules #13 — "Dry-run by default. Live trading requires explicit --live flag at the entry point."; "Run commands" block — `python -m src.main --match <ticker>` is the canonical invocation)
    - .planning/intel/constraints.md (CON-dry-run-default)
    - .planning/intel/decisions.md (DEC-022 — full text on dry-run safety; DEC-013 — note that audited `market_maker.py` uses `dry_run` as constructor arg, which we are explicitly NOT replicating)
    - .planning/codebase/CONVENTIONS.md (Anti-Patterns #7 — `dry_run` as constructor argument is forbidden; Logging — `[DRY-RUN]` prefix convention from reference/market_maker.py:218)
    - .planning/codebase/STRUCTURE.md (Entry Points (Planned) — `src/main.py`)
    - prd.md §13 (deployment context, for understanding why safety matters)
  </read_first>
  <action>
**Step A — Create `src/main.py`** with the following EXACT content (preserve every comment, every docstring, every blank line):

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

**Step B — Create `src/__main__.py`** to make `python -m src` work as an alternate dispatch:
```python
"""Allow ``python -m src`` to dispatch to ``src.main:main``."""

from __future__ import annotations

import sys

from src.main import main

if __name__ == "__main__":
    sys.exit(main())
```

Notes for the executor:
- Use the Write tool. Do not use heredoc.
- The `from __future__ import annotations` is required for the `list[str] | None` type hint to be valid under any Python 3.9+ (3.11 supports it natively but the import keeps the file consistent with the rest of `src/`).
- `argparse.Namespace.live` is read directly as `args.live` — argparse `store_true` always sets the attribute to `True`/`False`, so defensive `getattr` is unnecessary (and would conflict with CLAUDE.md "terse, no enterprise patterns" preference).
- The two `if __name__ == "__main__":` blocks (one in main.py, one in __main__.py) are intentional — both are valid invocation paths per CLAUDE.md "Run commands" and we want both to work identically.
- After writing, run the smoke commands:
  - `uv run python -m src.main --match KXVALORANT-TEST` should log a line containing `[DRY-RUN]`.
  - `uv run python -m src --match KXVALORANT-TEST --live` should log a line containing `[LIVE]` plus the warning about the promotion gate.
- Run `uv run mypy --strict src/pricing/` (regression — must still exit 0; the `__future__` import in main.py shouldn't affect this since main.py is in src/, not src/pricing/, but check).
- Note that `src/main.py` is NOT under the `[tool.mypy.overrides]` strict-on-`src.pricing.*` rule — it falls under the gradual-typing default. Still annotate fully (per CONVENTIONS.md type-hints reference style) but mypy will not error if a downstream change drops an annotation.
  </action>
  <verify>
    <automated>test -f src/main.py &amp;&amp; test -f src/__main__.py &amp;&amp; grep -q 'DRY_RUN_DEFAULT: Final\[bool\] = True' src/main.py &amp;&amp; grep -q 'def build_arg_parser' src/main.py &amp;&amp; grep -q 'def resolve_dry_run' src/main.py &amp;&amp; grep -q 'def main' src/main.py &amp;&amp; grep -q '"--live"' src/main.py &amp;&amp; grep -q 'action="store_true"' src/main.py &amp;&amp; grep -q 'if args.live:' src/main.py &amp;&amp; ! grep -q 'getattr(args' src/main.py &amp;&amp; grep -q 'from src.main import main' src/__main__.py &amp;&amp; uv run python -m src.main --match TEST-TICKER 2>&amp;1 | grep -q DRY-RUN &amp;&amp; uv run python -m src --match TEST-TICKER --live 2>&amp;1 | grep -q LIVE &amp;&amp; uv run mypy --strict src/pricing/ &amp;&amp; uv run ruff check src/main.py src/__main__.py</automated>
  </verify>
  <done>
    `src/main.py` exports `DRY_RUN_DEFAULT: Final[bool] = True`, `build_arg_parser`, `resolve_dry_run`, and `main(argv) -> int` with the EXACT signatures from the action block. `resolve_dry_run` reads `args.live` directly (no defensive `getattr`). `src/__main__.py` dispatches to `src.main:main`. CLI smoke tests log `[DRY-RUN]` without `--live` and `[LIVE]` with `--live`. `mypy --strict src/pricing/` regression passes. `ruff check src/main.py src/__main__.py` exits 0.
  </done>
</task>

<task type="auto">
  <name>Task 2: Write tests/test_main.py asserting dry-run-default + --live flip + --match required</name>
  <files>tests/test_main.py</files>
  <read_first>
    - src/main.py (just-created file — signatures and behavior)
    - .planning/intel/decisions.md (DEC-022 — the safety contract this test enforces)
    - tests/__init__.py (confirm package marker exists from Plan 01)
  </read_first>
  <action>
Use the Write tool to create `tests/test_main.py` with the following EXACT content:

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

Notes for the executor:
- Use the Write tool. Do not use heredoc.
- The `caplog` fixture is built in to pytest; no plugin needed.
- The `caplog.at_level(logging.INFO, logger="src.main")` scope ensures we capture records emitted by `src.main`'s module logger even though the global level may differ.
- After writing, run `uv run pytest tests/test_main.py -v` and confirm ALL ~10 tests pass.
- Also run `uv run pytest -v` (whole suite) to confirm Plan 02's `tests/config/test_constants.py` still passes.
- Run `uv run ruff check tests/test_main.py` (must exit 0).
- The test file deliberately does NOT mock `argparse` or stub `sys.argv` — passing `argv` explicitly to `main()` and `parse_args(argv)` keeps tests pure and avoids global-state pollution.
  </action>
  <verify>
    <automated>test -f tests/test_main.py &amp;&amp; uv run pytest tests/test_main.py -v &amp;&amp; uv run pytest -v &amp;&amp; uv run ruff check tests/test_main.py</automated>
  </verify>
  <done>
    `tests/test_main.py` contains ~10 tests covering: DRY_RUN_DEFAULT constant value; argparse rejection of missing --match; argparse accepts --match alone (dry-run); argparse accepts --match + --live (live); resolve_dry_run inverts --live correctly in both directions; main() returns 0 + logs [DRY-RUN] without --live; main() returns 0 + logs [LIVE] + promotion warning with --live; main() raises SystemExit(2) on missing --match. All tests pass under `uv run pytest`. Whole-repo `uv run pytest -v` (including Plan 02 tests) passes. `uv run ruff check tests/test_main.py` exits 0.
  </done>
</task>

</tasks>

<verification>
After both tasks complete, the following must hold:

```bash
# Files exist
test -f src/main.py
test -f src/__main__.py
test -f tests/test_main.py

# Module exposes the contracted public API
uv run python -c "from src.main import DRY_RUN_DEFAULT, build_arg_parser, resolve_dry_run, main; assert DRY_RUN_DEFAULT is True; print('ok')"

# resolve_dry_run uses args.live directly (no defensive getattr)
grep -q 'if args.live:' src/main.py
! grep -q 'getattr(args' src/main.py

# CLI smoke: dry-run path
uv run python -m src.main --match TEST 2>&1 | grep -q DRY-RUN

# CLI smoke: live path (must show LIVE banner + promotion warning)
uv run python -m src --match TEST --live 2>&1 | grep -q LIVE

# Missing --match must exit non-zero
uv run python -m src.main; test $? -ne 0

# Tests
uv run pytest -v       # all tests across plans 02 + 03 must pass

# Toolchain (regression)
uv run mypy --strict src/pricing/    # exit 0
uv run ruff check .                  # exit 0
```
</verification>

<success_criteria>
1. `src/main.py` exposes the four-symbol public API (`DRY_RUN_DEFAULT`, `build_arg_parser`, `resolve_dry_run`, `main`) with the exact signatures listed in the interfaces block.
2. `DRY_RUN_DEFAULT` is `True` and is the single source of truth for the dry-run/live distinction (no constructor argument, no env var, no config file).
3. `resolve_dry_run` reads `args.live` directly (not `getattr(args, "live", False)`) — argparse `store_true` always sets the attribute, so defensive access is unnecessary per CLAUDE.md "terse" preference.
4. `python -m src.main --match TICKER` runs in dry-run mode and logs `[DRY-RUN]`.
5. `python -m src --match TICKER --live` runs in live mode and logs `[LIVE]` plus the promotion-gate warning.
6. Missing `--match` causes argparse to exit non-zero (code 2) — `--match` is genuinely required.
7. `tests/test_main.py` proves all of the above; `uv run pytest -v` is fully green across the whole repo (Plan 02 tests + Plan 03 tests).
8. `uv run mypy --strict src/pricing/` regression passes (no impact from main.py since it's outside the strict override).
9. `uv run ruff check .` regression passes.
</success_criteria>

<output>
After completion, create `.planning/phases/00-foundation/00-03-SUMMARY.md` covering:
- Full final contents of `src/main.py` and `src/__main__.py`.
- Full final contents of `tests/test_main.py`.
- pytest output for `tests/test_main.py` and the whole suite.
- CLI smoke output for both `--match TICKER` (dry-run) and `--match TICKER --live` (live).
- Confirmation that the public API (`DRY_RUN_DEFAULT`, `build_arg_parser`, `resolve_dry_run`, `main`) is the contract Phase 4 will plug into; document what Phase 4 will need to add (KalshiOrderManager construction, kill-switch instantiation, event loop) and where it will get the `dry_run` boolean (from `resolve_dry_run` called inside `main()`).
- Note that CLAUDE.md "Run commands" section already documents `python -m src.main --match <ticker>` and `--live` — this plan satisfies the documented contract.
</output>
</output>
