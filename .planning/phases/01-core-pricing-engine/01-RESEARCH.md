# Phase 1: Core pricing engine — Research

**Researched:** 2026-04-27
**Domain:** Numerical pricing math (Markov DP, Bradley-Terry blend, hierarchical lookup, vega/confidence aggregation) — pure-Python, no external deps
**Confidence:** HIGH (every recommendation traces to a locked decision, the salvage source, or a verified Phase 0 artifact; no library or framework choices needed)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**MatchState scope (Phase 1 ↔ Phase 3 seam)**
- **D-01:** Phase 1 ships a **minimal stub `MatchState` dataclass** containing ONLY the fields `live_theo` reads. Phase 3 will *replace* this dataclass with its full ingestion-driven version (REQ-match-state-engine). The Phase 1 / Phase 3 seam absorbs one refactor, not Protocol/structural-typing — concrete dataclass is simpler for `mypy --strict`.
- **D-02:** Field set for the Phase 1 stub: `match_id, map_pool, map_idx, a_map_score, b_map_score, a_round, b_round, side_orient, pistol_winner_a (per-map dict), numerical_diff, bomb_planted, side, econ_bucket`. **No** `seq_id, last_updated_ts, players_alive, ults, time_left_s` — those land in Phase 3. Smallest surface that makes `live_theo` callable end-to-end.

**DP state representation (`BO3State` — DP cache key, separate from MatchState)**
- **D-03:** `BO3State` extends roadmap §1.1's tuple with **only** `pistol_winner_a: Optional[bool]` per map. Deterministic credit-flow econ-bucket modeling is **deferred to Phase 5** (see Deferred Ideas) — the roadmap §1.3 wording "small economy memory" is honored literally.
- **D-04:** Pistol/anti-eco probability inputs apply ONLY to rounds {1, 2, 3, 13, 14, 15}. Rounds {4-12, 16-24} use the gunround half-win-rate baseline and ignore `pistol_winner_a` entirely. Cache size grows ~2x relative to a no-pistol-memory DP.
- **D-05:** OT-coinflip leaf at total=24 per DEC-009. The DP returns `0.5 × value(after_a_OT_win) + 0.5 × value(after_b_OT_win)` at the 12-12 boundary; OT play continues with `p=0.5`. Reading roadmap §1.4 + DEC-009 together: the 12-12 leaf is computed (not flat 0.5) because each side of the leaf may have asymmetric downstream series outcomes (we may already be 1-0 in maps).

**Round-conclusion lookup placeholder (Phase 1 ↔ Phase 2 seam)**
- **D-06:** Phase 1's `round_conclusion(state) → 0.5` is a **flat 0.5** on every cell miss until Phase 2 calibrates the lookup tables. **Path-C compatible** — Phase 4 can ship the quoting layer without waiting on Phase 2.
- **D-07:** The hierarchical fallback chain structure (DEC-007 / roadmap §1.5) **is** built in Phase 1 as the SHAPE of the lookup, even though all cells return 0.5. Function signature, fallback order `(numerical_diff, bomb, side, econ_bucket, map) → ... → side baseline`, and Bayesian-shrinkage scaffolding ship in Phase 1 — only the cell *values* are Phase-2 work.

**`confidence` semantics in `TheoOutput`**
- **D-08:** `confidence ∈ [0, 1]` is a **per-pool aggregate weighted by remaining DP probability mass**. For each map `m` in `map_pool`: compute `data_w(m)` (audit-engine-style min-over-teams data weight on map `m`), then weight by `P(map m is reached and decisive | current state)` from the DP. Maps unlikely to be reached contribute less. **Implication:** confidence is state-dependent and changes round-to-round even with no new data.
- **D-09:** Use the audit engine's `_data_weight` formula per map verbatim (DEC-013 / `reference/theo_engine.py:104-129`): `min(team_a_avg_rounds, team_b_avg_rounds) / MIN_ROUNDS_FULL_WEIGHT`, capped at 1.0.

**`vega` — DEC-018 baseline form**
- **D-10:** Use DEC-018's initial form verbatim: `vega = round_p × (theo_after_a_win − theo)² + (1−round_p) × (theo_after_b_win − theo)²`. Refinement is Phase 5 work.
- **D-11:** Vega is computed at every `live_theo` invocation, not gated to round boundaries.

**Single canonical entry point**
- **D-12:** No reverse-compatibility shims for the audited engine's `series_theo` / `series_theo_no_sides` / `series_theo_from_map_probs` triplet. The entire pricing API surface for downstream phases is `live_theo(state: MatchState) → TheoOutput`. Non-negotiable.

**Module decomposition within `src/pricing/`**
- **D-13:** Five files, mirroring roadmap §1.1–1.6 verbatim: `dp.py`, `blend.py`, `round_types.py`, `round_conclusion.py`, `live_theo.py`.
- **D-14:** `MatchState` dataclass lives in `src/pricing/live_theo.py` for Phase 1 (the only consumer). When Phase 3 builds the full version, it will move to `src/state/match_state.py` and `live_theo.py` will import from there.

**Test scaffolding**
- **D-15:** Phase 1 ships *property tests* for the four invariants in roadmap §1.1, §1.2, §5.1: DP value ∈ [0,1] for any reachable state; symmetric-inputs DP equals `p²(3-2p)` from `fair_value.py`; Bradley-Terry symmetry; theo_series ↔ theo_map[] consistency. Phase 5's 80% coverage gate is project-wide; Phase 1 isn't expected to hit 80% on its own.

**DP cache strategy**
- **D-16:** Use `@functools.lru_cache(maxsize=None)` for in-process memoization. Defer `models/dp_table.pkl` warm-cache + mmap step to Phase 1 *if and only if* in-process cache is too slow for the < 500 ms latency budget. Decision rule: planner profiles a synthetic match replay end-to-end during Phase 1 and picks one of the two paths.

### Claude's Discretion

- The Bayesian-shrinkage formula inside `round_conclusion.py` (cell-to-parent shrink weights) is open. Phase 2 will calibrate; Phase 1 just needs *some* defensible formula so the structure is testable. Suggest reusing `SHRINK_PRIOR=15.0` from `src/config/constants.py` consistently.
- The exact `Optional[bool]` semantics of `pistol_winner_a` per map: pre-pistol = `None`, after pistol = `True/False`. Whether to surface this as a per-map dict, list, or per-`MatchState` field is planner's call.

### Deferred Ideas (OUT OF SCOPE)

