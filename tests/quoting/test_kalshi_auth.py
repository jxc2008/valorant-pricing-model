"""Plan 04-01 — REQ-kalshi-order-manager RSA-PSS auth RED-stub tests.

Three header tuple (KALSHI-ACCESS-KEY, KALSHI-ACCESS-TIMESTAMP,
KALSHI-ACCESS-SIGNATURE) produced by sign_request(method, path, ts, key_id,
private_key). PSS padding (NOT PKCS1v15 — Pitfall 2); path argument MUST NOT
contain a query string (Pitfall 1).

Source: PRD §5.3 / Plan 04-01 / RESEARCH §"Pattern 1" / Pitfalls 1, 2.
"""
from __future__ import annotations

import pytest


def test_sign_request_returns_three_headers(fake_private_key) -> None:
    pytest.xfail("Plan 04-01 — src/quoting/kalshi_auth.py not yet implemented")


def test_sign_request_rejects_query_string_path(fake_private_key) -> None:
    """Pitfall 1: signing must be applied to the canonical path WITHOUT query
    string; defensive assert that callers passing `/foo?bar=1` raise ValueError."""
    pytest.xfail("Plan 04-01 — src/quoting/kalshi_auth.py not yet implemented")


def test_sign_request_uses_pss_padding(fake_private_key) -> None:
    """Pitfall 2: signature must be RSA-PSS (not PKCS1v15); Kalshi verify-path
    rejects PKCS1v15 with 401."""
    pytest.xfail("Plan 04-01 — src/quoting/kalshi_auth.py not yet implemented")
