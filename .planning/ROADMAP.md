# ROADMAP — Valorant Live Pricing Model

**Source of truth for build sequencing:** `roadmap.md` (root) — full implementation guidance per phase, including code-level signatures, fallback chains, and probability-input tables. This file is the GSD-canonical phase index that mirrors that doc and points back to it; it does not duplicate its contents.

For locked design decisions referenced below (DEC-*), see `.planning/PROJECT.md`. For full requirement detail (REQ-*), see `.planning/REQUIREMENTS.md`.

> **v2 architecture pivot (2026-05-02):** Phase 3 onwards rescoped. Three-way trading mode + IDLE replaces "hybrid MM-default + DIRECTIONAL flip". Kill-feed CV / mid-round economy / ult tracking cut. Round-conclusion lookup rekeyed to post-plant-only. Portfolio Kelly aggregate cap added. Promotion gate switches to relative-Brier + fill-count. Existing 11 Phase 3 plans (commit `6677e5d`) need teardown + replan.

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

- [x] **Phase 0: Foundation** — Project structure, tooling, config skeleton (~2 days). (completed 2026-04-27)
- [ ] **Phase 1: Core pricing engine** — Generalized BO3 DP + Bradley-Terry blend + pistol/anti-eco modeling + canonical `live_theo` (~5–7 days).
- [x] **Phase 2: Round-event data** — rib.gg/bo3.gg API probe + `round_events` dataset OR OCR-driven labeling OR defer (~3 days API path / ~2 weeks OCR path). (completed 2026-05-01 — Path A: 1000 matches / 42586 rounds / calibrated `models/round_conclusion.json`)
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
- [x] 00-02-domain-constants-PLAN.md — src/config/constants.py with all 12 PRD thresholds + tests/config/test_constants.py invariants (Wave 2)
- [x] 00-03-dry-run-default-entry-point-PLAN.md — src/main.py + src/__main__.py CLI with --match/--live + tests/test_main.py safety contract (Wave 2)
**See**: `roadmap.md` §0 (0.1 layout / 0.2 tooling / 0.3 data store / 0.4 configuration)

### Phase 1: Core pricing engine
**Goal**: Single canonical `live_theo(state) → (theo_series, theo_map, vega, confidence)` with no data dependencies — between-round live pricing works end-to-end.
**Depends on**: Phase 0
**Requirements**: REQ-bo3-dp-engine, REQ-bradley-terry-blend, REQ-pistol-anti-eco-modeling, REQ-ot-handling, REQ-round-conclusion-lookup (skeleton only — calibration in Phase 2), REQ-canonical-live-theo, REQ-theo-series-output, REQ-theo-map-output, REQ-confidence-output, REQ-vega-output
**Must-haves** (falsifiable):
  1. `live_theo(state)` returns a `TheoOutput` dataclass with `theo_series, theo_map, vega, confidence`; no other pricing entry points exist (DEC-010); switching to/from MatchState→TheoOutput is the only API surface for the math layer.
  2. The four documented audit-engine bugs are fixed: Bradley-Terry blend (not arithmetic mean) per DEC-003, explicit OT hard-stop at total=24 per DEC-009, pistol/anti-eco rounds modeled with separate inputs per DEC-011, conviction clips at `[0.01, 0.99]` per DEC-012.
  3. Property tests pass: DP value ∈ `[0,1]` for any state; symmetric inputs match `p²(3−2p)` closed form; Bradley-Terry symmetry `round_p(a,b) == 1 − round_p(b,a)`; `theo_series` consistent with sum over `theo_map[]` outcomes (REQ-unit-and-property-tests subset).
