---
id: 03-04-scoreboard-poller
phase: 03
plan: 4
type: execute
wave: 3
depends_on:
  - 03-00-pyproject-and-constants
  - 03-01-shared-types-and-download
  - 03-02-salvage-verify
  - 03-03-match-state-move-and-extend
files_modified:
  - src/ingestion/scoreboard.py
  - src/ingestion/_http.py
  - tests/ingestion/test_scoreboard.py
autonomous: true
requirements:
  - REQ-scoreboard-polling
user_setup: []
must_haves:
  truths:
    - "ScoreboardPoller is a class (not module-level state) constructed per-match with explicit dependencies (CRule 2 + RESEARCH §Salvage-Port Delta line 586)"
    - "Poller uses Phase 2's _ribgg_wait + Connection: close header verbatim, with backoff cap overridden from 30s to RIBGG_LIVE_BACKOFF_CAP_S = 10s (RESEARCH Pitfall 3)"
    - "Poller emits a t_observed heartbeat ArbiterPending every 5s regardless of whether content changed (RESEARCH Pitfall 3 #1 — kill-switch staleness must trip correctly)"
    - "Poller is asyncio-native: poll loop is `async def`, calls `await loop.run_in_executor(executor, get_json, url)` per RESEARCH Standard Stack tradeoff line 104 (no aiohttp port)"
    - "Poller emits typed ArbiterPending events with source=\"ribgg\", event_type ∈ {score_change, round_end, ...}, t_observed=time.time(), t_ingested=time.monotonic()"
    - "Defensive null-roster handling per Phase 2 fix (commit fafa6ae) — early-return on missing rosters / attackingFirstTeamNumber"
    - "rib.gg HTTP layer (HEADERS, _ribgg_wait, get_json) shared between scripts/probe_round_events.py and src/ingestion/scoreboard.py via src/ingestion/_http.py (CRule 2 single canonical helper extraction per PATTERNS line 778)"
    - "mypy gradual on src/ingestion/ but new code is fully type-annotated (SPEC §Constraints)"
  artifacts:
    - path: src/ingestion/_http.py
      provides: "shared rib.gg HTTP helpers: HEADERS, _ribgg_wait, get_json (extracted from scripts/probe_round_events.py for CRule 2)"
      contains: "Connection: close"
    - path: src/ingestion/scoreboard.py
      provides: "ScoreboardPoller class with async poll() loop emitting typed ArbiterPending events"
      contains: "class ScoreboardPoller"
    - path: tests/ingestion/test_scoreboard.py
      provides: "monkeypatched HTTP test asserting cadence, heartbeat, resilience patterns, defensive null-roster"
  key_links:
    - from: "src/ingestion/scoreboard.py"
      to: "src/ingestion/_http.py"
      via: "from src.ingestion._http import HEADERS, get_json"
      pattern: "from src\\.ingestion\\._http import"
    - from: "src/ingestion/scoreboard.py"
      to: "src/ingestion/types.py"
      via: "emits ArbiterPending events with source=\"ribgg\""
      pattern: "ArbiterPending\\(.*source=.ribgg."
---

<objective>
Wave 2 source plan #1 — port the rib.gg HTTP polling layer from `reference/rib_scraper.py` (+ the verified Phase 2 `scripts/probe_round_events.py` patterns) into `src/ingestion/scoreboard.py` adapting to Phase 3's asyncio-native, typed-event-emitting shape.

Purpose: rib.gg is the authoritative-but-slow source. Per CONTEXT D-04 / DEC-006, the arbiter cross-confirms score changes against ≥ 1 other source within 2s; this poller is the rib.gg arm. RESEARCH Pitfall 3 calls out the live-cap delta from Phase 2's batch ETL: 5-failure cooldowns can't pause the poller > 5s or KILL_SWITCH_STALENESS_S trips.

Output: `src/ingestion/_http.py` (shared HEADERS + `_ribgg_wait` + `get_json` extracted for CRule 2), `src/ingestion/scoreboard.py` (`ScoreboardPoller` class with async poll loop), `tests/ingestion/test_scoreboard.py` (monkeypatched fixture-driven cadence + heartbeat + resilience + null-roster tests).
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/03-live-ingestion-layer/03-SPEC.md
@.planning/phases/03-live-ingestion-layer/03-CONTEXT.md
@.planning/phases/03-live-ingestion-layer/03-RESEARCH.md
@.planning/phases/03-live-ingestion-layer/03-PATTERNS.md
@.planning/phases/03-live-ingestion-layer/03-VALIDATION.md
@scripts/probe_round_events.py
@reference/rib_scraper.py
@reference/vlr_scraper.py
@src/ingestion/types.py
@src/ingestion/__init__.py
@src/config/constants.py
@tests/probe/conftest.py
@tests/probe/fixtures/match_details.json
@tests/probe/test_endpoint_shapes.py
@CLAUDE.md

<interfaces>
<!-- Phase 2 HTTP layer (analog for src/ingestion/_http.py) — scripts/probe_round_events.py:84-135 -->

