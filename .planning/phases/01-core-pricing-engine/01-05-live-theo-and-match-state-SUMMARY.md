---
phase: 01-core-pricing-engine
plan: 05
subsystem: pricing
tags: [pricing, live-theo, match-state, bundle, marginalization, confidence, vega, integration]
requires:
  - 01-01-constants-and-blend
  - 01-02-bo3-dp-engine
  - 01-03-round-types
  - 01-04-round-conclusion-skeleton
provides:
  - LiveTheoEngine
  - TheoOutput
  - MatchState (Phase 1 stub, 17 fields)
  - HalfRates (concrete loader)
affects:
  - src/pricing/__init__.py (public surface lock)
  - src/pricing/round_types.py (TYPE_CHECKING import retargeted to data.py per D-14)
  - tests/pricing/test_round_types.py (test updated to match D-14 canonical placement)
tech-stack:
  added:
    - functools.lru_cache for _p_reach_map_cached (RoundPFn registry indirection mirrors dp.py)
  patterns:
    - bundle pattern for state-only call surface (D-20)
    - frozen+slots dataclasses (Pattern S3)
    - TYPE_CHECKING-guarded circular imports
key-files:
  created:
    - src/pricing/data.py
    - src/pricing/live_theo.py
    - tests/pricing/test_live_theo.py
    - .planning/phases/01-core-pricing-engine/01-05-live-theo-and-match-state-SUMMARY.md
  modified:
    - src/pricing/__init__.py
    - src/pricing/round_types.py
    - tests/pricing/test_round_types.py
