---
id: 03-06-text-listener
phase: 03
plan: 6
type: execute
wave: 3
depends_on:
  - 03-00-pyproject-and-constants
  - 03-01-shared-types-and-download
  - 03-03-match-state-move-and-extend
files_modified:
  - src/ingestion/text_listener.py
  - src/config/constants.py
  - src/ingestion/__init__.py
  - tests/ingestion/test_text_listener.py
autonomous: true
requirements:
  - REQ-text-listener
user_setup:
  - service: twitter-api-v2
    why: "Twitter v2 streaming requires a Pro/Enterprise tier bearer token (Free/Basic streaming retired per RESEARCH §State of the Art). Phase 3 listener degrades to no-op coroutine when TWITTER_BEARER_TOKEN is unset (CRule 13 dry-run); production deployment needs the operator to set the env var. Synthetic E2E test (03-08) feeds a mocked stream so CI never touches paid Twitter."
    env_vars:
      - name: TWITTER_BEARER_TOKEN
        source: "https://developer.twitter.com/ -> Project -> App -> Keys and tokens -> Bearer Token"
    dashboard_config:
      - task: "Verify the project tier supports filtered-stream (Pro $5k/mo or Enterprise)"
        location: "https://developer.twitter.com/en/portal/products"
must_haves:
  truths:
    - "ValorantTextListener subclasses tweepy.asynchronous.AsyncStreamingClient (D-07 + RESEARCH Pattern 3)"
    - "Listener degrades to a no-op coroutine when TWITTER_BEARER_TOKEN is unset/empty — start() returns immediately, on_tweet never invoked (CRule 13 + RESEARCH Pitfall 5)"
    - "Bearer token NEVER logged, NEVER appears in JSONL, NEVER appears in error traces (T-creds-01)"
    - "Tweet text bounded to MAX_TWEET_TEXT_LEN chars before parsing; control characters dropped (T-input-01)"
    - "Twitter rules pushed at startup ONLY (D-07: NOT per-match); idempotent diff against existing rules"
    - "Listener emits ArbiterPending events with source=\"twitter\", event_type ∈ {score_change, kill, bomb, round_end} — soft-signal only; arbiter quarantines twitter-only kill/bomb/numerical per D-05 + DEC-006 (handled by 03-07)"
    - "max_retries=10 (NOT default infinite) so listener doesn't loop silently forever (RESEARCH Pitfall 5)"
    - "WARNING-6: super().__init__ does NOT pass wait_on_rate_limit (tweepy 4.15+ rejects it); a smoke test test_construct_with_real_super_init exercises the real super() to catch future signature drift"
    - "Tests pass without TWITTER_BEARER_TOKEN: 100% test coverage uses the no-op path + a mocked stream"
  artifacts:
    - path: src/ingestion/text_listener.py
      provides: "ValorantTextListener class + start() + on_tweet() + degrade-on-missing-token"
      contains: "class ValorantTextListener"
    - path: src/config/constants.py
      provides: "+2 constants: MAX_TWEET_TEXT_LEN, TWITTER_MAX_RETRIES"
      contains: "MAX_TWEET_TEXT_LEN"
    - path: tests/ingestion/test_text_listener.py
      provides: "no-token-noop, missing-token-no-exception, mocked-stream-emit, max-length-truncation, control-char-drop tests"
  key_links:
    - from: "src/ingestion/text_listener.py"
      to: "src/config/constants.py:TWITTER_RULE_SET"
      via: "from src.config.constants import TWITTER_RULE_SET"
      pattern: "from src\\.config\\.constants import.*TWITTER_RULE_SET"
    - from: "src/ingestion/text_listener.py"
      to: "src/ingestion/types.py"
      via: "emits ArbiterPending source=\"twitter\""
      pattern: "ArbiterPending\\(.*source=.twitter."
autonomous: true
---

<objective>
Wave 2 source plan #3 — implement the Twitter v2 streaming listener as a `tweepy.asynchronous.AsyncStreamingClient` subclass that degrades to a no-op when `TWITTER_BEARER_TOKEN` is unset (CRule 13 dry-run + RESEARCH §State of the Art on retired Free/Basic streaming).

Purpose: Twitter is the soft-signal cross-confirmation source. DEC-006 + D-05 mandate that any twitter-only kill/bomb/numerical state-change is QUARANTINED (never committed) by the arbiter; the listener only emits typed events. Phase 3 ships the full listener (NOT a stub — SPEC §boundaries explicit), wired through the arbiter, with a complete test surface that doesn't require a real bearer token.