**Plans**: 7 plans
  - [x] 01-01-constants-and-blend-PLAN.md — config constants + Bradley-Terry blend
  - [x] 01-02-bo3-dp-engine-PLAN.md — generalized BO3 DP + OT hard-stop
  - [x] 01-03-round-types-PLAN.md — pistol / anti-eco / gunround dispatch
  - [x] 01-04-round-conclusion-skeleton-PLAN.md — RoundConclusionLookup skeleton (flat 0.5 in Phase 1)
  - [x] 01-05-live-theo-and-match-state-PLAN.md — LiveTheoEngine bundle + MatchState + TheoOutput
  - [x] 01-06-derived-output-fixes-PLAN.md — gap closure for CR-01..CR-04 (vega/confidence corruption + memory leak)
  - [x] 01-07-pistol-anti-eco-dp-propagation-PLAN.md — gap closure for CR-05 / WR-06 (pistol_winner_a propagation through DP forward-pass)
**See**: `roadmap.md` §1 (1.1 DP / 1.2 blend / 1.3 round types / 1.4 OT / 1.5 round-conclusion / 1.6 live_theo)

### Phase 2: Round-event data
**Goal**: Round-conclusion lookup table populated with calibrated cells (Path A or Path B), or explicit defer with placeholder `p=0.5` (Path C). Decision gate per DEC-017.
**Depends on**: Phase 0 (parallel with Phase 1, Phase 3)
**Requirements**: REQ-round-event-data-pipeline
**Must-haves** (falsifiable):
  1. `scripts/probe_round_events.py` has been run against rib.gg + bo3.gg endpoints; the path decision (A / B / C) is recorded with evidence in the run log.
  2. If Path A: `round_events` table populated with ≥ 500 historical matches, schema `(match_id, map_num, round_num, ts_round_start, ts_first_kill, ts_bomb_plant, ts_round_end, mid_round_states[])` (`CON-round-events-schema`); `round_conclusion.py` cells calibrated from the dataset. If Path B: 100 VODs OCR-labeled at 1Hz with 10% sample hand-verified. If Path C: explicit defer documented and `round_conclusion` returns fixed `p=0.5`.
  3. Mid-round `live_theo` calls produce non-degenerate predictions (Path A/B) OR explicitly route to between-round-only flow (Path C — Phase 4 quoting still works).
**Plans**: 5 plans
- [x] 02-01-PLAN.md — Phase 2 calibration constants + src/pricing/economy.py + ETL deps (Wave 1)
- [x] 02-02-PLAN.md — Wave 0 test scaffolds (tests/probe/ fixtures + tests/calibration/ RED tests) (Wave 1)
- [x] 02-03-PLAN.md — scripts/probe_round_events.py rib.gg ETL + operator-driven --live run (Wave 2) — Path A Pass:YES (1000 matches)
- [x] 02-04-PLAN.md — RoundConclusionLookup.from_json + lookup body rewrite + scripts/calibrate_round_conclusion.py + models/round_conclusion.json (Wave 3)
- [x] 02-05-PLAN.md — Path B contingency stub + LiveTheoEngine integration test (Wave 4)
**See**: `roadmap.md` §2 (2.1 API scoping / 2.2 Path A / 2.3 Path B / 2.4 Path C)

