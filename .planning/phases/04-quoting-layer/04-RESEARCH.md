# Phase 04: Quoting Layer (RESCOPED v2) — Research

**Researched:** 2026-05-09
**Domain:** Kalshi REST + WebSocket order management, three-way + IDLE mode selector, between-round MM quoting, directional taking, post-plant defensive quote-pull, portfolio-aware Kelly sizing, four kill switches, order lifecycle reconciliation, paper-trade hypothetical-fill ledgers
**Confidence:** HIGH (Kalshi API surface, RSA-PSS auth, REST + WS schemas, fee curve, mode-selector, kill-switch predicate pattern, hypothetical-fill ledger), MEDIUM (rate-limit token cost map, post-plant vega formula, MIN_HALF_SPREAD floor calibration), LOW (initial threshold values for `TAKE_THRESHOLD` / `MM_MIN_EDGE` / `POST_PLANT_TAKE_THRESHOLD` — calibrate in Phase 5)

## Summary

Phase 04 wires the four-layer architecture's last stage: ingestion (Phase 03) feeds `MatchState` → pricing (`live_theo` from Phase 1) feeds `TheoOutput` → **mode selector** is a pure function over `(state, theo, market, vega_between, vega_post_plant, kill_switch_active)` returning one of four modes → **per-mode quoter / taker** writes to a Kalshi REST + WebSocket order manager with parallel hypothetical-fill ledgers in dry-run. The phase spans `src/quoting/` (new — currently empty `__init__.py`) and `src/sizing/` (new — currently empty `__init__.py`); plus a small bootstrap of `src/quoting/order_manager.py` extending `reference/market_maker.py`'s salvageable Kalshi plumbing. **Critical correction to CLAUDE.md / PRD §11**: Kalshi auth is **RSA-PSS** with SHA256 (mgf=MGF1, salt_length=DIGEST_LENGTH), not PKCS1v15 — verified directly against `docs.kalshi.com/getting_started/api_keys` 2026-05-09. The reference `market_maker.py` is also stale on `KalshiClient` (no longer the recommended interface — official `kalshi-python` v2.1.4 ships its own `Configuration + KalshiClient`); plumbing salvage is structural patterns (Quote dataclass, _is_near_close guard, _error_streak retry loop, dry-run wrapper), not direct imports.

The phase has tight latency constraint coupling with Phase 03: bomb-detect → quote-pull p50 < 200ms is split between Phase 03's commit-side budget (≤100ms, GREEN per 03-08 synthetic harness) and Phase 04's "pull all resting MM quotes" budget (≤100ms remaining). MM-between-round vs DIRECTIONAL-take parallel ledgers are a hard architectural requirement from DEC-020 v2: paper-trade promotion gate evaluates them independently, so the order manager MUST tag each hypothetical-fill record with a strategy-id at write time — retrofitting after Phase 5 wouldn't recover the data.

**Primary recommendation:**
1. **Auth** — implement `src/quoting/kalshi_auth.py` from scratch using `cryptography.hazmat.primitives.asymmetric.padding.PSS` directly (~50 lines); do NOT pull `kalshi-python==2.1.4` as a dependency (auto-generated OpenAPI client; bloated for our 5-endpoint surface; breaks the lean `mypy --strict` posture on `src/`).
2. **Order manager** — keep `aiohttp.ClientSession` (already in pyproject from Phase 03) for REST; use `websockets>=12` for the live channel (new dep). Single async-aware `KalshiOrderManager` with explicit `dry_run: bool` constructor argument — but that argument MUST originate from `src.main.resolve_dry_run(args)` which returns the literal `True` unless `--live` was passed (CLAUDE.md rule 13).
3. **Mode selector** — pure function in `src/quoting/mode_selector.py`. Input: a `MarketQuote` dataclass + the existing `MatchState` + `TheoOutput` from Phase 1 + `vega_post_plant: float` + `kill_switch_active: bool`. Six declared rules in declared order, no early-return optimization (clarity wins). NO hidden mutable state, NO `match_state.bomb_planted` mutation. Six unit tests, one per rule branch. (`Literal[...]` return type satisfies `mypy --strict`.)
4. **Sizing** — pure function `kelly_size(theo, ask, bankroll, series_id, current_series_exposure)` in `src/sizing/kelly.py` per DEC-023 v2; the `current_series_exposure: dict[str, float]` is owned by the caller (a `PortfolioState` registry that lives in `src/quoting/`), not the sizer.
5. **Kill switches** — four pure predicates `kill_*(state, theo, market, recent_briers) -> bool` in `src/quoting/kill_switches.py` plus a `KillSwitchAggregator.any_tripped()`. Each is grep-discoverable, each has a deterministic unit test covering trip + non-trip boundary, no per-switch disable flag (DEC-005).
6. **Hypothetical-fill ledgers** — per-strategy JSONL files at `data/fills/{match_id}.{strategy_id}.jsonl` (`MM_BETWEEN_ROUND` and `DIRECTIONAL_TAKE` get separate files; `POST_PLANT_QUOTE` gets a third). Schema: one fill per line keyed on `seq_id` so it lines up with the Phase 03 metrics + event-log JSONLs for replay-driven Brier computation in Phase 5.
7. **Reconciliation** — every poll cycle (5s default per `SCOREBOARD_POLL_CADENCE_S` — but reconcile only on the 1Hz subset to stay within rate budget), GET `/portfolio/orders?status=resting&ticker=...`, diff against in-memory `_active_quotes`, cancel orphans, drop stale references.

Decompose into **8 plans** (one per ROADMAP §4 v2 sub-section) across **5 waves**. Wave dependencies follow the natural data flow: auth + order manager skeleton → mode selector + Kelly sizer (parallelizable, pure functions) → MM/directional/post-plant quoters (parallelizable, all consume the same skeleton) → kill switches + reconciliation → end-to-end paper-trade harness against Phase 03's E2E gate.

## User Constraints

(No CONTEXT.md exists for Phase 04 yet — `/gsd:discuss-phase` has not been run. The constraints below are extracted directly from ROADMAP §4 v2, REQUIREMENTS.md Phase 4 section, PRD §2.1 / §6 / §7 / §8 / §11, CLAUDE.md, and the 22 locked DEC-* decisions in PROJECT.md. They are NOT a substitute for a CONTEXT.md from a discussion session — the planner should consider whether a discussion is warranted before writing PLAN.md files.)

### Locked Decisions (from PROJECT.md DEC-001..DEC-024)

- **DEC-001 v2** — Three-way mode + IDLE; pure-function selector in declared order: kill-switch → bomb-planted → mid-round-not-planted → take-threshold → MM-min-edge → IDLE. **MM and DIRECTIONAL are first-class peers, not primary/fallback.** `VEGA_DIRECTIONAL_THRESHOLD` REMOVED — DIRECTIONAL_TAKE triggers on `|theo − market_mid|`, not vega.
- **DEC-002 / DEC-010** — Single canonical `live_theo(state) → TheoOutput`. Phase 04 imports the existing `LiveTheoEngine` from `src.pricing`; do NOT recreate any pricing math here.
- **DEC-004 / DEC-023** — Half-Kelly with two caps: per-market cap (`PER_MARKET_CAP_FRAC = 0.05`) AND per-series aggregate cap (`SERIES_AGGREGATE_CAP_FRAC = 0.10`). Returns 0 if aggregate exceeded. Full covariance Kelly is Phase 7 (REQ-portfolio-correlation-kelly).
- **DEC-005** — Four kill switches, all-on, no per-switch disable flag.
- **DEC-013** — `reference/market_maker.py` is partial salvage: extract `Quote` dataclass, `_place_quote`, `_cancel_quote`, `cancel_all_orders`, `_error_streak` retry, `_is_near_close` guard, dry-run wrapper. Skip: `_compute_quotes` (synchronous polling-loop logic obsolete), `update_market` (fetches market via REST; we receive market via Phase 03 arbiter + Kalshi WS).
- **DEC-018 v2** — `vega_between_round` (Phase 1, shipped) sizes MM quote width via `spread = max(MIN_HALF_SPREAD, k × sqrt(vega_between)) + staleness_penalty`. `vega_post_plant` is **TBD formula** — pick + calibrate in Phase 04 against observed post-plant theo updates. The single `VEGA_DIRECTIONAL_THRESHOLD` from v1 is REMOVED.
- **DEC-020 v2** — Paper-trade promotion gate: relative Brier (model < market_mid − 0.02) AND fill-count gate (`MIN_FILLS_PER_MATCH = 3`) AND latency (p50 < 500ms general, < 200ms bomb-detect → quote-pull, p99 < 100ms cancel) AND zero ingestion-bug kill-switch trips. **MM and DIRECTIONAL evaluated independently** — DIRECTIONAL can promote even if MM is cut.
- **DEC-022** — Dry-run by default; live trading requires explicit `--live` flag. `src.main.resolve_dry_run` returns the literal `True` unless `--live` was passed; CLAUDE.md rule 13 says the literal MUST NOT be replaced with a module attribute reference.

### Carry-forward (locked elsewhere — NOT re-discussed)

