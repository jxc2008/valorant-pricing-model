"""REQ-match-state-engine — SPEC §1 acceptance: seq_id monotonicity + with_update field semantics.

Wave 1 (plan 03-01 Task 1): hypothesis property test for seq_id strict
monotonicity over 1000 random ``with_update`` calls per RESEARCH §"Code
Examples", plus a unit test on ``with_update`` field semantics (only changed
fields differ; seq_id bumps by 1; last_updated_ts strictly advances).

Pitfall 8 (RESEARCH): the monotonicity assertion is on ``seq_id`` only, not on
``last_updated_ts``. Windows wall-clock resolution is ~16ms — multiple
``time.time()`` calls inside a single test can collide.
"""
from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from src.state.match_state import MatchState


@st.composite
def field_diffs(draw: st.DrawFn) -> dict[str, Any]:
    """Generate random ``with_update(**diff)`` payloads.

    Picks any subset of the v2 dynamic fields to update with random values.
    Static fields are NEVER mutated by the arbiter, so we don't generate them.
    """
    diff: dict[str, Any] = {}
    if draw(st.booleans()):
        diff["a_round"] = draw(st.integers(min_value=0, max_value=24))
    if draw(st.booleans()):
        diff["b_round"] = draw(st.integers(min_value=0, max_value=24))
    if draw(st.booleans()):
        diff["a_map_score"] = draw(st.integers(min_value=0, max_value=2))
    if draw(st.booleans()):
        diff["b_map_score"] = draw(st.integers(min_value=0, max_value=2))
    if draw(st.booleans()):
        diff["bomb_planted"] = draw(st.booleans())
    if draw(st.booleans()):
        diff["attackers_alive"] = draw(st.one_of(st.none(), st.integers(min_value=0, max_value=5)))
    if draw(st.booleans()):
        diff["defenders_alive"] = draw(st.one_of(st.none(), st.integers(min_value=0, max_value=5)))
    if draw(st.booleans()):
        diff["time_left_s"] = draw(st.one_of(st.none(), st.floats(min_value=0.0, max_value=45.0)))
    return diff


@given(diffs=st.lists(field_diffs(), min_size=1, max_size=1000))
@settings(max_examples=50, deadline=None)
def test_seq_id_strictly_monotonic(
    diffs: list[dict[str, Any]],
) -> None:
    """seq_id strictly increases by 1 across each ``with_update`` call.

    RESEARCH §"Code Examples" / "Hypothesis property test for seq_id monotonicity".
    Pitfall 8: assertion is on ``seq_id``, NOT ``last_updated_ts``.
    """
    state = _initial_state()
    seq_ids = [state.seq_id]
    for diff in diffs:
        state = state.with_update(**diff)
        seq_ids.append(state.seq_id)
    # Strictly increasing by exactly 1 per step.
    # NOTE: pair adjacent elements via slicing; seq_ids[1:] is exactly one
    # shorter than seq_ids[:-1] by construction (strict=True is required by
    # the ruff B905 lint and is satisfied here).
    assert all(b == a + 1 for a, b in zip(seq_ids[:-1], seq_ids[1:], strict=True))


def test_with_update_field_semantics(
    make_match_state: Callable[..., MatchState],
) -> None:
    """with_update returns a NEW frozen instance; only the requested fields change.

    Asserts:
      - The returned instance is a fresh object (not the same identity).
      - Only the kwargs passed differ from the prior state.
      - seq_id bumps by exactly 1.
      - last_updated_ts strictly advances (sleep 1ms to dodge Windows wall-clock
        resolution per RESEARCH Pitfall 8).
    """
    prior = make_match_state()
    time.sleep(1e-3)  # Pitfall 8: avoid wall-clock collision on Windows.
    new = prior.with_update(bomb_planted=True, attackers_alive=4, defenders_alive=3)

    # Identity: a new instance was returned.
    assert new is not prior

    # Only the changed fields differ; everything else carries forward.
    assert new.bomb_planted is True
    assert new.attackers_alive == 4
    assert new.defenders_alive == 3
    assert new.match_id == prior.match_id
    assert new.team_a == prior.team_a
    assert new.team_b == prior.team_b
    assert new.map_pool == prior.map_pool
    assert new.map_side_orients == prior.map_side_orients
    assert new.map_winners == prior.map_winners
    assert new.pistol_winner_a == prior.pistol_winner_a
    assert new.map_idx == prior.map_idx
    assert new.a_map_score == prior.a_map_score
    assert new.b_map_score == prior.b_map_score
    assert new.a_round == prior.a_round
    assert new.b_round == prior.b_round
    assert new.side_orient == prior.side_orient
    assert new.time_left_s == prior.time_left_s

    # seq_id bumps by exactly 1.
    assert new.seq_id == prior.seq_id + 1

    # last_updated_ts strictly advances (Pitfall 8: 1ms sleep above guarantees).
    assert new.last_updated_ts > prior.last_updated_ts


def _initial_state() -> MatchState:
    """Build the initial MatchState for the property test (no fixtures needed)."""
    return MatchState(
        match_id="prop-test",
        team_a="A",
        team_b="B",
        map_pool=("Lotus", "Bind", "Haven"),
        map_side_orients=("a_atk", "a_def", "a_atk"),
        map_winners=(None, None, None),
        pistol_winner_a={0: None, 1: None, 2: None},
        map_idx=0,
        a_map_score=0,
        b_map_score=0,
        a_round=0,
        b_round=0,
        side_orient="a_atk",
        bomb_planted=False,
        attackers_alive=None,
        defenders_alive=None,
        time_left_s=None,
        seq_id=0,
        last_updated_ts=0.0,
    )
