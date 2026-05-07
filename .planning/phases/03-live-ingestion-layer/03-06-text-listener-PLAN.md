---
phase: 03-live-ingestion-layer
plan: "06"
type: execute
wave: 4
depends_on: ["03-01"]
files_modified:
  - src/ingestion/text_listener.py
  - src/ingestion/__init__.py
  - src/config/constants.py
  - tests/ingestion/test_text_listener.py
autonomous: true
requirements:
  - REQ-text-listener
notes: |
  Wave 4D — Twitter v2 streaming text listener (REQ-text-listener). Soft
  cross-confirmation source ONLY — never sole-source per SPEC §4. Built on
  tweepy.AsyncStreamingClient (RESEARCH §"Pattern 5"). Degrades to no-op when
  TWITTER_BEARER_TOKEN env var is empty/unset (SPEC test_no_token_noop).

  Runs in PARALLEL with 03-03/04/05. Depends only on 03-01. Pushes
  PendingEvents into the arbiter's score_changes deque tagged source="twitter";
  the arbiter's ≥2-source rule ensures Twitter alone never commits state.

  RESEARCH Pitfall 1: Twitter API Basic tier ($200/mo) deprecated 2026-02-06
  for new accounts. Treat the listener as PERMANENTLY DEGRADED for new
  accounts — module docstring documents this. CI runs without
  TWITTER_BEARER_TOKEN set; test_no_token_noop verifies the no-op path.

  Test that Twitter alone can NEVER commit state lives in the arbiter test
  suite (03-03's test_score_change_two_source_rule asserts single-source =
  no commit; this plan's test_twitter_only_update_quarantined adds a
  Twitter-specific stress test for the same property).

must_haves:
  truths:
    - "src/ingestion/text_listener.py exposes async run_text_listener(arbiter) coroutine"
    - "When TWITTER_BEARER_TOKEN env is empty/unset, run_text_listener returns immediately without raising (logs structured warning)"
    - "When TWITTER_BEARER_TOKEN is set, listener constructs tweepy.AsyncStreamingClient with TWITTER_RULE_SET rules and pushes PendingEvent(source='twitter', event_type='score_change_soft') on tweet matches"
    - "Arbiter NEVER commits a state change based ONLY on a Twitter event (Twitter is single-source soft-confirm only)"
    - "TWITTER_RULE_SET constant pinned in src/config/constants.py with 5 hashtag rules + operator-pinned VCT 2026 caster/league accounts"
  artifacts:
    - path: "src/ingestion/text_listener.py"
      provides: "tweepy.AsyncStreamingClient-based listener with degrade-to-no-op + score-signal regex parsing"
      contains: "run_text_listener"
      min_lines: 120
    - path: "src/config/constants.py"
      provides: "TWITTER_RULE_SET tuple + TWITTER_API_BASE_URL"
      contains: "TWITTER_RULE_SET"
    - path: "tests/ingestion/test_text_listener.py"
      provides: "GREEN test_emits_typed_soft_events + test_twitter_only_update_quarantined + test_no_token_noop"
      contains: "test_no_token_noop"
  key_links:
    - from: "src/ingestion/text_listener.py:run_text_listener"
      to: "TWITTER_BEARER_TOKEN env gate"
      via: "if not os.environ.get('TWITTER_BEARER_TOKEN', '').strip(): logger.warning(...); return"
      pattern: "TWITTER_BEARER_TOKEN"
    - from: "src/ingestion/text_listener.py listener"
      to: "arbiter.score_changes deque"
      via: "arbiter.score_changes.append(PendingEvent(source='twitter', ...))"
      pattern: "source=.twitter."
---

<objective>
Land the Twitter v2 streaming text listener (REQ-text-listener). Soft
cross-confirm source built on tweepy.AsyncStreamingClient. Degrades to no-op
when TWITTER_BEARER_TOKEN env var is unset (default on CI + new accounts
post-2026-02-06 deprecation).

Purpose: Twitter is the ONLY 3rd source the arbiter has for cross-confirming
score changes (after rib.gg + OCR). Even if Twitter is permanently degraded
for new accounts, the SPEC explicitly requires the listener to construct
cleanly with empty token (test_no_token_noop) so existing-account operators
can opt in by setting the env var without code changes.

