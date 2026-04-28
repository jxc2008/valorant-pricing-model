---
phase: 01-core-pricing-engine
plan: 03
type: execute
wave: 2
depends_on:
  - 01-01-constants-and-blend
files_modified:
  - src/pricing/round_types.py
  - tests/pricing/test_round_types.py
autonomous: true
requirements:
  - REQ-pistol-anti-eco-modeling
must_haves:
  truths:
    - "Bradley-Terry blend, not arithmetic mean (DEC-003 / CRule 3)"
    - "Conviction clip [0.01, 0.99] uniform (DEC-012 / CRule 6)"
    - "No magic numbers — every threshold in src/config/constants.py (CON-no-magic-numbers / CRule 12)"
    - "mypy --strict on src/pricing/ (CON-mypy-strict-pricing / CRule 11)"
    - "Single canonical entry point: live_theo(state) → TheoOutput (DEC-010 / CRule 1)"
    - "Pistol + anti-eco modeled explicitly for rounds {1, 2, 3, 13, 14, 15} using GUN_WIN_RATE=0.822 (DEC-011 / CRule 4)"
    - "round_types.py imports blend.round_p — never inlines arithmetic-mean form (DEC-003)"
    - "round_types.py never imports dp.py at runtime — the round_p_fn injection seam keeps dp pure (RESEARCH §Architectural Map)"
  outputs:
    - "src/pricing/round_types.py exports `round_p_for_round(state: BO3State, match_state: MatchState, half_rates: HalfRates) -> float`"
    - "Round dispatch: rounds {1, 13} → pistol (uses half_rates blend in Phase 1 per A8); {2, 3, 14, 15} → anti-eco (GUN_WIN_RATE if A won pistol, 1-GUN_WIN_RATE if B); {4-12, 16-24} → gunround (half_rates blend)"
    - "Defensive fallthrough: if pistol_winner_a[map_idx] is None for round 2/3/14/15 → return 0.5"
    - "HalfRates protocol: `class HalfRates(Protocol)` with `team(team: str, map_name: str, side: str) -> float` and `team_entry(team: str, map_name: str, side: str) -> Optional[dict[str, Any]]` — concrete impl ships in 01-05/live_theo.py"
    - "_team_a_side / _team_b_side helpers: opposite-side derivation per reference/theo_engine.py:158 pattern"
    - "tests/pricing/test_round_types.py: parametrized dispatch tests for rounds {1, 2, 3, 4, 12, 13, 14, 15, 16, 24} + None-pistol fallthrough + GUN_WIN_RATE wiring + side-flip helper tests"
    - "`uv run mypy --strict src/pricing/round_types.py` exits 0"
    - "`uv run pytest tests/pricing/test_round_types.py -x` exits 0"
    - "`uv run ruff check src/pricing/round_types.py tests/pricing/test_round_types.py` exits 0"
---

<rationale>
Wave 2 (depends on 01-01 for `GUN_WIN_RATE` from constants — already in Phase 0 — and `blend.round_p` from 01-01). Runs in parallel with 01-02 (DP engine) — `round_types.py` imports `blend.py` and `dp.BO3State` (type-only via `if TYPE_CHECKING:` to avoid circular), but does NOT import `dp.py` at runtime. The architectural seam: `round_types.round_p_for_round` IS the closure body that `live_theo.py` wraps and passes to `dp.series_value` via `round_p_fn` injection (01-05).

**Why split from DP (01-02):** Pure dispatch logic with no recursion or caching concerns. Different mental model. Different test surface (parametrized table-driven dispatch tests, not hypothesis property tests). Wave 2 parallelism: an executor can ship 01-02 while another ships 01-03 with zero shared file mutation.

**HalfRates as Protocol (not concrete dataclass):** The concrete `HalfRates` implementation reads `data/half_win_rates.json` and lives in `live_theo.py` (RESEARCH §Open Question 2). `round_types.py` only uses it via duck-typed Protocol — keeps the dispatch module pure and decouples it from the JSON-loading concern. Tests pass a fake object satisfying the Protocol.
</rationale>

