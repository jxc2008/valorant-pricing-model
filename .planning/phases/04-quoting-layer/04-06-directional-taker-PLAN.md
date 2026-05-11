---
phase: 04-quoting-layer
plan: "06"
type: execute
wave: 4
depends_on: ["00", "01", "02", "04", "05"]
files_modified:
  - src/quoting/directional_taker.py
  - src/quoting/__init__.py
  - tests/quoting/test_directional_taker.py
autonomous: true
requirements:
  - REQ-directional-taker
notes: |
  Wave 4 — DIRECTIONAL_TAKE first-class peer to MM_BETWEEN_ROUND (DEC-001
  v2 / PRD §2.1). Parallelizable with 04-05 and 04-07 (disjoint files;
  CONSUMES fill_ledger.maybe_record_mm_fill from 04-05 task 1 and
  kelly_size from 04-02 task 1).

  Active only when `mode == DIRECTIONAL_TAKE` (rule 4 of plan 04-04's
  trading_mode). PRD §2.1 v2: MM and DIRECTIONAL are first-class PEERS, not
  primary/fallback — DIRECTIONAL evaluated BEFORE MM in declared rule order
  precisely so the "first match wins" ordering is grep-discoverable, NOT
  because DIRECTIONAL is "preferred". Paper trade (DEC-020 v2) decides
  which (or both) survives via the relative-Brier + fill-count gates.

  Per RESEARCH §"Pattern 4" anti-pattern #1 + DEC-020 v2: DIRECTIONAL writes
  fills ONLY to data/fills/{match_id}.directional_take.jsonl. Reuses the
  shared maybe_record_mm_fill helper from plan 04-05 — strategy routing is
  automatic via quote.strategy_id="DIRECTIONAL_TAKE". This is the
  load-bearing architectural invariant: the helper is misleadingly named
  ("mm_fill") but is strategy-agnostic; the test
  test_writes_directional_ledger_only verifies this.

  Order placement semantics (RESEARCH §"Code Examples" IOC block):
    - DIRECTIONAL_TAKE LIFTS the offer (when buying YES) or HITS the bid
      (when selling YES) — taker intent, NOT post_only.
    - Use time_in_force="immediate_or_cancel" so an unfilled order
      doesn't sit as a resting quote (would corrupt MM cancel-stale logic
      AND pay non-zero rate-budget tokens).
    - Place ONLY ONE leg per decision (the side that captures the edge):
      if theo > market.mid → buy YES at market.yes_ask (lift the offer);
      if theo < market.mid → sell YES at market.yes_bid (hit the bid).

  Sizing (DEC-023 v2 — calls kelly_size from plan 04-02 task 1):
    - PortfolioState.snapshot() → dict passed to kelly_size
    - On non-zero size, PortfolioState.on_place(series_id, fraction) MUST be
      invoked BEFORE the next theo computation (or kelly_size will return
      the SAME size on the next call and stack exposure). Phase 04 calls
      on_place immediately after place_quote returns True; plan 04-08
      reconciliation wires on_settle when the round resolves (Pitfall 5).
    - kelly_size returning 0 → no order placed; no ledger write; no
      PortfolioState mutation (consistent zero-effect).

  Bankroll injection: directional_taker has NO knowledge of bankroll
  storage — the caller (bot main loop) passes it explicitly. For Phase 04
  unit tests, fixtures pass bankroll_cents=100_000 (~$1k). Plan 04-08 wires
  the real bankroll source. CLAUDE.md "Dry-run by default" applies via the
  KalshiOrderManager.dry_run flag — taker has NO direct flag.

  series_id derivation: passed by caller. For Phase 04 unit tests, fixtures
  pass series_id="VAL-EVENT-T1-VS-T2" mirroring Kalshi event-ticker root
  convention. Plan 04-08 wires it from the actual MatchState — typically
  derived from a (team_a, team_b) hash or a Kalshi-side event identifier;
  the exact derivation is plan 04-08's concern.

  Idempotency edge: a DIRECTIONAL_TAKE is fire-and-forget (IOC) — re-calling
  take_directional twice in a row with the same theo + market_mid + state
  WILL place TWO orders if both calls return non-zero size. The caller
  (bot main loop) MUST gate calls on `seq_id` change OR on a mode-transition
  edge (IDLE → DIRECTIONAL_TAKE) — plan 04-08 wires this.
  directional_taker itself does NOT enforce idempotency (consistent with
  the IOC/taker contract). Test test_no_intrinsic_idempotency_gate covers.

