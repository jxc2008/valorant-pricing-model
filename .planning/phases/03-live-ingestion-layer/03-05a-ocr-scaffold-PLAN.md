---
id: 03-05a-ocr-scaffold
phase: 03
plan: 5
type: execute
wave: 3
depends_on:
  - 03-00-pyproject-and-constants
  - 03-01-shared-types-and-download
  - 03-02-salvage-verify
  - 03-03-match-state-move-and-extend
files_modified:
  - src/ingestion/ocr.py
  - src/config/constants.py
  - tests/ingestion/test_ocr.py
  - tests/ingestion/fixtures/canned_kill_feed_frames/.gitkeep
autonomous: true
requirements:
  - REQ-ocr-pipeline
user_setup: []
must_haves:
  truths:
    - "OCRPipeline class is constructed per-match with explicit dependencies (executor, frame_source, emit, model_path) — no module-level mutable state (RESEARCH §Salvage-Port Delta line 586)"
    - "ONNX InferenceSession constructed with providers=['CPUExecutionProvider'] only (D-03 + REQ-cloud-vm has no GPU)"
    - "ONNX model file integrity verified before InferenceSession instantiation (T-deser-01 — call scripts.download_models.verify before load)"
    - "OCR runs in loop.run_in_executor(ThreadPoolExecutor) per D-06; pool_size = OCR_THREAD_POOL_SIZE (NEW const = 2)"
    - "Per-target HUD bbox crop + autocontrast preprocess (RESEARCH Pitfall 1) — bboxes declared in src/config/constants.py (4 new bbox constants + OCR_THREAD_POOL_SIZE)"
    - "5-frame ONNX accuracy probe placeholder (`tests/ingestion/fixtures/canned_kill_feed_frames/.gitkeep`); operator drops fixture frames per CONTEXT deferred-ideas — A3 mitigation"
    - "Scaffold tests pass (constructor verifies onnx integrity; skip_onnx_verify escape hatch works); backend logic + benchmark + cadence + low-conf-drop all live in 03-05b"
  artifacts:
    - path: src/ingestion/ocr.py
      provides: "OCRPipeline scaffold (class + constructor + integrity-verify hook + ThreadPoolExecutor + run_target stub); backends materialized in 03-05b"
      contains: "class OCRPipeline"
    - path: src/config/constants.py
      provides: "+5 OCR-specific constants (HUD bboxes for 4 targets + thread pool size)"
      contains: "HUD_BBOX_KILL_FEED"
    - path: tests/ingestion/test_ocr.py
      provides: "scaffold-level tests: integrity-verify, skip_onnx_verify, accuracy probe (skip-by-default)"
    - path: tests/ingestion/fixtures/canned_kill_feed_frames/.gitkeep
      provides: "directory for the 5 hand-labeled accuracy-probe frames (operator action documented)"
  key_links:
    - from: "src/ingestion/ocr.py"
      to: "models/en_PP-OCRv4_rec_infer.onnx"
      via: "onnxruntime.InferenceSession(model_path, providers=['CPUExecutionProvider'])"
      pattern: "InferenceSession.*CPUExecutionProvider"
    - from: "src/ingestion/ocr.py"
      to: "scripts.download_models.verify"
      via: "verify(MODEL_PATH, EXPECTED_SHA256) before InferenceSession"
      pattern: "from scripts.download_models import verify"
---

<objective>
Wave 3 source plan #2 (split-A) — port the OCR pipeline SCAFFOLD from `reference/vision_parser.py` into `src/ingestion/ocr.py`. Backends + `_signal_for` + benchmark + cadence + low-conf-drop tests live in **03-05b** (this plan's downstream split).

