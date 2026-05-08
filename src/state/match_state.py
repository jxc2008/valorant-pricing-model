"""MatchState v2 + JSONL event-log helpers — Phase 3 single-source-of-truth runtime state.

Per Phase 3 D-01 / D-02 / D-03 / D-14, RESEARCH §"Pattern 1" / §"Code Examples".

The dataclass is frozen + slots and carries:
  - 7 static-per-match fields required by ``live_theo`` (Phase 1 D-17/D-18/D-19):
    ``match_id, team_a, team_b, map_pool, map_side_orients, map_winners,
    pistol_winner_a``.
  - 12 dynamic v2 fields (D-01): ``map_idx, a_map_score, b_map_score, a_round,
    b_round, side_orient, bomb_planted, attackers_alive, defenders_alive,
    time_left_s, seq_id, last_updated_ts``.

Cut from the v1 stub (D-01): ``numerical_diff, side, econ_bucket`` — these were
v1 round_conclusion lookup keys and are irrelevant under the v2 keying
``(att, def, time_bucket, side, map)`` (D-04).

Pure mutator (D-02)
-------------------
``MatchState.with_update(**fields_changed)`` returns a NEW frozen instance with
``seq_id`` bumped by 1 and ``last_updated_ts = time.time()``. NO I/O. The
arbiter (Phase 3 Wave 3A) is the SOLE caller in production; tests construct
states directly.

Why pure: per D-02, decoupling JSONL append from the mutator makes the engine
unit-testable without ``tmp_path`` fixtures and keeps the dry-run path clean.

Single-writer JSONL helpers (D-03)
----------------------------------
``commit(prev, fields_changed, *, source, event_type, timestamps, jsonl_path)``
wraps ``with_update`` with a synchronous JSONL append per the D-03 schema.
``quarantine(...)`` writes a quarantine line; state is unchanged.

**Single-writer invariant:** the arbiter (Phase 3 Wave 3A) is the SOLE caller
of ``commit`` and ``quarantine`` in production. The JSONL append is atomic
under POSIX ``O_APPEND`` for writes ≤ PIPE_BUF (4KB on Linux); on Windows the
single-writer invariant is maintained by the arbiter's ``tick()`` loop being
the sole producer (RESEARCH Pitfall 4).

References
----------
- ``.planning/phases/03-live-ingestion-layer/03-CONTEXT.md``
  D-01, D-02, D-03, D-14
- ``.planning/phases/03-live-ingestion-layer/03-RESEARCH.md``
  Pattern 1, Pitfall 4, Pitfall 7, Pitfall 8
- ``CLAUDE.md`` ``MatchState`` field set (v2)
- Phase 1 D-17/D-18/D-19 — static fields preserved for ``live_theo``
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Optional


@dataclass(frozen=True, slots=True)
class MatchState:
    """Phase 3 v2 MatchState — 19 fields total.

    Field order (positional, no defaults — callers MUST be explicit):

    Static-per-match (7):
      match_id, team_a, team_b, map_pool, map_side_orients, map_winners,
      pistol_winner_a.

    Dynamic v2 (12):
      map_idx, a_map_score, b_map_score, a_round, b_round, side_orient,
      bomb_planted, attackers_alive, defenders_alive, time_left_s, seq_id,
      last_updated_ts.

    ``attackers_alive`` / ``defenders_alive`` / ``time_left_s`` are populated
    only when ``bomb_planted=True`` — see D-12, D-13, D-14. Otherwise they are
    ``None`` (carry-forward semantics per Phase 2 D-08).
    """

    # 7 static fields (Phase 1 D-17/D-18/D-19; required by live_theo)
    match_id: str
    team_a: str
    team_b: str
    map_pool: tuple[str, ...]
    map_side_orients: tuple[str, ...]
    map_winners: tuple[Optional[bool], ...]  # noqa: UP045 — Optional[bool] required for tuple keying
    pistol_winner_a: dict[int, Optional[bool]]  # noqa: UP045 — Optional[bool] kept for clarity

    # 12 dynamic fields (v2)
    map_idx: int
    a_map_score: int
    b_map_score: int
    a_round: int
    b_round: int
    side_orient: str
    bomb_planted: bool
    attackers_alive: Optional[int]  # noqa: UP045 — populated only when bomb_planted=True
    defenders_alive: Optional[int]  # noqa: UP045 — populated only when bomb_planted=True
    time_left_s: Optional[float]  # noqa: UP045 — computed per D-14 when bomb_planted=True
    seq_id: int
    last_updated_ts: float

    def with_update(self, **fields_changed: Any) -> MatchState:
        """Return a new MatchState with ``fields_changed`` applied.

        Bumps ``seq_id`` by 1 and refreshes ``last_updated_ts = time.time()``.
        Pure: no JSONL I/O — see module docstring.

        Calling with no kwargs still bumps ``seq_id`` (semantic: state has
        materially changed via heartbeat). The arbiter relies on this for the
        ``score_changes`` deque heartbeat path.

        Pitfall 8 (RESEARCH): ``last_updated_ts`` uses ``time.time()`` and is
        informational only — wall-clock resolution on Windows is ~16ms. The
        monotonicity primitive is ``seq_id``; tests MUST assert on ``seq_id``
        strictness, not ``last_updated_ts``.
        """
        return replace(
            self,
            seq_id=self.seq_id + 1,
            last_updated_ts=time.time(),
            **fields_changed,
        )


def commit(
    prev: MatchState,
    fields_changed: dict[str, Any],
    *,
    source: str,
    event_type: str,
    timestamps: dict[str, float | int | None],
    jsonl_path: Path,
) -> MatchState:
    """Commit a state mutation: bump seq_id, write JSONL diff line, return new state.

    Caller is the arbiter (sole writer per D-02 / RESEARCH Pitfall 4). The
    ``jsonl_path`` SHOULD be a per-match file at
    ``data/event_log/{match_id}.jsonl``. ``t_state_committed`` is recorded
    BEFORE the synchronous JSONL append to satisfy the D-03 / SPEC §6
    bomb-detect → t_state_committed p50 < 100ms budget — disk write latency
    is excluded from the latency math.

    The 9-key commit-line schema per D-03:
        seq_id, t_observed, t_ingested, t_arbited, t_state_committed,
        t_theo_computed, t_quote_sent, source, event_type, fields_changed.

    ``timestamps`` is a mutable dict supplied by the arbiter pre-populated with
    ``t_observed, t_ingested, t_arbited`` and ``t_theo_computed: None,
    t_quote_sent: None``. ``commit`` mutates it in place to record
    ``t_state_committed`` (RESEARCH §"Code Examples").
    """
    new_state = prev.with_update(**fields_changed)
    timestamps["t_state_committed"] = time.monotonic_ns()
    line: dict[str, Any] = {
        "seq_id": new_state.seq_id,
        "t_observed": timestamps.get("t_observed"),
        "t_ingested": timestamps.get("t_ingested"),
        "t_arbited": timestamps.get("t_arbited"),
        "t_state_committed": timestamps["t_state_committed"],
        "t_theo_computed": timestamps.get("t_theo_computed"),
        "t_quote_sent": timestamps.get("t_quote_sent"),
        "source": source,
        "event_type": event_type,
        "fields_changed": fields_changed,
    }
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    with jsonl_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(line, separators=(",", ":")) + "\n")
    return new_state


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
    """Record a quarantined event; state UNCHANGED.

    ``prev`` is accepted (and unused at the body level) to keep the call-site
    symmetric with ``commit(...)`` — the arbiter calls one or the other and
    passes ``prev`` for context.

    The 7-key quarantine-line schema per D-03:
        seq_id (always None), quarantined (always True), quarantine_reason,
        t_observed, source, event_type, fields_proposed.

    Replay logic MUST filter ``seq_id is None`` before applying ``with_update``
    (RESEARCH §"Common Pitfalls").
    """
    del prev  # symmetric with commit() signature; state unchanged.
    line: dict[str, Any] = {
        "seq_id": None,
        "quarantined": True,
        "quarantine_reason": quarantine_reason,
        "t_observed": t_observed,
        "source": source,
        "event_type": event_type,
        "fields_proposed": fields_proposed,
    }
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    with jsonl_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(line, separators=(",", ":")) + "\n")
