# Phase 03: Live Ingestion Layer — Specification (v2)

**Created:** 2026-05-04
**Ambiguity score:** 0.10 (gate: ≤ 0.20)
**Requirements:** 7 locked
**Supersedes:** v1 SPEC (kill-feed CV, hybrid mode, full mid-round) — invalidated by v2 architecture pivot 2026-05-02

## Goal

Real-time `MatchState` is fed by simplified arbited multi-source ingestion (rib.gg poller + tesseract OCR on three HUD targets + Twitter v2 listener) at sub-500ms event-to-state-commit latency, with **bomb-detect → state-commit p50 < 100ms** for the defensive-quote-pull path; round-conclusion lookup is rekeyed to post-plant-only `(attackers_alive, defenders_alive, time_remaining_bucket, side, map)` and recalibrated against a Phase 2 dataset re-run that augments mid-round states with absolute alive counts.

## Background

**Current state in this repo (post-revert, post-v2-doc-edits):**

- Phases 0/1/2 complete. `src/pricing/` math layer (DP, Bradley-Terry blend, pistol/anti-eco modeling, OT hard-stop, `live_theo`) is shipped and strategy-agnostic.
- `src/pricing/data.py` holds the v1 `MatchState` (17 fields, frozen+slots) — this is the Phase 1 stub. Phase 3 moves it to `src/state/match_state.py` with the v2 schema (smaller, post-plant-aware).
- `src/pricing/round_conclusion.py` ships `RoundConclusionLookup` with v1 schema keys `(numerical_diff, bomb, side, econ_bucket, map)` and the 5-tier hierarchical fallback. `models/round_conclusion.json` (324 KB, 22/44/524/1886 cells) is calibrated against the v1 schema.
- `data/round_events.sqlite` (145 MB, 42586 rows) contains the Phase 2 dataset. Each row's `mid_round_states[]` JSON has fields `t_offset, kind, numerical_diff, bomb_planted, side, econ_bucket`. **`a_alive` and `b_alive` are NOT persisted** — only their diff. The Phase 2 ETL (`scripts/probe_round_events.py:268-269`) tracks `a_alive`/`b_alive` internally during synthesis but discards them.
- `src/state/__init__.py`, `src/ingestion/__init__.py` are empty package directories.
- `scripts/probe_round_events.py` is the proven rib.gg ETL with resilience patterns (`Connection: close`, tenacity retry with `Retry-After`, per-page-skip, 5-failure cooldown). Direct salvage source for `src/ingestion/scoreboard.py`.

**v2 architecture (PRD 2a187b5, ROADMAP §3, REQUIREMENTS v2):**

- Three-way mode + IDLE replaces hybrid framing. Phase 3 doesn't build the mode selector (Phase 4) but ships the state pipeline that feeds it.
- OCR scope: three HUD targets (score banner, bomb-plant icon, round-end banner) + a fourth post-plant attackers/defenders-alive widget that's parsed only when `bomb_planted=True`. Tesseract handles all four. **Kill feed, ult tracking, mid-round economy inference are explicitly out.**
- MatchState v2 fields: `match_id, map_idx, a/b_map_score, a/b_round, side_orient, bomb_planted, attackers_alive | None, defenders_alive | None, time_left_s | None, seq_id, last_updated_ts`. Cut: `econ_a/b`, `ults_a/b`, `players_alive_a/b`.
- Two-path round-conclusion lookup: between-round uses the side baseline directly (no lookup); post-plant invokes `post_plant_lookup(att, def, time_bucket, side, map)`. No general mid-round path.

**What triggers Phase 3:** Phase 2 shipped a calibrated `RoundConclusionLookup`, but `live_theo` only sees real signals when an ingestion layer populates `MatchState` over time. Without Phase 3, the bot has no way to detect bomb plants, no way to update score in real time, no way to drive the mode selector that Phase 4 will build.

## Requirements

