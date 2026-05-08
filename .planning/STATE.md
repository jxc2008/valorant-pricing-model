---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_phase: 03
current_plan: 5 of 9
status: in_progress
stopped_at: Completed 03-04-scoreboard-poller-PLAN.md
last_updated: "2026-05-08T19:38:14Z"
last_activity: 2026-05-08
progress:
  total_phases: 9
  completed_phases: 3
  total_plans: 24
  completed_plans: 20
  percent: 83
---

# STATE — Valorant Live Pricing Model

**Project:** Valorant Live Pricing Model
**Last activity:** 2026-05-08
**Last activity description:** Phase 03 Plan 04 complete — async rib.gg scoreboard poller (REQ-scoreboard-polling) on Phase 2 ETL resilience patterns ported sync->async (Connection: close header + tenacity Retry-After-aware wait_base subclass capped 10s + 5-attempt cap + 5-failure cycle cooldown 60s); pushes one PendingEvent(source='ribgg', event_type='score_change', fields_proposed={a_round, b_round}) per non-degenerate fetch into Arbiter.score_changes for the DEC-006 v2 ≥2-source rule; 264 passed / 33 xfailed; 10 min wall-clock.

---

## Project Reference

- **Core value:** Live pricing engine for Valorant BO3 series + per-map Kalshi markets. Re-prices the series at any moment during a live match, hybrid market-maker / directional taker, fast enough to capture edge or — at minimum — avoid being adversely selected.
- **Owner:** jxc2008@nyu.edu
- **Status:** Phases 0/1/2 complete. Phase 3 (live ingestion) in progress — Plans 00/01/02/03/04 done; 4 plans remaining (03-05 OCR / 03-06 text-listener / 03-07 ETL re-run + calibration / 03-08 E2E gate).
- **Source-of-truth design docs:** `prd.md`, `roadmap.md`, `CLAUDE.md` at repo root.
- **Locked decisions:** 22 (DEC-001 through DEC-022) — see `.planning/PROJECT.md` `<decisions>` blocks.

## Current Position

Phase: 03 (live-ingestion-layer) — IN PROGRESS
Plan: 5 of 9 done (03-00 test infrastructure, 03-01 match-state-v2-migration, 03-02 round-conclusion-v2-surface, 03-03 arbiter-and-latency, 03-04 scoreboard-poller)

- **Current phase:** 03
- **Current plan:** 5 of 9
- **Status:** In progress; next plan is 03-05-ocr-pipeline
- **Progress:** [████████▌░] 83%

```
Phase 0  [##########] Complete (3/3 plans)
Phase 1  [##########] Complete (7/7 plans)
Phase 2  [##########] Complete (5/5 plans)
Phase 3  [#####░░░░░] In progress (5/9 plans)
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
| 3 — Live ingestion layer | In progress | 9 (03-00..03-08) | 5 |
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
| Phase 03 P03 | 7 min, 3 tasks, 8 files | DEC-006 v2 arbiter + 6-stage timestamps GREEN; 259 passed / 27 xfailed |
| Phase 03 P04 | 10 min, 2 tasks, 5 files | Async rib.gg scoreboard poller + tenacity Retry-After-aware async resilience GREEN; 264 passed / 33 xfailed |

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
- **2026-05-08 — score_change holds (re-queues), doesn't quarantine, on first sight of single-source events.** Quarantine only fires after _DEQUE_MAX_AGE_S=3s wall-clock staleness. Rationale: a fresh single-source event typically cross-confirms in the next 50ms tick once 2nd source emits; quarantining immediately would miss typical real-world cadence.
- **2026-05-08 — Bomb / round_end soft-commit is the production contract; arbiter does NOT roll back.** Rolling back would mutate the seq_id chain (subsequent commits leapfrog or reuse), breaking replay determinism. Phase 4 mode-selector handles the false-positive case via IDLE quoting on state mismatch.
- **2026-05-08 — Sibling JSONL files (event_log + metrics), not a single combined file.** event_log = state replay (commit + quarantine lines); metrics = latency analysis (commits only with fields_changed_keys for provenance, NO field values). Coupling them would force Phase 5 latency analysis to filter quarantine-line semantics; the split keeps each reader simple.
- **2026-05-08 — '|'-joined source provenance with sorted alphabetical order in JSONL line.** Set iteration order is non-deterministic across Python runs (CPython 3.11 randomized hashing). Replay determinism requires identical source string across runs of same input — `tuple(sorted(distinct_sources))` guarantees this.
- **2026-05-08 — Local `_DEQUE_MAX_AGE_S = 3.0` constant in arbiter.py rather than a public src.config.constants entry.** The arbiter is the sole consumer; promoting it would add public API surface no other module reads. Internal arbiter implementation detail; the public threshold ARBITER_SCORE_WINDOW_S IS in constants.py per CRule 12.
- **2026-05-08 — Test the inner helpers (_fetch_match_details + _extract_score_change_fields + manual deque push) rather than spinning the infinite run_scoreboard_poller loop.** Same code path the loop body executes per cycle; eliminates asyncio-task-cancellation flakiness. Documented inline in test_poller_emits_typed_events.
- **2026-05-08 — Tenacity wait cap 10s in the live poller (vs Phase 2 sync ETL's 30/60s cap).** Outer poll cadence is 5s; longer tenacity sleeps would starve arbiter.score_changes of the ribgg arm for multiple cycles. Caps both Retry-After honoring and exp-backoff fallback at 10s.
- **2026-05-08 — _extract_score_change_fields returns FULL {a_round, b_round} fields_proposed shape (NOT diff-only).** Arbiter groups score_change events by tuple(sorted(fields_proposed.items())); diff-only ribgg pushes wouldn't match full-shape OCR pushes and the ≥2-source rule would never fire.
- **2026-05-08 — Defensive _extract_score_change_fields returns None on sparse / non-int payloads.** The arbiter's existing 5s staleness kill-switch handles extended response gaps; hard-failing on a transient JSON-shape blip would propagate to a cycle-level exception + cooldown unnecessarily.
- **2026-05-08 — Same-commit Rule-3 prophylactic for tests/config/test_constants.py allow-list.** Wave 3A's SUMMARY documented this exact failure as a recurring blocking auto-fix when new constants land. Updating EXPECTED_NAMES + EXPECTED_TYPES in the SAME commit as the constants definition skips the post-hoc fix loop.

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

- **Last session ended:** 2026-05-08 — Phase 03 Plan 04 (scoreboard-poller) shipped. Commits: `440b656` (Task 1: feat — async rib.gg scoreboard poller with tenacity resilience + 3 new constants) → `5de7e6a` (Task 2: test — aioresponses-mocked fetch + Retry-After honoring).
- **Stopped at:** Completed 03-04-scoreboard-poller-PLAN.md
- **Next action:** Plan 03-05 (ocr-pipeline). Wave 3C — Tesseract-only OCR pipeline against three HUD targets (score banner / bomb-plant icon / round-end banner) + post-plant attackers/defenders-alive widget per DEC-024 v2 / D-11/D-12/D-13. Pushes PendingEvent(source="ocr_score" / "ocr_bomb" / "ocr_round_end" / "ocr_post_plant_alive") into the corresponding arbiter deques.
- **Cross-phase context lookup:** `.planning/PROJECT.md` `<decisions>` blocks expose all 22 DECs. Constraint detail in `.planning/intel/constraints.md`. Phase 3 implementation decisions in `.planning/phases/03-live-ingestion-layer/03-CONTEXT.md` (D-01 through D-14).
