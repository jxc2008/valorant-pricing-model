"""Tesseract OCR pipeline — 4 async workers for the 3 primary HUD targets +
post-plant alive widget (REQ-ocr-pipeline / DEC-024 v2 / D-11/D-12/D-13/D-14).

Workers
-------
- ``run_score_banner_worker`` (250ms cadence) — score banner OCR; pushes
  PendingEvent(source="ocr_score") into ``arbiter.score_changes``.
- ``run_bomb_icon_worker`` (500ms cadence) — bomb-plant icon detection;
  pushes PendingEvent(source="ocr_bomb", event_type="bomb_plant"|"bomb_defuse")
  on transitions into ``arbiter.bomb_events``.
- ``run_round_end_worker`` (100ms cadence) — round-end banner detection;
  pushes PendingEvent(source="ocr_round_end") into ``arbiter.round_end_events``.
- ``run_post_plant_alive_worker`` (250ms cadence; D-12 hard-gated on
  ``arbiter.state.bomb_planted=True``) — single-digit alive counts for
  attackers + defenders; pushes PendingEvent(source="ocr_post_plant_alive")
  into ``arbiter.bomb_events``.

Concurrency
-----------
Each worker dispatches the actual ``pytesseract.image_to_string`` call to a
shared ``_OCR_EXECUTOR = ThreadPoolExecutor(max_workers=2)`` via
``loop.run_in_executor`` per RESEARCH §"Pattern 4". pytesseract calls
``subprocess.Popen`` for the ``tesseract`` binary, which releases the GIL
effectively; max_workers > 2 just hits subprocess fork pressure.

DEC-024 v2 cuts (grep-verifiable absence in this file)
------------------------------------------------------
DO NOT add killfeed parsing, ult tracking, mid-round economy inference, ONNX
runtime, PaddleOCR, or CTC decoders. These are project-level cuts per
DEC-024 v2; the post-plant alive widget IS the v2 replacement signal for the
cut killfeed (per CLAUDE.md "Domain constants" / 03-CONTEXT.md §"specifics").
A repo-wide grep guard verifies absence of the canonical forbidden tokens in
this file; see Plan 03-05 Task 2 / Task 3 verify steps for the exact command.

D-13 quarantine path
--------------------
Tesseract returning text not in the whitelist (``{"0".."5"}`` for alive widget
or non-digit strings for the score banner) → decode helper returns ``None``;
the worker logs a warning and yields the cycle without pushing an event. State
carries forward via ``MatchState.with_update`` only-changed-fields semantics
(Phase 2 D-08), and the arbiter's existing 5s staleness kill-switch
(KILL_SWITCH_STALENESS_S) handles extended degradation.

Time discipline (RESEARCH Pitfall 3)
------------------------------------
- ``t_observed`` uses ``wall_time()`` (``time.time()``) — set BEFORE the OCR
  work so latency analysis attributes the event to the broadcast wall-clock.
- ``t_ingested`` uses ``mono_ns()`` (``time.monotonic_ns()``) — set AFTER the
  executor returns for latency math against ``t_arbited`` /
  ``t_state_committed``.
"""
from __future__ import annotations

import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

import cv2
import numpy as np
import pytesseract
from numpy.typing import NDArray
from PIL import Image

from src.config.constants import (
    BOMB_PLANT_ICON_ROI,
    OCR_BOMB_ICON_CADENCE_MS,
    OCR_POST_PLANT_ALIVE_CADENCE_MS,
    OCR_ROUND_END_CADENCE_MS,
    OCR_SCORE_BANNER_CADENCE_MS,
    POST_PLANT_ATTACKERS_ROI,
    POST_PLANT_DEFENDERS_ROI,
    ROUND_END_BANNER_ROI,
    SCORE_BANNER_TEAM1_ROI,
    SCORE_BANNER_TEAM2_ROI,
    TESS_CONFIG_DIGIT_MULTI,
    TESS_CONFIG_DIGIT_SINGLE,
)
from src.ingestion.events import EventType, PendingEvent
from src.ingestion.timestamps import mono_ns, wall_time

if TYPE_CHECKING:
    from src.ingestion.arbiter import Arbiter
    from src.ingestion.frame_source import FrameSource

logger = logging.getLogger(__name__)


# Module-init: configure pytesseract.tesseract_cmd from env (Windows host).
# CI / Linux hosts rely on PATH resolution; Windows dev sets TESSERACT_CMD in
# .env to point at C:\Program Files\Tesseract-OCR\tesseract.exe.
_TESS_CMD = os.environ.get("TESSERACT_CMD")
if _TESS_CMD:
    pytesseract.pytesseract.tesseract_cmd = _TESS_CMD


