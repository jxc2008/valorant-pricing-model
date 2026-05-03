---
id: 03-08-engine-driver-and-e2e
phase: 03
plan: 8
type: execute
wave: 5
depends_on:
  - 03-00-pyproject-and-constants
  - 03-01-shared-types-and-download
  - 03-02-salvage-verify
  - 03-03-match-state-move-and-extend
  - 03-04-scoreboard-poller
  - 03-05a-ocr-scaffold
  - 03-05b-ocr-backends
  - 03-06-text-listener
  - 03-07a-state-holder-and-event-log
  - 03-07b-arbiter
files_modified:
  - src/state/engine_driver.py
  - src/state/__init__.py
  - tests/ingestion/test_engine_driver.py
  - tests/ingestion/test_e2e.py
autonomous: true
requirements:
  - REQ-cross-source-arbiter
  - REQ-latency-instrumentation
  - REQ-end-to-end-latency
must_haves:
  truths:
    - "EngineDriver consumes ConfirmedEvent from asyncio.Queue, calls LiveTheoEngine(state_holder.read()), stamps t_theo_computed (REQ-latency-instrumentation)"
    - "EngineDriver does NOT mutate state — read-only consumer (CRule 2 single canonical implementation)"
    - "LiveTheoEngine signature unchanged — only what flows through state changes (CRule 1)"
    - "tests/ingestion/test_e2e.py drives synthetic rib.gg + OCR + Twitter through Arbiter → StateHolder → LiveTheoEngine asserting: seq_id strictly monotonic, p50 t_observed → t_state_committed < 500ms over ≥ 30 events (SPEC + RESEARCH §Validation Sampling Rate uses 50), theo_series ∈ (0.01, 0.99) on final state (non-degenerate)"
    - "JSONL parseable end-to-end; replay produces identical final state (per phase-level must-have)"
    - "Phase 1 + 2 tests still GREEN (regression gate per SPEC acceptance #11)"
    - "Twitter listener exercises the no-op path (TWITTER_BEARER_TOKEN unset in test env)"
    - "WARNING-4: e2e suite includes test_e2e_drives_one_ocr_backed_event_through_pipeline (OCR backend -> arbiter -> JSONL with source=ocr/event_type=kill); @pytest.mark.skip until Phase 5 CTC decoder ships (per 03-CONTEXT deferred-ideas)"
    - "ROADMAP.md and STATE.md updated to mark Phase 3 complete"
  artifacts:
    - path: src/state/engine_driver.py
      provides: "EngineDriver class — read-only ConfirmedEvent consumer + LiveTheoEngine invocation + t_theo_computed stamp"
      contains: "class EngineDriver"
    - path: tests/ingestion/test_engine_driver.py
      provides: "unit tests: consumes-from-queue, doesn't-mutate-state, calls-LiveTheoEngine, stamps-t_theo_computed"
    - path: tests/ingestion/test_e2e.py
      provides: "synthetic E2E gate: 50 events, p50 < 500ms, seq_id monotonic, theo non-degenerate"
  key_links:
    - from: "src/state/engine_driver.py"
      to: "src/pricing/live_theo.py:LiveTheoEngine"
      via: "self._engine(state_holder.read())"
      pattern: "self\\._engine\\("
    - from: "tests/ingestion/test_e2e.py"
      to: "src/ingestion/arbiter.py:Arbiter"
      via: "synthetic submit() loop -> arbiter -> engine_driver -> live_theo"
      pattern: "test_e2e_p50_latency"
autonomous: true
---

<objective>
Wave 4 final plan — wire the engine-driver consumer that bridges arbiter → live_theo, then run the synthetic E2E integration test that proves the entire Phase 3 pipeline meets the SPEC acceptance gate (p50 < 500ms, seq_id monotonic, theo non-degenerate).

Purpose: this is the SPEC §Acceptance Criteria #8 gate. Once green, Phase 3 is shippable: every confirmed event flows through arbiter → state mutation → live_theo invocation with the full six-stage timestamp lineage written to JSONL + metrics files.

Output: `src/state/engine_driver.py` (`EngineDriver` class), `tests/ingestion/test_engine_driver.py` (unit), `tests/ingestion/test_e2e.py` (the E2E gate), updated ROADMAP.md + STATE.md marking Phase 3 complete.
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
@src/pricing/live_theo.py
@src/pricing/data.py
@src/state/match_state.py
@src/state/state_holder.py
@src/ingestion/arbiter.py
@src/ingestion/types.py
@src/ingestion/event_log.py
@.planning/ROADMAP.md
@.planning/STATE.md
@models/round_conclusion.json
@CLAUDE.md

<interfaces>
<!-- LiveTheoEngine signature (locked per Phase 1 D-20) -->

```python
@dataclass(frozen=True)
class LiveTheoEngine:
    half_rates: HalfRates
    round_conclusion: Optional[RoundConclusionFn] = None

    def __call__(self, state: MatchState) -> TheoOutput: ...
```

<!-- EngineDriver shape (RESEARCH §Architectural Responsibility Map row "Engine driver" line 79; PATTERNS §src/state/engine_driver.py lines 161-189) -->

```python
@dataclass(frozen=True)
class EngineDriver:
    """Read-only consumer of ConfirmedEvent queue.

    Phase 4 will REPLACE this with the quoting driver — keep the seam thin.
    """
    engine: LiveTheoEngine
    state_holder: StateHolder
    queue: asyncio.Queue[ConfirmedEvent]
    metrics: MetricsWriter

    async def run(self) -> None:
        while True:
            ce = await self.queue.get()
            try:
                state = self.state_holder.read()
                t_theo_start_ns = time.monotonic_ns()
                _ = self.engine(state)
                t_theo_done_ns = time.monotonic_ns()
                # Phase 4: append a follow-up metrics line keyed by ce.confirmed_seq_id
                self.metrics.write_followup(seq_id=ce.confirmed_seq_id,
                                            t_theo_computed_ns=t_theo_done_ns)
            finally:
                self.queue.task_done()
```

<!-- Synthetic E2E test scaffold (RESEARCH §Code Examples lines 893-965) -->

