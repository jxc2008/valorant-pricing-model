# Phase 2: Round-event data — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-30
**Phase:** 02-round-event-data
**Areas discussed:** Probe acceptance & data-source priority, mid_round_states[] shape, Path B/C escalation policy, Calibration method

---

## Probe acceptance & data-source priority

### Q1: Source priority

| Option | Description | Selected |
|--------|-------------|----------|
| rib.gg → valorantr → scraper → bo3.gg | Try rib.gg internal API first; fall back through valorantr R-package, FlynV scraper, bo3.gg slug endpoint | ✓ |
| rib.gg only | Only attempt rib.gg; fail Path A on its failure | |
| valorantr/scraper first, rib.gg last | Try third-party packages first to avoid auth friction | |

### Q2: Acceptance bar

| Option | Description | Selected |
|--------|-------------|----------|
| Per-round timestamps + 1 mid-round event | Looser bar — maximizes Path A acceptance | ✓ |
| All 4 schema timestamps + numerical_diff snapshots | Strict bar — every round, every field reconstructable | |
| Bare round outcomes only | Just (winner, ts_round_start, ts_round_end) — no mid-round signal | |

### Q3: Match-coverage bar

| Option | Description | Selected |
|--------|-------------|----------|
| 500+ matches, last 12 months, tier-1+2 | ~37,500 rounds; relies on cells_no_econ/cells_no_map fallback | |
| 1000+ matches, last 18 months, tier-1 only | ~75,000 rounds; cells_full populated for popular combos | ✓ |
| 300+ matches, last 6 months, any tier | ~22,500 rounds; mostly cells_no_map answers | |

**Notes:** User initially asked for a layman explanation of "match-coverage bar." Re-asked after I broke down the 5-D `cells_full` grid (10×2×2×4×7 = 1,120 cells) and the rounds-per-cell math. User then chose the 1000+ tier-1 path — prioritizing signal density at `cells_full` over breadth, accepting narrower 30-team coverage and the 18-month patch-meta trade-off.

### Q4: Probe time cap

| Option | Description | Selected |
|--------|-------------|----------|
| 3 days (matches DEC-017) | Hard-stop matches the original DEC-017 estimate | |
| 1 week (more time to retry endpoints) | Allows debugging auth, retrying rate-limited endpoints | ✓ |
| No cap (run until decisive) | Open-ended — risks scope creep | |

**Notes:** User's choice to extend the 3-day cap to 1 week is documented in CONTEXT.md D-04 as a deliberate deviation from DEC-017 to allow auth/endpoint debug time.

---

## mid_round_states[] shape

### Q1: Sampling strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Event-driven only | List of (kill/plant/death event, post-state) per event | |
| Time-sampled (1Hz) | Fixed-cadence snapshot per second of round | |
| Hybrid (events + 5s heartbeats) | Events + synthetic 5s heartbeats reconstructed via carry-forward | ✓ |

### Q2: Per-entry payload fields

| Option | Description | Selected |
|--------|-------------|----------|
| Lookup-aligned (4 fields) | numerical_diff, bomb_planted, side, econ_bucket only | ✓ |
| Wider snapshot (+ ult_count, players_alive, time_left) | Future-proofs Phase 5 calibration | |
| Raw event payload + computed fields | Stores source API raw blob alongside computed | |

### Q3: numerical_diff derivation between events

| Option | Description | Selected |
|--------|-------------|----------|
| Carry-forward from last event | Deterministic, matches Phase 3 live ingestion semantics | ✓ |
| Linear interpolation | Smooth but nonsensical for discrete -5..+5 count | |
| Step-function with event timestamps | Same outcome as carry-forward, different abstraction | |

### Q4: Storage ordering

| Option | Description | Selected |
|--------|-------------|----------|
| Time-ordered list (sorted by t_offset asc) | Standard JSON array column in SQLite | ✓ |
| Set keyed on (t_offset, event_id) | Deduplication-friendly but adds complexity | |

---

## Path B/C escalation policy

### Q1: If Path A fails, default escalation

| Option | Description | Selected |
|--------|-------------|----------|
| Jump to Path C (defer, ship flat 0.5) | Skips Path B's 2-week OCR cost | |
| Commit to Path B (2-week OCR labeling) | Higher mid-round signal quality justifies calendar cost | ✓ |
| Ask before deciding (manual gate) | Probe pauses, user picks B vs C with full data | |