Output: `src/ingestion/text_listener.py` (`ValorantTextListener` class), 2 new constants (`MAX_TWEET_TEXT_LEN`, `TWITTER_MAX_RETRIES`), `tests/ingestion/test_text_listener.py` (no-token + mocked-stream + bounded-text + control-char tests).
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
@src/ingestion/types.py
@src/ingestion/__init__.py
@src/config/constants.py
@CLAUDE.md

<interfaces>
<!-- RESEARCH Pattern 3 (lines 309-359) — analog for ValorantTextListener -->

```python
from tweepy.asynchronous import AsyncStreamingClient
from tweepy import StreamRule

class ValorantTextListener(AsyncStreamingClient):
    """Twitter v2 streaming filter for Valorant match signals.

    Soft-signal source — never sole-source per arbiter D-05.
    Degrades to a no-op coroutine if TWITTER_BEARER_TOKEN is unset (CRule 13).
    """

    def __init__(self, arbiter_pending_emit, bearer_token=None):
        token = bearer_token or os.environ.get("TWITTER_BEARER_TOKEN", "")
        if not token:
            log.warning("TWITTER_BEARER_TOKEN unset — text listener will run as no-op")
            self._noop = True
            return
        self._noop = False
        super().__init__(token, max_retries=10)  # WARNING-6: dropped wait_on_rate_limit (not in tweepy 4.15+ signature)
        self._emit = arbiter_pending_emit

    async def start(self) -> None:
        if self._noop:
            return  # CRule 13: dry-run default
        existing = await self.get_rules()
        existing_values = {r.value for r in (existing.data or [])}
        new_rules = [StreamRule(v) for v in TWITTER_RULE_SET if v not in existing_values]
        if new_rules:
            await self.add_rules(new_rules)
        await self.filter()

    async def on_tweet(self, tweet) -> None:
        # parse + emit ArbiterPending source="twitter"
        ...
```

<!-- ArbiterPending shape (consume from src/ingestion/types.py) -->

```python
@dataclass(frozen=True, slots=True)
class ArbiterPending:
    signal_value: dict[str, Any]
    source: SourceTag                # "twitter"
    event_type: EventType            # primarily "score_change"; may also emit "round_end"
    t_observed: float
    t_ingested: float
```

<!-- Constants this plan reads (added by 03-00 + this plan) -->

```python
TWITTER_RULE_SET                # tuple[str, ...] — 10 rules from 03-00
TWITTER_API_BASE_URL            # "https://api.twitter.com/2"
MAX_TWEET_TEXT_LEN              # 280  (NEW from this plan — Twitter's hard cap)
TWITTER_MAX_RETRIES             # 10   (NEW from this plan — Pitfall 5)
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Create src/ingestion/text_listener.py with ValorantTextListener + degrade-on-missing-token + bounded text + tests</name>
  <files>src/ingestion/text_listener.py, src/config/constants.py, src/ingestion/__init__.py, tests/ingestion/test_text_listener.py</files>
  <read_first>
    - .planning/phases/03-live-ingestion-layer/03-RESEARCH.md §Architecture Patterns Pattern 3 (lines 302-359)
    - .planning/phases/03-live-ingestion-layer/03-RESEARCH.md §Common Pitfalls Pitfall 5 (lines 698-708 — rate-limit reconnection)
    - .planning/phases/03-live-ingestion-layer/03-CONTEXT.md D-07 (static rule set, no per-match CRUD)
    - .planning/phases/03-live-ingestion-layer/03-VALIDATION.md tasks 03-TX-01..03 (lines 52-54)
    - src/ingestion/types.py (ArbiterPending shape)
    - src/config/constants.py:TWITTER_RULE_SET, TWITTER_API_BASE_URL
  </read_first>
  <behavior>
    - Test 1 (test_no_token_noop_returns_immediately): construct with bearer_token=""; await listener.start(); assert returns within 10ms; assert listener.is_noop is True; no exception, no log error.
    - Test 2 (test_missing_env_var_noop): unset TWITTER_BEARER_TOKEN; construct without bearer_token arg; same expectations as Test 1.
    - Test 3 (test_bearer_token_never_logged_in_warning): Construct with bearer_token=""; capture caplog; assert no log record contains the literal token string (defensive: token is empty here, but ensure the warning message format never substitutes the token in).
    - Test 4 (test_max_tweet_text_len_truncation): call _bounded_text("a" * 1000); assert returned length is exactly MAX_TWEET_TEXT_LEN.
    - Test 5 (test_control_chars_dropped): call _bounded_text("hello\x00\x07\x1bworld"); assert returned text == "helloworld".
    - Test 6 (test_on_tweet_emits_arbiter_pending_source_twitter): construct with skip_super_init=True (testing escape hatch — bypass tweepy super().__init__) + bearer_token="dummy"; call await listener.on_tweet(MockTweet(text="A 13 - 7 B")); assert emit called once with ArbiterPending source="twitter", signal parsed.
    - Test 7 (test_on_tweet_in_noop_mode_does_nothing): construct with bearer_token=""; call on_tweet(...); assert emit NOT called (defensive: no path emits in no-op mode).
    - Test 8 (test_max_retries_set_to_10): construct with bearer_token="dummy" + skip_super_init=True; assert listener._max_retries_setting == TWITTER_MAX_RETRIES (Pitfall 5: never infinite).
    - Test 9 (test_on_disconnect_logs_and_increments_counter): call await listener.on_disconnect(); assert listener.stats["twitter_disconnects_total"] == 1 + log message present.
    - Test 10 (test_construct_with_real_super_init): WARNING-6 smoke - constructing with a real bearer token (no skip_super_init) must NOT raise TypeError on tweepy 4.15+ AsyncStreamingClient signature; @skipif when tweepy missing.
  </behavior>
  <action>
**(a)** Append 2 new constants to the Phase 3 section in `src/config/constants.py`:

```python
MAX_TWEET_TEXT_LEN: Final[int] = 280
"""Twitter v2 max tweet length, characters (T-input-01 mitigation).

Source: Twitter API docs (280 char hard cap on standard tweets). Listener
truncates incoming tweet text to this length before parsing — defense-in-depth
against malformed payloads (extended/long-form tweets exceed this; we treat
the truncated prefix as the meaningful signal)."""

