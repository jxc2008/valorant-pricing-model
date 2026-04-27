# Phase 1: Core pricing engine — Context

**Gathered:** 2026-04-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the single canonical `live_theo(state) → TheoOutput(theo_series, theo_map, vega, confidence)` math layer with **no data dependencies**. Between-round live pricing must work end-to-end against synthetic state. The four documented audit-engine bugs are fixed here:

1. Arithmetic-mean round blend → Bradley-Terry (DEC-003)
2. Silent OT iteration past round 24 → explicit hard-stop with coinflip leaf (DEC-009)
3. Constant `p1`/`p2` per half → pistol/anti-eco modeled separately (DEC-011)
4. Conviction clips `[0.05, 0.95]` and `[0.03, 0.97]` → unified `[0.01, 0.99]` (DEC-012)

**In scope:** `src/pricing/{dp,blend,round_types,round_conclusion,live_theo}.py` plus a Phase-1-stub `MatchState` dataclass. Property tests for DP value range, symmetric-input closed form, Bradley-Terry symmetry, and theo_series ↔ theo_map[] consistency.

**Out of scope (deferred to other phases):**
- Live ingestion / OCR / cross-source arbitration → Phase 3
- Round-conclusion *cell calibration* (skeleton only here, Phase 2 fills cells)
- Quoting / sizing / kill switches → Phase 4
- Backtest, paper trading, calibration loop → Phase 5

</domain>

<decisions>
## Implementation Decisions

### MatchState scope (Phase 1 ↔ Phase 3 seam)
- **D-01:** Phase 1 ships a **minimal stub `MatchState` dataclass** containing ONLY the fields `live_theo` reads. Phase 3 will *replace* this dataclass with its full ingestion-driven version (REQ-match-state-engine). The Phase 1 / Phase 3 seam absorbs one refactor, not Protocol/structural-typing — concrete dataclass is simpler for `mypy --strict`.
- **D-02:** Field set for the Phase 1 stub: `match_id, map_pool, map_idx, a_map_score, b_map_score, a_round, b_round, side_orient, pistol_winner_a (per-map dict), numerical_diff, bomb_planted, side, econ_bucket`. **No** `seq_id`, `last_updated_ts`, `players_alive`, `ults`, `time_left_s` — those land in Phase 3. Smallest surface that makes `live_theo` callable end-to-end.

### DP state representation (`BO3State` — DP cache key, separate from MatchState)
- **D-03:** `BO3State` extends roadmap §1.1's tuple with **only** `pistol_winner_a: Optional[bool]` per map. Deterministic credit-flow econ-bucket modeling is **deferred to Phase 5** (see Deferred Ideas) — the roadmap §1.3 wording "small economy memory" is honored literally.
- **D-04:** Pistol/anti-eco probability inputs apply ONLY to rounds {1, 2, 3, 13, 14, 15}. Rounds {4-12, 16-24} use the gunround half-win-rate baseline and ignore `pistol_winner_a` entirely. Cache size grows ~2x relative to a no-pistol-memory DP.
- **D-05:** OT-coinflip leaf at total=24 per DEC-009. The DP returns `0.5 × value(after_a_OT_win) + 0.5 × value(after_b_OT_win)` at the 12-12 boundary; OT play continues with `p=0.5`. Reading the roadmap §1.4 + DEC-009 together: the 12-12 leaf is computed (not flat 0.5) because each side of the leaf may have asymmetric downstream series outcomes (we may already be 1-0 in maps).

### Round-conclusion lookup placeholder (Phase 1 ↔ Phase 2 seam)
- **D-06:** Phase 1's `round_conclusion(state) → 0.5` is a **flat 0.5** on every cell miss until Phase 2 calibrates the lookup tables. **Path-C compatible** — Phase 4 can ship the quoting layer without waiting on Phase 2. No false signal from un-calibrated cells; mid-round vega will be flat between rounds until Phase 2 lands.
- **D-07:** The hierarchical fallback chain structure (DEC-007 / roadmap §1.5) **is** built in Phase 1 as the SHAPE of the lookup, even though all cells return 0.5. This means the function signature, fallback order `(numerical_diff, bomb, side, econ_bucket, map) → ... → side baseline`, and Bayesian-shrinkage scaffolding ship in Phase 1 — only the cell *values* are Phase-2 work. This avoids a Phase 2 refactor of the lookup interface.

