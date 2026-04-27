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