_OCR_EXECUTOR: ThreadPoolExecutor = ThreadPoolExecutor(
    max_workers=2,
    thread_name_prefix="ocr",
)
"""Shared executor for all 4 OCR workers (RESEARCH §"Pattern 4").

max_workers=2 — beyond 2 the pytesseract subprocess.Popen fork pressure
dominates throughput. Module-level singleton; never recreated. Workers
dispatch via ``loop.run_in_executor(_OCR_EXECUTOR, _decode_*, roi)``."""


# ---------------------------------------------------------------------------- #
# Sync decode helpers — run inside _OCR_EXECUTOR. Each takes a BGR uint8 ROI   #
# array and returns the parsed value or None on parse failure (D-13).          #
# ---------------------------------------------------------------------------- #


def _preprocess_digit_roi(roi_bgr: NDArray[np.uint8]) -> Image.Image:
    """grayscale → Otsu threshold → 2x upscale → PIL.Image (D-13 pipeline).

    The 2x upscale targets ~300 DPI equivalent at small ROI sizes per
    03-CONTEXT.md D-13; tesseract is calibrated for 300 DPI input.
    """
    gray = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    upscaled = cv2.resize(thresh, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
    return Image.fromarray(upscaled)


def _decode_alive_digit(roi_bgr: NDArray[np.uint8]) -> int | None:
    """Single-digit alive count — returns int in {0,1,2,3,4,5} or None on parse fail.

    D-13: anything outside the {0..5} whitelist is treated as a parse failure;
    caller emits a quarantine sentinel or carries state forward.
    """
    img = _preprocess_digit_roi(roi_bgr)
    text = pytesseract.image_to_string(img, config=TESS_CONFIG_DIGIT_SINGLE).strip()
    if text in {"0", "1", "2", "3", "4", "5"}:
        return int(text)
    return None


def _decode_score_digit(roi_bgr: NDArray[np.uint8]) -> int | None:
    """Multi-digit score (0-13) — returns int in [0,13] or None on parse fail.

    13 is the regulation-half win threshold (WIN_THRESHOLD); above-13 values
    are out-of-range and treated as parse failures (D-13)."""
    img = _preprocess_digit_roi(roi_bgr)
    text = pytesseract.image_to_string(img, config=TESS_CONFIG_DIGIT_MULTI).strip()
    if text.isdigit() and 0 <= int(text) <= 13:
        return int(text)
    return None


def _detect_bomb_plant_icon(roi_bgr: NDArray[np.uint8]) -> bool:
    """Detect spike icon presence — returns True if found, False otherwise.

    Phase 3 placeholder: HSV red-pixel mask with > 50 px count threshold.
    The spike icon is a distinctive red/orange shape on the HUD.

    TODO(03-future): replace with cv2.matchTemplate against
    fixtures/spike_icon_template.png pinned by operator. Template-match would
    cut the false-positive rate for "any red overlay" (e.g., killfeed
    flashes), but the current arbiter rule (single-source soft-commit + Phase
    4 mode-selector cross-check) tolerates the placeholder fidelity.
    """
    hsv = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2HSV)
    red_mask = cv2.inRange(hsv, np.array([0, 100, 100]), np.array([10, 255, 255]))
    return bool(cv2.countNonZero(red_mask) > 50)


def _detect_round_end_banner(roi_bgr: NDArray[np.uint8]) -> bool:
    """Detect round-end banner presence.

    Phase 3 placeholder — operator supplies fixtures/round_end_banner_template.png
    in Phase 3.5 calibration; for now we return False unless the ROI has
    significant non-zero content (rough proxy for "banner is rendered").

    TODO(03-future): replace with cv2.matchTemplate against the operator-supplied
    banner reference.
    """
    gray = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2GRAY)
    return bool(cv2.countNonZero(gray) > 5000)


# ---------------------------------------------------------------------------- #
# Async workers — each is an infinite cadence loop. Pushed into Arbiter deques #
# per RESEARCH §"Pattern 4" / 03-04 SUMMARY scoreboard poller pattern.         #
# ---------------------------------------------------------------------------- #


def _slice_roi(
    frame: NDArray[np.uint8],
    roi: tuple[int, int, int, int],
) -> NDArray[np.uint8]:
    """Slice (x1, y1, x2, y2) ROI from a BGR frame; returns a view.

    Note: the slice is a numpy view, NOT a copy; safe to pass into the
    executor because we don't mutate it inside the decode helpers.
    """
    x1, y1, x2, y2 = roi
    return frame[y1:y2, x1:x2]


