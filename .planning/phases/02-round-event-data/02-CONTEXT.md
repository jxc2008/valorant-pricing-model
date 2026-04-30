# Phase 2: Round-event data — Context

**Gathered:** 2026-04-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Acquire round-by-round event data offline and populate the `round_conclusion` lookup cells, OR explicitly defer (Path C) with documented rationale. Phase 1 already shipped the `RoundConclusionLookup` skeleton — its public surface is FROZEN. Phase 2 only:
1. Probes data sources and decides Path A / B / C per DEC-017.
2. If Path A or B: produces a `round_events` SQLite table per `CON-round-events-schema`, then runs `scripts/calibrate_round_conclusion.py` to populate the four `cells_*` dicts (and `side_baseline`) with `_Cell(n, p_hat, parent_p)` instances.
3. Persists the populated lookup to `models/round_conclusion.json`; Phase 4's engine init loads it.
4. If Path C: zero code changes to `round_conclusion.py` — the existing flat-0.5 skeleton ships as-is, and a HARD CONTRACT is locked with Phase 4 (mid-round triggers fire for order pulls but do NOT move theo).

**In scope:**
- `scripts/probe_round_events.py` — endpoint scoping + acceptance evaluation per Area A's bar
- `scripts/calibrate_round_conclusion.py` — populates cells via empirical Bayes shrinkage
- `data/round_events.sqlite` (or `.planning/data/`) — calibration dataset
- `models/round_conclusion.json` — calibrated lookup serialization
- `RoundConclusionLookup.from_json(path)` loader — additive change to the Phase 1 class, does not modify `__call__` / `lookup` / `_Cell` signatures
- `scripts/probe_round_events.py` writes `PROBE-LOG.md` recording the path decision (A/B/C) with evidence
- If Path B: OCR labeler under `scripts/ocr_round_events.py` + 100-VOD label set under `data/round_events_ocr/`