1. **MatchState v2 + JSONL log**: Migrate `MatchState` from `src/pricing/data.py` to `src/state/match_state.py` with the v2 field set; mutators bump monotonic `seq_id`; every mutation appended to a JSONL event log on disk.
   - Current: Phase 1 stub at `src/pricing/data.py:60` with 17 fields including `numerical_diff, bomb_planted, side, econ_bucket` (v1 schema). No mutator API. No event log.
   - Target: `src/state/match_state.py` exports a frozen+slots `MatchState` with the v2 schema; `with_update(...)` mutator returns a new instance with `seq_id = state.seq_id + 1` and appends a diff line to `data/event_log/{match_id}.jsonl`. Phase 1 imports of `MatchState` are rewritten in one atomic commit; `src/pricing/data.py` either deletes the class or keeps a one-line re-export shim (planner picks).
   - Acceptance: `seq_id` strictly monotonic across N=1000 random `with_update` calls; JSONL replay produces identical final state; `mypy --strict src/pricing/` AND `mypy --strict src/state/` clean.

2. **rib.gg scoreboard polling**: A 5s-cadence asynchronous poller against rib.gg `/v1/series` and `/v1/matches/{id}/details` endpoints feeds score-change events into the arbiter. Authoritative but slowest source.
   - Current: No live poller exists; only the offline ETL `scripts/probe_round_events.py` from Phase 2.
   - Target: `src/ingestion/scoreboard.py` (ported from `scripts/probe_round_events.py` resilience patterns: `Connection: close` header, tenacity retry with `Retry-After`-aware backoff capped at 10s, per-page-skip on transient errors, 5-failure cooldown) yields a stream of typed score-update events at 5s cadence.
   - Acceptance: Integration test with monkeypatched `requests.get` returning fixture series/match-details JSON; poller emits ≥3 typed events at the expected cadence (±10% jitter); events conform to the typed shape consumed by the arbiter.

3. **OCR pipeline — three HUD targets + post-plant alive widget**: Tesseract-only, CPU-only computer-vision parser of broadcast HUD elements with per-target cadences and latency budget.
   - Current: No OCR. `vision_parser.py` salvage from sibling `thunderedge/` is **explicitly NOT brought in** under v2.
   - Target: `src/ingestion/ocr.py` decodes the YouTube low-latency stream at:
     - **Score banner** — 250ms cadence — score-change events
     - **Round-end banner** — 100ms during round-end window — soft round-outcome commit (~500ms before scoreboard updates)
     - **Bomb-plant icon** — 500ms cadence — plant/defuse events (drives POST_PLANT_QUOTE in Phase 4 + defensive quote-pull)
     - **Post-plant attackers/defenders-alive widget** — 250ms cadence, ACTIVE ONLY when `bomb_planted=True` — single-integer-per-side widget; populates `attackers_alive` / `defenders_alive` fields on `MatchState`
   - Acceptance: Per-target benchmark asserts decode + inference < 100ms median over ≥50 frames per target; per-target cadence within ±10% jitter under sustained load. Kill-feed parsing, ult-orb tracking, mid-round economy inference, ONNX runtime, and CTC decoders are absent from `src/ingestion/ocr.py` (grep-verifiable).

4. **Twitter v2 streaming text listener**: Soft cross-confirmation source. Twitter v2 streaming filter on match-related hashtags / accounts. Degrades to no-op without bearer token.
   - Current: Does not exist.
   - Target: `src/ingestion/text_listener.py` opens a Twitter v2 streaming connection with a static rule set declared in `src/config/constants.TWITTER_RULE_SET`, parses tweet content for round/score signals, emits typed soft-confirmation events into the arbiter. NEVER sole-source confirmation. When `TWITTER_BEARER_TOKEN` env var is empty, the listener returns immediately with a structured warning log and emits no events.
   - Acceptance: Integration test with a mocked Twitter stream feeding canned tweets emits typed soft-events; arbiter never commits a state change based ONLY on a Twitter event (test explicitly asserts a Twitter-only update is quarantined, not committed); `test_no_token_noop` passes — listener constructs cleanly with empty `TWITTER_BEARER_TOKEN` and raises no exceptions.