### `confidence` semantics in `TheoOutput`
- **D-08:** `confidence ∈ [0, 1]` is a **per-pool aggregate weighted by remaining DP probability mass**. Concretely: for each map `m` in `map_pool`, compute `data_w(m)` (audit-engine-style min-over-teams data weight on map `m`), then weight by `P(map m is reached and decisive | current state)` from the DP. Maps that the series is unlikely to reach contribute less.
  - **Implication:** confidence is *state-dependent* and changes round-to-round even with no new data. Downstream Phase 4 kill-switch logic must accept that.
  - **Not picked:** simple equal-weight mean (less honest about which map is currently driving theo) and vega-derived confidence (loses the "how much data backs this" signal).
- **D-09:** Use the audit engine's `_data_weight` formula per map verbatim (DEC-013 / `reference/theo_engine.py:104-129`): `min(team_a_avg_rounds, team_b_avg_rounds) / MIN_ROUNDS_FULL_WEIGHT`, capped at 1.0. Bottlenecked by the weaker team's coverage on each map.

### `vega` — DEC-018 baseline form
- **D-10:** Use DEC-018's initial form verbatim: `vega = round_p × (theo_after_a_win − theo)² + (1−round_p) × (theo_after_b_win − theo)²`. Refinement is Phase 5 work. Phase 1 does **not** explore variance-of-future-rounds or bomb-plant-conditional vega — those are open TBDs in PROJECT.md.
- **D-11:** Vega is computed at every `live_theo` invocation, not gated to round boundaries — the function reflects whatever variance is implied by the current state. Mid-round events (bomb plant, numerical flip) update `round_p` via `round_conclusion`, which in turn moves vega; Phase 1 doesn't need to special-case mid-round vega.

### Single canonical entry point
- **D-12:** No reverse-compatibility shims for the audited engine's `series_theo` / `series_theo_no_sides` / `series_theo_from_map_probs` triplet. The entire pricing API surface for downstream phases is `live_theo(state: MatchState) → TheoOutput`. This is non-negotiable per DEC-010 / CON-single-canonical-live-theo / CLAUDE.md Critical Rule 1.

### Module decomposition within `src/pricing/`
- **D-13:** Five files, mirroring roadmap §1.1–1.6 verbatim:
  - `dp.py` — generalized BO3 DP (`series_value(state, round_p_fn)`)
  - `blend.py` — Bradley-Terry round blend
  - `round_types.py` — pistol/anti-eco probability inputs
  - `round_conclusion.py` — hierarchical-lookup skeleton (cells = 0.5 in Phase 1)
  - `live_theo.py` — `live_theo` + `TheoOutput` + the Phase 1 stub `MatchState`
- **D-14:** `MatchState` dataclass lives in `src/pricing/live_theo.py` for Phase 1 (the only consumer). When Phase 3 builds the full version, it will move to `src/state/match_state.py` and `live_theo.py` will import from there. Documenting this seam in CONTEXT.md so the Phase 3 planner knows where to look.

### Test scaffolding (Phase 5 owns the full coverage gate)
- **D-15:** Phase 1 ships *property tests* (REQ-unit-and-property-tests subset) for the four invariants in roadmap §1.1, §1.2, §5.1: DP value ∈ [0,1] for any reachable state; symmetric-inputs DP equals `p²(3-2p)` from `fair_value.py`; Bradley-Terry symmetry `round_p(a,b) == 1 − round_p(b,a)`; theo_series consistent with sum over `theo_map[]` outcomes. Phase 5's 80% coverage gate (now correctly scoped to `src/` per the Phase-0 fix WR-03) measures full-codebase coverage; Phase 1 isn't expected to hit 80% on its own.

### DP cache strategy (roadmap §1.1)
- **D-16:** Use `@functools.lru_cache(maxsize=None)` for in-process memoization. **Defer** the `models/dp_table.pkl` warm-cache + mmap step to Phase 1 *if and only if* in-process cache hit is fast enough; if profiling shows the cold path is too slow for the < 500 ms latency budget (REQ-end-to-end-latency), the pkl dump lands in Phase 1. Otherwise it's a Phase 5/6 optimization. Decision rule: planner profiles a synthetic match replay end-to-end during Phase 1 and picks one of the two paths.