- **CRule 11** — `mypy --strict` enforced on `src/pricing/` AND `src/state/` (Phase 03 SPEC). Phase 04 SHOULD extend strict to `src/quoting/` and `src/sizing/` per the project's "math layer must type-check" posture (planner discretion; recommend adding the override).
- **CRule 12** — Every threshold lives in `src/config/constants.py`. Phase 04 must NOT inline numeric literals for `TAKE_THRESHOLD`, `MM_MIN_EDGE`, `POST_PLANT_TAKE_THRESHOLD`, `MIN_HALF_SPREAD`, `MIN_FILLS_PER_MATCH`, `RELATIVE_BRIER_EDGE_MIN`, or `SERIES_AGGREGATE_CAP_FRAC`. All seven constants must land in `src/config/constants.py` in the same plan that introduces their first consumer.
- **Phase 03 contracts** — `src/state/match_state.MatchState` (frozen, seq_id-versioned, 19 fields, attackers/defenders_alive populated only when bomb_planted=True). `src/ingestion/arbiter.Arbiter.tick()` is sole writer of state. Six-stage timestamp lineage: Phase 04 fills `t_theo_computed` (after `live_theo`) and `t_quote_sent` (after `_place_quote`). `data/event_log/{match_id}.jsonl` for state replay; `data/metrics/{match_id}.metrics.jsonl` for latency analysis. Phase 04 appends to a NEW sibling `data/fills/{match_id}.{strategy_id}.jsonl` for hypothetical fills (planner's discretion on path).
- **Pricing surface** — `LiveTheoEngine(half_rates, RoundConclusionLookup.from_json(...))(state) → TheoOutput` is the locked seam. `TheoOutput.vega` is `vega_between_round` only (Phase 1 D-10/D-11). Phase 04 computes `vega_post_plant` separately (DEC-018 v2; formula TBD).

### Claude's Discretion (planner picks)

- Auth implementation: from-scratch RSA-PSS signer (~50 lines) vs `kalshi-python==2.1.4` SDK pull. Researcher recommends from-scratch.
- WebSocket library: `websockets>=12` (canonical asyncio websocket library, auto ping/pong) vs `aiohttp.ClientSession.ws_connect()` (already a dep — saves a dep). Researcher recommends `websockets>=12` because the Kalshi docs explicitly mention it handles ping/pong; aiohttp WS leaves heartbeat to caller.
- WebSocket vs REST for order book: Phase 04 needs current `yes_bid`, `yes_ask`, `mid`, `spread` per market. WS `orderbook_delta` channel is real-time; REST `/markets/{ticker}` is 5-30s polling. Researcher recommends WS for live mode, REST poll for paper-trade dry-run (saves WS connection for testing without bearer token / API key — the `KALSHI_KEY_PATH` is not present in dev `.env`).
- Kill-switch evaluation cadence: every arbiter `tick()` (50ms) vs every `theo_computed` event vs every order action. Researcher recommends every theo computation (after `live_theo` returns) — covers all three trigger types without redundant work.
- Hypothetical-fill simulation rule: `MM_BETWEEN_ROUND` quotes "hit" when market crosses through them; `DIRECTIONAL_TAKE` always "hits" the offer/bid at write time. Researcher recommends the simple "limit order touched" rule (next observed mid moves through the quote price); slippage / queue-position modeling is out of scope per DEC-020 (no order-fill backtest).
- Post-plant vega formula: variance over `{kill, defuse, time-out}` outcomes — researcher recommends starting with `var = sum_over_outcomes (P(outcome) × (theo_after_outcome − theo)²)` mirroring DEC-018's between-round shape, with outcomes parameterized by `(att, def, time_bucket)` — calibrate concretely in Phase 5 against logged post-plant theo updates.
- Reconciliation cadence: 1Hz vs every score-change vs every-arbiter-tick. Researcher recommends 1Hz (1000ms) — Phase 03 metrics show ~50ms tick interval; reconciling at every tick would burn 20× the rate-limit budget for no observable benefit.

### Deferred Ideas (OUT OF SCOPE for Phase 04)

- Covariance-aware portfolio Kelly (REQ-portfolio-correlation-kelly, Phase 7).
- Order-fill backtest (DEC-020 — paper trading replaces it; reconsider only if Kalshi exposes historical order-book data, not currently).
- Daily portfolio loss limit (DEC-021, Phase 7) — distinct from per-market kill switches.
- Multi-account / sub-account support — Kalshi `subaccount: int` field exists but Phase 04 hard-codes `subaccount=0`.
- FIX gateway (Kalshi has a separate FIX surface; we use REST + WS).
- Order replace endpoint (Kalshi `decrease-order` and `amend-order` exist; cancel-and-replace is simpler and is what `reference/market_maker.py` salvages).
- Inventory/skew management beyond DEC-018 vega-scaled spread — full prediction-market market-maker skew (e.g., Paradigm hackathon `skew_rate = min(0.08, 2.8 / size)`) is Phase 5 calibration work.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| REQ-kalshi-order-manager | REST + WS auth (RSA-PSS / SHA256), place/cancel/replace, dry-run wrapper, error-streak retry | §"Standard Stack" — `cryptography>=42`, `websockets>=12`, `aiohttp` (already dep); §"Code Examples" — RSA-PSS signing snippet, place_order body schema; §"Architecture Patterns" — single async manager + dry-run wrapper |
| REQ-mode-selector (v2) | Pure function returning `Literal["MM_BETWEEN_ROUND","DIRECTIONAL_TAKE","POST_PLANT_QUOTE","IDLE"]` | §"Architecture Patterns" — six-rule waterfall in declared order; §"Code Examples" — pure-function shape with mypy strict-friendly Literal return; §"Common Pitfalls" — both-thresholds-pass tie-break |
| REQ-mm-quoter (v2 between-round) | `theo ± vega-scaled spread` with floor beating Kalshi commission + slippage | §"Standard Stack" — Phase 1's `TheoOutput.vega` (= vega_between_round); §"Code Examples" — half-spread formula; §"Common Pitfalls" — `MIN_HALF_SPREAD` must beat 1.75¢ taker fee at 50¢ |
| REQ-directional-taker (v2 first-class peer) | `\|theo − market_mid\| > TAKE_THRESHOLD` → lift/hit; portfolio-Kelly sized | §"Architecture Patterns" — peer ledger; §"Code Examples" — IOC order with `time_in_force="immediate_or_cancel"` |
| REQ-post-plant-quoter (NEW v2) | Bomb-detect → cancel-all-MM-quotes within 200ms; re-price; take or quote-narrow-spread | §"Architecture Patterns" — defensive quote-pull as separate code path triggered on `bomb_planted=False → True` transition; §"Code Examples" — POST_PLANT_TAKE_THRESHOLD branching; §"Common Pitfalls" — measuring 200ms p50 needs Phase 03's `t_state_committed` as the start clock |
| REQ-kelly-sizer (v2 portfolio-aware) | Half-Kelly + per-market cap + per-series aggregate cap | §"Code Examples" — DEC-023 v2 formula verbatim; §"Common Pitfalls" — aggregate-exposure tracking is owner of `dict[series_id, float]`, not sizer |
| REQ-kill-switches | Four pure predicates over `(state, theo, market, recent_briers)`; ANY trip → cancel-all + alert | §"Architecture Patterns" — predicate aggregator; §"Code Examples" — deviation, staleness, Brier predicates; §"Common Pitfalls" — Brier window must NOT include rounds where mode was IDLE |
| REQ-order-lifecycle-reconciliation | Each poll cycle: GET open orders, diff against `_active_quotes` | §"Architecture Patterns" — polled reconciliation, NOT WS-only; §"Code Examples" — diff-and-cancel pattern |

## Standard Stack

### Core (Phase 04 adds)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `cryptography` | `>=42,<46` | RSA-PSS SHA256 signing for Kalshi API headers | Standard CPython crypto library; auditable; in scope of `mypy --strict` because the typed `cryptography.hazmat.primitives` API has stubs since 41.x. Direct dep — no `kalshi-python` SDK indirection. |
| `websockets` | `>=12,<14` | Asyncio WebSocket client for Kalshi `wss://external-api-ws.kalshi.com/trade-api/ws/v2` | Native asyncio, automatic ping/pong (Kalshi docs explicitly call this out for the `websockets` library); type-stub support since 12.x. |
| `aiohttp` | `>=3.13,<4` (already dep) | REST client (place/cancel/get) + WebSocket fallback if needed | Already in pyproject from Phase 03 (rib.gg poller). Reuse the same `ClientSession` lifecycle helpers. |
| `tenacity` | `>=8.5` (already dep) | Retry with exponential backoff on 429 + transient 5xx | Already used in `src/ingestion/scoreboard.py` with `Retry-After` honoring; copy that pattern. Kalshi 429 does NOT include `Retry-After` per docs (verified) — use exponential backoff up to 10s. |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pydantic` | `>=2.7,<3` | Optional — typed Kalshi response models | Use ONLY if the planner finds the dataclass + TypedDict approach gets unwieldy for the 5 endpoints. Adds ~3MB and a dep. Researcher recommends starting with frozen dataclasses + TypedDict (matches Phase 03's `_RoundConclusionJsonV2` pattern). |
| `httpx` | — | Sync REST fallback | Skip; we are async-native already. |
| `python-dotenv` | `>=1` | `.env` parsing for `KALSHI_KEY_ID` + `KALSHI_KEY_PATH` | Add. The `.env` file does NOT yet exist in dev (operator must create per CLAUDE.md "Run commands"). |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Hand-rolled RSA-PSS signer | `kalshi-python==2.1.4` (official, last release 2025-09-06) | Pro: signing helpers built in. Con: auto-generated OpenAPI client (~50 endpoints generated; ~3MB); breaks `mypy --strict` posture (auto-generated stubs are loose); pulls `urllib3 + requests` even though we are aiohttp-native. **Researcher: skip the SDK, copy the ~50 line auth snippet.** |
| `websockets>=12` for WS | `aiohttp.ClientSession.ws_connect()` | Saves a dep but Kalshi docs flag that `websockets` handles ping/pong automatically; aiohttp WS leaves heartbeat to caller — extra failure surface for marginal gain. |
| Per-strategy fill JSONL files | Single combined fills.jsonl with `strategy_id` field | Combined file forces Phase 5 Brier computation to filter; per-strategy split keeps each Brier read simple. Mirrors Phase 03's "sibling JSONL files" decision (event_log + metrics — not combined). |
| 1Hz reconciliation | Every-tick reconciliation | Every-tick is 20Hz at `ARBITER_TICK_HZ=20`; at default token cost = 10 per `/portfolio/orders` request × 20 calls/sec = 200 tokens/s — at the Basic-tier read budget of 200/s, single-market reconciliation alone consumes the entire budget. 1Hz keeps headroom for actual placement + cancellation. |

**Installation:**
```bash
uv add cryptography websockets python-dotenv
# tenacity, aiohttp already in pyproject from Phase 03
```

## Architecture Patterns

### Recommended Project Structure

```
src/
├── quoting/
│   ├── __init__.py                  # exports KalshiOrderManager, trading_mode, etc.
│   ├── kalshi_auth.py               # RSA-PSS signer (~50 lines, mypy --strict)
│   ├── order_manager.py             # KalshiOrderManager: place/cancel/get + dry-run wrapper
│   ├── market_data.py               # MarketQuote dataclass (yes_bid/yes_ask/mid/spread)
│   │                                # + WS subscriber for orderbook_delta channel
│   ├── mode_selector.py             # PURE: trading_mode(state, theo, market, vega_*, ks_active)
│   ├── mm_quoter.py                 # MM_BETWEEN_ROUND: theo ± vega-scaled spread
│   ├── directional_taker.py         # DIRECTIONAL_TAKE: lift/hit at threshold
│   ├── post_plant_quoter.py         # POST_PLANT_QUOTE: defensive pull + re-price + take/quote
│   ├── kill_switches.py             # 4 pure predicates + KillSwitchAggregator
│   ├── reconciliation.py            # diff in-memory _active_quotes vs Kalshi GET response
│   ├── portfolio.py                 # PortfolioState: dict[series_id, float] aggregate exposure
│   └── fill_ledger.py               # JSONL writer for hypothetical fills (per strategy)
├── sizing/
│   ├── __init__.py
│   └── kelly.py                     # PURE: kelly_size(theo, ask, bankroll, series_id, exposure)
└── config/
    └── constants.py                 # +7 new Phase 04 constants (see "Constants to add" below)
```

### Pattern 1: Pure-function mode selector

**What:** A single function with no side effects, no I/O, no hidden state. Inputs in, mode out. The mode determines which quoter/taker function the caller invokes.
**When to use:** REQ-mode-selector — the v2 selection logic is finite, deterministic, and must be unit-testable without mocking Kalshi.
**Example:**
```python
# Source: PRD §2.1 / DEC-001 v2 / ROADMAP §4.2
from typing import Literal
from src.state.match_state import MatchState
from src.pricing.data import TheoOutput
from src.quoting.market_data import MarketQuote
from src.config.constants import (
    TAKE_THRESHOLD,
    MM_MIN_EDGE,
    POST_PLANT_TAKE_THRESHOLD,  # only used by post_plant_quoter, not selector
)

TradingMode = Literal[
    "MM_BETWEEN_ROUND",
    "DIRECTIONAL_TAKE",
    "POST_PLANT_QUOTE",
    "IDLE",
]


def trading_mode(
    state: MatchState,
    theo: TheoOutput,
    market: MarketQuote,
    vega_between: float,         # = theo.vega from Phase 1
    vega_post_plant: float,      # computed separately by Phase 04 (DEC-018 v2)
    kill_switch_active: bool,
) -> TradingMode:
    # Rule 1: kill-switch dominates everything
    if kill_switch_active:
        return "IDLE"
    # Rule 2: bomb-planted → POST_PLANT branch (latency-critical)
    if state.bomb_planted:
        return "POST_PLANT_QUOTE"
    # Rule 3: mid-round-not-planted → IDLE (no general mid-round path per DEC-007)
    if _is_mid_round(state) and not state.bomb_planted:
        return "IDLE"
    # Rules 4 & 5: between-round — take dominates MM by declared order
    theo_cents = round(theo.theo_series * 100)
    if abs(theo_cents - market.mid) > TAKE_THRESHOLD:
        return "DIRECTIONAL_TAKE"
    if market.spread > MM_MIN_EDGE:
        return "MM_BETWEEN_ROUND"
    # Rule 6: fall-through
    return "IDLE"


def _is_mid_round(state: MatchState) -> bool:
    """Mid-round means the round timer has started but neither team has won the round.

    Carry-forward from Phase 03 D-14: time_left_s is None except when bomb_planted=True
    or when a separate timer-source has populated it. For Phase 04 simplicity, treat
    time_left_s is not None as the mid-round signal. Phase 5 calibration may refine.
    """
    return state.time_left_s is not None
```

**Anti-Patterns to Avoid:**
- **Mode selector with mutable state.** A class with `self._last_mode` to "smooth" transitions silently introduces history-dependent decisions and breaks unit testability. The PRD insists "mode is a deterministic function of inputs (no hidden state)" — keep it a pure function.
- **Re-implementing kill-switch checks inside the selector.** The selector takes `kill_switch_active: bool` as input; the `KillSwitchAggregator` is a separate concern that the caller evaluates first. Mixing them silently couples the selector to the aggregator's internal state and breaks the single-responsibility test surface.
- **"Default MM" framing.** PRD §2.1 explicitly removes this — `MM_BETWEEN_ROUND` and `DIRECTIONAL_TAKE` are peers. The selector evaluates take BEFORE MM in declared order (rule 4 before rule 5) so the "first match wins" ordering is grep-discoverable, but neither is a fallback.

### Pattern 2: Async order manager with dry-run wrapper

**What:** Single class owning the `aiohttp.ClientSession`, the `websockets` connection, the active-quotes dict, and the dry-run flag. Every place/cancel call routes through a `_dry_run_or_live` switch that logs in dry-run and only hits the network in live mode.
**When to use:** REQ-kalshi-order-manager — preserves the `dry_run=True` default per CLAUDE.md rule 13 / DEC-022 while providing a single API surface for all four quoters.
**Example:**
```python
# Source: salvaged structure from reference/market_maker.py + Kalshi docs (RSA-PSS verified)
import time
import uuid
from dataclasses import dataclass
from typing import Optional

import aiohttp

from src.quoting.kalshi_auth import sign_request
from src.config.constants import KALSHI_BASE_URL  # NEW — see "Constants to add"


@dataclass(slots=True)
class Quote:
    """Salvaged from reference/market_maker.py:36-46.

    Kalshi cents-encoding preserved. action: 'buy'|'sell'; side: 'yes'|'no'.
    """
    ticker: str
    side: str
    action: str
    price: int
    count: int
    strategy_id: str  # NEW v2 — required for hypothetical-fill ledger routing
    order_id: Optional[str] = None
    placed_at: Optional[float] = None
    client_order_id: Optional[str] = None


class KalshiOrderManager:
    def __init__(
        self,
        session: aiohttp.ClientSession,
        key_id: str,
        private_key,           # cryptography.hazmat.primitives RSA private key
        *,
        dry_run: bool,         # MUST be passed explicitly from src.main.resolve_dry_run
    ) -> None:
        self._session = session
        self._key_id = key_id
        self._private_key = private_key
        self._dry_run = dry_run
        self._active_quotes: dict[str, dict[str, Quote]] = {}
        self._error_streak = 0

    async def place_quote(self, quote: Quote) -> bool:
        client_oid = quote.client_order_id or str(uuid.uuid4())
        if self._dry_run:
            quote.order_id = f"DRY_{client_oid[:8]}"
            quote.placed_at = time.time()
            return True
        # Live path — sign + POST
        body = {
            "ticker": quote.ticker,
            "side": quote.side,
            "action": quote.action,
            "count": quote.count,
            "yes_price": quote.price if quote.side == "yes" else None,
            "no_price": quote.price if quote.side == "no" else None,
            "client_order_id": client_oid,
            "post_only": True,           # MM intent — never cross
            "time_in_force": "good_till_canceled",
        }
        path = "/trade-api/v2/portfolio/orders"
        headers = sign_request(self._key_id, self._private_key, "POST", path)
        async with self._session.post(KALSHI_BASE_URL + path, json=body, headers=headers) as r:
            if r.status == 201:
                data = await r.json()
                quote.order_id = data["order"]["order_id"]
                quote.placed_at = time.time()
                self._error_streak = 0
                return True
            self._error_streak += 1
            return False

    async def cancel_all_orders(self) -> None:
        """Salvaged from reference/market_maker.py:270 — but we batch for rate-budget.

        Kalshi DELETE /portfolio/orders/batched is 2 tokens/order vs default 10/order;
        for 5 markets × 2 quotes = 10 orders, batch = 20 tokens vs 100 tokens individual.
        """
        order_ids = [
            q.order_id for legs in self._active_quotes.values() for q in legs.values()
            if q.order_id
        ]
        if not order_ids:
            return
        if self._dry_run:
            for oid in order_ids:
                # log only
                pass
            self._active_quotes.clear()
            return
        body = {"order_ids": order_ids}
        path = "/trade-api/v2/portfolio/orders/batched"
        headers = sign_request(self._key_id, self._private_key, "DELETE", path)
        async with self._session.delete(KALSHI_BASE_URL + path, json=body, headers=headers):
            pass
        self._active_quotes.clear()
```

**Anti-Patterns to Avoid:**
- **dry_run as a constructor default**. CLAUDE.md rule 13 / DEC-022 explicitly disallows this — the literal `True` lives in `src.main.resolve_dry_run` and propagates explicitly. `KalshiOrderManager(dry_run=True)` as the only knob is OK; `dry_run=DRY_RUN_DEFAULT` as a module-attribute lookup is NOT.
- **Sync `requests` calls**. `reference/market_maker.py` uses sync `requests` via `KalshiClient`. We are async-native (Phase 03 already runs `asyncio` for the rib.gg poller, OCR workers, and Twitter listener). Mixing sync HTTP into the asyncio loop blocks the arbiter.tick() at 50ms cadence.
- **Storing `order_id` only in memory**. On reconnect, we MUST be able to GET our own resting orders and reattach them — `client_order_id` (UUID we generate, sent in the request body) survives our process death. Always set it.

### Pattern 3: Predicate-style kill switches with aggregator

**What:** Each kill switch is a pure function `(state, theo, market, recent_briers) -> bool` that returns True iff the switch trips. The aggregator collects them in a list and ANDs/ORs as needed. Cancel-all-orders fires on first trip.
**When to use:** REQ-kill-switches — DEC-005 says all four are always-on with no per-switch disable; predicate style satisfies that AND keeps each predicate independently testable.
**Example:**
```python
# Source: PRD §5.4 / DEC-005 / ROADMAP §4.7
import time
from collections import deque

from src.state.match_state import MatchState
from src.pricing.data import TheoOutput
from src.quoting.market_data import MarketQuote
from src.config.constants import (
    KILL_SWITCH_STALENESS_S,
    KILL_SWITCH_DEVIATION_C,
    KILL_SWITCH_BRIER_BOUND,
    KILL_SWITCH_BRIER_WINDOW,
)


def kill_switch_staleness(state: MatchState, *, now: float | None = None) -> bool:
    """Trips when state.last_updated_ts is older than KILL_SWITCH_STALENESS_S.

    `now` injected for testability — production passes None and uses time.time().
    """
    n = now if now is not None else time.time()
    return (n - state.last_updated_ts) > KILL_SWITCH_STALENESS_S


def kill_switch_deviation(theo: TheoOutput, market: MarketQuote) -> bool:
    """Trips when |theo - market_mid| > KILL_SWITCH_DEVIATION_C cents."""
    theo_c = round(theo.theo_series * 100)
    return abs(theo_c - market.mid) > KILL_SWITCH_DEVIATION_C


def kill_switch_brier(recent_briers: deque[float]) -> bool:
    """Trips when rolling Brier > KILL_SWITCH_BRIER_BOUND over WINDOW predictions.

    recent_briers is a `deque(maxlen=KILL_SWITCH_BRIER_WINDOW)` owned by the bot
    main loop and updated after every round resolution. Returns False until the
    window is full to avoid early false positives.
    """
    if len(recent_briers) < KILL_SWITCH_BRIER_WINDOW:
        return False
    return (sum(recent_briers) / len(recent_briers)) > KILL_SWITCH_BRIER_BOUND


def kill_switch_api_error(error_streak: int, threshold: int = 3) -> bool:
    """Trips when consecutive API errors exceed threshold.

    Salvaged from reference/market_maker.py:73 (_MAX_ERRORS_BEFORE_PAUSE).
    """
    return error_streak >= threshold


class KillSwitchAggregator:
    def __init__(self) -> None:
        self.recent_briers: deque[float] = deque(maxlen=KILL_SWITCH_BRIER_WINDOW)

    def any_tripped(
        self,
        state: MatchState,
        theo: TheoOutput,
        market: MarketQuote,
        error_streak: int,
    ) -> tuple[bool, list[str]]:
        tripped: list[str] = []
        if kill_switch_staleness(state):
            tripped.append("staleness")
        if kill_switch_deviation(theo, market):
            tripped.append("deviation")
        if kill_switch_brier(self.recent_briers):
            tripped.append("brier")
        if kill_switch_api_error(error_streak):
            tripped.append("api_error")
        return (bool(tripped), tripped)
```

**Anti-Patterns to Avoid:**
- **Kill switch with `disable_X: bool` flag.** DEC-005 explicitly bans this. If a switch is too sensitive, recalibrate the threshold in `src/config/constants.py`; do NOT add a disable knob.
- **Brier window includes IDLE rounds.** The deque should only receive Brier scores for rounds where the bot was actually in a quoting mode — rounds where mode was IDLE (e.g., during an unrelated kill-switch cooldown) corrupt the rolling Brier signal. Phase 5 calibration will surface this; bootstrapping correctly in Phase 04 saves a backfill.
- **Catching `cancel_all` exceptions silently.** A cancel-all that swallows network errors leaves resting orders open while the bot believes it's flat. Log AND retry (with a tighter retry budget than placement) AND fire the API-error kill switch.

### Pattern 4: Per-strategy hypothetical-fill ledger

**What:** Two (or three) JSONL files per match, one per strategy (`MM_BETWEEN_ROUND`, `DIRECTIONAL_TAKE`, `POST_PLANT_QUOTE`). Each file records hypothetical fills as one line per fill, keyed on `seq_id` so it can be joined against `data/event_log/{match_id}.jsonl` (Phase 03 state replay) and `data/metrics/{match_id}.metrics.jsonl` (Phase 03 latency).
**When to use:** REQ-mm-quoter + REQ-directional-taker — DEC-020 v2 evaluates the two ledgers INDEPENDENTLY; combined writes corrupt the gate.
**Example:**
```python
# Source: derived from Phase 03 sibling-JSONL pattern + DEC-020 v2 fill-count gate
from pathlib import Path
from typing import Any
import json
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class HypotheticalFill:
    seq_id: int                  # joins to event_log + metrics
    strategy: str                # "MM_BETWEEN_ROUND" | "DIRECTIONAL_TAKE" | "POST_PLANT_QUOTE"
    ticker: str
    side: str                    # "yes"|"no"
    action: str                  # "buy"|"sell"
    price_c: int                 # cents 1-99
    count: int
    theo_c_at_fill: int          # snapshot for Brier(model) computation
    market_mid_c_at_fill: int    # snapshot for Brier(market_mid) computation
    realized_outcome: bool | None = None  # filled in by Phase 5 backtest replay
    pnl_cents: int | None = None         # filled in by Phase 5

    def to_jsonl_line(self) -> str:
        return json.dumps(self.__dict__, separators=(",", ":")) + "\n"


def append_fill(fill: HypotheticalFill, ledger_dir: Path, match_id: str) -> None:
    """Append one hypothetical fill to data/fills/{match_id}.{strategy}.jsonl.

    Mirrors src.state.commit pattern — atomic POSIX append; single writer
    per (match_id, strategy) keeps PIPE_BUF guarantee (line < 4KB).
    """
    path = ledger_dir / f"{match_id}.{fill.strategy.lower()}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(fill.to_jsonl_line())


def maybe_record_mm_fill(
    quote: Quote,
    last_mid_c: int,
    next_mid_c: int,
    seq_id: int,
    theo_c: int,
    ledger_dir: Path,
    match_id: str,
) -> bool:
    """Hypothetical-fill simulation: limit order touched by the next mid (DEC-020 simple rule).

    For a YES bid at price P: filled iff next_mid_c < P (someone selling YES dropped through).
    For a YES ask at price P: filled iff next_mid_c > P (someone buying YES through us).

    No queue-position modeling. Slippage is exactly 0 (we are at our limit price).
    Phase 5 may refine; Phase 04 must NOT (DEC-020 — order-fill backtest is out of scope).
    """
    if quote.action == "buy" and next_mid_c < quote.price:
        # crossed our bid
        pass
    elif quote.action == "sell" and next_mid_c > quote.price:
        # crossed our ask
        pass
    else:
        return False
    fill = HypotheticalFill(
        seq_id=seq_id,
        strategy=quote.strategy_id,
        ticker=quote.ticker,
        side=quote.side,
        action=quote.action,
        price_c=quote.price,
        count=quote.count,
        theo_c_at_fill=theo_c,
        market_mid_c_at_fill=next_mid_c,
    )
    append_fill(fill, ledger_dir, match_id)
    return True
```

**Anti-Patterns to Avoid:**
- **Single combined `fills.jsonl`.** Phase 5 Brier computation per strategy requires filtering; per-file split makes it `cat data/fills/{match_id}.mm_between_round.jsonl | python -c "..."`. Mirror Phase 03's event_log + metrics split decision.
- **Including realized P&L in the fill record at write time.** P&L depends on round resolution which is a Phase 03 score-change event AFTER the fill; fill records ship with `realized_outcome=None` and Phase 5 backtest replay populates the missing fields.
- **Storing `theo` as float.** Save it as cents (int) — same as the market mid. Brier computation across model + market needs them on the same scale.

### Pattern 5: Polled order reconciliation

**What:** Every reconcile cycle, GET `/portfolio/orders?status=resting&ticker=...` (or `?ticker=...&status=resting`), build a set of remote `order_id`s, diff against in-memory `_active_quotes` order_ids. Cancel orphans (Kalshi has, we don't track), drop ghosts (we track, Kalshi doesn't have).
**When to use:** REQ-order-lifecycle-reconciliation — survives bot restart, websocket disconnect, transient API errors that left a place succeeding but our local update failing.
**Example:**
```python
# Source: ROADMAP §4.7; Polymarket reconciliation pattern (NautilusTrader)
async def reconcile_once(self, ticker: str) -> None:
    """1Hz reconciliation pass.

    Cost: 1 request × 10 tokens (default cost). At Basic tier 200 tokens/s read,
    1Hz costs 10/s = 5% of the read budget. Fits comfortably alongside REST
    market-data fallback pollers.
    """
    if self._dry_run:
        return  # dry-run has no remote state to reconcile against
    path = f"/trade-api/v2/portfolio/orders?status=resting&ticker={ticker}"
    headers = sign_request(self._key_id, self._private_key, "GET",
                           "/trade-api/v2/portfolio/orders")  # path WITHOUT query!
    async with self._session.get(KALSHI_BASE_URL + path, headers=headers) as r:
        data = await r.json()
    remote_ids = {o["order_id"] for o in data.get("orders", [])}
    local_ids = {
        q.order_id for legs in self._active_quotes.values() for q in legs.values()
        if q.order_id and not q.order_id.startswith("DRY_")
    }
    orphans = remote_ids - local_ids
    ghosts = local_ids - remote_ids
    for oid in orphans:
        await self._cancel_order_id(oid)
    for oid in ghosts:
        self._drop_local_quote(oid)
```

**Anti-Patterns to Avoid:**
- **Signing the path WITH query parameters.** Kalshi docs: "When signing requests, use the path **without query parameters**." This is the most common Kalshi auth bug per the cited docs.
- **WebSocket-only reconciliation.** WS gives us live `user_orders` + `user_fills` channels but on disconnect they re-emit all state from "now"; orders that resolved during the gap are missed. REST reconciliation is the safety net.

### Recommended Wave Decomposition

```
Wave 0: Test infrastructure (RED scaffolds)
  └ 04-00-test-infrastructure-PLAN
      ├ tests/quoting/conftest.py: fake KalshiOrderManager, MarketQuote factory
      ├ tests/quoting/test_*.py: RED stubs for selector / mm / directional /
      │   post-plant / kill-switches / reconciliation
      ├ tests/sizing/test_kelly.py: RED stubs (per-market + per-series cap cases)
      └ Add 7 constants placeholders to src/config/constants.py with TODO markers

Wave 1: Skeleton layer
  ├ 04-01-kalshi-order-manager-PLAN
  │   ├ src/quoting/kalshi_auth.py: RSA-PSS sign_request(...)
  │   ├ src/quoting/order_manager.py: KalshiOrderManager + Quote dataclass
  │   └ src/quoting/market_data.py: MarketQuote dataclass + WS subscriber
  └ 04-06-portfolio-kelly-PLAN
      └ src/sizing/kelly.py: pure kelly_size + PortfolioState helper

Wave 2: Pure-function layer (parallelizable; no Wave 1 dep beyond MarketQuote shape)
  ├ 04-02-mode-selector-PLAN
  │   └ src/quoting/mode_selector.py: trading_mode(...)
  └ 04-07-kill-switches-PLAN
      └ src/quoting/kill_switches.py: 4 predicates + KillSwitchAggregator

Wave 3: Quoter / taker layer (parallelizable; depends on Wave 1 + Wave 2)
  ├ 04-03-mm-between-round-quoter-PLAN
  │   ├ src/quoting/mm_quoter.py
  │   └ src/quoting/fill_ledger.py (shared with 04-04)
  ├ 04-04-directional-taker-PLAN
  │   └ src/quoting/directional_taker.py
  └ 04-05-post-plant-quoter-PLAN
      └ src/quoting/post_plant_quoter.py + post_plant_vega formula

Wave 4: Recovery + integration
  └ 04-08-order-lifecycle-reconciliation-PLAN
      ├ src/quoting/reconciliation.py
      └ tests/quoting/test_e2e.py: drives MatchState transitions through the
        full mode-selector → quoter → fill-ledger pipe with mocked Kalshi
```

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| RSA-PSS signing | Re-implement ASN.1 PSS encoding | `cryptography.hazmat.primitives.asymmetric.padding.PSS` | OpenSSL-backed, audited, side-channel-safe. The full sign call is 4 lines. |
| WebSocket framing + ping/pong | Raw socket + manual framing | `websockets>=12` | Kalshi docs explicitly recommend the `websockets` library because it auto-handles ping/pong; rolling your own gets disconnected on the 30s-idle path. |
| Retry with `Retry-After` honoring | Custom while loop with `time.sleep` | `tenacity` `_RibggWaitAsync` pattern (Phase 03 03-04) | Already in `src/ingestion/scoreboard.py`; copy. Note: Kalshi 429 does NOT include `Retry-After` per docs (verified) — fall back to exponential backoff capped at 10s, same as Phase 03's poller. |
| Aggregate-exposure tracking dict | Inline `if series_id in {...}` chains | `PortfolioState.update(series_id, delta)` | Single mutator + grep-discoverable; passes a `dict[str, float]` snapshot to `kelly_size` keeping the sizer pure. |
| Order ID UUID generation | `random.randbytes` | `uuid.uuid4()` (already in reference/market_maker.py:213) | UUID4 is the canonical client-side dedup id; Kalshi accepts up to 64-char `client_order_id`. |
| Limit order touched simulation | Custom queue-position model | `next_mid_c < quote.price` boolean for buy / `> quote.price` for sell | DEC-020 explicitly excludes order-fill backtest fidelity; the simple "touched" rule is what the v2 promotion gate evaluates. |
| JSONL atomic append | `json.dump + manual lock` | `with path.open('a') as f: f.write(line)` | Phase 03 D-03 / single-writer invariant guarantees POSIX `O_APPEND` atomicity for sub-PIPE_BUF lines. Phase 04 is sole writer of `data/fills/{match_id}.{strategy}.jsonl` — same guarantee. |

**Key insight:** The v1 code in `reference/market_maker.py` has the right structural primitives (`Quote`, `_place_quote`, `_cancel_quote`, `_error_streak`, `_is_near_close`, dry-run wrapper) but is wrong on:
- **Auth path** (`KalshiClient` is from a 2024-era SDK; we use `cryptography` directly).
- **Sync `requests` vs async** (we are asyncio-native).
- **Single-mode framing** (it was MM-only; Phase 04 v2 has four modes).
- **Per-market cap only** (it has no per-series aggregate cap; DEC-023 v2 adds the layer).

Salvage the dataclass and the structural patterns; rewrite the verbs against `aiohttp` + `cryptography`.

## Common Pitfalls

### Pitfall 1: Auth signing with the query-string path
**What goes wrong:** `KALSHI-ACCESS-SIGNATURE` is computed over `timestamp + method + "/v2/portfolio/orders?ticker=X"`, returns 401 unauthorized.
**Why it happens:** Intuition says "sign the URL"; Kalshi requires the path WITHOUT query parameters. Documented in the API keys page but easy to miss.
**How to avoid:** `sign_request(...)` takes `(method: str, path: str)` where `path` is the URL path component only. Add a defensive assert: `assert "?" not in path, "sign path WITHOUT query"`.
**Warning signs:** First place_order call returns 401; works for endpoints without query parameters (cancel by ID).

### Pitfall 2: RSA-PSS vs PKCS1v15
**What goes wrong:** CLAUDE.md says "RSA PKCS1v15/SHA-256 auth" — wrong. Kalshi docs verified 2026-05-09 confirm RSA-PSS with `MGF1(SHA256)` and `salt_length=PSS.DIGEST_LENGTH`. Using PKCS1v15 results in 401.
**Why it happens:** Stale documentation; CLAUDE.md was written before the v2 verification.
**How to avoid:** Implement `sign_request` using `padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH)` exactly. Update CLAUDE.md as a side-effect commit when Phase 04 lands. The RESEARCH cites `docs.kalshi.com/getting_started/api_keys` as primary source.
**Warning signs:** Local crypto unit test passes against a fake server but real Kalshi returns 401 with "invalid signature".

### Pitfall 3: Tied mode-selector branches (DIRECTIONAL_TAKE vs MM_BETWEEN_ROUND)
**What goes wrong:** Both `abs(theo - market.mid) > TAKE_THRESHOLD` AND `market.spread > MM_MIN_EDGE` evaluate true. Without declared order, behavior is implementation-dependent.
**Why it happens:** When the market is wide AND mispriced, both rules fire. PRD §2.1 says rule 4 (DIRECTIONAL_TAKE) precedes rule 5 (MM_BETWEEN_ROUND).
**How to avoid:** Implement rules as a sequence of `if ... return ...` statements in declared order. Do NOT use `match` / dict dispatch / "highest priority wins" — the literal source-code order IS the priority.
**Warning signs:** Mode flips between MM and DIRECTIONAL on the same `(state, theo, market)` across runs.

### Pitfall 4: `MIN_HALF_SPREAD` below Kalshi commission
**What goes wrong:** MM quotes at `theo ± 1c`, then immediately gets adverse-selected and pays the 1.75c taker fee on every fill, net-negative on every trade.
**Why it happens:** PRD §5.4 says "Spread floor must beat Kalshi commission + slippage" but doesn't specify the value; intuition picks 1c (smallest tick) as the floor.
**How to avoid:** Set `MIN_HALF_SPREAD = 3` (3 cents). Justification: at theo=50c, Kalshi taker fee is `ceil(0.07 × 0.5 × 0.5 × 100) / 100 = 1.75c`; maker fee is 25% × 1.75c = 0.44c. We are quoting passively (post_only=True intent) so we mostly earn the maker rebate-equivalent (Kalshi has no rebate, just lower fees). A 3c half-spread quotes at theo±3c; if filled we pay 0.44c maker fee = net 2.56c edge if theo is exact — covers half a cent of model slippage AND a full half-cent of slippage from arbiter staleness. Calibrate down to 2c only after Phase 5 paper-trade shows the floor is tight.
**Warning signs:** MM ledger shows positive raw P&L but negative net-of-fee P&L; alternatively, MM hypothetical fills are massively positive in dry-run but live MM gets crushed.

### Pitfall 5: Series-aggregate exposure not decremented on fill resolution
**What goes wrong:** `current_series_exposure[series_id]` is incremented on placement; never decremented when the round resolves and the position is settled. Series exposure monotonically grows; Kelly returns 0 forever.
**Why it happens:** Sizer is pure; the caller forgets to decrement. PRD §2.3: "the sizer takes a `current_series_exposure: dict[series_id, float]` argument and clips new positions so cumulative exposure ≤ aggregate cap. Returns 0 if the aggregate cap is already exceeded."
**How to avoid:** A `PortfolioState` class in `src/quoting/portfolio.py` owns the dict. `PortfolioState.on_place(series_id, fraction)` increments; `PortfolioState.on_settle(series_id, fraction)` decrements. Phase 03 metrics JSONL records the seq_id of the resolution event; Phase 04's `PortfolioState` listens for `event_type=score_change` mapping to "round/map/series resolved" and decrements.
**Warning signs:** Across a long paper-trade run, second and third Kalshi market on the same series never get sized.

### Pitfall 6: bomb-detect → quote-pull p50 measured from wrong start clock
**What goes wrong:** The 200ms budget per DEC-020 v2 is "bomb-detect → quote-pull p50". If we measure from `t_state_committed` (Phase 03's commit timestamp) we are budgeting 200ms for Phase 04 alone; if we measure from `t_observed` (broadcast wall-clock) we are budgeting 200ms for the entire chain.
**Why it happens:** Phase 03's E2E gate measures `t_observed → t_state_committed` p50 < 100ms (synthetic harness — production gate is Phase 5 paper-trade per RESEARCH Pitfall 3 in 03-RESEARCH); Phase 04's measurement clock starts at `t_state_committed` and ends when ALL resting MM quotes have been cancelled (not just a single cancel call returning).
**How to avoid:** Phase 04 instrumentation records `t_quote_pull_completed = mono_ns()` at the moment `cancel_all_orders` returns successfully (or the dry-run equivalent). The metric is `t_quote_pull_completed - t_state_committed`; budget is 100ms (Phase 04's piece) → total p50 is < 200ms (PRD bound).
**Warning signs:** Phase 5 paper-trade reports total bomb-detect → quote-pull p50 > 200ms even though Phase 03 metric is fine.

### Pitfall 7: WebSocket reconnect loses orderbook_delta state
**What goes wrong:** Kalshi WS `orderbook_delta` channel sends the FULL book on subscribe and then deltas. On reconnect the bot resubscribes; until the FULL book arrives (~50-200ms), `MarketQuote.mid` is stale. Mode selector sees stale mid + fresh theo, possibly trips the deviation kill switch falsely.
**Why it happens:** WS reconnect race; mid not invalidated atomically with the subscription teardown.
**How to avoid:** On WS disconnect, set `MarketQuote.is_valid = False`; mode selector rule 1 (kill_switch_active) should include "is_valid=False on any subscribed market". Resume normal flow only after the next FULL book arrives.
**Warning signs:** Kill-switch trips correlate with WS reconnects in Phase 5 paper-trade logs.

### Pitfall 8: dry-run path never exercises the live-only auth path
**What goes wrong:** `_dry_run_or_live` shortcuts ALL Kalshi calls in dry-run mode; the auth signing path never runs in dev. First operator-driven `--live` run hits 401.
**Why it happens:** The dry-run wrapper is too coarse-grained.
**How to avoid:** A separate `kalshi_auth_smoke_test.py` script (no `--live` requirement) that signs a GET `/trade-api/v2/exchange/status` (public + signed) and asserts 200. Operator runs once after first checkout to verify their `.env` works. Phase 04 should ship this — landing Phase 04 to operator-test gate per the additional-context note.
**Warning signs:** Phase 04 lands GREEN on all unit tests; first paper-trade live run shows "401 invalid signature" for every order.

## Code Examples

Verified patterns from primary sources:

### Kalshi RSA-PSS signing (verified against docs.kalshi.com 2026-05-09)
```python
# Source: docs.kalshi.com/getting_started/api_keys
import time
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding


def load_private_key(pem_path: str):
    with open(pem_path, "rb") as f:
        return serialization.load_pem_private_key(f.read(), password=None)


def sign_request(
    key_id: str,
    private_key,           # rsa.RSAPrivateKey from cryptography
    method: str,           # "GET" | "POST" | "DELETE"
    path: str,             # "/trade-api/v2/portfolio/orders"  — NO QUERY STRING
) -> dict[str, str]:
    """Returns the 3 KALSHI-ACCESS-* headers per https://docs.kalshi.com/getting_started/api_keys.

    PSS padding with MGF1(SHA256) and digest-length salt — verified 2026-05-09.
    NOT PKCS1v15 (despite stale CLAUDE.md text).
    """
    assert "?" not in path, "Sign path WITHOUT query parameters (Kalshi auth pitfall #1)"
    timestamp_ms = str(int(time.time() * 1000))
    message = (timestamp_ms + method + path).encode("utf-8")
    signature = private_key.sign(
        message,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.DIGEST_LENGTH,
        ),
        hashes.SHA256(),
    )
    import base64
    return {
        "KALSHI-ACCESS-KEY": key_id,
        "KALSHI-ACCESS-SIGNATURE": base64.b64encode(signature).decode("ascii"),
        "KALSHI-ACCESS-TIMESTAMP": timestamp_ms,
    }