5. **Cross-source arbiter — three deques, simplified rules (DEC-006 v2)**: Three-queue pipeline `sources → pending_updates → arbiter → confirmed_updates → state engine` with per-event-type confirmation rules. Quarantined updates logged but not committed.
   - Current: No arbiter exists.
   - Target: `src/ingestion/arbiter.py` implements the pipeline with **3 deques** (was 5 in v1): `score_changes`, `bomb_events`, `round_end_events`. Cut: `kill_events`, `numerical_flips`. Rules:
     - Score change: ≥ 2 sources within 2s window (rib.gg + OCR + Twitter as soft-confirm)
     - Bomb plant/defuse: 1 OCR source — soft commit; hard-confirmed by next round-end or score
     - Round-end banner: 1 OCR source — soft commit; hard-confirmed by next score update
     - Pre-match lineup, sides: API single-source
   - Acceptance: Property test enumerates each event type and asserts the arbiter rule fires correctly with synthetic source emissions; quarantined events appear in the JSONL log with `quarantined: true` and `seq_id: null` (NOT bumped); `kill_events` and `numerical_flips` deques are absent from `src/ingestion/arbiter.py` (grep-verifiable).

6. **Six-stage latency instrumentation + Phase 3 latency assertion**: Every event carries timestamps at each pipeline stage and is logged to a metrics file. Phase 3 owns the path from `t_observed` to `t_state_committed`; Phase 4 fills `t_theo_computed` and `t_quote_sent`.
   - Current: No latency instrumentation; events have no timestamp lineage.
   - Target: Every confirmed event records the six-stage timestamp set: `t_observed, t_ingested, t_arbited, t_state_committed, t_theo_computed, t_quote_sent`. `t_quote_sent` is reserved as `None` in Phase 3. Logged to `data/metrics/{match_id}.metrics.jsonl`. Time discipline: `time.time()` for `t_observed` (replay vs. broadcast); `time.monotonic_ns()` for the other five (latency math).
   - Acceptance: End-to-end test asserts all six fields populated on every confirmed event (`t_quote_sent=None` in Phase 3 is OK); p50 `t_observed → t_state_committed` < 500ms over a synthetic 30+ event run; **bomb-detect → t_state_committed p50 < 100ms** specifically for events where `event_type == "bomb_plant"` (reserves 100ms for Phase 4 quote-cancel within the 200ms PRD bomb-detect → quote-pull budget); metrics file is line-by-line parseable.

7. **Round-conclusion lookup rekey + post-plant calibration**: Augment the Phase 2 ETL to persist `a_alive`/`b_alive` per state, re-run against ~1000 series, recalibrate `models/round_conclusion.json` to the v2 schema, and update `live_theo` to dispatch between two clean code paths.
   - Current: `models/round_conclusion.json` keyed on `(numerical_diff, bomb_planted, side, econ_bucket, map)`. `data/round_events.sqlite.mid_round_states[]` lacks `a_alive`/`b_alive`. `RoundConclusionLookup.lookup` is the single entry point regardless of bomb state.
   - Target:
     - `scripts/probe_round_events.py:synthesize_mid_round_states` augmented to emit two new fields per state: `a_alive: int`, `b_alive: int` (already tracked internally on lines 268-269 — just persist them). Schema bump to `mid_round_states[]` is additive.
     - rib.gg ETL re-run: re-fetch ~1000 series (target: same coverage as Phase 2 — ≥1000 distinct match_ids / ≥40k rounds). Cache rib.gg responses to disk this time so future re-runs don't re-hit the API.
     - `scripts/calibrate_round_conclusion.py` rewritten (or new sibling script) to filter to `bomb_planted=True` rows, derive `(attackers_alive, defenders_alive)` from `(a_alive, b_alive, side)`, derive `time_remaining_bucket` from `(t_offset, ts_bomb_plant)` (45s post-plant timer), key cells on `(att, def, time_bucket, side, map)`, and emit a new `models/round_conclusion.json` with the v2 schema.
     - `RoundConclusionLookup` extended with two code paths: `between_round_p(side, map, round_idx)` returns the side baseline directly (no lookup); `post_plant_p(att, def, time_bucket, side, map)` walks the new hierarchical fallback `(att, def, time_bucket, side, map) → (att, def, side, map) → (att, def, side) → (att, def) → side baseline`.
     - `live_theo(state)` dispatches: `state.bomb_planted=True → post_plant_p(...)` else `between_round_p(...)`. Mid-round-not-planted returns `between_round_p` with degraded `confidence`.
   - Acceptance: Augmented ETL persists `a_alive`/`b_alive` on every state (random sample of 100 rows verifies); v2 `models/round_conclusion.json` exists with cells keyed on `att|def|time_bucket|side|map`; `live_theo` test asserts dispatch is correct (bomb_planted=True invokes post-plant path; otherwise between-round path); regression: existing Phase 1 + Phase 2 tests stay GREEN under the new lookup signature.

