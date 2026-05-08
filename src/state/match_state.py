"""MatchState v2 — Phase 3 single-source-of-truth runtime state.

Per Phase 3 D-01 / D-02 / D-14, RESEARCH §"Pattern 1" / §"Code Examples".

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
The companion ``commit`` / ``quarantine`` module-level helpers (added in plan
03-01 Task 2) wrap ``with_update`` + JSONL append into the arbiter-facing
single-writer surface.

References
----------
- ``.planning/phases/03-live-ingestion-layer/03-CONTEXT.md`` D-01, D-02, D-14
- ``.planning/phases/03-live-ingestion-layer/03-RESEARCH.md`` Pattern 1, Pitfall 7, Pitfall 8
- ``CLAUDE.md`` ``MatchState`` field set (v2)
- Phase 1 D-17/D-18/D-19 — static fields preserved for ``live_theo``
"""

from __future__ import annotations

import time
from dataclasses import dataclass, replace
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