```

### Kalshi WebSocket subscribe (orderbook_delta + ticker + user_fills)
```python
# Source: docs.kalshi.com/getting_started/quick_start_websockets + /websockets/user-fills
import json
import websockets

KALSHI_WS_URL = "wss://external-api-ws.kalshi.com/trade-api/ws/v2"


async def open_ws(key_id, private_key):
    headers = sign_request(key_id, private_key, "GET", "/trade-api/ws/v2")
    return await websockets.connect(KALSHI_WS_URL, additional_headers=headers)


async def subscribe(ws, ticker: str) -> None:
    """Subscribe to public orderbook_delta + private user_fills for one ticker.

    Channels per Kalshi docs:
      - orderbook_delta: full book on subscribe + deltas (need to track full book locally)
      - ticker: latest yes_bid/yes_ask/last_price
      - fill: user fills (auth required)
      - user_orders: user open-order lifecycle (auth required)
    """
    await ws.send(json.dumps({
        "id": 1,
        "cmd": "subscribe",
        "params": {
            "channels": ["orderbook_delta", "ticker"],
            "market_ticker": ticker,
        },
    }))
    await ws.send(json.dumps({
        "id": 2,
        "cmd": "subscribe",
        "params": {"channels": ["fill", "user_orders"]},  # all markets — own fills only
    }))
