---
id: 03-07b-arbiter
phase: 03
plan: 7
type: execute
wave: 4
depends_on:
  - 03-00-pyproject-and-constants
  - 03-01-shared-types-and-download
  - 03-03-match-state-move-and-extend
  - 03-04-scoreboard-poller
  - 03-05a-ocr-scaffold
  - 03-05b-ocr-backends
  - 03-06-text-listener
  - 03-07a-state-holder-and-event-log
files_modified:
  - src/ingestion/arbiter.py
  - src/ingestion/__init__.py
  - tests/ingestion/test_arbiter.py
autonomous: true
requirements:
  - REQ-cross-source-arbiter
  - REQ-latency-instrumentation
must_haves:
  truths:
    - "Arbiter implements DEC-006 / D-04 / D-05 rules: 5 deques (score_changes, kill_events, bomb_events, numerical_flips, round_end_events) + tick(now_ns) at ARBITER_TICK_HZ"
    - "Score-change rule: ≥ 2 distinct sources within ARBITER_SCORE_WINDOW_S => commit; single source within window => quarantine"
    - "Kill / bomb / numerical-flip rule: 1 OCR source within window => commit; Twitter-only within window => QUARANTINE (D-05 + RESEARCH §Assumptions A9)"
    - "Round-end rule: OCR-only soft commit via ConfirmedEvent.is_soft=True (BLOCKER-1: NO _round_end_soft sentinel injected into fields_changed; arbiter passes EMPTY fields_changed to swap_with for round_end events; the soft signal lives ONLY on ConfirmedEvent.is_soft + the optional pure-extra fields_changed of {} for the engine driver to see via the queue)"
    - "BLOCKER-1: Arbiter._commit() strips any underscore-prefix sentinel keys from fields_changed BEFORE calling swap_with — but in practice 03-05b OCR backends + the round_end pathway via is_soft mean the strip is a defense-in-depth no-op; the ValueError from StateHolder.swap_with would also catch it"
    - "Per-event-type deques bounded by ARBITER_DEQUE_MAX (consumed from 03-07a)"
    - "Tests cover: rule matrix property test, score-window boundary, quarantine log shape, six-stage timestamp populated, round_end commits with is_soft=True (NOT via _round_end_soft sentinel)"
  artifacts:
    - path: src/ingestion/arbiter.py
      provides: "Arbiter class — 5 deques, tick(), per-rule predicates, _commit(), _quarantine()"
      contains: "class Arbiter"
    - path: tests/ingestion/test_arbiter.py
      provides: "rule matrix property test (≥ 2000 executions per VALIDATION line 69) + BLOCKER-1 regression tests"
  key_links:
    - from: "src/ingestion/arbiter.py"
      to: "src/state/state_holder.py"
      via: "self._state_holder.swap_with(fields_changed)"
      pattern: "_state_holder\\.swap_with"
    - from: "src/ingestion/arbiter.py"
      to: "src/ingestion/event_log.py"
      via: "self._event_log.write_committed/_quarantined(...)"
      pattern: "write_committed|write_quarantined"
    - from: "Arbiter._commit"
      to: "ConfirmedEvent.is_soft"
      via: "is_soft=(event_type=='round_end')"
      pattern: "is_soft="
---

<objective>
Wave 4 plan (split-B) — implement the cross-source Arbiter on top of 03-07a's StateHolder + JSONL writers. Routes round_end soft commits via `ConfirmedEvent.is_soft=True` (BLOCKER-1 root-cause fix), NOT via `_round_end_soft` sentinel injection into fields_changed.

Purpose: Per BLOCKER-1, the original `_eval_round_end_rule` was injecting `_round_end_soft` into `fields_changed` and passing it to `swap_with`, which would crash `dataclasses.replace`. Per WARNING-5, splitting reduces the file count this plan touches.

