"""Plan 04-07 — REQ-post-plant-quoter RED-stub tests.

POST_PLANT_QUOTE quoter: defensive quote-pull on bomb_planted False -> True
edge; repricing through live_theo's post-plant lookup; take-OR-quote branch at
POST_PLANT_TAKE_THRESHOLD; 100ms p50 quote-pull latency (Phase 04's piece of
PRD's 200ms bomb-detect -> quote-pull budget; Pitfall 6).

Source: PRD §5.4 / REQ-post-plant-quoter / Pitfall 6.
"""
from __future__ import annotations

import pytest


def test_defensive_quote_pull(make_match_state) -> None:
    """bomb_planted edge False -> True triggers cancel-all-MM_BETWEEN_ROUND
    resting orders before re-quoting on the post-plant path."""
    pytest.xfail("Plan 04-07 — src/quoting/post_plant_quoter.py not yet implemented")


def test_repricing_via_post_plant_lookup(make_match_state, make_market_quote) -> None:
    """Repricing path consumes live_theo's post_plant dispatch (Phase 03 D-05)
    — keyed on (att, def_, time_bucket, side, map)."""
    pytest.xfail("Plan 04-07 — src/quoting/post_plant_quoter.py not yet implemented")


def test_take_or_quote_branch_at_threshold(make_match_state, make_market_quote) -> None:
    """|theo - market.mid| > POST_PLANT_TAKE_THRESHOLD branches to take;
    otherwise quotes at theo +/- narrow spread."""
    pytest.xfail("Plan 04-07 — src/quoting/post_plant_quoter.py not yet implemented")


def test_quote_pull_p50(make_match_state) -> None:
    """Phase 04's 100ms piece of PRD's 200ms bomb-detect -> quote-pull p50 budget
    (Pitfall 6). Synthetic harness — production gate is Phase 5 paper-trade."""
    pytest.xfail("Plan 04-07 — src/quoting/post_plant_quoter.py not yet implemented")
