---
phase: 04-quoting-layer
plan: "07"
type: execute
wave: 4
depends_on: ["00", "01", "02", "04", "05"]
files_modified:
  - src/quoting/post_plant_quoter.py
  - src/quoting/__init__.py
  - src/ingestion/arbiter.py
  - tests/quoting/test_post_plant_quoter.py
  - tests/ingestion/test_arbiter_t_quote_pull_completed.py
autonomous: true
requirements:
  - REQ-post-plant-quoter
notes: |
  Wave 4 — POST_PLANT_QUOTE (REQ-post-plant-quoter NEW v2) + the
  `t_quote_pull_completed` timestamp extension to the arbiter's 6-stage
  lineage. Parallelizable with 04-05 and 04-06 (disjoint files; CONSUMES
  fill_ledger.maybe_record_mm_fill from 04-05 + KalshiOrderManager from
  04-01 + compute_vega_post_plant from 04-04).

  Active only when `mode == POST_PLANT_QUOTE` (rule 2 of plan 04-04's
  trading_mode). The latency-critical mode — PRD §5.4 / DEC-020 v2 budgets
  bomb-detect → quote-pull p50 < 200 ms END-TO-END, split between:
    - Phase 03's t_observed → t_state_committed (≤100ms, GREEN per
      plan 03-08 synthetic harness, validation production gate is Phase 5)
    - Phase 04-07's t_state_committed → t_quote_pull_completed (≤100ms)
  This plan ships the SECOND half. Latency assertion in
  test_quote_pull_p50_under_100ms covers the Phase 04 piece.

  Three actions on POST_PLANT_QUOTE per ROADMAP §4.5 / PRD §2.1 / §5.4:
    1. DEFENSIVE QUOTE-PULL: cancel every resting MM_BETWEEN_ROUND quote
       via KalshiOrderManager.cancel_all_orders. Latency-critical — this is
       the 100ms target. Records `t_quote_pull_completed = mono_ns()` to
       the timestamps dict at the moment cancel_all_orders returns.
    2. RE-PRICE: live_theo(state) (Phase 1 contract) uses the post-plant
       lookup path automatically when state.bomb_planted=True (Phase 1
       D-14 contract — already in place; this plan does NOT modify
       live_theo).
    3. TAKE-OR-QUOTE: if |theo_c - market.mid| > POST_PLANT_TAKE_THRESHOLD
       (3c, narrower than between-round take's 5c), TAKE via IOC lift/hit
       (mirroring plan 04-06 shape); otherwise QUOTE at theo ± narrow
       spread (single half-spread = POST_PLANT_TAKE_THRESHOLD = 3c, since
       post-plant is a high-conviction state per PRD §5.4 — no
       vega-scaling). Fills land in data/fills/{match_id}.post_plant_quote.jsonl
       via the strategy-agnostic helper (strategy_id="POST_PLANT_QUOTE").

  CRITICAL — `t_quote_pull_completed` is a NEW timestamp key in the
  arbiter's per-event timestamps dict (extends the 6-stage lineage from
  Phase 03 D-03 to 7 stages: t_observed, t_ingested, t_arbited,
  t_state_committed, t_theo_computed, t_quote_sent,
  t_quote_pull_completed). Phase 03's arbiter writes the dict to
  data/metrics/{match_id}.metrics.jsonl with t_quote_pull_completed=None
  initially. THIS plan extends:
    - src/ingestion/arbiter.py — populate "t_quote_pull_completed": None
      in the initial timestamps dict
    - src/ingestion/arbiter.py _write_metrics_line — include the new key
    - src/quoting/post_plant_quoter.py — set timestamps["t_quote_pull_completed"]
      = mono_ns() after the cancel_all_orders return
  Atomic same-commit pattern — splitting the arbiter extension from the
  post_plant_quoter would leave one of them out of sync.

  CRITICAL — `POST_PLANT_QUOTE` mode is REACHED via rule 2 of mode_selector,
  which fires BEFORE the take/MM threshold rules. Once we're in this mode,
  the quoter ALWAYS performs the defensive pull first (even if a take
  opportunity is present) per the PRD §2.1 ordering. The pull-then-decide
  shape is what gives us the 200ms p50 budget end-to-end.

  Idempotency-on-pull: the post-plant quoter should NOT pull-then-pull on
  subsequent state updates while bomb_planted remains True. The caller
  (bot main loop in plan 04-08) gates the defensive pull on the
  bomb_planted=False → True TRANSITION (a "first call" flag in the
  caller's loop). For Phase 04 unit tests, the test fixture passes
  `is_first_call: bool` explicitly. Subsequent same-mode calls only do
  step 3 (take-or-quote with refreshed theo + market).

  POST_PLANT_QUOTE quoter consumes the new `compute_vega_post_plant`
  function from plan 04-04 ONLY informationally — it is reserved for
  future Phase 5 calibration of the take threshold; the QUOTE branch uses
  POST_PLANT_TAKE_THRESHOLD as a flat half-spread for now (high-conviction
  state per PRD §5.4 — no vega-scaling in v2).

  Reads bankroll_cents + series_id + portfolio + last_mid_c from caller
  per plan 04-06 convention (taker uses portfolio Kelly; quoter does NOT
  size by Kelly — quotes are at a fixed half-spread).

must_haves:
  truths:
    - "On is_first_call=True, post_plant_quoter calls mgr.cancel_all_orders() BEFORE anything else"
    - "On is_first_call=False, post_plant_quoter does NOT call cancel_all_orders (idempotency — only the bomb-detect transition triggers the pull)"
    - "Defensive pull completes within 100ms p50 (Phase 04's piece of PRD's 200ms bomb-detect → quote-pull budget) — measured via timestamps[\"t_quote_pull_completed\"] - timestamps[\"t_state_committed\"]"
    - "After defensive pull, post_plant_quoter calls live_theo(state) which routes to post-plant lookup (Phase 1 D-14 — bomb_planted=True triggers post-plant path); plan 04-07 does NOT re-implement the routing"
    - "If |theo_c - market.mid| > POST_PLANT_TAKE_THRESHOLD (3), take via IOC (action=buy at yes_ask or sell at yes_bid, strategy_id=\"POST_PLANT_QUOTE\")"
    - "If |theo_c - market.mid| <= POST_PLANT_TAKE_THRESHOLD, QUOTE at theo ± POST_PLANT_TAKE_THRESHOLD (flat 3c half-spread)"
    - "All Quote objects placed by post_plant_quoter have strategy_id=\"POST_PLANT_QUOTE\""
    - "Hypothetical fills land ONLY in data/fills/{match_id}.post_plant_quote.jsonl"
    - "src/ingestion/arbiter.py timestamps dict contains \"t_quote_pull_completed\": None at creation; key flows through to metrics JSONL"
    - "src/ingestion/arbiter.py _write_metrics_line emits t_quote_pull_completed in the metrics line schema"
  artifacts:
    - path: "src/quoting/post_plant_quoter.py"
      provides: "post_plant_quote coroutine — defensive pull + re-price + take-or-quote"
      min_lines: 120
      contains: "POST_PLANT_QUOTE"
    - path: "src/ingestion/arbiter.py"
      provides: "t_quote_pull_completed key added to timestamps dict + _write_metrics_line"
      contains: "t_quote_pull_completed"
    - path: "tests/quoting/test_post_plant_quoter.py"
      provides: "10+ tests covering pull / re-price / take-or-quote / p50 latency / separate ledger"
      contains: "test_quote_pull_p50_under_100ms"
    - path: "tests/ingestion/test_arbiter_t_quote_pull_completed.py"
      provides: "1-2 tests verifying the new metrics key flows through arbiter unchanged for non-bomb events"
      contains: "t_quote_pull_completed"
  key_links:
    - from: "src/quoting/post_plant_quoter.post_plant_quote"
      to: "src/quoting/order_manager.KalshiOrderManager.cancel_all_orders"
      via: "Defensive pull on is_first_call=True; latency-critical 100ms target"
      pattern: "cancel_all_orders"
    - from: "src/quoting/post_plant_quoter.post_plant_quote"
      to: "src/pricing/live_theo.live_theo"
      via: "Re-price step 2 — bomb_planted=True routes to post-plant lookup per Phase 1 D-14"
      pattern: "live_theo"
    - from: "src/quoting/post_plant_quoter.post_plant_quote"
      to: "src/quoting/fill_ledger.maybe_record_mm_fill"
      via: "strategy_id=\"POST_PLANT_QUOTE\" — strategy-agnostic helper routes to .post_plant_quote.jsonl"
      pattern: "POST_PLANT_QUOTE"
    - from: "src/ingestion/arbiter timestamps dict"
      to: "src/quoting/post_plant_quoter — sets t_quote_pull_completed after cancel_all returns"
      via: "Per-event metrics line gets the new key; Pitfall 6 measurement clock alignment"
      pattern: "t_quote_pull_completed"
---

<objective>
Build the POST_PLANT_QUOTE quoter (REQ-post-plant-quoter NEW v2) — the
latency-critical mode where bomb-detection triggers a defensive pull of
every resting between-round MM quote within 100ms (Phase 04's piece of
PRD's 200ms bomb-detect → quote-pull budget; Phase 03 owns the first
100ms `t_observed → t_state_committed`, this plan owns the remaining
100ms `t_state_committed → t_quote_pull_completed`).

Purpose: REQ-post-plant-quoter — three actions on bomb-plant detection:
(1) defensive quote-pull within 100ms (cancel-all_resting-MM-quotes), (2)
re-price using live_theo's post-plant path (Phase 1 D-14 routes
bomb_planted=True automatically), (3) take if |theo - market| >
POST_PLANT_TAKE_THRESHOLD (narrower than between-round take per PRD §5.4
high-conviction state) OR quote at theo ± narrow spread.

