# ROADMAP — Valorant Live Pricing Model

**Source of truth for build sequencing:** `roadmap.md` (root) — full implementation guidance per phase, including code-level signatures, fallback chains, and probability-input tables. This file is the GSD-canonical phase index that mirrors that doc and points back to it; it does not duplicate its contents.

For locked design decisions referenced below (DEC-*), see `.planning/PROJECT.md`. For full requirement detail (REQ-*), see `.planning/REQUIREMENTS.md`.

---

## Dependency graph

```
Phase 0 (foundation) ──┬→ Phase 1 (pricing engine) ──┐
                       ├→ Phase 2 (round-event data) ┤
                       └→ Phase 3 (live ingestion) ──┴→ Phase 4 (quoting)
                                                              ↓
                                                   Phase 5 (validation)
                                                              ↓
                                                   Phase 6 (deployment)
                                                              ↓
                                                   Phase 7 (operational maturity)
```

Phases 1, 2, 3 run in parallel after Phase 0 completes — this is a deliberate design choice (`roadmap.md` header diagram). Phase 4 needs both pricing (Phase 1) and ingestion (Phase 3); it can ship without Phase 2 if `round_conclusion` is deferred (Path C of DEC-017), in which case mid-round edge is sacrificed but between-round MM still works.

## Phases

- [ ] **Phase 0: Foundation** — Project structure, tooling, config skeleton (~2 days).
- [ ] **Phase 1: Core pricing engine** — Generalized BO3 DP + Bradley-Terry blend + pistol/anti-eco modeling + canonical `live_theo` (~5–7 days).
- [ ] **Phase 2: Round-event data** — rib.gg/bo3.gg API probe + `round_events` dataset OR OCR-driven labeling OR defer (~3 days API path / ~2 weeks OCR path).
- [ ] **Phase 3: Live ingestion layer** — `MatchState` engine + scoreboard polling + OCR pipeline + text listeners + cross-source arbiter + latency instrumentation (~7–10 days).
- [ ] **Phase 4: Quoting layer** — `KalshiOrderManager` + mode selector + MM quoter + directional taker + Kelly sizer + kill switches + order reconciliation (~5–7 days).
- [ ] **Phase 5: Validation** — Unit/property tests + backtest + paper trading + calibration loop (~2–4 weeks, calendar-bound by live events).
- [ ] **Phase 6: Deployment** — Containerization + cloud VM + deploy pipeline + secrets + logging/alerting + monitoring dashboard (~3–5 days).
- [ ] **Phase 7: Operational maturity** — Daily metrics report + weekly drift detection + incident runbook + portfolio loss limit (ongoing).

---

## Phase Details

### Phase 0: Foundation
**Goal**: Project skeleton ready — directory tree, tooling, config baseline, dry-run-default safety in place so Phases 1, 2, 3 can start in parallel.
**Depends on**: nothing (entry phase)
**Requirements**: none (bootstrap-only — Phase 0 scope codified as constraints in `.planning/intel/constraints.md`: `CON-package-layout`, `CON-tooling-versions`, `CON-mypy-strict-pricing`, `CON-no-magic-numbers`, `CON-domain-constants-baseline`, `CON-dry-run-default`, `CON-live-state-no-sqlite`)
**Must-haves** (falsifiable):
  1. `src/{pricing,state,ingestion,quoting,sizing,config}/` directory tree exists; `tests/`, `scripts/`, `data/`, `models/`, `reference/` siblings in place (DEC-019).
  2. `pyproject.toml` declares Python 3.11 + uv-managed deps; `mypy --strict src/pricing/` runs (even on empty modules); `ruff` passes (DEC-014).
  3. `src/config/constants.py` declares baseline values (`SHRINK_PRIOR=15.0`, `SIGNAL_SCALE=0.10`, `GUN_WIN_RATE=0.822`, `KELLY_MULTIPLIER=0.5`, `PER_MARKET_CAP_FRAC=0.05`, `VEGA_DIRECTIONAL_THRESHOLD=0.04`, all four `KILL_SWITCH_*` constants, `REGULATION_HALF=12`, `WIN_THRESHOLD=13`) per DEC-016 / `CON-domain-constants-baseline`.