async def run_score_banner_worker(
    arbiter: Arbiter,
    frame_source: FrameSource,
    *,
    cadence_s: float = OCR_SCORE_BANNER_CADENCE_MS / 1000.0,
) -> None:
    """Score banner OCR worker (250ms cadence).

    Reads both team-score ROIs in parallel via asyncio.gather of
    run_in_executor. Pushes PendingEvent(source="ocr_score",
    event_type="score_change", fields_proposed={"a_round": ..., "b_round": ...})
    into ``arbiter.score_changes`` when EITHER team's score differs from
    ``arbiter.state``. The arbiter's ≥ 2-source rule cross-confirms against
    rib.gg before committing (DEC-006 v2).

    fields_proposed contains BOTH team scores even when only one changed —
    matches the rib.gg poller's emission shape (03-04 SUMMARY) so the
    arbiter's signature-grouping over fields_proposed.items() trips the
    cross-confirm.
    """
    loop = asyncio.get_running_loop()
    while True:
        try:
            t_observed = wall_time()
            frame = await frame_source.latest_frame()
            team1_roi = _slice_roi(frame, SCORE_BANNER_TEAM1_ROI)
            team2_roi = _slice_roi(frame, SCORE_BANNER_TEAM2_ROI)
            team1_task = loop.run_in_executor(_OCR_EXECUTOR, _decode_score_digit, team1_roi)
            team2_task = loop.run_in_executor(_OCR_EXECUTOR, _decode_score_digit, team2_roi)
            team1, team2 = await asyncio.gather(team1_task, team2_task)
            t_ingested = mono_ns()
            if team1 is None or team2 is None:
                # D-13: parse fail on either side → carry forward, don't push.
                logger.warning(
                    "OCR score banner parse fail (a_round=%r, b_round=%r) — carry-forward",
                    team1, team2,
                )
                await asyncio.sleep(cadence_s)
                continue
            prev = arbiter.state
            if team1 == prev.a_round and team2 == prev.b_round:
                await asyncio.sleep(cadence_s)
                continue
            arbiter.score_changes.append(
                PendingEvent(
                    source="ocr_score",
                    event_type="score_change",
                    fields_proposed={"a_round": team1, "b_round": team2},
                    t_observed=t_observed,
                    t_ingested=t_ingested,
                )
            )
            await asyncio.sleep(cadence_s)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 — top-level resilience boundary
            logger.warning(
                "score_banner_worker cycle failure: %s: %s",
                type(exc).__name__,
                exc,
            )
            await asyncio.sleep(cadence_s)


async def run_bomb_icon_worker(
    arbiter: Arbiter,
    frame_source: FrameSource,
    *,
    cadence_s: float = OCR_BOMB_ICON_CADENCE_MS / 1000.0,
) -> None:
    """Bomb-plant icon detection worker (500ms cadence).

    Detects the spike icon presence in BOMB_PLANT_ICON_ROI; emits
    PendingEvent(source="ocr_bomb", event_type="bomb_plant"|"bomb_defuse")
    ONLY on transition (False→True = bomb_plant; True→False = bomb_defuse).
    Steady-state True / False both yield without pushing — the arbiter only
    needs the edge for the soft-commit.

    The local ``last_bomb_state`` mirror tracks the worker's view of the
    bomb-planted state; we trust the icon detection's own continuity rather
    than reading ``arbiter.state.bomb_planted`` so a stale Phase-4 mode-flip
    can't induce phantom transitions.
    """
    loop = asyncio.get_running_loop()
    last_bomb_state: bool = arbiter.state.bomb_planted
    while True:
        try:
            t_observed = wall_time()
            frame = await frame_source.latest_frame()
            icon_roi = _slice_roi(frame, BOMB_PLANT_ICON_ROI)
            detected = await loop.run_in_executor(
                _OCR_EXECUTOR, _detect_bomb_plant_icon, icon_roi,
            )
            t_ingested = mono_ns()
            if detected != last_bomb_state:
                # Literal narrowing: explicit branch keeps EventType static.
                event_type: EventType = "bomb_plant" if detected else "bomb_defuse"
                arbiter.bomb_events.append(
                    PendingEvent(
                        source="ocr_bomb",
                        event_type=event_type,
                        fields_proposed={"bomb_planted": detected},
                        t_observed=t_observed,
                        t_ingested=t_ingested,
                    )
                )
                last_bomb_state = detected
            await asyncio.sleep(cadence_s)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 — top-level resilience boundary
            logger.warning(
                "bomb_icon_worker cycle failure: %s: %s",
                type(exc).__name__,
                exc,
            )
            await asyncio.sleep(cadence_s)


