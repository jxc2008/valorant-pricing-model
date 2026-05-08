---
phase: 03-live-ingestion-layer
plan: "05"
subsystem: ingestion
tags: [ocr, tesseract, async-workers, threadpool, frame-source-protocol, dec-024-v2, d-11-roi-placeholders, d-12-bomb-gate, d-13-quarantine, d-14-computed-time]

requires:
  - phase: 03-live-ingestion-layer
    provides: 03-01 MatchState v2 (bomb_planted / attackers_alive / defenders_alive); 03-03 Arbiter (3 deques + PendingEvent + 6-stage timestamps)
provides:
  - "src/ingestion/ocr.py — 4 async cadence workers (run_score_banner_worker / run_bomb_icon_worker / run_round_end_worker / run_post_plant_alive_worker) + 4 sync decode helpers + module-init pytesseract.tesseract_cmd config + shared _OCR_EXECUTOR = ThreadPoolExecutor(max_workers=2)."
  - "src/ingestion/frame_source.py — FrameSource Protocol + StubFrameSource (tests) + YouTubeFrameSource skeleton (TODO(phase-4) raises NotImplementedError)."
  - "src/ingestion/__init__.py — public re-exports: 4 worker functions + FrameSource / StubFrameSource / YouTubeFrameSource."
  - "9 new src/config/constants.py constants: 4 OCR cadences (250/500/100/250 ms), OCR_DECODE_BUDGET_MS=100, BROADCAST_TEMPLATE_VERSION='vct-2026-international', 6 placeholder ROI tuples + 2 tesseract config strings (PSM 10 single + PSM 7 multi)."
  - "scripts/dump_roi_overlay.py — operator helper that draws labeled colored rectangles for every configured ROI on a captured broadcast frame (read-only against src/)."
  - "Tesseract OCR pipeline as the v2 visual-signal source (DEC-024 v2). Post-plant alive widget worker is THE v2 replacement for the cut killfeed per CONTEXT §specifics."
affects: [03-08-e2e-gate]

tech-stack:
  added: []
  patterns:
    - "4 async cadence workers, each is an infinite while-True asyncio loop with cadence_s sleep at end. Per-cycle: capture t_observed (wall_time) before OCR work; dispatch decode helpers to _OCR_EXECUTOR via loop.run_in_executor; capture t_ingested (mono_ns) after; push PendingEvent into the appropriate Arbiter deque only when the decoded value differs from arbiter.state."
    - "Shared ThreadPoolExecutor(max_workers=2) singleton (RESEARCH §Pattern 4). pytesseract.image_to_string spawns subprocess.Popen for the tesseract binary which releases the GIL; max_workers > 2 hits subprocess fork pressure."
    - "D-12 hard-gate on post_plant_alive worker: yields with await asyncio.sleep(cadence_s) when arbiter.state.bomb_planted=False; saves ~30ms/cycle CPU during the ~80% of match runtime when no plant is active. Worker only does OCR work during the 45s post-plant window."
    - "D-13 parse-failure path: decode helpers (_decode_alive_digit, _decode_score_digit) return None when Tesseract returns text outside the configured whitelist; workers log a warning and yield the cycle without pushing an event. State carries forward via MatchState only-changed-fields semantics. The arbiter's existing 5s staleness kill-switch (KILL_SWITCH_STALENESS_S) handles extended degradation — conflating with a per-frame quarantine PendingEvent would race against the soft-commit contract."
    - "D-14 time_left_s is COMPUTED downstream (Phase 4 mode-selector reads time.time() − t_bomb_plant_observed clipped to [0, 45]); this plan does NOT add a fourth OCR target for the timer per scope discipline."
    - "Bomb-icon and round-end workers fire only on transition (False→True), not on steady-state True. Single-source soft-commit per arbiter rules; the next score commit hard-confirms (Phase 4 mode-selector handles soft-commit-vs-score-mismatch via IDLE quoting, not arbiter rollback)."
    - "Score-banner worker emits the FULL {a_round, b_round} fields_proposed shape (not diff-only) to match the rib.gg poller's emission shape — the arbiter's signature-grouping over fields_proposed.items() then trips the ≥2-source cross-confirm rule (DEC-006 v2) just as the 03-04 SUMMARY documented for the rib.gg arm."
    - "DEC-024 v2 grep guard: src/ingestion/ocr.py contains no kill_feed / ult_orb / economy_credits / onnx / paddleocr / ctc_decode substrings. The module docstring documents the guard without using the literal forbidden tokens (paraphrased so grep doesn't trip on the comment)."