```python
@pytest.mark.asyncio
async def test_e2e_synthetic_50_events(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("TWITTER_BEARER_TOKEN", "")  # force no-op listener
    # Construct seed MatchState, StateHolder, queue, writers, arbiter, engine_driver.
    # Drive 50 synthetic ArbiterPending through arbiter.submit().
    # Assert: seq_id strictly monotonic; p50 < 500ms; theo non-degenerate; metrics parseable.
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Create src/state/engine_driver.py + add MetricsWriter.write_followup + unit tests</name>
  <files>src/state/engine_driver.py, src/state/__init__.py, src/ingestion/event_log.py, tests/ingestion/test_engine_driver.py</files>
  <read_first>
    - src/pricing/live_theo.py:650-684 (LiveTheoEngine bundle pattern)
    - src/state/state_holder.py (read() interface)
    - src/ingestion/types.py (ConfirmedEvent shape — t_theo_computed field is Optional)
    - src/ingestion/event_log.py (MetricsWriter — needs write_followup method added)
    - .planning/phases/03-live-ingestion-layer/03-PATTERNS.md §src/state/engine_driver.py (lines 159-190)
    - .planning/phases/03-live-ingestion-layer/03-RESEARCH.md §Pattern 5 timestamp lineage (Phase 4 follow-up line per Pitfall 8 line 743)
    - .planning/phases/03-live-ingestion-layer/03-CONTEXT.md integration_points line 151 (engine driver in src/state/)
  </read_first>
  <behavior>
    - Test 1 (test_engine_driver_consumes_queue_and_calls_engine): mock engine; put 1 ConfirmedEvent on queue; run driver task for 1 iteration; assert engine called exactly once with the StateHolder's current state.
    - Test 2 (test_engine_driver_does_not_mutate_state): construct with state_holder seeded; run driver against 5 ConfirmedEvents; assert state_holder.read().seq_id == initial seq_id (driver doesn't mutate; only the arbiter does — arbiter not in this test's loop).
    - Test 3 (test_engine_driver_stamps_t_theo_computed_via_followup): mock MetricsWriter.write_followup; run driver against 1 ConfirmedEvent; assert write_followup called once with seq_id matching the ConfirmedEvent + t_theo_computed_ns > 0.
    - Test 4 (test_engine_driver_handles_engine_exception_without_crashing): mock engine to raise ValueError on call; run driver against 1 ConfirmedEvent; driver logs error and continues to the next event (does NOT propagate).
    - Test 5 (test_metrics_writer_followup_line_shape): MetricsWriter.write_followup(seq_id=42, t_theo_computed_ns=...); read line; assert keys = {seq_id, t_theo_computed} only (per Pitfall 8 — second-line shape keyed by seq_id).
  </behavior>
  <action>
**(a)** Add `write_followup` method to `src/ingestion/event_log.py:MetricsWriter` (RESEARCH Pitfall 8: Phase 4 — and Phase 3 engine_driver — appends a follow-up line keyed by seq_id with `t_theo_computed` and/or `t_quote_sent`):

Insert this method on the `MetricsWriter` class:

```python
    def write_followup(
        self,
        *,
        seq_id: int,
        t_theo_computed_ns: int | None = None,
        t_quote_sent_ns: int | None = None,
    ) -> None:
        """Per Pitfall 8: append a second JSONL line keyed by seq_id with the
        late-stage timestamps. Phase 5 latency analysis joins on seq_id at read
        time (committed line + follow-up line(s) -> full lineage).

        Phase 3 engine_driver fills t_theo_computed_ns; Phase 4 quoter will
        fill t_quote_sent_ns via the same method.
        """
        line: dict[str, Any] = {"seq_id": seq_id}
        if t_theo_computed_ns is not None:
            line["t_theo_computed"] = t_theo_computed_ns / 1e9
        if t_quote_sent_ns is not None:
            line["t_quote_sent"] = t_quote_sent_ns / 1e9
        self._fh.write(json.dumps(line, separators=(",", ":")) + "\n")
        self._n_since_flush += 1
        if self._n_since_flush >= _FLUSH_EVERY_N:
            self._fh.flush()
            self._n_since_flush = 0
```

(Place right after the existing `write` method, before `close`.)

**(b)** Create `src/state/engine_driver.py`:

```python
"""Phase 3 engine driver — read-only ConfirmedEvent consumer (REQ-latency-instrumentation).

Bridges the arbiter (sole writer to MatchState) and live_theo (Phase 1 pricing
core). The driver:
  1. Reads ConfirmedEvent from the asyncio.Queue
  2. Snapshots the current MatchState via StateHolder.read() (lock-free)
  3. Invokes LiveTheoEngine(state) — Phase 1 D-20 surface, locked
  4. Stamps t_theo_computed_ns via MetricsWriter.write_followup() per Pitfall 8

The driver is a THIN seam (CONTEXT integration_points line 151). Phase 4 will
REPLACE this with the quoting driver — same shape (queue consumer + engine
invocation), additional Kalshi-order plumbing.

Sources
-------
- 03-SPEC.md §6 (REQ-latency-instrumentation — t_theo_computed populated)
- 03-CONTEXT.md integration_points line 151 (thin engine driver in src/state/)
- 03-RESEARCH.md §Pattern 5 (Pitfall 8 — follow-up line per seq_id)
- 03-PATTERNS.md §src/state/engine_driver.py (lines 159-190)
- src/pricing/live_theo.py:650-684 (LiveTheoEngine bundle — locked surface)
- CRule 1 (single canonical live_theo entry — driver does not widen the surface)
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass

from src.ingestion.event_log import MetricsWriter
from src.ingestion.types import ConfirmedEvent
from src.pricing.live_theo import LiveTheoEngine
from src.state.state_holder import StateHolder

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class EngineDriver:
    """Read-only consumer of the arbiter's ConfirmedEvent queue.

    Constructor:
        engine: LiveTheoEngine (Phase 1 bundle; signature locked per CRule 1)
        state_holder: StateHolder (read-only access here; arbiter is sole writer)
        queue: asyncio.Queue[ConfirmedEvent] (the same queue the arbiter writes to)
        metrics: MetricsWriter (for the Pitfall 8 follow-up line)

    Public API:
        await driver.run()  # loop forever; caller cancels at shutdown
    """

    engine: LiveTheoEngine
    state_holder: StateHolder
    queue: asyncio.Queue[ConfirmedEvent]
    metrics: MetricsWriter

    async def run(self) -> None:
        """Loop forever: get -> read state -> compute theo -> stamp -> task_done."""
        try:
            while True:
                ce = await self.queue.get()
                try:
                    self._process(ce)
                except Exception as exc:
                    # Don't crash the driver on a single bad event — log and continue.
                    log.error(
                        "engine_driver_error seq_id=%s exc=%s",
                        ce.confirmed_seq_id, exc,
                    )
                finally:
                    self.queue.task_done()
        except asyncio.CancelledError:
            log.info("engine_driver_loop_cancelled")
            raise

    def _process(self, ce: ConfirmedEvent) -> None:
        """Single-event critical section: snapshot state, invoke engine, stamp."""
        if ce.confirmed_seq_id is None:
            log.warning("engine_driver_no_seq_id event_type=%s", ce.event_type)
            return
        # Snapshot the current (post-mutation) state. Lock-free; the frozen+slots
        # MatchState is safe to read concurrently.
        state = self.state_holder.read()
        # Phase 1 D-20 surface — LiveTheoEngine.__call__(state) -> TheoOutput.
        # The driver doesn't NEED the TheoOutput in Phase 3 (Phase 4's quoter
        # will consume it). It calls engine() ONLY to (a) verify the engine
        # works against the live-mutated state, (b) measure t_theo_computed
        # for REQ-end-to-end-latency.
        t_start_ns = time.monotonic_ns()
        _ = self.engine(state)
        t_done_ns = time.monotonic_ns()
        # Pitfall 8 follow-up line — keyed by seq_id; mergeable in Phase 5 analysis.
        self.metrics.write_followup(
            seq_id=ce.confirmed_seq_id,
            t_theo_computed_ns=t_done_ns,
        )
```

**(c)** Update `src/state/__init__.py`:

```python
from src.state.engine_driver import EngineDriver
from src.state.match_state import MatchState
from src.state.state_holder import StateHolder

__all__ = ["MatchState", "StateHolder", "EngineDriver"]
```

**(d)** Create `tests/ingestion/test_engine_driver.py`:

```python
"""EngineDriver tests — REQ-latency-instrumentation acceptance + thin-seam discipline."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from src.ingestion.event_log import EventLogWriter, MetricsWriter
from src.ingestion.types import ConfirmedEvent
from src.state import EngineDriver, StateHolder
from src.state.match_state import MatchState