```

### Portfolio Kelly with per-series aggregate cap (DEC-023 v2)
```python
# Source: PRD §2.3 + ROADMAP §4.6 + PROJECT.md DEC-023 — verbatim formula
from src.config.constants import (
    KELLY_MULTIPLIER,
    PER_MARKET_CAP_FRAC,
    SERIES_AGGREGATE_CAP_FRAC,  # NEW v2
)


def kelly_size(
    theo: float,                              # P(YES wins) ∈ [0, 1]
    market_yes_ask: int,                      # cents 1-99
    bankroll: int,                            # cents
    series_id: str,
    current_series_exposure: dict[str, float],  # snapshot — NOT mutated here
) -> int:
    """Returns contract count; 0 if any cap binds.

    Acceptance per REQ-kelly-sizer:
      - identical to v1 single-market case (when exposure is 0)
      - aggregate cap binds when exposure[series_id] >= SERIES_AGGREGATE_CAP_FRAC
      - never returns full-Kelly sizing
    """
    ask = market_yes_ask / 100.0
    if ask <= 0 or ask >= 1:
        return 0
    p = theo
    q = 1.0 - p
    b = (1.0 - ask) / ask                    # net odds for YES at ask
    f_full = (b * p - q) / b
    f = max(0.0, KELLY_MULTIPLIER * f_full)  # half-Kelly per DEC-004
    f = min(f, PER_MARKET_CAP_FRAC)          # per-market cap (0.05)
    headroom = max(
        0.0,
        SERIES_AGGREGATE_CAP_FRAC - current_series_exposure.get(series_id, 0.0),
    )
    f = min(f, headroom)                     # per-series aggregate cap (0.10) — DEC-023 v2
    if f == 0.0:
        return 0
    return int(f * bankroll / market_yes_ask)
