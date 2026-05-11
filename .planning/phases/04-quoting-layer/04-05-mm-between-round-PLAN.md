---
phase: 04-quoting-layer
plan: "05"
type: execute
wave: 4
depends_on: ["00", "01", "02", "03", "04"]
files_modified:
  - src/quoting/mm_quoter.py
  - src/quoting/fill_ledger.py
  - src/quoting/__init__.py
  - tests/quoting/test_mm_quoter.py
  - tests/quoting/test_fill_ledger.py
autonomous: true
requirements:
  - REQ-mm-quoter
notes: |
  Wave 4 — MM_BETWEEN_ROUND quoter (REQ-mm-quoter v2 narrowed) + shared
  fill-ledger module that 04-06 (directional taker) + 04-07 (post-plant
  quoter) co-own (writes go to disjoint per-strategy files per DEC-020 v2).
  Parallelizable with 04-06 and 04-07 (disjoint files; 04-06 only APPENDS
  imports to fill_ledger.py via the same atomic-commit Rule-3 pattern).

  Active only when `mode == MM_BETWEEN_ROUND` (rule 5 of plan 04-04's
  trading_mode). The quoter is a pure-ish coroutine: it takes (state, theo,
  market, vega_between, mgr, ledger_dir, last_mid_c) and:
    1. Computes half-spread per DEC-018 v2: `hs = max(MIN_HALF_SPREAD,
       k_vega * sqrt(vega_between)) + staleness_penalty`.
    2. Cancels any stale resting MM quotes (different price or > 2s old).
    3. Places fresh yes-buy at `theo_c - hs` and yes-sell at `theo_c + hs`,
       strategy_id="MM_BETWEEN_ROUND" tagged on the Quote dataclass per
       plan 04-01.
    4. Calls `maybe_record_mm_fill(...)` for every resting quote against the
       (last_mid_c, market.mid) transition — RESEARCH §"Pattern 4" simple
       "limit touched" rule (DEC-020 — order-fill backtest is OUT OF SCOPE;
       no queue position / no slippage / no partial fills).

  CRITICAL — separate ledgers per DEC-020 v2 (RESEARCH §"Pattern 4"
  anti-pattern #1). MM and DIRECTIONAL fills MUST land in different files:
    - data/fills/{match_id}.mm_between_round.jsonl
    - data/fills/{match_id}.directional_take.jsonl
    - data/fills/{match_id}.post_plant_quote.jsonl
  Combined writes corrupt the promotion gate (DEC-020 v2 evaluates the two
  ledgers independently — MM can be cut while DIRECTIONAL promotes).

  CRITICAL — `MIN_HALF_SPREAD = 3` floor MUST beat Kalshi maker fee + 1c
  slippage budget (RESEARCH Pitfall 4 — verified 2026-05-09 against
  kalshi.com/docs/kalshi-fee-schedule.pdf). 3c half-spread quoting at
  theo±3c earns 0.44c maker fee at theo=50c (25% of 1.75c taker), netting
  2.56c if theo is exact. Calibrate down to 2c only after Phase 5
  paper-trade shows the floor is tight. Property test
  test_spread_floor_beats_fee covers this invariant.

  Staleness penalty: `time.time() - state.last_updated_ts > 2.0s` widens the
  spread (or pulls quotes outright per PRD §5.4). Phase 04 ships the widen
  branch — pull-on-staleness is the kill_switch_staleness path in plan
  04-03 (5s threshold). Between 2s and 5s, widen by `(age - 2) * 1c/s`
  added to the half-spread; > 5s, kill switch trips and 04-08's
  cancel-all-on-trip handler clears the book.

  `k_vega` constant lives in src/config/constants.py as
  `MM_VEGA_SPREAD_K: Final[float] = 50.0` (TBD; initial guess that scales
  Phase 1's typical vega_between range [0.001, 0.01] into a [1.5c, 5c]
  spread band on top of the 3c floor). Atomic same-commit pattern: add the
  constant AND extend tests/config/test_constants.py allow-list in the
  same commit (Phase 03 D-08 carry-forward).

  Hypothetical-fill recording cadence: invoked at every theo computation
  (mode == MM_BETWEEN_ROUND) using (last_mid_c, current_market.mid) as the
  touched-rule inputs. `last_mid_c` is threaded through the bot main loop
  (plan 04-08 wires it; for Phase 04 unit tests, fixtures pass it directly).

  Dry-run by default per DEC-022 — KalshiOrderManager.dry_run flag from
  plan 04-01 shortcuts the network path. mm_quoter has NO knowledge of
  dry-run vs live (delegates entirely to the order manager).

must_haves:
  truths:
    - "compute_half_spread(vega_between, staleness_s) returns max(MIN_HALF_SPREAD, MM_VEGA_SPREAD_K * sqrt(vega_between)) + staleness_penalty"
    - "compute_half_spread returns >= MIN_HALF_SPREAD (3c) for any non-negative vega and staleness — floor invariant verified by hypothesis property test"
    - "compute_half_spread floor beats Kalshi maker fee (0.44c at theo=50c) + 1c slippage budget — property test"
    - "quote_mm_between_round() places yes-buy at theo_c - hs AND yes-sell at theo_c + hs through KalshiOrderManager.place_quote"
    - "Every Quote placed by quote_mm_between_round has strategy_id=\"MM_BETWEEN_ROUND\""
    - "On stale quotes (price mismatch OR placed > 2s ago), quote_mm_between_round cancels them via KalshiOrderManager.cancel_quote BEFORE placing fresh quotes"
    - "Hypothetical-fill simulation: yes-buy at P fills iff next_mid_c < P <= last_mid_c (limit touched)"
    - "Hypothetical-fill simulation: yes-sell at P fills iff last_mid_c <= P < next_mid_c"
    - "Recorded fills append to data/fills/{match_id}.mm_between_round.jsonl with strategy=\"MM_BETWEEN_ROUND\""
    - "Recorded fills NEVER append to .directional_take.jsonl or .post_plant_quote.jsonl"
    - "HypotheticalFill record contains seq_id, strategy, ticker, side, action, price_c, count, theo_c_at_fill, market_mid_c_at_fill (per RESEARCH §\"Pattern 4\")"
  artifacts:
    - path: "src/quoting/mm_quoter.py"
      provides: "compute_half_spread + quote_mm_between_round coroutine"
      min_lines: 100
      contains: "MM_BETWEEN_ROUND"
    - path: "src/quoting/fill_ledger.py"
      provides: "HypotheticalFill dataclass + append_fill + maybe_record_mm_fill (touched rule)"
      min_lines: 80
      contains: "HypotheticalFill"
    - path: "src/config/constants.py"
      provides: "MM_VEGA_SPREAD_K constant (TBD calibrate phase-5)"
      contains: "MM_VEGA_SPREAD_K"
    - path: "tests/quoting/test_mm_quoter.py"
      provides: "8+ tests: spread formula + floor invariant + place + cancel-stale + strategy_id tag"
      contains: "test_spread_floor_beats_fee"
    - path: "tests/quoting/test_fill_ledger.py"
      provides: "8+ tests: simulate touched rule (buy + sell + no-touch) + per-strategy file path + JSONL schema"
      contains: "test_per_strategy_ledger_separate_files"
  key_links:
    - from: "src/quoting/mm_quoter.quote_mm_between_round"
      to: "src/quoting/order_manager.KalshiOrderManager.place_quote + cancel_quote"
      via: "Quote dataclass with strategy_id=\"MM_BETWEEN_ROUND\""
      pattern: "MM_BETWEEN_ROUND"
    - from: "src/quoting/mm_quoter.compute_half_spread"
      to: "src.config.constants.MIN_HALF_SPREAD + MM_VEGA_SPREAD_K"
      via: "import + floor math (DEC-018 v2 / Pitfall 4)"
      pattern: "MIN_HALF_SPREAD"
    - from: "src/quoting/fill_ledger.maybe_record_mm_fill"
      to: "data/fills/{match_id}.mm_between_round.jsonl"
      via: "append_fill writes one JSONL line per touched-rule fill"
      pattern: "mm_between_round.jsonl"
    - from: "src/quoting/mm_quoter.quote_mm_between_round"
      to: "plan 04-04 mode_selector returning MM_BETWEEN_ROUND"
      via: "caller (bot main loop) dispatches on trading_mode return value"
      pattern: "MM_BETWEEN_ROUND"
---

<objective>
Build the MM_BETWEEN_ROUND quoter (REQ-mm-quoter v2) + shared
hypothetical-fill ledger module. The quoter is the first-class peer to the
directional taker (DEC-001 v2) — runs on its OWN ledger
(data/fills/{match_id}.mm_between_round.jsonl) so paper-trade promotion
gate (DEC-020 v2) evaluates MM independently of DIRECTIONAL via the
fill-count gate.

Purpose: REQ-mm-quoter (v2 narrowed to between-round only). Spread floor
per DEC-018 v2: `spread = max(MIN_HALF_SPREAD, k × sqrt(vega_between)) +
staleness_penalty`. Floor MUST beat Kalshi maker fee + slippage (RESEARCH
Pitfall 4 — verified at theo=50c: 0.44c maker fee × 1c slippage budget).
Hypothetical fills written to per-strategy JSONL files so Phase 5 Brier
computation is `cat data/fills/{id}.mm_between_round.jsonl | python -c
"..."` without filtering.

Output: src/quoting/mm_quoter.py + src/quoting/fill_ledger.py + 1 new
constant (MM_VEGA_SPREAD_K) + 16+ GREEN tests covering spread formula
invariants, simulate-touched rule, separate-ledger routing.
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
@.planning/phases/04-quoting-layer/04-04-mode-selector-PLAN.md
@src/config/constants.py
@src/state/match_state.py
@src/pricing/data.py
@src/pricing/live_theo.py

<interfaces>
<!-- Plan 04-01 surface this plan consumes -->
From src/quoting/order_manager.py:
```python
@dataclass(slots=True)
class Quote:
    ticker: str
    side: Literal["yes", "no"]
    action: Literal["buy", "sell"]
    price: int                                 # cents 1-99
    count: int
    strategy_id: Literal["MM_BETWEEN_ROUND", "DIRECTIONAL_TAKE", "POST_PLANT_QUOTE"]
    order_id: str | None = None
    placed_at: float | None = None
    client_order_id: str | None = None

class KalshiOrderManager:
    @property
    def active_quotes(self) -> dict[str, dict[str, Quote]]: ...
    async def place_quote(self, quote: Quote) -> bool: ...
    async def cancel_quote(self, ticker: str, leg_key: str) -> bool: ...
    async def cancel_all_orders(self) -> None: ...
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

def make_quote(yes_bid: int, yes_ask: int, *, is_valid: bool = True) -> MarketQuote: ...
```

<!-- Plan 04-04 mode-selector surface -->
From src/quoting/mode_selector.py:
```python
TradingMode = Literal["MM_BETWEEN_ROUND", "DIRECTIONAL_TAKE", "POST_PLANT_QUOTE", "IDLE"]
def trading_mode(state, theo, market, vega_between, vega_post_plant, kill_switch_active) -> TradingMode: ...
```

<!-- Phase 1 pricing surface -->
From src/pricing/data.py:
```python
@dataclass(frozen=True, slots=True)
class TheoOutput:
    theo_series: float
    theo_map: tuple[float, ...]
    vega: float                                # = vega_between_round (DEC-018 D-10/D-11)
    confidence: float
```

<!-- Phase 04 constants from plan 04-00 + this plan -->
From src/config/constants.py:
```python
MIN_HALF_SPREAD: Final[int] = 3            # cents, plan 04-00
MM_MIN_EDGE: Final[int] = 4                # cents, plan 04-00
# NEW in this plan:
MM_VEGA_SPREAD_K: Final[float] = 50.0      # k in `k * sqrt(vega_between)` (TBD)
```

<!-- New surfaces this plan creates -->
NEW src/quoting/mm_quoter.py public surface:
```python
def compute_half_spread(
    vega_between: float,
    staleness_s: float,
) -> int: ...                                   # cents; >= MIN_HALF_SPREAD

async def quote_mm_between_round(
    state: MatchState,
    theo: TheoOutput,
    market: MarketQuote,
    mgr: KalshiOrderManager,
    ticker: str,
    count: int,
    *,
    now: float | None = None,
) -> None: ...                                  # places / cancels via mgr; pure I/O
```

NEW src/quoting/fill_ledger.py public surface:
```python
@dataclass(frozen=True, slots=True)
class HypotheticalFill:
    seq_id: int
    strategy: str                               # "MM_BETWEEN_ROUND" | "DIRECTIONAL_TAKE" | "POST_PLANT_QUOTE"
    ticker: str
    side: Literal["yes", "no"]
    action: Literal["buy", "sell"]
    price_c: int
    count: int
    theo_c_at_fill: int
    market_mid_c_at_fill: int
    realized_outcome: bool | None = None
    pnl_cents: int | None = None

    def to_jsonl_line(self) -> str: ...

def append_fill(fill: HypotheticalFill, ledger_dir: Path, match_id: str) -> None: ...

def simulate_touched(
    quote_price_c: int,
    quote_action: Literal["buy", "sell"],
    last_mid_c: int,
    next_mid_c: int,
) -> bool: ...

def maybe_record_mm_fill(
    quote: Quote,
    last_mid_c: int,
    next_mid_c: int,
    seq_id: int,
    theo_c: int,
    ledger_dir: Path,
    match_id: str,
) -> bool: ...
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: src/quoting/fill_ledger.py + MM_VEGA_SPREAD_K constant + GREEN test_fill_ledger.py</name>
  <files>src/quoting/fill_ledger.py, src/quoting/__init__.py, src/config/constants.py, tests/config/test_constants.py, tests/quoting/test_fill_ledger.py</files>
  <behavior>
    - HypotheticalFill is frozen+slots; to_jsonl_line() returns a JSON string with no trailing newline (caller appends \n)
    - simulate_touched("buy", P, last_mid, next_mid) returns True iff next_mid < P <= last_mid (limit touched on buy)
    - simulate_touched("sell", P, last_mid, next_mid) returns True iff last_mid <= P < next_mid
    - simulate_touched returns False when mid does NOT cross the quote price
    - simulate_touched returns False on edge case last_mid == next_mid (no movement, no touch)
    - append_fill creates parent directory if missing; writes ONE JSONL line per call
    - append_fill routes to data/fills/{match_id}.{strategy_lowercased}.jsonl — MM_BETWEEN_ROUND → mm_between_round.jsonl; DIRECTIONAL_TAKE → directional_take.jsonl; POST_PLANT_QUOTE → post_plant_quote.jsonl
    - Append is atomic — multiple calls produce N lines in order (POSIX O_APPEND single-writer invariant per Phase 03 D-03)
    - maybe_record_mm_fill returns True iff simulate_touched returned True AND a JSONL line was written
    - maybe_record_mm_fill records strategy=quote.strategy_id (NEVER hardcoded — supports MM, DIRECTIONAL, POST_PLANT via same helper called from each quoter)
    - MM_VEGA_SPREAD_K constant is importable from src.config.constants and tests/config/test_constants.py EXPECTED_NAMES allow-list contains it
  </behavior>
  <action>
(A) src/config/constants.py — append MM_VEGA_SPREAD_K to the Phase 4 quoting
    layer thresholds section (after MIN_HALF_SPREAD per plan 04-00 layout):

    ```python
    MM_VEGA_SPREAD_K: Final[float] = 50.0  # TBD
    """Vega-to-spread scaling factor for MM_BETWEEN_ROUND quoter.

    Half-spread formula (DEC-018 v2 / REQ-mm-quoter):
        hs = max(MIN_HALF_SPREAD, MM_VEGA_SPREAD_K * sqrt(vega_between))
              + staleness_penalty

    Initial guess: 50.0 scales Phase 1's typical vega_between range
    [0.001, 0.01] into a [1.5c, 5c] vega-driven band on top of the 3c floor.
    Net effective spreads at the bounds:
      - vega = 0.001 (low conviction):  hs = max(3, 50*0.0316) = max(3, 1.58) = 3c
      - vega = 0.005 (mid):              hs = max(3, 50*0.0707) = max(3, 3.54) = 3.54c
      - vega = 0.01 (high):              hs = max(3, 50*0.1)    = max(3, 5)    = 5c
    Source: DEC-018 v2 / PRD §5.4 / RESEARCH §"Code Examples" half-spread formula.

    TODO(phase-5-calibrate): Tune k after 20+ live matches. If MM hypothetical
    fills are ALL at the 3c floor (vega contribution is always below), reduce
    k or raise vega normalization. If MM fills are ALL above 8c, raise k or
    lower the floor.
    """
    ```

(B) tests/config/test_constants.py — append "MM_VEGA_SPREAD_K" to EXPECTED_NAMES
    AND EXPECTED_TYPES (type: float). Atomic same-commit Rule-3 pattern per
    Phase 03 D-08 — splitting (A) and (B) leaves CI red between commits.

(C) Create src/quoting/fill_ledger.py:

```python
"""Hypothetical-fill JSONL ledger — per-strategy file split (DEC-020 v2).

CO-OWNED by plan 04-05 (MM quoter), 04-06 (directional taker), 04-07
(post-plant quoter). Each quoter calls maybe_record_*_fill with its OWN
strategy_id; the helper routes to the correct per-strategy file
(data/fills/{match_id}.{strategy_lower}.jsonl).

Per RESEARCH §"Pattern 4" + DEC-020 v2:
  - MM_BETWEEN_ROUND and DIRECTIONAL_TAKE fills MUST land in different files.
    Combined writes corrupt the promotion gate evaluation (DEC-020 v2 fill-
    count gate per strategy).
  - Schema: 10-key JSONL per fill, keyed on seq_id so Phase 5 backtest replay
    can JOIN against data/event_log/{match_id}.jsonl (state) and
    data/metrics/{match_id}.metrics.jsonl (latency).
  - Atomic POSIX append: each write is one < 4KB line via O_APPEND;
    single-writer invariant per (match_id, strategy) preserved by the bot
    main loop's serial dispatch.
  - DEC-020 simple "limit touched" rule: no queue position, no slippage,
    no partial fills. Phase 5 may refine; Phase 04 MUST NOT (RESEARCH
    §"Common Pitfalls" anti-pattern 1).

Source: PRD §8 / DEC-020 v2 / RESEARCH §"Pattern 4" / Phase 03 D-03
single-writer JSONL invariant.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from src.quoting.order_manager import Quote


@dataclass(frozen=True, slots=True)
class HypotheticalFill:
    """One simulated fill — RESEARCH §"Pattern 4" 10-key schema.

    seq_id JOINs to data/event_log/{match_id}.jsonl + data/metrics/{match_id}.metrics.jsonl.
    realized_outcome + pnl_cents are populated by Phase 5 backtest replay,
    NOT at write time (RESEARCH anti-pattern #2 — don't include P&L at write
    time; round resolution is a Phase 03 event AFTER the fill).
    """

    seq_id: int
    strategy: str                                  # "MM_BETWEEN_ROUND" | ...
    ticker: str
    side: Literal["yes", "no"]
    action: Literal["buy", "sell"]
    price_c: int                                   # cents 1-99
    count: int
    theo_c_at_fill: int                            # snapshot for Brier(model)
    market_mid_c_at_fill: int                      # snapshot for Brier(market_mid)
    realized_outcome: bool | None = None           # Phase 5 backtest
    pnl_cents: int | None = None                   # Phase 5 backtest

    def to_jsonl_line(self) -> str:
        """Return one-line JSON; caller appends '\\n'."""
        return json.dumps(asdict(self), separators=(",", ":"))


def append_fill(fill: HypotheticalFill, ledger_dir: Path, match_id: str) -> None:
    """Append one fill to data/fills/{match_id}.{strategy_lower}.jsonl.

    Strategy file naming (Pattern 4):
        MM_BETWEEN_ROUND  → {match_id}.mm_between_round.jsonl
        DIRECTIONAL_TAKE  → {match_id}.directional_take.jsonl
        POST_PLANT_QUOTE  → {match_id}.post_plant_quote.jsonl

    Atomic POSIX append per Phase 03 D-03 — line < 4KB guarantees PIPE_BUF
    atomicity even with concurrent writers (we have exactly one writer per
    (match_id, strategy) pair, so this is belt + suspenders).
    """
    strategy_lower = fill.strategy.lower()
    path = ledger_dir / f"{match_id}.{strategy_lower}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(fill.to_jsonl_line() + "\n")


def simulate_touched(
    quote_price_c: int,
    quote_action: Literal["buy", "sell"],
    last_mid_c: int,
    next_mid_c: int,
) -> bool:
    """Simple "limit touched" rule per DEC-020.

    YES buy at P fills iff mid drops THROUGH P  (next_mid < P <= last_mid).
    YES sell at P fills iff mid rises THROUGH P (last_mid <= P < next_mid).

    No queue-position modeling. No slippage. No partial fills. Phase 5 may
    refine the rule; Phase 04 MUST NOT (DEC-020 — order-fill backtest is OOS).

    Edge case: last_mid == next_mid (no movement) returns False under both
    branches (no crossing event happened).
    """
    if quote_action == "buy":
        return next_mid_c < quote_price_c <= last_mid_c
    if quote_action == "sell":
        return last_mid_c <= quote_price_c < next_mid_c
    return False


def maybe_record_mm_fill(
    quote: Quote,
    last_mid_c: int,
    next_mid_c: int,
    seq_id: int,
    theo_c: int,
    ledger_dir: Path,
    match_id: str,
) -> bool:
    """If the touched rule fires, write a HypotheticalFill to the ledger.

    Returns True iff a fill was recorded. The same helper is invoked from the
    directional taker (plan 04-06) and post-plant quoter (plan 04-07) — the
    strategy routing happens automatically via quote.strategy_id.
    """
    if not simulate_touched(quote.price, quote.action, last_mid_c, next_mid_c):
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

(D) Update src/quoting/__init__.py to export HypotheticalFill, append_fill,
    simulate_touched, maybe_record_mm_fill.

(E) Flip RED stubs in tests/quoting/test_fill_ledger.py to GREEN:

```python
"""Plan 04-05 — REQ-mm-quoter fill ledger GREEN tests.

DEC-020 v2 per-strategy ledger split (anti-pattern #1 — combined files
corrupt the promotion gate fill-count evaluation).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.quoting.fill_ledger import (
    HypotheticalFill,
    append_fill,
    maybe_record_mm_fill,
    simulate_touched,
)
from src.quoting.order_manager import Quote


def _quote(action: str = "buy", price: int = 50,
           strategy: str = "MM_BETWEEN_ROUND") -> Quote:
    return Quote(
        ticker="VAL-T1-WIN",
        side="yes",
        action=action,  # type: ignore[arg-type]
        price=price,
        count=10,
        strategy_id=strategy,  # type: ignore[arg-type]
    )


# ---------------- simulate_touched ----------------

def test_simulate_touched_buy_crossed() -> None:
    # YES buy at 50; mid drops from 51 to 49 → 49 < 50 <= 51 → True
    assert simulate_touched(50, "buy", last_mid_c=51, next_mid_c=49) is True


def test_simulate_touched_buy_at_boundary() -> None:
    # YES buy at 50; mid drops from 50 to 49 → 49 < 50 <= 50 → True (last_mid_c=50 inclusive)
    assert simulate_touched(50, "buy", last_mid_c=50, next_mid_c=49) is True


def test_simulate_touched_buy_not_crossed() -> None:
    # YES buy at 50; mid rises from 51 to 53 → no crossing
    assert simulate_touched(50, "buy", last_mid_c=51, next_mid_c=53) is False


def test_simulate_touched_sell_crossed() -> None:
    # YES sell at 50; mid rises from 49 to 51 → 49 <= 50 < 51 → True
    assert simulate_touched(50, "sell", last_mid_c=49, next_mid_c=51) is True


def test_simulate_touched_sell_at_boundary() -> None:
    # YES sell at 50; mid rises from 50 to 51 → 50 <= 50 < 51 → True (last_mid_c=50 inclusive)
    assert simulate_touched(50, "sell", last_mid_c=50, next_mid_c=51) is True


def test_simulate_touched_sell_not_crossed() -> None:
    assert simulate_touched(50, "sell", last_mid_c=49, next_mid_c=48) is False


def test_simulate_touched_no_movement() -> None:
    """last_mid == next_mid (no crossing event)."""
    assert simulate_touched(50, "buy", last_mid_c=50, next_mid_c=50) is False
    assert simulate_touched(50, "sell", last_mid_c=50, next_mid_c=50) is False


# ---------------- append_fill + per-strategy routing ----------------

def test_append_fill_writes_jsonl_line(tmp_fill_ledger_dir: Path) -> None:
    fill = HypotheticalFill(
        seq_id=42, strategy="MM_BETWEEN_ROUND", ticker="VAL-T1-WIN",
        side="yes", action="buy", price_c=50, count=10,
        theo_c_at_fill=52, market_mid_c_at_fill=49,
    )
    append_fill(fill, tmp_fill_ledger_dir, match_id="M1")
    path = tmp_fill_ledger_dir / "M1.mm_between_round.jsonl"
    assert path.exists()
    lines = path.read_text().splitlines()
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["seq_id"] == 42
    assert parsed["strategy"] == "MM_BETWEEN_ROUND"
    assert parsed["price_c"] == 50


def test_per_strategy_ledger_separate_files(tmp_fill_ledger_dir: Path) -> None:
    """RESEARCH §"Pattern 4" — MM, DIRECTIONAL, POST_PLANT in DIFFERENT files."""
    for strategy in ("MM_BETWEEN_ROUND", "DIRECTIONAL_TAKE", "POST_PLANT_QUOTE"):
        fill = HypotheticalFill(
            seq_id=1, strategy=strategy, ticker="VAL-T1-WIN",
            side="yes", action="buy", price_c=50, count=10,
            theo_c_at_fill=52, market_mid_c_at_fill=49,
        )
        append_fill(fill, tmp_fill_ledger_dir, match_id="M1")
    expected = {
        "M1.mm_between_round.jsonl",
        "M1.directional_take.jsonl",
        "M1.post_plant_quote.jsonl",
    }
    actual = {p.name for p in tmp_fill_ledger_dir.iterdir() if p.is_file()}
    assert expected == actual


def test_jsonl_line_schema_keys() -> None:
    fill = HypotheticalFill(
        seq_id=1, strategy="MM_BETWEEN_ROUND", ticker="VAL-T1-WIN",
        side="yes", action="buy", price_c=50, count=10,
        theo_c_at_fill=52, market_mid_c_at_fill=49,
    )
    parsed = json.loads(fill.to_jsonl_line())
    expected_keys = {
        "seq_id", "strategy", "ticker", "side", "action", "price_c", "count",
        "theo_c_at_fill", "market_mid_c_at_fill", "realized_outcome", "pnl_cents",
    }
    assert set(parsed.keys()) == expected_keys


def test_atomic_append_preserves_order(tmp_fill_ledger_dir: Path) -> None:
    """Phase 03 D-03 single-writer invariant: N appends → N lines in order."""
    for i in range(5):
        fill = HypotheticalFill(
            seq_id=i, strategy="MM_BETWEEN_ROUND", ticker="VAL-T1-WIN",
            side="yes", action="buy", price_c=50 + i, count=10,
            theo_c_at_fill=52, market_mid_c_at_fill=49,
        )
        append_fill(fill, tmp_fill_ledger_dir, match_id="M1")
    path = tmp_fill_ledger_dir / "M1.mm_between_round.jsonl"
    lines = path.read_text().splitlines()
    assert len(lines) == 5
    seq_ids = [json.loads(l)["seq_id"] for l in lines]
    assert seq_ids == [0, 1, 2, 3, 4]


# ---------------- maybe_record_mm_fill ----------------

def test_maybe_record_mm_fill_buy_crossed_returns_true(tmp_fill_ledger_dir: Path) -> None:
    quote = _quote("buy", 50, "MM_BETWEEN_ROUND")
    result = maybe_record_mm_fill(
        quote, last_mid_c=51, next_mid_c=49, seq_id=7, theo_c=52,
        ledger_dir=tmp_fill_ledger_dir, match_id="M1",
    )
    assert result is True
    path = tmp_fill_ledger_dir / "M1.mm_between_round.jsonl"
    assert path.exists()
    parsed = json.loads(path.read_text().splitlines()[0])
    assert parsed["seq_id"] == 7
    assert parsed["strategy"] == "MM_BETWEEN_ROUND"


def test_maybe_record_mm_fill_not_crossed_returns_false(tmp_fill_ledger_dir: Path) -> None:
    quote = _quote("buy", 50, "MM_BETWEEN_ROUND")
    result = maybe_record_mm_fill(
        quote, last_mid_c=51, next_mid_c=53, seq_id=7, theo_c=52,
        ledger_dir=tmp_fill_ledger_dir, match_id="M1",
    )
    assert result is False
    path = tmp_fill_ledger_dir / "M1.mm_between_round.jsonl"
    assert not path.exists()  # No ledger file created


def test_maybe_record_uses_quote_strategy_id(tmp_fill_ledger_dir: Path) -> None:
    """Helper routes by quote.strategy_id — supports MM/DIRECTIONAL/POST_PLANT."""
    quote = _quote("buy", 50, "DIRECTIONAL_TAKE")  # NOT MM
    maybe_record_mm_fill(
        quote, last_mid_c=51, next_mid_c=49, seq_id=7, theo_c=52,
        ledger_dir=tmp_fill_ledger_dir, match_id="M1",
    )
    assert (tmp_fill_ledger_dir / "M1.directional_take.jsonl").exists()
    assert not (tmp_fill_ledger_dir / "M1.mm_between_round.jsonl").exists()
```
  </action>
  <verify>
    <automated>uv run pytest tests/config/test_constants.py tests/quoting/test_fill_ledger.py -x --no-cov &amp;&amp; uv run mypy --strict src/quoting/</automated>
  </verify>
  <done>
- src/config/constants.py exports MM_VEGA_SPREAD_K; tests/config/test_constants.py allow-list extended in same commit.
- src/quoting/fill_ledger.py defines HypotheticalFill, append_fill, simulate_touched, maybe_record_mm_fill.
- 13+ tests in tests/quoting/test_fill_ledger.py pass GREEN.
- Per-strategy file naming verified (mm_between_round / directional_take / post_plant_quote).
- mypy --strict src/quoting/ clean.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: src/quoting/mm_quoter.py + GREEN test_mm_quoter.py (incl. spread-floor-beats-fee property test)</name>
  <files>src/quoting/mm_quoter.py, src/quoting/__init__.py, tests/quoting/test_mm_quoter.py</files>
  <behavior>
    - compute_half_spread(vega_between=0.0, staleness_s=0.0) returns MIN_HALF_SPREAD (3c) — floor invariant
    - compute_half_spread(vega_between=0.01, staleness_s=0.0) returns ceil(MM_VEGA_SPREAD_K * sqrt(0.01)) = ceil(50 * 0.1) = 5 cents
    - compute_half_spread(vega_between=0.005, staleness_s=0.0) returns max(3, ceil(50 * sqrt(0.005))) = max(3, 4) = 4
    - compute_half_spread(vega_between=0.0, staleness_s=3.0) returns 3 (floor) + 1 (= staleness above 2s × 1c/s) = 4
    - compute_half_spread(vega_between=0.0, staleness_s=4.5) returns 3 + 2 (2.5 rounded up to 3 — staleness above 2s in 1c/s steps) — verify exact behavior: floor(staleness - 2) cents added
    - Property (hypothesis): compute_half_spread(vega, staleness) >= MIN_HALF_SPREAD for any non-negative inputs
    - Property: compute_half_spread floor beats Kalshi maker fee — at theo=50c, maker fee = ceil(0.035 * 0.5 * 0.5 * 100) / 100 = 0.88c; MIN_HALF_SPREAD=3c > 0.88c + 1c slippage budget → 3 > 1.88 ✓
    - quote_mm_between_round places exactly 2 Quote objects (one yes-buy at theo_c - hs, one yes-sell at theo_c + hs) when mgr.active_quotes is empty
    - Every placed Quote has strategy_id="MM_BETWEEN_ROUND"
    - When mgr has existing MM quotes at different prices, quote_mm_between_round cancels them via cancel_quote BEFORE placing fresh ones
    - When mgr has existing MM quotes at correct prices (no price change), quote_mm_between_round does NOT cancel or replace (idempotent)
    - When existing MM quote is > 2s old (stale), quote_mm_between_round cancels and replaces
    - quote_mm_between_round skips placement if the resulting quote would be at price ≤ 0 or ≥ 100 (defensive guard; e.g., theo near 0.01 or 0.99 boundary)
  </behavior>
  <action>
(A) Create src/quoting/mm_quoter.py (~140-180 lines):

```python
"""MM_BETWEEN_ROUND quoter — REQ-mm-quoter v2 (DEC-018 v2 first arm).

Active only when trading_mode == "MM_BETWEEN_ROUND" (plan 04-04 rule 5).
Quotes at theo ± compute_half_spread(...) via KalshiOrderManager from plan
04-01. Hypothetical fills routed to data/fills/{match_id}.mm_between_round.jsonl
via fill_ledger.maybe_record_mm_fill (plan 04-05 task 1) — first-class peer
to DIRECTIONAL_TAKE per DEC-020 v2.

Half-spread formula (DEC-018 v2 + RESEARCH Pitfall 4):
    base = max(MIN_HALF_SPREAD, MM_VEGA_SPREAD_K * sqrt(vega_between))
    penalty = max(0, floor(staleness_s - 2.0))            # 1c/s above 2s
    hs = base + penalty

MIN_HALF_SPREAD = 3 (cents) MUST beat Kalshi maker fee + slippage budget:
    - Kalshi maker fee at theo=50c: ceil(0.035 * 0.5 * 0.5 * 100) / 100 = 0.88c
    - Kalshi taker fee at theo=50c: ceil(0.07 * 0.5 * 0.5 * 100) / 100  = 1.75c
    - We quote post_only=True (maker intent), so we mostly earn the 0.88c
      delta; 3c half-spread - 0.88c maker fee = 2.12c net of fees if theo
      is exact. Covers a 1c model slippage budget AND ~1c arbiter
      staleness slippage budget.
Property test (test_spread_floor_beats_fee) enforces this invariant
hypothesis-style across the Kalshi fee curve.

Staleness handling (PRD §5.4):
    state.last_updated_ts older than 2s → widen by 1c/s incremental.
    state.last_updated_ts older than 5s → kill_switch_staleness trips (plan
    04-03); 04-08's cancel-all-on-trip path clears the book entirely. This
    quoter does NOT need to handle the 5s pull case directly — kill switch
    aggregator owns it.

Source: PRD §5.4 / DEC-001 v2 / DEC-018 v2 / ROADMAP §4.3 / RESEARCH
§"Pattern 4" + Pitfall 4.
"""
from __future__ import annotations

import math
import time

from src.config.constants import MIN_HALF_SPREAD, MM_VEGA_SPREAD_K
from src.pricing.data import TheoOutput
from src.quoting.market_data import MarketQuote
from src.quoting.order_manager import KalshiOrderManager, Quote
from src.state.match_state import MatchState

_STALENESS_PENALTY_FLOOR_S: float = 2.0
"""Staleness threshold (seconds) above which we ADD widening cents.

PRD §5.4: "time_since_last_state_update > 2s → widen or pull". Phase 04
ships the widen branch; the pull-at-5s branch is plan 04-03's
kill_switch_staleness (and plan 04-08's cancel-all-on-trip handler).
"""


def compute_half_spread(
    vega_between: float,
    staleness_s: float,
) -> int:
    """Return MM half-spread in cents per DEC-018 v2 formula.

    Args:
        vega_between: TheoOutput.vega from Phase 1 (= vega_between_round).
        staleness_s: time.time() - state.last_updated_ts.

    Returns:
        Integer cents >= MIN_HALF_SPREAD. Floor invariant verified by
        property test (test_spread_floor_beats_fee).

    The vega contribution is `ceil(MM_VEGA_SPREAD_K * sqrt(vega_between))`
    — ceiling avoids the 1c off-by-one where a vega-driven spread of 3.01c
    would round down to 3c and tie the floor exactly (defensive: prefer to
    quote wider than too narrow when fee curve is the binding constraint).
    """
    if vega_between < 0.0:
        vega_between = 0.0  # defensive — negative vega is a programming error
    vega_cents = math.ceil(MM_VEGA_SPREAD_K * math.sqrt(vega_between))
    base = max(MIN_HALF_SPREAD, vega_cents)
    penalty = max(0, int(math.floor(staleness_s - _STALENESS_PENALTY_FLOOR_S)))
    return base + penalty


async def quote_mm_between_round(
    state: MatchState,
    theo: TheoOutput,
    market: MarketQuote,
    mgr: KalshiOrderManager,
    ticker: str,
    count: int,
    *,
    now: float | None = None,
) -> None:
    """Quote MM_BETWEEN_ROUND ladder (yes-buy at theo_c - hs, yes-sell at theo_c + hs).

    Idempotent: if quotes already exist at the correct prices AND are < 2s
    old, do nothing (avoid burning rate budget on identical replacements).
    On stale-or-mispriced quotes, cancel then place fresh.

    Boundary guards: if theo is near 0.01 or 0.99, the resulting bid/ask
    can fall outside [1, 99] — skip placement entirely (defensive; the
    market would also be near-degenerate at those theos and MM_MIN_EDGE
    likely fails rule 5 of the mode selector anyway).
    """
    n = now if now is not None else time.time()
    staleness_s = max(0.0, n - state.last_updated_ts)
    hs = compute_half_spread(theo.vega, staleness_s)
    theo_c = round(theo.theo_series * 100)
    buy_price = theo_c - hs
    sell_price = theo_c + hs

    # Boundary guard: Kalshi cents must be in [1, 99].
    if buy_price < 1 or sell_price > 99:
        return

    existing = mgr.active_quotes.get(ticker, {})
    buy_quote = existing.get("buy_yes")
    sell_quote = existing.get("sell_yes")

    # Cancel stale or mispriced quotes BEFORE placing fresh (per RESEARCH
    # Pattern 2 — cancel-and-replace is simpler than amend-order).
    if buy_quote is not None:
        age = n - (buy_quote.placed_at or 0.0)
        if buy_quote.price != buy_price or age > _STALENESS_PENALTY_FLOOR_S:
            await mgr.cancel_quote(ticker, "buy_yes")
            buy_quote = None
    if sell_quote is not None:
        age = n - (sell_quote.placed_at or 0.0)
        if sell_quote.price != sell_price or age > _STALENESS_PENALTY_FLOOR_S:
            await mgr.cancel_quote(ticker, "sell_yes")
            sell_quote = None

    # Place fresh quotes if missing (idempotent — no-op if cancel was no-op
    # AND existing quote price matched).
    if buy_quote is None:
        await mgr.place_quote(Quote(
            ticker=ticker,
            side="yes",
            action="buy",
            price=buy_price,
            count=count,
            strategy_id="MM_BETWEEN_ROUND",
        ))
    if sell_quote is None:
        await mgr.place_quote(Quote(
            ticker=ticker,
            side="yes",
            action="sell",
            price=sell_price,
            count=count,
            strategy_id="MM_BETWEEN_ROUND",
        ))
```

(B) Update src/quoting/__init__.py to export compute_half_spread,
    quote_mm_between_round.

(C) Flip RED stubs in tests/quoting/test_mm_quoter.py to GREEN. Use
    `make_match_state`, `make_market_quote`, and a fresh
    KalshiOrderManager(dry_run=True) for each test.

```python
"""Plan 04-05 — REQ-mm-quoter (v2 between-round only) GREEN tests.

DEC-018 v2 spread formula + RESEARCH Pitfall 4 (floor beats Kalshi fee curve).
"""
from __future__ import annotations

import math

import aiohttp
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from hypothesis import HealthCheck, given, settings, strategies as st

from src.config.constants import MIN_HALF_SPREAD, MM_VEGA_SPREAD_K
from src.pricing.data import TheoOutput
from src.quoting.market_data import make_quote
from src.quoting.mm_quoter import compute_half_spread, quote_mm_between_round
from src.quoting.order_manager import KalshiOrderManager


def _theo(theo_series: float = 0.50, vega: float = 0.0) -> TheoOutput:
    return TheoOutput(theo_series=theo_series, theo_map=(theo_series,),
                       vega=vega, confidence=1.0)


@pytest.fixture
async def mgr(fake_private_key: rsa.RSAPrivateKey) -> KalshiOrderManager:
    async with aiohttp.ClientSession() as session:
        yield KalshiOrderManager(session=session, key_id="K", private_key=fake_private_key, dry_run=True)


# ---------------- compute_half_spread ----------------

def test_spread_floor_at_zero_vega() -> None:
    """Zero vega + zero staleness → MIN_HALF_SPREAD (3c)."""
    assert compute_half_spread(0.0, 0.0) == MIN_HALF_SPREAD


def test_spread_vega_contribution_at_typical_value() -> None:
    """vega=0.01 → ceil(50 * 0.1) = 5c."""
    assert compute_half_spread(0.01, 0.0) == 5


def test_spread_floor_binds_at_low_vega() -> None:
    """vega=0.001 → ceil(50 * 0.0316) = 2c < floor → returns 3c."""
    assert compute_half_spread(0.001, 0.0) == MIN_HALF_SPREAD


def test_spread_staleness_penalty_below_floor() -> None:
    """staleness <= 2s → no penalty."""
    assert compute_half_spread(0.0, 1.5) == MIN_HALF_SPREAD
    assert compute_half_spread(0.0, 2.0) == MIN_HALF_SPREAD


def test_spread_staleness_penalty_above_2s() -> None:
    """staleness=3s → +1c penalty; staleness=4.5s → +2c."""
    assert compute_half_spread(0.0, 3.0) == MIN_HALF_SPREAD + 1
    assert compute_half_spread(0.0, 4.5) == MIN_HALF_SPREAD + 2


def test_spread_handles_negative_vega_defensively() -> None:
    """Negative vega is a programming error; defensively clip to 0."""
    assert compute_half_spread(-0.05, 0.0) == MIN_HALF_SPREAD


@given(
    vega=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    staleness=st.floats(min_value=0.0, max_value=4.99, allow_nan=False),
)
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_spread_floor_invariant(vega: float, staleness: float) -> None:
    """Property: half-spread >= MIN_HALF_SPREAD for all non-negative inputs."""
    assert compute_half_spread(vega, staleness) >= MIN_HALF_SPREAD


def test_spread_floor_beats_fee() -> None:
    """RESEARCH Pitfall 4: MIN_HALF_SPREAD must exceed Kalshi maker fee + 1c slippage.

    At theo=50c (worst case for fee curve):
        maker fee = ceil(0.035 * 0.5 * 0.5 * 100) / 100 = 0.88c
        slippage budget = 1c
        required floor > 1.88c → MIN_HALF_SPREAD=3c satisfies this.
    """
    # Symbolic worst-case fee at theo=0.5
    p = 0.50
    maker_fee_c = math.ceil(0.035 * p * (1 - p) * 100) / 100
    slippage_c = 1.0
    assert MIN_HALF_SPREAD > maker_fee_c + slippage_c


# ---------------- quote_mm_between_round (dry-run) ----------------

@pytest.mark.asyncio
async def test_places_both_legs(mgr: KalshiOrderManager, make_match_state) -> None:
    state = make_match_state(bomb_planted=False, time_left_s=None, last_updated_ts=1000.0)
    market = make_quote(46, 54)  # mid=50, spread=8
    await quote_mm_between_round(
        state, _theo(0.50, vega=0.005), market, mgr,
        ticker="VAL-T1-WIN", count=10, now=1000.5,
    )
    legs = mgr.active_quotes["VAL-T1-WIN"]
    assert "buy_yes" in legs
    assert "sell_yes" in legs
    # theo=50, vega=0.005 → ceil(50*sqrt(0.005)) = 4c half-spread
    assert legs["buy_yes"].price == 50 - 4
    assert legs["sell_yes"].price == 50 + 4


@pytest.mark.asyncio
async def test_quotes_tagged_with_strategy_id(mgr: KalshiOrderManager, make_match_state) -> None:
    state = make_match_state(bomb_planted=False, time_left_s=None, last_updated_ts=1000.0)
    market = make_quote(46, 54)
    await quote_mm_between_round(state, _theo(0.50), market, mgr,
                                   ticker="VAL-T1-WIN", count=10, now=1000.5)
    for leg in mgr.active_quotes["VAL-T1-WIN"].values():
        assert leg.strategy_id == "MM_BETWEEN_ROUND"


@pytest.mark.asyncio
async def test_idempotent_on_unchanged_prices(mgr: KalshiOrderManager, make_match_state) -> None:
    """Same theo + market + age < 2s → no cancel, no re-place."""
    state = make_match_state(bomb_planted=False, time_left_s=None, last_updated_ts=1000.0)
    market = make_quote(46, 54)
    await quote_mm_between_round(state, _theo(0.50), market, mgr,
                                   ticker="VAL-T1-WIN", count=10, now=1000.5)
    first_oids = {leg: q.order_id for leg, q in mgr.active_quotes["VAL-T1-WIN"].items()}
    # Second call with same inputs + age < 2s → quotes unchanged
    await quote_mm_between_round(state, _theo(0.50), market, mgr,
                                   ticker="VAL-T1-WIN", count=10, now=1001.0)
    second_oids = {leg: q.order_id for leg, q in mgr.active_quotes["VAL-T1-WIN"].items()}
    assert first_oids == second_oids


@pytest.mark.asyncio
async def test_cancels_stale_quotes(mgr: KalshiOrderManager, make_match_state) -> None:
    """Quote placed > 2s ago is treated as stale → cancel + re-place."""
    state = make_match_state(bomb_planted=False, time_left_s=None, last_updated_ts=1000.0)
    market = make_quote(46, 54)
    await quote_mm_between_round(state, _theo(0.50), market, mgr,
                                   ticker="VAL-T1-WIN", count=10, now=1000.0)
    first_oids = {leg: q.order_id for leg, q in mgr.active_quotes["VAL-T1-WIN"].items()}
    # Second call with now=1005 → age=5s > 2s → quotes replaced
    await quote_mm_between_round(state, _theo(0.50), market, mgr,
                                   ticker="VAL-T1-WIN", count=10, now=1005.0)
    second_oids = {leg: q.order_id for leg, q in mgr.active_quotes["VAL-T1-WIN"].items()}
    assert first_oids != second_oids  # New order_ids after re-place


@pytest.mark.asyncio
async def test_cancels_mispriced_quotes(mgr: KalshiOrderManager, make_match_state) -> None:
    """Theo shifted → buy_yes price changed → cancel + re-place."""
    state = make_match_state(bomb_planted=False, time_left_s=None, last_updated_ts=1000.0)
    market = make_quote(46, 54)
    await quote_mm_between_round(state, _theo(0.50), market, mgr,
                                   ticker="VAL-T1-WIN", count=10, now=1000.5)
    first_buy_price = mgr.active_quotes["VAL-T1-WIN"]["buy_yes"].price
    # Theo shifts to 0.55 → buy_yes price moves up
    await quote_mm_between_round(state, _theo(0.55), market, mgr,
                                   ticker="VAL-T1-WIN", count=10, now=1001.0)
    new_buy_price = mgr.active_quotes["VAL-T1-WIN"]["buy_yes"].price
    assert new_buy_price != first_buy_price
    assert new_buy_price == 55 - 3  # theo_c=55, hs=3 floor


@pytest.mark.asyncio
async def test_boundary_guard_skips_when_price_below_1(mgr: KalshiOrderManager, make_match_state) -> None:
    """theo=0.02 → buy_price = 2 - 3 = -1 (out of bounds) → skip placement."""
    state = make_match_state(bomb_planted=False, time_left_s=None, last_updated_ts=1000.0)
    market = make_quote(1, 5)
    await quote_mm_between_round(state, _theo(0.02), market, mgr,
                                   ticker="VAL-T1-WIN", count=10, now=1000.5)
    assert "VAL-T1-WIN" not in mgr.active_quotes


@pytest.mark.asyncio
async def test_boundary_guard_skips_when_price_above_99(mgr: KalshiOrderManager, make_match_state) -> None:
    """theo=0.98 → sell_price = 98 + 3 = 101 (out of bounds) → skip placement."""
    state = make_match_state(bomb_planted=False, time_left_s=None, last_updated_ts=1000.0)
    market = make_quote(95, 99)
    await quote_mm_between_round(state, _theo(0.98), market, mgr,
                                   ticker="VAL-T1-WIN", count=10, now=1000.5)
    assert "VAL-T1-WIN" not in mgr.active_quotes
```

Note: the `mgr` fixture is async; existing tests in test_order_manager.py
(plan 04-01 task 3) use the same pattern. The `@pytest.fixture` decorator
on an async generator is the canonical pytest-asyncio idiom (already a dev
dep from Phase 03).
  </action>
  <verify>
    <automated>uv run pytest tests/quoting/test_mm_quoter.py -x --no-cov &amp;&amp; uv run mypy --strict src/quoting/</automated>
  </verify>
  <done>
- src/quoting/mm_quoter.py defines compute_half_spread + quote_mm_between_round.
- 11+ tests in tests/quoting/test_mm_quoter.py pass GREEN (incl. hypothesis property test).
- test_spread_floor_beats_fee verifies MIN_HALF_SPREAD > maker_fee + 1c slippage at theo=50c.
- Idempotency + cancel-stale + cancel-mispriced + boundary guard all covered.
- src/quoting/__init__.py exports compute_half_spread + quote_mm_between_round.
- mypy --strict src/quoting/ clean.
  </done>
</task>

</tasks>

<verification>
1. `uv run pytest tests/config/test_constants.py tests/quoting/test_fill_ledger.py tests/quoting/test_mm_quoter.py -x --no-cov` — all GREEN.
2. `uv run mypy --strict src/quoting/` clean.
3. `uv run pytest tests/ -x --no-cov` — Phase 03 + plans 04-00..04-05 stay green; remaining stubs (06, 07, 08) xfail.
4. `rg "directional_take|post_plant_quote" src/quoting/mm_quoter.py` returns empty (mm_quoter does NOT write to peer-strategy ledgers).
5. `rg "MM_VEGA_SPREAD_K" tests/config/test_constants.py` matches (allow-list extended atomically).
6. `python -c "from src.quoting import compute_half_spread, quote_mm_between_round, HypotheticalFill, simulate_touched, maybe_record_mm_fill, append_fill; print('ok')"` runs without ImportError.
</verification>

<success_criteria>
- MM_BETWEEN_ROUND quoter writes fills ONLY to data/fills/{match_id}.mm_between_round.jsonl (DEC-020 v2 separate-ledger invariant).
- MIN_HALF_SPREAD=3c floor verified to beat Kalshi maker fee + 1c slippage at theo=50c (Pitfall 4).
- compute_half_spread is grep-discoverable + hypothesis-property-tested for the floor invariant.
- quote_mm_between_round is idempotent on unchanged inputs; cancels stale or mispriced quotes before re-placing.
- Every Quote placed has strategy_id="MM_BETWEEN_ROUND" (enables Phase 5 fill-count gate evaluation per DEC-020 v2).
</success_criteria>

<output>
After completion, create `.planning/phases/04-quoting-layer/04-05-SUMMARY.md` documenting:
- src/quoting/mm_quoter.py + src/quoting/fill_ledger.py file contents.
- MM_VEGA_SPREAD_K constant added (same-commit Rule-3 with allow-list extension).
- 24+ test results.
- Forward links: plan 04-06 (directional taker REUSES maybe_record_mm_fill helper — strategy routing by quote.strategy_id), plan 04-07 (post-plant quoter REUSES same helper), plan 04-08 (E2E test asserts MM + DIRECTIONAL fills land in SEPARATE files).
</output>
