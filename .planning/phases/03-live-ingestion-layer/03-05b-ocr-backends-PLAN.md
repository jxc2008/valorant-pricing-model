---
id: 03-05b-ocr-backends
phase: 03
plan: 5
type: execute
wave: 3
depends_on:
  - 03-00-pyproject-and-constants
  - 03-01-shared-types-and-download
  - 03-02-salvage-verify
  - 03-03-match-state-move-and-extend
  - 03-05a-ocr-scaffold
files_modified:
  - src/ingestion/ocr.py
  - tests/ingestion/test_ocr.py
autonomous: true
requirements:
  - REQ-ocr-pipeline
user_setup: []
must_haves:
  truths:
    - "Hybrid backend per D-03: ONNX small text-recognition CNN for kill_feed; pytesseract for score_banner / bomb_icon / round_end_banner"
    - "Kill-feed inference checks softmax_top1_prob >= OCR_KILLFEED_CONF_THRESHOLD; below => no event emitted (RESEARCH Pitfall 2)"
    - "Backlog cap enforced: ocr scheduler tracks pending count; when > OCR_BACKLOG_MAX => DROP frame + increment ocr_dropped_frames_total (RESEARCH Pitfall 6)"
    - "Per-target cadence honored within ±10% jitter under sustained load (REQ-ocr-pipeline acceptance + VALIDATION 03-OC-02)"
    - "50-frame median decode + inference < 100ms per target (REQ-ocr-pipeline acceptance + VALIDATION 03-OC-01)"
    - "BLOCKER-1: kill_feed _signal_for emits {numerical_diff: int} (NOT numerical_diff_delta — that key does NOT exist on MatchState)"
    - "BLOCKER-1: round_end_banner ROUTES THROUGH ConfirmedEvent.is_soft=True channel — does NOT inject _round_end_soft sentinel into signal_value, does NOT include round_end_text (no MatchState slot)"
    - "WARNING-4: test_ocr_kill_feed_drives_numerical_diff_change exercises ONE recorded fixture frame end-to-end through the OCR backend; @pytest.mark.skip until CTC decoder ships in Phase 5 (per 03-CONTEXT deferred-ideas)"
  artifacts:
    - path: src/ingestion/ocr.py
      provides: "real backends — _maybe_emit, _inference, _infer_onnx, _infer_tesseract, _signal_for, _event_type_for"
      contains: "_infer_onnx"
    - path: tests/ingestion/test_ocr.py
      provides: "backend tests: low-conf drop, above-threshold emit, backlog cap, per-target cadence, signal extraction, benchmark, kill-feed integration probe"
  key_links:
    - from: "src/ingestion/ocr.py"
      to: "src/ingestion/types.py"
      via: "emits ArbiterPending source=\"ocr\" with numerical_diff key (BLOCKER-1)"
      pattern: "ArbiterPending\\(.*source=.ocr."
---

<objective>
Wave 3 source plan #2 (split-B) — fill in the OCR backend bodies on top of 03-05a's scaffold. Hybrid ONNX (kill_feed) + pytesseract (the other 3 targets). Routes round_end soft commits through `ConfirmedEvent.is_soft=True` per BLOCKER-1 (the original `_round_end_soft` sentinel-key path injected an unknown attribute into `MatchState.with_update` and is forbidden).

Purpose: Per BLOCKER-2 + WARNING-4, the original 03-05 was too large AND introduced the BLOCKER-1 typo (`numerical_diff_delta`). This plan ships ONLY the backends + extraction + tests, against the 03-05a scaffold, with the corrected key names AND the new fixture-driven integration test.

