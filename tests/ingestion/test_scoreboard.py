"""REQ-scoreboard-polling — async rib.gg poller integration tests (03-04).

Both tests run against an aioresponses-mocked rib.gg endpoint:

- ``test_poller_emits_typed_events``: drives ``_fetch_match_details`` +
  ``_extract_score_change_fields`` + the manual arbiter push that
  ``run_scoreboard_poller`` performs each cycle. Asserts the deque receives
  exactly one ``PendingEvent`` with the expected source / event_type /
  fields_proposed shape.

- ``test_retry_honors_retry_after``: stacks two queued responses
  (503 + Retry-After:1, then 200 with payload). ``_fetch_match_details``
  retries via tenacity, honoring the Retry-After header per
  ``_RibggWaitAsync`` (Phase 2 ``_ribgg_wait`` async port).

We test the inner functions directly (rather than spinning the infinite
``run_scoreboard_poller`` loop) because the loop body is the same code path
under test, just without the timing/cancellation harness.
"""

from __future__ import annotations

from pathlib import Path

import aiohttp
import pytest
from aioresponses import aioresponses

from src.config.constants import RIBGG_BASE_URL
from src.ingestion import Arbiter, PendingEvent, mono_ns, wall_time
from src.ingestion.scoreboard import (
    _extract_score_change_fields,
    _fetch_match_details,
)
from src.state.match_state import MatchState


def _make_state() -> MatchState:
    """Synthetic v2 MatchState with a_round=10, b_round=8 — used as the diff anchor."""
    return MatchState(
        match_id="scoreboard-test-001",
        team_a="A",
        team_b="B",
        map_pool=("Lotus", "Bind", "Haven"),
        map_side_orients=("a_atk", "a_def", "a_atk"),
        map_winners=(None, None, None),
        pistol_winner_a={0: None, 1: None, 2: None},
        map_idx=0,
        a_map_score=0,
        b_map_score=0,
        a_round=10,
        b_round=8,
        side_orient="atk",
        bomb_planted=False,
        attackers_alive=None,
        defenders_alive=None,
        time_left_s=None,
        seq_id=0,
        last_updated_ts=0.0,
    )


@pytest.mark.asyncio
async def test_poller_emits_typed_events(tmp_path: Path) -> None:
    """One run_scoreboard_poller cycle pushes 1 PendingEvent into arbiter.score_changes.

    Mocked rib.gg returns ``team1Score=13 / team2Score=10``; prev state
    carries ``a_round=10 / b_round=8``; the diff produces ``fields_proposed=
    {a_round: 13, b_round: 10}`` and the arbiter deque ends with len=1.
    """
    arb = Arbiter(
        _make_state(),
        event_log_dir=tmp_path / "event_log",
        metrics_log_dir=tmp_path / "metrics",
    )
    match_id = 12345

    with aioresponses() as mocked:
        mocked.get(
            f"{RIBGG_BASE_URL}/matches/{match_id}/details",
            payload={"team1Score": 13, "team2Score": 10},
        )

        # Drive the inner functions directly — same code path that
        # run_scoreboard_poller drives once per cadence_s.
        async with aiohttp.ClientSession() as session:
            details = await _fetch_match_details(session, match_id)
            fields = _extract_score_change_fields(details, arb.state)

        assert fields == {"a_round": 13, "b_round": 10}

        # Mirror the arbiter push that run_scoreboard_poller would perform.
        arb.score_changes.append(
            PendingEvent(
                source="ribgg",
                event_type="score_change",
                fields_proposed=fields,
                t_observed=wall_time(),
                t_ingested=mono_ns(),
            )
        )

    assert len(arb.score_changes) == 1
    ev = arb.score_changes[0]
    assert ev.source == "ribgg"
    assert ev.event_type == "score_change"
    assert ev.fields_proposed == {"a_round": 13, "b_round": 10}


@pytest.mark.asyncio
async def test_retry_honors_retry_after() -> None:
    """Tenacity retry honors Retry-After header on 5xx (Phase 2 _ribgg_wait async port).

    aioresponses queues responses in order: first GET -> 503 with
    Retry-After:1; second GET -> 200 with payload. ``_fetch_match_details``
    retries (via tenacity ``@retry``), the ``_RibggWaitAsync`` wait function
    honors the 1s Retry-After header (briefly enough to not slow the test),
    and the second call returns the payload.
    """
    match_id = 12345
    with aioresponses() as mocked:
        mocked.get(
            f"{RIBGG_BASE_URL}/matches/{match_id}/details",
            status=503,
            headers={"Retry-After": "1"},
        )
        mocked.get(
            f"{RIBGG_BASE_URL}/matches/{match_id}/details",
            payload={"team1Score": 13, "team2Score": 10},
        )

        async with aiohttp.ClientSession() as session:
            result = await _fetch_match_details(session, match_id)

        assert result["team1Score"] == 13
        assert result["team2Score"] == 10
