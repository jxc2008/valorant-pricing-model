# Phase 03: Live Ingestion Layer — Context (v2)

**Gathered:** 2026-05-06
**Status:** Ready for planning
**Supersedes:** v1 03-CONTEXT.md (2026-05-01) — invalidated by v2 architecture pivot 2026-05-02. Old v1 decisions (D-03 ONNX kill-feed, D-04 5-deque arbiter, vision_parser salvage) are deleted, not amended.

<domain>
## Phase Boundary

Real-time `MatchState` is fed by simplified arbited multi-source ingestion at sub-500ms event-to-state-commit latency, with **bomb-detect → state-commit p50 < 100ms**. Three OCR HUD targets (score banner, bomb-plant icon, round-end banner) + a post-plant attackers/defenders-alive widget — all tesseract-only, CPU-only — combined with rib.gg async polling and Twitter v2 streaming as a soft cross-confirm source feed three arbiter deques (`score_changes`, `bomb_events`, `round_end_events`). The arbiter is the SOLE writer of `MatchState`, the SOLE appender of the JSONL event log, and emits six-stage timestamp lineage on every confirmed event.

Phase 3 also rekeys `models/round_conclusion.json` to v2 schema `(att, def, time_bucket, side, map)`, augments the Phase 2 ETL to persist `a_alive`/`b_alive`, re-runs against ~1000 series with response caching, and updates `live_theo` to dispatch between two clean code paths (between-round side baseline vs post-plant lookup) with NO general mid-round path.

</domain>

<spec_lock>
## Requirements (locked via SPEC.md)

**7 requirements are locked.** See `03-SPEC.md` for full requirements, boundaries, and acceptance criteria (ambiguity score 0.10, gate ≤ 0.20).

Downstream agents MUST read `03-SPEC.md` before planning or implementing. Requirements are NOT duplicated here.

**In scope (from SPEC.md):**
- Atomic move of `MatchState` from `src/pricing/data.py` to `src/state/match_state.py` with v2 field set
- JSONL event log for state mutations (`data/event_log/{match_id}.jsonl`)
- rib.gg async scoreboard poller built on Phase 2 resilience patterns
- Tesseract-only OCR pipeline against three primary HUD targets + post-plant alive widget
- Twitter v2 streaming listener with degrade-to-no-op on missing bearer token
- Cross-source arbiter implementing DEC-006 v2 (3 deques, simplified rules)
- Six-stage timestamp lineage on every event (Phase 4 fills `t_quote_sent`)
- Phase 2 ETL re-run with `a_alive`/`b_alive` persisted; `models/round_conclusion.json` rekeyed to v2 schema
- `live_theo` dispatch: between-round path vs post-plant path; no general mid-round path
- Synthetic E2E integration test in `tests/ingestion/test_e2e.py`

**Out of scope (from SPEC.md):**
- Quoting / order placement / Kalshi integration (Phase 4)
- Backtest / paper trading / Brier measurement / fill-count ledgers (Phase 5)
- Persistent SQLite live state (`CON-live-state-no-sqlite`)
- Kill-feed CV, mid-round economy inference, ult-count tracking (DEC-024 v2 — project-level cuts)
- ONNX runtime / CTC decoder / GPU dependency / `vision_parser.py` salvage (DEC-024 v2)
- General mid-round pricing (DEC-007 v2)
- 30-min operator-driven live smoke run (replaced by synthetic E2E)
- bo3.gg / vlr.gg adapters (deferred to Phase 5 robustness work)

</spec_lock>

<decisions>
## Implementation Decisions

### MatchState v2 dataclass shape (Area A)

- **D-01: Single dataclass at `src/state/match_state.py`, ~19 fields.** Frozen+slots `MatchState` carries all 13 v2 dynamic fields (`match_id, map_idx, a_map_score, b_map_score, a_round, b_round, side_orient, bomb_planted, attackers_alive | None, defenders_alive | None, time_left_s | None, seq_id, last_updated_ts`) PLUS the 6 Phase-1 static-per-match fields (`team_a, team_b, map_pool, map_side_orients, map_winners, pistol_winner_a`). The SPEC §1 enumeration lists only the 13 dynamic deltas — the Phase 1 static fields are required by `live_theo` (per Phase 1 D-17/D-18/D-19) and MUST remain on the v2 dataclass. Cut from v1: `numerical_diff, side, econ_bucket` — these were v1 round_conclusion lookup keys, irrelevant to the v2 keying. Splitting into MatchState + MatchContext at engine init was rejected: needlessly changes LiveTheoEngine signature; static fields are tiny and don't dominate per-mutation alloc cost (slots=True keeps each instance ~250 bytes).

