"""RED tests for scripts.probe_round_events.side_for_team_a (Pitfall 3).

Sides flip at round 13 (start of second half). Mis-mapping bit-flips every
calibration row's `side` field → garbage cells.

Sources
-------
- 02-RESEARCH.md §"Pitfall 3: attackingTeamNumber ambiguity for side"
"""

from __future__ import annotations

import pytest

probe_mod = pytest.importorskip(
    "scripts.probe_round_events",
    reason="Awaiting Plan 02-03 — scripts/probe_round_events.py",
)


@pytest.mark.parametrize(
    "round_num,attacking_first_team_num,team_a_team_num,expected",
    [
        # Team 1 attacks first; team A is team 1 → A attacks rounds 1-12
        (1, 1, 1, "atk"),
        (5, 1, 1, "atk"),
        (12, 1, 1, "atk"),
        # Half flip: rounds 13-24 swap sides
        (13, 1, 1, "def"),
        (18, 1, 1, "def"),
        (24, 1, 1, "def"),
        # Team B perspective: team A is team 2 → A defends first half
        (1, 1, 2, "def"),
        (12, 1, 2, "def"),
        (13, 1, 2, "atk"),
        (24, 1, 2, "atk"),
        # Team 2 attacks first; team A is team 1 → A defends first half
        (1, 2, 1, "def"),
        (12, 2, 1, "def"),
        (13, 2, 1, "atk"),
        (24, 2, 1, "atk"),
    ],
)
def test_side_for_team_a_half_flips_at_round_13(
    round_num: int,
    attacking_first_team_num: int,
    team_a_team_num: int,
    expected: str,
) -> None:
    result = probe_mod.side_for_team_a(
        round_num=round_num,
        attacking_first_team_num=attacking_first_team_num,
        team_a_team_num=team_a_team_num,
    )
    assert result == expected
