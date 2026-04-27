# STATE — Valorant Live Pricing Model

**Project:** Valorant Live Pricing Model
**Last activity:** 2026-04-27
**Last activity description:** Bootstrapped GSD planning artifacts (PROJECT.md, REQUIREMENTS.md, ROADMAP.md, STATE.md) from existing prd.md + roadmap.md via doc-synthesizer intel.

---

## Project Reference

- **Core value:** Live pricing engine for Valorant BO3 series + per-map Kalshi markets. Re-prices the series at any moment during a live match, hybrid market-maker / directional taker, fast enough to capture edge or — at minimum — avoid being adversely selected.
- **Owner:** jxc2008@nyu.edu
- **Status:** Draft
- **Source-of-truth design docs:** `prd.md`, `roadmap.md`, `CLAUDE.md` at repo root.
- **Locked decisions:** 22 (DEC-001 through DEC-022) — see `.planning/PROJECT.md` `<decisions>` blocks.

## Current Position

- **Current phase:** none (planning artifacts just bootstrapped)
- **Current plan:** none
- **Status:** awaiting first `/gsd-plan-phase` invocation
- **Progress:** 0/8 phases complete (0%)

```
Phase 0  [          ] Pending
Phase 1  [          ] Pending
Phase 2  [          ] Pending
Phase 3  [          ] Pending
Phase 4  [          ] Pending
Phase 5  [          ] Pending
Phase 6  [          ] Pending
Phase 7  [          ] Pending
```

## Phase Status

| Phase | Status | Plans | Completed |
|---|---|---|---|
| 0 — Foundation | Pending | none | — |
| 1 — Core pricing engine | Pending | none | — |
| 2 — Round-event data | Pending | none | — |
| 3 — Live ingestion layer | Pending | none | — |
| 4 — Quoting layer | Pending | none | — |
| 5 — Validation | Pending | none | — |
| 6 — Deployment | Pending | none | — |
| 7 — Operational maturity | Pending | none | — |

## Performance Metrics

| Metric | Target | Measured |
|---|---|---|
| End-to-end latency (event → theo) | < 500 ms (median) | not yet measured |
| Quote-cancel latency (state change → all stale orders pulled) | < 100 ms | not yet measured |
| Brier vs static-prior baseline (50-round window) | beat by ≥ 0.02 | not yet measured |
| Paper-trade promotion gate Brier | < 0.22 over ≥ 1 full event | not yet measured |
| Coverage on `src/pricing/` | ≥ 80% | not yet measured |
| Docker image size | < 500 MB | not yet built |

## Accumulated Context

### Recent decisions (cross-phase)

22 locked decisions inherited from `prd.md` + `roadmap.md` via synthesizer. See `.planning/PROJECT.md` for full text. Highlights:

- DEC-001 — hybrid trading mode (event-trigger with vega override)
- DEC-002 — single DP for BO3 series + per-map (no parallel models)
- DEC-009 — OT explicit hard-stop at total=24 with documented coinflip leaf (resolves audit-engine bug)
- DEC-010 — single canonical `live_theo` entry point (no triplet sprawl)
- DEC-017 — Phase-2 API decision gate (Path A / Path B / Path C)
- DEC-022 — dry-run by default; live trading requires explicit `--live` flag

### Active todos

- [ ] Phase 0 (Foundation) — first executable phase; runs `/gsd-plan-phase 0` when ready

### Blockers

None.

### Open TBDs (intentional, deferred per PRD §9)

1. Bankroll size and `PER_MARKET_CAP_FRAC` — operational, depends on capital allocation.
2. Threshold values (`VEGA_DIRECTIONAL_THRESHOLD`, kill-switch constants) — initial guesses, re-tune in Phase 5 after 20+ live matches.
3. Vega formula refinement — DEC-018 picks variant (a) initially; revisit in Phase 5.
4. Backtest fidelity — DEC-020 skips order-fill backtest in favor of paper trading; reconsider if Kalshi exposes historical order-book data.

## Session Continuity

- **Last session ended:** 2026-04-27 — initial GSD bootstrap from existing prd.md + roadmap.md.
- **Next action:** invoke `/gsd-discuss-phase 0` (recommended) or `/gsd-plan-phase 0` directly to begin Phase 0 (Foundation). Phases 1, 2, 3 can run in parallel after Phase 0; the discussion phase is most valuable for Phase 2 (DEC-017 path-decision gate) and Phase 3 (ingestion architecture).
- **Cross-phase context lookup:** `.planning/PROJECT.md` `<decisions>` blocks expose all 22 DECs to future plan-phase agents. Constraint detail in `.planning/intel/constraints.md`.