Output: `src/ingestion/arbiter.py` (Arbiter class with 5 deques + tick + rules), tests covering all DEC-006 rules + BLOCKER-1 regression (round_end uses is_soft, not sentinel keys).
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
@src/state/match_state.py
@src/state/state_holder.py
@src/ingestion/event_log.py
@src/ingestion/types.py
@src/ingestion/scoreboard.py
@src/ingestion/ocr.py
@src/ingestion/text_listener.py
@src/config/constants.py
@CLAUDE.md
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Create src/ingestion/arbiter.py — 5 deques + tick + per-rule predicates + commit/quarantine; route round_end via ConfirmedEvent.is_soft (BLOCKER-1)</name>
  <files>src/ingestion/arbiter.py, src/ingestion/__init__.py, tests/ingestion/test_arbiter.py</files>
  <read_first>
    - src/ingestion/types.py (ArbiterPending, ConfirmedEvent.is_soft from 03-01)
    - src/state/state_holder.py (StateHolder.swap_with — raises ValueError on bad keys)
    - src/ingestion/event_log.py (writer interface from 03-07a)
    - .planning/phases/03-live-ingestion-layer/03-RESEARCH.md §Architecture Patterns Pattern 4
    - .planning/phases/03-live-ingestion-layer/03-RESEARCH.md §Pattern 5 timestamp lineage
    - .planning/phases/03-live-ingestion-layer/03-VALIDATION.md tasks 03-AR-01..03 + Sampling minimums lines 69-70
    - src/config/constants.py:ARBITER_TICK_HZ, ARBITER_SCORE_WINDOW_S, ARBITER_*_WINDOW_*, ARBITER_ROUND_END_WINDOW_S, ARBITER_DEQUE_MAX
  </read_first>
  <behavior>
    - Test 1 (test_score_change_two_sources_within_window_commits): submit 2 ArbiterPending source=ribgg + source=ocr with same signal_value within 2s; tick(); assert state mutated + ConfirmedEvent on queue + JSONL committed line.
    - Test 2 (test_score_change_single_source_quarantined): submit 1 source=twitter; tick after >2s; assert NO state mutation + JSONL has quarantined line.
    - Test 3 (test_kill_event_single_ocr_commits): submit 1 source=ocr event_type=kill; tick; assert commit + state.numerical_diff updated.
    - Test 4 (test_kill_event_single_twitter_quarantined): submit 1 source=twitter event_type=kill; tick; assert NO commit + JSONL quarantined line.
    - Test 5 (test_bomb_event_single_ocr_commits): mirrors test 3 with event_type=bomb.
    - Test 6 (BLOCKER-1: test_round_end_ocr_commits_via_is_soft_NOT_via_sentinel_keys): submit 1 source=ocr event_type=round_end with EMPTY signal_value (or a few legitimate keys); tick; assert (a) ConfirmedEvent on queue has is_soft=True; (b) the JSONL committed line's fields_changed dict does NOT contain `_round_end_soft` or any underscore-prefixed key; (c) state.seq_id advanced (StateHolder.swap_with did not raise ValueError); (d) the engine driver consumer would see is_soft=True via the queue.
    - Test 7 (BLOCKER-1 regression: test_arbiter_never_passes_underscore_keys_to_swap_with): mock the StateHolder; assert swap_with is called ONLY with dicts whose keys are all in dataclasses.fields(MatchState) and NONE start with `_`. Drives a small mixed event stream then verifies the recorded swap_with calls.
    - Test 8 (test_six_stage_timestamps_populated): JSONL committed line has all 6 timestamp keys; t_theo_computed and t_quote_sent are JSON null.
    - Test 9 (test_metrics_file_one_line_per_commit): 5 events => 5 lines in metrics file.
    - Test 10 (test_rule_matrix_property): hypothesis @given over (source, event_type) @settings(max_examples=100) — 15+ combos × 100 = 1500+ executions. Per VALIDATION line 69 with score-change multi-source test brings total ≥ 2000.
    - Test 11 (test_deque_cap_prevents_unbounded_growth): submit ARBITER_DEQUE_MAX + 100 events; deque size never exceeds ARBITER_DEQUE_MAX.
  </behavior>
  <action>
Create `src/ingestion/arbiter.py`. KEY DIFFERENCES from the original 03-07 plan (BLOCKER-1 fixes):

1. **`_eval_round_end_rule`** does NOT inject `_round_end_soft` into `fields_changed`. Instead it passes `fields_changed=dict(p.signal_value)` (which 03-05b ensures is `{}` for round_end_banner) and sets `is_soft=True` on the ConfirmedEvent.