Output: src/quoting/post_plant_quoter.py + src/ingestion/arbiter.py
extension (t_quote_pull_completed key) + 12+ GREEN tests including the
latency assertion.
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
@.planning/phases/04-quoting-layer/04-05-mm-between-round-PLAN.md
@src/config/constants.py
@src/state/match_state.py
@src/pricing/live_theo.py
@src/ingestion/arbiter.py

<interfaces>
<!-- Plan 04-01 surface this plan consumes -->
From src/quoting/order_manager.py:
```python
class KalshiOrderManager:
    @property
    def active_quotes(self) -> dict[str, dict[str, Quote]]: ...
    async def place_quote(self, quote: Quote) -> bool: ...
    async def cancel_all_orders(self) -> None: ...   # batched DELETE; clears _active_quotes

@dataclass(slots=True)
class Quote:
    ticker: str
    side: Literal["yes", "no"]
    action: Literal["buy", "sell"]
    price: int
    count: int
    strategy_id: Literal["MM_BETWEEN_ROUND", "DIRECTIONAL_TAKE", "POST_PLANT_QUOTE"]
    ...
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

<!-- Phase 1 pricing surface -->
From src/pricing/live_theo.py:
```python
class LiveTheoEngine:
    def __call__(self, state: MatchState) -> TheoOutput: ...
    # When state.bomb_planted=True, internal routing dispatches to the
    # post-plant lookup automatically (Phase 1 D-14 contract). plan 04-07
    # does NOT touch this routing.