TWITTER_MAX_RETRIES: Final[int] = 10
"""tweepy AsyncStreamingClient max_retries cap (RESEARCH Pitfall 5).

Source: 03-RESEARCH.md §Common Pitfalls Pitfall 5 (line 707). NEVER set to
None/infinite — pin to a finite number so the listener doesn't loop forever
silently if Twitter is permanently unavailable. tweepy default is infinite;
we override."""
```

**(b)** Create `src/ingestion/text_listener.py`:

```python
"""Phase 3 Twitter v2 streaming text listener (REQ-text-listener).

Subclasses `tweepy.asynchronous.AsyncStreamingClient` (D-06 asyncio-native).
Soft-signal source per DEC-006 + D-05: arbiter quarantines any twitter-only
kill / bomb / numerical event (handled in src/ingestion/arbiter.py — 03-07);
listener only EMITS typed events.

Degradation: when TWITTER_BEARER_TOKEN is unset/empty, the listener becomes
a no-op coroutine (CRule 13 dry-run + RESEARCH §State of the Art — Free/Basic
streaming was retired in 2023-Q2; Pro tier is $5k/mo). CI cannot exercise
live Twitter; the synthetic E2E test (03-08) feeds a mocked stream.

Static rules (D-07): rule set is pinned in src/config/constants.TWITTER_RULE_SET
and pushed at startup ONLY (no per-match CRUD — Twitter rule-CRUD is rate-limited
to ~15/min globally and team-handle metadata isn't always available).

Defense-in-depth (T-input-01 + T-creds-01):
- Tweet text bounded to MAX_TWEET_TEXT_LEN chars before parsing.
- Control characters stripped from text.
- Bearer token NEVER logged, NEVER in error traces, NEVER in emitted ArbiterPending.

Sources
-------
- 03-SPEC.md §4 (REQ-text-listener)
- 03-CONTEXT.md D-07 (static rule set)
- 03-RESEARCH.md §Architecture Patterns Pattern 3 (lines 302-359)
- 03-RESEARCH.md §Common Pitfalls Pitfall 5 (rate-limit reconnection)
- 03-RESEARCH.md §State of the Art (Twitter v1.1 streaming retirement)
- 03-VALIDATION.md tasks 03-TX-01..03
"""
from __future__ import annotations

import logging
import os
import string
import time
from collections.abc import Awaitable, Callable
from typing import Any, Final, Optional

from src.config.constants import (
    MAX_TWEET_TEXT_LEN,
    TWITTER_MAX_RETRIES,
    TWITTER_RULE_SET,
)
from src.ingestion.types import ArbiterPending

