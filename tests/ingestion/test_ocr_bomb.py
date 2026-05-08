"""REQ-ocr-pipeline — bomb-plant icon OCR tests (03-05).

Wave 3C green wiring per Plan 03-05 Task 3. Two tests, both GREEN-by-default
(color-threshold heuristic is fast + deterministic; doesn't depend on ROI
calibration in the same way the digit-OCR helpers do):

- ``test_decode_benchmark_p50``: 50 invocations of ``_detect_bomb_plant_icon``
  on a red-filled ROI; asserts p50 < ``OCR_DECODE_BUDGET_MS``.
- ``test_decode_correctness``: red-filled ROI → True; black ROI → False.
"""
from __future__ import annotations

import time

import cv2
import numpy as np

from src.config.constants import BOMB_PLANT_ICON_ROI, OCR_DECODE_BUDGET_MS
from src.ingestion.ocr import _detect_bomb_plant_icon


def test_decode_benchmark_p50():
    """50-invocation ``_detect_bomb_plant_icon`` p50 < OCR_DECODE_BUDGET_MS.

    Color-threshold heuristic is fast (<1ms typical) — should pass even
    against the placeholder ROI because the heuristic is shape-agnostic
    (counts red pixels regardless of where they land within the slice).
    """
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    cv2.rectangle(
        frame,
        (BOMB_PLANT_ICON_ROI[0], BOMB_PLANT_ICON_ROI[1]),
        (BOMB_PLANT_ICON_ROI[2], BOMB_PLANT_ICON_ROI[3]),
        (0, 0, 255),  # BGR red
        -1,
    )
    roi = frame[
        BOMB_PLANT_ICON_ROI[1]:BOMB_PLANT_ICON_ROI[3],
        BOMB_PLANT_ICON_ROI[0]:BOMB_PLANT_ICON_ROI[2],
    ]
    durations_ms: list[float] = []
    for _ in range(50):
        t0 = time.monotonic_ns()
        _detect_bomb_plant_icon(roi)
        durations_ms.append((time.monotonic_ns() - t0) / 1_000_000)
    p50 = sorted(durations_ms)[len(durations_ms) // 2]
    assert p50 < OCR_DECODE_BUDGET_MS


def test_decode_correctness():
    """Red ROI → True; black ROI → False (placeholder color-threshold heuristic)."""
    # True case — red-filled ROI region.
    red_frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    cv2.rectangle(
        red_frame,
        (BOMB_PLANT_ICON_ROI[0], BOMB_PLANT_ICON_ROI[1]),
        (BOMB_PLANT_ICON_ROI[2], BOMB_PLANT_ICON_ROI[3]),
        (0, 0, 255),
        -1,
    )
    red_roi = red_frame[
        BOMB_PLANT_ICON_ROI[1]:BOMB_PLANT_ICON_ROI[3],
        BOMB_PLANT_ICON_ROI[0]:BOMB_PLANT_ICON_ROI[2],
    ]
    assert _detect_bomb_plant_icon(red_roi) is True

    # False case — black ROI.
    black_roi = np.zeros(
        (
            BOMB_PLANT_ICON_ROI[3] - BOMB_PLANT_ICON_ROI[1],
            BOMB_PLANT_ICON_ROI[2] - BOMB_PLANT_ICON_ROI[0],
            3,
        ),
        dtype=np.uint8,
    )
    assert _detect_bomb_plant_icon(black_roi) is False
