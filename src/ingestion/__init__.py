"""Live ingestion layer — sources + arbiter + JSONL event log (Phase 3)."""

from src.ingestion.arbiter import Arbiter
from src.ingestion.events import (
    ConfirmedEvent,
    EventType,
    PendingEvent,
    SourceName,
)
from src.ingestion.frame_source import FrameSource, StubFrameSource, YouTubeFrameSource
from src.ingestion.ocr import (
    run_bomb_icon_worker,
    run_post_plant_alive_worker,
    run_round_end_worker,
    run_score_banner_worker,
)
from src.ingestion.scoreboard import run_scoreboard_poller
from src.ingestion.timestamps import TimestampRecord, mono_ns, wall_time

__all__ = [
    "Arbiter",
    "ConfirmedEvent",
    "EventType",
    "FrameSource",
    "PendingEvent",
    "SourceName",
    "StubFrameSource",
    "TimestampRecord",
    "YouTubeFrameSource",
    "mono_ns",
    "run_bomb_icon_worker",
    "run_post_plant_alive_worker",
    "run_round_end_worker",
    "run_score_banner_worker",
    "run_scoreboard_poller",
    "wall_time",
]