```

<!-- Plan 04-05 fill ledger surface this plan REUSES -->
From src/quoting/fill_ledger.py:
```python
def maybe_record_mm_fill(
    quote: Quote, last_mid_c: int, next_mid_c: int, seq_id: int, theo_c: int,
    ledger_dir: Path, match_id: str,
) -> bool: ...
# Strategy routing automatic via quote.strategy_id="POST_PLANT_QUOTE".
```

<!-- Phase 04 constants from plan 04-00 -->
From src/config/constants.py:
```python
POST_PLANT_TAKE_THRESHOLD: Final[int] = 3   # cents — narrower than TAKE_THRESHOLD (5)
```

<!-- Phase 03 contract this plan extends -->
From src/ingestion/arbiter.py (Phase 03 baseline — 6-stage timestamps):
```python
timestamps: dict[str, float | int | None] = {
    "t_observed": t_observed,
    "t_ingested": t_ingested,
    "t_arbited": mono_ns(),
    "t_state_committed": None,        # commit() sets this
    "t_theo_computed": None,          # Phase 4 sets this
    "t_quote_sent": None,             # Phase 4 sets this
    # NEW v2 in this plan:
    "t_quote_pull_completed": None,   # plan 04-07 sets this after cancel_all_orders returns
}
```

<!-- New surface this plan creates -->
NEW src/quoting/post_plant_quoter.py public surface:
```python
async def post_plant_quote(
    state: MatchState,
    theo: TheoOutput,
    market: MarketQuote,
    mgr: KalshiOrderManager,
    ticker: str,
    count: int,
    last_mid_c: int,
    ledger_dir: Path,
    timestamps: dict[str, float | int | None],
    *,
    is_first_call: bool,
    seq_id: int | None = None,
) -> None: ...
# Sets timestamps["t_quote_pull_completed"] = mono_ns() if is_first_call
# and cancel_all_orders was invoked.
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Extend src/ingestion/arbiter.py with t_quote_pull_completed timestamp key + GREEN test_arbiter_t_quote_pull_completed.py</name>
  <files>src/ingestion/arbiter.py, tests/ingestion/test_arbiter_t_quote_pull_completed.py</files>
  <behavior>
    - arbiter._commit_event() initializes timestamps dict with "t_quote_pull_completed": None
    - arbiter._write_metrics_line() emits "t_quote_pull_completed" key in the metrics JSONL line (value is None for non-bomb events; populated by plan 04-07 quoter for bomb events)
    - Phase 03 tests (test_arbiter.py + test_e2e.py from plan 03-08) all STILL PASS — backward compatible additive change
    - Metrics JSONL line for a non-bomb event includes `"t_quote_pull_completed":null` (verified by parsing one line after a score_change commit)
  </behavior>
  <action>
(A) Edit src/ingestion/arbiter.py — locate the timestamps dict in
    `_commit_event` (Phase 03 baseline lines 227-234) and add the new key:

    Use Edit tool. old_string:
    ```python
        timestamps: dict[str, float | int | None] = {
            "t_observed": t_observed,
            "t_ingested": t_ingested,
            "t_arbited": mono_ns(),
            "t_state_committed": None,  # commit() sets this in place
            "t_theo_computed": None,
            "t_quote_sent": None,
        }
    ```
    new_string:
    ```python
        timestamps: dict[str, float | int | None] = {
            "t_observed": t_observed,
            "t_ingested": t_ingested,
            "t_arbited": mono_ns(),
            "t_state_committed": None,         # commit() sets this in place
            "t_theo_computed": None,           # Phase 4 fills this
            "t_quote_sent": None,              # Phase 4 fills this
            "t_quote_pull_completed": None,    # Plan 04-07 fills this on bomb-detect → cancel_all return
        }
    ```

(B) Edit src/ingestion/arbiter.py — locate `_write_metrics_line` (Phase 03
    baseline lines 272-283). Add the new key to the emitted line:

    Use Edit tool. old_string:
    ```python
            "t_quote_sent": timestamps.get("t_quote_sent"),
            "source": source,
    ```
    new_string:
    ```python
            "t_quote_sent": timestamps.get("t_quote_sent"),
            "t_quote_pull_completed": timestamps.get("t_quote_pull_completed"),
            "source": source,
    ```

(C) Create tests/ingestion/test_arbiter_t_quote_pull_completed.py with 2
    tests verifying the new key flows through cleanly without breaking
    Phase 03 expectations:

```python
"""Plan 04-07 — additive arbiter timestamps extension test.

Adds t_quote_pull_completed to the 6-stage Phase 03 lineage → 7-stage
Phase 04. Non-bomb events emit the new key as null; bomb events get it
populated by plan 04-07's post_plant_quoter (covered in
tests/quoting/test_post_plant_quoter.py).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.ingestion.arbiter import Arbiter, PendingEvent
from src.state.match_state import MatchState


@pytest.fixture
def empty_state() -> MatchState:
    return MatchState(
        match_id="M1", team_a="A", team_b="B",
        map_pool=("Lotus",), map_side_orients=("a_atk",),
        map_winners=(None,), pistol_winner_a={0: None},
        map_idx=0, a_map_score=0, b_map_score=0, a_round=0, b_round=0,
        side_orient="a_atk", bomb_planted=False, attackers_alive=None,
        defenders_alive=None, time_left_s=None, seq_id=0, last_updated_ts=0.0,
    )


def test_score_change_emits_t_quote_pull_completed_null(
    empty_state: MatchState, tmp_path: Path,
) -> None:
    """Non-bomb commit → metrics line includes t_quote_pull_completed=null."""
    jsonl_path = tmp_path / "M1.jsonl"
    metrics_path = tmp_path / "M1.metrics.jsonl"
    arb = Arbiter(empty_state, jsonl_path=jsonl_path, metrics_path=metrics_path)

    # Push two score_change sources within 2s window — commits per DEC-006 v2.
    arb.score_changes.append(PendingEvent(
        source="ribgg", event_type="score_change",
        fields_proposed={"a_round": 1}, t_observed=100.0,
    ))
    arb.score_changes.append(PendingEvent(
        source="ocr", event_type="score_change",
        fields_proposed={"a_round": 1}, t_observed=100.5,
    ))
    arb.tick()

    lines = metrics_path.read_text().splitlines()
    assert len(lines) >= 1
    parsed = json.loads(lines[0])
    assert "t_quote_pull_completed" in parsed
    assert parsed["t_quote_pull_completed"] is None


def test_phase03_baseline_still_passes(tmp_path: Path, empty_state: MatchState) -> None:
    """Smoke check: Phase 03 6-stage keys still present after extension."""
    jsonl_path = tmp_path / "M1.jsonl"
    metrics_path = tmp_path / "M1.metrics.jsonl"
    arb = Arbiter(empty_state, jsonl_path=jsonl_path, metrics_path=metrics_path)

    arb.score_changes.append(PendingEvent(
        source="ribgg", event_type="score_change",
        fields_proposed={"a_round": 1}, t_observed=100.0,
    ))
    arb.score_changes.append(PendingEvent(
        source="ocr", event_type="score_change",
        fields_proposed={"a_round": 1}, t_observed=100.5,
    ))
    arb.tick()

    parsed = json.loads(metrics_path.read_text().splitlines()[0])
    # All 6 Phase 03 keys remain present.
    for key in ("t_observed", "t_ingested", "t_arbited",
                 "t_state_committed", "t_theo_computed", "t_quote_sent"):
        assert key in parsed
```

NOTE: the exact `Arbiter` constructor signature + `PendingEvent` import
path may differ slightly from the literal text above; consult
src/ingestion/arbiter.py at task execution time and align imports
accordingly. The test SHAPE (push 2 sources → tick → parse metrics line
→ assert t_quote_pull_completed present) is the load-bearing assertion.
  </action>
  <verify>
    <automated>uv run pytest tests/ingestion/test_arbiter_t_quote_pull_completed.py tests/ingestion/test_arbiter.py tests/ingestion/test_e2e.py -x --no-cov &amp;&amp; uv run mypy --strict src/ingestion/ src/state/</automated>
  </verify>
  <done>
- src/ingestion/arbiter.py timestamps dict initialization includes "t_quote_pull_completed": None.
- _write_metrics_line emits the new key in the JSONL line (verified by parsing).
- 2 new tests in tests/ingestion/test_arbiter_t_quote_pull_completed.py pass GREEN.
- Phase 03 tests (test_arbiter.py + test_e2e.py) STILL PASS — backward compatible additive extension.
- mypy --strict src/ingestion/ + src/state/ clean.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: src/quoting/post_plant_quoter.py + GREEN test_post_plant_quoter.py (incl. 100ms p50 latency assertion)</name>
  <files>src/quoting/post_plant_quoter.py, src/quoting/__init__.py, tests/quoting/test_post_plant_quoter.py</files>
  <behavior>
    - On is_first_call=True, post_plant_quote calls mgr.cancel_all_orders() FIRST; sets timestamps["t_quote_pull_completed"] = mono_ns() immediately after cancel_all returns
    - On is_first_call=False, post_plant_quote does NOT call cancel_all_orders; timestamps["t_quote_pull_completed"] is not modified
    - After defensive pull (if applicable), with |theo_c - market.mid| > POST_PLANT_TAKE_THRESHOLD (3), places ONE Quote with strategy_id="POST_PLANT_QUOTE", action=buy at yes_ask (theo > mid) or sell at yes_bid (theo < mid)
    - With |theo_c - market.mid| <= POST_PLANT_TAKE_THRESHOLD, places TWO Quote objects: yes-buy at theo_c - 3, yes-sell at theo_c + 3 (flat 3c half-spread, both strategy_id="POST_PLANT_QUOTE")
    - Hypothetical fills via maybe_record_mm_fill — fills land ONLY in data/fills/{match_id}.post_plant_quote.jsonl
    - Boundary guard: theo_c - 3 < 1 OR theo_c + 3 > 99 → skip the quoting branch (defensive; consistent with plan 04-05 quoter)
    - Defensive double-check: state.bomb_planted=False → post_plant_quote returns immediately WITHOUT placing or pulling (caller should have routed elsewhere, but guard against misuse)
    - Latency assertion (synthetic harness): on a dry-run mgr with 10 pre-placed MM quotes, p50 of (t_quote_pull_completed - t_state_committed) over 50 trials is < 100ms. Latency is structurally trivial in dry-run (cancel_all clears the dict synchronously); the test verifies the INSTRUMENTATION captures the right interval and the implementation has NO unnecessary awaits/blocks BEFORE setting the timestamp (RESEARCH Pitfall 6 — measurement clock alignment)
  </behavior>
  <action>
(A) Create src/quoting/post_plant_quoter.py (~140 lines):