<objective>
Implement the pistol/anti-eco/gunround round-type dispatch in `src/pricing/round_types.py`. This is the round-number-aware resolver for `round_p` that fixes audit bug #5 (PRD §12.2 #5 / DEC-011): the audit engine used a constant `p1` for rounds 1-12 and `p2` for rounds 13-24, ignoring the empirically large pistol-and-anti-eco effects. The new dispatch routes:
- Rounds {1, 13} (pistols) → half-rates blend (Phase 1 fallback per A8 — Phase 2 will calibrate per-team pistol-only rates)
- Rounds {2, 3, 14, 15} (post-pistol anti-eco) → `GUN_WIN_RATE` (0.822) for the pistol winner's side; `1 - GUN_WIN_RATE` (0.178) for the loser's side
- Rounds {4-12, 16-24} (gunround baseline) → half-rates blend

Purpose: Implement DEC-011 "single largest accuracy gain" per roadmap §1.3. The structurally-correct dispatch ships in Phase 1 even though pistol-only rates are deferred to Phase 2 calibration — this lets Phase 2 swap in calibrated rates without changing call sites.

Output: `round_p_for_round` public function, `HalfRates` Protocol, side-derivation helpers, full parametrized test suite covering all six round-type buckets and the None-pistol fallthrough.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@.planning/phases/01-core-pricing-engine/01-CONTEXT.md
@.planning/phases/01-core-pricing-engine/01-RESEARCH.md
@.planning/phases/01-core-pricing-engine/01-PATTERNS.md
@.planning/phases/01-core-pricing-engine/01-01-constants-and-blend-SUMMARY.md
@CLAUDE.md
@prd.md
@roadmap.md
@src/config/constants.py
@src/pricing/blend.py
@reference/theo_engine.py

<interfaces>
<!-- All code skeletons from RESEARCH §4 and PATTERNS lines 100-163 — ship verbatim. -->

From src/config/constants.py:
```python
GUN_WIN_RATE: Final[float] = 0.822
"""Population mean P(team with rifles wins an eco round). DEC-011."""
```

From src/pricing/blend.py (01-01 output):
```python
def round_p(a_rate: float, b_rate_opposite_side: float) -> float:
    """Bradley-Terry blend with BT_BLEND_EPSILON input clip."""
```

From src/pricing/dp.py (01-02 output — type-only import):
```python
@dataclass(frozen=True, slots=True)
class BO3State:
    map_idx: int; a_map_score: int; b_map_score: int
    a_round: int; b_round: int
    side_orient: str  # 'a_atk' | 'a_def'
    map_pool: tuple[str, ...]
    pistol_winner_a: tuple[Optional[bool], ...]
```

The dispatch (RESEARCH §4, lines 609-644 — ship verbatim with HalfRates Protocol abstraction):
```python
def round_p_for_round(
    state: BO3State,
    match_state: MatchState,
    half_rates: HalfRates,
) -> float:
    round_num = state.a_round + state.b_round + 1  # 1-indexed
    map_name = state.map_pool[state.map_idx]
    side = state.side_orient

    if round_num == 1 or round_num == 13:
        # Pistol — Phase 1 fallback to half_rates per A8 (Phase 2 calibrates).
        a_rate = half_rates.team(match_state.team_a, map_name, _team_a_side(side))
        b_rate = half_rates.team(match_state.team_b, map_name, _team_b_side(side))
        return blend.round_p(a_rate, b_rate)

    if round_num in (2, 3, 14, 15):
        pistol_won_by_a = state.pistol_winner_a[state.map_idx]
        if pistol_won_by_a is None:
            return 0.5  # defensive
        return GUN_WIN_RATE if pistol_won_by_a else 1.0 - GUN_WIN_RATE

    # Gunround baseline (4-12, 16-24)
    a_rate = half_rates.team(match_state.team_a, map_name, _team_a_side(side))
    b_rate = half_rates.team(match_state.team_b, map_name, _team_b_side(side))
    return blend.round_p(a_rate, b_rate)
```

Side-derivation pattern (reference/theo_engine.py:158):
```python
def _team_a_side(side_orient: str) -> str:
    """Team A's side this half. Strips 'a_' prefix from side_orient."""
    return "atk" if side_orient == "a_atk" else "def"

def _team_b_side(side_orient: str) -> str:
    """Team B plays the opposite side from team A."""
    return "def" if side_orient == "a_atk" else "atk"
```