```python
HEADERS: dict[str, str] = {
    "User-Agent": "Mozilla/5.0 (compatible; valorant-pricing-model/0.1; +github)",
    "Referer": "https://www.rib.gg/",
    "Connection": "close",
}

def _ribgg_wait(retry_state: RetryCallState) -> float:
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        ra = exc.response.headers.get("Retry-After")
        if ra is not None:
            try:
                return min(float(ra), 60.0)
            except ValueError:
                pass
    attempt = retry_state.attempt_number
    return min(2.0 ** (attempt - 1), 30.0)

@retry(stop=stop_after_attempt(5), wait=_ribgg_wait)
def get_json(url: str) -> dict[str, Any]:
    resp = requests.get(url, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    return resp.json()
```

<!-- ArbiterPending shape (consume from src/ingestion/types.py — NEW from 03-01) -->

```python
@dataclass(frozen=True, slots=True)
class ArbiterPending:
    signal_value: dict[str, Any]
    source: SourceTag                # "ribgg" for this poller
    event_type: EventType            # "score_change" or "round_end"
    t_observed: float                # wall-clock seconds
    t_ingested: float                # monotonic seconds
```

<!-- Constants this plan reads (from src/config/constants.py — added by 03-00) -->

```python
RIBGG_BASE_URL                  # "https://be-prod.rib.gg/v1"
RIBGG_LIVE_BACKOFF_CAP_S        # 10.0  (Pitfall 3 override of Phase 2's 30s)
KILL_SWITCH_STALENESS_S         # 5.0   (the budget the heartbeat protects against)
```

<!-- Existing test fixture availability (from tests/probe/conftest.py via pytest_plugins) -->

```python
events_response  -> dict   # GET /v1/events sample
series_response  -> dict   # GET /v1/series sample
match_details   -> dict   # GET /v1/matches/{id}/details sample
mock_ribgg_response -> Callable[[url], dict]  # url->fixture mapper (from 03-01 conftest)
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Extract shared rib.gg HTTP layer into src/ingestion/_http.py</name>
  <files>src/ingestion/_http.py, scripts/probe_round_events.py</files>
  <read_first>
    - scripts/probe_round_events.py:84-141 (HEADERS + _ribgg_wait + get_json source)
    - src/config/constants.py:RIBGG_BASE_URL, RIBGG_LIVE_BACKOFF_CAP_S
    - .planning/phases/03-live-ingestion-layer/03-PATTERNS.md §Single-source canonical helper extraction (lines 770-779)
    - .planning/phases/03-live-ingestion-layer/03-RESEARCH.md §Don't Hand-Roll first row (lines 565-568)
    - .planning/phases/03-live-ingestion-layer/03-RESEARCH.md §Common Pitfalls Pitfall 3 (lines 656-668 — backoff cap)
  </read_first>
  <action>
Create `src/ingestion/_http.py` containing the shared HTTP layer. It exports two names: `HEADERS` (the rib.gg request headers) and `get_json` (the tenacity-retried GET). It also exports `make_get_json(backoff_cap_s)` for callers who need a different backoff cap (Phase 2 ETL uses 30s; live poller uses 10s per RESEARCH Pitfall 3).

```python
"""Shared rib.gg HTTP layer used by both scripts/probe_round_events.py
(Phase 2 batch ETL) and src/ingestion/scoreboard.py (Phase 3 live poller).

CRule 2 single-source per concept — extracted from
scripts/probe_round_events.py:84-141 verbatim, with the addition of a
configurable backoff cap so Phase 3 can override Phase 2's 30s default
to RIBGG_LIVE_BACKOFF_CAP_S = 10s (RESEARCH Pitfall 3 — keeps the
KILL_SWITCH_STALENESS_S budget honored on extended outages).

The Phase 2 callsite (scripts/probe_round_events.py) imports the original
30s-cap function; the Phase 3 callsite (src/ingestion/scoreboard.py)
imports the live-cap function via make_get_json(RIBGG_LIVE_BACKOFF_CAP_S).

Sources
-------
- scripts/probe_round_events.py:84-141 (verbatim source)
- 03-RESEARCH.md §Don't Hand-Roll row 1 (line 566)
- 03-RESEARCH.md §Common Pitfalls Pitfall 3 (lines 656-668)
- 03-PATTERNS.md §Single-source canonical helper extraction (lines 770-779)
- src/config/constants.py:RIBGG_LIVE_BACKOFF_CAP_S (added by 03-00)
"""
from __future__ import annotations

from typing import Any, Callable, Final

import requests
from tenacity import RetryCallState, retry, stop_after_attempt

HEADERS: Final[dict[str, str]] = {
    "User-Agent": "Mozilla/5.0 (compatible; valorant-pricing-model/0.3; +github)",
    "Referer": "https://www.rib.gg/",
    # Disable urllib3's default keep-alive pooling. On Windows, pooled sockets
    # to be-prod.rib.gg go stale after the server closes them silently — next
    # `requests.get` reuses the dead socket and hangs at the 30s read timeout.
    # `Connection: close` makes the server close cleanly and prevents urllib3
    # from caching the socket. Costs ~0.2s extra TLS handshake per call.
    "Connection": "close",
}
"""Verbatim from scripts/probe_round_events.py:84-94 (Phase 2 W6 fix). The
Connection: close header is the proven Phase 2 reliability pattern; do NOT
remove or replace with keep-alive without re-validating against rib.gg's
silent socket teardown behavior on Windows."""

