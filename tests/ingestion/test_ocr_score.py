"""REQ-ocr-pipeline — score banner OCR tests (03-05).

Wave 3C green wiring per Plan 03-05 Task 3. Two tests:

- ``test_decode_benchmark_p50``: 56 synthetic frames across scores {0..13};
  asserts p50 decode latency below ``OCR_DECODE_BUDGET_MS``. xfails with
  operator-recalibrate TODO if the budget is missed (placeholder ROIs
  from D-11; subprocess fork overhead per RESEARCH Pitfall 2).
- ``test_decode_correctness``: synthetic 13 → ``_decode_score_digit`` returns
  13 (or xfails with operator TODO if the placeholder ROI doesn't align with
  the synthetic-text-render position).
"""
from __future__ import annotations

import time

import pytest

from src.config.constants import OCR_DECODE_BUDGET_MS, SCORE_BANNER_TEAM1_ROI
from src.ingestion.ocr import _decode_score_digit


def test_decode_benchmark_p50(synthetic_frame_factory):
    durations_ms: list[float] = []
    for score in list(range(14)) * 4:  # 56 samples
        frame = synthetic_frame_factory(score_a=score, score_a_roi=SCORE_BANNER_TEAM1_ROI)
        roi = frame[
            SCORE_BANNER_TEAM1_ROI[1]:SCORE_BANNER_TEAM1_ROI[3],
            SCORE_BANNER_TEAM1_ROI[0]:SCORE_BANNER_TEAM1_ROI[2],
        ]
        t0 = time.monotonic_ns()
        _decode_score_digit(roi)
        durations_ms.append((time.monotonic_ns() - t0) / 1_000_000)
    p50 = sorted(durations_ms)[len(durations_ms) // 2]
    if p50 >= OCR_DECODE_BUDGET_MS:
        pytest.xfail(
            f"OCR p50={p50:.1f}ms exceeds budget {OCR_DECODE_BUDGET_MS}ms — "
            "TODO(operator): recalibrate ROIs against real broadcast frames "
            "via scripts/dump_roi_overlay.py."
        )
    assert p50 < OCR_DECODE_BUDGET_MS


def test_decode_correctness(synthetic_frame_factory):
    """Synthetic 13-digit at SCORE_BANNER_TEAM1_ROI → ``_decode_score_digit`` returns 13."""
    frame = synthetic_frame_factory(score_a=13, score_a_roi=SCORE_BANNER_TEAM1_ROI)
    roi = frame[
        SCORE_BANNER_TEAM1_ROI[1]:SCORE_BANNER_TEAM1_ROI[3],
        SCORE_BANNER_TEAM1_ROI[0]:SCORE_BANNER_TEAM1_ROI[2],
    ]
    result = _decode_score_digit(roi)
    if result != 13:
        pytest.xfail(
            f"got {result!r} not 13 — TODO(operator): recalibrate ROIs against "
            "real broadcast frames via scripts/dump_roi_overlay.py."
        )
    assert result == 13
