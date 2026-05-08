"""State engine — `MatchState` dataclass + JSONL event log (Phase 3).

Re-exports MatchState from ``src.state.match_state`` so callers may write
``from src.state import MatchState`` (the long-term canonical import path per
Phase 3 D-01).

The companion ``commit`` / ``quarantine`` helpers ship in plan 03-01 Task 2 and
will be re-exported here at that point.
"""

from src.state.match_state import MatchState

__all__ = ["MatchState"]