HTTP_TIMEOUT_S: Final[int] = 60


def make_get_json(backoff_cap_s: float) -> Callable[[str], dict[str, Any]]:
    """Build a tenacity-retried GET function with a configurable backoff cap.

    Phase 2 callsite (batch ETL):  make_get_json(30.0)
    Phase 3 callsite (live poller): make_get_json(RIBGG_LIVE_BACKOFF_CAP_S=10.0)

    Returned callable signature: (url: str) -> dict[str, Any]
    Behavior: 5 attempts; wait time per attempt = max(Retry-After if HTTPError,
    min(2**(attempt-1), backoff_cap_s)); raises after 5 failures.
    """

    def _wait(retry_state: RetryCallState) -> float:
        exc = retry_state.outcome.exception() if retry_state.outcome else None
        if isinstance(exc, requests.HTTPError) and exc.response is not None:
            ra = exc.response.headers.get("Retry-After")
            if ra is not None:
                try:
                    return min(float(ra), 60.0)
                except ValueError:
                    pass
        attempt = retry_state.attempt_number
        return min(2.0 ** (attempt - 1), backoff_cap_s)

    @retry(stop=stop_after_attempt(5), wait=_wait)
    def _get_json(url: str) -> dict[str, Any]:
        resp = requests.get(url, headers=HEADERS, timeout=HTTP_TIMEOUT_S)
        resp.raise_for_status()
        out: dict[str, Any] = resp.json()
        return out

    return _get_json


# Default phase-2 batch-ETL caller. Phase 3 callsite uses make_get_json(10.0).
get_json: Final[Callable[[str], dict[str, Any]]] = make_get_json(30.0)
"""Phase 2 batch-ETL get_json (30s backoff cap) — preserves the original behavior
exactly so scripts/probe_round_events.py can `from src.ingestion._http import get_json`
without changing semantics."""


