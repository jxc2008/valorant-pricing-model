"""Twitter v2 streaming text listener (REQ-text-listener / 03-CONTEXT D-07).

Soft cross-confirm source ONLY — NEVER sole-source per SPEC §4. The arbiter's
>=2-source rule (DEC-006 v2 / ``ARBITER_SCORE_WINDOW_S=2.0``) ensures a Twitter
event alone cannot commit state; rib.gg or OCR must provide the other source
within the cross-confirm window. The Twitter-only quarantine path is exercised
by ``tests/ingestion/test_text_listener.py::test_twitter_only_update_quarantined``.

PERMANENT DEGRADATION (RESEARCH Pitfall 1)
------------------------------------------
- Twitter API Basic tier ($200/mo) was deprecated 2026-02-06 for new accounts.
- New developers cannot subscribe — the API moved to a pay-per-use model.
- Default deployment has no ``TWITTER_BEARER_TOKEN`` env var; this listener
  degrades to no-op silently (``logger.warning`` emitted on startup so CI logs
  surface the absence; no exception, no retries).
- Arbiter still satisfies its >=2-source rule via rib.gg + OCR cross-confirm;
  the listener is opt-in for operators with pre-2026-02-06 Basic-tier accounts.

Surface
-------
- ``run_text_listener(arbiter)`` — env-gated init; if ``TWITTER_BEARER_TOKEN``
  is empty/unset, returns immediately. Otherwise constructs a
  ``_MatchSignalListener``, syncs static rules from ``TWITTER_RULE_SET``, and
  calls ``listener.filter()`` to block on the stream until cancelled
  (``asyncio.TaskGroup`` teardown by 03-08 E2E composition).

NEVER
-----
- Push to ``arbiter.bomb_events`` or ``arbiter.round_end_events`` (Twitter
  signal-quality is too noisy for those event types per SPEC §5; OCR is the
  authoritative source for bomb/round-end commits).
- Construct without the env gate — raising on missing token would break
  ``test_no_token_noop`` and the default CI deployment.

Implementation notes
--------------------
- ``tweepy.asynchronous.AsyncStreamingClient`` is the import path in tweepy
  4.16.x — the symbol is NOT re-exported at the ``tweepy`` top level (verified
  empirically; researcher's ``import tweepy; tweepy.AsyncStreamingClient``
  reference would AttributeError). ``tweepy.StreamRule`` IS at top level and
  is reused.
- ``AsyncStreamingClient.filter()`` blocks on the stream; cancellation by the
  caller's TaskGroup tears it down cleanly per tweepy's asyncio contract.
- Score-signal regex is intentionally loose (``\\d{1,2}\\s*[-:]\\s*\\d{1,2}``)
  with a >13 reject — Twitter posts about OT scores are rare and noisy enough
  to drop without harm; the arbiter's other 2 sources cover OT cleanly.

References
----------
- ``.planning/phases/03-live-ingestion-layer/03-CONTEXT.md`` D-07
- ``.planning/phases/03-live-ingestion-layer/03-RESEARCH.md`` Pattern 5, Pitfall 1
- ``.planning/phases/03-live-ingestion-layer/03-SPEC.md`` §4 (REQ-text-listener)
- ``src/ingestion/arbiter.py`` — downstream consumer (arbiter.score_changes)
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any

import tweepy
from tweepy.asynchronous import AsyncStreamingClient

from src.config.constants import TWITTER_RULE_SET
from src.ingestion.arbiter import Arbiter
from src.ingestion.events import PendingEvent
from src.ingestion.timestamps import mono_ns, wall_time

logger = logging.getLogger(__name__)

# Score signal patterns from tweet text: "13-9", "13:9", "13 - 9", etc.
# Anchored on word boundaries to avoid matching dates / years / mentions.
_SCORE_PATTERN = re.compile(r"\b(\d{1,2})\s*[-:]\s*(\d{1,2})\b")


class _MatchSignalListener(AsyncStreamingClient):  # type: ignore[misc]  # tweepy ships no stubs; AsyncStreamingClient resolves to Any under mypy
    """tweepy AsyncStreamingClient subclass that pushes soft-confirm score events.

    ``on_tweet`` parses the tweet text against ``_SCORE_PATTERN`` and, on a
    valid score signal (each side <= 13), pushes a single
    ``PendingEvent(source="twitter", event_type="score_change")`` into
    ``arbiter.score_changes``. The arbiter's >=2-source rule guards the commit
    — Twitter is NEVER the sole source for a state mutation.
    """

    def __init__(self, bearer_token: str, arbiter: Arbiter) -> None:
        # return_type=dict so on_tweet receives plain dicts (researcher pattern)
        # and tests can construct synthetic tweet payloads without tweepy's
        # Tweet model.
        super().__init__(bearer_token=bearer_token, return_type=dict)
        self._arbiter = arbiter

    def _parse_score(self, text: str) -> dict[str, int] | None:
        """Extract ``{a_round, b_round}`` from tweet text; ``None`` if no valid match.

        Reject impossible scores (max 13 in regulation per ``WIN_THRESHOLD``).
        Loose bound — Twitter posts about OT scores are rare and noisy enough
        to drop without harm; the arbiter's other 2 sources (rib.gg + OCR)
        cover OT cleanly.
        """
        m = _SCORE_PATTERN.search(text)
        if m is None:
            return None
        a, b = int(m.group(1)), int(m.group(2))
        if a > 13 or b > 13:
            return None
        return {"a_round": a, "b_round": b}

    async def on_tweet(self, tweet: Any) -> None:
        """tweepy callback per matching tweet.

        SOFT-CONFIRM ONLY — the arbiter's >=2-source rule guards every commit.
        Twitter alone NEVER mutates ``MatchState``; this push is queued in
        ``arbiter.score_changes`` awaiting cross-confirm by rib.gg or OCR
        within ``ARBITER_SCORE_WINDOW_S`` (2s).
        """
        text = tweet.get("text", "") if isinstance(tweet, dict) else ""
        signal = self._parse_score(text)
        if signal is None:
            return
        self._arbiter.score_changes.append(
            PendingEvent(
                source="twitter",
                event_type="score_change",
                fields_proposed=signal,
                t_observed=wall_time(),
                t_ingested=mono_ns(),
            )
        )


async def run_text_listener(arbiter: Arbiter) -> None:
    """Long-running Twitter v2 streaming listener; degrades to no-op without token.

    Designed to fail SILENTLY on missing token (warning log only) so the
    arbiter's other 2 sources (rib.gg + OCR) remain unaffected. Caller wraps
    this in ``asyncio.TaskGroup`` (03-08 E2E gate); cancellation breaks
    ``listener.filter()`` cleanly per tweepy's asyncio contract.

    Whitespace-only tokens count as empty (``.strip()`` gate) — accidental
    blank-string secrets in CI configs degrade to no-op rather than silently
    booting a listener that immediately 401s.
    """
    token = os.environ.get("TWITTER_BEARER_TOKEN", "").strip()
    if not token:
        logger.warning(
            "TWITTER_BEARER_TOKEN absent — text listener degrades to no-op "
            "(RESEARCH Pitfall 1: Twitter Basic tier deprecated 2026-02-06 "
            "for new accounts; arbiter still satisfies >=2-source rule via "
            "rib.gg + OCR cross-confirm)."
        )
        return  # SPEC §4 acceptance: test_no_token_noop

    listener = _MatchSignalListener(bearer_token=token, arbiter=arbiter)

    # Sync rules — clear any existing rules from prior runs, install static set.
    # Wrapped in a try/except so a transient rule-API failure does not nuke the
    # listener; we proceed with whatever rule set the API currently holds.
    try:
        existing = await listener.get_rules()
        if isinstance(existing, dict) and existing.get("data"):
            ids = [r["id"] for r in existing["data"] if isinstance(r, dict) and "id" in r]
            if ids:
                await listener.delete_rules(ids)
        await listener.add_rules([tweepy.StreamRule(value=q) for q in TWITTER_RULE_SET])
    except Exception as exc:  # noqa: BLE001 — listener must keep running through rule-sync hiccups
        logger.warning("Twitter rule sync failed (%s) — proceeding with existing rules", exc)

    # Block on the stream; TaskGroup cancellation tears this down.
    await listener.filter()