- **D-02: Pure mutator + decoupled JSONL append.** `MatchState.with_update(**fields_changed) → MatchState` is pure: bumps `seq_id += 1` and `last_updated_ts = time.time()`, returns a new frozen instance, no I/O. The arbiter is the SOLE caller; after `with_update` returns, the arbiter appends a JSONL diff line AND atomically swaps the engine's reference. Pure mutator is unit-testable without disk fixtures. seq_id discipline guaranteed structurally (arbiter is sole writer of state AND sole appender of JSONL — single `commit(prev, next, source, event_type)` helper in `src/state/`). Tight coupling (with_update writes JSONL itself) was rejected: every test would need a tmp_path fixture; harder dry-run.

- **D-03: JSONL line schema = diff-only with seq_id + six timestamps + provenance.** Per arbiter commit:
  ```json
  {"seq_id": 1042, "t_observed": 1730439612.123, "t_ingested": 1730439612.151,
   "t_arbited": 1730439612.198, "t_state_committed": 1730439612.201,
   "t_theo_computed": null, "t_quote_sent": null,
   "source": "ocr", "event_type": "bomb_plant",
   "fields_changed": {"bomb_planted": true, "attackers_alive": 4, "defenders_alive": 3, "time_left_s": 45.0}}
  ```
  Replay: `state = state.with_update(**line["fields_changed"])` in seq_id order. Quarantined lines: `seq_id: null, quarantined: true, quarantine_reason: "...", fields_proposed: {...}` (carried forward from stale D-05; still valid). Disk: ~200-400B/line × ~1500 events/match ≈ 0.3-0.6 MB/match; path `data/event_log/{match_id}.jsonl` (gitignored). `t_theo_computed`/`t_quote_sent` are filled by Phase 4 (append a follow-up keyed by seq_id, or in a parallel metrics line — planner picks). Time discipline per SPEC: `t_observed` uses `time.time()` (replay vs broadcast); the other five use `time.monotonic_ns()` (latency math).

### round_conclusion v2 surface + live_theo dispatch (Area B)

- **D-04: Two methods + two Protocols on `RoundConclusionLookup`.** Add `between_round_p(side: str, map_name: str, round_idx: int) -> float` (returns the per-side baseline directly; no lookup walk) AND `post_plant_p(att: int, def_: int, time_bucket: int, side: str, map_name: str) -> float` (walks the new hierarchical fallback `(att, def, time_bucket, side, map) → (att, def, side, map) → (att, def, side) → (att, def) → side baseline` with Bayesian shrinkage cell-to-parent, inheriting `SHRINK_PRIOR=15`, `SIGNAL_SCALE=0.10`). The v1 `lookup(numerical_diff, bomb_planted, side, econ_bucket, map_name)` method is DELETED in the same atomic commit. The v1 `RoundConclusionFn` Protocol is DELETED — no callers remain after the live_theo refactor. Two new Protocols `BetweenRoundFn`, `PostPlantFn` formalize the new surfaces. Phase 2's frozen-surface contract (D-15) is broken intentionally — there's no value in keeping a v1 method against a v2 schema.