key-files:
  created:
    - "src/ingestion/ocr.py — 4 async OCR workers + 4 sync decode helpers + module-init pytesseract.tesseract_cmd + _OCR_EXECUTOR (~440 LOC)."
    - "src/ingestion/frame_source.py — FrameSource Protocol + StubFrameSource + YouTubeFrameSource skeleton (~75 LOC)."
    - "scripts/dump_roi_overlay.py — operator HUD-calibration helper, CLI: --frame INPUT.png --output ANNOTATED.png (~99 LOC)."
  modified:
    - "src/config/constants.py — appended 'Phase 3 — OCR pipeline (DEC-024 v2 / D-11 / D-12 / D-13 / D-14)' section with 9 new Final-typed constants plus TODO(operator) recalibrate markers on each ROI."
    - "src/ingestion/__init__.py — added re-exports for FrameSource, StubFrameSource, YouTubeFrameSource AND the 4 OCR worker functions."
    - "tests/ingestion/conftest.py — synthetic_frame_factory upgraded from Wave-0 zero-frame stub to actually draw cv2.putText digits (white-on-black, FONT_HERSHEY_SIMPLEX, scale 1.5, thickness 3) at the lower-left of each provided ROI. Now accepts att / def_ / score_a / score_b kwargs."
    - "tests/config/test_constants.py — appended 14 new constant entries (9 OCR + the 6 ROIs share 1 'tuple' EXPECTED_TYPES key) to EXPECTED_NAMES + EXPECTED_TYPES allow-list in the same commit as the constants definitions (Wave 3A SUMMARY prophylactic)."
    - "tests/ingestion/test_ocr_score.py — 2 GREEN tests replacing 2 Wave-0 xfail stubs (test_decode_benchmark_p50 over 56 synthetic frames; test_decode_correctness on score=13)."
    - "tests/ingestion/test_ocr_bomb.py — 2 GREEN tests replacing 2 Wave-0 xfail stubs (test_decode_benchmark_p50 over 50 calls of the HSV-mask heuristic; test_decode_correctness on red ROI True / black ROI False)."
    - "tests/ingestion/test_ocr_round_end.py — 2 RUNTIME-XFAIL tests with explicit operator TODO (Phase 3.5 calibration ships fixtures/round_end_banner_template.png and swaps _detect_round_end_banner to cv2.matchTemplate)."
    - "tests/ingestion/test_ocr_alive_widget.py — 2 GREEN tests replacing 2 Wave-0 xfail stubs (test_decode_benchmark_p50 over 60 synthetic frames; test_parse_failure_quarantine on empty ROI)."

key-decisions:
  - "Tesseract reads synthetic frames cleanly at the placeholder ROIs. Probe runs on representative inputs measured: alive-digit decode median ~140ms (driven by the first-call subprocess fork), score-digit decode median ~110ms — but across the 50/56/60-sample benchmarks the p50 lands well under 100ms because the fork amortizes across calls in the same process. Net: all the non-round-end benchmarks land GREEN against the placeholders."
  - "The round-end banner is the one HUD target whose synthetic frame can't trivially be built without an operator-supplied reference image. Per the plan's Task 3 fallback, both round-end tests xfail with operator-recalibrate TODO. Phase 3.5 calibration ships fixtures/round_end_banner_template.png and swaps the placeholder gray-pixel-content threshold for cv2.matchTemplate."
  - "synthetic_frame_factory accepts BOTH att/def_ AND score_a/score_b kwargs in the same call signature (each independent). The plan-body sketch added them piecewise; consolidating in one factory keeps test files terse and avoids per-test fixture overrides."
  - "Bomb-icon worker keeps a local `last_bomb_state` mirror rather than reading arbiter.state.bomb_planted to decide on transitions. Trade-off: mirror is a single-cycle staleness vs reading arbiter.state — but reading arbiter.state would couple worker continuity to Phase-4 mode-flips that could induce phantom transitions. Local mirror is the conservative pick."
  - "Top-level Exception catch in each worker (BLE001 noqa-tagged) so a transient cv2/pytesseract glitch doesn't kill the worker permanently. The asyncio.CancelledError bypass keeps task cancellation clean (no swallowing). Pattern matches scoreboard.py's resilience boundary from 03-04."
  - "Local `_OCR_EXECUTOR` module-level singleton vs per-task injection. Singleton matches RESEARCH §Pattern 4; injecting an executor would let test isolation be tighter, but the workers are stateless enough that the singleton is fine for both tests and production. Phase 5 paper-trade infrastructure can monkey-patch the module-level reference if it needs per-match isolation."
  - "Same-commit Rule-3 prophylactic for tests/config/test_constants.py allow-list (Wave 3A SUMMARY documented this exact failure mode when new constants land). Updated EXPECTED_NAMES + EXPECTED_TYPES (added 'tuple' for the 6 ROI entries) in the SAME commit as the constants definition (Task 1)."
  - "Module docstring for ocr.py paraphrases the DEC-024 v2 cuts ('killfeed parsing', 'ult tracking', etc) without using the literal forbidden substrings ('kill_feed', 'ult_orb', etc) so the grep guard doesn't trip on the comment that documents the guard. Initial draft used the literal tokens in a code-fenced grep example and tripped the guard immediately on first verify."