**Plans**: 3 plans
- [x] 00-01-project-structure-and-tooling-PLAN.md — pyproject.toml + uv + ruff + mypy --strict on src/pricing/ + package skeleton (Wave 1)
- [ ] 00-02-domain-constants-PLAN.md — src/config/constants.py with all 12 PRD thresholds + tests/config/test_constants.py invariants (Wave 2)
- [ ] 00-03-dry-run-default-entry-point-PLAN.md — src/main.py + src/__main__.py CLI with --match/--live + tests/test_main.py safety contract (Wave 2)
**See**: `roadmap.md` §0 (0.1 layout / 0.2 tooling / 0.3 data store / 0.4 configuration)

### Phase 1: Core pricing engine
**Goal**: Single canonical `live_theo(state) → (theo_series, theo_map, vega, confidence)` with no data dependencies — between-round live pricing works end-to-end.
**Depends on**: Phase 0
**Requirements**: REQ-bo3-dp-engine, REQ-bradley-terry-blend, REQ-pistol-anti-eco-modeling, REQ-ot-handling, REQ-round-conclusion-lookup (skeleton only — calibration in Phase 2), REQ-canonical-live-theo, REQ-theo-series-output, REQ-theo-map-output, REQ-confidence-output, REQ-vega-output
**Must-haves** (falsifiable):
  1. `live_theo(state)` returns a `TheoOutput` dataclass with `theo_series, theo_map, vega, confidence`; no other pricing entry points exist (DEC-010); switching to/from MatchState→TheoOutput is the only API surface for the math layer.
  2. The four documented audit-engine bugs are fixed: Bradley-Terry blend (not arithmetic mean) per DEC-003, explicit OT hard-stop at total=24 per DEC-009, pistol/anti-eco rounds modeled with separate inputs per DEC-011, conviction clips at `[0.01, 0.99]` per DEC-012.
  3. Property tests pass: DP value ∈ `[0,1]` for any state; symmetric inputs match `p²(3−2p)` closed form; Bradley-Terry symmetry `round_p(a,b) == 1 − round_p(b,a)`; `theo_series` consistent with sum over `theo_map[]` outcomes (REQ-unit-and-property-tests subset).
**Plans**: TBD
**See**: `roadmap.md` §1 (1.1 DP / 1.2 blend / 1.3 round types / 1.4 OT / 1.5 round-conclusion / 1.6 live_theo)

### Phase 2: Round-event data
**Goal**: Round-conclusion lookup table populated with calibrated cells (Path A or Path B), or explicit defer with placeholder `p=0.5` (Path C). Decision gate per DEC-017.
**Depends on**: Phase 0 (parallel with Phase 1, Phase 3)
**Requirements**: REQ-round-event-data-pipeline
**Must-haves** (falsifiable):
  1. `scripts/probe_round_events.py` has been run against rib.gg + bo3.gg endpoints; the path decision (A / B / C) is recorded with evidence in the run log.
  2. If Path A: `round_events` table populated with ≥ 500 historical matches, schema `(match_id, map_num, round_num, ts_round_start, ts_first_kill, ts_bomb_plant, ts_round_end, mid_round_states[])` (`CON-round-events-schema`); `round_conclusion.py` cells calibrated from the dataset. If Path B: 100 VODs OCR-labeled at 1Hz with 10% sample hand-verified. If Path C: explicit defer documented and `round_conclusion` returns fixed `p=0.5`.
  3. Mid-round `live_theo` calls produce non-degenerate predictions (Path A/B) OR explicitly route to between-round-only flow (Path C — Phase 4 quoting still works).
**Plans**: TBD
**See**: `roadmap.md` §2 (2.1 API scoping / 2.2 Path A / 2.3 Path B / 2.4 Path C)