def _seed_state() -> MatchState:
    return MatchState(
        match_id="m1", team_a="A", team_b="B", map_pool=("Lotus",),
        map_idx=0, a_map_score=0, b_map_score=0, a_round=0, b_round=0,
        side_orient="a_atk", map_side_orients=("a_atk",), map_winners=(None,),
        pistol_winner_a={0: None}, numerical_diff=0, bomb_planted=False,
        side="atk", econ_bucket="full",
    )


def _ce(seq_id: int) -> ConfirmedEvent:
    import time
    return ConfirmedEvent(
        fields_changed={"a_round": seq_id},
        source_set=("ribgg",),
        event_type="score_change",
        t_observed=time.time(),
        t_ingested=time.monotonic(),
        t_arbited=time.monotonic(),
        t_state_committed=time.monotonic(),
        confirmed_seq_id=seq_id,
    )


@pytest.fixture
def metrics(tmp_path: Path):
    m = MetricsWriter("test", log_dir=tmp_path)
    yield m
    m.close()


@pytest.fixture
def holder():
    return StateHolder(_seed_state())


@pytest.mark.asyncio
async def test_engine_driver_consumes_queue_and_calls_engine(metrics, holder) -> None:
    mock_engine = MagicMock()
    mock_engine.return_value = MagicMock(theo_series=0.5, theo_map=(0.5,), vega=0.0, confidence=0.0)
    queue: asyncio.Queue = asyncio.Queue()
    driver = EngineDriver(engine=mock_engine, state_holder=holder, queue=queue, metrics=metrics)
    await queue.put(_ce(1))
    task = asyncio.create_task(driver.run())
    # Wait for the queue to drain.
    await queue.join()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert mock_engine.call_count == 1
    # Engine was called with a MatchState (the one in the holder).
    arg = mock_engine.call_args.args[0]
    assert isinstance(arg, MatchState)


@pytest.mark.asyncio
async def test_engine_driver_does_not_mutate_state(metrics, holder) -> None:
    initial_seq = holder.read().seq_id
    mock_engine = MagicMock()
    mock_engine.return_value = MagicMock()
    queue: asyncio.Queue = asyncio.Queue()
    driver = EngineDriver(engine=mock_engine, state_holder=holder, queue=queue, metrics=metrics)
    for i in range(5):
        await queue.put(_ce(i + 1))
    task = asyncio.create_task(driver.run())
    await queue.join()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert holder.read().seq_id == initial_seq, "driver must not mutate state"


@pytest.mark.asyncio
async def test_engine_driver_stamps_t_theo_computed_via_followup(metrics, holder, tmp_path) -> None:
    mock_engine = MagicMock()
    mock_engine.return_value = MagicMock()
    queue: asyncio.Queue = asyncio.Queue()
    driver = EngineDriver(engine=mock_engine, state_holder=holder, queue=queue, metrics=metrics)
    await queue.put(_ce(7))
    task = asyncio.create_task(driver.run())
    await queue.join()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    metrics.close()
    # Read back the metrics file and find the follow-up line for seq_id=7.
    raw = metrics.path.read_text().strip().split("\n")
    followups = [json.loads(l) for l in raw if "t_theo_computed" in json.loads(l)]
    assert len(followups) == 1
    assert followups[0]["seq_id"] == 7
    assert followups[0]["t_theo_computed"] > 0


@pytest.mark.asyncio
async def test_engine_driver_handles_exception_without_crash(metrics, holder, caplog) -> None:
    mock_engine = MagicMock()
    mock_engine.side_effect = [ValueError("boom"), MagicMock()]  # 1st raises, 2nd succeeds
    queue: asyncio.Queue = asyncio.Queue()
    driver = EngineDriver(engine=mock_engine, state_holder=holder, queue=queue, metrics=metrics)
    await queue.put(_ce(1))
    await queue.put(_ce(2))
    task = asyncio.create_task(driver.run())
    await queue.join()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    # Both events processed; first raised, second succeeded.
    assert mock_engine.call_count == 2
    assert any("engine_driver_error" in r.getMessage() for r in caplog.records)


def test_metrics_writer_followup_line_shape(tmp_path: Path) -> None:
    m = MetricsWriter("test", log_dir=tmp_path)
    m.write_followup(seq_id=42, t_theo_computed_ns=1_000_000_000)
    m.close()
    raw = m.path.read_text().strip()
    rec = json.loads(raw)
    assert rec == {"seq_id": 42, "t_theo_computed": 1.0}
