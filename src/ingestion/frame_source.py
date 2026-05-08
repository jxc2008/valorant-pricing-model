"""Abstract frame-grabber Protocol + StubFrameSource for tests (RESEARCH Open Q 2).

YouTube wiring (vidgear / yt-dlp / ffmpeg) is OUT OF SCOPE for Phase 3 per
research recommendation: 'Phase 3 ships FrameSource Protocol + StubFrameSource;
YouTube wiring is a paper-trade-bring-up concern that lives at the boundary
between Phase 3 and Phase 4.'

The synthetic E2E test (03-08) injects synthetic frames directly via
StubFrameSource; real YouTube decode lands in Phase 4 alongside paper-trade
infrastructure.
"""
from __future__ import annotations

from typing import Protocol

import numpy as np
from numpy.typing import NDArray


class FrameSource(Protocol):
    """Abstract frame-grabber consumed by the OCR workers.

    Implementations return the most recent decoded broadcast frame as a BGR
    uint8 numpy array of shape (1080, 1920, 3) — the standard 1920x1080 VCT
    international broadcast layout that the ROI constants assume. Phase 5
    robustness work could extend to multi-resolution sources.
    """

    async def latest_frame(self) -> NDArray[np.uint8]:
        """Return most recent decoded frame as BGR uint8 (1080, 1920, 3)."""
        ...


class StubFrameSource:
    """In-memory frame stub for tests + synthetic E2E (Open Q 2).

    Caller pushes frames via push(); workers consume via latest_frame().
    Designed to never block — if no frame pushed, raises RuntimeError so
    tests fail loudly rather than hang.
    """

    def __init__(self) -> None:
        self._frame: NDArray[np.uint8] | None = None

    def push(self, frame: NDArray[np.uint8]) -> None:
        """Set the current frame buffer (overwrites prior)."""
        self._frame = frame

    async def latest_frame(self) -> NDArray[np.uint8]:
        if self._frame is None:
            raise RuntimeError("StubFrameSource: no frame pushed; call push() first")
        return self._frame


class YouTubeFrameSource:
    """YouTube low-latency live frame grabber.

    TODO(phase-4): wire vidgear.CamGear (yt-dlp + threading) per RESEARCH
    §"Standard Stack" alternatives table. ~3s typical end-to-end YouTube live
    latency; satisfies SPEC's broadcast-aligned-replay requirement.

    Phase 3 ships the skeleton so Phase 4 can wire the implementation without
    a Phase-3-revisit; calling __init__ raises with a clear "Phase 4 wires this"
    message to fail loudly if accidentally instantiated in tests.
    """

    def __init__(self, url: str) -> None:
        self.url = url
        raise NotImplementedError(
            "YouTubeFrameSource is a Phase 4 deliverable — wire vidgear/yt-dlp "
            "alongside paper-trade infrastructure. Use StubFrameSource for tests."
        )

    async def latest_frame(self) -> NDArray[np.uint8]:
        raise NotImplementedError("Phase 4 wires this")
