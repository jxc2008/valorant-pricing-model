---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_phase: 04
current_plan: "4 of 9 (04-00..04-03 shipped; next: 04-04 mode-selector — Wave 3, depends on 04-03 kill-switch surface)"
status: in-progress
stopped_at: Completed 04-03-kill-switches-PLAN.md
last_updated: "2026-05-11T20:09:00.216Z"
last_activity: 2026-05-11
progress:
  total_phases: 9
  completed_phases: 4
  total_plans: 33
  completed_plans: 28
  percent: 85
---

# STATE — Valorant Live Pricing Model

**Project:** Valorant Live Pricing Model
**Last activity:** 2026-05-11
**Last activity description:** Phase 04 Plan 03 (kill-switches) shipped — REQ-kill-switches Wave-2 GREEN promotion. Five pure-predicate kill switches in `src/quoting/kill_switches.py` (4 DEC-005 + 1 Pitfall 7 carry-forward): `kill_switch_staleness` (strict > 5s on `state.last_updated_ts`), `kill_switch_deviation` (strict > 20c on `|round(theo.theo_series * 100) - market.mid|`), `kill_switch_brier` (window-full AND strict > 0.30 mean — uses `math.fsum` Shewchuk pairwise summation to avoid IEEE 754 drift: naive sum of 50 copies of 0.30 yields 0.30000000000000027 which would spuriously trip the boundary), `kill_switch_api_error` (non-strict >= 3 from `reference/market_maker.py:73` `_MAX_ERRORS_BEFORE_PAUSE` salvage; consumes `KalshiOrderManager.error_streak`), `kill_switch_market_invalid` (Pitfall 7 WS reconnect: `not market.is_valid` — mode-selector rule 1 returns IDLE during reconnect gaps). `KillSwitchAggregator` owns `recent_briers: deque(maxlen=KILL_SWITCH_BRIER_WINDOW)` as a PUBLIC attribute so plan 04-08 reconciliation can `agg.recent_briers.append(score)` directly after round resolution (Pitfall 4 contract: only when mode != IDLE — documented in class docstring, NOT enforced by predicate). `.any_tripped(state, theo, market, error_streak)` returns `(bool, sorted_names: list[str])` — sorted name list is deterministic across Python runs (Phase 03 D-08 set-iteration-non-determinism carry-forward). DEC-005 absolute: no per-switch off-switch flag — grep guard `rg "disable_" src/quoting/kill_switches.py` returns no matches (docstring paraphrased "per-switch off-switch flag / per-switch bool knob" to dodge self-tripping the guard; same pattern as Phase 03 plan 03-05). 18 GREEN tests cover trip + non-trip boundary per predicate (staleness 5.01s/5.0s/4.99s; deviation mid=71/70; brier 49-zeros/50×0.30/50×0.40; api_error 3/2/10; market_invalid False/True) plus 5 aggregator semantics tests (empty / single-staleness / multi-trip-sorted / deque-shape / brier-accumulated). 374 passed / 53 xfailed (+18 GREEN, -10 xfailed from 04-02 baseline 356/63; 0 regressions); mypy --strict src/quoting/ clean (6 source files).

---

## Project Reference

- **Core value:** Live pricing engine for Valorant BO3 series + per-map Kalshi markets. Re-prices the series at any moment during a live match, hybrid market-maker / directional taker, fast enough to capture edge or — at minimum — avoid being adversely selected.
- **Owner:** jxc2008@nyu.edu
- **Status:** Ready to plan
- **Source-of-truth design docs:** `prd.md`, `roadmap.md`, `CLAUDE.md` at repo root.
- **Locked decisions:** 22 (DEC-001 through DEC-022) — see `.planning/PROJECT.md` `<decisions>` blocks.

## Current Position

Phase: 04 (quoting-layer) — IN PROGRESS (Wave 2 complete; Wave 3 next)
Plan: 4 of 9