MatchState forward declaration (the Phase 1 stub lives in live_theo.py — 01-05 — but we need its type signature for round_types.py NOW):
```python
# In round_types.py — type-only import to avoid circular imports.
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.pricing.live_theo import MatchState  # populated in 01-05
```
The runtime contract `round_types.py` requires from MatchState: attributes `team_a: str` and `team_b: str`. Phase 1 stub MatchState (01-05) MUST provide these. Tests use a `@dataclass` fake satisfying this contract.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Implement src/pricing/round_types.py with parametrized round-type dispatch + tests</name>
  <files>src/pricing/round_types.py, tests/pricing/test_round_types.py</files>

  <read_first>
    - src/pricing/blend.py (01-01 output — verify `round_p` signature)
    - src/config/constants.py (verify GUN_WIN_RATE=0.822)
    - .planning/phases/01-core-pricing-engine/01-RESEARCH.md §4 "Pistol/anti-eco round-type model" (lines 603-656)
    - .planning/phases/01-core-pricing-engine/01-PATTERNS.md "src/pricing/round_types.py (math, new)" section (lines 98-163) and "tests/pricing/test_round_types.py (test, new)" section (lines 656-693)
    - .planning/phases/01-core-pricing-engine/01-CONTEXT.md D-04 (rounds {1,2,3,13,14,15} only — others use gunround baseline)
    - reference/theo_engine.py:146-162 — `_round_win_prob` — DROP the arithmetic-mean form on line 161; SALVAGE the `team_b_side` derivation pattern on line 158
    - prd.md §12.2 #5 (the constant-p1/p2 bug being fixed; DEC-011 fix)
    - roadmap.md §1.3 (round-type dispatch table)
    - CLAUDE.md Critical Rule 4 (pistol + anti-eco modeled explicitly)
  </read_first>

  <behavior>
    - Test 1 (round 1, pistol): `round_p_for_round(state with a_round=0, b_round=0, ...)` calls `blend.round_p(half_rates.team(team_a, map, atk), half_rates.team(team_b, map, def))`. Verify by checking the returned value matches `blend.round_p(0.55, 0.50) ≈ 0.55*0.5 / (0.55*0.5 + 0.45*0.50)`.
    - Test 2 (round 2, A won pistol): returns exactly `GUN_WIN_RATE` (0.822)
    - Test 3 (round 2, B won pistol): returns exactly `1 - GUN_WIN_RATE` (0.178)
    - Test 4 (round 3, A won pistol): returns `GUN_WIN_RATE` (Phase 1 simplification per A6 — rounds 3/15 use same as 2/14)
    - Test 5 (round 13, pistol — second-half pistol): same as round 1 but with side flipped. Verify by asserting `round_p_for_round` calls `half_rates.team(team_a, map, def)` (since side_orient='a_def' on round 13)
    - Test 6 (round 14, A won pistol of map 0, second-half): returns `GUN_WIN_RATE` (uses pistol_winner_a[map_idx] regardless of which half)
    - Test 7 (round 4, gunround): calls `blend.round_p` — verify same behavior as round 1 EXCEPT not gated on pistol_winner_a
    - Test 8 (round 12, gunround): calls `blend.round_p`
    - Test 9 (round 16, second-half gunround): calls `blend.round_p` with flipped side
    - Test 10 (round 24, last gunround before OT): calls `blend.round_p`
    - Test 11 (None-pistol fallthrough): round 2 with `pistol_winner_a[map_idx] = None` returns exactly 0.5
    - Test 12 (side-flip helpers): `_team_a_side('a_atk') == 'atk'`, `_team_a_side('a_def') == 'def'`, `_team_b_side('a_atk') == 'def'`, `_team_b_side('a_def') == 'atk'`
    - Test 13 (regression — no arithmetic mean): source does NOT contain `(a_rate + (1.0 - b_rate)) / 2` or similar (DEC-003)
    - Test 14 (regression — no DP runtime import): source contains `if TYPE_CHECKING:` guard around `from src.pricing.live_theo import MatchState` (avoids circular import; PATTERNS line 119)
  </behavior>

  <action>
Create `src/pricing/round_types.py`:

```python
"""Pistol / anti-eco / gunround round-type dispatch.

Resolves P(team A wins this round) per round number, conditional on
``state.pistol_winner_a[map_idx]`` for rounds 2, 3, 14, 15. Implements DEC-011
(rounds {1, 2, 3, 13, 14, 15} are pistol-or-anti-eco; others use the
gunround baseline).

Architectural seam
------------------
``round_p_for_round`` IS the function body that ``live_theo.py`` wraps in a
closure and passes to ``dp.series_value`` via the ``round_p_fn`` injection
point. This module does NOT import ``dp.py`` at runtime — it consumes
``BO3State`` only via the type-only import below. This keeps ``dp.py`` a pure
DP recursion with no domain awareness (RESEARCH Architectural Responsibility
Map; CON-bo3-dp-signature).

Phase 1 simplification (A8 in RESEARCH Assumptions Log)
-------------------------------------------------------
Rounds 1, 13 (pistols) fall back to the half-rates Bradley-Terry blend in
Phase 1 — the same input as gunrounds. Phase 2 (REQ-round-event-data-pipeline)
will calibrate per-team pistol-only rates from ``match_round_data`` and swap
them in WITHOUT changing this call shape. The structural dispatch is what
matters; the rate value defers.

Phase 1 simplification (A6)
---------------------------
Rounds 3 and 15 use the same ``GUN_WIN_RATE`` model as rounds 2 and 14.
Roadmap §1.3 notes empirical rate is ~60% on round 3 vs ~75% on round 2;
Phase 2 calibration may differentiate. Phase 1 ships the structurally-correct
dispatch.

Sources
-------
- DEC-011 / CLAUDE.md rule 4 / CON-pistol-anti-eco
- prd.md §12.2 #5 (the constant-p1/p2 audit bug being fixed)
- roadmap.md §1.3 (round-type dispatch table)
- 01-RESEARCH.md §4 (concrete signatures + Phase 1 simplifications)
- reference/theo_engine.py:158 (team_b_side derivation pattern — salvage with attribution)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional, Protocol

from src.config.constants import GUN_WIN_RATE
from src.pricing import blend

if TYPE_CHECKING:
    # Type-only imports avoid runtime circular dependency. live_theo.py and
    # dp.py both import from this module via runtime; we only need their types.
    from src.pricing.dp import BO3State
    from src.pricing.live_theo import MatchState


# --------------------------------------------------------------------------- #
# 1. HalfRates Protocol                                                       #
# --------------------------------------------------------------------------- #
# The concrete HalfRates implementation lives in live_theo.py (it loads
# data/half_win_rates.json). round_types.py only requires the duck-typed
# interface below.


class HalfRates(Protocol):
    """Read-only interface to per-team-map-side win rates.

    The concrete implementation is in src/pricing/live_theo.py (Phase 1 stub).
    Loads data/half_win_rates.json and applies the audit-engine fallback chain
    (team → league → overall). Tests construct fake objects satisfying this
    Protocol.
    """

    def team(self, team: str, map_name: str, side: str) -> float:
        """Bayesian-shrunk win-rate for ``team`` on ``map_name`` while playing ``side``."""
        ...

    def team_entry(
        self, team: str, map_name: str, side: str
    ) -> Optional[dict[str, Any]]:
        """Raw entry (n, rate, used_fallback) — powers data_weight in live_theo."""
        ...


# --------------------------------------------------------------------------- #
# 2. Side-derivation helpers                                                  #
# --------------------------------------------------------------------------- #
# Source: reference/theo_engine.py:158 — verbatim per DEC-013.


def _team_a_side(side_orient: str) -> str:
    """Strip the 'a_' prefix: side_orient='a_atk' → 'atk', 'a_def' → 'def'."""
    return "atk" if side_orient == "a_atk" else "def"


def _team_b_side(side_orient: str) -> str:
    """Team B plays the opposite side from team A this half."""
    return "def" if side_orient == "a_atk" else "atk"


# --------------------------------------------------------------------------- #
# 3. Public dispatch                                                          #
# --------------------------------------------------------------------------- #


def round_p_for_round(
    state: "BO3State",
    match_state: "MatchState",
    half_rates: HalfRates,
) -> float:
    """Resolve P(team A wins the round about to start in ``state``).

    Dispatches by 1-indexed round number:
      - 1, 13: pistol — Phase 1 falls back to half_rates blend (A8).
      - 2, 3, 14, 15: anti-eco — GUN_WIN_RATE if A won pistol, else 1 - GUN_WIN_RATE.
      - 4-12, 16-24: gunround — half_rates Bradley-Terry blend.

    Args:
        state: Current BO3State (provides round counts, side_orient, map_idx,
            pistol_winner_a). The ``round`` about to start is round number
            ``state.a_round + state.b_round + 1`` (1-indexed).
        match_state: Phase 1 stub MatchState — provides ``team_a``, ``team_b``.
            Phase 3 will replace MatchState with the full ingestion-driven
            version (REQ-match-state-engine) without changing this contract.
        half_rates: Protocol-typed half-win-rates source. Concrete impl ships
            in live_theo.py.

    Returns:
        Float in ``(0.0, 1.0)`` (output of blend.round_p, with input clip
        already applied) for pistol/gunround paths, OR exactly ``GUN_WIN_RATE``
        (0.822) / ``1 - GUN_WIN_RATE`` (0.178) for anti-eco paths, OR exactly
        ``0.5`` for the defensive None-pistol fallthrough.
    """
    round_num = state.a_round + state.b_round + 1  # 1-indexed
    map_name = state.map_pool[state.map_idx]
    side = state.side_orient

    if round_num == 1 or round_num == 13:
        # Pistol — Phase 1 fallback to half_rates (A8).
        a_rate = half_rates.team(match_state.team_a, map_name, _team_a_side(side))
        b_rate = half_rates.team(match_state.team_b, map_name, _team_b_side(side))
        return blend.round_p(a_rate, b_rate)

    if round_num in (2, 3, 14, 15):
        pistol_won_by_a = state.pistol_winner_a[state.map_idx]
        if pistol_won_by_a is None:
            # Defensive — round 2 implies round 1 is settled, so this shouldn't
            # happen in well-formed states. Returning 0.5 keeps the DP value in
            # range while flagging the malformed input through the test suite.
            return 0.5
        return GUN_WIN_RATE if pistol_won_by_a else 1.0 - GUN_WIN_RATE

    # Gunround baseline (rounds 4-12, 16-24).
    a_rate = half_rates.team(match_state.team_a, map_name, _team_a_side(side))
    b_rate = half_rates.team(match_state.team_b, map_name, _team_b_side(side))
    return blend.round_p(a_rate, b_rate)
```