```python
"""POST_PLANT_QUOTE quoter — REQ-post-plant-quoter (NEW v2).

Active when trading_mode == "POST_PLANT_QUOTE" (plan 04-04 rule 2 —
state.bomb_planted=True AND kill switch not active). The latency-critical
mode per PRD §5.4 / DEC-020 v2 — bomb-detect → quote-pull p50 < 200ms
END-TO-END, split:
    Phase 03 (t_observed → t_state_committed): ≤100ms  [GREEN per 03-08]
    Phase 04 (t_state_committed → t_quote_pull_completed): ≤100ms  [HERE]

Three actions per ROADMAP §4.5:
    1. DEFENSIVE QUOTE-PULL: cancel every resting MM quote via
       mgr.cancel_all_orders(). Latency-critical; sets
       timestamps["t_quote_pull_completed"] = mono_ns() at the moment
       cancel_all returns.
    2. RE-PRICE: caller passes `theo: TheoOutput` already computed from
       live_theo(state) — Phase 1 D-14 contract routes bomb_planted=True
       through the post-plant lookup automatically. Plan 04-07 does NOT
       re-implement the routing.
    3. TAKE-OR-QUOTE:
       - |theo_c - market.mid| > POST_PLANT_TAKE_THRESHOLD (3c, narrower
         than between-round 5c) → TAKE via IOC lift/hit
       - else → QUOTE at theo ± POST_PLANT_TAKE_THRESHOLD (flat 3c
         half-spread; high-conviction state per PRD §5.4 — no vega-scaling)

Idempotency-on-pull (RESEARCH Pitfall 6 + ROADMAP §4.5): the caller (bot
main loop in plan 04-08) gates is_first_call=True on the bomb_planted
False → True TRANSITION; subsequent same-mode calls pass is_first_call=
False so cancel_all is NOT re-invoked. This matches the PRD intent —
the defensive pull happens ONCE at bomb-detect, then we steady-state
quote/take with updated theo.

Latency measurement (RESEARCH Pitfall 6):
    timestamps["t_quote_pull_completed"] is set IMMEDIATELY after
    cancel_all_orders returns — no async dispatch, no logging in between,
    no other awaits. The metric is
    `t_quote_pull_completed - t_state_committed`, NOT
    `t_quote_pull_completed - t_observed` (the latter would double-count
    Phase 03's piece of the budget).

Source: PRD §2.1 + §5.4 / DEC-020 v2 / ROADMAP §4.5 / RESEARCH §"Common
Pitfalls" Pitfall 6.
"""
from __future__ import annotations

from pathlib import Path

from src.config.constants import POST_PLANT_TAKE_THRESHOLD
from src.ingestion.timestamps import mono_ns
from src.pricing.data import TheoOutput
from src.quoting.fill_ledger import maybe_record_mm_fill
from src.quoting.market_data import MarketQuote
from src.quoting.order_manager import KalshiOrderManager, Quote
from src.state.match_state import MatchState


async def post_plant_quote(
    state: MatchState,
    theo: TheoOutput,
    market: MarketQuote,
    mgr: KalshiOrderManager,
    ticker: str,
    count: int,
    last_mid_c: int,
    ledger_dir: Path,
    timestamps: dict[str, float | int | None],
    *,
    is_first_call: bool,
    seq_id: int | None = None,
) -> None:
    """Three-action POST_PLANT_QUOTE: defensive pull + re-price + take-or-quote.

    Args:
        is_first_call: True on the bomb_planted False → True transition (one
            time per plant). Triggers the defensive cancel_all_orders. False
            on subsequent same-mode calls — only steps 2 + 3 run.
        timestamps: arbiter's per-event dict; this function sets
            timestamps["t_quote_pull_completed"] = mono_ns() iff
            is_first_call=True AND cancel_all is invoked.

    Latency contract (PRD §5.4 / DEC-020 v2):
        p50 of (t_quote_pull_completed - t_state_committed) < 100ms.
        Verified by test_quote_pull_p50_under_100ms (synthetic harness).
    """
    # Defensive guard — caller should have routed via mode_selector.
    if not state.bomb_planted:
        return

    # Step 1: DEFENSIVE QUOTE-PULL (only on first call per plant).
    if is_first_call:
        await mgr.cancel_all_orders()
        # Set the timestamp IMMEDIATELY — no logging / no other awaits
        # between cancel_all return and this assignment (Pitfall 6).
        timestamps["t_quote_pull_completed"] = mono_ns()

    # Step 2: RE-PRICE — `theo` is already the post-plant-routed value
    # (caller computed it via live_theo(state); Phase 1 D-14 contract
    # dispatches bomb_planted=True through the post-plant lookup). No
    # additional work here.

    # Step 3: TAKE-OR-QUOTE.
    theo_c = round(theo.theo_series * 100)
    diff = abs(theo_c - market.mid)

    if diff > POST_PLANT_TAKE_THRESHOLD:
        # TAKE path — IOC lift/hit mirroring plan 04-06 shape (no Kelly
        # sizing here per the PRD; post-plant uses a fixed count from
        # caller — Phase 5 calibration may refine).
        if theo_c > market.mid:
            quote = Quote(
                ticker=ticker, side="yes", action="buy",
                price=market.yes_ask, count=count,
                strategy_id="POST_PLANT_QUOTE",
            )
        else:
            quote = Quote(
                ticker=ticker, side="yes", action="sell",
                price=market.yes_bid, count=count,
                strategy_id="POST_PLANT_QUOTE",
            )
        placed = await mgr.place_quote(quote)
        if placed:
            sid = seq_id if seq_id is not None else state.seq_id
            maybe_record_mm_fill(
                quote=quote, last_mid_c=last_mid_c, next_mid_c=market.mid,
                seq_id=sid, theo_c=theo_c,
                ledger_dir=ledger_dir, match_id=state.match_id,
            )
    else:
        # QUOTE path — flat half-spread = POST_PLANT_TAKE_THRESHOLD (3c).
        buy_price = theo_c - POST_PLANT_TAKE_THRESHOLD
        sell_price = theo_c + POST_PLANT_TAKE_THRESHOLD
        if buy_price < 1 or sell_price > 99:
            return  # boundary guard (mirrors plan 04-05 mm_quoter)

        buy_q = Quote(
            ticker=ticker, side="yes", action="buy",
            price=buy_price, count=count,
            strategy_id="POST_PLANT_QUOTE",
        )
        sell_q = Quote(
            ticker=ticker, side="yes", action="sell",
            price=sell_price, count=count,
            strategy_id="POST_PLANT_QUOTE",
        )
        await mgr.place_quote(buy_q)
        await mgr.place_quote(sell_q)

        sid = seq_id if seq_id is not None else state.seq_id
        maybe_record_mm_fill(
            quote=buy_q, last_mid_c=last_mid_c, next_mid_c=market.mid,
            seq_id=sid, theo_c=theo_c,
            ledger_dir=ledger_dir, match_id=state.match_id,
        )
        maybe_record_mm_fill(
            quote=sell_q, last_mid_c=last_mid_c, next_mid_c=market.mid,
            seq_id=sid, theo_c=theo_c,
            ledger_dir=ledger_dir, match_id=state.match_id,
        )
```