```

### Hypothetical-fill simulation rule (DEC-020 simple "limit touched")
```python
# Source: DEC-020 v2 — order-fill backtest fidelity is OUT OF SCOPE; simple touched rule.
def simulate_mm_fill(
    quote_price_c: int,
    quote_action: str,         # "buy" | "sell"
    last_mid_c: int,
    next_mid_c: int,
) -> bool:
    """Returns True if this MM quote would have hypothetically filled
    given a market mid moving from last_mid_c to next_mid_c.

    Simple rule per DEC-020:
      - YES buy at P fills if mid drops THROUGH P (next_mid < P <= last_mid)
      - YES sell at P fills if mid rises THROUGH P (last_mid <= P < next_mid)

    No queue position, no slippage, no partial fills. The complexity Phase 5
    paper-trade promotion gate evaluates is filled vs not-filled — quantity
    and effective price are exact from the quote dataclass.
    """
    if quote_action == "buy":
        return next_mid_c < quote_price_c <= last_mid_c
    if quote_action == "sell":
        return last_mid_c <= quote_price_c < next_mid_c
    return False
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Sync `KalshiClient` from `reference/market_maker.py` (2024) | Async `aiohttp` + `cryptography` direct sign | Phase 03 went async-native | Mixing sync into asyncio loop blocks 50ms tick — full rewrite forced |
| Auth: PKCS1v15 (per stale CLAUDE.md) | Auth: RSA-PSS with MGF1(SHA256), salt=DIGEST_LENGTH | Pre-2024 (always RSA-PSS per docs) | CLAUDE.md is wrong; verified against docs.kalshi.com 2026-05-09 |
| Single MM mode (`reference/market_maker.py`) | Three-way mode + IDLE | v2 pivot 2026-05-02 | Mode selector is new code; MM is one branch of four |
| Per-market cap only | Per-market + per-series aggregate cap | DEC-023 v2 — 2026-05-02 | New `SERIES_AGGREGATE_CAP_FRAC` constant; new `PortfolioState`; new arg to `kelly_size` |
| Absolute Brier promotion gate (< 0.22) | Relative Brier (model < market_mid − 0.02) + fill-count gate | DEC-020 v2 — 2026-05-02 | Hypothetical-fill ledger MUST be per-strategy (NEW); both Brier and market_mid logged per fill (NEW) |
| `VEGA_DIRECTIONAL_THRESHOLD = 0.04` triggers DIRECTIONAL_TAKE | DIRECTIONAL_TAKE triggers on `|theo − market_mid| > TAKE_THRESHOLD` | DEC-018 v2 — 2026-05-02 | Constant REMOVED (still in `src/config/constants.py` as legacy — Phase 04 deletes it); selector uses cents-deviation directly |
| FIX gateway as primary order entry | REST + WebSocket | Always (project scope) | Kalshi FIX exists but PRD picks REST + WS; smaller surface, fewer codecs |
| Order replace via `decrease-order` / `amend-order` | Cancel-and-replace pattern | reference/market_maker.py salvage | Simpler invariants (each cancel + place is atomic); 2 tokens (cancel) + 10 tokens (place) = 12 vs amend at 10 — close enough at 1Hz reconcile cadence |

