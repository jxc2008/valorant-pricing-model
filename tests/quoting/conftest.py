"""Phase 04 quoting/sizing shared fixtures.

Used by every tests/quoting/test_*.py and tests/sizing/test_*.py per
.planning/phases/04-quoting-layer/04-VALIDATION.md.

Re-exports `make_match_state` from tests/ingestion/conftest.py so quoting
tests can build MatchState instances without depending on the ingestion
package layout. Adds Phase 04-specific fixtures: make_market_quote,
fake_private_key, fake_kalshi_session, tmp_fill_ledger_dir.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

# Re-export Phase 03 fixture so quoting tests can build MatchState instances.
from tests.ingestion.conftest import make_match_state  # noqa: F401  (pytest fixture re-export)


@dataclass(frozen=True, slots=True)
class _StubMarketQuote:
    """Stand-in MarketQuote shape for use BEFORE plan 04-01 ships the real
    dataclass at src/quoting/market_data.py. Plans 04-04 onwards will swap
    this for the real import."""

    yes_bid: int       # cents 1-99
    yes_ask: int
    mid: int
    spread: int        # = yes_ask - yes_bid
    is_valid: bool = True


@pytest.fixture
def make_market_quote() -> Callable[..., _StubMarketQuote]:
    """Build a stand-in MarketQuote with sensible defaults; tests pass kwargs to override."""

    def _make(**overrides: Any) -> _StubMarketQuote:
        base: dict[str, Any] = {
            "yes_bid": 48,
            "yes_ask": 52,
            "mid": 50,
            "spread": 4,
            "is_valid": True,
        }
        base.update(overrides)
        return _StubMarketQuote(**base)

    return _make


@pytest.fixture
def fake_private_key() -> Any:
    """Fresh RSA key for auth-signing tests. Standard 2048-bit per Kalshi docs."""
    from cryptography.hazmat.primitives.asymmetric import rsa

    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def tmp_fill_ledger_dir(tmp_path: Path) -> Path:
    """Per-test hypothetical-fill ledger dir; mirrors data/fills/ layout."""
    d = tmp_path / "fills"
    d.mkdir(parents=True, exist_ok=True)
    return d


@pytest.fixture
def fake_kalshi_session() -> Any:
    """aioresponses-mocked aiohttp ClientSession for Kalshi REST tests.

    Usage:
        async def test_x(fake_kalshi_session):
            with fake_kalshi_session as m:
                m.post("https://api.elections.kalshi.com/trade-api/v2/portfolio/orders",
                       status=201, payload={"order": {"order_id": "abc"}})
                ...
    """
    from aioresponses import aioresponses

    return aioresponses()