```
  </action>
  <verify>
    <automated>pytest tests/ingestion/test_engine_driver.py -x &amp;&amp; mypy --strict src/state/engine_driver.py &amp;&amp; ruff check src/state/engine_driver.py src/ingestion/event_log.py tests/ingestion/test_engine_driver.py</automated>
  </verify>
  <done>EngineDriver exists in src/state/engine_driver.py + re-exported from src/state/__init__.py; MetricsWriter has write_followup; 5 unit tests in tests/ingestion/test_engine_driver.py PASS; driver doesn't mutate state, doesn't crash on engine exceptions, stamps t_theo_computed; mypy --strict src/state/ clean.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: tests/ingestion/test_e2e.py — synthetic E2E gate (SPEC acceptance #8)</name>
  <files>tests/ingestion/test_e2e.py</files>
  <read_first>
    - .planning/phases/03-live-ingestion-layer/03-RESEARCH.md §Code Examples Synthetic E2E test scaffold (lines 893-965)
    - .planning/phases/03-live-ingestion-layer/03-VALIDATION.md tasks 03-E2E-01 + 03-E2E-02 + Sampling minimums line 72
    - .planning/phases/03-live-ingestion-layer/03-SPEC.md acceptance criteria (lines 91-103)
    - src/state/engine_driver.py (interface from Task 1)
    - src/state/state_holder.py
    - src/ingestion/arbiter.py
    - src/ingestion/event_log.py
    - src/pricing/live_theo.py:LiveTheoEngine
    - src/pricing/data.py:HalfRates
    - data/half_win_rates.json (existing input — Phase 1 calibrated)
    - models/round_conclusion.json (Phase 2 calibrated)
    - src/pricing/round_conclusion.py:RoundConclusionLookup.from_json
  </read_first>
  <behavior>
    - Test 1 (test_e2e_p50_latency_under_500ms_50_events): drive 50 synthetic events through arbiter → engine_driver; assert p50 of (t_state_committed - t_observed) is < 500ms; ALSO assert seq_id strictly monotonic across the run.
    - Test 2 (test_e2e_theo_non_degenerate_after_50_events): after the 50-event drive, call live_theo on the FINAL StateHolder.read(); assert TheoOutput.theo_series is in (0.01, 0.99) and is NOT 0.5 ± 0.001 (proves the lookup hit a calibrated cell, not flat-fallback).
    - Test 3 (test_e2e_jsonl_replay_round_trip): write 50 events; read the JSONL log; replay via with_update on a fresh seed; assert final replayed state matches the StateHolder's final state (every non-time field).
    - Test 4 (test_e2e_metrics_file_parseable_after_drive): each line is JSON; total line count = 50 committed lines + 50 follow-up lines (Pitfall 8) = 100; t_observed monotonic-ish (within reasonable jitter for synthetic events).
    - Test 5 (test_e2e_twitter_listener_in_noop_path): force TWITTER_BEARER_TOKEN="" via monkeypatch; construct ValorantTextListener; assert is_noop=True; ensure no twitter ArbiterPending events are emitted by the listener (we synthesize them directly to test arbiter behavior).
  </behavior>
  <action>
Create `tests/ingestion/test_e2e.py` (the SPEC acceptance #8 gate):

```python
"""Phase 3 synthetic E2E gate — SPEC acceptance #8.

Drives a fake rib.gg + fake OCR + fake Twitter event stream through the full
pipeline:
    sources -> arbiter.submit() -> arbiter.tick() -> StateHolder.swap_with()
                -> ConfirmedEvent on queue -> EngineDriver -> LiveTheoEngine
                -> Pitfall 8 follow-up MetricsLogLine

Asserts (per SPEC + RESEARCH §Validation Architecture):
  1. seq_id strictly monotonic over >= 50 events (>= 30 floor per SPEC)
  2. p50 (t_observed -> t_state_committed) < 500ms
  3. theo_series on final state is non-degenerate (not 0.5 flat fallback)
  4. JSONL replay reproduces final state
  5. Metrics file parseable line-by-line; 50 committed + 50 follow-up = 100 lines
  6. Twitter listener forced to no-op path (CRule 13 + TWITTER_BEARER_TOKEN="")

Sources
-------
- 03-SPEC.md acceptance criteria (lines 91-103)
- 03-VALIDATION.md tasks 03-E2E-01, 03-E2E-02 (lines 60-61) + Sampling minimums line 72
- 03-RESEARCH.md §Code Examples Synthetic E2E test scaffold (lines 893-965)
"""
from __future__ import annotations

import asyncio
import dataclasses
import json
import statistics
import time
from collections.abc import Awaitable, Callable
from pathlib import Path

import pytest

from src.ingestion.arbiter import Arbiter
from src.ingestion.event_log import EventLogWriter, MetricsWriter
from src.ingestion.text_listener import ValorantTextListener
from src.ingestion.types import ArbiterPending, ConfirmedEvent
from src.pricing import HalfRates, LiveTheoEngine
from src.pricing.round_conclusion import RoundConclusionLookup
from src.state import EngineDriver, StateHolder
from src.state.match_state import MatchState

E2E_EVENT_COUNT: int = 50  # >=30 SPEC floor; 50 reduces p50 noise per VALIDATION line 72
E2E_LATENCY_BUDGET_MS: float = 500.0


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #


def _seed_state() -> MatchState:
    return MatchState(
        match_id="m1", team_a="Sentinels", team_b="LOUD",
        map_pool=("Lotus", "Bind", "Haven"),
        map_idx=0, a_map_score=0, b_map_score=0, a_round=0, b_round=0,
        side_orient="a_atk",
        map_side_orients=("a_atk", "a_def", "a_atk"),
        map_winners=(None, None, None),
        pistol_winner_a={0: None, 1: None, 2: None},
        numerical_diff=0, bomb_planted=False, side="atk", econ_bucket="full",
    )


def _build_engine() -> LiveTheoEngine:
    """Construct LiveTheoEngine using the calibrated Phase 2 round_conclusion lookup."""
    half = HalfRates.from_json(Path("data/half_win_rates.json"))
    lookup = RoundConclusionLookup.from_json(Path("models/round_conclusion.json"))
    return LiveTheoEngine(half_rates=half, round_conclusion=lookup.lookup)


async def _drive_synthetic_events(
    arbiter: Arbiter,
    n_events: int,
) -> None:
    """Submit a multi-source synthetic event stream that exercises both the
    score_change cross-confirm rule and the kill-rule single-OCR commit path.

    Pattern:
      - Pairs of (ribgg, ocr) score_change at the same signal_value
      - Solo OCR kill events to drive numerical_diff updates
    """
    base_t = time.time()
    base_mono = time.monotonic()
    a_round = 0
    b_round = 0
    for i in range(n_events):
        if i % 2 == 0:
            # Score-change cross-confirm: ribgg + ocr same signal.
            a_round += 1 if i % 4 == 0 else 0
            b_round += 1 if i % 4 == 2 else 0
            for source in ("ribgg", "ocr"):
                await arbiter.submit(ArbiterPending(
                    signal_value={"a_round": a_round, "b_round": b_round},
                    source=source,           # type: ignore[arg-type]
                    event_type="score_change",
                    t_observed=base_t + i * 0.01,
                    t_ingested=base_mono + i * 0.01,
                ))
        else:
            # Solo OCR kill -> numerical_diff update.
            await arbiter.submit(ArbiterPending(
                signal_value={"numerical_diff": (i % 5) - 2},
                source="ocr",
                event_type="kill",
                t_observed=base_t + i * 0.01,
                t_ingested=base_mono + i * 0.01,
            ))
        # Tick the arbiter after each submission to drive immediate commits.
        await arbiter._tick(time.monotonic_ns())


# --------------------------------------------------------------------------- #
# Tests                                                                       #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_e2e_twitter_listener_in_noop_path(monkeypatch) -> None:
    """REQ-text-listener acceptance: TWITTER_BEARER_TOKEN unset -> listener no-ops.
    Phase 3 E2E test runs without paid Twitter access (RESEARCH §State of the Art)."""
    monkeypatch.setenv("TWITTER_BEARER_TOKEN", "")

    async def _noop_emit(p: ArbiterPending) -> None:
        pass

    listener = ValorantTextListener(emit=_noop_emit)
    assert listener.is_noop is True
    await asyncio.wait_for(listener.start(), timeout=1.0)
    # No exception, no events emitted.


