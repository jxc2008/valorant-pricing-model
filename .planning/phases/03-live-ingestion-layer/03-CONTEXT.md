# Phase 03: Live Ingestion Layer — Context

**Created:** 2026-05-01
**Phase number:** 03
**Phase slug:** live-ingestion-layer
**Status:** Ready for `/gsd-plan-phase 03` (research → planner)

<domain>
Real-time `MatchState` is fed by tiered, arbited multi-source ingestion (rib.gg API + OCR + Twitter v2 streaming) at sub-500ms latency from observable in-game event → updated theo. Every state mutation is monotonically `seq_id`-versioned, six-stage timestamped, and appended to a JSONL event log. Phase 3 ships the plumbing that turns Phase 1's `live_theo` from a one-shot pricing call into a true live engine.
</domain>

<spec_lock>
**SPEC.md is locked** — `.planning/phases/03-live-ingestion-layer/03-SPEC.md` (commit `d7f666b`, 6 requirements, 11 acceptance criteria, ambiguity 0.16).

The following are **NOT** open for redesign in planning:
- The 6 REQs (MatchState engine, scoreboard polling, OCR pipeline, Twitter listener, arbiter, latency instrumentation) — all in scope, none deferred.
- In-scope / out-of-scope boundaries (no quoting, no SQLite, no operator-driven smoke run, no bo3.gg/vlr.gg adapters).
- Latency budget (E2E p50 < 500ms; OCR per-frame < 100ms).
- Acceptance gate: synthetic E2E integration test in `tests/ingestion/test_e2e.py`.
- Salvage discipline: copy `vlr_scraper.py` / `rib_scraper.py` / `vision_parser.py` from `thunderedge/` into `reference/` first, then port to `src/ingestion/`.
- MatchState migration: atomic move from `src/pricing/data.py` to `src/state/match_state.py` with Phase 3 fields added in one plan.
- Twitter listener: full build (not stubbed).

Planner reads SPEC.md directly — do NOT re-derive WHAT/WHY questions in plans.
</spec_lock>

<decisions>
## Implementation Decisions

### MatchState mutator API (Area A)

- **D-01:** Mutator pattern = **frozen dataclass + `replace()` returning new state**. `MatchState` stays `@dataclass(frozen=True, slots=True)` for the Phase 3 superset of fields. Mutator API: `new_state = state.with_update(numerical_diff=4, source="ocr", event_type="kill")` returns a fresh frozen instance with `seq_id = state.seq_id + 1`, `last_updated_ts = now()`. The arbiter is the sole caller; it atomically swaps the engine's reference under a single `asyncio.Lock`. Pure-functional, threadsafe by construction, matches Phase 1's frozen invariant. Per-mutation allocation cost is negligible at slots=True (~200 bytes/instance). Mutable + `.commit()` rejected (would break Phase 1 frozen contract; lock contention with arbiter→engine read path). Builder pattern rejected (no multi-step transactions; every confirmed event is atomic).

### JSONL event log schema (Area A)

- **D-02:** Event log line = **diff-only with `seq_id` + six-stage timestamps + provenance**. Each line written by the arbiter on commit:
  ```json
  {"seq_id": 1042, "t_observed": 1730439612.123, "t_ingested": 1730439612.151,
   "t_arbited": 1730439612.198, "t_state_committed": 1730439612.201,
   "t_theo_computed": null, "t_quote_sent": null,
   "source": "ocr", "event_type": "kill_feed",
   "fields_changed": {"numerical_diff": 4, "players_alive_a": 4}}
  ```
  Phase 4 fills `t_theo_computed` / `t_quote_sent` post-write (append a follow-up line keyed by `seq_id`). Replay is `for line in jsonl: state = state.with_update(**line["fields_changed"])` in seq_id order. Quarantined events (D-05) live in the SAME file with `"quarantined": true` and seq_id is NOT bumped. Disk size: ~150-300 bytes/line × ~30k events / 90-min match ≈ 5-10 MB/match. Path: `data/event_log/{match_id}.jsonl` (one per match, gitignored). Full-snapshot-per-line rejected (50× disk cost). Hybrid checkpoints rejected (premature optimization — replay over 30k diffs is sub-second).

### OCR backend strategy (Area B)