patterns-established:
  - "FrameSource Protocol abstraction lets the 4 OCR workers run against StubFrameSource in tests + Phase-4 YouTubeFrameSource in production without conditional code. Stub raises RuntimeError on latest_frame() before push() (loud failure preferred over silent hang); YouTube skeleton raises NotImplementedError in __init__ (loud failure preferred over silent infinite block)."
  - "Per-worker top-level Exception catch + log + await asyncio.sleep(cadence_s) — mirrors scoreboard.py's resilience boundary. Keeps a transient OCR glitch from killing the worker; the cycle-failure pattern composes cleanly with the arbiter's 5s staleness kill-switch."
  - "Operator-gate placeholder pattern: ROI tuples ship with TODO(operator) comments, default to best-estimate values for 1920x1080 VCT international broadcast, and a dump_roi_overlay.py helper reads the constants and visually annotates a captured broadcast frame. Constants + tests + helper land in the same plan; operator visual recalibration is a separate (later) commit that doesn't require code changes downstream of constants.py."

requirements-completed: [REQ-ocr-pipeline]

# Metrics
duration: 10 min
completed: 2026-05-08
---

# Phase 3 Plan 05: OCR Pipeline Summary

**Tesseract OCR pipeline (DEC-024 v2 / D-11 / D-12 / D-13 / D-14) — 4 async cadence workers (run_score_banner_worker / run_bomb_icon_worker / run_round_end_worker / run_post_plant_alive_worker) dispatching pytesseract decode helpers to a shared ThreadPoolExecutor(max_workers=2), pushing PendingEvents into Arbiter.score_changes / .bomb_events / .round_end_events; FrameSource Protocol + StubFrameSource for tests; 9 new ingestion constants with TODO(operator) ROI placeholders + scripts/dump_roi_overlay.py operator helper — REQ-ocr-pipeline GREEN.**

## Performance

- **Duration:** 10 min
- **Started:** 2026-05-08T19:49:09Z
- **Completed:** 2026-05-08T19:58:58Z
- **Tasks:** 4
- **Files created:** 3 (src/ingestion/ocr.py, src/ingestion/frame_source.py, scripts/dump_roi_overlay.py)
- **Files modified:** 6 (src/config/constants.py, src/ingestion/__init__.py, tests/ingestion/conftest.py, tests/config/test_constants.py, tests/ingestion/test_ocr_*.py rewrites x4)

## Accomplishments

