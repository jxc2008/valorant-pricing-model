"""Plan 04-05 / 04-06 / 04-07 — REQ-fill-ledger RED-stub tests.

Per-strategy hypothetical-fill ledgers (Pattern 4): MM_BETWEEN_ROUND,
DIRECTIONAL, POST_PLANT each write to a SEPARATE file. Simple "touched" fill
rule for MM (DEC-020); 10-key JSONL schema.

Source: PRD §8 / DEC-020 v2 / Pattern 4.
"""
from __future__ import annotations

import pytest


def test_per_strategy_ledger_separate_files(tmp_fill_ledger_dir) -> None:
    """MM_BETWEEN_ROUND, DIRECTIONAL, POST_PLANT each write to their own JSONL."""
    pytest.xfail("Plan 04-05 — src/quoting/fill_ledger.py not yet implemented")


def test_simulate_mm_fill_buy_crossed(tmp_fill_ledger_dir, make_market_quote) -> None:
    """DEC-020 simple "touched" rule: BUY at yes_bid fills when market.yes_bid
    moves up to >= our quote price."""
    pytest.xfail("Plan 04-05 — src/quoting/fill_ledger.py not yet implemented")


def test_simulate_mm_fill_sell_crossed(tmp_fill_ledger_dir, make_market_quote) -> None:
    """SELL at yes_ask fills when market.yes_ask moves down to <= our quote price."""
    pytest.xfail("Plan 04-05 — src/quoting/fill_ledger.py not yet implemented")


def test_simulate_mm_fill_not_touched(tmp_fill_ledger_dir, make_market_quote) -> None:
    """No-fill case — market does not cross our quote."""
    pytest.xfail("Plan 04-05 — src/quoting/fill_ledger.py not yet implemented")


def test_jsonl_line_schema(tmp_fill_ledger_dir) -> None:
    """10-key JSONL schema: ts, match_id, strategy, side, price, qty, theo,
    market_mid, vega, fill_outcome."""
    pytest.xfail("Plan 04-05 — src/quoting/fill_ledger.py not yet implemented")


def test_directional_separate_ledger(tmp_fill_ledger_dir) -> None:
    """DIRECTIONAL fills land in directional.jsonl only — never in
    mm_between_round.jsonl."""
    pytest.xfail("Plan 04-06 — src/quoting/fill_ledger.py not yet implemented")
