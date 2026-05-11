"""Phase 4 quoting layer — Kalshi order plumbing + mode-aware quoters.

Public surface populated incrementally across plans 04-01 (auth +
order manager + market data) through 04-08 (reconciliation + E2E).
"""
from src.quoting.kalshi_auth import load_private_key, sign_request

__all__ = ["load_private_key", "sign_request"]