### Phase 3: Live ingestion layer (RESCOPED v2)
**Goal**: Real-time `MatchState` is fed by simplified arbited ingestion at sub-500ms latency, with bomb-detect → defensive-quote-pull p50 < 200ms; round-conclusion lookup rekeyed to post-plant-only `(att, def, time_bucket, side, map)` and recalibrated against existing Phase 2 dataset filtered to `bomb_planted=True` (~25k samples).
**Depends on**: Phase 0, Phase 1, Phase 2
**Requirements**: REQ-match-state-engine (rescoped), REQ-scoreboard-polling, REQ-ocr-pipeline (3 HUD targets only), REQ-text-listener, REQ-cross-source-arbiter (3 deques), REQ-latency-instrumentation, REQ-round-conclusion-lookup (rekeyed)
**Must-haves** (falsifiable):
  1. `MatchState` at `src/state/match_state.py` carries the v2 field set: `match_id, map_idx, a/b_map_score, a/b_round, side_orient, bomb_planted, attackers_alive | None, defenders_alive | None, time_left_s | None, seq_id, last_updated_ts`. Fields cut from v1: `econ_a/b`, `ults_a/b`, `players_alive_a/b`. Mutators bump monotonic `seq_id`; every mutation appended to a JSONL event log on disk.
  2. Cross-source arbiter has 3 deques (`score_changes`, `bomb_events`, `round_end_events`) per DEC-006 v2 — kill_events / numerical_flips REMOVED. Score ≥2 sources/2s; bomb 1 OCR source soft-commit; round-end 1 OCR source soft-commit. Quarantined events logged with `quarantined: true`.
  3. OCR pipeline parses three HUD targets only (DEC-024): score banner 250ms, bomb-plant icon 500ms, round-end banner 100ms-during-window. Tesseract-only, CPU-only. **Kill-feed parsing, ult tracking, mid-round economy inference are explicitly out of scope.** When `bomb_planted=True`, a separate post-plant attackers/defenders-alive HUD widget is parsed at 250ms cadence.
  4. `live_theo` dispatches: `bomb_planted=True → post_plant_lookup(att, def, time_bucket, side, map)`; otherwise → side baseline. No general mid-round path. The `models/round_conclusion.json` is rekeyed (Phase 2 dataset filter + recalibration); v1 keys (numerical_diff, econ_bucket) are deleted.
  5. Synthetic E2E gate `tests/ingestion/test_e2e.py` drives ≥30 events through arbiter → MatchState → `live_theo` and asserts: seq_id strictly monotonic; p50 `t_observed → t_state_committed` < 500ms; **bomb-detect → quote-pull p50 < 200ms** (latency-critical); `theo_series` non-degenerate post-plant.
**Plans**: 11 plans currently exist on commit `6677e5d` — these were written under v1 architecture and need teardown + replan under v2.
**See**: `roadmap.md` §3 (v2: 3.1 state engine / 3.2 scoreboard / 3.3 OCR-3-targets / 3.4 text / 3.5 arbiter-3-deques / 3.6 round-conclusion-rekey / 3.7 instrumentation / 3.8 E2E gate)

### Phase 4: Quoting layer (RESCOPED v2)
**Goal**: Bot runs three-way mode + IDLE on Kalshi markets — MM and DIRECTIONAL are first-class peers running on parallel hypothetical-fill ledgers during paper trade; POST_PLANT_QUOTE handles bomb-planted state with defensive quote-pull. Sizing is portfolio-aware (per-market + per-series aggregate cap). Defended by four always-on kill switches.
**Depends on**: Phase 1, Phase 3
**Requirements**: REQ-kalshi-order-manager, REQ-mode-selector (v2 three-way + IDLE), REQ-mm-quoter (v2 between-round only), REQ-directional-taker (v2 first-class peer), REQ-post-plant-quoter (NEW v2), REQ-kelly-sizer (v2 portfolio-aware), REQ-kill-switches, REQ-order-lifecycle-reconciliation
**Must-haves** (falsifiable):
  1. `trading_mode(state, theo, market, vega_between, vega_post_plant, kill_switch_active)` is a pure function returning `Literal["MM_BETWEEN_ROUND", "DIRECTIONAL_TAKE", "POST_PLANT_QUOTE", "IDLE"]` per DEC-001 v2; selection in declared order: kill-switch → bomb-planted → mid-round-not-planted → take-threshold → MM-min-edge → IDLE. **No "default MM" framing** — MM and DIRECTIONAL are peers.
  2. `kelly_size(theo, market_yes_ask, bankroll, series_id, current_series_exposure)` implements DEC-023 v2 portfolio Kelly: per-market cap (`PER_MARKET_CAP_FRAC = 0.05`) AND per-series aggregate cap (`SERIES_AGGREGATE_CAP_FRAC = 0.10`). Returns 0 if aggregate cap already exceeded. Never returns full-Kelly sizing.
  3. POST_PLANT_QUOTE produces defensive quote-pull within 200ms of bomb-detect (latency-critical); re-prices using post-plant lookup; takes if `|theo - market| > POST_PLANT_TAKE_THRESHOLD`, otherwise quotes at theo ± narrow spread.
  4. MM_BETWEEN_ROUND and DIRECTIONAL_TAKE write hypothetical fills to **separate ledgers** so paper-trade promotion gate (DEC-020 v2) can evaluate them independently — DIRECTIONAL can promote to live even if MM is cut for thin fills.
  5. All four kill switches active by default with no per-switch disable flag (DEC-005); each is a pure predicate over `(state, theo, market, recent_briers)`; ANY trip cancels all resting quotes and fires alert; bot stays in `dry_run=True` until promotion gate met (DEC-022).