(B) Update src/quoting/__init__.py to export post_plant_quote.

(C) Flip RED stubs in tests/quoting/test_post_plant_quoter.py to GREEN:

```python
"""Plan 04-07 — REQ-post-plant-quoter (NEW v2) GREEN tests.

Three-action contract: defensive pull (latency-critical) + re-price + take-or-quote.
Latency assertion verifies Phase 04's 100ms piece of PRD's 200ms bomb-detect →
quote-pull p50 budget (RESEARCH Pitfall 6 measurement-clock alignment).
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any

import aiohttp
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from src.config.constants import POST_PLANT_TAKE_THRESHOLD
from src.ingestion.timestamps import mono_ns
from src.pricing.data import TheoOutput
from src.quoting.market_data import make_quote
from src.quoting.order_manager import KalshiOrderManager, Quote
from src.quoting.post_plant_quoter import post_plant_quote


def _theo(theo_series: float = 0.50) -> TheoOutput:
    return TheoOutput(theo_series=theo_series, theo_map=(theo_series,),
                       vega=0.0, confidence=1.0)


def _ts() -> dict[str, Any]:
    """Synthetic arbiter-style timestamps dict."""
    return {
        "t_observed": 0.0, "t_ingested": 0, "t_arbited": 0,
        "t_state_committed": mono_ns(), "t_theo_computed": None,
        "t_quote_sent": None, "t_quote_pull_completed": None,
    }


@pytest.fixture
async def mgr(fake_private_key: rsa.RSAPrivateKey) -> KalshiOrderManager:
    async with aiohttp.ClientSession() as session:
        yield KalshiOrderManager(session=session, key_id="K", private_key=fake_private_key, dry_run=True)


# ---------------- Defensive guard ----------------

@pytest.mark.asyncio
async def test_returns_immediately_when_not_bomb_planted(
    mgr: KalshiOrderManager, make_match_state, tmp_fill_ledger_dir: Path,
) -> None:
    """state.bomb_planted=False → no-op (caller routed in error)."""
    state = make_match_state(bomb_planted=False)
    market = make_quote(48, 52)
    ts = _ts()
    await post_plant_quote(
        state, _theo(0.50), market, mgr,
        ticker="VAL-T1-WIN", count=10, last_mid_c=50,
        ledger_dir=tmp_fill_ledger_dir, timestamps=ts, is_first_call=True,
    )
    assert mgr.active_quotes == {}
    assert ts["t_quote_pull_completed"] is None


# ---------------- Defensive pull (is_first_call) ----------------

@pytest.mark.asyncio
async def test_first_call_invokes_cancel_all_and_sets_timestamp(
    mgr: KalshiOrderManager, make_match_state, tmp_fill_ledger_dir: Path,
) -> None:
    """is_first_call=True → cancel_all_orders + t_quote_pull_completed populated."""
    # Pre-place an MM quote to verify it gets cancelled.
    await mgr.place_quote(Quote(
        ticker="VAL-T1-WIN", side="yes", action="buy", price=50, count=10,
        strategy_id="MM_BETWEEN_ROUND",
    ))
    assert "VAL-T1-WIN" in mgr.active_quotes

    state = make_match_state(bomb_planted=True, attackers_alive=2,
                              defenders_alive=3, time_left_s=20.0)
    market = make_quote(48, 52)
    ts = _ts()
    await post_plant_quote(
        state, _theo(0.50), market, mgr,
        ticker="VAL-T1-WIN", count=10, last_mid_c=50,
        ledger_dir=tmp_fill_ledger_dir, timestamps=ts, is_first_call=True,
    )
    # cancel_all clears MM quotes; t_quote_pull_completed is now non-None.
    assert ts["t_quote_pull_completed"] is not None
    assert isinstance(ts["t_quote_pull_completed"], int)


@pytest.mark.asyncio
async def test_non_first_call_does_not_pull_or_set_timestamp(
    mgr: KalshiOrderManager, make_match_state, tmp_fill_ledger_dir: Path,
) -> None:
    """is_first_call=False → no cancel_all; timestamp stays None."""
    await mgr.place_quote(Quote(
        ticker="VAL-T1-WIN", side="yes", action="buy", price=50, count=10,
        strategy_id="MM_BETWEEN_ROUND",
    ))
    pre_count = len(mgr.active_quotes.get("VAL-T1-WIN", {}))

    state = make_match_state(bomb_planted=True, attackers_alive=2,
                              defenders_alive=3, time_left_s=20.0)
    market = make_quote(48, 52)
    ts = _ts()
    # theo=0.50, mid=50 → diff=0 < 3 → QUOTE branch only (no cancel_all on non-first)
    await post_plant_quote(
        state, _theo(0.50), market, mgr,
        ticker="VAL-T1-WIN", count=10, last_mid_c=50,
        ledger_dir=tmp_fill_ledger_dir, timestamps=ts, is_first_call=False,
    )
    assert ts["t_quote_pull_completed"] is None
    # The MM quote we pre-placed is still there (cancel_all NOT invoked).
    assert "VAL-T1-WIN" in mgr.active_quotes


# ---------------- TAKE branch ----------------

@pytest.mark.asyncio
async def test_take_branch_buy(
    mgr: KalshiOrderManager, make_match_state, tmp_fill_ledger_dir: Path,
) -> None:
    """theo=0.55 (55c), mid=50 → diff=5 > 3 → TAKE via buy at yes_ask."""
    state = make_match_state(bomb_planted=True, attackers_alive=2,
                              defenders_alive=3, time_left_s=20.0)
    market = make_quote(48, 52)  # yes_ask=52
    await post_plant_quote(
        state, _theo(0.55), market, mgr,
        ticker="VAL-T1-WIN", count=10, last_mid_c=50,
        ledger_dir=tmp_fill_ledger_dir, timestamps=_ts(), is_first_call=False,
    )
    legs = mgr.active_quotes["VAL-T1-WIN"]
    assert len(legs) == 1
    quote = next(iter(legs.values()))
    assert quote.action == "buy"
    assert quote.price == 52
    assert quote.strategy_id == "POST_PLANT_QUOTE"


@pytest.mark.asyncio
async def test_take_branch_sell(
    mgr: KalshiOrderManager, make_match_state, tmp_fill_ledger_dir: Path,
) -> None:
    """theo=0.45 (45c), mid=50 → diff=5 > 3 → TAKE via sell at yes_bid."""
    state = make_match_state(bomb_planted=True, attackers_alive=2,
                              defenders_alive=3, time_left_s=20.0)
    market = make_quote(48, 52)  # yes_bid=48
    await post_plant_quote(
        state, _theo(0.45), market, mgr,
        ticker="VAL-T1-WIN", count=10, last_mid_c=50,
        ledger_dir=tmp_fill_ledger_dir, timestamps=_ts(), is_first_call=False,
    )
    quote = next(iter(mgr.active_quotes["VAL-T1-WIN"].values()))
    assert quote.action == "sell"
    assert quote.price == 48
    assert quote.strategy_id == "POST_PLANT_QUOTE"


# ---------------- QUOTE branch ----------------

@pytest.mark.asyncio
async def test_quote_branch_places_two_legs(
    mgr: KalshiOrderManager, make_match_state, tmp_fill_ledger_dir: Path,
) -> None:
    """theo=0.50 (50c), mid=50 → diff=0 <= 3 → QUOTE branch (flat 3c spread)."""
    state = make_match_state(bomb_planted=True, attackers_alive=2,
                              defenders_alive=3, time_left_s=20.0)
    market = make_quote(48, 52)
    await post_plant_quote(
        state, _theo(0.50), market, mgr,
        ticker="VAL-T1-WIN", count=10, last_mid_c=50,
        ledger_dir=tmp_fill_ledger_dir, timestamps=_ts(), is_first_call=False,
    )
    legs = mgr.active_quotes["VAL-T1-WIN"]
    assert len(legs) == 2
    prices = sorted(q.price for q in legs.values())
    assert prices == [50 - POST_PLANT_TAKE_THRESHOLD, 50 + POST_PLANT_TAKE_THRESHOLD]
    for q in legs.values():
        assert q.strategy_id == "POST_PLANT_QUOTE"


# ---------------- Separate-ledger invariant ----------------

@pytest.mark.asyncio
async def test_writes_post_plant_ledger_only(
    mgr: KalshiOrderManager, make_match_state, tmp_fill_ledger_dir: Path,
) -> None:
    """RESEARCH §"Pattern 4" anti-pattern #1: POST_PLANT fills NEVER land in mm or directional."""
    state = make_match_state(bomb_planted=True, attackers_alive=2,
                              defenders_alive=3, time_left_s=20.0, match_id="M-X")
    market = make_quote(48, 52)
    # TAKE path: theo=0.60, mid=50 → diff=10 > 3.
    # Touched rule: last_mid_c=53, next_mid_c=50, quote at yes_ask=52 (buy) →
    # 50 < 52 <= 53 → fill.
    await post_plant_quote(
        state, _theo(0.60), market, mgr,
        ticker="VAL-T1-WIN", count=10, last_mid_c=53,
        ledger_dir=tmp_fill_ledger_dir, timestamps=_ts(), is_first_call=False,
    )
    pp_path = tmp_fill_ledger_dir / "M-X.post_plant_quote.jsonl"
    mm_path = tmp_fill_ledger_dir / "M-X.mm_between_round.jsonl"
    dir_path = tmp_fill_ledger_dir / "M-X.directional_take.jsonl"
    assert pp_path.exists()
    assert not mm_path.exists()
    assert not dir_path.exists()
    parsed = json.loads(pp_path.read_text().splitlines()[0])
    assert parsed["strategy"] == "POST_PLANT_QUOTE"


# ---------------- Boundary guard ----------------

@pytest.mark.asyncio
async def test_quote_branch_skips_when_below_1c(
    mgr: KalshiOrderManager, make_match_state, tmp_fill_ledger_dir: Path,
) -> None:
    """QUOTE branch at theo=0.02 (2c) → buy_price=-1 → skip."""
    state = make_match_state(bomb_planted=True, attackers_alive=2,
                              defenders_alive=3, time_left_s=20.0)
    market = make_quote(1, 3)  # mid=2
    await post_plant_quote(
        state, _theo(0.02), market, mgr,
        ticker="VAL-T1-WIN", count=10, last_mid_c=2,
        ledger_dir=tmp_fill_ledger_dir, timestamps=_ts(), is_first_call=False,
    )
    assert "VAL-T1-WIN" not in mgr.active_quotes


# ---------------- Latency assertion (PRD §5.4 / DEC-020 v2) ----------------

@pytest.mark.asyncio
async def test_quote_pull_p50_under_100ms(
    fake_private_key: rsa.RSAPrivateKey, make_match_state,
    tmp_fill_ledger_dir: Path,
) -> None:
    """Phase 04's piece of PRD's 200ms bomb-detect → quote-pull budget.

    Verifies the INSTRUMENTATION captures the right interval (Pitfall 6 —
    measurement clock alignment). Dry-run cancel_all is structurally
    O(N) over active_quotes; with 10 pre-placed MM quotes, latency is
    sub-millisecond. The 100ms ceiling is the PRD spec; the test asserts
    p50 << 100ms to catch any future regression where blocking I/O slips
    into the cancel-then-timestamp window.
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
            t_state = ts["t_state_committed"]
            await post_plant_quote(
                state, _theo(0.50), market, mgr,
                ticker="VAL-T0", count=10, last_mid_c=50,
                ledger_dir=tmp_fill_ledger_dir,
                timestamps=ts, is_first_call=True,
            )
            assert ts["t_quote_pull_completed"] is not None
            durations_ns.append(int(ts["t_quote_pull_completed"]) - int(t_state))

    p50_ns = statistics.median(durations_ns)
    p50_ms = p50_ns / 1_000_000
    # PRD budget for Phase 04's piece: 100ms. Synthetic harness should be << that.
    assert p50_ms < 100, f"quote_pull p50 {p50_ms:.2f}ms exceeds 100ms budget"
```
  </action>
  <verify>
    <automated>uv run pytest tests/quoting/test_post_plant_quoter.py -x --no-cov &amp;&amp; uv run mypy --strict src/quoting/</automated>
  </verify>
  <done>
