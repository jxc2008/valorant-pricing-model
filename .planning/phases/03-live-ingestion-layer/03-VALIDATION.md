---
phase: 03
slug: live-ingestion-layer
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-02
---

# Phase 03 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Sampling targets lifted verbatim from `03-RESEARCH.md` §Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `pytest>=8.0` (already pinned) + `pytest-asyncio>=0.24,<2` (NEW) + `pytest-benchmark>=4,<6` (NEW) + `hypothesis>=6.100` (already pinned) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` — Wave 0 adds `asyncio_mode = "auto"` |
| **Quick run command** | `pytest tests/ -x -k "not benchmark and not e2e"` |
| **Full suite command** | `pytest tests/` |
| **Estimated runtime** | ~30 seconds (quick) / ~3 min (full incl. benchmark + e2e) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -k "not benchmark and not e2e"`
- **After every plan wave:** Run `pytest tests/`
- **Before `/gsd-verify-work`:** Full suite must be green; `mypy --strict src/pricing/ src/state/` clean; `ruff check src/ tests/ scripts/` clean.
- **Max feedback latency:** 30 seconds quick, 180 seconds full

---

## Per-Task Verification Map

> Plan IDs are placeholders (`03-01-…`); planner replaces them with concrete task IDs after wave assignment. Threat refs filled in by `/gsd-secure-phase`.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 03-WAVE0 | 00 | 0 | infra | — | N/A | infra | `pip install -e ".[dev]" && pytest tests/ -x` | ❌ W0 | ⬜ pending |
| 03-MS-01 | match-state | 2 | REQ-match-state-engine | — | seq_id strictly monotonic — replay determinism | property | `pytest tests/state/test_match_state.py::test_seq_id_monotonic_1000_mutators -x` | ❌ W0 | ⬜ pending |
| 03-MS-02 | match-state | 2 | REQ-match-state-engine | — | `with_update` strips caller-provided `seq_id`/`last_updated_ts` | unit | `pytest tests/state/test_match_state.py::test_with_update_strips_seq_id -x` | ❌ W0 | ⬜ pending |
| 03-MS-03 | match-state | 2 | REQ-match-state-engine | — | JSONL replay round-trip → identical final state | property | `pytest tests/state/test_match_state.py::test_jsonl_replay_round_trip -x` | ❌ W0 | ⬜ pending |
| 03-SP-01 | scoreboard | 3 | REQ-scoreboard-polling | — | Monkeypatched `requests.get` → typed events at 5s cadence | integration | `pytest tests/ingestion/test_scoreboard.py -x` | ❌ W0 | ⬜ pending |
| 03-SP-02 | scoreboard | 3 | REQ-scoreboard-polling | — | `Connection: close` + `_ribgg_wait` resilience patterns honored | unit | `pytest tests/ingestion/test_scoreboard.py::test_resilience_patterns -x` | ❌ W0 | ⬜ pending |
| 03-OC-01 | ocr (03-05b) | 3 | REQ-ocr-pipeline | — | 50-frame median decode + inference < 100ms per target | benchmark | `pytest tests/ingestion/test_ocr.py::test_ocr_benchmark_50_frames -x` | ❌ W0 | ⬜ pending |
| 03-OC-02 | ocr (03-05b) | 3 | REQ-ocr-pipeline | — | Per-target cadence within ±10% jitter under sustained load | integration | `pytest tests/ingestion/test_ocr.py::test_per_target_cadence -x` | ❌ W0 | ⬜ pending |
| 03-OC-03 | ocr (03-05b) | 3 | REQ-ocr-pipeline | — | Confidence below `OCR_KILLFEED_CONF_THRESHOLD` → no event emitted (Pitfall 2) | unit | `pytest tests/ingestion/test_ocr.py::test_low_confidence_drop -x` | ❌ W0 | ⬜ pending |
| 03-TX-01 | text-listener | 3 | REQ-text-listener | — | Mocked Twitter stream → typed soft-events emitted | integration | `pytest tests/ingestion/test_text_listener.py -x` | ❌ W0 | ⬜ pending |
| 03-TX-02 | text-listener | 3 | REQ-text-listener | — | Twitter-only state-change quarantined, never committed | unit | `pytest tests/ingestion/test_text_listener.py::test_twitter_only_quarantined -x` | ❌ W0 | ⬜ pending |
| 03-TX-03 | text-listener | 3 | REQ-text-listener | — | Missing `TWITTER_BEARER_TOKEN` → listener no-ops, no exception | unit | `pytest tests/ingestion/test_text_listener.py::test_no_token_noop -x` | ❌ W0 | ⬜ pending |
| 03-AR-01 | arbiter (03-07b) | 4 | REQ-cross-source-arbiter | — | Rule matrix: 15 (source × event_type) combos fire correctly per DEC-006 | property | `pytest tests/ingestion/test_arbiter.py::test_rule_matrix -x` | ❌ W0 | ⬜ pending |
| 03-AR-02 | arbiter (03-07b) | 4 | REQ-cross-source-arbiter | — | Quarantined events appear in JSONL with `quarantined: true`, `seq_id: null` | unit | `pytest tests/ingestion/test_arbiter.py::test_quarantine_log_shape -x` | ❌ W0 | ⬜ pending |
| 03-AR-03 | arbiter (03-07b) | 4 | REQ-cross-source-arbiter | — | Score-change rule: ≥2 sources within 2s → fire; else quarantine | property | `pytest tests/ingestion/test_arbiter.py::test_score_change_window -x` | ❌ W0 | ⬜ pending |
| 03-LI-01 | latency (03-07b) | 4 | REQ-latency-instrumentation | — | Every confirmed event in JSONL has all six timestamp fields (Phase 4 = None) | unit | `pytest tests/ingestion/test_arbiter.py::test_six_stage_timestamps -x` | ❌ W0 | ⬜ pending |
| 03-LI-02 | latency (03-07b) | 4 | REQ-latency-instrumentation | — | Metrics file parseable line-by-line; `t_observed` ascending | unit | `pytest tests/ingestion/test_arbiter.py::test_metrics_parseable -x` | ❌ W0 | ⬜ pending |
| 03-E2E-01 | e2e | 5 | REQ-end-to-end-latency | — | E2E synthetic ≥30 events: p50 `t_observed → t_state_committed` < 500ms | integration | `pytest tests/ingestion/test_e2e.py::test_e2e_p50_latency -x` | ❌ W0 | ⬜ pending |
| 03-E2E-02 | e2e | 5 | REQ-end-to-end-latency | — | E2E synthetic: `theo_series` non-degenerate (∈ (0.01, 0.99), not 0.5) | integration | `pytest tests/ingestion/test_e2e.py::test_e2e_theo_non_degenerate -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

