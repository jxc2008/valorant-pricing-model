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

from typing import TYPE_CHECKING, Any, Protocol

from src.config.constants import GUN_WIN_RATE
from src.pricing import blend

if TYPE_CHECKING:
    # Type-only imports avoid runtime circular dependency. live_theo.py and
    # dp.py both import from this module via runtime; we only need their types.
    # MatchState lives in src/state/match_state.py (Phase 3 D-01 / plan 03-01).
    # The original 01-03 plan referenced live_theo.py before D-14 was added;
    # Phase 1 D-14 moved it to src/pricing/data.py and Phase 3 D-01 then moved
    # it to its long-term home in src/state/match_state.py.
    from src.pricing.dp import BO3State
    from src.state.match_state import MatchState


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
    (team -> league -> overall). Tests construct fake objects satisfying this
    Protocol.
    """

    def team(self, team: str, map_name: str, side: str) -> float:
        """Bayesian-shrunk win-rate for ``team`` on ``map_name`` while playing ``side``."""
        ...

    def team_entry(
        self, team: str, map_name: str, side: str
    ) -> dict[str, Any] | None:
        """Raw entry (n, rate, used_fallback) — powers data_weight in live_theo."""
        ...


# --------------------------------------------------------------------------- #
# 2. Side-derivation helpers                                                  #
# --------------------------------------------------------------------------- #
# Source: reference/theo_engine.py:158 — verbatim per DEC-013.


def _team_a_side(side_orient: str) -> str:
    """Strip the 'a_' prefix: side_orient='a_atk' -> 'atk', 'a_def' -> 'def'."""
    return "atk" if side_orient == "a_atk" else "def"


def _team_b_side(side_orient: str) -> str:
    """Team B plays the opposite side from team A this half."""
    return "def" if side_orient == "a_atk" else "atk"


# --------------------------------------------------------------------------- #
# 3. Public dispatch                                                          #
# --------------------------------------------------------------------------- #


def round_p_for_round(
    state: BO3State,
    match_state: MatchState,
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