Output: completed `src/ingestion/ocr.py` (overwrites the scaffold's `_inference` + `_maybe_emit` placeholders); `tests/ingestion/test_ocr.py` extended with backend tests + the new `test_ocr_kill_feed_drives_numerical_diff_change` integration test.
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
@src/ingestion/ocr.py
@src/ingestion/__init__.py
@src/config/constants.py
@scripts/download_models.py
@CLAUDE.md
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Implement backends in src/ingestion/ocr.py — _maybe_emit (is_soft routing), _inference dispatch, _infer_onnx, _infer_tesseract, _signal_for (BLOCKER-1 corrected), _event_type_for</name>
  <files>src/ingestion/ocr.py</files>
  <read_first>
    - src/ingestion/ocr.py (scaffold from 03-05a — overwrite the two placeholder methods)
    - reference/vision_parser.py (verbatim source for HUD parsing patterns)
    - .planning/phases/03-live-ingestion-layer/03-RESEARCH.md §Architecture Patterns Pattern 2 (lines 271-300)
    - .planning/phases/03-live-ingestion-layer/03-RESEARCH.md §Common Pitfalls Pitfall 2 (low-conf drop)
    - src/state/match_state.py (verify the field names — numerical_diff EXISTS, numerical_diff_delta DOES NOT; bomb_planted EXISTS; round_end_text DOES NOT exist as a field)
    - src/ingestion/types.py (ConfirmedEvent.is_soft from 03-01)
  </read_first>
  <behavior>
    - Test 1 (test_low_confidence_kill_feed_drops_event): patch _infer_onnx to return _OCRResult(confidence=0.5); call _maybe_emit("kill_feed", result); assert NO emit + stats["ocr_low_confidence_drops"] == 1.
    - Test 2 (test_above_threshold_kill_feed_emits): patch _infer_onnx to return _OCRResult(confidence=0.9); _maybe_emit; assert emit IS called with source="ocr", event_type="kill"; signal_value contains the key `numerical_diff` (BLOCKER-1: NOT `numerical_diff_delta`).
    - Test 3 (test_round_end_banner_emits_via_is_soft_channel): patch _infer_tesseract to return _OCRResult(text="ROUND END") for round_end_banner; _maybe_emit; assert emit called with event_type="round_end" AND the ArbiterPending's signal_value does NOT contain `_round_end_soft`, does NOT contain `round_end_text`. The is_soft routing happens inside the arbiter's _commit (03-07b).
    - Test 4 (test_backlog_cap_drops_frame): set pipeline._pending_count = OCR_BACKLOG_MAX; run_target("kill_feed") for one iteration; assert ocr_dropped_frames_total > 0 + emit not called.
    - Test 5 (test_per_target_cadence_within_jitter): each target's sleep period == its cadence within ±10%.
    - Test 6 (test_event_type_mapping): for each OCRTarget assert _event_type_for returns the spec'd EventType.
    - Test 7 (test_signal_extraction_score_banner): _signal_for("score_banner", _OCRResult(text="13 - 7", ...)) returns {"a_round": 13, "b_round": 7}; malformed text returns None.
    - Test 8 (test_ocr_benchmark_50_frames): pytest-benchmark over 50 synthetic frames per target; median per-target inference < 100ms; conditional skip without ONNX/tesseract.
    - Test 9 (test_ocr_kill_feed_drives_numerical_diff_change): WARNING-4 integration probe — runs OCR backend against ONE recorded fixture frame in tests/ingestion/fixtures/canned_kill_feed_frames/ and asserts the resulting ConfirmedEvent's fields_changed contains a non-zero `numerical_diff`. @pytest.mark.skip(reason="OCR kill-feed CTC decoder deferred to Phase 5 per CONTEXT") because the CTC decoder isn't shipped in Phase 3.
  </behavior>
  <action>
**OVERWRITE** the two placeholder methods in `src/ingestion/ocr.py` with real bodies, AND add the four new helper methods. Do NOT touch the scaffold's class boilerplate, constants, or imports (except adding `from io import BytesIO` and `import pytesseract` at module level — but actually keep the lazy imports inside `_infer_tesseract` for cold-start speed; only add `from io import BytesIO` to module-level if it isn't already there).

Replace the scaffold's `_maybe_emit` and `_inference` placeholder methods with:

