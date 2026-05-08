"""Typed event shapes for the 3-deque arbiter (DEC-006 v2 / 03-CONTEXT D-04).

The 3 deques are exposed by src/ingestion/arbiter.py:
- score_changes: PendingEvent with event_type="score_change"
- bomb_events: PendingEvent with event_type in {"bomb_plant", "bomb_defuse", "post_plant_alive"}
- round_end_events: PendingEvent with event_type="round_end"

Cut from v1 schema (DEC-006 v2 / DEC-024 v2):
- kill_events deque (kill-feed CV is gone)
- numerical_flips deque (mid-round economy inference is gone)

Each ingestion source pushes PendingEvents; the arbiter materializes
ConfirmedEvent records (after rule check) and forwards to src.state.commit.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

EventType = Literal[
    "score_change",
    "bomb_plant",
    "bomb_defuse",
    "round_end",
    "post_plant_alive",
]

SourceName = Literal[
    "ribgg",
    "ocr_score",
    "ocr_bomb",
    "ocr_round_end",
    "ocr_post_plant_alive",
    "twitter",
]


@dataclass(frozen=True, slots=True)
class PendingEvent:
    """Source-emitted event awaiting arbiter confirmation."""

    source: SourceName
    event_type: EventType
    fields_proposed: dict[str, Any]
    t_observed: float  # wall_time() — broadcast wall-clock
    t_ingested: int    # mono_ns() — set by source at push time


@dataclass(frozen=True, slots=True)
class ConfirmedEvent:
    """Arbiter-confirmed event ready for src.state.commit."""

    event_type: EventType
    fields_changed: dict[str, Any]
    sources: tuple[SourceName, ...]
    timestamps: dict[str, float | int | None]
