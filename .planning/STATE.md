---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_phase: 03
current_plan: 3 of 9
status: in_progress
stopped_at: Completed 03-02-round-conclusion-v2-surface-PLAN.md
last_updated: "2026-05-08T19:08:02.668Z"
last_activity: 2026-05-08
progress:
  total_phases: 9
  completed_phases: 3
  total_plans: 24
  completed_plans: 18
  percent: 75
---

# STATE — Valorant Live Pricing Model

**Project:** Valorant Live Pricing Model
**Last activity:** 2026-05-08
**Last activity description:** Phase 03 Plan 02 complete — wholesale rewrite of RoundConclusionLookup to v2 surface (between_round_p + post_plant_p + schema_version=2 gate); live_theo bomb_planted dispatch per D-05; atomic-replace models/round_conclusion.json with v2 synthetic-cell file; REQ-round-conclusion-lookup GREEN; 250 passed / 40 xfailed.

---

## Project Reference

- **Core value:** Live pricing engine for Valorant BO3 series + per-map Kalshi markets. Re-prices the series at any moment during a live match, hybrid market-maker / directional taker, fast enough to capture edge or — at minimum — avoid being adversely selected.
- **Owner:** jxc2008@nyu.edu
- **Status:** Phases 0/1/2 complete. Phase 3 (live ingestion) in progress — Plans 00/01/02 done; 6 plans remaining.
- **Source-of-truth design docs:** `prd.md`, `roadmap.md`, `CLAUDE.md` at repo root.
- **Locked decisions:** 22 (DEC-001 through DEC-022) — see `.planning/PROJECT.md` `<decisions>` blocks.

## Current Position

Phase: 03 (live-ingestion-layer) — IN PROGRESS
Plan: 3 of 9 done (03-00 test infrastructure, 03-01 match-state-v2-migration, 03-02 round-conclusion-v2-surface)

- **Current phase:** 03
- **Current plan:** 3 of 9
- **Status:** In progress; next plan is 03-03-arbiter-and-latency
- **Progress:** [████████░░] 75%