```python
    async def _maybe_emit(self, target: OCRTarget, result: Optional[_OCRResult]) -> None:  # noqa: UP045
        """Pitfall 2: low-confidence kill-feed drops. BLOCKER-1: round_end
        routes through ConfirmedEvent.is_soft channel (handled by arbiter)."""
        if result is None:
            return
        if target == "kill_feed" and result.confidence < OCR_KILLFEED_CONF_THRESHOLD:
            self.stats["ocr_low_confidence_drops"] += 1
            log.debug("ocr_low_conf_drop target=%s conf=%.3f", target, result.confidence)
            return
        signal_value = self._signal_for(target, result)
        if signal_value is None:
            return
        event_type = self._event_type_for(target)
        await self._emit(
            ArbiterPending(
                signal_value=signal_value,
                source="ocr",
                event_type=event_type,
                t_observed=time.time(),
                t_ingested=time.monotonic(),
            )
        )

    @staticmethod
    def _event_type_for(target: OCRTarget) -> Literal["kill", "bomb", "round_end", "score_change"]:
        return {
            "kill_feed":        "kill",
            "score_banner":     "score_change",
            "bomb_icon":        "bomb",
            "round_end_banner": "round_end",
        }[target]

    def _inference(self, frame: bytes, target: OCRTarget) -> Optional[_OCRResult]:  # noqa: UP045
        """Decode + crop + preprocess + backend dispatch (BLOCKS — runs in executor)."""
        try:
            from io import BytesIO
            im = Image.open(BytesIO(frame))
            cropped = im.crop(_TARGET_BBOX[target])
            cropped = ImageOps.autocontrast(cropped)
            if target == "kill_feed":
                return self._infer_onnx(cropped)
            return self._infer_tesseract(cropped, target)
        except Exception as exc:
            log.warning("ocr_inference_error target=%s exc=%s", target, exc)
            return None

    def _infer_onnx(self, im: Image.Image) -> Optional[_OCRResult]:  # noqa: UP045
        """Kill-feed only (D-03 hybrid). Returns top-1 text + softmax confidence.

        NOTE per CONTEXT deferred-ideas: full PaddleOCR character-dictionary CTC
        text decode lives in Phase 5 calibration. Phase 3 returns text="" with a
        REAL softmax-min confidence so the low-conf-drop gate (Pitfall 2) and
        the integration wiring are exercised end-to-end."""
        target_h = 48
        w, h = im.size
        ratio = target_h / max(h, 1)
        target_w = max(int(w * ratio), 32)
        im_resized = im.resize((target_w, target_h)).convert("RGB")
        arr = np.asarray(im_resized).astype(np.float32) / 255.0
        arr = (arr - 0.5) / 0.5
        arr = arr.transpose(2, 0, 1)[np.newaxis, :, :, :]
        outputs = self._onnx_session.run(None, {self._onnx_session.get_inputs()[0].name: arr})
        logits = outputs[0][0]
        exp = np.exp(logits - logits.max(axis=-1, keepdims=True))
        probs = exp / exp.sum(axis=-1, keepdims=True)
        top1_probs = probs.max(axis=-1)
        confidence = float(top1_probs.min())
        return _OCRResult(text="", confidence=confidence, target="kill_feed")

    def _infer_tesseract(self, im: Image.Image, target: OCRTarget) -> Optional[_OCRResult]:  # noqa: UP045
        """Tesseract for the 3 non-kill-feed targets."""
        import pytesseract
        psm = "8" if target == "bomb_icon" else "7"
        text = pytesseract.image_to_string(im, lang="eng", config=f"--psm {psm}").strip()
        confidence = 1.0 if text else 0.0
        return _OCRResult(text=text, confidence=confidence, target=target)

    @staticmethod
    def _signal_for(target: OCRTarget, result: _OCRResult) -> Optional[dict[str, Any]]:  # noqa: UP045
        """Map OCR output -> arbiter signal_value dict.

        BLOCKER-1 corrections:
        - kill_feed emits `numerical_diff` (NOT `numerical_diff_delta`; that key
          does NOT exist on MatchState).
        - round_end_banner emits an EMPTY signal_value dict and relies on
          ConfirmedEvent.is_soft=True (set by the arbiter during _commit) to
          carry the soft-commit signal. Does NOT inject `_round_end_soft`
          sentinel keys (forbidden — would crash StateHolder.swap_with). Does
          NOT emit `round_end_text` (no MatchState slot, no current consumer).
        """
        if not result.text and target != "kill_feed":
            return None
        if target == "kill_feed":
            # CONTEXT deferred: full CTC text decode + numerical_diff
            # extraction lands in Phase 5 calibration. Phase 3 emits a
            # placeholder numerical_diff=0 so the e2e wiring is exercised.
            # The integration test test_ocr_kill_feed_drives_numerical_diff_change
            # is @skip until Phase 5 ships the decoder.
            return {"numerical_diff": 0}
        if target == "score_banner":
            try:
                parts = result.text.replace("-", " ").split()
                a, b = int(parts[0]), int(parts[1])
                return {"a_round": a, "b_round": b}
            except (ValueError, IndexError):
                return None
        if target == "bomb_icon":
            return {"bomb_planted": True}
        if target == "round_end_banner":
            # BLOCKER-1: empty signal_value; is_soft channel carries the round-end signal.
            return {}
        return None
```

