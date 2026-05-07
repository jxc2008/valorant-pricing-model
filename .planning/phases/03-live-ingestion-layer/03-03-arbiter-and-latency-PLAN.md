---
phase: 03-live-ingestion-layer
plan: "03"
type: execute
wave: 4
depends_on: ["03-01"]
files_modified:
  - src/ingestion/__init__.py
  - src/ingestion/arbiter.py
  - src/ingestion/timestamps.py
  - src/ingestion/events.py
  - src/config/constants.py
  - tests/ingestion/test_arbiter.py
  - tests/ingestion/test_latency.py
  - tests/ingestion/conftest.py
autonomous: true
requirements:
  - REQ-cross-source-arbiter
  - REQ-latency-instrumentation
notes: |
  Wave 4A — DEC-006 v2 cross-source arbiter (3 deques, simplified rules) +
  6-stage timestamp lineage. The arbiter is the SOLE writer of MatchState
  and SOLE appender of data/event_log/{match_id}.jsonl per D-02 / RESEARCH
  Pitfall 4 single-writer atomicity. Six timestamps per confirmed event:
  t_observed (wall-clock for replay), t_ingested, t_arbited, t_state_committed,
  t_theo_computed (None in Phase 3 — Phase 4 fills), t_quote_sent (None in
  Phase 3 — Phase 4 fills). Metrics file at data/metrics/{match_id}.metrics.jsonl.

  Runs in PARALLEL with 03-04 (scoreboard), 03-05 (OCR), 03-06 (text listener)
  — all four depend only on 03-01 (MatchState v2 + commit/quarantine helpers
  from src/state). 03-08 (E2E gate) is the wave-6 downstream consumer.

  v2 grep-guard: src/ingestion/arbiter.py MUST NOT contain "kill_events" or
  "numerical_flips" (DEC-006 v2 / DEC-024 v2 cuts). Verify command in Task 1.

must_haves:
  truths:
    - "Arbiter exposes 3 deques: score_changes, bomb_events, round_end_events (no kill_events, no numerical_flips)"
    - "Arbiter is sole writer of MatchState — calls state.with_update() and commit() from src.state"
    - "score_change rule: ≥ 2 sources within ARBITER_SCORE_WINDOW_S (2s) → commit; otherwise hold"
    - "bomb_event rule: 1 OCR source soft-commit immediately; hard-confirm by next score/round-end"
    - "round_end_event rule: 1 OCR source soft-commit immediately; hard-confirm by next score update"
    - "Quarantined events emit JSONL line with seq_id: null, quarantined: true, fields_proposed: {...}"
    - "Every confirmed event JSONL line carries 6 timestamps (t_quote_sent / t_theo_computed = None in Phase 3)"
    - "Metrics file at data/metrics/{match_id}.metrics.jsonl is line-by-line parseable"
    - "src/ingestion/arbiter.py contains no 'kill_events' or 'numerical_flips' substrings (DEC-006 v2 grep guard)"
  artifacts:
    - path: "src/ingestion/__init__.py"
      provides: "Public re-exports: Arbiter, PendingEvent, wall_time, mono_ns"
      contains: "Arbiter"
    - path: "src/ingestion/arbiter.py"
      provides: "Arbiter class with 3 deques + tick() + commit/quarantine plumbing"
      contains: "score_changes"
      min_lines: 200
    - path: "src/ingestion/timestamps.py"
      provides: "wall_time() / mono_ns() helpers; six-stage timestamp record TypedDict"
      contains: "monotonic_ns"
    - path: "src/ingestion/events.py"
      provides: "PendingEvent + ConfirmedEvent dataclasses (typed event shapes for the 3 deques)"
      contains: "PendingEvent"
    - path: "src/config/constants.py"
      provides: "ARBITER_TICK_HZ + ARBITER_SCORE_WINDOW_S + EVENT_LOG_DIR + METRICS_LOG_DIR"
      contains: "ARBITER_TICK_HZ"
    - path: "tests/ingestion/test_arbiter.py"
      provides: "GREEN test_score_change_two_source_rule + test_bomb_event_one_source_soft_commit + test_round_end_one_source_soft_commit + test_quarantine_jsonl_format"
      contains: "test_score_change_two_source_rule"
    - path: "tests/ingestion/test_latency.py"
      provides: "GREEN test_six_stage_populated"
      contains: "test_six_stage_populated"
  key_links:
    - from: "src/ingestion/arbiter.py:Arbiter.tick"
      to: "src.state.match_state.commit"
      via: "from src.state import commit; new_state = commit(prev_state, fields, ...)"
      pattern: "from src\\.state.*commit"
    - from: "src/ingestion/arbiter.py:Arbiter.tick"
      to: "src.state.match_state.quarantine"
      via: "from src.state import quarantine"
      pattern: "from src\\.state.*quarantine"
    - from: "src/ingestion/arbiter.py JSONL writer"
      to: "data/event_log/{match_id}.jsonl"
      via: "commit() helper writes diff line with 6 timestamps"
      pattern: "data/event_log"
    - from: "src/ingestion/arbiter.py metrics writer"
      to: "data/metrics/{match_id}.metrics.jsonl"
      via: "parallel metrics line"
      pattern: "data/metrics"
---

<objective>
Land the v2 cross-source arbiter (DEC-006: 3 deques, simplified rules) and
the 6-stage latency instrumentation. The arbiter consumes PendingEvents from
the four sources (scoreboard, OCR, text listener, post-plant alive widget),
applies confirmation rules, and either commits via src.state.commit (which
writes the JSONL diff line) or quarantines via src.state.quarantine.

Purpose: REQ-cross-source-arbiter and REQ-latency-instrumentation are the
plumbing that connects the four ingestion sources (waves 4B/4C/4D) to the
state engine. Without the arbiter, the sources have nowhere to push events;
without the timestamp lineage, the E2E gate (03-08) cannot measure latency.