must_haves:
  truths:
    - "take_directional(theo, market, ..., kelly_size_fn, mgr, ...) places exactly ONE Quote when |theo_c - market.mid| > TAKE_THRESHOLD"
    - "take_directional places ZERO quotes when |theo_c - market.mid| <= TAKE_THRESHOLD (defensive — caller should have routed via mode_selector, but guard against rule 4 false)"
    - "take_directional places ZERO quotes when kelly_size returns 0 (no edge OR aggregate cap binding)"
    - "Quote.strategy_id == \"DIRECTIONAL_TAKE\" for every placed order"
    - "Quote.action == \"buy\" AND Quote.price == market.yes_ask when theo*100 > market.mid (lift the offer)"
    - "Quote.action == \"sell\" AND Quote.price == market.yes_bid when theo*100 < market.mid (hit the bid)"
    - "On non-zero size, take_directional calls portfolio.on_place(series_id, fraction_of_bankroll) BEFORE returning"
    - "When kelly_size returns 0, portfolio.on_place is NOT called (no exposure mutation on zero-effect call)"
    - "Hypothetical fill recorded ONLY to data/fills/{match_id}.directional_take.jsonl (never .mm_between_round.jsonl)"
    - "take_directional has no resting quotes — IOC time_in_force; consistent with first-class-peer taker contract"
  artifacts:
    - path: "src/quoting/directional_taker.py"
      provides: "take_directional async coroutine — IOC lift/hit with portfolio Kelly sizing"
      min_lines: 90
      contains: "DIRECTIONAL_TAKE"
    - path: "tests/quoting/test_directional_taker.py"
      provides: "8+ tests covering lift / hit / threshold / kelly-zero / portfolio.on_place / separate ledger"
      contains: "test_writes_directional_ledger_only"
  key_links:
    - from: "src/quoting/directional_taker.take_directional"
      to: "src/sizing/kelly.kelly_size"
      via: "PortfolioState.snapshot() → kelly_size(theo, ask, bankroll, series_id, exposure_snap)"
      pattern: "kelly_size"
    - from: "src/quoting/directional_taker.take_directional"
      to: "src/quoting/fill_ledger.maybe_record_mm_fill"
      via: "strategy routing via Quote.strategy_id=\"DIRECTIONAL_TAKE\""
      pattern: "DIRECTIONAL_TAKE"
    - from: "src/quoting/directional_taker.take_directional"
      to: "src/quoting/portfolio.PortfolioState.on_place"
      via: "Pitfall 5 — exposure incremented at placement time"
      pattern: "on_place"
    - from: "src/quoting/directional_taker.take_directional"
      to: "src.config.constants.TAKE_THRESHOLD"
      via: "import + |theo_c - market.mid| > TAKE_THRESHOLD guard"
      pattern: "TAKE_THRESHOLD"
---