Output:
- src/ingestion/text_listener.py (~150 LOC: env-gated init + tweepy subclass + score-signal parsing)
- 2 new constants in src/config/constants.py
- 3 GREEN tests
</objective>

<execution_context>
@C:/Users/Joseph Cheng/.claude/get-shit-done/workflows/execute-plan.md
@C:/Users/Joseph Cheng/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/phases/03-live-ingestion-layer/03-SPEC.md
@.planning/phases/03-live-ingestion-layer/03-CONTEXT.md
@.planning/phases/03-live-ingestion-layer/03-RESEARCH.md
@.planning/phases/03-live-ingestion-layer/03-VALIDATION.md
@.planning/phases/03-live-ingestion-layer/03-01-match-state-v2-migration-PLAN.md
@.planning/phases/03-live-ingestion-layer/03-03-arbiter-and-latency-PLAN.md
@src/config/constants.py

<interfaces>
src/ingestion/text_listener.py target shape (RESEARCH §"Pattern 5"):

```python
import os
import re
import asyncio
import logging
import tweepy
from src.config.constants import TWITTER_RULE_SET
from src.ingestion.arbiter import Arbiter
from src.ingestion.events import PendingEvent
from src.ingestion.timestamps import mono_ns, wall_time

logger = logging.getLogger(__name__)

# Score signal patterns: "13-9", "13:9", "T1 wins map 1 13-9", etc.
_SCORE_PATTERN = re.compile(r"\b(\d{1,2})\s*[-:]\s*(\d{1,2})\b")


class _MatchSignalListener(tweepy.AsyncStreamingClient):
    def __init__(self, bearer_token: str, arbiter: Arbiter) -> None:
        super().__init__(bearer_token=bearer_token, return_type=dict)
        self._arbiter = arbiter

    def _parse_score(self, text: str) -> dict[str, int] | None:
        m = _SCORE_PATTERN.search(text)
        if m is None:
            return None
        a, b = int(m.group(1)), int(m.group(2))
        if a > 13 or b > 13:  # Valorant max round count is 13 in regulation
            return None
        return {"a_round": a, "b_round": b}

    async def on_tweet(self, tweet: dict) -> None:
        text = tweet.get("text", "") if isinstance(tweet, dict) else ""
        signal = self._parse_score(text)
        if signal is None:
            return
        # NEVER sole-source — push as soft confirm only
        self._arbiter.score_changes.append(PendingEvent(
            source="twitter",
            event_type="score_change",
            fields_proposed=signal,
            t_observed=wall_time(),
            t_ingested=mono_ns(),
        ))


async def run_text_listener(arbiter: Arbiter) -> None:
    token = os.environ.get("TWITTER_BEARER_TOKEN", "").strip()
    if not token:
        logger.warning(
            "TWITTER_BEARER_TOKEN absent — text listener degrades to no-op "
            "(RESEARCH Pitfall 1: Twitter Basic tier deprecated 2026-02-06 "
            "for new accounts; arbiter still satisfies ≥2-source rule via "
            "rib.gg + OCR cross-confirm)."
        )
        return  # SPEC §4 acceptance: test_no_token_noop

    listener = _MatchSignalListener(bearer_token=token, arbiter=arbiter)
    # Add static rules from constants.TWITTER_RULE_SET (de-dup against existing rules first)
    existing_rules_resp = await listener.get_rules()
    existing_ids = []
    if existing_rules_resp and existing_rules_resp.get("data"):
        existing_ids = [r["id"] for r in existing_rules_resp["data"]]
    if existing_ids:
        await listener.delete_rules(existing_ids)
    await listener.add_rules([tweepy.StreamRule(value=q) for q in TWITTER_RULE_SET])
    await listener.filter()  # blocks until cancelled
```