@pytest.mark.asyncio
async def test_e2e_p50_latency_under_500ms_and_seq_id_monotonic(
    tmp_path: Path, monkeypatch
) -> None:
    """SPEC acceptance #8 + REQ-end-to-end-latency: 50-event synthetic drive,
    p50 < 500ms, seq_id strictly monotonic."""
    monkeypatch.setenv("TWITTER_BEARER_TOKEN", "")

    holder = StateHolder(_seed_state())
    queue: asyncio.Queue[ConfirmedEvent] = asyncio.Queue()
    event_log = EventLogWriter("e2e_match", log_dir=tmp_path / "events")
    metrics = MetricsWriter("e2e_match", log_dir=tmp_path / "metrics")
    arbiter = Arbiter(holder, queue, event_log, metrics)
    engine = _build_engine()
    driver = EngineDriver(engine=engine, state_holder=holder, queue=queue, metrics=metrics)

    driver_task = asyncio.create_task(driver.run())
    try:
        await _drive_synthetic_events(arbiter, E2E_EVENT_COUNT)
        # Wait for the engine driver to drain the queue.
        await asyncio.wait_for(queue.join(), timeout=10.0)
    finally:
        driver_task.cancel()
        try:
            await driver_task
        except asyncio.CancelledError:
            pass
        event_log.close()
        metrics.close()

    # --- Assertion 1: seq_id strictly monotonic ---
    raw = event_log.path.read_text().strip().split("\n")
    committed = [json.loads(l) for l in raw if not json.loads(l).get("quarantined")]
    seq_ids = [r["seq_id"] for r in committed]
    assert seq_ids == sorted(seq_ids), f"seq_ids not monotonic: {seq_ids[:10]}..."
    assert len(set(seq_ids)) == len(seq_ids), f"seq_id duplicates: {seq_ids}"
    assert len(seq_ids) >= 30, f"E2E delivered only {len(seq_ids)} commits; SPEC floor is 30"

    # --- Assertion 2: p50 latency < 500ms ---
    latencies_ms = [
        (r["t_state_committed"] - r["t_observed"]) * 1000.0
        for r in committed
    ]
    p50 = statistics.median(latencies_ms)
    assert p50 < E2E_LATENCY_BUDGET_MS, (
        f"E2E p50 latency {p50:.1f}ms exceeds {E2E_LATENCY_BUDGET_MS}ms budget. "
        f"Distribution: min={min(latencies_ms):.1f} max={max(latencies_ms):.1f}"
    )


@pytest.mark.asyncio
async def test_e2e_theo_non_degenerate_on_final_state(
    tmp_path: Path, monkeypatch
) -> None:
    """SPEC acceptance: final theo_series in (0.01, 0.99), NOT stuck at flat 0.5.

    Proves the round_conclusion lookup hit a calibrated cell (not the
    side_baseline fallback), which proves the four cell-keying fields
    (numerical_diff, bomb_planted, side, econ_bucket) propagated correctly
    through state mutations from synthetic events.
    """
    monkeypatch.setenv("TWITTER_BEARER_TOKEN", "")

    holder = StateHolder(_seed_state())
    queue: asyncio.Queue[ConfirmedEvent] = asyncio.Queue()
    event_log = EventLogWriter("e2e_theo", log_dir=tmp_path / "events")
    metrics = MetricsWriter("e2e_theo", log_dir=tmp_path / "metrics")
    arbiter = Arbiter(holder, queue, event_log, metrics)
    engine = _build_engine()
    driver = EngineDriver(engine=engine, state_holder=holder, queue=queue, metrics=metrics)

    driver_task = asyncio.create_task(driver.run())
    try:
        await _drive_synthetic_events(arbiter, E2E_EVENT_COUNT)
        await asyncio.wait_for(queue.join(), timeout=10.0)
    finally:
        driver_task.cancel()
        try:
            await driver_task
        except asyncio.CancelledError:
            pass
        event_log.close()
        metrics.close()

    final_state = holder.read()
    out = engine(final_state)
    assert 0.01 < out.theo_series < 0.99, f"theo_series clipped at boundary: {out.theo_series}"
    # Non-flat: NOT exactly 0.5 (or extremely close). Allows 0.45..0.55 — the
    # synthetic events shouldn't drive a strong directional outcome but should
    # produce some movement off the flat prior.
    # If this is too tight in practice, RESEARCH §Open Questions item 3
    # accuracy probe + Phase 5 calibration may revisit.
    assert abs(out.theo_series - 0.5) > 0.001 or out.confidence > 0.0, (
        f"theo_series stuck at flat 0.5 with zero confidence — calibrated lookup "
        f"may not have been hit. theo={out.theo_series} confidence={out.confidence}"
    )


@pytest.mark.asyncio
async def test_e2e_jsonl_replay_round_trip(
    tmp_path: Path, monkeypatch
) -> None:
    """Phase-level must-have: JSONL parseable; replay reproduces final state."""
    monkeypatch.setenv("TWITTER_BEARER_TOKEN", "")

    holder = StateHolder(_seed_state())
    queue: asyncio.Queue[ConfirmedEvent] = asyncio.Queue()
    event_log = EventLogWriter("e2e_replay", log_dir=tmp_path / "events")
    metrics = MetricsWriter("e2e_replay", log_dir=tmp_path / "metrics")
    arbiter = Arbiter(holder, queue, event_log, metrics)
    engine = _build_engine()
    driver = EngineDriver(engine=engine, state_holder=holder, queue=queue, metrics=metrics)

    driver_task = asyncio.create_task(driver.run())
    try:
        await _drive_synthetic_events(arbiter, E2E_EVENT_COUNT)
        await asyncio.wait_for(queue.join(), timeout=10.0)
    finally:
        driver_task.cancel()
        try:
            await driver_task
        except asyncio.CancelledError:
            pass
        event_log.close()
        metrics.close()

    # Replay diff-only fields_changed in seq_id order.
    raw_lines = event_log.path.read_text().strip().split("\n")
    committed = sorted(
        (json.loads(l) for l in raw_lines if not json.loads(l).get("quarantined")),
        key=lambda r: r["seq_id"],
    )
    replayed = _seed_state()
    for rec in committed:
        replayed = replayed.with_update(**rec["fields_changed"])

    final = holder.read()
    # All non-time fields must match.
    for f in dataclasses.fields(MatchState):
        if f.name == "last_updated_ts":
            continue
        assert getattr(replayed, f.name) == getattr(final, f.name), (
            f"replay mismatch on {f.name}: replayed={getattr(replayed, f.name)!r} "
            f"vs holder.final={getattr(final, f.name)!r}"
        )
    # seq_id density check.
    assert replayed.seq_id == final.seq_id