Output:
- src/ingestion/arbiter.py (~250 LOC: Arbiter class + tick() + 3 confirmation rules + JSONL bridge)
- src/ingestion/timestamps.py (~50 LOC: wall_time, mono_ns, TimestampRecord TypedDict)
- src/ingestion/events.py (~60 LOC: PendingEvent + ConfirmedEvent dataclasses)
- src/ingestion/__init__.py (~10 LOC re-exports)
- 4 new constants in src/config/constants.py
- tests/ingestion/test_arbiter.py — 4 GREEN tests
- tests/ingestion/test_latency.py — 1 GREEN test
- conftest.py `arbiter_with_stub_sources` fixture upgraded to return a real Arbiter
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
@src/state/match_state.py
@src/config/constants.py

<interfaces>
<!-- src/state/match_state.py — already shipped in 03-01 -->
From src/state:
```python
from src.state import MatchState, commit, quarantine

def commit(
    prev: MatchState,
    fields_changed: dict[str, Any],
    *,
    source: str,
    event_type: str,
    timestamps: dict[str, float | int | None],
    jsonl_path: Path,
) -> MatchState:
    """Bump seq_id, write JSONL diff line, return new state. Sole writer is the arbiter."""

def quarantine(
    prev: MatchState,
    fields_proposed: dict[str, Any],
    *,
    source: str,
    event_type: str,
    quarantine_reason: str,
    t_observed: float,
    jsonl_path: Path,
) -> None:
    """Write quarantined JSONL line; state UNCHANGED."""
```

<!-- Target src/ingestion/timestamps.py -->
```python
import time
from typing import TypedDict

def wall_time() -> float:
    """Wall-clock seconds for t_observed (replay vs broadcast). NEVER use for latency math."""
    return time.time()

def mono_ns() -> int:
    """Monotonic nanoseconds for latency math (t_ingested, t_arbited, t_state_committed,
    t_theo_computed, t_quote_sent). NEVER mix with wall_time() for duration computation."""
    return time.monotonic_ns()

class TimestampRecord(TypedDict):
    t_observed: float            # wall_time()
    t_ingested: int | None       # mono_ns() — set by source on push
    t_arbited: int | None        # mono_ns() — set by arbiter at confirmation
    t_state_committed: int | None  # mono_ns() — set by commit() helper
    t_theo_computed: int | None  # None in Phase 3 (Phase 4 fills)
    t_quote_sent: int | None     # None in Phase 3 (Phase 4 fills)
```

<!-- Target src/ingestion/events.py -->
```python
from dataclasses import dataclass, field
from typing import Any, Literal

EventType = Literal["score_change", "bomb_plant", "bomb_defuse", "round_end", "post_plant_alive"]
SourceName = Literal["ribgg", "ocr_score", "ocr_bomb", "ocr_round_end", "ocr_post_plant_alive", "twitter"]

@dataclass(frozen=True, slots=True)
class PendingEvent:
    source: SourceName
    event_type: EventType
    fields_proposed: dict[str, Any]
    t_observed: float
    t_ingested: int

@dataclass(frozen=True, slots=True)
class ConfirmedEvent:
    event_type: EventType
    fields_changed: dict[str, Any]
    sources: tuple[SourceName, ...]   # which sources contributed
    timestamps: dict[str, float | int | None]
```

<!-- Target src/ingestion/arbiter.py — sketch -->
```python
from collections import deque
from pathlib import Path
from src.state import MatchState, commit, quarantine
from src.config.constants import (
    ARBITER_SCORE_WINDOW_S,
    EVENT_LOG_DIR,
    METRICS_LOG_DIR,
)

class Arbiter:
    def __init__(self, initial_state: MatchState, *, event_log_dir: Path = Path(EVENT_LOG_DIR), metrics_log_dir: Path = Path(METRICS_LOG_DIR)) -> None:
        self._state = initial_state
        self._jsonl_path = event_log_dir / f"{initial_state.match_id}.jsonl"
        self._metrics_path = metrics_log_dir / f"{initial_state.match_id}.metrics.jsonl"
        self.score_changes: deque[PendingEvent] = deque(maxlen=128)
        self.bomb_events: deque[PendingEvent] = deque(maxlen=64)
        self.round_end_events: deque[PendingEvent] = deque(maxlen=64)
        # Tracking for hard-confirm pending soft-committed bomb / round-end events
        self._pending_bomb_confirm: ConfirmedEvent | None = None
        self._pending_round_end_confirm: ConfirmedEvent | None = None

    @property
    def state(self) -> MatchState:
        return self._state

    def tick(self) -> None:
        """Drain deques, apply confirmation rules, commit / quarantine."""
        self._drain_score_changes()
        self._drain_bomb_events()
        self._drain_round_end_events()
```

