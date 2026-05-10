---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_phase: 03
current_plan: 7 of 9
status: in_progress
stopped_at: Completed 03-06-text-listener-PLAN.md
last_updated: "2026-05-10T01:58:00Z"
last_activity: 2026-05-10
progress:
  total_phases: 9
  completed_phases: 3
  total_plans: 24
  completed_plans: 22
  percent: 92
---

# STATE — Valorant Live Pricing Model

**Project:** Valorant Live Pricing Model
**Last activity:** 2026-05-10
**Last activity description:** Phase 03 Plan 06 complete — Twitter v2 streaming text listener (REQ-text-listener / 03-CONTEXT D-07): tweepy.asynchronous.AsyncStreamingClient subclass + score-signal regex (\d{1,2}\s*[-:]\s*\d{1,2}) + TWITTER_BEARER_TOKEN env-gate degrading to no-op (RESEARCH Pitfall 1: Basic tier deprecated 2026-02-06 for new accounts); soft-confirm-only contract — pushes PendingEvent(source=twitter) into arbiter.score_changes, NEVER sole-sources a state mutation per arbiter's >=2-source rule; 2 new constants (TWITTER_API_BASE_URL + TWITTER_RULE_SET with 9 entries: 5 hashtags + 4 league/caster accounts). 3 GREEN tests replaced Wave-0 xfail stubs (test_emits_typed_soft_events / test_twitter_only_update_quarantined / test_no_token_noop). mypy + ruff clean. 287 passed / 26 xfailed (up 3 GREEN from 284/29). 8 min wall-clock.

---

## Project Reference

- **Core value:** Live pricing engine for Valorant BO3 series + per-map Kalshi markets. Re-prices the series at any moment during a live match, hybrid market-maker / directional taker, fast enough to capture edge or — at minimum — avoid being adversely selected.
- **Owner:** jxc2008@nyu.edu
- **Status:** Phases 0/1/2 complete. Phase 3 (live ingestion) in progress — Plans 00/01/02/03/04/05/06 done; 2 plans remaining (03-07 ETL re-run + calibration / 03-08 E2E gate).
- **Source-of-truth design docs:** `prd.md`, `roadmap.md`, `CLAUDE.md` at repo root.
- **Locked decisions:** 22 (DEC-001 through DEC-022) — see `.planning/PROJECT.md` `<decisions>` blocks.

## Current Position

Phase: 03 (live-ingestion-layer) — IN PROGRESS
Plan: 7 of 9 done (03-00 test infrastructure, 03-01 match-state-v2-migration, 03-02 round-conclusion-v2-surface, 03-03 arbiter-and-latency, 03-04 scoreboard-poller, 03-05 ocr-pipeline, 03-06 text-listener)

- **Current phase:** 03
- **Current plan:** 7 of 9
- **Status:** In progress; next plan is 03-07-etl-rerun-and-calibration
- **Progress:** [█████████░] 92%

