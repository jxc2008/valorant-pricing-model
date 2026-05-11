"""Plan 04-01 — REQ-order-lifecycle-reconciliation RED-stub tests.

Periodic reconcile: cancel orphans (Kalshi has, we don't), drop ghosts (we
have, Kalshi doesn't). Dry-run is a no-op. Signing path stays canonical
(no query string — Pitfall 1 re-asserted at the reconcile site).

Source: PRD §5.3 / REQ-order-lifecycle-reconciliation / Pitfall 1.
"""
from __future__ import annotations

import pytest


def test_cancel_orphans(fake_kalshi_session) -> None:
    """Kalshi reports an open order our local _active_quotes doesn't know about
    — reconciler issues cancel for that order_id."""
    pytest.xfail("Plan 04-01 — src/quoting/order_manager.py not yet implemented")


def test_drop_ghosts(fake_kalshi_session) -> None:
    """We hold a local quote that Kalshi has no record of — reconciler drops
    the local entry (Kalshi is the source of truth for fills)."""
    pytest.xfail("Plan 04-01 — src/quoting/order_manager.py not yet implemented")


def test_dry_run_noop(fake_kalshi_session) -> None:
    """reconcile_once returns early in dry-run mode without touching Kalshi."""
    pytest.xfail("Plan 04-01 — src/quoting/order_manager.py not yet implemented")


def test_signs_path_without_query(fake_private_key) -> None:
    """Pitfall 1 re-asserted: reconcile's GET /portfolio/orders signs the path
    without the ?cursor=...&limit=... query string."""
    pytest.xfail("Plan 04-01 — src/quoting/order_manager.py not yet implemented")
