---
id: 03-07a-state-holder-and-event-log
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
files_modified:
  - src/ingestion/event_log.py
  - src/state/state_holder.py
  - src/state/__init__.py
  - src/ingestion/__init__.py
  - src/config/constants.py
  - tests/ingestion/test_event_log.py
autonomous: true
requirements:
  - REQ-cross-source-arbiter
  - REQ-latency-instrumentation
  - REQ-match-state-engine
must_haves:
  truths:
    - "StateHolder.swap_with(fields_changed) ENFORCES the BLOCKER-1 strip-before-replace discipline: rejects any key starting with `_` (sentinel) AND any key not in dataclasses.fields(MatchState) (raises ValueError); ONLY then calls self._state.with_update(**fields_changed)"
    - "Sentinel-key rejection happens BEFORE swap_with reaches with_update — never after — so dataclasses.replace on the frozen+slots MatchState NEVER sees an unknown key (BLOCKER-1 root-cause fix)"
    - "Quarantined entries written to SAME JSONL with seq_id=None, quarantined=true, fields_proposed populated; seq_id NOT bumped (D-05)"
    - "Every committed event in JSONL has all 6 timestamp fields present (Phase 3 fills t_observed/t_ingested/t_arbited/t_state_committed; t_theo_computed and t_quote_sent are JSON null per Pitfall 8)"
    - "Metrics file shape parseable line-by-line; one MetricsLogLine per ConfirmedEvent (REQ-latency-instrumentation)"
    - "match_id sanitized before file path construction: only [a-zA-Z0-9_-] allowed; reject path traversal (T-files-01)"
    - "JSONL writer uses pathlib.Path.open(\"a\", buffering=1<<16, encoding=\"utf-8\") with periodic flush every _FLUSH_EVERY_N events (RESEARCH §Anti-Patterns line 554)"
    - "ARBITER_DEQUE_MAX constant exists in src/config/constants.py (CRule 12) — consumed by arbiter in 03-07b"
    - "Regression test test_swap_with_rejects_unknown_keys asserts swap_with NEVER receives a key starting with `_` or any key not in MatchState's annotated field set (uses dataclasses.fields(MatchState) for the allowlist)"
  artifacts:
    - path: src/state/state_holder.py
      provides: "StateHolder class — wraps a MatchState reference under asyncio.Lock; arbiter is sole writer; sanitizes fields_changed before with_update"
      contains: "class StateHolder"
    - path: src/ingestion/event_log.py
      provides: "EventLogWriter + MetricsWriter — JSONL writers per RESEARCH §Code Examples lines 814-889"
      contains: "class EventLogWriter"
    - path: src/config/constants.py
      provides: "+1 constant: ARBITER_DEQUE_MAX (T-resource-01 mitigation)"
      contains: "ARBITER_DEQUE_MAX"
    - path: tests/ingestion/test_event_log.py
      provides: "JSONL writer tests + StateHolder tests + sanitize-keys regression test (BLOCKER-1)"
  key_links:
    - from: "src/state/state_holder.py"
      to: "src/state/match_state.py"
      via: "self._state.with_update(**sanitized_fields)"
      pattern: "with_update"
    - from: "src/state/state_holder.py"
      to: "dataclasses.fields(MatchState)"
      via: "allowlist for sanitize_fields_changed"
      pattern: "dataclasses\\.fields\\(MatchState\\)"
---

<objective>
Wave 4 plan (split-A) — implement `StateHolder` (asyncio.Lock-protected MatchState reference cell) and the JSONL `EventLogWriter` + `MetricsWriter`. The Arbiter class itself lives in **03-07b**.

Purpose: Per BLOCKER-1, the arbiter's `_eval_round_end_rule` was injecting `_round_end_soft` into `fields_changed` and passing it to `with_update`, which would crash `dataclasses.replace` on the frozen+slots MatchState. Per WARNING-5, 03-07 modified ~11 files in two tasks and crossed the 10-file warning threshold. This split puts the StateHolder (root-cause fix location) into a separate plan with tight test coverage; 03-07b builds the arbiter against the sanitized swap_with surface.