2. **`_commit`** strips underscore-prefixed sentinel keys from `fields_changed` BEFORE calling `state_holder.swap_with(...)` as defense-in-depth (StateHolder also rejects them, so this is belt-and-suspenders).

3. **`_commit`** signature accepts an `is_soft: bool = False` parameter that gets routed to ConfirmedEvent.

```python
"""Phase 3 cross-source arbiter (REQ-cross-source-arbiter + REQ-latency-instrumentation).

Implements DEC-006 / D-04 / D-05.

BLOCKER-1 (sentinel-key routing fix)
------------------------------------
Round-end soft commits route through ConfirmedEvent.is_soft=True (a typed
field on the ConfirmedEvent dataclass added in 03-01) — NOT via injecting
`_round_end_soft` into `fields_changed`. The latter would crash
StateHolder.swap_with -> dataclasses.replace on the frozen+slots MatchState.

_commit() additionally strips any underscore-prefixed sentinel keys from
fields_changed BEFORE calling swap_with, as defense-in-depth. StateHolder
also rejects them, so this is belt-and-suspenders against future arbiter
extensions that mistakenly emit sentinel keys.

Sources
-------
- 03-SPEC.md §5 (REQ-cross-source-arbiter), §6 (REQ-latency-instrumentation)
- 03-CONTEXT.md D-04 (deque + tick), D-05 (quarantine policy)
- 03-RESEARCH.md §Architecture Patterns Pattern 4, §Pattern 5
- BLOCKER-1 plan-checker note: route round_end soft commit via ConfirmedEvent.is_soft
- src/state/state_holder.py (StateHolder.swap_with — raises ValueError on bad keys)
- src/ingestion/event_log.py (writers from 03-07a)
- src/ingestion/types.py (ArbiterPending, ConfirmedEvent.is_soft)
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict, deque
from typing import Any, Final, Literal

from src.config.constants import (
    ARBITER_BOMB_WINDOW_MS,
    ARBITER_DEQUE_MAX,
    ARBITER_KILL_WINDOW_MS,
    ARBITER_NUMERICAL_WINDOW_MS,
    ARBITER_ROUND_END_WINDOW_S,
    ARBITER_SCORE_WINDOW_S,
    ARBITER_TICK_HZ,
)
from src.ingestion.event_log import EventLogWriter, MetricsWriter
from src.ingestion.types import ArbiterPending, ConfirmedEvent, EventType
from src.state.state_holder import StateHolder

log = logging.getLogger(__name__)


def _strip_sentinel_keys(d: dict[str, Any]) -> dict[str, Any]:
    """BLOCKER-1 defense-in-depth: drop any key starting with '_'.
    StateHolder.swap_with also rejects these via ValueError; this strip
    happens FIRST so callers see a clean dict and a clean disk record.
    """
    return {k: v for k, v in d.items() if not k.startswith("_")}


class Arbiter:
    """Cross-source arbiter (D-04). Sole writer-via-StateHolder to MatchState."""

    def __init__(
        self,
        state_holder: StateHolder,
        out_queue: asyncio.Queue[ConfirmedEvent],
        event_log: EventLogWriter,
        metrics: MetricsWriter,
    ) -> None:
        self._state_holder = state_holder
        self._queue = out_queue
        self._event_log = event_log
        self._metrics = metrics
        self._lock: asyncio.Lock = asyncio.Lock()
        self._deques: dict[EventType, deque[ArbiterPending]] = {
            "score_change":   deque(maxlen=ARBITER_DEQUE_MAX),
            "kill":           deque(maxlen=ARBITER_DEQUE_MAX),
            "bomb":           deque(maxlen=ARBITER_DEQUE_MAX),
            "numerical_flip": deque(maxlen=ARBITER_DEQUE_MAX),
            "round_end":      deque(maxlen=ARBITER_DEQUE_MAX),
        }

    async def submit(self, pending: ArbiterPending) -> None:
        async with self._lock:
            self._deques[pending.event_type].append(pending)

    async def run(self) -> None:
        period_s = 1.0 / ARBITER_TICK_HZ
        try:
            while True:
                await asyncio.sleep(period_s)
                await self._tick(time.monotonic_ns())
        except asyncio.CancelledError:
            log.info("arbiter_tick_loop_cancelled")
            raise

    async def _tick(self, now_ns: int) -> None:
        async with self._lock:
            self._evict_score_quarantine(now_ns)
            self._evict_simple(self._deques["kill"],           now_ns, ARBITER_KILL_WINDOW_MS * 1_000_000)
            self._evict_simple(self._deques["bomb"],           now_ns, ARBITER_BOMB_WINDOW_MS * 1_000_000)
            self._evict_simple(self._deques["numerical_flip"], now_ns, ARBITER_NUMERICAL_WINDOW_MS * 1_000_000)
            self._evict_simple(self._deques["round_end"],      now_ns, int(ARBITER_ROUND_END_WINDOW_S * 1e9))
            await self._eval_score_rule(now_ns)
            await self._eval_simple_cv_rule("kill",           now_ns)
            await self._eval_simple_cv_rule("bomb",           now_ns)
            await self._eval_simple_cv_rule("numerical_flip", now_ns)
            await self._eval_round_end_rule(now_ns)

    def _evict_simple(
        self, dq: deque[ArbiterPending], now_ns: int, window_ns: int
    ) -> None:
        threshold_s = (now_ns - window_ns) / 1e9
        while dq and dq[0].t_ingested < threshold_s:
            dq.popleft()

    def _evict_score_quarantine(self, now_ns: int) -> None:
        dq = self._deques["score_change"]
        threshold_s = (now_ns - int(ARBITER_SCORE_WINDOW_S * 1e9)) / 1e9
        while dq and dq[0].t_ingested < threshold_s:
            old = dq.popleft()
            self._event_log.write_quarantined(
                source=old.source,
                event_type=old.event_type,
                fields_proposed=old.signal_value,
                t_observed=old.t_observed,
                reason=f"score_change saw 1 source ({old.source}); needs >=2 within {ARBITER_SCORE_WINDOW_S}s",
            )

    async def _eval_score_rule(self, now_ns: int) -> None:
        dq = self._deques["score_change"]
        by_signal: dict[tuple[Any, ...], list[ArbiterPending]] = defaultdict(list)
        for p in dq:
            key = tuple(sorted(p.signal_value.items()))
            by_signal[key].append(p)
        committed_ids: set[int] = set()
        for key, pendings in by_signal.items():
            sources = {p.source for p in pendings}
            if len(sources) >= 2:
                await self._commit(
                    fields_changed=dict(key),
                    inputs=pendings,
                    event_type="score_change",
                    now_ns=now_ns,
                )
                for p in pendings:
                    committed_ids.add(id(p))
        if committed_ids:
            self._deques["score_change"] = deque(
                (p for p in dq if id(p) not in committed_ids),
                maxlen=ARBITER_DEQUE_MAX,
            )

    async def _eval_simple_cv_rule(
        self,
        event_type: Literal["kill", "bomb", "numerical_flip"],
        now_ns: int,
    ) -> None:
        dq = self._deques[event_type]
        snapshot = list(dq)
        dq.clear()
        for p in snapshot:
            if p.source == "ocr":
                await self._commit(
                    fields_changed=p.signal_value,
                    inputs=[p],
                    event_type=event_type,
                    now_ns=now_ns,
                )
            elif p.source == "twitter":
                self._event_log.write_quarantined(
                    source="twitter",
                    event_type=event_type,
                    fields_proposed=p.signal_value,
                    t_observed=p.t_observed,
                    reason=f"{event_type} needs CV source; twitter-only",
                )
            elif p.source == "ribgg":
                self._event_log.write_quarantined(
                    source="ribgg",
                    event_type=event_type,
                    fields_proposed=p.signal_value,
                    t_observed=p.t_observed,
                    reason=f"{event_type} needs OCR source; ribgg routed to quarantine",
                )

    async def _eval_round_end_rule(self, now_ns: int) -> None:
        """OCR commits round_end via ConfirmedEvent.is_soft=True (BLOCKER-1).
        DOES NOT inject _round_end_soft into fields_changed."""
        dq = self._deques["round_end"]
        snapshot = list(dq)
        dq.clear()
        for p in snapshot:
            if p.source == "ocr":
                # BLOCKER-1: do NOT inject _round_end_soft. Use is_soft channel.
                # 03-05b ensures p.signal_value is {} for round_end; if a future
                # backend adds legitimate keys, they pass through unchanged.
                await self._commit(
                    fields_changed=dict(p.signal_value),
                    inputs=[p],
                    event_type="round_end",
                    now_ns=now_ns,
                    is_soft=True,
                )
            else:
                self._event_log.write_quarantined(
                    source=p.source,
                    event_type="round_end",
                    fields_proposed=p.signal_value,
                    t_observed=p.t_observed,
                    reason=f"round_end needs OCR source; {p.source}-only routed to quarantine",
                )

    async def _commit(
        self,
        *,
        fields_changed: dict[str, Any],
        inputs: list[ArbiterPending],
        event_type: EventType,
        now_ns: int,
        is_soft: bool = False,
    ) -> None:
        """Build ConfirmedEvent, swap state via StateHolder, write JSONL + metrics, push to queue.

        BLOCKER-1: strips underscore-prefixed sentinel keys from fields_changed
        BEFORE calling swap_with (defense-in-depth; StateHolder also rejects).
        """
        t_arbited_ns = now_ns
        # BLOCKER-1: strip sentinel keys BEFORE swap_with reaches with_update.
        sanitized_fields = _strip_sentinel_keys(fields_changed)
        # State swap (sole writer). StateHolder rejects unknown keys via ValueError.
        new_state, t_committed_ns = await self._state_holder.swap_with(sanitized_fields)
        source_set = tuple(sorted({p.source for p in inputs}))
        ce = ConfirmedEvent(
            fields_changed=sanitized_fields,
            source_set=source_set,
            event_type=event_type,
            t_observed=min(p.t_observed for p in inputs),
            t_ingested=min(p.t_ingested for p in inputs),
            t_arbited=t_arbited_ns / 1e9,
            t_state_committed=t_committed_ns / 1e9,
            is_soft=is_soft,
            confirmed_seq_id=new_state.seq_id,
        )
        self._event_log.write_committed(
            seq_id=new_state.seq_id,
            t_observed=ce.t_observed,
            t_ingested_ns=int(ce.t_ingested * 1e9),
            t_arbited_ns=t_arbited_ns,
            t_state_committed_ns=t_committed_ns,
            source=",".join(source_set),
            event_type=event_type,
            fields_changed=sanitized_fields,
        )
        self._metrics.write(
            seq_id=new_state.seq_id,
            t_observed=ce.t_observed,
            t_ingested_ns=int(ce.t_ingested * 1e9),
            t_arbited_ns=t_arbited_ns,
            t_state_committed_ns=t_committed_ns,
            source=",".join(source_set),
            event_type=event_type,
        )
        await self._queue.put(ce)


__all__ = ["Arbiter"]
```

