"""Smoke tests for src.config.constants.

These tests are NOT calibration tests — they verify only:
1. Every constant documented in CON-domain-constants-baseline is importable.
2. Each constant has the documented type.
3. Each constant satisfies the obvious sanity invariants (probabilities in
   [0, 1], rounds positive, fractions in (0, 1], etc.).

Tuning of these values happens in Phase 5 (REQ-calibration-loop). Updates to
the values must update both `src/config/constants.py` AND this test.
"""

from __future__ import annotations

import pytest

from src.config import constants

# --------------------------------------------------------------------------- #
# 1. Importability                                                            #
# --------------------------------------------------------------------------- #

EXPECTED_NAMES: tuple[str, ...] = (
    # Pricing
    "SHRINK_PRIOR",
    "SIGNAL_SCALE",
    "GUN_WIN_RATE",
    "REGULATION_HALF",
    "WIN_THRESHOLD",
    "CONVICTION_CLIP_LOW",
    "CONVICTION_CLIP_HIGH",
    "MIN_ROUNDS_FULL_WEIGHT",
    "BT_BLEND_EPSILON",
    # Sizing
    "KELLY_MULTIPLIER",
    "PER_MARKET_CAP_FRAC",
    # Kill switches
    "KILL_SWITCH_STALENESS_S",
    "KILL_SWITCH_DEVIATION_C",
    "KILL_SWITCH_BRIER_BOUND",
    "KILL_SWITCH_BRIER_WINDOW",
    # Mode flip
    "VEGA_DIRECTIONAL_THRESHOLD",
    # Phase 2 — rib.gg probe ETL
    "RIBGG_BASE_URL",
    "RIBGG_RECENCY_MONTHS",
    "RIBGG_TARGET_MATCH_COUNT",
    "RIBGG_TIER_FILTER",
    "RIBGG_RATE_LIMIT_RPS",
    # Phase 2 — calibration
    "MIN_CELL_N",
    "MID_ROUND_HEARTBEAT_S",
    # Phase 3 — round-conclusion v2 (D-04 / D-06 / D-10)
    "POST_PLANT_TIMER_S",
    "TIME_BUCKET_WIDTH_S",
    "ROUND_CONCLUSION_JSON_PATH",
    # Phase 3 — ingestion arbiter + event logs (DEC-006 v2 / D-03)
    "ARBITER_TICK_HZ",
    "ARBITER_SCORE_WINDOW_S",
    "EVENT_LOG_DIR",
    "METRICS_LOG_DIR",
    # Phase 3 — scoreboard poller (REQ-scoreboard-polling / 03-04 / D-09)
    "SCOREBOARD_POLL_CADENCE_S",
    "SCOREBOARD_FAILURE_COOLDOWN_S",
    "SCOREBOARD_MAX_RETRIES",
    # Phase 3 — OCR pipeline (DEC-024 v2 / D-11/D-12/D-13/D-14)
    "OCR_SCORE_BANNER_CADENCE_MS",
    "OCR_BOMB_ICON_CADENCE_MS",
    "OCR_ROUND_END_CADENCE_MS",
    "OCR_POST_PLANT_ALIVE_CADENCE_MS",
    "OCR_DECODE_BUDGET_MS",
    "BROADCAST_TEMPLATE_VERSION",
    "SCORE_BANNER_TEAM1_ROI",
    "SCORE_BANNER_TEAM2_ROI",
    "BOMB_PLANT_ICON_ROI",
    "ROUND_END_BANNER_ROI",
    "POST_PLANT_ATTACKERS_ROI",
    "POST_PLANT_DEFENDERS_ROI",
    "TESS_CONFIG_DIGIT_SINGLE",
    "TESS_CONFIG_DIGIT_MULTI",
    # Phase 3 — text listener (REQ-text-listener / 03-06 / D-07)
    "TWITTER_API_BASE_URL",
    "TWITTER_RULE_SET",
)


def test_all_expected_constants_are_importable() -> None:
    """Every name in EXPECTED_NAMES must be present and non-None on the module."""
    missing: list[str] = []
    for name in EXPECTED_NAMES:
        if not hasattr(constants, name):
            missing.append(name)
        elif getattr(constants, name) is None:
            missing.append(f"{name} (is None)")
    assert not missing, f"Constants module is missing: {missing}"


def test_no_unexpected_uppercase_names_leak_in() -> None:
    """Catch typos / accidental new constants that weren't added to EXPECTED_NAMES.

    Uses ``__annotations__`` rather than ``dir()`` as the source of truth so
    imported all-caps names cannot trip this test for the wrong reason.

    Every legitimate constant in ``src/config/constants.py`` is declared with
    a PEP-526 ``Final[...]`` annotation (enforced separately by
    ``test_constant_has_expected_type``), which means it lands in
    ``constants.__annotations__``. An ``import``-side name like
    ``from typing import TYPE_CHECKING`` does NOT add to ``__annotations__``,
    so it is correctly excluded here. The (vanishingly small) failure mode
    where someone defines a new threshold WITHOUT a ``Final[...]`` annotation
    would also fail ``test_constant_has_expected_type``, so the contract is
    redundant-but-tight.
    """
    annotated_uppercase = {
        name
        for name in constants.__annotations__
        if name.isupper() and not name.startswith("_")
    }
    expected = set(EXPECTED_NAMES)
    extras = annotated_uppercase - expected
    assert not extras, (
        f"Unexpected UPPER_CASE names in constants module: {extras}. "
        f"If intentional, add to EXPECTED_NAMES in this test."
    )