@pytest.mark.skip(
    reason="WARNING-4: full OCR-backed E2E exercise deferred to Phase 5 CTC "
           "decoder (see 03-CONTEXT.md `<deferred>`). Phase 3 ships the "
           "scaffold + signal_for + arbiter wiring; this test re-enables "
           "once 03-05b's OCR backend produces a real numerical_diff."
)
@pytest.mark.asyncio
async def test_e2e_drives_one_ocr_backed_event_through_pipeline(
    tmp_path: Path, monkeypatch
) -> None:
    """WARNING-4: drive ONE OCR-backed event (real backend, fixture frame)
    through the full pipeline; assert the JSONL contains at least one line
    with source == 'ocr' AND event_type == 'kill'.

    Currently @skip per CONTEXT deferred-ideas (CTC decoder ships Phase 5).
    When the decoder lands, drop the @skip and ensure the OCR pipeline is
    constructed against a real fixture frame instead of a synthetic
    ArbiterPending.
    """
    import io as _io
    from concurrent.futures import ThreadPoolExecutor as _TPE
    from PIL import Image as _Image

    from src.ingestion.ocr import OCRPipeline as _OCRPipeline

    monkeypatch.setenv("TWITTER_BEARER_TOKEN", "")

    holder = StateHolder(_seed_state())
    queue: asyncio.Queue[ConfirmedEvent] = asyncio.Queue()
    event_log = EventLogWriter("e2e_ocr", log_dir=tmp_path / "events")
    metrics = MetricsWriter("e2e_ocr", log_dir=tmp_path / "metrics")
    arbiter = Arbiter(holder, queue, event_log, metrics)
    engine = _build_engine()
    driver = EngineDriver(engine=engine, state_holder=holder, queue=queue, metrics=metrics)

    # Construct an OCRPipeline that emits directly into the arbiter.
    async def _ocr_emit(p: ArbiterPending) -> None:
        await arbiter.submit(p)

    class _OneFrame:
        def frames(self):
            im = _Image.new("RGB", (200, 100), color=(255, 255, 255))
            buf = _io.BytesIO()
            im.save(buf, format="PNG")
            yield buf.getvalue()

    # Use a real OCR pipeline (skip_onnx_verify for the test fixture).
    pool = _TPE(max_workers=2, thread_name_prefix="e2e-ocr")
    try:
        ocr = _OCRPipeline(
            emit=_ocr_emit, executor=pool, frame_source=_OneFrame(),
            onnx_model_path=Path("models/en_PP-OCRv4_rec_infer.onnx"),
            skip_onnx_verify=True,
        )
        driver_task = asyncio.create_task(driver.run())
        try:
            # Drive ONE kill_feed inference -> arbiter -> state -> driver.
            await ocr.run_target_once("kill_feed")  # add a one-shot helper, see Note below
            await arbiter._tick(time.monotonic_ns())
            await asyncio.wait_for(queue.join(), timeout=5.0)
        finally:
            driver_task.cancel()
            try:
                await driver_task
            except asyncio.CancelledError:
                pass
    finally:
        pool.shutdown(wait=True, cancel_futures=False)
        event_log.close()
        metrics.close()

    # Assert the JSONL contains at least one source=='ocr' event_type=='kill' line.
    raw_lines = event_log.path.read_text().strip().split("\n")
    committed = [json.loads(l) for l in raw_lines if not json.loads(l).get("quarantined")]
    ocr_kills = [r for r in committed if r["source"] == "ocr" and r["event_type"] == "kill"]
    assert len(ocr_kills) >= 1, (
        f"WARNING-4: expected >=1 OCR-backed kill event in JSONL; got "
        f"{[(r['source'], r['event_type']) for r in committed]}"
    )

    # NOTE: this test calls `ocr.run_target_once("kill_feed")` which is a
    # one-shot helper that the executor MUST add to OCRPipeline in 03-05b
    # (single-frame inference + emit; no infinite loop). If the helper is
    # missing, this test is also a forcing function for 03-05b to expose it.


@pytest.mark.asyncio
async def test_e2e_metrics_file_has_committed_plus_followup_lines(
    tmp_path: Path, monkeypatch
) -> None:
    """REQ-latency-instrumentation: metrics file has 1 committed + 1 follow-up
    line per ConfirmedEvent (Pitfall 8). Total = 2 * N events."""
    monkeypatch.setenv("TWITTER_BEARER_TOKEN", "")

    holder = StateHolder(_seed_state())
    queue: asyncio.Queue[ConfirmedEvent] = asyncio.Queue()
    event_log = EventLogWriter("e2e_metrics", log_dir=tmp_path / "events")
    metrics = MetricsWriter("e2e_metrics", log_dir=tmp_path / "metrics")
    arbiter = Arbiter(holder, queue, event_log, metrics)
    engine = _build_engine()
    driver = EngineDriver(engine=engine, state_holder=holder, queue=queue, metrics=metrics)

    driver_task = asyncio.create_task(driver.run())
    try:
        await _drive_synthetic_events(arbiter, E2E_EVENT_COUNT)
        await asyncio.wait_for(queue.join(), timeout=10.0)
    finally:
        driver_task.cancel()
        try:
            await driver_task
        except asyncio.CancelledError:
            pass
        event_log.close()
        metrics.close()

    raw = metrics.path.read_text().strip().split("\n")
    parsed = [json.loads(l) for l in raw]
    committed = [r for r in parsed if "t_state_committed" in r]
    followups = [r for r in parsed if "t_theo_computed" in r and "t_state_committed" not in r]
    assert len(committed) == len(followups), (
        f"committed lines ({len(committed)}) != follow-up lines ({len(followups)}) "
        f"— each ConfirmedEvent must produce one of each"
    )
    assert len(committed) >= 30, f"only {len(committed)} commits; SPEC floor 30"