- **REQ-ocr-pipeline GREEN.** SPEC §3 acceptance #5 satisfied for the non-round-end targets: 4 OCR workers exist; per-target benchmarks (alive widget, score banner, bomb icon) run p50 under OCR_DECODE_BUDGET_MS=100ms against placeholder ROIs in unit tests; round-end banner xfails with explicit Phase 3.5 operator-recalibrate TODO. Grep guard PASSES.
- **DEC-024 v2 grep guard PASSED.** `grep -E "kill_feed|ult_orb|economy_credits|onnx|paddleocr|ctc_decode" src/ingestion/ocr.py` returns 0 hits — DEC-024 v2 cuts (kill-feed CV, ult tracking, mid-round economy inference, ONNX, PaddleOCR, CTC decoders) are structurally absent from the OCR module. Module docstring paraphrases the prohibited concepts without using the literal grep tokens.
- **D-11 placeholder ROI strategy honored.** Each ROI ships with `# TODO(operator): recalibrate against first VCT 2026 broadcast frame` immediately above the constant; coordinates default to operator-pre-cleared estimates for 1920x1080 VCT international broadcast. scripts/dump_roi_overlay.py operator helper reads the constants and produces an annotated PNG for visual verification.
- **D-12 hard-gate on post_plant_alive worker.** `if not arbiter.state.bomb_planted: await asyncio.sleep(cadence_s); continue` saves ~30ms/cycle CPU during the ~80% of match runtime when no plant is active. Worker only spins up the OCR work during the 45s post-plant window.
- **D-13 parse-failure path tested.** test_parse_failure_quarantine asserts that an empty ROI returns None from `_decode_alive_digit`; workers log + carry-forward (the 5s staleness kill-switch handles extended degradation, no per-frame quarantine PendingEvent).
- **D-14 time_left_s NOT OCR'd.** Computed downstream by Phase 4 mode-selector from `t_bomb_plant_observed` — no fourth OCR target. Discipline preserved.
- **mypy clean.** `mypy --strict src/state/ src/pricing/` clean (9 source files); `mypy src/ingestion/` (gradual) clean (7 source files). Full annotations on all new code.
- **ruff clean.** `ruff check src/ tests/ scripts/` clean across the repo (no isort / lint regressions introduced).
- **Phase 0 + 1 + 2 + 03-00..03-04 regression GREEN.** 284 passed / 19 xfailed (xfails: round-end-banner placeholder x2, text-listener stub x3, E2E gate x3, calibrator-flavored x10, plus 1 misc). 0 failures.
- **Tesseract empirically validates against synthetic frames.** Probe runs on placeholder ROIs read 'att=3' as 3 in 140ms (first-call) settling under 100ms p50 across 60 frames; 'score=13' reads as 13 in 110ms first-call settling under 100ms p50 across 56 frames. Real broadcast frames will need operator recalibration BUT placeholder budget is met today.

## Task Commits

1. **Task 1: Add OCR constants + create FrameSource Protocol + StubFrameSource** — `ebbb840` (feat)
2. **Task 2: Tesseract OCR pipeline with 4 async workers (REQ-ocr-pipeline / DEC-024 v2)** — `b0acf99` (feat)
3. **Task 3: OCR worker tests + benchmarks (xfail placeholder ROIs per D-11)** — `d61b1c1` (test)
4. **Task 4: scripts/dump_roi_overlay.py operator ROI calibration helper** — `6f825fd` (feat)

**Plan metadata commit:** to follow (this SUMMARY.md + STATE.md + ROADMAP.md update).

## Files Created/Modified

### Created
- `src/ingestion/ocr.py` (~440 LOC) — module docstring (DEC-024 v2 cuts paraphrased), 4 sync decode helpers (_preprocess_digit_roi, _decode_alive_digit, _decode_score_digit, _detect_bomb_plant_icon, _detect_round_end_banner), 4 async cadence workers (run_score_banner_worker @ 250ms, run_bomb_icon_worker @ 500ms, run_round_end_worker @ 100ms, run_post_plant_alive_worker @ 250ms with D-12 hard-gate), module-init pytesseract.tesseract_cmd config, _OCR_EXECUTOR ThreadPoolExecutor(max_workers=2).
- `src/ingestion/frame_source.py` (~75 LOC) — FrameSource Protocol + StubFrameSource (tests; raises if no frame pushed) + YouTubeFrameSource skeleton (raises NotImplementedError with phase-4 TODO).
- `scripts/dump_roi_overlay.py` (~99 LOC) — operator helper drawing 6 labeled colored rectangles + BROADCAST_TEMPLATE_VERSION stamp on a captured 1920x1080 broadcast frame; CLI: `--frame INPUT.png --output ANNOTATED.png`.