**Plans**: TBD
**See**: `roadmap.md` §4 v2 (4.1 KalshiOrderManager / 4.2 mode-selector / 4.3 MM-between-round / 4.4 directional-taker / 4.5 post-plant-quoter / 4.6 portfolio-Kelly / 4.7 kill switches / 4.8 reconciliation)

### Phase 5: Validation (RECALIBRATED GATES v2)
**Goal**: Model and bot pass v2 promotion gate — relative Brier (`Brier(model) < Brier(market_mid) − 0.02` over 50-round windows) AND fill-count gate (MM cut from production if hypothetical fills < `MIN_FILLS_PER_MATCH`) AND latency targets AND zero ingestion-bug kill-switch trips. **MM and DIRECTIONAL ledgers evaluated independently** — DIRECTIONAL can promote even if MM is cut.
**Depends on**: Phase 4
**Requirements**: REQ-unit-and-property-tests, REQ-backtest, REQ-paper-trading (v2 gates), REQ-calibration-loop
**Must-haves** (falsifiable):
  1. 80% line coverage on `src/pricing/`; hypothesis property tests pass for the four invariants in REQ-unit-and-property-tests.
  2. Backtest replay reports per-bucket Brier (between-round / post-plant) for **both model and market_mid** side-by-side; shows live theo Brier ≤ market_mid Brier by ≥ 0.02 over 50-round windows. Order-fill backtest skipped per DEC-020.
  3. Paper-trade promotion gate satisfied (DEC-020 v2):
     a. `Brier(model) < Brier(market_mid) − 0.02` over 50-round window (replaces absolute < 0.22)
     b. MM hypothetical fills ≥ `MIN_FILLS_PER_MATCH` averaged across the event (else MM cut from production)
     c. Latency p50 event→state-commit < 500ms; bomb-detect → quote-pull p50 < 200ms; quote-cancel p99 < 100ms
     d. Zero kill-switch trips for ingestion bugs (model-trip OK; bug-trip not)
**Plans**: TBD
**See**: `roadmap.md` §5 v2 (5.1 tests / 5.2 backtest with side-by-side market Brier / 5.3 paper trading 2-ledger / 5.4 promotion gate / 5.5 calibration)

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

### Phase 7: Operational maturity (v2 — adds covariance Kelly)
**Goal**: Bot is sustainably operable in production — daily/weekly automated reporting, drift alerting, an incident runbook, a portfolio-level loss limit distinct from per-market kill switches, AND **full covariance-aware portfolio Kelly** that replaces the simple aggregate cap from Phase 4.
**Depends on**: Phase 6
**Requirements**: REQ-daily-metrics-report, REQ-weekly-drift-detection, REQ-incident-runbook, REQ-portfolio-loss-limit, REQ-portfolio-correlation-kelly (NEW v2)
**Must-haves** (falsifiable):
  1. Cron job emails daily summary (matches traded, fills per strategy, P&L per strategy, Brier-vs-market, kill-switch trips, model version) every UTC day with no manual intervention.
  2. Weekly drift job compares last-7-days Brier distribution to baseline calibration set; KL divergence above threshold fires an alert with diagnostic context.
  3. Portfolio loss limit halts the bot when cumulative realized + unrealized P&L < −X% of bankroll until manual review (DEC-021); incident runbook documents remote-halt, manual-cancel-via-Kalshi-UI, image-rollback, and per-kill-switch interpretation.
  4. **Covariance-aware portfolio Kelly** replaces the v1-floor aggregate cap (DEC-023) once sufficient paper-trade + live correlation data exists. Per-series correlation matrix derived from observed inter-market beta; sizer recomputes positions accounting for cross-market correlation rather than just bounding fractional exposure.