Purpose: Per BLOCKER-2 (checker), the original 03-05 bundled ~250 LOC across constants, scaffold, ONNX session, ThreadPool wiring, 4 backends, and signal extraction. Splitting reduces copy-paste error surface (which is where BLOCKER-1's `numerical_diff_delta` typo originated).

Output: `src/ingestion/ocr.py` (OCRPipeline class skeleton with integrity verify hook, ThreadPoolExecutor wiring, run_target loop scaffolding); `+5` HUD bbox + thread-pool constants; `tests/ingestion/test_ocr.py` (integrity-verify + skip_onnx_verify + 5-frame accuracy probe); placeholder dir for operator-supplied accuracy probe frames.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/03-live-ingestion-layer/03-SPEC.md
@.planning/phases/03-live-ingestion-layer/03-CONTEXT.md
@.planning/phases/03-live-ingestion-layer/03-RESEARCH.md
@.planning/phases/03-live-ingestion-layer/03-PATTERNS.md
@.planning/phases/03-live-ingestion-layer/03-VALIDATION.md
@reference/vision_parser.py
@src/ingestion/types.py
@src/ingestion/__init__.py
@src/config/constants.py
@scripts/download_models.py
@CLAUDE.md

<interfaces>
<!-- Constants this plan reads (added by 03-00 + this plan) -->

```python
# From 03-00:
OCR_KILLFEED_CADENCE_MS         # 100
OCR_SCOREBOARD_CADENCE_MS       # 250
OCR_BOMB_CADENCE_MS             # 500
OCR_ROUNDEND_CADENCE_MS         # 100
OCR_DECODE_BUDGET_MS            # 50
OCR_INFERENCE_BUDGET_MS         # 50
OCR_KILLFEED_CONF_THRESHOLD     # 0.7
OCR_BACKLOG_MAX                 # 4

# Added by THIS plan:
HUD_BBOX_SCORE_BANNER           # tuple[int, int, int, int] — (x0, y0, x1, y1) per Pitfall 1
HUD_BBOX_KILL_FEED              # tuple[int, int, int, int]
HUD_BBOX_BOMB_ICON              # tuple[int, int, int, int]
HUD_BBOX_ROUND_END_BANNER       # tuple[int, int, int, int]
OCR_THREAD_POOL_SIZE            # 2
```

<!-- ArbiterPending shape (consume from src/ingestion/types.py) -->

```python
@dataclass(frozen=True, slots=True)
class ArbiterPending:
    signal_value: dict[str, Any]
    source: SourceTag                # "ocr"
    event_type: EventType            # "kill" | "bomb" | "round_end" | "score_change"
    t_observed: float
    t_ingested: float
```

<!-- Pattern 2 ThreadPoolExecutor OCR worker (RESEARCH lines 271-300) -->

```python
_OCR_POOL: Final[ThreadPoolExecutor] = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ocr")

async def run_ocr_frame(frame: bytes, target: str) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_OCR_POOL, _ocr_blocking, frame, target)
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add HUD bbox + pool-size constants; create OCRPipeline scaffold + frame-source protocol + integrity-verify hook</name>
  <files>src/config/constants.py, src/ingestion/ocr.py, src/ingestion/__init__.py</files>
  <read_first>
    - src/config/constants.py (Phase 3 section block)
    - reference/vision_parser.py (entire file — verbatim source for HUD bbox coordinates IF salvage has them; treat as TEMPLATE)
    - .planning/phases/03-live-ingestion-layer/03-RESEARCH.md §Common Pitfalls Pitfall 1 (lines 624-641 — HUD bbox coordinates as Final constants)
    - .planning/phases/03-live-ingestion-layer/03-RESEARCH.md §Architecture Patterns Pattern 2 (lines 271-300)
    - .planning/phases/03-live-ingestion-layer/03-RESEARCH.md §Common Pitfalls Pitfall 6 (lines 711-723 — backlog cap mechanism)
    - .planning/phases/03-live-ingestion-layer/03-RESEARCH.md §Common Pitfalls Pitfall 4 (lines 668-695 — Windows ProactorEventLoop + executor shutdown discipline)
    - src/ingestion/types.py (ArbiterPending shape)
    - scripts/download_models.py (verify function used to gate InferenceSession load)
  </read_first>
  <action>
**(a)** Append 5 new constants to the Phase 3 section in `src/config/constants.py` (after the existing OCR_BACKLOG_MAX block):

```python
# OCR HUD bounding boxes (Pitfall 1: tesseract on raw 1080p frames returns
# garbage; crop to a known HUD bbox before OCR). Coordinates are illustrative
# (RESEARCH §Sources Tertiary line 1179 — A1 not live-verified). The 03-05b OCR
# backend plan adds calibration tests; final values land here.
# Format: (x0, y0, x1, y1) for PIL.Image.crop()

HUD_BBOX_SCORE_BANNER: Final[tuple[int, int, int, int]] = (820, 20, 1100, 80)
"""Score-banner bbox for 1920x1080 broadcast frames (Pitfall 1)."""

HUD_BBOX_KILL_FEED: Final[tuple[int, int, int, int]] = (1500, 100, 1900, 400)
"""Kill-feed bbox (right side of screen, 1920x1080 broadcast frames)."""

HUD_BBOX_BOMB_ICON: Final[tuple[int, int, int, int]] = (940, 110, 980, 150)
"""Bomb-icon bbox (top-center of screen)."""

HUD_BBOX_ROUND_END_BANNER: Final[tuple[int, int, int, int]] = (700, 400, 1220, 500)
"""Round-end banner bbox (center of screen during round-end window)."""

OCR_THREAD_POOL_SIZE: Final[int] = 2
"""Number of worker threads in the OCR ThreadPoolExecutor (D-06)."""
```

**(b)** Create `src/ingestion/ocr.py` SCAFFOLD ONLY (backends + signal extraction live in 03-05b). The scaffold ships:
- Module docstring explaining the split (this plan = scaffold; 03-05b = backends).
- `OCRTarget`, `EmitFn`, `_TARGET_CADENCE_MS`, `_TARGET_BBOX` lookups.
- `FrameSource` Protocol.
- `_OCRResult` internal dataclass.
- `OCRPipeline.__init__` with integrity-verify hook (`_verify_onnx_model` calling `scripts.download_models.verify`); `skip_onnx_verify` test escape hatch; ThreadPoolExecutor wiring; counters (`stats`, `_pending_count`).
- `OCRPipeline._build_onnx_session` — ONLY `CPUExecutionProvider` per D-03.
- `OCRPipeline.run_target` async loop — frame fetch + backlog cap + executor offload + maybe_emit + sleep at the per-target cadence. The `_inference` method is referenced but DEFINED IN 03-05b (this scaffold can call into a stub method that raises NotImplementedError until 03-05b lands; or the scaffold can include a placeholder `_inference` that returns `None` so cadence/integrity tests pass without the real backends).

PRECISE CONTRACT for the placeholder: this plan's `_inference(frame, target)` returns `None` unconditionally. 03-05b REPLACES this method body with the real ONNX/tesseract dispatch. Keep the method signature stable so the test contract is fixed.

```python
"""Phase 3 OCR pipeline SCAFFOLD (REQ-ocr-pipeline). Plan 03-05a.

This file ships the *scaffold*: class, constructor, integrity-verify hook,
ThreadPoolExecutor offload, per-target cadence loop, and the empty
`_inference` placeholder. The real ONNX + pytesseract backends + signal
extraction live in plan 03-05b which OVERWRITES `_inference`, `_signal_for`,
`_event_type_for`, `_infer_onnx`, and `_infer_tesseract`.

Why split: the original 03-05 bundled ~250 LOC; the BLOCKER-1 typo
(`numerical_diff_delta` vs `numerical_diff`) traced back to that bundle.

Sources
-------
- 03-SPEC.md §3 (REQ-ocr-pipeline acceptance)
- 03-CONTEXT.md D-03, D-06
- 03-RESEARCH.md §Architecture Patterns Pattern 2; Common Pitfalls 1, 4, 6
- scripts/download_models.py (T-deser-01 verify hook)
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal, Optional, Protocol, runtime_checkable

import numpy as np
from PIL import Image, ImageOps

from src.config.constants import (
    HUD_BBOX_BOMB_ICON,
    HUD_BBOX_KILL_FEED,
    HUD_BBOX_ROUND_END_BANNER,
    HUD_BBOX_SCORE_BANNER,
    OCR_BACKLOG_MAX,
    OCR_BOMB_CADENCE_MS,
    OCR_KILLFEED_CADENCE_MS,
    OCR_KILLFEED_CONF_THRESHOLD,
    OCR_ROUNDEND_CADENCE_MS,
    OCR_SCOREBOARD_CADENCE_MS,
    OCR_THREAD_POOL_SIZE,
)
from src.ingestion.types import ArbiterPending

log = logging.getLogger(__name__)

OCRTarget = Literal["kill_feed", "score_banner", "bomb_icon", "round_end_banner"]
EmitFn = Callable[[ArbiterPending], Awaitable[None]]

_TARGET_CADENCE_MS: Final[dict[OCRTarget, int]] = {
    "kill_feed":         OCR_KILLFEED_CADENCE_MS,
    "score_banner":      OCR_SCOREBOARD_CADENCE_MS,
    "bomb_icon":         OCR_BOMB_CADENCE_MS,
    "round_end_banner":  OCR_ROUNDEND_CADENCE_MS,
}
_TARGET_BBOX: Final[dict[OCRTarget, tuple[int, int, int, int]]] = {
    "kill_feed":         HUD_BBOX_KILL_FEED,
    "score_banner":      HUD_BBOX_SCORE_BANNER,
    "bomb_icon":         HUD_BBOX_BOMB_ICON,
    "round_end_banner":  HUD_BBOX_ROUND_END_BANNER,
}


@runtime_checkable
class FrameSource(Protocol):
    def frames(self) -> Iterator[bytes]: ...


@dataclass(frozen=True, slots=True)
class _OCRResult:
    text: str
    confidence: float
    target: OCRTarget


class OCRPipeline:
    """OCR pipeline scaffold. Backends in 03-05b."""

    def __init__(
        self,
        emit: EmitFn,
        executor: ThreadPoolExecutor,
        frame_source: FrameSource,
        onnx_model_path: Path,
        skip_onnx_verify: bool = False,
    ) -> None:
        self._emit = emit
        self._executor = executor
        self._frame_source = frame_source
        self._onnx_model_path = onnx_model_path
        if not skip_onnx_verify:
            self._verify_onnx_model()
        self._onnx_session = self._build_onnx_session()
        self.stats: dict[str, int] = {
            "ocr_dropped_frames_total": 0,
            "ocr_low_confidence_drops": 0,
        }
        self._pending_count: int = 0

    def _verify_onnx_model(self) -> None:
        """T-deser-01: SHA-256 verify before deserialize."""
        from scripts.download_models import EXPECTED_SHA256, verify
        ok, observed = verify(self._onnx_model_path, EXPECTED_SHA256)
        if not ok:
            raise RuntimeError(
                f"ONNX model integrity check FAILED: path={self._onnx_model_path} "
                f"expected_sha256={EXPECTED_SHA256!r} observed={observed!r}. "
                f"Run: python -m scripts.download_models --force"
            )

    def _build_onnx_session(self) -> Any:
        """Build the InferenceSession once at construct time. CPU-only per D-03."""
        import onnxruntime as ort
        return ort.InferenceSession(
            str(self._onnx_model_path),
            providers=["CPUExecutionProvider"],
        )

    async def run_target(self, target: OCRTarget) -> None:
        """Loop forever at this target's cadence. Caller cancels the task to stop."""
        period_s = _TARGET_CADENCE_MS[target] / 1000.0
        frame_iter = iter(self._frame_source.frames())
        while True:
            try:
                frame = next(frame_iter)
            except StopIteration:
                await asyncio.sleep(period_s)
                continue
            if self._pending_count >= OCR_BACKLOG_MAX:
                self.stats["ocr_dropped_frames_total"] += 1
                log.debug("ocr_backlog_drop target=%s pending=%d", target, self._pending_count)
                await asyncio.sleep(period_s)
                continue
            self._pending_count += 1
            try:
                result = await asyncio.get_running_loop().run_in_executor(
                    self._executor, self._inference, frame, target,
                )
            finally:
                self._pending_count -= 1
            await self._maybe_emit(target, result)
            await asyncio.sleep(period_s)

    async def _maybe_emit(self, target: OCRTarget, result: Optional[_OCRResult]) -> None:  # noqa: UP045
        """Pitfall 2 + BLOCKER-1: low-conf drop + soft-channel routing.
        Implementation completed in 03-05b (signal_value extraction + ArbiterPending construction).
        Scaffold's placeholder simply returns when result is None."""
        if result is None:
            return
        # Implementation continued in 03-05b which OVERWRITES this method.
        raise NotImplementedError("Backend body lives in 03-05b — see 03-05b-ocr-backends-PLAN.md")

    def _inference(self, frame: bytes, target: OCRTarget) -> Optional[_OCRResult]:  # noqa: UP045
        """Scaffold placeholder. 03-05b OVERWRITES this with the real ONNX +
        tesseract dispatch. Returning None preserves the run_target loop and
        backlog-cap test surface; tests that exercise real inference live in 03-05b."""
        return None
```

(c) Update `src/ingestion/__init__.py` to re-export the scaffold types:

```python
from src.ingestion.ocr import OCRPipeline, FrameSource, OCRTarget
```

Add `"OCRPipeline", "FrameSource", "OCRTarget"` to `__all__`.
  </action>
  <verify>
    <automated>python -c "from src.ingestion import OCRPipeline, FrameSource; from src.ingestion.ocr import OCRTarget; from src.config.constants import HUD_BBOX_KILL_FEED, HUD_BBOX_SCORE_BANNER, HUD_BBOX_BOMB_ICON, HUD_BBOX_ROUND_END_BANNER, OCR_THREAD_POOL_SIZE; print('all symbols ok')" &amp;&amp; mypy src/ingestion/ocr.py &amp;&amp; ruff check src/ingestion/ocr.py src/config/constants.py</automated>
  </verify>
  <done>5 new constants in src/config/constants.py; src/ingestion/ocr.py scaffold exports OCRPipeline + FrameSource + OCRTarget with `_inference` returning None and `_maybe_emit` raising NotImplementedError; mypy + ruff clean (gradual scope on src/ingestion/); ALL Phase 1+2+03-03 tests still pass; 03-05b is the immediate next plan that fills in the backends.</done>
</task>

<task type="auto">
  <name>Task 2: tests/ingestion/test_ocr.py — scaffold-level tests (integrity-verify + skip_onnx_verify + 5-frame accuracy probe)</name>
  <files>tests/ingestion/test_ocr.py, tests/ingestion/fixtures/canned_kill_feed_frames/.gitkeep</files>
  <read_first>
    - src/ingestion/ocr.py (scaffold from Task 1)
    - .planning/phases/03-live-ingestion-layer/03-VALIDATION.md Manual-Only Verifications (lines 96-99 — A3 accuracy probe)
    - .planning/phases/03-live-ingestion-layer/03-RESEARCH.md §Assumptions Log A3 (lines 1022-1023 — fallback options if accuracy < 70%)
  </read_first>
  <action>
Create `tests/ingestion/fixtures/canned_kill_feed_frames/.gitkeep` (placeholder for operator-supplied accuracy probe frames; per CONTEXT deferred-ideas the CTC text decoder ships in Phase 5).

```
# Operator-supplied: 5 hand-labeled PNG frames from real Valorant broadcast
# kill-feed area (cropped per HUD_BBOX_KILL_FEED).
# Used by tests/ingestion/test_ocr.py::test_ocr_accuracy_probe_5_frames
# to surface the A3 accuracy metric (RESEARCH §Open Questions item 3).
# If empty/missing: that test SKIPS with a clear operator-action message.
# Phase 3 ships scaffold + signal_for path; full text decoder calibrated in
# Phase 5 (see 03-CONTEXT.md `<deferred>`).
```

Create `tests/ingestion/test_ocr.py` with the SCAFFOLD-LEVEL tests only:

```python
"""OCRPipeline SCAFFOLD tests — REQ-ocr-pipeline acceptance (split-A).

Backend tests (benchmark, cadence, low-conf drop, signal extraction,
test_ocr_kill_feed_drives_numerical_diff_change) live in 03-05b which
overwrites `_inference` and `_maybe_emit`.

Sources
-------
- 03-VALIDATION.md tasks 03-OC-01..03 + Manual-Only A3 probe
- 03-RESEARCH.md §Common Pitfalls Pitfalls 1/2/4/6 + §Open Questions A3
- src/ingestion/ocr.py (module under test)
"""
from __future__ import annotations

import io
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PIL import Image

from src.config.constants import OCR_KILLFEED_CONF_THRESHOLD
from src.ingestion.ocr import (
    FrameSource,
    OCRPipeline,
    _OCRResult,
)
from src.ingestion.types import ArbiterPending


def _png_bytes() -> bytes:
    im = Image.new("RGB", (200, 100), color=(255, 255, 255))
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


class FakeFrameSource:
    def __init__(self, n_frames: int = 100) -> None:
        self._payload = _png_bytes()
        self._n = n_frames

    def frames(self) -> Iterator[bytes]:
        for _ in range(self._n):
            yield self._payload


@pytest.fixture
def emitted() -> list[ArbiterPending]:
    return []


@pytest.fixture
def emit_fn(emitted: list[ArbiterPending]):
    async def _emit(p: ArbiterPending) -> None:
        emitted.append(p)
    return _emit


@pytest.fixture
def executor():
    pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="test-ocr")
    yield pool
    pool.shutdown(wait=True, cancel_futures=False)


