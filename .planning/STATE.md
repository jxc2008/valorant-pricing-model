---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_phase: 03
current_plan: 0
status: ready
stopped_at: Phase 02 complete — Path A calibrated lookup shipped
last_updated: "2026-05-01T17:30:00Z"
last_activity: 2026-05-01
progress:
  total_phases: 8
  completed_phases: 3
  total_plans: 15
  completed_plans: 15
  percent: 100
---

# STATE — Valorant Live Pricing Model

**Project:** Valorant Live Pricing Model
**Last activity:** 2026-05-01
**Last activity description:** Phase 02 complete — Wave 3 (Plan 02-04 calibrator) and Wave 4 (Plan 02-05 close-out) shipped sequentially after Path A probe Pass:YES.

---

## Project Reference

- **Core value:** Live pricing engine for Valorant BO3 series + per-map Kalshi markets. Re-prices the series at any moment during a live match, hybrid market-maker / directional taker, fast enough to capture edge or — at minimum — avoid being adversely selected.
- **Owner:** jxc2008@nyu.edu
- **Status:** Phases 0/1/2 complete. Phase 3 (live ingestion) is the next planning candidate. Phases 3 + 4 unblock the live trading path; Phase 2 was the only prerequisite Phase 4 needs beyond Phase 1.
- **Source-of-truth design docs:** `prd.md`, `roadmap.md`, `CLAUDE.md` at repo root.
- **Locked decisions:** 22 (DEC-001 through DEC-022) — see `.planning/PROJECT.md` `<decisions>` blocks.

## Current Position

Phase: 03 (live-ingestion-layer) — READY FOR PLANNING
Plan: 0 of TBD

- **Current phase:** 03
- **Current plan:** 0 (no plans yet — phase needs `/gsd-spec-phase` or `/gsd-discuss-phase` to begin)
- **Status:** Ready to plan Phase 03
- **Progress:** 3/8 phases complete (37.5%); 15/15 planned plans complete (100% of planned)

```
Phase 0  [##########] Complete (3/3 plans)
Phase 1  [##########] Complete (7/7 plans)
Phase 2  [##########] Complete (5/5 plans)
Phase 3  [          ] Pending (no plans yet)
Phase 4  [          ] Pending
Phase 5  [          ] Pending
Phase 6  [          ] Pending
Phase 7  [          ] Pending
```

## Phase Status

| Phase | Status | Plans | Completed |
|---|---|---|---|
| 0 — Foundation | Complete (2026-04-27) | 3 (00-01, 00-02, 00-03) | 3 |
| 1 — Core pricing engine | Complete | 7 (01-01..01-07) | 7 |
| 2 — Round-event data | Complete (2026-05-01) | 5 (02-01..02-05) | 5 |
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
| Coverage on `src/pricing/` | ≥ 80% | not yet measured (252 tests pass) |
| Docker image size | < 500 MB | not yet built |

## Accumulated Context

### Recent decisions (cross-phase)

22 locked decisions inherited from `prd.md` + `roadmap.md` via synthesizer. See `.planning/PROJECT.md` for full text. Highlights:

- DEC-001 — hybrid trading mode (event-trigger with vega override)
- DEC-002 — single DP for BO3 series + per-map (no parallel models)
- DEC-009 — OT explicit hard-stop at total=24 with documented coinflip leaf (resolves audit-engine bug)
- DEC-010 — single canonical `live_theo` entry point (no triplet sprawl)
- DEC-017 — Phase-2 API decision gate (Path A / Path B / Path C) — **resolved Path A on 2026-05-01**
- DEC-022 — dry-run by default; live trading requires explicit `--live` flag

### Phase 2 outcomes (2026-05-01)

- **Path A passed.** rib.gg `/v1/{events,series,matches/{id}/details}` chain delivered 1000 distinct matches / 42586 rounds. `02-PROBE-LOG.md` records `Pass: YES`, D-05 partial-pass NOT triggered, ts_round_start + ts_round_end at 100% coverage.
- **Calibrated artifact shipped.** `models/round_conclusion.json` (324 KB) — 22/44/524/1886 cells in the 5-tier (cells_full → cells_no_map → cells_no_econ → side_baseline → 0.5) fallback chain. `side_baseline = {atk: 0.5256, def: 0.4751}`. Phase 1's flat-0.5 stub replaced; `RoundConclusionLookup.from_json` / `to_json` are additive.
- **Live engine smoke verified.** `live_theo(state)` consuming the calibrated lookup produces non-degenerate predictions: `theo_series=0.6199`, `theo_map=(0.7363, 0.4787, 0.5242)`, `vega=0.0021`, `confidence=0.0` — all within the [0.01, 0.99] band.
- **In-flight bug fixes (Plan 02-03 — surfaced during operator's --live run):**
  - `hasSeries=true` URL param caused 30s server timeouts on every page; removed (commit `fafa6ae`). `divisions[]=VCT` also doesn't filter server-side; client-side filter at line 417 is what works.
  - `transform_match_to_rows` blew up on null rosters from cancelled/forfeited matches; defensive `.get()` + early return + try/except in caller (commit `fafa6ae`).
- **In-flight bug fixes (Plan 02-04 — surfaced during execution):**
  - JOIN `m.match_id = re.match_id` returned 0 rows because `round_events.match_id` carries `::1`/`::2` perspective suffixes from Plan 02-03 BLOCKER 4. Fixed via `substr(re.match_id, 1, instr(re.match_id, '::') - 1)` + `team_a_team_num` alignment.
  - `.gitignore` blanket `models/` prevented committing the D-15 artifact. Changed to `models/*` + `!models/round_conclusion.json` exception.

### Active todos

None — Phase 02 close-out complete.

### Blockers

None.

### Open TBDs (intentional, deferred per PRD §9)

1. Bankroll size and `PER_MARKET_CAP_FRAC` — operational, depends on capital allocation.
2. Threshold values (`VEGA_DIRECTIONAL_THRESHOLD`, kill-switch constants) — initial guesses, re-tune in Phase 5 after 20+ live matches.
3. Vega formula refinement — DEC-018 picks variant (a) initially; revisit in Phase 5.
4. Backtest fidelity — DEC-020 skips order-fill backtest in favor of paper trading; reconsider if Kalshi exposes historical order-book data.

## Session Continuity

- **Last session ended:** 2026-05-01 — Phase 02 fully shipped. Phase 2 chain: probe (`56f807d`) → resilience patches (`cd6076e`, `fafa6ae`) → checkpoint clearance + PROBE-LOG (`9981248`) → calibrator (`6ad51f4`, `f344da6`, `afed250`) → close-out (`7748e9f`, `862c69a`, `24182b8`).
- **Stopped at:** Phase 02 complete — Path A calibrated lookup shipped
- **Next action:** Phase 03 (live ingestion layer) needs spec/discuss → plan → execute. Per `roadmap.md` §3, the phase covers `MatchState` engine + scoreboard polling + OCR pipeline + text listeners + cross-source arbiter + latency instrumentation. Phase 3 is sub-500ms-latency live state plumbing; it's the largest phase by surface area. Recommended next command: `/gsd-spec-phase 03` to refine WHAT it delivers before discussing HOW.
- **Cross-phase context lookup:** `.planning/PROJECT.md` `<decisions>` blocks expose all 22 DECs to future plan-phase agents. Constraint detail in `.planning/intel/constraints.md`.