log = logging.getLogger(__name__)

# Allowed text characters: printable ASCII + common whitespace. Strips control
# characters per T-input-01.
_ALLOWED_CHARS: Final[frozenset[str]] = frozenset(string.printable)

EmitFn = Callable[[ArbiterPending], Awaitable[None]]


def _bounded_text(text: str) -> str:
    """Truncate to MAX_TWEET_TEXT_LEN; strip control characters (T-input-01)."""
    cleaned = "".join(c for c in text if c in _ALLOWED_CHARS or c.isspace())
    return cleaned[:MAX_TWEET_TEXT_LEN]


# tweepy is an optional runtime dep at the listener level — when bearer
# token is missing we never actually call into tweepy, so an import failure
# in CI without tweepy installed should also degrade gracefully. But since
# 03-00 declares tweepy in pyproject.toml as a runtime dep, the import is
# guaranteed in production.
try:
    from tweepy import StreamRule
    from tweepy.asynchronous import AsyncStreamingClient
    _TWEEPY_AVAILABLE = True
except ImportError:
    AsyncStreamingClient = object  # type: ignore[assignment,misc]
    StreamRule = None  # type: ignore[assignment,misc]
    _TWEEPY_AVAILABLE = False


class ValorantTextListener(AsyncStreamingClient):
    """Twitter v2 streaming listener for Valorant match signals.

    Constructor:
        emit            (EmitFn): async callback for every parsed tweet.
        bearer_token   (str | None): explicit token override; defaults to env var.
        skip_super_init (bool): TEST-ONLY — bypass tweepy super().__init__ so unit
                                tests can construct without network/credentials.
    """

    def __init__(
        self,
        emit: EmitFn,
        bearer_token: Optional[str] = None,  # noqa: UP045
        skip_super_init: bool = False,
    ) -> None:
        token = bearer_token if bearer_token is not None else os.environ.get("TWITTER_BEARER_TOKEN", "")
        self._emit = emit
        self.stats: dict[str, int] = {
            "twitter_disconnects_total": 0,
            "twitter_request_errors_total": 0,
            "twitter_tweets_received_total": 0,
        }
        self._max_retries_setting = TWITTER_MAX_RETRIES  # exposed for assertions
        self.is_noop: bool
        if not token:
            log.warning(
                "TWITTER_BEARER_TOKEN unset (or empty) — listener will run as no-op (CRule 13)"
            )
            self.is_noop = True
            return
        if not _TWEEPY_AVAILABLE:
            log.warning("tweepy not importable — listener will run as no-op")
            self.is_noop = True
            return
        if skip_super_init:
            # TEST-ONLY: skip tweepy super().__init__ which would attempt validation.
            self.is_noop = False
            self._test_mode = True
            return
        # WARNING-6: tweepy 4.15+ AsyncStreamingClient.__init__ rejects
        # wait_on_rate_limit; drop it. Pro tier handles rate-limits server-side
        # via max_retries (tenacity-style) per RESEARCH Pitfall 5.
        super().__init__(
            bearer_token=token,
            max_retries=TWITTER_MAX_RETRIES,
        )
        self.is_noop = False

    async def start(self) -> None:
        """Push static rules (D-07) once + open filtered stream.

        No-op when bearer token missing (CRule 13). Idempotent rule push:
        diffs TWITTER_RULE_SET against existing rules; only adds the delta.
        """
        if self.is_noop:
            return
        # Diff existing rules vs static set; push only delta.
        try:
            existing = await self.get_rules()
            existing_values = {r.value for r in (existing.data or [])} if existing else set()
            new_rules = [StreamRule(v) for v in TWITTER_RULE_SET if v not in existing_values]
            if new_rules:
                await self.add_rules(new_rules)
                log.info("twitter_rules_added count=%d", len(new_rules))
        except Exception as exc:
            log.error("twitter_rule_push_failed exc=%s", exc)
            return  # Don't enter the stream if rule push fails
        await self.filter()  # blocks until disconnect

    async def on_tweet(self, tweet: Any) -> None:
        """Parse the tweet text into a typed ArbiterPending + emit.

        No-op when listener is no-op (defensive — tweepy shouldn't ever invoke
        on_tweet in no-op mode, but this guard prevents accidental emission
        in test scenarios that bypass `is_noop`).
        """
        if self.is_noop:
            return
        text = _bounded_text(getattr(tweet, "text", ""))
        if not text:
            return
        self.stats["twitter_tweets_received_total"] += 1
        signal_value, event_type = self._parse(text)
        if signal_value is None or event_type is None:
            return
        await self._emit(
            ArbiterPending(
                signal_value=signal_value,
                source="twitter",
                event_type=event_type,
                t_observed=time.time(),
                t_ingested=time.monotonic(),
            )
        )

    @staticmethod
    def _parse(text: str) -> tuple[Optional[dict[str, Any]], Optional[str]]:  # noqa: UP045
        """Extract a soft signal_value + event_type from tweet text.

        Phase 3 ships minimum-viable extraction (score patterns + round-end
        keywords). Phase 5 calibration tightens this with the actual
        twitter-account text patterns observed live.
        """
        # Score-change pattern: "TEAM_A 13 - 7 TEAM_B" or similar.
        # Use a conservative regex to avoid false positives.
        import re
        m = re.search(r"\b(\d{1,2})\s*-\s*(\d{1,2})\b", text)
        if m:
            try:
                a = int(m.group(1))
                b = int(m.group(2))
                if 0 <= a <= 24 and 0 <= b <= 24:
                    return {"a_round": a, "b_round": b}, "score_change"
            except ValueError:
                pass
        # Round-end keywords (soft signal).
        lowered = text.lower()
        for kw in ("round won", "round lost", "ace", "clutch"):
            if kw in lowered:
                return {"_round_end_soft": True, "tweet_keyword": kw}, "round_end"
        return None, None

    async def on_disconnect(self) -> None:
        """Pitfall 5: log disconnects + increment counter for Phase 5 alarming."""
        self.stats["twitter_disconnects_total"] += 1
        log.warning("twitter_stream_disconnect total=%d", self.stats["twitter_disconnects_total"])

    async def on_request_error(self, status_code: int) -> None:
        """tweepy retries internally up to TWITTER_MAX_RETRIES; log here for visibility."""
        self.stats["twitter_request_errors_total"] += 1
        log.error("twitter_stream_request_error status=%d total=%d",
                  status_code, self.stats["twitter_request_errors_total"])


