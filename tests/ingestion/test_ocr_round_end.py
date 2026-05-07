"""REQ-ocr-pipeline — SPEC §3 acceptance: round-end banner OCR p50 budget + correctness.

RED stub. Wave 3C (plan 03-05) populates this with a benchmark loop at
OCR_ROUND_END_CADENCE_MS=100ms during the round-end window; asserts decode
latency budget and correctness against synthetic banner frames.
"""
from __future__ import annotations

import pytest


def test_decode_benchmark_p50() -> None:
    pytest.xfail("Wave 3C — src/ingestion/ocr.py round-end banner decoder pending")


def test_decode_correctness() -> None:
    pytest.xfail("Wave 3C — round-end banner correctness on synthetic frames pending")
