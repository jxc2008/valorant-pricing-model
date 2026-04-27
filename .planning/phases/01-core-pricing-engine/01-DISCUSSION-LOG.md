# Phase 1: Core pricing engine — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-27
**Phase:** 1-core-pricing-engine
**Areas discussed:** MatchState scope, Round-conclusion placeholder, Confidence formula, Economy-memory state encoding

---

## MatchState scope (Phase 1 ↔ Phase 3 seam)

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal stub | Phase 1 ships a small `MatchState` with only the fields `live_theo` reads. Phase 3 *replaces* this with its full dataclass and `live_theo` is updated to read the new fields. Cleaner Phase 1 boundary; one refactor at the seam. | ✓ |
| Full Phase 3 spec | Phase 1 defines the full Phase 3 `MatchState` (REQ-match-state-engine: bomb_planted, players_alive, econ_a/b, ults, time_left_s, seq_id, etc.) with stub population. No refactor at the seam, but Phase 1 ships dead fields. | |
| Protocol/typing.Protocol | Phase 1 defines a `MatchStateProtocol` (structural typing). Phase 3 implements a concrete `MatchState` dataclass that satisfies the protocol. | |

**User's choice:** Minimal stub.
**Follow-up:** Field set narrowed to **pricing-only** (D-02): `match_id, map_pool, map_idx, a_map_score, b_map_score, a_round, b_round, side_orient, pistol_winner_a, numerical_diff, bomb_planted, side, econ_bucket`. Explicitly dropped: `seq_id`, `last_updated_ts`, `players_alive`, `ults`, `time_left_s` — those are Phase 3 ingestion fields.
**Rationale:** Smallest surface that makes `live_theo` callable end-to-end without polluting Phase 1 with fields it can't populate.

---

## Round-conclusion placeholder (Phase 1 ↔ Phase 2 seam)

| Option | Description | Selected |
|--------|-------------|----------|
| Flat 0.5 | Path-C compatible. `round_conclusion(state) → 0.5` regardless of inputs until Phase 2 calibrates cells. Phase 4 ships independently of DEC-017's path choice. | ✓ |
| Side baseline from `half_win_rates.json` | Use the bottom-of-fallback-chain side baseline from offline data until Phase 2 calibrates richer cells. Non-trivial mid-round signal pre-Phase-2; can be misleading mid-round when 4v5 / post-plant state "looks" typical. | |
| Raise NotImplementedError | Force Phase 4 to NOT call `round_conclusion` until Phase 2 lands. Makes the data dependency explicit; blocks Phase 4 entirely on Phase 2. | |

**User's choice:** Flat 0.5.
**Rationale:** Path-C compatibility was the deciding factor — Phase 4 must be able to ship the quoting layer if DEC-017 picks Path C. The hierarchical-lookup fallback chain *structure* still ships in Phase 1 (D-07); only the cell *values* are Phase 2 work.

---

## Confidence formula

| Option | Description | Selected |
|--------|-------------|----------|
| Audit-engine `data_w` (per-current-map) | Min over both teams' coverage on the *currently active* map only. Familiar; matches existing `confidence_label` semantics. | |
| Aggregated across map pool | Geometric or weighted mean of per-map data weights, weighted by remaining DP probability mass. Reflects total information content across the *series* rather than just the current map. | ✓ |
| Vega-derived | `confidence = 1 - clip(vega / VEGA_MAX, 0, 1)`. Cleaner downstream semantics for kill switches but loses the "how much data backed this" signal. | |

**User's choice:** Aggregated across map pool, **weighted by remaining DP probability mass** (per follow-up).
**Follow-up:** Equal-weight mean and geometric mean were the alternatives within "aggregated"; user chose DP-mass weighting because it's "most honest 'how confident *for this series state*' number". Implication accepted: confidence is state-dependent and changes round-to-round even with no new data.
**Per-map data_w formula:** Reuse the audit engine's `_data_weight(team_a, team_b, map_name)` verbatim (D-09).

---

## Economy-memory state encoding

| Option | Description | Selected |
|--------|-------------|----------|
| `won_pistol_a: Optional[bool]` | Single field per map; smallest possible state expansion (~2x cache); minimal modeling complexity. | |
| `last_round_winner: Optional[int]` (0/1/None) | Generic 'who won the most recent round'. Slightly larger cache (~3x); more general but most rounds (4-12, 16-24) ignore it. | |
| Full econ bucket per side | Carry `econ_a, econ_b ∈ {full, semi-buy, semi-eco, eco}`. Most expressive; matches `match_round_data` taxonomy. ~16x state expansion, requires modeling credit dynamics inside the DP. | ✗ (initially picked, then deferred after scope check) |

**User's initial choice:** Full econ buckets.
**Follow-up scope check:** Claude flagged the 16x state expansion and that this exceeds roadmap §1.3 wording ("small economy memory"). User reconsidered with three options: keep full buckets and model credit-flow now, compromise to `pistol_winner_a + post-pistol-state`, or defer full buckets to Phase 5 entirely.
**Final choice:** **Defer full buckets to Phase 5; ship pistol-only Phase 1.**
**Implementation:** `BO3State` extends roadmap §1.1's tuple with **only** `pistol_winner_a: Optional[bool]` per map. Pistol/anti-eco probabilities apply to rounds {1, 2, 3, 13, 14, 15} only; rounds {4-12, 16-24} use the gunround half-win-rate baseline. Cache size grows ~2x.
**Rationale:** Honors roadmap §1.3 literally. Captures the high-leverage pistol/anti-eco accuracy gain without committing to credit-flow modeling that's better calibrated against real `match_round_data` from Phase 2.

---

## Claude's Discretion

- Bayesian-shrinkage formula inside `round_conclusion.py` (cell-to-parent shrink weights). Phase 2 will calibrate; Phase 1 just needs a defensible placeholder formula. Suggested reusing `SHRINK_PRIOR=15.0` from `src/config/constants.py`.
- The `Optional[bool]` semantics of `pistol_winner_a` per map: pre-pistol = `None`, after pistol = `True/False`. Whether to surface this as a per-map dict, list, or per-`MatchState` field is the planner's call.
- DP cache strategy (D-16): use `lru_cache` first; planner profiles end-to-end during Phase 1 and ships `models/dp_table.pkl` warm cache + mmap *only if* cold-path latency exceeds the 500 ms budget.

## Deferred Ideas

- **Full economy-bucket DP state** with deterministic credit-flow transitions — deferred to Phase 5 calibration once Phase 2's `match_round_data` is in hand.
- **`models/dp_table.pkl` warm cache + mmap** — deferred to Phase 1 only if profiling demands it; otherwise Phase 5/6 optimization.
- **Vega refinement** — DEC-018 picks variant (a); revisit Phase 5 per PRD §9 TBD #3.
- **Round-conclusion shrinkage formula calibration** — Phase 5 calibration loop refits parent-cell hierarchy and shrink weights against observed live Brier (REQ-calibration-loop).