- Full economy-bucket DP state (deferred to Phase 5 calibration). Carrying `econ_a, econ_b ∈ {full, semi-buy, semi-eco, eco}` per side as DP state with deterministic credit-flow rules. Cost: ~16x state expansion. Phase 1's `pistol_winner_a` is a deliberate compromise.
- `models/dp_table.pkl` warm cache + mmap (decision deferred until Phase 1 profiling). Per D-16, ship in Phase 1 only if cold-path latency exceeds budget.
- Vega refinement (PRD §9 TBD #3 / DEC-018 / Phase 5). DEC-018 picks variant (a) initially.
- Variance of round_conclusion outputs (Phase 5 calibration loop). Phase 1 ships placeholder shrink weights using `SHRINK_PRIOR=15.0`.

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REQ-bo3-dp-engine | Generalized BO3 DP `series_value(state, round_p_fn) → float`, memoized, value ∈ [0,1], symmetric-input → `p²(3-2p)` | §1 (DP state representation), §2 (recursion skeleton), §5 (OT leaf math), §11 (property-test fixture) |
| REQ-bradley-terry-blend | `p = a*(1-b) / (a*(1-b) + (1-a)*b)`, clip `a, b ∈ [1e-6, 1-1e-6]`, symmetric `round_p(a,b) == 1 − round_p(b,a)` | §3 (blend signature & edge cases) |
| REQ-pistol-anti-eco-modeling | Rounds {1,2,3,13,14,15} have separate probability inputs derived from `pistol_winner_a` and `GUN_WIN_RATE=0.822` | §4 (round-type model), §1 (`pistol_winner_a` semantics) |
| REQ-ot-handling | DP hard-stops at total=24 with documented coinflip leaf | §5 (OT coinflip leaf math) |
| REQ-round-conclusion-lookup (skeleton-only) | Hierarchical fallback chain skeleton; cells return 0.5; calibration deferred to Phase 2 | §6 (lookup signature & shrinkage scaffold) |
| REQ-canonical-live-theo | Single `live_theo(state) → TheoOutput`; do NOT recreate the triplet | §13 (salvage delta), Architecture diagram |
| REQ-theo-series-output | `theo_series ∈ [0,1]` = DP value at root state | §2 (recursion skeleton) |
| REQ-theo-map-output | `theo_map[i] ∈ [0,1]` = P(team A wins map i) by marginalizing the DP | §2, §11 (consistency property test) |
| REQ-confidence-output | DP-mass-weighted aggregate of per-map data weights (D-08) | §7 (DP-mass-weighted confidence) |
| REQ-vega-output | DEC-018 form: `round_p × (theo_a − theo)² + (1−round_p) × (theo_b − theo)²` (D-10) | §8 (vega at every invocation) |

</phase_requirements>

## Project Constraints (from CLAUDE.md)

These are **non-negotiable** project rules that bound every Phase 1 plan:

1. **Single canonical `live_theo`.** No `series_theo` / `series_theo_no_sides` / `series_theo_from_map_probs` triplet. (Critical Rule 1, DEC-010, CON-single-canonical-live-theo)
2. **BO3 series and per-map theos from the same DP.** Marginalize for per-map. (Critical Rule 2, DEC-002)
3. **Bradley-Terry blend, not arithmetic mean.** `p = a*(1-b) / (a*(1-b) + (1-a)*b)`. (Critical Rule 3, DEC-003)
4. **Pistol + anti-eco modeled explicitly** for rounds {1, 2, 3, 13, 14, 15}, using `GUN_WIN_RATE=0.822`. (Critical Rule 4, DEC-011)
5. **OT explicit hard-stop at total=24** with documented coinflip leaf. Do NOT silently iterate past round 24 with `p=0.5`. (Critical Rule 5, DEC-009, CON-ot-hard-stop)
6. **Conviction clips `[0.01, 0.99]`** — replaces audit-engine's `[0.05, 0.95]` and `[0.03, 0.97]`. (Critical Rule 6, DEC-012, CON-conviction-clip)
7. **`mypy --strict` on `src/pricing/`.** Every function/dataclass needs full annotations. (Critical Rule 11, CON-mypy-strict-pricing) — already wired in `pyproject.toml [[tool.mypy.overrides]] module = "src.pricing.*"`
8. **No magic numbers.** Every threshold lives in `src/config/constants.py`. (Critical Rule 12, CON-no-magic-numbers, DEC-016)
9. **One canonical implementation per concept.** No two functions doing the same thing differently. (Critical Rule 17 / Preferences)

---

## Summary

Phase 1 is a self-contained math layer with **zero external dependencies**. The work is five files in `src/pricing/`, ~600–900 lines of pure Python, fully covered by `mypy --strict`. There is no library research to do — the salvage source (`reference/theo_engine.py`) supplies the DP loop structure, and Phase 0 supplies every constant we need. The research effort is therefore concentrated on **settling design questions inside the math** so the planner can write 5–8 plans with concrete acceptance criteria.

The four documented audit-engine bugs are the load-bearing fixes:
1. Arithmetic-mean blend → Bradley-Terry log-odds blend (DEC-003).
2. Silent OT-as-coinflip via `range(26)` loop → explicit hard-stop at `total=24` with documented leaf (DEC-009).
3. Constant `p1`/`p2` per half → pistol/anti-eco modeled for rounds {1,2,3,13,14,15} (DEC-011).
4. Conviction clips `[0.05,0.95]`/`[0.03,0.97]` → unified `[0.01,0.99]` (DEC-012).

The fifth load-bearing change is structural: replace the three-function audit triplet with the single canonical `live_theo(state) → TheoOutput` (DEC-010) and derive per-map theos by **marginalizing the same DP** (DEC-002) — never run a parallel model.

**Primary recommendation:** Build the five modules in dependency order — `blend.py` → `round_types.py` → `dp.py` → `round_conclusion.py` → `live_theo.py` — each with property tests landed in the same wave. Plan 01-01 should bottom out the `BO3State` cache key + DP recursion (the load-bearing piece of the phase); the other four files are smaller and can wave in parallel afterward. Profile end-to-end synthetic-match replay before committing to D-16's `dp_table.pkl` path.

## Architectural Responsibility Map

Phase 1 is single-tier (a Python library module). Tier mapping is not the relevant concern; **layer-within-the-pricing-package** is. The seams that matter are:

| Capability | Module owner | Consumer | Rationale |
|------------|-------------|----------|-----------|
| BO3 DP recursion | `src/pricing/dp.py` | `live_theo.py` | Pure DP value function over `BO3State` — no awareness of round-types or live state |
| Round-win-prob blend | `src/pricing/blend.py` | `round_types.py`, `live_theo.py` | Atomic two-rate combiner — no DP awareness |
| Pistol/anti-eco logic | `src/pricing/round_types.py` | `dp.py` (via `round_p_fn` injection), `live_theo.py` | Round-number→probability resolver — depends on `blend.py`, not on DP |
| Mid-round lookup skeleton | `src/pricing/round_conclusion.py` | `live_theo.py` | Hierarchical lookup over (numerical_diff, bomb, side, econ_bucket, map) — Phase 1 cells return 0.5; Phase 2 calibrates |
| Output assembly + vega + confidence | `src/pricing/live_theo.py` | Phase 4 quoting layer | The single public API surface; orchestrates all four other modules |
| `MatchState` dataclass | `src/pricing/live_theo.py` (Phase 1 stub) | `live_theo` itself | Phase 3 will move this to `src/state/match_state.py` and `live_theo` will import from there |
| Constants | `src/config/constants.py` (Phase 0) | All five Phase-1 modules | Already in place; never inline values |

**Why this matters:** The `round_p_fn: Callable[[BO3State], float]` injection point in `dp.py` (per CON-bo3-dp-signature) is the load-bearing seam. It lets `round_types.py` (which knows about pistols and `GUN_WIN_RATE`) feed into `dp.py` (which is a pure DP recursion with no domain awareness). This dependency direction must not flip — `dp.py` MUST NOT import `round_types.py`.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `functools.lru_cache` | stdlib (Python 3.11) | Memoized DP recursion `[CITED: roadmap §1.1]` | Roadmap §1.1 explicitly specifies it; matches the cache-key requirement (frozen tuple, hashable) |
| `dataclasses` | stdlib (Python 3.11) | `TheoOutput`, `MatchState` (Phase 1 stub), and any helper records `[CITED: roadmap §1.6]` | Roadmap §1.6 + §3.1 use `@dataclass`; `frozen=True` gives hashability for free |
| `typing.Final` | stdlib (Python 3.11) | Module-level constants (already used in `src/config/constants.py`) `[VERIFIED: src/config/constants.py:38]` | Phase 0 convention; `mypy --strict` catches reassignment |
| `typing.Callable, Optional, Literal` | stdlib (Python 3.11) | Type hints across `round_p_fn`, `pistol_winner_a`, `side_orient` `[CITED: CON-bo3-dp-signature]` | Required for `mypy --strict` correctness |

### Supporting (test-only)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pytest` | 8+ (resolved 9.0.3 in lockfile) `[VERIFIED: 00-VERIFICATION.md]` | Test runner | Every test file |
| `hypothesis` | 6.100+ (resolved 6.152.4) `[VERIFIED: 00-VERIFICATION.md]` | Property-based testing | The four roadmap §5.1 invariants — DP range, monotonicity, BT symmetry, series↔map consistency |
| `pytest-cov` | 5+ (resolved 7.1.0) `[VERIFIED: 00-VERIFICATION.md]` | Line-coverage measurement | Phase 1 doesn't enforce a gate; Phase 5 does (80% per CON-coverage-target) |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `@dataclass(frozen=True)` | `typing.NamedTuple` | NamedTuple is hashable by default but doesn't allow defaults to participate in keyword args cleanly; `frozen=True` dataclass is more idiomatic for `mypy --strict` and supports `field(default_factory=...)`. **Recommend frozen dataclass.** `[ASSUMED]` |
| `functools.lru_cache(maxsize=None)` | `functools.cache` (Python 3.9+) | `cache` is `lru_cache(maxsize=None)` aliased — identical for our purposes. Roadmap explicitly says `lru_cache(maxsize=None)`; stick to that for traceability. `[CITED: roadmap §1.1]` |
| `typing.NamedTuple` for `BO3State` | `tuple[int, int, int, int, int, str, tuple[str, ...], tuple[Optional[bool], ...]]` | A bare tuple is trivially hashable but loses field-name introspection. NamedTuple is the right shape but mypy's strict default-handling for NamedTuple is fiddly with `Optional[bool]`. **Recommend frozen dataclass with `__slots__`** for both readability and lru_cache compatibility. `[ASSUMED]` |

**Installation:** None. Phase 0 already pinned all deps in `uv.lock` (pytest 9.0.3, pytest-cov 7.1.0, hypothesis 6.152.4, ruff 0.15.12, mypy 1.20.2). `[VERIFIED: STATE.md "Plan 00-01 outcomes"]`

**Version verification:** Not applicable — no new packages. Phase 1 uses only the Python 3.11 stdlib plus the dev-deps already locked in Phase 0.

---

## Architecture Patterns

### System Architecture Diagram

```
                        Phase 4 quoting layer (downstream)
                                       │
                                       ▼
                          ┌────────────────────────┐
                          │   live_theo.py         │
                          │   live_theo(state)     │
                          │   → TheoOutput(        │
                          │       theo_series,     │
                          │       theo_map,        │
                          │       vega,            │
                          │       confidence)      │
                          └─────────────┬──────────┘
                                        │
              ┌──────────────┬──────────┼──────────┬─────────────────┐
              ▼              ▼          ▼          ▼                 ▼
        ┌─────────┐   ┌─────────────┐  │   ┌─────────────────┐  ┌──────────┐
        │ dp.py   │   │ round_      │  │   │ round_          │  │ helpers  │
        │ series_ │   │ types.py    │  │   │ conclusion.py   │  │ (vega,   │
        │ value   │◀──│ round_p_fn  │  │   │ lookup(...) →   │  │ conf,    │
        │ (state, │   │ (state,...) │  │   │ float (=0.5     │  │ marg.)   │
        │ round_p_│   │             │  │   │ Phase 1 stub)   │  └────┬─────┘
        │ fn)     │   └──────┬──────┘  │   └────────┬────────┘       │
        └────┬────┘          │         │            │                 │
             │               ▼         │            │                 │
             │         ┌──────────┐    │            │                 │
             └────────▶│ blend.py │◀───┘            │                 │
                       │ round_p( │                 │                 │
                       │   a, b   │                 │                 │
                       │ ) → float│                 │                 │
                       └─────┬────┘                 │                 │
                             │                      │                 │
                             ▼                      ▼                 ▼
                       ┌─────────────────────────────────────────────────┐
                       │      src/config/constants.py (Phase 0)         │
                       │  GUN_WIN_RATE, SHRINK_PRIOR, REGULATION_HALF,  │
                       │  WIN_THRESHOLD, SIGNAL_SCALE, [new:             │
                       │  CONVICTION_CLIP_LO/HI, OT_TOTAL_HARDSTOP,      │
                       │  MIN_ROUNDS_FULL_WEIGHT, BT_BLEND_EPSILON]     │
                       └─────────────────────────────────────────────────┘
                                                    ▲
                                                    │ data/half_win_rates.json
                                                    │ (read by live_theo for
                                                    │  per-team/map/side rates)
```

**Data-flow trace** (single `live_theo(state)` call):

1. `live_theo` reads `state.map_pool, map_idx, a/b_map_score, a/b_round, side_orient, pistol_winner_a, numerical_diff, bomb_planted, side, econ_bucket`.
2. Constructs the root `BO3State` from `state` fields.
3. Calls `dp.series_value(root_state, round_p_fn)` where `round_p_fn` is a closure over `state` that:
   - For round ∈ {1, 2, 3, 13, 14, 15}: delegates to `round_types.pistol_round_p(...)`.
   - Otherwise: looks up half-win-rates and calls `blend.round_p(a, b)`.
4. **For per-map output**: marginalizes the DP — re-runs `series_value` with hypothetical "this map already won by A" and "this map already won by B" boundary conditions, computes `P(map_i won by A | reaches & decides map_i)`. (See §10.)
5. **For vega**: computes `round_p` at the current state, runs the DP twice (after-A-wins-this-round, after-B-wins-this-round), assembles `round_p × (theo_a − theo)² + (1−round_p) × (theo_b − theo)²`.
6. **For confidence**: per map in pool, computes `data_w(m)` from `half_win_rates.json` (audit `_data_weight` formula), weights by `P(map m reached & decisive)` from the DP forward pass, sums.
7. **For mid-round adjustment**: if any of `numerical_diff != 0, bomb_planted, econ_bucket != 'full'` is set, calls `round_conclusion.lookup(numerical_diff, bomb_planted, side, econ_bucket, map_name)` (returns 0.5 in Phase 1) and overrides the between-round `round_p` for the current round only.
8. Clips `theo_series` and each `theo_map[i]` to `[CONVICTION_CLIP_LO, CONVICTION_CLIP_HI]` = `[0.01, 0.99]`.
9. Returns `TheoOutput(theo_series, theo_map, vega, confidence)`.

### Recommended Project Structure

```
src/pricing/
├── __init__.py             # already exists (Phase 0 placeholder)
├── blend.py                # ~30 LoC. round_p(a, b) + module-level epsilon.
├── round_types.py          # ~80 LoC. pistol_round_p / anti_eco_round_p / dispatch.
├── dp.py                   # ~150 LoC. BO3State dataclass + series_value + lru_cache.
├── round_conclusion.py     # ~120 LoC. Hierarchical lookup skeleton + shrinkage.
└── live_theo.py            # ~250 LoC. MatchState stub + TheoOutput + live_theo + helpers.

tests/pricing/
├── __init__.py
├── test_blend.py           # 3 unit cases + 1 hypothesis symmetry test.
├── test_round_types.py     # Pistol/anti-eco round-num dispatch + GUN_WIN_RATE wiring.
├── test_dp.py              # Range + symmetric-input (uses fair_value) + monotonicity.
├── test_round_conclusion.py # Skeleton returns 0.5 + fallback chain wiring.
└── test_live_theo.py       # End-to-end + theo_series ↔ theo_map[] consistency.
```

### Pattern 1: `round_p_fn` Closure Injection

**What:** `dp.series_value` accepts `round_p_fn: Callable[[BO3State], float]` rather than reading round-type logic itself.
**When to use:** Always. This is the seam that keeps `dp.py` pure-DP and `round_types.py` domain-aware.
**Example (will appear in `live_theo.py`):**
```python
# Source: roadmap.md §1.1 (CON-bo3-dp-signature)
def _build_round_p_fn(state: MatchState, half_rates: HalfRates) -> Callable[[BO3State], float]:
    def round_p_fn(s: BO3State) -> float:
        round_num = s.a_round + s.b_round + 1  # 1-indexed
        if round_num in (1, 2, 3, 13, 14, 15):
            return round_types.pistol_or_antieco_p(s, state, half_rates)
        # Gunround baseline:
        a_rate = half_rates.team(state.team_a, s.current_map(), s.team_a_side())
        b_rate = half_rates.team(state.team_b, s.current_map(), s.team_b_side())
        return blend.round_p(a_rate, b_rate)
    return round_p_fn

# Then:
theo_series = dp.series_value(root_bo3_state, _build_round_p_fn(state, half_rates))
```

### Pattern 2: Marginalization for `theo_map[i]`

**What:** Compute `P(team A wins map i | current state)` by running the DP twice with map-i-outcome forced and comparing.
**When to use:** Once per map in `map_pool`, inside `live_theo`.
**Example:**
```python
# Source: PRD §2.2 (DEC-002), roadmap §1.6
def _marginal_map_prob(
    root: BO3State,
    map_idx: int,
    round_p_fn: Callable[[BO3State], float],
) -> float:
    # P(A wins map i) = E[1{A wins map i}] under the DP measure.
    # Forward pass: walk every reachable terminal of the DP, accumulate mass weighted by
    # whether map i was won by A. Cheaper alternative: re-run series_value with map_idx
    # forced to 1 vs 0 wins for A, take the difference. Use the forward-pass approach
    # since we already need it for confidence weighting (see §7).
    ...
```

### Anti-Patterns to Avoid

- **Recreating the audit triplet.** `series_theo` / `series_theo_no_sides` / `series_theo_from_map_probs` had inconsistent `signal_strength` application — that was the bug. Phase 1 has ONE entry point: `live_theo`. (DEC-010, CON-single-canonical-live-theo)
- **Inlining magic numbers.** Every `0.01`, `0.99`, `15`, `24`, `0.822` etc. comes from `src/config/constants.py`. New constants needed by Phase 1 must be added to `constants.py` first (see §12).
- **Silent OT iteration.** Do NOT write `for total in range(26)` and pretend `p=0.5` past `total=24` is intentional. Hard-stop at `total=24` with explicit OT leaf math (DEC-009, CON-ot-hard-stop).
- **Arithmetic-mean blend.** `(a + (1-b)) / 2` is the audit-engine bug. Use Bradley-Terry: `a*(1-b) / (a*(1-b) + (1-a)*b)`. (DEC-003, CON-bradley-terry-formula)
- **Per-half-flat `p1`/`p2`.** The audit engine's `_markov_map_win(p1, p2)` ignores pistols. The new `series_value` MUST consult `round_p_fn(state)` per-round so rounds {1,2,3,13,14,15} can use pistol/anti-eco probs. (DEC-011)
- **Tighter clips than `[0.01, 0.99]` without documenting them.** (DEC-012, CON-conviction-clip)
- **Mutating `MatchState` inside pricing.** `live_theo` is a pure read; Phase 3 owns mutation. Defensive copy if anything is needed (frozen dataclass prevents this by construction).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Memoized recursion | Custom dict-based memo | `@functools.lru_cache(maxsize=None)` | Stdlib, thread-safe, debuggable via `cache_info()`, explicitly mandated by roadmap §1.1 |
| Bisection root-finder for `p²(3-2p) = S` | Re-implement | `reference/fair_value.py::map_prob_from_series` | Already salvaged as-is per DEC-013. Don't rewrite. |
| Closed-form symmetric DP value `p²(3-2p)` | Re-derive | `reference/fair_value.py::_bo3_series_prob` | Salvaged. Import as test fixture. |
| Half-win-rate fallback chain (team→league→overall) | Re-implement | Adapt `reference/theo_engine.py::_get_rate` (lines 84-102) | This logic is correct in the audit engine; fix only the upstream callers. Salvage with attribution. |
| Data-weight per map | Re-derive | Adapt `reference/theo_engine.py::_data_weight` (lines 104-129) | DEC-013 says salvage; D-09 says use verbatim. |

**Key insight:** The salvage source (`reference/theo_engine.py`) is **correct on data plumbing** (rate lookups, data-weight, fallback chain) and **wrong on math** (round-blend, OT loop, round-type, clips). The Phase 1 strategy: keep the right plumbing, fix the wrong math, kill the triplet structure.

---

## Common Pitfalls

### Pitfall 1: Caching `BO3State` with `pistol_winner_a` as a list/dict
**What goes wrong:** `lru_cache` requires hashable keys. Lists are not hashable; dicts are not hashable.
**Why it happens:** Natural Python instinct is to model "per-map pistol winner" as `dict[int, Optional[bool]]`.
**How to avoid:** Use `tuple[Optional[bool], ...]` indexed positionally by `map_idx` inside `BO3State`. Convert from `MatchState`'s dict form at the top of `live_theo` before recursion.
**Warning signs:** `TypeError: unhashable type: 'dict'` on first DP call.

### Pitfall 2: OT leaf semantics — recursing into "OT play" instead of returning the closed form
**What goes wrong:** When you reach `total=24`, you might be tempted to recurse into a separate "OT DP" with `p=0.5` per round until win-by-2. That's a wholly separate DP, unbounded in length, and will silently violate the hard-stop.
**Why it happens:** Reading "OT continues with `p=0.5`" naturally suggests recursion.
**How to avoid:** At `total=24`, return the closed-form leaf: `0.5 × series_value(state_after_a_wins_this_map) + 0.5 × series_value(state_after_b_wins_this_map)`. The "OT-as-coinflip" assumption collapses the entire OT subtree into a 50/50 — the leaf is the answer, not an entry point. (See §5 below.)
**Warning signs:** `RecursionError`, or DP cache size growing per match.

### Pitfall 3: `theo_map[i]` and `theo_series` disagreeing
**What goes wrong:** If you run a separate model for `theo_map[i]` instead of marginalizing the DP, the per-map probabilities and series probability silently disagree (the audit engine's `series_theo_no_sides` bug).
**Why it happens:** It's tempting to compute per-map "directly" from half-win-rates as a shortcut.
**How to avoid:** `theo_map[i]` MUST come from the same DP as `theo_series` via marginalization (DEC-002). The roadmap §5.1 property test "theo_series equals sum over outcomes derivable from theo_map[]" is the unit-level check.
**Warning signs:** Property test fails; `theo_series` and `expected_theo_series_from_marginals` differ by > 1e-10.

### Pitfall 4: Bradley-Terry blend at boundary inputs
**What goes wrong:** `round_p(0.0, 1.0)` → `0.0 / (0.0 + 0.0)` = `NaN` (0-divided-by-0) without epsilon clipping.
**Why it happens:** Pure log-odds blend has poles at 0 and 1.
**How to avoid:** Clip `a, b` to `[1e-6, 1-1e-6]` BEFORE the blend (CON-bradley-terry-formula). The output is then automatically in `[1e-12, 1-1e-12]`, well inside `[0.01, 0.99]`. **Do not also clip the output** — that breaks BT symmetry (`round_p(a,b) + round_p(b,a) != 1` when one but not both saturate). See §3.
**Warning signs:** `RuntimeWarning: invalid value encountered`, NaN propagating into DP cache.

### Pitfall 5: `lru_cache` on `MatchState` (instead of `BO3State`)
**What goes wrong:** `MatchState` includes fields like `seq_id`, `last_updated_ts` (in Phase 3) that change every event but don't affect DP value. Caching on the full `MatchState` blows out the cache and defeats memoization.
**Why it happens:** Forgetting that the cache key should be the *DP-relevant* subset of state.
**How to avoid:** `lru_cache` decorates `series_value(BO3State, ...)`, not `live_theo(MatchState)`. `live_theo` extracts the `BO3State` from `MatchState` per call.
**Warning signs:** `cache_info().currsize` growing unboundedly during a match replay; cold-path latency on repeat calls.

### Pitfall 6: Forgetting to flip side at map boundary
**What goes wrong:** Within a map, halves alternate (atk → def at round 13). Across maps in a BO3, the starting side is determined by veto, not by automatic alternation. The audit engine's `series_theo_no_sides` averaged atk-start and def-start to dodge this — that's wrong (PRD §12.2 #6).
**Why it happens:** Veto outcome lives in `MatchState.side_orient` per map, not derivable from index.
**How to avoid:** `MatchState` carries `side_orient` per map (D-02 says `side_orient` is a single field for the current map; per-map history is captured in the existing scoreline). For Phase 1 with no veto info upstream, the planner must define how `side_orient` is interpreted across map boundaries — propose: `MatchState.map_side_orients: tuple[str, ...]` indexed by map_idx, where index 0 is map 1's starting side, etc. **Open question for the planner.**
**Warning signs:** Property test "round 13 of map 1 has flipped side" fails; values differ from hand-computed expectations.

### Pitfall 7: Floating-point drift in `theo_series ↔ theo_map[]` consistency
**What goes wrong:** Marginalization over a 24-round DP accumulates float error. Strict equality (`==`) in property tests fails.
**Why it happens:** `lru_cache` doesn't change float semantics; the DP itself does ~24 multiplications and additions per terminal path.
**How to avoid:** Use `pytest.approx(rel=1e-9)` or `math.isclose(a, b, rel_tol=1e-9)` in consistency tests, NOT `==`. Document the tolerance in the test file.
**Warning signs:** Hypothesis flaky-test report showing differences at the 12th decimal.

---

## Runtime State Inventory

**Phase 1 is greenfield code (no rename/refactor/migration).** The only existing-state concern is the salvage source `reference/theo_engine.py`, which is read-only and not modified. No data migration, no live service config, no OS-registered state, no secrets/env vars, no build artifacts to manage.

Section omitted per researcher instruction (greenfield).

---

## Code Examples

Verified patterns sourced from the salvage layer or directly mandated by roadmap/CONTEXT.

### `BO3State` dataclass + cache key

```python
# Source: CON-bo3-dp-signature (roadmap §1.1) + D-03 (pistol_winner_a per map)
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True, slots=True)
class BO3State:
    """DP cache key. Hashable; suitable for @lru_cache.

    Distinct from MatchState: BO3State holds ONLY DP-relevant fields. Live state
    (seq_id, ts, players_alive, etc.) does NOT belong here.
    """
    map_idx: int                              # current map index (0-based)
    a_map_score: int                          # 0, 1, or 2
    b_map_score: int                          # 0, 1, or 2
    a_round: int                              # rounds team A has won in current map
    b_round: int                              # rounds team B has won in current map
    side_orient: str                          # 'a_atk' | 'a_def' (current half)
    map_pool: tuple[str, ...]                 # frozen for hashability
    pistol_winner_a: tuple[Optional[bool], ...]  # per-map; None=pre-pistol; len == len(map_pool)
```

### Bradley-Terry blend

```python
# Source: CON-bradley-terry-formula (prd §12.2 #4 + roadmap §1.2)
from typing import Final

BT_BLEND_EPSILON: Final[float] = 1e-6  # PROPOSED for src/config/constants.py — see §12

def round_p(a_rate: float, b_rate_opposite_side: float) -> float:
    """P(team A wins one round) given team A's win-rate on its side and
    team B's win-rate on the opposite side."""
    a = max(BT_BLEND_EPSILON, min(1.0 - BT_BLEND_EPSILON, a_rate))
    b = max(BT_BLEND_EPSILON, min(1.0 - BT_BLEND_EPSILON, b_rate_opposite_side))
    return (a * (1.0 - b)) / (a * (1.0 - b) + (1.0 - a) * b)
```

### Symmetric-input property fixture

```python
# Source: REQ-bo3-dp-engine acceptance ("symmetric inputs equal p²(3-2p)")
# Test fixture imports from reference/ — already-salvaged closed form.
from reference.fair_value import _bo3_series_prob

def test_dp_symmetric_inputs(p: float = 0.6) -> None:
    """For constant round_p across all states, DP value = p²(3-2p)."""
    state = BO3State(
        map_idx=0, a_map_score=0, b_map_score=0,
        a_round=0, b_round=0, side_orient='a_atk',
        map_pool=('Lotus', 'Bind', 'Haven'),
        pistol_winner_a=(None, None, None),
    )
    constant_round_p_fn = lambda _s: p
    assert math.isclose(
        series_value(state, constant_round_p_fn),
        _bo3_series_prob(p),
        rel_tol=1e-9,
    )
```

**Caveat for symmetric-input test:** When `round_p` is constant, BT-blend symmetry implies `p == round_p(r, 1-r)` if we set both teams' inputs symmetrically. But the test passes a `lambda` that ignores state and returns a literal `p` — that bypasses the blend entirely and tests only the DP recursion. That's the correct test scope (DP, not BT). The BT symmetry is tested separately in `test_blend.py`.

### Audit-engine `_data_weight` (salvage-with-attribution per D-09)

```python
# Source: reference/theo_engine.py:104-129 (DEC-013 / D-09 — salvage verbatim)
# This computation is what 'confidence' weighting consumes.
def data_weight_for_map(team_a: str, team_b: str, map_name: str, half_rates: HalfRates) -> float:
    """Audit-engine formula: min over teams of (avg_rounds across sides) / MIN_ROUNDS_FULL_WEIGHT."""
    team_weights: list[float] = []
    for team in (team_a, team_b):
        total = 0.0; count = 0
        for side in ('atk', 'def'):
            entry = half_rates.team_entry(team, map_name, side)
            if entry and not entry.get('used_fallback', False):
                total += float(entry.get('total', 0))
                count += 1
        if count == 0:
            return 0.0
        team_weights.append(total / count)
    return min(1.0, min(team_weights) / MIN_ROUNDS_FULL_WEIGHT)
```

---

## State of the Art

This is a closed-system math layer with no library version drift to worry about. The "state of the art" lives in the locked decisions:

| Old Approach (audit engine) | Current Approach (Phase 1) | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Arithmetic-mean blend `(a + (1-b))/2` | Bradley-Terry log-odds `a*(1-b) / (a*(1-b) + (1-a)*b)` | DEC-003 / 2026-04-27 | Compounding edges (e.g., `(0.7, 0.3)` → 0.84 vs 0.70) `[CITED: roadmap §1.2 acceptance criterion]` |
| Constant `p1` (R1-12) / `p2` (R13-24) | Per-round resolver, pistol/anti-eco for {1,2,3,13,14,15} | DEC-011 / 2026-04-27 | "Single largest accuracy gain" per roadmap §1.3 |
| Silent OT-as-coinflip via `range(26)` | Explicit hard-stop at `total=24` with documented leaf | DEC-009 / 2026-04-27 | No-op math (still 0.5 at OT), but explicit + audit-trail-visible |
| Three pricing entry points with inconsistent `signal_strength` | Single canonical `live_theo` | DEC-010 / 2026-04-27 | Eliminates the "switching entry points silently changes results" bug class |
| Conviction clips `[0.05, 0.95]` and `[0.03, 0.97]` | Unified `[0.01, 0.99]` | DEC-012 / 2026-04-27 | Wider conviction range; more honest extreme states |

**Deprecated/outdated:**
- `series_theo`, `series_theo_no_sides`, `series_theo_from_map_probs` — all three replaced by single `live_theo`. Do NOT salvage. (DEC-010)
- `_round_win_prob` (audit `theo_engine.py:146`) — uses arithmetic-mean blend. Do NOT salvage. (DEC-003)

---

## Settled Design Questions

The 13 questions the planner asked the researcher to settle, with concrete answers.

### §1. DP state representation — exact `BO3State` shape

**Decision:** Frozen dataclass with `slots=True`, all fields hashable.

```python
# src/pricing/dp.py (proposed)
@dataclass(frozen=True, slots=True)
class BO3State:
    map_idx: int
    a_map_score: int
    b_map_score: int
    a_round: int
    b_round: int
    side_orient: str  # 'a_atk' or 'a_def' for the current half of the current map
    map_pool: tuple[str, ...]
    pistol_winner_a: tuple[Optional[bool], ...]  # length == len(map_pool); None pre-pistol
```

**Rationale:**
- `frozen=True` makes it hashable for `@lru_cache(maxsize=None)`. Verified: `dataclass(frozen=True)` produces `__hash__` based on `(field1, field2, ...)`. `[VERIFIED: Python 3.11 docs / dataclasses module]`
- `slots=True` cuts memory ~40% per instance (no `__dict__`); meaningful at ~1M cache entries. `[CITED: PEP 412, dataclasses slots]`
- All fields are hashable atoms (`int`, `str`, `tuple`, `Optional[bool]`). `tuple[Optional[bool], ...]` is hashable because tuples of hashables are hashable.
- **Why dataclass not NamedTuple:** Named field access in cache-key debugging; NamedTuple's interaction with `slots=True` and `Optional[bool]` defaults under `mypy --strict` is more fragile. `[ASSUMED]`
- **Why `tuple` not `list` for `map_pool` and `pistol_winner_a`:** lists are unhashable. The conversion happens once, at the top of `live_theo`, when building the root state from `MatchState`.
- **Cardinality estimate:** see §9.

### §2. DP recursion code shape

**Decision:** Single function `series_value(state, round_p_fn)` in `dp.py`, top-down memoized recursion. NO separate `_markov_map_win` — the full BO3 is one recursion.

```python
# src/pricing/dp.py (proposed; FIXES audit lines 168-206)
@functools.lru_cache(maxsize=None)
def _series_value_cached(
    state: BO3State,
    round_p_id: int,  # see §9 — round_p_fn cannot be in the cache key directly
) -> float:
    """Bottom-up via top-down recursion with memoization.

    Terminal cases:
      - a_map_score == 2 → 1.0   (A clinched series)
      - b_map_score == 2 → 0.0   (B clinched series)
      - map terminal (a_round == 13 or b_round == 13) → recurse with next-map root state
      - within-map total == 24 → OT coinflip leaf (see §5)
      - else → standard within-map recurrence
    """
    # [terminals first]
    if state.a_map_score >= 2:
        return 1.0
    if state.b_map_score >= 2:
        return 0.0

    # Map terminal: someone hit 13 rounds in this map
    if state.a_round >= WIN_THRESHOLD:
        next_state = _advance_to_next_map(state, a_won_this_map=True)
        return _series_value_cached(next_state, round_p_id)
    if state.b_round >= WIN_THRESHOLD:
        next_state = _advance_to_next_map(state, a_won_this_map=False)
        return _series_value_cached(next_state, round_p_id)

    # OT hard-stop at total=24
    total = state.a_round + state.b_round
    if total == REGULATION_HALF * 2:  # == 24
        return _ot_coinflip_leaf(state, round_p_id)  # see §5

    # Within-map recurrence
    p = _ROUND_P_FNS[round_p_id](state)
    state_a_wins = _advance_round(state, a_wins=True)
    state_b_wins = _advance_round(state, a_wins=False)
    return (
        p * _series_value_cached(state_a_wins, round_p_id)
        + (1.0 - p) * _series_value_cached(state_b_wins, round_p_id)
    )

# Public entry:
def series_value(state: BO3State, round_p_fn: Callable[[BO3State], float]) -> float:
    round_p_id = _register_round_p_fn(round_p_fn)  # see §9 cache strategy
    return _series_value_cached(state, round_p_id)
```

**Helpers `_advance_round`, `_advance_to_next_map`, `_ot_coinflip_leaf`:**
- `_advance_round(state, a_wins=True)`: increment `a_round` or `b_round`; if `a_round + b_round == 12` (just finished round 12), flip `side_orient` (atk↔def). Otherwise leave `side_orient` unchanged. Returns new frozen `BO3State`.
- `_advance_to_next_map(state, a_won_this_map=True)`: `map_idx += 1`, `a_map_score += 1` (or `b_map_score += 1`), reset `a_round=b_round=0`, set `side_orient` to map-(map_idx)'s starting side (sourced from `MatchState.map_side_orients[map_idx]` — see Pitfall 6 / planner-open-question), reset `pistol_winner_a` for the new map's slot to `None`.
- `_ot_coinflip_leaf`: see §5.

**Why this shape:**
- Top-down with `@lru_cache` is what the roadmap §1.1 specifies and matches the bottom-up audit `_markov_map_win` in semantics but generalizes to the full BO3.
- One function for the whole BO3 (not separate `_markov_map_win` for each map) eliminates the audit triplet's "two-model disagreement" risk class.
- The `round_p_id` indirection (see §9) is necessary because `Callable` is not hashable for `lru_cache`.

### §3. Bradley-Terry blend signature and edge cases

**Decision:**

```python
# src/pricing/blend.py
from src.config.constants import BT_BLEND_EPSILON  # PROPOSED — see §12

def round_p(a_rate: float, b_rate_opposite_side: float) -> float:
    a = max(BT_BLEND_EPSILON, min(1.0 - BT_BLEND_EPSILON, a_rate))
    b = max(BT_BLEND_EPSILON, min(1.0 - BT_BLEND_EPSILON, b_rate_opposite_side))
    return (a * (1.0 - b)) / (a * (1.0 - b) + (1.0 - a) * b)
```

**Edge-case audit:**

| Input | Output | Notes |
|-------|--------|-------|
| `(0.5, 0.5)` | `0.25 / 0.5 = 0.5` | Coin flip — required by acceptance criterion |
| `(0.7, 0.3)` | `0.7*0.7 / (0.7*0.7 + 0.3*0.3) = 0.49/0.58 = 0.8448...` | "0.84 (compounding edge)" per acceptance |
| `(1.0, 0.0)` | After clip: `(1-1e-6, 1e-6)` → `(1-1e-6)*(1-1e-6) / (...) ≈ 0.999999999998` | Required acceptance "→ 1.0" satisfied (within tolerance) |
| `(0.0, 1.0)` | After clip: `1e-6 * 1e-6 / (1e-6 * 1e-6 + (1-1e-6)*(1-1e-6)) ≈ 1e-12` | Zero, as expected |

**Symmetry property:** `round_p(a, b) == 1 − round_p(b, a)`. Verified algebraically:
```
round_p(a, b) = a(1-b) / [a(1-b) + (1-a)b]
1 - round_p(b, a) = 1 - [b(1-a) / (b(1-a) + (1-b)a)]
                  = (1-b)a / [(1-b)a + b(1-a)]
                  = a(1-b) / [a(1-b) + (1-a)b]                  ✓
```
**Clip ordering preserves symmetry:** clipping `a → a'` and `b → b'` symmetrically before the formula keeps the algebra symmetric. Clipping the *output* would break it (e.g., `0.999... → 0.99` is not paired with `0.001... → 0.01` for `1-x`). **Therefore: clip inputs only, never outputs in `blend.py`.** (Output clip to `[0.01, 0.99]` happens in `live_theo.py` on the final `theo_series` and `theo_map[i]`, not on intermediate round-probabilities.)

### §4. Pistol/anti-eco round-type model

**Decision:** Six round types, dispatched by round number:

```python
# src/pricing/round_types.py
def round_p_for_round(
    state: BO3State,
    match_state: MatchState,
    half_rates: HalfRates,
) -> float:
    """Resolves P(team A wins this round) for the round about to start in `state`."""
    round_num = state.a_round + state.b_round + 1  # 1-indexed
    map_name = state.map_pool[state.map_idx]
    side = state.side_orient

    if round_num == 1 or round_num == 13:
        # Pistol: per-team/side/map pistol-win-rate from match_round_data.
        # Phase 1: NO match_round_data yet — use half_rates as the fallback.
        # The blend.round_p of (a_pistol_rate, b_pistol_rate_opposite_side) is the
        # right shape; cell calibration to actual pistol-only rates is Phase 2 work.
        a_rate = half_rates.team(match_state.team_a, map_name, _team_a_side(side))
        b_rate = half_rates.team(match_state.team_b, map_name, _team_b_side(side))
        return blend.round_p(a_rate, b_rate)

    if round_num in (2, 3, 14, 15):
        # Anti-eco / pistol-conversion. Conditional on pistol_winner_a[map_idx]:
        pistol_won_by_a = state.pistol_winner_a[state.map_idx]
        if pistol_won_by_a is None:
            # Should not happen (round 2 implies round 1 is settled), but defensive:
            return 0.5
        if pistol_won_by_a:
            # Team A is the gun-side this round; team B is on eco/forced-buy.
            return GUN_WIN_RATE  # 0.822
        else:
            # Team A is on eco/forced-buy; team B is on guns.
            return 1.0 - GUN_WIN_RATE  # 0.178

    # Gunround baseline (rounds 4-12, 16-24)
    a_rate = half_rates.team(match_state.team_a, map_name, _team_a_side(side))
    b_rate = half_rates.team(match_state.team_b, map_name, _team_b_side(side))
    return blend.round_p(a_rate, b_rate)
```

**Concrete probability inputs:**

| Round | Input | Source |
|-------|-------|--------|
| 1, 13 (pistol) | `blend.round_p(a_pistol_rate, b_pistol_rate_opposite_side)` | `half_rates.team(...)` for Phase 1; **Phase 2 will calibrate** to per-team pistol-only rates from `match_round_data` (DEC-011 / roadmap §1.3 table) |
| 2, 14 (post-pistol-loser-eco) | `GUN_WIN_RATE = 0.822` if A won pistol; `1 - GUN_WIN_RATE = 0.178` if B won pistol | DEC-011, `src/config/constants.py` |
| 3, 15 (third-round bonus / continued anti-eco) | Same as round 2/14 — Phase 1 simplification. **Phase 2 may differentiate** (empirical conversion rate ~75% on round 2 and ~60% on round 3 per roadmap §1.3) | DEC-011 |
| 4-12, 16-24 (gunrounds) | `blend.round_p(a_rate, b_rate_opposite_side)` from `half_rates` | DEC-011, half_win_rates.json |

**Phase 1 simplification flag:** Rounds 3 and 15 use the same `GUN_WIN_RATE` model as rounds 2 and 14. Roadmap §1.3 notes empirical rate is ~60% on round 3 (vs ~75% on round 2). Phase 1 ships the structurally-correct dispatch; Phase 2 calibrates the rate differential. **This is acceptable because:** (a) `match_round_data` is not yet available (Phase 2's job to fetch), and (b) the structural dispatch is what enables Phase 2 to drop in calibrated rates without code changes. Document this in `round_types.py` docstring.

### §5. OT coinflip leaf math

**Decision:** At `total = 24` (i.e., 12-12 in regulation), the leaf returns:
```
0.5 × series_value(state_after_a_wins_this_map) + 0.5 × series_value(state_after_b_wins_this_map)
```

**Concrete meaning of "value(after_a_OT_win)":** It does NOT recurse into a separate "OT play" DP. It treats the OT-winning team as if they won the map and recurses into the **next-map root state**. The DP returns the **series-level value** assuming this map is decided 50/50 by an OT coinflip.

```python
# src/pricing/dp.py
def _ot_coinflip_leaf(state: BO3State, round_p_id: int) -> float:
    """At total=24, OT is a coinflip per DEC-009. Each side of the leaf is a
    next-map root state — i.e., we collapse the entire OT sub-DP into a 50/50."""
    state_a_wins_map = _advance_to_next_map(state, a_won_this_map=True)
    state_b_wins_map = _advance_to_next_map(state, a_won_this_map=False)
    return (
        0.5 * _series_value_cached(state_a_wins_map, round_p_id)
        + 0.5 * _series_value_cached(state_b_wins_map, round_p_id)
    )
```

**Why this is the right interpretation of D-05/DEC-009:**
- D-05 explicitly says the leaf is "computed (not flat 0.5) because each side of the leaf may have asymmetric downstream series outcomes (we may already be 1-0 in maps)." That asymmetry comes from the **post-OT series state**, not from in-OT round outcomes.
- DEC-009 says "OT continues with constant `p = 0.5` until win-by-2." Under `p=0.5`, the win-by-2 OT is symmetric — `P(A wins OT) = 0.5`. So the value of "this map under OT" is `0.5 × value(A won map) + 0.5 × value(B won map)`. There is no need to model OT's internal round structure because all paths through it have probability symmetric in A/B.
- This avoids unbounded recursion (Pitfall 2).

### §6. Hierarchical-lookup skeleton signature

**Decision:**

```python
# src/pricing/round_conclusion.py
from typing import Final
from src.config.constants import SHRINK_PRIOR

# All cells return 0.5 in Phase 1 (D-06). Structure ships now (D-07).
_PHASE_1_FLAT_CELL_VALUE: Final[float] = 0.5

@dataclass(frozen=True, slots=True)
class RoundConclusionLookup:
    """Hierarchical fallback chain (DEC-007, roadmap §1.5).

    Phase 1: every cell returns 0.5 regardless of key. The shape is fixed so
    Phase 2 can drop in calibrated cells without changing the consumer interface.
    """
    cells_full: dict[tuple[int, bool, str, str, str], _Cell]      # (numerical_diff, bomb, side, econ_bucket, map)
    cells_no_econ: dict[tuple[int, bool, str, str], _Cell]        # (numerical_diff, bomb, side, map)
    cells_no_map: dict[tuple[int, bool, str], _Cell]              # (numerical_diff, bomb, side)
    cells_minimal: dict[tuple[int, bool], _Cell]                  # (numerical_diff, bomb)
    side_baseline: dict[str, float]                               # 'atk' | 'def' → baseline

    def lookup(
        self,
        numerical_diff: int,
        bomb_planted: bool,
        side: str,
        econ_bucket: str,
        map_name: str,
    ) -> float:
        """Phase 1: always returns 0.5. Phase 2: shrinks cell→parent→...→side baseline."""
        # Structure shipped; cells empty.
        return _PHASE_1_FLAT_CELL_VALUE


@dataclass(frozen=True, slots=True)
class _Cell:
    """Bayesian-shrinkage cell (Phase 2 will populate)."""
    n: int                # observed sample size in this cell
    p_hat: float          # observed P(A wins round) in this cell
    parent_p: float       # parent-cell estimate for shrinkage

    def shrunk(self) -> float:
        """`(n * p_hat + SHRINK_PRIOR * parent_p) / (n + SHRINK_PRIOR)`.

        Source: `reference/theo_engine.py:_get_rate` (lines 84-102) — same formula
        as the half-win-rate Bayesian shrinkage, applied per cell. Reusing
        `SHRINK_PRIOR=15.0` per Claude's-discretion guidance in CONTEXT.md.
        """
        return (self.n * self.p_hat + SHRINK_PRIOR * self.parent_p) / (self.n + SHRINK_PRIOR)
```

**Construction:** `RoundConclusionLookup` is built once at module import with empty `cells_*` dicts. The `lookup` method short-circuits to `0.5` in Phase 1. When Phase 2 populates cells (via JSON-deserialized round-event data), `lookup` walks the fallback chain:

```python
def lookup(self, numerical_diff, bomb_planted, side, econ_bucket, map_name) -> float:
    # Phase 2 logic (Phase 1 just returns 0.5):
    key5 = (numerical_diff, bomb_planted, side, econ_bucket, map_name)
    if key5 in self.cells_full:
        return self.cells_full[key5].shrunk()
    key4 = (numerical_diff, bomb_planted, side, map_name)
    if key4 in self.cells_no_econ:
        return self.cells_no_econ[key4].shrunk()
    key3 = (numerical_diff, bomb_planted, side)
    if key3 in self.cells_no_map:
        return self.cells_no_map[key3].shrunk()
    key2 = (numerical_diff, bomb_planted)
    if key2 in self.cells_minimal:
        return self.cells_minimal[key2].shrunk()
    return self.side_baseline.get(side, 0.5)
```

**Phase 1 acceptance:** the function exists, the type signature is locked, the `lookup` returns 0.5 for every input. The Phase-2 population path is sketched-but-unused.

### §7. DP-mass-weighted confidence

**Decision:** `confidence` aggregates per-map data weights weighted by `P(map m is reached AND decisive | current state)`, computed via a single forward pass over the DP table.

```python
# src/pricing/live_theo.py (helper)
def _compute_confidence(
    root: BO3State,
    map_pool: tuple[str, ...],
    team_a: str,
    team_b: str,
    half_rates: HalfRates,
    dp_terminal_distribution: dict[BO3State, float],  # from forward pass
) -> float:
    """Per-map data_w, weighted by DP-mass on (map m reached & decisive)."""
    confidence = 0.0
    total_weight = 0.0
    for map_idx, map_name in enumerate(map_pool):
        # P(map_idx is played AND decides anything | current state)
        # = sum of dp_mass over states where this map's outcome was the deciding one
        weight_m = sum(
            mass for state, mass in dp_terminal_distribution.items()
            if state.map_idx == map_idx  # this map was reached
        )
        dw_m = data_weight_for_map(team_a, team_b, map_name, half_rates)
        confidence += weight_m * dw_m
        total_weight += weight_m
    if total_weight == 0.0:  # shouldn't happen but defensive
        return 0.0
    return confidence / total_weight
```

**Concrete formula for `P(map m reached and decisive)`:**
- "Reached" = state with `state.map_idx == m` is reachable from the root with non-zero probability.
- "Decisive" = the DP terminal contributing mass to this map's bucket.
- **Cheap or expensive?** The forward pass is O(reachable states). Reachable BO3 states from any root: ≤ ~3000 (3 maps × 12×12 grid × 2 sides × small pistol-state branches). One forward pass per `live_theo` call. **Cheap.**

**Implementation strategy:** One forward pass that accumulates terminal-mass-by-map, reusing the same recursion engine but in "forward-distribution" mode rather than "backward-value" mode. This is a separate recursive function `_dp_forward_distribution(state, round_p_fn) → dict[BO3State, float]` that returns probability mass at each terminal/decisive state. Cache it via `lru_cache` on `(state, round_p_id)` like `series_value`.

**Computational cost:** O(#reachable states) ≤ O(few thousand) per call. Well within latency budget.

### §8. Vega formula at every invocation

**Decision:** DEC-018 form, computed per-call, NOT cached:

```python
# src/pricing/live_theo.py (inside live_theo, after computing theo_series)
def _compute_vega(
    root: BO3State,
    round_p: float,
    round_p_fn: Callable[[BO3State], float],
) -> float:
    """vega = round_p × (theo_after_a_win - theo)² + (1-round_p) × (theo_after_b_win - theo)²"""
    state_a_wins = _advance_round(root, a_wins=True)
    state_b_wins = _advance_round(root, a_wins=False)
    theo = series_value(root, round_p_fn)
    theo_a = series_value(state_a_wins, round_p_fn)
    theo_b = series_value(state_b_wins, round_p_fn)
    return round_p * (theo_a - theo) ** 2 + (1.0 - round_p) * (theo_b - theo) ** 2
```

**Concrete meaning of "theo_after_a_win" and "theo_after_b_win":** They are `series_value(state_after_a_round_win)` and `series_value(state_after_b_round_win)` — i.e., the DP at the state where THIS round has been won by A (or B). Both are cached by `lru_cache`, so they're free if `series_value(root)` was already computed. (They will be — they were computed on the way to `theo` itself in the recursion.)

**At-OT-leaf vega:** When the root state is at `total=24`, the post-this-round states are `(state with a_round=13)` and `(state with b_round=13)` — both map terminals, both already in the cache. Same formula applies, no special-case needed.

### §9. DP cache strategy decision rule

**Decision:** Profile during Phase 1 implementation; default to `lru_cache(maxsize=None)`. Only ship `models/dp_table.pkl` if profiling shows the budget is breached.

**Profiling protocol:**
1. **Synthetic match replay:** in `tests/pricing/test_dp_perf.py` (or `scripts/profile_dp.py`), construct a sequence of `MatchState` snapshots representing a 24-round map (cold cache → 24 calls; warm cache → 24 cache-hits). Measure wall-clock per call.
2. **Round-by-round latency:** call `live_theo` after each synthetic state mutation. p50 and p99 across 24 rounds × 3 maps = 72 calls per match. Replay across 5 synthetic matches.
3. **Threshold:** if p99 latency on a cold first call > 100 ms (well below the 500 ms budget for the full pipeline; pricing is 1 of N stages), ship the pkl warm cache. Otherwise defer to Phase 5/6.

**`Callable` cache-key problem (and solution):** `lru_cache` cannot key on a `Callable` because callables aren't hashable in a stable way. Solution: maintain a module-level registry of round_p_fns, key the cache on a registered `int` ID:

```python
# src/pricing/dp.py
_ROUND_P_FNS: list[Callable[[BO3State], float]] = []

def _register_round_p_fn(fn: Callable[[BO3State], float]) -> int:
    _ROUND_P_FNS.append(fn)
    return len(_ROUND_P_FNS) - 1

@functools.lru_cache(maxsize=None)
def _series_value_cached(state: BO3State, round_p_id: int) -> float:
    fn = _ROUND_P_FNS[round_p_id]
    # ... use fn(state) at recurrence ...
```

**Caveat:** Each `live_theo` call creates a new closure (via `_build_round_p_fn`), so each call gets a new `round_p_id` and a fresh cache slice. This is correct (different `MatchState` → different round_p closures) but means the cache only memoizes within a single `live_theo` call. For repeated calls on the same MatchState, the closure is recreated. **This is fine** because `live_theo` itself is called per state-update — different states warrant different round_p logic.

**Cache cardinality estimate:**
- BO3State fields: `map_idx ∈ {0,1,2}` (3) × `a_map_score ∈ {0,1}` (2; ≥2 is terminal) × `b_map_score ∈ {0,1}` (2) × `a_round ∈ {0..13}` (14) × `b_round ∈ {0..13}` (14) × `side_orient ∈ {a_atk, a_def}` (2) × `map_pool` (constant per call) × `pistol_winner_a` per map (≤ 3 maps × 3 states each) ≤ ~3 × 2 × 2 × 14 × 14 × 2 × 27 = **~63,500 reachable states max per call**, but most paths prune quickly (a_round + b_round ≤ 24 always, and many combinations are unreachable).
- Realistic reachable count: ~1000-3000 states per call.
- At ~100 bytes per entry (frozen dataclass with slots) → **~300 KB cache per call**. Trivial.
- **Cross-call sharing** would multiply this by ~50-100 calls/match → ~30 MB. Still trivial. The pkl warm cache (~10 MB per roadmap §1.1) is therefore likely **unnecessary** for performance, but useful for cold-start latency on first match of the day.

**Recommendation:** Ship `lru_cache(maxsize=None)` only in Phase 1. Add a profiling task to Plan 01-04 (or 01-05) that produces a single number (p99 cold-call latency); if > 100 ms, add a second task for `dp_table.pkl`. Otherwise defer.

### §10. `MatchState` Phase 1 stub field set

**Decision:** D-02's 13 fields are sufficient. Confirm `pistol_winner_a` is `dict[int, Optional[bool]]` keyed by map_idx (clearer than positional list in `MatchState`, even though `BO3State` uses tuple).

```python
# src/pricing/live_theo.py
@dataclass(frozen=True, slots=True)
class MatchState:
    """Phase 1 stub. Phase 3 (REQ-match-state-engine) replaces this with the
    full ingestion-driven version in src/state/match_state.py.

    Fields are the minimum live_theo needs. Do NOT add players_alive, ults,
    time_left_s, seq_id, or last_updated_ts here — those are Phase 3 concerns.
    """
    match_id: str
    team_a: str          # added — needed for half_rates lookup
    team_b: str          # added — needed for half_rates lookup
    map_pool: tuple[str, ...]
    map_idx: int
    a_map_score: int
    b_map_score: int
    a_round: int
    b_round: int
    side_orient: str                             # 'a_atk' | 'a_def' for current map
    map_side_orients: tuple[str, ...]            # added — starting side per map (Pitfall 6)
    pistol_winner_a: dict[int, Optional[bool]]   # map_idx → who-won-pistol (None pre-pistol)
    numerical_diff: int                          # for round_conclusion lookup
    bomb_planted: bool                           # for round_conclusion lookup
    side: str                                    # for round_conclusion lookup ('atk'|'def' from team A's perspective)
    econ_bucket: str                             # for round_conclusion lookup
```

**Notes on D-02 augmentations:**
- **`team_a`, `team_b` added** — D-02 has `match_id` but no team identifiers. `live_theo` needs them for `half_rates` lookup. **Open for planner: confirm this addition.**
- **`map_side_orients` added** — D-02 has `side_orient` (current map only). Per-map starting side is needed for the DP across map boundaries (Pitfall 6). **Open for planner: confirm this addition.**
- **`pistol_winner_a` as dict, not list** — dict survives the Phase 1 → Phase 3 stub→full transition more cleanly because Phase 3's `MatchState` is event-stream-driven (entries appear as pistols resolve). The `BO3State` conversion at the top of `live_theo` packs the dict into a tuple keyed by map_idx.

**Invariant for `pistol_winner_a` shape conversion (live_theo top):**
```python
def _bo3_state_from_match_state(ms: MatchState) -> BO3State:
    pistol_tuple = tuple(
        ms.pistol_winner_a.get(i)  # None if not yet set
        for i in range(len(ms.map_pool))
    )
    return BO3State(
        map_idx=ms.map_idx,
        a_map_score=ms.a_map_score,
        b_map_score=ms.b_map_score,
        a_round=ms.a_round,
        b_round=ms.b_round,
        side_orient=ms.side_orient,
        map_pool=ms.map_pool,
        pistol_winner_a=pistol_tuple,
    )
```

`map_side_orients` is read separately by `_advance_to_next_map` via closure capture — does not need to live in `BO3State` because all reachable states already carry their `side_orient`.

### §11. Property-test fixture sources

**Decision:** Use `reference/fair_value.py::_bo3_series_prob` directly as the closed-form fixture. The symmetric-input test bypasses the Bradley-Terry blend.

```python
# tests/pricing/test_dp.py
import math
from hypothesis import given, strategies as st
from reference.fair_value import _bo3_series_prob

from src.pricing.dp import series_value, BO3State

@given(p=st.floats(min_value=0.05, max_value=0.95))
def test_dp_symmetric_input_matches_closed_form(p: float) -> None:
    """When round_p is constant across all states, the DP value equals p²(3-2p)
    from fair_value._bo3_series_prob (closed-form IID BO3 series win)."""
    state = BO3State(
        map_idx=0, a_map_score=0, b_map_score=0,
        a_round=0, b_round=0, side_orient='a_atk',
        map_pool=('Lotus', 'Bind', 'Haven'),
        pistol_winner_a=(None, None, None),
    )
    constant_p = lambda _state: p
    actual = series_value(state, constant_p)
    expected = _bo3_series_prob(p)
    assert math.isclose(actual, expected, rel_tol=1e-9)
```

**Where does `round_p(a, b)` for the symmetric case come from?** It does NOT route through Bradley-Terry — the test passes `lambda _state: p` directly, bypassing `blend.round_p`. This is correct: the symmetric test isolates the DP recursion. Bradley-Terry symmetry is a separate property test in `test_blend.py`.

**Verification that `_bo3_series_prob` is the right fixture:**
- `reference/fair_value.py:79`: `def _bo3_series_prob(p: float) -> float: return p * p * (3 - 2 * p)` — this is `p²(3-2p)`. `[VERIFIED: reference/fair_value.py:77-79]`
- The closed form assumes IID maps, IID rounds within each map. The DP's symmetric input exactly matches this assumption. ✓
- Edge: at `p=0.5`, both should return 0.5. `_bo3_series_prob(0.5) = 0.25 * 2 = 0.5` ✓. The DP recursion at constant `p=0.5` also returns 0.5 (by symmetry). ✓

### §12. CON-no-magic-numbers compliance — new constants

**Decision:** Phase 1 needs **four** new constants in `src/config/constants.py`. Plan 01-XX should include a "constants extension" task (small) that lands these BEFORE the modules that use them.

| Proposed constant | Value | Used in | Source / Justification |
|--------------------|-------|---------|-------------------------|
| `CONVICTION_CLIP_LOW` | `0.01` | `live_theo.py` (final theo + each theo_map[i]) | DEC-012 / CON-conviction-clip / CLAUDE.md Critical Rule 6 |
| `CONVICTION_CLIP_HIGH` | `0.99` | `live_theo.py` (final theo + each theo_map[i]) | DEC-012 / CON-conviction-clip / CLAUDE.md Critical Rule 6 |
| `OT_TOTAL_HARDSTOP` | `24` | `dp.py` (OT leaf detection) | DEC-009 / CON-ot-hard-stop. Currently derivable as `REGULATION_HALF * 2`, but having an explicit named constant is clearer and makes the OT hard-stop searchable. **Alternative: define in dp.py as `Final[int] = REGULATION_HALF * 2` and skip constants.py.** — Planner's call. |
| `MIN_ROUNDS_FULL_WEIGHT` | `15` | `live_theo.py` (data weight) | Audit `theo_engine.py:36`. Salvage value for `_data_weight` formula (D-09). |
| `BT_BLEND_EPSILON` | `1e-6` | `blend.py` (clip on inputs) | CON-bradley-terry-formula explicitly specifies `[1e-6, 1-1e-6]` |

**Recommendation:** Land all five in a single commit before Plan 01-02 (blend.py) so all downstream modules import cleanly. Constants tests in `tests/config/test_constants.py` should add 5 new parametrized cases (the existing test file has 25 cases for the current 12 constants — pattern is established).

**Why not inline:** CLAUDE.md Critical Rule 12 + CON-no-magic-numbers explicitly forbid inlining. The Phase 0 verification (00-VERIFICATION.md) confirms the constants module is the single source of truth.

**Edge case:** `OT_TOTAL_HARDSTOP` is mathematically identical to `REGULATION_HALF * 2`. **Recommend NOT adding it as a constant** — instead, write the OT check as `if total == REGULATION_HALF * 2:` so the relationship is explicit. This keeps `constants.py` minimal and the math grounded. **Final list: 4 new constants** (`CONVICTION_CLIP_LOW`, `CONVICTION_CLIP_HIGH`, `MIN_ROUNDS_FULL_WEIGHT`, `BT_BLEND_EPSILON`).

### §13. `reference/theo_engine.py` salvage delta — line-level diff

| `theo_engine.py` lines | Verdict | Phase 1 destination | Notes |
|-------------------------|---------|---------------------|-------|
| 29-32 (`_DEFAULT_RATES_PATH`) | Skip | n/a | Path resolution is Phase 1's `live_theo.py` concern; rebuild as needed |
| 34-35 (`REGULATION_HALF`, `WIN_THRESHOLD`) | Already done | `src/config/constants.py:66, 73` | Phase 0 already imported these (verified) |
| 36 (`MIN_ROUNDS_FULL_WEIGHT = 15`) | **Move to constants** | `src/config/constants.py` (new) | Used by `_data_weight` salvage (D-09) |
| 37-38 (`SHRINK_PRIOR`, `SIGNAL_SCALE`) | Already done | `src/config/constants.py:44, 51` | Phase 0 already imported these |
| 41-51 (`_signal_strength`) | **DROP** | n/a | Audit triplet's inconsistent `signal_strength` was the bug class (PRD §12.2 #2). Kill it. |
| 58-78 (`TheoEngine.__init__` + JSON load) | Adapt | `live_theo.py` helper `HalfRates` class | Phase 1 reads `data/half_win_rates.json`. Schema verified: keys `team_map_side`, `league_map_side`, `overall_avg`. (Verified by reading `data/half_win_rates.json`.) |
| 84-102 (`_get_rate`) | **Salvage verbatim** (with re-typing for mypy strict) | `live_theo.py` helper or new `_rates.py` | Bayesian shrinkage formula is correct; reuse |
| 104-129 (`_data_weight`) | **Salvage verbatim** (per D-09) | `live_theo.py` helper | Powers confidence (§7) |
| 131-140 (`preferred_side`) | Skip | n/a | Veto modeling is Phase 3+ |
| 146-162 (`_round_win_prob`) | **DROP** | n/a | Uses arithmetic-mean blend (PRD §12.2 #4 bug). Replaced by `blend.round_p`. |
| 162 (clip `[0.05, 0.95]`) | **DROP** | n/a | Replaced by `[0.01, 0.99]` (DEC-012) |
| 168-206 (`_markov_map_win`) | **Adapt with bug fixes** | `dp.py::series_value` — but see §2 | Loop *structure* sound (lines 168, 175-177, 196-204). Lines 179-194 are the bug class: (a) `range(WIN_THRESHOLD * 2) = range(26)` runs PAST `total=24` — fix to hard-stop; (b) `if total < REGULATION_HALF: p = p1` else `p = p2` — replace with `p = round_p_fn(state)` per-round. Lines 196-204 (state advance) generalize cleanly to BO3State. |
| 208-219 (`map_win_prob`) | **DROP** | n/a | Subsumed by `series_value` over single-map BO3State (or just one map of BO3) |
| 225-252 (`model_series_prob`) | **DROP** | n/a | The "p1*p2 + p1*(1-p2)*p3 + (1-p1)*p2*p3" formula in line 250 is the IID BO3 closed form — replaced by single DP that doesn't assume IID across maps |
| 258-275 (`_solve_map_win_prob`) | Skip | n/a | Already exists in `reference/fair_value.py::map_prob_from_series`. Use that one if needed (Phase 4 quoting may need it; Phase 1 doesn't). |
| 281-328 (`series_theo`) | **DROP** (per DEC-010) | n/a | One of the three audit entry points — killed |
| 330-384 (`series_theo_from_map_probs`) | **DROP** (per DEC-010) | n/a | Second audit entry point + has the `0.5`-vs-`fallback_q` docstring drift bug (PRD §12.2 #1) |
| 390-426 (`series_theo_no_sides`) | **DROP** (per DEC-010) | n/a | Third audit entry point + averages atk/def starting sides (PRD §12.2 #6 bug) |

**Summary table:**
- **Salvage verbatim:** `_get_rate` (lines 84-102), `_data_weight` (lines 104-129)
- **Adapt with bug fixes:** `_markov_map_win` structure (lines 168-206) → `series_value` per §2
- **Move constants:** `MIN_ROUNDS_FULL_WEIGHT` (line 36) → `src/config/constants.py`
- **Drop entirely:** `_signal_strength`, `_round_win_prob`, `map_win_prob`, `model_series_prob`, all three `series_theo*` functions

---

## Common Pitfalls

(Already documented above in the dedicated section — referencing here for completeness.)

---

## Assumptions Log

The following claims in this research are tagged `[ASSUMED]` and should be confirmed by the planner before being baked into a plan:

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `frozen=True` dataclass with `slots=True` is the right choice over `NamedTuple` for `BO3State`. | §1, Standard Stack alternatives | Low — both are hashable and work with `lru_cache`. Switching is a 5-line refactor. |
| A2 | The `_bo3_series_prob(p)` closed form `p²(3-2p)` is the correct fixture for the symmetric-input DP test. | §11 | Low — verified algebraically (IID BO3, identical maps, identical rounds). |
| A3 | A single forward pass over the DP is sufficient to compute `P(map m reached & decisive)` for all maps in `< 5 ms`. | §7 | Medium — depends on actual reachable-state count. If profiling shows > 5ms, fall back to closed-form: `weight_m = (probability map m is reached) × (probability map m is decisive given reached)`. |
| A4 | `team_a` and `team_b` should be added to the Phase 1 `MatchState` stub even though D-02 doesn't list them. | §10 | Low — `live_theo` needs them for `half_rates` lookup; trivial planner confirmation. |
| A5 | `map_side_orients: tuple[str, ...]` should be added to `MatchState` to handle map-boundary side flips. | §10, Pitfall 6 | Low — required to compute `_advance_to_next_map` correctly. |
| A6 | Rounds 3 and 15 use `GUN_WIN_RATE` identically to rounds 2 and 14 in Phase 1; Phase 2 will calibrate the differential. | §4 | Low — the structural dispatch is correct; only the rate value defers. |
| A7 | `OT_TOTAL_HARDSTOP` is best left as inline `REGULATION_HALF * 2` rather than a separate constant. | §12 | Trivial — naming preference only. |
| A8 | The pistol-round-1 input in Phase 1 should fallback to the regular `half_rates` blend (not GUN_WIN_RATE), pending Phase 2 calibrated pistol rates. | §4 | Medium — affects pistol-round-1 theo accuracy. Phase 2 will calibrate; Phase 1 ships the structurally-correct dispatch with degraded rate. |

If this table is empty: All claims in this research were verified or cited — no user confirmation needed.

(Table is non-empty; the above 8 items need planner-confirmation as part of plan 01-XX scoping.)

---

## Open Questions

1. **Side orientation across map boundaries.**
   - What we know: Within a map, sides flip at round 13 (atk → def, or vice versa). Across maps, starting side is decided by veto, not deterministic.
   - What's unclear: Does the Phase 1 stub `MatchState` carry per-map starting sides? D-02 lists `side_orient` (singular, current map). Pitfall 6 raises this.
   - Recommendation: Plan 01-XX adds `map_side_orients: tuple[str, ...]` to MatchState (per A5 in Assumptions Log). Phase 3's full MatchState will retain this field.

2. **`half_win_rates.json` access pattern.**
   - What we know: File schema is `{team_map_side, league_map_side, overall_avg, ...}`; loaded once via `json.load`.
   - What's unclear: Is `half_rates` instantiated once (module-level singleton) or passed into `live_theo` each call? If singleton, what's the test-isolation strategy?
   - Recommendation: `HalfRates` dataclass with explicit `from_json(path)` classmethod; instantiated by the caller (Phase 4 quoter) and passed into `live_theo`. Tests construct synthetic `HalfRates`. Avoids global state.

3. **Pistol-round-1 input source for Phase 1.**
   - What we know: DEC-011 / roadmap §1.3 says rounds 1, 13 should use `match_round_data` filtered to pistol rounds. `match_round_data` is Phase 2's deliverable, not Phase 1.
   - What's unclear: What probability does Phase 1 emit for round 1? Options: (a) regular half_win_rate via `blend.round_p`, (b) flat 0.5, (c) `GUN_WIN_RATE`-like assumption.
   - Recommendation: Option (a) — use the standard half_win_rate blend for round 1 in Phase 1, with a `# TODO Phase 2: replace with pistol-only rate` comment. Phase 2's calibration will swap in the per-team pistol rate without changing the call shape.

4. **`econ_bucket` source in Phase 1.**
   - What we know: D-02 lists `econ_bucket` as a `MatchState` field; CON-economy-buckets defines the four labels {full, semi-buy, semi-eco, eco}.
   - What's unclear: How does Phase 1 derive `econ_bucket` if Phase 3 hasn't built ingestion? Does Phase 1 just accept whatever the test fixture provides?
   - Recommendation: Phase 1 treats `econ_bucket` as opaque input (whatever the caller provides). It only flows into `round_conclusion.lookup`, which returns 0.5 in Phase 1 anyway. **No Phase 1 logic depends on the bucket value** — it's purely a Phase 2-onwards consumer. Test fixtures can use `'full'` everywhere.

---

## Environment Availability

Phase 1 has no external tool/service dependencies beyond the Python 3.11 toolchain that Phase 0 already installed and verified.

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Python 3.11 | All Phase 1 modules | ✓ | 3.11 (pinned via `.python-version`) `[VERIFIED: 00-VERIFICATION.md]` | — |
| `uv` | dependency mgmt + run | ✓ | 0.11.8 `[VERIFIED: STATE.md]` | — |
| `pytest` | tests | ✓ | 9.0.3 `[VERIFIED: 00-VERIFICATION.md]` | — |
| `hypothesis` | property tests | ✓ | 6.152.4 `[VERIFIED: 00-VERIFICATION.md]` | — |
| `mypy` | strict type-check | ✓ | 1.20.2 `[VERIFIED: 00-VERIFICATION.md]` | — |
| `ruff` | lint+format | ✓ | 0.15.12 `[VERIFIED: 00-VERIFICATION.md]` | — |
| `data/half_win_rates.json` | live_theo per-team rates | ✓ | 66KB file, schema verified `[VERIFIED: data inspection]` | If missing for a team/map: audit-engine fallback chain (team→league→overall_avg=0.5) |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** None.

Phase 1 is fully self-contained on the existing Phase 0 toolchain.

---

## Validation Architecture

`workflow.nyquist_validation` is not explicitly disabled in `.planning/config.json`; treating as enabled.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 + hypothesis 6.152.4 (already in `pyproject.toml`) |
| Config file | `pyproject.toml [tool.pytest.ini_options]` (already in place from Phase 0) |
| Quick run command | `uv run pytest tests/pricing/ -x` |
| Full suite command | `uv run pytest` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REQ-bo3-dp-engine | DP value ∈ [0,1]; symmetric input → `p²(3-2p)` | property | `uv run pytest tests/pricing/test_dp.py -x` | ❌ Wave 0 |
| REQ-bradley-terry-blend | Three unit cases; symmetry | unit + property | `uv run pytest tests/pricing/test_blend.py -x` | ❌ Wave 0 |
| REQ-pistol-anti-eco-modeling | Round-num dispatch correct; pistol_winner_a fallthrough; GUN_WIN_RATE wired | unit | `uv run pytest tests/pricing/test_round_types.py -x` | ❌ Wave 0 |
| REQ-ot-handling | DP returns coinflip leaf at total=24; never iterates past | unit + property | `uv run pytest tests/pricing/test_dp.py::test_ot_hardstop -x` | ❌ Wave 0 |
| REQ-round-conclusion-lookup | Skeleton returns 0.5 on every input; signature matches DEC-007 chain | unit | `uv run pytest tests/pricing/test_round_conclusion.py -x` | ❌ Wave 0 |
| REQ-canonical-live-theo | Single import surface `from src.pricing.live_theo import live_theo, TheoOutput` | unit | `uv run pytest tests/pricing/test_live_theo.py::test_import_surface -x` | ❌ Wave 0 |
| REQ-theo-series-output | `theo_series ∈ [0, 1]`; equals DP value at root | unit + property | `uv run pytest tests/pricing/test_live_theo.py::test_theo_series_range -x` | ❌ Wave 0 |
| REQ-theo-map-output | `theo_map[i] ∈ [0, 1]`; consistent with theo_series | unit + property | `uv run pytest tests/pricing/test_live_theo.py::test_theo_map_consistency -x` | ❌ Wave 0 |
| REQ-confidence-output | confidence ∈ [0, 1]; DP-mass-weighted aggregate | unit | `uv run pytest tests/pricing/test_live_theo.py::test_confidence_range -x` | ❌ Wave 0 |
| REQ-vega-output | `vega = round_p × (theo_a − theo)² + (1-round_p) × (theo_b − theo)²` | unit | `uv run pytest tests/pricing/test_live_theo.py::test_vega_formula -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/pricing/<file>.py -x` (≤ 1s per file)
- **Per wave merge:** `uv run pytest tests/pricing/ -x` (≤ 5s for full pricing tests)
- **Phase gate:** `uv run pytest && uv run mypy --strict src/pricing/ && uv run ruff check .` (all green before `/gsd-verify-work`)

### Wave 0 Gaps
- [ ] `tests/pricing/__init__.py` — package marker
- [ ] `tests/pricing/conftest.py` — shared fixtures (synthetic `MatchState`, synthetic `HalfRates`, synthetic `BO3State`)
- [ ] `tests/pricing/test_blend.py` — REQ-bradley-terry-blend
- [ ] `tests/pricing/test_round_types.py` — REQ-pistol-anti-eco-modeling
- [ ] `tests/pricing/test_dp.py` — REQ-bo3-dp-engine + REQ-ot-handling
- [ ] `tests/pricing/test_round_conclusion.py` — REQ-round-conclusion-lookup (skeleton)
- [ ] `tests/pricing/test_live_theo.py` — REQ-canonical-live-theo, REQ-theo-*-output, REQ-confidence-output, REQ-vega-output

Test framework already installed (Phase 0). Pricing-test directory needs to be created in Wave 0 of Phase 1.

---

## Security Domain

Phase 1 is pure-math computational logic with **no auth, no network, no user input, no PII, no secrets, no DB**. Per ASVS, the only relevant category is V5 (input validation), which is enforced by `mypy --strict` typing on `MatchState` fields.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | n/a — no auth in pricing layer |
| V3 Session Management | no | n/a — no sessions |
| V4 Access Control | no | n/a — library module, not a service |
| V5 Input Validation | yes | `@dataclass(frozen=True)` + `mypy --strict` on all field types; runtime validation for `pistol_winner_a` shape, `side_orient ∈ {'a_atk','a_def'}`, etc. |
| V6 Cryptography | no | n/a — no crypto |

### Known Threat Patterns for Python pricing math layer

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Numerical overflow / NaN propagation | Tampering (output corruption) | Input clipping to `[BT_BLEND_EPSILON, 1-BT_BLEND_EPSILON]` in `blend.py`; final clip to `[CONVICTION_CLIP_LOW, CONVICTION_CLIP_HIGH]` in `live_theo.py`; assert NaN-free in property tests |
| Cache poisoning via hash collision | Tampering | Frozen dataclass auto-derives `__hash__` from `__eq__`; immutable inputs only |
| Incorrect type allowed at runtime (e.g., string where int expected, bypassing mypy) | Tampering | `mypy --strict` blocks at compile time; runtime check `isinstance` at the public `live_theo(state: MatchState)` boundary; `@dataclass(frozen=True)` prevents post-construction mutation |

The security domain for Phase 1 is essentially "input-validation discipline at the pricing-API boundary." That's already covered by the strict-typing constraint Phase 0 wired in.

---

## Sources

### Primary (HIGH confidence)
- `prd.md` (root) — full design doc, §2 (output contract), §6 (canonical entry point), §12.2 (four bugs), §12.3 (audited-engine triplet to NOT recreate)
- `roadmap.md` (root) — §1.1–1.6 (every Phase 1 module), §0.4 (domain constants)
- `CLAUDE.md` (root) — Critical Rules 1, 3, 5, 6, 11, 12 (single canonical, BT, OT hardstop, clips, mypy strict, no magic numbers)
- `.planning/PROJECT.md` `<decisions>` — DEC-002, DEC-003, DEC-007, DEC-009, DEC-010, DEC-011, DEC-012, DEC-013, DEC-016, DEC-018
- `.planning/REQUIREMENTS.md` — all 11 Phase-1 REQs (REQ-bo3-dp-engine, REQ-bradley-terry-blend, REQ-pistol-anti-eco-modeling, REQ-ot-handling, REQ-round-conclusion-lookup, REQ-canonical-live-theo, REQ-theo-series-output, REQ-theo-map-output, REQ-confidence-output, REQ-vega-output, REQ-end-to-end-latency)
- `.planning/intel/constraints.md` — CON-mypy-strict-pricing, CON-no-magic-numbers, CON-single-canonical-live-theo, CON-bo3-dp-signature, CON-bradley-terry-formula, CON-conviction-clip, CON-ot-hard-stop, CON-domain-constants-baseline, CON-theo-output-schema, CON-round-conclusion-fallback-chain
- `.planning/phases/01-core-pricing-engine/01-CONTEXT.md` — D-01 through D-16 (16 user decisions)
- `.planning/phases/00-foundation/00-VERIFICATION.md` — Phase 0 toolchain confirmed
- `reference/theo_engine.py` — DP skeleton salvage source (DEC-013), inspected end-to-end
- `reference/fair_value.py` — closed-form `p²(3-2p)` for property tests, inspected end-to-end
- `reference/odds_utils.py` — salvage as-is (not consumed Phase 1)
- `src/config/constants.py` — Phase 0 output, all 12 baseline constants verified
- `src/pricing/__init__.py` — Phase 0 placeholder (empty docstring); Phase 1 adds modules
- `pyproject.toml` — `[[tool.mypy.overrides]] module = "src.pricing.*" strict = true` verified
- `data/half_win_rates.json` — schema inspected (`team_map_side`, `league_map_side`, `overall_avg`, `min_rounds_threshold`, `maps_in_data`, `event_weights`)

### Secondary (MEDIUM confidence)
- Python 3.11 stdlib docs (verified through training cutoff): `functools.lru_cache(maxsize=None)`, `dataclasses.dataclass(frozen=True, slots=True)`, `typing.Final`, `typing.Callable`, `typing.Optional` — all are stable APIs `[CITED: docs.python.org/3.11/library/]`
- pytest 8/9 + hypothesis 6 conventions (verified by Phase 0 test files at `tests/test_main.py` and `tests/config/test_constants.py`) — strategy patterns and property-test idioms

### Tertiary (LOW confidence)
- None. Every recommendation in this research traces to either a locked decision, the salvage source, a verified Phase 0 artifact, or stable Python 3.11 stdlib semantics.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — Python 3.11 stdlib only; no library version risk
- Architecture (DP shape, BT blend, OT leaf): HIGH — every choice traces to a locked DEC or CON
- `confidence` formula (DP-mass-weighted): MEDIUM — D-08 specifies the semantics but the "P(map m reached & decisive)" forward-pass computation has implementation latitude; A3 in Assumptions Log
- Salvage delta: HIGH — every line of `reference/theo_engine.py` was inspected and classified
- New constants list: HIGH — each is required by an explicit DEC or CON
- Cache cardinality estimate: MEDIUM — order-of-magnitude analysis; profile-and-confirm is in §9
- Pitfalls: HIGH — derived from explicit audit bugs (PRD §12.2) plus standard Python pitfalls

**Research date:** 2026-04-27
**Valid until:** 2026-05-27 (30 days — stable; no fast-moving deps; locked decisions are stable; only revalidate if PROJECT.md DECs change or roadmap.md is rewritten)
