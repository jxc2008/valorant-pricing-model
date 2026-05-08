"""Phase 3 ingestion test fixtures.

Used by every tests/ingestion/test_*.py file per VALIDATION.md.

Wave 1 (plan 03-01) update: ``make_match_state`` now returns a real
``MatchState`` dataclass instance (not a dict) — Wave 0 deferred the swap
because src/state/match_state.py didn't exist yet.
"""
from __future__ import annotations

from collections import deque
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from src.state.match_state import MatchState


@pytest.fixture
def make_match_state() -> Callable[..., MatchState]:
    """Build a v2-shape MatchState; tests pass kwargs to override any field.

    Default state: BO3 series in progress, map 0 active, T1 vs Sentinels on
    Lotus|Bind|Haven, side_orient=a_atk, no bomb planted, seq_id=0.
    Override any field via kwargs.
    """

    def _make(**overrides: Any) -> MatchState:
        base: dict[str, Any] = {
            "match_id": "test-match-001",
            "team_a": "T1",
            "team_b": "Sentinels",
            "map_pool": ("Lotus", "Bind", "Haven"),
            "map_side_orients": ("a_atk", "a_def", "a_atk"),
            "map_winners": (None, None, None),
            "pistol_winner_a": {0: None, 1: None, 2: None},
            "map_idx": 0,
            "a_map_score": 0,
            "b_map_score": 0,
            "a_round": 0,
            "b_round": 0,
            "side_orient": "a_atk",
            "bomb_planted": False,
            "attackers_alive": None,
            "defenders_alive": None,
            "time_left_s": None,
            "seq_id": 0,
            "last_updated_ts": 0.0,
        }
        base.update(overrides)
        return MatchState(**base)

    return _make


@pytest.fixture
def tmp_event_log_path(tmp_path: Path) -> Path:
    """Per-test JSONL event-log path; gitignored data/event_log/ format mirrored."""
    p = tmp_path / "event_log" / "test-match-001.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


@pytest.fixture
def synthetic_frame_factory() -> Callable[..., np.ndarray]:
    """Build a fake BGR uint8 1920x1080 frame with optional digit overlays at ROI coords.

    Used by Wave 3C OCR benchmarks. Caller passes (att, def_) tuples and
    pixel coordinates; returns a frame ready for cv2 ROI extraction.
    """

    def _make(
        att: int | None = None,
        def_: int | None = None,
        att_roi: tuple[int, int, int, int] | None = None,
        def_roi: tuple[int, int, int, int] | None = None,
    ) -> np.ndarray:
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        # Wave 3C will draw digits via cv2.putText into the ROI rects;
        # this stub just allocates the frame buffer for collection.
        del att, def_, att_roi, def_roi  # populated by Wave 3C
        return frame

    return _make


@pytest.fixture
def arbiter_with_stub_sources() -> Callable[..., Any]:
    """Build an Arbiter wired to in-memory stub sources.

    Returns a builder Wave 3A populates once src/ingestion/arbiter.py exists.
    Wave 0 stub: returns SimpleNamespace with empty deques.
    """

    def _build(**kwargs: Any) -> SimpleNamespace:
        del kwargs
        return SimpleNamespace(
            score_changes=deque(maxlen=128),
            bomb_events=deque(maxlen=64),
            round_end_events=deque(maxlen=64),
        )

    return _build