Then create `tests/pricing/test_round_types.py`:

```python
"""Tests for src.pricing.round_types — REQ-pistol-anti-eco-modeling.

Verifies:
  - Round-num dispatch correctly routes to pistol / anti-eco / gunround paths.
  - GUN_WIN_RATE wired correctly: rounds 2/3/14/15 return 0.822 (or 0.178).
  - pistol_winner_a fall-through (None pre-pistol → defensive 0.5).
  - Side-derivation helpers (_team_a_side, _team_b_side) are correct.
  - Source does not contain the audit-engine arithmetic-mean blend (DEC-003).
  - Source uses TYPE_CHECKING-guarded import for MatchState (avoids circular).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import pytest

from src.config.constants import GUN_WIN_RATE
from src.pricing import blend
from src.pricing.dp import BO3State
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
    ) -> Optional[dict[str, Any]]:
        return None


def _state(
    a_round: int = 0,
    b_round: int = 0,
    side_orient: str = "a_atk",
    pistol_winner_a: tuple[Optional[bool], ...] = (None, None, None),
) -> BO3State:
    return BO3State(
        map_idx=0,
        a_map_score=0,
        b_map_score=0,
        a_round=a_round,
        b_round=b_round,
        side_orient=side_orient,
        map_pool=("Lotus", "Bind", "Haven"),
        pistol_winner_a=pistol_winner_a,
    )


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
    actual = round_p_for_round(state, _FakeMatchState(), half_rates)
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
    actual = round_p_for_round(state, _FakeMatchState(), half_rates)
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
    actual = round_p_for_round(state, _FakeMatchState(), _FakeHalfRates())
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
    actual = round_p_for_round(state, _FakeMatchState(), _FakeHalfRates())
    assert math.isclose(actual, 1.0 - GUN_WIN_RATE, rel_tol=1e-12)


def test_anti_eco_with_none_pistol_winner_returns_defensive_05() -> None:
    """Defensive: round 2 with pistol_winner_a=None → 0.5 (shouldn't happen in
    well-formed states, but covered for robustness)."""
    state = _state(
        a_round=1,
        b_round=0,
        pistol_winner_a=(None, None, None),
    )
    actual = round_p_for_round(state, _FakeMatchState(), _FakeHalfRates())
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
    actual = round_p_for_round(state, _FakeMatchState(), half_rates)
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
    """
    src = Path("src/pricing/round_types.py").read_text(encoding="utf-8")
    assert "if TYPE_CHECKING:" in src
    # Both type-only imports must be inside the guard block (or absent at runtime)
    assert "from src.pricing.live_theo import MatchState" in src
    # The import statement should appear AFTER `if TYPE_CHECKING:` line:
    type_checking_idx = src.find("if TYPE_CHECKING:")
    matchstate_idx = src.find("from src.pricing.live_theo import MatchState")
    assert type_checking_idx < matchstate_idx, (
        "MatchState import must be inside TYPE_CHECKING block"
    )
```