```
Phase 0  [##########] Complete (3/3 plans)
Phase 1  [##########] Complete (7/7 plans)
Phase 2  [##########] Complete (5/5 plans)
Phase 3  [###░░░░░░░] In progress (3/9 plans)
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
| 3 — Live ingestion layer | In progress | 9 (03-00..03-08) | 3 |
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
| Coverage on `src/pricing/` | ≥ 80% | not yet measured (263 tests pass) |
| Docker image size | < 500 MB | not yet built |
| Phase 03 P00 | 8 min, 3 tasks, 16 files | RED-stubs landed; 263 passed / 31 xfailed |
| Phase 03 P01 | 6h 14m wall-clock (~30 min active), 2 tasks, 14 files | MatchState v2 + JSONL replay GREEN; 268 passed / 26 xfailed |
| Phase 03 P02 | 6h 49m wall-clock (~30 min active), 3 tasks, 14 files | RoundConclusion v2 surface + D-05 dispatch GREEN; 250 passed / 40 xfailed |

## Accumulated Context

### Decisions

#### Phase 03

- **2026-05-07 — RED-stub xfail pattern: pytest.xfail() runtime call inside body, not @pytest.mark.xfail decorator.** Wave-N executors flip stubs by replacing the body; decorator removal would leave dead xfail-call lines. Recorded in 03-00 SUMMARY.
- **2026-05-07 — Conftest fixtures return dict[str, Any] instead of MatchState dataclass.** Survives Wave 1 atomic move of MatchState from src/pricing/data.py to src/state/match_state.py — Wave 1's first task patches the `make_match_state` helper to return dataclass instances once src/state/match_state.py exists.
- **2026-05-08 — One-line transition shim across Task 1 → Task 2 in src/pricing/data.py for MatchState.** Plan 03-01 picked the shim path (vs Task-1 hard-delete) so the import-rewrite seam was atomic at Task 1; Task 2 deletes the shim atomically with the helper additions. No long-term residue.
- **2026-05-08 — All-positional dataclass fields with NO defaults on MatchState v2.** 19 fields total; forces every caller to be explicit. Mirrors the Phase 1 idiom and dodges the kw_only / mixed-default-after-non-default trap.
- **2026-05-08 — `with_update` is pure (no JSONL I/O); module-level `commit()`/`quarantine()` helpers wrap with the disk-side audit append.** Per D-02 / D-03. Single-writer invariant documented at the helper module-docstring level.
- **2026-05-08 — Replay test compares all 18 dataclass fields EXCEPT last_updated_ts.** D-02 marks last_updated_ts as informational-only. In-memory and replay paths run with_update at different real times; comparing every other field catches every actual divergence.
- **2026-05-08 — `commit()` records t_state_committed BEFORE the JSONL write.** Disk write latency excluded from D-03 hot-path budget. `commit()` mutates the caller-supplied `timestamps` dict in place so the arbiter (Wave 3A) can read t_state_committed immediately after `commit()` returns.
- [Phase 03]: v2 surface DELETES v1 in same commit (no compatibility shim) — Phase 2 D-15 frozen-surface contract intentionally broken — no value keeping a v1 5-arg lookup() against a v2 (att, def_, time_bucket, side, map) schema. CRule 1 / DEC-010 reject parallel models.
- [Phase 03]: Future-round transitions ALWAYS use between-round fn closure in bomb_planted branch (D-05) — Nested post-plant lookups would require alive-counts at every future round (impossible — those are post-plant event state) and would blow up the cache key space. Single current-round override matches DEC-018's one-step branch composition pattern.
- [Phase 03]: Defensive None-guard for malformed bomb_planted=True states falls back to between-round path with degraded confidence — bomb_planted=True with missing attackers_alive/defenders_alive/time_left_s falls back rather than hard-erroring; Phase 4 mode-selector reads low confidence and maps to IDLE per DEC-001 v2. Hard error would crash the live engine on data races between OCR worker and arbiter.
- [Phase 03]: Asymmetric HalfRates required to test the dispatch override (symmetric rates make dispatch invisible) — Under symmetric rates DP delivers v(state_after_a_wins) == v(state_after_b_wins) by symmetry, so p*v + (1-p)*v == v for any p. Test fixture uses TeamA at 0.6 / TeamB at 0.4 to break symmetry; comment block in _make_half_rates flags the trap.

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
- **Calibrated artifact shipped.** `models/round_conclusion.json` (324 KB) — 22/44/524/1886 cells in the 5-tier fallback chain. `side_baseline = {atk: 0.5256, def: 0.4751}`. Phase 1's flat-0.5 stub replaced.
- **Live engine smoke verified.** `live_theo(state)` consuming the calibrated lookup produces non-degenerate predictions.

### Active todos

None.

### Blockers

None.

### Open TBDs (intentional, deferred per PRD §9)

1. Bankroll size and `PER_MARKET_CAP_FRAC` — operational, depends on capital allocation.
2. Threshold values — initial guesses, re-tune in Phase 5 after 20+ live matches.
3. Vega formula refinement — DEC-018 picks variant (a) initially; revisit in Phase 5.
4. Backtest fidelity — DEC-020 skips order-fill backtest in favor of paper trading; reconsider if Kalshi exposes historical order-book data.

## Session Continuity

- **Last session ended:** 2026-05-08 — Phase 03 Plan 02 (round-conclusion-v2-surface) shipped. Commits: `cc70aa0` (Task 1: v2 constants + delete economy.py per CLAUDE.md, landed in prior session) → `3005709` (Task 2: rewrite RoundConclusionLookup to v2 surface + atomic-replace round_conclusion.json) → `a519023` (Task 3: live_theo bomb_planted dispatch (D-05) + Phase 1+2 regression patch).
- **Stopped at:** Completed 03-02-round-conclusion-v2-surface-PLAN.md
- **Next action:** Plan 03-03 (arbiter-and-latency). Wave 3A — 3-deque cross-source arbiter (score_changes / bomb_events / round_end_events per DEC-006 v2) + six-stage timestamp lineage on every event + REQ-cross-source-arbiter / REQ-latency-instrumentation acceptance.
- **Cross-phase context lookup:** `.planning/PROJECT.md` `<decisions>` blocks expose all 22 DECs. Constraint detail in `.planning/intel/constraints.md`. Phase 3 implementation decisions in `.planning/phases/03-live-ingestion-layer/03-CONTEXT.md` (D-01 through D-14).
