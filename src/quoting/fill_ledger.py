"""Hypothetical-fill JSONL ledger — per-strategy file split (DEC-020 v2).

CO-OWNED by plan 04-05 (MM quoter), 04-06 (directional taker), 04-07
(post-plant quoter). Each quoter calls maybe_record_mm_fill with its OWN
strategy_id; the helper routes to the correct per-strategy file
(data/fills/{match_id}.{strategy_lower}.jsonl).

Per RESEARCH §"Pattern 4" + DEC-020 v2:
  - MM_BETWEEN_ROUND and DIRECTIONAL_TAKE fills MUST land in different files.
    Combined writes corrupt the promotion gate evaluation (DEC-020 v2 fill-
    count gate per strategy).
  - Schema: 11-key JSONL per fill (10 written at fill time + realized_outcome
    + pnl_cents populated by Phase 5 backtest replay), keyed on seq_id so
    Phase 5 backtest replay can JOIN against data/event_log/{match_id}.jsonl
    (state) and data/metrics/{match_id}.metrics.jsonl (latency).
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
    """One simulated fill — RESEARCH §"Pattern 4" 10-key schema (+2 Phase-5 keys).

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
        MM_BETWEEN_ROUND  -> {match_id}.mm_between_round.jsonl
        DIRECTIONAL_TAKE  -> {match_id}.directional_take.jsonl
        POST_PLANT_QUOTE  -> {match_id}.post_plant_quote.jsonl

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