<!-- src/config/constants.py — Phase 3 ingestion section to ADD -->
```python
# --------------------------------------------------------------------------- #
# Phase 3 — ingestion arbiter + event logs (DEC-006 v2 / D-03)               #
# --------------------------------------------------------------------------- #

ARBITER_TICK_HZ: Final[int] = 20
"""Arbiter drain frequency (Hz). 20Hz = 50ms tick interval, well within the
500ms event→state-commit budget. Used by src/main.py asyncio loop only;
src/ingestion/arbiter.py exposes the bare tick() — driver picks the cadence."""

ARBITER_SCORE_WINDOW_S: Final[float] = 2.0
"""Score-change cross-confirm window (seconds). DEC-006 v2: a score_change
event commits when ≥ 2 independent sources push events with t_observed
within this window of each other."""

EVENT_LOG_DIR: Final[str] = "data/event_log"
"""JSONL diff log directory (one file per match_id). Gitignored per
03-00-PLAN's .gitignore additions."""

METRICS_LOG_DIR: Final[str] = "data/metrics"
"""6-stage timestamp metrics directory (one file per match_id). Phase 4
fills t_theo_computed / t_quote_sent on a parallel metrics line per D-03."""
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Create src/ingestion/{timestamps,events,__init__}.py + 4 constants</name>
  <files>
    src/ingestion/__init__.py
    src/ingestion/timestamps.py
    src/ingestion/events.py
    src/config/constants.py
  </files>
  <behavior>
    - `src/ingestion/timestamps.py` exposes `wall_time() -> float`, `mono_ns() -> int`, and `TimestampRecord` TypedDict per <interfaces>. Module docstring documents per RESEARCH Pitfall 3: "wall_time = time.time() for t_observed only; mono_ns = time.monotonic_ns() for latency math; NEVER mix for duration computation."
    - `src/ingestion/events.py` exposes `PendingEvent`, `ConfirmedEvent` dataclasses (frozen=True, slots=True) + `EventType` and `SourceName` Literal aliases. Module docstring cites DEC-006 v2 (3 deques) and CONTEXT D-04 (deque mechanism baseline).
    - `src/ingestion/__init__.py` re-exports all of the above PLUS Arbiter (which Task 2 lands; for Task 1 just re-export the 3 from events + 2 from timestamps).
    - `src/config/constants.py` has 4 new constants: ARBITER_TICK_HZ=20, ARBITER_SCORE_WINDOW_S=2.0, EVENT_LOG_DIR="data/event_log", METRICS_LOG_DIR="data/metrics".
    - All annotations use `Final[T]` per CRule 12.
    - `mypy --strict src/state/` STILL clean (existing); `mypy src/ingestion/` runs without errors (gradual mode is fine for ingestion per SPEC §"Constraints", but new code annotates fully — `mypy src/ingestion/` exits 0 with NO errors found, even without --strict).
  </behavior>
  <action>
1) **Create `src/ingestion/timestamps.py`** (~50 LOC):

```python
"""Six-stage timestamp helpers (REQ-latency-instrumentation, 03-CONTEXT D-03).

Time discipline (RESEARCH Pitfall 3 — NEVER violate):
- ``t_observed`` uses ``time.time()`` (wall-clock, broadcast-aligned for replay).
- The other 5 timestamps use ``time.monotonic_ns()`` (latency math, undefined
  reference point — NEVER subtract from ``t_observed``).

The TimestampRecord TypedDict is consumed by:
- src/ingestion/scoreboard.py / ocr.py / text_listener.py — sources set
  t_observed + t_ingested at push time.
- src/ingestion/arbiter.py:tick — sets t_arbited at confirmation; passes the
  dict to src.state.commit which sets t_state_committed.
- Phase 4 — fills t_theo_computed (after live_theo) and t_quote_sent (after
  KalshiOrderManager.place_quote).
"""
from __future__ import annotations

import time
from typing import TypedDict


def wall_time() -> float:
    """Wall-clock seconds for ``t_observed`` only (replay alignment).

    NEVER use for latency math — broadcast-aligned wall-clock has no defined
    relationship to mono_ns(). Pitfall 3 catches this if ignored.
    """
    return time.time()


def mono_ns() -> int:
    """Monotonic nanoseconds for latency math.

    Used for t_ingested, t_arbited, t_state_committed, t_theo_computed,
    t_quote_sent. The reference point is process-local; only the differences
    between two mono_ns() reads are meaningful.
    """
    return time.monotonic_ns()


class TimestampRecord(TypedDict):
    """Six-stage timestamp lineage per confirmed event (D-03)."""

    t_observed: float
    t_ingested: int | None
    t_arbited: int | None
    t_state_committed: int | None
    t_theo_computed: int | None
    t_quote_sent: int | None
