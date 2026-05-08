"""REQ-match-state-engine — JSONL replay determinism + commit/quarantine schema.

Wave 1 (plan 03-01 Task 2): replay-from-disk tests asserting seq_id-ordered
replay reconstructs the live MatchState byte-for-byte; commit/quarantine line
schemas match D-03 (six timestamps + provenance for commit; null seq_id +
quarantine_reason for quarantine).

Reference: 03-CONTEXT.md D-03 / RESEARCH §"Code Examples".
"""
from __future__ import annotations

import json
import random
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from src.state import MatchState, commit, quarantine


def _make_timestamps() -> dict[str, float | int | None]:
    """Build a fresh six-stage timestamp dict shaped per D-03.

    The arbiter populates t_observed/t_ingested/t_arbited; commit() writes
    t_state_committed; t_theo_computed/t_quote_sent are filled by Phase 4.
    """
    now_ns = time.monotonic_ns()
    return {
        "t_observed": time.time(),
        "t_ingested": now_ns,
        "t_arbited": now_ns,
        "t_state_committed": None,
        "t_theo_computed": None,
        "t_quote_sent": None,
    }


def _random_diff(rng: random.Random) -> dict[str, Any]:
    """Generate a single random with_update payload over v2 dynamic fields.

    Mirrors the strategies in test_match_state.test_seq_id_strictly_monotonic
    but seeded for determinism across the replay test.
    """
    diff: dict[str, Any] = {}
    if rng.random() < 0.5:
        diff["a_round"] = rng.randint(0, 24)
    if rng.random() < 0.5:
        diff["b_round"] = rng.randint(0, 24)
    if rng.random() < 0.3:
        diff["a_map_score"] = rng.randint(0, 2)
    if rng.random() < 0.3:
        diff["b_map_score"] = rng.randint(0, 2)
    if rng.random() < 0.2:
        diff["bomb_planted"] = rng.choice([True, False])
    if rng.random() < 0.2:
        diff["attackers_alive"] = rng.choice([None, 1, 2, 3, 4, 5])
    if rng.random() < 0.2:
        diff["defenders_alive"] = rng.choice([None, 1, 2, 3, 4, 5])
    if rng.random() < 0.2:
        diff["time_left_s"] = rng.choice([None, 5.0, 12.5, 30.0, 44.9])
    return diff


def test_replay_determinism(
    make_match_state: Callable[..., MatchState],
    tmp_event_log_path: Path,
) -> None:
    """Write 1000 commits, replay JSONL line-by-line, assert final state matches.

    Per D-03 / SPEC §1 acceptance: a JSONL diff log must reconstruct the live
    state byte-for-byte when replayed in seq_id order. The replay path is the
    operator's debugging tool + the post-mortem latency analyzer.
    """
    rng = random.Random(42)
    state = make_match_state()
    initial = state

    # Generate the diffs deterministically up front so we can compare in-memory
    # vs replayed states without re-running the rng inside the assertion.
    diffs = [_random_diff(rng) for _ in range(1000)]

    in_memory_state = initial
    for diff in diffs:
        in_memory_state = commit(
            in_memory_state,
            diff,
            source="test",
            event_type="test_event",
            timestamps=_make_timestamps(),
            jsonl_path=tmp_event_log_path,
        )

    # Replay from disk: read JSONL, sort by seq_id, apply with_update in order.
    replay_state = initial
    lines: list[dict[str, Any]] = []
    with tmp_event_log_path.open("r", encoding="utf-8") as f:
        for raw in f:
            lines.append(json.loads(raw))

    # Filter quarantined lines (RESEARCH §"Common Pitfalls" — replay must not
    # apply seq_id is None entries). Sort by seq_id for determinism.
    commit_lines = sorted(
        (line for line in lines if line.get("seq_id") is not None),
        key=lambda line: line["seq_id"],
    )
    assert len(commit_lines) == 1000

    for line in commit_lines:
        replay_state = replay_state.with_update(**line["fields_changed"])

    # Final replayed state must match in-memory state on every dynamic field.
    # last_updated_ts is wall-clock and will differ across the in-memory vs
    # replay paths (replay's with_update calls happen later in real time);
    # exclude it from the comparison per D-02 (informational only).
    fields_to_compare = (
        "match_id",
        "team_a",
        "team_b",
        "map_pool",
        "map_side_orients",
        "map_winners",
        "pistol_winner_a",
        "map_idx",
        "a_map_score",
        "b_map_score",
        "a_round",
        "b_round",
        "side_orient",
        "bomb_planted",
        "attackers_alive",
        "defenders_alive",
        "time_left_s",
        "seq_id",
    )
    for name in fields_to_compare:
        assert getattr(replay_state, name) == getattr(in_memory_state, name), (
            f"replay diverged at field {name!r}"
        )