- **D-05: live_theo dispatches via top-level current-round override; DP recursion unchanged.** When `state.bomb_planted=True`, `_live_theo_impl` computes the CURRENT round's p separately:
  ```python
  if state.bomb_planted:
      time_bucket_idx = int(min(state.time_left_s, POST_PLANT_TIMER_S) / TIME_BUCKET_WIDTH_S)
      p_round = round_conclusion.post_plant_p(
          att=state.attackers_alive, def_=state.defenders_alive,
          time_bucket=time_bucket_idx, side=state.side_orient, map_name=state.map_pool[state.map_idx])
      bo3 = _bo3_state_from_match_state(state)
      state_after_a = _advance_round(bo3, a_wins=True)
      state_after_b = _advance_round(bo3, a_wins=False)
      theo_series = p_round * series_value(state_after_a, fn_between) + (1 - p_round) * series_value(state_after_b, fn_between)
  else:
      theo_series = series_value(_bo3_state_from_match_state(state), fn_between)
  ```
  `fn_between` = current Phase-1 `_RoundPFnImpl` (round_p_for_round + Bradley-Terry + pistol/anti-eco). DP recursion is UNTOUCHED — future-round transitions ALWAYS use between-round semantics (no nested post-plant lookups in the recursion). Mirrors how `_compute_vega` already composes one-step branches. Mid-round-not-planted: between-round path with degraded `confidence` (consumed by Phase 4 mode selector → IDLE per DEC-001 v2). Threading an override into `_RoundPFnImpl` was rejected (couples post-plant signal through closure machinery; harder to reason about which calls hit which path). Two separate engine entry points was rejected (parallel-models bug class — PRD §12.2 #6 / CRule 6).

- **D-06: `models/round_conclusion.json` migrates atomic-replace at same path with `schema_version: 2` field.** Phase 2's v1 file (324 KB) is overwritten in one commit. New top-level field `"schema_version": 2`; `RoundConclusionLookup.from_json` HARD-FAILS on `schema_version != 2` (raises `ValueError`, NOT silent fallback). v1 file's history is preserved in git — retrievable via `git show HEAD~N:models/round_conclusion.json`. v2 JSON shape:
  ```json
  {
    "schema_version": 2,
    "side_baseline": {"atk": 0.5256, "def": 0.4751},
    "cells_minimal":  { "<att>|<def>": _CellJson, ... },
    "cells_no_map":   { "<att>|<def>|<side>": _CellJson, ... },
    "cells_no_time":  { "<att>|<def>|<side>|<map>": _CellJson, ... },
    "cells_full":     { "<att>|<def>|<time_bucket>|<side>|<map>": _CellJson, ... }
  }
  ```
  `_Cell` shape (`n, p_hat, parent_p`) is unchanged — only the keys shift. `to_json` writes `schema_version: 2` automatically. Versioned filenames (v1/v2 both on disk) was rejected: dual-artifact hygiene cost outweighs forensic value (git history is sufficient).

### REQ-7 ETL re-run (Area C)

- **D-07: Full re-fetch of the same ~1000 series into a NEW `data/round_events_v2.sqlite`.** The Phase 2 v1 db (`data/round_events.sqlite`, 145 MB, 42586 rows) lacks `a_alive`/`b_alive` and CANNOT be backfilled (rib.gg responses weren't cached in Phase 2; numerical_diff alone is ambiguous about which team scored a kill on a flip). Phase 3 re-fetches the same match-id list end-to-end with the augmented `synthesize_mid_round_states` (lines 268-269 of `scripts/probe_round_events.py` already track `a_alive`/`b_alive` internally — just persist them in the SQLite write). Output to NEW `data/round_events_v2.sqlite`; v1 db retained on disk for forensic / re-run validation. SPEC coverage target: ≥1000 distinct match_ids / ≥40k rounds (matches Phase 2). Smaller-scope option (~500 series, faster) was rejected — halving the post-plant sample size leaves the v2 cells_full sparse and forces the calibrator to lean heavier on hierarchy fallback than is sound. Augment-only-with-derivation was rejected — derivation is ambiguous in too many states.

- **D-08: Cache via `requests-cache` filesystem backend at `data/ribgg_cache/`.** Add `requests-cache` to `pyproject.toml`. Wrap the existing `requests.Session` from `scripts/probe_round_events.py` with `CachedSession(cache_name='data/ribgg_cache', backend='filesystem', expire_after=NEVER)`. Phase 2's resilience patterns (`Connection: close` header, tenacity retry with `Retry-After`-aware `_ribgg_wait`, per-page skip, 5-failure cooldown) compose cleanly through CachedSession. Per-response file (one per URL+params SHA), human-readable JSON, individually inspectable / deletable. Estimated size: ~5 MB/series × 1000 ≈ 5 GB on disk; `.gitignore` excludes `data/ribgg_cache/`. Hand-rolled cache (50 LOC) was rejected (reinvents the wheel); SQLite cache table inside the v2 db was rejected (couples cache with computed data — re-running calibration with empty data table would force full re-fetch unless we preserved the cache table separately).

- **D-09: Idempotency via per-series SQLite transactions; resume by `SELECT DISTINCT match_id`.** Wrap each match's SQLite writes in a transaction that commits after ALL of that match's rounds are persisted (`SAVEPOINT match_<id>; ROLLBACK` on exception). On resume, query `SELECT DISTINCT match_id FROM round_events_v2` and skip those match_ids in the input list. No separate `etl_progress.json` file (drift risk; second source-of-truth). The cache layer makes already-fetched calls instant (~1ms disk read), so re-running after a crash is essentially free for I/O-bound work — only un-processed match_ids cost network time. Net: idempotent by construction; resumable for free; mirrors Phase 2's pattern.

- **D-10: `time_remaining_bucket` granularity = 5s; 9 buckets across the 45s post-plant timer.** Buckets `[0-5, 5-10, 10-15, 15-20, 20-25, 25-30, 30-35, 35-40, 40-45]`. `TIME_BUCKET_WIDTH_S = 5.0` constant in `src/config/constants.py`. Cell estimate: (att 1-5) × (def 1-5) × 9 × 2 sides × 7 maps = ~3150 `cells_full` slots over ~25k post-plant samples ≈ 8 samples/cell average; sparse cells fall through hierarchy fallback to `cells_no_time` level (~350 slots, ~70 samples/cell). Captures the late-clutch urgency signal that 10s/15s buckets blur. Bayesian shrinkage (SHRINK_PRIOR=15) handles sparsity in the long tail. If Phase 5 calibration shows cells_full is too sparse to beat market_mid, widen the buckets in a follow-up calibration run — cheap because of the cache.

### Post-plant alive widget OCR (Area D)

- **D-11: ROIs hand-calibrated from 2026 VCT VOD samples; pinned in `src/config/constants.py`.** Constants `POST_PLANT_ATTACKERS_ROI = (x1, y1, x2, y2)`, `POST_PLANT_DEFENDERS_ROI = (x1, y1, x2, y2)` (pixel-coordinate tuples) plus `BROADCAST_TEMPLATE_VERSION: Final[str] = "vct-2026-international"` as a layout-version anchor. Researcher MUST review ~10 sample post-plant frames during research to populate the values. Single-template assumption initially; if international vs regional VCT layouts differ, that becomes Phase 5 robustness work (multi-template fallback). Auto-detect via `cv2.matchTemplate` was rejected: 5-10ms per frame burns the 100ms budget; silent failure mode (low match score → no ROI → no signal). Operator-driven smoke calibration was rejected: SPEC explicitly traded off operator runs for synthetic E2E.

- **D-12: Hard-gated activation on `state.bomb_planted=True`; worker stops within 1 cycle of defuse/round-end.** OCR loop polls `state.bomb_planted` at every tick; when True, the alive-widget worker activates at 250ms cadence (`OCR_POST_PLANT_ALIVE_CADENCE_MS`). When False, worker yields immediately — saves ~30ms/cycle CPU during ~80% of match runtime when no plant is active. Defuse and round-end transitions cut the worker on the next tick (≤250ms latency). 1-cycle race between `bomb_planted=True` commit and first widget read is mitigated by 250ms cadence aligning with arbiter tick. Always-on with quarantine-when-False was rejected (wasteful; CPU budget tight). One-shot read on plant detection was rejected (misses kill events during the 45s window).

- **D-13: Read-failure → emit None → arbiter quarantines → state carries forward.** If a per-side digit doesn't parse to `{0,1,2,3,4,5}`, the OCR worker emits a `quarantined` event; `state.attackers_alive` / `defenders_alive` stay at their prior valid values via with_update only-changed-fields semantics (Phase 2 D-08 carry-forward). Quarantine line: `{"seq_id": null, "quarantined": true, "quarantine_reason": "ocr_parse_fail", "source": "ocr_post_plant_alive", "fields_proposed": {...}, "t_observed": ...}`. If alive counts are stale for >2 ticks (i.e., 500ms+), `live_theo`'s post-plant lookup falls through hierarchy: `cells_full → cells_no_time → ... → side_baseline` (alive becomes structurally absent rather than wrong). Tesseract config: PSM 10 (single-character), `tessedit_char_whitelist=012345`, preprocessing = grayscale → Otsu threshold → 2× upscale (for >300 DPI equivalent at the small ROI size). Constants pinned in `src/config/constants.py`. Carry-forward without quarantine was rejected (silent stale data); kill-switch on parse fail was rejected (existing 5s staleness kill switch already covers extended degradation; conflating layers).

- **D-14: `time_left_s` is COMPUTED, not OCR'd.** `time_left_s = max(0.0, POST_PLANT_TIMER_S - (time.time() - t_bomb_plant_observed))` clipped to `[0.0, 45.0]`. `POST_PLANT_TIMER_S: Final[float] = 45.0` in `src/config/constants.py`. The arbiter records `t_bomb_plant_observed` when `bomb_planted=True` first commits; `time_left_s` is computed-on-read, not stored as a mutable field that the arbiter has to refresh every cycle. Caveat: bomb-plant detection latency (500ms OCR cadence + arbiter tick) offsets the computed timer by ~250ms median — acceptable since `time_remaining_bucket` is 5s wide (D-10) so the offset stays within one bucket. NOT a fourth OCR target — SPEC §3 lists three primary OCR targets + the alive widget; adding a timer widget is scope creep. rib.gg server-side timer was rejected (5s poll cadence too coarse for a 45s timer).

### Carried forward from prior phases (NOT re-discussed; locked elsewhere)

- **Phase 1 D-14, D-20:** `MatchState` moves to `src/state/match_state.py`. `LiveTheoEngine.__call__(state) → TheoOutput` is the locked seam; per-call surface stays state-only. Phase 3 changes only what flows through `state`.
- **Phase 1 D-17/D-18/D-19:** static fields `team_a, team_b, map_pool, map_side_orients, map_winners, pistol_winner_a` are required by `live_theo` and remain on v2 MatchState (D-01 above carries them forward).
- **Phase 1 D-21:** Latency MEASUREMENT lives in Phase 5 (paper trading). Phase 3 ships instrumentation hooks + the synthetic-test latency budget per SPEC acceptance §6.
- **Phase 2 D-06, D-08:** carry-forward semantics for state derivation. Phase 3's `with_update(**only_changed_fields)` honors this natively. Mid-round-states `kind` enum (`"event"` vs `"heartbeat"`) is preserved in the v2 ETL re-run.
- **Phase 2 D-13:** Bayesian shrinkage with `SHRINK_PRIOR=15.0` is the calibration formula — unchanged for v2 cells.
- **DEC-006 v2:** arbiter has 3 deques (`score_changes, bomb_events, round_end_events`) — locked at project level. `kill_events`, `numerical_flips` are NOT created.
- **DEC-007 v2:** two-path round-conclusion (between-round + post-plant only); no general mid-round path. Locked at project level.
- **DEC-024 v2:** OCR scope cut to three HUD targets + post-plant alive widget. Kill-feed parsing, ult tracking, mid-round economy inference, ONNX, vision_parser.py salvage are ALL out of project scope. Locked.
- **CRule 11/12/13:** `mypy --strict` extends from `src/pricing/` to ALSO cover `src/state/`; `src/ingestion/` stays gradual but new code annotates fully. Every threshold in `src/config/constants.py`. Dry-run default; live trading needs `--live` flag (preserved by Phase 3 — ingestion runs alongside dry-run pricing).

### Claude's discretion (not asked; planner picks)

- Whether `src/pricing/data.py` keeps a one-line re-export shim for `MatchState` during transition or is deleted outright. SPEC §1 explicitly says "planner picks"; both work.
- Concurrency runtime: stale CONTEXT D-06 (asyncio event loop + `loop.run_in_executor(thread_pool)` for OCR; `concurrent.futures.ThreadPoolExecutor(max_workers=2)`) is the carry-forward baseline post-ONNX-removal. Researcher to confirm tesseract releases the GIL during `pytesseract.image_to_string` calls; if not, flag for re-discussion.
- Arbiter mechanism: stale CONTEXT D-04 (per-event-type `collections.deque` + explicit `tick()` eviction; tick frequency = 20Hz) is the carry-forward baseline; deque count drops from 5 to 3 per DEC-006 v2.
- Twitter v2 rule set: stale CONTEXT D-07 picked `["#VCT", "#VALORANTChampions", "#VCTAmericas", "#VCTEMEA", "#VCTPacific"]`. Researcher pins concrete 2026-season caster/league/team-org accounts. Twitter API tier (free/basic/pro) — researcher confirms streaming v2 is available on the project's tier; if not, listener degrades to no-op (per SPEC §4).
- bomb-detect → state-commit p50 < 100ms hot-path engineering: planner may pre-allocate hot-path objects, inline JSONL appends behind a buffered writer, or otherwise tighten — not a discussion-time decision.
- Twitter listener implementation: `tweepy.AsyncStreamingClient` vs raw aiohttp connection — researcher picks based on dep weight and degrade-to-no-op ergonomics.
- YouTube stream decode pipeline upstream of OCR (yt-dlp + ffmpeg + opencv frame grab vs alternatives) — researcher to choose; out-of-band from the alive-widget specifics covered above.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Locked specs and decisions

- `.planning/phases/03-live-ingestion-layer/03-SPEC.md` — **7 REQs locked, 17 acceptance criteria, ambiguity 0.10. MUST read before planning.** Supersedes v1 SPEC; v1 has been reverted.
- `.planning/PROJECT.md` `<decisions>` blocks — DEC-001..DEC-024 with v2 updates; especially DEC-006 v2 (3-deque arbiter), DEC-007 v2 (two-path round-conclusion), DEC-018 v2 (two-context vega), DEC-024 v2 (OCR scope cut).
- `.planning/REQUIREMENTS.md` — REQ-match-state-engine (rescoped v2), REQ-scoreboard-polling, REQ-ocr-pipeline (rescoped v2), REQ-text-listener, REQ-cross-source-arbiter (simplified v2), REQ-latency-instrumentation, REQ-round-conclusion-lookup (rekeyed v2), REQ-end-to-end-latency.
- `.planning/intel/constraints.md` — `CON-match-state-schema` (v2), `CON-event-timestamp-fields`, `CON-ingestion-cadences`, `CON-live-state-no-sqlite`, `CON-mypy-strict-pricing`, `CON-no-magic-numbers`, `CON-dry-run-default`.

### Authoritative design docs (repo root)

- `prd.md` — §2 (latency budgets), §2.1 (three-way mode + IDLE), §5.1 (v2 multi-source arbiter rules + OCR scope), §5.2 (MatchState v2 fields), §5.3 (two-path round-conclusion v2), §6 (live_theo state-only call surface). v2 pivot dated 2026-05-02.
- `roadmap.md` — §3 (Phase 3 implementation guidance — v2 rescope), §3.1–3.6 (per-REQ detail), §4.5 (post-plant quoter consuming Phase 3's plumbing).
- `CLAUDE.md` — critical rules (CRule 1 single-canonical live_theo, CRule 9 always-on kill switches, CRule 10 simplified arbiter, CRule 10a OCR scope, CRule 11 mypy-strict, CRule 12 no-magic-numbers, CRule 13 dry-run default), domain constants table, v2 changelog.

### Prior phase contexts (carry-forward)

- `.planning/phases/01-core-pricing-engine/01-CONTEXT.md` — Phase 1 D-02 (MatchState minimal stub), D-14 (Phase 3 location move), D-17/D-18/D-19 (static fields), D-20 (LiveTheoEngine bundle pattern), D-21 (latency-in-Phase-5).
- `.planning/phases/02-round-event-data/02-CONTEXT.md` — Phase 2 D-06 (hybrid event+heartbeat), D-08 (carry-forward semantics — MUST match v2 runtime), D-13 (empirical Bayes shrinkage), D-15 (round_conclusion.json persistence).

### Phase 1 + 2 artifacts (in-repo; do NOT redesign)

- `src/pricing/live_theo.py` — `LiveTheoEngine` bundle (engine(state) → TheoOutput). Phase 3 modifies `_live_theo_impl` to add the bomb_planted dispatch (D-05) but preserves the call surface.
- `src/pricing/data.py` — Phase 1 stub MatchState (17 fields). Phase 3 plan moves to `src/state/match_state.py` with v2 field set; plan picks delete vs re-export shim.
- `src/pricing/round_conclusion.py` — `RoundConclusionLookup`, `_Cell`, v1 `lookup` method, v1 `RoundConclusionFn` Protocol. Phase 3 deletes `lookup` + `RoundConclusionFn`, adds `between_round_p` + `post_plant_p` + new Protocols (D-04).
- `src/pricing/dp.py`, `src/pricing/round_types.py`, `src/pricing/economy.py` — pricing math; consumed by `live_theo` post-MatchState-update. `economy.credits_to_bucket` is DELETED in Phase 3 per CLAUDE.md (no callers after v2 rekey).
- `src/config/constants.py` — Phase 3 ADDS `OCR_SCORE_BANNER_CADENCE_MS`, `OCR_BOMB_ICON_CADENCE_MS`, `OCR_ROUND_END_CADENCE_MS`, `OCR_POST_PLANT_ALIVE_CADENCE_MS`, `OCR_DECODE_BUDGET_MS`, `ARBITER_TICK_HZ`, `ARBITER_SCORE_WINDOW_S`, `TWITTER_RULE_SET`, `TWITTER_API_BASE_URL`, `EVENT_LOG_DIR`, `METRICS_LOG_DIR`, `POST_PLANT_TIMER_S`, `TIME_BUCKET_WIDTH_S`, `POST_PLANT_ATTACKERS_ROI`, `POST_PLANT_DEFENDERS_ROI`, `BROADCAST_TEMPLATE_VERSION`, plus the round-banner / bomb-icon / score-banner ROI constants.
- `scripts/probe_round_events.py` — resilience patterns (`get_json`, `_ribgg_wait`, `Connection: close`, per-page skip, 5-failure cooldown). Direct salvage source for `src/ingestion/scoreboard.py`. Phase 3 ALSO augments lines 268-269 to persist `a_alive`/`b_alive`.
- `scripts/calibrate_round_conclusion.py` — Phase 2 v1 calibrator. Phase 3 rewrites (or new sibling `calibrate_round_conclusion_v2.py` — planner picks) to filter to `bomb_planted=True` rows, derive `(attackers_alive, defenders_alive, time_remaining_bucket)`, key cells per D-04, emit v2 schema with `schema_version: 2`.
- `models/round_conclusion.json` — v1 calibrated (324 KB, 22/44/524/1886 cells). Phase 3 atomic-replaces with v2 (D-06).
- `data/round_events.sqlite` — v1 dataset (145 MB, 42586 rows). Retained on disk; Phase 3 writes NEW `data/round_events_v2.sqlite` (D-07).
- `data/half_win_rates.json` — Phase 1 input; consumed via `HalfRates.from_json`. Phase 3 unchanged.

### Read-only reference (already in repo; v2-aware)

- `reference/theo_engine.py`, `reference/fair_value.py`, `reference/odds_utils.py`, `reference/market_maker.py` — Phase 1 / Phase 4 salvage. `reference/vision_parser.py` is EXPLICITLY NOT brought in under v2 (DEC-024).

### Test infrastructure

- `tests/probe/conftest.py` + Phase 2 fixtures (`events_response.json`, `series_response.json`, `match_details.json`) — reusable as the rib.gg arm of `tests/ingestion/test_e2e.py`.
- `tests/ingestion/test_e2e.py` (NEW) — synthetic E2E gate per SPEC §6 acceptance. Drives fake rib.gg + fake OCR + fake Twitter through arbiter → MatchState → live_theo; asserts seq_id monotonic, six-stage timestamps populated, p50 latencies (event → state-commit < 500ms; bomb_plant events specifically < 100ms), theo non-degeneracy in populated post-plant cells (≥ 1¢ off side baseline).

### External (third-party libs added by Phase 3)

- `requests-cache` — filesystem backend cache for the ETL re-run (D-08).
- `aiohttp` — asyncio HTTP for the live rib.gg poller + Twitter v2 stream.
- `pytesseract`, `Pillow`, `numpy` — OCR pipeline.
- `tweepy` (or raw aiohttp) — Twitter v2 streaming. Researcher decides.
- (Existing from prior phases: `requests`, `tenacity`, `tqdm`.)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`src/pricing/data.py:60` (Phase 1 MatchState)** — 17-field frozen+slots stub. Phase 3 plan moves to `src/state/match_state.py` per D-01; cuts `numerical_diff, side, econ_bucket` and adds the v2 dynamic fields. Caller-import surface in `src/pricing/__init__.py` (re-exports `MatchState`).
- **`scripts/probe_round_events.py:122` (`@retry` + `_ribgg_wait`)** — resilience pattern: tenacity retry with `Retry-After` honoring + exponential fallback + `Connection: close` headers + 60s timeouts. Transplant to `src/ingestion/scoreboard.py` near-verbatim (D-09 idempotency leans on this).
- **`scripts/probe_round_events.py:268-269` (`a_alive`/`b_alive` tracked but discarded)** — augment to PERSIST these fields per D-07. The v2 ETL re-run adds two new columns to `mid_round_states[]` JSON shape; schema is additive.
- **`scripts/probe_round_events.py:531` (`transform_match_to_rows` defensive null-roster handling)** — defensive `.get()` + early-return pattern. Inform `src/ingestion/scoreboard.py` event-shape parser when matches arrive with sparse fields.
- **`src/config/constants.py`** — already declares `RIBGG_BASE_URL`, `RIBGG_RATE_LIMIT_RPS`, `MID_ROUND_HEARTBEAT_S`, `SHRINK_PRIOR=15.0`, `SIGNAL_SCALE=0.10`, `GUN_WIN_RATE=0.822`, `MIN_ROUNDS_FULL_WEIGHT`, `CONVICTION_CLIP_LOW/HIGH`. Phase 3 adds the OCR/arbiter/post-plant/event-log constants enumerated in canonical_refs.
- **`tests/probe/conftest.py`** + Phase 2 fixtures — reusable for `tests/ingestion/test_e2e.py`'s rib.gg arm.

### Established Patterns

- **Frozen dataclass + slots=True for hot-path types** — Phase 1 set the precedent (`MatchState`, `TheoOutput`, `BO3State`, `HalfRates`, `_Cell`, `RoundConclusionLookup`). Phase 3 continues for v2 `MatchState` per D-01.
- **Salvage-via-`reference/`-then-port (Phase 1 pattern)** — DOES NOT APPLY to OCR in v2 (`vision_parser.py` is explicitly NOT brought in per DEC-024). Only thunderedge salvage allowed in Phase 3 is the rib.gg HTTP patterns from `scripts/probe_round_events.py` (already in this repo).
- **Constants imported from `src/config/constants.py` only** — CRule 12 / CON-no-magic-numbers. Every cadence, window, budget, URL, ROI, and rule set lives there.
- **Resilience-first HTTP** — Phase 2's `_ribgg_wait` + `Connection: close` + per-page-skip + 5-failure cooldown patterns. Reuse them; don't invent new HTTP handling.
- **mypy --strict by package** — Phase 0 scoped to `src/pricing/`. Phase 3 extends to ALSO cover `src/state/` per SPEC. `src/ingestion/` stays gradual but new code annotates fully.
- **Diff-based commits per task** — Phase 1 + 2 ship one commit per task with conventional `feat(03-XX)`/`fix(03-XX)`/`test(03-XX)`/`docs(03-XX)` prefixes. Phase 3 plans keep this discipline.
- **Public-interface freeze pattern** — Phase 1 / Phase 2 froze interfaces and downstream phases populated state. Phase 3 INTENTIONALLY breaks this for `RoundConclusionFn` Protocol + `lookup` method (D-04) — the v2 schema rekey makes the v1 surface meaningless.

### Integration Points

- **`src/pricing/data.py` → `src/state/match_state.py`** — atomic file move + import-rewrite. All Phase 1 imports of `MatchState` (live_theo.py, dp.py, round_conclusion.py, round_types.py, economy.py, tests/) updated in one commit. Planner picks delete-data.py vs one-line re-export shim.
- **`src/state/match_state.py` ← `src/ingestion/arbiter.py`** — arbiter is SOLE writer of MatchState. All four sources (`scoreboard.py`, `ocr.py`, `text_listener.py`, post-plant alive widget worker inside `ocr.py`) emit pending events into deques; arbiter's `tick()` materializes confirmed events and calls `state.with_update(...)` then appends JSONL diff line. No other module mutates state.
- **`src/ingestion/arbiter.py` → `data/event_log/{match_id}.jsonl`** — arbiter writes diff line on commit AND quarantine line on rejection.
- **`src/ingestion/arbiter.py` → `data/metrics/{match_id}.metrics.jsonl`** — Phase 3 reserves the metrics file format with six-stage timestamps. Phase 4 fills `t_quote_sent`; Phase 5 latency analysis consumes it.
- **`src/pricing/live_theo.py:LiveTheoEngine.__call__(state) ← arbiter`** — engine invoked AFTER each `state.with_update()`. Either arbiter holds engine reference and re-invokes, OR a thin engine-driver in `src/state/` does (planner picks).
- **`models/round_conclusion.json` → live `live_theo`** — wired by Phase 4's engine init via `RoundConclusionLookup.from_json`. Phase 3 owns the file's schema migration (D-06) and the population (D-07/D-10).
- **`tests/ingestion/test_e2e.py` (NEW)** — synthetic E2E gate per SPEC. Drives fake rib.gg + fake OCR + fake Twitter through arbiter → MatchState → `live_theo` → asserts seq_id monotonicity, < 500ms p50 latency (< 100ms for bomb_plant), six-stage timestamps populated, post-plant cells shift theo off baseline by ≥ 1¢.
- **`pyproject.toml` deps to add:** `requests-cache`, `aiohttp`, `pytesseract`, `Pillow`, `numpy`, `tweepy` (or raw aiohttp). Existing: `requests`, `tenacity`, `tqdm`.

</code_context>

<specifics>
## Specific Ideas

- **The user explicitly chose to rewrite CONTEXT from scratch** rather than patch the v1 stale CONTEXT — accepting the hygiene cost in exchange for clean v2 framing. Old v1 D-01..D-07 carried forward selectively (D-01 mutator pattern, D-04 deque mechanism, D-05 quarantine policy, D-06 concurrency baseline, D-07 Twitter rule set scaffold) but with v2 cuts applied (no ONNX, no kill_events / numerical_flips deques, no `players_alive_a/b` field, no vision_parser salvage).
- **The user prefers Phase 3 to be a DECISIVELY v2 phase** — no compatibility shims for v1 `RoundConclusionFn` Protocol or v1 `lookup` method. The atomic-replace approach to `models/round_conclusion.json` (D-06) reflects the same preference.
- **Per-series SQLite transactions for ETL idempotency (D-09)** mirror the Phase 2 close-out pattern — keep the pattern consistent across phases for operator ergonomics.
- **The post-plant alive widget is THE replacement signal for the cut kill feed.** All v2 mid-round dynamics flow through `attackers_alive`/`defenders_alive` updates. The 250ms cadence is the floor that determines how quickly post-plant theo can update; the 100ms median decode budget is therefore HARD.

</specifics>

<deferred>
## Deferred Ideas

- **bo3.gg API adapter** — REQ-scoreboard-polling mentions it as backup but rib.gg is sufficient. Re-evaluate in Phase 5 if rib.gg reliability degrades.
- **vlr.gg API adapter** — same; could be added as a third arbiter source for robustness in Phase 5.
- **Twitch / YouTube IRC chat as soft cross-confirm** — surfaced during v1 discussion (carry-forward). Could be a small follow-up phase if Twitter v2 streaming proves noisy or paywalled.
- **Per-match dynamic Twitter rule sync** — v1 D-07 chose static league rules. Per-match rule CRUD could be added if signal-to-noise becomes a problem.
- **GPU-accelerated OCR** — DEC-024 v2 explicitly forbids; promotion to GPU instance could be Phase 6 work IF Phase 5 paper-trade Brier shows OCR-latency-driven misses.
- **Per-event-class hybrid checkpoint snapshots in JSONL** — D-03 went pure-diff. Add a `kind: "checkpoint"` line every N events later if replay over 30k diffs becomes a hot path.
- **30-min operator-driven live smoke run** — explicitly traded off in SPEC for synthetic E2E. Could be added as a Phase 5 bring-up gate.
- **Multi-template OCR fallback (international vs regional VCT layouts)** — D-11 ships single-template assumption. If Phase 3 development surfaces drift, expand to multi-template via `cv2.matchTemplate` in Phase 5 robustness work.
- **Wider time_remaining_bucket calibration sweep** — D-10 picks 5s. If Phase 5 calibration shows cells_full too sparse to beat market_mid, run a 10s/15s bucket sweep against the cached responses (cheap because cache is on disk).
- **Backfill `a_alive`/`b_alive` into Phase 2 `data/round_events.sqlite`** — D-07 chose not to (derivation is ambiguous). If a clean derivation surfaces (e.g., we can mine kill-feed-event source data later), Phase 5 could backfill the v1 db retroactively for forensic analysis.
- **Phase 4 follow-up JSONL line for `t_theo_computed`/`t_quote_sent`** — D-03 reserves these as `null` in Phase 3. Phase 4 either appends a follow-up line keyed by seq_id OR writes parallel metrics lines to `data/metrics/`. Planner-deferred to Phase 4.

### Reviewed Todos (not folded)

None — no pending todos with `area: ingestion` or matching this phase's scope (cross_reference_todos returned `todo_count: 0`).

</deferred>

---

*Phase: 03-live-ingestion-layer*
*Context gathered: 2026-05-06 (v2 rewrite-from-scratch, supersedes 2026-05-01 v1 CONTEXT)*
*Decisions captured: 14 (D-01 through D-14)*
*Carry-forward: 8 cross-phase decisions (Phase 1 D-14/D-17/D-18/D-19/D-20/D-21, Phase 2 D-06/D-08/D-13, Phase 2 D-15 schema-rekeyed)*
*Project-level locked decisions referenced: DEC-001/006/007/018/024 v2*
*Next step: `/gsd-plan-phase 03` — researcher + planner consume `03-SPEC.md` + this CONTEXT.md*
