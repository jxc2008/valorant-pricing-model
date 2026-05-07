"""REQ-ocr-pipeline — SPEC §3 acceptance: score banner OCR p50 budget + correctness.

RED stub. Wave 3C (plan 03-05) populates this with a benchmark loop over the
synthetic frame factory at OCR_SCORE_BANNER_CADENCE_MS=250ms cadence; asserts
p50 decode latency under the budget and correctness on synthetic frames.
"""
from __future__ import annotations

import pytest


def test_decode_benchmark_p50() -> None:
    pytest.xfail("Wave 3C — src/ingestion/ocr.py score banner decoder pending")


def test_decode_correctness() -> None:
    pytest.xfail("Wave 3C — score banner correctness on synthetic frames pending")
