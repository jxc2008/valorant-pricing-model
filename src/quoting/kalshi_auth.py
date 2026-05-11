"""Kalshi RSA-PSS request signing (REQ-kalshi-order-manager).

Verified directly against docs.kalshi.com/getting_started/api_keys
(2026-05-09). RSA-PSS with MGF1(SHA256) and salt_length=DIGEST_LENGTH.

NOT PKCS1v15 — CLAUDE.md was previously WRONG on this point and is
corrected in the same commit that ships this module (RESEARCH Pitfall 2).

The path argument MUST NOT include query parameters; signing the URL
with a query string returns 401 (RESEARCH Pitfall 1 — the most common
Kalshi auth bug). The defensive ``assert "?" not in path`` is the
primary guardrail.
"""
from __future__ import annotations

import base64
import time
from pathlib import Path
from typing import Final

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa


_PSS_PADDING: Final = padding.PSS(
    mgf=padding.MGF1(hashes.SHA256()),
    salt_length=padding.PSS.DIGEST_LENGTH,
)
"""RSA-PSS padding configuration; verified against Kalshi docs 2026-05-09."""


def load_private_key(pem_path: str | Path) -> rsa.RSAPrivateKey:
    """Load a PKCS#8 RSA private key from a PEM file with no password.

    Source: docs.kalshi.com/getting_started/api_keys "Generate API keys"
    — Kalshi exports the key as a PEM-formatted PKCS#8 file by default.
    """
    with open(pem_path, "rb") as f:
        key = serialization.load_pem_private_key(f.read(), password=None)
    if not isinstance(key, rsa.RSAPrivateKey):
        raise TypeError(f"Expected RSAPrivateKey, got {type(key).__name__}")
    return key


def sign_request(
    key_id: str,
    private_key: rsa.RSAPrivateKey,
    method: str,
    path: str,
) -> dict[str, str]:
    """Return the 3 KALSHI-ACCESS-* headers for a Kalshi REST/WS request.

    Args:
        key_id: KALSHI-ACCESS-KEY value (operator's key UUID).
        private_key: rsa.RSAPrivateKey loaded via load_private_key.
        method: "GET" | "POST" | "DELETE".
        path: URL path component WITHOUT query parameters
              (e.g. "/trade-api/v2/portfolio/orders"). The defensive
              assert below catches the most common Kalshi auth bug
              (RESEARCH Pitfall 1).
    """
    assert "?" not in path, "Sign path WITHOUT query parameters (Kalshi auth pitfall #1)"
    timestamp_ms = str(int(time.time() * 1000))
    message = (timestamp_ms + method + path).encode("utf-8")
    signature = private_key.sign(message, _PSS_PADDING, hashes.SHA256())
    return {
        "KALSHI-ACCESS-KEY": key_id,
        "KALSHI-ACCESS-SIGNATURE": base64.b64encode(signature).decode("ascii"),
        "KALSHI-ACCESS-TIMESTAMP": timestamp_ms,
    }