@pytest.fixture
def pipeline(emit_fn, executor) -> OCRPipeline:
    """OCRPipeline with skip_onnx_verify=True and onnxruntime mocked."""
    with patch("onnxruntime.InferenceSession") as MockSession:
        mock_sess = MagicMock()
        mock_sess.get_inputs.return_value = [MagicMock(name="x")]
        mock_sess.run.return_value = [np.random.randn(1, 5, 100) * 5.0]
        MockSession.return_value = mock_sess
        return OCRPipeline(
            emit=emit_fn,
            executor=executor,
            frame_source=FakeFrameSource(n_frames=10),
            onnx_model_path=Path("models/en_PP-OCRv4_rec_infer.onnx"),
            skip_onnx_verify=True,
        )


# ----- Construction / integrity ----- #


def test_constructor_verifies_onnx_integrity(emit_fn, executor) -> None:
    """T-deser-01: missing model path / unpinned hash MUST raise RuntimeError."""
    with pytest.raises(RuntimeError, match="ONNX model integrity check FAILED"):
        OCRPipeline(
            emit=emit_fn,
            executor=executor,
            frame_source=FakeFrameSource(),
            onnx_model_path=Path("/nonexistent/model.onnx"),
            skip_onnx_verify=False,
        )


def test_skip_onnx_verify_escape_hatch_works(pipeline: OCRPipeline) -> None:
    """skip_onnx_verify=True bypasses the integrity check (test-only)."""
    assert pipeline._onnx_session is not None
    assert pipeline.stats["ocr_dropped_frames_total"] == 0
    assert pipeline.stats["ocr_low_confidence_drops"] == 0