After this overwrite, `src/ingestion/ocr.py` is complete. Run `python -c "from src.ingestion.ocr import OCRPipeline; from src.ingestion.types import ArbiterPending; print('backend wired')"` to sanity-check.

Run mypy + ruff: `mypy src/ingestion/ocr.py && ruff check src/ingestion/ocr.py`.
  </action>
  <verify>
    <automated>python -c "from src.ingestion.ocr import OCRPipeline" &amp;&amp; mypy src/ingestion/ocr.py &amp;&amp; ruff check src/ingestion/ocr.py</automated>
  </verify>
  <done>src/ingestion/ocr.py has real `_maybe_emit`, `_inference`, `_infer_onnx`, `_infer_tesseract`, `_signal_for`, `_event_type_for` methods; kill_feed `_signal_for` emits `numerical_diff` key (BLOCKER-1 corrected); round_end_banner `_signal_for` returns `{}` (no sentinel keys); mypy + ruff clean.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: tests/ingestion/test_ocr.py — append backend tests (low-conf drop, above-threshold emit, round_end is_soft routing, backlog cap, cadence, signal extraction, benchmark) + WARNING-4 integration probe</name>
  <files>tests/ingestion/test_ocr.py</files>
  <read_first>
    - tests/ingestion/test_ocr.py (scaffold tests from 03-05a)
    - src/ingestion/ocr.py (real backends from Task 1)
    - .planning/phases/03-live-ingestion-layer/03-VALIDATION.md tasks 03-OC-01..03 + Sampling minimums lines 70-71
    - .planning/phases/03-live-ingestion-layer/03-CONTEXT.md `<deferred>` block (CTC decoder)
  </read_first>
  <action>
APPEND the backend tests to `tests/ingestion/test_ocr.py` (after the scaffold tests from 03-05a). Add these test functions:

