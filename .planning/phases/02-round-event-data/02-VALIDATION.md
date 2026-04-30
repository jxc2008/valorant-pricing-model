---
phase: 2
slug: round-event-data
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-30
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (already pinned by Phase 1) |
| **Config file** | `pyproject.toml` (Phase 1) |
| **Quick run command** | `pytest tests/pricing/test_round_conclusion.py tests/calibration/ tests/probe/ -x -q` |
| **Full suite command** | `pytest -x -q` |
| **Estimated runtime** | ~30 seconds (no live HTTP in CI; live probe is opt-in) |

---

## Sampling Rate

- **After every task commit:** Run quick command
- **After every plan wave:** Run full suite command
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

> Populated by gsd-planner during planning. Each plan task with `<automated>` block must appear here.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-XX-XX | XX | X | REQ-round-event-data-pipeline | — | N/A | unit/integration | `{command}` | ⬜ TBD | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/probe/test_endpoint_shapes.py` — fixture-based parsers for `/v1/events`, `/v1/series`, `/v1/matches/{id}/details` JSON shape (offline fixtures only — no live HTTP in CI)
- [ ] `tests/probe/fixtures/match_details.json` — recorded sample from VCT 2025 match (≥1 round with bomb plant + defuse)
- [ ] `tests/calibration/test_shrinkage_walk.py` — bottom-up walk over a synthetic 5-round dataset
- [ ] `tests/calibration/test_from_json_roundtrip.py` — `RoundConclusionLookup` → JSON → `RoundConclusionLookup` invariant
- [ ] `tests/calibration/test_econ_bucketing.py` — Phase-3-shareable `econ_bucket` boundary cases (4999/5000/9999/10000/19999/20000)
- [ ] `tests/calibration/test_side_baseline.py` — `half_win_rates.json` ingestion: present file, missing file, zero-coverage file (0.5 fallback)
- [ ] `tests/calibration/conftest.py` — shared fixtures: synthetic `round_events` row factory, in-memory SQLite engine

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live rib.gg probe completes ≥500 series within 1-week cap | REQ-round-event-data-pipeline (must-have #1) | Requires live network + auth; would slow CI; environment-dependent (rate limits) | Run `python scripts/probe_round_events.py --live --limit 1000`; verify `02-PROBE-LOG.md` records ≥500 successful series and acceptance bar evaluation |
| Path B OCR labeling 100 VODs at 1Hz w/ 10% hand-verified | REQ-round-event-data-pipeline (must-have #2, Path B branch) | Requires VOD downloads + human verification labor | Only required if Path A fails. Documented in `scripts/ocr_round_events.py --help` |
| `models/round_conclusion.json` produces non-degenerate predictions in `live_theo` | REQ-round-event-data-pipeline (must-have #3) | Phase 4 wiring not yet present in Phase 2's scope | Future Phase 4 verification; Phase 2 verifies `_Cell.shrunk()` returns non-0.5 values for populated cells |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (probe fixtures, calibration test scaffold, in-memory SQLite)
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