**Out of scope (deferred to other phases):**
- Live ingestion / OCR-during-match → Phase 3 (Path B's offline OCR is a one-time labeling job, NOT live)
- Cross-source arbitration → Phase 3
- Quoting / mid-round directional flips → Phase 4 (Phase 2 only locks the Phase 4 contract)
- Mid-round vega refinement, automated drift detection, weekly recalibration → Phase 5 / Phase 7
- Per-half pistol-winner extension to `pistol_winner_a` (rounds 14/15) → Phase 2 follow-up captured in `dp.py:33-47` but NOT implemented here unless it organically falls out of round_events ingestion

</domain>

<decisions>
## Implementation Decisions

### Probe scope, source priority, and acceptance bar (Area A)

- **D-01:** Source priority — `scripts/probe_round_events.py` attempts in order: (1) **rib.gg internal API direct** (auth required), (2) **`valorantr` R-package** via subprocess (no R dep — call as CLI; if R is unavailable on Windows, treat this source as definitively failed and continue), (3) **`FlynV/RIB.GG-Web-Scraper`** Node project, (4) **bo3.gg slug endpoint** (CLAUDE.md notes filter params are broken — only single-match-by-slug works). Probe stops at the first source that meets the acceptance bar.

- **D-02:** Acceptance bar for "Path A passes" — the chosen source must reliably return per-round `(ts_round_start, ts_round_end, ts_first_kill)` AND at least one mid-round event timestamp (e.g., `ts_bomb_plant`) for ≥50% of rounds. Loose bar — maximizes Path A acceptance because rib.gg-derived sources rarely expose 100% of mid-round events.

- **D-03:** Coverage bar — **1000+ matches, last 18 months, tier-1 only (VCT)**. ~75,000 rounds. Yields populated `cells_full` for popular `(numerical_diff, bomb_planted, side, econ_bucket, map)` combinations. The 18-month window straddles 2-3 patch metas — the calibrator does NOT weight by recency in v1; recency-weighting is a Phase 5/7 enhancement if Brier surfaces meta drift.

- **D-04:** Probe time cap — **1 week from probe start** (extended from DEC-017's `~3 days` to allow endpoint debugging, auth setup, retry on rate limits). After 1 week without acceptance, declare Path A failed and route to Path B per Area C.

- **D-05:** Partial-pass policy — if Path A returns per-round timestamps but `bomb_plant` is missing for >50% of rounds (or any other mid-round event class is sparse), TREAT THIS AS A PASS but populate ONLY `cells_no_econ` and `cells_no_map`. Document the gap in `PROBE-LOG.md` so Phase 5 calibration knows to weight predictions accordingly. Cleaner than a strict reject.

### `mid_round_states[]` shape (Area B)

- **D-06:** Sampling strategy — **Hybrid: events + 5s heartbeats**. Each `mid_round_states[]` entry is `{t_offset: float, kind: "event" | "heartbeat", numerical_diff: int, bomb_planted: bool, side: str, econ_bucket: str}`. If the source API does not expose 5s heartbeats natively (the common case), the probe synthesizes them by carry-forward from the most recent prior event. The synthesized vs native distinction is captured by `kind` so the calibrator can weight differently if Phase 5 finds carry-forward bias.

- **D-07:** Per-entry payload — exactly the four fields the `cells_full` lookup keys on (`numerical_diff`, `bomb_planted`, `side`, `econ_bucket`). `map_name` is stored once at the row level (not duplicated in every entry). Storage-efficient. Wider snapshot fields (`ult_count`, `players_alive`, `time_left_s`) are deferred to Phase 5 if calibration surfaces a need.

- **D-08:** `numerical_diff` derivation between events — **carry-forward from the last event**. Events are ordered by `(t_offset, event_id)` to handle simultaneous-tick double-kills deterministically. Linear interpolation rejected (numerical_diff is discrete). The same carry-forward semantics will be used by Phase 3's live ingestion, so Phase 2's calibration data and Phase 3's runtime data are mutually consistent.

- **D-09:** Storage ordering — `mid_round_states[]` is a **time-ordered list sorted ascending by `t_offset`**, persisted as a SQLite JSON array column. Required for carry-forward derivation and for any Phase 5 timeline-based analysis.

### Path B / C escalation policy (Area C)

- **D-10:** If Path A fails the acceptance bar after the 1-week cap → **commit to Path B (2-week OCR labeling)**. The user judges mid-round signal value worth the calendar cost. Path B = OCR-label 100 VODs at 1Hz with 10% hand-verified. Path B labels live in `data/round_events_ocr/{match_id}/{map_num}.json` and feed the same `round_events` SQLite table downstream.

- **D-11:** Path C output (if Path A AND Path B both fail) — **flat 0.5**. Zero code changes to `round_conclusion.py`; the existing skeleton ships as-is. CONTEXT.md and `02-VERIFICATION.md` document the deferral. `models/round_conclusion.json` is NOT created.

- **D-12:** Phase 4 hard contract (locked here, enforced in Phase 4 planning) — **Path C ⇒ Phase 4's directional-flip event triggers (numerical imbalance, bomb plant) STILL fire for order-pull purposes BUT do NOT move theo**. Mid-round vega is flat between rounds. This codifies the literal D-06 reading from Phase 1's CONTEXT and prevents the audit-engine parallel-models bug class (PRD §12.2 #6 / CRule 6) from re-emerging in Phase 4.

### Calibration method (Area D)

- **D-13:** Method — **empirical Bayes shrinkage with `SHRINK_PRIOR=15`**. Matches the Phase 1 `_Cell` skeleton verbatim: `shrunk = (n × p_hat + 15 × parent_p) / (n + 15)`. Audit-engine pattern, transparent, mypy-friendly, no external deps. Logistic regression and GBT explicitly rejected — opaquer interpretation, heavier deps, and would require replacing the `_Cell` class.

- **D-14:** `parent_p` derivation — **recursive walk up the chain, deepest level first**. `cells_full` cells use the corresponding `cells_no_econ` cell as `parent_p`; `cells_no_econ` uses `cells_no_map`; `cells_no_map` uses `cells_minimal`; `cells_minimal` uses `side_baseline`; `side_baseline` is computed from `data/half_win_rates.json` per-side marginals (with 0.5 fallback if the half-rate file is missing or has zero coverage). Each level shrinks toward the level above — preserves the inductive structure that motivated the 5-tier fallback chain. Calibration is implemented as a bottom-up pass: populate `side_baseline` first, then `cells_minimal`, ... then `cells_full`. Each level can reference its parent because the parent is already populated by the time the level runs.

- **D-15:** Persistence — **`models/round_conclusion.json`**. Plain text JSON with explicit per-level dicts, reviewable in PRs, diff-friendly. `RoundConclusionLookup.from_json(path) → RoundConclusionLookup` is a new classmethod added to `round_conclusion.py` (additive — does not modify any Phase 1 signature). Engine init in Phase 4 loads it. Total file size ~100KB at 1000-match coverage.

- **D-16:** Recalibration cadence — **manual one-off Phase 2 run; recompute on demand** (after a major patch, new map, or Phase 5's drift detector flags Brier degradation). Automated weekly reruns and per-match incremental updates are explicitly Phase 7 work. The `scripts/calibrate_round_conclusion.py` is idempotent — re-running it on a refreshed `round_events` table regenerates the JSON.

### Claude's discretion

- Probe failure logging shape (field names in `PROBE-LOG.md`, whether to emit JSONL or markdown) — researcher/planner choice.
- OCR tooling for Path B (Tesseract, EasyOCR, PaddleOCR, etc.) — researcher to compare on a sample VOD frame; CLAUDE.md notes Tesseract is already on the system PATH so default to that unless a sample frame fails it.
- Half-rate-derived `side_baseline` computation: which exact statistic to extract from `half_win_rates.json` — let the planner pick after reading the file's actual schema.
- Probe credential management (rib.gg auth) — `.env` per CLAUDE.md "Kalshi" pattern; planner picks the variable name and any safety net (skip-if-unset semantics).
- Whether to gate Path B on user re-confirmation at the time the 1-week probe cap hits, or auto-trigger — D-10 says "commit to Path B" so default to auto-trigger; planner can add a re-confirm prompt if scope demands it.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Authoritative design docs
- `prd.md` §5 — four-layer architecture (Ingestion, State, Theo, Quoting); Phase 2 lives in the offline-data side of Theo
- `prd.md` §7 step 4 — Phase 2 in the build sequence; DEC-017 path-decision context
- `prd.md` §9 — locked decisions including DEC-017 (path gate) and DEC-015 (SQLite for dataset cache)
- `roadmap.md` §2 — Phase 2 implementation guidance: 2.1 API scoping, 2.2 Path A, 2.3 Path B, 2.4 Path C
- `CLAUDE.md` Data sources — rib.gg / bo3.gg endpoint behavior + auth notes; Tesseract availability for OCR; Path B baseline

### Requirements + decision log
- `.planning/REQUIREMENTS.md` REQ-round-event-data-pipeline — Phase 2's only requirement; locks Path A/B/C semantics
- `.planning/intel/decisions.md` DEC-017 — phase decision gate; reference for the probe scope rationale
- `.planning/intel/decisions.md` DEC-015 — SQLite for dataset cache (locks the persistence layer for `round_events`)
- `.planning/intel/decisions.md` DEC-013 — empirical Bayes shrinkage with `SHRINK_PRIOR=15` (the audit-engine pattern Phase 1 inherited)
- `.planning/intel/decisions.md` DEC-007 — 5-level fallback chain hierarchy
- `.planning/intel/constraints.md` CON-round-events-schema — frozen schema for the SQLite `round_events` table

### Phase 1 artifacts (carry-forward — interface lock)
- `.planning/phases/01-core-pricing-engine/01-CONTEXT.md` D-06, D-07 — `round_conclusion` skeleton design + Phase-C compatibility commitment
- `.planning/phases/01-core-pricing-engine/01-VERIFICATION.md` — confirms Phase 1 interface state Phase 2 inherits
- `src/pricing/round_conclusion.py` — `_Cell`, `RoundConclusionLookup`, `RoundConclusionFn` Protocol; the public surface Phase 2 must NOT change
- `src/config/constants.py` — `SHRINK_PRIOR=15` (used by `_Cell.shrunk()`); `MIN_ROUNDS_FULL_WEIGHT` (relevant to side_baseline calibration)

### Reference / read-only
- `reference/theo_engine.py:84-129` — audit-engine empirical-Bayes shrinkage source pattern (DEC-013 / D-09 origin)
- `data/half_win_rates.json` — input for `side_baseline` derivation; schema generated by `thunderedge/worktrees/half-win-rate/`

### Third-party data sources (probe targets)
- rib.gg internal API — no public REST docs; auth via account credentials (CLAUDE.md: stash in `.env`)
- `FlynV/RIB.GG-Web-Scraper` — Node project, may need rib.gg auth pass-through
- `valorantr` R-package — CRAN-published rib.gg client; CLI invocation possible via `Rscript -e ...`
- bo3.gg API — slug endpoint only (`/api/v1/matches/{slug}`); list/filter endpoints broken per CLAUDE.md

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable assets
- **`src/pricing/round_conclusion.py:RoundConclusionLookup`** — frozen-dataclass skeleton with mutable `cells_*` dict fields. Phase 2 mutates the dict contents post-init via `lookup_obj.cells_full[key] = _Cell(...)` — the Phase 1 module docstring explicitly calls out this pattern as supported.
- **`src/pricing/round_conclusion.py:_Cell`** — `(n: int, p_hat: float, parent_p: float)` with `shrunk()` method. Phase 2 instantiates these from binned round_events.
- **`src/pricing/round_conclusion.py:RoundConclusionFn` Protocol** — Phase 2's `RoundConclusionLookup.lookup` continues to satisfy this Protocol after the body is rewritten with the fallback-chain walk.
- **`src/config/constants.py:SHRINK_PRIOR`** — `Final[float] = 15.0`; reused verbatim in `_Cell.shrunk()`.
- **`data/half_win_rates.json`** — pre-existing input for `side_baseline` derivation. No upstream regeneration needed for Phase 2 (regeneration is a `thunderedge/worktrees/half-win-rate/` task).
- **`reference/theo_engine.py:84-129`** — read-only audit-engine reference for the empirical-Bayes shrinkage formula. Salvage formulae but do NOT import — `reference/` is intentionally walled off.

### Established patterns
- **Public-interface freeze pattern** — Phase 1 ships skeletons with Protocol-typed call surfaces; later phases populate state without changing the surface. Phase 2 MUST honor this for `round_conclusion.py` (only `lookup` body, internal `_Cell` instances, and ONE additive classmethod `from_json` may change).
- **`mypy --strict` on `src/pricing/`** — new `from_json` method must satisfy strict typing including JSON parsing (use `TypedDict` for the JSON schema).
- **No magic numbers in business logic** — calibration knobs (e.g., minimum-cell-`n` cutoff, recency cutoff months) live in `src/config/constants.py` as `Final` values. The current `SHRINK_PRIOR=15` and `MIN_ROUNDS_FULL_WEIGHT` exemplify this.
- **Frozen + slots dataclasses with controlled mutation** — Phase 1's `RoundConclusionLookup` uses `frozen=True` to lock field references but allows dict-content mutation via `lookup_obj.cells_full[key] = ...`. Phase 2's calibrator uses this pattern verbatim.
- **Atomic per-task commits with `--no-verify`-aware tooling** — Phase 2 commits at probe-passes, schema-creates, calibrate-runs boundaries, not as one large dump.

### Integration points
- **Phase 4 quoting layer (downstream)** — engine init in `src/quoting/` (Phase 4) calls `RoundConclusionLookup.from_json("models/round_conclusion.json")` and injects into `LiveTheoEngine(half_rates, round_conclusion=...)`. If Path C is taken, `models/round_conclusion.json` does not exist; Phase 4's engine init falls back to `RoundConclusionLookup()` (empty, returns flat 0.5). The HARD CONTRACT in D-12 governs whether the Phase 4 directional-flip triggers move theo.
- **Phase 3 ingestion (parallel)** — Phase 3's live `MatchState` carries `numerical_diff`, `bomb_planted`, `side`, `econ_bucket`. Phase 2's `mid_round_states[]` carry-forward semantics MUST match Phase 3's runtime semantics so calibration and live evaluation share the same input distribution.
- **`scripts/` directory** — Phase 2 adds `probe_round_events.py` and `calibrate_round_conclusion.py`. Both write to `models/`, `data/`, and append to `.planning/phases/02-round-event-data/02-PROBE-LOG.md`.
- **`models/` directory** — currently empty per Phase 1's D-21 (DP table cache deferred to Phase 5). Phase 2 introduces the first model artifact: `round_conclusion.json`.

</code_context>

<specifics>
## Specific Ideas

- **rib.gg auth pattern** — CLAUDE.md `Kalshi API v2` row sets the precedent: keys in `.env`, surface in `src/` only via a config wrapper. The probe should follow the same pattern (e.g., `RIBGG_BEARER` or `RIBGG_SESSION_COOKIE`) and skip-if-unset for unauthenticated reproducibility.
- **`PROBE-LOG.md` as a verification artifact** — the must-have #1 in ROADMAP.md §2 says the path decision is "recorded with evidence in the run log." `02-PROBE-LOG.md` IS that run log; treat it as a first-class deliverable on par with VERIFICATION.md. Format: per-source attempt with status, sample row, acceptance evaluation, and final path decision at the bottom.
- **Hand-written design docs as authoritative** — per PROJECT.md "Source-of-truth docs" section, `prd.md`, `roadmap.md`, and `CLAUDE.md` at the repo root remain authoritative; `.planning/` artifacts are derived. When Phase 2 surfaces a new design tension (e.g., "the `mid_round_states[]` synthetic-heartbeat decision implies Phase 3 must use the same carry-forward semantics"), update `prd.md` / `roadmap.md` rather than letting the `.planning/` artifact drift independently.
- **Frozen schema discipline** — `CON-round-events-schema` is locked (`(match_id, map_num, round_num, ts_round_start, ts_first_kill, ts_bomb_plant, ts_round_end, mid_round_states[])`). The 8 columns are the lock; the JSON shape inside `mid_round_states[]` (Area B's D-06 / D-07) is what Phase 2 picks. Do not add or remove columns at the row level without an ADR-style update.

</specifics>

<deferred>
## Deferred Ideas

- **Recency-weighted calibration** — current D-13 / D-14 weights every match equally regardless of date. If Phase 5's Brier window flags meta drift, add an exponential-decay weight (e.g., `w = exp(-age_months / 6)`). Phase 5/7 work.
- **Automated weekly recalibration via CI** — D-16 keeps recalibration manual. If operationally annoying after a few months of live trading, schedule via GitHub Actions or a Hetzner-side cron. Phase 7.
- **Per-match incremental cell updates** — append-after-each-match pattern. Risks instability between matches the bot is trading; better as Phase 7.
- **Wider mid_round_states snapshot fields** — `ult_count`, `players_alive`, `time_left_s`. Deferred to Phase 5 if calibration coverage at the lookup-aligned 4-field level proves insufficient.
- **Logistic regression / GBT calibration alternatives** — rejected for v1 (D-13). Revisit only if empirical Bayes proves miscalibrated under live trading (Phase 5 finding).
- **OCR auto-validation against known rib.gg data** — if both Path A and Path B run (e.g., spot-check Path B labels against a small Path A subset), it would tighten OCR confidence. Phase 5 enhancement.
- **Per-half pistol-winner extension to `pistol_winner_a`** — `dp.py:33-47` documents this as a Phase 2 follow-up but only if round_events ingestion organically surfaces second-half pistol outcomes; otherwise it remains a separate ticket. Re-evaluate during planning.

</deferred>

---

*Phase: 02-round-event-data*
*Context gathered: 2026-04-30*