- **Current phase:** 04
- **Current plan:** 4 of 9 (04-00..04-03 shipped; next: 04-04 mode-selector — Wave 3, depends on 04-03 kill-switch surface)
- **Status:** in-progress
- **Progress:** [█████████░] 85%

```
Phase 0  [##########] Complete (3/3 plans)
Phase 1  [##########] Complete (7/7 plans)
Phase 2  [##########] Complete (5/5 plans)
Phase 3  [##########] Complete (9/9 plans)
Phase 4  [####......] In Progress (4/9 plans)
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
| 3 — Live ingestion layer | Complete (2026-05-09) | 9 (03-00..03-08) | 9 |
| 4 — Quoting layer | In Progress | 9 (04-00..04-08) | 4 |
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
| Phase 03 P07 | ~6h 45m wall-clock (~70 min active code; ~5h 35m blocking on rib.gg scrape), 3 tasks, 13 files | ETL re-run + v2 calibration (REQ-round-conclusion-lookup, D-07/D-08/D-09/D-10): scripts/probe_round_events_v2.py augments Phase 2 ETL with a_alive/b_alive persisted + requests-cache filesystem backend + per-match SAVEPOINT transactions; scripts/calibrate_round_conclusion_v2.py top-down Bayesian shrinkage walk. Atomic-replaced models/round_conclusion.json (806 KB) with 5736/854/72/36 cells across 4 tiers from 24500 bomb-planted samples / 1000 logical match_ids / 42370 perspective-doubled rounds. side_baseline {atk: 0.5299, def: 0.4701} converges within 0.005 of Phase 2 v1. 294 passed / 25 xfailed (+7 GREEN; v1 calibrator + v1 synthesize_states tests collapse to permanent xfails). |
| Phase 03 P08 | ~10 min, 2 tasks, 3 files | Synthetic E2E gate (REQ-end-to-end-latency / SPEC §6 acceptance): tests/ingestion/test_e2e.py composes Arbiter + LiveTheoEngine through 30+ events end-to-end via PendingEvent injection (no real network / OCR / tweepy). 3 GREEN tests: test_e2e_latency_p50 (seq_id strictly monotonic + 6-stage timestamps populated + p50 t_ingested → t_state_committed < 500ms over 30 score_change events), test_bomb_detect_p50 (bomb_plant p50 < 100ms over 30 events; Phase 3's 100ms piece of PRD's 200ms bomb-detect → quote-pull budget), test_post_plant_non_degenerate (post-plant theo shift |theo_bomb - theo_baseline| ≥ 1¢ on injected synthetic cell at (3, 2, 0, atk, Lotus); measured delta=0.0155 with TeamA-at-0.55 asymmetric HalfRates breaking DP symmetry). Synthetic harness latency math is structurally trivial (sub-ms) per RESEARCH Pitfall 3 — the test verifies the INSTRUMENTATION captures the right numbers; production gate is Phase 5 paper-trade. 297 passed / 22 xfailed (+3 GREEN); mypy strict + ruff clean. |
| Phase 04 P00 | 7 min, 2 tasks, 21 files (16 created + 5 modified) | Wave-1 RED-stub scaffolding for entire quoting layer: 13 per-REQ test files (58 xfailed stubs) + 2 __init__.py + populated conftest with 5 fixtures (make_match_state re-export, make_market_quote stand-in dataclass, fake_private_key cryptography 2048-bit RSA, fake_kalshi_session aioresponses, tmp_fill_ledger_dir); 9 new Phase 04 constants (TAKE_THRESHOLD, MM_MIN_EDGE, POST_PLANT_TAKE_THRESHOLD, MIN_HALF_SPREAD, SERIES_AGGREGATE_CAP_FRAC, RELATIVE_BRIER_EDGE_MIN, MIN_FILLS_PER_MATCH, KALSHI_BASE_URL, KALSHI_WS_URL) atomically gated by test_constants.py allow-list (Phase 03 D-08 prophylactic); 5 new deps (cryptography>=42 + websockets>=12 + python-dotenv>=1 + Rule-3 unpinning of async-lru and oauthlib after uv sync uninstalled async-lru, blocking tweepy.asynchronous import); [[tool.mypy.overrides]] strict blocks for src.quoting.* + src.sizing.*; data/fills/ glob-then-allow-list .gitignore pattern. 306 passed / 80 xfailed (22 Phase 03 baseline + 58 new Phase 04 stubs); mypy strict clean. |
| Phase 04 P01 | 14 min, 3 tasks, 9 files (4 created + 5 modified) | REQ-kalshi-order-manager Wave-2 GREEN. Hand-rolled RSA-PSS signer (~50 lines; padding.PSS(MGF1(SHA256), salt_length=PSS.DIGEST_LENGTH) verified docs.kalshi.com 2026-05-09; defensive `assert '?' not in path` for Pitfall 1) + KalshiOrderManager async REST plumbing (place_quote/cancel_quote/cancel_all_orders; /portfolio/orders/batched 2 tokens/order; dry_run constructor arg as single source of truth per DEC-022/CLAUDE.md rule 13; error_streak feeds kill_switch_api_error; Quote.strategy_id v2 field for DEC-020 fill-ledger routing) + MarketQuote (frozen+slots) + MarketDataSource Protocol (runtime_checkable) with SyntheticMarketData (default for dry-run/tests) + KalshiWsMarketData skeleton (dry_run=True returns; dry_run=False raises NotImplementedError pending Phase 6 deployment work) + mark_invalid Pitfall 7 mitigation + scripts/kalshi_auth_smoke.py operator-gated GET /exchange/status (exit codes 0/1/2; .env-missing path verified locally) + ATOMIC CLAUDE.md correction (PKCS1v15→RSA-PSS in same commit as kalshi_auth.py). 326 passed / 70 xfailed (+20 GREEN from 306/80 baseline; 0 regressions); mypy --strict src/quoting/ clean (4 source files). |
| Phase 04 P02 | 4 min, 2 tasks, 6 files (3 created + 3 modified) | REQ-kelly-sizer Wave-2 GREEN. Pure `kelly_size(theo, market_yes_ask, bankroll, series_id, current_series_exposure)` in src/sizing/kelly.py implementing DEC-023 v2 verbatim three-cap formula (half-Kelly → per-market 0.05 → headroom = aggregate 0.10 − exposure[s]); preserves v1 single-market compat when exposure=={}. Mutable PortfolioState registry in src/quoting/portfolio.py with on_place / on_settle / snapshot / current methods — Pitfall 5 mitigation surface (RESEARCH §"Common Pitfalls" #5: on_settle clips at 0.0 against double-settlement bugs; grep-discoverable name so plan 04-08 reconciliation can wire round-resolution callback). 30 new GREEN tests: 17 kelly (13 unit + 4 hypothesis property tests over full input domain covering never-full-Kelly invariant, aggregate-cap-binding at exposure ≥ 0.10, non-negative-integer, no-mutation-of-snapshot) + 13 portfolio_state unit tests (empty / monotonic accumulation / independent series / settlement decrement / double-settlement clipping / snapshot copy semantics / negative-fraction ValueError guards / full place→settle lifecycle). 356 passed / 63 xfailed (+30 GREEN, -7 xfailed from 04-01 baseline 326/70; 0 regressions); mypy --strict src/sizing/ (2 files) + src/quoting/ (5 files, +1 portfolio.py) clean. Integration smoke verified: `ps.on_place('s', 0.05); kelly_size(0.6, 50, 100000, 's', ps.snapshot()) → 100`. |
| Phase 04 P03 | 5 min, 1 task, 3 files (1 created + 2 modified) | REQ-kill-switches Wave-2 GREEN. Five pure-predicate kill switches in src/quoting/kill_switches.py (4 DEC-005 + 1 Pitfall 7): kill_switch_staleness (strict > 5s), kill_switch_deviation (strict > 20c), kill_switch_brier (window-full AND strict > 0.30; uses math.fsum to avoid IEEE 754 drift on 50×0.30 boundary), kill_switch_api_error (non-strict >= 3 salvage from reference/market_maker.py:73), kill_switch_market_invalid (Pitfall 7 WS reconnect: not market.is_valid). KillSwitchAggregator owns recent_briers: deque(maxlen=KILL_SWITCH_BRIER_WINDOW) as PUBLIC attribute for plan 04-08 reconciliation append (Pitfall 4 contract: only when mode != IDLE — documented in docstring); .any_tripped() returns (bool, sorted_names) for deterministic logging. DEC-005 grep guard verified: `rg "disable_" src/quoting/kill_switches.py` returns no matches (docstring paraphrased to dodge self-trip — Phase 03 D-08 carry-forward). 18 GREEN tests (10 RED stubs replaced): trip + non-trip boundary per predicate + 5 aggregator semantics. 374 passed / 53 xfailed (+18 GREEN, -10 xfailed from 04-02 baseline 356/63; 0 regressions); mypy --strict src/quoting/ clean (6 source files). Auto-fixes: [Rule 1 - Bug] math.fsum for Brier mean (naive sum drifts to 0.30000000000000027 spuriously tripping boundary); [Rule 1 - Bug] docstring paraphrase to keep grep guard clean. |

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
- **2026-05-10 — D-07 implementation: persist `a_alive` AND `b_alive` per state dict; drop `econ_bucket` and `numerical_diff`.** Numerical_diff is derivable as `(a_alive - b_alive)` when needed; v2 calibrator keys cells on raw alive counts so storing the derived diff would be redundant. Econ_bucket gone per CLAUDE.md "Economy buckets — DEPRECATED in v2".
- **2026-05-10 — D-08 implementation: module-level CachedSession at import time; `--cache PATH` rebuilds.** The default-CLI invocation skips a session rebuild. `allowable_codes=[200] / allowable_methods=['GET']` is intentional — caching error responses would forever poison the cache for any match that hit a transient 503 cold-start.
- **2026-05-10 — D-09 implementation: SAVEPOINT match_<id> with sanitized identifier; resume strips perspective suffix.** SQLite's identifier rules don't accept arbitrary punctuation; the savepoint name strips non-alphanumeric chars from match_id. The resume set in `get_resume_set` strips the `::1` / `::2` suffix on read so the orchestrator's plain-id iteration matches. One match (239119) rolled back during Task 3 due to malformed `attackingFirstTeamNumber=null` in the rib.gg payload — the SAVEPOINT contract IS the fix; ~0.06% data loss accepted.
- **2026-05-10 — v2 calibrator structure: pure function `_build_lookup_from_rows` decoupled from SQLite reader `_iterate_db`.** The 9 GREEN tests exercise the pure function over a synthetic in-memory dataset; the SQLite reader is exercised end-to-end by Task 3's actual scrape + calibrate flow. Splitting also keeps `_build_lookup_from_rows` test-friendly without an SQLite fixture.
- **2026-05-10 — v1 ETL `credits_to_bucket` shim deletion = NameError-at-runtime deprecation contract.** scripts/probe_round_events.py is forensic-only post-03-07; the call site is preserved with a `# noqa: F821` so ruff stays clean. tests/calibration/test_synthesize_states.py xfailed at the file level with raises=NameError (Rule 3 deviation auto-fixed in Task 1).
- **2026-05-10 — `.gitignore` directory pattern flip for Phase 3 directories.** The bare `data/ribgg_cache/` directory pattern blocks `!data/ribgg_cache/.gitkeep` from un-ignoring (Git PATTERN FORMAT — "two consequences" caveat). Switching to glob form `data/ribgg_cache/*` per parent dir + explicit allow-list lines keeps the contents excluded while permitting the marker. Same fix applied to data/event_log/ and data/metrics/.
- **2026-05-10 — Sample density vs SPEC §7 1c gate: smoke (3,2,8,atk,Lotus) cell shrunk_p≈0.527 lands near the DP's between-round inference.** Calibrator shipped 52 samples on that cell; happens to be near the population mean. Lopsided cells (5v1: +1.18¢; 1v5: -2.93¢) shift theo by 1-3¢ as expected, confirming the dispatch path is structurally active. Phase 5 calibration loop will refine sparse cells; 03-08 E2E gate uses asymmetric states with stronger signal per VALIDATION.md.