### Modified
- `src/config/constants.py` — appended Phase 3 OCR pipeline section: 4 cadences (OCR_SCORE_BANNER_CADENCE_MS=250, OCR_BOMB_ICON_CADENCE_MS=500, OCR_ROUND_END_CADENCE_MS=100, OCR_POST_PLANT_ALIVE_CADENCE_MS=250), OCR_DECODE_BUDGET_MS=100, BROADCAST_TEMPLATE_VERSION="vct-2026-international", 6 ROI tuples with TODO(operator) recalibrate comments, TESS_CONFIG_DIGIT_SINGLE (PSM 10) + TESS_CONFIG_DIGIT_MULTI (PSM 7).
- `src/ingestion/__init__.py` — public re-exports added: FrameSource, StubFrameSource, YouTubeFrameSource, run_score_banner_worker, run_bomb_icon_worker, run_round_end_worker, run_post_plant_alive_worker.
- `tests/ingestion/conftest.py` — synthetic_frame_factory upgraded to draw cv2.putText digits at lower-left of each provided ROI. Accepts att / def_ / score_a / score_b kwargs (independent rendering for each).
- `tests/config/test_constants.py` — EXPECTED_NAMES + EXPECTED_TYPES extended with 9 + 9 = 14 new entries (the 6 ROI tuples share the 'tuple' type entry; 8 individual int/str entries cover the cadences + budget + version + 2 tesseract config strings).
- `tests/ingestion/test_ocr_score.py` — 2 GREEN tests replacing Wave-0 xfail stubs.
- `tests/ingestion/test_ocr_bomb.py` — 2 GREEN tests replacing Wave-0 xfail stubs.
- `tests/ingestion/test_ocr_round_end.py` — 2 RUNTIME-XFAIL tests with operator TODO (Phase 3.5 fixture).
- `tests/ingestion/test_ocr_alive_widget.py` — 2 GREEN tests replacing Wave-0 xfail stubs.

## Decisions Made

- **Module docstring paraphrases the DEC-024 v2 cuts without the literal grep tokens.** Initial draft used the literal forbidden substrings (`kill_feed`, `ult_orb`, etc) inside a code-fenced grep example block; the same grep guard tripped on the comment that was documenting the guard. Resolution: paraphrase ('killfeed parsing', 'ult tracking', etc) and reference the guard's command without echoing the literal tokens.
- **`event_type: EventType = "bomb_plant" if detected else "bomb_defuse"` explicit annotation.** Mypy narrows the inferred type to `str` on a ternary across two Literal-equivalent strings; the annotation pins it to the EventType Literal alias so PendingEvent's frozen dataclass type-checks.
- **Bomb-icon worker keeps local `last_bomb_state` mirror, doesn't read arbiter.state.bomb_planted.** The mirror is single-cycle stale by construction; reading arbiter.state would couple worker transitions to Phase-4 mode-flips that could induce phantom edge-firings. Local mirror is the safer pick.
- **All decode helpers run inside _OCR_EXECUTOR via loop.run_in_executor; the cadence-loop body itself is async + non-blocking.** Pattern matches RESEARCH §Pattern 4 — pytesseract.image_to_string is a blocking subprocess.Popen call; running it in the cadence loop directly would block the event loop for ~10-100ms per frame, starving the other workers + the arbiter tick.
- **Same-commit Rule-3 prophylactic for tests/config/test_constants.py allow-list.** Wave 3A SUMMARY documented this exact failure when new constants land but the EXPECTED_NAMES allow-list isn't updated in the same commit. Updated in Task 1 alongside the constants definitions.
- **synthetic_frame_factory takes both att/def_ AND score_a/score_b kwargs in one signature.** Plan-body sketch added them piecewise across the test files; consolidating in conftest keeps test files terse and avoids per-test fixture overrides.
- **`_detect_round_end_banner` gray-pixel-content threshold is the Phase 3 placeholder; both round-end tests xfail.** Building a synthetic round-end banner frame to exercise the placeholder reliably requires either operator-supplied banner template OR a sophisticated synthetic banner mock — neither in scope for Plan 03-05. The xfail with explicit Phase 3.5 TODO is the clean signal for downstream calibration work.
- **YouTubeFrameSource.__init__ raises NotImplementedError immediately rather than lazy-raising on first latest_frame() call.** Loud failure on construction is easier to debug than the alternative async-context lazy raise; tests that accidentally instantiate YouTubeFrameSource fail in stack-trace position 1 rather than 50 frames deep in the cadence loop.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] DEC-024 v2 grep guard initially tripped because the module docstring's example grep command literally included the forbidden tokens.**
- **Found during:** Task 2 verify (`grep -E "kill_feed|..." src/ingestion/ocr.py` returned a hit on the docstring line that documented the guard).
- **Issue:** Module docstring contained a code-fenced example: `! grep -E "kill_feed|ult_orb|economy_credits|onnx|paddleocr|ctc_decode" src/ingestion/ocr.py` — the literal substrings inside that example tripped the guard the example was documenting.
- **Fix:** Paraphrased the docstring to use 'killfeed parsing' / 'ult tracking' / 'mid-round economy inference' / 'ONNX runtime' / 'PaddleOCR' / 'CTC decoders' (full English phrasing instead of grep tokens) and reference the guard command without echoing the literal substrings ('A repo-wide grep guard verifies absence of the canonical forbidden tokens').
- **Files modified:** `src/ingestion/ocr.py`.
- **Verification:** `grep -E "..." src/ingestion/ocr.py` returns no matches.
- **Committed in:** `b0acf99` (Task 2 commit, pre-push).

