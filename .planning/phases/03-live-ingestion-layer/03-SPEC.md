# Phase 03: Live Ingestion Layer — Specification

**Created:** 2026-05-01
**Ambiguity score:** 0.16
**Requirements:** 6 locked

## Goal

Real-time `MatchState` is fed by tiered, arbited multi-source ingestion (rib.gg API + OCR + Twitter) at sub-500ms latency from observable in-game event → updated theo. Every state mutation is monotonically versioned via `seq_id`, six-stage timestamped, and appended to a JSONL event log.

## Background

**Current state in this repo:**
- `src/state/__init__.py` — empty (just docstring). Target home for `MatchState` per D-14.
- `src/ingestion/__init__.py` — empty. Target for OCR / scoreboard polling / text listener / cross-source arbiter.
- `src/pricing/data.py` — Phase 1 stub `MatchState` lives here (17 fields, frozen dataclass). Phase 1's `live_theo`, DP, and round-conclusion lookup all import it from this location.
- `scripts/probe_round_events.py` — Phase 2 already proved the rib.gg `/v1/{events,series,matches/{id}/details}` chain works end-to-end with `requests` + `tenacity` retry + `Connection: close` resilience. Same patterns transplant directly to live polling.
- `models/round_conclusion.json` — Phase 2 calibrated lookup; consumed by `live_theo` once the new `MatchState` carries the four mid-round signals (`numerical_diff`, `bomb_planted`, `side`, `econ_bucket`) populated from real ingestion (Phase 1's stub had them frozen at construction).

**What does NOT exist locally:**
- No `vlr_scraper.py` / `rib_scraper.py` / `vision_parser.py` in `reference/` (only `fair_value.py`, `market_maker.py`, `odds_utils.py`, `theo_engine.py`). The references in REQ-scoreboard-polling and REQ-ocr-pipeline point to `thunderedge/worktrees/market-maker/` (sibling repo). Phase 3 must copy those files into `reference/` first as read-only salvage, then port them into `src/ingestion/`.
- No live polling, no OCR pipeline, no Twitter listener, no arbiter.

**What triggers Phase 3:** Phase 2 shipped a calibrated `RoundConclusionLookup`, but `live_theo` only sees real mid-round signals when an ingestion layer populates `MatchState` over time. Without Phase 3, `live_theo` runs once per match construction with frozen state — no live edge.

## Requirements

1. **MatchState engine + JSONL log**: Single `@dataclass MatchState` migrated to `src/state/match_state.py`, extended with the Phase 3 fields (`seq_id`, `last_updated_ts`, `players_alive_a/b`, `ults_a/b`, `time_left_s`, `econ_a/b`); mutators bump monotonic `seq_id`; every mutation appended to a JSONL event log on disk.
   - **Current:** Phase 1 stub MatchState in `src/pricing/data.py` (17 fields, frozen, no mutators, no seq_id, no event log).
   - **Target:** `src/state/match_state.py` exports a versioned MatchState with mutator methods that bump `seq_id` and append to JSONL. `src/pricing/data.py` re-exports from the new location for backwards compatibility (or is deleted with all imports updated in one atomic plan).
   - **Acceptance:** Test asserts `seq_id` strictly monotonic across N=1000 random mutator calls; JSONL file is line-by-line parseable with each line containing the post-mutation state; `mypy --strict src/pricing/` AND `mypy --strict src/state/` clean.

2. **rib.gg scoreboard polling**: A 5-second-cadence poller against the rib.gg `/v1/series` and `/v1/matches/{id}/details` endpoints (the same chain Phase 2 proved working) feeds score-change events into the arbiter. Authoritative but slowest source.
   - **Current:** No poller exists; only the offline ETL `scripts/probe_round_events.py` from Phase 2.
   - **Target:** `src/ingestion/scoreboard.py` (ported from `thunderedge/.../rib_scraper.py` + `vlr_scraper.py`, both copied into `reference/` first) yields a stream of typed score-update events at 5s cadence with `Connection: close` + tenacity retry per the Phase 2 resilience patterns.
   - **Acceptance:** Integration test with monkeypatched `requests.get` returning fixture series/match-details JSON; poller emits N events at the expected cadence; events conform to the typed shape consumed by the arbiter.

3. **OCR pipeline at PRD §5.1 cadences**: Computer-vision parser of broadcast HUD elements with per-target cadences and latency budget.
   - **Current:** No OCR; only the offline scrape.
   - **Target:** `src/ingestion/ocr.py` (ported from `thunderedge/.../vision_parser.py`, salvaged into `reference/` first) decodes the YouTube low-latency stream at: score banner 250ms, kill feed 100ms, bomb icon 500ms, round-end banner 100ms-during-round-end-window. Uses GPU if available, else tesseract + small CNNs. Decode + inference ≤ 100ms per frame total.
   - **Acceptance:** Per-target benchmark test asserts decode + inference < 100ms median over 50 frames; per-target cadences honored within ±10% jitter under sustained load; produces typed events the arbiter consumes.

4. **Twitter v2 streaming text listener**: Soft cross-confirmation source. Twitter API v2 streaming filter on match-related hashtags / accounts.
   - **Current:** Does not exist.
   - **Target:** `src/ingestion/text_listener.py` opens a Twitter v2 streaming connection with hashtag/account rules, parses tweet content for round/score signals, emits typed soft-confirmation events into the arbiter. NEVER sole-source confirmation — only used to cross-confirm CV signals.
   - **Acceptance:** Integration test with a mocked Twitter stream feeding canned tweets; listener emits typed soft-events; arbiter never commits a state change based ONLY on a Twitter event (test explicitly asserts a Twitter-only update is quarantined, not committed).

5. **Cross-source arbiter with PRD §5.1 / DEC-006 rules**: Three-queue pipeline `sources → pending_updates → arbiter → confirmed_updates → state engine` with per-event-type confirmation rules. Quarantined updates logged but not committed.
   - **Current:** No arbiter exists.
   - **Target:** `src/ingestion/arbiter.py` implements the pipeline with these rules: score change ≥ 2 sources within 2s; bomb-plant/kill/numerical-flip 1 CV-based source if kill-feed cross-confirms within same frame; round-end soft commit, hard-confirmed by next score update; pre-match lineup/sides API single-source. Quarantined events written to a quarantine log line in the JSONL.
   - **Acceptance:** Property test enumerates each event type and asserts the arbiter rule fires correctly with synthetic source emissions; quarantined events appear in the JSONL log with `quarantined: true` annotation; never confirmed.

6. **Six-stage latency instrumentation**: Every event carries timestamps at each pipeline stage and is logged to a metrics file.
   - **Current:** No latency instrumentation; events have no timestamp lineage.
   - **Target:** Every confirmed event records the six-stage timestamp set: `t_observed, t_ingested, t_arbited, t_state_committed, t_theo_computed, t_quote_sent` (the last stage is populated by Phase 4 quoting; Phase 3 reserves the field). Logged to a metrics file (separate JSONL) consumed by Phase 5 latency analysis.
   - **Acceptance:** End-to-end test with synthetic event emission asserts all six fields populated (with `t_quote_sent` as None during Phase 3 dev, set in Phase 4); p50 latency from `t_observed` → `t_state_committed` < 500ms in the synthetic run; metrics file is line-by-line parseable.

## Boundaries

**In scope:**
- Migration of `MatchState` from `src/pricing/data.py` to `src/state/match_state.py` with Phase 3 fields added (atomic — single plan).
- JSONL event log for state mutations (separate from the metrics file).
- rib.gg scoreboard poller built on top of the Phase 2 verified `/v1/` endpoint chain.
- OCR pipeline ported from `vision_parser.py` (after copying to `reference/` as read-only salvage).
- Twitter v2 streaming listener with full integration through arbiter (NOT stubbed).
- Cross-source arbiter implementing PRD §5.1 / DEC-006 rules.
- Six-stage timestamp lineage on every event (Phase 4 fills `t_quote_sent`).
- Synthetic E2E integration test in `tests/ingestion/test_e2e.py` driving fake rib.gg + fake OCR + fake Twitter through arbiter → MatchState → live_theo, asserting seq_id monotonicity, latency budget, and theo non-degeneracy.

**Out of scope:**
- Quoting / order placement / Kalshi integration — that's Phase 4 (REQ-kalshi-order-manager, REQ-mode-selector, REQ-mm-quoter, REQ-directional-taker, REQ-kelly-sizer, REQ-kill-switches). Phase 3 only reserves `t_quote_sent` as a None placeholder.
- Backtest / paper trading / Brier measurement — Phase 5.
- Persistent SQLite live state — `CON-live-state-no-sqlite` (in-memory + JSONL only).
- 30-min live operator-driven smoke run — explicitly traded off in favor of synthetic E2E test in CI.
- bo3.gg API — REQ-scoreboard-polling mentions it as backup, but rib.gg is the primary; bo3.gg adapter slips to a follow-up phase if Path A reliability degrades. (Phase 2's PROBE-LOG already documented bo3.gg as "considered, rejected" for the offline ETL.)
- vlr.gg adapter — same: rib.gg is sufficient and proven; vlr.gg may be added as a third source for arbiter robustness in Phase 5 if needed.

## Constraints

- **Latency budget:** End-to-end `t_observed → t_state_committed < 500ms (median)` per REQ-end-to-end-latency. OCR per-frame ≤ 100ms (50ms decode + 50ms inference per PRD §5.1).
- **State storage:** In-memory MatchState + JSONL event log on disk. No SQLite (`CON-live-state-no-sqlite`).
- **Mutator monotonicity:** Every mutator must bump `seq_id` BEFORE the JSONL append; quoting layer (Phase 4) only acts on monotonically-increasing seq_ids.
- **OCR cadences (CON-ingestion-cadences):** Score banner 250ms; kill feed 100ms; bomb icon 500ms; round-end banner 100ms during round-end window.
- **Type discipline:** `mypy --strict` extended from `src/pricing/` to ALSO cover `src/state/`. `src/ingestion/` stays gradual (per CLAUDE.md current scoping) but new code should still type-annotate.
- **No magic numbers:** All thresholds (cadences, latency budgets, arbiter window sizes) declared in `src/config/constants.py` per CRule 12.
- **Dry-run preserved:** Phase 3 ingestion runs alongside dry-run pricing; no live trading is enabled by Phase 3 (`--live` flag remains a Phase 4 concern).
- **Salvage discipline:** `vlr_scraper.py`, `rib_scraper.py`, `vision_parser.py` MUST be copied into `reference/` first (read-only, like the existing salvage), then ported into `src/ingestion/` adapting to this repo's conventions. Do NOT import directly from `thunderedge/`.

## Acceptance Criteria

- [ ] `src/state/match_state.py` exists with MatchState carrying all 17 Phase 1 fields PLUS Phase 3 fields (`seq_id`, `last_updated_ts`, `players_alive_a/b`, `ults_a/b`, `time_left_s`, `econ_a/b`); `src/pricing/data.py` either re-exports or is deleted with all imports updated atomically.
- [ ] Mutator test passes: 1000 random mutator calls produce strictly monotonic `seq_id` and a parseable JSONL event log on disk.
- [ ] `reference/vlr_scraper.py`, `reference/rib_scraper.py`, `reference/vision_parser.py` exist (committed as read-only salvage); `src/ingestion/scoreboard.py` and `src/ingestion/ocr.py` ported and integrated.
- [ ] `src/ingestion/scoreboard.py` integration test passes: monkeypatched fixtures yield typed events at 5s cadence.
- [ ] `src/ingestion/ocr.py` benchmark test passes: 50-frame median decode + inference < 100ms; per-target cadences within ±10% jitter.
- [ ] `src/ingestion/text_listener.py` integration test passes: mocked Twitter stream emits typed soft-events; Twitter-only state update is quarantined (test explicit).
- [ ] `src/ingestion/arbiter.py` property tests pass: every event-type rule from PRD §5.1 / DEC-006 fires correctly with synthetic source emissions; quarantined events appear in JSONL with `quarantined: true`.
- [ ] Every confirmed event in the JSONL carries the six-stage timestamp set; metrics file parseable; synthetic E2E p50 `t_observed → t_state_committed` < 500ms.
- [ ] `tests/ingestion/test_e2e.py` E2E integration test passes: fake rib.gg + fake OCR + fake Twitter → arbiter → MatchState → `live_theo` produces non-degenerate predictions, seq_id monotonic, six-stage timestamps populated.
- [ ] `mypy --strict src/pricing/` AND `mypy --strict src/state/` clean.
- [ ] `ruff check` clean on all of `src/`, `tests/`, `scripts/`.
- [ ] All Phase 1 + 2 tests still GREEN (regression gate).
- [ ] STATE.md / ROADMAP.md updated to mark Phase 3 complete.

## Ambiguity Report

| Dimension | Score | Min | Status | Notes |
|---|---|---|---|---|
| Goal Clarity | 0.85 | 0.75 | ✓ | 6 REQs, all in scope, no deferrals — one atomic phase |
| Boundary Clarity | 0.85 | 0.70 | ✓ | Twitter full-build, OCR full-build, salvage-via-reference, MatchState atomic move |
| Constraint Clarity | 0.80 | 0.65 | ✓ | Latency, cadences, type discipline, no-SQLite all locked |
| Acceptance Criteria | 0.85 | 0.70 | ✓ | E2E synthetic integration test + per-REQ acceptance + 11 falsifiable checks |
| **Ambiguity** | **0.16** | ≤0.20 | ✓ | Gate passed |

## Interview Log

| Round | Perspective | Question summary | Decision locked |
|---|---|---|---|
| 1 | Researcher | How to source `vlr_scraper.py` / `rib_scraper.py` / `vision_parser.py` (live in sibling thunderedge/ repo)? | **Copy + commit salvage** — copy into `reference/` as read-only, then port to `src/ingestion/` |
| 1 | Researcher | MatchState move + extend (D-14) — what scope? | **Move + extend in one plan** — atomic migration to `src/state/match_state.py` with Phase 3 fields added; Phase 1 imports updated atomically |
| 2 | Boundary Keeper | Twitter listener scope — full build, stub, or defer? | **Full build now** — Twitter v2 streaming filter wired through arbiter as soft cross-confirmation source |
| 2 | Failure Analyst | What's the falsifiable "Phase 3 done" end-to-end check? | **Synthetic E2E integration test** — `tests/ingestion/test_e2e.py` drives fake rib.gg + fake OCR + fake Twitter → arbiter → MatchState → `live_theo`; asserts seq_id monotonicity, latency budget, theo non-degeneracy |

---

*Phase: 03-live-ingestion-layer*
*Spec created: 2026-05-01*
*Next step: /gsd-discuss-phase 03 — implementation decisions (how to build what's specified above)*