```python
# ----- Low-confidence drop (Pitfall 2) ----- #


@pytest.mark.asyncio
async def test_low_confidence_kill_feed_drops_event(
    pipeline: OCRPipeline, emitted: list[ArbiterPending]
) -> None:
    """REQ-ocr-pipeline + VALIDATION 03-OC-03: kill_feed below threshold => no emit."""
    result = _OCRResult(text="ghost", confidence=OCR_KILLFEED_CONF_THRESHOLD - 0.01, target="kill_feed")
    await pipeline._maybe_emit("kill_feed", result)
    assert emitted == []
    assert pipeline.stats["ocr_low_confidence_drops"] == 1


@pytest.mark.asyncio
async def test_above_threshold_kill_feed_emits(
    pipeline: OCRPipeline, emitted: list[ArbiterPending]
) -> None:
    """kill_feed at-threshold => emit ArbiterPending source=ocr event_type=kill;
    BLOCKER-1: signal_value has `numerical_diff` (NOT `numerical_diff_delta`)."""
    result = _OCRResult(text="real", confidence=0.95, target="kill_feed")
    await pipeline._maybe_emit("kill_feed", result)
    assert len(emitted) == 1
    assert emitted[0].source == "ocr"
    assert emitted[0].event_type == "kill"
    # BLOCKER-1: the key MUST be `numerical_diff` (matches MatchState).
    assert "numerical_diff" in emitted[0].signal_value
    assert "numerical_diff_delta" not in emitted[0].signal_value


@pytest.mark.asyncio
async def test_round_end_banner_emits_empty_signal_value(
    pipeline: OCRPipeline, emitted: list[ArbiterPending]
) -> None:
    """BLOCKER-1 regression: round_end_banner signal_value must be empty/no-sentinels.
    The is_soft soft-commit signal is carried by ConfirmedEvent.is_soft=True
    inside arbiter._commit (03-07b), NOT by injecting _round_end_soft into
    fields_changed (which would crash dataclasses.replace on the frozen+slots
    MatchState)."""
    result = _OCRResult(text="ROUND END", confidence=1.0, target="round_end_banner")
    await pipeline._maybe_emit("round_end_banner", result)
    assert len(emitted) == 1
    assert emitted[0].source == "ocr"
    assert emitted[0].event_type == "round_end"
    assert emitted[0].signal_value == {}, (
        "BLOCKER-1: round_end_banner must NOT inject _round_end_soft or round_end_text "
        "into signal_value; the arbiter routes the soft signal via ConfirmedEvent.is_soft."
    )


# ----- Backlog cap (Pitfall 6) ----- #


@pytest.mark.asyncio
async def test_backlog_cap_drops_frame(
    pipeline: OCRPipeline, emitted: list[ArbiterPending]
) -> None:
    """Pitfall 6: pending >= OCR_BACKLOG_MAX => DROP frame."""
    import asyncio
    pipeline._pending_count = OCR_BACKLOG_MAX
    sleep_calls: list[float] = []

    async def _fake_sleep(t: float) -> None:
        sleep_calls.append(t)
        if len(sleep_calls) >= 2:
            raise asyncio.CancelledError()

    with patch("asyncio.sleep", _fake_sleep):
        with pytest.raises(asyncio.CancelledError):
            await pipeline.run_target("kill_feed")
    assert pipeline.stats["ocr_dropped_frames_total"] >= 1
    assert emitted == []


# ----- Cadence (REQ-ocr-pipeline acceptance) ----- #


@pytest.mark.asyncio
async def test_per_target_cadence_within_jitter(
    pipeline: OCRPipeline, emitted: list[ArbiterPending]
) -> None:
    import asyncio
    from src.config.constants import (
        OCR_BOMB_CADENCE_MS,
        OCR_KILLFEED_CADENCE_MS,
        OCR_ROUNDEND_CADENCE_MS,
        OCR_SCOREBOARD_CADENCE_MS,
    )
    expected = {
        "kill_feed":         OCR_KILLFEED_CADENCE_MS / 1000.0,
        "score_banner":      OCR_SCOREBOARD_CADENCE_MS / 1000.0,
        "bomb_icon":         OCR_BOMB_CADENCE_MS / 1000.0,
        "round_end_banner":  OCR_ROUNDEND_CADENCE_MS / 1000.0,
    }
    for target, exp_period in expected.items():
        sleeps: list[float] = []

        async def _fake_sleep(t: float) -> None:
            sleeps.append(t)
            if len(sleeps) >= 2:
                raise asyncio.CancelledError()

        pipeline._frame_source = FakeFrameSource(n_frames=10)
        with patch("asyncio.sleep", _fake_sleep):
            with pytest.raises(asyncio.CancelledError):
                await pipeline.run_target(target)
        assert abs(sleeps[0] - exp_period) < exp_period * 0.10


# ----- Pure helpers ----- #


def test_event_type_mapping(pipeline: OCRPipeline) -> None:
    assert pipeline._event_type_for("kill_feed") == "kill"
    assert pipeline._event_type_for("score_banner") == "score_change"
    assert pipeline._event_type_for("bomb_icon") == "bomb"
    assert pipeline._event_type_for("round_end_banner") == "round_end"


def test_signal_extraction_score_banner(pipeline: OCRPipeline) -> None:
    good = pipeline._signal_for("score_banner", _OCRResult(text="13 - 7", confidence=1.0, target="score_banner"))
    assert good == {"a_round": 13, "b_round": 7}
    bad = pipeline._signal_for("score_banner", _OCRResult(text="garbage", confidence=1.0, target="score_banner"))
    assert bad is None


def test_signal_extraction_kill_feed_uses_numerical_diff_key(pipeline: OCRPipeline) -> None:
    """BLOCKER-1 regression: kill_feed signal_for emits `numerical_diff`."""
    sig = pipeline._signal_for("kill_feed", _OCRResult(text="", confidence=0.9, target="kill_feed"))
    assert sig is not None
    assert "numerical_diff" in sig
    assert "numerical_diff_delta" not in sig


# ----- Benchmark (VALIDATION 03-OC-01) ----- #


import shutil
_TESS_PRESENT: bool = shutil.which("tesseract") is not None


@pytest.mark.benchmark
@pytest.mark.skipif(not _TESS_PRESENT, reason="tesseract not on PATH")
@pytest.mark.skipif(not _ONNX_MODEL_PRESENT, reason="ONNX model not downloaded")
def test_ocr_benchmark_50_frames(benchmark, emit_fn, executor) -> None:
    """REQ-ocr-pipeline acceptance: 50-frame median decode + inference < 100ms."""
    pipeline = OCRPipeline(
        emit=emit_fn,
        executor=executor,
        frame_source=FakeFrameSource(n_frames=50),
        onnx_model_path=Path("models/en_PP-OCRv4_rec_infer.onnx"),
        skip_onnx_verify=True,
    )
    frame = _png_bytes()
    def _one_kill_feed_call() -> None:
        pipeline._inference(frame, "kill_feed")
    benchmark(_one_kill_feed_call)
    median_ns = benchmark.stats["median"] * 1e9
    assert median_ns < 100 * 1e6, f"kill_feed median {median_ns/1e6:.1f}ms > 100ms"


# ----- WARNING-4 integration probe (deferred per CONTEXT until CTC decoder ships) ----- #


@pytest.mark.skip(
    reason="OCR kill-feed CTC text decoder deferred to Phase 5 calibration "
           "(see 03-CONTEXT.md `<deferred>` block). Re-enable when the full "
           "PaddleOCR character-dictionary CTC decode lands AND the operator "
           "has dropped >=1 hand-labeled frame into "
           "tests/ingestion/fixtures/canned_kill_feed_frames/."
)
@pytest.mark.asyncio
async def test_ocr_kill_feed_drives_numerical_diff_change(
    emit_fn, emitted: list[ArbiterPending], executor, monkeypatch
) -> None:
    """WARNING-4: end-to-end probe that the OCR backend produces a non-zero
    `numerical_diff` ConfirmedEvent against ONE recorded fixture frame.

    Currently @skip because Phase 3 ships only confidence + signal_value=
    {numerical_diff: 0} placeholder until Phase 5 calibration adds the CTC
    text decoder. When the decoder ships, drop the @skip decorator and ensure
    the asserted non-zero numerical_diff comes from a real fixture frame.
    """
    fixture_dir = Path(__file__).parent / "fixtures" / "canned_kill_feed_frames"
    pngs = sorted(fixture_dir.glob("*.png")) if fixture_dir.exists() else []
    if not pngs:
        pytest.skip("No fixture frames yet (operator drops them in Phase 5)")
    pipeline = OCRPipeline(
        emit=emit_fn,
        executor=executor,
        frame_source=FakeFrameSource(n_frames=1),
        onnx_model_path=Path("models/en_PP-OCRv4_rec_infer.onnx"),
        skip_onnx_verify=True,
    )
    frame = pngs[0].read_bytes()
    result = pipeline._inference(frame, "kill_feed")
    assert result is not None
    await pipeline._maybe_emit("kill_feed", result)
    assert len(emitted) == 1
    pending = emitted[0]
    assert pending.source == "ocr"
    assert pending.event_type == "kill"
    # The whole point of the probe: numerical_diff is non-zero from a real frame.
    assert pending.signal_value.get("numerical_diff", 0) != 0, (
        f"Phase 5 CTC decoder must extract numerical_diff from a real frame. "
        f"signal_value={pending.signal_value!r}"
    )
```