async def run_round_end_worker(
    arbiter: Arbiter,
    frame_source: FrameSource,
    *,
    cadence_s: float = OCR_ROUND_END_CADENCE_MS / 1000.0,
) -> None:
    """Round-end banner OCR worker (100ms cadence).

    Phase 3 placeholder: detects banner presence via gray-pixel content
    threshold; on detection (and only on detection-edge), pushes
    PendingEvent(source="ocr_round_end", event_type="round_end") into
    ``arbiter.round_end_events``. The arbiter soft-commits the round_end
    immediately; the next score commit hard-confirms (D-CONTEXT D-03).

    TODO(03-future): swap _detect_round_end_banner to cv2.matchTemplate
    against operator-supplied banner reference once that's pinned.
    """
    loop = asyncio.get_running_loop()
    last_banner_state: bool = False
    while True:
        try:
            t_observed = wall_time()
            frame = await frame_source.latest_frame()
            banner_roi = _slice_roi(frame, ROUND_END_BANNER_ROI)
            detected = await loop.run_in_executor(
                _OCR_EXECUTOR, _detect_round_end_banner, banner_roi,
            )
            t_ingested = mono_ns()
            if detected and not last_banner_state:
                arbiter.round_end_events.append(
                    PendingEvent(
                        source="ocr_round_end",
                        event_type="round_end",
                        fields_proposed={"round_end_observed": True},
                        t_observed=t_observed,
                        t_ingested=t_ingested,
                    )
                )
            last_banner_state = detected
            await asyncio.sleep(cadence_s)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 — top-level resilience boundary
            logger.warning(
                "round_end_worker cycle failure: %s: %s",
                type(exc).__name__,
                exc,
            )
            await asyncio.sleep(cadence_s)


async def run_post_plant_alive_worker(
    arbiter: Arbiter,
    frame_source: FrameSource,
    *,
    cadence_s: float = OCR_POST_PLANT_ALIVE_CADENCE_MS / 1000.0,
) -> None:
    """Post-plant attackers/defenders-alive widget worker (250ms cadence).

    D-12 hard-gated: yields immediately when ``arbiter.state.bomb_planted=False``.
    When True, reads both alive ROIs in parallel via asyncio.gather of
    run_in_executor; pushes PendingEvent(source="ocr_post_plant_alive",
    event_type="post_plant_alive", fields_proposed={"attackers_alive": ...,
    "defenders_alive": ...}) into ``arbiter.bomb_events`` only when EITHER
    count differs from ``arbiter.state``.

    D-13: parse failure on either side → log warning + carry forward (no
    push; state's prior valid values stay). The arbiter's existing 5s
    staleness kill-switch handles extended degradation; conflating layers
    with a per-frame quarantine event would race against the soft-commit
    contract (CONTEXT D-13 last paragraph).

    Post-plant alive is THE replacement signal for the cut kill feed —
    every v2 mid-round dynamic flows through these updates per
    03-CONTEXT.md §specifics.
    """
    loop = asyncio.get_running_loop()
    while True:
        try:
            # D-12 gate — yield without doing OCR work when no plant active.
            if not arbiter.state.bomb_planted:
                await asyncio.sleep(cadence_s)
                continue
            t_observed = wall_time()
            frame = await frame_source.latest_frame()
            att_roi = _slice_roi(frame, POST_PLANT_ATTACKERS_ROI)
            def_roi = _slice_roi(frame, POST_PLANT_DEFENDERS_ROI)
            att_task = loop.run_in_executor(_OCR_EXECUTOR, _decode_alive_digit, att_roi)
            def_task = loop.run_in_executor(_OCR_EXECUTOR, _decode_alive_digit, def_roi)
            att, def_ = await asyncio.gather(att_task, def_task)
            t_ingested = mono_ns()
            if att is None or def_ is None:
                # D-13 carry-forward path.
                logger.warning(
                    "OCR alive widget parse fail (att=%r, def_=%r) — carry-forward",
                    att, def_,
                )
                await asyncio.sleep(cadence_s)
                continue
            prev = arbiter.state
            if att == prev.attackers_alive and def_ == prev.defenders_alive:
                await asyncio.sleep(cadence_s)
                continue
            arbiter.bomb_events.append(
                PendingEvent(
                    source="ocr_post_plant_alive",
                    event_type="post_plant_alive",
                    fields_proposed={"attackers_alive": att, "defenders_alive": def_},
                    t_observed=t_observed,
                    t_ingested=t_ingested,
                )
            )
            await asyncio.sleep(cadence_s)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 — top-level resilience boundary
            logger.warning(
                "post_plant_alive_worker cycle failure: %s: %s",
                type(exc).__name__,
                exc,
            )
            await asyncio.sleep(cadence_s)
