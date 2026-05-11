"""Plan 04-06 — REQ-directional-taker RED-stub tests.

DIRECTIONAL_TAKE quoter: fires on |theo - market.mid| > TAKE_THRESHOLD,
consumes kelly_size from src.sizing.kelly, writes to dedicated DIRECTIONAL
hypothetical-fill ledger (Pattern 4).

Source: PRD §2.1 / REQ-directional-taker / DEC-001 v2.
"""
from __future__ import annotations

import pytest


def test_take_fires_at_threshold(make_match_state, make_market_quote) -> None:
    """|theo_cents - market.mid| > TAKE_THRESHOLD triggers a take order."""
    pytest.xfail("Plan 04-06 — src/quoting/directional_taker.py not yet implemented")


def test_kelly_sized(make_match_state, make_market_quote) -> None:
    """Sizer call uses src.sizing.kelly.kelly_size with portfolio Kelly (DEC-023)."""
    pytest.xfail("Plan 04-06 — src/quoting/directional_taker.py not yet implemented")


def test_writes_directional_ledger_only(tmp_fill_ledger_dir) -> None:
    """Pattern 4 (Pattern 4 separate ledgers) — directional fills go to
    directional.jsonl, NOT mm_between_round.jsonl."""
    pytest.xfail("Plan 04-06 — src/quoting/directional_taker.py not yet implemented")
