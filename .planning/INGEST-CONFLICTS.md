## Conflict Detection Report

Synthesized from 2 source docs (1 PRD, 1 SPEC) under precedence ordering `ADR > SPEC > PRD > DOC`. No ADRs in scope. No cycles in cross-ref graph (roadmap → prd; prd does not back-reference roadmap).

### BLOCKERS (0)

(none)

### WARNINGS (0)

(none — the one open warning was user-resolved during ingest; see INFO entry below)

### INFO (4)

[INFO] User-resolved (2026-04-27): kill-switch constant naming
  Original conflict:
    - source: roadmap.md §0.4 declares `KILL_SWITCH_STALENESS_S = 5.0`, `KILL_SWITCH_DEVIATION_C = 20`, `KILL_SWITCH_BRIER_BOUND = 0.30`, `KILL_SWITCH_BRIER_WINDOW = 50`
    - source: CLAUDE.md "Domain constants" block declared `KILL_STALENESS_S = 5.0`, `KILL_DEVIATION_C = 20`, `KILL_BRIER_BOUND = 0.30`, `KILL_BRIER_WINDOW = 50`
  Resolution: User picked `KILL_SWITCH_*` (roadmap.md prefix) as canonical. CLAUDE.md was updated to match during ingest. Locked in `intel/constraints.md / CON-domain-constants-baseline`. Phase 0 `src/config/constants.py` MUST use `KILL_SWITCH_*`.


[INFO] Auto-resolved: SPEC operationalization of OT policy reconciled with PRD non-goal phrasing
  Note: prd.md §3 lists "OT modeling (excluded everywhere per existing repo convention)" as a non-goal. prd.md §12.2 #3 and roadmap.md §1.4 prescribe an explicit hard-stop at `total = 24` with a documented OT-as-coinflip leaf (`0.5 × value(after_a_OT_win) + 0.5 × value(after_b_OT_win)` at the 12-12 boundary, OT continues with `p = 0.5` per round until win-by-2).
  Resolution: These are not contradictory once parsed precisely. PRD §3's "no OT modeling" means "we do not attempt to *predict OT outcomes* with a calibrated model"; PRD §12.2 #3 and roadmap §1.4 enforce an *explicit, documented* coinflip leaf rather than letting the DP silently iterate past round 24 with `p = 0.5` (which was the audited engine's bug). The operational rule (DEC-009 / REQ-ot-handling / CON-ot-hard-stop) takes the explicit-hard-stop framing. PRD §3 wording remains valid as a *modeling-effort* non-goal.
  Source-of-truth ordering applied: SPEC (roadmap §1.4) refines PRD §3's intent without contradicting PRD §12.2 #3. Recorded for transparency.

[INFO] Auto-resolved: SPEC picks Vega computation variant (a) of three PRD-listed alternatives
  Note: prd.md §9 TBD #3 lists three defensible vega definitions: (a) variance under round-outcome distribution only, (b) variance including ingestion-noise term, (c) bootstrap over recent calibration error — and defers the choice to "phase 1". roadmap.md §1.6 commits to variant (a): `vega = round_p × (theo_after_a_win − theo)² + (1−round_p) × (theo_after_b_win − theo)²`, with refinement deferred to Phase 5.
  Resolution: SPEC > PRD on the same scope ("vega formula"); SPEC's choice stands. Recorded as DEC-018 / REQ-vega-output. PRD §9 TBD #3 should be considered superseded by roadmap §1.6 for Phase 1 purposes; revisit in Phase 5 calibration.

[INFO] Auto-resolved: SPEC chooses backtest fidelity option (a) of two PRD-listed alternatives
  Note: prd.md §9 TBD #4 lists two backtest options: (a) skip order-fill backtest and rely on paper trading, (b) build synthetic counterparty quoting at vig-removed market price. roadmap.md §5.2 commits to (a) — "Option (a) is faster and more honest." Model-only Brier validation still happens (REQ-backtest); the *order-fill* backtest is what's skipped.
  Resolution: SPEC > PRD on the same scope ("backtest scope"). Recorded as DEC-020.