Output: `src/state/state_holder.py` (with strip-before-swap discipline), `src/ingestion/event_log.py` (JSONL + metrics writers), `+1` deque-cap constant (consumed in 03-07b), tests covering sanitization + JSONL shape + StateHolder concurrency.
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
@src/ingestion/types.py
@src/config/constants.py
@CLAUDE.md
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add ARBITER_DEQUE_MAX constant + create src/state/state_holder.py with strip-before-swap discipline + create src/ingestion/event_log.py + tests</name>
  <files>src/state/state_holder.py, src/ingestion/event_log.py, src/state/__init__.py, src/ingestion/__init__.py, src/config/constants.py, tests/ingestion/test_event_log.py</files>
  <read_first>
    - src/state/match_state.py (with_update signature — sole mutator)
    - .planning/phases/03-live-ingestion-layer/03-RESEARCH.md §Code Examples EventLogLine writer (lines 814-889)
    - .planning/phases/03-live-ingestion-layer/03-RESEARCH.md §Anti-Patterns (lines 552-560)
    - .planning/phases/03-live-ingestion-layer/03-CONTEXT.md D-02 + D-05
    - src/ingestion/types.py (EventLogLine, MetricsLogLine, ConfirmedEvent.is_soft)
    - src/config/constants.py:EVENT_LOG_DIR, METRICS_LOG_DIR
  </read_first>
  <behavior>
    - Test 1 (test_match_id_sanitization_blocks_traversal): EventLogWriter(match_id="../../../etc/passwd") raises ValueError; "../foo" raises; "match\x00null" raises. Allowed: "abc", "match-123", "abc_def".
    - Test 2 (test_committed_line_shape): write_committed; read back; assert keys == {seq_id, t_observed, t_ingested, t_arbited, t_state_committed, t_theo_computed, t_quote_sent, source, event_type, fields_changed, quarantined}; t_theo_computed and t_quote_sent are JSON null.
    - Test 3 (test_quarantined_line_shape): write_quarantined; assert seq_id is JSON null, quarantined=true, quarantine_reason populated, fields_proposed populated.
    - Test 4 (test_committed_and_quarantined_share_file): D-05 — both shapes coexist in one .jsonl.
    - Test 5 (test_metrics_writer_one_line_per_committed_event): 5 events => 5 lines, each parseable, each has 6 timestamp keys.
    - Test 6 (test_periodic_flush): _FLUSH_EVERY_N + 1 events => disk size > 0.
    - Test 7 (test_state_holder_swap_returns_new_state_with_seq_id_bumped): StateHolder(seed); await holder.swap_with({"a_round": 5}); new state has seq_id=seed.seq_id+1.
    - Test 8 (test_state_holder_lock_prevents_concurrent_swap): two concurrent swap_with calls => seq_id 1 and 2 (never both 1).
    - Test 9 (BLOCKER-1 regression: test_swap_with_rejects_underscore_prefix_keys): await holder.swap_with({"_round_end_soft": True}) raises ValueError; state seq_id unchanged.
    - Test 10 (BLOCKER-1 regression: test_swap_with_rejects_unknown_keys): await holder.swap_with({"round_end_text": "hi"}) raises ValueError (round_end_text NOT in dataclasses.fields(MatchState)); state unchanged.
    - Test 11 (BLOCKER-1 regression: test_swap_with_accepts_known_keys): await holder.swap_with({"numerical_diff": 4}) succeeds (numerical_diff IS in MatchState fields).
  </behavior>
  <action>
**(a)** Append 1 new constant to `src/config/constants.py` Phase 3 section:

```python
ARBITER_DEQUE_MAX: Final[int] = 1000
"""Per-event-type deque cap (T-resource-01 mitigation; consumed by Arbiter in 03-07b)."""
```

**(b)** Create `src/state/state_holder.py`:

```python
"""Phase 3 StateHolder — asyncio.Lock-protected MatchState reference cell.

The arbiter is the SOLE writer to MatchState (per CONTEXT integration_points
line 148). Reader threads (engine driver, future quoter) hold a read-only
reference obtained via .read(); writers go through .swap_with() which holds
the lock for the duration of the with_update() call.

BLOCKER-1 (sole-writer discipline + sentinel-key rejection)
-----------------------------------------------------------
swap_with() ENFORCES that fields_changed contains ONLY keys that are public
attributes on MatchState. Specifically:
  1. Rejects any key starting with '_' (arbiter-internal sentinel; the arbiter
     uses ConfirmedEvent.is_soft=True instead).
  2. Rejects any key not in dataclasses.fields(MatchState) (allowlist).

This makes it IMPOSSIBLE for a future caller to crash dataclasses.replace by
sneaking an unknown key through with_update. The check happens BEFORE the
lock-protected mutation so a sentinel-key bug surfaces as a clean ValueError
in the caller's stack frame, not as a TypeError deep inside replace().

Sources
-------
- 03-CONTEXT.md integration_points (line 148 - arbiter is sole writer)
- 03-CONTEXT.md D-01 (frozen MatchState; with_update returns new instance)
- 03-RESEARCH.md §Architecture Patterns Pattern 4 (state_holder used by Arbiter)
- BLOCKER-1 from plan-checker: route soft-commit signal through is_soft, not
  through fields_changed; strip + reject sentinel keys before swap_with reaches
  with_update.
"""
from __future__ import annotations

import asyncio
import dataclasses
import time
from typing import Any, Final

from src.state.match_state import MatchState

# Allowlist computed once at import — public field names on MatchState.
_MATCH_STATE_FIELDS: Final[frozenset[str]] = frozenset(
    f.name for f in dataclasses.fields(MatchState)
)


def _sanitize_fields_changed(fields_changed: dict[str, Any]) -> dict[str, Any]:
    """BLOCKER-1: reject any key starting with '_' OR any key not in
    dataclasses.fields(MatchState). Returns a NEW dict containing only
    well-formed keys; raises ValueError if ANY rejected key is present.

    The strict reject (vs silent drop) ensures bugs surface immediately
    instead of silently dropping data that the arbiter expected to commit.
    """
    bad_underscore = [k for k in fields_changed if k.startswith("_")]
    bad_unknown = [k for k in fields_changed if k not in _MATCH_STATE_FIELDS]
    if bad_underscore or bad_unknown:
        raise ValueError(
            f"swap_with: invalid keys in fields_changed. "
            f"underscore-prefixed (sentinel; route via ConfirmedEvent.is_soft instead): "
            f"{bad_underscore!r}; unknown (not on MatchState): {bad_unknown!r}. "
            f"MatchState fields: {sorted(_MATCH_STATE_FIELDS)}"
        )
    return dict(fields_changed)  # defensive copy


class StateHolder:
    """Single-writer, multi-reader MatchState cell."""

    def __init__(self, initial: MatchState) -> None:
        self._state: MatchState = initial
        self._lock: asyncio.Lock = asyncio.Lock()

    def read(self) -> MatchState:
        return self._state

    async def swap_with(self, fields_changed: dict[str, Any]) -> tuple[MatchState, int]:
        """Apply with_update(**sanitized_fields_changed) under the lock.

        Returns (new_state, t_state_committed_ns).

        Raises ValueError if fields_changed contains any underscore-prefixed
        key or any key not in dataclasses.fields(MatchState) (BLOCKER-1).
        """
        sanitized = _sanitize_fields_changed(fields_changed)
        async with self._lock:
            new_state = self._state.with_update(**sanitized)
            t_committed_ns = time.monotonic_ns()
            self._state = new_state
            return new_state, t_committed_ns
```

**(c)** Update `src/state/__init__.py` to export it:

```python
from src.state.match_state import MatchState
from src.state.state_holder import StateHolder

__all__ = ["MatchState", "StateHolder"]
```

**(d)** Create `src/ingestion/event_log.py` (verbatim from original 03-07 — sanitization helper + EventLogWriter + MetricsWriter; see the original 03-07 plan body for the full code; reproduce it as-is here, with `_FLUSH_EVERY_N`, `_MATCH_ID_RE`, `_sanitize_match_id`, `EventLogWriter`, and `MetricsWriter` classes).