```

2) **Create `src/ingestion/events.py`** (~60 LOC):

```python
"""Typed event shapes for the 3-deque arbiter (DEC-006 v2 / 03-CONTEXT D-04).

The 3 deques are exposed by src/ingestion/arbiter.py:
- score_changes: PendingEvent with event_type="score_change"
- bomb_events: PendingEvent with event_type in {"bomb_plant", "bomb_defuse", "post_plant_alive"}
- round_end_events: PendingEvent with event_type="round_end"

Cut from v1 schema (DEC-006 v2 / DEC-024 v2):
- kill_events deque (kill-feed CV is gone)
- numerical_flips deque (mid-round economy inference is gone)

Each ingestion source pushes PendingEvents; the arbiter materializes
ConfirmedEvent records (after rule check) and forwards to src.state.commit.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

EventType = Literal[
    "score_change",
    "bomb_plant",
    "bomb_defuse",
    "round_end",
    "post_plant_alive",
]

SourceName = Literal[
    "ribgg",
    "ocr_score",
    "ocr_bomb",
    "ocr_round_end",
    "ocr_post_plant_alive",
    "twitter",
]


@dataclass(frozen=True, slots=True)
class PendingEvent:
    """Source-emitted event awaiting arbiter confirmation."""

    source: SourceName
    event_type: EventType
    fields_proposed: dict[str, Any]
    t_observed: float  # wall_time() — broadcast wall-clock
    t_ingested: int    # mono_ns() — set by source at push time


@dataclass(frozen=True, slots=True)
class ConfirmedEvent:
    """Arbiter-confirmed event ready for src.state.commit."""

    event_type: EventType
    fields_changed: dict[str, Any]
    sources: tuple[SourceName, ...]
    timestamps: dict[str, float | int | None]
```

3) **Create `src/ingestion/__init__.py`** (Task 2 will append `Arbiter`):

```python
"""Live ingestion layer — sources + arbiter + JSONL event log (Phase 3)."""

from src.ingestion.events import (
    ConfirmedEvent,
    EventType,
    PendingEvent,
    SourceName,
)
from src.ingestion.timestamps import TimestampRecord, mono_ns, wall_time

__all__ = [
    "ConfirmedEvent",
    "EventType",
    "PendingEvent",
    "SourceName",
    "TimestampRecord",
    "mono_ns",
    "wall_time",
]
```

4) **Add 4 constants to `src/config/constants.py`** — append a new "Phase 3 — ingestion arbiter + event logs" section per <interfaces>. Use `Final[int]`, `Final[float]`, `Final[str]` annotations.

Atomic commit message: `feat(03-03): add src/ingestion timestamp + event types + 4 arbiter constants`
  </action>
  <verify>
    <automated>uv run python -c "from src.ingestion import wall_time, mono_ns, PendingEvent, ConfirmedEvent, EventType, SourceName, TimestampRecord; from src.config.constants import ARBITER_TICK_HZ, ARBITER_SCORE_WINDOW_S, EVENT_LOG_DIR, METRICS_LOG_DIR; assert ARBITER_TICK_HZ == 20 and ARBITER_SCORE_WINDOW_S == 2.0; print('imports + constants ok')" && uv run mypy src/ingestion/ && uv run ruff check src/ tests/</automated>
  </verify>
  <done>
- src/ingestion/timestamps.py, events.py, __init__.py exist with the symbols above.
- src/config/constants.py declares ARBITER_TICK_HZ=20, ARBITER_SCORE_WINDOW_S=2.0, EVENT_LOG_DIR, METRICS_LOG_DIR.
- All imports succeed; smoke command prints "imports + constants ok".
- mypy src/ingestion/ — 0 errors (annotations fully typed).
- ruff check src/ tests/ — clean.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Implement Arbiter (3 deques + tick + commit/quarantine bridge); GREEN test_arbiter</name>
  <files>
    src/ingestion/arbiter.py
    src/ingestion/__init__.py
    tests/ingestion/test_arbiter.py
    tests/ingestion/conftest.py
  </files>
  <behavior>
    - `src/ingestion/arbiter.py` exposes `Arbiter` class with attributes `score_changes: deque[PendingEvent]`, `bomb_events: deque[PendingEvent]`, `round_end_events: deque[PendingEvent]`. NO `kill_events` or `numerical_flips` deques (DEC-006 v2 grep guard).
    - `Arbiter.__init__(self, initial_state: MatchState, *, event_log_dir: Path = Path(EVENT_LOG_DIR))`: sets initial state, computes per-match `_jsonl_path = event_log_dir / f"{initial_state.match_id}.jsonl"`. (Metrics path computed similarly but Task 3 wires it.)
    - `Arbiter.state` property returns the current MatchState.
    - `Arbiter.tick()` drains all 3 deques and applies confirmation rules:
        - **score_change rule (DEC-006 v2)**: ≥ 2 sources within ARBITER_SCORE_WINDOW_S (2s) on the SAME score event (matched by t_observed proximity AND identical fields_proposed) → commit. If only 1 source within the window after one full tick of the source emission, hold (don't quarantine yet — wait for next tick). Quarantine-then-clear-on-cross-confirm is too noisy; SPEC says "soft-confirm" Twitter never sole-sources, so a single-source score change just stays in the deque until either (a) a second source arrives OR (b) the deque max-age (3s wall-clock) elapses → quarantine.
        - **bomb_event rule (DEC-006 v2)**: 1 OCR source = soft-commit immediately. The hard-confirm-by-next-score logic is tracked via `_pending_bomb_confirm` — if a subsequent score commit arrives with consistent state, the bomb event is confirmed (silently); if a contradicting score commit arrives, no rollback (state already committed) but a logger.warning is emitted. The "1 OCR source soft-commit" semantics ARE the production contract — Phase 5 calibration revisits if false-positive rate too high.
        - **round_end_event rule (DEC-006 v2)**: 1 OCR source = soft-commit immediately. Same hard-confirm-by-next-score machinery as bomb.
    - On commit: arbiter calls `src.state.commit(prev_state, fields_changed, source=..., event_type=..., timestamps=..., jsonl_path=self._jsonl_path)` — which bumps seq_id, writes the diff line with `t_state_committed = mono_ns()` BEFORE the JSONL append (per RESEARCH §"Pattern 2" hot-path key insight). The new state replaces `self._state` AFTER commit() returns the new instance.
    - On quarantine: arbiter calls `src.state.quarantine(self._state, fields_proposed, source=..., event_type=..., quarantine_reason=..., t_observed=..., jsonl_path=self._jsonl_path)`. State UNCHANGED.
    - Single-writer invariant documented at the class docstring AND at every commit/quarantine call site (RESEARCH Pitfall 4).
    - `tests/ingestion/test_arbiter.py` (RED stubs from 03-00) all GREEN:
        - `test_score_change_two_source_rule`: push 1 PendingEvent from "ribgg", call tick — assert state UNCHANGED (single source). Push a 2nd PendingEvent from "ocr_score" with same fields_proposed and t_observed within ARBITER_SCORE_WINDOW_S, call tick — assert state UPDATED (commit fired). Read JSONL line, assert it has `seq_id`, `source` (or sources tuple — pick one), `event_type: "score_change"`, `fields_changed: {...}`.
        - `test_bomb_event_one_source_soft_commit`: push 1 PendingEvent from "ocr_bomb" with fields_proposed={"bomb_planted": True, "attackers_alive": 4, "defenders_alive": 3, "time_left_s": 45.0}, call tick — assert state UPDATED immediately. Read JSONL line, verify diff.
        - `test_round_end_one_source_soft_commit`: push 1 PendingEvent from "ocr_round_end" with fields_proposed={"a_round": 13, "b_round": 11}, call tick — assert state UPDATED immediately.
        - `test_quarantine_jsonl_format`: push a PendingEvent with stale t_observed (older than the 3s deque max-age), call tick — assert state UNCHANGED, JSONL line carries `seq_id: null, quarantined: true, quarantine_reason: "<reason>", fields_proposed: {...}`.
    - Conftest `arbiter_with_stub_sources` fixture upgraded from SimpleNamespace stub to a real Arbiter instance with empty deques + tmp_event_log_path wiring.
    - `src/ingestion/__init__.py` re-exports Arbiter.
    - mypy src/ingestion/ — 0 errors.
  </behavior>
  <action>
1) **Create `src/ingestion/arbiter.py`** (~250 LOC). Skeleton structure:

```python
"""DEC-006 v2 cross-source arbiter — 3 deques, simplified rules.

