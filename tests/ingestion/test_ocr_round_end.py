"""REQ-ocr-pipeline — round-end banner OCR tests (03-05). Placeholder XFAIL.

Round-end banner template detection ships as a placeholder gray-pixel-content
threshold in src/ingestion/ocr.py:_detect_round_end_banner; the real
template-match against an operator-supplied banner reference image lands in
Phase 3.5 calibration. Per Plan 03-05 Task 3, both tests xfail with explicit
TODO pointing at the missing fixture.

When fixtures/round_end_banner_template.png lands, swap _detect_round_end_banner
to cv2.matchTemplate and flip these xfails to hard assertions.
"""
from __future__ import annotations

import pytest


def test_decode_benchmark_p50():
    pytest.xfail(
        "Round-end banner template detection is placeholder — "
        "TODO(operator): supply fixtures/round_end_banner_template.png in "
        "Phase 3.5 calibration; revisit when template lands."
    )


def test_decode_correctness():
    pytest.xfail(
        "Round-end banner template detection is placeholder — "
        "TODO(operator): supply fixtures/round_end_banner_template.png in "
        "Phase 3.5 calibration."
    )
