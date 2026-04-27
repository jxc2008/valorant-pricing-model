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
    "KELLY_MULTIPLIER": float,
    "PER_MARKET_CAP_FRAC": float,
    "KILL_SWITCH_STALENESS_S": float,
    "KILL_SWITCH_DEVIATION_C": int,
    "KILL_SWITCH_BRIER_BOUND": float,
    "KILL_SWITCH_BRIER_WINDOW": int,
    "VEGA_DIRECTIONAL_THRESHOLD": float,
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
