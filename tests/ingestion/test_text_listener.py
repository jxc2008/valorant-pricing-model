"""REQ-text-listener — SPEC §4: typed soft events + degrade-to-no-op + Twitter-only quarantine.

GREEN tests (Wave 3D / plan 03-06):

- ``test_emits_typed_soft_events`` — direct ``on_tweet`` invocation drives a
  PendingEvent into ``arbiter.score_changes`` with ``source="twitter"`` and
  ``event_type="score_change"``. Non-score tweets are no-ops.
- ``test_twitter_only_update_quarantined`` — a Twitter-only score event aged
  past the arbiter's _DEQUE_MAX_AGE_S (3s wall-clock) is quarantined to
  JSONL with ``seq_id=null`` + ``quarantined=true`` + ``source="twitter"``;
  ``MatchState`` is UNCHANGED (the >=2-source rule blocks the commit).
- ``test_no_token_noop`` — ``run_text_listener`` returns within < 1s when
  ``TWITTER_BEARER_TOKEN`` is empty/unset (or whitespace-only).

The mocked Twitter API path is exercised by direct invocation of
``_MatchSignalListener.on_tweet`` rather than by booting the network stream;
the rule-sync / ``listener.filter()`` code path is only entered when the
token gate is satisfied, which the no-op test inverts intentionally.
"""
from __future__ import annotations

import asyncio
import json
import time

import pytest

from src.ingestion.events import PendingEvent
from src.ingestion.text_listener import _MatchSignalListener, run_text_listener
from src.ingestion.timestamps import mono_ns, wall_time


@pytest.mark.asyncio
async def test_emits_typed_soft_events(arbiter_with_stub_sources) -> None:  # type: ignore[no-untyped-def]
    """Tweet with score pattern -> 1 PendingEvent in arbiter.score_changes; tweet without -> 0."""
    arb = arbiter_with_stub_sources
    listener = _MatchSignalListener(bearer_token="dummy-test-token", arbiter=arb)

    initial_len = len(arb.score_changes)
    await listener.on_tweet({"text": "T1 takes Lotus 13-9 vs Sentinels"})
    assert len(arb.score_changes) == initial_len + 1
    ev = arb.score_changes[-1]
    assert ev.source == "twitter"
    assert ev.event_type == "score_change"
    assert ev.fields_proposed == {"a_round": 13, "b_round": 9}

    # Non-score tweet — no push.
    await listener.on_tweet({"text": "good game everyone, gg"})
    assert len(arb.score_changes) == initial_len + 1


@pytest.mark.asyncio
async def test_twitter_only_update_quarantined(arbiter_with_stub_sources) -> None:  # type: ignore[no-untyped-def]
    """Twitter-alone score event NEVER commits — single-source < arbiter's >=2-source rule.

    Drives the staleness path (t_observed older than _DEQUE_MAX_AGE_S=3s) so
    the arbiter quarantines on the next tick; verifies state UNCHANGED and
    JSONL line carries ``seq_id=null`` + ``quarantined=true`` +
    ``source="twitter"``.
    """
    arb = arbiter_with_stub_sources
    initial_seq = arb.state.seq_id
    initial_a_round = arb.state.a_round

    # Push 1 Twitter event with stale t_observed (older than _DEQUE_MAX_AGE_S = 3s)
    # so the arbiter quarantines it on tick.
    stale_t = wall_time() - 10.0
    arb.score_changes.append(
        PendingEvent(
            source="twitter",
            event_type="score_change",
            fields_proposed={"a_round": initial_a_round + 1},
            t_observed=stale_t,
            t_ingested=mono_ns(),
        )
    )
    arb.tick()

    # State UNCHANGED (no commit).
    assert arb.state.seq_id == initial_seq
    assert arb.state.a_round == initial_a_round

    # Quarantine line in JSONL.
    log_text = arb.jsonl_path.read_text(encoding="utf-8")
    assert log_text  # not empty
    line = json.loads(log_text.strip().splitlines()[0])
    assert line["seq_id"] is None
    assert line["quarantined"] is True
    assert line["source"] == "twitter"
    assert line["event_type"] == "score_change"
    assert line["quarantine_reason"] == "stale_in_deque_no_cross_confirm"


@pytest.mark.asyncio
async def test_no_token_noop(monkeypatch: pytest.MonkeyPatch, arbiter_with_stub_sources) -> None:  # type: ignore[no-untyped-def]
    """run_text_listener returns immediately if TWITTER_BEARER_TOKEN is empty.

    Default CI deployment has no token (RESEARCH Pitfall 1: Twitter Basic
    tier deprecated 2026-02-06 for new accounts) — the listener MUST log a
    warning and return without raising so the arbiter's other 2 sources
    (rib.gg + OCR) keep running unaffected.
    """
    monkeypatch.delenv("TWITTER_BEARER_TOKEN", raising=False)

    arb = arbiter_with_stub_sources
    initial_seq = arb.state.seq_id
    initial_score_changes = len(arb.score_changes)

    # Run with timeout — if it doesn't return cleanly, the test fails.
    t0 = time.monotonic()
    await asyncio.wait_for(run_text_listener(arb), timeout=2.0)
    elapsed = time.monotonic() - t0

    assert elapsed < 1.0  # immediate return per no-op contract
    assert arb.state.seq_id == initial_seq  # no state change
    assert len(arb.score_changes) == initial_score_changes  # no events pushed

    # Re-test with whitespace-only string (counts as empty per .strip() gate).
    monkeypatch.setenv("TWITTER_BEARER_TOKEN", "   ")
    await asyncio.wait_for(run_text_listener(arb), timeout=2.0)
    assert arb.state.seq_id == initial_seq