Run all OCR tests except benchmark in CI: `pytest tests/ingestion/test_ocr.py -x -k "not benchmark"`.
  </action>
  <verify>
    <automated>pytest tests/ingestion/test_ocr.py -x -k "not benchmark" &amp;&amp; mypy src/ingestion/ocr.py &amp;&amp; ruff check src/ingestion/ocr.py tests/ingestion/test_ocr.py</automated>
  </verify>
  <done>tests/ingestion/test_ocr.py extended with 9 backend tests + 1 WARNING-4 integration probe; all run-by-default tests PASS; benchmark + integration probe + accuracy probe conditionally skip; ruff + mypy clean. Phase 1 + 2 + 03-* prior regressions GREEN.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| frame bytes -> PIL.Image.open | Untrusted-image deserialization on every frame from FrameSource. |
| pytesseract subprocess | `pytesseract.image_to_string` shells out to the system tesseract binary. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-03-05b-01 | T (Tampering) | PIL.Image.open on untrusted bytes | mitigate | `Image.open` is wrapped in try/except in `_inference`; malformed frames log `ocr_inference_error` but do not crash the pipeline. |
| T-03-05b-02 | E (Elevation of privilege) | pytesseract subprocess | mitigate | Image is passed via stdin/temp file; no shell interpolation of frame bytes. |
| T-03-05b-03 | D (Denial of service) | low-confidence kill-feed flood | mitigate | Pitfall 2: confidence < 0.7 drops the event before emit (Test 1 + signal helper). |
| T-03-05b-04 (BLOCKER-1) | T (Tampering) | unknown sentinel keys leaking into MatchState | mitigate | round_end_banner `_signal_for` returns `{}`; the arbiter (03-07b) carries soft-commit info via `ConfirmedEvent.is_soft=True`. Test 3 asserts no `_round_end_soft`/`round_end_text` keys reach the ArbiterPending. |
</threat_model>

