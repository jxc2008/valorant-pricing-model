"""REQ-text-listener — SPEC §4 acceptance: typed soft events + degrade-to-no-op + Twitter-only quarantine.

RED stub. Wave 3D (plan 03-06) populates this with mocked Twitter v2 stream
fixtures asserting (a) typed soft-event emission, (b) Twitter-only updates
flagged for arbiter quarantine, (c) listener no-ops cleanly when
TWITTER_BEARER_TOKEN is absent.
"""
from __future__ import annotations

import pytest


def test_emits_typed_soft_events() -> None:
    pytest.xfail("Wave 3D — src/ingestion/text_listener.py async stream pending")


def test_twitter_only_update_quarantined() -> None:
    pytest.xfail("Wave 3D — Twitter-only soft-event quarantine policy pending")


def test_no_token_noop() -> None:
    pytest.xfail("Wave 3D — bearer-token absence degrade-to-no-op pending")
