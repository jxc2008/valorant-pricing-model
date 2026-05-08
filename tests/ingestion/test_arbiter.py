"""REQ-cross-source-arbiter — DEC-006 v2 (3 deques) test suite (03-03).

Acceptance per SPEC §5: score_change needs >=2 sources within
ARBITER_SCORE_WINDOW_S, bomb_events soft-commit on 1 OCR source, round_end
soft-commit on 1 OCR source, quarantined events appear in JSONL with
seq_id=null + quarantined=true.
"""
from __future__ import annotations

import json
from pathlib import Path

from src.ingestion import Arbiter, PendingEvent, mono_ns, wall_time
from src.state.match_state import MatchState


def _make_state() -> MatchState:
    return MatchState(
        match_id="arbiter-test-001",
        team_a="A",
        team_b="B",
        map_pool=("Lotus", "Bind", "Haven"),
        map_side_orients=("a_atk", "a_def", "a_atk"),
        map_winners=(None, None, None),
        pistol_winner_a={0: None, 1: None, 2: None},
        map_idx=0,
        a_map_score=0,
        b_map_score=0,
        a_round=10,
        b_round=8,
        side_orient="atk",
        bomb_planted=False,
        attackers_alive=None,
        defenders_alive=None,
        time_left_s=None,
        seq_id=0,
        last_updated_ts=0.0,
    )


def test_score_change_two_source_rule(tmp_path: Path) -> None:
    """DEC-006 v2: score_change commits only when >=2 sources within window."""
    arb = Arbiter(
        _make_state(),
        event_log_dir=tmp_path / "event_log",
        metrics_log_dir=tmp_path / "metrics",
    )
    initial_seq = arb.state.seq_id
    t = wall_time()
    fields = {"a_round": 11}

    # Push 1st source — single source, no commit yet
    arb.score_changes.append(
        PendingEvent(
            source="ribgg",
            event_type="score_change",
            fields_proposed=fields,
            t_observed=t,
            t_ingested=mono_ns(),
        )
    )
    arb.tick()
    assert arb.state.seq_id == initial_seq  # no commit yet

    # Push 2nd source within ARBITER_SCORE_WINDOW_S — commits
    arb.score_changes.append(
        PendingEvent(
            source="ocr_score",
            event_type="score_change",
            fields_proposed=fields,
            t_observed=t + 0.5,
            t_ingested=mono_ns(),
        )
    )
    arb.tick()
    assert arb.state.seq_id == initial_seq + 1  # commit fired
    assert arb.state.a_round == 11

    # Verify JSONL line shape
    log_lines = (tmp_path / "event_log" / "arbiter-test-001.jsonl").read_text().strip().splitlines()
    assert len(log_lines) == 1
    line = json.loads(log_lines[0])
    assert line["seq_id"] == initial_seq + 1
    assert line["event_type"] == "score_change"
    assert line["fields_changed"] == {"a_round": 11}
    assert "ribgg" in line["source"] and "ocr_score" in line["source"]


def test_bomb_event_one_source_soft_commit(tmp_path: Path) -> None:
    """DEC-006 v2: bomb_plant soft-commits on a single OCR source."""
    arb = Arbiter(
        _make_state(),
        event_log_dir=tmp_path / "event_log",
        metrics_log_dir=tmp_path / "metrics",
    )
    initial_seq = arb.state.seq_id
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
    assert arb.state.seq_id == initial_seq + 1  # immediate soft-commit
    assert arb.state.bomb_planted is True
    assert arb.state.attackers_alive == 4
    assert arb.state.defenders_alive == 3
    assert arb.state.time_left_s == 45.0


def test_round_end_one_source_soft_commit(tmp_path: Path) -> None:
    """DEC-006 v2: round_end soft-commits on a single OCR source."""
    arb = Arbiter(
        _make_state(),
        event_log_dir=tmp_path / "event_log",
        metrics_log_dir=tmp_path / "metrics",
    )
    initial_seq = arb.state.seq_id
    fields = {"a_round": 13, "b_round": 11}
    arb.round_end_events.append(
        PendingEvent(
            source="ocr_round_end",
            event_type="round_end",
            fields_proposed=fields,
            t_observed=wall_time(),
            t_ingested=mono_ns(),
        )
    )
    arb.tick()
    assert arb.state.seq_id == initial_seq + 1
    assert arb.state.a_round == 13
    assert arb.state.b_round == 11


def test_quarantine_jsonl_format(tmp_path: Path) -> None:
    """D-03 quarantine line schema: seq_id=null, quarantined=true, fields_proposed populated."""
    arb = Arbiter(
        _make_state(),
        event_log_dir=tmp_path / "event_log",
        metrics_log_dir=tmp_path / "metrics",
    )
    initial_seq = arb.state.seq_id
    # Stale event — older than _DEQUE_MAX_AGE_S (3s)
    stale_t = wall_time() - 10.0
    fields = {"a_round": 11}
    arb.score_changes.append(
        PendingEvent(
            source="ribgg",
            event_type="score_change",
            fields_proposed=fields,
            t_observed=stale_t,
            t_ingested=mono_ns(),
        )
    )
    arb.tick()
    assert arb.state.seq_id == initial_seq  # NO commit (quarantined)

    log_lines = (tmp_path / "event_log" / "arbiter-test-001.jsonl").read_text().strip().splitlines()
    assert len(log_lines) == 1
    line = json.loads(log_lines[0])
    assert line["seq_id"] is None
    assert line["quarantined"] is True
    assert line["quarantine_reason"] == "stale_in_deque_no_cross_confirm"
    assert line["source"] == "ribgg"
    assert line["fields_proposed"] == {"a_round": 11}