# ----- A3 accuracy probe (operator-run; CONTEXT deferred CTC decoder) ----- #


_ONNX_MODEL_PRESENT: bool = Path("models/en_PP-OCRv4_rec_infer.onnx").exists()


@pytest.mark.skip(
    reason="OCR kill-feed CTC text decoder deferred to Phase 5 calibration "
           "(see 03-CONTEXT.md `<deferred>`). Probe re-enables once 03-05b "
           "ships the real backend AND the operator drops 5 frames into "
           "tests/ingestion/fixtures/canned_kill_feed_frames/."
)
def test_ocr_accuracy_probe_5_frames(emit_fn, executor) -> None:
    """A3 mitigation: surfaces ONNX kill-feed accuracy on real frames.
    Skipped in Phase 3 per CONTEXT deferred-ideas (CTC decoder ships Phase 5).
    """
    if not _ONNX_MODEL_PRESENT:
        pytest.skip("ONNX model not downloaded; run `python -m scripts.download_models`")
    fixture_dir = Path(__file__).parent / "fixtures" / "canned_kill_feed_frames"
    pngs = sorted(fixture_dir.glob("*.png")) if fixture_dir.exists() else []
    if not pngs:
        pytest.skip(
            f"No canned kill-feed frames in {fixture_dir}. "
            f"Operator: drop 5 hand-labeled PNG crops to enable the probe."
        )
    pipeline = OCRPipeline(
        emit=emit_fn,
        executor=executor,
        frame_source=FakeFrameSource(),
        onnx_model_path=Path("models/en_PP-OCRv4_rec_infer.onnx"),
        skip_onnx_verify=True,
    )
    confidences: list[float] = []
    for png in pngs:
        result = pipeline._inference(png.read_bytes(), "kill_feed")
        if result is not None:
            confidences.append(result.confidence)
    if not confidences:
        pytest.skip("All probe frames failed inference; check fixture quality")
    mean_conf = float(np.mean(confidences))
    print(
        f"\n[A3 PROBE] ONNX kill-feed mean confidence over {len(confidences)} frames: "
        f"{mean_conf:.3f} (threshold {OCR_KILLFEED_CONF_THRESHOLD})"
    )
