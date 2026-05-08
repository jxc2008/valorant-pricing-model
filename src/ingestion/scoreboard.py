"""Async rib.gg scoreboard poller (REQ-scoreboard-polling / 03-04 / 03-CONTEXT D-09).

Direct salvage of Phase 2 ETL's resilience playbook from
``scripts/probe_round_events.py:122`` (sync ``requests``-based ``get_json`` +
``_ribgg_wait``) ported to async over ``aiohttp.ClientSession``:

- ``Connection: close`` HTTP header — prevents urllib3-on-Windows stale-socket
  pooling against be-prod.rib.gg (Heroku-fronted; idle sockets close silently).
- ``_RibggWaitAsync`` — tenacity wait subclass honoring HTTP ``Retry-After``
  on 4xx/5xx; falls through to capped exponential backoff (max 10s).
- ``stop_after_attempt(SCOREBOARD_MAX_RETRIES)`` — 5 attempts per call.
- 5-failure cooldown — after ``SCOREBOARD_MAX_RETRIES`` consecutive failures,
  the poller pauses for ``SCOREBOARD_FAILURE_COOLDOWN_S`` (60s) before resuming.

Output contract (RESEARCH §"Pattern 3" / 03-04 PLAN <interfaces>):
- ``run_scoreboard_poller`` is the SOLE producer of ``PendingEvent(source="ribgg",
  event_type="score_change", ...)`` records into ``Arbiter.score_changes``.
- The arbiter's ≥ 2-source rule (DEC-006 v2 / ``ARBITER_SCORE_WINDOW_S=2.0``)
  cross-confirms each ribgg push against the OCR score-banner stream before
  committing — this poller NEVER sole-sources a state mutation.

Time discipline (RESEARCH Pitfall 3):
- ``t_observed`` uses ``wall_time()`` (``time.time()``) — replay alignment only.
- ``t_ingested`` uses ``mono_ns()`` (``time.monotonic_ns()``) — latency math.

References
----------
- ``.planning/phases/03-live-ingestion-layer/03-CONTEXT.md`` D-09
- ``.planning/phases/03-live-ingestion-layer/03-RESEARCH.md`` Pattern 3, Pitfall 3
- ``scripts/probe_round_events.py`` (lines ~97-148) — salvage source
- ``src/ingestion/arbiter.py`` — downstream consumer (``Arbiter.score_changes``)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
from tenacity import RetryCallState, retry, stop_after_attempt
from tenacity.wait import wait_base

from src.config.constants import (
    RIBGG_BASE_URL,
    SCOREBOARD_FAILURE_COOLDOWN_S,
    SCOREBOARD_MAX_RETRIES,
    SCOREBOARD_POLL_CADENCE_S,
)
from src.ingestion.arbiter import Arbiter
from src.ingestion.events import PendingEvent
from src.ingestion.timestamps import mono_ns, wall_time
from src.state.match_state import MatchState

logger = logging.getLogger(__name__)


HEADERS: dict[str, str] = {
    "User-Agent": "Mozilla/5.0 (compatible; valorant-pricing-model/0.1; +github)",
    "Accept": "application/json",
    # Connection: close — Phase 2 resilience (probe_round_events.py:106). Stops
    # urllib3/aiohttp from caching sockets against be-prod.rib.gg that the
    # Heroku frontend silently closes; trades ~0.2s extra TLS per call for
    # full reliability on Windows.
    "Connection": "close",
}

_REQUEST_TIMEOUT_S: float = 60.0
"""Per-request total timeout (seconds). Phase 2 carry-forward — rib.gg pages
occasionally stall under VCT-event load; a longer per-call wait is cheaper
than retrying the whole 5-attempt cycle prematurely."""


class _RibggWaitAsync(wait_base):
    """Tenacity wait function honoring rib.gg's ``Retry-After`` header (W6).

    Async port of ``_ribgg_wait`` in ``scripts/probe_round_events.py:115``.
    If the most recent attempt raised ``aiohttp.ClientResponseError`` carrying
    a ``Retry-After`` header (typical 429/503 from Heroku-fronted APIs), wait
    that many seconds capped at 10s. Otherwise fall through to exponential
    backoff capped at 10s.

    Cap at 10s (vs Phase 2 sync's 30/60s) because the poller's outer cadence
    is 5s — a 30s tenacity sleep would leave the poller silent for 6 cycles.
    """

    def __call__(self, retry_state: RetryCallState) -> float:
        exc = retry_state.outcome.exception() if retry_state.outcome else None
        if isinstance(exc, aiohttp.ClientResponseError) and exc.headers is not None:
            ra = exc.headers.get("Retry-After")
            if ra is not None:
                try:
                    return min(float(ra), 10.0)
                except ValueError:
                    pass
        attempt = retry_state.attempt_number
        return float(min(2.0 ** (attempt - 1), 10.0))


_ribgg_wait_async: _RibggWaitAsync = _RibggWaitAsync()
"""Module-level singleton — tenacity instantiates wait classes once per
decorator application; reusing the singleton across decorators keeps the
import surface small and matches the Phase 2 sync pattern (one shared
`_ribgg_wait` callable)."""


@retry(
    stop=stop_after_attempt(SCOREBOARD_MAX_RETRIES),
    wait=_ribgg_wait_async,
    reraise=True,
)
async def _fetch_match_details(
    session: aiohttp.ClientSession,
    match_id: int,
) -> dict[str, Any]:
    """GET ``/v1/matches/{id}/details`` with tenacity retry + Retry-After honoring.

    Returns the parsed JSON body. Raises ``aiohttp.ClientResponseError`` on
    final failure (after ``SCOREBOARD_MAX_RETRIES`` attempts).
    """
    url = f"{RIBGG_BASE_URL}/matches/{match_id}/details"
    timeout = aiohttp.ClientTimeout(total=_REQUEST_TIMEOUT_S)
    async with session.get(url, headers=HEADERS, timeout=timeout) as resp:
        resp.raise_for_status()
        payload: dict[str, Any] = await resp.json()
        return payload


@retry(
    stop=stop_after_attempt(SCOREBOARD_MAX_RETRIES),
    wait=_ribgg_wait_async,
    reraise=True,
)
async def _fetch_series(
    session: aiohttp.ClientSession,
    series_id: int,
) -> dict[str, Any]:
    """GET ``/v1/series/{id}`` with tenacity retry + Retry-After honoring.

    Reserved for future best-of-N series-level state needs (per-map score
    derivation when ``map_idx`` rolls). Phase 3 03-04 only uses
    ``_fetch_match_details``; this helper keeps the rib.gg call surface
    symmetric for downstream waves.
    """
    url = f"{RIBGG_BASE_URL}/series/{series_id}"
    timeout = aiohttp.ClientTimeout(total=_REQUEST_TIMEOUT_S)
    async with session.get(url, headers=HEADERS, timeout=timeout) as resp:
        resp.raise_for_status()
        payload: dict[str, Any] = await resp.json()
        return payload


def _extract_score_change_fields(
    details: dict[str, Any],
    prev_state: MatchState,
) -> dict[str, Any] | None:
    """Diff rib.gg ``/matches/{id}/details`` payload against ``prev_state``.

    Returns the ``fields_proposed`` dict for a ``PendingEvent(event_type=
    "score_change")`` push, OR ``None`` if no score delta is observed.

    Read keys (per Phase 2 probe_round_events shape):
      - ``team1Score`` -> ``a_round``
      - ``team2Score`` -> ``b_round``

    A change in EITHER field returns the FULL ``{"a_round": ..., "b_round":
    ...}`` proposal (so the arbiter's signature-grouping over
    ``fields_proposed.items()`` matches OCR's emission shape). Returns None
    when both values match the prior state — keeps the poller idempotent
    across the 5s cadence.

    Defensive: missing keys (sparse rib.gg response) -> None (no push). The
    arbiter's staleness kill-switch (5s) handles extended response gaps.
    """
    a_round_new = details.get("team1Score")
    b_round_new = details.get("team2Score")
    if a_round_new is None or b_round_new is None:
        return None
    if not isinstance(a_round_new, int) or not isinstance(b_round_new, int):
        return None
    if a_round_new == prev_state.a_round and b_round_new == prev_state.b_round:
        return None
    return {"a_round": a_round_new, "b_round": b_round_new}


async def run_scoreboard_poller(
    session: aiohttp.ClientSession,
    match_id: int,
    arbiter: Arbiter,
    *,
    cadence_s: float = SCOREBOARD_POLL_CADENCE_S,
) -> None:
    """Infinite loop — poll rib.gg ``/matches/{id}/details`` every ``cadence_s``.

    Per non-degenerate fetch, push exactly ONE ``PendingEvent(source="ribgg",
    event_type="score_change", ...)`` into ``arbiter.score_changes``. The
    arbiter's tick() method applies the DEC-006 v2 ≥ 2-source rule before
    committing.

    Failure handling:
    - Per-call: tenacity ``@retry`` honors ``Retry-After`` and exp-backs off.
    - Cycle-level: catch all exceptions; increment ``consecutive_failures``;
      after ``SCOREBOARD_MAX_RETRIES`` (5) consecutive failed cycles, sleep
      ``SCOREBOARD_FAILURE_COOLDOWN_S`` (60s) and reset the counter.

    The function never returns under normal operation. Cancellation is the
    expected exit path (``asyncio.CancelledError`` propagates).
    """
    consecutive_failures = 0
    while True:
        t_observed = wall_time()
        t_ingested = mono_ns()
        try:
            details = await _fetch_match_details(session, match_id)
            fields = _extract_score_change_fields(details, arbiter.state)
            if fields is not None:
                arbiter.score_changes.append(
                    PendingEvent(
                        source="ribgg",
                        event_type="score_change",
                        fields_proposed=fields,
                        t_observed=t_observed,
                        t_ingested=t_ingested,
                    )
                )
            consecutive_failures = 0
            await asyncio.sleep(cadence_s)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 — top-level resilience boundary
            consecutive_failures += 1
            logger.warning(
                "scoreboard_poller fetch failure",
                extra={
                    "match_id": match_id,
                    "consecutive_failures": consecutive_failures,
                    "exc_type": type(exc).__name__,
                    "exc_msg": str(exc),
                },
            )
            if consecutive_failures >= SCOREBOARD_MAX_RETRIES:
                logger.warning(
                    "scoreboard_poller entering cooldown after %d consecutive failures",
                    consecutive_failures,
                    extra={"cooldown_s": SCOREBOARD_FAILURE_COOLDOWN_S},
                )
                await asyncio.sleep(SCOREBOARD_FAILURE_COOLDOWN_S)
                consecutive_failures = 0
            else:
                await asyncio.sleep(cadence_s)