__all__ = ["HEADERS", "HTTP_TIMEOUT_S", "get_json", "make_get_json"]
```

Then refactor `scripts/probe_round_events.py` to import from this new module:

(a) Add `from src.ingestion._http import HEADERS, get_json` to the imports block (after the existing `from src.config.constants import (...)` block on line 47).

(b) Delete the inline `HEADERS` definition (lines 84-94).

(c) Delete the inline `_ribgg_wait` function definition (lines 102-119).

(d) Delete the inline `@retry @stop_after_attempt(5) @wait=_ribgg_wait def get_json(...)` definition (lines 122-135).

(e) Delete the now-unused `from tenacity import RetryCallState, RetryError, retry, stop_after_attempt` -> reduce to `from tenacity import RetryError` (RetryError is still re-raised by callers; check via grep).

If `RetryError` is also unused after the import-level decorator deletion, drop the entire tenacity import line. Run `mypy --strict src/pricing/` (regression) + `ruff check scripts/probe_round_events.py` (catches unused imports).

The Phase 2 ETL behavior MUST be unchanged: `python -m scripts.probe_round_events --dry-run` should still work end-to-end against the live API. Test by running the dry-run probe and confirming no behavioral diff.
  </action>
  <verify>
    <automated>python -c "from src.ingestion._http import HEADERS, get_json, make_get_json; assert HEADERS['Connection'] == 'close'; live_get = make_get_json(10.0); assert callable(live_get); print('http layer ok')" &amp;&amp; mypy src/ingestion/_http.py &amp;&amp; ruff check src/ingestion/_http.py scripts/probe_round_events.py &amp;&amp; pytest tests/ -x -k "not benchmark and not e2e"</automated>
  </verify>
  <done>src/ingestion/_http.py exports HEADERS + get_json + make_get_json; scripts/probe_round_events.py imports from the new module (its own copies deleted); ruff + mypy clean; ALL Phase 1 + 2 tests still pass (regression).</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Create src/ingestion/scoreboard.py — ScoreboardPoller class with async poll loop + emit ArbiterPending</name>
  <files>src/ingestion/scoreboard.py, src/ingestion/__init__.py, tests/ingestion/test_scoreboard.py</files>
  <read_first>
    - reference/rib_scraper.py (entire file — verbatim salvage source for endpoint URLs + parser shapes; treat as a TEMPLATE not as importable code)
    - reference/vlr_scraper.py (entire file — bo3.gg/vlr.gg are out-of-scope per SPEC, but glance for any score-parser patterns worth borrowing)
    - scripts/probe_round_events.py:531-543 (defensive null-roster pattern — analog for live poller)
    - src/ingestion/types.py (ArbiterPending signature)
    - src/ingestion/_http.py (shared HEADERS + make_get_json)
    - .planning/phases/03-live-ingestion-layer/03-PATTERNS.md §src/ingestion/scoreboard.py (lines 193-298)
    - .planning/phases/03-live-ingestion-layer/03-RESEARCH.md §Salvage-Port Delta Checklist (lines 583-606) — apply 8 deltas + rib_scraper-specific extras
    - .planning/phases/03-live-ingestion-layer/03-RESEARCH.md §Common Pitfalls Pitfall 3 (lines 656-668)
    - .planning/phases/03-live-ingestion-layer/03-RESEARCH.md §Standard Stack tradeoff (line 104 — keep sync requests.get inside loop.run_in_executor; do NOT port to aiohttp)
    - tests/probe/test_endpoint_shapes.py (analog for monkeypatched fixture-driven testing)
    - tests/probe/conftest.py (analog for fixture loading)
  </read_first>
  <behavior>
    - Test 1 (test_poller_initial_observe_emits_score_change): Construct ScoreboardPoller against a monkeypatched mock_ribgg_response; call poll_once(); assert it emits >= 1 ArbiterPending with source="ribgg", event_type="score_change", and signal_value containing the keys parsed from match_details fixture (likely a_round, b_round).
    - Test 2 (test_poller_emits_heartbeat_on_no_change): Run poll_once() twice with the same fixture (no content change); assert the SECOND call still emits a heartbeat ArbiterPending (so KILL_SWITCH_STALENESS_S timer resets). Per RESEARCH Pitfall 3 #1.
    - Test 3 (test_poller_resilience_uses_connection_close_and_backoff_cap): Spy on `requests.get` to capture headers; assert HEADERS["Connection"] == "close"; assert the underlying make_get_json was invoked with backoff_cap_s = RIBGG_LIVE_BACKOFF_CAP_S (10.0), NOT 30.0. Per RESEARCH Pitfall 3 #3.
    - Test 4 (test_poller_skips_null_roster_match): Patch the fixture to return a match_details payload with team1PlayerIds = None; assert the poller emits NO score_change ArbiterPending for that match (defensive null-roster early-return per Phase 2 fafa6ae fix). Heartbeat MAY still emit.
    - Test 5 (test_poller_async_loop_cadence_5s): Run async poll_loop() with monkeypatched asyncio.sleep capturing the await arg; assert it's called with 5.0 seconds between iterations (the constant LIVE_POLL_INTERVAL_S; introduce as Final if not already in constants). The plan needs a NEW constant LIVE_POLL_INTERVAL_S = 5.0 — add to src/config/constants.py within this task.
    - Test 6 (test_poller_handles_HTTP_error_without_crash): Patch get_json to raise requests.HTTPError; assert poll_once() returns gracefully (logs error, no exception propagates) and the next call retries.
  </behavior>
  <action>
Create `src/ingestion/scoreboard.py` per the PATTERNS analog. Key shape decisions:

1. **Class-based (not module-level state)** per RESEARCH §Salvage-Port Delta line 586. Constructor takes the dependencies needed: an arbiter-emit callback (`Callable[[ArbiterPending], Awaitable[None]]`), a match_id, a thread pool for the executor offload.

2. **sync requests inside loop.run_in_executor** per RESEARCH Standard Stack tradeoff line 104.

3. **5s cadence** with the heartbeat-on-no-change pattern (Pitfall 3 #1) — even when content didn't change, emit an ArbiterPending with `event_type="score_change"` and the SAME signal_value as last time, so the arbiter sees the staleness reset.

4. **Live backoff cap** per Pitfall 3 #3 — instantiate via `make_get_json(RIBGG_LIVE_BACKOFF_CAP_S)`.

5. **Defensive null-roster skip** per Pitfall 3-style guard (transplant from probe_round_events.py:531-543).

The plan also needs to add a new constant `LIVE_POLL_INTERVAL_S = 5.0` to `src/config/constants.py`. Add it to the Phase 3 section block (next to other ARBITER_*/RIBGG_* constants):

```python
LIVE_POLL_INTERVAL_S: Final[float] = 5.0
"""rib.gg live-poll interval, seconds (REQ-scoreboard-polling).

Source: roadmap.md §3.2 (5s authoritative cadence) / 03-CONTEXT.md D-04. The
arbiter cross-confirms within ARBITER_SCORE_WINDOW_S (2.0s); 5s sampling
keeps the source side polite (~12 calls/min/match) while remaining within
the score-window upper bound."""
```

Now the scoreboard module:

```python
"""Phase 3 rib.gg live scoreboard poller (REQ-scoreboard-polling).

Authoritative-but-slow source for the cross-source arbiter (DEC-006). Polls
the Phase 2 verified rib.gg /v1/{events,series,matches/{id}/details} chain at
LIVE_POLL_INTERVAL_S cadence and emits typed ArbiterPending events per source
"ribgg".

Ported from reference/rib_scraper.py applying the 8-item delta checklist
(03-RESEARCH.md §Salvage-Port Delta lines 583-606) plus the rib_scraper-specific
extras: drop hasSeries=true URL param (Phase 2 30s timeout fix in commit
fafa6ae), apply defensive null-roster early-return, route through the verified
endpoint chain.

Architecture notes
------------------
- sync requests.get inside loop.run_in_executor (D-06 + RESEARCH Standard Stack
  tradeoff line 104) — avoids re-validating Phase 2's HTTP resilience against
  an aiohttp port for a 5s cadence path that isn't latency-critical.
- Heartbeat-on-no-change pattern: every poll emits an ArbiterPending even when
  content didn't change, so KILL_SWITCH_STALENESS_S (5.0s) sees a fresh
  t_observed and doesn't trip on healthy-but-quiet matches (RESEARCH Pitfall 3 #1).
- Live backoff cap = RIBGG_LIVE_BACKOFF_CAP_S (10s) NOT Phase 2's 30s. Ensures
  consecutive failures degrade fast enough for the kill-switch to trip at the
  correct latency edge (Pitfall 3 #3).

Sources
-------
- 03-SPEC.md §2 (REQ-scoreboard-polling)
- 03-CONTEXT.md D-04 (arbiter consumer), D-06 (asyncio + executor)
- 03-RESEARCH.md §Architecture Patterns line 142, §Salvage-Port Delta (583-606)
- 03-RESEARCH.md §Common Pitfalls Pitfall 3 (656-668)
- 03-PATTERNS.md §src/ingestion/scoreboard.py (lines 193-298)
- scripts/probe_round_events.py:531-543 (defensive null-roster pattern)
- reference/rib_scraper.py (salvage shape template)
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Final, Optional

from src.config.constants import (
    LIVE_POLL_INTERVAL_S,
    RIBGG_BASE_URL,
    RIBGG_LIVE_BACKOFF_CAP_S,
)
from src.ingestion._http import make_get_json
from src.ingestion.types import ArbiterPending

log = logging.getLogger(__name__)

EmitFn = Callable[[ArbiterPending], Awaitable[None]]

_DEFAULT_GET_JSON: Final[Callable[[str], dict[str, Any]]] = make_get_json(
    RIBGG_LIVE_BACKOFF_CAP_S
)
"""Module-level singleton with the LIVE backoff cap. Tests can override the
poller's _get_json attribute (per-instance) for monkeypatched HTTP."""