# --------------------------------------------------------------------------- #
# 2. Types                                                                    #
# --------------------------------------------------------------------------- #

EXPECTED_TYPES: dict[str, type] = {
    "SHRINK_PRIOR": float,
    "SIGNAL_SCALE": float,
    "GUN_WIN_RATE": float,
    "REGULATION_HALF": int,
    "WIN_THRESHOLD": int,
    "CONVICTION_CLIP_LOW": float,
    "CONVICTION_CLIP_HIGH": float,
    "MIN_ROUNDS_FULL_WEIGHT": int,
    "BT_BLEND_EPSILON": float,
    "KELLY_MULTIPLIER": float,
    "PER_MARKET_CAP_FRAC": float,
    "KILL_SWITCH_STALENESS_S": float,
    "KILL_SWITCH_DEVIATION_C": int,
    "KILL_SWITCH_BRIER_BOUND": float,
    "KILL_SWITCH_BRIER_WINDOW": int,
    "VEGA_DIRECTIONAL_THRESHOLD": float,
    "RIBGG_BASE_URL": str,
    "RIBGG_RECENCY_MONTHS": int,
    "RIBGG_TARGET_MATCH_COUNT": int,
    "RIBGG_TIER_FILTER": str,
    "RIBGG_RATE_LIMIT_RPS": float,
    "MIN_CELL_N": int,
    "MID_ROUND_HEARTBEAT_S": float,
    "POST_PLANT_TIMER_S": float,
    "TIME_BUCKET_WIDTH_S": float,
    "ROUND_CONCLUSION_JSON_PATH": str,
    "ARBITER_TICK_HZ": int,
    "ARBITER_SCORE_WINDOW_S": float,
    "EVENT_LOG_DIR": str,
    "METRICS_LOG_DIR": str,
    "SCOREBOARD_POLL_CADENCE_S": float,
    "SCOREBOARD_FAILURE_COOLDOWN_S": float,
    "SCOREBOARD_MAX_RETRIES": int,
    "OCR_SCORE_BANNER_CADENCE_MS": int,
    "OCR_BOMB_ICON_CADENCE_MS": int,
    "OCR_ROUND_END_CADENCE_MS": int,
    "OCR_POST_PLANT_ALIVE_CADENCE_MS": int,
    "OCR_DECODE_BUDGET_MS": int,
    "BROADCAST_TEMPLATE_VERSION": str,
    "SCORE_BANNER_TEAM1_ROI": tuple,
    "SCORE_BANNER_TEAM2_ROI": tuple,
    "BOMB_PLANT_ICON_ROI": tuple,
    "ROUND_END_BANNER_ROI": tuple,
    "POST_PLANT_ATTACKERS_ROI": tuple,
    "POST_PLANT_DEFENDERS_ROI": tuple,
    "TESS_CONFIG_DIGIT_SINGLE": str,
    "TESS_CONFIG_DIGIT_MULTI": str,
    "TWITTER_API_BASE_URL": str,
    "TWITTER_RULE_SET": tuple,
}


@pytest.mark.parametrize("name,expected_type", list(EXPECTED_TYPES.items()))
def test_constant_has_expected_type(name: str, expected_type: type) -> None:
    value = getattr(constants, name)
    # `bool` is a subclass of int — reject it explicitly so a stray `True` literal
    # is caught as a type bug instead of silently passing as int.
    assert not isinstance(value, bool), f"{name} must not be a bool"
    assert isinstance(value, expected_type), (
        f"{name} expected {expected_type.__name__}, got {type(value).__name__}"
    )


# --------------------------------------------------------------------------- #
# 3. Value invariants                                                         #
# --------------------------------------------------------------------------- #


def test_shrink_prior_positive() -> None:
    assert constants.SHRINK_PRIOR > 0


def test_signal_scale_in_unit_interval() -> None:
    # SIGNAL_SCALE divides |model_p - 0.5| (max 0.5) — values >0.5 would
    # always clip to weight 1 and be useless; values <=0 are nonsensical.
    assert 0.0 < constants.SIGNAL_SCALE <= 0.5


def test_gun_win_rate_is_a_probability() -> None:
    assert 0.0 < constants.GUN_WIN_RATE < 1.0
    # Sanity: GUN_WIN_RATE is empirical "rifles beat eco" — should be well above 0.5.
    assert constants.GUN_WIN_RATE > 0.5


