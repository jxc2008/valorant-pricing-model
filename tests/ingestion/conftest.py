"""Phase 3 ingestion test fixtures.

Used by every tests/ingestion/test_*.py file per VALIDATION.md.

Wave 1 (plan 03-01) update: ``make_match_state`` now returns a real
``MatchState`` dataclass instance (not a dict) — Wave 0 deferred the swap
because src/state/match_state.py didn't exist yet.

Wave 3A (plan 03-03) update: ``arbiter_with_stub_sources`` now returns a real
``Arbiter`` wired to per-test tmp event-log + metrics paths. Sources push
PendingEvents directly into ``arb.score_changes`` / ``arb.bomb_events`` /
``arb.round_end_events`` deques and call ``arb.tick()`` to drive confirmation.
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from src.ingestion import Arbiter
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

    Used by Wave 3C OCR benchmarks. Caller passes optional digit values + the
    ROI tuple they should be drawn inside; the factory renders the digit via
    cv2.putText (white on black, FONT_HERSHEY_SIMPLEX, scale 1.5, thickness 3
    — high contrast for tesseract).

    Wave 3C (plan 03-05) upgrade: now actually draws digits inside the ROI
    rectangles so OCR has something to parse. Each ROI tuple is (x1, y1, x2,
    y2); the digit is rendered with its baseline near the ROI's lower-left
    corner so the glyph fits within the rectangle.
    """
    import cv2

    def _make(
        att: int | None = None,
        def_: int | None = None,
        att_roi: tuple[int, int, int, int] | None = None,
        def_roi: tuple[int, int, int, int] | None = None,
        score_a: int | None = None,
        score_b: int | None = None,
        score_a_roi: tuple[int, int, int, int] | None = None,
        score_b_roi: tuple[int, int, int, int] | None = None,
    ) -> np.ndarray:
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        for digit, roi in (
            (att, att_roi),
            (def_, def_roi),
            (score_a, score_a_roi),
            (score_b, score_b_roi),
        ):
            if digit is not None and roi is not None:
                # Render at lower-left of ROI; white on black for high contrast.
                x = roi[0] + 5
                y = roi[3] - 5
                cv2.putText(
                    frame, str(digit), (x, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 3,
                )
        return frame

    return _make


@pytest.fixture
def arbiter_with_stub_sources(tmp_path: Path) -> Arbiter:
    """Real Arbiter wired to tmp event log + metrics — sources push directly into deques.

    Wave 3A (plan 03-03): replaces the Wave-0 SimpleNamespace stub. Tests
    push PendingEvents into ``arb.score_changes`` / ``arb.bomb_events`` /
    ``arb.round_end_events`` and call ``arb.tick()`` to drive confirmation.
    JSONL diff log lives at ``arb.jsonl_path`` (under tmp_path/event_log/);
    metrics line at ``arb.metrics_path`` (under tmp_path/metrics/).
    """
    initial = MatchState(
        match_id="conftest-arbiter-001",
        team_a="A",
        team_b="B",
        map_pool=("Lotus",),
        map_side_orients=("a_atk",),
        map_winners=(None,),
        pistol_winner_a={0: None},
        map_idx=0,
        a_map_score=0,
        b_map_score=0,
        a_round=0,
        b_round=0,
        side_orient="atk",
        bomb_planted=False,
        attackers_alive=None,
        defenders_alive=None,
        time_left_s=None,
        seq_id=0,
        last_updated_ts=0.0,
    )
    return Arbiter(
        initial,
        event_log_dir=tmp_path / "event_log",
        metrics_log_dir=tmp_path / "metrics",
    )