**Plans**: TBD
**See**: `roadmap.md` §7 v2 (7.1 daily / 7.2 drift / 7.3 runbook / 7.4 loss limit / 7.5 covariance Kelly)

---

## Progress

| Phase | Plans Complete | Status | Completed |
|---|---|---|---|
| 0. Foundation | 3/3 | Complete    | 2026-04-27 |
| 1. Core pricing engine | 7/7 | Complete    | 2026-04-30 |
| 2. Round-event data | 5/5 | Complete    | 2026-05-01 |
| 3. Live ingestion layer | 5/9 | In Progress | — |
| 4. Quoting layer | 0/0 | Not started | — |
| 5. Validation | 0/0 | Not started | — |
| 6. Deployment | 0/0 | Not started | — |
| 7. Operational maturity | 0/0 | Not started | — |

---

## Coverage check

- All 39 v2 requirements (REQ-*) mapped across Phases 1–7 (was 37 in v1; +REQ-post-plant-quoter, +REQ-portfolio-correlation-kelly). Phase 0 has no REQs (bootstrap; constraint-only scope).
- No orphans, no duplicates. See `.planning/REQUIREMENTS.md` Traceability table.
- Critical-path totals (v2): Phases 0/1/2 done; Phase 3 (rescoped) ~5–7 days; Phase 4 (rescoped) ~5–7 days; Phase 5 ~3–5 days build + 2 weeks paper trade calendar; Phase 6 ~3–5 days. **~5–6 weeks calendar to first live deploy.**
- Earliest revenue: between-round directional taking after ~3 weeks if Phase 3 ingestion + Phase 4 mode selector + portfolio Kelly land cleanly. POST_PLANT_QUOTE additive on top. MM survives only if fill-count gate clears in paper trade.

---

## Backlog

### Phase 999.1: half-win-rates refresh automation + staleness sentinel + version anchor (BACKLOG)

**Goal:** Close the operational gap around `data/half_win_rates.json` becoming stale during a live VCT season. Currently the file is a static snapshot generated by the upstream `thunderedge/worktrees/half-win-rate/` project, refreshed manually only — no cron, no schedule, no staleness detector. Worth filling **BEFORE** Phase 6 deployment, not after Phase 7 drift detection.

**Requirements:** TBD (three sub-items)
- Automated weekly refresh job (cron / GitHub Action) that runs the upstream pipeline, commits the new JSON, optionally hot-reloads the bot.
- Staleness sentinel: bot reads file mtime at startup and on a timer; fires kill-switch / refuses live mode if older than `MAX_RATES_AGE_DAYS`.
- Version anchor inside the JSON (e.g., `data_through_date`, `last_event_id`) so the bot knows what window it's pricing against and Phase 5 backtest replay can reproduce historical states.

**Surfaced:** 2026-05-06 during Phase 03 discussion. Phase 7.2 drift detection (alert-only) is the only existing mitigation; covers catastrophic drift but not normal-cadence refresh during a season. Related gaps not in scope of this item: no within-event recency weighting (early-stage games count same as recent), no patch-version awareness, no roster-change awareness.

**Plans:**
- [ ] TBD (promote with `/gsd-review-backlog` when ready)
