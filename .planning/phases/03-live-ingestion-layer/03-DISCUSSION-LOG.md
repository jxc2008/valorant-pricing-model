# Phase 03: Live Ingestion Layer — Discussion Log (v2)

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `03-CONTEXT.md` — this log preserves the alternatives considered.
> Supersedes the v1 discussion log (2026-05-01) which covered ONNX kill-feed / 5-deque arbiter / vision_parser salvage decisions invalidated by the v2 architecture pivot.

**Date:** 2026-05-06
**Phase:** 03-live-ingestion-layer
**Areas discussed:** MatchState v2 field set + Phase-1 reconciliation, round_conclusion v2 surface + live_theo dispatch, REQ-7 ETL re-run, Post-plant alive widget OCR specifics
**Pre-discussion preamble:** User selected "Rewrite from scratch" when offered Update / Surgical update / View / Skip — accepting the hygiene cost of a full rewrite over patching a v1-era CONTEXT against v2 SPEC.

---

## MatchState v2 field set + Phase-1 reconciliation

### Q1: Single dataclass or split MatchState (dynamic) + MatchContext (static)?

| Option | Description | Selected |
|--------|-------------|----------|
| Single dataclass, ~19 fields | 13 v2 dynamic fields PLUS Phase 1 static (team_a, team_b, map_pool, map_side_orients, map_winners, pistol_winner_a). Drop only numerical_diff, side, econ_bucket. ~250 bytes/instance at slots=True. | ✓ |
| Split: dynamic MatchState + static MatchContext at engine init | LiveTheoEngine takes context once at match start. Cleaner separation. Cost: changes engine init signature; Phase 4 must build context per match. | |
| Strict SPEC literal: 13 fields only | Refactor live_theo to load static elsewhere via match_id registry. Largest refactor; arguably violates D-20. | |

**User's choice:** Single dataclass, ~19 fields (Recommended)
**Notes:** Carry forward Phase 1 D-17/D-18/D-19 static fields as-is. Cut only the v1 round_conclusion lookup keys.

### Q2: Where does the JSONL append happen — inside with_update or in arbiter?

| Option | Description | Selected |
|--------|-------------|----------|
| Decoupled — arbiter writes JSONL after with_update returns | with_update is pure (no I/O). Arbiter is sole writer of state AND sole appender of JSONL. Pure mutator unit-testable without disk fixtures. | ✓ |
| Tight coupling — with_update appends JSONL itself | seq_id discipline guaranteed by construction. Cost: every test needs tmp_path fixture; harder dry-run. | |
| Both — with_update emits a Diff object, caller appends | Pure mutator with explicit data flow; slightly verbose call sites. | |

**User's choice:** Decoupled (Recommended)
**Notes:** Single `commit(prev_state, new_state, source, event_type)` helper in `src/state/` enforces discipline structurally.

### Q3: JSONL line shape?

| Option | Description | Selected |
|--------|-------------|----------|
| Diff-only: seq_id + six timestamps + source/event_type + fields_changed | Per-arbiter-commit line. Quarantined: seq_id=null, quarantined=true. ~200-400B/line × ~1500 events/match. | ✓ |
| Full snapshot per line | Whole MatchState dumped each commit. 50× disk cost; kills forensic analysis. | |
| Diff + periodic snapshot | Diff lines normally; `kind: "snapshot"` every N events. Premature optimization. | |

**User's choice:** Diff-only (Recommended)
**Notes:** Phase 4 fills `t_theo_computed`/`t_quote_sent` either as follow-up keyed by seq_id or in `data/metrics/{match_id}.metrics.jsonl` parallel — planner-deferred.

---

## round_conclusion v2 surface + live_theo dispatch

### Q1: How does RoundConclusionLookup expose the v2 two-path API?

| Option | Description | Selected |
|--------|-------------|----------|
| Two methods on RoundConclusionLookup, two Protocols | Add `between_round_p` AND `post_plant_p`. v1 `lookup` method DELETED. v1 `RoundConclusionFn` Protocol DELETED. | ✓ |
| One unified method that dispatches internally on bomb_planted | Single `lookup(state)`. Couples MatchState shape to round_conclusion module — violates layered architecture. | |
| Two free functions outside the class | Module-level functions; lookup becomes pure data container. More functional; less ergonomic. | |