Sources push PendingEvents into the appropriate deque (score_changes,
bomb_events, round_end_events). The arbiter's tick() method drains the
deques, applies the per-event-type confirmation rules, and either:
  - commits (writes JSONL diff line via src.state.commit, swaps state ref), OR
  - quarantines (writes seq_id=null line via src.state.quarantine; state UNCHANGED), OR
  - holds (event stays in deque awaiting cross-confirm or max-age expiry).

CRITICAL invariants (RESEARCH Pitfall 4 / D-02):
- Arbiter is the SOLE writer of MatchState. NO other module calls state.with_update.
- Arbiter is the SOLE appender of data/event_log/{match_id}.jsonl.
- These two together guarantee seq_id monotonicity AND JSONL line atomicity
  (single writer + sub-PIPE_BUF lines).

DEC-006 v2 cuts from v1 (grep-verifiable absence):
- kill_events deque (kill-feed CV is gone — DEC-024 v2)
- numerical_flips deque (mid-round economy inference is gone — DEC-024 v2)
"""
from __future__ import annotations

import logging
from collections import deque
from pathlib import Path
from typing import Any

from src.config.constants import (
    ARBITER_SCORE_WINDOW_S,
    EVENT_LOG_DIR,
    METRICS_LOG_DIR,
)
from src.ingestion.events import EventType, PendingEvent, SourceName
from src.ingestion.timestamps import mono_ns, wall_time
from src.state import MatchState, commit, quarantine

logger = logging.getLogger(__name__)

_DEQUE_MAX_AGE_S: float = 3.0  # events older than this in the deque -> quarantine


class Arbiter:
    """Single-consumer arbiter for 3 ingestion deques (DEC-006 v2)."""

    def __init__(
        self,
        initial_state: MatchState,
        *,
        event_log_dir: Path | None = None,
        metrics_log_dir: Path | None = None,
    ) -> None:
        self._state = initial_state
        elog = event_log_dir or Path(EVENT_LOG_DIR)
        mlog = metrics_log_dir or Path(METRICS_LOG_DIR)
        self._jsonl_path = elog / f"{initial_state.match_id}.jsonl"
        self._metrics_path = mlog / f"{initial_state.match_id}.metrics.jsonl"
        self.score_changes: deque[PendingEvent] = deque(maxlen=128)
        self.bomb_events: deque[PendingEvent] = deque(maxlen=64)
        self.round_end_events: deque[PendingEvent] = deque(maxlen=64)

    @property
    def state(self) -> MatchState:
        return self._state

    @property
    def jsonl_path(self) -> Path:
        return self._jsonl_path

    @property
    def metrics_path(self) -> Path:
        return self._metrics_path

    def tick(self) -> None:
        """Drain all 3 deques; apply confirmation rules; commit / quarantine."""
        self._drain_score_changes()
        self._drain_bomb_events()
        self._drain_round_end_events()

    # --------------------------------------------------------------------- #
    # Rule: score_change — ≥ 2 sources within ARBITER_SCORE_WINDOW_S (2s)   #
    # --------------------------------------------------------------------- #
    def _drain_score_changes(self) -> None:
        if not self.score_changes:
            return
        now = wall_time()
        # Group by fields_proposed signature; commit if any group has ≥ 2 sources
        # within the window. Drop stale (older than _DEQUE_MAX_AGE_S) → quarantine.
        groups: dict[tuple[tuple[str, Any], ...], list[PendingEvent]] = {}
        survivors: deque[PendingEvent] = deque(maxlen=self.score_changes.maxlen)
        for ev in self.score_changes:
            if now - ev.t_observed > _DEQUE_MAX_AGE_S:
                # Stale event; quarantine.
                self._quarantine_event(ev, reason="stale_in_deque_no_cross_confirm")
                continue
            key = tuple(sorted(ev.fields_proposed.items()))
            groups.setdefault(key, []).append(ev)

        for sig, evs in groups.items():
            distinct_sources = {ev.source for ev in evs}
            if len(distinct_sources) >= 2 and self._within_window(evs):
                # Confirmed — commit using the EARLIEST t_observed (broadcast wall-clock)
                earliest = min(evs, key=lambda e: e.t_observed)
                fields_changed = dict(sig)
                self._commit_event(
                    fields_changed=fields_changed,
                    event_type=earliest.event_type,
                    sources=tuple(distinct_sources),
                    t_observed=earliest.t_observed,
                    t_ingested=earliest.t_ingested,
                )
            else:
                # Hold — re-queue all events in the group for next tick (may cross-confirm later)
                for ev in evs:
                    survivors.append(ev)

        self.score_changes = survivors

    @staticmethod
    def _within_window(evs: list[PendingEvent]) -> bool:
        ts = [ev.t_observed for ev in evs]
        return (max(ts) - min(ts)) <= ARBITER_SCORE_WINDOW_S

    # --------------------------------------------------------------------- #
    # Rule: bomb_event — 1 OCR source soft-commit immediately               #
    # --------------------------------------------------------------------- #
    def _drain_bomb_events(self) -> None:
        while self.bomb_events:
            ev = self.bomb_events.popleft()
            self._commit_event(
                fields_changed=dict(ev.fields_proposed),
                event_type=ev.event_type,
                sources=(ev.source,),
                t_observed=ev.t_observed,
                t_ingested=ev.t_ingested,
            )

    # --------------------------------------------------------------------- #
    # Rule: round_end_event — 1 OCR source soft-commit immediately          #
    # --------------------------------------------------------------------- #
    def _drain_round_end_events(self) -> None:
        while self.round_end_events:
            ev = self.round_end_events.popleft()
            self._commit_event(
                fields_changed=dict(ev.fields_proposed),
                event_type=ev.event_type,
                sources=(ev.source,),
                t_observed=ev.t_observed,
                t_ingested=ev.t_ingested,
            )

    # --------------------------------------------------------------------- #
    # Commit / quarantine plumbing — sole writer of MatchState + JSONL      #
    # --------------------------------------------------------------------- #
    def _commit_event(
        self,
        *,
        fields_changed: dict[str, Any],
        event_type: EventType,
        sources: tuple[SourceName, ...],
        t_observed: float,
        t_ingested: int,
    ) -> None:
        # Concatenate sources for JSONL provenance; commit() takes a single source string.
        source_str = "|".join(sources) if len(sources) > 1 else sources[0]
        timestamps: dict[str, float | int | None] = {
            "t_observed": t_observed,
            "t_ingested": t_ingested,
            "t_arbited": mono_ns(),
            "t_state_committed": None,  # commit() sets this AFTER with_update, BEFORE JSONL write
            "t_theo_computed": None,
            "t_quote_sent": None,
        }
        self._state = commit(
            self._state,
            fields_changed,
            source=source_str,
            event_type=event_type,
            timestamps=timestamps,
            jsonl_path=self._jsonl_path,
        )
        # Mirror to metrics log (Phase 4 fills t_theo_computed / t_quote_sent there)
        self._write_metrics_line(timestamps, source_str, event_type, fields_changed)

    def _quarantine_event(self, ev: PendingEvent, *, reason: str) -> None:
        quarantine(
            self._state,
            dict(ev.fields_proposed),
            source=ev.source,
            event_type=ev.event_type,
            quarantine_reason=reason,
            t_observed=ev.t_observed,
            jsonl_path=self._jsonl_path,
        )

    def _write_metrics_line(
        self,
        timestamps: dict[str, float | int | None],
        source: str,
        event_type: EventType,
        fields_changed: dict[str, Any],
    ) -> None:
        import json
        line = {
            "seq_id": self._state.seq_id,
            **timestamps,
            "source": source,
            "event_type": event_type,
            "fields_changed_keys": sorted(fields_changed.keys()),  # provenance only — no PII / no values
        }
        self._metrics_path.parent.mkdir(parents=True, exist_ok=True)
        with self._metrics_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(line, separators=(",", ":")) + "\n")
```

(The metrics-line writer mirrors the timestamps + adds the field-changed key list. It does NOT duplicate the JSONL diff log — separation of concerns: event_log = state replay; metrics = latency analysis.)

2) **Update `src/ingestion/__init__.py`** to re-export Arbiter:

```python
from src.ingestion.arbiter import Arbiter
# ... existing exports ...
__all__ = ["Arbiter", ...]
```

3) **Wire `tests/ingestion/test_arbiter.py`** (RED stubs from 03-00) to GREEN:

```python
"""REQ-cross-source-arbiter — DEC-006 v2 (3 deques) test suite (03-03)."""
import json
import time
import pytest
from pathlib import Path
from src.ingestion import Arbiter, PendingEvent, mono_ns, wall_time
from src.state.match_state import MatchState

def _make_state() -> MatchState:
    return MatchState(
        match_id="arbiter-test-001",
        team_a="A", team_b="B",
        map_pool=("Lotus", "Bind", "Haven"),
        map_side_orients=("a_atk", "a_def", "a_atk"),
        map_winners=(None, None, None),
        pistol_winner_a={0: None, 1: None, 2: None},
        map_idx=0, a_map_score=0, b_map_score=0,
        a_round=10, b_round=8,
        side_orient="atk",
        bomb_planted=False, attackers_alive=None, defenders_alive=None, time_left_s=None,
        seq_id=0, last_updated_ts=0.0,
    )

def test_score_change_two_source_rule(tmp_path):
    arb = Arbiter(_make_state(), event_log_dir=tmp_path / "event_log", metrics_log_dir=tmp_path / "metrics")
    initial_seq = arb.state.seq_id
    t = wall_time()
    fields = {"a_round": 11}

    # Push 1st source — single source, no commit
    arb.score_changes.append(PendingEvent(source="ribgg", event_type="score_change", fields_proposed=fields, t_observed=t, t_ingested=mono_ns()))
    arb.tick()
    assert arb.state.seq_id == initial_seq  # no commit yet

    # Push 2nd source within window — commits
    arb.score_changes.append(PendingEvent(source="ocr_score", event_type="score_change", fields_proposed=fields, t_observed=t + 0.5, t_ingested=mono_ns()))
    arb.tick()
    assert arb.state.seq_id == initial_seq + 1  # commit fired
    assert arb.state.a_round == 11

    # Verify JSONL line shape
    log_lines = (tmp_path / "event_log" / "arbiter-test-001.jsonl").read_text().strip().splitlines()
    assert len(log_lines) == 1
    line = json.loads(log_lines[0])
    assert line["seq_id"] == initial_seq + 1
    assert line["event_type"] == "score_change"
    assert line["fields_changed"] == {"a_round": 11}
    assert "ribgg" in line["source"] and "ocr_score" in line["source"]

def test_bomb_event_one_source_soft_commit(tmp_path):
    arb = Arbiter(_make_state(), event_log_dir=tmp_path / "event_log", metrics_log_dir=tmp_path / "metrics")
    initial_seq = arb.state.seq_id
    fields = {"bomb_planted": True, "attackers_alive": 4, "defenders_alive": 3, "time_left_s": 45.0}
    arb.bomb_events.append(PendingEvent(source="ocr_bomb", event_type="bomb_plant", fields_proposed=fields, t_observed=wall_time(), t_ingested=mono_ns()))
    arb.tick()
    assert arb.state.seq_id == initial_seq + 1  # immediate soft-commit
    assert arb.state.bomb_planted is True
    assert arb.state.attackers_alive == 4
    assert arb.state.defenders_alive == 3

def test_round_end_one_source_soft_commit(tmp_path):
    arb = Arbiter(_make_state(), event_log_dir=tmp_path / "event_log", metrics_log_dir=tmp_path / "metrics")
    initial_seq = arb.state.seq_id
    fields = {"a_round": 13, "b_round": 11}
    arb.round_end_events.append(PendingEvent(source="ocr_round_end", event_type="round_end", fields_proposed=fields, t_observed=wall_time(), t_ingested=mono_ns()))
    arb.tick()
    assert arb.state.seq_id == initial_seq + 1
    assert arb.state.a_round == 13
    assert arb.state.b_round == 11

def test_quarantine_jsonl_format(tmp_path):
    arb = Arbiter(_make_state(), event_log_dir=tmp_path / "event_log", metrics_log_dir=tmp_path / "metrics")
    initial_seq = arb.state.seq_id
    # Stale event — older than _DEQUE_MAX_AGE_S (3s)
    stale_t = wall_time() - 10.0
    fields = {"a_round": 11}
    arb.score_changes.append(PendingEvent(source="ribgg", event_type="score_change", fields_proposed=fields, t_observed=stale_t, t_ingested=mono_ns()))
    arb.tick()
    assert arb.state.seq_id == initial_seq  # NO commit (quarantined)

    log_lines = (tmp_path / "event_log" / "arbiter-test-001.jsonl").read_text().strip().splitlines()
    assert len(log_lines) == 1
    line = json.loads(log_lines[0])
    assert line["seq_id"] is None
    assert line["quarantined"] is True
    assert line["quarantine_reason"] == "stale_in_deque_no_cross_confirm"
    assert line["source"] == "ribgg"
    assert line["fields_proposed"] == {"a_round": 11}
```

Replace the xfail stubs with these implementations.

4) **Upgrade `tests/ingestion/conftest.py::arbiter_with_stub_sources`** fixture to return a real Arbiter:

```python
@pytest.fixture
def arbiter_with_stub_sources(tmp_path):
    """Real Arbiter wired to tmp event log + metrics — sources push directly into deques."""
    from src.ingestion import Arbiter
    from src.state.match_state import MatchState

    initial = MatchState(
        match_id="conftest-arbiter-001",
        team_a="A", team_b="B",
        map_pool=("Lotus",), map_side_orients=("a_atk",), map_winners=(None,),
        pistol_winner_a={0: None},
        map_idx=0, a_map_score=0, b_map_score=0, a_round=0, b_round=0,
        side_orient="atk",
        bomb_planted=False, attackers_alive=None, defenders_alive=None, time_left_s=None,
        seq_id=0, last_updated_ts=0.0,
    )
    return Arbiter(initial, event_log_dir=tmp_path / "event_log", metrics_log_dir=tmp_path / "metrics")
```

5) **Run the v2 grep-guard** to confirm no kill_events / numerical_flips substrings in arbiter.py.

Atomic commit message: `feat(03-03): Arbiter (3 deques + tick + commit/quarantine bridge) per DEC-006 v2`
  </action>
  <verify>
    <automated>uv run pytest tests/ingestion/test_arbiter.py -v -x --no-cov && uv run mypy src/ingestion/ && ! grep -E "kill_events|numerical_flips" src/ingestion/arbiter.py && uv run ruff check src/ingestion/ tests/ingestion/</automated>
  </verify>
  <done>
- src/ingestion/arbiter.py exists with Arbiter class + 3 deques (score_changes, bomb_events, round_end_events) + tick() + per-rule drain methods.
- tests/ingestion/test_arbiter.py — 4 tests GREEN.
- DEC-006 v2 grep guard PASSES: no `kill_events|numerical_flips` substrings in arbiter.py.
- src/ingestion/__init__.py re-exports Arbiter.
- tests/ingestion/conftest.py::arbiter_with_stub_sources returns a real Arbiter.
- mypy src/ingestion/ — 0 errors.
- ruff check — clean.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: GREEN test_six_stage_populated — verify metrics line carries all 6 timestamps</name>
  <files>
    tests/ingestion/test_latency.py
  </files>
  <behavior>
    - `tests/ingestion/test_latency.py::test_six_stage_populated` GREEN:
        - Build an Arbiter via the conftest fixture; push a bomb_event; call tick.
        - Read the metrics file at `arbiter.metrics_path`; parse the single JSON line.
        - Assert all six keys exist in the line: `t_observed`, `t_ingested`, `t_arbited`, `t_state_committed`, `t_theo_computed`, `t_quote_sent`.
        - Assert `t_observed` is a float (wall-clock seconds — sanity-check it's within 60s of `time.time()` at test start).
        - Assert `t_ingested`, `t_arbited`, `t_state_committed` are ints (monotonic_ns).
        - Assert `t_arbited >= t_ingested` and `t_state_committed >= t_arbited` (monotonic ordering of the 3 in-Phase-3 stages).
        - Assert `t_theo_computed is None and t_quote_sent is None` (Phase 3 reservation per D-03).
        - Assert the Arbiter's JSONL diff log (event_log/) ALSO carries all 6 timestamps on its commit line (the metrics line and the JSONL line are sibling artifacts; both must populate the same 6-key set).
  </behavior>
  <action>
1) **Wire `tests/ingestion/test_latency.py`** (RED stub from 03-00) to GREEN:

```python
"""REQ-latency-instrumentation — six-stage timestamp lineage test (03-03 / D-03)."""
import json
import time
import pytest
from src.ingestion import PendingEvent, mono_ns, wall_time

def test_six_stage_populated(arbiter_with_stub_sources):
    """Every confirmed event JSONL line + metrics line carries all 6 timestamps."""
    arb = arbiter_with_stub_sources
    test_start_wall = time.time()

    # Push a bomb_event — single OCR source soft-commit
    fields = {"bomb_planted": True, "attackers_alive": 4, "defenders_alive": 3, "time_left_s": 45.0}
    arb.bomb_events.append(PendingEvent(
        source="ocr_bomb", event_type="bomb_plant",
        fields_proposed=fields,
        t_observed=wall_time(),
        t_ingested=mono_ns(),
    ))
    arb.tick()

    # Read metrics line
    metrics_lines = arb.metrics_path.read_text().strip().splitlines()
    assert len(metrics_lines) == 1
    metrics = json.loads(metrics_lines[0])
    SIX_KEYS = ("t_observed", "t_ingested", "t_arbited", "t_state_committed", "t_theo_computed", "t_quote_sent")
    for k in SIX_KEYS:
        assert k in metrics, f"metrics line missing {k}"
    assert isinstance(metrics["t_observed"], float)
    assert abs(metrics["t_observed"] - test_start_wall) < 60.0  # sanity: within minute of test start
    assert isinstance(metrics["t_ingested"], int)
    assert isinstance(metrics["t_arbited"], int)
    assert isinstance(metrics["t_state_committed"], int)
    # Monotonic ordering of the 3 in-Phase-3 stages
    assert metrics["t_arbited"] >= metrics["t_ingested"]
    assert metrics["t_state_committed"] >= metrics["t_arbited"]
    # Phase 3 reservations
    assert metrics["t_theo_computed"] is None
    assert metrics["t_quote_sent"] is None

    # JSONL diff log mirrors the same 6 timestamps
    jsonl_lines = arb.jsonl_path.read_text().strip().splitlines()
    assert len(jsonl_lines) == 1
    jsonl = json.loads(jsonl_lines[0])
    for k in SIX_KEYS:
        assert k in jsonl, f"JSONL line missing {k}"
    assert jsonl["t_state_committed"] == metrics["t_state_committed"]  # same commit-time anchor
```

Replace the xfail stub with this implementation.

Atomic commit message: `test(03-03): six-stage timestamp lineage assertion (REQ-latency-instrumentation)`
  </action>
  <verify>
    <automated>uv run pytest tests/ingestion/test_latency.py tests/ingestion/test_arbiter.py -v -x --no-cov && uv run pytest tests/ -x --no-cov -k "not test_calibrate_round_conclusion"</automated>
  </verify>
  <done>
- tests/ingestion/test_latency.py::test_six_stage_populated GREEN.
- All 4 arbiter tests STILL GREEN (Task 2 work preserved).
- Phase 1+2 regression suite STILL GREEN.
- Both JSONL and metrics files carry the 6-key timestamp record on commit lines.
  </done>
</task>

</tasks>

<verification>
- `uv run pytest tests/ingestion/test_arbiter.py tests/ingestion/test_latency.py -v` — 5 tests pass.
- `! grep -E "kill_events|numerical_flips" src/ingestion/arbiter.py` — 0 hits (DEC-006 v2 grep guard).
- `uv run mypy src/ingestion/ src/state/` — 0 errors.
- `uv run ruff check src/ tests/` — clean.
- All Phase 1+2 + 03-01 + 03-02 tests STILL GREEN under the new module structure.
</verification>

<success_criteria>
- REQ-cross-source-arbiter SPEC acceptance #5 GREEN: 3 deques exist; rule per event-type fires; quarantined events appear in JSONL with seq_id: null.
- REQ-latency-instrumentation SPEC acceptance #6 GREEN: every confirmed event carries 6 timestamps; t_quote_sent / t_theo_computed = None reserved.
- DEC-006 v2 grep guard PASSED.
- Single-writer invariant documented + structurally enforced.
</success_criteria>

<output>
After completion, create `.planning/phases/03-live-ingestion-layer/03-03-SUMMARY.md`
documenting:
- 3 deques shipped (score_changes, bomb_events, round_end_events) + 0 deques NOT shipped (kill_events, numerical_flips per DEC-006 v2)
- Confirmation rules per event_type (≥2 sources / 1 OCR soft-commit / 1 OCR soft-commit)
- 6-key TimestampRecord shape + time discipline (wall_time vs mono_ns)
- Single-writer invariant (Arbiter is sole caller of state.with_update + sole appender of jsonl_path)
- 4 arbiter tests GREEN + 1 latency test GREEN
- New constants: ARBITER_TICK_HZ, ARBITER_SCORE_WINDOW_S, EVENT_LOG_DIR, METRICS_LOG_DIR
- next-wave dependency: 03-04 (scoreboard), 03-05 (OCR), 03-06 (text listener) push PendingEvents into Arbiter deques; 03-08 E2E gate consumes the JSONL+metrics files
</output>
</content>
</invoke>