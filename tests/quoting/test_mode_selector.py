"""Plan 04-04 — REQ-mode-selector (v2 three-way + IDLE) GREEN tests.

Six rules in declared order. Tie-break test verifies RESEARCH Pitfall 3
(DIRECTIONAL evaluated BEFORE MM when both conditions hold).

Source: PRD §2.1 / DEC-001 v2 / RESEARCH §"Pattern 1" / Pitfall 3.
"""
from __future__ import annotations

from src.pricing.data import TheoOutput
from src.quoting.market_data import make_quote
from src.quoting.mode_selector import trading_mode


def _theo(theo_series: float = 0.50) -> TheoOutput:
    return TheoOutput(
        theo_series=theo_series,
        theo_map=(theo_series,),
        vega=0.0,
        confidence=1.0,
    )


def test_rule_1_kill_switch_dominates_bomb_planted(make_match_state, make_market_quote) -> None:
    """Rule 1: kill_switch_active=True returns IDLE even when bomb_planted=True."""
    state = make_match_state(
        bomb_planted=True,
        attackers_alive=2,
        defenders_alive=3,
        time_left_s=20.0,
    )
    market = make_quote(48, 52)
    assert trading_mode(
        state, _theo(0.99), market, 0.0, 0.0, kill_switch_active=True
    ) == "IDLE"


def test_rule_2_bomb_planted_returns_post_plant_quote(make_match_state, make_market_quote) -> None:
    """Rule 2: bomb_planted=True → POST_PLANT_QUOTE when kill switch is not active."""
    state = make_match_state(
        bomb_planted=True,
        attackers_alive=2,
        defenders_alive=3,
        time_left_s=20.0,
    )
    market = make_quote(48, 52)
    assert trading_mode(
        state, _theo(0.50), market, 0.0, 0.0, kill_switch_active=False
    ) == "POST_PLANT_QUOTE"


def test_rule_3_mid_round_not_planted_returns_idle(make_match_state, make_market_quote) -> None:
    """Rule 3: time_left_s is not None AND bomb_planted=False → IDLE."""
    state = make_match_state(bomb_planted=False, time_left_s=30.0)  # mid-round timer
    market = make_quote(48, 52)
    # theo=0.99 vs mid=50 would normally trigger DIRECTIONAL, but rule 3 fires first.
    assert trading_mode(
        state, _theo(0.99), market, 0.0, 0.0, kill_switch_active=False
    ) == "IDLE"


def test_rule_4_take_threshold_returns_directional(make_match_state, make_market_quote) -> None:
    """Rule 4: |theo*100 - market.mid| > TAKE_THRESHOLD (5) → DIRECTIONAL_TAKE."""
    state = make_match_state(bomb_planted=False, time_left_s=None)  # between-round
    market = make_quote(40, 44)  # mid=42, spread=4
    # theo=0.50 (50c), mid=42 → |50-42| = 8 > 5 → DIRECTIONAL
    assert trading_mode(
        state, _theo(0.50), market, 0.0, 0.0, kill_switch_active=False
    ) == "DIRECTIONAL_TAKE"


def test_rule_5_mm_min_edge_returns_mm_between_round(make_match_state, make_market_quote) -> None:
    """Rule 5: market.spread > MM_MIN_EDGE (4) → MM_BETWEEN_ROUND."""
    state = make_match_state(bomb_planted=False, time_left_s=None)
    market = make_quote(46, 54)  # mid=50, spread=8 > 4
    # theo=0.50, mid=50 → diff=0 < 5 (rule 4 false), spread=8 > 4 (rule 5 true)
    assert trading_mode(
        state, _theo(0.50), market, 0.0, 0.0, kill_switch_active=False
    ) == "MM_BETWEEN_ROUND"


def test_rule_6_fall_through_returns_idle(make_match_state, make_market_quote) -> None:
    """Rule 6: fall-through (no rule fires) → IDLE."""
    state = make_match_state(bomb_planted=False, time_left_s=None)
    market = make_quote(49, 51)  # mid=50, spread=2
    # theo=0.50, diff=0 < 5; spread=2 < 4 → all rules fall through → IDLE
    assert trading_mode(
        state, _theo(0.50), market, 0.0, 0.0, kill_switch_active=False
    ) == "IDLE"


def test_tie_directional_dominates_mm(make_match_state, make_market_quote) -> None:
    """Pitfall 3: when BOTH rule 4 AND rule 5 conditions hold, declared order
    says rule 4 (DIRECTIONAL_TAKE) wins."""
    state = make_match_state(bomb_planted=False, time_left_s=None)
    market = make_quote(40, 50)  # mid=45, spread=10 > 4
    # theo=0.60 (60c), mid=45 → |60-45|=15 > 5 (rule 4) AND spread=10 > 4 (rule 5)
    assert trading_mode(
        state, _theo(0.60), market, 0.0, 0.0, kill_switch_active=False
    ) == "DIRECTIONAL_TAKE"


def test_pure_function_no_hidden_state(make_match_state, make_market_quote) -> None:
    """Same inputs → same output across multiple calls."""
    state = make_match_state(bomb_planted=False, time_left_s=None)
    market = make_quote(46, 54)
    results = [
        trading_mode(state, _theo(0.50), market, 0.0, 0.0, kill_switch_active=False)
        for _ in range(10)
    ]
    assert all(r == results[0] for r in results)