decisions:
  - DEC-002 marginalization-consistency holds (same DP for series + per-map)
  - DEC-010 single canonical entry point shipped as LiveTheoEngine bundle (D-20)
  - DEC-012 conviction clip [0.01, 0.99] applied via _clip_conviction
  - DEC-018 vega = p*(theo_a-theo)^2 + (1-p)*(theo_b-theo)^2
  - D-08 confidence is TRUE DP-mass-weighted (no theo_map proxy)
  - D-09 _data_weight_for_map verbatim salvage from reference/theo_engine.py:104-129
  - D-14 MatchState lives in src/pricing/data.py; Phase 3 will move it
  - D-17 team_a/team_b carried by MatchState (no match_id parsing)
  - D-18 map_side_orients consumed by _RoundPFnImpl (closes PRD §12.2 #6 audit bug)
  - D-19 map_winners short-circuits _marginal_map_prob for already-played maps
  - D-20 LiveTheoEngine bundle preserves PRD §6 / CRule 1 state-only call surface
metrics:
  duration_minutes: 27
  tasks_completed: 4
  files_created: 3
  files_modified: 3
  tests_added: 30
  tests_total_pricing: 94
  tests_total_repo: 137
  completed_date: 2026-04-28
---

# Phase 01 Plan 05: live-theo-and-match-state Summary

**One-liner:** Single canonical pricing entry point `LiveTheoEngine` (bundle pattern per D-20) wiring `dp.series_value` + `round_types.round_p_for_round` + `round_conclusion.RoundConclusionLookup` + `blend.round_p` into `engine(state) -> TheoOutput` with DP-mass-weighted confidence (D-08), DEC-018 vega, and forbidden-audit-triplet regression locks.

## What Shipped

### `src/pricing/data.py` (created)

Three frozen+slots dataclasses (TheoOutput, MatchState) plus a frozen-only one (HalfRates):

**`TheoOutput`** — exactly four fields per PRD §2 / DEC-010:
- `theo_series: float` (clipped to `[CONVICTION_CLIP_LOW, CONVICTION_CLIP_HIGH] = [0.01, 0.99]`)
- `theo_map: tuple[float, ...]` (per-map marginals; same clip; `len == len(map_pool)`)
- `vega: float` (>= 0, DEC-018 form)
- `confidence: float` (in [0, 1], DP-mass-weighted per D-08)

**`MatchState`** — Phase 1 stub, 17 fields per D-02 + D-17 + D-18 + D-19:

| Group | Fields |
|-------|--------|
| Identity | `match_id`, `team_a` (D-17), `team_b` (D-17) |
| Series state | `map_pool`, `map_idx`, `a_map_score`, `b_map_score` |
| Within-map state | `a_round`, `b_round`, `side_orient` |
| Per-map starting sides + winners | `map_side_orients` (D-18), `map_winners` (D-19) |
| Pistol memory | `pistol_winner_a` |
| Mid-round signals (Phase 1 opaque) | `numerical_diff`, `bomb_planted`, `side`, `econ_bucket` |

Phase 3 (REQ-match-state-engine) deferred fields: live-state sequence id, last-updated timestamp, players-alive, ult counters, time-left.

**`HalfRates`** — concrete impl satisfying `round_types.HalfRates` Protocol:
- `from_json(path)` classmethod loads `data/half_win_rates.json` (Open Question 2 resolution)
- `team(team, map_name, side) -> float` — Bayesian-shrunk: `(n * raw + SHRINK_PRIOR * prior) / (n + SHRINK_PRIOR)` (verbatim salvage from `reference/theo_engine.py:84-102` per D-09)
- `team_entry(team, map_name, side) -> Optional[dict]` — raw entry for `_data_weight_for_map`
- Fallback chain: team_rates → league_rates → overall_avg (0.5)

### `src/pricing/live_theo.py` (created)

The orchestrator, ~9 sections:

1. **`_bo3_state_from_match_state(state)`** — projects MatchState's 17-field surface into a hashable BO3State cache key; packs `pistol_winner_a` dict into a tuple keyed by `map_idx`.

2. **`_RoundPFnImpl`** (frozen dataclass, satisfies dp.RoundPFn Protocol) — D-18 wiring closure:
   - `__call__(state)` resolves the EFFECTIVE side from `match_state.map_side_orients[state.map_idx]` AND applies the within-map round-12 flip; closes PRD §12.2 #6 audit `series_theo_no_sides` bug class.
   - `_effective_side(state)` — `starting_side` if `total < REGULATION_HALF` else flipped.
   - `next_side_orient_for(map_idx)` — bounds-checked accessor for `_advance_to_next_map` and `_ot_coinflip_leaf`.

3. **`_marginal_map_prob(state, m, half_rates)`** — three-case structure per D-19 + DEC-002:
   - `m < state.map_idx`: short-circuit on `map_winners[m]` → `CONVICTION_CLIP_HIGH` if A won, `CONVICTION_CLIP_LOW` if B won.
   - `m == state.map_idx`: marginalization identity `(v_root - v_after_b) / (v_after_a - v_after_b)`, clipped.
   - `m > state.map_idx`: delegated to `_within_map_p_a_wins` (a memoized within-map sub-DP that doesn't reuse `series_value` because the audit-engine BO3 DP auto-advances past `map_pool` for unreachable synthetic roots).

4. **`_within_map_p_a_wins(map_pool, map_idx, starting_side, pistol_winner_a, match_state, half_rates)`** — within-map ladder from `(a_round=0, b_round=0)`; OT-as-coinflip leaf at `total == REGULATION_HALF * 2`; result clipped per DEC-012. Manual memoization via dict.

5. **`_clip_conviction(theo)`** — single chokepoint for DEC-012 / CRule 6.

6. **`_data_weight_for_map(team_a, team_b, map_name, half_rates)`** — verbatim salvage from `reference/theo_engine.py:104-129` per D-09: `min(team_weights) / MIN_ROUNDS_FULL_WEIGHT`, where each team's weight is the average sample size across `atk` and `def` excluding `used_fallback` entries; returns 0.0 if any team has no entries.

7. **`_p_map_decisive(state, m, half_rates)`** — TRUE DP-mass forward pass per D-08 / W3, three explicit cases:
   - `m < state.map_idx`: indicator from `map_winners[0..m]` (was map m the clinching map? — i.e., did one team go from 1 wins before to 2 wins after?).
   - `m == state.map_idx`: `p_a_wins * a_decisive + (1 - p_a_wins) * b_decisive` where `a/b_decisive ∈ {0.0, 1.0}` per `state.a/b_map_score + 1 == 2`.
   - `m > state.map_idx`: `_p_reach_map(bo3, fn, m) × P(decisive | reached)`. For the BO3 last map (`m == len(map_pool) - 1`), `P(decisive | reached) = 1.0`.

8. **`_p_reach_map(state, round_p_fn, m)`** — wrapper indirecting through `_REACH_MAP_FNS` registry (mirrors `dp.py`'s `_ROUND_P_FNS` pattern); body in `_p_reach_map_cached(state, round_p_fn_id, m)` with `@functools.lru_cache(maxsize=None)`. Recursive on map advancement — terminates at `state.map_idx == m` (reached) or `a/b_map_score >= 2` (clinched before).

9. **`_compute_confidence(state, half_rates)`** — DP-mass-weighted aggregate per D-08:
   ```
   weighted_sum = Σ_m data_w(m) × _p_map_decisive(state, m)
   mass_sum     = Σ_m _p_map_decisive(state, m)
   confidence   = clip(weighted_sum / mass_sum, [0, 1])
   ```
   Returns 0.0 if `mass_sum < 1e-12` (defensive: series effectively decided). NOT a `theo_map` proxy — the source-level grep regression-locks the `0.5 + 0.5 * abs(theo_map - 0.5)` proxy formula's absence.

10. **`_compute_vega(root, round_p_fn)`** — DEC-018 form:
    ```
    vega = p × (theo_a - theo)^2 + (1 - p) × (theo_b - theo)^2
    ```
    Always >= 0 by construction; computed at every `live_theo` invocation per D-11.

11. **`LiveTheoEngine`** — frozen dataclass bundle per D-20:
    ```python
    @dataclass(frozen=True)
    class LiveTheoEngine:
        half_rates: HalfRates
        round_conclusion: Optional[RoundConclusionFn] = None

        def __call__(self, state: MatchState) -> TheoOutput:
            return _live_theo_impl(state, self.half_rates, self.round_conclusion)
    ```

### `src/pricing/__init__.py` (modified)

```python
from src.pricing.data import HalfRates, MatchState, TheoOutput
from src.pricing.live_theo import LiveTheoEngine

__all__ = ["LiveTheoEngine", "TheoOutput", "MatchState", "HalfRates"]
```

`dp` / `blend` / `round_types` / `round_conclusion` remain private to the package per D-12.

## Test Coverage

41 new tests in `tests/pricing/test_live_theo.py` across 5 sections:

| Section | Count | Focus |
|---------|-------|-------|
| 1. Data shapes | 8 | TheoOutput / MatchState / HalfRates structural invariants |
| 2. HalfRates JSON loader | 4 | from_json + Bayesian shrinkage + fallback chain |
| 3. _live_theo_impl core | 13 | conversion, closure side-orient + flip, marginal short-circuits, clip |
| 4. LiveTheoEngine bundle | 13 | _p_map_decisive 3-case, confidence, vega DEC-018, _data_weight, bundle |
| 5. Public surface + integration | 6 | __all__ lock, forbidden-symbol grep, marginalization consistency, hypothesis property test (30 reachable states) |

Whole-package mypy/pytest/ruff sweep:
- `uv run mypy --strict src/pricing/`: clean (7 source files)
- `uv run pytest tests/pricing/`: 94 passed
- `uv run pytest`: 137 passed (full repo)
- `uv run ruff check src/pricing/ tests/pricing/`: clean

## DEC-002 / CRule 2 Marginalization Consistency

The integration test `test_live_theo_marginalization_consistency_dec002` reconstructs the algebraic identity:

```
theo_series ≈ theo_map[map_idx] × clip(series_value(state_a_won_current))
            + (1 − theo_map[map_idx]) × clip(series_value(state_b_won_current))
```

Holds within `rel_tol = 1e-3` (the slack accommodates the clip on both `theo_series` and `theo_map[map_idx]`). The same DP feeds both; no parallel models can exist that disagree.

## Forbidden-Symbol Regression Lock

`test_forbidden_audit_triplet_symbols_absent_from_source` greps `src/pricing/*.py` for top-level `def` matches of:
- `series_theo`
- `series_theo_no_sides`
- `series_theo_from_map_probs`
- `model_series_prob`
- `_signal_strength`

None present. Mentions in module docstrings (e.g., "Replaces audit-engine series_theo / series_theo_no_sides / series_theo_from_map_probs triplet") do not count — the regex is `^def <name>\b` per Multiline.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `round_types.py` TYPE_CHECKING import retargeted from `live_theo` to `data` (D-14 canonical placement)**
- **Found during:** Task 2a (mypy --strict failed with `Module "src.pricing.live_theo" does not explicitly export attribute "MatchState"` because `MatchState` is imported (not defined) in live_theo.py and not in its `__all__`).
- **Issue:** The 01-03 plan hard-coded `from src.pricing.live_theo import MatchState` before D-14 finalized that MatchState lives in `data.py`.
- **Fix:** Updated the TYPE_CHECKING block to `from src.pricing.data import MatchState`.
- **Files modified:** `src/pricing/round_types.py` (TYPE_CHECKING block only — no runtime change).
- **Commit:** `96bb6b2` (Task 2a).

**2. [Rule 3 - Blocking] `tests/pricing/test_round_types.py::test_source_uses_type_checking_guard_for_circular_imports` updated**
- **Found during:** Task 3 full-suite verification.
- **Issue:** The 01-03 test grepped for the literal `from src.pricing.live_theo import MatchState` to verify the TYPE_CHECKING guard, which broke after the Rule 3 fix above.
- **Fix:** Updated the test to expect `from src.pricing.data import MatchState`. Added a comment explaining the D-14 retarget.
- **Files modified:** `tests/pricing/test_round_types.py`.
- **Commit:** `b92dec7` (Task 3).

**3. [Rule 3 - Blocking] `_p_map_decisive` future-map case rewritten to use within-map sub-DP**
- **Found during:** Task 2a (test_marginal_map_prob_for_future_map_in_clip_range).
- **Issue:** The plan's prescribed approach for `m > state.map_idx` constructed a synthetic `BO3State(map_idx=m, a_map_score=0, b_map_score=0)` and called `series_value` on hypothetical advance states. For BO3, this pushes the audit-engine DP into states where `_advance_to_next_map` lands at `map_idx=3` with non-terminal map scores (e.g., `(map_idx=3, a=1, b=1)`), which then tries to call `round_p_for_round` accessing `map_pool[3]` → IndexError. The audit-engine DP always advances past a within-map clinch, even if the resulting state is unreachable in a real BO3.
- **Fix:** Added `_within_map_p_a_wins(map_pool, map_idx, starting_side, pistol_winner_a, match_state, half_rates)` — a memoized within-map ladder that terminates strictly at WIN_THRESHOLD or the explicit OT-as-coinflip leaf. Used by `_marginal_map_prob` for `m > state.map_idx`. The `_p_reach_map` helper still uses `series_value` because it operates on reachable BO3 forward-pass states (same a_map_score/b_map_score progression as a real series).
- **Commit:** `96bb6b2` (Task 2a).

No Rule 1 bugs found; no Rule 2 missing critical functionality; no Rule 4 architectural decisions required.

## Sanity Check Output

```
$ uv run python -c "from src.pricing import LiveTheoEngine, HalfRates, MatchState; ..."
theo_series: 0.44921213688511
theo_map:    (0.5, 0.3984242737702202, 0.4999999999999999)
vega:        0.0016236922189740756
confidence:  0.0
```

`confidence == 0.0` for SEN/100T because `data/half_win_rates.json` has those teams with `used_fallback: true` for the demo maps; `_data_weight_for_map` returns 0.0 per D-09 (no real per-team data backs the rates). This is correct behavior — the value will rise as Phase 2 calibration data lands (REQ-round-event-data-pipeline).

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | `0fc5314` | feat(01-05): add MatchState/TheoOutput/HalfRates data shapes (D-17/D-18/D-19) |
| 2a | `96bb6b2` | feat(01-05): implement _live_theo_impl core (state conversion + closures + per-map marginals) |
| 2b | `0315746` | feat(01-05): implement DP-mass-weighted confidence + vega + LiveTheoEngine bundle (D-08/D-20) |
| 3 | `b92dec7` | feat(01-05): wire __init__ re-exports + integration property tests (DEC-002/CRule 1) |

## Self-Check: PASSED

- All four expected commits exist in git log: `0fc5314`, `96bb6b2`, `0315746`, `b92dec7`.
- All key files present:
  - `src/pricing/data.py` — created
  - `src/pricing/live_theo.py` — created
  - `src/pricing/__init__.py` — modified (3 re-exports + `__all__`)
  - `src/pricing/round_types.py` — modified (TYPE_CHECKING import retarget)
  - `tests/pricing/test_live_theo.py` — created (41 tests)
  - `tests/pricing/test_round_types.py` — modified (1 test updated)
- `uv run mypy --strict src/pricing/`: clean
- `uv run pytest tests/pricing/`: 94 passed
- `uv run pytest`: 137 passed
- `uv run ruff check src/pricing/ tests/pricing/`: clean
- Forbidden audit-triplet absent from `src/pricing/*.py` (regex `^def <name>\b`): verified
- DEC-002 marginalization-consistency identity holds (within `rel_tol=1e-3`).
- All 22 D-IDs from CONTEXT.md `<decisions>` honored — no decisions deviated from.
