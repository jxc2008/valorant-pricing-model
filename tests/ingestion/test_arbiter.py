"""REQ-cross-source-arbiter — SPEC §5 acceptance: 3-deque rules + quarantine JSONL.

RED stub. Wave 3A (plan 03-03) populates this with hypothesis property tests
per DEC-006 v2: score_changes need >=2 sources within ARBITER_SCORE_WINDOW_S,
bomb_events soft-commit on 1 OCR source, round_end_events soft-commit then
hard-confirm on next score, and quarantine lines match D-03 schema.
"""
from __future__ import annotations

import pytest


def test_score_change_two_source_rule() -> None:
    pytest.xfail("Wave 3A — src/ingestion/arbiter.py 3-deque tick pending")


def test_bomb_event_one_source_soft_commit() -> None:
    pytest.xfail("Wave 3A — bomb_events soft-commit semantics pending")


def test_round_end_one_source_soft_commit() -> None:
    pytest.xfail("Wave 3A — round_end_events soft-commit + hard-confirm-next-score pending")


def test_quarantine_jsonl_format() -> None:
    pytest.xfail("Wave 3A — D-03 quarantine line emission pending")