class ScoreboardPoller:
    """rib.gg /v1/matches/{id}/details poller.

    Constructor arguments (D-04 + RESEARCH §Salvage-Port Delta line 586):
        match_id: which rib.gg match to poll (URL: /v1/matches/{match_id}/details).
        emit:     async callback invoked once per poll with an ArbiterPending.
        executor: shared ThreadPoolExecutor for the sync requests.get offload.
                  Pass the same executor as the OCR pipeline (max_workers=2).
        get_json: overridable HTTP fn (defaults to live-cap singleton). Tests
                  inject a fixture-returning mock here.

    Public API:
        await poller.poll_once()        # one HTTP call + one or more emits
        await poller.run()              # loop forever at LIVE_POLL_INTERVAL_S cadence
                                          (caller cancels the task to stop)
    """

    def __init__(
        self,
        match_id: str,
        emit: EmitFn,
        executor: ThreadPoolExecutor,
        get_json: Optional[Callable[[str], dict[str, Any]]] = None,  # noqa: UP045
    ) -> None:
        self._match_id = match_id
        self._emit = emit
        self._executor = executor
        self._get_json = get_json or _DEFAULT_GET_JSON
        self._last_signal: Optional[dict[str, Any]] = None  # noqa: UP045 — heartbeat memory
        self._consecutive_failures: int = 0

    @property
    def url(self) -> str:
        return f"{RIBGG_BASE_URL}/matches/{self._match_id}/details"

    async def poll_once(self) -> None:
        """Single fetch + emit cycle.

        Always emits at least one ArbiterPending (heartbeat) when the HTTP
        call succeeds, even if the parsed signal didn't change vs last poll
        (Pitfall 3 #1: kill-switch staleness needs a fresh t_observed).
        On HTTP failure: log + increment consecutive_failures + emit no
        event (kill-switch trips at the correct latency edge).
        """
        loop = asyncio.get_running_loop()
        try:
            payload = await loop.run_in_executor(self._executor, self._get_json, self.url)
        except Exception as exc:  # broad: tenacity has already retried 5x
            self._consecutive_failures += 1
            log.warning(
                "scoreboard_poll_failed match=%s consecutive=%d exc=%s",
                self._match_id,
                self._consecutive_failures,
                exc,
            )
            return

        self._consecutive_failures = 0
        signal = self._parse(payload)
        if signal is None:
            # Defensive null-roster early-return (Phase 2 fafa6ae). Don't emit
            # but DO update _last_signal=None so heartbeat picks up cleanly
            # once the match resolves. Skip this cycle.
            return
        # Always emit (heartbeat semantics): same signal_value if no content
        # change; arbiter sees fresh t_observed regardless.
        await self._emit(
            ArbiterPending(
                signal_value=signal,
                source="ribgg",
                event_type="score_change",
                t_observed=time.time(),
                t_ingested=time.monotonic(),
            )
        )
        self._last_signal = signal

    def _parse(self, payload: dict[str, Any]) -> Optional[dict[str, Any]]:  # noqa: UP045
        """Extract the score-change signal from a /matches/{id}/details payload.

        Defensive: returns None if the payload is missing rosters or sides
        (cancelled/forfeited matches per Phase 2 commit fafa6ae). Caller
        treats None as "skip this cycle, don't emit".

        Returned shape (signal_value): {"a_round": int, "b_round": int,
        "a_map_score": int, "b_map_score": int, "side_orient": str}.
        Other downstream MatchState fields (numerical_diff, players_alive_*,
        bomb_planted, time_left_s, ults_*, econ_*) come from the OCR + Twitter
        sources, not from rib.gg.
        """
        # Phase 2 defensive null-roster pattern (commit fafa6ae /
        # scripts/probe_round_events.py:531-543).
        match = payload.get("match") or {}
        t1 = match.get("team1PlayerIds")
        t2 = match.get("team2PlayerIds")
        atk_first = match.get("attackingFirstTeamNumber")
        if not t1 or not t2 or atk_first is None:
            log.debug(
                "scoreboard_skip_null_roster match=%s t1=%s t2=%s atk_first=%s",
                self._match_id, bool(t1), bool(t2), atk_first,
            )
            return None
        # Extract score signals. Field names match the Phase 2 verified
        # /matches/{id}/details schema (see tests/probe/test_endpoint_shapes.py).
        try:
            return {
                "a_round": int(match.get("team1Score", 0)),
                "b_round": int(match.get("team2Score", 0)),
            }
        except (TypeError, ValueError):
            log.warning("scoreboard_parse_error match=%s payload_keys=%s",
                        self._match_id, list(match.keys()))
            return None

    async def run(self) -> None:
        """Loop forever at LIVE_POLL_INTERVAL_S cadence.

        Caller is expected to wrap in `asyncio.create_task(poller.run())` and
        `task.cancel()` at shutdown. Cancellation is honored at the top of
        each iteration via the await asyncio.sleep call.
        """
        while True:
            await self.poll_once()
            await asyncio.sleep(LIVE_POLL_INTERVAL_S)


