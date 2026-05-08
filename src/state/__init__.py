"""State engine — `MatchState` dataclass + JSONL event-log helpers (Phase 3).

Re-exports MatchState plus the single-writer JSONL helpers from
``src.state.match_state`` so callers may write
``from src.state import MatchState, commit, quarantine`` (the long-term
canonical import path per Phase 3 D-01 / D-03).
"""

from src.state.match_state import MatchState, commit, quarantine

__all__ = ["MatchState", "commit", "quarantine"]