**Notes:** Significant trade-off. User chose to commit upfront to Path B as the default escalation — judges mid-round signal quality worth the calendar cost. This means if Path A fails, the planner can begin Path B without re-prompting.

### Q2: Path C output

| Option | Description | Selected |
|--------|-------------|----------|
| Flat 0.5 (matches Phase 1 D-06 exactly) | Zero code changes; skeleton ships as-is | ✓ |
| side_baseline only (atk/def half-rates) | Slightly more signal — captures side asymmetry | |
| Half-rate-derived per-map cells_minimal | Looks calibrated but isn't — false confidence risk | |

### Q3: Partial Path A success policy

| Option | Description | Selected |
|--------|-------------|----------|
| Treat as pass; populate cells_no_econ + cells_no_map only | Use what data exists; document gap in PROBE-LOG.md | ✓ |
| Treat as fail; escalate per the policy | Strict acceptance bar; rejects partial signal | |
| Recompute coverage bar with what's available | Risks moving the goalposts | |

### Q4: Phase 4 contract on Path C

| Option | Description | Selected |
|--------|-------------|----------|
| Hard contract: Path C ⇒ Phase 4 mid-round triggers don't move theo | Codify in CONTEXT.md as Phase 2 ↔ Phase 4 seam | ✓ |
| Soft contract: document but don't enforce | Looser coupling, parallel-models bug risk | |

---

## Calibration method

### Q1: Calibration approach

| Option | Description | Selected |
|--------|-------------|----------|
| Empirical Bayes shrinkage (audit pattern, SHRINK_PRIOR=15) | Matches Phase 1 _Cell skeleton verbatim | ✓ |
| Logistic regression with L2 | More flexible but opaquer; sklearn dep | |
| Gradient-boosted trees | Strongest predictive perf but heavy dep, lost interpretability | |

### Q2: parent_p computation

| Option | Description | Selected |
|--------|-------------|----------|
| Recursive walk up the chain (deepest first) | Bottom-up pass; each level uses level above as prior | ✓ |
| Fixed at side_baseline | Single global anchor; loses chain hierarchy | |
| Fixed at 0.5 (no parent guidance) | Pure ratio-with-prior; ignores fallback chain motivation | |

### Q3: Persistence

| Option | Description | Selected |
|--------|-------------|----------|
| models/round_conclusion.json | Diff-friendly text JSON; ~100KB | ✓ |
| models/round_conclusion.pkl | Binary pickle; not reviewable; security warnings | |
| Inline in src/pricing/round_conclusion.py | Code-generated dict committed; bloats source | |

### Q4: Recalibration cadence

| Option | Description | Selected |
|--------|-------------|----------|
| Manual: one-off Phase 2 run, recompute on demand | Idempotent script; rerun after meta shift | ✓ |
| Automated: weekly scheduled rerun | Catches drift fast; needs CI infra not yet built | |
| Per-match incremental update | Real-time but instability risk between trading matches | |

---

## Claude's Discretion

The following sub-decisions were left to the researcher / planner per CONTEXT.md:

- Probe failure logging shape (`PROBE-LOG.md` field names, JSONL vs markdown)
- OCR tooling for Path B (Tesseract / EasyOCR / PaddleOCR — Tesseract default per CLAUDE.md system PATH)
- `side_baseline` exact statistic from `half_win_rates.json` (after planner reads the file's actual schema)
- `.env` variable naming for rib.gg auth (follow Kalshi pattern)
- Auto-trigger vs re-confirm prompt at Path A → Path B transition (default auto-trigger per D-10)

---

## Deferred Ideas

Surfaced during discussion or in the area trade-offs but explicitly out of scope for Phase 2:

- Recency-weighted calibration (Phase 5/7 if Brier flags meta drift)
- Automated weekly recalibration via CI (Phase 7)
- Per-match incremental cell updates (Phase 7)
- Wider mid_round_states snapshot fields: `ult_count`, `players_alive`, `time_left_s` (Phase 5 if needed)
- Logistic regression / GBT calibration alternatives (revisit if empirical Bayes miscalibrated)
- OCR auto-validation against rib.gg subset cross-reference (Phase 5 enhancement if both paths run)
- Per-half pistol-winner extension (`pistol_winner_a` for rounds 14/15) — separate ticket per `dp.py:33-47`