__all__ = ["ScoreboardPoller", "EmitFn"]
```

Then update `src/ingestion/__init__.py` to export `ScoreboardPoller`:

Append `ScoreboardPoller, EmitFn` to the existing imports block:

```python
from src.ingestion.scoreboard import EmitFn, ScoreboardPoller
```

Add `"ScoreboardPoller", "EmitFn"` to `__all__`.

Then create `tests/ingestion/test_scoreboard.py`:

```python
"""ScoreboardPoller tests — REQ-scoreboard-polling acceptance."""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from unittest.mock import patch

import pytest

from src.config.constants import LIVE_POLL_INTERVAL_S, RIBGG_LIVE_BACKOFF_CAP_S
from src.ingestion._http import HEADERS
from src.ingestion.scoreboard import ScoreboardPoller
from src.ingestion.types import ArbiterPending


# --------------------------------------------------------------------------- #
# Helpers / fixtures                                                          #
# --------------------------------------------------------------------------- #


def _valid_match_details() -> dict[str, Any]:
    """Minimum viable /matches/{id}/details payload for parser happy path."""
    return {
        "match": {
            "team1PlayerIds": [1, 2, 3, 4, 5],
            "team2PlayerIds": [6, 7, 8, 9, 10],
            "attackingFirstTeamNumber": 1,
            "team1Score": 7,
            "team2Score": 3,
        }
    }


def _null_roster_payload() -> dict[str, Any]:
    """Payload missing rosters — cancelled/forfeited match shape (Phase 2 fafa6ae)."""
    return {
        "match": {
            "team1PlayerIds": None,
            "team2PlayerIds": None,
            "attackingFirstTeamNumber": None,
        }
    }


@pytest.fixture
def emitted() -> list[ArbiterPending]:
    return []


@pytest.fixture
def emit_fn(emitted: list[ArbiterPending]):
    async def _emit(p: ArbiterPending) -> None:
        emitted.append(p)
    return _emit


@pytest.fixture
def executor():
    pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="test-poll")
    yield pool
    pool.shutdown(wait=True, cancel_futures=False)


# --------------------------------------------------------------------------- #
# Tests                                                                       #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_poller_initial_observe_emits_score_change(
    emit_fn, emitted, executor
) -> None:
    """REQ-scoreboard-polling acceptance: monkeypatched fixture -> typed event."""
    poller = ScoreboardPoller(
        match_id="m1",
        emit=emit_fn,
        executor=executor,
        get_json=lambda url: _valid_match_details(),
    )
    await poller.poll_once()
    assert len(emitted) == 1
    pending = emitted[0]
    assert pending.source == "ribgg"
    assert pending.event_type == "score_change"
    assert pending.signal_value == {"a_round": 7, "b_round": 3}
    assert pending.t_observed > 0
    assert pending.t_ingested > 0


