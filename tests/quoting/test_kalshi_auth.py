"""Plan 04-01 — REQ-kalshi-order-manager auth tests (RSA-PSS verified).

Three header tuple (KALSHI-ACCESS-KEY, KALSHI-ACCESS-TIMESTAMP,
KALSHI-ACCESS-SIGNATURE) produced by sign_request(key_id, private_key,
method, path). PSS padding (NOT PKCS1v15 — Pitfall 2); path argument MUST
NOT contain a query string (Pitfall 1).

Source: PRD §5.3 / Plan 04-01 / RESEARCH §"Pattern 1" / Pitfalls 1, 2.
"""
from __future__ import annotations

import base64
import time

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding

from src.quoting.kalshi_auth import sign_request


def test_sign_request_returns_three_headers(fake_private_key) -> None:
    headers = sign_request("KEY-UUID", fake_private_key, "GET", "/trade-api/v2/exchange/status")
    assert set(headers.keys()) == {
        "KALSHI-ACCESS-KEY",
        "KALSHI-ACCESS-SIGNATURE",
        "KALSHI-ACCESS-TIMESTAMP",
    }
    assert headers["KALSHI-ACCESS-KEY"] == "KEY-UUID"
    # Signature must base64-decode to 256 bytes (2048-bit RSA).
    sig = base64.b64decode(headers["KALSHI-ACCESS-SIGNATURE"])
    assert len(sig) == 256


def test_sign_request_rejects_query_string_path(fake_private_key) -> None:
    """Pitfall 1: signing must be applied to the canonical path WITHOUT query
    string; defensive assert that callers passing `/foo?bar=1` raise AssertionError."""
    with pytest.raises(AssertionError, match="WITHOUT query parameters"):
        sign_request("KEY", fake_private_key, "GET", "/foo?bar=1")


def test_sign_request_uses_pss_padding(fake_private_key) -> None:
    """Pitfall 2: signature MUST verify under PSS, not PKCS1v15. If PKCS1v15
    were used, the verify call below would raise InvalidSignature."""
    headers = sign_request("K", fake_private_key, "GET", "/trade-api/v2/exchange/status")
    ts = headers["KALSHI-ACCESS-TIMESTAMP"]
    sig = base64.b64decode(headers["KALSHI-ACCESS-SIGNATURE"])
    message = (ts + "GET" + "/trade-api/v2/exchange/status").encode("utf-8")
    # If PKCS1v15 were used, this verify call raises InvalidSignature.
    fake_private_key.public_key().verify(
        sig,
        message,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
        hashes.SHA256(),
    )


def test_sign_request_timestamp_is_recent(fake_private_key) -> None:
    before = int(time.time() * 1000)
    headers = sign_request("K", fake_private_key, "GET", "/x")
    after = int(time.time() * 1000)
    ts = int(headers["KALSHI-ACCESS-TIMESTAMP"])
    assert before <= ts <= after + 10
