"""RED tests for scripts.probe_round_events.synthesize_mid_round_states.

These tests SKIP until Plan 02-03 ships scripts/probe_round_events.py. When it
ships, they activate automatically and pin the D-06 / D-08 / Pitfall 4 contract.

Sources
-------
- 02-RESEARCH.md §"Pattern 2: mid_round_states[] synthesis from events[]"
- D-06 (hybrid event + 5s heartbeat)
- D-08 (carry-forward numerical_diff between events)
- Pitfall 4 (defuse → bomb_planted=False, terminate states)
- src/config/constants.MID_ROUND_HEARTBEAT_S = 5.0 (Plan 02-01)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

# Skip-gate: until Plan 02-03 ships the module these tests SKIP cleanly.
synth_mod = pytest.importorskip(
    "scripts.probe_round_events",
    reason="Awaiting Plan 02-03 — scripts/probe_round_events.py",
)

FIXTURE_DIR: Path = Path(__file__).parent.parent / "probe" / "fixtures"


def _round_events(round_num: int) -> list[dict[str, Any]]:
    data: dict[str, Any] = json.loads(
        (FIXTURE_DIR / "match_details.json").read_text(encoding="utf-8")
    )
    return [e for e in data["events"] if e["roundNumber"] == round_num]


def _round_loadouts(round_num: int) -> dict[int, int]:
    data: dict[str, Any] = json.loads(
        (FIXTURE_DIR / "match_details.json").read_text(encoding="utf-8")
    )
    return {
        e["playerId"]: e["loadoutValue"]
        for e in data["economies"]
        if e["roundNumber"] == round_num
    }


TEAM_A: set[int] = {101, 102, 103, 104, 105}
TEAM_B: set[int] = {201, 202, 203, 204, 205}


def test_round_1_defuse_terminates_states_at_defuse_t_offset() -> None:
    """Pitfall 4: defuse is the round terminator for defenders.

    Round 1 in the fixture is start → kill → plant → defuse @ 38000ms. The
    final emitted state must be at t_offset=38.0 with bomb_planted=False (defuse
    reversed the plant). NO states emitted past 38.0s.
    """
    states = synth_mod.synthesize_mid_round_states(
        round_events=_round_events(1),
        round_team_a_players=TEAM_A,
        round_team_b_players=TEAM_B,
        round_loadouts=_round_loadouts(1),
        side_a_this_round="atk",
        map_name="Lotus",
    )
    last = states[-1]
    assert last["t_offset"] == pytest.approx(38.0)
    assert last["bomb_planted"] is False
    # No states past the defuse
    assert all(s["t_offset"] <= 38.0 for s in states)


def test_round_2_plant_remains_planted_through_round_end() -> None:
    """Round 2: plant @ 28s, no defuse — bomb_planted=True for all states t >= 28."""
    states = synth_mod.synthesize_mid_round_states(
        round_events=_round_events(2),
        round_team_a_players=TEAM_A,
        round_team_b_players=TEAM_B,
        round_loadouts=_round_loadouts(2),
        side_a_this_round="atk",
        map_name="Lotus",
    )
    post_plant = [s for s in states if s["t_offset"] >= 28.0]
    assert len(post_plant) >= 1
    assert all(s["bomb_planted"] is True for s in post_plant)


def test_round_3_no_plant_keeps_bomb_false_throughout() -> None:
    """Round 3: 5 sequential kills, no plant — every state has bomb_planted=False."""
    states = synth_mod.synthesize_mid_round_states(
        round_events=_round_events(3),
        round_team_a_players=TEAM_A,
        round_team_b_players=TEAM_B,
        round_loadouts=_round_loadouts(3),
        side_a_this_round="atk",
        map_name="Lotus",
    )
    assert all(s["bomb_planted"] is False for s in states)


def test_heartbeat_cadence_matches_constant() -> None:
    """D-06: heartbeats at multiples of MID_ROUND_HEARTBEAT_S between events."""
    from src.config.constants import MID_ROUND_HEARTBEAT_S

    states = synth_mod.synthesize_mid_round_states(
        round_events=_round_events(2),
        round_team_a_players=TEAM_A,
        round_team_b_players=TEAM_B,
        round_loadouts=_round_loadouts(2),
        side_a_this_round="atk",
        map_name="Lotus",
    )
    # At least one heartbeat at t=0 and one at t=MID_ROUND_HEARTBEAT_S
    heartbeat_offsets = sorted(s["t_offset"] for s in states if s["kind"] == "heartbeat")
    assert 0.0 in heartbeat_offsets
    assert MID_ROUND_HEARTBEAT_S in heartbeat_offsets


def test_carry_forward_numerical_diff_between_events() -> None:
    """D-08: numerical_diff carried forward from most recent event into heartbeats.

    Round 2 has kill at 8.5s (A advantage +1) then kill at 14.2s (A advantage +2).
    A heartbeat at 10s should carry numerical_diff=+1 (carry-forward from t=8.5s).
    """
    states = synth_mod.synthesize_mid_round_states(
        round_events=_round_events(2),
        round_team_a_players=TEAM_A,
        round_team_b_players=TEAM_B,
        round_loadouts=_round_loadouts(2),
        side_a_this_round="atk",
        map_name="Lotus",
    )
    # Find heartbeat at t=10 (between 8.5s kill and 14.2s kill)
    hb_at_10 = [
        s
        for s in states
        if s["kind"] == "heartbeat" and s["t_offset"] == pytest.approx(10.0)
    ]
    assert len(hb_at_10) >= 1
    # After kill #1 (A killed B-player), A_alive=5, B_alive=4 → diff=+1
    assert hb_at_10[0]["numerical_diff"] == 1


def test_states_are_sorted_ascending_by_t_offset() -> None:
    """D-09: mid_round_states[] is time-ordered ascending."""
    states = synth_mod.synthesize_mid_round_states(
        round_events=_round_events(2),
        round_team_a_players=TEAM_A,
        round_team_b_players=TEAM_B,
        round_loadouts=_round_loadouts(2),
        side_a_this_round="atk",
        map_name="Lotus",
    )
    offsets = [s["t_offset"] for s in states]
    assert offsets == sorted(offsets)
