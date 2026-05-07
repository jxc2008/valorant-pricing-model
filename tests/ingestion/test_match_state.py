"""REQ-match-state-engine — SPEC §1 acceptance: seq_id strict monotonicity + with_update field semantics.

RED stub. Wave 1 (plan 03-01) swaps these xfails for hypothesis property tests
per RESEARCH §"Code Examples" (seq_id strictly increases by 1; with_update
returns a new frozen MatchState with only the requested fields changed).
"""
from __future__ import annotations

import pytest


def test_seq_id_strictly_monotonic() -> None:
    pytest.xfail("Wave 1 — src/state/match_state.py + with_update implementation pending")


def test_with_update_field_semantics() -> None:
    pytest.xfail("Wave 1 — src/state/match_state.py + with_update implementation pending")
