"""Plan 04-04 — REQ-mode-selector RED-stub tests.

All 6 selection rules in declared order + tie-break + IDLE fall-through.
Each test xfails until plan 04-04 ships src/quoting/mode_selector.py.

Source: PRD §2.1 / DEC-001 v2 / RESEARCH §"Pattern 1" / Pitfall 3.
"""
from __future__ import annotations

import pytest


def test_rule_1_kill_switch_dominates(make_match_state, make_market_quote) -> None:
    pytest.xfail("Plan 04-04 — src/quoting/mode_selector.py not yet implemented")


def test_rule_2_bomb_planted_returns_post_plant_quote(make_match_state, make_market_quote) -> None:
    pytest.xfail("Plan 04-04 — src/quoting/mode_selector.py not yet implemented")


def test_rule_3_mid_round_not_planted_returns_idle(make_match_state, make_market_quote) -> None:
    pytest.xfail("Plan 04-04 — src/quoting/mode_selector.py not yet implemented")


def test_rule_4_take_threshold_returns_directional(make_match_state, make_market_quote) -> None:
    pytest.xfail("Plan 04-04 — src/quoting/mode_selector.py not yet implemented")


def test_rule_5_mm_min_edge_returns_mm_between_round(make_match_state, make_market_quote) -> None:
    pytest.xfail("Plan 04-04 — src/quoting/mode_selector.py not yet implemented")


def test_rule_6_fall_through_returns_idle(make_match_state, make_market_quote) -> None:
    pytest.xfail("Plan 04-04 — src/quoting/mode_selector.py not yet implemented")


def test_tie_directional_dominates_mm(make_match_state, make_market_quote) -> None:
    """Pitfall 3: when BOTH rule 4 AND rule 5 conditions hold, declared
    order says rule 4 wins (DIRECTIONAL_TAKE). Pure-source-order priority."""
    pytest.xfail("Plan 04-04 — src/quoting/mode_selector.py not yet implemented")