Commit with message `feat(01-03): implement pistol/anti-eco round-type dispatch + tests`.
  </action>

  <verify>
    <automated>uv run mypy --strict src/pricing/round_types.py &amp;&amp; uv run pytest tests/pricing/test_round_types.py -x &amp;&amp; uv run ruff check src/pricing/round_types.py tests/pricing/test_round_types.py</automated>
  </verify>

  <acceptance_criteria>
    - `test -f src/pricing/round_types.py`
    - `grep -q "def round_p_for_round(" src/pricing/round_types.py`
    - `grep -q "class HalfRates(Protocol):" src/pricing/round_types.py`
    - `grep -q "if TYPE_CHECKING:" src/pricing/round_types.py`
    - `grep -q "from src.pricing.live_theo import MatchState" src/pricing/round_types.py` (under TYPE_CHECKING)
    - `grep -q "GUN_WIN_RATE if pistol_won_by_a else 1.0 - GUN_WIN_RATE" src/pricing/round_types.py`
    - `grep -q "round_num == 1 or round_num == 13" src/pricing/round_types.py`
    - `grep -q "round_num in (2, 3, 14, 15)" src/pricing/round_types.py`
    - `grep -qE "blend\.round_p\(" src/pricing/round_types.py` (consumes blend module — DEC-003)
    - Comment-stripped: `! (grep -v "^[[:space:]]*#" src/pricing/round_types.py | grep -E "\(a_rate \+ \(1\.0? - b_rate\)\) / 2")` (no arithmetic mean)
    - `test -f tests/pricing/test_round_types.py`
    - `grep -q "test_round_1_pistol_uses_half_rates_blend" tests/pricing/test_round_types.py`
    - `grep -q "test_round_13_pistol_uses_flipped_side" tests/pricing/test_round_types.py`
    - `grep -q "test_anti_eco_returns_gun_win_rate_when_a_won_pistol" tests/pricing/test_round_types.py`
    - `grep -q "test_anti_eco_returns_complement_when_b_won_pistol" tests/pricing/test_round_types.py`
    - `grep -q "test_anti_eco_with_none_pistol_winner_returns_defensive_05" tests/pricing/test_round_types.py`
    - `grep -q "test_gunround_uses_half_rates_blend" tests/pricing/test_round_types.py`
    - `grep -q "test_side_derivation" tests/pricing/test_round_types.py`
    - `uv run mypy --strict src/pricing/round_types.py` exits 0
    - `uv run pytest tests/pricing/test_round_types.py -x` exits 0 (≥ 14 tests pass — 2 side-derivation parametrize cases + 1 round-1 + 1 round-13 + 4 anti-eco-gun + 4 anti-eco-complement + 1 None fallthrough + 4 gunround parametrize + 2 source regressions)
    - `uv run ruff check src/pricing/round_types.py tests/pricing/test_round_types.py` exits 0
  </acceptance_criteria>

  <done>
    `src/pricing/round_types.py` exports `round_p_for_round`, `HalfRates` Protocol, `_team_a_side`, `_team_b_side`. All round buckets correctly dispatched: rounds {1, 13} → half-rates blend (A8 fallback); {2, 3, 14, 15} → GUN_WIN_RATE/complement; {4-12, 16-24} → half-rates blend; None-pistol fallthrough → 0.5. No arithmetic-mean form in source (DEC-003 regression-locked). TYPE_CHECKING guard present (no runtime circular import). All ≥ 14 tests pass under `mypy --strict`.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| `round_p_for_round` ↔ caller (live_theo.py closure) | Caller supplies BO3State, MatchState, HalfRates. Invariants: `pistol_winner_a` length matches `map_pool`; `side_orient ∈ {'a_atk', 'a_def'}`; `team_a`/`team_b` are non-empty strings. Caller is responsible. |