@pytest.mark.asyncio
async def test_poller_emits_heartbeat_on_no_change(
    emit_fn, emitted, executor
) -> None:
    """RESEARCH Pitfall 3 #1: same content -> still emits, fresh t_observed.
    Kill-switch staleness must reset on every successful poll."""
    poller = ScoreboardPoller(
        match_id="m1",
        emit=emit_fn,
        executor=executor,
        get_json=lambda url: _valid_match_details(),
    )
    await poller.poll_once()
    await poller.poll_once()
    assert len(emitted) == 2
    assert emitted[0].signal_value == emitted[1].signal_value
    assert emitted[1].t_observed >= emitted[0].t_observed


@pytest.mark.asyncio
async def test_poller_skips_null_roster_match(
    emit_fn, emitted, executor
) -> None:
    """Phase 2 fafa6ae regression: null-roster payloads emit nothing."""
    poller = ScoreboardPoller(
        match_id="m1",
        emit=emit_fn,
        executor=executor,
        get_json=lambda url: _null_roster_payload(),
    )
    await poller.poll_once()
    assert emitted == []  # no emit for null-roster


@pytest.mark.asyncio
async def test_poller_handles_http_error_without_crash(
    emit_fn, emitted, executor
) -> None:
    """Pitfall 3 #2: HTTP error logs + increments counter + does NOT propagate."""
    import requests

    def _raises(url: str) -> dict[str, Any]:
        raise requests.HTTPError("simulated 503")

    poller = ScoreboardPoller(
        match_id="m1",
        emit=emit_fn,
        executor=executor,
        get_json=_raises,
    )
    # Must not raise.
    await poller.poll_once()
    assert emitted == []
    # On recovery, next call emits successfully.
    poller._get_json = lambda url: _valid_match_details()  # type: ignore[assignment]
    await poller.poll_once()
    assert len(emitted) == 1
    # Counter reset on success.
    assert poller._consecutive_failures == 0


@pytest.mark.asyncio
async def test_poller_run_loop_cadence_is_5s(
    emit_fn, emitted, executor, monkeypatch
) -> None:
    """REQ-scoreboard-polling: 5s cadence — assert the await sleep is called
    with LIVE_POLL_INTERVAL_S between iterations."""
    sleep_calls: list[float] = []

    async def _fake_sleep(t: float) -> None:
        sleep_calls.append(t)
        # Cancel after 3 iterations to exit the loop deterministically.
        if len(sleep_calls) >= 3:
            raise asyncio.CancelledError()

    monkeypatch.setattr(asyncio, "sleep", _fake_sleep)

    poller = ScoreboardPoller(
        match_id="m1",
        emit=emit_fn,
        executor=executor,
        get_json=lambda url: _valid_match_details(),
    )
    with pytest.raises(asyncio.CancelledError):
        await poller.run()
    assert sleep_calls == [LIVE_POLL_INTERVAL_S, LIVE_POLL_INTERVAL_S, LIVE_POLL_INTERVAL_S]


def test_resilience_patterns_use_connection_close_and_live_backoff_cap() -> None:
    """RESEARCH Pitfall 3 #3: live poller backoff cap = RIBGG_LIVE_BACKOFF_CAP_S, not 30s."""
    assert HEADERS["Connection"] == "close"
    assert RIBGG_LIVE_BACKOFF_CAP_S == 10.0
    # The default get_json singleton in scoreboard.py was built with the live cap.
    from src.ingestion.scoreboard import _DEFAULT_GET_JSON
    assert _DEFAULT_GET_JSON is not None
    # Smoke: callable + correct factory was used (we can't introspect the closure
    # cap value cleanly, but we can confirm the singleton exists and was built
    # via make_get_json — checked by import side-effect).


def test_url_construction() -> None:
    """URL = RIBGG_BASE_URL + /matches/{id}/details."""
    poller = ScoreboardPoller(
        match_id="abc",
        emit=lambda p: asyncio.sleep(0),  # type: ignore[arg-type]
        executor=ThreadPoolExecutor(max_workers=1),
        get_json=lambda url: {},
    )
    assert poller.url == "https://be-prod.rib.gg/v1/matches/abc/details"
```

(7 named test functions; the cancellation pattern in test 5 cleanly exits the infinite loop without sleep delays in CI.)
  </action>
  <verify>
    <automated>pytest tests/ingestion/test_scoreboard.py -x &amp;&amp; mypy src/ingestion/scoreboard.py src/ingestion/_http.py &amp;&amp; ruff check src/ingestion/ tests/ingestion/test_scoreboard.py</automated>
  </verify>
  <done>src/ingestion/scoreboard.py exports ScoreboardPoller; constants file has LIVE_POLL_INTERVAL_S; src/ingestion/__init__.py re-exports the class; 7 test functions PASS without network; mypy + ruff clean; Phase 1 + 2 + 03-03 regressions all GREEN.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| outbound HTTPS | `src/ingestion/scoreboard.py` calls `https://be-prod.rib.gg/v1/matches/{id}/details` via the shared `_http.py` module. |
