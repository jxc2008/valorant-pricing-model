---
phase: 02-round-event-data
plan: 05
subsystem: pricing
tags: [integration-test, path-b-stub, phase-2-closeout, must-have-3]

# Dependency graph
requires:
  - phase: 02-round-event-data
    provides: models/round_conclusion.json + RoundConclusionLookup.from_json (Plan 02-04)
  - phase: 01-core-pricing-engine
    provides: LiveTheoEngine + HalfRates + MatchState + TheoOutput (Phase 1 frozen surface)
  - phase: 02-round-event-data
    provides: scripts/probe_round_events.py + 02-PROBE-LOG.md (Plan 02-03 — Path A pass)
provides:
  - scripts/ocr_round_events.py (Path B contingency stub — D-10 placeholder, NotImplementedError)
  - tests/pricing/test_live_theo_with_calibrated_round_conclusion.py (must-have #3 e2e integration test)
affects: [04-quoting-layer]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Phase B contingency-stub pattern — module raises NotImplementedError on __main__, anchors a constant from src.config.constants via noqa: F401, and embeds an explicit /gsd-insert-phase escalation handle in the docstring so a future plan-phase can locate the re-entry point without reading other phase artifacts"
    - "Path-C compat integration test — D-12 hard contract locked by asserting empty_lookup.lookup(...) == 0.5 verbatim AND that LiveTheoEngine remains callable with that empty lookup. Engine call MUST still produce a valid TheoOutput in the conviction-clip band even when round_conclusion is the empty (Path C) lookup, so Phase 4's quoting layer inherits a green test for both Path A/B (calibrated) AND Path C (deferred) without code duplication"
    - "MatchState side-encoding distinction surfaced — `side_orient` / `map_side_orients` are 'a_atk' / 'a_def' (Phase 1 BO3State key encoding); `side` is 'atk' / 'def' (lookup-facing). Plan 02-05 PLAN's example used the bare encoding; the integration test honors the actual constructor invariant. Documented in test module docstring so future Phase 3 ingestion-driven MatchState builders preserve the distinction"

key-files:
  created:
    - scripts/ocr_round_events.py
    - tests/pricing/test_live_theo_with_calibrated_round_conclusion.py
  modified: []

key-decisions:
  - "Phase 2 closes with NO src/ surface change — Plan 02-05 ships only a script stub + an integration test. The Phase 1 frozen surface (LiveTheoEngine, MatchState, TheoOutput, RoundConclusionFn Protocol) and the Plan 02-04 additive surface (RoundConclusionLookup.from_json/to_json + rewritten lookup body) are both consumed unchanged, validating the freeze discipline introduced in Phase 1."
  - "Side-encoding correction: the 02-05-PLAN example synthetic state used `side_orient='atk'` / `map_side_orients=('atk','def','atk')`, which mismatches `_RoundPFnImpl._effective_side` (live_theo.py:113 — `'a_def' if starting_side == 'a_atk' else 'a_atk'`). The Plan explicitly authorized the test author to adapt to the actual MatchState invariants. Test uses 'a_atk' / 'a_def' for orient fields and 'atk' for the lookup-facing `side`. Live engine smoke now produces theo_series=0.6199, theo_map=(0.7363, 0.4787, 0.5242), vega=0.0021 — all in [0.01, 0.99] band."
  - "Path B stub line count is 51 (objective said 25-50). The PLAN's contract `min_lines: 25` is a hard floor; the 25-50 prose hint was approximate. Choosing readability and proper line wrapping (ruff line-length=100) over a strict 50-line cap. Acceptance grep contracts honored: 8 'Path B' / 2 'deferred' / 3 'D-10' / 4 'phase 02.5' / 4 'OCR_FRAMES_PER_SECOND' / 1 'NotImplementedError' / 0 OCR-lib imports."

patterns-established:
  - "Phase boundary close-out via integration test, not unit test — Plan 02-05's tests live under tests/pricing/ (not tests/calibration/) because they exercise the Phase 4 INTEGRATION call path (LiveTheoEngine + RoundConclusionLookup), not the Phase 2 calibration internals. Reusable for future phase-boundary plans: name the test `test_<consumer>_with_calibrated_<provider>.py`."
  - "Auto-skip for Path-C scenarios — every test uses `pytest.skip('... Path C deferred')` for the missing-artifact branch. Distinguishes 'cannot run' from 'failed' in CI; locks the D-11 (Path C) and D-12 (Phase 4 hard contract) contracts symmetrically (one explicit Path-C-compat assertion test + four artifact-conditional skips)."

requirements-completed: []  # REQ-round-event-data-pipeline already closed by Plan 02-04

# Metrics
duration: ~25min
completed: 2026-05-01
---

# Phase 02 Plan 05: Path B Stub + Phase-2 Close-Out Integration Test Summary

**Phase 2 close-out: must-have #3 locked by a 5-test integration suite wiring LiveTheoEngine -> calibrated RoundConclusionLookup; Path B contingency stub ships at scripts/ocr_round_events.py.**

## Performance

- **Duration:** ~25 min
- **Tasks:** 2 of 2 (both `type="auto" tdd="true"`)
- **Files created:** 2 (1 stub script + 1 integration test file)
- **Files modified:** 0
- **Test delta:** Phase 2 suite 247 -> 252 passing (+5 new tests)

## Plan-level Status

```
Plan 02-05 status: COMPLETE (2026-05-01)
Phase 02 status:   COMPLETE — all 3 must-haves from ROADMAP §2 satisfied
```

| Task | Type | Status | Commit |
|---|---|---|---|
| 1 — scripts/ocr_round_events.py Path B contingency stub | auto (tdd) | COMPLETE | `7748e9f` |
| 2 — e2e integration test wiring LiveTheoEngine to calibrated lookup | auto (tdd) | COMPLETE | `862c69a` |

## Accomplishments

### Task 1 — Path B contingency stub (commit `7748e9f`)

- **scripts/ocr_round_events.py** (51 lines) — module-level `main()` raises `NotImplementedError` on invocation; importable; zero OCR-engine deps (no cv2 / easyocr / paddleocr / tesseract imports).
- **OCR_FRAMES_PER_SECOND anchor** — imports the constant from `src.config.constants` with `noqa: F401` so phase 02.5 (if invoked) finds the threshold pre-located in constants.py. The error message also prints `OCR_FRAMES_PER_SECOND={value}` so the constant is referenced 4 times across the file (1 import + 3 docstring/error mentions).
- **Escalation handle in docstring** — explicit `/gsd-insert-phase 02.5 --slug path-b-ocr` invocation embedded in the docstring (4 occurrences) so a future planner can locate the re-entry handle by string search. Documents the 5-step escalation: re-read PROBE-LOG, read RESEARCH §"State of the Art" (cv2.matchTemplate not Tesseract for HUD digits), open `/gsd-insert-phase 02.5`, implement the ROI/template-match pipeline at `OCR_FRAMES_PER_SECOND = 1.0`, output the same `data/round_events.sqlite` shape so Plan 02-04's calibrator consumes Path B output unmodified.
- **Source citations** in docstring: D-10, D-11, 02-RESEARCH.md Summary, 02-RESEARCH.md §"State of the Art", `src/config/constants.OCR_FRAMES_PER_SECOND`, ROADMAP.md §2.

### Task 2 — e2e integration test (commit `862c69a`)

- **tests/pricing/test_live_theo_with_calibrated_round_conclusion.py** (168 lines) — 5 pytest tests + 1 helper:
  1. `test_lookup_loads_from_calibrated_json` — `RoundConclusionLookup.from_json(MODEL_PATH)` succeeds.
  2. `test_engine_constructs_with_calibrated_lookup` — `LiveTheoEngine(half_rates=..., round_conclusion=lookup.lookup)` constructs without error.
  3. `test_engine_returns_theo_output_with_calibrated_lookup` — engine call returns a `TheoOutput` with `theo_series`, every `theo_map[i]`, and bounded `vega`/`confidence` in spec.
  4. `test_calibrated_lookup_returns_finite_value_for_in_distribution_key` — `lookup(0, False, "atk", "full", "Lotus")` returns a finite value in [0,1]; calibration produced at least one cells_minimal entry with shrunk() != 0.5 (must-have #3 non-degenerate signal).
  5. `test_path_c_compat_no_json_falls_back_to_baseline` — empty lookup returns 0.5 verbatim AND engine remains callable with it; locks D-12 hard contract.
- **Helper `_synthetic_mid_round_state()`** — representative mid-round state: SEN vs KRÜ, Lotus/Bind/Haven map pool, mid-Map-1 (a_round=6, b_round=5), numerical_diff=0, bomb=False, side="atk", econ="full". Maximizes the chance of hitting a populated cells_minimal cell.
- **All conviction-band assertions** use `CONVICTION_CLIP_LOW` / `CONVICTION_CLIP_HIGH` from `src.config.constants` per CRule 12 (no magic numbers).
- **Path C symmetry** — every test that depends on `models/round_conclusion.json` uses `pytest.skip("... Path C deferred")` for the missing-artifact branch; the Path-C-compat test runs unconditionally (only requires `data/half_win_rates.json`).

### Live smoke (engine + calibrated lookup)

```text
theo_series:  0.6199
theo_map:     (0.7363, 0.4787, 0.5242)   # all in [0.01, 0.99]
vega:         0.0021                      # >= 0
confidence:   0.0                         # in [0, 1]
lookup(0, False, "atk", "full", "Lotus"): 0.5496
empty_lookup(0, False, "atk", "full", "Lotus"): 0.5
cells_minimal populated cells: 22
```

The mid-round prediction (0.5496) is distinct from the side_baseline (0.5256) AND from the uninformative 0.5 prior — must-have #3 satisfied beyond the bare floor.

### Verification (all GREEN)

```text
uv run mypy --strict src/pricing/                              -> 0 issues found in 8 source files
uv run ruff check src/ scripts/ tests/                         -> All checks passed!
uv run pytest tests/probe/ tests/calibration/ tests/pricing/ tests/config/ -x -q -> 252 passed
test -f scripts/ocr_round_events.py                            -> exists
test -f models/round_conclusion.json                           -> exists (324 KB)
test -f tests/pricing/test_live_theo_with_calibrated_round_conclusion.py -> exists
uv run python -c "import scripts.ocr_round_events"             -> exit 0 (importable)
uv run python -m scripts.ocr_round_events                      -> raises NotImplementedError as designed
```

## Phase 2 close-out — must-have coverage (ROADMAP §2)

| Must-have | Status | Evidence |
|---|---|---|
| #1 Path decision recorded with evidence in `02-PROBE-LOG.md` | DONE (Plan 02-03) | Path A passed: 1000 matches, 42586 rounds; D-05 partial-pass NOT triggered |
| #2 `data/round_events.sqlite` populated AND `models/round_conclusion.json` calibrated | DONE (Plans 02-03 + 02-04) | 1000 matches in SQLite; cells_full=1886, cells_no_econ=524, cells_no_map=44, cells_minimal=22, side_baseline={atk: 0.5256, def: 0.4751} |
| #3 Mid-round live_theo calls produce non-degenerate predictions (Path A/B) OR explicit between-round Path C contract | DONE (Plan 02-05) | 5 integration tests: 4 calibrated-path tests + 1 Path-C-compat test (D-12) |

## Path B status

**DEFERRED — Path B stub ships at scripts/ocr_round_events.py.**

- Plan 02-03 confirmed Path A passed (1000 distinct match_id values; floor 500). Path B is contingency only.
- Stub raises `NotImplementedError`; importable; no OCR deps.
- Re-entry handle: `phase 02.5 (path-b-ocr) via /gsd-insert-phase 02.5 --slug path-b-ocr`. The Plan 02-05 stub docstring is the source of truth for the escalation procedure.

## Phase 2 surface delta (cumulative across all 5 plans)

| Component | Phase 1 input | Phase 2 output | Plan |
|---|---|---|---|
| `scripts/probe_round_events.py` | n/a | rib.gg ETL — 1000 matches scraped | 02-03 |
| `data/round_events.sqlite` | n/a | 42586 rounds (CON-round-events-schema) | 02-03 |
| `02-PROBE-LOG.md` | n/a | path decision recorded | 02-03 |
| `scripts/calibrate_round_conclusion.py` | n/a | empirical-Bayes calibrator + CLI | 02-04 |
| `models/round_conclusion.json` | n/a | 324 KB calibrated lookup | 02-04 |
| `RoundConclusionLookup.from_json` | n/a | additive classmethod (D-15) | 02-04 |
| `RoundConclusionLookup.to_json` | n/a | additive instance method (D-15) | 02-04 |
| `RoundConclusionLookup.lookup` body | flat 0.5 | 5-tier fallback chain walk | 02-04 |
| `scripts/ocr_round_events.py` | n/a | Path B contingency stub (D-10) | 02-05 |
| `tests/pricing/test_live_theo_with_calibrated_round_conclusion.py` | n/a | e2e integration test | 02-05 |
| **Phase 1 frozen surface** | LiveTheoEngine, MatchState, TheoOutput, RoundConclusionFn Protocol, _Cell | **UNCHANGED** | n/a |

Total commit count for Plan 02-05: **2** (Task 1: `7748e9f`; Task 2: `862c69a`).

Net new tests in Plan 02-05: **5** (Task 2 only — Task 1 has no test file because the verification is grep-based on the stub itself).

Phase 2 cumulative test count: 252 passing (Plans 02-01 through 02-05; Phase 2 subset 252 out of 263 repo total).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] Plan example synthetic state used invalid side_orient values**

- **Found during:** Task 2 — first import-test of the integration test triggered an immediate KeyError at engine call.
- **Issue:** The Plan's example synthetic state set `side_orient="atk"` and `map_side_orients=("atk", "def", "atk")`. `src/pricing/live_theo.py:113` (`_RoundPFnImpl._effective_side`) returns `"a_def" if starting_side == "a_atk" else "a_atk"` — i.e., the encoding is `a_atk` / `a_def`, not bare `atk` / `def`. The Plan explicitly authorized the test author to adapt to the actual MatchState invariants ("If the synthetic MatchState constructor signature drifts ... adjust the synthetic state builder ... The test's invariants ... are independent of the exact MatchState fields.").
- **Fix:** Test sets `side_orient="a_atk"` and `map_side_orients=("a_atk", "a_def", "a_atk")`. The lookup-facing `side` field stays `"atk"` because the `RoundConclusionFn.lookup` Protocol takes the bare side encoding.
- **Files modified:** `tests/pricing/test_live_theo_with_calibrated_round_conclusion.py` (only).
- **Verification:** All 5 tests pass; full Phase 2 suite 252 GREEN; engine smoke: theo_series=0.6199 in [0.01, 0.99].
- **Commit:** `862c69a`.

### Non-deviation: Path B stub line count

The PLAN's objective hinted at "25-50 line stub". The stub came in at 51 lines after ruff line-length=100 wrapping of the long inline reference strings. The PLAN's hard contract is `min_lines: 25` (artifacts table) which is satisfied by 51. Choosing readability over a strict line-count cap; ruff is GREEN.

## Threat Flags

None — both deliverables are contained within the threat model declared in `02-05-PLAN.md` `<threat_model>`. Mitigations confirmed:
- T-02-05-01 (stub tampering): stub raises immediately; no logic surface to subvert. Verified by `python -m scripts.ocr_round_events` exiting with NotImplementedError.
- T-02-05-02 (test fixture PII): `_synthetic_mid_round_state` uses public team names (SEN, KRÜ) and standard map names; no API tokens; no PII.
- T-02-05-03 (test runtime DoS): integration test runs 5 short tests (<2 seconds total when artifact present; <0.1 seconds when skipped); no live HTTP.
- T-02-05-04 (engine-construction spoofing): `LiveTheoEngine` is `mypy --strict`-typed; tests use imported types directly, no string-keyed dispatch.

## TDD Gate Compliance

Plan-level type is `execute` (not `tdd`), so plan-level RED/GREEN/REFACTOR gates do not apply. Each task is `type="auto" tdd="true"` — RED phase satisfied by the in-task `<behavior>` test invariants which were authored before the implementation; GREEN satisfied by the verification block (252 passing, ruff clean, mypy clean).

## Self-Check: PASSED

- `scripts/ocr_round_events.py` — FOUND (commit `7748e9f`)
- `tests/pricing/test_live_theo_with_calibrated_round_conclusion.py` — FOUND (commit `862c69a`)
- Commit `7748e9f` — FOUND in `git log`
- Commit `862c69a` — FOUND in `git log`
- `mypy --strict src/pricing/` -> 0 issues found in 8 source files
- `ruff check src/ scripts/ tests/` -> All checks passed!
- `pytest tests/probe/ tests/calibration/ tests/pricing/ tests/config/` -> 252 passed
- `python -c "import scripts.ocr_round_events"` -> exit 0
- `python -m scripts.ocr_round_events` -> raises NotImplementedError (D-10 message visible)
- `lookup(0, False, "atk", "full", "Lotus")` smoke -> 0.5496 (calibrated, non-degenerate)
- `RoundConclusionLookup().lookup(0, False, "atk", "full", "Lotus")` -> 0.5 (Path-C contract)