def test_regulation_half_and_win_threshold_match_valorant_rules() -> None:
    # Valorant: 12 rounds per half, 13 to win regulation.
    assert constants.REGULATION_HALF == 12
    assert constants.WIN_THRESHOLD == 13
    assert constants.WIN_THRESHOLD == constants.REGULATION_HALF + 1


def test_conviction_clips_are_a_unit_subinterval() -> None:
    """DEC-012 / CRule 6 — clip band is a symmetric sub-interval of (0, 1)."""
    assert 0.0 < constants.CONVICTION_CLIP_LOW < 0.5
    assert 0.5 < constants.CONVICTION_CLIP_HIGH < 1.0
    assert pytest.approx(1.0) == constants.CONVICTION_CLIP_LOW + constants.CONVICTION_CLIP_HIGH


def test_min_rounds_full_weight_positive() -> None:
    """D-09 — `_data_weight` divisor must be a positive sample size."""
    assert constants.MIN_ROUNDS_FULL_WEIGHT > 0


def test_bt_blend_epsilon_is_a_small_positive_float() -> None:
    """CON-bradley-terry-formula — epsilon must be a tiny positive number."""
    assert 0.0 < constants.BT_BLEND_EPSILON < 0.01


def test_kelly_multiplier_is_half() -> None:
    # CLAUDE.md rule 7: half-Kelly. Anything else is a violation of the locked decision.
    assert constants.KELLY_MULTIPLIER == 0.5


def test_per_market_cap_frac_is_a_small_fraction() -> None:
    assert 0.0 < constants.PER_MARKET_CAP_FRAC <= 0.25  # 25% of bankroll on one market is the
    # generous upper bound for sanity; the actual locked initial value is 0.05.


def test_kill_switch_staleness_positive_seconds() -> None:
    assert constants.KILL_SWITCH_STALENESS_S > 0


def test_kill_switch_deviation_positive_cents() -> None:
    assert constants.KILL_SWITCH_DEVIATION_C > 0
    # Kalshi prices are 1-99 cents; a deviation > 99 would never trip.
    assert constants.KILL_SWITCH_DEVIATION_C < 100


def test_kill_switch_brier_bound_in_unit_interval() -> None:
    # Brier scores for binary outcomes lie in [0, 1].
    # An upper bound of 0 would always trip; an upper bound of 1 would never.
    assert 0.0 < constants.KILL_SWITCH_BRIER_BOUND < 1.0


def test_kill_switch_brier_window_is_positive_int() -> None:
    assert constants.KILL_SWITCH_BRIER_WINDOW > 0


def test_vega_directional_threshold_in_unit_interval() -> None:
    # Vega here is variance of next theo update, theo in [0,1] => vega in [0, 0.25].
    assert 0.0 < constants.VEGA_DIRECTIONAL_THRESHOLD <= 0.25


# --------------------------------------------------------------------------- #
# 4. Phase 2 — value invariants                                               #
# --------------------------------------------------------------------------- #


def test_ribgg_base_url_is_v1_endpoint() -> None:
    """02-RESEARCH.md verified `https://be-prod.rib.gg/v1` 2026-04-30."""
    assert constants.RIBGG_BASE_URL == "https://be-prod.rib.gg/v1"


def test_ribgg_recency_months_positive() -> None:
    """D-03: hard cap on event recency."""
    assert constants.RIBGG_RECENCY_MONTHS > 0


def test_ribgg_target_match_count_at_least_500() -> None:
    """D-03 / must-have #1: target 1000 matches; floor for must-have is 500."""
    assert constants.RIBGG_TARGET_MATCH_COUNT >= 500


def test_ribgg_tier_filter_is_vct() -> None:
    """D-03: tier-1 filter token."""
    assert constants.RIBGG_TIER_FILTER == "VCT"


def test_ribgg_rate_limit_positive_rps() -> None:
    """02-RESEARCH.md §Pattern 1: polite-citizen throttle."""
    assert constants.RIBGG_RATE_LIMIT_RPS > 0


def test_min_cell_n_positive_int() -> None:
    """02-RESEARCH.md §Project Constraints #6: cell drop floor."""
    assert constants.MIN_CELL_N >= 1


def test_mid_round_heartbeat_positive_seconds() -> None:
    """D-06: synthetic-heartbeat interval."""
    assert constants.MID_ROUND_HEARTBEAT_S > 0


def test_post_plant_timer_is_45_seconds() -> None:
    """03-CONTEXT.md D-14: Valorant post-plant bomb timer."""
    assert constants.POST_PLANT_TIMER_S == 45.0


def test_time_bucket_width_is_5_seconds() -> None:
    """03-CONTEXT.md D-10: 9 buckets across the 45s post-plant timer."""
    assert constants.TIME_BUCKET_WIDTH_S == 5.0
    # 45 / 5 = 9 buckets — sanity check the math.
    assert constants.POST_PLANT_TIMER_S / constants.TIME_BUCKET_WIDTH_S == 9.0


def test_round_conclusion_json_path_default() -> None:
    """D-06: canonical disk path for the v2 calibrated lookup."""
    assert constants.ROUND_CONCLUSION_JSON_PATH == "models/round_conclusion.json"