### Claude's Discretion
- The Bayesian-shrinkage formula inside `round_conclusion.py` (cell-to-parent shrink weights) is open. Phase 2 will calibrate; Phase 1 just needs *some* defensible formula so the structure is testable. Suggest reusing `SHRINK_PRIOR=15.0` from `src/config/constants.py` consistently.
- The exact `Optional[bool]` semantics of `pistol_winner_a` per map: pre-pistol = `None`, after pistol = `True/False`. Whether to surface this as a per-map dict, list, or per-`MatchState` field is planner's call.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Locked decisions and requirements (project-level)
- `prd.md` (root) — full design doc, especially §2 (output contract), §6 (canonical entry point), §12.2 (four bugs being fixed), §12.3 (audited-engine triplet to NOT recreate)
- `roadmap.md` (root) — §1.1–1.6 implementation guidance for every module landing in Phase 1; §0.4 domain constants
- `CLAUDE.md` (root) — Critical Rules 1, 3, 5, 6 (single canonical `live_theo`; Bradley-Terry not arithmetic; OT hard-stop; clips `[0.01, 0.99]`); domain constants table
- `.planning/PROJECT.md` `<decisions>` blocks — DEC-002, DEC-003, DEC-007, DEC-009, DEC-010, DEC-011, DEC-012, DEC-013, DEC-017, DEC-018 are direct Phase 1 inputs
- `.planning/REQUIREMENTS.md` — REQ-bo3-dp-engine, REQ-bradley-terry-blend, REQ-pistol-anti-eco-modeling, REQ-ot-handling, REQ-round-conclusion-lookup, REQ-canonical-live-theo, REQ-theo-series-output, REQ-theo-map-output, REQ-confidence-output, REQ-vega-output, REQ-end-to-end-latency
- `.planning/intel/constraints.md` — CON-mypy-strict-pricing, CON-no-magic-numbers, CON-single-canonical-live-theo

### Phase-0 outputs (foundation)
- `src/config/constants.py` — `SHRINK_PRIOR=15.0`, `SIGNAL_SCALE=0.10`, `GUN_WIN_RATE=0.822`, `REGULATION_HALF=12`, `WIN_THRESHOLD=13`. **Never** inline these in Phase 1 business logic (Critical Rule 12 + CON-no-magic-numbers).
- `pyproject.toml` — `[tool.mypy.overrides]` enforces `--strict` on `src.pricing.*`. Every new file in `src/pricing/` must type-check.
- `tests/test_smoke.py`, `tests/config/test_constants.py`, `tests/test_main.py` — existing tests Phase 1 must not regress.

### Salvage from `reference/` (read-only)
- `reference/theo_engine.py` — DP skeleton salvage source per DEC-013. Adapt the structure of `_markov_map_win` (lines 168–206) but FIX the four bugs documented above. Do **not** copy `_round_win_prob` (line 146) — it uses the arithmetic-mean blend that DEC-003 replaces.
- `reference/fair_value.py` — closed-form `p²(3−2p)` for symmetric-input property tests (REQ-bo3-dp-engine acceptance criterion).
- `reference/odds_utils.py` — salvage as-is per DEC-013 (e.g., for cents↔probability conversions in Phase 4; not consumed by Phase 1 directly).

### Data inputs (offline, computed upstream)
- `data/half_win_rates.json` — pre-match per-team/map/side rates. Schema: `team_map_side`, `league_map_side`, `overall_avg`. Generated by `thunderedge/worktrees/half-win-rate/`. Phase 1 reads this; doesn't recompute.