def test_commit_line_schema(
    make_match_state: Callable[..., MatchState],
    tmp_event_log_path: Path,
) -> None:
    """commit() writes a 10-key line per D-03 with correct types.

    The 9 keys plus fields_changed listed in D-03:
      seq_id (int), t_observed (float), t_ingested (int), t_arbited (int),
      t_state_committed (int), t_theo_computed (None), t_quote_sent (None),
      source (str), event_type (str), fields_changed (dict).
    """
    state = make_match_state()
    timestamps = _make_timestamps()
    new_state = commit(
        state,
        {"a_round": 1},
        source="test",
        event_type="round_end",
        timestamps=timestamps,
        jsonl_path=tmp_event_log_path,
    )
    assert new_state.a_round == 1
    assert new_state.seq_id == state.seq_id + 1

    line = json.loads(tmp_event_log_path.read_text(encoding="utf-8").strip())
    expected_keys = {
        "seq_id",
        "t_observed",
        "t_ingested",
        "t_arbited",
        "t_state_committed",
        "t_theo_computed",
        "t_quote_sent",
        "source",
        "event_type",
        "fields_changed",
    }
    assert set(line.keys()) == expected_keys

    assert isinstance(line["seq_id"], int)
    assert line["seq_id"] == new_state.seq_id
    assert isinstance(line["t_observed"], float)
    assert isinstance(line["t_ingested"], int)
    assert isinstance(line["t_arbited"], int)
    assert isinstance(line["t_state_committed"], int)
    assert line["t_theo_computed"] is None
    assert line["t_quote_sent"] is None
    assert line["source"] == "test"
    assert line["event_type"] == "round_end"
    assert line["fields_changed"] == {"a_round": 1}

    # commit() must record t_state_committed in the supplied timestamps dict
    # (RESEARCH §"Code Examples" — caller passes mutable dict).
    assert timestamps["t_state_committed"] == line["t_state_committed"]


def test_quarantine_line_schema(
    make_match_state: Callable[..., MatchState],
    tmp_event_log_path: Path,
) -> None:
    """quarantine() writes a 7-key line with seq_id=None and quarantined=True.

    State must be UNCHANGED (the helper returns None; caller does not swap
    references). Per D-03 + D-13.
    """
    state = make_match_state()
    t_observed = time.time()
    result = quarantine(
        state,
        {"attackers_alive": 99},  # invalid — would-be parse-fail proposal
        source="ocr_post_plant_alive",
        event_type="alive_widget",
        quarantine_reason="ocr_parse_fail",
        t_observed=t_observed,
        jsonl_path=tmp_event_log_path,
    )
    assert result is None  # Quarantine returns None; state unchanged at caller.

    line = json.loads(tmp_event_log_path.read_text(encoding="utf-8").strip())
    expected_keys = {
        "seq_id",
        "quarantined",
        "quarantine_reason",
        "t_observed",
        "source",
        "event_type",
        "fields_proposed",
    }
    assert set(line.keys()) == expected_keys

    assert line["seq_id"] is None
    assert line["quarantined"] is True
    assert line["quarantine_reason"] == "ocr_parse_fail"
    assert line["t_observed"] == t_observed
    assert line["source"] == "ocr_post_plant_alive"
    assert line["event_type"] == "alive_widget"
    assert line["fields_proposed"] == {"attackers_alive": 99}
