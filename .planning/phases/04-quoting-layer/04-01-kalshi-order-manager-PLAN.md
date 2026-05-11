---
phase: 04-quoting-layer
plan: "01"
type: execute
wave: 2
depends_on: ["00"]
files_modified:
  - src/quoting/kalshi_auth.py
  - src/quoting/order_manager.py
  - src/quoting/market_data.py
  - src/quoting/__init__.py
  - tests/quoting/test_kalshi_auth.py
  - tests/quoting/test_order_manager.py
  - tests/quoting/test_market_data.py
  - scripts/kalshi_auth_smoke.py
  - CLAUDE.md
autonomous: true
requirements:
  - REQ-kalshi-order-manager
notes: |
  Wave 2 — KalshiOrderManager skeleton + RSA-PSS auth + MarketDataSource Protocol.

  CRITICAL — atomic CLAUDE.md correction. CLAUDE.md line referencing "RSA
  PKCS1v15/SHA-256 auth" is WRONG (RESEARCH Pitfall 2 — verified directly
  against docs.kalshi.com 2026-05-09). The auth code in this plan implements
  RSA-PSS with MGF1(SHA256) and salt_length=PSS.DIGEST_LENGTH. Per the
  quality_gate from the planner brief, the same commit that ships
  src/quoting/kalshi_auth.py MUST also patch CLAUDE.md to remove the
  PKCS1v15 reference. Splitting the correction across commits leaves a
  contradicting authoritative project doc on disk.

  CRITICAL — operator gate 2 (Kalshi auth smoke test). This plan ships
  scripts/kalshi_auth_smoke.py — a no-`--live` script that signs a GET
  /trade-api/v2/exchange/status call (public + signed) and asserts 200.
  Per RESEARCH Pitfall 8, dry-run shortcuts ALL Kalshi calls in production
  code; the auth signing path never runs in dev unless the operator
  explicitly invokes the smoke test. The script is OPERATOR-GATED — execution
  requires a populated `.env` (KALSHI_KEY_ID + KALSHI_KEY_PATH) which doesn't
  exist in dev. The plan does NOT block on operator running it; the smoke
  test is documented in CLAUDE.md "Run commands" so the operator runs it
  once after first checkout to verify their `.env` works.

  Skip the official kalshi-python==2.1.4 SDK per RESEARCH §"Don't Hand-Roll".
  Auto-generated OpenAPI client is bloated (~50 endpoints; ~3MB) and breaks
  mypy --strict. Hand-roll the ~50-line signer instead.

  MarketDataSource Protocol (RESEARCH §"Open Questions" #3): two
  implementations land here — KalshiWsMarketData (live; uses websockets>=12)
  and SyntheticMarketData (default for dry-run; tests + dev). The Protocol
  surface lets plan 04-04 (mode-selector) consume MarketQuote without
  knowing which backend supplies it.

must_haves:
  truths:
    - "src/quoting/kalshi_auth.sign_request(key_id, private_key, method, path) returns 3 KALSHI-ACCESS-* headers"
    - "sign_request defensively asserts '?' not in path (RESEARCH Pitfall 1)"
    - "sign_request uses padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH) — NOT PKCS1v15"
    - "KalshiOrderManager.place_quote in dry_run=True records DRY_<uuid8> order_id without network calls"
    - "KalshiOrderManager.cancel_all_orders in dry_run clears _active_quotes"
    - "MarketQuote dataclass exposes yes_bid, yes_ask, mid, spread, is_valid (frozen + slots)"
    - "SyntheticMarketData implementation lets quoter tests run without WS connection"
    - "scripts/kalshi_auth_smoke.py exits 0 with valid .env or prints clear error if KALSHI_KEY_PATH missing"
    - "CLAUDE.md no longer claims 'RSA PKCS1v15/SHA-256' — replaced with 'RSA-PSS / SHA-256'"
  artifacts:
    - path: "src/quoting/kalshi_auth.py"
      provides: "RSA-PSS signer (~50 lines): load_private_key + sign_request"
      min_lines: 40
      contains: "padding.PSS"
    - path: "src/quoting/order_manager.py"
      provides: "Quote dataclass + KalshiOrderManager (place/cancel/cancel_all + dry_run wrapper + _error_streak)"
      min_lines: 150
      contains: "class KalshiOrderManager"
    - path: "src/quoting/market_data.py"
      provides: "MarketQuote dataclass + MarketDataSource Protocol + SyntheticMarketData + KalshiWsMarketData skeletons"
      min_lines: 80
      contains: "class MarketQuote"
    - path: "scripts/kalshi_auth_smoke.py"
      provides: "Operator-run smoke test that signs GET /exchange/status and asserts 200"
      contains: "exchange/status"
    - path: "CLAUDE.md"
      provides: "RSA-PSS auth scheme correction"
      contains: "RSA-PSS"
  key_links:
    - from: "src/quoting/order_manager.py KalshiOrderManager.place_quote"
      to: "src/quoting/kalshi_auth.sign_request"
      via: "import + call in live path"
      pattern: "from src.quoting.kalshi_auth import sign_request"
    - from: "src/quoting/order_manager.py KalshiOrderManager.__init__"
      to: "dry_run argument from src.main.resolve_dry_run (CLAUDE.md rule 13)"
      via: "explicit constructor arg, NO module-attribute default"
      pattern: "dry_run: bool"
    - from: "src/quoting/market_data.py MarketDataSource Protocol"
      to: "future plan 04-04 mode-selector + 04-05/04-06/04-07 quoters"
      via: "Protocol definition (DEC-013-style structural typing)"
      pattern: "Protocol"
---

<objective>
Build the Kalshi REST + WS plumbing layer that all four mode quoters/takers
will sit on top of: RSA-PSS auth (~50-line signer), KalshiOrderManager
(place / cancel / cancel_all + dry-run wrapper + error-streak retry counter),
MarketQuote dataclass, and the MarketDataSource Protocol with two
implementations (SyntheticMarketData for dry-run/tests, KalshiWsMarketData
skeleton for live). Atomically corrects CLAUDE.md's stale "PKCS1v15" claim.

Purpose: REQ-kalshi-order-manager — single async-aware order plumbing layer
that all four modes share. Single source of truth for the dry-run wrapper
(DEC-022). Single source of truth for sign path-without-query (RESEARCH
Pitfall 1) so mode-specific quoters don't re-implement and re-bug it.

Output: 4 new src/quoting/ modules + 1 operator script + CLAUDE.md correction
+ GREEN-flipped RED stubs for test_kalshi_auth.py / test_order_manager.py /
test_market_data.py.
</objective>

<execution_context>
@C:/Users/Joseph Cheng/.claude/get-shit-done/workflows/execute-plan.md
@C:/Users/Joseph Cheng/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/04-quoting-layer/04-RESEARCH.md
@.planning/phases/04-quoting-layer/04-VALIDATION.md
@CLAUDE.md
@reference/market_maker.py
@src/config/constants.py
@src/state/match_state.py

<interfaces>
<!-- Phase 03 contracts -->
From src/state/match_state.py:
```python
@dataclass(frozen=True, slots=True)
class MatchState: ...  # 19-field shape; KalshiOrderManager doesn't import this directly
```

From src/config/constants.py (Phase 04 additions from plan 04-00):
```python
KALSHI_BASE_URL: Final[str] = "https://api.elections.kalshi.com/trade-api/v2"
KALSHI_WS_URL: Final[str] = "wss://api.elections.kalshi.com/trade-api/ws/v2"
```

From reference/market_maker.py (SALVAGE STRUCTURALLY ONLY — DEC-013):
```python
@dataclass
class Quote:
    ticker: str
    side: str          # 'yes'|'no'
    action: str        # 'buy'|'sell'
    price: int         # cents 1-99
    count: int
    order_id: Optional[str] = None
    placed_at: Optional[float] = None
# _MAX_ERRORS_BEFORE_PAUSE = 3
# _ERROR_PAUSE_SECONDS = 60
```

<!-- New surfaces this plan creates that downstream plans (04-04..04-08) consume -->
NEW src/quoting/kalshi_auth.py public surface:
```python
def load_private_key(pem_path: str | Path): ...   # returns rsa.RSAPrivateKey
def sign_request(
    key_id: str,
    private_key: rsa.RSAPrivateKey,
    method: str,                                   # "GET" | "POST" | "DELETE"
    path: str,                                      # "/trade-api/v2/portfolio/orders" — NO QUERY STRING
) -> dict[str, str]: ...                           # 3 KALSHI-ACCESS-* headers
```

NEW src/quoting/market_data.py public surface:
```python
@dataclass(frozen=True, slots=True)
class MarketQuote:
    yes_bid: int                                   # cents 1-99
    yes_ask: int
    mid: int                                       # int((yes_bid + yes_ask) / 2)
    spread: int                                    # yes_ask - yes_bid
    is_valid: bool                                 # False during WS reconnect (Pitfall 7)
    last_updated_ts: float                         # wall_time at last book update

class MarketDataSource(Protocol):
    def latest(self, ticker: str) -> MarketQuote | None: ...
    async def run(self) -> None: ...

@dataclass
class SyntheticMarketData:
    """Dry-run/test backend; quotes injected programmatically."""
    _quotes: dict[str, MarketQuote] = field(default_factory=dict)
    def push(self, ticker: str, quote: MarketQuote) -> None: ...
    def latest(self, ticker: str) -> MarketQuote | None: ...
    async def run(self) -> None: ...               # no-op

class KalshiWsMarketData:
    """Live backend; subscribes to orderbook_delta + ticker channels."""
    def __init__(self, key_id: str, private_key, *, dry_run: bool) -> None: ...
    def latest(self, ticker: str) -> MarketQuote | None: ...
    async def run(self) -> None: ...               # WS connect + subscribe + book maintenance loop
```

NEW src/quoting/order_manager.py public surface:
```python
@dataclass(slots=True)
class Quote:
    ticker: str
    side: Literal["yes", "no"]
    action: Literal["buy", "sell"]
    price: int                                      # cents 1-99
    count: int
    strategy_id: Literal["MM_BETWEEN_ROUND", "DIRECTIONAL_TAKE", "POST_PLANT_QUOTE"]  # NEW v2
    order_id: str | None = None
    placed_at: float | None = None
    client_order_id: str | None = None              # uuid4 by default

class KalshiOrderManager:
    def __init__(
        self,
        session: aiohttp.ClientSession,
        key_id: str,
        private_key: rsa.RSAPrivateKey,
        *,
        dry_run: bool,                              # MUST come from src.main.resolve_dry_run (DEC-022)
    ) -> None: ...
    @property
    def active_quotes(self) -> dict[str, dict[str, Quote]]: ...
    @property
    def error_streak(self) -> int: ...
    async def place_quote(self, quote: Quote) -> bool: ...
    async def cancel_quote(self, ticker: str, leg: str) -> bool: ...
    async def cancel_all_orders(self) -> None: ...   # batch DELETE — 2 tokens/order
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: src/quoting/kalshi_auth.py + GREEN test_kalshi_auth.py + CLAUDE.md correction</name>
  <files>src/quoting/kalshi_auth.py, src/quoting/__init__.py, tests/quoting/test_kalshi_auth.py, CLAUDE.md</files>
  <behavior>
    - sign_request(key_id, private_key, "GET", "/trade-api/v2/exchange/status") returns dict with EXACTLY three keys: KALSHI-ACCESS-KEY, KALSHI-ACCESS-SIGNATURE, KALSHI-ACCESS-TIMESTAMP
    - KALSHI-ACCESS-TIMESTAMP is a string of milliseconds (int(time.time() * 1000)); within 1000ms of test wall-clock
    - KALSHI-ACCESS-SIGNATURE is base64-encoded; decodable to 256 bytes (2048-bit RSA)
    - Signature verifies with the corresponding public key using padding.PSS(MGF1(SHA256), salt_length=DIGEST_LENGTH) over the message timestamp_ms + method + path
    - Defensive: sign_request("KEY", key, "GET", "/x?foo=bar") raises AssertionError("Sign path WITHOUT query parameters")
    - load_private_key reads a PEM file with no password and returns an rsa.RSAPrivateKey
  </behavior>
  <action>
(A) Create src/quoting/kalshi_auth.py (~50 lines) per RESEARCH §"Code Examples"
    Kalshi RSA-PSS signing block. EXACT implementation:

    ```python
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
    ```

(B) Create/update src/quoting/__init__.py to export the public surface:
    ```python
    """Phase 4 quoting layer — Kalshi order plumbing + mode-aware quoters.

    Public surface populated incrementally across plans 04-01 (auth +
    order manager + market data) through 04-08 (reconciliation + E2E).
    """
    from src.quoting.kalshi_auth import load_private_key, sign_request
    # KalshiOrderManager / Quote / MarketQuote exports added in same task.

    __all__ = ["load_private_key", "sign_request"]
    ```

    (Plans 04-02..04-08 will extend `__all__` as they ship modules.)

(C) Flip RED stubs in tests/quoting/test_kalshi_auth.py to GREEN tests:

    ```python
    """Plan 04-01 — REQ-kalshi-order-manager auth tests (RSA-PSS verified)."""
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


    def test_sign_request_rejects_query_string_path(fake_private_key) -> None:
        with pytest.raises(AssertionError, match="WITHOUT query parameters"):
            sign_request("KEY", fake_private_key, "GET", "/foo?bar=1")


    def test_sign_request_uses_pss_padding(fake_private_key) -> None:
        """Pitfall 2: signature MUST verify under PSS, not PKCS1v15."""
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
        assert before <= int(headers["KALSHI-ACCESS-TIMESTAMP"]) <= after + 10
    ```

(D) CLAUDE.md correction — atomic in same commit per `notes`:

    Search CLAUDE.md for the exact string "RSA PKCS1v15/SHA-256 auth" inside
    the "Data sources" table row for Kalshi (line in the table currently reads
    "RSA PKCS1v15/SHA-256 auth. Key in `.env`."). REPLACE with:

      "RSA-PSS / SHA-256 auth (verified docs.kalshi.com 2026-05-09;
      MGF1(SHA256), salt_length=DIGEST_LENGTH). Key in `.env`."

    Use the Edit tool with old_string = "RSA PKCS1v15/SHA-256 auth. Key in `.env`."
    and new_string = "RSA-PSS / SHA-256 auth (verified docs.kalshi.com 2026-05-09; MGF1(SHA256), salt_length=DIGEST_LENGTH). Key in `.env`."

    NO other CLAUDE.md changes — keep the surrounding text intact. The single-
    line correction is the minimum viable fix.

CRITICAL — atomic commit per `notes`. Do NOT split (A)..(D) across commits.
  </action>
  <verify>
    <automated>uv run pytest tests/quoting/test_kalshi_auth.py -x --no-cov &amp;&amp; uv run mypy --strict src/quoting/</automated>
  </verify>
  <done>
- src/quoting/kalshi_auth.py exists, ~50 lines, uses padding.PSS with MGF1(SHA256) and salt_length=PSS.DIGEST_LENGTH.
- All 4 tests in tests/quoting/test_kalshi_auth.py pass GREEN (no xfail).
- `uv run mypy --strict src/quoting/` clean.
- CLAUDE.md no longer contains "PKCS1v15" (verified by `rg "PKCS1v15" CLAUDE.md` returning empty).
- src/quoting/__init__.py exports load_private_key + sign_request.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: src/quoting/market_data.py + GREEN test_market_data.py</name>
  <files>src/quoting/market_data.py, src/quoting/__init__.py, tests/quoting/test_market_data.py</files>
  <behavior>
    - MarketQuote(yes_bid=48, yes_ask=52) auto-derives mid=50, spread=4 (frozen + slots; equality + hashing work)
    - SyntheticMarketData.push("VAL-T1-WIN", quote) followed by .latest("VAL-T1-WIN") returns the same quote
    - SyntheticMarketData.latest("UNKNOWN") returns None
    - SyntheticMarketData.run() is a no-op coroutine that returns immediately (test: `asyncio.wait_for(src.run(), 0.1)` doesn't time out)
    - MarketDataSource.latest is part of the structural Protocol (typing.Protocol with @runtime_checkable)
    - WS reconnect path: KalshiWsMarketData.is_valid flips to False on disconnect handler trigger; mode-selector callers receive `is_valid=False` MarketQuote (Pitfall 7)
    - KalshiWsMarketData skeleton: constructor accepts (key_id, private_key, dry_run) and has a `run()` coroutine; the actual WS connect + subscribe + book-maintenance loop is NotImplementedError-stubbed (production-grade implementation deferred to Phase 6 — for Phase 04 paper-trade we use SyntheticMarketData per RESEARCH §"User Constraints")
  </behavior>
  <action>
Build src/quoting/market_data.py (~80-120 lines):

```python
"""MarketQuote + MarketDataSource Protocol (REQ-kalshi-order-manager market-data
arm).

Two implementations:
  - SyntheticMarketData: dry-run / test backend; quotes injected via push().
    Default for Phase 04 paper-trade; the dev .env doesn't have KALSHI_KEY_PATH
    populated and the WS path requires it.
  - KalshiWsMarketData: live backend; subscribes to orderbook_delta + ticker
    channels per Kalshi docs. Skeleton in this plan; full WS book maintenance
    is operator-gated (operator gate 2 + Phase 6 deployment work).

Source: RESEARCH §"Architecture Patterns" Pattern 2 + §"Code Examples" Kalshi
WS subscribe + §"Open Questions" #3 SyntheticMarketData/KalshiWsMarketData
split.

Pitfall 7 mitigation: on WS disconnect, the KalshiWsMarketData implementation
flips is_valid=False on cached MarketQuotes; mode-selector kill_switch_active
treats is_valid=False as a synthetic kill-switch trip (plan 04-03 wires this).
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from cryptography.hazmat.primitives.asymmetric import rsa


@dataclass(frozen=True, slots=True)
class MarketQuote:
    """Snapshot of one Kalshi market's top-of-book.

    Cents-encoded per Kalshi convention. `is_valid=False` signals stale book
    (e.g., during WS reconnect — Pitfall 7); kill_switch_active in plan 04-03
    treats this as a trip.
    """

    yes_bid: int          # cents 1-99
    yes_ask: int          # cents 1-99
    mid: int              # int((yes_bid + yes_ask) / 2)
    spread: int           # yes_ask - yes_bid
    is_valid: bool
    last_updated_ts: float


def make_quote(yes_bid: int, yes_ask: int, *, is_valid: bool = True) -> MarketQuote:
    """Convenience constructor; auto-computes mid + spread."""
    return MarketQuote(
        yes_bid=yes_bid,
        yes_ask=yes_ask,
        mid=(yes_bid + yes_ask) // 2,
        spread=yes_ask - yes_bid,
        is_valid=is_valid,
        last_updated_ts=time.time(),
    )


@runtime_checkable
class MarketDataSource(Protocol):
    """Structural protocol every market-data backend satisfies.

    Consumers (mode-selector, quoters, kill switches) call .latest(ticker);
    backends call .run() once at startup to enter their event loop (no-op for
    SyntheticMarketData, WS subscribe + book loop for KalshiWsMarketData).
    """

    def latest(self, ticker: str) -> MarketQuote | None: ...
    async def run(self) -> None: ...


@dataclass
class SyntheticMarketData:
    """In-memory MarketDataSource for dry-run + tests.

    Quoters retrieve quotes via .latest(); test fixtures (or live state-engine
    handlers) inject quotes via .push().
    """

    _quotes: dict[str, MarketQuote] = field(default_factory=dict)

    def push(self, ticker: str, quote: MarketQuote) -> None:
        self._quotes[ticker] = quote

    def latest(self, ticker: str) -> MarketQuote | None:
        return self._quotes.get(ticker)

    async def run(self) -> None:
        """No-op event loop; keeps the protocol surface uniform."""
        return None


class KalshiWsMarketData:
    """Live Kalshi WebSocket market-data backend.

    SKELETON — full WS connect + subscribe + book maintenance is operator-gated
    (the dev .env doesn't have KALSHI_KEY_PATH; the smoke test in
    scripts/kalshi_auth_smoke.py exercises the auth path independently).

    Pitfall 7: on WS disconnect handler, set every cached MarketQuote.is_valid
    to False; resume only after the next FULL book arrives via the
    orderbook_delta `snapshot` message.
    """

    def __init__(
        self,
        key_id: str,
        private_key: rsa.RSAPrivateKey,
        *,
        dry_run: bool,
    ) -> None:
        self._key_id = key_id
        self._private_key = private_key
        self._dry_run = dry_run
        self._quotes: dict[str, MarketQuote] = {}
        self._connected = False

    def latest(self, ticker: str) -> MarketQuote | None:
        return self._quotes.get(ticker)

    async def run(self) -> None:
        """WS connect + subscribe + book maintenance loop.

        SKELETON — operator gate 2 (RESEARCH Pitfall 8) covers auth; the full
        WS implementation is Phase 6 deployment work. For Phase 04 paper-trade,
        SyntheticMarketData is the default.
        """
        if self._dry_run:
            return None
        raise NotImplementedError(
            "KalshiWsMarketData.run live path is operator-gated; ship in Phase 6 "
            "deployment work after operator-gate-2 smoke test passes."
        )

    def mark_invalid(self) -> None:
        """Flip every cached quote's is_valid to False (Pitfall 7 disconnect path)."""
        for ticker, q in list(self._quotes.items()):
            self._quotes[ticker] = MarketQuote(
                yes_bid=q.yes_bid,
                yes_ask=q.yes_ask,
                mid=q.mid,
                spread=q.spread,
                is_valid=False,
                last_updated_ts=q.last_updated_ts,
            )
```

Update src/quoting/__init__.py to add the new exports:
```python
from src.quoting.market_data import (
    KalshiWsMarketData,
    MarketDataSource,
    MarketQuote,
    SyntheticMarketData,
    make_quote,
)
__all__ = [
    "KalshiWsMarketData", "MarketDataSource", "MarketQuote",
    "SyntheticMarketData", "load_private_key", "make_quote", "sign_request",
]
```

Flip RED stubs in tests/quoting/test_market_data.py to GREEN. Cover:
- test_market_quote_dataclass_shape: `make_quote(48, 52)` -> mid=50, spread=4, is_valid=True
- test_synthetic_market_data_push_latest: round-trip
- test_synthetic_market_data_latest_unknown_returns_none
- test_synthetic_market_data_run_is_noop: `await asyncio.wait_for(src.run(), 0.1)` returns
- test_kalshi_ws_market_data_dry_run_returns: `await ws.run()` returns None when dry_run=True
- test_kalshi_ws_market_data_live_raises_not_implemented: `await ws.run()` raises NotImplementedError when dry_run=False (skeleton contract)
- test_market_data_source_protocol_runtime_check: `isinstance(SyntheticMarketData(), MarketDataSource)` True
- test_mark_invalid_flips_cached_quotes: pre-push 1 quote, mark_invalid, latest().is_valid is False
  </action>
  <verify>
    <automated>uv run pytest tests/quoting/test_market_data.py -x --no-cov &amp;&amp; uv run mypy --strict src/quoting/</automated>
  </verify>
  <done>
- src/quoting/market_data.py defines MarketQuote (frozen+slots), make_quote helper, MarketDataSource Protocol, SyntheticMarketData, KalshiWsMarketData (skeleton).
- 8 tests in tests/quoting/test_market_data.py pass GREEN.
- src/quoting/__init__.py re-exports all new names.
- mypy --strict clean.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: src/quoting/order_manager.py + GREEN test_order_manager.py + scripts/kalshi_auth_smoke.py</name>
  <files>src/quoting/order_manager.py, src/quoting/__init__.py, tests/quoting/test_order_manager.py, scripts/kalshi_auth_smoke.py</files>
  <behavior>
    - Quote dataclass has strategy_id field (NEW v2) typed Literal["MM_BETWEEN_ROUND", "DIRECTIONAL_TAKE", "POST_PLANT_QUOTE"]
    - Quote.client_order_id auto-generates a uuid4 hex string if None at place time
    - KalshiOrderManager(dry_run=True).place_quote(q) sets q.order_id to "DRY_<uuid8>" and q.placed_at to time.time(); _active_quotes[ticker][leg] = q; returns True; NO network call
    - KalshiOrderManager(dry_run=True).cancel_all_orders() clears _active_quotes; returns None; NO network call
    - place_quote in dry-run records ZERO error_streak increments
    - In live mode (dry_run=False) with mocked aioresponses returning 201, place_quote sets q.order_id from response and resets _error_streak = 0
    - In live mode with mocked 4xx response, place_quote increments _error_streak and returns False
    - cancel_all in live mode batches via DELETE /portfolio/orders/batched (single request) per RESEARCH §"Pattern 2" rate-budget note (2 tokens/order vs 10/order individual)
    - sign_request is called with path WITHOUT query parameters (regression test for Pitfall 1)
  </behavior>
  <action>
(A) Create src/quoting/order_manager.py (~150-180 lines). Salvage structural patterns
    from reference/market_maker.py (DEC-013): Quote dataclass, _active_quotes dict,
    error_streak counter, _is_near_close guard structure (the close-time guard wraps
    place_quote in live mode). Rewrite verbs against aiohttp + cryptography per
    RESEARCH §"Pattern 2".

    ```python
    """KalshiOrderManager — async REST plumbing for Kalshi order lifecycle.

    Owns:
      - aiohttp.ClientSession (caller-supplied so a single session is reused
        across the order manager + market-data WS + reconciliation pollers)
      - In-memory active quotes dict (rebuildable from Kalshi via plan 04-08
        reconciliation)
      - error_streak counter for the API-error kill switch (DEC-005 #a)
      - dry_run wrapper (DEC-022 / CLAUDE.md rule 13 — `dry_run` MUST come from
        src.main.resolve_dry_run; do NOT default to a module attribute)

    Salvaged structurally from reference/market_maker.py per DEC-013:
      - Quote dataclass shape (with strategy_id added v2)
      - _MAX_ERRORS_BEFORE_PAUSE = 3 / _ERROR_PAUSE_SECONDS = 60 names
      - cancel_all_orders intent + dry-run shortcut

    NEW v2:
      - strategy_id field on Quote so plan 04-05/04-06/04-07 hypothetical-fill
        ledgers route to the right per-strategy JSONL file (DEC-020 v2)
      - batched DELETE for cancel_all_orders (2 tokens/order budget) per
        RESEARCH §"Pattern 2" rate-budget note
      - aiohttp instead of sync requests (Phase 03 went async-native)
      - cryptography RSA-PSS instead of KalshiClient SDK (skip per RESEARCH
        §"Standard Stack" Alternatives Considered)

    Source: REQ-kalshi-order-manager / DEC-013 / RESEARCH §"Pattern 2".
    """
    from __future__ import annotations

    import time
    import uuid
    from dataclasses import dataclass
    from typing import Literal

    import aiohttp
    from cryptography.hazmat.primitives.asymmetric import rsa

    from src.config.constants import KALSHI_BASE_URL
    from src.quoting.kalshi_auth import sign_request

    StrategyId = Literal["MM_BETWEEN_ROUND", "DIRECTIONAL_TAKE", "POST_PLANT_QUOTE"]


    @dataclass(slots=True)
    class Quote:
        """One resting limit order — Phase 04 v2 surface.

        Salvaged shape from reference/market_maker.py:36-46 with strategy_id
        added (DEC-020 v2 — fills ledger routing).
        """
        ticker: str
        side: Literal["yes", "no"]
        action: Literal["buy", "sell"]
        price: int                           # cents 1-99
        count: int
        strategy_id: StrategyId              # NEW v2 — required for fill-ledger routing
        order_id: str | None = None
        placed_at: float | None = None
        client_order_id: str | None = None   # uuid4 hex; generated at place time if None


    _MAX_ERRORS_BEFORE_PAUSE: int = 3
    """Salvaged from reference/market_maker.py:73. Triggers kill_switch_api_error."""


    class KalshiOrderManager:
        """Async Kalshi REST + dry-run wrapper for order placement / cancellation.

        Single source of truth for the dry-run wrapper (DEC-022 / CLAUDE.md
        rule 13). Mode-specific quoters (MM, DIRECTIONAL, POST_PLANT) consume
        this single class; they do NOT each implement their own dry-run
        shortcut.
        """

        def __init__(
            self,
            session: aiohttp.ClientSession,
            key_id: str,
            private_key: rsa.RSAPrivateKey,
            *,
            dry_run: bool,
        ) -> None:
            self._session = session
            self._key_id = key_id
            self._private_key = private_key
            self._dry_run = dry_run
            self._active_quotes: dict[str, dict[str, Quote]] = {}
            self._error_streak: int = 0

        @property
        def active_quotes(self) -> dict[str, dict[str, Quote]]:
            """Read-only view; mutation only via place/cancel methods."""
            return self._active_quotes

        @property
        def error_streak(self) -> int:
            return self._error_streak

        @property
        def dry_run(self) -> bool:
            return self._dry_run

        async def place_quote(self, quote: Quote) -> bool:
            """Place a limit order; track in _active_quotes on success.

            In dry-run: assigns DRY_<uuid8> order_id, records placed_at, returns True.
            In live: signs and POSTs /portfolio/orders, sets order_id from response.
            On 4xx/5xx: increments _error_streak and returns False.
            """
            client_oid = quote.client_order_id or uuid.uuid4().hex
            quote.client_order_id = client_oid

            if self._dry_run:
                quote.order_id = f"DRY_{client_oid[:8]}"
                quote.placed_at = time.time()
                self._active_quotes.setdefault(quote.ticker, {})
                leg_key = f"{quote.action}_{quote.side}"
                self._active_quotes[quote.ticker][leg_key] = quote
                return True

            body: dict[str, object] = {
                "ticker": quote.ticker,
                "side": quote.side,
                "action": quote.action,
                "count": quote.count,
                "yes_price": quote.price if quote.side == "yes" else None,
                "no_price": quote.price if quote.side == "no" else None,
                "client_order_id": client_oid,
                "post_only": True,
                "time_in_force": "good_till_canceled",
            }
            path = "/trade-api/v2/portfolio/orders"
            headers = sign_request(self._key_id, self._private_key, "POST", path)
            try:
                async with self._session.post(KALSHI_BASE_URL + "/portfolio/orders",
                                               json=body, headers=headers) as r:
                    if r.status == 201:
                        data = await r.json()
                        quote.order_id = data["order"]["order_id"]
                        quote.placed_at = time.time()
                        self._active_quotes.setdefault(quote.ticker, {})
                        leg_key = f"{quote.action}_{quote.side}"
                        self._active_quotes[quote.ticker][leg_key] = quote
                        self._error_streak = 0
                        return True
                    self._error_streak += 1
                    return False
            except aiohttp.ClientError:
                self._error_streak += 1
                return False

        async def cancel_quote(self, ticker: str, leg_key: str) -> bool:
            """Cancel one resting quote. Plan 04-08 reconciliation calls this for ghosts."""
            legs = self._active_quotes.get(ticker, {})
            quote = legs.get(leg_key)
            if quote is None or quote.order_id is None:
                return False

            if self._dry_run:
                del legs[leg_key]
                if not legs:
                    del self._active_quotes[ticker]
                return True

            path = f"/trade-api/v2/portfolio/orders/{quote.order_id}"
            headers = sign_request(self._key_id, self._private_key, "DELETE", path)
            try:
                async with self._session.delete(KALSHI_BASE_URL + f"/portfolio/orders/{quote.order_id}",
                                                 headers=headers) as r:
                    success = r.status in (200, 204)
                    if success:
                        del legs[leg_key]
                        if not legs:
                            del self._active_quotes[ticker]
                    else:
                        self._error_streak += 1
                    return success
            except aiohttp.ClientError:
                self._error_streak += 1
                return False

        async def cancel_all_orders(self) -> None:
            """Batch-cancel every resting order. Used by kill switches and POST_PLANT_QUOTE.

            Live path uses DELETE /portfolio/orders/batched (2 tokens/order vs
            10/order individual) per RESEARCH §"Pattern 2" rate-budget note.
            """
            order_ids = [
                q.order_id for legs in self._active_quotes.values() for q in legs.values()
                if q.order_id
            ]
            if not order_ids:
                return

            if self._dry_run:
                self._active_quotes.clear()
                return

            body = {"order_ids": order_ids}
            path = "/trade-api/v2/portfolio/orders/batched"
            headers = sign_request(self._key_id, self._private_key, "DELETE", path)
            try:
                async with self._session.delete(KALSHI_BASE_URL + "/portfolio/orders/batched",
                                                 json=body, headers=headers) as r:
                    if r.status not in (200, 204):
                        self._error_streak += 1
            except aiohttp.ClientError:
                self._error_streak += 1
            finally:
                # Clear local state EVEN on cancel failure (Pitfall 4 — cancel_all
                # that swallows network errors leaves us believing we are flat
                # while resting orders still exist; downstream API-error kill
                # switch trip + reconciliation will surface the divergence).
                self._active_quotes.clear()
    ```

(B) Update src/quoting/__init__.py to add Quote + KalshiOrderManager exports.

(C) Flip RED stubs in tests/quoting/test_order_manager.py to GREEN. Use the
    `fake_kalshi_session` fixture (aioresponses) for live-mode tests; dry-run
    tests don't need a network mock.

    Required tests:
    - test_place_quote_dry_run: q = Quote("VAL-T1", "yes", "buy", 50, 10, "MM_BETWEEN_ROUND"); await mgr.place_quote(q); assert q.order_id.startswith("DRY_") and len(q.order_id) == 12 and q.placed_at is not None
    - test_place_quote_dry_run_no_network: similar, but use a session whose .post would raise if invoked (we never go to network)
    - test_place_quote_dry_run_records_active_quotes: after place_quote, mgr.active_quotes["VAL-T1"]["buy_yes"] == q
    - test_cancel_all_dry_run: place 3 quotes; await mgr.cancel_all_orders(); assert mgr.active_quotes == {}
    - test_error_streak_zero_on_dry_run: place 5 quotes; assert mgr.error_streak == 0
    - test_client_order_id_uuid_set: place a quote with client_order_id=None; assert quote.client_order_id is not None and len(quote.client_order_id) == 32 (uuid4().hex)
    - test_place_quote_live_201_succeeds: mock aioresponses to return 201 with payload {"order": {"order_id": "abc"}}; assert await mgr.place_quote(q) is True and q.order_id == "abc" and mgr.error_streak == 0
    - test_place_quote_live_4xx_increments_error_streak: mock 400; assert returns False and mgr.error_streak == 1
    - test_cancel_all_uses_batched_path: live mode; place 2 quotes; mock DELETE /portfolio/orders/batched 200; await cancel_all; verify the call URL contained "/batched"

(D) Create scripts/kalshi_auth_smoke.py — operator-gated smoke test:

    ```python
    """Operator-gated Kalshi auth smoke test (RESEARCH Pitfall 8 mitigation).

    Signs a GET /trade-api/v2/exchange/status request with the operator's
    `.env` credentials and asserts a 200 response. Run ONCE after first
    checkout to verify the .env works:

        python scripts/kalshi_auth_smoke.py

    The dry-run wrapper in production code shortcuts ALL Kalshi calls in
    dev (KALSHI_KEY_PATH not in .env), so the auth signing path never
    runs in production code paths until --live mode. This script gives
    operators a no-`--live` way to validate auth.

    Exit codes:
        0 — success (signed request returned 200)
        1 — .env missing or KALSHI_KEY_PATH not set
        2 — non-200 response (auth failure or Kalshi-side issue)
    """
    from __future__ import annotations

    import os
    import sys

    import aiohttp
    import asyncio
    from dotenv import load_dotenv

    from src.config.constants import KALSHI_BASE_URL
    from src.quoting.kalshi_auth import load_private_key, sign_request


    async def _run() -> int:
        load_dotenv()
        key_id = os.getenv("KALSHI_KEY_ID")
        key_path = os.getenv("KALSHI_KEY_PATH")
        if not key_id or not key_path:
            print("ERROR: KALSHI_KEY_ID and KALSHI_KEY_PATH must be in .env", file=sys.stderr)
            return 1

        private_key = load_private_key(key_path)
        path = "/trade-api/v2/exchange/status"
        headers = sign_request(key_id, private_key, "GET", path)
        async with aiohttp.ClientSession() as session:
            async with session.get(KALSHI_BASE_URL + "/exchange/status",
                                    headers=headers) as r:
                if r.status == 200:
                    body = await r.json()
                    print(f"OK status={r.status} body={body}")
                    return 0
                print(f"FAIL status={r.status} body={await r.text()}", file=sys.stderr)
                return 2


    if __name__ == "__main__":
        sys.exit(asyncio.run(_run()))
    ```

    Add a brief reference under CLAUDE.md "Run commands":
    ```
    # Operator gate 2 — Kalshi auth smoke (one-time after .env populated)
    python scripts/kalshi_auth_smoke.py
    ```

    Use Edit tool with old_string from the existing "Run commands" block to
    insert the new line after the existing Phase 1 / Phase 2 entries.
  </action>
  <verify>
    <automated>uv run pytest tests/quoting/test_order_manager.py -x --no-cov &amp;&amp; uv run mypy --strict src/quoting/ &amp;&amp; uv run python -c "import scripts.kalshi_auth_smoke"</automated>
  </verify>
  <done>
- src/quoting/order_manager.py defines Quote (with strategy_id v2 field) and KalshiOrderManager (place_quote / cancel_quote / cancel_all_orders + dry-run wrapper + error_streak counter).
- 9 tests in tests/quoting/test_order_manager.py pass GREEN; aioresponses-mocked live tests cover 201 + 4xx paths.
- scripts/kalshi_auth_smoke.py exists; importable; CLI shape documented in CLAUDE.md "Run commands".
- src/quoting/__init__.py exports Quote + KalshiOrderManager.
- mypy --strict src/quoting/ clean.
  </done>
</task>

</tasks>

<verification>
1. `uv run pytest tests/quoting/test_kalshi_auth.py tests/quoting/test_order_manager.py tests/quoting/test_market_data.py -x --no-cov` — all 21 GREEN.
2. `uv run mypy --strict src/quoting/` clean.
3. `uv run pytest tests/ -x --no-cov` — Phase 03 stays green; Phase 04 stubs for plans 04-02..04-08 remain xfailed.
4. `rg "PKCS1v15" CLAUDE.md` returns empty (correction landed atomically).
5. `python scripts/kalshi_auth_smoke.py` exits 1 with "KALSHI_KEY_ID and KALSHI_KEY_PATH must be in .env" message when no .env exists (verifies the script's error path; operator runs the success path manually).
</verification>

<success_criteria>
- KalshiOrderManager dry-run path is the single source of truth for "no network in dev mode" (DEC-022).
- RSA-PSS auth verified against Kalshi docs; CLAUDE.md atomic correction shipped.
- MarketDataSource Protocol with SyntheticMarketData (default) + KalshiWsMarketData (skeleton) lets downstream plans 04-04..04-08 consume MarketQuote without choosing a backend at import time.
- All 21 newly-GREEN tests pass.
</success_criteria>

<output>
After completion, create `.planning/phases/04-quoting-layer/04-01-SUMMARY.md` documenting:
- Files created (src/quoting/kalshi_auth.py, order_manager.py, market_data.py, scripts/kalshi_auth_smoke.py).
- CLAUDE.md correction (one-line PKCS1v15 → RSA-PSS replacement).
- Operator gate 2 instructions (one-time `python scripts/kalshi_auth_smoke.py` after .env populated).
- mypy --strict src/quoting/ clean confirmation.
- Forward links to plan 04-04 (mode-selector consumes MarketQuote + KalshiOrderManager.dry_run flag) and plans 04-05..04-07 (consume Quote.strategy_id for fill-ledger routing).
</output>
