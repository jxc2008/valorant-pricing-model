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
