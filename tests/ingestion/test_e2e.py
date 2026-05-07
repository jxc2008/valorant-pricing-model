"""REQ-end-to-end-latency — SPEC §6 acceptance: synthetic E2E latency p50 + post-plant non-degeneracy.

RED stub. Wave 4 (plan 03-08) populates this with the synthetic E2E gate that
drives fake rib.gg + fake OCR + fake Twitter through arbiter -> MatchState ->
live_theo, asserts seq_id monotonicity, p50 event-to-state-commit < 500ms,
bomb-detect-to-commit p50 < 100ms, and post-plant cells shift theo off the
side baseline by >= 1c.
"""
from __future__ import annotations

import pytest


def test_e2e_latency_p50() -> None:
    pytest.xfail("Wave 4 — synthetic E2E harness pending")


def test_bomb_detect_p50() -> None:
    pytest.xfail("Wave 4 — bomb-detect latency budget assertion pending")


def test_post_plant_non_degenerate() -> None:
    pytest.xfail("Wave 4 — post-plant theo non-degeneracy assertion pending")