- src/quoting/post_plant_quoter.py defines post_plant_quote async coroutine.
- 12 tests in tests/quoting/test_post_plant_quoter.py pass GREEN.
- test_quote_pull_p50_under_100ms verifies Phase 04's 100ms piece of the 200ms bomb-detect → quote-pull budget (50-trial synthetic harness).
- Defensive pull + re-price + take-or-quote three-action contract verified.
- POST_PLANT fills land ONLY in data/fills/{match_id}.post_plant_quote.jsonl.
- src/quoting/__init__.py exports post_plant_quote.
- mypy --strict src/quoting/ clean.
  </done>
</task>

</tasks>

<verification>
1. `uv run pytest tests/ingestion/test_arbiter_t_quote_pull_completed.py tests/quoting/test_post_plant_quoter.py -x --no-cov` — all GREEN.
2. `uv run pytest tests/ingestion/ -x --no-cov` — Phase 03 backward compatibility preserved.
3. `uv run mypy --strict src/quoting/ src/ingestion/` clean.
4. `uv run pytest tests/ -x --no-cov` — Phase 03 + plans 04-00..04-07 stay green; remaining stub (08) xfail.
5. `rg "t_quote_pull_completed" src/ingestion/arbiter.py` matches (key added to both timestamps dict + metrics line).
6. `rg "POST_PLANT_QUOTE" src/quoting/post_plant_quoter.py` matches the strategy_id field on every placed Quote.
7. `python -c "from src.quoting import post_plant_quote; print(post_plant_quote)"` runs without ImportError.
</verification>

<success_criteria>
- Defensive quote-pull p50 < 100ms (Phase 04's piece of PRD's 200ms bomb-detect → quote-pull budget; Pitfall 6 measurement-clock alignment).
- POST_PLANT_QUOTE writes fills ONLY to data/fills/{match_id}.post_plant_quote.jsonl (DEC-020 v2 separate-ledger invariant).
- Three-action contract (pull / re-price / take-or-quote) implemented; idempotent on subsequent calls via is_first_call gating.
- Arbiter timestamps lineage extended to 7 stages (t_quote_pull_completed); Phase 03 baseline backward-compatible.
- All Quote objects placed by post_plant_quoter have strategy_id="POST_PLANT_QUOTE".
</success_criteria>

<output>
After completion, create `.planning/phases/04-quoting-layer/04-07-SUMMARY.md` documenting:
- src/quoting/post_plant_quoter.py file contents (~140 lines).
- src/ingestion/arbiter.py t_quote_pull_completed extension (atomic same-commit with the quoter).
- 14 test results — including test_quote_pull_p50_under_100ms (the latency-critical synthetic harness).
- Forward link: plan 04-08 (E2E test composes the full bomb-detect flow end-to-end + asserts kill-switch cancel-all behavior + mode transition cleanup).
</output>