```

The benchmark + cadence + low-conf-drop + backlog-cap + signal-extraction + `test_ocr_kill_feed_drives_numerical_diff_change` tests all live in **03-05b** (which overwrites `_inference` and `_maybe_emit` with the real backend bodies).
  </action>
  <verify>
    <automated>pytest tests/ingestion/test_ocr.py -x &amp;&amp; mypy src/ingestion/ocr.py &amp;&amp; ruff check src/ingestion/ocr.py tests/ingestion/test_ocr.py</automated>
  </verify>
  <done>tests/ingestion/test_ocr.py has 3 named tests (constructor integrity, skip_onnx_verify, accuracy probe @skip); all pass; tests/ingestion/fixtures/canned_kill_feed_frames/.gitkeep exists; mypy + ruff clean. Backend tests deferred to 03-05b.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| ONNX model deserialization | `onnxruntime.InferenceSession()` parses the binary; integrity verified before load. |
| ThreadPoolExecutor | OCR jobs share a pool with the scoreboard poller. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-03-05a-01 (covers T-deser-01) | T (Tampering) | ONNX model file | mitigate | `_verify_onnx_model()` calls `scripts.download_models.verify(MODEL_PATH, EXPECTED_SHA256)` BEFORE `onnxruntime.InferenceSession()`. RuntimeError raised on mismatch. |
| T-03-05a-02 | D (Denial of service) | unbounded ThreadPoolExecutor backlog | mitigate | Pitfall 6: `_pending_count >= OCR_BACKLOG_MAX` drops the frame and increments the counter (test surface in 03-05b). |
</threat_model>

<verification>
- `pytest tests/ingestion/test_ocr.py -x` PASSES (3 scaffold tests).
- `mypy src/ingestion/ocr.py` clean.
- `ruff check src/ingestion/ocr.py tests/ingestion/test_ocr.py src/config/constants.py` clean.
- `python -c "from src.ingestion import OCRPipeline, FrameSource"` works.
- 5 new HUD bbox + pool-size constants importable.
- Phase 1 + 2 + 03-03 regressions GREEN.
</verification>

<success_criteria>
Wave 3 plan 03-05a (OCR scaffold) is COMPLETE when:

1. `src/ingestion/ocr.py` ships the OCRPipeline scaffold with integrity-verify hook + ThreadPoolExecutor + run_target loop + `_inference` placeholder returning None.
2. ONNX integrity verify gates `InferenceSession()` per T-deser-01.
3. 5 new constants in `src/config/constants.py` (HUD bboxes + OCR_THREAD_POOL_SIZE).
4. `tests/ingestion/test_ocr.py` has 3 scaffold tests (constructor integrity, skip_onnx_verify, accuracy probe @skip).
5. `tests/ingestion/fixtures/canned_kill_feed_frames/.gitkeep` exists; A3 accuracy-probe deferred to Phase 5 per CONTEXT.
6. `src/ingestion/__init__.py` re-exports scaffold types.
7. Phase 1 + 2 + 03-03 regressions GREEN.
8. 03-05b can begin (overwrites `_inference` + `_maybe_emit` with real backend bodies).
</success_criteria>

<output>
After completion, create `.planning/phases/03-live-ingestion-layer/03-05a-SUMMARY.md` documenting the scaffold + the deferred backend handoff to 03-05b.
</output>