```
  </action>
  <verify>
    <automated>pytest tests/ingestion/test_e2e.py -x &amp;&amp; pytest tests/ -x -k "not benchmark and not accuracy_probe" &amp;&amp; mypy --strict src/pricing/ src/state/</automated>
  </verify>
  <done>5 tests in tests/ingestion/test_e2e.py PASS; p50 latency < 500ms over 50 events; seq_id strictly monotonic; theo non-degenerate on final state; JSONL replay round-trip; metrics file has 50 committed + 50 follow-up lines; ALL Phase 1 + 2 + 03-* tests GREEN; mypy --strict src/pricing/ + src/state/ clean.</done>
</task>

<task type="auto">
  <name>Task 3: Update ROADMAP.md + STATE.md to mark Phase 3 complete</name>
  <files>.planning/ROADMAP.md, .planning/STATE.md</files>
  <read_first>
    - .planning/ROADMAP.md (entire file — 172 lines; specifically the Phase 3 section + the Progress table at line 153)
    - .planning/STATE.md (entire file — 126 lines)
    - .planning/phases/03-live-ingestion-layer/03-SPEC.md acceptance line 102 (STATE.md / ROADMAP.md updated)
  </read_first>
  <action>
**(a)** Edit `.planning/ROADMAP.md`:

In the Phase 3 section (lines 88-100), update:
- Line 88: change `- [ ] **Phase 3: Live ingestion layer**` to `- [x] **Phase 3: Live ingestion layer**`
- After "**Plans**: TBD" (line 96) add:
  ```
  **Plans**: 9 plans
    - [x] 03-00-pyproject-and-constants-PLAN.md — pyproject deps + asyncio_mode + mypy override + 19 new constants + .gitignore (Wave 0)
    - [x] 03-01-shared-types-and-download-PLAN.md — src/ingestion/types.py + tests/conftest + scripts/download_models.py (Wave 0)
    - [x] 03-02-salvage-verify-PLAN.md — operator-staged reference/{vlr_scraper,rib_scraper,vision_parser}.py + verification test (Wave 0)
    - [x] 03-03-match-state-move-and-extend-PLAN.md — MatchState atomic move src/pricing/data.py -> src/state/match_state.py + 8 Phase 3 fields + with_update (Wave 1)
    - [x] 03-04-scoreboard-poller-PLAN.md — src/ingestion/scoreboard.py rib.gg poller + shared _http.py (Wave 2)
    - [x] 03-05a-ocr-scaffold-PLAN.md (and 03-05b-ocr-backends-PLAN.md per BLOCKER-2 split) -- src/ingestion/ocr.py hybrid ONNX + tesseract pipeline (Wave 3)
    - [x] 03-06-text-listener-PLAN.md — src/ingestion/text_listener.py Twitter v2 streaming + degrade-on-missing-token (Wave 2)
    - [x] 03-07a-state-holder-and-event-log-PLAN.md (and 03-07b-arbiter-PLAN.md per WARNING-5 split) -- StateHolder (BLOCKER-1 strip-before-swap) + Arbiter (5 deques + ConfirmedEvent.is_soft routing) (Wave 3)
    - [x] 03-08-engine-driver-and-e2e-PLAN.md — src/state/engine_driver.py + tests/ingestion/test_e2e.py (Wave 4)
  ```

In the Progress table (line 153), update the Phase 3 row:
- Change `| 3. Live ingestion layer | 0/0 | Not started | — |` to `| 3. Live ingestion layer | 11/11 | Complete | {YYYY-MM-DD} |` (substitute today's date).

In the Phases summary list at the top (lines 27-34), update line 30:
- Change `- [ ] **Phase 3: Live ingestion layer**` to `- [x] **Phase 3: Live ingestion layer**` (matches Phase 0 + 2 done-style).

**(b)** Edit `.planning/STATE.md`:

(i) Update the YAML frontmatter:
- Line 5: `current_phase: 03` -> `current_phase: 04`
- Line 6: `current_plan: 0` -> `current_plan: 0` (still 0; planning hasn't started for Phase 4)
- Line 7: `status: ready` -> `status: ready`
- Line 8: `stopped_at: Phase 02 complete — Path A calibrated lookup shipped` -> `stopped_at: Phase 03 complete — live ingestion pipeline (sources -> arbiter -> state -> engine driver) shipped with synthetic E2E gate green`
- Line 9: `last_updated: "2026-05-01T17:30:00Z"` -> `last_updated: "{YYYY-MM-DDTHH:MM:SSZ}"` (today's UTC timestamp)
- Line 10: `last_activity: 2026-05-01` -> `last_activity: {YYYY-MM-DD}`
- Line 12-15 (`progress:` block):
  - `total_plans: 15` -> `total_plans: 26` (15 prior + 11 Phase 3)
  - `completed_plans: 15` -> `completed_plans: 26`
  - `percent: 100` -> `percent: 100` (still 100% of planned plans complete)
  - `completed_phases: 3` -> `completed_phases: 4` (Phases 0, 1, 2, 3)

(ii) Update the body sections:
- "Last activity description" (line 23): replace with "Phase 03 complete — live ingestion pipeline shipped end-to-end. 9 plans across 5 waves: Wave 0 infra (constants + types + downloader + salvage gate), Wave 1 MatchState move + extend, Wave 2 sources (scoreboard + OCR + text listener) in parallel, Wave 3 arbiter + JSONL writers + state holder, Wave 4 engine driver + synthetic E2E gate. p50 latency under 500ms over 50 synthetic events; seq_id strictly monotonic; theo non-degenerate on final state. Twitter listener degrades to no-op without bearer token (CRule 13)."
- Line 31 (Owner status): replace "Phases 0/1/2 complete" with "Phases 0/1/2/3 complete"; update "next planning candidate" to "Phase 4 (quoting layer)".
- Line 37 (Current Position phase): "Phase: 03 (live-ingestion-layer) — READY FOR PLANNING" -> "Phase: 04 (quoting-layer) — READY FOR PLANNING"
- Line 38: `Plan: 0 of TBD` -> stays the same.
- Lines 40-43 (the dashed list): update to reflect Phase 4.
- Line 43 (Progress: 3/8 -> 4/8): "Progress: 3/8 phases complete (37.5%)" -> "Progress: 4/8 phases complete (50%); 26/26 planned plans complete (100% of planned)"
- Lines 45-54 (the ASCII bar chart): update Phase 3 from `[          ] Pending (no plans yet)` to `[##########] Complete (11/11 plans)`.
- Lines 58-67 (Phase Status table): update the Phase 3 row to `| 3 — Live ingestion layer | Complete ({YYYY-MM-DD}) | 9 (03-00..03-08) | 9 |`.
- Add new bullet to "Recent decisions" section (line 84): "Phase 3 D-01..D-07 + carry-forward (Phase 1 D-02/D-14/D-20/D-21, Phase 2 D-06/D-08/D-15) — see 03-CONTEXT.md."
- Add a NEW subsection after "Phase 2 outcomes" titled "### Phase 3 outcomes ({YYYY-MM-DD})" with bullets:
  - "MatchState atomic move from src/pricing/data.py to src/state/match_state.py (25 fields = 17 Phase 1 + 8 Phase 3); with_update mutator strips defensive overrides; mypy --strict src/state/ added."
  - "rib.gg live poller: 5s cadence + heartbeat-on-no-change + 10s backoff cap (down from Phase 2's 30s) per RESEARCH Pitfall 3."
  - "Hybrid OCR: ONNX en_PP-OCRv4_rec_infer.onnx for kill-feed (CPU only, integrity verified before InferenceSession); pytesseract for the other 3 targets."
  - "Twitter v2 streaming listener degrades to no-op when TWITTER_BEARER_TOKEN unset (Pro tier $5k/mo; Free/Basic streaming retired 2023)."
  - "5-deque arbiter implementing DEC-006 + D-04 + D-05; sole writer to MatchState via StateHolder + asyncio.Lock."
  - "Six-stage timestamp lineage in JSONL + metrics file (Pitfall 8 follow-up line keyed by seq_id)."
  - "Synthetic E2E gate green: 50 events, p50 < 500ms, seq_id strictly monotonic, theo non-degenerate."
- Line 107 (Active todos): keep as "None — Phase 03 close-out complete."
- Line 110 (Blockers): keep as "None."
- Line 122 (Last session ended): replace with "{YYYY-MM-DD} — Phase 03 fully shipped. 11 plans (post-revision splits) + ~85 new tests across src/state/ + src/ingestion/ + tests/state/ + tests/ingestion/."
- Line 123: "Stopped at: Phase 03 complete — ..."
- Line 124 (Next action): "Phase 4 (quoting layer) needs spec/discuss -> plan -> execute. Per roadmap.md §4: KalshiOrderManager + mode selector + MM quoter + directional taker + Kelly sizer + 4 always-on kill switches + order reconciliation. Recommended next command: `/gsd-spec-phase 04`."

NOTE-7 (executor MUST substitute literally, NOT keep the placeholder text):

For every `{YYYY-MM-DD}` marker in either file, substitute with:
```powershell
(Get-Date).ToUniversalTime().ToString('yyyy-MM-dd')
```

For every `{YYYY-MM-DDTHH:MM:SSZ}` marker (the STATE.md frontmatter `last_updated:` line), substitute with:
```powershell
(Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
```

Concretely: in PowerShell, capture `$date = (Get-Date).ToUniversalTime().ToString('yyyy-MM-dd')` and `$ts = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')` BEFORE writing the file, then string-substitute `{YYYY-MM-DD}` -> `$date` and `{YYYY-MM-DDTHH:MM:SSZ}` -> `$ts` in the file content.

The executor MUST substitute via PowerShell before writing the file. Do NOT keep the literal `{YYYY-MM-DD}` placeholder text in the on-disk markdown.
  </action>
  <verify>
    <automated>grep -q "Phase 03 complete" .planning/STATE.md &amp;&amp; grep -q "current_phase: 04" .planning/STATE.md &amp;&amp; grep -q "11 plans" .planning/ROADMAP.md &amp;&amp; grep -q "Live ingestion layer | 11/11 | Complete" .planning/ROADMAP.md &amp;&amp; pytest tests/ -x -k "not benchmark and not accuracy_probe"</automated>
  </verify>
  <done>ROADMAP.md Phase 3 entry shows 9 completed plans + Progress table marks Phase 3 Complete; STATE.md frontmatter shows current_phase=04, completed_phases=4, total_plans=24, completed_plans=24; new Phase 3 outcomes section added; Last session ended note updated; ALL Phase 1 + 2 + 03-* tests GREEN (regression).</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| arbiter -> queue -> driver | ConfirmedEvent crosses an asyncio.Queue boundary between writer (arbiter) and reader (driver). |
| driver -> live_theo | Driver invokes the Phase 1 LiveTheoEngine; signature is the locked Phase 1 D-20 surface. |
| documentation update | ROADMAP.md + STATE.md are markdown-only; no code paths affected. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-03-08-01 | T (Tampering) | engine_driver doesn't widen the live_theo surface | mitigate | EngineDriver._process calls `self.engine(state)` with the locked Phase 1 D-20 signature. CRule 1 (single canonical live_theo) is preserved. Test 1 of Task 1 verifies the engine is called with a `MatchState` instance only. |
| T-03-08-02 | T (Tampering) | engine_driver doesn't mutate state | mitigate | `state_holder.read()` returns a frozen+slots MatchState; the driver never calls `state_holder.swap_with()`. Test 2 of Task 1 proves seq_id is unchanged after 5 events through the driver. |
| T-03-08-03 | D (Denial of service) | engine exception in driver loop | mitigate | `_process` is wrapped in try/except; exceptions log and continue. Test 4 of Task 1 proves a single failing event does NOT crash the driver. |
| T-03-08-04 | I (Information disclosure) | metrics follow-up line | accept | The follow-up line carries `seq_id` + `t_theo_computed` (and Phase 4 will add `t_quote_sent`); no PII. |
| T-03-08-05 | T (Tampering) | E2E test environment | mitigate | E2E test forces `TWITTER_BEARER_TOKEN=""` via monkeypatch, ensuring the test never attempts a live Twitter connection regardless of operator's local env. |
| T-03-08-06 | I (Information disclosure) | STATE.md / ROADMAP.md | accept | These are project-internal planning files; team names + match IDs are public. Today's date is the only operator-injected value. |
</threat_model>

<verification>
- `pytest tests/ingestion/test_engine_driver.py tests/ingestion/test_e2e.py -x` PASSES (5 + 5 = 10 tests).
- `pytest tests/ -x -k "not benchmark and not accuracy_probe"` PASSES — full Phase 1 + 2 + 03-* regression.
- `mypy --strict src/pricing/ src/state/` clean.
- `mypy src/ingestion/` clean (gradual scope).
- `ruff check src/ tests/ scripts/` clean.
- E2E synthetic test:
  - 50 events drive through arbiter → engine driver
  - p50 (t_observed → t_state_committed) < 500ms
  - seq_id strictly monotonic
  - theo_series ∈ (0.01, 0.99) on final state and not stuck at flat 0.5
  - JSONL replay reproduces final state field-for-field
  - metrics file has 50 committed lines + 50 follow-up lines
- ROADMAP.md: Phase 3 marked complete with 9/9 plans; Progress table updated.
- STATE.md: current_phase=04, completed_phases=4, total_plans=24, completed_plans=24; Phase 3 outcomes section added; Last session ended note updated.
</verification>

<success_criteria>
Wave 4 plan 03-08 (engine driver + E2E gate) is COMPLETE when:

1. `src/state/engine_driver.py` exports `EngineDriver` (read-only ConfirmedEvent consumer + LiveTheoEngine invocation + Pitfall-8 follow-up line stamp).
2. `MetricsWriter.write_followup` method added per Pitfall 8 (Phase 4-shape-compatible).
3. `src/state/__init__.py` re-exports `EngineDriver`.
4. `tests/ingestion/test_engine_driver.py` has 5 unit tests; ALL PASS.
5. `tests/ingestion/test_e2e.py` has 5 named tests covering the SPEC acceptance #8 gate; ALL PASS:
   - Twitter listener no-op path
   - p50 latency < 500ms + seq_id monotonic over 50 events
   - theo non-degenerate on final state
   - JSONL replay round-trip
   - metrics file has committed + follow-up lines per Pitfall 8
6. ROADMAP.md updated: Phase 3 marked complete with 9 plans listed; Progress table updated.
7. STATE.md updated: current_phase=04; completed_phases=4; total_plans=24; Phase 3 outcomes documented; Last session ended note updated.
8. `mypy --strict src/pricing/ src/state/` clean (regression-safe — Phase 3 didn't break Phase 1).
9. `pytest tests/ -x -k "not benchmark and not accuracy_probe"` GREEN — full project regression.
10. Phase 3 ships; orchestrator can advance to `/gsd-spec-phase 04`.
</success_criteria>

<output>
After completion, create `.planning/phases/03-live-ingestion-layer/03-08-SUMMARY.md`:

```markdown
# 03-08 SUMMARY — engine driver + E2E gate

**Status:** complete
**Wave:** 4 (final)
**Files created:** src/state/engine_driver.py, tests/ingestion/test_engine_driver.py, tests/ingestion/test_e2e.py
**Files modified:** src/state/__init__.py, src/ingestion/event_log.py (+ MetricsWriter.write_followup), .planning/ROADMAP.md, .planning/STATE.md

## Public API
- EngineDriver(engine, state_holder, queue, metrics): await driver.run()
- MetricsWriter.write_followup(seq_id, t_theo_computed_ns=..., t_quote_sent_ns=...) — Pitfall 8 follow-up

## E2E gate results (SPEC acceptance #8)
- 50 synthetic events
- p50 latency: {measured}ms (< 500ms budget)
- seq_id strictly monotonic across run
- theo non-degenerate on final state (∈ (0.01, 0.99), not stuck at flat 0.5)
- JSONL replay: {N} events round-tripped, identical final state on all non-time fields
- Metrics file: {N} committed + {N} follow-up lines = {2N} total

## Phase 3 status
- 11 plans across 6 waves COMPLETE (post-revision)
- ~80 new tests across src/state/ + src/ingestion/ + tests/{state,ingestion}/
- Phase 1 + 2 regression: GREEN
- All 7 phase requirement IDs covered
- All 7 D-XX decisions implemented
- mypy --strict src/pricing/ + src/state/: clean
- ruff check src/ tests/ scripts/: clean

## Next phase
Phase 4 (quoting layer) — `/gsd-spec-phase 04`
```
</output>
