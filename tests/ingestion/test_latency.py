"""REQ-latency-instrumentation — six-stage timestamp lineage test (03-03 / D-03).

Acceptance per SPEC §6: every confirmed event JSONL line + metrics line carries
all six timestamps with monotonic ordering of the three Phase-3-owned stages
(t_ingested -> t_arbited -> t_state_committed). Phase 4 fills t_theo_computed
and t_quote_sent on a parallel update.
"""
from __future__ import annotations

import json
import time

from src.ingestion import Arbiter, PendingEvent, mono_ns, wall_time

SIX_KEYS = (
    "t_observed",
    "t_ingested",
    "t_arbited",
    "t_state_committed",
    "t_theo_computed",
    "t_quote_sent",
)


def test_six_stage_populated(arbiter_with_stub_sources: Arbiter) -> None:
    """Every confirmed event JSONL line + metrics line carries all 6 timestamps."""
    arb = arbiter_with_stub_sources
    test_start_wall = time.time()

    # Push a bomb_event — single OCR source soft-commit
    fields = {
        "bomb_planted": True,
        "attackers_alive": 4,
        "defenders_alive": 3,
        "time_left_s": 45.0,
    }
    arb.bomb_events.append(
        PendingEvent(
            source="ocr_bomb",
            event_type="bomb_plant",
            fields_proposed=fields,
            t_observed=wall_time(),
            t_ingested=mono_ns(),
        )
    )
    arb.tick()

    # Read metrics line
    metrics_lines = arb.metrics_path.read_text().strip().splitlines()
    assert len(metrics_lines) == 1
    metrics = json.loads(metrics_lines[0])
    for k in SIX_KEYS:
        assert k in metrics, f"metrics line missing {k}"
    assert isinstance(metrics["t_observed"], float)
    # Sanity: within minute of test start (wall-clock alignment)
    assert abs(metrics["t_observed"] - test_start_wall) < 60.0
    assert isinstance(metrics["t_ingested"], int)
    assert isinstance(metrics["t_arbited"], int)
    assert isinstance(metrics["t_state_committed"], int)
    # Monotonic ordering of the 3 in-Phase-3 stages
    assert metrics["t_arbited"] >= metrics["t_ingested"]
    assert metrics["t_state_committed"] >= metrics["t_arbited"]
    # Phase 3 reservations
    assert metrics["t_theo_computed"] is None
    assert metrics["t_quote_sent"] is None

    # JSONL diff log mirrors the same 6 timestamps
    jsonl_lines = arb.jsonl_path.read_text().strip().splitlines()
    assert len(jsonl_lines) == 1
    jsonl = json.loads(jsonl_lines[0])
    for k in SIX_KEYS:
        assert k in jsonl, f"JSONL line missing {k}"
    # Same commit-time anchor across both files (commit() mutates timestamps in place,
    # _write_metrics_line reads after commit() returns)
    assert jsonl["t_state_committed"] == metrics["t_state_committed"]