### Phase 3: Live ingestion layer
**Goal**: Real-time `MatchState` is fed by tiered, arbited multi-source ingestion at sub-500ms latency; every state mutation is timestamped through the pipeline.
**Depends on**: Phase 0 (parallel with Phase 1, Phase 2)
**Requirements**: REQ-match-state-engine, REQ-scoreboard-polling, REQ-ocr-pipeline, REQ-text-listener, REQ-cross-source-arbiter, REQ-latency-instrumentation
**Must-haves** (falsifiable):
  1. `MatchState` dataclass with all fields per `CON-match-state-schema`; mutators bump monotonic `seq_id`; every mutation appended to a JSONL event log on disk.
  2. Cross-source arbiter implements PRD §5.1 tiered confirmation per DEC-006 (score ≥2 sources/2s; bomb/kill/numerical 1 CV-source if kill-feed cross-confirms; round-end soft+hard; pre-match single-source); quarantined updates logged but not committed.
  3. Every event carries the six-stage timestamp set (`t_observed, t_ingested, t_arbited, t_state_committed, t_theo_computed, t_quote_sent` — `CON-event-timestamp-fields`) into a metrics log; OCR per-target cadences match `CON-ingestion-cadences` (250ms score banner, 100ms kill feed, 500ms bomb icon, 100ms round-end window).
**Plans**: TBD
**UI hint**: yes
**See**: `roadmap.md` §3 (3.1 state engine / 3.2 scoreboard / 3.3 OCR / 3.4 text / 3.5 arbiter / 3.6 instrumentation)

> **UI hint rationale:** OCR / vision-parser work is computer-vision UI parsing of broadcast HUD elements (score banner, kill feed, bomb icon). It is *not* a user-facing frontend, but the Phase 3 work touches visual-parsing concerns and warrants the same downstream tooling consideration. If `/gsd-ui-phase` is irrelevant for non-frontend CV work in this project's conventions, the orchestrator can ignore the hint.

### Phase 4: Quoting layer
**Goal**: Bot quotes Kalshi markets in MM mode by default with hybrid event-trigger flips to DIRECTIONAL, sized by half-Kelly, defended by four always-on kill switches.
**Depends on**: Phase 1, Phase 3 (Phase 2 optional — degrades to between-round-only MM under Path C)
**Requirements**: REQ-kalshi-order-manager, REQ-mode-selector, REQ-mm-quoter, REQ-directional-taker, REQ-kelly-sizer, REQ-kill-switches, REQ-order-lifecycle-reconciliation
**Must-haves** (falsifiable):
  1. `trading_mode(state, vega)` is a pure function evaluating triggers in PRD §2.1 order (numerical imbalance → bomb planted → map-point → late decider → vega override → MM default) per DEC-001 / `CON-trading-mode-signature`; resets to MM at round end + 5v5 + no flags.
  2. `kelly_size(theo, market_yes_ask, bankroll)` implements `CON-kelly-sizer-signature` exactly: `b = (1−ask)/ask`, `f = max(0, KELLY_MULTIPLIER × f_full)`, `f = min(f, PER_MARKET_CAP_FRAC)` (DEC-004); never returns full-Kelly sizing.
  3. All four kill switches active by default with no per-switch disable flag (DEC-005); each is a pure predicate over `(state, theo, market, recent_briers)`; ANY trip cancels all resting quotes via `KalshiOrderManager.cancel_all_orders` and fires alert; bot stays in `dry_run=True` until promotion gate met (DEC-022).
**Plans**: TBD
**See**: `roadmap.md` §4 (4.1 KalshiOrderManager / 4.2 mode / 4.3 MM / 4.4 directional / 4.5 Kelly / 4.6 kill switches / 4.7 reconciliation)

### Phase 5: Validation
**Goal**: Model and bot pass the promotion gate — Brier baseline beaten by ≥ 0.02 over 50-round windows in backtest, ≥ 1 full event of paper trading with Brier < 0.22 and zero ingestion-bug kill-switch trips.
**Depends on**: Phase 4
**Requirements**: REQ-unit-and-property-tests, REQ-backtest, REQ-paper-trading, REQ-calibration-loop
**Must-haves** (falsifiable):
  1. 80% line coverage on `src/pricing/` (`CON-coverage-target`); hypothesis property tests pass for the four invariants in REQ-unit-and-property-tests.
  2. Backtest replay against past season's matches reports per-bucket Brier (early-game / mid-game / post-plant / late) and shows live theo Brier ≤ static-prior baseline by ≥ 0.02 over 50-round windows; order-fill backtest skipped per DEC-020.
  3. Paper-trade promotion gate satisfied (`CON-promotion-gate`): ≥ 1 full event with Brier < 0.22 and zero kill-switch trips for ingestion bugs (model-trip kill switches acceptable). Latency p50 < 500ms event→theo and quote-cancel p99 < 100ms recorded across the event.
