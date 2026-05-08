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
from typing import Optional, TypedDict


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
    t_ingested: Optional[int]  # noqa: UP045 — TypedDict + None requires Optional
    t_arbited: Optional[int]  # noqa: UP045
    t_state_committed: Optional[int]  # noqa: UP045
    t_theo_computed: Optional[int]  # noqa: UP045 — None in Phase 3 (Phase 4 fills)
    t_quote_sent: Optional[int]  # noqa: UP045 — None in Phase 3 (Phase 4 fills)