## Boundaries

**In scope:**

- Atomic move of `MatchState` from `src/pricing/data.py` to `src/state/match_state.py` with v2 field set. All ~5 in-repo import sites updated atomically.
- JSONL event log for state mutations (`data/event_log/{match_id}.jsonl`).
- rib.gg async scoreboard poller built on Phase 2 resilience patterns.
- Tesseract-only OCR pipeline against three primary HUD targets + the post-plant alive widget.
- Twitter v2 streaming listener with degrade-to-no-op on missing bearer token.
- Cross-source arbiter implementing DEC-006 v2 (3 deques, simplified rules).
- Six-stage timestamp lineage on every event (Phase 4 fills `t_quote_sent`).
- Phase 2 ETL re-run with `a_alive`/`b_alive` persisted; `models/round_conclusion.json` rekeyed to v2 schema.
- `live_theo` dispatch: between-round path vs. post-plant path; no general mid-round path.
- Synthetic E2E integration test in `tests/ingestion/test_e2e.py` driving fake rib.gg + fake OCR + fake Twitter through arbiter → MatchState → `live_theo`, asserting seq_id monotonicity, latency budget, and theo non-degeneracy in post-plant cells.

**Out of scope:**

- Quoting / order placement / Kalshi integration — that's Phase 4 (REQ-kalshi-order-manager, REQ-mode-selector, REQ-mm-quoter, REQ-directional-taker, REQ-post-plant-quoter, REQ-kelly-sizer, REQ-kill-switches). Phase 3 reserves `t_quote_sent` as `None`.
- Backtest / paper trading / Brier measurement / fill-count ledgers — Phase 5.
- Persistent SQLite live state — `CON-live-state-no-sqlite` (in-memory + JSONL only).
- **Kill-feed CV** — DEC-024 v2 cuts this from project scope, not just Phase 3.
- **Mid-round economy inference** — DEC-024 v2 cut. `econ_a/b` is gone from MatchState.
- **Ult-count tracking** — DEC-024 v2 cut.
- **ONNX runtime / CTC decoder / GPU dependency / `vision_parser.py` salvage** — all dropped by DEC-024 v2.
- **General mid-round pricing** — DEC-007 v2 explicitly: only between-round and post-plant paths exist.
- **30-min operator-driven live smoke run** — replaced by synthetic E2E in CI (workflow consistency with Phase 2 close-out).
- bo3.gg / vlr.gg adapters — deferred to Phase 5 robustness work; rib.gg primary is sufficient.

## Constraints