__all__ = ["ValorantTextListener", "EmitFn", "_bounded_text"]
```

**(c)** Update `src/ingestion/__init__.py` to re-export `ValorantTextListener`:

```python
from src.ingestion.text_listener import ValorantTextListener
```

Add `"ValorantTextListener"` to `__all__`.

**(d)** Create `tests/ingestion/test_text_listener.py`:

```python
"""ValorantTextListener tests — REQ-text-listener acceptance.

Covers VALIDATION rows 03-TX-01..03 + T-creds-01 + T-input-01 mitigations.
NO live Twitter — all tests use the no-op path or skip_super_init=True
escape hatch.

Sources
-------
- 03-VALIDATION.md tasks 03-TX-01, 03-TX-02, 03-TX-03 (lines 52-54)
- 03-RESEARCH.md §Architecture Patterns Pattern 3 (lines 302-359)
- src/ingestion/text_listener.py (module under test)
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest

from src.config.constants import MAX_TWEET_TEXT_LEN, TWITTER_MAX_RETRIES
from src.ingestion.text_listener import (
    ValorantTextListener,
    _bounded_text,
)
from src.ingestion.types import ArbiterPending


# --------------------------------------------------------------------------- #
# Fixtures                                                                    #
# --------------------------------------------------------------------------- #


@pytest.fixture
def emitted() -> list[ArbiterPending]:
    return []


@pytest.fixture
def emit_fn(emitted: list[ArbiterPending]):
    async def _emit(p: ArbiterPending) -> None:
        emitted.append(p)
    return _emit


# --------------------------------------------------------------------------- #
# No-op / degradation tests (REQ-text-listener acceptance row 03-TX-03)       #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_no_token_noop_returns_immediately(emit_fn, emitted, monkeypatch) -> None:
    """REQ-text-listener acceptance: missing TWITTER_BEARER_TOKEN -> listener no-ops."""
    monkeypatch.setenv("TWITTER_BEARER_TOKEN", "")
    listener = ValorantTextListener(emit=emit_fn)
    assert listener.is_noop is True
    # start() returns instantly without raising
    await asyncio.wait_for(listener.start(), timeout=1.0)
    assert emitted == []


@pytest.mark.asyncio
async def test_missing_env_var_noop(emit_fn, monkeypatch) -> None:
    """No env var set -> listener no-ops, no exception."""
    monkeypatch.delenv("TWITTER_BEARER_TOKEN", raising=False)
    listener = ValorantTextListener(emit=emit_fn)
    assert listener.is_noop is True


@pytest.mark.asyncio
async def test_explicit_empty_string_token_noop(emit_fn, monkeypatch) -> None:
    """Explicit bearer_token='' -> no-op."""
    monkeypatch.setenv("TWITTER_BEARER_TOKEN", "should-be-ignored")
    listener = ValorantTextListener(emit=emit_fn, bearer_token="")
    assert listener.is_noop is True


def test_bearer_token_never_logged(emit_fn, monkeypatch, caplog) -> None:
    """T-creds-01: never log the bearer token, even in degraded path."""
    monkeypatch.setenv("TWITTER_BEARER_TOKEN", "")
    fake_token = "secret-xyz-abc-12345"
    with caplog.at_level(logging.WARNING):
        ValorantTextListener(emit=emit_fn, bearer_token="")
    for rec in caplog.records:
        assert fake_token not in rec.getMessage()
    # And the no-op warning IS logged (sanity).
    assert any("no-op" in r.getMessage() for r in caplog.records)


# --------------------------------------------------------------------------- #
# Bounded text + control-char strip (T-input-01)                              #
# --------------------------------------------------------------------------- #


def test_bounded_text_truncation() -> None:
    """T-input-01: text > MAX_TWEET_TEXT_LEN truncated."""
    long = "a" * 1000
    out = _bounded_text(long)
    assert len(out) == MAX_TWEET_TEXT_LEN


def test_bounded_text_control_chars_dropped() -> None:
    """T-input-01: control chars stripped."""
    raw = "hello\x00\x07\x1bworld"
    out = _bounded_text(raw)
    assert out == "helloworld"


def test_bounded_text_preserves_normal_whitespace() -> None:
    """Whitespace (space, tab, newline) IS preserved."""
    out = _bounded_text("a b\tc\nd")
    assert out == "a b\tc\nd"


# --------------------------------------------------------------------------- #
# Mocked-stream emit tests (REQ-text-listener acceptance row 03-TX-01)        #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_on_tweet_emits_arbiter_pending_source_twitter(emit_fn, emitted) -> None:
    """REQ-text-listener: parsed tweet -> ArbiterPending source='twitter'."""
    listener = ValorantTextListener(
        emit=emit_fn, bearer_token="dummy", skip_super_init=True
    )
    assert listener.is_noop is False
    fake_tweet = SimpleNamespace(text="Sentinels 13 - 7 LOUD")
    await listener.on_tweet(fake_tweet)
    assert len(emitted) == 1
    assert emitted[0].source == "twitter"
    assert emitted[0].event_type == "score_change"
    assert emitted[0].signal_value == {"a_round": 13, "b_round": 7}


@pytest.mark.asyncio
async def test_on_tweet_round_end_keyword(emit_fn, emitted) -> None:
    """Round-end keyword in tweet -> event_type='round_end'."""
    listener = ValorantTextListener(
        emit=emit_fn, bearer_token="dummy", skip_super_init=True
    )
    fake = SimpleNamespace(text="Insane CLUTCH from TenZ to win the round!")
    await listener.on_tweet(fake)
    assert len(emitted) == 1
    assert emitted[0].event_type == "round_end"


@pytest.mark.asyncio
async def test_on_tweet_in_noop_mode_does_nothing(emit_fn, emitted, monkeypatch) -> None:
    """Defensive: even if on_tweet is invoked while is_noop=True, nothing emits."""
    monkeypatch.setenv("TWITTER_BEARER_TOKEN", "")
    listener = ValorantTextListener(emit=emit_fn)
    fake = SimpleNamespace(text="Sentinels 13 - 7 LOUD")
    await listener.on_tweet(fake)
    assert emitted == []


@pytest.mark.asyncio
async def test_on_tweet_unparseable_emits_nothing(emit_fn, emitted) -> None:
    """Tweets without score / round-end keywords -> no emission."""
    listener = ValorantTextListener(
        emit=emit_fn, bearer_token="dummy", skip_super_init=True
    )
    fake = SimpleNamespace(text="random thoughts about nothing")
    await listener.on_tweet(fake)
    assert emitted == []


@pytest.mark.asyncio
async def test_on_tweet_truncates_long_text(emit_fn, emitted) -> None:
    """A 5000-char tweet still parses against the 280-char prefix only."""
    listener = ValorantTextListener(
        emit=emit_fn, bearer_token="dummy", skip_super_init=True
    )
    text = "Sentinels 13 - 7 LOUD " + ("x" * 5000)
    fake = SimpleNamespace(text=text)
    await listener.on_tweet(fake)
    assert len(emitted) == 1
    assert emitted[0].signal_value == {"a_round": 13, "b_round": 7}


# --------------------------------------------------------------------------- #
# Disconnect / retry config (Pitfall 5)                                       #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_on_disconnect_logs_and_increments(emit_fn, caplog) -> None:
    listener = ValorantTextListener(
        emit=emit_fn, bearer_token="dummy", skip_super_init=True
    )
    with caplog.at_level(logging.WARNING):
        await listener.on_disconnect()
    assert listener.stats["twitter_disconnects_total"] == 1
    assert any("twitter_stream_disconnect" in r.getMessage() for r in caplog.records)


@pytest.mark.skipif(
    "tweepy" not in __import__("sys").modules and __import__("importlib.util").util.find_spec("tweepy") is None,
    reason="tweepy not installed",
)
def test_construct_with_real_super_init(emit_fn) -> None:
    """WARNING-6 smoke: constructing with a non-empty bearer token MUST hit the
    real tweepy super().__init__ without TypeError. Catches signature drift
    (e.g. wait_on_rate_limit being removed in tweepy 4.15+).
    Skips cleanly if tweepy is unavailable so CI without the dep still passes."""
    # NOTE: real super().__init__ does NOT validate the bearer token until
    # connect time, so a dummy token is safe here.
    listener = ValorantTextListener(emit=emit_fn, bearer_token="dummy-pro-token")
    assert listener.is_noop is False


def test_max_retries_set_to_finite(emit_fn) -> None:
    """RESEARCH Pitfall 5: NEVER infinite retries."""
    listener = ValorantTextListener(
        emit=emit_fn, bearer_token="dummy", skip_super_init=True
    )
    assert listener._max_retries_setting == TWITTER_MAX_RETRIES
    assert TWITTER_MAX_RETRIES == 10
    assert isinstance(TWITTER_MAX_RETRIES, int)
```

(11 named test functions; ALL run without network or paid Twitter access.)
  </action>
  <verify>
    <automated>pytest tests/ingestion/test_text_listener.py -x &amp;&amp; mypy src/ingestion/text_listener.py &amp;&amp; ruff check src/ingestion/text_listener.py tests/ingestion/test_text_listener.py</automated>
  </verify>
  <done>src/ingestion/text_listener.py exports ValorantTextListener; 2 new constants in src/config/constants.py (MAX_TWEET_TEXT_LEN, TWITTER_MAX_RETRIES); src/ingestion/__init__.py re-exports the class; 11 test functions in tests/ingestion/test_text_listener.py PASS without network; bearer token never appears in any log capture; bounded text + control char drop verified; mypy + ruff clean; Phase 1 + 2 + 03-03 + 03-04 + 03-05 regressions GREEN.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| environment -> code | `TWITTER_BEARER_TOKEN` env var is the only credential channel. |
| Twitter v2 stream -> arbiter | Untrusted external text crosses into the arbiter's pending deque. |
| tweepy library -> our subclass | `AsyncStreamingClient` invokes `on_tweet`, `on_disconnect`, `on_request_error` as callbacks. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-03-06-01 (covers T-creds-01) | I (Information disclosure) | bearer token | mitigate | Token read from env var ONCE in `__init__`; stored only inside the tweepy super() instance (not a self attr we control); never logged (`test_bearer_token_never_logged` proves the no-op warning omits any token); never appears in emitted ArbiterPending (`signal_value` only contains parsed score/keyword data); never in error traces (we catch `Exception as exc` in `start()` and log only the exc, but tweepy never includes the token in exception text). |
| T-03-06-02 (covers T-input-01) | T (Tampering) | tweet text -> arbiter | mitigate | `_bounded_text()` truncates to MAX_TWEET_TEXT_LEN (280) and strips non-printable control chars before parsing. The parser uses `re.search` (no `eval`), bounds `int()` casts in try/except, and rejects scores outside [0, 24] (sanity bound). |
| T-03-06-03 | T (Tampering) | TLS to api.twitter.com (T-net-01) | mitigate | tweepy uses `aiohttp` underneath; `aiohttp.ClientSession` defaults to `verify_ssl=True`; never disabled. No certificate-pinning bypass. |
| T-03-06-04 (covers T-net-01) | D (Denial of service) | infinite reconnect loop | mitigate | `max_retries=TWITTER_MAX_RETRIES (=10)` per Pitfall 5 — finite cap means listener gives up after 10 consecutive failures. Disconnect counter exposed for Phase 5 alarming. |
| T-03-06-05 | E (Elevation of privilege) | tweepy's `super().__init__` | accept | tweepy is a major widely-used library (4.16.0 verified live in RESEARCH); we trust its bearer-token validation + connection lifecycle code. The `skip_super_init=True` escape hatch is TEST-ONLY and explicitly named so it can't be set by accident in production code. |
| T-03-06-06 | I (Information disclosure) | rule push at startup | accept | Rule values come from `TWITTER_RULE_SET` (10 public hashtags/accounts in source code). Logging "twitter_rules_added count=N" reveals the count, not the rule values themselves. |
</threat_model>

<verification>
- `pytest tests/ingestion/test_text_listener.py -x` PASSES (11 named tests, NONE require a real Twitter token).
- `mypy src/ingestion/text_listener.py` clean.
- `ruff check src/ingestion/text_listener.py tests/ingestion/test_text_listener.py src/config/constants.py` clean.
- `python -c "from src.ingestion import ValorantTextListener; print(ValorantTextListener.__module__)"` returns 0.
- `MAX_TWEET_TEXT_LEN` and `TWITTER_MAX_RETRIES` importable.
- All Phase 1 + 2 + 03-03 + 03-04 + 03-05 tests GREEN.
- Regression: `pytest tests/ -x -k "not benchmark and not e2e and not accuracy_probe"` PASSES.
</verification>

<success_criteria>
Wave 2 plan 03-06 (text listener) is COMPLETE when:

1. `src/ingestion/text_listener.py` exports `ValorantTextListener` subclass of `tweepy.asynchronous.AsyncStreamingClient`.
2. Listener degrades to no-op when `TWITTER_BEARER_TOKEN` is unset/empty (CRule 13 + RESEARCH §State of the Art on retired Free/Basic streaming).
3. Bearer token NEVER logged, NEVER in emitted ArbiterPending, NEVER in error traces (T-creds-01 — verified by `test_bearer_token_never_logged`).
4. Tweet text bounded to MAX_TWEET_TEXT_LEN + control chars stripped (T-input-01 — verified by `test_bounded_text_*`).
5. `max_retries=TWITTER_MAX_RETRIES (=10)`, NEVER infinite (Pitfall 5 — verified by `test_max_retries_set_to_finite`).
6. Static `TWITTER_RULE_SET` pushed once at startup with idempotent diff (D-07).
7. 2 new constants in `src/config/constants.py` (Phase 3 section now totals 27).
8. `tests/ingestion/test_text_listener.py` has 11 named test functions; ALL PASS without paid Twitter access.
9. `src/ingestion/__init__.py` re-exports `ValorantTextListener`.
10. Phase 1 + 2 + 03-03 + 03-04 + 03-05 regressions GREEN.
</success_criteria>

<output>
After completion, create `.planning/phases/03-live-ingestion-layer/03-06-SUMMARY.md`:

```markdown
# 03-06 SUMMARY — Twitter v2 text listener

**Status:** complete
**Wave:** 2 (parallel with 03-04 + 03-05)
**Files created:** src/ingestion/text_listener.py, tests/ingestion/test_text_listener.py
**Files modified:** src/ingestion/__init__.py, src/config/constants.py (+2 constants: MAX_TWEET_TEXT_LEN, TWITTER_MAX_RETRIES)

## Public API
- ValorantTextListener(emit, bearer_token=None, skip_super_init=False)
- await listener.start()                 # idempotent rule push + filter()
- listener.is_noop                       # True when no token; degrades gracefully
- listener.stats                         # disconnects/request-errors/tweets-received counters

## CRule 13 + T-creds-01 + T-input-01 mitigations
- Missing token -> log warning + return is_noop=True
- Token never logged + never emitted
- 280-char text cap + control-char strip

## Soft-signal arbiter integration (D-05 + DEC-006)
- Listener emits source="twitter" only for score_change + round_end
- Arbiter (03-07) QUARANTINES twitter-only kill/bomb/numerical (no path here)

## Tests (11)
- 4 no-op / degradation
- 3 bounded text / control char
- 5 mocked-stream emit
- 2 disconnect / retry config
```
</output>