**2. [Rule 1 - Bug] Mypy `Argument "event_type" to "PendingEvent" has incompatible type "str"; expected "Literal[...]"`.**
- **Found during:** Task 2 verify (`mypy src/ingestion/`).
- **Issue:** `event_type = "bomb_plant" if detected else "bomb_defuse"` — mypy infers the type as `str` even though both branches are Literal-equivalent.
- **Fix:** Added explicit annotation `event_type: EventType = ...` and added `EventType` to the imports from `src.ingestion.events`.
- **Files modified:** `src/ingestion/ocr.py`.
- **Verification:** `mypy src/ingestion/` clean.
- **Committed in:** `b0acf99` (Task 2 commit, pre-push).

**3. [Rule 3 - Blocking] Ruff UP037 'Remove quotes from type annotation' on the `arbiter: "Arbiter"` and `frame_source: "FrameSource"` parameter annotations.**
- **Found during:** Task 2 verify (`ruff check src/ingestion/`).
- **Issue:** With `from __future__ import annotations` active, all string-quoted type annotations are redundant; ruff UP037 flags them. The TYPE_CHECKING-guarded imports were already in place; the quotes were vestigial from an early draft that didn't have `from __future__ import annotations`.
- **Fix:** Removed quotes (`arbiter: Arbiter`, `frame_source: FrameSource`) — works correctly because `from __future__ import annotations` defers evaluation.
- **Files modified:** `src/ingestion/ocr.py`.
- **Verification:** `ruff check src/ingestion/` clean.
- **Committed in:** `b0acf99` (Task 2 commit, pre-push).

**4. [Rule 3 - Blocking] Duplicate `from __future__ import annotations` after Edit operation.**
- **Found during:** Task 2 verify (`ruff check src/ingestion/ocr.py` flagged isort I001 — incorrect import ordering due to the duplicate).
- **Issue:** When fixing deviation 2, the Edit added `from __future__ import annotations` at the top of the imports block, but the file already had it from the original Write — landed twice.
- **Fix:** Removed the duplicate; one `from __future__ import annotations` at the top of the imports block.
- **Files modified:** `src/ingestion/ocr.py`.
- **Verification:** `ruff check` clean.
- **Committed in:** `b0acf99` (Task 2 commit, pre-push).

---

**Total deviations:** 4 auto-fixed (1 bug, 1 type bug, 2 blocking lint). All discovered during the same Task 2 verify run; all fixed inline before the Task 2 commit. None of the fixes changed plan intent — all were one-shot bridge-the-gap-to-typecheck-and-lint corrections.

**Impact on plan:** None. The grep guard is the canonical project-level constraint for this plan; deviation 1 was the most consequential (a literal-token-in-example bug) and is now structurally absent from the file. Deviations 2-4 were standard typing-and-style corrections.

## Authentication Gates

None — no external services touched. Tesseract binary path is read from `TESSERACT_CMD` env (Windows) or the system PATH (Linux/macOS); the placeholder ROIs are placeholder pixel coordinates, not authentication credentials. The operator-pre-cleared coordinates per the environment notes were taken directly from the plan body and the operator gate was already authorized.

## Issues Encountered

None blocking. All 4 deviations were auto-fixed inline within Task 2 before commit. The probe of synthetic frames against the placeholder ROIs surfaced an interesting empirical: Tesseract reads the placeholder-ROI synthetic digits cleanly because the cv2.putText render position aligns with the placeholder ROI's lower-left corner — meaning the benchmarks GREEN against placeholders even though the placeholders aren't pinned against real broadcast frames. Operator recalibration via dump_roi_overlay.py is still required before paper-trade bring-up; the GREEN unit-test result is a sanity check on the OCR pipeline, not a substitute for visual ROI verification.

## User Setup Required

