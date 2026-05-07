"""REQ-ocr-pipeline — SPEC §3 acceptance: bomb-icon OCR p50 budget + correctness.

RED stub. Wave 3C (plan 03-05) populates this with a benchmark loop at
OCR_BOMB_ICON_CADENCE_MS=500ms cadence; asserts the bomb-detect path lands
within the 100ms median budget that gates the post-plant lookup activation.
"""
from __future__ import annotations

import pytest


def test_decode_benchmark_p50() -> None:
    pytest.xfail("Wave 3C — src/ingestion/ocr.py bomb icon decoder pending")


def test_decode_correctness() -> None:
    pytest.xfail("Wave 3C — bomb icon correctness on synthetic frames pending")