| HalfRates Protocol ↔ concrete impl | Protocol-typed at compile time; runtime correctness relies on the concrete impl in live_theo.py (01-05) — covered by that plan's threat model. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-01-03-01 | Tampering | `round_p_for_round` (regression to arithmetic-mean blend) | mitigate | `test_source_does_not_contain_arithmetic_mean_blend` regression-locks; the only blend call site is `blend.round_p` (which itself uses BT) |
| T-01-03-02 | Tampering | Pistol-winner None passed to anti-eco round | mitigate | Defensive `if pistol_won_by_a is None: return 0.5` covered by `test_anti_eco_with_none_pistol_winner_returns_defensive_05` |
| T-01-03-03 | Tampering | Wrong side passed to half_rates (atk/def confusion across map boundary) | mitigate | `_team_a_side` / `_team_b_side` helpers; `test_side_derivation` parametrize over both side_orient values; round-13 test verifies post-half-flip side wiring |
| T-01-03-04 | Tampering | Round-number off-by-one (1-indexed vs 0-indexed) | mitigate | Source uses `state.a_round + state.b_round + 1` explicitly with comment `# 1-indexed`; tests cover round 1 (a=0,b=0), round 13 (a=12,b=0), round 24 (a=15,b=8) — all three boundaries |
| T-01-03-05 | DoS | Circular import between round_types.py / dp.py / live_theo.py at runtime | mitigate | TYPE_CHECKING guard; `test_source_uses_type_checking_guard_for_circular_imports` regression-locks |
</threat_model>

<verification>
After Task 1 completes:

```bash
uv run mypy --strict src/pricing/round_types.py
uv run pytest tests/pricing/test_round_types.py -x -v
uv run ruff check src/pricing/round_types.py tests/pricing/test_round_types.py
```

All MUST exit 0. Test count: ≥ 14 tests, all pass.

Sanity check (manual):
```bash
uv run python -c "
from src.pricing.dp import BO3State
from src.pricing.round_types import round_p_for_round

class FakeMS:
    team_a, team_b = 'A', 'B'

class FakeHR:
    def team(self, team, map_name, side): return 0.55 if team == 'A' else 0.45
    def team_entry(self, *a): return None

s = BO3State(0, 0, 0, 1, 0, 'a_atk', ('Lotus','Bind','Haven'), (True, None, None))
print('round 2 (A won pistol):', round_p_for_round(s, FakeMS(), FakeHR()))
# Expected: 0.822
"
```
Expected output: `round 2 (A won pistol): 0.822`
</verification>

<success_criteria>
- `round_p_for_round(state, match_state, half_rates)` correctly dispatches all six round-type buckets per DEC-011
- Anti-eco rounds (2, 3, 14, 15) return EXACTLY `GUN_WIN_RATE` or `1 - GUN_WIN_RATE` based on `pistol_winner_a[map_idx]`
- Pistol rounds (1, 13) call `blend.round_p` with correct atk/def side wiring (Phase 1 simplification — Phase 2 calibrates)
- Gunrounds (4-12, 16-24) call `blend.round_p` with correct sides; ignore `pistol_winner_a`
- None-pistol fallthrough returns 0.5 defensively
- `_team_a_side` / `_team_b_side` helpers correctly derive sides from `side_orient`
- TYPE_CHECKING guard prevents runtime circular imports with live_theo and dp
- No arithmetic-mean blend form in source (DEC-003 regression-locked)
- `mypy --strict`, `pytest`, `ruff` all green
- All Phase 0 + 01-01 + 01-02 tests still pass (no regression)
</success_criteria>

<output>
After completion, create `.planning/phases/01-core-pricing-engine/01-03-round-types-SUMMARY.md`.

The SUMMARY must record:
- The full dispatch table as shipped (rounds 1/13 path, 2/3/14/15 path, 4-12/16-24 path)
- Phase 1 simplifications taken (A6: rounds 3/15 = rounds 2/14; A8: pistol fallback to half_rates)
- HalfRates Protocol surface (two methods: `team`, `team_entry`)
- Test count: ≥ 14 tests across 5 test classes (side helpers / pistol / anti-eco / gunround / source regression)
- Confirmation that round_types.py does NOT import dp.py or live_theo.py at runtime (verified via grep)
- Commit SHA for the single atomic commit
</output>