#### Phase 04

- **2026-05-11 — RED-stub xfail body pattern carried forward verbatim from Phase 03 D-01.** Every Phase 04 stub function calls `pytest.xfail("Plan 04-NN — ...")` inside its body — NOT `@pytest.mark.xfail` decorator. Wave-N executors flip stubs by replacing the function body in one edit; decorator removal would leave dead xfail-call lines.
- **2026-05-11 — Phase 04 constants land as a SINGLE atomic commit alongside their test_constants.py allow-list extension** (Phase 03 D-08 same-commit Rule-3 prophylactic carry-forward). Splitting across commits would leave CI red between them.
- **2026-05-11 — mypy strict block extension for src.quoting.* AND src.sizing.* added at the `pyproject.toml` level**, not via CLI override. RESEARCH Pitfall 7 carry-forward: CI runs strict only if the override is declared at TOML level. CLI-only invocations would let CI ship loose strictness silently.
- **2026-05-11 — Stand-in `_StubMarketQuote` dataclass in tests/quoting/conftest.py.** Lets Phase 04 tests be written BEFORE plan 04-01 ships the real `src/quoting/market_data.py`. Wave 2+ swaps the import in-place when the real type lands.
- **2026-05-11 — `async-lru` and `oauthlib` unpinned explicitly in `[project].dependencies` (Rule-3 deviation auto-fixed).** tweepy.asynchronous lazily imports both at module load (`raise TweepyException(...)` else); previous environments had them as undeclared transitives that `uv sync` removed during Plan 04-00 Task 2. Pinning makes the install reproducible across machines.
- **2026-05-11 — `VEGA_DIRECTIONAL_THRESHOLD` NOT deleted in Plan 04-00.** Its deletion is atomic with the mode-selector implementation in Plan 04-04, along with its tests/config allow-list removal. Deleting now would leave the mode-selector codepath dangling at HEAD~N.
- **2026-05-11 — Hand-rolled ~50-line RSA-PSS signer instead of kalshi-python==2.1.4 SDK** (Plan 04-01). RESEARCH §"Don't Hand-Roll" flagged the auto-generated OpenAPI client as bloated (~50 endpoints, ~3MB) and mypy --strict-incompatible. Signer surface (3 headers from 4 inputs) is small enough that hand-rolling is a net win.
- **2026-05-11 — CLAUDE.md PKCS1v15 correction ATOMIC with src/quoting/kalshi_auth.py in commit 4bb87b6** (Plan 04-01). RESEARCH Pitfall 2 + planner quality_gate. Splitting across commits would leave HEAD with contradictory authoritative project doc.
- **2026-05-11 — KalshiWsMarketData ships as SKELETON in Plan 04-01.** dry_run=True returns immediately; dry_run=False raises NotImplementedError with "operator-gated; ship in Phase 6 deployment work" message. SyntheticMarketData is the default for Phase 04 paper-trade per RESEARCH §"User Constraints" — dev .env has no KALSHI_KEY_PATH and the WS path requires it. Full WS book maintenance + subscribe loop is Phase 6 work.
- **2026-05-11 — `cancel_all_orders` clears `_active_quotes` EVEN on network failure** (Plan 04-01 / Pitfall 4 mitigation). Downstream API-error kill switch + plan 04-08 reconciliation surface the divergence rather than silently corrupting local state by holding onto already-cancelled orders.
- **2026-05-11 — `Quote.strategy_id` is REQUIRED (no default)** (Plan 04-01 / DEC-020 v2). Every quote MUST route to a per-strategy fill ledger downstream. Defaulting to MM_BETWEEN_ROUND would let stray quotes from new quoters slip into the wrong ledger by mistake.
- **2026-05-11 — KalshiOrderManager takes caller-supplied `aiohttp.ClientSession`** (Plan 04-01). Single session reused across order manager + market-data WS + reconciliation pollers (Phase 6) rather than per-class session. Constructor signature also makes test setup obvious — pytest scopes the session to per-test.
- **2026-05-11 — Defensive `assert "?" not in path` in sign_request guards Pitfall 1 at the single signer module** (Plan 04-01). Every Kalshi REST/WS call routes through `sign_request` and so inherits the guard. Path-with-query-string is the #1 documented Kalshi auth failure mode.
- **2026-05-11 — /portfolio/orders/batched for cancel_all_orders (live path)** (Plan 04-01 / RESEARCH §"Pattern 2"). 2 tokens/order vs 10/order for individual DELETEs = 5× rate-budget improvement; critical when a kill switch cancels 5-10 simultaneous quotes during a fast-moving series.
- **2026-05-11 — Pure-function sizer + mutable-state registry split** (Plan 04-02 / DEC-023 v2). `src/sizing/kelly.kelly_size` is pure (no I/O, no state, takes snapshot dict it never mutates); `src/quoting/portfolio.PortfolioState` owns the mutable dict and exposes `on_place`/`on_settle`/`snapshot`. Mirrors Phase 03's pure-`with_update` + module-level-`commit/quarantine` split — math layer stays `mypy --strict` clean, mutation layer is auditable.
- **2026-05-11 — `PortfolioState.on_settle` clips at 0.0 (does NOT raise)** (Plan 04-02 / Pitfall 5 mitigation). Protects against double-settlement bugs (resolution event delivered twice). Exposure should never go negative under any real-world placement+settlement sequence; clipping degrades gracefully rather than crashing the quoter loop.
- **2026-05-11 — Both `on_place` AND `on_settle` reject negative fractions via `ValueError`** (Plan 04-02). Placements always increase exposure; settlements always decrement. Negative fraction = caller programming error (sign flip), NOT a data condition — hard-fail surfaces the bug at the call site.
- **2026-05-11 — `snapshot()` returns a FRESH dict copy each call** (Plan 04-02). Combined with the pure-function contract on `kelly_size`, immutability is enforceable from BOTH ends: sizer doesn't mutate the dict it gets; registry doesn't share the dict it returns.
- **2026-05-11 — Three-cap composition order verbatim from DEC-023 v2** (Plan 04-02): `max(0, half-Kelly)` → `min(per-market 0.05)` → `min(headroom = 0.10 - exposure[s])`. Reordering would change which constraint binds and break v1 single-market compat when `exposure == {}` (REQ-kelly-sizer acceptance criterion #1).
- **2026-05-11 — Boundary guards return 0 (do NOT raise) for ask / bankroll degenerate values** (Plan 04-02). The quoter loop reads `market_yes_ask` straight from `MarketQuote` (Plan 04-01 surface) which can be stale-zero on WS disconnect (Pitfall 7). Raising would crash the loop; returning 0 silently no-ops the placement — same behavior as a negative-edge input.
- **2026-05-11 — +1 tolerance in `test_never_full_kelly` hypothesis property** (Plan 04-02). `int()` floor rounding can differ by 1 between the formula computation in the test and the actual implementation when `f * bankroll / ask` lands within ε of an integer. The half-Kelly upper bound is the conceptual invariant; +1 is the implementation-detail floor parity tolerance.
- **2026-05-11 — Five-predicate kill-switch design (4 DEC-005 + 1 Pitfall 7)** (Plan 04-03). Each switch is a pure function over its inputs (no shared state, no inheritance). The 5th `kill_switch_market_invalid` ships alongside the DEC-005 baseline because RESEARCH Pitfall 7 (WS reconnect leaves `MarketQuote.is_valid=False`) is implied by PRD §5.4's "stop trading when market data is unreliable" intent — mode-selector rule 1 (plan 04-04) returns IDLE during reconnect gaps via this trip.
- **2026-05-11 — `math.fsum` for rolling-Brier mean in `kill_switch_brier`** (Plan 04-03 Rule-1 auto-fix). Naive `sum([0.30] * 50)` accumulates to `0.30000000000000027` under CPython 3.11 IEEE 754 — would spuriously trip the strict-inequality boundary contract from CLAUDE.md / PRD §5.4 ("rolling Brier > 0.30"). Shewchuk pairwise summation produces exact rounded result `15.0` → mean `0.30` → `> 0.30` is `False`. Same-commit Rule-1 fix per Phase 03 D-08 prophylactic carry-forward.
- **2026-05-11 — Strict inequality for staleness/deviation/brier; non-strict `>=` for api_error** (Plan 04-03). Matches PRD §5.4 / CLAUDE.md prose ("staleness > 5s", "|theo - market| > 20¢", "rolling Brier > 0.30") AND the api_error threshold semantic ("trip after this many consecutive errors" — 3 means "the third error trips", salvaged from `reference/market_maker.py:73` `_MAX_ERRORS_BEFORE_PAUSE = 3`). Boundary tests in Plan 04-03 verify each switch's inequality direction explicitly.
- **2026-05-11 — `KillSwitchAggregator.any_tripped` returns sorted tripped-name list** (Plan 04-03). Phase 03 D-08 carry-forward (set-iteration is non-deterministic under CPython 3.11 randomized hashing). Sorted list keeps log lines / alerts / replay traces stable across Python runs.
- **2026-05-11 — `recent_briers` is a PUBLIC attribute on `KillSwitchAggregator`** (Plan 04-03). Plan 04-08 reconciliation needs to `agg.recent_briers.append(score)` directly after each round resolution (when mode != IDLE per Pitfall 4 contract — documented in class docstring, not enforced by the predicate). Private-with-getter would be ceremony for no protection benefit.
- **2026-05-11 — Docstring paraphrase to keep DEC-005 grep guard clean** (Plan 04-03 Rule-1 auto-fix). First-draft module docstring used the literal phrase "do NOT add a `disable_X: bool` knob" to document the DEC-005 prohibition. This self-tripped the success-criterion grep `rg "disable_" src/quoting/kill_switches.py` which must return zero matches. Rewrote as "per-switch off-switch flag / per-switch bool knob" — same prohibition, no forbidden substring. Identical pattern to Phase 03 plan 03-05 (kill_feed / ult_orb cuts).

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

### Phase 03 outcomes (2026-05-09)

- **MatchState v2 migrated to src/state/match_state.py** (19 fields; cut numerical_diff/side/econ_bucket; added attackers_alive/defenders_alive/time_left_s/seq_id/last_updated_ts). Pure `with_update` mutator + module-level `commit()`/`quarantine()` helpers; single-writer invariant documented at module-docstring level. JSONL replay determinism over 1000 random commits.
- **RoundConclusionLookup v2 surface** (`between_round_p` + `post_plant_p`, 5-tier hierarchy, `schema_version=2` `from_json` gate). `live_theo` dispatches on `state.bomb_planted` (D-05): bomb_planted=True overrides current-round p with `post_plant_p(att, def, time_bucket, side, map)`, future-round transitions ALWAYS use between-round semantics. `src/pricing/economy.py` deleted per CLAUDE.md v2 deprecation.
- **Cross-source arbiter shipped** (3 deques per DEC-006 v2: score_changes, bomb_events, round_end_events; kill_events / numerical_flips NOT created). Score ≥2 sources/2s; bomb 1 OCR source soft-commit; round-end 1 OCR source soft-commit. Sole writer of MatchState; sole appender of event_log + metrics JSONL.
- **Six-stage timestamp lineage on every confirmed event** (data/metrics/{match_id}.metrics.jsonl). `t_observed` (wall_time, source) → `t_ingested` (mono_ns, source) → `t_arbited` (mono_ns, arbiter) → `t_state_committed` (mono_ns, src.state.commit) → `t_theo_computed` (Phase 4) → `t_quote_sent` (Phase 4).
- **Async rib.gg poller, tesseract OCR (4 workers), Twitter v2 listener (degrade-to-no-op) all in place.** Twitter never sole-sources score commits because >=2-source rule blocks Twitter-alone commits; tweepy.asynchronous.AsyncStreamingClient subclass + score-signal regex + degrade-to-no-op env gate.
- **Phase 2 ETL re-run with a_alive/b_alive persisted**; ~1000 series re-fetched into data/round_events_v2.sqlite (398 MB ribgg_cache, 24500 bomb-planted samples); cells calibrated into models/round_conclusion.json schema_version=2 (5736 cells_full / 854 cells_no_time / 72 cells_no_map / 36 cells_minimal; side_baseline {atk: 0.5299, def: 0.4701}).
- **Synthetic E2E gate at tests/ingestion/test_e2e.py:** seq_id monotonic, 6 timestamps populated, p50 < 500ms general / < 100ms bomb-detect (synthetic harness — production gate is Phase 5 paper-trade per RESEARCH Pitfall 3), post-plant theo shift ≥ 1¢ on the injected synthetic cell (delta=0.0155 with asymmetric HalfRates breaking DP symmetry; (3, 2, 0, atk, Lotus) was sparse in calibrated data so test_post_plant_non_degenerate uses _make_engine fallback inject — informs Phase 5 calibration prioritization for low-time-bucket cells).

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

- **Last session ended:** 2026-05-11 — Phase 04 Plan 03 (kill-switches) shipped. Commit: `b47f886` (feat — 5 pure-predicate kill switches + KillSwitchAggregator + math.fsum Brier-mean fix + docstring grep-guard paraphrase; 18 GREEN tests replacing 10 RED stubs). 1 file created (`src/quoting/kill_switches.py` ~170 lines) + 2 modified (`src/quoting/__init__.py` adding 6 new exports, `tests/quoting/test_kill_switches.py` 10 RED stubs → 18 GREEN tests). 374 passed / 53 xfailed (+18 GREEN, -10 xfailed from 04-02 baseline 356/63; 0 regressions); mypy --strict src/quoting/ clean (6 source files: kalshi_auth, order_manager, market_data, portfolio, kill_switches, __init__). Grep guards verified: `rg "disable_" src/quoting/kill_switches.py` returns empty (DEC-005 absolute — no per-switch off-switch flag). Integration smoke verified: `from src.quoting import KillSwitchAggregator, kill_switch_staleness, kill_switch_deviation, kill_switch_brier, kill_switch_api_error, kill_switch_market_invalid` resolves cleanly.
- **Stopped at:** Completed 04-03-kill-switches-PLAN.md
- **Next action:** Phase 04 Plan 04 (mode-selector) — implements REQ-mode-selector (DEC-001 v2: three-way mode + IDLE selection rules 1-6). Wave 3, depends on 04-03 kill-switch surface (`KillSwitchAggregator.any_tripped()[0]` → kill_switch_active boolean for rule 1) AND 04-01 MarketQuote surface (market.spread for rule 5 MM_MIN_EDGE gate). Drops GREEN tests into pre-existing `tests/quoting/test_mode_selector.py` RED stubs from Plan 04-00 (6 xfailed tests covering rules 1-6 + tie-breaking semantics). Recommended next command: `/gsd:execute-phase 04`.
- **Cross-phase context lookup:** `.planning/PROJECT.md` `<decisions>` blocks expose all 22 DECs. Constraint detail in `.planning/intel/constraints.md`. Phase 3 implementation decisions in `.planning/phases/03-live-ingestion-layer/03-CONTEXT.md`. Phase 4 RESEARCH/VALIDATION at `.planning/phases/04-quoting-layer/04-RESEARCH.md` + `04-VALIDATION.md`. Phase 4 Plan 01 + 02 + 03 docstring decisions at `.planning/phases/04-quoting-layer/04-01-kalshi-order-manager-SUMMARY.md` + `04-02-portfolio-kelly-SUMMARY.md` + `04-03-kill-switches-SUMMARY.md`.