For paper-trade bring-up (Phase 4/5):
1. Install Tesseract 5.x system binary (Windows: `choco install tesseract`; Linux CI: `apt-get install -y tesseract-ocr`; macOS dev: `brew install tesseract`).
2. Set `TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe` in `.env` for Windows host.
3. Run `python scripts/dump_roi_overlay.py --frame <captured_vod_frame.png> --output <annotated.png>` against a representative VCT broadcast frame; visually verify each rectangle lands on the right HUD element.
4. If any rectangle is off, edit `src/config/constants.py` (the 6 ROI tuples) and bump `BROADCAST_TEMPLATE_VERSION`; re-run dump_roi_overlay.py until satisfied; commit the updated constants + the annotated PNG to `fixtures/calibration/` for forensic record.
5. Phase 3.5 calibration ships `fixtures/round_end_banner_template.png` (operator-supplied reference image) and swaps `_detect_round_end_banner` to `cv2.matchTemplate`; flip the 2 round-end xfails to hard assertions at that point.

## Next Phase Readiness

Plan 03-06 (text-listener) is unblocked and orthogonal — Twitter v2 streaming pushes `PendingEvent(source="twitter", event_type="score_change", ...)` into `arbiter.score_changes` for soft cross-confirm against ribgg + ocr_score. The 4 OCR workers are idle peers; no shared state.

Plan 03-08 (E2E gate) is unblocked:
- `from src.ingestion import (Arbiter, StubFrameSource, run_score_banner_worker, run_bomb_icon_worker, run_round_end_worker, run_post_plant_alive_worker, run_scoreboard_poller)` resolves.
- The synthetic E2E test in `tests/ingestion/test_e2e.py` can drive a `StubFrameSource` push schedule + an `aioresponses`-mocked rib.gg poller through `Arbiter` → `MatchState` → `live_theo`; the 4 OCR workers fan out into the 3 arbiter deques alongside the rib.gg arm.
- `OCR_DECODE_BUDGET_MS=100` is the hot-path floor for the E2E `test_bomb_detect_p50` assertion (bomb-detect → state-commit p50 < 100ms per SPEC §6).

Phase 4 (quoting) consumers:
- Post-plant alive widget worker is THE replacement signal for the cut killfeed; every v2 mid-round dynamic flows through `attackers_alive`/`defenders_alive` updates per CONTEXT §specifics. Phase 4's `POST_PLANT_QUOTE` mode reads the live MatchState that this plan's worker keeps fresh during the 45s window.

## Self-Check: PASSED

- `src/ingestion/ocr.py` exists on disk (verified via Bash `ls`).
- `src/ingestion/frame_source.py` exists on disk.
- `scripts/dump_roi_overlay.py` exists on disk.
- `src/ingestion/__init__.py` re-exports the 4 worker functions + 3 frame-source classes (verified via `python -c "from src.ingestion import StubFrameSource, run_post_plant_alive_worker; print(run_post_plant_alive_worker, StubFrameSource)"`).
- `src/config/constants.py` declares all 9 new constants — `OCR_POST_PLANT_ALIVE_CADENCE_MS=250`, `TESS_CONFIG_DIGIT_SINGLE` ends with `012345`, `BROADCAST_TEMPLATE_VERSION="vct-2026-international"` — verified via importable smoke command.
- All 4 task commits reachable on git: `ebbb840` (Task 1), `b0acf99` (Task 2), `d61b1c1` (Task 3), `6f825fd` (Task 4).
- `pytest tests/ingestion/test_ocr_score.py tests/ingestion/test_ocr_bomb.py tests/ingestion/test_ocr_round_end.py tests/ingestion/test_ocr_alive_widget.py -v --no-cov` -> 6 passed, 2 xfailed, 0 failed.
- `pytest tests/ -x --no-cov -k "not test_calibrate_round_conclusion"` -> 284 passed / 19 xfailed / 0 failed.
- `mypy --strict src/state/ src/pricing/` clean (9 source files); `mypy src/ingestion/` clean (7 source files, gradual).
- `ruff check src/ tests/ scripts/` clean ('All checks passed!').
- DEC-024 v2 grep guard: `grep -E "kill_feed|ult_orb|economy_credits|onnx|paddleocr|ctc_decode" src/ingestion/ocr.py` returns no matches (PASS).
- `python scripts/dump_roi_overlay.py --help` runs cleanly with the documented CLI signature.

---
*Phase: 03-live-ingestion-layer*
*Completed: 2026-05-08*