Constants to add (RESEARCH §"Constants to Add"):
```python
TWITTER_API_BASE_URL: Final[str] = "https://api.twitter.com/2"

TWITTER_RULE_SET: Final[tuple[str, ...]] = (
    "#VCT", "#VALORANTChampions",
    "#VCTAmericas", "#VCTEMEA", "#VCTPacific",
    # Operator-pinned 2026-season caster/league/team-org accounts:
    "from:ValorantEsports",
    "from:VCT_Americas",
    "from:VCT_EMEA",
    "from:VCT_Pacific",
)
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add Twitter constants + create src/ingestion/text_listener.py with degrade-to-no-op</name>
  <files>
    src/config/constants.py
    src/ingestion/text_listener.py
    src/ingestion/__init__.py
  </files>
  <behavior>
    - 2 new constants in src/config/constants.py: TWITTER_API_BASE_URL, TWITTER_RULE_SET (tuple of 9 rules per <interfaces>).
    - src/ingestion/text_listener.py exposes:
        - `_SCORE_PATTERN` regex matching "N-N" or "N:N" formats (N = 1-2 digits, ≤ 13).
        - `_MatchSignalListener(tweepy.AsyncStreamingClient)` subclass with `_parse_score(text) -> dict | None` and `async def on_tweet(tweet)` per <interfaces>.
        - `run_text_listener(arbiter) -> None` async function: env-gates on TWITTER_BEARER_TOKEN; returns immediately with warning log if empty; otherwise constructs listener, syncs rules, calls `await listener.filter()`.
        - Module docstring documents RESEARCH Pitfall 1 (Twitter Basic tier deprecation).
    - src/ingestion/__init__.py re-exports `run_text_listener`.
    - mypy src/ingestion/ — 0 errors.
  </behavior>
  <action>
1) Append 2 constants to `src/config/constants.py` in the Phase 3 ingestion section:

```python
TWITTER_API_BASE_URL: Final[str] = "https://api.twitter.com/2"
"""Twitter API v2 base URL. Used by tweepy.AsyncStreamingClient under the hood;
referenced here only for module-init sanity checks."""