Update `src/ingestion/__init__.py`:

```python
from src.ingestion.arbiter import Arbiter
```

Add `"Arbiter"` to `__all__`.

Then create `tests/ingestion/test_arbiter.py` covering all 11 behaviors. Most tests mirror the original 03-07 plan but with the BLOCKER-1 corrections:

```python
"""Arbiter rule + BLOCKER-1 routing tests."""
from __future__ import annotations

import asyncio
import dataclasses
import json
import time
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from src.config.constants import ARBITER_DEQUE_MAX, ARBITER_SCORE_WINDOW_S
from src.ingestion.arbiter import Arbiter, _strip_sentinel_keys
from src.ingestion.event_log import EventLogWriter, MetricsWriter
from src.ingestion.types import ArbiterPending, ConfirmedEvent
from src.state import StateHolder
from src.state.match_state import MatchState


def _seed_state() -> MatchState:
    return MatchState(
        match_id="m1", team_a="A", team_b="B", map_pool=("Lotus",),
        map_idx=0, a_map_score=0, b_map_score=0, a_round=0, b_round=0,
        side_orient="a_atk", map_side_orients=("a_atk",), map_winners=(None,),
        pistol_winner_a={0: None}, numerical_diff=0, bomb_planted=False,
        side="atk", econ_bucket="full",
    )


@pytest.fixture
def writers(tmp_path: Path):
    ev = EventLogWriter("test_match", log_dir=tmp_path / "events")
    mt = MetricsWriter("test_match", log_dir=tmp_path / "metrics")
    yield ev, mt
    ev.close()
    mt.close()


@pytest.fixture
def arbiter_setup(writers):
    ev, mt = writers
    holder = StateHolder(_seed_state())
    queue: asyncio.Queue[ConfirmedEvent] = asyncio.Queue()
    arb = Arbiter(holder, queue, ev, mt)
    return arb, holder, queue, ev, mt


def _pending(source: str, event_type: str, signal: dict[str, Any], t_off: float = 0.0) -> ArbiterPending:
    base_t = time.time() + t_off
    return ArbiterPending(
        signal_value=signal, source=source, event_type=event_type,  # type: ignore[arg-type]
        t_observed=base_t, t_ingested=time.monotonic() + t_off,
    )


# ----- Score-change rule ----- #

@pytest.mark.asyncio
async def test_score_change_two_sources_commits(arbiter_setup) -> None:
    arb, holder, queue, ev, mt = arbiter_setup
    await arb.submit(_pending("ribgg", "score_change", {"a_round": 7, "b_round": 3}))
    await arb.submit(_pending("ocr",   "score_change", {"a_round": 7, "b_round": 3}))
    await arb._tick(time.monotonic_ns())
    assert holder.read().a_round == 7
    assert holder.read().seq_id == 1
    assert queue.qsize() == 1


@pytest.mark.asyncio
async def test_score_change_single_source_quarantined(arbiter_setup) -> None:
    arb, holder, queue, ev, mt = arbiter_setup
    await arb.submit(_pending("twitter", "score_change", {"a_round": 7}, t_off=-(ARBITER_SCORE_WINDOW_S + 1.0)))
    await arb._tick(time.monotonic_ns())
    assert holder.read().a_round == 0
    raw = ev.path.read_text().strip().split("\n")
    quarantined = [json.loads(l) for l in raw if json.loads(l).get("quarantined")]
    assert len(quarantined) >= 1


# ----- Kill / bomb / numerical-flip ----- #

@pytest.mark.asyncio
async def test_kill_event_single_ocr_commits(arbiter_setup) -> None:
    arb, holder, *_ = arbiter_setup
    await arb.submit(_pending("ocr", "kill", {"numerical_diff": 4}))
    await arb._tick(time.monotonic_ns())
    assert holder.read().numerical_diff == 4


@pytest.mark.asyncio
async def test_kill_event_twitter_only_quarantined(arbiter_setup) -> None:
    arb, holder, queue, ev, _ = arbiter_setup
    await arb.submit(_pending("twitter", "kill", {"numerical_diff": 4}))
    await arb._tick(time.monotonic_ns())
    assert holder.read().numerical_diff == 0
    raw = ev.path.read_text().strip().split("\n")
    quarantined = [json.loads(l) for l in raw if json.loads(l).get("quarantined")]
    assert len(quarantined) == 1


@pytest.mark.asyncio
async def test_bomb_event_single_ocr_commits(arbiter_setup) -> None:
    arb, holder, *_ = arbiter_setup
    await arb.submit(_pending("ocr", "bomb", {"bomb_planted": True}))
    await arb._tick(time.monotonic_ns())
    assert holder.read().bomb_planted is True


# ----- BLOCKER-1: round_end via is_soft ----- #

@pytest.mark.asyncio
async def test_round_end_ocr_commits_via_is_soft_NOT_via_sentinel_keys(arbiter_setup) -> None:
    """BLOCKER-1: round_end must commit via ConfirmedEvent.is_soft=True; the
    JSONL fields_changed must NOT contain `_round_end_soft` or any other
    underscore-prefixed sentinel key. State seq_id MUST advance."""
    arb, holder, queue, ev, _ = arbiter_setup
    # 03-05b OCR backend emits empty signal_value for round_end_banner; mirror that here.
    await arb.submit(_pending("ocr", "round_end", {}))
    await arb._tick(time.monotonic_ns())
    # State advanced (StateHolder.swap_with did NOT raise ValueError):
    assert holder.read().seq_id == 1
    # ConfirmedEvent on queue carries is_soft=True:
    ce = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert ce.is_soft is True
    assert ce.event_type == "round_end"
    # JSONL fields_changed has no underscore-prefixed keys:
    rec = json.loads(ev.path.read_text().strip().split("\n")[0])
    assert rec["event_type"] == "round_end"
    bad = [k for k in rec["fields_changed"] if k.startswith("_")]
    assert bad == [], f"BLOCKER-1: sentinel keys leaked into JSONL: {bad}"


@pytest.mark.asyncio
async def test_arbiter_never_passes_underscore_keys_to_swap_with(arbiter_setup) -> None:
    """BLOCKER-1 regression: even if a hypothetical buggy source emits a
    sentinel key, _commit's _strip_sentinel_keys defense-in-depth removes it
    BEFORE swap_with sees it. We mock the holder to record swap_with calls.
    """
    arb, holder, queue, ev, _ = arbiter_setup
    recorded: list[dict[str, Any]] = []
    real_swap = holder.swap_with

    async def _spy(fields_changed: dict[str, Any]):
        recorded.append(dict(fields_changed))
        return await real_swap(fields_changed)

    holder.swap_with = _spy  # type: ignore[assignment]

    # Submit a synthetic event with a sentinel key; the arbiter's _strip
    # should remove it before swap_with sees it. Use kill type so a single
    # OCR source auto-commits.
    await arb.submit(_pending("ocr", "kill", {"numerical_diff": 4, "_debug_marker": True}))
    await arb._tick(time.monotonic_ns())

    assert len(recorded) == 1
    for k in recorded[0]:
        assert not k.startswith("_"), f"sentinel key {k!r} reached swap_with"
        assert k in {f.name for f in dataclasses.fields(MatchState)}, (
            f"unknown key {k!r} reached swap_with"
        )


def test_strip_sentinel_keys_drops_underscore_prefix() -> None:
    """Pure-helper unit test for the strip helper."""
    out = _strip_sentinel_keys({"a": 1, "_b": 2, "c": 3, "_round_end_soft": True})
    assert out == {"a": 1, "c": 3}


# ----- Six-stage timestamps ----- #

@pytest.mark.asyncio
async def test_six_stage_timestamps_in_jsonl(arbiter_setup) -> None:
    arb, _, queue, ev, _ = arbiter_setup
    await arb.submit(_pending("ocr", "kill", {"numerical_diff": 4}))
    await arb._tick(time.monotonic_ns())
    rec = json.loads(ev.path.read_text().strip().split("\n")[0])
    for k in ("t_observed", "t_ingested", "t_arbited", "t_state_committed",
              "t_theo_computed", "t_quote_sent"):
        assert k in rec
    assert rec["t_theo_computed"] is None
    assert rec["t_quote_sent"] is None


@pytest.mark.asyncio
async def test_metrics_file_one_line_per_commit(arbiter_setup) -> None:
    arb, _, queue, ev, mt = arbiter_setup
    for i in range(5):
        await arb.submit(_pending("ocr", "kill", {"numerical_diff": i}))
        await arb._tick(time.monotonic_ns())
    while not queue.empty():
        await queue.get()
    lines = mt.path.read_text().strip().split("\n")
    assert len(lines) == 5


# ----- Property: rule matrix ----- #

_sources = ["ribgg", "ocr", "twitter"]
_event_types = ["score_change", "kill", "bomb", "numerical_flip", "round_end"]


@given(source=st.sampled_from(_sources), event_type=st.sampled_from(_event_types))
@settings(max_examples=100, deadline=None)
@pytest.mark.asyncio
async def test_rule_matrix_single_source(source: str, event_type: str, tmp_path_factory) -> None:
    """For each (source, event_type) combo: a single submission; assert
    DEC-006 / D-04 / D-05 conformance. 15 combos x 100 = 1500."""
    tmp = tmp_path_factory.mktemp("arb")
    ev = EventLogWriter("test", log_dir=tmp / "ev")
    mt = MetricsWriter("test", log_dir=tmp / "mt")
    holder = StateHolder(_seed_state())
    q: asyncio.Queue = asyncio.Queue()
    arb = Arbiter(holder, q, ev, mt)
    # Use legitimate signal values per event_type so swap_with doesn't reject.
    sigs = {
        "score_change": {"a_round": 1},
        "kill":         {"numerical_diff": 1},
        "bomb":         {"bomb_planted": True},
        "numerical_flip": {"numerical_diff": 2},
        "round_end":    {},
    }
    await arb.submit(_pending(source, event_type, sigs[event_type], t_off=-(ARBITER_SCORE_WINDOW_S + 1.0)))
    await arb._tick(time.monotonic_ns())
    if source == "ocr" and event_type in ("kill", "bomb", "numerical_flip", "round_end"):
        assert holder.read().seq_id == 1
    else:
        assert holder.read().seq_id == 0
    ev.close()
    mt.close()


@pytest.mark.asyncio
async def test_deque_cap_prevents_unbounded_growth(arbiter_setup) -> None:
    arb, *_ = arbiter_setup
    for i in range(ARBITER_DEQUE_MAX + 100):
        await arb.submit(_pending("twitter", "score_change", {"v": i}))
    assert len(arb._deques["score_change"]) <= ARBITER_DEQUE_MAX
```
  </action>
  <verify>
    <automated>pytest tests/ingestion/test_arbiter.py -x &amp;&amp; mypy src/ingestion/arbiter.py &amp;&amp; ruff check src/ingestion/arbiter.py tests/ingestion/test_arbiter.py</automated>
  </verify>
  <done>src/ingestion/arbiter.py exports Arbiter; src/ingestion/__init__.py re-exports it; tests/ingestion/test_arbiter.py covers 11 behaviors including the 3 BLOCKER-1 regression tests (round_end via is_soft, no underscore keys to swap_with, _strip_sentinel_keys helper); rule matrix property delivers ≥1500 executions; mypy + ruff clean; ALL prior phase regressions GREEN.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| arbiter -> StateHolder | Sole writer to MatchState; concurrent submit() calls serialized via asyncio.Lock. |