- **D-03:** OCR stack = **hybrid: ONNX small text-recognition CNN for the kill feed; tesseract for score banner / bomb icon / round-end banner**. Kill feed is the latency-critical path (100ms cadence + downstream feeds numerical_diff into the four cell-keying fields D-15 of Phase 2 keys on). ONNX runtime CPU-only target ~10-20ms inference; the model file (~2-5 MB, e.g. PaddleOCR's `en_PP-OCRv4_rec_infer.onnx` or a similarly small public checkpoint — researcher to pin one) is committed to `models/` alongside the round-conclusion artifact. The other three targets sit at ≥250ms cadence so tesseract's 100-300ms latency is in budget. Dependencies added to `pyproject.toml`: `onnxruntime` (CPU build), `pytesseract`, `Pillow`, `numpy`. GPU/ONNX-only rejected (Hetzner CCX13 prod target has no GPU per REQ-cloud-vm; would force a Phase 6 deployment redesign). Pure tesseract rejected (misses kill-feed cadence; loses edge in fast-action windows). Researcher MUST verify the small-CNN model file is permissively-licensed (MIT/Apache-2.0/BSD) before pinning.

### Cross-source arbiter mechanism (Area C)

- **D-04:** Arbiter data structure = **per-event-type `collections.deque` + explicit `tick()` eviction**. Five deques: `score_changes`, `kill_events`, `bomb_events`, `numerical_flips`, `round_end_events`. Each entry is `ArbiterPending(signal_value, source, t_observed, t_ingested)`. Arbiter's `tick(now)` loop: (1) evict entries older than the rule's window (2s for score; 1 frame ≈ 50ms for kill/bomb/numerical; round-end window is round-end-banner-active period); (2) re-evaluate each rule predicate against remaining entries; (3) emit `ConfirmedEvent`s and remove their inputs. Tick frequency = max(20Hz, 2× highest source cadence) to keep arbiter latency below the 100ms kill-feed cadence. Reactive/RxPy rejected (heavy dep, foreign idiom). Single tagged stream + per-rule predicate rejected (O(N×E) per tick, harder race-condition reasoning).

- **D-05:** Quarantine policy = **same JSONL, `quarantined: true` annotation, seq_id NOT bumped**. Quarantined line shape:
  ```json
  {"seq_id": null, "quarantined": true, "quarantine_reason": "score change saw 1 source, needs >=2 within 2s",
   "source": "twitter", "event_type": "score_change",
   "fields_proposed": {"a_round": 7}, "t_observed": 1730439645.001}
  ```
  Replay tooling filters by `quarantined != true`. One-file ergonomics for Phase 5 forensics. Separate `quarantine.jsonl` rejected (two-file management cost; replay tooling complication).

### Concurrency model + source orchestration (Area D)

- **D-06:** Runtime = **asyncio event loop for I/O-bound sources + `loop.run_in_executor(thread_pool, ...)` for OCR**. Coroutines: rib.gg poller (5s cadence, `aiohttp` for compatibility with the loop), Twitter v2 streaming listener (long-lived `aiohttp` connection or `tweepy.asynchronous`), arbiter `tick()` (driven by `asyncio.create_task` with 50ms sleep), and the engine reader (consumes confirmed events via `asyncio.Queue`). OCR runs in a `concurrent.futures.ThreadPoolExecutor(max_workers=2)` — tesseract and ONNX both release the GIL during native calls, so threads parallelize cleanly without multiprocessing IPC overhead. Single shared `asyncio.Queue` carries all confirmed events from arbiter → engine. Multiprocessing rejected (IPC cost adds 1-3ms per OCR result vs the < 100ms budget; pickling MatchState; harder Docker process-tree management for Phase 6). Pure threading rejected (GIL contention under sustained CV load; harder deterministic testing).

- **D-07:** Twitter listener rule set = **static league watch list** declared in `src/config/constants.py`. Initial set: `["#VCT", "#VALORANTChampions", "#VCTAmericas", "#VCTEMEA", "#VCTPacific"]` plus a list of caster/league/team-org accounts (concrete names pinned by researcher from current 2026 VCT season). Rules pushed to Twitter API once at startup; not per-match. Soft-signal-only policy (REQ-text-listener) + arbiter's quarantine-on-single-source rule (D-05) make noise tolerable. Per-match dynamic rule sync rejected (Twitter API rule-CRUD rate-limited at ~15/min globally; team-handle metadata not always available; per-match brittleness).

### Carried forward from prior phases (NOT re-discussed; locked elsewhere)

- **Phase 1 D-02:** Phase 1 stub MatchState had 17 fields, Phase 3 fields explicitly deferred. SPEC §1 unblocks them: add `seq_id, last_updated_ts, players_alive_a/b, ults_a/b, time_left_s, econ_a/b`.
- **Phase 1 D-14:** Phase 3 moves `MatchState` from `src/pricing/data.py` to `src/state/match_state.py`. Atomic move (one plan), all Phase 1 imports updated together.
- **Phase 1 D-20:** `LiveTheoEngine.__call__(state) → TheoOutput` is the locked seam. Phase 3 changes only what flows through `state` — never the call signature.
- **Phase 1 D-21:** Latency MEASUREMENT lives in Phase 5 (paper trading). Phase 3 ships instrumentation hooks + the synthetic-test latency budget per SPEC acceptance #8 (E2E p50 < 500ms in CI).
- **Phase 2 D-06 / D-08:** `numerical_diff` carry-forward semantics are mandatory — Phase 3 mutators MUST use carry-forward (NOT linear interpolation, NOT zero-fill) so calibration data and runtime data stay mutually consistent. Carry-forward = "until a new event mutates this field, the prior value persists" — implemented natively by D-01's `replace()`-with-only-changed-fields semantics.
- **Phase 2 D-15:** `models/round_conclusion.json` keys on `(numerical_diff, bomb_planted, side, econ_bucket, map)`. Phase 3 mutators MUST populate exactly these four cell-keying fields on every state-change so `live_theo` lookups land in `cells_full` (currently 1886 populated cells per Phase 2 calibration).
- **Phase 2 patterns transplant:** `Connection: close` header, tenacity retry with custom `_ribgg_wait` honoring `Retry-After`, per-page skip on transient errors, 5-consecutive-failure cooldown — all proven in `scripts/probe_round_events.py` and directly transplant to the live rib.gg poller.
</decisions>

<canonical_refs>
## Canonical references (MUST read during research + planning)

### Locked specs and decisions

- `.planning/phases/03-live-ingestion-layer/03-SPEC.md` — **Locked requirements; planner MUST read.** 6 REQs, 11 acceptance criteria, in/out scope.
- `.planning/PROJECT.md` — DEC-001..DEC-022 (project-level decisions; DEC-006 cross-source arbiter rules locked here).
- `.planning/REQUIREMENTS.md` — REQ-match-state-engine, REQ-scoreboard-polling, REQ-ocr-pipeline, REQ-text-listener, REQ-cross-source-arbiter, REQ-latency-instrumentation, plus REQ-end-to-end-latency (target).
- `.planning/intel/constraints.md` — `CON-match-state-schema`, `CON-event-timestamp-fields`, `CON-ingestion-cadences`, `CON-live-state-no-sqlite`, `CON-mypy-strict-pricing`, `CON-no-magic-numbers`, `CON-dry-run-default`.

### Authoritative design docs

- `prd.md` (repo root) — §5.1 (multi-source arbiter rules), §5.2 (MatchState fields), §2 (latency budgets), §6 (live_theo state-only call surface).
- `roadmap.md` (repo root) — §3 (Phase 3 implementation guidance per source), §3.1–3.6 (per-REQ detail).
- `CLAUDE.md` (repo root) — critical rules (especially CRule 11 mypy-strict, CRule 12 no-magic-numbers, CRule 13 dry-run-default).

### Prior phase contexts (carry forward)

- `.planning/phases/01-core-pricing-engine/01-CONTEXT.md` — Phase 1 D-02 (MatchState scope), D-08 (confidence semantics), D-14 (MatchState location), D-20 (LiveTheoEngine bundle), D-21 (latency-in-Phase-5).
- `.planning/phases/02-round-event-data/02-CONTEXT.md` — Phase 2 D-06 (hybrid event+heartbeat), D-08 (carry-forward semantics), D-15 (round_conclusion.json keying).

### Phase 1 + 2 artifacts (interface lock — do NOT redesign)

- `src/pricing/live_theo.py` — `LiveTheoEngine` bundle (engine(state) → TheoOutput). Signature locked.
- `src/pricing/data.py` — Phase 1 stub MatchState with 17 fields. Phase 3 plan moves this to `src/state/match_state.py`.
- `src/pricing/round_conclusion.py` — `RoundConclusionLookup.from_json` consumed by Phase 4 quoter. Reads from `models/round_conclusion.json`.
- `src/pricing/dp.py`, `src/pricing/round_types.py`, `src/pricing/economy.py` — pricing math; consumed by `live_theo` post-MatchState-update.
- `scripts/probe_round_events.py` — resilience patterns (`get_json`, `_ribgg_wait`, `Connection: close`, per-page skip). Direct salvage source for `src/ingestion/scoreboard.py`.
- `models/round_conclusion.json` — calibrated lookup; Phase 3 mutators populate the four keys this consumes.

### Read-only salvage (must be copied into `reference/` first per SPEC)

- `thunderedge/worktrees/market-maker/.../vlr_scraper.py` → copy to `reference/vlr_scraper.py` → port to `src/ingestion/scoreboard.py`.
- `thunderedge/worktrees/market-maker/.../rib_scraper.py` → copy to `reference/rib_scraper.py` → consult during scoreboard port (rib.gg shape).
- `thunderedge/worktrees/market-maker/.../vision_parser.py` → copy to `reference/vision_parser.py` → port to `src/ingestion/ocr.py`.
- (User does the copy — these files live in a separate repo. Phase 3 plan should NOT assume they're present until copied.)

### Existing read-only salvage (already in `reference/`)

- `reference/theo_engine.py`, `reference/fair_value.py`, `reference/odds_utils.py`, `reference/market_maker.py` — Phase 1 / Phase 2 / Phase 4 salvage. Not directly used by Phase 3 ingestion.
</canonical_refs>

<reusable_assets>
## Reusable assets in current codebase

- **`src/pricing/data.py:60` (MatchState dataclass)** — 17-field frozen+slots stub. Phase 3 plan moves to `src/state/match_state.py` and extends with 8 new fields. Caller-import surface in `src/pricing/__init__.py` (re-exports `MatchState`).
- **`scripts/probe_round_events.py:122` (`@retry` decorator + `_ribgg_wait`)** — verified resilience pattern: tenacity retry with `Retry-After` honoring + exponential fallback + `Connection: close` headers + 60s timeouts. Transplant to `src/ingestion/scoreboard.py` near-verbatim.
- **`scripts/probe_round_events.py:531` (`transform_match_to_rows` — defensive null-roster handling)** — defensive `.get()` + early-return pattern. Inform `src/ingestion/scoreboard.py` event-shape parser when matches arrive with sparse fields.
- **`src/config/constants.py` (RIBGG_BASE_URL, RIBGG_RATE_LIMIT_RPS, MID_ROUND_HEARTBEAT_S)** — already declares the rib.gg configuration constants. Phase 3 adds: `OCR_KILLFEED_CADENCE_MS`, `OCR_SCOREBOARD_CADENCE_MS`, `OCR_BOMB_CADENCE_MS`, `OCR_ROUNDEND_CADENCE_MS`, `OCR_DECODE_BUDGET_MS`, `OCR_INFERENCE_BUDGET_MS`, `ARBITER_TICK_HZ`, `ARBITER_SCORE_WINDOW_S`, `ARBITER_KILL_WINDOW_MS`, `TWITTER_RULE_SET`, `TWITTER_API_BASE_URL`, `EVENT_LOG_DIR`, `METRICS_LOG_DIR` — all per CRule 12.
- **`src/pricing/economy.credits_to_bucket`** — single canonical bucketing impl (Phase 2 lifted it here). Phase 3 ingestion populates `econ_bucket` via THIS function (NOT inline literals); same call site as Phase 2 calibrator.
- **`tests/probe/conftest.py`** + fixtures (`events_response.json`, `series_response.json`, `match_details.json`) — Phase 2 fixtures; reusable as the rib.gg arm of `tests/ingestion/test_e2e.py`.
</reusable_assets>

<patterns>
## Established patterns to follow

- **Frozen dataclass + slots=True for hot-path types** — Phase 1 set the precedent (`MatchState`, `TheoOutput`, `BO3State`, `HalfRates`). Phase 3 continues for the extended `MatchState` per D-01.
- **Salvage-via-`reference/`-then-port** — Phase 1 used this for `theo_engine.py` (read-only reference, code lifted into `src/pricing/round_conclusion.py:_Cell` etc). Phase 3 applies the same to `vlr_scraper.py` / `rib_scraper.py` / `vision_parser.py`.
- **Constants imported from `src/config/constants.py` only** — CRule 12 / CON-no-magic-numbers. Every cadence, window, budget, URL, and rule set goes there.
- **Resilience-first HTTP** — Phase 2's `_ribgg_wait` + `Connection: close` + per-page-skip + 5-failure cooldown patterns are the project's canonical way to talk to rib.gg. Reuse them; don't invent new HTTP handling.
- **mypy --strict by package** — Phase 0 scoped strict to `src/pricing/`. Phase 3 extends to ALSO cover `src/state/` per SPEC's Constraints. `src/ingestion/` stays gradual but new code annotates fully.
- **Operator-driven checkpoints via `<phase>-PHASE-STATUS.md` sentinel** — Phase 2 introduced this for the operator `--live` probe. Phase 3 SPEC ruled out operator smoke runs in favor of synthetic E2E, so this pattern is unlikely to apply here — but available if any plan ends up needing real-world OCR validation that can't be mocked.
- **Diff-based commits per task** — Phase 1 + 2 ship one commit per task with conventional `feat()`/`fix()`/`test()`/`docs()` prefixes. Phase 3 plans should keep this discipline.
</patterns>

<integration_points>
## Integration points

- **`src/pricing/data.py` → `src/state/match_state.py`** — atomic file move + import-rewrite. All Phase 1 imports of `MatchState` (live_theo.py, dp.py, round_conclusion.py, round_types.py, economy.py, tests/) updated in one commit. `src/pricing/data.py` either deleted (with imports rewritten) OR kept as a one-line re-export shim — planner picks based on file size and what else lives there.
- **`src/state/match_state.py` ←  `src/ingestion/arbiter.py`** — arbiter is the SOLE writer to MatchState. All four sources (`scoreboard.py`, `ocr.py`, `text_listener.py`) emit `ArbiterPending` events into deques; arbiter's `tick()` materializes `ConfirmedEvent`s and calls `state.with_update(...)`. No other module mutates state.
- **`src/ingestion/arbiter.py` → JSONL event log** — arbiter writes the diff line on commit AND on quarantine. Path: `data/event_log/{match_id}.jsonl`.
- **`src/ingestion/arbiter.py` → metrics log** — Phase 3 reserves the metrics file format. Path: `data/metrics/{match_id}.metrics.jsonl`. Phase 5 latency analysis consumes it.
- **`src/pricing/live_theo.py:LiveTheoEngine.__call__(state)` ← arbiter** — engine is invoked AFTER each `state.with_update()`. The arbiter (or a thin engine-driver in `src/state/`) holds the engine reference and re-invokes on every commit.
- **`models/round_conclusion.json` → live `live_theo`** — already wired by Phase 2; Phase 3 just makes sure the four cell-keying fields (`numerical_diff`, `bomb_planted`, `side`, `econ_bucket`) are populated truthfully on every state mutation.
- **`tests/ingestion/test_e2e.py` (NEW)** — synthetic E2E gate per SPEC. Drives fake rib.gg fixture frames + fake OCR frames + fake Twitter events through arbiter → engine → asserts seq_id monotonicity, < 500ms p50 latency, theo non-degeneracy.
- **`pyproject.toml` deps to add:** `aiohttp` (asyncio HTTP for rib.gg poller + Twitter stream), `pytesseract`, `Pillow`, `numpy`, `onnxruntime`. (Existing: `requests`, `tenacity`, `tqdm` from Phase 2 — rib.gg poller may stay on `requests` inside an executor if `aiohttp` migration cost is high; researcher to call.)
</integration_points>

<deferred>
## Deferred ideas (NOT in Phase 3 scope)

- **bo3.gg API adapter** — REQ-scoreboard-polling mentions it as backup but rib.gg is sufficient. Re-evaluate in Phase 5 if rib.gg reliability degrades.
- **vlr.gg API adapter** — same; could be added as a third arbiter source for robustness in Phase 5.
- **Twitch / YouTube IRC chat as soft cross-confirm** — surfaced during Area B discussion. Captured here so it isn't lost. Could be a small follow-up phase if Twitter v2 streaming proves noisy or paywalled.
- **Per-match dynamic Twitter rule sync** — D-07 chose static league rules. Per-match rule CRUD could be added later if signal-to-noise becomes a problem.
- **GPU-accelerated OCR** — D-03 chose CPU-only ONNX + tesseract to fit Hetzner CCX13. Phase 6 deployment could promote to GPU instance if Phase 5 paper-trade Brier shows OCR-latency-driven misses.
- **Per-event-class hybrid checkpoint snapshots in JSONL** — D-02 went pure-diff. Add a `kind: "checkpoint"` line every N events later if replay over 30k diffs becomes a hot path.
- **30-min operator-driven live smoke run** — explicitly traded off in SPEC for synthetic E2E in CI. Could be added as a Phase 5 bring-up gate.
</deferred>

---

*Phase: 03-live-ingestion-layer*
*Context written: 2026-05-01*
*Decisions captured: 7 (D-01 through D-07)*
*Carry-forward: 7 cross-phase decisions (Phase 1 D-02/D-14/D-20/D-21, Phase 2 D-06/D-08/D-15)*
*Next step: `/gsd-plan-phase 03` — researcher + planner consume SPEC.md + this CONTEXT.md*