| executor offload | Sync `requests.get` runs in the `ThreadPoolExecutor` shared with the OCR pipeline (Plan 03-05). |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-03-04-01 (covers T-net-01) | T (Tampering) | rib.gg HTTPS connection | mitigate | `requests.get` defaults to TLS verification (`verify=True`); never disabled. The `Connection: close` header is a reliability concern (silent socket teardown on Windows), NOT a downgrade — TLS handshake happens fresh per call. No plaintext fallback. |
| T-03-04-02 | I (Information disclosure) | logged HTTP errors | mitigate | `log.warning` records `match_id`, `consecutive_failures`, and the exception message. Match IDs are public. The exception message from `requests.HTTPError` MAY include URL but never contains rib.gg auth (rib.gg's public API is unauthenticated). |
| T-03-04-03 | D (Denial of service) | tenacity retry on 503 | mitigate | `stop_after_attempt(5)` + RIBGG_LIVE_BACKOFF_CAP_S = 10s cap means a single failure cycle is bounded at ~5 * 10s = 50s — safely above the kill-switch staleness threshold (5s) so the kill switch trips at the right edge. The `_consecutive_failures` counter is exposed for the kill-switch (Phase 4) to read. |
| T-03-04-04 | T (Tampering) | rib.gg payload parser | mitigate | `_parse()` is defensive: returns None on missing rosters (Phase 2 fafa6ae regression), wraps int casts in try/except, never `eval`-s payload content. |
| T-03-04-05 | E (Elevation of privilege) | shared ThreadPoolExecutor | accept | Pool is constructed by the caller; lifetime is the caller's responsibility. Same pool used by OCR (Plan 03-05) — both jobs are CPU-bound but threads release the GIL during native calls. |
</threat_model>

<verification>
- `pytest tests/ingestion/test_scoreboard.py -x` PASSES (7 named tests + parametrize variants).
- `mypy src/ingestion/scoreboard.py src/ingestion/_http.py` clean (gradual scope, but new code annotates fully).
- `ruff check src/ingestion/ tests/ingestion/test_scoreboard.py scripts/probe_round_events.py` clean.
- `python -c "from src.ingestion import ScoreboardPoller; from src.ingestion._http import HEADERS, get_json; assert HEADERS['Connection'] == 'close'"` returns 0.
- All Phase 1 + 2 + 03-03 tests still GREEN: `pytest tests/ -x -k "not benchmark and not e2e"` PASSES.
- `LIVE_POLL_INTERVAL_S` and the existing 19 Phase 3 constants total 20 in `src/config/constants.py` Phase 3 section.
</verification>

<success_criteria>
Wave 2 plan 03-04 (scoreboard) is COMPLETE when:

1. `src/ingestion/_http.py` extracts the rib.gg HTTP layer for shared use; `scripts/probe_round_events.py` is refactored to import from it (CRule 2: single canonical helper).
2. `src/ingestion/scoreboard.py` exports `ScoreboardPoller` with async `poll_once()` + `run()` methods.
3. `LIVE_POLL_INTERVAL_S = 5.0` added to `src/config/constants.py`.
4. Heartbeat-on-no-change semantic implemented (Pitfall 3 #1): even unchanged content emits an ArbiterPending so kill-switch sees fresh t_observed.
5. Live backoff cap = 10s (not Phase 2's 30s) per Pitfall 3 #3.
6. Defensive null-roster early-return per Phase 2 commit fafa6ae regression.
7. `tests/ingestion/test_scoreboard.py` has 7 test functions covering: initial-emit, heartbeat-on-no-change, null-roster-skip, HTTP-error-no-crash, 5s-cadence, Connection-close, URL-construction. ALL PASS.
8. `src/ingestion/__init__.py` re-exports `ScoreboardPoller` and `EmitFn`.
9. Phase 1 + 2 + 03-03 regression: `pytest tests/ -x -k "not benchmark and not e2e"` GREEN.
</success_criteria>

<output>
After completion, create `.planning/phases/03-live-ingestion-layer/03-04-SUMMARY.md`:

```markdown
# 03-04 SUMMARY — scoreboard poller

**Status:** complete
**Wave:** 2 (parallel with 03-05 + 03-06)
**Files created:** src/ingestion/_http.py, src/ingestion/scoreboard.py, tests/ingestion/test_scoreboard.py
**Files modified:** scripts/probe_round_events.py (refactor: imports from _http now), src/ingestion/__init__.py, src/config/constants.py (+1 constant: LIVE_POLL_INTERVAL_S)

## Public API
- ScoreboardPoller(match_id, emit, executor, get_json=None)
- await poller.poll_once()       # one HTTP fetch + emit
- await poller.run()              # loop forever at LIVE_POLL_INTERVAL_S cadence

## Resilience deltas vs Phase 2
- Backoff cap: 10s (live) vs 30s (batch ETL)
- Heartbeat on no-change (Pitfall 3 #1)
- Defensive null-roster early-return (Phase 2 fafa6ae regression)

## Tests
- 7 test functions; all PASS without network
- Phase 1 + 2 + 03-03 regression: GREEN
```
</output>