```python
"""Phase 3 JSONL writers — event log (D-02) + metrics file (REQ-latency-instrumentation)."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Final, Optional, TextIO

from src.config.constants import EVENT_LOG_DIR, METRICS_LOG_DIR

_FLUSH_EVERY_N: Final[int] = 32
_MATCH_ID_RE: Final[re.Pattern[str]] = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def _sanitize_match_id(match_id: str) -> str:
    if not isinstance(match_id, str):
        raise ValueError(f"match_id must be str, got {type(match_id).__name__}")
    if not _MATCH_ID_RE.match(match_id):
        raise ValueError(
            f"match_id {match_id!r} contains disallowed characters or is too long. "
            f"Allowed: [a-zA-Z0-9_-]{{1,64}}"
        )
    return match_id


class EventLogWriter:
    """JSONL writer for committed + quarantined events (D-02 unified file)."""

    def __init__(self, match_id: str, log_dir: Path = EVENT_LOG_DIR) -> None:
        self._match_id = _sanitize_match_id(match_id)
        log_dir.mkdir(parents=True, exist_ok=True)
        self._path: Path = log_dir / f"{self._match_id}.jsonl"
        self._fh: TextIO = self._path.open("a", buffering=1 << 16, encoding="utf-8")
        self._n_since_flush: int = 0

    @property
    def path(self) -> Path:
        return self._path

    def write_committed(
        self,
        *,
        seq_id: int,
        t_observed: float,
        t_ingested_ns: int,
        t_arbited_ns: int,
        t_state_committed_ns: int,
        source: str,
        event_type: str,
        fields_changed: dict[str, Any],
    ) -> None:
        line: dict[str, Any] = {
            "seq_id": seq_id,
            "t_observed": t_observed,
            "t_ingested": t_ingested_ns / 1e9,
            "t_arbited": t_arbited_ns / 1e9,
            "t_state_committed": t_state_committed_ns / 1e9,
            "t_theo_computed": None,
            "t_quote_sent": None,
            "source": source,
            "event_type": event_type,
            "fields_changed": fields_changed,
            "quarantined": False,
        }
        self._write(line)

    def write_quarantined(
        self,
        *,
        source: str,
        event_type: str,
        fields_proposed: dict[str, Any],
        t_observed: float,
        reason: str,
    ) -> None:
        line: dict[str, Any] = {
            "seq_id": None,
            "quarantined": True,
            "quarantine_reason": reason,
            "source": source,
            "event_type": event_type,
            "fields_proposed": fields_proposed,
            "t_observed": t_observed,
        }
        self._write(line)

    def _write(self, line: dict[str, Any]) -> None:
        self._fh.write(json.dumps(line, separators=(",", ":")) + "\n")
        self._n_since_flush += 1
        if self._n_since_flush >= _FLUSH_EVERY_N:
            self._fh.flush()
            self._n_since_flush = 0

    def close(self) -> None:
        self._fh.flush()
        self._fh.close()


class MetricsWriter:
    """JSONL writer for the six-stage latency lineage (REQ-latency-instrumentation)."""

    def __init__(self, match_id: str, log_dir: Path = METRICS_LOG_DIR) -> None:
        self._match_id = _sanitize_match_id(match_id)
        log_dir.mkdir(parents=True, exist_ok=True)
        self._path: Path = log_dir / f"{self._match_id}.metrics.jsonl"
        self._fh: TextIO = self._path.open("a", buffering=1 << 16, encoding="utf-8")
        self._n_since_flush: int = 0

    @property
    def path(self) -> Path:
        return self._path

    def write(
        self,
        *,
        seq_id: int,
        t_observed: float,
        t_ingested_ns: int,
        t_arbited_ns: int,
        t_state_committed_ns: int,
        source: str,
        event_type: str,
        t_theo_computed_ns: Optional[int] = None,  # noqa: UP045
        t_quote_sent_ns: Optional[int] = None,     # noqa: UP045
    ) -> None:
        line: dict[str, Any] = {
            "seq_id": seq_id,
            "t_observed": t_observed,
            "t_ingested": t_ingested_ns / 1e9,
            "t_arbited": t_arbited_ns / 1e9,
            "t_state_committed": t_state_committed_ns / 1e9,
            "t_theo_computed": (t_theo_computed_ns / 1e9) if t_theo_computed_ns is not None else None,
            "t_quote_sent": (t_quote_sent_ns / 1e9) if t_quote_sent_ns is not None else None,
            "source": source,
            "event_type": event_type,
        }
        self._fh.write(json.dumps(line, separators=(",", ":")) + "\n")
        self._n_since_flush += 1
        if self._n_since_flush >= _FLUSH_EVERY_N:
            self._fh.flush()
            self._n_since_flush = 0

    def write_followup(
        self,
        *,
        seq_id: int,
        t_theo_computed_ns: Optional[int] = None,  # noqa: UP045
        t_quote_sent_ns: Optional[int] = None,     # noqa: UP045
    ) -> None:
        """Per Pitfall 8: append a follow-up line keyed by seq_id."""
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

    def close(self) -> None:
        self._fh.flush()
        self._fh.close()


__all__ = ["EventLogWriter", "MetricsWriter", "_sanitize_match_id"]
```

