---
phase: 04
slug: quoting-layer
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-10
---

# Phase 04 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (already installed Phase 03) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `python -m pytest tests/quoting/ tests/sizing/ -x --no-cov` |
| **Full suite command** | `python -m pytest tests/ --no-cov` |
| **Estimated runtime** | ~30 seconds (full suite); ~5 seconds (quoting/sizing only) |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/quoting/ tests/sizing/ -x --no-cov`
- **After every plan wave:** Run `python -m pytest tests/ --no-cov`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

Filled by planner after PLAN.md generation. Initial map below mirrors the 8-plan / 5-wave decomposition recommended in RESEARCH.md.

| Plan | Wave | Requirement | Test Type | Status |
|------|------|-------------|-----------|--------|
| 04-00 (test scaffolds + dev deps) | 1 | infrastructure | RED-stub | ⬜ pending |
| 04-01 (KalshiOrderManager + auth) | 2 | REQ-kalshi-order-manager | unit + integration | ⬜ pending |
| 04-02 (kelly_size portfolio sizer) | 2 | REQ-kelly-sizer | unit + property | ⬜ pending |
| 04-03 (kill switches) | 2 | REQ-kill-switches | unit (predicate-style) | ⬜ pending |
| 04-04 (mode-selector) | 3 | REQ-mode-selector | unit (truth-table) | ⬜ pending |
| 04-05 (MM-between-round quoter) | 4 | REQ-mm-quoter | unit + integration | ⬜ pending |
| 04-06 (directional taker) | 4 | REQ-directional-taker | unit + integration | ⬜ pending |
| 04-07 (post-plant quoter) | 4 | REQ-post-plant-quoter | unit + integration + latency | ⬜ pending |
| 04-08 (order lifecycle reconciliation + E2E) | 5 | REQ-order-lifecycle-reconciliation | unit + E2E | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/quoting/__init__.py` — package marker
- [ ] `tests/quoting/conftest.py` — shared fixtures (mock Kalshi REST/WS responses, synthetic MarketQuote, MatchState builders that exercise three-way mode + IDLE)
- [ ] `tests/quoting/test_kalshi_order_manager.py` — RED stubs
- [ ] `tests/quoting/test_mode_selector.py` — RED stubs (truth-table coverage)
- [ ] `tests/quoting/test_mm_between_round.py` — RED stubs
- [ ] `tests/quoting/test_directional_taker.py` — RED stubs
- [ ] `tests/quoting/test_post_plant_quoter.py` — RED stubs (incl. 100ms latency assertion)
- [ ] `tests/quoting/test_kill_switches.py` — RED stubs (4 kill switches)
- [ ] `tests/quoting/test_order_lifecycle.py` — RED stubs
- [ ] `tests/quoting/test_e2e.py` — RED stub (full quoting pipeline)
- [ ] `tests/sizing/__init__.py` + `test_kelly_portfolio.py` — RED stubs (per-market + per-series cap, property-based)
- [ ] dev deps if needed: `cryptography>=42` (RSA-PSS signing), `websockets>=12` (Kalshi WS), `hypothesis>=6` (property tests for kelly_size)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| First Kalshi REST call against operator's `.env` | REQ-kalshi-order-manager | Auth requires live Kalshi credentials | `python -m scripts.kalshi_auth_smoke` — must return 200 with operator's `.env` (operator gate 2) |
| Production --live flag | REQ-kalshi-order-manager + DEC-022 | Capital risk | Operator-only; gated until promotion gate met (Phase 5.3) |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter (after planner fills the per-task map)

**Approval:** pending
