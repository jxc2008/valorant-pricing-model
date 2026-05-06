---
phase: 03
slug: live-ingestion-layer
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-06
---

# Phase 03 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.0+, hypothesis 6.100+, pytest-cov 5.0+ (existing) + `pytest-asyncio>=0.23` (NEW dev dep) + `aioresponses>=0.7.6` (NEW dev dep) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (already configured); add `[tool.mypy.overrides]` for `src.state.*` strict |
| **Quick run command** | `uv run pytest tests/ingestion/ -x --no-cov -k 'not benchmark'` |
| **Full suite command** | `uv run pytest --cov=src --cov-report=term-missing` |
| **Estimated runtime** | ~30s quick (per-task) / ~3-5 min full suite incl. benchmarks |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ingestion/test_<module>.py -x --no-cov` (target: <30s; benchmarks excluded via `-k 'not benchmark'`)
- **After every plan wave:** Run `uv run pytest tests/ -x` (full suite without coverage report; benchmarks included)
- **Before `/gsd:verify-work`:** `uv run pytest --cov=src --cov-report=term-missing && uv run mypy --strict src/pricing src/state && uv run ruff check src tests scripts` — full suite GREEN, mypy strict clean on both packages, ruff clean
- **Max feedback latency:** ~30s

---

## Per-Task Verification Map

> Wave/plan/task IDs are placeholders pending plan generation; updated post-planner. Tests below come from RESEARCH §Validation Architecture.

| Test File / Method | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|--------------------|------|-------------|-----------|-------------------|-------------|--------|
| `tests/ingestion/test_match_state.py::test_seq_id_strictly_monotonic` | 1 | REQ-match-state-engine | property | `uv run pytest tests/ingestion/test_match_state.py::test_seq_id_strictly_monotonic -x` | ❌ W0 | ⬜ pending |
| `tests/ingestion/test_match_state_jsonl.py::test_replay_determinism` | 1 | REQ-match-state-engine | unit | `uv run pytest tests/ingestion/test_match_state_jsonl.py::test_replay_determinism -x` | ❌ W0 | ⬜ pending |
| `mypy --strict src/state/` | 1 | REQ-match-state-engine | static | `uv run mypy src/state/` | ❌ W0 | ⬜ pending |
| `tests/ingestion/test_scoreboard.py::test_poller_emits_typed_events` | 3B | REQ-scoreboard-polling | integration (aioresponses) | `uv run pytest tests/ingestion/test_scoreboard.py::test_poller_emits_typed_events -x` | ❌ W0 | ⬜ pending |
| `tests/ingestion/test_scoreboard.py::test_retry_honors_retry_after` | 3B | REQ-scoreboard-polling | integration | `uv run pytest tests/ingestion/test_scoreboard.py::test_retry_honors_retry_after -x` | ❌ W0 | ⬜ pending |
| `tests/ingestion/test_ocr_score.py::test_decode_benchmark_p50` | 3C | REQ-ocr-pipeline | benchmark | `uv run pytest tests/ingestion/test_ocr_score.py -k benchmark -x` | ❌ W0 | ⬜ pending |
| `tests/ingestion/test_ocr_bomb.py::test_decode_benchmark_p50` | 3C | REQ-ocr-pipeline | benchmark | `uv run pytest tests/ingestion/test_ocr_bomb.py -k benchmark -x` | ❌ W0 | ⬜ pending |
| `tests/ingestion/test_ocr_round_end.py::test_decode_benchmark_p50` | 3C | REQ-ocr-pipeline | benchmark | `uv run pytest tests/ingestion/test_ocr_round_end.py -k benchmark -x` | ❌ W0 | ⬜ pending |
| `tests/ingestion/test_ocr_alive_widget.py::test_decode_benchmark_p50` | 3C | REQ-ocr-pipeline | benchmark | `uv run pytest tests/ingestion/test_ocr_alive_widget.py -k benchmark -x` | ❌ W0 | ⬜ pending |
| `tests/ingestion/test_ocr_alive_widget.py::test_parse_failure_quarantine` | 3C | REQ-ocr-pipeline | unit | `uv run pytest tests/ingestion/test_ocr_alive_widget.py::test_parse_failure_quarantine -x` | ❌ W0 | ⬜ pending |
| Grep guard `kill_feed\|ult_orb\|economy_credits\|onnx\|paddleocr\|ctc_decode` in `src/ingestion/ocr.py` | 3C | REQ-ocr-pipeline | smoke (CI guard) | `! grep -E 'kill_feed\|ult_orb\|economy_credits\|onnx\|paddleocr\|ctc_decode' src/ingestion/ocr.py` | ❌ W0 | ⬜ pending |
| `tests/ingestion/test_text_listener.py::test_emits_typed_soft_events` | 3D | REQ-text-listener | integration (mocked stream) | `uv run pytest tests/ingestion/test_text_listener.py::test_emits_typed_soft_events -x` | ❌ W0 | ⬜ pending |
| `tests/ingestion/test_text_listener.py::test_twitter_only_update_quarantined` | 3D | REQ-text-listener | integration | `uv run pytest tests/ingestion/test_text_listener.py::test_twitter_only_update_quarantined -x` | ❌ W0 | ⬜ pending |
| `tests/ingestion/test_text_listener.py::test_no_token_noop` | 3D | REQ-text-listener | unit | `uv run pytest tests/ingestion/test_text_listener.py::test_no_token_noop -x` | ❌ W0 | ⬜ pending |
| `tests/ingestion/test_arbiter.py::test_score_change_two_source_rule` | 3A | REQ-cross-source-arbiter | property | `uv run pytest tests/ingestion/test_arbiter.py::test_score_change_two_source_rule -x` | ❌ W0 | ⬜ pending |
| `tests/ingestion/test_arbiter.py::test_bomb_event_one_source_soft_commit` | 3A | REQ-cross-source-arbiter | property | `uv run pytest tests/ingestion/test_arbiter.py::test_bomb_event_one_source_soft_commit -x` | ❌ W0 | ⬜ pending |
| `tests/ingestion/test_arbiter.py::test_round_end_one_source_soft_commit` | 3A | REQ-cross-source-arbiter | property | `uv run pytest tests/ingestion/test_arbiter.py::test_round_end_one_source_soft_commit -x` | ❌ W0 | ⬜ pending |
| `tests/ingestion/test_arbiter.py::test_quarantine_jsonl_format` | 3A | REQ-cross-source-arbiter | integration | `uv run pytest tests/ingestion/test_arbiter.py::test_quarantine_jsonl_format -x` | ❌ W0 | ⬜ pending |
| Grep guard `kill_events\|numerical_flips` in `src/ingestion/arbiter.py` | 3A | REQ-cross-source-arbiter | smoke (CI guard) | `! grep -E 'kill_events\|numerical_flips' src/ingestion/arbiter.py` | ❌ W0 | ⬜ pending |
| `tests/ingestion/test_latency.py::test_six_stage_populated` | 3A | REQ-latency-instrumentation | integration | `uv run pytest tests/ingestion/test_latency.py::test_six_stage_populated -x` | ❌ W0 | ⬜ pending |
| `tests/pricing/test_round_conclusion_v2.py::test_post_plant_p_hierarchy` | 2A | REQ-round-conclusion-lookup | unit | `uv run pytest tests/pricing/test_round_conclusion_v2.py::test_post_plant_p_hierarchy -x` | ❌ W0 | ⬜ pending |
| `tests/pricing/test_round_conclusion_v2.py::test_from_json_rejects_v1` | 2A | REQ-round-conclusion-lookup | unit | `uv run pytest tests/pricing/test_round_conclusion_v2.py::test_from_json_rejects_v1 -x` | ❌ W0 | ⬜ pending |
| `tests/pricing/test_live_theo_dispatch.py::test_dispatch_bomb_planted` | 2A | REQ-round-conclusion-lookup | unit | `uv run pytest tests/pricing/test_live_theo_dispatch.py::test_dispatch_bomb_planted -x` | ❌ W0 | ⬜ pending |
| `tests/pricing/test_live_theo_dispatch.py::test_dispatch_between_round` | 2A | REQ-round-conclusion-lookup | unit | `uv run pytest tests/pricing/test_live_theo_dispatch.py::test_dispatch_between_round -x` | ❌ W0 | ⬜ pending |
| Phase 1 + Phase 2 regression suite | 2A | REQ-round-conclusion-lookup | regression | `uv run pytest tests/pricing/ tests/probe/ tests/calibration/ -x` | ✅ exists | ⬜ pending |
| `tests/ingestion/test_e2e.py::test_e2e_latency_p50` | 4 | REQ-end-to-end-latency | benchmark | `uv run pytest tests/ingestion/test_e2e.py::test_e2e_latency_p50 -x` | ❌ W0 | ⬜ pending |
| `tests/ingestion/test_e2e.py::test_bomb_detect_p50` | 4 | REQ-end-to-end-latency | benchmark | `uv run pytest tests/ingestion/test_e2e.py::test_bomb_detect_p50 -x` | ❌ W0 | ⬜ pending |
| `tests/ingestion/test_e2e.py::test_post_plant_non_degenerate` | 4 | REQ-end-to-end-latency | integration | `uv run pytest tests/ingestion/test_e2e.py::test_post_plant_non_degenerate -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/ingestion/__init__.py` — package marker
- [ ] `tests/ingestion/conftest.py` — shared fixtures: `make_match_state(**overrides)`, `tmp_event_log_path`, `synthetic_frame_factory`, `arbiter_with_stub_sources`
- [ ] `tests/ingestion/test_match_state.py` — REQ-match-state-engine seq_id property test + `with_update` field semantics (RED stub)
- [ ] `tests/ingestion/test_match_state_jsonl.py` — JSONL replay determinism + commit/quarantine line schema (RED stub)
- [ ] `tests/ingestion/test_scoreboard.py` — REQ-scoreboard-polling (aioresponses) (RED stub)
- [ ] `tests/ingestion/test_ocr_score.py` — score banner OCR benchmark + correctness (RED stub)
- [ ] `tests/ingestion/test_ocr_bomb.py` — bomb-icon OCR benchmark + correctness (RED stub)
- [ ] `tests/ingestion/test_ocr_round_end.py` — round-end banner OCR benchmark + correctness (RED stub)
- [ ] `tests/ingestion/test_ocr_alive_widget.py` — post-plant alive widget OCR benchmark + correctness + parse-failure quarantine (RED stub)
- [ ] `tests/ingestion/test_text_listener.py` — Twitter v2 mocked stream + no-token-noop (RED stub)
- [ ] `tests/ingestion/test_arbiter.py` — 3-deque rule property tests + quarantine flow (RED stub)
- [ ] `tests/ingestion/test_latency.py` — six-stage timestamp populated assertion (RED stub)
- [ ] `tests/ingestion/test_e2e.py` — SPEC §6 acceptance gate (RED stub)
- [ ] `tests/ingestion/fixtures/` — synthetic post-plant frames at known ROI coordinates (PNG, ~10 files), score banner frames (~10), round-end banner frames (~10), bomb-icon frames (~10)
- [ ] `tests/pricing/test_round_conclusion_v2.py` — REQ-round-conclusion-lookup v2 surface tests (post_plant_p hierarchy + from_json schema_version gate) (RED stub)
- [ ] `tests/pricing/test_live_theo_dispatch.py` — D-05 dispatch test (bomb_planted=True → post-plant path; else → between-round) (RED stub)
- [ ] Framework install: `uv add --dev pytest-asyncio aioresponses` — required before async tests can run
- [ ] mypy strict override for `src.state.*` in `pyproject.toml` `[[tool.mypy.overrides]]`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| ROI hand-calibration against 2026 VCT international broadcast frames | REQ-ocr-pipeline (D-11) | Pixel coordinates depend on operator-supplied broadcast frames; placeholder values land in `src/config/constants.py` per operator gate #1 | Operator: open `scripts/dump_roi_overlay.py` (added in Wave 3C) against a recorded VOD; visually verify the score-banner / bomb-icon / round-end-banner / post-plant-alive ROIs land cleanly. Bump `BROADCAST_TEMPLATE_VERSION` if layout shifts. |
| ETL re-run multi-hour scrape against rib.gg | REQ-round-conclusion-lookup (D-07) | Network-bound multi-hour run; not part of CI feedback loop | Operator/autonomous: run `uv run python scripts/probe_round_events_v2.py --target-series 1000 --cache data/ribgg_cache/`; resumable via D-09. Acceptance: `SELECT COUNT(DISTINCT match_id) FROM round_events_v2` ≥ 1000 and total rows ≥ 40000. |
| LiveTheoEngine smoke under v2 calibrated lookup | REQ-round-conclusion-lookup (D-06) | One-off post-calibration sanity (mirror Phase 2 close-out) | `uv run python -c "from src.pricing.live_theo import build_engine; ..."` — assert non-degenerate post-plant theo (off side baseline by ≥ 1¢). Documented in Wave 2C task. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (16 test files + 2 dev deps + mypy override)
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s (per-task quick run)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
