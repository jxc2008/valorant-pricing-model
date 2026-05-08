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

DEC-006 v2 cuts from v1 (grep-verifiable absence in this file):
- 5-deque schema (DEC-024 v2 cuts kill-feed CV + mid-round economy inference)

Confirmation rules (DEC-006 v2):
- score_change: ≥ 2 sources within ARBITER_SCORE_WINDOW_S (2s) on the SAME
  proposed fields → commit. Single-source events stay in the deque awaiting
  a cross-confirm; events older than _DEQUE_MAX_AGE_S (3s wall-clock) are
  quarantined as "stale_in_deque_no_cross_confirm".
- bomb_plant / bomb_defuse / post_plant_alive: 1 OCR source soft-commit
  immediately. Hard-confirm-by-next-score is a Phase 4 mode-selector concern;
  the arbiter does the soft-commit so live_theo can react inside the 100ms
  bomb-detect → state-commit budget.
- round_end: 1 OCR source soft-commit immediately. Same shape as bomb_plant.

Six-stage timestamp lineage (D-03 / SPEC §6):
- t_observed: source-side wall_time() at frame capture / API response
- t_ingested: source-side mono_ns() at PendingEvent push time
- t_arbited: arbiter mono_ns() at confirmation (right before commit)
- t_state_committed: src.state.commit mono_ns() right before JSONL write
- t_theo_computed: Phase 4 (LiveTheoEngine after live_theo)
- t_quote_sent: Phase 4 (KalshiOrderManager after place_quote)
"""
from __future__ import annotations

import json
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
from src.ingestion.timestamps import mono_ns
from src.state import MatchState, commit, quarantine

logger = logging.getLogger(__name__)

_DEQUE_MAX_AGE_S: float = 3.0
"""Single-source events older than this in score_changes -> quarantine."""


class Arbiter:
    """Single-consumer arbiter for 3 ingestion deques (DEC-006 v2).

    SOLE writer of MatchState in production: every state mutation flows
    through `_commit_event` -> `src.state.commit` -> JSONL append. SOLE
    appender of `data/event_log/{match_id}.jsonl` and
    `data/metrics/{match_id}.metrics.jsonl`.
    """

    def __init__(
        self,
        initial_state: MatchState,
        *,
        event_log_dir: Path | None = None,
        metrics_log_dir: Path | None = None,
    ) -> None:
        self._state = initial_state
        elog = event_log_dir if event_log_dir is not None else Path(EVENT_LOG_DIR)
        mlog = metrics_log_dir if metrics_log_dir is not None else Path(METRICS_LOG_DIR)
        self._jsonl_path: Path = elog / f"{initial_state.match_id}.jsonl"
        self._metrics_path: Path = mlog / f"{initial_state.match_id}.metrics.jsonl"
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
        """Drain all 3 deques; apply confirmation rules; commit / quarantine.

        Invariant: this method is the SOLE caller of `src.state.commit` and
        `src.state.quarantine` in production. Driver code (asyncio loop in
        src/main.py) invokes `tick()` at ARBITER_TICK_HZ; tests call it
        directly after pushing PendingEvents.
        """
        self._drain_score_changes()
        self._drain_bomb_events()
        self._drain_round_end_events()

    # ------------------------------------------------------------------ #
    # Rule: score_change — >= 2 sources within ARBITER_SCORE_WINDOW_S    #
    # ------------------------------------------------------------------ #
    def _drain_score_changes(self) -> None:
        """Group score_changes by fields_proposed signature.

        - >= 2 distinct sources within ARBITER_SCORE_WINDOW_S -> commit
          (SOLE caller of src.state.commit for score events).
        - Stale events (t_observed older than _DEQUE_MAX_AGE_S) -> quarantine.
        - Otherwise hold (re-queue for next tick).
        """
        if not self.score_changes:
            return

        # Use mono_ns()-driven "now" for staleness checks via wall delta.
        # ev.t_observed is wall_time(); compare in same domain.
        import time
        now = time.time()

        groups: dict[tuple[tuple[str, Any], ...], list[PendingEvent]] = {}
        survivors: deque[PendingEvent] = deque(maxlen=self.score_changes.maxlen)

        for ev in self.score_changes:
            if now - ev.t_observed > _DEQUE_MAX_AGE_S:
                self._quarantine_event(ev, reason="stale_in_deque_no_cross_confirm")
                continue
            key = tuple(sorted(ev.fields_proposed.items()))
            groups.setdefault(key, []).append(ev)

        for sig, evs in groups.items():
            distinct_sources = {ev.source for ev in evs}
            if len(distinct_sources) >= 2 and self._within_window(evs):
                # Confirmed — commit using earliest t_observed (broadcast wall-clock).
                earliest = min(evs, key=lambda e: e.t_observed)
                fields_changed: dict[str, Any] = dict(sig)
                self._commit_event(
                    fields_changed=fields_changed,
                    event_type=earliest.event_type,
                    sources=tuple(sorted(distinct_sources)),
                    t_observed=earliest.t_observed,
                    t_ingested=earliest.t_ingested,
                )
            else:
                # Hold — re-queue all events in the group for next tick.
                for ev in evs:
                    survivors.append(ev)

        self.score_changes = survivors

    @staticmethod
    def _within_window(evs: list[PendingEvent]) -> bool:
        ts = [ev.t_observed for ev in evs]
        return (max(ts) - min(ts)) <= ARBITER_SCORE_WINDOW_S

    # ------------------------------------------------------------------ #
    # Rule: bomb_event — 1 OCR source soft-commit immediately            #
    # ------------------------------------------------------------------ #
    def _drain_bomb_events(self) -> None:
        """Bomb plant / defuse / post-plant alive widget — single-source soft-commit.

        SOLE caller of src.state.commit for bomb-family events. Hard-confirm
        by next score is a Phase 4 mode-selector concern (degrades quoting to
        IDLE if the next score commit contradicts the soft-committed state);
        the arbiter does NOT roll back here per CONTEXT D-02 single-writer
        invariant.
        """
        while self.bomb_events:
            ev = self.bomb_events.popleft()
            self._commit_event(
                fields_changed=dict(ev.fields_proposed),
                event_type=ev.event_type,
                sources=(ev.source,),
                t_observed=ev.t_observed,
                t_ingested=ev.t_ingested,
            )

    # ------------------------------------------------------------------ #
    # Rule: round_end_event — 1 OCR source soft-commit immediately       #
    # ------------------------------------------------------------------ #
    def _drain_round_end_events(self) -> None:
        """Round-end banner OCR — single-source soft-commit immediately.

        SOLE caller of src.state.commit for round_end events. Same shape as
        bomb_events: arbiter does not retry / roll back; Phase 4 mode-selector
        handles the next-score consistency check.
        """
        while self.round_end_events:
            ev = self.round_end_events.popleft()
            self._commit_event(
                fields_changed=dict(ev.fields_proposed),
                event_type=ev.event_type,
                sources=(ev.source,),
                t_observed=ev.t_observed,
                t_ingested=ev.t_ingested,
            )

    # ------------------------------------------------------------------ #
    # Commit / quarantine plumbing — sole writer of MatchState + JSONL   #
    # ------------------------------------------------------------------ #
    def _commit_event(
        self,
        *,
        fields_changed: dict[str, Any],
        event_type: EventType,
        sources: tuple[SourceName, ...],
        t_observed: float,
        t_ingested: int,
    ) -> None:
        """SOLE production caller of src.state.commit.

        Concatenates source provenance into a "|"-joined string for the JSONL
        line; commit() takes a single source field. The t_arbited timestamp
        is set HERE (right before commit()); t_state_committed is set inside
        commit() right before the JSONL append per RESEARCH §"Pattern 2"
        hot-path key insight.
        """
        source_str = "|".join(sources) if len(sources) > 1 else sources[0]
        timestamps: dict[str, float | int | None] = {
            "t_observed": t_observed,
            "t_ingested": t_ingested,
            "t_arbited": mono_ns(),
            "t_state_committed": None,  # commit() sets this in place
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
        # Mirror to metrics log (Phase 4 fills t_theo_computed / t_quote_sent there).
        self._write_metrics_line(timestamps, source_str, event_type, fields_changed)

    def _quarantine_event(self, ev: PendingEvent, *, reason: str) -> None:
        """SOLE production caller of src.state.quarantine."""
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
        """Append one line to data/metrics/{match_id}.metrics.jsonl.

        Mirror of the timestamps record + commit-side provenance. Does NOT
        duplicate the JSONL diff log: event_log = state replay; metrics =
        latency analysis. Phase 4 fills t_theo_computed / t_quote_sent on a
        parallel update keyed by seq_id.
        """
        line: dict[str, Any] = {
            "seq_id": self._state.seq_id,
            "t_observed": timestamps.get("t_observed"),
            "t_ingested": timestamps.get("t_ingested"),
            "t_arbited": timestamps.get("t_arbited"),
            "t_state_committed": timestamps.get("t_state_committed"),
            "t_theo_computed": timestamps.get("t_theo_computed"),
            "t_quote_sent": timestamps.get("t_quote_sent"),
            "source": source,
            "event_type": event_type,
            "fields_changed_keys": sorted(fields_changed.keys()),
        }
        self._metrics_path.parent.mkdir(parents=True, exist_ok=True)
        with self._metrics_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(line, separators=(",", ":")) + "\n")