(NOTE: `MetricsWriter.write_followup` is included here since it's needed by 03-08's EngineDriver and the BLOCKER-1 / WARNING-5 split surfaces it earlier; that's a small forward-port.)

**(e)** Create `tests/ingestion/test_event_log.py` covering all 11 behaviors (the previous 03-07 test file PLUS the BLOCKER-1 sanitize-keys tests):

```python
"""EventLogWriter + MetricsWriter + StateHolder tests — REQ-match-state-engine
JSONL + REQ-latency-instrumentation + T-files-01 + BLOCKER-1 sanitize."""
from __future__ import annotations

import asyncio
import dataclasses
import json
from pathlib import Path

import pytest

from src.ingestion.event_log import (
    EventLogWriter,
    MetricsWriter,
    _FLUSH_EVERY_N,
    _sanitize_match_id,
)
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


# ----- T-files-01 sanitization ----- #

@pytest.mark.parametrize("bad", [
    "../../../etc/passwd", "../foo", "match\x00null", "match/foo", "match\\foo",
    "match.jsonl", "", "a" * 65,
])
def test_sanitize_match_id_rejects_disallowed(bad: str) -> None:
    with pytest.raises(ValueError):
        _sanitize_match_id(bad)


@pytest.mark.parametrize("good", ["abc", "match-123", "abc_def", "x", "A1_B2-C3"])
def test_sanitize_match_id_accepts_safe(good: str) -> None:
    assert _sanitize_match_id(good) == good


# ----- EventLogWriter (D-02 + D-05) ----- #

def test_committed_line_shape(tmp_path: Path) -> None:
    w = EventLogWriter("match1", log_dir=tmp_path)
    w.write_committed(
        seq_id=42, t_observed=1730439612.123,
        t_ingested_ns=1_730_439_612_151_000_000,
        t_arbited_ns=1_730_439_612_198_000_000,
        t_state_committed_ns=1_730_439_612_201_000_000,
        source="ocr", event_type="kill",
        fields_changed={"numerical_diff": 4},
    )
    w.close()
    rec = json.loads((tmp_path / "match1.jsonl").read_text().strip())
    expected_keys = {
        "seq_id", "t_observed", "t_ingested", "t_arbited", "t_state_committed",
        "t_theo_computed", "t_quote_sent", "source", "event_type",
        "fields_changed", "quarantined",
    }
    assert set(rec.keys()) == expected_keys
    assert rec["t_theo_computed"] is None
    assert rec["t_quote_sent"] is None
    assert rec["quarantined"] is False


def test_quarantined_line_shape(tmp_path: Path) -> None:
    w = EventLogWriter("match1", log_dir=tmp_path)
    w.write_quarantined(
        source="twitter", event_type="kill",
        fields_proposed={"numerical_diff": 4}, t_observed=1730439645.001,
        reason="kill needs CV source; twitter-only",
    )
    w.close()
    rec = json.loads((tmp_path / "match1.jsonl").read_text().strip())
    assert rec["seq_id"] is None
    assert rec["quarantined"] is True
    assert "twitter" in rec["quarantine_reason"]


def test_committed_and_quarantined_share_file(tmp_path: Path) -> None:
    w = EventLogWriter("match1", log_dir=tmp_path)
    w.write_committed(
        seq_id=1, t_observed=1.0, t_ingested_ns=1_000_000_000,
        t_arbited_ns=2_000_000_000, t_state_committed_ns=3_000_000_000,
        source="ribgg", event_type="score_change", fields_changed={"a_round": 7},
    )
    w.write_quarantined(
        source="twitter", event_type="kill",
        fields_proposed={"numerical_diff": 4}, t_observed=2.0,
        reason="twitter-only kill",
    )
    w.close()
    lines = (tmp_path / "match1.jsonl").read_text().strip().split("\n")
    assert len(lines) == 2
    assert json.loads(lines[0])["seq_id"] == 1
    assert json.loads(lines[1])["seq_id"] is None


def test_periodic_flush_lands_data_on_disk(tmp_path: Path) -> None:
    w = EventLogWriter("match1", log_dir=tmp_path)
    for i in range(_FLUSH_EVERY_N + 1):
        w.write_committed(
            seq_id=i, t_observed=float(i), t_ingested_ns=i,
            t_arbited_ns=i, t_state_committed_ns=i,
            source="ocr", event_type="kill", fields_changed={},
        )
    size = (tmp_path / "match1.jsonl").stat().st_size
    w.close()
    assert size > 0


# ----- MetricsWriter ----- #

def test_metrics_writer_one_line_per_event(tmp_path: Path) -> None:
    w = MetricsWriter("match1", log_dir=tmp_path)
    for i in range(5):
        w.write(
            seq_id=i, t_observed=float(i),
            t_ingested_ns=i * 1_000_000_000,
            t_arbited_ns=(i + 1) * 1_000_000_000,
            t_state_committed_ns=(i + 2) * 1_000_000_000,
            source="ocr", event_type="kill",
        )
    w.close()
    lines = (tmp_path / "match1.metrics.jsonl").read_text().strip().split("\n")
    assert len(lines) == 5


# ----- StateHolder ----- #

@pytest.mark.asyncio
async def test_state_holder_swap_returns_new_state_with_seq_id_bumped() -> None:
    holder = StateHolder(_seed_state())
    assert holder.read().seq_id == 0
    new_state, t_ns = await holder.swap_with({"a_round": 5})
    assert new_state.seq_id == 1
    assert new_state.a_round == 5
    assert isinstance(t_ns, int)


@pytest.mark.asyncio
async def test_state_holder_lock_serializes_concurrent_swaps() -> None:
    holder = StateHolder(_seed_state())

    async def _do_swap(field_val: int) -> int:
        s, _ = await holder.swap_with({"numerical_diff": field_val})
        return s.seq_id

    results = await asyncio.gather(_do_swap(1), _do_swap(2))
    assert sorted(results) == [1, 2]


# ----- BLOCKER-1 regression: sentinel-key + unknown-key rejection ----- #

@pytest.mark.asyncio
async def test_swap_with_rejects_underscore_prefix_keys() -> None:
    """BLOCKER-1: arbiter sentinel keys (underscore-prefixed) must NOT reach
    dataclasses.replace. swap_with raises ValueError before any state mutation.
    """
    holder = StateHolder(_seed_state())
    with pytest.raises(ValueError, match="underscore-prefixed"):
        await holder.swap_with({"_round_end_soft": True})
    assert holder.read().seq_id == 0  # state unchanged


@pytest.mark.asyncio
async def test_swap_with_rejects_unknown_keys_not_on_matchstate() -> None:
    """BLOCKER-1: keys not in dataclasses.fields(MatchState) raise ValueError.
    Catches typos like `numerical_diff_delta` (the original BLOCKER-1 root cause)
    and OCR backend bugs that emit `round_end_text` (no MatchState slot)."""
    holder = StateHolder(_seed_state())
    with pytest.raises(ValueError, match="unknown"):
        await holder.swap_with({"round_end_text": "ROUND END"})
    with pytest.raises(ValueError, match="unknown"):
        await holder.swap_with({"numerical_diff_delta": 4})
    assert holder.read().seq_id == 0


@pytest.mark.asyncio
async def test_swap_with_accepts_all_known_matchstate_keys() -> None:
    """BLOCKER-1 regression: every key in dataclasses.fields(MatchState) that
    isn't seq_id/last_updated_ts (those are stripped by with_update) IS accepted.
    Fenced over the actual field list so a future MatchState rename can't
    silently break the allowlist."""
    holder = StateHolder(_seed_state())
    # Sample a few known fields, including the BLOCKER-1 corrected `numerical_diff`.
    for known in ("a_round", "numerical_diff", "bomb_planted", "side", "econ_bucket"):
        assert known in {f.name for f in dataclasses.fields(MatchState)}
        # Construct a sane payload per field type.
        payload: dict[str, object] = {known: 4 if known.endswith(("_round", "_diff")) else (
            False if known == "bomb_planted" else "atk" if known == "side" else "full"
        )}
        await holder.swap_with(payload)  # must not raise
    # Sanity: state has been mutated through several legal calls.
    assert holder.read().seq_id >= 1
```

**(f)** `src/ingestion/__init__.py` — add `EventLogWriter, MetricsWriter` to the existing exports (no Arbiter yet — that's 03-07b).
  </action>
  <verify>
    <automated>pytest tests/ingestion/test_event_log.py -x &amp;&amp; mypy --strict src/state/state_holder.py &amp;&amp; mypy src/ingestion/event_log.py &amp;&amp; ruff check src/state/state_holder.py src/ingestion/event_log.py tests/ingestion/test_event_log.py</automated>
  </verify>
  <done>StateHolder + 2 JSONL writers exist; T-files-01 sanitization rejects 8 traversal/path-injection variants; BLOCKER-1 strip-before-swap discipline rejects underscore-prefixed keys + unknown keys (3 dedicated regression tests); concurrent swap serialized; mypy --strict src/state/ clean; ALL Phase 1+2+03-* prior regressions GREEN. 03-07b can begin.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| arbiter -> filesystem | EventLogWriter + MetricsWriter write `data/event_log/{match_id}.jsonl`. |
| arbiter -> StateHolder | Sole writer to MatchState; concurrent submit() calls serialized via asyncio.Lock. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-03-07a-01 (covers T-files-01) | T (Tampering) | filename construction | mitigate | `_sanitize_match_id()` whitelists `[a-zA-Z0-9_-]{1,64}`. |
| T-03-07a-02 (BLOCKER-1) | T (Tampering) | sentinel-key crash on dataclasses.replace | mitigate | `_sanitize_fields_changed` rejects underscore-prefixed AND unknown keys BEFORE swap_with reaches with_update. 3 regression tests prove it. |
| T-03-07a-03 | T (Tampering) | StateHolder concurrent swap | mitigate | `swap_with()` holds `self._lock` for the duration of `with_update()`. |
</threat_model>

<verification>
- `pytest tests/ingestion/test_event_log.py -x` PASSES.
- `mypy --strict src/state/state_holder.py` clean.
- `mypy src/ingestion/event_log.py` clean.
- BLOCKER-1 regression tests prove `_round_end_soft`, `round_end_text`, `numerical_diff_delta` all raise ValueError.
- Phase 1 + 2 + 03-* prior regressions GREEN.
</verification>

<success_criteria>
Wave 4 plan 03-07a is COMPLETE when:

1. `src/state/state_holder.py` exports StateHolder with `_sanitize_fields_changed` strip-before-swap discipline (BLOCKER-1 root-cause fix).
2. `src/ingestion/event_log.py` exports EventLogWriter + MetricsWriter + write_followup + `_sanitize_match_id`.
3. `ARBITER_DEQUE_MAX = 1000` added to `src/config/constants.py`.
4. `tests/ingestion/test_event_log.py` has tests covering: T-files-01 sanitization (8 reject + 5 accept), JSONL committed/quarantined shape, periodic flush, metrics writer, StateHolder swap + concurrency, AND 3 BLOCKER-1 regression tests (`_round_end_soft`, `round_end_text`/`numerical_diff_delta`, accept-known-keys).
5. `src/state/__init__.py` re-exports StateHolder.
6. Phase 1 + 2 + 03-* prior regressions GREEN.
7. 03-07b can begin (consumes StateHolder.swap_with + EventLogWriter + MetricsWriter).
</success_criteria>

<output>
After completion, create `.planning/phases/03-live-ingestion-layer/03-07a-SUMMARY.md` documenting the StateHolder + JSONL writers + BLOCKER-1 fix.
</output>
