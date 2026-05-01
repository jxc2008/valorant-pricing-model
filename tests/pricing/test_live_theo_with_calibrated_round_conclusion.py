"""Phase 2 integration test — must-have #3 from ROADMAP §2.

Wires:
    HalfRates.from_json(data/half_win_rates.json)
        -> RoundConclusionLookup.from_json(models/round_conclusion.json)
        -> LiveTheoEngine(half_rates=..., round_conclusion=lookup.lookup)
        -> engine(mid_round_match_state) -> TheoOutput

Asserts:
  - The wiring succeeds end-to-end (no import-time errors, no constructor errors).
  - The engine returns a well-shaped TheoOutput within conviction clips.
  - The mid-round path produces a non-degenerate result when the calibrated
    lookup has a populated cell that the state's `(numerical_diff, bomb_planted)`
    key hits (skipped if no such cell exists in the calibration).
  - Path C compatibility: with no JSON file, the engine still works (flat 0.5
    baseline) — locks D-12's hard contract that mid-round triggers do NOT move
    theo when round_conclusion is the empty lookup.

Side-orient note: src/pricing/live_theo.py uses the "a_atk" / "a_def" Phase 1
encoding for side_orient and map_side_orients (not the bare "atk" / "def" used
by the round_conclusion lookup's `side` parameter). The synthetic state below
honors that distinction — `side_orient` / `map_side_orients` carry "a_atk" /
"a_def"; `side` carries "atk".

Sources
-------
- 02-CONTEXT.md must-have #3
- ROADMAP.md §2 must-have #3
- 02-CONTEXT.md D-12 (Phase 4 hard contract for Path C)
- src/pricing/live_theo.py (LiveTheoEngine constructor + side_orient encoding)
- src/pricing/data.py (MatchState 17-field surface)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.config.constants import CONVICTION_CLIP_HIGH, CONVICTION_CLIP_LOW
from src.pricing.data import HalfRates, MatchState, TheoOutput
from src.pricing.live_theo import LiveTheoEngine
from src.pricing.round_conclusion import RoundConclusionLookup

MODEL_PATH: Path = Path("models/round_conclusion.json")
HALF_RATES_PATH: Path = Path("data/half_win_rates.json")


def _synthetic_mid_round_state() -> MatchState:
    """A representative mid-round state at numerical_diff=0, bomb_planted=False.

    Choosing nd=0 / bomb=False maximizes the chance that the calibrated
    cells_minimal has a populated entry (most rounds spend time at nd=0 prior
    to the first kill). The mid-round assertion only fires when a populated
    cell hits; otherwise the test SKIPs with a reason.

    Uses Phase 1 side encoding: side_orient and map_side_orients are
    "a_atk" / "a_def"; the lookup-facing `side` is "atk".
    """
    return MatchState(
        match_id="TEST-INTEG-01",
        team_a="SEN",
        team_b="KRÜ",
        map_pool=("Lotus", "Bind", "Haven"),
        map_idx=0,
        a_map_score=0,
        b_map_score=0,
        a_round=6,
        b_round=5,
        side_orient="a_atk",
        map_side_orients=("a_atk", "a_def", "a_atk"),
        map_winners=(None, None, None),
        pistol_winner_a={0: True, 1: None, 2: None},
        numerical_diff=0,
        bomb_planted=False,
        side="atk",
        econ_bucket="full",
    )


def test_lookup_loads_from_calibrated_json() -> None:
    """Plan 02-04 ships models/round_conclusion.json — load it."""
    if not MODEL_PATH.exists():
        pytest.skip("models/round_conclusion.json not generated (Path C deferred)")
    lookup = RoundConclusionLookup.from_json(MODEL_PATH)
    assert isinstance(lookup, RoundConclusionLookup)


def test_engine_constructs_with_calibrated_lookup() -> None:
    """LiveTheoEngine accepts the calibrated lookup's `.lookup` as RoundConclusionFn."""
    if not MODEL_PATH.exists() or not HALF_RATES_PATH.exists():
        pytest.skip("Calibrated artifact or half_win_rates.json missing")
    half_rates = HalfRates.from_json(HALF_RATES_PATH)
    lookup = RoundConclusionLookup.from_json(MODEL_PATH)
    engine = LiveTheoEngine(half_rates=half_rates, round_conclusion=lookup.lookup)
    assert engine is not None


