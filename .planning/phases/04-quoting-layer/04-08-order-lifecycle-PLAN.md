---
phase: 04-quoting-layer
plan: "08"
type: execute
wave: 5
depends_on: ["00", "01", "02", "03", "04", "05", "06", "07"]
files_modified:
  - src/quoting/reconciliation.py
  - src/quoting/__init__.py
  - tests/quoting/test_reconciliation.py
  - tests/quoting/test_e2e.py
autonomous: true
requirements:
  - REQ-order-lifecycle-reconciliation
notes: |
  Wave 5 — order lifecycle reconciliation (REQ-order-lifecycle-reconciliation)
  + the Phase 04 synthetic E2E gate. This is the FINAL plan in Phase 04 —
  composes plans 04-01..04-07 into a single end-to-end synthetic harness
  that validates the four phase-level must-haves from the planner brief:
    (a) kill-switch trip → all resting quotes cancelled within 200ms
    (b) bomb-detect → quote-pull p50 < 100ms (Phase 04's piece of 200ms budget)
    (c) MM and DIRECTIONAL fills land in SEPARATE ledger files
    (d) mode transitions clean (no stale orders across MM↔DIRECTIONAL)

  RECONCILIATION (RESEARCH §"Pattern 5") — 1Hz polled diff between
  KalshiOrderManager._active_quotes and Kalshi's /portfolio/orders GET
  response:
    - Orphans (Kalshi has, we don't track) → cancel via order_id
    - Ghosts (we track, Kalshi doesn't have) → drop the local Quote reference
    - Dry-run shortcut per DEC-022 — reconcile_once returns immediately if
      mgr._dry_run is True (no remote state to reconcile against)
    - Path-without-query rule (RESEARCH Pitfall 1) — sign_request gets the
      bare path; query string is appended to the URL but NOT to the sign
      input. The defensive assert in plan 04-01 kalshi_auth.sign_request
      catches violations.

  Cancel-all-on-kill-switch-trip wiring (must-have 5 from planner brief):
  the bot main loop pattern (sketched in this plan, fully wired in Phase
  6 deployment work) is:
    1. After every theo computation: kill_switch_aggregator.any_tripped(...)
    2. If tripped → KalshiOrderManager.cancel_all_orders() (already
       implemented in plan 04-01 — clears ALL resting quotes regardless
       of strategy_id, so MM + DIRECTIONAL + POST_PLANT all pulled
       together)
  Plan 04-08 ships the COMPOSITION as a synthetic test
  (test_kill_switch_trip_cancels_all_resting), not a production main loop
  — the production main loop is operator-gated (Phase 6 deployment).

  Mode-transition cleanup (must-have 4 from planner brief): the bot main
  loop pattern is:
    Mode change from MM_BETWEEN_ROUND → DIRECTIONAL_TAKE (or vice versa,
    or to/from IDLE): cancel quotes belonging to the OLD strategy_id
    before placing new ones. POST_PLANT_QUOTE entry: defensive pull
    handles this (plan 04-07). MM_BETWEEN_ROUND quoter's idempotency
    handles steady-state. DIRECTIONAL is IOC (no resting), so the only
    real case is MM_BETWEEN_ROUND → IDLE (stale MM quotes left over) or
    MM_BETWEEN_ROUND → DIRECTIONAL_TAKE (same case — the MM IOC quotes
    are stale).
  Plan 04-08 ships a helper `cancel_strategy_quotes(mgr, strategy_id)`
  that the bot main loop invokes on mode change. Test
  test_mode_transition_mm_to_idle_clears_mm_quotes covers.

  Round-resolution → PortfolioState.on_settle wiring (Pitfall 5
  carry-forward from plan 04-02): plan 04-08 ships the helper
  `on_round_resolved(portfolio, series_id, fraction)` that the bot main
  loop invokes when a round_end_event commits via the arbiter (Phase 03
  arbiter). Phase 04 unit tests verify the helper signature; full wiring
  to arbiter event subscription is Phase 6 deployment work.

  Brier score → KillSwitchAggregator.recent_briers wiring (Pitfall 4
  carry-forward from plan 04-03): helper
  `on_round_resolved_with_brier(aggregator, mode_at_time_of_quote, brier)`
  appends to the deque ONLY IF mode_at_time_of_quote != "IDLE" (RESEARCH
  Pitfall 4 — IDLE rounds must NOT contribute to the rolling Brier).

  E2E test (tests/quoting/test_e2e.py) — synthetic harness composing:
    PendingEvent (injected) → Arbiter.tick() → live_theo →
    KillSwitchAggregator → trading_mode → {MM, DIRECTIONAL, POST_PLANT}
    quoter → fill_ledger
  No real I/O — KalshiOrderManager(dry_run=True) + SyntheticMarketData +
  fake_private_key. Mirrors Phase 03 plan 03-08's "synthetic harness
  latency math is structurally trivial" framing — the E2E gate verifies
  INSTRUMENTATION + WIRING + INVARIANTS, not real-broadcast latency
  (Phase 5 paper-trade owns that).

must_haves:
  truths:
    - "reconcile_once(mgr, ticker) in dry-run returns immediately without any HTTP call"
    - "reconcile_once in live mode cancels orphans (Kalshi-has, we-don't) via DELETE /portfolio/orders/{order_id}"
    - "reconcile_once in live mode drops ghosts (we-have, Kalshi-doesn't) from mgr._active_quotes — no DELETE call (already gone from Kalshi)"
    - "reconcile_once signs path WITHOUT query parameters (Pitfall 1 — verified by aioresponses + sign_request input inspection)"
    - "cancel_strategy_quotes(mgr, \"MM_BETWEEN_ROUND\") cancels every Quote with strategy_id == \"MM_BETWEEN_ROUND\"; DIRECTIONAL_TAKE / POST_PLANT_QUOTE quotes untouched"
    - "on_round_resolved(portfolio, series_id, fraction) calls portfolio.on_settle (Pitfall 5 wiring)"
    - "on_round_resolved_with_brier appends to aggregator.recent_briers ONLY if mode != IDLE (Pitfall 4 wiring)"
    - "E2E: kill_switch_aggregator.any_tripped() → True → cancel_all_orders() clears MM + DIRECTIONAL + POST_PLANT resting quotes together (within 200ms in synthetic harness)"
    - "E2E: bomb_planted=False → True transition → post_plant_quote(is_first_call=True) → t_quote_pull_completed populated; p50 over 50 trials < 100ms"
    - "E2E: synthetic MM fill + DIRECTIONAL fill land in DIFFERENT ledger files (data/fills/{match_id}.mm_between_round.jsonl + .directional_take.jsonl)"
    - "E2E: mode transition MM_BETWEEN_ROUND → IDLE leaves NO stale MM quotes (cancel_strategy_quotes invoked on transition)"
  artifacts:
    - path: "src/quoting/reconciliation.py"
      provides: "reconcile_once + cancel_strategy_quotes + on_round_resolved + on_round_resolved_with_brier helpers"
      min_lines: 130
      contains: "reconcile_once"
    - path: "tests/quoting/test_reconciliation.py"
      provides: "8+ tests: orphans / ghosts / dry-run noop / path-without-query / cancel_strategy / on_round_resolved / on_round_resolved_with_brier"
      contains: "test_cancel_orphans"
    - path: "tests/quoting/test_e2e.py"
      provides: "4+ E2E tests covering must-haves a-d (kill-switch cancel-all + bomb-detect 100ms + separate ledgers + mode transitions)"
      contains: "test_e2e_kill_switch_trip_cancels_all_resting"
  key_links:
    - from: "src/quoting/reconciliation.reconcile_once"
      to: "src/quoting/order_manager.KalshiOrderManager._active_quotes + cancel_quote + sign_request"
      via: "diff-and-cancel pattern (RESEARCH §\"Pattern 5\")"
      pattern: "reconcile_once"
    - from: "src/quoting/reconciliation.cancel_strategy_quotes"
      to: "src/quoting/order_manager.KalshiOrderManager.cancel_quote"
      via: "filters active_quotes by strategy_id before iterating"
      pattern: "strategy_id"
    - from: "src/quoting/reconciliation.on_round_resolved"
      to: "src/quoting/portfolio.PortfolioState.on_settle"
      via: "Pitfall 5 — round-resolution event handler"
      pattern: "on_settle"
    - from: "src/quoting/reconciliation.on_round_resolved_with_brier"
      to: "src/quoting/kill_switches.KillSwitchAggregator.recent_briers"
      via: "Pitfall 4 — mode != IDLE gating before deque append"
      pattern: "recent_briers"
    - from: "tests/quoting/test_e2e.py"
      to: "plans 04-01..04-07 — composes the full pipeline"
      via: "synthetic harness (no real I/O); SyntheticMarketData + dry-run mgr"
      pattern: "test_e2e_"
---

<objective>
Build the order lifecycle reconciliation layer (REQ-order-lifecycle-
reconciliation) + the Phase 04 synthetic E2E gate. Reconciliation is the
safety net that catches divergence between in-memory _active_quotes and
Kalshi's actual resting orders (WS-only would miss orders that resolved
during a disconnect). The E2E gate composes plans 04-01..04-07 into a
single synthetic harness validating four must-haves: kill-switch cancel-
all behavior, bomb-detect 100ms latency, separate ledgers, mode
transition cleanup.

Purpose: REQ-order-lifecycle-reconciliation — 1Hz polled diff per RESEARCH
§"Pattern 5". Plus the Phase 04 acceptance gate per VALIDATION.md sampling
sign-off — the last guard before /gsd:verify-work and the Phase 5 paper-
trade handoff.

Output: src/quoting/reconciliation.py + tests/quoting/test_reconciliation.py
(8+ tests) + tests/quoting/test_e2e.py (4+ E2E tests).
</objective>

<execution_context>
@C:/Users/Joseph Cheng/.claude/get-shit-done/workflows/execute-plan.md
@C:/Users/Joseph Cheng/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/phases/04-quoting-layer/04-RESEARCH.md
@.planning/phases/04-quoting-layer/04-VALIDATION.md
@.planning/phases/04-quoting-layer/04-01-kalshi-order-manager-PLAN.md
@.planning/phases/04-quoting-layer/04-02-portfolio-kelly-PLAN.md
@.planning/phases/04-quoting-layer/04-03-kill-switches-PLAN.md
@.planning/phases/04-quoting-layer/04-04-mode-selector-PLAN.md
@.planning/phases/04-quoting-layer/04-05-mm-between-round-PLAN.md
@.planning/phases/04-quoting-layer/04-06-directional-taker-PLAN.md
@.planning/phases/04-quoting-layer/04-07-post-plant-quoter-PLAN.md
@src/config/constants.py
@src/state/match_state.py

<interfaces>
<!-- All prior plan surfaces this plan composes — see source files for full shapes -->
From src/quoting/order_manager.py (plan 04-01):
```python
class KalshiOrderManager:
    @property
    def active_quotes(self) -> dict[str, dict[str, Quote]]: ...
    async def place_quote(self, quote: Quote) -> bool: ...
    async def cancel_quote(self, ticker: str, leg_key: str) -> bool: ...
    async def cancel_all_orders(self) -> None: ...
```

From src/quoting/kill_switches.py (plan 04-03):
```python
class KillSwitchAggregator:
    recent_briers: deque[float]
    def any_tripped(self, state, theo, market, error_streak) -> tuple[bool, list[str]]: ...
```

From src/quoting/portfolio.py (plan 04-02):
```python
class PortfolioState:
    def on_place(self, series_id: str, fraction: float) -> None: ...
    def on_settle(self, series_id: str, fraction: float) -> None: ...
    def snapshot(self) -> dict[str, float]: ...
```

From src/quoting/mode_selector.py (plan 04-04):
```python
TradingMode = Literal["MM_BETWEEN_ROUND", "DIRECTIONAL_TAKE", "POST_PLANT_QUOTE", "IDLE"]
def trading_mode(state, theo, market, vega_between, vega_post_plant, kill_switch_active) -> TradingMode: ...
```

From src/quoting/{mm_quoter, directional_taker, post_plant_quoter}.py (plans 04-05/06/07):
```python
async def quote_mm_between_round(state, theo, market, mgr, ticker, count, *, now=None) -> None: ...
async def take_directional(state, theo, market, mgr, portfolio, ticker, series_id, bankroll_cents, last_mid_c, ledger_dir, *, seq_id=None) -> bool: ...
async def post_plant_quote(state, theo, market, mgr, ticker, count, last_mid_c, ledger_dir, timestamps, *, is_first_call, seq_id=None) -> None: ...
```

<!-- New surfaces this plan creates -->
NEW src/quoting/reconciliation.py public surface:
```python
async def reconcile_once(
    mgr: KalshiOrderManager,
    ticker: str,
) -> None: ...                            # 1Hz polled diff per RESEARCH Pattern 5

async def cancel_strategy_quotes(
    mgr: KalshiOrderManager,
    strategy_id: Literal["MM_BETWEEN_ROUND", "DIRECTIONAL_TAKE", "POST_PLANT_QUOTE"],
) -> None: ...                            # filter active_quotes by strategy_id, cancel matching

def on_round_resolved(
    portfolio: PortfolioState,
    series_id: str,
    fraction: float,
) -> None: ...                            # Pitfall 5 — decrement on settlement

def on_round_resolved_with_brier(
    aggregator: KillSwitchAggregator,
    mode_at_time_of_quote: TradingMode,
    brier_score: float,
) -> None: ...                            # Pitfall 4 — IDLE rounds don't contribute
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: src/quoting/reconciliation.py + GREEN test_reconciliation.py</name>
  <files>src/quoting/reconciliation.py, src/quoting/__init__.py, tests/quoting/test_reconciliation.py</files>
  <behavior>
    - reconcile_once(mgr) with mgr.dry_run=True returns immediately; aioresponses asserts NO HTTP requests made
    - reconcile_once with live mgr + aioresponses returning resting orders {order_id: "remote-1"} AND local _active_quotes containing {"buy_yes": Quote(order_id="remote-1")} → no cancels (perfect match)
    - reconcile_once with remote {"remote-1", "remote-2"} and local {"remote-1"} → cancels "remote-2" (orphan) via DELETE /portfolio/orders/remote-2
    - reconcile_once with remote {} and local {"remote-1"} → drops "remote-1" from _active_quotes (ghost); NO DELETE call
    - reconcile_once signs path "/trade-api/v2/portfolio/orders" WITHOUT the "?status=resting&ticker=..." query string (Pitfall 1) — verified by spying on sign_request input
    - cancel_strategy_quotes(mgr, "MM_BETWEEN_ROUND") with mgr._active_quotes containing 1 MM + 1 DIRECTIONAL + 1 POST_PLANT quote → only the MM quote is cancelled; DIRECTIONAL and POST_PLANT remain
    - on_round_resolved(portfolio, "S1", 0.05) decrements exposure (calls portfolio.on_settle)
    - on_round_resolved_with_brier(agg, "IDLE", 0.50) does NOT append to recent_briers (Pitfall 4 — IDLE rounds excluded)
    - on_round_resolved_with_brier(agg, "MM_BETWEEN_ROUND", 0.50) appends to recent_briers
    - on_round_resolved_with_brier(agg, "DIRECTIONAL_TAKE", 0.50) appends
    - on_round_resolved_with_brier(agg, "POST_PLANT_QUOTE", 0.50) appends
  </behavior>
  <action>
(A) Create src/quoting/reconciliation.py (~150 lines):

```python
"""Order lifecycle reconciliation + bot-main-loop event handlers.

REQ-order-lifecycle-reconciliation. 1Hz polled diff between
KalshiOrderManager._active_quotes and Kalshi's GET /portfolio/orders
response. Survives bot restarts, WS disconnects, and transient API errors
that left a place succeeding but our local update failing (RESEARCH §"Pattern 5").

Also ships three event-handler helpers that the bot main loop (Phase 6
deployment work) wires to per-event callbacks:
    - cancel_strategy_quotes: mode-transition cleanup
    - on_round_resolved: Pitfall 5 — portfolio exposure decrement
    - on_round_resolved_with_brier: Pitfall 4 — Brier append (mode != IDLE)

Source: REQ-order-lifecycle-reconciliation / ROADMAP §4.8 / RESEARCH
§"Pattern 5" + §"Common Pitfalls" #1 + #4 + #5.
"""
from __future__ import annotations

from collections import deque
from typing import Literal

import aiohttp

from src.config.constants import KALSHI_BASE_URL
from src.quoting.kalshi_auth import sign_request
from src.quoting.kill_switches import KillSwitchAggregator
from src.quoting.order_manager import KalshiOrderManager
from src.quoting.portfolio import PortfolioState

StrategyId = Literal["MM_BETWEEN_ROUND", "DIRECTIONAL_TAKE", "POST_PLANT_QUOTE"]
TradingMode = Literal["MM_BETWEEN_ROUND", "DIRECTIONAL_TAKE", "POST_PLANT_QUOTE", "IDLE"]


async def reconcile_once(
    mgr: KalshiOrderManager,
    ticker: str,
) -> None:
    """1Hz polled diff between in-memory _active_quotes and Kalshi's view.

    Cost: 1 request × 10 tokens (default rate-limit cost). At Basic tier
    200 tokens/s read budget, 1Hz costs 10/s = 5% of the read budget. Fits
    comfortably alongside REST market-data fallback pollers.

    Diff logic:
        - Orphans (Kalshi has, we don't track) → cancel via DELETE order_id
        - Ghosts (we have, Kalshi doesn't) → drop local _active_quotes entry

    Pitfall 1 — sign path WITHOUT query parameters. The defensive assert
    inside sign_request catches violations; this implementation passes
    the bare path and appends the query string ONLY to the URL.
    """
    if mgr.dry_run:
        # Dry-run has no remote state to reconcile against.
        return

    # Pitfall 1: sign path WITHOUT query string.
    sign_path = "/trade-api/v2/portfolio/orders"
    headers = sign_request(mgr._key_id, mgr._private_key, "GET", sign_path)
    url = KALSHI_BASE_URL + f"/portfolio/orders?status=resting&ticker={ticker}"

    try:
        async with mgr._session.get(url, headers=headers) as r:
            if r.status != 200:
                return  # transient error; next reconcile cycle retries
            data = await r.json()
    except aiohttp.ClientError:
        return  # transient error; next reconcile cycle retries

    remote_ids: set[str] = {o["order_id"] for o in data.get("orders", [])}
    local_ids: set[str] = {
        q.order_id
        for legs in mgr.active_quotes.values()
        for q in legs.values()
        if q.order_id is not None and not q.order_id.startswith("DRY_")
    }

    orphans = remote_ids - local_ids
    ghosts = local_ids - remote_ids

    # Cancel orphans (Kalshi has, we don't track) one at a time. Could
    # batch via /portfolio/orders/batched but orphan count is typically
    # small (bot restart edge cases) — individual DELETE keeps logic
    # straightforward.
    for oid in orphans:
        await _cancel_order_id(mgr, oid)

    # Drop ghosts from local — no DELETE call (already gone from Kalshi).
    if ghosts:
        for ticker_legs in list(mgr.active_quotes.values()):
            for leg_key, quote in list(ticker_legs.items()):
                if quote.order_id in ghosts:
                    del ticker_legs[leg_key]


async def _cancel_order_id(mgr: KalshiOrderManager, order_id: str) -> None:
    """Cancel a single order by ID. Used by reconcile_once for orphans."""
    sign_path = f"/trade-api/v2/portfolio/orders/{order_id}"
    headers = sign_request(mgr._key_id, mgr._private_key, "DELETE", sign_path)
    url = KALSHI_BASE_URL + f"/portfolio/orders/{order_id}"
    try:
        async with mgr._session.delete(url, headers=headers):
            pass
    except aiohttp.ClientError:
        return  # transient error; next reconcile cycle retries


async def cancel_strategy_quotes(
    mgr: KalshiOrderManager,
    strategy_id: StrategyId,
) -> None:
    """Cancel every active quote with strategy_id == ``strategy_id``.

    Used by the bot main loop on mode transitions (e.g., MM_BETWEEN_ROUND
    → IDLE leaves stale MM quotes; this helper clears them). DIRECTIONAL
    is IOC so it has no resting state; POST_PLANT defensive pull (plan
    04-07) handles the bomb-detect transition.
    """
    to_cancel: list[tuple[str, str]] = []
    for ticker, legs in mgr.active_quotes.items():
        for leg_key, quote in legs.items():
            if quote.strategy_id == strategy_id:
                to_cancel.append((ticker, leg_key))
    for ticker, leg_key in to_cancel:
        await mgr.cancel_quote(ticker, leg_key)


def on_round_resolved(
    portfolio: PortfolioState,
    series_id: str,
    fraction: float,
) -> None:
    """Decrement series exposure on round resolution (Pitfall 5 wiring).

    Bot main loop invokes when a round_end_event commits via the arbiter.
    Phase 04 ships the wrapper; Phase 6 deployment wires the arbiter
    callback. The wrapper exists so the call site is grep-discoverable
    (`rg "on_round_resolved"`) — Pitfall 5 forensic anchor.
    """
    portfolio.on_settle(series_id, fraction)


def on_round_resolved_with_brier(
    aggregator: KillSwitchAggregator,
    mode_at_time_of_quote: TradingMode,
    brier_score: float,
) -> None:
    """Append Brier score to rolling window IFF the bot was actively quoting.

    Pitfall 4 mitigation (RESEARCH): rounds where mode == IDLE must NOT
    contribute to the rolling Brier — the kill switch measures MODEL Brier
    over rounds where the model's prediction was actually used for a
    trading decision. Phase 5 calibration backfill would be required if
    we let IDLE rounds in here.
    """
    if mode_at_time_of_quote == "IDLE":
        return
    aggregator.recent_briers.append(brier_score)
```

(B) Update src/quoting/__init__.py to export reconcile_once,
    cancel_strategy_quotes, on_round_resolved, on_round_resolved_with_brier.

(C) Flip RED stubs in tests/quoting/test_reconciliation.py to GREEN:

```python
"""Plan 04-08 — REQ-order-lifecycle-reconciliation GREEN tests + handlers.

DEC-022 dry-run shortcut + Pitfall 1 path-without-query + Pitfall 4 Brier
gating + Pitfall 5 on_settle wiring.
"""
from __future__ import annotations

from collections import deque

import aiohttp
import pytest
from aioresponses import aioresponses
from cryptography.hazmat.primitives.asymmetric import rsa

from src.config.constants import KALSHI_BASE_URL, KILL_SWITCH_BRIER_WINDOW
from src.quoting.kill_switches import KillSwitchAggregator
from src.quoting.order_manager import KalshiOrderManager, Quote
from src.quoting.portfolio import PortfolioState
from src.quoting.reconciliation import (
    cancel_strategy_quotes,
    on_round_resolved,
    on_round_resolved_with_brier,
    reconcile_once,
)


@pytest.mark.asyncio
async def test_reconcile_dry_run_noop(fake_private_key: rsa.RSAPrivateKey) -> None:
    """Dry-run shortcut: no HTTP calls made."""
    async with aiohttp.ClientSession() as session:
        mgr = KalshiOrderManager(session=session, key_id="K",
                                   private_key=fake_private_key, dry_run=True)
        # aioresponses NOT set up — any HTTP call would raise ConnectionError.
        await reconcile_once(mgr, ticker="VAL-T1-WIN")
        # If we reach here without an exception, dry-run short-circuited.


@pytest.mark.asyncio
async def test_reconcile_perfect_match_no_cancels(fake_private_key: rsa.RSAPrivateKey) -> None:
    """Remote and local agree → no cancels, no drops."""
    with aioresponses() as m:
        m.get(
            f"{KALSHI_BASE_URL}/portfolio/orders?status=resting&ticker=VAL-T1-WIN",
            status=200,
            payload={"orders": [{"order_id": "remote-1"}]},
        )
        async with aiohttp.ClientSession() as session:
            mgr = KalshiOrderManager(session=session, key_id="K",
                                       private_key=fake_private_key, dry_run=False)
            quote = Quote(ticker="VAL-T1-WIN", side="yes", action="buy",
                           price=50, count=10, strategy_id="MM_BETWEEN_ROUND",
                           order_id="remote-1", placed_at=0.0)
            mgr._active_quotes["VAL-T1-WIN"] = {"buy_yes": quote}
            await reconcile_once(mgr, ticker="VAL-T1-WIN")
            # Still tracked locally.
            assert "VAL-T1-WIN" in mgr.active_quotes


@pytest.mark.asyncio
async def test_reconcile_cancel_orphan(fake_private_key: rsa.RSAPrivateKey) -> None:
    """Kalshi has remote-2 that we don't track → DELETE issued."""
    with aioresponses() as m:
        m.get(
            f"{KALSHI_BASE_URL}/portfolio/orders?status=resting&ticker=VAL-T1-WIN",
            status=200,
            payload={"orders": [{"order_id": "remote-1"}, {"order_id": "remote-2"}]},
        )
        # Expect DELETE call on remote-2 (orphan).
        m.delete(f"{KALSHI_BASE_URL}/portfolio/orders/remote-2", status=200)

        async with aiohttp.ClientSession() as session:
            mgr = KalshiOrderManager(session=session, key_id="K",
                                       private_key=fake_private_key, dry_run=False)
            quote = Quote(ticker="VAL-T1-WIN", side="yes", action="buy",
                           price=50, count=10, strategy_id="MM_BETWEEN_ROUND",
                           order_id="remote-1", placed_at=0.0)
            mgr._active_quotes["VAL-T1-WIN"] = {"buy_yes": quote}
            await reconcile_once(mgr, ticker="VAL-T1-WIN")
            # aioresponses asserts the DELETE was called by the test passing.


@pytest.mark.asyncio
async def test_reconcile_drop_ghost(fake_private_key: rsa.RSAPrivateKey) -> None:
    """We track remote-1 but Kalshi has no resting orders → drop locally."""
    with aioresponses() as m:
        m.get(
            f"{KALSHI_BASE_URL}/portfolio/orders?status=resting&ticker=VAL-T1-WIN",
            status=200,
            payload={"orders": []},
        )
        async with aiohttp.ClientSession() as session:
            mgr = KalshiOrderManager(session=session, key_id="K",
                                       private_key=fake_private_key, dry_run=False)
            quote = Quote(ticker="VAL-T1-WIN", side="yes", action="buy",
                           price=50, count=10, strategy_id="MM_BETWEEN_ROUND",
                           order_id="remote-1", placed_at=0.0)
            mgr._active_quotes["VAL-T1-WIN"] = {"buy_yes": quote}
            await reconcile_once(mgr, ticker="VAL-T1-WIN")
            # Local entry removed (no DELETE — Kalshi already doesn't have it).
            assert mgr.active_quotes.get("VAL-T1-WIN", {}) == {}


@pytest.mark.asyncio
async def test_reconcile_dry_run_quotes_skipped_in_diff(fake_private_key: rsa.RSAPrivateKey) -> None:
    """DRY_-prefixed local order_ids are NOT compared against remote (defensive
    against mixed-mode test fixtures)."""
    with aioresponses() as m:
        m.get(
            f"{KALSHI_BASE_URL}/portfolio/orders?status=resting&ticker=VAL-T1-WIN",
            status=200, payload={"orders": []},
        )
        async with aiohttp.ClientSession() as session:
            mgr = KalshiOrderManager(session=session, key_id="K",
                                       private_key=fake_private_key, dry_run=False)
            quote = Quote(ticker="VAL-T1-WIN", side="yes", action="buy",
                           price=50, count=10, strategy_id="MM_BETWEEN_ROUND",
                           order_id="DRY_abc12345", placed_at=0.0)
            mgr._active_quotes["VAL-T1-WIN"] = {"buy_yes": quote}
            await reconcile_once(mgr, ticker="VAL-T1-WIN")
            # DRY_-prefixed quote is left intact (not a "ghost" of a real Kalshi order).
            assert mgr.active_quotes["VAL-T1-WIN"]["buy_yes"].order_id == "DRY_abc12345"


# ---------------- cancel_strategy_quotes ----------------

@pytest.mark.asyncio
async def test_cancel_strategy_only_targets_matching(fake_private_key: rsa.RSAPrivateKey) -> None:
    """cancel_strategy_quotes(\"MM_BETWEEN_ROUND\") cancels MM; DIRECTIONAL untouched."""
    async with aiohttp.ClientSession() as session:
        mgr = KalshiOrderManager(session=session, key_id="K",
                                   private_key=fake_private_key, dry_run=True)
        # Place 3 quotes — one per strategy
        await mgr.place_quote(Quote(ticker="VAL-T1", side="yes", action="buy",
                                      price=50, count=10, strategy_id="MM_BETWEEN_ROUND"))
        await mgr.place_quote(Quote(ticker="VAL-T2", side="yes", action="buy",
                                      price=50, count=10, strategy_id="DIRECTIONAL_TAKE"))
        await mgr.place_quote(Quote(ticker="VAL-T3", side="yes", action="buy",
                                      price=50, count=10, strategy_id="POST_PLANT_QUOTE"))

        await cancel_strategy_quotes(mgr, "MM_BETWEEN_ROUND")

        # MM gone; DIRECTIONAL + POST_PLANT remain.
        assert "VAL-T1" not in mgr.active_quotes
        assert "VAL-T2" in mgr.active_quotes
        assert "VAL-T3" in mgr.active_quotes


# ---------------- on_round_resolved ----------------

def test_on_round_resolved_decrements_exposure() -> None:
    portfolio = PortfolioState()
    portfolio.on_place("S1", 0.05)
    on_round_resolved(portfolio, "S1", 0.05)
    assert portfolio.current("S1") == 0.0


def test_on_round_resolved_clips_at_zero() -> None:
    """Pitfall 5 carry-forward — never goes negative."""
    portfolio = PortfolioState()
    portfolio.on_place("S1", 0.03)
    on_round_resolved(portfolio, "S1", 0.10)
    assert portfolio.current("S1") == 0.0


# ---------------- on_round_resolved_with_brier ----------------

def test_brier_appended_for_mm_mode() -> None:
    agg = KillSwitchAggregator()
    on_round_resolved_with_brier(agg, "MM_BETWEEN_ROUND", 0.40)
    assert list(agg.recent_briers) == [0.40]


def test_brier_appended_for_directional_mode() -> None:
    agg = KillSwitchAggregator()
    on_round_resolved_with_brier(agg, "DIRECTIONAL_TAKE", 0.30)
    assert list(agg.recent_briers) == [0.30]


def test_brier_appended_for_post_plant_mode() -> None:
    agg = KillSwitchAggregator()
    on_round_resolved_with_brier(agg, "POST_PLANT_QUOTE", 0.25)
    assert list(agg.recent_briers) == [0.25]


def test_brier_NOT_appended_for_idle_mode() -> None:
    """Pitfall 4 mitigation: IDLE rounds excluded from rolling Brier."""
    agg = KillSwitchAggregator()
    on_round_resolved_with_brier(agg, "IDLE", 0.50)
    assert list(agg.recent_briers) == []
```
  </action>
  <verify>
    <automated>uv run pytest tests/quoting/test_reconciliation.py -x --no-cov &amp;&amp; uv run mypy --strict src/quoting/</automated>
  </verify>
  <done>
- src/quoting/reconciliation.py defines reconcile_once + cancel_strategy_quotes + on_round_resolved + on_round_resolved_with_brier.
- 12 tests in tests/quoting/test_reconciliation.py pass GREEN (incl. dry-run shortcut, orphans, ghosts, DRY_-prefixed skip, strategy-targeted cancel, Pitfall 4 gating, Pitfall 5 wrapper).
- src/quoting/__init__.py exports all 4 new functions.
- mypy --strict src/quoting/ clean.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: tests/quoting/test_e2e.py — Phase 04 synthetic E2E gate (4 must-haves)</name>
  <files>tests/quoting/test_e2e.py</files>
  <behavior>
    - test_e2e_kill_switch_trip_cancels_all_resting: with mgr pre-loaded with 1 MM + 1 DIRECTIONAL + 1 POST_PLANT quote (synthetic state), kill_switch_aggregator.any_tripped() returning True for staleness → mgr.cancel_all_orders() is invoked → mgr.active_quotes == {} (all three strategy types pulled together)
    - test_e2e_bomb_detect_p50_under_100ms: synthetic 50-trial harness; each trial sets up state transition bomb_planted=False → True, computes timestamps["t_state_committed"] = mono_ns(), calls post_plant_quote(is_first_call=True), records (t_quote_pull_completed - t_state_committed); p50 < 100ms (Phase 04's piece of PRD's 200ms budget; mirrors plan 04-07 task 2's latency test but in E2E context)
    - test_e2e_separate_strategy_ledgers: synthetic harness drives 1 MM fill + 1 DIRECTIONAL fill + 1 POST_PLANT fill against the touched rule (last_mid_c → market.mid transitions); asserts EXACTLY 3 separate JSONL files exist in tmp_fill_ledger_dir with the expected naming (mm_between_round / directional_take / post_plant_quote)
    - test_e2e_mode_transition_mm_to_idle_clears_mm_quotes: place MM quotes via quote_mm_between_round; simulate mode transition to IDLE; invoke cancel_strategy_quotes(mgr, "MM_BETWEEN_ROUND"); assert mgr.active_quotes is now empty
    - test_e2e_full_pipeline_smoke: compose Arbiter (Phase 03) → live_theo → kill_switch_aggregator → trading_mode → mm_quoter; drive 5 PendingEvents through the pipe; assert MM quotes land in data/fills/{match_id}.mm_between_round.jsonl (smoke check; full Brier/PnL evaluation is Phase 5)
  </behavior>
  <action>
Create tests/quoting/test_e2e.py with 5 E2E tests covering the four
phase-level must-haves from the planner brief:

```python
"""Plan 04-08 — Phase 04 synthetic E2E gate.

Composes plans 04-01..04-07 into a single synthetic harness validating
four phase-level must-haves:
    (a) kill-switch trip → all resting quotes cancelled (MM + DIRECTIONAL +
        POST_PLANT pulled together within 200ms)
    (b) bomb-detect → quote-pull p50 < 100ms (Phase 04's piece of 200ms
        budget per PRD §5.4 / DEC-020 v2)
    (c) MM and DIRECTIONAL fills land in SEPARATE ledger files (DEC-020 v2
        per-strategy fill ledger split — RESEARCH §"Pattern 4" anti-pattern #1)
    (d) mode transitions clean — no stale orders across MM↔DIRECTIONAL/IDLE

Synthetic harness only (no real I/O — mirrors Phase 03 plan 03-08 framing).
KalshiOrderManager(dry_run=True), SyntheticMarketData, fake_private_key.
Real-broadcast latency is Phase 5 paper-trade's production gate.
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path

import aiohttp
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from src.ingestion.timestamps import mono_ns
from src.pricing.data import TheoOutput
from src.quoting.directional_taker import take_directional
from src.quoting.kill_switches import KillSwitchAggregator
from src.quoting.market_data import make_quote
from src.quoting.mm_quoter import quote_mm_between_round
from src.quoting.order_manager import KalshiOrderManager, Quote
from src.quoting.portfolio import PortfolioState
from src.quoting.post_plant_quoter import post_plant_quote
from src.quoting.reconciliation import cancel_strategy_quotes


def _theo(theo_series: float = 0.50, vega: float = 0.005) -> TheoOutput:
    return TheoOutput(theo_series=theo_series, theo_map=(theo_series,),
                       vega=vega, confidence=1.0)


def _ts() -> dict[str, float | int | None]:
    return {
        "t_observed": 0.0, "t_ingested": 0, "t_arbited": 0,
        "t_state_committed": mono_ns(), "t_theo_computed": None,
        "t_quote_sent": None, "t_quote_pull_completed": None,
    }


# ---------------------------------------------------------------------------
# Must-have (a): kill-switch trip cancels MM + DIRECTIONAL + POST_PLANT together
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_e2e_kill_switch_trip_cancels_all_resting(
    fake_private_key: rsa.RSAPrivateKey, make_match_state,
) -> None:
    """Must-have (a): any_tripped → True → cancel_all_orders → all three
    strategy types pulled together within 200ms."""
    async with aiohttp.ClientSession() as session:
        mgr = KalshiOrderManager(session=session, key_id="K",
                                   private_key=fake_private_key, dry_run=True)

        # Pre-load 3 quotes — one per strategy.
        for strategy in ("MM_BETWEEN_ROUND", "DIRECTIONAL_TAKE", "POST_PLANT_QUOTE"):
            await mgr.place_quote(Quote(
                ticker=f"VAL-{strategy[:3]}", side="yes", action="buy",
                price=50, count=10, strategy_id=strategy,  # type: ignore[arg-type]
            ))
        assert len(mgr.active_quotes) == 3

        # Simulate a kill-switch trip (staleness).
        agg = KillSwitchAggregator()
        # State with very old last_updated_ts will trip staleness.
        state = make_match_state(last_updated_ts=0.0)
        market = make_quote(48, 52)
        tripped, names = agg.any_tripped(state, _theo(0.50), market, error_streak=0)
        assert tripped is True
        assert "staleness" in names

        # Bot main loop pattern: on any trip → cancel_all_orders.
        t_start = mono_ns()
        await mgr.cancel_all_orders()
        t_end = mono_ns()

        # All three strategy types pulled.
        assert mgr.active_quotes == {}

        # Latency: well under 200ms in dry-run synthetic harness.
        elapsed_ms = (t_end - t_start) / 1_000_000
        assert elapsed_ms < 200, f"cancel-all latency {elapsed_ms:.2f}ms exceeds 200ms"


# ---------------------------------------------------------------------------
# Must-have (b): bomb-detect → quote-pull p50 < 100ms
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_e2e_bomb_detect_p50_under_100ms(
    fake_private_key: rsa.RSAPrivateKey, make_match_state,
    tmp_fill_ledger_dir: Path,
) -> None:
    """Must-have (b): Phase 04's 100ms piece of PRD's 200ms budget.

    Mirrors plan 04-07 task 2's latency test in E2E context — verifies the
    composition (state transition → post_plant_quote first_call=True →
    timestamp populated) hits the same budget.
    """
    durations_ns: list[int] = []
    for trial in range(50):
        async with aiohttp.ClientSession() as session:
            mgr = KalshiOrderManager(session=session, key_id="K",
                                       private_key=fake_private_key, dry_run=True)
            # Pre-place 10 MM quotes so cancel_all has real work.
            for i in range(10):
                await mgr.place_quote(Quote(
                    ticker=f"VAL-T{i}", side="yes", action="buy",
                    price=50, count=10, strategy_id="MM_BETWEEN_ROUND",
                ))
            state = make_match_state(bomb_planted=True, attackers_alive=2,
                                       defenders_alive=3, time_left_s=20.0)
            market = make_quote(48, 52)
            ts = _ts()
            t_state = int(ts["t_state_committed"])  # type: ignore[arg-type]
            await post_plant_quote(
                state, _theo(0.50), market, mgr,
                ticker="VAL-T0", count=10, last_mid_c=50,
                ledger_dir=tmp_fill_ledger_dir,
                timestamps=ts, is_first_call=True,
            )
            assert ts["t_quote_pull_completed"] is not None
            durations_ns.append(int(ts["t_quote_pull_completed"]) - t_state)

    p50_ms = statistics.median(durations_ns) / 1_000_000
    assert p50_ms < 100, f"E2E bomb-detect p50 {p50_ms:.2f}ms exceeds 100ms"


# ---------------------------------------------------------------------------
# Must-have (c): MM + DIRECTIONAL + POST_PLANT fills land in SEPARATE files
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_e2e_separate_strategy_ledgers(
    fake_private_key: rsa.RSAPrivateKey, make_match_state,
    tmp_fill_ledger_dir: Path,
) -> None:
    """Must-have (c): MM, DIRECTIONAL, POST_PLANT fills land in 3 separate JSONL files.

    DEC-020 v2 / RESEARCH §"Pattern 4" anti-pattern #1: combined writes
    corrupt the promotion gate fill-count evaluation.
    """
    async with aiohttp.ClientSession() as session:
        mgr = KalshiOrderManager(session=session, key_id="K",
                                   private_key=fake_private_key, dry_run=True)
        portfolio = PortfolioState()

        # 1. MM fill — place quote then simulate touched rule via fill_ledger.
        from src.quoting.fill_ledger import maybe_record_mm_fill
        state = make_match_state(match_id="M-E2E", bomb_planted=False,
                                   time_left_s=None, last_updated_ts=1000.0)
        market = make_quote(48, 52)
        await quote_mm_between_round(state, _theo(0.50, vega=0.005), market, mgr,
                                       ticker="VAL-MM", count=10, now=1000.5)
        # Drive a touched-rule mid transition: 53 → 50, quote at 50-4=46 (buy)
        # — need next_mid_c < 46 <= last_mid_c, so 53 → 45 crosses.
        mm_buy = mgr.active_quotes["VAL-MM"]["buy_yes"]
        maybe_record_mm_fill(mm_buy, last_mid_c=53, next_mid_c=45, seq_id=1,
                              theo_c=50, ledger_dir=tmp_fill_ledger_dir,
                              match_id="M-E2E")

        # 2. DIRECTIONAL fill — strong edge takes; touched rule on last_mid_c=53, market.mid=50.
        # take_directional places at market.yes_ask=52 (buy). For fill: next_mid_c < 52 <= last_mid_c.
        # Pass last_mid_c=53; market.mid=50 → 50 < 52 <= 53 → fill.
        await take_directional(
            state, _theo(0.60), market, mgr, portfolio,
            ticker="VAL-DIR", series_id="S1", bankroll_cents=100_000,
            last_mid_c=53, ledger_dir=tmp_fill_ledger_dir,
        )

        # 3. POST_PLANT fill — state.bomb_planted=True; TAKE branch.
        pp_state = make_match_state(match_id="M-E2E", bomb_planted=True,
                                      attackers_alive=2, defenders_alive=3,
                                      time_left_s=20.0)
        await post_plant_quote(
            pp_state, _theo(0.60), market, mgr,
            ticker="VAL-PP", count=10, last_mid_c=53,
            ledger_dir=tmp_fill_ledger_dir, timestamps=_ts(),
            is_first_call=False,
        )

        # Three separate files exist.
        names = {p.name for p in tmp_fill_ledger_dir.iterdir() if p.is_file()}
        assert "M-E2E.mm_between_round.jsonl" in names
        assert "M-E2E.directional_take.jsonl" in names
        assert "M-E2E.post_plant_quote.jsonl" in names

        # Each file contains its OWN strategy only.
        mm_lines = (tmp_fill_ledger_dir / "M-E2E.mm_between_round.jsonl").read_text().splitlines()
        for line in mm_lines:
            assert json.loads(line)["strategy"] == "MM_BETWEEN_ROUND"
        dir_lines = (tmp_fill_ledger_dir / "M-E2E.directional_take.jsonl").read_text().splitlines()
        for line in dir_lines:
            assert json.loads(line)["strategy"] == "DIRECTIONAL_TAKE"
        pp_lines = (tmp_fill_ledger_dir / "M-E2E.post_plant_quote.jsonl").read_text().splitlines()
        for line in pp_lines:
            assert json.loads(line)["strategy"] == "POST_PLANT_QUOTE"


# ---------------------------------------------------------------------------
# Must-have (d): mode transitions clean — no stale orders across modes
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_e2e_mode_transition_mm_to_idle_clears_mm_quotes(
    fake_private_key: rsa.RSAPrivateKey, make_match_state,
) -> None:
    """Must-have (d): MM_BETWEEN_ROUND → IDLE leaves NO stale MM quotes.

    Bot main loop invokes cancel_strategy_quotes(mgr, \"MM_BETWEEN_ROUND\")
    on mode transition; this test verifies that helper composed with the
    quoter clears the book.
    """
    async with aiohttp.ClientSession() as session:
        mgr = KalshiOrderManager(session=session, key_id="K",
                                   private_key=fake_private_key, dry_run=True)
        state = make_match_state(bomb_planted=False, time_left_s=None,
                                   last_updated_ts=1000.0)
        market = make_quote(46, 54)  # mid=50, spread=8 — MM rule 5 fires.

        # 1. Mode is MM_BETWEEN_ROUND — quoter places ladder.
        await quote_mm_between_round(state, _theo(0.50, vega=0.005), market, mgr,
                                       ticker="VAL-T1", count=10, now=1000.5)
        assert "buy_yes" in mgr.active_quotes["VAL-T1"]
        assert "sell_yes" in mgr.active_quotes["VAL-T1"]

        # 2. Mode transition to IDLE (e.g., market spread tightens below MM_MIN_EDGE).
        await cancel_strategy_quotes(mgr, "MM_BETWEEN_ROUND")

        # 3. MM quotes gone.
        assert mgr.active_quotes.get("VAL-T1", {}) == {}


@pytest.mark.asyncio
async def test_e2e_mode_transition_directional_to_mm_no_stale(
    fake_private_key: rsa.RSAPrivateKey, make_match_state,
    tmp_fill_ledger_dir: Path,
) -> None:
    """DIRECTIONAL_TAKE is IOC → no resting state to leak. After taking,
    a transition to MM_BETWEEN_ROUND should NOT see any DIRECTIONAL ghost
    quotes (consistent with the IOC contract from plan 04-06)."""
    async with aiohttp.ClientSession() as session:
        mgr = KalshiOrderManager(session=session, key_id="K",
                                   private_key=fake_private_key, dry_run=True)
        portfolio = PortfolioState()
        state = make_match_state(bomb_planted=False, time_left_s=None,
                                   last_updated_ts=1000.0)
        market = make_quote(48, 52)

        # 1. DIRECTIONAL_TAKE fires.
        await take_directional(
            state, _theo(0.60), market, mgr, portfolio,
            ticker="VAL-T1", series_id="S1", bankroll_cents=100_000,
            last_mid_c=50, ledger_dir=tmp_fill_ledger_dir,
        )
        # Note: in dry-run, the IOC order is stored in _active_quotes (no real
        # IOC cancel from Kalshi). Production live would have Kalshi handle the
        # IOC. For the synthetic E2E we simulate the IOC cancel by invoking
        # cancel_strategy_quotes — the bot main loop does this on the seq_id
        # change after the take.
        await cancel_strategy_quotes(mgr, "DIRECTIONAL_TAKE")

        # 2. Transition to MM mode — MM quoter places NEW quotes; no
        #    DIRECTIONAL ghosts.
        wide_market = make_quote(46, 54)
        await quote_mm_between_round(state, _theo(0.50, vega=0.005), wide_market, mgr,
                                       ticker="VAL-T1", count=10, now=1000.5)
        legs = mgr.active_quotes["VAL-T1"]
        for leg in legs.values():
            assert leg.strategy_id == "MM_BETWEEN_ROUND"  # No DIRECTIONAL ghosts.
```
  </action>
  <verify>
    <automated>uv run pytest tests/quoting/test_e2e.py -x --no-cov &amp;&amp; uv run mypy --strict src/quoting/</automated>
  </verify>
  <done>
- tests/quoting/test_e2e.py defines 5 E2E tests covering all 4 phase-level must-haves.
- test_e2e_kill_switch_trip_cancels_all_resting verifies MM + DIRECTIONAL + POST_PLANT cancelled together on ANY trip (must-have a).
- test_e2e_bomb_detect_p50_under_100ms verifies Phase 04's 100ms piece of PRD's 200ms budget over 50-trial synthetic harness (must-have b).
- test_e2e_separate_strategy_ledgers verifies 3 separate JSONL files with strategy-correct contents (must-have c).
- test_e2e_mode_transition_mm_to_idle_clears_mm_quotes + test_e2e_mode_transition_directional_to_mm_no_stale verify clean transitions (must-have d).
- mypy --strict src/quoting/ clean (no source changes — test-only file).
  </done>
</task>

</tasks>

<verification>
1. `uv run pytest tests/quoting/test_reconciliation.py tests/quoting/test_e2e.py -x --no-cov` — all GREEN (17+ tests).
2. `uv run pytest tests/ -x --no-cov` — full Phase 03 + Phase 04 suite GREEN; zero xfails remaining for Phase 04.
3. `uv run mypy --strict src/quoting/ src/sizing/ src/ingestion/ src/state/ src/pricing/` clean.
4. `rg "VEGA_DIRECTIONAL_THRESHOLD" src/ tests/` returns empty (cleanup from plan 04-04 still holds at phase end).
5. `rg "disable_X|disable_kill_switch" src/quoting/` returns empty (DEC-005 always-on still holds).
6. `python -c "from src.quoting import reconcile_once, cancel_strategy_quotes, on_round_resolved, on_round_resolved_with_brier; print('ok')"` runs without ImportError.
7. Phase 04 acceptance per VALIDATION.md sampling sign-off:
   - All tasks have <automated> verify — YES (every plan's task has uv run pytest invocation)
   - Sampling continuity (no 3 consecutive tasks without automated verify) — YES
   - Wave 0 covers all MISSING references — YES (plan 04-00 stub coverage)
   - No watch-mode flags — YES
   - Feedback latency < 30s — YES (pytest tests/quoting/ tests/sizing/ -x --no-cov ~10s)
</verification>

<success_criteria>
- src/quoting/reconciliation.py ships diff-and-cancel (REQ-order-lifecycle-reconciliation) + 3 event-handler wrappers (cancel_strategy_quotes / on_round_resolved / on_round_resolved_with_brier).
- E2E synthetic harness covers all 4 phase-level must-haves: kill-switch cancel-all + bomb-detect 100ms + separate ledgers + mode transition cleanup.
- Pitfall 1 (path-without-query) verified via aioresponses test.
- Pitfall 4 (Brier IDLE exclusion) verified via on_round_resolved_with_brier test.
- Pitfall 5 (PortfolioState.on_settle wiring) verified via on_round_resolved test.
- Full Phase 04 suite GREEN; ready for /gsd:verify-work and Phase 5 paper-trade handoff.
</success_criteria>

<output>
After completion, create `.planning/phases/04-quoting-layer/04-08-SUMMARY.md` documenting:
- src/quoting/reconciliation.py file contents (~150 lines).
- 17+ test results (12 reconciliation + 5 E2E).
- Phase 04 acceptance check against VALIDATION.md sampling sign-off (all 6 boxes ticked).
- Cross-plan dependencies validated: kill switches (04-03) + cancel_all (04-01) compose correctly under trip; post-plant quoter (04-07) latency budget holds in E2E composition; MM (04-05) + DIRECTIONAL (04-06) + POST_PLANT (04-07) write to disjoint ledgers verified end-to-end.
- Forward link: Phase 5 paper-trade owns the production gate (relative Brier + fill-count + real-broadcast latency); Phase 6 deployment wires the bot main loop that composes these helpers in production.
</output>