<verification>
- `pytest tests/ingestion/test_ocr.py -x -k "not benchmark"` PASSES (all backend tests; integration + accuracy probes @skip per CONTEXT deferred-ideas).
- `mypy src/ingestion/ocr.py` clean.
- `ruff check src/ingestion/ocr.py tests/ingestion/test_ocr.py` clean.
- Phase 1 + 2 + 03-* regressions GREEN.
</verification>

<success_criteria>
Wave 3 plan 03-05b (OCR backends) is COMPLETE when:

1. `src/ingestion/ocr.py` has real `_maybe_emit`, `_inference`, `_infer_onnx`, `_infer_tesseract`, `_signal_for`, `_event_type_for` method bodies (overwriting the 03-05a placeholders).
2. BLOCKER-1 corrected: kill_feed `_signal_for` emits `numerical_diff` key (NOT `numerical_diff_delta`); round_end_banner `_signal_for` returns `{}` (no sentinel keys).
3. `tests/ingestion/test_ocr.py` extended with 9 backend tests + 1 WARNING-4 integration probe (@skip until Phase 5 CTC decoder ships).
4. WARNING-4 deferred entry exists in `03-CONTEXT.md` `<deferred>` block.
5. Phase 1 + 2 + 03-* prior regressions GREEN.
</success_criteria>

<output>
After completion, create `.planning/phases/03-live-ingestion-layer/03-05b-SUMMARY.md` documenting the backend wire-up + the deferred CTC decoder + the BLOCKER-1 corrections.
</output>