**User's choice:** Two methods + two Protocols (Recommended)
**Notes:** Atomic surface change in one commit. v1 frozen-surface contract (Phase 2 D-15) intentionally broken — no value keeping a v1 method against v2 schema.

### Q2: How does live_theo dispatch the bomb_planted branch?

| Option | Description | Selected |
|--------|-------------|----------|
| Top-level current-round override; DP unchanged | live_theo computes `p_round = post_plant_p(...)` separately when bomb_planted=True; composes via series_value(state_after_a) and series_value(state_after_b). DP recursion uses Phase-1 round_p_for_round for between-round future-rounds. | ✓ |
| Thread a current-round override into _RoundPFnImpl | Couples post-plant signal through closure machinery; harder to reason about which calls hit which path. | |
| Two separate engine entry points | Parallel implementations of top-level math. Risks parallel-models bug class (PRD §12.2 #6 / CRule 6). | |

**User's choice:** Top-level current-round override; DP unchanged (Recommended)
**Notes:** Mirrors how `_compute_vega` already composes one-step branches. Mid-round-not-planted: between-round path with degraded confidence (Phase 4 mode-selector → IDLE per DEC-001 v2).

### Q3: How does models/round_conclusion.json migrate from v1 to v2 schema?

| Option | Description | Selected |
|--------|-------------|----------|
| Atomic replace, same filename, schema-version field | `"schema_version": 2`; `from_json` HARD-FAILS on mismatch. v1 history preserved in git. | ✓ |
| Versioned filenames, both retained on disk | Side-by-side debugging. Cost: dual artifacts in models/, .gitignore tweaks. | |
| Delete v1, no schema_version field | Simplest. Risk: future schema change has no version anchor. | |

**User's choice:** Atomic replace, same filename, schema-version field (Recommended)
**Notes:** v2 JSON shape: `{schema_version: 2, side_baseline: {...}, cells_minimal/no_map/no_time/full: {...}}`. _Cell shape (n, p_hat, parent_p) unchanged.

---

## REQ-7 ETL re-run: cache, scope, idempotency

### Q1: What's the re-run scope for the ETL?

| Option | Description | Selected |
|--------|-------------|----------|
| Full re-fetch of the same ~1000 series with caching | Augmented `synthesize_mid_round_states` persists `a_alive`/`b_alive`. NEW `data/round_events_v2.sqlite` (preserve v1 db). | ✓ |
| Augment-existing: backfill alive counts where derivable | numerical_diff doesn't carry trade-direction; ambiguous in many states. Likely degrades to mostly-full re-fetch. | |
| Smaller re-run scope (~500 series) | Halves post-plant calibration sample; sparser cells; defer full coverage to Phase 5. | |

**User's choice:** Full re-fetch with caching (Recommended)
**Notes:** v1 sqlite retained on disk for forensic / re-run validation.

### Q2: How is the rib.gg response cache implemented?

| Option | Description | Selected |
|--------|-------------|----------|
| requests-cache library, filesystem backend at data/ribgg_cache/ | Standard library; Phase 2 resilience patterns compose cleanly. ~5 GB on disk; .gitignore excludes. | ✓ |
| Hand-rolled JSON-per-response cache | ~50 LOC; no built-in TTL. Reinvents the wheel. | |
| SQLite cache table inside data/round_events_v2.sqlite | Cache + computed data coupled. Re-running calibration re-fetches everything. | |

**User's choice:** requests-cache filesystem backend (Recommended)
**Notes:** Add `requests-cache` to `pyproject.toml`. `.gitignore` excludes `data/ribgg_cache/`.

### Q3: Resume strategy if the re-run dies mid-way?

| Option | Description | Selected |
|--------|-------------|----------|
| Trust the cache + per-series SQLite commit | Cache makes already-fetched calls ~instant. Per-series transaction (`SAVEPOINT match_<id>`); resume by `SELECT DISTINCT match_id`. Idempotent by construction. | ✓ |
| Explicit progress tracker file | `data/etl_progress.json` with processed/failed lists. Drift risk; second source-of-truth. | |
| No resume — truncate and restart on any failure | Throws away progress. | |

**User's choice:** Trust the cache + per-series SQLite commit (Recommended)
**Notes:** Mirrors Phase 2's pattern.

### Q4: time_remaining_bucket granularity?

| Option | Description | Selected |
|--------|-------------|----------|
| 5s buckets — 9 buckets | ~3150 cells_full slots over ~25k samples ≈ 8 samples/cell. Captures last-5-second urgency. | ✓ |
| 10s buckets — 5 buckets | Coarser; ~14 samples/cell. Loses end-of-timer urgency. | |
| 15s buckets — 3 buckets (early/mid/late) | Coarsest; ~24 samples/cell. May be too coarse for late-clutch dynamics. | |

**User's choice:** 5s buckets — 9 buckets (Recommended)
**Notes:** `TIME_BUCKET_WIDTH_S = 5.0` in src/config/constants.py. Bayesian shrinkage (SHRINK_PRIOR=15) handles sparsity.

---

## Post-plant alive widget OCR specifics

### Q1: Source-of-truth for the post-plant alive widget's visual region?

| Option | Description | Selected |
|--------|-------------|----------|
| Hand-calibrated ROIs from sample 2026 VCT VOD frames, in src/config/constants.py | Pin POST_PLANT_ATTACKERS_ROI, POST_PLANT_DEFENDERS_ROI + BROADCAST_TEMPLATE_VERSION. Single-template assumption. | ✓ |
| Auto-detect via cv2.matchTemplate | 5-10ms per frame burns budget; silent low-match-score failure mode. | |
| Defer ROI calibration to operator-driven smoke run | SPEC explicitly traded off operator runs for synthetic E2E. | |

**User's choice:** Hand-calibrated ROIs in constants.py (Recommended)
**Notes:** International-template ROIs first; multi-template fallback if Phase 3 surfaces drift.

### Q2: When does the post-plant alive widget OCR actually run?

| Option | Description | Selected |
|--------|-------------|----------|
| Hard-gated on state.bomb_planted=True; stops within 1 cycle of defuse/round-end | Worker activates at 250ms when bomb_planted=True; yields when False. Saves ~30ms/cycle CPU during ~80% of match runtime. | ✓ |
| Always-on OCR, but discard reads when bomb_planted=False | Reads emitted but quarantined when False. Wasteful CPU. | |
| OCR only the moment bomb_planted flips True; one-shot read | Misses kill events during 45s window. Defeats purpose. | |

**User's choice:** Hard-gated activation (Recommended)
**Notes:** OCR_POST_PLANT_ALIVE_CADENCE_MS = 250.

### Q3: What happens when the OCR read returns garbage / no digit detected?

| Option | Description | Selected |
|--------|-------------|----------|
| Emit None for that field; don't update state; arbiter quarantines the tick | Quarantine line in JSONL with `quarantined: true, fields_proposed: {...}, quarantine_reason: 'ocr_parse_fail'`. State carries forward. Lookup falls through hierarchy if alive missing for >2 ticks. | ✓ |
| Carry-forward last good reading silently | Risk: silent stale data. | |
| Treat any parse failure as a kill switch trip | Conflates ingestion staleness with parse-quality issues. | |

**User's choice:** Emit None → quarantine → carry-forward via no-state-update (Recommended)
**Notes:** Tesseract: PSM 10, whitelist `012345`, grayscale + Otsu + 2× upscale. Existing 5s staleness kill switch covers extended degradation.

### Q4: Where does `time_left_s` (the post-plant 45s timer) come from?

| Option | Description | Selected |
|--------|-------------|----------|
| Computed: `time_left_s = max(0, 45 - (now - t_bomb_plant))` | When bomb_planted=True commits, arbiter records t_bomb_plant_observed. time_left_s computed-on-read. POST_PLANT_TIMER_S = 45.0. | ✓ |
| Read from HUD timer widget (extra OCR target) | Scope creep — SPEC §3 lists three OCR targets + alive widget. | |
| Read from rib.gg API (server-side timer) | rib.gg poll cadence is 5s — too coarse for 45s timer. | |

**User's choice:** Computed (Recommended)
**Notes:** Detection-to-commit latency offsets ~250ms median — fits within 5s bucket width.

---

## Wrap-up question

### "Which gray areas remain unclear?"

| Option | Description | Selected |
|--------|-------------|----------|
| I'm ready for context | Write CONTEXT.md with the 13 decisions. Concurrency runtime + arbiter mechanism + bomb-detect hot-path covered by stale CONTEXT D-04/D-06 carry-forward; Twitter rule set is a planner-level constant pin. | ✓ |
| Explore concurrency + arbiter mechanism | Re-confirm asyncio + ThreadPoolExecutor + 3-deque tick model. | |
| Explore bomb-detect <100ms hot-path | OCR detect (500ms cadence + ~80ms decode) is already ≥50% of budget; engineer hot-path bypass. | |
| Explore Twitter v2 rule set + 2026 season | Pin static league watch list; API tier (free/basic/pro). | |

**User's choice:** I'm ready for context (Recommended)

---

## Claude's Discretion (planner picks; not asked of user)

- Whether `src/pricing/data.py` keeps a one-line re-export shim for `MatchState` during transition or is deleted outright. SPEC §1: "planner picks".
- Concurrency runtime: stale CONTEXT D-06 baseline (asyncio + ThreadPoolExecutor) carries forward post-ONNX-removal. Researcher confirms tesseract releases GIL during `pytesseract.image_to_string`.
- Arbiter mechanism: stale CONTEXT D-04 baseline (per-event-type `collections.deque` + `tick()` eviction) carries forward; deque count drops 5 → 3 per DEC-006 v2.
- Twitter v2 rule set: stale CONTEXT D-07 picked `["#VCT", "#VALORANTChampions", "#VCTAmericas", "#VCTEMEA", "#VCTPacific"]`. Researcher pins concrete 2026-season caster/league/team-org accounts.
- Twitter API tier confirmation: researcher confirms streaming v2 is available on the project's tier; if not, listener degrades to no-op (per SPEC §4).
- bomb-detect → state-commit p50 < 100ms hot-path engineering: pre-allocate hot-path objects, buffered JSONL writer — planner picks.
- Twitter listener implementation: `tweepy.AsyncStreamingClient` vs raw aiohttp — researcher picks.
- YouTube stream decode pipeline (yt-dlp + ffmpeg + opencv frame grab vs alternatives) — researcher picks.
- Whether `scripts/calibrate_round_conclusion.py` is rewritten in place or new sibling `calibrate_round_conclusion_v2.py` is added — planner picks.
- `time_bucket_idx` derivation in live_theo's post-plant dispatch: floor vs round-half-up at the bucket boundary.

## Deferred Ideas

- bo3.gg API adapter (Phase 5 robustness)
- vlr.gg API adapter (Phase 5)
- Twitch / YouTube IRC chat as soft cross-confirm (follow-up phase)
- Per-match dynamic Twitter rule sync (if static rules prove noisy)
- GPU-accelerated OCR (Phase 6 only if Phase 5 paper-trade Brier shows OCR-latency-driven misses)
- Per-event-class hybrid checkpoint snapshots in JSONL (replay optimization)
- 30-min operator-driven live smoke run (Phase 5 bring-up gate alternative)
- Multi-template OCR fallback for international vs regional VCT layouts (Phase 5 robustness)
- Wider time_remaining_bucket calibration sweep (10s/15s) using cached responses (Phase 5)
- Backfill `a_alive`/`b_alive` into Phase 2 v1 sqlite if a clean derivation surfaces (Phase 5 forensic)
- Phase 4 follow-up JSONL line for `t_theo_computed`/`t_quote_sent` placement (planner-deferred to Phase 4)