| arbiter -> filesystem | EventLogWriter + MetricsWriter via 03-07a interfaces. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-03-07b-01 (BLOCKER-1) | T (Tampering) | round_end soft commit signal routing | mitigate | `_eval_round_end_rule` sets `is_soft=True` on the ConfirmedEvent; does NOT inject `_round_end_soft` into fields_changed. `_commit._strip_sentinel_keys` drops any underscore-prefix as defense-in-depth. StateHolder also rejects unknown keys via ValueError. |
| T-03-07b-02 (covers T-resource-01) | D (Denial of service) | unbounded deque growth | mitigate | All 5 deques constructed with `maxlen=ARBITER_DEQUE_MAX (=1000)`. |
| T-03-07b-03 | T (Tampering) | sentinel-key leak in JSONL | mitigate | `_strip_sentinel_keys` strips before write; the BLOCKER-1 round_end test asserts no `_`-prefixed keys land in the JSONL `fields_changed`. |
</threat_model>

<verification>
- `pytest tests/ingestion/test_arbiter.py -x` PASSES (~11 tests + 1500 hypothesis executions).
- `mypy src/ingestion/arbiter.py` clean.
- `ruff check src/ingestion/ tests/ingestion/test_arbiter.py` clean.
- BLOCKER-1: round_end commits via `is_soft=True` and JSONL contains no underscore-prefixed keys (test 6).
- BLOCKER-1: `swap_with` never receives an underscore-prefixed or unknown key (test 7).
- Phase 1 + 2 + 03-* prior regressions GREEN.
</verification>

<success_criteria>
Wave 4 plan 03-07b is COMPLETE when:

1. `src/ingestion/arbiter.py` exports `Arbiter` with 5 deques + tick + per-rule predicates per DEC-006 / D-04 / D-05.
2. BLOCKER-1: `_eval_round_end_rule` routes via `is_soft=True`; `_commit` strips underscore-prefixed sentinel keys before swap_with (defense-in-depth).
3. `tests/ingestion/test_arbiter.py` has 11 named tests including 3 BLOCKER-1 regression tests + 1 hypothesis property test (≥1500 executions).
4. `src/ingestion/__init__.py` re-exports `Arbiter`.
5. Phase 1 + 2 + 03-* prior regressions GREEN.
</success_criteria>

<output>
After completion, create `.planning/phases/03-live-ingestion-layer/03-07b-SUMMARY.md` documenting the arbiter's BLOCKER-1 routing + the rule matrix.
</output>