**Plans**: TBD
**See**: `roadmap.md` §5 (5.1 tests / 5.2 backtest / 5.3 paper trading / 5.4 calibration)

### Phase 6: Deployment
**Goal**: Bot runs in production on a US-East cloud VM with proper secrets handling, structured observability, and a working CI/CD path from local dev to live `--live`-flag deployment.
**Depends on**: Phase 5
**Requirements**: REQ-containerization, REQ-cloud-vm, REQ-deploy-pipeline, REQ-secrets-handling, REQ-logging-and-alerting, REQ-monitoring-dashboard
**Must-haves** (falsifiable):
  1. Multi-stage Dockerfile builds an image < 500MB (`CON-image-size-target`); CI (GitHub Actions) builds, tests, and pushes to GHCR.
  2. Production VM is a Hetzner CCX13 (or AWS t3.small) in US-East; Kalshi private key mounted as a Docker secret — never in image, never in env vars (`CON-secrets-handling` / DEC-008).
  3. Structured JSON logs ship to Loki / Grafana Cloud; PagerDuty/SMS alerts fire on kill-switch trips and process crashes; Grafana dashboard shows theo vs market, fill rate, inventory, kill-switch trip log, latency p50/p99, daily P&L.
**Plans**: TBD
**UI hint**: yes
**See**: `roadmap.md` §6 (6.1 containerization / 6.2 VM / 6.3 pipeline / 6.4 secrets / 6.5 logging / 6.6 monitoring)

> **UI hint rationale:** Phase 6.6 builds a Grafana dashboard. It is operator-facing observability, not end-user product UI; included for downstream-tooling completeness.

### Phase 7: Operational maturity
**Goal**: Bot is sustainably operable in production — daily/weekly automated reporting, drift alerting, an incident runbook, and a portfolio-level loss limit distinct from per-market kill switches.
**Depends on**: Phase 6
**Requirements**: REQ-daily-metrics-report, REQ-weekly-drift-detection, REQ-incident-runbook, REQ-portfolio-loss-limit
**Must-haves** (falsifiable):
  1. Cron job emails daily summary (matches traded, fills, P&L, Brier, kill-switch trips, model version) every UTC day with no manual intervention.
  2. Weekly drift job compares last-7-days Brier distribution to baseline calibration set; KL divergence above threshold fires an alert with diagnostic context.
  3. Portfolio loss limit halts the bot when cumulative realized + unrealized P&L < −X% of bankroll until manual review (DEC-021); incident runbook documents remote-halt, manual-cancel-via-Kalshi-UI, image-rollback, and per-kill-switch interpretation.
**Plans**: TBD
**See**: `roadmap.md` §7 (7.1 daily / 7.2 drift / 7.3 runbook / 7.4 risk limits)

---

## Progress

| Phase | Plans Complete | Status | Completed |
|---|---|---|---|
| 0. Foundation | 1/3 | In Progress|  |
| 1. Core pricing engine | 0/0 | Not started | — |
| 2. Round-event data | 0/0 | Not started | — |
| 3. Live ingestion layer | 0/0 | Not started | — |
| 4. Quoting layer | 0/0 | Not started | — |
| 5. Validation | 0/0 | Not started | — |
| 6. Deployment | 0/0 | Not started | — |
| 7. Operational maturity | 0/0 | Not started | — |

---

## Coverage check

- All 37 v1 requirements (REQ-*) mapped across Phases 1–7. Phase 0 has no REQs (bootstrap; constraint-only scope).
- No orphans, no duplicates. See `.planning/REQUIREMENTS.md` Traceability table.
- Critical-path totals from `roadmap.md`: ~4–6 weeks of build time + ~2 weeks paper trading; ~7–8 weeks calendar end-to-end (API path) or ~10–12 weeks (OCR path).
- Earliest revenue: between-round live MM after ~3 weeks if Phases 1, 3, 4 ship with `round_conclusion` deferred (Path C).