def test_engine_returns_theo_output_with_calibrated_lookup() -> None:
    """End-to-end call returns a well-shaped TheoOutput in the conviction clip band."""
    if not MODEL_PATH.exists() or not HALF_RATES_PATH.exists():
        pytest.skip("Calibrated artifact or half_win_rates.json missing")
    half_rates = HalfRates.from_json(HALF_RATES_PATH)
    lookup = RoundConclusionLookup.from_json(MODEL_PATH)
    engine = LiveTheoEngine(half_rates=half_rates, round_conclusion=lookup.lookup)
    state = _synthetic_mid_round_state()

    result = engine(state)
    assert isinstance(result, TheoOutput)
    assert CONVICTION_CLIP_LOW <= result.theo_series <= CONVICTION_CLIP_HIGH
    for theo_map_i in result.theo_map:
        assert CONVICTION_CLIP_LOW <= theo_map_i <= CONVICTION_CLIP_HIGH
    assert result.vega >= 0.0
    assert 0.0 <= result.confidence <= 1.0


def test_calibrated_lookup_returns_finite_value_for_in_distribution_key() -> None:
    """Must-have #3: mid-round live_theo produces non-degenerate predictions
    (when calibration cells exist for the queried key).

    Picks a (nd, bp) key likely to have data — (0, False) is the most-common
    cell in any calibration dataset because every round starts there.
    """
    if not MODEL_PATH.exists():
        pytest.skip("Calibrated artifact missing — Path C deferred")
    lookup = RoundConclusionLookup.from_json(MODEL_PATH)
    val = lookup.lookup(0, False, "atk", "full", "Lotus")
    assert 0.0 <= val <= 1.0

    # Stronger signal: if calibration produced cells_minimal entries, at least
    # one of them should produce a non-0.5 shrunk value (not exactly the
    # uninformative prior).
    if lookup.cells_minimal:
        any_non_05 = any(
            abs(c.shrunk() - 0.5) > 1e-9 for c in lookup.cells_minimal.values()
        )
        assert any_non_05, (
            "cells_minimal populated but every shrunk() == 0.5 — calibration "
            "produced only uninformative cells; check synthetic_round_events "
            "fixture or live data."
        )


def test_path_c_compat_no_json_falls_back_to_baseline() -> None:
    """Must-have #3 alternative: with no JSON, lookup still callable; returns 0.5.

    D-12 hard contract: mid-round vega is flat for Path C — directional-flip
    triggers fire for order-pull purposes but do NOT move theo. Asserted here
    by the empty lookup returning the side_baseline default (0.5) verbatim.
    """
    if not HALF_RATES_PATH.exists():
        pytest.skip("data/half_win_rates.json missing")
    half_rates = HalfRates.from_json(HALF_RATES_PATH)
    # Path C: empty lookup, no cells. side_baseline defaults to {atk: 0.5, def: 0.5}.
    empty_lookup = RoundConclusionLookup()
    engine = LiveTheoEngine(
        half_rates=half_rates, round_conclusion=empty_lookup.lookup
    )

    state = _synthetic_mid_round_state()
    result = engine(state)
    # The engine still returns a valid TheoOutput; mid-round contribution is just
    # the side_baseline for Path C (D-12 hard contract).
    assert isinstance(result, TheoOutput)
    assert CONVICTION_CLIP_LOW <= result.theo_series <= CONVICTION_CLIP_HIGH

    # Direct lookup call returns the side_baseline value (0.5)
    assert empty_lookup.lookup(0, False, "atk", "full", "Lotus") == 0.5
