"""Plan 04-05 — REQ-mm-quoter RED-stub tests.

MM_BETWEEN_ROUND quoter: spread formula floor (MIN_HALF_SPREAD), vega scaling,
2s staleness pull, dedicated MM hypothetical-fill ledger (Pattern 4 separate
ledgers per strategy).

Source: PRD §5.4 / REQ-mm-quoter / Pitfall 4 (fee floor) / Pattern 4.
"""
from __future__ import annotations

import pytest


def test_spread_formula(make_match_state, make_market_quote) -> None:
    """spread = max(MIN_HALF_SPREAD, k * sqrt(vega_between)) + staleness_penalty."""
    pytest.xfail("Plan 04-05 — src/quoting/mm_quoter.py not yet implemented")


def test_spread_floor_beats_fee(make_market_quote) -> None:
    """Property test (Pitfall 4): for theo in [10c, 90c], floor spread + maker fee
    nets positive after Kalshi fee curve."""
    pytest.xfail("Plan 04-05 — src/quoting/mm_quoter.py not yet implemented")


def test_writes_mm_between_round_ledger(tmp_fill_ledger_dir) -> None:
    """Pattern 4: MM fills land ONLY in mm_between_round.jsonl, not the
    directional or post_plant ledgers."""
    pytest.xfail("Plan 04-05 — src/quoting/mm_quoter.py not yet implemented")


def test_pulls_quotes_on_2s_staleness(make_match_state) -> None:
    """PRD §5.4 — MM quote-pull fires when arbiter staleness exceeds 2s
    (well before the 5s KILL_SWITCH_STALENESS_S trip)."""
    pytest.xfail("Plan 04-05 — src/quoting/mm_quoter.py not yet implemented")
