"""REQ-latency-instrumentation — SPEC §5/§6 acceptance: six-stage timestamps populated.

RED stub. Wave 3A (plan 03-03) populates this with an integration test that
drives a synthetic event through the arbiter and asserts every commit JSONL
line carries the five Phase-3-owned timestamps populated; t_quote_sent stays
null until Phase 4.
"""
from __future__ import annotations

import pytest


def test_six_stage_populated() -> None:
    pytest.xfail("Wave 3A — six-stage timestamp lineage instrumentation pending")