**Deprecated/outdated:**
- `VEGA_DIRECTIONAL_THRESHOLD` in `src/config/constants.py` (Phase 04 deletes per DEC-018 v2 / CLAUDE.md "Removed in v2").
- Sync `KalshiClient` import path from reference/market_maker.py (skip; not in current Kalshi `kalshi-python==2.1.4` either).
- `vision_parser.py` (already cut in Phase 03 per DEC-024 v2).

## Open Questions

1. **Initial values for `TAKE_THRESHOLD`, `MM_MIN_EDGE`, `POST_PLANT_TAKE_THRESHOLD`, `MIN_HALF_SPREAD`.**
   - What we know: PRD §9 marks these as TBD; Phase 5 calibrates after 20+ live matches; researcher recommends `MIN_HALF_SPREAD = 3` cents based on Kalshi taker fee curve (verified 2026-05-09).
   - What's unclear: `TAKE_THRESHOLD` (5c? 8c?), `MM_MIN_EDGE` (4c? 6c?), `POST_PLANT_TAKE_THRESHOLD` (3c? narrower than between-round take per PRD §5.4).
   - Recommendation: ship initial values with TODO(phase-5-calibrate) markers in `src/config/constants.py`. Initial guesses: `TAKE_THRESHOLD = 5`, `MM_MIN_EDGE = 4`, `POST_PLANT_TAKE_THRESHOLD = 3`, `MIN_HALF_SPREAD = 3`. Document each citation in the constant docstring.