### Out-of-scope but worth knowing about for the seam
- `.planning/phases/00-foundation/00-VERIFICATION.md` — confirms toolchain green; lists the WR-03 coverage scope fix that affects how Phase 1's Phase-5 coverage gate will measure.
- DEC-017 "Path A / Path B / Path C" — Phase 2's API decision gates *cell calibration* but not the lookup *skeleton*. Phase 1's flat-0.5 placeholder is path-neutral.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/config/constants.py` — every threshold Phase 1 needs (`SHRINK_PRIOR`, `GUN_WIN_RATE`, `REGULATION_HALF`, `WIN_THRESHOLD`, `SIGNAL_SCALE`) is already exported with `Final[...]` typing. No need to redefine.
- `reference/theo_engine.py:168-206` — DP loop *structure* (bottom-up over `(a, b)` states with absorbing terminals) is sound. Adapt this skeleton, fix the four bugs, generalize to `BO3State` not `(a, b)` only.
- `reference/fair_value.py` — closed-form symmetric-input DP value used directly in property tests. Import as test fixture.

### Established Patterns
- **`mypy --strict` on `src/pricing/`** (CON-mypy-strict-pricing). Every function and dataclass in this phase needs full annotations. Use `typing.Final` for module-level constants and `@dataclass(frozen=True)` for state types so they're hashable for `lru_cache`.
- **`Final[...]`-typed module-level constants** (Phase 0 convention from `src/config/constants.py`). New thresholds, if any, go in `constants.py` not Phase 1 modules.
- **Test layout mirrors source** (`tests/config/test_constants.py` matches `src/config/constants.py`). Phase 1 will add `tests/pricing/test_dp.py`, `tests/pricing/test_blend.py`, etc.
- **Atomic commits per task** (Phase 0 pattern: `feat(00-XX): ...`, `test(00-XX): ...`, `docs(00-XX): ...`). Phase 1 plans should follow `feat(01-XX): ...` etc.

### Integration Points
- **`live_theo` is the only public pricing API.** Downstream Phase 4 quoting layer imports `from src.pricing.live_theo import live_theo, TheoOutput`. No private pricing functions get exposed across the package boundary.
- **`MatchState` is the input contract.** Phase 1 owns the stub; Phase 3 replaces it. Document the field set in `live_theo.py` so the Phase 3 planner sees a clear delta.
- **`round_p_fn: Callable[[BO3State], float]`** (roadmap §1.1) is the DP's injection point for round-type logic — this lets `round_types.py` (which knows about pistols) feed into `dp.py` (which doesn't). Pure-function seam; no circular imports.
- **`round_conclusion(state) → float`** is what `live_theo` calls for *mid-round* updates (vs `round_p_fn` for between-round DP recursion). Two different functions because the DP runs once per round but live_theo updates can happen any time mid-round when bomb plants / numerical flips fire.

</code_context>

<specifics>
## Specific Ideas

- The user wants **Path-C compatibility preserved**. Phase 1's flat-0.5 placeholder for `round_conclusion` is the reason: if DEC-017 lands on Path C ("defer round-conc model"), Phase 4 can ship the quoting layer immediately because Phase 1's placeholder is structurally complete and semantically neutral.
- The user wants **confidence to reflect series-level information content** rather than just current-map data weight. The DP-mass weighting was explicitly chosen over the simpler audit-engine form for this reason. Phase 4 kill-switch design must accept that confidence will fluctuate round-to-round even without new data.
- The user explicitly **deferred deterministic credit-flow econ-bucket modeling** to Phase 5 calibration after seeing the 16x state-space cost. Phase 1's `pistol_winner_a` is a deliberate compromise to honor roadmap §1.3 literally.

</specifics>

<deferred>
## Deferred Ideas

### Full economy-bucket DP state (deferred to Phase 5 calibration)
Carry `econ_a, econ_b ∈ {full, semi-buy, semi-eco, eco}` per side as DP state, with deterministic credit-flow transition rules (winners reset to full, losers cascade). Cost: ~16x state expansion, requires modeling credit dynamics inside the DP. Reason for deferral: Phase 1's pistol-only modeling captures most of the accuracy gain (DEC-011 "single largest accuracy gain" applies primarily to rounds 1, 2, 3, 13, 14, 15); the full bucket model is a Phase 5 calibration enhancement once `match_round_data` from Phase 2 is in hand.

### `models/dp_table.pkl` warm cache + mmap (decision deferred until Phase 1 profiling)
Roadmap §1.1 mentions ~10MB pkl dump + mmap on load. Per D-16, ship this in Phase 1 *only if* `lru_cache` cold-path latency exceeds the < 500 ms budget. Otherwise it's a Phase 5/6 optimization. Planner profiles end-to-end during Phase 1 to decide.

### Vega refinement (PRD §9 TBD #3 / DEC-018 / Phase 5)
DEC-018 picks variant (a) for vega initially. PRD §9 lists three defensible alternatives. Revisit after 20+ live matches' worth of observed predictive variance.

### Variance of round_conclusion outputs (Phase 5 calibration loop)
Once Phase 2 calibrates real cell values, the round-conclusion shrinkage formula and the parent-cell hierarchy can be re-fit empirically per REQ-calibration-loop. Phase 1 ships placeholder shrink weights using `SHRINK_PRIOR=15.0`.

### Reviewed Todos (not folded)
None — no pending todos with `area: pricing` or matching this phase's scope. The single STATE.md active todo (`Phase 0 — first executable phase`) was resolved by Phase 0 itself.

</deferred>

---

*Phase: 1-core-pricing-engine*
*Context gathered: 2026-04-27*
