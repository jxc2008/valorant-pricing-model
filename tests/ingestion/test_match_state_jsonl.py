"""REQ-match-state-engine — SPEC §1 acceptance: JSONL replay determinism + commit/quarantine line schema.

RED stub. Wave 1 (plan 03-01) populates this with replay-from-disk tests
asserting seq_id-ordered replay reconstructs the live MatchState byte-for-byte
and that commit/quarantine line schemas match D-03 (six timestamps + provenance).
"""
from __future__ import annotations

import pytest


def test_replay_determinism() -> None:
    pytest.xfail("Wave 1 — JSONL append + replay loop implementation pending")


def test_commit_line_schema() -> None:
    pytest.xfail("Wave 1 — D-03 commit-line schema validator pending")


def test_quarantine_line_schema() -> None:
    pytest.xfail("Wave 1 — D-03 quarantine-line schema validator pending")