2. **`vega_post_plant` formula choice.**
   - What we know: DEC-018 v2 is explicit that the formula is TBD; PRD §5.4 hints at `var = sum_over_outcomes (P(outcome) × (theo_after_outcome − theo)²)` shape; outcomes are `{kill, defuse, time-out}` parameterized by `(att, def, time_bucket)`.
   - What's unclear: Whether to use the raw 3-outcome variance (which assumes the 3 outcomes are mutually exclusive — they ARE in Valorant post-plant) OR a simpler theo-shift second-moment from observed lookup neighbors.
   - Recommendation: ship the simpler "between-round vega shape, but over post-plant outcomes" formula in 04-05-post-plant-quoter-PLAN with explicit Phase 5 calibration TODO. Land it as a separate function `compute_vega_post_plant(state, lookup) -> float` in `src/pricing/live_theo.py` mirroring `_compute_vega` (Phase 1's between-round function).

3. **WebSocket vs REST market-data source in dry-run.**
   - What we know: WS gives ~10ms updates; REST `/markets/{ticker}` is rate-limit-budgeted at 5-30s polling.
   - What's unclear: Whether dev environment without `KALSHI_KEY_PATH` should still try to authenticate the WS connection (fails fast, clear error) or run with synthesized `MarketQuote` (no live market data at all in dry-run).
   - Recommendation: a `MarketDataSource` Protocol in `src/quoting/market_data.py` with two implementations — `KalshiWsMarketData` (live) and `SyntheticMarketData` (dry-run; tests + dev). Operator can opt-in to live WS in dry-run via `--live-market-data` flag (separate from `--live` trading). Phase 04 ships SyntheticMarketData; KalshiWsMarketData is per-plan in 04-01.

4. **Brier window scope: per-mode or all-modes?**
   - What we know: REQ-kill-switches says "rolling Brier > 0.30 over last 50 round predictions"; doesn't specify what counts as a "prediction".
   - What's unclear: Whether IDLE rounds (no quote, no take) contribute to the Brier window. PRD §5.4 implies all rounds should count; Pitfall 3 above warns against this.
   - Recommendation: All rounds with a `theo_series` value contribute (regardless of whether we traded). The kill switch measures MODEL Brier, not P&L Brier; quoting decisions don't affect the round outcome. This matches the v1 framing in PRD §5.4.

## Validation Architecture

(Per `nyquist_validation` enabled — no `.planning/config.json` exists, default is enabled.)

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8+ + pytest-asyncio 0.23+ + hypothesis 6+ (already in `[dependency-groups].dev` per pyproject.toml) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (already configured: testpaths=["tests"], strict-markers, strict-config) |
| Quick run command | `uv run pytest tests/quoting/ tests/sizing/ -x --tb=short` |
| Full suite command | `uv run pytest -x` (all of Phases 0-4) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REQ-kalshi-order-manager | RSA-PSS signed headers structurally correct | unit | `uv run pytest tests/quoting/test_kalshi_auth.py -x` | ❌ Wave 0 |
| REQ-kalshi-order-manager | place_quote dry-run records `DRY_*` order_id without network | unit | `uv run pytest tests/quoting/test_order_manager.py::test_place_quote_dry_run -x` | ❌ Wave 0 |
| REQ-kalshi-order-manager | cancel_all in dry-run clears `_active_quotes` | unit | `uv run pytest tests/quoting/test_order_manager.py::test_cancel_all_dry_run -x` | ❌ Wave 0 |
| REQ-mode-selector (v2) | All 6 rules — one test per rule, declared order | unit | `uv run pytest tests/quoting/test_mode_selector.py -x` (6 tests) | ❌ Wave 0 |
| REQ-mode-selector (v2) | Tied DIRECTIONAL+MM → DIRECTIONAL wins | unit | `uv run pytest tests/quoting/test_mode_selector.py::test_tie_directional_dominates_mm -x` | ❌ Wave 0 |
| REQ-mm-quoter (v2) | spread = max(MIN_HALF_SPREAD, k×sqrt(vega)) | unit | `uv run pytest tests/quoting/test_mm_quoter.py::test_spread_formula -x` | ❌ Wave 0 |
| REQ-mm-quoter (v2) | spread floor beats taker fee at theo=50c | property (hypothesis) | `uv run pytest tests/quoting/test_mm_quoter.py::test_spread_floor_beats_fee -x` | ❌ Wave 0 |
| REQ-directional-taker (v2) | take fires on `\|theo − mid\| > TAKE_THRESHOLD`; sized by Kelly | unit | `uv run pytest tests/quoting/test_directional_taker.py -x` | ❌ Wave 0 |
| REQ-directional-taker (v2) | hypothetical-fill written to DIRECTIONAL ledger only | unit | `uv run pytest tests/quoting/test_fill_ledger.py::test_directional_separate_ledger -x` | ❌ Wave 0 |
| REQ-post-plant-quoter (NEW v2) | bomb_planted=False → True triggers cancel-all-MM-quotes | unit | `uv run pytest tests/quoting/test_post_plant_quoter.py::test_defensive_quote_pull -x` | ❌ Wave 0 |
| REQ-post-plant-quoter (NEW v2) | re-prices using post_plant_p path (lookup hit) | unit | `uv run pytest tests/quoting/test_post_plant_quoter.py::test_repricing_via_lookup -x` | ❌ Wave 0 |
| REQ-post-plant-quoter (NEW v2) | bomb-detect → quote-pull p50 < 100ms (Phase 04 piece of 200ms PRD budget) | latency synthetic | `uv run pytest tests/quoting/test_post_plant_quoter.py::test_quote_pull_p50 -x` | ❌ Wave 0 |
| REQ-kelly-sizer (v2) | identical to v1 single-market when exposure=0 | unit | `uv run pytest tests/sizing/test_kelly.py::test_v1_single_market_compat -x` | ❌ Wave 0 |
| REQ-kelly-sizer (v2) | per-series aggregate cap binds at exposure ≥ 0.10 | property (hypothesis) | `uv run pytest tests/sizing/test_kelly.py::test_aggregate_cap_binds -x` | ❌ Wave 0 |
| REQ-kelly-sizer (v2) | returns 0 if aggregate exceeded | unit | `uv run pytest tests/sizing/test_kelly.py::test_returns_zero_when_capped -x` | ❌ Wave 0 |
| REQ-kelly-sizer (v2) | never returns full-Kelly sizing (always ≤ KELLY_MULTIPLIER × full) | property | `uv run pytest tests/sizing/test_kelly.py::test_never_full_kelly -x` | ❌ Wave 0 |
| REQ-kill-switches | each of 4 predicates: trip + non-trip boundary cases | unit (8 tests) | `uv run pytest tests/quoting/test_kill_switches.py -x` | ❌ Wave 0 |
| REQ-kill-switches | aggregator: ANY trip → returns True + name list | unit | `uv run pytest tests/quoting/test_kill_switches.py::test_aggregator_any_tripped -x` | ❌ Wave 0 |
| REQ-order-lifecycle-reconciliation | orphans (Kalshi-has, we-don't) cancelled | unit (mocked aiohttp) | `uv run pytest tests/quoting/test_reconciliation.py::test_cancel_orphans -x` | ❌ Wave 0 |
| REQ-order-lifecycle-reconciliation | ghosts (we-have, Kalshi-doesn't) dropped from local | unit | `uv run pytest tests/quoting/test_reconciliation.py::test_drop_ghosts -x` | ❌ Wave 0 |
| REQ-order-lifecycle-reconciliation | reconcile_once is no-op in dry-run | unit | `uv run pytest tests/quoting/test_reconciliation.py::test_dry_run_noop -x` | ❌ Wave 0 |
| (E2E) | MatchState transitions drive selector → quoter → ledger pipe end-to-end | integration | `uv run pytest tests/quoting/test_e2e.py -x` | ❌ Wave 4 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/quoting/ tests/sizing/ -x` (~5-10s)
- **Per wave merge:** `uv run pytest -x` (full suite — Phase 0-4; ~30-60s once Phase 04 lands)
- **Phase gate:** Full suite GREEN + `uv run mypy --strict src/quoting/ src/sizing/` clean before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/quoting/__init__.py` — package marker
- [ ] `tests/quoting/conftest.py` — fixtures: `make_match_state` (re-export from tests/ingestion/conftest.py), `make_market_quote`, `fake_kalshi_session` (aioresponses-mocked), `tmp_fill_ledger_dir`
- [ ] `tests/quoting/test_kalshi_auth.py` — RSA-PSS signature shape
- [ ] `tests/quoting/test_order_manager.py` — place / cancel / dry-run / error-streak
- [ ] `tests/quoting/test_market_data.py` — MarketQuote dataclass + WS subscriber state machine
- [ ] `tests/quoting/test_mode_selector.py` — 6 rules + tie-break tests
- [ ] `tests/quoting/test_mm_quoter.py` — spread formula + floor-beats-fee
- [ ] `tests/quoting/test_directional_taker.py` — take threshold + Kelly sizing wired
- [ ] `tests/quoting/test_post_plant_quoter.py` — defensive pull + re-price + take-or-quote
- [ ] `tests/quoting/test_kill_switches.py` — 4 predicates × 2 boundary tests + aggregator
- [ ] `tests/quoting/test_fill_ledger.py` — per-strategy JSONL append + simulate_mm_fill rule
- [ ] `tests/quoting/test_reconciliation.py` — orphan/ghost diff
- [ ] `tests/quoting/test_e2e.py` — full integration (Wave 4)
- [ ] `tests/sizing/__init__.py`
- [ ] `tests/sizing/test_kelly.py` — pure-function Kelly with portfolio cap
- [ ] Add to pyproject.toml `[tool.mypy.overrides]` — strict on `src.quoting.*` AND `src.sizing.*` (per CRule 11 extension)

### Constants to Add (in 04-00 plan, per CRule 12)

```python
# src/config/constants.py — Phase 04 additions

# Mode-selector thresholds (DEC-001 v2)
TAKE_THRESHOLD: Final[int] = 5  # TBD — cents; |theo - market_mid| above this → DIRECTIONAL_TAKE
MM_MIN_EDGE: Final[int] = 4     # TBD — cents; market.spread above this → MM_BETWEEN_ROUND
POST_PLANT_TAKE_THRESHOLD: Final[int] = 3  # TBD — cents; narrower than TAKE_THRESHOLD per PRD §5.4
MIN_HALF_SPREAD: Final[int] = 3  # cents; calibrated to beat Kalshi taker fee 1.75c at theo=50c
                                 # + ~1c slippage budget. PRD §5.4 floor invariant.

# Sizing — portfolio Kelly v2 (DEC-023)
SERIES_AGGREGATE_CAP_FRAC: Final[float] = 0.10  # TBD — per-series aggregate cap

# Promotion gate (DEC-020 v2) — referenced from Phase 04 fill-ledger / kill-switch logic
RELATIVE_BRIER_EDGE_MIN: Final[float] = 0.02
MIN_FILLS_PER_MATCH: Final[int] = 3

# Kalshi
KALSHI_BASE_URL: Final[str] = "https://api.elections.kalshi.com/trade-api/v2"
KALSHI_WS_URL: Final[str] = "wss://api.elections.kalshi.com/trade-api/ws/v2"

# Removed (DEC-018 v2)
# VEGA_DIRECTIONAL_THRESHOLD — DELETE in 04-02 (mode-selector plan).
# Update tests/config/test_constants.py allow-list in same commit.
```

## Sources

### Primary (HIGH confidence)
- `docs.kalshi.com/getting_started/api_keys` — RSA-PSS auth scheme + headers + path-without-query rule (verified 2026-05-09)
- `docs.kalshi.com/api-reference/orders/create-order` — POST /portfolio/orders body schema (verified 2026-05-09)
- `docs.kalshi.com/api-reference/orders/cancel-order` — DELETE /portfolio/orders/{order_id} response shape, partial-fill behavior (verified 2026-05-09)
- `docs.kalshi.com/getting_started/quick_start_websockets` — WS URL, subscription cmd, ping/pong handling (verified 2026-05-09)
- `docs.kalshi.com/websockets/user-fills` — fill message schema (verified 2026-05-09)
- `docs.kalshi.com/getting_started/rate_limits` — token cost map, 429 behavior, no Retry-After (verified 2026-05-09)
- `kalshi.com/docs/kalshi-fee-schedule.pdf` — fee curve `ceil(0.07 × P × (1-P) × 100) / 100` per contract (verified 2026-05-09)
- `prd.md` (root) §2.1, §2.3, §5.4, §6, §8 — project design doc; v2 framing
- `roadmap.md` (root) §4.1-4.8 — implementation guidance
- `CLAUDE.md` (root) — critical rules 7, 8, 9, 10b, 11, 12, 13
- `.planning/PROJECT.md` — DEC-001..DEC-024 (especially v2: DEC-001, DEC-018, DEC-020, DEC-023, DEC-024)
- `.planning/REQUIREMENTS.md` Phase 4 section — REQ-* enumeration
- `reference/market_maker.py` — salvageable Kalshi plumbing structure (Quote, _place_quote, _cancel_quote, _is_near_close, dry-run wrapper)
- `src/state/match_state.py` — Phase 03 MatchState v2 contract
- `src/pricing/live_theo.py` — Phase 03 LiveTheoEngine + TheoOutput shape
- `src/pricing/round_conclusion.py` — Phase 03 RoundConclusionLookup v2 surface
- `src/ingestion/arbiter.py` — Phase 03 6-stage timestamp lineage
- `src/config/constants.py` — Phase 03 baseline; Phase 04 extends per CRule 12

### Secondary (MEDIUM confidence)
- `pypi.org/project/kalshi-python` — official SDK at v2.1.4 (last release 2025-09-06); referenced for "do NOT use this — too bloated" decision
- `arxiv.org/pdf/1710.00431` — "Kelly's Criterion in Portfolio Optimization: A Decoupled Problem"; supports proportional-scaling aggregate-cap as v1 floor
- `agentbets.ai/guides/kelly-criterion-bet-sizing/` — implementation considerations for half-Kelly + per-trade cap in 2026 trading bots
- `github.com/octavi42/prediction-market-maker` — Paradigm hackathon #2 winner; supports `sigma_est ∝ sqrt(time)` framing for between-round vega → spread mapping

### Tertiary (LOW confidence — flagged for validation in Phase 5)
- `newyorkcityservers.com/blog/prediction-market-making-guide` — "Market Making on Prediction Markets: Complete 2026 Guide"; supports adverse-selection-by-category framing but not authoritative for Kalshi specifically
- Various Polymarket bot blogs (`quantvps.com`, `agentbets.ai/guides/polymarket-trading-bot-quickstart/`) — supports REST + WS hybrid pattern + reconciliation cadence; NOT directly applicable (Polymarket has different rate limits and fees)

## Metadata

**Confidence breakdown:**
- Standard stack (cryptography, websockets, aiohttp, tenacity): HIGH — all are pyproject deps OR Kalshi-docs-recommended.
- Architecture (mode selector / kill switches / sizing / fill ledger): HIGH — direct from PRD + DEC; pure-function patterns mirror Phase 03 conventions.
- Kalshi API surface (auth, REST, WS): HIGH — verified against `docs.kalshi.com` 2026-05-09; corrects stale CLAUDE.md PKCS1v15 claim.
- Pitfalls (auth path-with-query, RSA-PSS vs PKCS1v15, MIN_HALF_SPREAD < fees, exposure dec on settle): HIGH — all directly cited.
- Initial threshold values (`TAKE_THRESHOLD`, `MM_MIN_EDGE`, `POST_PLANT_TAKE_THRESHOLD`): LOW — placeholder guesses pending Phase 5 calibration; flagged.
- Post-plant vega formula: MEDIUM — recommended formula matches DEC-018 between-round shape but exact form is TBD per PRD §9.5.

**Research date:** 2026-05-09
**Valid until:** 2026-06-08 (30 days for stable APIs; if Phase 04 starts after this date, re-verify Kalshi RSA-PSS + WS URL + rate-limit token costs).