TWITTER_RULE_SET: Final[tuple[str, ...]] = (
    "#VCT",
    "#VALORANTChampions",
    "#VCTAmericas",
    "#VCTEMEA",
    "#VCTPacific",
    # Operator-pinned 2026-season caster/league/team-org accounts.
    # CONTEXT D-07 carry-forward; researcher-pinned per RESEARCH §"Code Examples".
    "from:ValorantEsports",
    "from:VCT_Americas",
    "from:VCT_EMEA",
    "from:VCT_Pacific",
)
"""Static rule set for tweepy.AsyncStreamingClient filter (REQ-text-listener).

Twitter API v2 streaming rules — added once at listener init via add_rules.
Operator can extend by editing this tuple + redeploying. Per-match dynamic
rule sync is deferred (CONTEXT 'Deferred Ideas' / RESEARCH §"Open Questions").
"""
```

2) Create `src/ingestion/text_listener.py` (~150 LOC):

```python
"""Twitter v2 streaming text listener (REQ-text-listener / 03-CONTEXT D-07).

Soft cross-confirm source ONLY — NEVER sole-source per SPEC §4. The arbiter's
≥2-source rule ensures a Twitter event alone cannot commit state; rib.gg or
OCR must provide the other source within ARBITER_SCORE_WINDOW_S (2s).

PERMANENT DEGRADATION (RESEARCH Pitfall 1):
- Twitter API Basic tier ($200/mo) deprecated 2026-02-06 for new accounts.
- New developers cannot subscribe — pay-per-use only.
- Default deployment has no TWITTER_BEARER_TOKEN env var; this listener
  degrades to no-op silently (logger.warning emitted on startup).
- Arbiter still satisfies ≥2-source rule via rib.gg + OCR cross-confirm; the
  listener is opt-in for operators with pre-2026-02-06 Basic-tier accounts.

Surface:
- run_text_listener(arbiter): env-gated init; if TWITTER_BEARER_TOKEN empty,
  returns immediately. Otherwise constructs _MatchSignalListener, syncs static
  rules from TWITTER_RULE_SET, and calls listener.filter() to block on the
  stream until cancelled (asyncio.TaskGroup teardown).

NEVER:
- Push to bomb_events or round_end_events deques (Twitter signal-quality is too
  noisy for those event types per SPEC §5).
- Construct without the env gate (raise on missing token would break
  test_no_token_noop and the default CI deployment).
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any

import tweepy

from src.config.constants import TWITTER_RULE_SET
from src.ingestion.arbiter import Arbiter
from src.ingestion.events import PendingEvent
from src.ingestion.timestamps import mono_ns, wall_time

logger = logging.getLogger(__name__)

# Score signal patterns from tweet text: "13-9", "13:9", "13 - 9", etc.
# Anchored on word boundaries to avoid matching dates / years / mentions.
_SCORE_PATTERN = re.compile(r"\b(\d{1,2})\s*[-:]\s*(\d{1,2})\b")


class _MatchSignalListener(tweepy.AsyncStreamingClient):
    """tweepy AsyncStreamingClient subclass that pushes soft-confirm score events."""

    def __init__(self, bearer_token: str, arbiter: Arbiter) -> None:
        super().__init__(bearer_token=bearer_token, return_type=dict)
        self._arbiter = arbiter

    def _parse_score(self, text: str) -> dict[str, int] | None:
        """Extract (a_round, b_round) from tweet text; None if no valid match."""
        m = _SCORE_PATTERN.search(text)
        if m is None:
            return None
        a, b = int(m.group(1)), int(m.group(2))
        # Reject impossible scores (max 13 in regulation per WIN_THRESHOLD).
        # Loose bound — Twitter posts about OT scores are rare and noisy enough
        # to drop without harm.
        if a > 13 or b > 13:
            return None
        return {"a_round": a, "b_round": b}

    async def on_tweet(self, tweet: Any) -> None:
        """tweepy callback per matching tweet."""
        text = tweet.get("text", "") if isinstance(tweet, dict) else ""
        signal = self._parse_score(text)
        if signal is None:
            return
        # SOFT-CONFIRM ONLY — arbiter's ≥2-source rule guards the commit.
        self._arbiter.score_changes.append(PendingEvent(
            source="twitter",
            event_type="score_change",
            fields_proposed=signal,
            t_observed=wall_time(),
            t_ingested=mono_ns(),
        ))


async def run_text_listener(arbiter: Arbiter) -> None:
    """Long-running Twitter v2 streaming listener; degrades to no-op without token.

    Designed to fail SILENTLY on missing token (warning log only) so the
    arbiter's other 2 sources (rib.gg + OCR) remain unaffected. Caller wraps
    this in asyncio.TaskGroup; cancellation breaks listener.filter().
    """
    token = os.environ.get("TWITTER_BEARER_TOKEN", "").strip()
    if not token:
        logger.warning(
            "TWITTER_BEARER_TOKEN absent — text listener degrades to no-op "
            "(RESEARCH Pitfall 1: Twitter Basic tier deprecated 2026-02-06)."
        )
        return  # SPEC §4 acceptance: test_no_token_noop

    listener = _MatchSignalListener(bearer_token=token, arbiter=arbiter)

    # Sync rules — clear any existing rules from prior runs, install static set
    try:
        existing = await listener.get_rules()
        if existing and isinstance(existing, dict) and existing.get("data"):
            ids = [r["id"] for r in existing["data"] if "id" in r]
            if ids:
                await listener.delete_rules(ids)
        await listener.add_rules([tweepy.StreamRule(value=q) for q in TWITTER_RULE_SET])
    except Exception as exc:
        logger.warning("Twitter rule sync failed (%s) — proceeding anyway", exc)

    # Block on the stream; TaskGroup cancellation tears this down.
    await listener.filter()
```

3) Update `src/ingestion/__init__.py` to re-export `run_text_listener`:
```python
from src.ingestion.text_listener import run_text_listener
# add to __all__
```

Atomic commit message: `feat(03-06): Twitter v2 streaming text listener with degrade-to-no-op (REQ-text-listener)`
  </action>
  <verify>
    <automated>uv run python -c "from src.ingestion.text_listener import run_text_listener, _MatchSignalListener, _SCORE_PATTERN; from src.config.constants import TWITTER_RULE_SET, TWITTER_API_BASE_URL; assert len(TWITTER_RULE_SET) >= 5; assert TWITTER_API_BASE_URL.startswith('https://'); print('text_listener imports ok')" && uv run mypy src/ingestion/ && uv run ruff check src/ingestion/</automated>
  </verify>
  <done>
- 2 constants exist in src/config/constants.py.
- src/ingestion/text_listener.py exists with run_text_listener + _MatchSignalListener + _SCORE_PATTERN + _parse_score.
- Re-exports work.
- mypy src/ingestion/ — 0 errors.
- ruff check — clean.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: GREEN test_text_listener — emits soft-events + Twitter-only quarantines + no-token-noop</name>
  <files>
    tests/ingestion/test_text_listener.py
  </files>
  <behavior>
    - tests/ingestion/test_text_listener.py (RED stubs from 03-00) all GREEN:
        - `test_emits_typed_soft_events`: build an Arbiter via conftest fixture; build a `_MatchSignalListener` instance with bearer_token="dummy" and the arbiter; directly call `await listener.on_tweet({"text": "T1 takes Lotus 13-9 vs Sentinels"})`. Assert exactly 1 PendingEvent appears in `arbiter.score_changes` with `source="twitter"`, `event_type="score_change"`, `fields_proposed={"a_round": 13, "b_round": 9}`. Then call `await listener.on_tweet({"text": "good game!"})` (no score signal); assert deque length unchanged.
        - `test_twitter_only_update_quarantined`: build Arbiter; push a single Twitter PendingEvent to arbiter.score_changes; call `arbiter.tick()` ONCE; assert state UNCHANGED (single source < 2-source rule); event remains in deque (held for cross-confirm). Then advance wall clock past _DEQUE_MAX_AGE_S (3s) by patching `arbiter._drain_score_changes` evaluation OR by manually constructing a stale event (`t_observed = wall_time() - 10`) and calling tick — assert the JSONL log has a quarantine line with `source: "twitter", quarantined: true`.
        - `test_no_token_noop`: ensure `TWITTER_BEARER_TOKEN` is empty/unset (use `monkeypatch.delenv` and `monkeypatch.setenv("TWITTER_BEARER_TOKEN", "")`); call `await run_text_listener(arbiter)`; assert it returns within reasonable time (< 1s) without raising any exception.
    - All tests use `@pytest.mark.asyncio`.
  </behavior>
  <action>
1) Wire `tests/ingestion/test_text_listener.py` (RED stubs from 03-00) to GREEN:

```python
"""REQ-text-listener — Twitter v2 streaming listener tests (03-06)."""
import asyncio
import json
import time
import pytest

from src.ingestion import Arbiter, mono_ns, wall_time
from src.ingestion.events import PendingEvent
from src.ingestion.text_listener import _MatchSignalListener, run_text_listener


@pytest.mark.asyncio
async def test_emits_typed_soft_events(arbiter_with_stub_sources):
    """Tweet with score pattern → 1 PendingEvent in arbiter.score_changes; tweet without → 0."""
    arb = arbiter_with_stub_sources
    listener = _MatchSignalListener(bearer_token="dummy-test-token", arbiter=arb)

    initial_len = len(arb.score_changes)
    await listener.on_tweet({"text": "T1 takes Lotus 13-9 vs Sentinels"})
    assert len(arb.score_changes) == initial_len + 1
    ev = arb.score_changes[-1]
    assert ev.source == "twitter"
    assert ev.event_type == "score_change"
    assert ev.fields_proposed == {"a_round": 13, "b_round": 9}

    # Non-score tweet — no push
    await listener.on_tweet({"text": "good game everyone, gg"})
    assert len(arb.score_changes) == initial_len + 1


@pytest.mark.asyncio
async def test_twitter_only_update_quarantined(arbiter_with_stub_sources):
    """Twitter-alone score event NEVER commits — single-source < 2-source rule."""
    arb = arbiter_with_stub_sources
    initial_seq = arb.state.seq_id
    initial_a_round = arb.state.a_round

    # Push 1 Twitter event with stale t_observed (older than _DEQUE_MAX_AGE_S = 3s)
    stale_t = wall_time() - 10.0
    arb.score_changes.append(PendingEvent(
        source="twitter", event_type="score_change",
        fields_proposed={"a_round": initial_a_round + 1},
        t_observed=stale_t, t_ingested=mono_ns(),
    ))
    arb.tick()

    # State UNCHANGED (no commit)
    assert arb.state.seq_id == initial_seq
    assert arb.state.a_round == initial_a_round

    # Quarantine line in JSONL
    log_text = arb.jsonl_path.read_text()
    assert log_text  # not empty
    line = json.loads(log_text.strip().splitlines()[0])
    assert line["seq_id"] is None
    assert line["quarantined"] is True
    assert line["source"] == "twitter"


@pytest.mark.asyncio
async def test_no_token_noop(monkeypatch, arbiter_with_stub_sources):
    """run_text_listener returns immediately if TWITTER_BEARER_TOKEN is empty."""
    monkeypatch.delenv("TWITTER_BEARER_TOKEN", raising=False)

    arb = arbiter_with_stub_sources
    initial_seq = arb.state.seq_id
    initial_score_changes = len(arb.score_changes)

    # Run with timeout — if it doesn't return cleanly, the test fails
    t0 = time.monotonic()
    await asyncio.wait_for(run_text_listener(arb), timeout=2.0)
    elapsed = time.monotonic() - t0

    assert elapsed < 1.0  # immediate return per no-op contract
    assert arb.state.seq_id == initial_seq  # no state change
    assert len(arb.score_changes) == initial_score_changes  # no events pushed

    # Re-test with empty string (whitespace-only counts as empty per .strip())
    monkeypatch.setenv("TWITTER_BEARER_TOKEN", "   ")
    await asyncio.wait_for(run_text_listener(arb), timeout=2.0)
    assert arb.state.seq_id == initial_seq
```

Replace the xfail stubs with these implementations.

Atomic commit message: `test(03-06): text listener tests — soft events + Twitter-only quarantine + no-token-noop`
  </action>
  <verify>
    <automated>uv run pytest tests/ingestion/test_text_listener.py -v -x --no-cov</automated>
  </verify>
  <done>
- tests/ingestion/test_text_listener.py — 3 tests GREEN.
- _MatchSignalListener correctly parses score signals from tweet text.
- Twitter-only events are quarantined (never commit) per arbiter rule.
- run_text_listener returns immediately without raising when token is empty.
  </done>
</task>

</tasks>

<verification>
- `uv run pytest tests/ingestion/test_text_listener.py -v` — 3 tests pass.
- `uv run mypy src/ingestion/` — 0 errors.
- `uv run ruff check src/ tests/` — clean.
- All Phase 1+2 + 03-01 + 03-02 + 03-03 + 03-04 + 03-05 tests STILL GREEN.
</verification>

<success_criteria>
- REQ-text-listener SPEC acceptance #6 GREEN: mocked Twitter stream emits typed soft-events; Twitter-only update quarantined; test_no_token_noop passes.
- RESEARCH Pitfall 1 (Twitter Basic tier deprecation) documented + handled via degrade-to-no-op.
- TWITTER_RULE_SET pinned with operator-recommended VCT 2026 hashtags + accounts.
</success_criteria>

<output>
After completion, create `.planning/phases/03-live-ingestion-layer/03-06-SUMMARY.md`
documenting:
- Twitter v2 streaming via tweepy.AsyncStreamingClient
- Degrade-to-no-op semantics (TWITTER_BEARER_TOKEN env gate)
- 9 static rules in TWITTER_RULE_SET (5 hashtags + 4 league accounts)
- Score-signal regex (\d{1,2}\s*[-:]\s*\d{1,2})
- Arbiter ≥2-source rule guard verified — Twitter alone never commits
- 3 GREEN tests
- next-wave dependency: 03-08 E2E gate composes the listener via TaskGroup; 03-03 arbiter receives PendingEvents from this source
</output>
</content>
</invoke>