### Sampling minimums (Nyquist) — pin into PLAN must_haves

- `test_seq_id_monotonic_1000_mutators` — ≥1000 random `with_update` calls per example, `@settings(max_examples=20)` → 20k mutations exercised.
- `test_jsonl_replay_round_trip` — ≥1000 events written + replayed; assert final state equality.
- `test_rule_matrix` — 20 combos (3 sources × 5 event types + 5 multi-source) × `@settings(max_examples=100)` → 2000 arbiter executions.
- `test_score_change_window` — hypothesis-generated time offsets ∈ [-3.0s, +3.0s], ≥200 examples.
- `test_ocr_benchmark_50_frames` — `--benchmark-min-rounds=50` for the acceptance benchmark; 4 targets × 50 = 200 frame inferences.
- `test_e2e_p50_latency` — ≥30 events (SPEC); recommend 50 to reduce p50 noise.

---

## Wave 0 Requirements

- [ ] `pyproject.toml` — add deps (`aiohttp`, `tweepy`, `onnxruntime`, `pytesseract`, `Pillow`, `numpy`, `pytest-asyncio`, `pytest-benchmark`); add `asyncio_mode = "auto"`; add `[tool.mypy.overrides]` block for `src.state.*`.
- [ ] `tests/ingestion/__init__.py` — empty
- [ ] `tests/state/__init__.py` — empty
- [ ] `tests/ingestion/conftest.py` — fixtures: `mock_ribgg_response`, `fake_ocr_frame_source`, `fake_twitter_stream`
- [ ] `tests/ingestion/fixtures/canned_kill_feed_frames/` — 5 hand-labeled PNGs (researcher A3 mitigation)
- [ ] `scripts/download_models.py` — fetches `en_PP-OCRv4_rec_infer.onnx` to `models/`, verifies SHA-256
- [ ] `models/.gitkeep` + `.gitignore` rule for `models/*.onnx`
- [ ] `data/event_log/.gitkeep` + `data/metrics/.gitkeep` + `.gitignore` rules
- [ ] `src/state/__init__.py` — re-exports `MatchState`
- [ ] `src/ingestion/__init__.py` — re-exports primary classes
- [ ] `src/config/constants.py` — 13 new constants per RESEARCH §Reusable Assets
- [ ] `src/ingestion/types.py` — `ArbiterPending`, `ConfirmedEvent`, `EventLogLine`, `MetricsLogLine` dataclasses

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `reference/vlr_scraper.py`, `reference/rib_scraper.py`, `reference/vision_parser.py` salvage copy | REQ-scoreboard-polling, REQ-ocr-pipeline | Files live in sibling `thunderedge/` repo — outside this repo's working copy | User copies the three files into `reference/` and stages them; planner inserts a Wave 0 checklist task that verifies presence via `test -f reference/{vlr_scraper,rib_scraper,vision_parser}.py` |
| ONNX accuracy probe on real Valorant kill-feed frames (researcher A3) | REQ-ocr-pipeline | No published benchmark on Valorant HUD; needs eyeballing 5 hand-labeled frames | Operator runs `pytest tests/ingestion/test_ocr.py::test_ocr_accuracy_probe` and inspects the printed character-error-rate; if ≥30%, fall back to tesseract for kill-feed (sacrifices the 100ms cadence) |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s quick / 180s full
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
