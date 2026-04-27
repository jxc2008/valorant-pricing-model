# Synthesis Summary

Entry point for downstream consumers (`gsd-roadmapper`). Produced by `gsd-doc-synthesizer` from per-doc classifications + source documents.

**Mode:** new (bootstrap; no existing `.planning/` context to reconcile)
**Precedence ordering applied:** `ADR > SPEC > PRD > DOC` (no ADRs in scope)
**Cycle detection:** clean (DAG: roadmap.md → prd.md; prd.md has no back-reference)

---

## Doc inventory

| Type | Count | Sources |
|---|---|---|
| ADR | 0 | — |
| SPEC | 1 | `roadmap.md` |
| PRD | 1 | `prd.md` |
| DOC | 0 | — |
| UNKNOWN | 0 | — |

Both source classifications had `confidence: high`, `manifest_override: true`, `locked: false`.

---

## Decisions extracted

22 distinct decisions (DEC-001 through DEC-022). None flagged `locked: true` at classification level, but PRD §9 explicitly enumerates 9 decisions as "resolved" — these are treated as authoritative-by-source. SPEC corroborates 17 of them with implementation specifics.

Highlights:

- DEC-001 hybrid trading mode (event-trigger + vega override)
- DEC-002 single DP for BO3 series + per-map (no parallel models)
- DEC-003 Bradley-Terry round-win-prob blend
- DEC-004 half-Kelly + per-market cap
- DEC-005 four kill switches, all-on, no per-switch disable
- DEC-006 tiered ingestion confirmation by event type
- DEC-007 hierarchical-lookup round-conclusion model
- DEC-008 hybrid local dev + cloud production
- DEC-009 OT explicit hard-stop at total=24 (documented coinflip leaf)
- DEC-010 single canonical `live_theo` entry point
- DEC-011 pistol + anti-eco modeled explicitly (rounds 1, 2, 3, 13, 14, 15)
- DEC-012 conviction clips at [0.01, 0.99]
- DEC-013 audited-engine salvage map (keep / partial / skip)
- DEC-014 tooling: Python 3.11, uv, pytest+hypothesis, ruff, mypy --strict
- DEC-015 SQLite for cache; in-memory only for live state
- DEC-016 magic numbers centralized in `config/constants.py`
- DEC-017 Phase-2 API decision gate (rib.gg/bo3.gg → OCR fallback → defer)
- DEC-018 vega initial formula (variance of next theo update)
- DEC-019 `src/{pricing,state,ingestion,quoting,sizing,config}/` layout
- DEC-020 paper-trade promotion gate (≥1 event, Brier < 0.22, no bug-trip kill switches)
- DEC-021 daily portfolio loss limit (separate from per-market kill switches)
- DEC-022 dry-run by default; `--live` required at entry point

Full text: `.planning/intel/decisions.md`

---

## Requirements extracted

37 requirements (REQ-*). Coverage across all 8 roadmap phases:

- Pricing output contract: REQ-theo-series-output, REQ-theo-map-output, REQ-confidence-output, REQ-vega-output, REQ-end-to-end-latency
- Pricing core: REQ-bo3-dp-engine, REQ-bradley-terry-blend, REQ-pistol-anti-eco-modeling, REQ-ot-handling, REQ-round-conclusion-lookup, REQ-canonical-live-theo
- Trading mode + sizing: REQ-mode-selector, REQ-kelly-sizer
- Data acquisition: REQ-round-event-data-pipeline
- Ingestion: REQ-match-state-engine, REQ-scoreboard-polling, REQ-ocr-pipeline, REQ-text-listener, REQ-cross-source-arbiter, REQ-latency-instrumentation
- Quoting: REQ-kalshi-order-manager, REQ-mm-quoter, REQ-directional-taker, REQ-kill-switches, REQ-order-lifecycle-reconciliation
- Validation: REQ-unit-and-property-tests, REQ-backtest, REQ-paper-trading, REQ-calibration-loop
- Deployment: REQ-containerization, REQ-cloud-vm, REQ-deploy-pipeline, REQ-secrets-handling, REQ-logging-and-alerting, REQ-monitoring-dashboard
- Operational: REQ-daily-metrics-report, REQ-weekly-drift-detection, REQ-incident-runbook, REQ-portfolio-loss-limit

Full text: `.planning/intel/requirements.md`

---

## Constraints extracted

26 constraints (CON-*) covering NFRs, schemas, API contracts, and protocols:

- NFRs: mypy --strict pricing, no magic numbers, dry-run default, tooling versions, image size, coverage target, promotion gate, kill switches always-on, secrets handling, domain-constants baseline
- Schemas: live state no-SQLite, theo output, MatchState, economy buckets, package layout, round_events table, event timestamp fields
- API contracts: single canonical live_theo, BO3 DP signature, Bradley-Terry formula, conviction clip, OT hard-stop, trading-mode signature, Kelly sizer signature, MM spread formula, round-conclusion fallback chain
- Protocols: arbiter tiered confirmation, ingestion cadences, phase dependency graph

Full text: `.planning/intel/constraints.md`

---

## Context topics

11 topical context entries: project relationship to thunderedge/, origin problem statement, Black-Scholes conceptual analog, architecture overview, three-tier inputs taxonomy, latency budget per source, salvage map from audited engine, documented bugs in `theo_engine.py`, open TBDs, explicit non-goals, PRD-level build-phase framing, critical-path timeline, data sources summary, success metrics.

Full text: `.planning/intel/context.md`

---

## Conflicts

| Bucket | Count |
|---|---|
| BLOCKERS | 0 |
| WARNINGS | 0 |
| INFO | 4 |

**INFO (4):**
1. **Kill-switch constant naming (user-resolved 2026-04-27):** `KILL_SWITCH_*` prefix wins per roadmap.md §0.4. CLAUDE.md updated to match. Canonical names locked in `constraints.md / CON-domain-constants-baseline`.
2. OT policy: PRD §3 "non-goal" phrasing reconciled with PRD §12.2 #3 + roadmap §1.4 explicit-hard-stop operationalization (not actually contradictory once parsed precisely).
3. Vega formula: SPEC §1.6 picked variant (a) of three PRD §9 TBD #3 alternatives.
4. Backtest fidelity: SPEC §5.2 picked option (a) (skip order-fill backtest) of two PRD §9 TBD #4 alternatives.

Full report: `.planning/INGEST-CONFLICTS.md`

---

## Pointers for downstream

- `.planning/intel/decisions.md` — DEC-001 through DEC-022
- `.planning/intel/requirements.md` — 37 REQs with acceptance criteria where source provides them
- `.planning/intel/constraints.md` — 26 CONs by type (api-contract / schema / nfr / protocol)
- `.planning/intel/context.md` — narrative background and salvage history
- `.planning/INGEST-CONFLICTS.md` — three-bucket conflict report

Status for `gsd-roadmapper`: **READY FOR ROUTING** — all conflicts resolved (kill-switch naming locked to `KILL_SWITCH_*` per user 2026-04-27). No BLOCKERs, no open WARNINGs.
