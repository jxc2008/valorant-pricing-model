"""Plan 04-05 — REQ-mm-quoter fill ledger GREEN tests.

DEC-020 v2 per-strategy ledger split (anti-pattern #1 — combined files
corrupt the promotion gate fill-count evaluation).
"""
from __future__ import annotations

import json
from pathlib import Path

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
    # YES buy at 50; mid drops from 51 to 49 -> 49 < 50 <= 51 -> True
    assert simulate_touched(50, "buy", last_mid_c=51, next_mid_c=49) is True


def test_simulate_touched_buy_at_boundary() -> None:
    # YES buy at 50; mid drops from 50 to 49 -> 49 < 50 <= 50 -> True (last_mid_c=50 inclusive)
    assert simulate_touched(50, "buy", last_mid_c=50, next_mid_c=49) is True


def test_simulate_touched_buy_not_crossed() -> None:
    # YES buy at 50; mid rises from 51 to 53 -> no crossing
    assert simulate_touched(50, "buy", last_mid_c=51, next_mid_c=53) is False


def test_simulate_touched_sell_crossed() -> None:
    # YES sell at 50; mid rises from 49 to 51 -> 49 <= 50 < 51 -> True
    assert simulate_touched(50, "sell", last_mid_c=49, next_mid_c=51) is True


def test_simulate_touched_sell_at_boundary() -> None:
    # YES sell at 50; mid rises from 50 to 51 -> 50 <= 50 < 51 -> True (last_mid_c=50 inclusive)
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
    """Phase 03 D-03 single-writer invariant: N appends -> N lines in order."""
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
    seq_ids = [json.loads(line)["seq_id"] for line in lines]
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
