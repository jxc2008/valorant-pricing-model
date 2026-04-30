---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_phase: 01
current_plan: 1
status: ready_to_plan
stopped_at: End of Phase 0 Wave 1. SUMMARY at `.planning/phases/00-foundation/00-01-project-structure-and-tooling-SUMMARY.md`.
last_updated: "2026-04-29T20:30:39.944Z"
last_activity: 2026-04-29
progress:
  total_phases: 8
  completed_phases: 2
  total_plans: 10
  completed_plans: 9
  percent: 25
---

# STATE — Valorant Live Pricing Model

**Project:** Valorant Live Pricing Model
**Last activity:** 2026-04-30
**Last activity description:** Phase 01 execution started

---

## Project Reference

- **Core value:** Live pricing engine for Valorant BO3 series + per-map Kalshi markets. Re-prices the series at any moment during a live match, hybrid market-maker / directional taker, fast enough to capture edge or — at minimum — avoid being adversely selected.
- **Owner:** jxc2008@nyu.edu
- **Status:** Ready to plan
- **Source-of-truth design docs:** `prd.md`, `roadmap.md`, `CLAUDE.md` at repo root.
- **Locked decisions:** 22 (DEC-001 through DEC-022) — see `.planning/PROJECT.md` `<decisions>` blocks.

## Current Position

Phase: 01 (core-pricing-engine) — EXECUTING
Plan: 1 of 7

- **Current phase:** 2
- **Current plan:** Not started
- **Status:** Wave 1 (00-01) complete; Wave 2 ready
- **Progress:** 0/8 phases complete (0%); 1/3 Phase 0 plans complete (33%)

```
Phase 0  [###       ] In progress (1/3 plans)
Phase 1  [          ] Pending
Phase 2  [          ] Pending
Phase 3  [          ] Pending
Phase 4  [          ] Pending
Phase 5  [          ] Pending
Phase 6  [          ] Pending
Phase 7  [          ] Pending
```

## Phase Status

| Phase | Status | Plans | Completed |
|---|---|---|---|
| 0 — Foundation | In progress (Wave 1 done) | 3 (00-01, 00-02, 00-03) | 1 (00-01) |
| 1 — Core pricing engine | Pending | none | — |
| 2 — Round-event data | Pending | none | — |
| 3 — Live ingestion layer | Pending | none | — |
| 4 — Quoting layer | Pending | none | — |
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
| Coverage on `src/pricing/` | ≥ 80% | not yet measured |
| Docker image size | < 500 MB | not yet built |

## Accumulated Context

### Recent decisions (cross-phase)

22 locked decisions inherited from `prd.md` + `roadmap.md` via synthesizer. See `.planning/PROJECT.md` for full text. Highlights:

- DEC-001 — hybrid trading mode (event-trigger with vega override)
- DEC-002 — single DP for BO3 series + per-map (no parallel models)
- DEC-009 — OT explicit hard-stop at total=24 with documented coinflip leaf (resolves audit-engine bug)
- DEC-010 — single canonical `live_theo` entry point (no triplet sprawl)
- DEC-017 — Phase-2 API decision gate (Path A / Path B / Path C)
- DEC-022 — dry-run by default; live trading requires explicit `--live` flag

### Plan 00-01 outcomes (2026-04-27)

- uv 0.11.8 installed via `pip install --user uv` (host-level, one-time setup; uv on PATH at `%APPDATA%\Roaming\Python\Python311\Scripts\`).
- `uv.lock` committed (uv application-project convention) — Phase 6 Docker build will inherit deterministic dep resolution.
- `[tool.mypy.overrides]` strict mode scoped to `src.pricing.*` only (CON-mypy-strict-pricing); other layers gradual.
- README.md stub created (Rule 3 deviation — required by hatchling readme metadata to make `uv sync` succeed).
- Resolved versions: pytest 9.0.3, pytest-cov 7.1.0, hypothesis 6.152.4, ruff 0.15.12, mypy 1.20.2.
- All four toolchain commands exit 0: `uv sync`, `uv run mypy --strict src/pricing/`, `uv run ruff check .`, `uv run pytest --collect-only`.

### Active todos

- [x] Plan 00-01 — project structure + tooling (uv + pyproject.toml + Python 3.11 + ruff + mypy --strict on src/pricing/)
- [ ] Plan 00-02 — domain constants (`src/config/constants.py`)
- [ ] Plan 00-03 — dry-run-default entry point

### Blockers

None.

### Open TBDs (intentional, deferred per PRD §9)

1. Bankroll size and `PER_MARKET_CAP_FRAC` — operational, depends on capital allocation.
2. Threshold values (`VEGA_DIRECTIONAL_THRESHOLD`, kill-switch constants) — initial guesses, re-tune in Phase 5 after 20+ live matches.
3. Vega formula refinement — DEC-018 picks variant (a) initially; revisit in Phase 5.
4. Backtest fidelity — DEC-020 skips order-fill backtest in favor of paper trading; reconsider if Kalshi exposes historical order-book data.

## Session Continuity

- **Last session ended:** 2026-04-27 — Plan 00-01 (project structure + tooling) complete. Two task commits: `91a6419` (chore: pyproject.toml + uv toolchain), `83b00b0` (feat: convert src/* to real Python packages + pytest sentinel).
- **Stopped at:** End of Phase 0 Wave 1. SUMMARY at `.planning/phases/00-foundation/00-01-project-structure-and-tooling-SUMMARY.md`.
- **Next action:** Execute Phase 0 Wave 2 — plans 00-02 (domain constants in `src/config/constants.py`) and 00-03 (dry-run-default entry point) can run in parallel. After Phase 0 completes, Phases 1, 2, 3 unblock for parallel planning; the discussion phase is most valuable for Phase 2 (DEC-017 path-decision gate) and Phase 3 (ingestion architecture).
- **Cross-phase context lookup:** `.planning/PROJECT.md` `<decisions>` blocks expose all 22 DECs to future plan-phase agents. Constraint detail in `.planning/intel/constraints.md`.
