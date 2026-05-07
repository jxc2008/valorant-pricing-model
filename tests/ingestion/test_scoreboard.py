"""REQ-scoreboard-polling — SPEC §2 acceptance: typed events + Retry-After-aware retry.

RED stub. Wave 3B (plan 03-04) populates this with aioresponses-backed tests
that drive a fake rib.gg endpoint through the async poller and assert typed
event emission + tenacity retry honoring HTTP 429 Retry-After.
"""
from __future__ import annotations

import pytest


def test_poller_emits_typed_events() -> None:
    pytest.xfail("Wave 3B — src/ingestion/scoreboard.py async poller pending")


def test_retry_honors_retry_after() -> None:
    pytest.xfail("Wave 3B — Retry-After-aware tenacity wrapper pending")