<objective>
Build the DIRECTIONAL_TAKE first-class peer (REQ-directional-taker v2) —
IOC lift/hit at the Kalshi top-of-book when |theo - market_mid| >
TAKE_THRESHOLD, sized by portfolio Kelly (DEC-023 v2 via plan 04-02),
written to its OWN ledger per DEC-020 v2 (RESEARCH §"Pattern 4"
anti-pattern #1 — combined files corrupt the promotion gate).

Purpose: REQ-directional-taker. Runs on its OWN hypothetical-fill ledger
parallel to MM; promotion gate (DEC-020 v2) evaluates the two ledgers
independently — DIRECTIONAL can promote to live even if MM is cut for
thin fills. PRD §2.1 v2 framing: MM and DIRECTIONAL are PEERS — declared
order in mode_selector is a tie-break, NOT a priority.

Output: src/quoting/directional_taker.py + 8+ GREEN tests covering all
8 must_have truths.
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
@.planning/phases/04-quoting-layer/04-04-mode-selector-PLAN.md
@.planning/phases/04-quoting-layer/04-05-mm-between-round-PLAN.md
@src/config/constants.py
@src/state/match_state.py

<interfaces>
<!-- Plan 04-01 surface this plan consumes -->
From src/quoting/order_manager.py:
```python
@dataclass(slots=True)
class Quote:
    ticker: str
    side: Literal["yes", "no"]
    action: Literal["buy", "sell"]
    price: int
    count: int
    strategy_id: Literal["MM_BETWEEN_ROUND", "DIRECTIONAL_TAKE", "POST_PLANT_QUOTE"]
    order_id: str | None = None
    placed_at: float | None = None
    client_order_id: str | None = None
```

<!-- Plan 04-01 market data surface -->
From src/quoting/market_data.py:
```python
@dataclass(frozen=True, slots=True)
class MarketQuote:
    yes_bid: int
    yes_ask: int
    mid: int
    spread: int
    is_valid: bool
    last_updated_ts: float
```

<!-- Plan 04-02 surfaces this plan consumes -->
From src/sizing/kelly.py:
```python
def kelly_size(
    theo: float, market_yes_ask: int, bankroll: int, series_id: str,
    current_series_exposure: dict[str, float],
) -> int: ...   # contracts; 0 if any cap binds
```

From src/quoting/portfolio.py:
```python
class PortfolioState:
    def on_place(self, series_id: str, fraction: float) -> None: ...
    def on_settle(self, series_id: str, fraction: float) -> None: ...
    def snapshot(self) -> dict[str, float]: ...
    def current(self, series_id: str) -> float: ...
```

<!-- Plan 04-05 fill ledger surface this plan REUSES -->
From src/quoting/fill_ledger.py:
```python
def maybe_record_mm_fill(
    quote: Quote, last_mid_c: int, next_mid_c: int, seq_id: int, theo_c: int,
    ledger_dir: Path, match_id: str,
) -> bool: ...
# Strategy routing is automatic via quote.strategy_id — the "mm" in the
# function name is misleading; helper is strategy-agnostic.
```

<!-- Phase 04 constants from plan 04-00 -->
From src/config/constants.py:
```python
TAKE_THRESHOLD: Final[int] = 5             # cents — DIRECTIONAL trigger
```

<!-- New surface this plan creates -->
NEW src/quoting/directional_taker.py public surface:
```python
async def take_directional(
    state: MatchState,
    theo: TheoOutput,
    market: MarketQuote,
    mgr: KalshiOrderManager,
    portfolio: PortfolioState,
    ticker: str,
    series_id: str,
    bankroll_cents: int,
    last_mid_c: int,
    ledger_dir: Path,
    *,
    seq_id: int | None = None,
) -> bool: ...                            # True iff an order was placed
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: src/quoting/directional_taker.py + GREEN test_directional_taker.py</name>
  <files>src/quoting/directional_taker.py, src/quoting/__init__.py, tests/quoting/test_directional_taker.py</files>
  <behavior>
    - take_directional with |theo_c - market.mid| <= TAKE_THRESHOLD returns False; mgr.active_quotes empty; portfolio.snapshot() unchanged
    - take_directional with theo_c=60, market.mid=50 (diff=10 > 5) AND positive kelly_size → places 1 Quote with action="buy", price=market.yes_ask, side="yes", strategy_id="DIRECTIONAL_TAKE"
    - take_directional with theo_c=40, market.mid=50 (diff=10 > 5) AND positive kelly_size → places 1 Quote with action="sell", price=market.yes_bid, side="yes"
    - When kelly_size returns 0 (cap binding), take_directional returns False; NO quote placed; portfolio.snapshot() unchanged
    - On successful place, take_directional calls portfolio.on_place(series_id, count*price/bankroll_cents) — fractional exposure increment
    - take_directional reuses maybe_record_mm_fill — fill (if next_mid_c crosses quote price) lands in directional_take.jsonl ONLY
    - take_directional has NO intrinsic idempotency gate — two back-to-back calls with same inputs place TWO orders (consistent with IOC/taker contract; caller gates on seq_id change)
    - Bankroll boundary: bankroll_cents=0 → kelly_size returns 0 → no order; defensive
    - market.is_valid=False → take_directional returns False without calling kelly_size (defensive layer — kill_switch_market_invalid normally catches this at the mode_selector gate, but the taker double-checks)
  </behavior>
  <action>
(A) Create src/quoting/directional_taker.py (~120 lines):

```python
"""DIRECTIONAL_TAKE first-class peer to MM_BETWEEN_ROUND (REQ-directional-taker v2).

Active when trading_mode == "DIRECTIONAL_TAKE" (plan 04-04 rule 4). PRD §2.1
v2 explicit: MM and DIRECTIONAL are PEERS, not primary/fallback — declared
order in mode_selector is the tie-break, NOT a priority ranking.

IOC (immediate-or-cancel) lift/hit at the Kalshi top-of-book per RESEARCH
§"Code Examples" IOC block:
    theo_c > market.mid → action="buy",  price=market.yes_ask (lift offer)
    theo_c < market.mid → action="sell", price=market.yes_bid (hit bid)

NO resting quote — IOC time_in_force ensures unfilled orders are cancelled
automatically by Kalshi rather than sitting and corrupting MM stale-quote
detection (plan 04-05). One leg per call; no two-sided quoting.

Sizing per DEC-023 v2 (calls plan 04-02 kelly_size + PortfolioState):
    snap = portfolio.snapshot()
    size = kelly_size(theo, ask, bankroll_cents, series_id, snap)
    if size == 0: return False  (no edge OR aggregate cap binding)
    place(size); portfolio.on_place(series_id, size * ask_dollars / bankroll_dollars)

CRITICAL — separate ledger per DEC-020 v2 / RESEARCH §"Pattern 4" anti-
pattern #1: writes ONLY to data/fills/{match_id}.directional_take.jsonl via
the strategy-agnostic maybe_record_mm_fill helper from plan 04-05. The
"mm" in the function name is misleading (RESEARCH calls this out) —
routing is by quote.strategy_id, which we set to "DIRECTIONAL_TAKE".

Idempotency: take_directional is FIRE-AND-FORGET — back-to-back calls
with identical inputs WILL place two orders. The caller (bot main loop
in plan 04-08) gates on seq_id change OR on a mode-transition edge
(IDLE → DIRECTIONAL_TAKE). This contract matches the IOC/taker shape;
diff against MM which is idempotent on unchanged inputs (plan 04-05).

Source: PRD §2.1 v2 / DEC-001 v2 / DEC-023 v2 / ROADMAP §4.4 / RESEARCH
§"Architecture Patterns" Pattern 4 + §"Common Pitfalls" Pitfall 5.
"""
from __future__ import annotations

from pathlib import Path

from src.config.constants import TAKE_THRESHOLD
from src.pricing.data import TheoOutput
from src.quoting.fill_ledger import maybe_record_mm_fill
from src.quoting.market_data import MarketQuote
from src.quoting.order_manager import KalshiOrderManager, Quote
from src.quoting.portfolio import PortfolioState
from src.sizing.kelly import kelly_size
from src.state.match_state import MatchState


async def take_directional(
    state: MatchState,
    theo: TheoOutput,
    market: MarketQuote,
    mgr: KalshiOrderManager,
    portfolio: PortfolioState,
    ticker: str,
    series_id: str,
    bankroll_cents: int,
    last_mid_c: int,
    ledger_dir: Path,
    *,
    seq_id: int | None = None,
) -> bool:
    """Lift the offer (or hit the bid) on a directional edge.

    Returns True iff an order was placed AND portfolio.on_place was called.
    False on any of:
        - |theo_c - market.mid| <= TAKE_THRESHOLD (defensive — caller should
          have routed elsewhere via mode_selector)
        - market.is_valid is False (defensive double-check)
        - kelly_size returned 0 (no edge OR aggregate cap binding)
        - bankroll_cents <= 0

    On non-zero size, exposure is incremented at placement time per Pitfall 5.
    Plan 04-08 reconciliation wires the on_settle path when the round
    resolves.
    """
    # Defensive guard — caller should normally route via mode_selector,
    # but the taker double-checks.
    theo_c = round(theo.theo_series * 100)
    if abs(theo_c - market.mid) <= TAKE_THRESHOLD:
        return False
    if not market.is_valid:
        return False
    if bankroll_cents <= 0:
        return False

    # Determine side based on theo vs market direction.
    if theo_c > market.mid:
        # Buy YES — lift the offer at market.yes_ask.
        action = "buy"
        price = market.yes_ask
        ask_for_kelly = market.yes_ask
    else:
        # Sell YES — hit the bid at market.yes_bid.
        # For Kelly sizing on a sell, "P(YES wins)" becomes "P(YES loses)"
        # and the ask becomes the NO ask = 100 - yes_bid. Convert.
        action = "sell"
        price = market.yes_bid
        # When we sell YES at market.yes_bid, our payoff is winning if YES
        # LOSES — so effective p = 1 - theo, effective ask = 100 - yes_bid.
        ask_for_kelly = 100 - market.yes_bid

    # Defensive ask boundary (plan 04-02 kelly_size also guards).
    if ask_for_kelly <= 0 or ask_for_kelly >= 100:
        return False

    # Compute sizing — Kelly takes (effective theo, effective ask).
    effective_theo = theo.theo_series if action == "buy" else (1.0 - theo.theo_series)
    snap = portfolio.snapshot()
    size = kelly_size(
        effective_theo, ask_for_kelly, bankroll_cents, series_id, snap,
    )
    if size == 0:
        return False  # aggregate cap binding or no edge after caps

    quote = Quote(
        ticker=ticker,
        side="yes",
        action=action,  # type: ignore[arg-type]
        price=price,
        count=size,
        strategy_id="DIRECTIONAL_TAKE",
    )
    placed = await mgr.place_quote(quote)
    if not placed:
        return False

    # Increment exposure ONLY on successful place (Pitfall 5).
    # fraction = (size * ask_for_kelly cents) / bankroll_cents
    fraction = (size * ask_for_kelly) / bankroll_cents
    portfolio.on_place(series_id, fraction)

    # Record hypothetical fill (touched rule against last_mid_c → market.mid).
    # The fill records seq_id and strategy="DIRECTIONAL_TAKE" via the
    # strategy-agnostic helper from plan 04-05.
    sid = seq_id if seq_id is not None else state.seq_id
    maybe_record_mm_fill(
        quote=quote,
        last_mid_c=last_mid_c,
        next_mid_c=market.mid,
        seq_id=sid,
        theo_c=theo_c,
        ledger_dir=ledger_dir,
        match_id=state.match_id,
    )
    return True
```

(B) Update src/quoting/__init__.py to export take_directional.

(C) Flip RED stubs in tests/quoting/test_directional_taker.py to GREEN:

```python
"""Plan 04-06 — REQ-directional-taker (v2 first-class peer) GREEN tests.

DEC-023 v2 portfolio Kelly sizing + DEC-020 v2 separate-ledger invariant.
"""
from __future__ import annotations

import json
from pathlib import Path

import aiohttp
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from src.config.constants import TAKE_THRESHOLD
from src.pricing.data import TheoOutput
from src.quoting.directional_taker import take_directional
from src.quoting.market_data import MarketQuote, make_quote
from src.quoting.order_manager import KalshiOrderManager
from src.quoting.portfolio import PortfolioState


def _theo(theo_series: float = 0.50) -> TheoOutput:
    return TheoOutput(theo_series=theo_series, theo_map=(theo_series,),
                       vega=0.0, confidence=1.0)


@pytest.fixture
async def mgr(fake_private_key: rsa.RSAPrivateKey) -> KalshiOrderManager:
    async with aiohttp.ClientSession() as session:
        yield KalshiOrderManager(session=session, key_id="K", private_key=fake_private_key, dry_run=True)


@pytest.fixture
def portfolio() -> PortfolioState:
    return PortfolioState()


# ---------------- threshold gating ----------------

@pytest.mark.asyncio
async def test_no_take_below_threshold(
    mgr: KalshiOrderManager, portfolio: PortfolioState,
    make_match_state, tmp_fill_ledger_dir: Path,
) -> None:
    """|theo_c - mid| == TAKE_THRESHOLD (5) — NOT > 5 → no take."""
    state = make_match_state(bomb_planted=False, time_left_s=None)
    market = make_quote(48, 52)  # mid=50
    result = await take_directional(
        state, _theo(0.55), market, mgr, portfolio,
        ticker="VAL-T1-WIN", series_id="S1", bankroll_cents=100_000,
        last_mid_c=50, ledger_dir=tmp_fill_ledger_dir,
    )
    assert result is False
    assert mgr.active_quotes == {}
    assert portfolio.snapshot() == {}


@pytest.mark.asyncio
async def test_take_above_threshold_lifts_offer(
    mgr: KalshiOrderManager, portfolio: PortfolioState,
    make_match_state, tmp_fill_ledger_dir: Path,
) -> None:
    """theo=0.60 (60c), mid=50 → diff=10 > 5 → lift offer (buy yes at yes_ask)."""
    state = make_match_state(bomb_planted=False, time_left_s=None)
    market = make_quote(48, 52)  # mid=50, yes_ask=52
    result = await take_directional(
        state, _theo(0.60), market, mgr, portfolio,
        ticker="VAL-T1-WIN", series_id="S1", bankroll_cents=100_000,
        last_mid_c=50, ledger_dir=tmp_fill_ledger_dir,
    )
    assert result is True
    legs = mgr.active_quotes["VAL-T1-WIN"]
    assert len(legs) == 1
    quote = next(iter(legs.values()))
    assert quote.action == "buy"
    assert quote.price == 52  # market.yes_ask
    assert quote.side == "yes"
    assert quote.strategy_id == "DIRECTIONAL_TAKE"


@pytest.mark.asyncio
async def test_take_below_mid_hits_bid(
    mgr: KalshiOrderManager, portfolio: PortfolioState,
    make_match_state, tmp_fill_ledger_dir: Path,
) -> None:
    """theo=0.40 (40c), mid=50 → diff=10 > 5 → hit bid (sell yes at yes_bid)."""
    state = make_match_state(bomb_planted=False, time_left_s=None)
    market = make_quote(48, 52)  # mid=50, yes_bid=48
    result = await take_directional(
        state, _theo(0.40), market, mgr, portfolio,
        ticker="VAL-T1-WIN", series_id="S1", bankroll_cents=100_000,
        last_mid_c=50, ledger_dir=tmp_fill_ledger_dir,
    )
    assert result is True
    quote = next(iter(mgr.active_quotes["VAL-T1-WIN"].values()))
    assert quote.action == "sell"
    assert quote.price == 48  # market.yes_bid


# ---------------- Kelly + portfolio state wiring ----------------

@pytest.mark.asyncio
async def test_kelly_zero_blocks_placement(
    mgr: KalshiOrderManager, portfolio: PortfolioState,
    make_match_state, tmp_fill_ledger_dir: Path,
) -> None:
    """Pre-load series exposure to SERIES_AGGREGATE_CAP_FRAC → kelly_size returns 0."""
    portfolio.on_place("S1", 0.10)  # exact aggregate cap
    state = make_match_state(bomb_planted=False, time_left_s=None)
    market = make_quote(48, 52)
    result = await take_directional(
        state, _theo(0.99), market, mgr, portfolio,
        ticker="VAL-T1-WIN", series_id="S1", bankroll_cents=100_000,
        last_mid_c=50, ledger_dir=tmp_fill_ledger_dir,
    )
    assert result is False
    assert mgr.active_quotes == {}
    # Exposure unchanged from pre-load
    assert portfolio.current("S1") == pytest.approx(0.10)


@pytest.mark.asyncio
async def test_portfolio_on_place_called_on_success(
    mgr: KalshiOrderManager, portfolio: PortfolioState,
    make_match_state, tmp_fill_ledger_dir: Path,
) -> None:
    """Pitfall 5: exposure MUST be incremented at placement time."""
    state = make_match_state(bomb_planted=False, time_left_s=None)
    market = make_quote(48, 52)
    pre = portfolio.current("S1")
    result = await take_directional(
        state, _theo(0.60), market, mgr, portfolio,
        ticker="VAL-T1-WIN", series_id="S1", bankroll_cents=100_000,
        last_mid_c=50, ledger_dir=tmp_fill_ledger_dir,
    )
    assert result is True
    post = portfolio.current("S1")
    assert post > pre


@pytest.mark.asyncio
async def test_portfolio_unchanged_when_kelly_zero(
    mgr: KalshiOrderManager, portfolio: PortfolioState,
    make_match_state, tmp_fill_ledger_dir: Path,
) -> None:
    """When kelly_size returns 0, on_place is NOT called."""
    portfolio.on_place("S1", 0.10)  # cap binding
    state = make_match_state(bomb_planted=False, time_left_s=None)
    market = make_quote(48, 52)
    await take_directional(
        state, _theo(0.99), market, mgr, portfolio,
        ticker="VAL-T1-WIN", series_id="S1", bankroll_cents=100_000,
        last_mid_c=50, ledger_dir=tmp_fill_ledger_dir,
    )
    assert portfolio.current("S1") == pytest.approx(0.10)


# ---------------- Separate-ledger invariant (DEC-020 v2) ----------------

@pytest.mark.asyncio
async def test_writes_directional_ledger_only(
    mgr: KalshiOrderManager, portfolio: PortfolioState,
    make_match_state, tmp_fill_ledger_dir: Path,
) -> None:
    """RESEARCH §"Pattern 4" anti-pattern #1: DIRECTIONAL fills NEVER land in mm_between_round.jsonl."""
    state = make_match_state(bomb_planted=False, time_left_s=None, match_id="M-X")
    market = make_quote(48, 52)  # mid=50
    # Touched-rule: last_mid_c=51, next_mid_c=50 — for action=buy at price=52,
    # need next_mid_c < 52 <= last_mid_c. last_mid_c=53 satisfies; next_mid_c=50 < 52 ✓.
    await take_directional(
        state, _theo(0.60), market, mgr, portfolio,
        ticker="VAL-T1-WIN", series_id="S1", bankroll_cents=100_000,
        last_mid_c=53, ledger_dir=tmp_fill_ledger_dir,
    )
    directional_path = tmp_fill_ledger_dir / "M-X.directional_take.jsonl"
    mm_path = tmp_fill_ledger_dir / "M-X.mm_between_round.jsonl"
    assert directional_path.exists()
    assert not mm_path.exists()
    parsed = json.loads(directional_path.read_text().splitlines()[0])
    assert parsed["strategy"] == "DIRECTIONAL_TAKE"


# ---------------- Defensive guards ----------------

@pytest.mark.asyncio
async def test_market_invalid_short_circuit(
    mgr: KalshiOrderManager, portfolio: PortfolioState,
    make_match_state, tmp_fill_ledger_dir: Path,
) -> None:
    """market.is_valid=False → no take even with strong edge."""
    state = make_match_state(bomb_planted=False, time_left_s=None)
    market = MarketQuote(yes_bid=48, yes_ask=52, mid=50, spread=4,
                          is_valid=False, last_updated_ts=0.0)
    result = await take_directional(
        state, _theo(0.99), market, mgr, portfolio,
        ticker="VAL-T1-WIN", series_id="S1", bankroll_cents=100_000,
        last_mid_c=50, ledger_dir=tmp_fill_ledger_dir,
    )
    assert result is False


@pytest.mark.asyncio
async def test_zero_bankroll_short_circuit(
    mgr: KalshiOrderManager, portfolio: PortfolioState,
    make_match_state, tmp_fill_ledger_dir: Path,
) -> None:
    state = make_match_state(bomb_planted=False, time_left_s=None)
    market = make_quote(48, 52)
    result = await take_directional(
        state, _theo(0.99), market, mgr, portfolio,
        ticker="VAL-T1-WIN", series_id="S1", bankroll_cents=0,
        last_mid_c=50, ledger_dir=tmp_fill_ledger_dir,
    )
    assert result is False


# ---------------- IOC / fire-and-forget contract ----------------

@pytest.mark.asyncio
async def test_no_intrinsic_idempotency_gate(
    mgr: KalshiOrderManager, portfolio: PortfolioState,
    make_match_state, tmp_fill_ledger_dir: Path,
) -> None:
    """Two back-to-back calls with identical inputs place TWO orders.

    Consistent with the IOC/taker contract — the caller (plan 04-08 bot
    main loop) is responsible for gating on seq_id change.
    """
    state = make_match_state(bomb_planted=False, time_left_s=None)
    market = make_quote(48, 52)
    await take_directional(state, _theo(0.60), market, mgr, portfolio,
                            ticker="VAL-T1-WIN", series_id="S1",
                            bankroll_cents=100_000, last_mid_c=50,
                            ledger_dir=tmp_fill_ledger_dir)
    pre_legs_count = sum(len(legs) for legs in mgr.active_quotes.values())
    # KalshiOrderManager stores legs by f"{action}_{side}" — two back-to-back
    # buy_yes calls will OVERWRITE the leg key in dry-run; verify by checking
    # portfolio.on_place was called TWICE (exposure doubled).
    pre_exposure = portfolio.current("S1")
    await take_directional(state, _theo(0.60), market, mgr, portfolio,
                            ticker="VAL-T1-WIN", series_id="S1",
                            bankroll_cents=100_000, last_mid_c=50,
                            ledger_dir=tmp_fill_ledger_dir)
    post_exposure = portfolio.current("S1")
    # Exposure incremented again → on_place fired twice → no idempotency gate.
    assert post_exposure == pytest.approx(2 * pre_exposure)
```
  </action>
  <verify>
    <automated>uv run pytest tests/quoting/test_directional_taker.py -x --no-cov &amp;&amp; uv run mypy --strict src/quoting/ src/sizing/</automated>
  </verify>
  <done>
- src/quoting/directional_taker.py defines take_directional coroutine.
- 10 tests in tests/quoting/test_directional_taker.py pass GREEN.
- DIRECTIONAL fills land ONLY in data/fills/{match_id}.directional_take.jsonl (separate-ledger invariant verified).
- portfolio.on_place called on success; NOT called when kelly_size returns 0 (Pitfall 5 mitigation).
- Lift offer / hit bid semantics verified for both theo > mid and theo < mid branches.
- IOC fire-and-forget contract documented + test (no intrinsic idempotency gate).
- src/quoting/__init__.py exports take_directional.
- mypy --strict src/quoting/ + src/sizing/ clean.
  </done>
</task>

</tasks>

<verification>
1. `uv run pytest tests/quoting/test_directional_taker.py -x --no-cov` — 10 GREEN.
2. `uv run mypy --strict src/quoting/ src/sizing/` clean.
3. `uv run pytest tests/ -x --no-cov` — Phase 03 + plans 04-00..04-06 stay green; remaining stubs (07, 08) xfail.
4. `rg "mm_between_round" src/quoting/directional_taker.py` returns empty (no peer-strategy ledger writes).
5. `rg "POST_PLANT_QUOTE" src/quoting/directional_taker.py` returns empty (no peer-strategy contamination).
6. `python -c "from src.quoting import take_directional; print(take_directional)"` runs without ImportError.
</verification>

<success_criteria>
- DIRECTIONAL_TAKE writes fills ONLY to data/fills/{match_id}.directional_take.jsonl (DEC-020 v2 separate-ledger invariant).
- Sizing via plan 04-02 kelly_size + PortfolioState; on_place fires at placement time (Pitfall 5 mitigation).
- Lift-the-offer / hit-the-bid semantics correctly differentiated by theo vs mid.
- Defensive guards (market.is_valid, zero bankroll) prevent live mode from placing orders without proper market data.
- IOC fire-and-forget contract: no intrinsic idempotency gate; caller responsible for seq_id gating (plan 04-08).
</success_criteria>

<output>
After completion, create `.planning/phases/04-quoting-layer/04-06-SUMMARY.md` documenting:
- src/quoting/directional_taker.py file contents (~120 lines).
- 10 test results — incl. test_writes_directional_ledger_only (proves DEC-020 v2 separate-ledger invariant).
- Forward link: plan 04-07 (post-plant quoter also REUSES maybe_record_mm_fill — three-strategy routing now verified live), plan 04-08 (E2E test asserts MM + DIRECTIONAL fills land in different files AND mode transitions IDLE↔DIRECTIONAL leave no stale orders).
</output>