- **Latency budget:** End-to-end p50 `t_observed → t_state_committed < 500ms` per REQ-end-to-end-latency. Bomb-detect → `t_state_committed` p50 < 100ms (reserves 100ms for Phase 4 quote-cancel within the PRD's 200ms bomb-detect → quote-pull budget). OCR per-frame ≤ 100ms (decode + inference, all four targets).
- **State storage:** In-memory MatchState + JSONL event log on disk. No SQLite for live state (`CON-live-state-no-sqlite`).
- **Mutator monotonicity:** Every mutator must bump `seq_id` BEFORE the JSONL append; quoting layer (Phase 4) only acts on monotonically-increasing seq_ids.
- **OCR cadences:** Score banner 250ms; round-end banner 100ms during round-end window; bomb-plant icon 500ms; post-plant alive widget 250ms (active only when `bomb_planted=True`). Constants in `src/config/constants.py` per CRule 12.
- **Type discipline:** `mypy --strict` extended from `src/pricing/` to ALSO cover `src/state/`. `src/ingestion/` stays gradual but new code annotates fully.
- **No magic numbers:** All thresholds (cadences, latency budgets, arbiter window sizes, Twitter rules) declared in `src/config/constants.py` per CRule 12.
- **Dry-run preserved:** Phase 3 ingestion runs alongside dry-run pricing; no live trading is enabled by Phase 3.
- **Tesseract dependency:** Tesseract 5.x system binary required at runtime (already installed locally at `C:\Program Files\Tesseract-OCR\tesseract.exe`; CI installs via apt/choco; Docker runtime image installs).
- **No salvage from sibling `thunderedge/` repo for OCR:** `vision_parser.py` is dropped per DEC-024 v2. The only thunderedge salvage allowed in Phase 3 is the rib.gg HTTP patterns from `scripts/probe_round_events.py` (already in this repo).
- **ETL re-run scope:** Phase 3 includes the partial Phase 2 ETL re-run (re-fetch ~1000 series with `a_alive`/`b_alive` persisted, recalibrate). Cache rib.gg responses to disk so future re-runs don't re-hit the API. This is a Phase 3 deliverable, NOT a Phase 2.5 sub-phase.

## Acceptance Criteria

- [ ] `src/state/match_state.py` exists with `MatchState` carrying the v2 field set (12 fields: `match_id, map_idx, a_map_score, b_map_score, a_round, b_round, side_orient, bomb_planted, attackers_alive | None, defenders_alive | None, time_left_s | None, seq_id, last_updated_ts`); `src/pricing/data.py` either re-exports or is deleted with all imports updated atomically.
- [ ] `MatchState.with_update(...)` returns a new instance with `seq_id = old.seq_id + 1` and appends a diff line to `data/event_log/{match_id}.jsonl`. 1000 random mutator calls produce strictly monotonic `seq_id`.
- [ ] JSONL replay determinism: write 1000 events, replay → identical final state.
- [ ] `src/ingestion/scoreboard.py` integration test passes: monkeypatched fixtures yield ≥3 typed events at 5s cadence (±10% jitter); resilience patterns (`Connection: close`, tenacity retry with `Retry-After`-aware backoff capped at 10s) honored.
- [ ] `src/ingestion/ocr.py` benchmark test passes: 50-frame median decode + inference < 100ms per target across all four (score banner, round-end banner, bomb icon, post-plant alive widget); per-target cadence within ±10% jitter; grep `kill_feed\|ult_orb\|economy_credits\|onnx\|paddleocr\|ctc_decode` returns 0 hits in `src/ingestion/ocr.py`.
- [ ] `src/ingestion/text_listener.py` integration test passes: mocked Twitter stream emits typed soft-events; Twitter-only state-change update is quarantined (test explicit); `test_no_token_noop` passes — listener constructs with empty `TWITTER_BEARER_TOKEN` and raises no exceptions.
- [ ] `src/ingestion/arbiter.py` property tests pass: each event-type rule from DEC-006 v2 fires correctly with synthetic source emissions; quarantined events appear in JSONL with `quarantined: true`, `seq_id: null`; grep `kill_events\|numerical_flips` returns 0 hits in `src/ingestion/arbiter.py`.
- [ ] Every confirmed event in JSONL carries the six-stage timestamp set (`t_quote_sent=None` in Phase 3 is OK); metrics file parseable; synthetic E2E p50 `t_observed → t_state_committed` < 500ms over ≥30 events; bomb-detect events achieve p50 < 100ms specifically.
- [ ] `scripts/probe_round_events.py:synthesize_mid_round_states` augmented to emit `a_alive` and `b_alive` per state. Random sample of 100 rows from re-run SQLite confirms presence and consistency (`a_alive + b_alive ≤ 10`, both ∈ [0, 5]).
- [ ] rib.gg ETL re-run produces ≥1000 distinct match_ids / ≥40k rounds in `data/round_events.sqlite` (matching Phase 2 coverage). Raw rib.gg responses cached to `data/ribgg_cache/` for future re-runs.
- [ ] `models/round_conclusion.json` (v2) keyed on `att|def|time_bucket|side|map` with cells covering `bomb_planted=True` rounds only (~25k samples expected). 5-tier hierarchical fallback chain populated.
- [ ] `live_theo(state)` dispatches: `state.bomb_planted=True → post_plant_p(...)` else `between_round_p(...)`. Test asserts both code paths exercised.
- [ ] `tests/ingestion/test_e2e.py` synthetic E2E test passes: fake rib.gg + fake OCR + fake Twitter → arbiter → MatchState → `live_theo` produces non-degenerate predictions (post-plant cells shift theo off side baseline by ≥ 1¢ in a synthetic state designed to land in a populated cell), seq_id monotonic, six-stage timestamps populated, p50 latencies as above.
- [ ] `mypy --strict src/pricing/` AND `mypy --strict src/state/` clean.
- [ ] `ruff check` clean on all of `src/`, `tests/`, `scripts/`.
- [ ] All Phase 1 + Phase 2 tests still GREEN (regression gate).
- [ ] STATE.md / ROADMAP.md updated to mark Phase 3 complete.

## Ambiguity Report

| Dimension          | Score | Min  | Status | Notes                                                            |
|--------------------|-------|------|--------|------------------------------------------------------------------|
| Goal Clarity       | 0.95  | 0.75 | ✓      | 7 REQs locked; latency targets pinned at Phase 3 boundary       |
| Boundary Clarity   | 0.90  | 0.70 | ✓      | DEC-024 v2 explicit cuts; ETL re-run inside Phase 3 (not 2.5)   |
| Constraint Clarity | 0.85  | 0.65 | ✓      | Alive-count keys + ETL re-run path locked; latency split clean   |
| Acceptance Criteria| 0.85  | 0.70 | ✓      | 17 pass/fail criteria; all grep- or test-verifiable              |
| **Ambiguity**      | 0.10  | ≤0.20| ✓      | Gate passed in 1 round                                           |

## Interview Log

| Round | Perspective | Question summary                                                  | Decision locked                                                              |
|-------|-------------|------------------------------------------------------------------|------------------------------------------------------------------------------|
| 1     | Researcher  | Post-plant lookup keys: alive-counts (ETL re-run) vs diff-only?   | **ETL re-run** — augment `synthesize_mid_round_states` to persist `a_alive`/`b_alive`, re-fetch ~1000 series, recalibrate. Cache rib.gg responses to disk. ~2-3 days inside Phase 3. |
| 1     | Researcher  | Phase 3 latency assertion (PRD's 200ms is partly Phase 4)?         | **bomb-detect → state-commit p50 < 100ms** in Phase 3 e2e. Reserves 100ms of the 200ms PRD budget for Phase 4 quote-cancel. |
| 1     | Researcher  | v1 03-RESEARCH.md / 03-VALIDATION.md still in repo — action?       | **Revert both** before SPEC.md (commits eb45503, a751ca1). Already executed in commit f9be3b6. Fresh research happens during the new `/gsd-plan-phase 03` cycle. |

---

*Phase: 03-live-ingestion-layer*
*Spec created: 2026-05-04 (v2 architecture)*
*Next step: /gsd-discuss-phase 03 — implementation decisions (how to build what's specified above)*
