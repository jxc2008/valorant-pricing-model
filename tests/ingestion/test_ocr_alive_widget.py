"""REQ-ocr-pipeline — SPEC §3 acceptance: post-plant alive widget OCR p50 + parse-fail quarantine.

RED stub. Wave 3C (plan 03-05) populates this with a benchmark loop at
OCR_POST_PLANT_ALIVE_CADENCE_MS=250ms cadence and a parse-failure path that
emits quarantine lines per D-13 instead of mutating MatchState.
"""
from __future__ import annotations

import pytest


def test_decode_benchmark_p50() -> None:
    pytest.xfail("Wave 3C — src/ingestion/ocr.py post-plant alive widget decoder pending")


def test_parse_failure_quarantine() -> None:
    pytest.xfail("Wave 3C — D-13 parse-failure quarantine path pending")