```
Phase 0  [##########] Complete (3/3 plans)
Phase 1  [##########] Complete (7/7 plans)
Phase 2  [##########] Complete (5/5 plans)
Phase 3  [#######░░░] In progress (7/9 plans)
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
| 3 — Live ingestion layer | In progress | 9 (03-00..03-08) | 7 |
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
| Phase 03 P05 | 10 min, 4 tasks, 11 files | Tesseract OCR pipeline (4 async workers + FrameSource Protocol + 9 constants + dump_roi_overlay.py operator helper) GREEN; 284 passed / 19 xfailed (GREEN'd 6 OCR tests; round-end-banner placeholder x2 xfailed for Phase 3.5 fixture) |
| Phase 03 P06 | 8 min, 2 tasks, 5 files | Twitter v2 text listener (REQ-text-listener / D-07): tweepy.asynchronous.AsyncStreamingClient subclass + score-signal regex + degrade-to-no-op env gate + soft-confirm-only contract via arbiter.score_changes (>=2-source rule blocks Twitter-alone commits); 9-rule TWITTER_RULE_SET. 287 passed / 26 xfailed (3 GREEN, up from 284/29). |

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
- **2026-05-08 — OCR module docstring paraphrases the DEC-024 v2 cuts.** Initial draft used the literal forbidden tokens (kill_feed / ult_orb / etc) inside a code-fenced grep example block; the same grep guard tripped on the comment that documented the guard. Resolution: paraphrase ('killfeed parsing' / 'ult tracking' / etc) and reference the guard command without echoing the literal substrings.
- **2026-05-08 — Bomb-icon worker keeps a local last_bomb_state mirror, doesn't read arbiter.state.bomb_planted to gate transitions.** Reading arbiter.state would couple worker continuity to Phase-4 mode-flips that could induce phantom edge-firings. Local mirror is single-cycle stale by construction but conservative.
- **2026-05-08 — All OCR decode helpers run inside a shared _OCR_EXECUTOR ThreadPoolExecutor(max_workers=2) module-level singleton.** RESEARCH §Pattern 4: pytesseract.image_to_string is blocking subprocess.Popen which releases GIL; max_workers > 2 hits subprocess fork pressure. Tested empirically: 60-frame p50 lands well under 100ms after first-call fork amortizes.
- **2026-05-08 — Score-banner OCR worker pushes FULL {a_round, b_round} fields_proposed shape (not diff-only).** Matches the rib.gg poller's emission shape (03-04 SUMMARY) so the arbiter's signature-grouping over fields_proposed.items() trips the ≥2-source cross-confirm rule (DEC-006 v2). Diff-only would never match the full-shape ribgg pushes and the cross-confirm would never fire.
- **2026-05-08 — D-13 carry-forward without per-frame quarantine PendingEvent.** Workers log + skip-cycle on parse failure; the existing 5s staleness kill-switch handles extended degradation. Conflating with per-frame quarantine PendingEvents would race against the soft-commit contract that the arbiter implements for bomb_events.
- **2026-05-08 — _detect_round_end_banner ships as a placeholder gray-pixel-content threshold; both round-end tests xfail with Phase 3.5 operator-recalibrate TODO.** Building a synthetic round-end banner frame to exercise the placeholder reliably requires either operator-supplied banner template OR a sophisticated synthetic banner mock — neither in scope for Plan 03-05. xfail with explicit Phase 3.5 TODO is the clean signal for downstream calibration work.
- **2026-05-10 — tweepy 4.16.x exposes AsyncStreamingClient under tweepy.asynchronous, not at the tweepy top level.** Plan 03-06 `<interfaces>` block referenced `tweepy.AsyncStreamingClient` which AttributeErrors at module load. Fix: `from tweepy.asynchronous import AsyncStreamingClient` while still using `tweepy.StreamRule` (top-level). Documented in module docstring "Implementation notes" so future maintainers don't re-introduce the broken import. Rule-1 deviation auto-fixed in commit `cbf2017`.
- **2026-05-10 — Whitespace-only TWITTER_BEARER_TOKEN counts as empty (.strip() before truthiness check).** test_no_token_noop second pass with `monkeypatch.setenv("TWITTER_BEARER_TOKEN", "   ")` verifies — accidental blank-string secrets in CI configs degrade to no-op rather than 401-looping a real client.
- **2026-05-10 — Text listener tests exercise on_tweet via direct method calls, NOT a real network stream.** environment_notes "tests should mock the Twitter API (no real network)" satisfied by avoiding the network code path entirely (the rule-sync / listener.filter() path is only entered when the token gate passes, which test_no_token_noop inverts). No aioresponses fixture needed.
- **2026-05-10 — Twitter-only quarantine asserted via the staleness path (t_observed = wall_time() - 10s).** Pushing a fresh single-source event would assert hold-not-quarantine semantics; the SPEC §4 acceptance is the stronger "Twitter-only update quarantined" assertion which the staleness path produces directly via _DEQUE_MAX_AGE_S=3s expiry.
- **2026-05-10 — type: ignore[misc] localized on `class _MatchSignalListener(AsyncStreamingClient)`.** tweepy ships no stubs so AsyncStreamingClient resolves to Any under mypy; "Class cannot subclass Any [misc]" fires. The ignore is canonical for stubless library inheritance and is scoped to the one declaration line.

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

- **Last session ended:** 2026-05-10 — Phase 03 Plan 06 (text-listener) shipped. Commits: `cbf2017` (Task 1: feat — Twitter v2 streaming text listener with degrade-to-no-op, REQ-text-listener) → `e25b5de` (Task 2: test — text listener tests for soft events + Twitter-only quarantine + no-token-noop).
- **Stopped at:** Completed 03-06-text-listener-PLAN.md
- **Next action:** Plan 03-07 (etl-rerun-and-calibration). REQ-round-conclusion-lookup ETL re-run against ~1000 series with response caching via requests-cache filesystem backend (D-08), per-series SQLite transactions for idempotency (D-09), output to NEW data/round_events_v2.sqlite (D-07). Then v2 calibrator rewrite filtering to bomb_planted=True rows, deriving (attackers_alive, defenders_alive, time_remaining_bucket=5s, side, map) cell keys per D-04, emitting models/round_conclusion.json with schema_version: 2 (D-06).
- **Cross-phase context lookup:** `.planning/PROJECT.md` `<decisions>` blocks expose all 22 DECs. Constraint detail in `.planning/intel/constraints.md`. Phase 3 implementation decisions in `.planning/phases/03-live-ingestion-layer/03-CONTEXT.md` (D-01 through D-14).
