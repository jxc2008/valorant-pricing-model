"""Tests for src.pricing.round_types — REQ-pistol-anti-eco-modeling.

Verifies:
  - Round-num dispatch correctly routes to pistol / anti-eco / gunround paths.
  - GUN_WIN_RATE wired correctly: rounds 2/3/14/15 return 0.822 (or 0.178).
  - pistol_winner_a fall-through (None pre-pistol → defensive 0.5).
  - Side-derivation helpers (_team_a_side, _team_b_side) are correct.
  - Source does not contain the audit-engine arithmetic-mean blend (DEC-003).
  - Source uses TYPE_CHECKING-guarded import for MatchState (avoids circular).

Notes
-----
``BO3State`` is owned by ``src/pricing/dp.py`` (Plan 01-02, parallel wave-2 worktree).
Because this plan (01-03) executes in a sibling worktree that must not stomp on
01-02's dp.py, the tests here use a local ``_FakeBO3State`` dataclass that
satisfies the documented runtime contract (the same field names and types
specified in 01-02-bo3-dp-engine-PLAN lines 162-170 and 01-RESEARCH §2 / §4).
``round_types.round_p_for_round`` is duck-typed at runtime (BO3State only
appears under ``if TYPE_CHECKING:``), so this fake is functionally identical to
the real type for these tests. After both worktrees merge, the same tests
exercise the real ``src.pricing.dp.BO3State`` indirectly via 01-05's live_theo
integration tests.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from src.config.constants import GUN_WIN_RATE
from src.pricing import blend
from src.pricing.round_types import (
    HalfRates,
    _team_a_side,
    _team_b_side,
    round_p_for_round,
)

# --------------------------------------------------------------------------- #
# 0. Test fixtures                                                            #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class _FakeBO3State:
    """Duck-typed BO3State stand-in. Mirrors src.pricing.dp.BO3State (01-02).

    Field semantics match 01-02-bo3-dp-engine-PLAN lines 265-282 verbatim. We
    do not import the real BO3State because 01-02 ships dp.py in a parallel
    worktree (see module docstring for details).
    """

    map_idx: int
    a_map_score: int
    b_map_score: int
    a_round: int
    b_round: int
    side_orient: str
    map_pool: tuple[str, ...]
    pistol_winner_a: tuple[bool | None, ...]


@dataclass(frozen=True)
class _FakeMatchState:
    """Minimal MatchState shape required by round_p_for_round."""

    team_a: str = "TeamA"
    team_b: str = "TeamB"


class _FakeHalfRates:
    """In-memory HalfRates Protocol implementation.

    Stores per-(team, map, side) rates explicitly. team() returns the stored
    value or 0.5 as a default. team_entry() is unused by round_types but the
    Protocol requires it.
    """

    def __init__(self) -> None:
        self._rates: dict[tuple[str, str, str], float] = {}

    def set(self, team: str, map_name: str, side: str, rate: float) -> None:
        self._rates[(team, map_name, side)] = rate

    def team(self, team: str, map_name: str, side: str) -> float:
        return self._rates.get((team, map_name, side), 0.5)

    def team_entry(
        self, team: str, map_name: str, side: str
    ) -> dict[str, Any] | None:
        return None


def _state(
    a_round: int = 0,
    b_round: int = 0,
    side_orient: str = "a_atk",
    pistol_winner_a: tuple[bool | None, ...] = (None, None, None),
) -> _FakeBO3State:
    return _FakeBO3State(
        map_idx=0,
        a_map_score=0,
        b_map_score=0,
        a_round=a_round,
        b_round=b_round,
        side_orient=side_orient,
        map_pool=("Lotus", "Bind", "Haven"),
        pistol_winner_a=pistol_winner_a,
    )


def test_halfrates_protocol_runtime_check() -> None:
    """_FakeHalfRates duck-types HalfRates — sanity check the Protocol surface."""
    hr: HalfRates = _FakeHalfRates()
    assert hr.team("X", "Lotus", "atk") == 0.5  # default
    assert hr.team_entry("X", "Lotus", "atk") is None


# --------------------------------------------------------------------------- #
# 1. Side-derivation helpers                                                  #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "side_orient,a_side,b_side",
    [
        ("a_atk", "atk", "def"),
        ("a_def", "def", "atk"),
    ],
)
def test_side_derivation(side_orient: str, a_side: str, b_side: str) -> None:
    assert _team_a_side(side_orient) == a_side
    assert _team_b_side(side_orient) == b_side


# --------------------------------------------------------------------------- #
# 2. Pistol rounds (1, 13) — Phase 1 fallback to half-rates blend             #
# --------------------------------------------------------------------------- #


def test_round_1_pistol_uses_half_rates_blend() -> None:
    """Round 1 (a_round=0, b_round=0): blend.round_p(team_a_atk_rate, team_b_def_rate)."""
    half_rates = _FakeHalfRates()
    half_rates.set("TeamA", "Lotus", "atk", 0.55)
    half_rates.set("TeamB", "Lotus", "def", 0.50)
    state = _state(a_round=0, b_round=0, side_orient="a_atk")
    expected = blend.round_p(0.55, 0.50)
    actual = round_p_for_round(state, _FakeMatchState(), half_rates)  # type: ignore[arg-type]
    assert math.isclose(actual, expected, rel_tol=1e-12)


def test_round_13_pistol_uses_flipped_side() -> None:
    """Round 13 (a_round + b_round + 1 == 13 → e.g., a_round=12, b_round=0):
    side_orient should be 'a_def' (sides flipped after round 12). The dispatch
    fetches half_rates for team A on def, team B on atk."""
    half_rates = _FakeHalfRates()
    half_rates.set("TeamA", "Lotus", "def", 0.45)
    half_rates.set("TeamB", "Lotus", "atk", 0.60)
    state = _state(a_round=12, b_round=0, side_orient="a_def")
    expected = blend.round_p(0.45, 0.60)
    actual = round_p_for_round(state, _FakeMatchState(), half_rates)  # type: ignore[arg-type]
    assert math.isclose(actual, expected, rel_tol=1e-12)


# --------------------------------------------------------------------------- #
# 3. Anti-eco rounds (2, 3, 14, 15)                                            #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "a_round,b_round,description",
    [
        (1, 0, "round 2 — A won round 1"),
        (2, 0, "round 3 — A won rounds 1 and 2"),
        (12, 1, "round 14"),
        (12, 2, "round 15"),
    ],
)
def test_anti_eco_returns_gun_win_rate_when_a_won_pistol(
    a_round: int, b_round: int, description: str
) -> None:
    """Anti-eco rounds with pistol_winner_a[map_idx] = True → exactly GUN_WIN_RATE."""
    state = _state(
        a_round=a_round,
        b_round=b_round,
        pistol_winner_a=(True, None, None),
    )
    actual = round_p_for_round(state, _FakeMatchState(), _FakeHalfRates())  # type: ignore[arg-type]
    assert actual == GUN_WIN_RATE, description


@pytest.mark.parametrize(
    "a_round,b_round",
    [(1, 0), (2, 0), (12, 1), (12, 2)],
)
def test_anti_eco_returns_complement_when_b_won_pistol(
    a_round: int, b_round: int
) -> None:
    """Anti-eco rounds with pistol_winner_a[map_idx] = False → exactly 1 - GUN_WIN_RATE."""
    state = _state(
        a_round=a_round,
        b_round=b_round,
        pistol_winner_a=(False, None, None),
    )
    actual = round_p_for_round(state, _FakeMatchState(), _FakeHalfRates())  # type: ignore[arg-type]
    assert math.isclose(actual, 1.0 - GUN_WIN_RATE, rel_tol=1e-12)


def test_anti_eco_with_none_pistol_winner_returns_defensive_05_for_malformed_external_input() -> None:  # noqa: E501
    """The 0.5 fallback at round_types.py:152 is for MALFORMED EXTERNAL INPUTS
    only — e.g., a caller hand-rolling a state with `a_round + b_round + 1 == 2`
    AND `pistol_winner_a[map_idx] is None` (an inconsistent live-ingestion
    payload). In a well-formed DP forward-pass after the CR-05 fix
    (01-VERIFICATION.md gaps[0] / 01-07 plan), `dp._advance_round` populates
    `pistol_winner_a[map_idx]` when round 1 settles, so the round-2/3 dispatch
    in DP recursion NEVER reaches this branch. Same for the future-map sub-DP
    after the WR-06 fix in `_within_map_p_a_wins`.

    The assertion target is UNCHANGED: the round_types.py dispatch is unchanged;
    only the upstream DP forward-pass updates pistol_winner_a. This test now
    documents the post-fix invariant — the 0.5 fallback is a defensive guard
    against malformed external inputs, not a code path the DP ever hits.
    """
    state = _state(
        a_round=1,
        b_round=0,
        pistol_winner_a=(None, None, None),
    )
    actual = round_p_for_round(state, _FakeMatchState(), _FakeHalfRates())  # type: ignore[arg-type]
    assert actual == 0.5


# --------------------------------------------------------------------------- #
# 4. Gunround baseline (4-12, 16-24)                                           #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "a_round,b_round,side_orient,a_side,b_side",
    [
        (3, 0, "a_atk", "atk", "def"),    # round 4 — first half
        (8, 3, "a_atk", "atk", "def"),    # round 12 — first half
        (13, 2, "a_def", "def", "atk"),   # round 16 — second half
        (15, 8, "a_def", "def", "atk"),   # round 24 — last regulation round
    ],
)
def test_gunround_uses_half_rates_blend(
    a_round: int, b_round: int, side_orient: str, a_side: str, b_side: str
) -> None:
    """Gunrounds {4-12, 16-24}: half_rates blend, ignores pistol_winner_a."""
    half_rates = _FakeHalfRates()
    half_rates.set("TeamA", "Lotus", a_side, 0.52)
    half_rates.set("TeamB", "Lotus", b_side, 0.48)
    state = _state(
        a_round=a_round,
        b_round=b_round,
        side_orient=side_orient,
        pistol_winner_a=(None, None, None),  # gunround ignores this
    )
    expected = blend.round_p(0.52, 0.48)
    actual = round_p_for_round(state, _FakeMatchState(), half_rates)  # type: ignore[arg-type]
    assert math.isclose(actual, expected, rel_tol=1e-12)


# --------------------------------------------------------------------------- #
# 5. Source-level regressions                                                 #
# --------------------------------------------------------------------------- #


def test_source_does_not_contain_arithmetic_mean_blend() -> None:
    """DEC-003 / CRule 3: arithmetic-mean blend (a + (1-b)) / 2 forbidden."""
    src = Path("src/pricing/round_types.py").read_text(encoding="utf-8")
    code_lines = [
        line for line in src.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    code = "\n".join(code_lines)
    assert "(a_rate + (1.0 - b_rate)) / 2" not in code
    assert "(a_rate + (1 - b_rate)) / 2" not in code
    assert "(a + (1 - b)) / 2" not in code


def test_source_uses_type_checking_guard_for_circular_imports() -> None:
    """RESEARCH Architectural Map: round_types.py must NOT import live_theo /
    dp at runtime — use TYPE_CHECKING guard.

    NOTE (01-05 Rule 3 deviation): MatchState lives in src/pricing/data.py per
    D-14. The original 01-03 test hard-coded the live_theo path before D-14
    landed; updated here to match the canonical placement. dp.py and
    live_theo.py both import data.py at runtime safely (data.py has zero
    intra-package deps).
    """
    src = Path("src/pricing/round_types.py").read_text(encoding="utf-8")
    assert "if TYPE_CHECKING:" in src
    # The MatchState type-only import must be inside the guard block.
    assert "from src.pricing.data import MatchState" in src
    type_checking_idx = src.find("if TYPE_CHECKING:")
    matchstate_idx = src.find("from src.pricing.data import MatchState")
    assert type_checking_idx < matchstate_idx, (
        "MatchState import must be inside TYPE_CHECKING block"
    )
