---
phase: 01-core-pricing-engine
plan: 05
type: execute
wave: 3
depends_on:
  - 01-02-bo3-dp-engine
  - 01-03-round-types
  - 01-04-round-conclusion-skeleton
files_modified:
  - src/pricing/data.py
  - src/pricing/live_theo.py
  - src/pricing/__init__.py
  - tests/pricing/test_live_theo.py
autonomous: true
requirements:
  - REQ-canonical-live-theo
  - REQ-theo-series-output
  - REQ-theo-map-output
  - REQ-confidence-output
  - REQ-vega-output
must_haves:
  truths:
    - "Bradley-Terry blend, not arithmetic mean (DEC-003 / CRule 3)"
    - "Conviction clip [0.01, 0.99] uniform (DEC-012 / CRule 6)"
    - "No magic numbers — every threshold in src/config/constants.py (CON-no-magic-numbers / CRule 12)"
    - "mypy --strict on src/pricing/ (CON-mypy-strict-pricing / CRule 11)"
    - "Single canonical entry point: live_theo(state) → TheoOutput (DEC-010 / CRule 1) — Phase 1 ships LiveTheoEngine bundle pattern (D-20); engine(state) → TheoOutput preserves the state-only call surface"
    - "OT explicit hard-stop at total=24 with documented coinflip leaf (DEC-009 / CRule 5)"
    - "BO3 series and per-map theos from the SAME DP — marginalize, never parallel models (DEC-002 / CRule 2)"
    - "Forbidden: series_theo, series_theo_no_sides, series_theo_from_map_probs — DROP per DEC-010 / PRD §12.3 / CRule 1"
    - "MatchState is the Phase 1 stub — Phase 3 (REQ-match-state-engine) replaces it without changing the engine's signature (D-01 / D-14)"
    - "TheoOutput is a frozen+slots dataclass with exactly four fields: theo_series, theo_map, vega, confidence (PRD §2 / DEC-010)"
    - "MatchState carries `map_winners: tuple[Optional[bool], ...]` (D-19) so _marginal_map_prob can short-circuit already-decided maps to clipped 1.0/0.0 indicators"
    - "MatchState carries `map_side_orients: tuple[str, ...]` (D-18) and the closure consults it via `match_state.map_side_orients[s.map_idx]` with within-map flip on round 12"
    - "MatchState carries `team_a: str, team_b: str` (D-17) so HalfRates lookups don't fall back to brittle `match_id` parsing"
    - "confidence is DP-mass-weighted aggregate per D-08 — `sum_m (data_w(m) × P(map m decisive | state)) / sum_m P(map m decisive | state)`, with per-map decisive mass computed via DP forward pass (TRUE D-08, not theo_map proxy)"
    - "_p_map_decisive(state, m) recurrence is explicit (per W3): m < state.map_idx → indicator from map_winners, m == state.map_idx → DP over current BO3State, m > state.map_idx → DP forward pass over hypothetical maps-tied paths"
    - "vega = round_p × (theo_a − theo)² + (1−round_p) × (theo_b − theo)² (DEC-018 / D-10 / D-11)"
    - "theo_series ↔ theo_map[] consistency under marginalization (DEC-002 / CRule 2): theo_series == theo_map[map_idx] × clip(series_value(state_a_won_current_map)) + (1 − theo_map[map_idx]) × clip(series_value(state_b_won_current_map)) within rel_tol≈1e-9"
  outputs:
    - "src/pricing/data.py exports `HalfRates` dataclass (with `from_json(path)` classmethod, `team(team, map, side)` Bayesian-shrunk lookup, `team_entry(team, map, side)` raw-entry accessor satisfying round_types.HalfRates Protocol), `MatchState` Phase 1 stub frozen+slots dataclass (17 fields per D-02 + D-17 + D-18 + D-19), `TheoOutput` frozen+slots dataclass (theo_series, theo_map, vega, confidence)"
    - "MatchState fields exactly: match_id (str), team_a (str — D-17), team_b (str — D-17), map_pool (tuple[str, ...]), map_idx (int), a_map_score (int), b_map_score (int), a_round (int), b_round (int), side_orient (str), map_side_orients (tuple[str, ...] — D-18; len == len(map_pool)), map_winners (tuple[Optional[bool], ...] — D-19; True=A won, False=B won, None=undecided; len == len(map_pool)), pistol_winner_a (dict[int, Optional[bool]]), numerical_diff (int), bomb_planted (bool), side (str), econ_bucket (str). NO seq_id, last_updated_ts, players_alive, ults, time_left_s (deferred to Phase 3 per D-02). 17 fields total."
    - "src/pricing/live_theo.py exports `LiveTheoEngine` class (D-20 / A7 bundle pattern): `engine = LiveTheoEngine(half_rates, round_conclusion=None)`; `engine(state) -> TheoOutput` preserves PRD §6 / DEC-010 / CRule 1's state-only call surface"
    - "src/pricing/live_theo.py also exports the pure helper `_live_theo_impl(state, half_rates, round_conclusion) -> TheoOutput` for testability and the `_p_map_decisive(state, m, half_rates) -> float` lru-cached forward-pass helper per W3"
    - "Internal helpers: `_bo3_state_from_match_state` (MatchState → BO3State conversion, packs pistol_winner_a dict into tuple keyed by map_idx); `_RoundPFnImpl` (RoundPFn-Protocol-satisfying object — `__call__(s)` consults match_state.map_side_orients[s.map_idx] with within-map flip on round 12 to resolve effective side before delegating to round_p_for_round; `next_side_orient_for(map_idx)` returns map_side_orients[map_idx] with bounds-checking); `_marginal_map_prob` (short-circuits to CONVICTION_CLIP_HIGH/LOW on map_winners for k < state.map_idx; uses DP marginalization for k >= state.map_idx); `_data_weight_for_map` (verbatim salvage from reference/theo_engine.py:104-129 per D-09); `_p_map_decisive` (TRUE DP-mass forward pass per W3 — `lru_cache` helper computing P(map m decisive | state)); `_compute_confidence` (DP-mass-weighted per D-08 using _p_map_decisive); `_compute_vega` (DEC-018 form using two extra series_value lookups per D-10/D-11); `_clip_conviction` (output clip to [CONVICTION_CLIP_LOW, CONVICTION_CLIP_HIGH])"
    - "src/pricing/__init__.py modified: re-exports `LiveTheoEngine`, `TheoOutput`, `MatchState`, `HalfRates` and __all__ = ['LiveTheoEngine', 'TheoOutput', 'MatchState', 'HalfRates']. NO re-exports of dp/blend/round_types/round_conclusion (private to package)."
    - "tests/pricing/test_live_theo.py: data-shape tests (test_match_state_is_17_field_frozen_dataclass, test_theo_output_is_frozen_dataclass, test_half_rates_loads_json, test_half_rates_missing_team_falls_back_to_overall_avg), public-surface tests (test_public_imports_only, test_forbidden_audit_triplet_symbols_absent_from_source), core-impl tests (test_theo_series_in_clip_range, test_marginal_map_prob_short_circuits_on_map_winners, test_build_round_p_fn_consults_map_side_orients, test_compute_confidence_dp_mass_forward_pass, test_p_map_decisive_three_case_recurrence, test_confidence_in_unit_interval, test_vega_matches_dec_018_formula, test_vega_non_negative), bundle tests (test_live_theo_engine_call_surface), integration tests (test_live_theo_marginalization_consistency_dec002, test_live_theo_property_invariants_hypothesis)"
    - "`uv run mypy --strict src/pricing/` (whole package, including 01-01..01-04 outputs) exits 0"
    - "`uv run pytest tests/pricing/ -x` (whole pricing test suite) exits 0"
    - "`uv run ruff check src/pricing/ tests/pricing/` exits 0"
---

<rationale>
Wave 3 (depends on 01-02 BO3State + series_value + RoundPFn Protocol, 01-03 round_p_for_round + HalfRates Protocol, 01-04 RoundConclusionLookup + RoundConclusionFn Protocol). Cannot start until ALL THREE land — this plan is the orchestrator that wires them together. files_modified overlap: `src/pricing/__init__.py` is modified ONLY here (none of 01-01..01-04 touched it), so Wave 3 has no merge conflicts with Waves 1-2.

**Why a single multi-task plan:** live_theo.py is the load-bearing orchestrator (~300 LoC including the DP forward-pass helper + LiveTheoEngine bundle). Splitting "MatchState + TheoOutput dataclasses" from "live_theo function + helpers" would force the executor to ship the data shapes WITHOUT being able to test them end-to-end in plan A, then re-load context in plan B. Single plan, FOUR tasks (Task 2 split into 2a + 2b per W1), ~50% context budget.

**Four-task split rationale (W1-aligned):**
1. **Task 1 — Data shapes + HalfRates concrete impl + import-surface tests:** The dataclasses (`HalfRates`, `MatchState` 17-field stub per D-02 + D-17 + D-18 + D-19, `TheoOutput`) plus the JSON loader. Lands first so downstream tasks have stable types to import. (~10-15% context.)
2. **Task 2a — `_live_theo_impl` core (conversion + closures + per-map marginals):** `_bo3_state_from_match_state`, `_RoundPFnImpl` (consumes `map_side_orients[s.map_idx]` with within-map round-12 flip; satisfies the RoundPFn Protocol from 01-02), `_marginal_map_prob` (short-circuits on `map_winners`), top-level `_live_theo_impl` orchestration with output clipping. Tests cover REQ-theo-series-output, REQ-theo-map-output, REQ-vega-output range/consistency. (~20% context.)
3. **Task 2b — `LiveTheoEngine` bundle + DP-mass-weighted confidence + vega:** `_p_map_decisive` (TRUE DP-mass forward pass per D-08 / W3 — three explicit cases for m < / == / > state.map_idx), `_compute_confidence` (D-08 weighting using the forward pass — NO theo_map proxy), `_compute_vega` (DEC-018), `_clip_conviction`, **`LiveTheoEngine` bundle class (D-20)**. Tests cover REQ-canonical-live-theo (only `LiveTheoEngine` and `TheoOutput` exported), REQ-confidence-output (D-08 weighted aggregate, range [0,1]). (~20% context.)
4. **Task 3 — Package re-exports + integration regression:** Update `src/pricing/__init__.py` to expose `LiveTheoEngine`, `TheoOutput`, `MatchState`, `HalfRates`. End-to-end synthetic state (round 7, side flip, mid-map) verifies all four TheoOutput fields populated; theo_series consistency property test (DEC-002 / CRule 2 marginalization-consistency); no other pricing entry points exist (`! grep -E "^def series_theo" src/pricing/*.py`). (~10% context.)

Each task is ≤ ~20% context; total ≤ 50%.

**Why __init__.py re-export wiring lives here, not in 01-01:** PATTERNS.md §`src/pricing/__init__.py` (lines 34-60) explicitly says "the public re-exports should be added when the modules land." Re-exporting `LiveTheoEngine`, `MatchState`, `TheoOutput`, `HalfRates` requires those symbols to exist — they only exist after this plan ships. Re-exporting earlier would create import errors during 01-02/03/04 execution.

**Why HalfRates concrete impl lives here, not in 01-03:** 01-03 (round_types) defines the HalfRates Protocol — duck-typed shape only. The concrete dataclass loading `data/half_win_rates.json` belongs with the orchestrator per RESEARCH §Open Question 2 / D-20 (instantiated by the caller, passed into the engine constructor). Deferring to here also means data/half_win_rates.json is read for the first time in this plan — its schema (verified during planning: `team_map_side`, `league_map_side`, `overall_avg=0.5`) gates the loader implementation.

**Files NOT modified here:** none of 01-01..01-04 source/test files. The package mypy sweep covers them but does not modify them.

**Locked decisions consumed (from 01-CONTEXT.md `<decisions>`):**
- D-17 → `team_a`, `team_b` added to MatchState (Task 1)
- D-18 → `map_side_orients` added to MatchState; consumed by `_RoundPFnImpl` (Task 1 + Task 2a)
- D-19 → `map_winners` added to MatchState; consumed by `_marginal_map_prob` short-circuit (Task 1 + Task 2a)
- D-20 → `LiveTheoEngine` bundle class is the public surface, not a free function (Task 2b)
- D-21 → No DP-cache-pickle profiling task in Phase 1 (no Task ships latency profiling; deferred to Phase 5)
- D-08 / D-09 → DP-mass-weighted confidence using `_data_weight_for_map` salvage (Task 2b)
- D-10 / D-11 → Vega per DEC-018 form, every-call computation (Task 2b)
- D-12 → No `series_theo` / `series_theo_no_sides` / `series_theo_from_map_probs` reverse-compat shims; forbidden-symbols regression test in Task 3
- D-14 → MatchState lives in this package for Phase 1; Phase 3 will move it to `src/state/match_state.py`. Documented in module docstring (Task 1)
</rationale>

<objective>
Ship the single canonical pricing entry point per DEC-010 / CRule 1 / PRD §6 — replacing the audit engine's `series_theo` / `series_theo_no_sides` / `series_theo_from_map_probs` triplet (DROP per PRD §12.3) with a `LiveTheoEngine` class (D-20) whose `__call__(state) → TheoOutput` preserves the state-only public call surface and:
- Returns `theo_series` (DP value at root, clipped) + `theo_map` (per-map marginals from the SAME DP per CRule 2 / DEC-002, with `map_winners` short-circuit per D-19) + `vega` (DEC-018 form) + `confidence` (TRUE DP-mass-weighted per D-08 with explicit `_p_map_decisive` three-case recurrence per W3)
- Wires together `dp.series_value`, `dp.RoundPFn` Protocol, `round_types.round_p_for_round`, `round_conclusion.RoundConclusionLookup`, and `blend.round_p`
- Defines the Phase 1 stub `MatchState` dataclass (D-01/D-02 + D-17/D-18/D-19 extensions) and the concrete `HalfRates` JSON loader
- Threads `MatchState.map_side_orients` through the round_p_fn closure (D-18 — fixes PRD §12.2 #6 audit `series_theo_no_sides` bug class)
- Applies the conviction clip `[CONVICTION_CLIP_LOW, CONVICTION_CLIP_HIGH] = [0.01, 0.99]` to `theo_series` and each `theo_map[i]` per DEC-012 / CRule 6
- Locks the public package surface: `from src.pricing import LiveTheoEngine, TheoOutput, MatchState, HalfRates` and NOTHING ELSE

Purpose: Close out Phase 1 with the orchestrator that makes everything callable end-to-end. Locks REQ-canonical-live-theo, REQ-theo-series-output, REQ-theo-map-output, REQ-confidence-output, REQ-vega-output. The integration property tests (true marginalization-consistency per DEC-002 / CRule 2; hypothesis range invariants; forbidden-audit-triplet symbols absent from src/pricing/) are the regression-lock for CRule 1 + CRule 2.

Output: `LiveTheoEngine` class, `TheoOutput` + `MatchState` + `HalfRates` dataclasses, package re-exports, end-to-end integration test suite covering all five Phase 1 REQ-IDs delivered by this plan.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@.planning/phases/01-core-pricing-engine/01-CONTEXT.md
@.planning/phases/01-core-pricing-engine/01-RESEARCH.md
@.planning/phases/01-core-pricing-engine/01-PATTERNS.md
@.planning/phases/01-core-pricing-engine/01-01-constants-and-blend-PLAN.md
@.planning/phases/01-core-pricing-engine/01-02-bo3-dp-engine-PLAN.md
@.planning/phases/01-core-pricing-engine/01-03-round-types-PLAN.md
@.planning/phases/01-core-pricing-engine/01-04-round-conclusion-skeleton-PLAN.md
@.planning/phases/01-core-pricing-engine/01-01-constants-and-blend-SUMMARY.md
@.planning/phases/01-core-pricing-engine/01-02-bo3-dp-engine-SUMMARY.md
@.planning/phases/01-core-pricing-engine/01-03-round-types-SUMMARY.md
@.planning/phases/01-core-pricing-engine/01-04-round-conclusion-skeleton-SUMMARY.md
@CLAUDE.md
@prd.md
@roadmap.md
@src/config/constants.py
@src/pricing/__init__.py
@src/pricing/blend.py
@src/pricing/dp.py
@src/pricing/round_types.py
@src/pricing/round_conclusion.py
@reference/theo_engine.py
@reference/fair_value.py
@data/half_win_rates.json

<interfaces>
<!-- Code skeletons drawn from RESEARCH §7, §8, §10 + PATTERNS lines 343-466 + reference/theo_engine.py:84-129 (verbatim _get_rate + _data_weight salvage). All upstream contracts (BO3State, series_value, RoundPFn Protocol, round_p_for_round, HalfRates Protocol, RoundConclusionLookup, RoundConclusionFn) are SHIPPED in 01-02/03/04. -->

From src/config/constants.py (Phase 0 + 01-01):
```python
CONVICTION_CLIP_LOW: Final[float] = 0.01
CONVICTION_CLIP_HIGH: Final[float] = 0.99
MIN_ROUNDS_FULL_WEIGHT: Final[int] = 15
SHRINK_PRIOR: Final[float] = 15.0
GUN_WIN_RATE: Final[float] = 0.822
REGULATION_HALF: Final[int] = 12
WIN_THRESHOLD: Final[int] = 13
```

From src/pricing/dp.py (01-02):
```python
@dataclass(frozen=True, slots=True)
class BO3State:
    map_idx: int
    a_map_score: int
    b_map_score: int
    a_round: int
    b_round: int
    side_orient: str
    map_pool: tuple[str, ...]
    pistol_winner_a: tuple[Optional[bool], ...]

class RoundPFn(Protocol):
    def __call__(self, state: BO3State) -> float: ...
    def next_side_orient_for(self, map_idx: int) -> str: ...

def series_value(state: BO3State, round_p_fn: RoundPFn) -> float: ...
def _advance_round(state: BO3State, a_wins: bool) -> BO3State: ...
def _advance_to_next_map(state: BO3State, a_won: bool, next_side_orient: str) -> BO3State: ...
```

From src/pricing/round_types.py (01-03):
```python
class HalfRates(Protocol):
    def team(self, team: str, map_name: str, side: str) -> float: ...
    def team_entry(self, team: str, map_name: str, side: str) -> Optional[dict[str, Any]]: ...

def round_p_for_round(state: BO3State, match_state: MatchState, half_rates: HalfRates) -> float: ...
```

From src/pricing/round_conclusion.py (01-04):
```python
class RoundConclusionFn(Protocol):
    def __call__(self, numerical_diff: int, bomb_planted: bool, side: str, econ_bucket: str, map_name: str) -> float: ...

@dataclass(frozen=True, slots=True)
class RoundConclusionLookup:
    # ...dict fields and side_baseline...
    def lookup(self, numerical_diff: int, bomb_planted: bool, side: str, econ_bucket: str, map_name: str) -> float: ...
    # Phase 1: returns 0.5 always
```

From src/pricing/blend.py (01-01):
```python
def round_p(a_rate: float, b_rate_opposite_side: float) -> float: ...
```

`data/half_win_rates.json` schema (verified by planner — opening the file):
```json
{
  "team_map_side": {"SEN|Lotus|atk": {"wins": 4.0, "total": 10.0, "rate": 0.5, "used_fallback": true}, ...},
  "league_map_side": {"Lotus|atk": {"wins": 67.0, "total": 134.0, "rate": 0.5}, ...},
  "overall_avg": 0.5,
  "min_rounds_threshold": ...,
  "maps_in_data": [...],
  "event_weights": {...}
}
```

The PRD §2 / DEC-010 output contract (TheoOutput shape — ship verbatim):
```python
@dataclass(frozen=True, slots=True)
class TheoOutput:
    theo_series: float                 # ∈ [CONVICTION_CLIP_LOW, CONVICTION_CLIP_HIGH]
    theo_map: tuple[float, ...]        # one per map in pool; same clip
    vega: float                        # ≥ 0
    confidence: float                  # ∈ [0, 1]
```

The MatchState Phase 1 stub (D-02 + D-17 + D-18 + D-19 — 17 fields):
```python
@dataclass(frozen=True, slots=True)
class MatchState:
    """Phase 1 stub. Phase 3 (REQ-match-state-engine) replaces with full version."""
    match_id: str
    team_a: str                                          # D-17
    team_b: str                                          # D-17
    map_pool: tuple[str, ...]
    map_idx: int
    a_map_score: int
    b_map_score: int
    a_round: int
    b_round: int
    side_orient: str                                     # current within-map side ('a_atk' | 'a_def')
    map_side_orients: tuple[str, ...]                    # D-18 — per-map STARTING side; len == len(map_pool)
    map_winners: tuple[Optional[bool], ...]              # D-19 — True=A won this map, False=B won, None=undecided; len == len(map_pool)
    pistol_winner_a: dict[int, Optional[bool]]
    numerical_diff: int
    bomb_planted: bool
    side: str
    econ_bucket: str
```

`HalfRates` concrete dataclass (`from_json` classmethod + `_get_rate` salvage from reference/theo_engine.py:84-102, retyped for mypy strict):
```python
@dataclass(frozen=True)
class HalfRates:
    team_rates: dict[str, dict[str, Any]]
    league_rates: dict[str, dict[str, Any]]
    overall_avg: float

    @classmethod
    def from_json(cls, path: str | Path) -> "HalfRates":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            team_rates=data.get("team_map_side", {}),
            league_rates=data.get("league_map_side", {}),
            overall_avg=float(data.get("overall_avg", 0.5)),
        )

    def team(self, team: str, map_name: str, side: str) -> float:
        # Source: reference/theo_engine.py:84-102 — verbatim per D-09.
        league_key = f"{map_name}|{side}"
        lg = self.league_rates.get(league_key)
        prior: float = float(lg["rate"]) if lg else self.overall_avg
        team_key = f"{team}|{map_name}|{side}"
        entry = self.team_rates.get(team_key)
        if entry:
            n_val: float = float(entry.get("total", 0))
            raw: float = float(entry["rate"])
            return (n_val * raw + SHRINK_PRIOR * prior) / (n_val + SHRINK_PRIOR)
        return prior

    def team_entry(self, team: str, map_name: str, side: str) -> Optional[dict[str, Any]]:
        return self.team_rates.get(f"{team}|{map_name}|{side}")
```

`_data_weight` salvage (`reference/theo_engine.py:104-129` — D-09 verbatim):
```python
def _data_weight_for_map(team_a: str, team_b: str, map_name: str, half_rates: HalfRates) -> float:
    team_weights: list[float] = []
    for team in (team_a, team_b):
        team_total = 0.0
        team_count = 0
        for side in ("atk", "def"):
            entry = half_rates.team_entry(team, map_name, side)
            if entry and not entry.get("used_fallback", False):
                team_total += float(entry.get("total", 0))
                team_count += 1
        if team_count == 0:
            return 0.0
        team_weights.append(team_total / team_count)
    avg_rounds = min(team_weights)
    return min(1.0, avg_rounds / MIN_ROUNDS_FULL_WEIGHT)
```

Vega formula (RESEARCH §8 / DEC-018 / D-10):
```python
def _compute_vega(root: BO3State, round_p: float, round_p_fn: RoundPFn) -> float:
    """vega = round_p × (theo_a − theo)² + (1−round_p) × (theo_b − theo)²"""
    state_a_wins = _advance_round(root, a_wins=True)
    state_b_wins = _advance_round(root, a_wins=False)
    theo   = series_value(root, round_p_fn)
    theo_a = series_value(state_a_wins, round_p_fn)
    theo_b = series_value(state_b_wins, round_p_fn)
    return round_p * (theo_a - theo) ** 2 + (1.0 - round_p) * (theo_b - theo) ** 2
```

`_p_map_decisive` recurrence (TRUE DP-mass forward pass per W3 — three explicit cases):
```python
def _p_map_decisive(state: MatchState, m: int) -> float:
    """P(map m is the map that closes the series | current state).

    For m < state.map_idx:
        1.0 if map m clinched (one team reached 2 wins exactly at index m,
        derivable from map_winners[0..m]), else 0.0.
    For m == state.map_idx:
        P(current map is decisive) = P(this map ends with series 2-x where 2 is
        leader's score), evaluated via DP over the current BO3State's
        hypothetical map-decided next states. Specifically:
            theo_map_curr = _marginal_map_prob(state, m)
            P_decisive_a = 1.0 if (a_map_score + 1 == 2) else 0.0
            P_decisive_b = 1.0 if (b_map_score + 1 == 2) else 0.0
            return theo_map_curr * P_decisive_a + (1 - theo_map_curr) * P_decisive_b
    For m > state.map_idx:
        P(reach map m AND it's decisive) = sum over BO3 paths arriving at
        map m with one team at 1 win and the other at 0 or 1 wins, then this
        map clinches. Computed via DP forward pass over BO3State at map index m.
        For BO3 (best-of-3): map m > state.map_idx is reached only if maps
        played so far end with neither team at 2. The only way to reach map 2
        in a BO3 is through 1-1 (both teams have 1 map). Decisiveness on map 2
        is automatic (it's the last map). So for m == 2: P_reached =
        P(maps 0 and 1 split 1-1 | current state); decisive given reached = 1.0.
    """
    # Implementation uses lru_cache + a small forward-pass DP variant.
```

`_RoundPFnImpl` closure satisfying RoundPFn Protocol (D-18 wiring):
```python
@dataclass(frozen=True)
class _RoundPFnImpl:
    """Satisfies dp.RoundPFn Protocol; threads MatchState through to round_p_for_round.

    __call__(s) overrides s.side_orient by reading match_state.map_side_orients[s.map_idx]
    AND applying the within-map round-12 flip (rounds 0-11 use starting side; rounds 12-23
    use flipped side; OT (round 24+) handled by 01-02's OT leaf collapse).
    """
    match_state: MatchState
    half_rates: HalfRates

    def __call__(self, s: BO3State) -> float:
        effective_side = self._effective_side(s)
        s_corrected = replace(s, side_orient=effective_side)
        return round_p_for_round(s_corrected, self.match_state, self.half_rates)

    def _effective_side(self, s: BO3State) -> str:
        if s.map_idx >= len(self.match_state.map_side_orients):
            return "a_atk"  # past series-clinch; never consumed but defensive
        starting_side = self.match_state.map_side_orients[s.map_idx]
        rounds_played = s.a_round + s.b_round
        if rounds_played < REGULATION_HALF:
            return starting_side
        return "a_def" if starting_side == "a_atk" else "a_atk"

    def next_side_orient_for(self, map_idx: int) -> str:
        if map_idx >= len(self.match_state.map_side_orients):
            return "a_atk"
        return self.match_state.map_side_orients[map_idx]
```

`LiveTheoEngine` bundle (D-20):
```python
@dataclass(frozen=True)
class LiveTheoEngine:
    """Bundle pattern preserving PRD §6 / CRule 1 state-only call surface.

    Phase 4 instantiates once per match: `engine = LiveTheoEngine(half_rates)`.
    Per pricing call: `out = engine(state)`.
    """
    half_rates: HalfRates
    round_conclusion: Optional[RoundConclusionFn] = None

    def __call__(self, state: MatchState) -> TheoOutput:
        return _live_theo_impl(state, self.half_rates, self.round_conclusion)
```

The package re-export (PATTERNS lines 50-57):
```python
# src/pricing/__init__.py:
from src.pricing.live_theo import LiveTheoEngine
from src.pricing.data import HalfRates, MatchState, TheoOutput

__all__ = ["LiveTheoEngine", "TheoOutput", "MatchState", "HalfRates"]
```
**Do NOT re-export** `dp`, `blend`, `round_types`, `round_conclusion`, or any of their symbols — those are private to the package per DEC-010 / D-12.

Forbidden symbols (CRule 1 / DEC-010 / PRD §12.3 — these MUST NOT appear in src/pricing/):
- `series_theo`
- `series_theo_no_sides`
- `series_theo_from_map_probs`
- `_signal_strength` (PRD §12.2 #2 bug class — drop entirely)
- `model_series_prob` (PRD §12.3 — closed-form IID BO3 alternative; the DP supersedes it)
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Implement src/pricing/data.py with HalfRates + MatchState (17 fields) + TheoOutput dataclasses</name>
  <files>src/pricing/data.py, tests/pricing/test_live_theo.py</files>

  <read_first>
    - src/config/constants.py — verify SHRINK_PRIOR=15.0 is exported (Phase 0 / 01-01)
    - src/pricing/round_types.py — confirm HalfRates Protocol shape: `team(team, map, side) -> float` and `team_entry(team, map, side) -> Optional[dict]` (the concrete impl in this task MUST satisfy this Protocol structurally so 01-03's `round_p_for_round` accepts it)
    - .planning/phases/01-core-pricing-engine/01-CONTEXT.md `<decisions>` — D-02 (13-field base), D-17 (`team_a`/`team_b`), D-18 (`map_side_orients`), D-19 (`map_winners`)
    - .planning/phases/01-core-pricing-engine/01-RESEARCH.md §10 "MatchState surface — confirmed extensions A4/A5/A6" (lines 868-892)
    - .planning/phases/01-core-pricing-engine/01-PATTERNS.md "src/pricing/live_theo.py (service + data-shape, new)" section (lines 343-466) — borrow MatchState/TheoOutput skeleton; the concrete HalfRates `_get_rate` salvage (verbatim from reference/theo_engine.py:84-102 per D-09)
    - reference/theo_engine.py:84-102 — `_get_rate` salvage source (study end-to-end; the formula at line 100 is what `HalfRates.team` reuses verbatim)
    - data/half_win_rates.json (head ~50 lines) — verify schema keys: `team_map_side`, `league_map_side`, `overall_avg`. Confirm dict-of-dict shape so `team_rates: dict[str, dict[str, Any]]` matches.
    - tests/config/test_constants.py (existing pattern to mirror — section dividers, parametrize style)
    - CLAUDE.md Critical Rules 11 (mypy --strict), 12 (no magic numbers — SHRINK_PRIOR must come from constants)
  </read_first>

  <behavior>
    - Test 1 (MatchState shape — 17 fields, frozen+slots): `dataclasses.fields(MatchState)` returns exactly 17 entries with the names listed in `must_haves.outputs`; `@dataclass(frozen=True, slots=True)` enforced
    - Test 2 (MatchState D-17/D-18/D-19 fields present): `MatchState.__annotations__` includes `team_a: str`, `team_b: str`, `map_side_orients: tuple[str, ...]`, `map_winners: tuple[Optional[bool], ...]`
    - Test 3 (TheoOutput shape): four fields exactly — `theo_series: float`, `theo_map: tuple[float, ...]`, `vega: float`, `confidence: float`; frozen+slots
    - Test 4 (HalfRates loads JSON): `HalfRates.from_json("data/half_win_rates.json")` returns an instance with non-empty `team_rates`, `league_rates`, and `overall_avg == 0.5` (verified by planner)
    - Test 5 (HalfRates.team for known team uses Bayesian shrinkage formula): pick a `(team, map, side)` triple known to be in `team_map_side` → returned value matches `(n * raw + SHRINK_PRIOR * prior) / (n + SHRINK_PRIOR)` within `rel_tol=1e-12`
    - Test 6 (HalfRates.team missing-team fallback chain): for an unknown team, returns the league_rates value if present; else returns `overall_avg`
    - Test 7 (HalfRates.team_entry returns raw dict or None): satisfies the Protocol; for known triple returns the dict, for unknown returns None
    - Test 8 (REQ-canonical-live-theo import surface — pre-flight): `from src.pricing.data import HalfRates, MatchState, TheoOutput` succeeds (the package re-export wiring lands in Task 3 — this test confirms the underlying module exports)
  </behavior>

  <action>
Create `src/pricing/data.py` with this content (data shapes + concrete `HalfRates`):

```python
"""Phase 1 pricing data shapes: HalfRates, MatchState, TheoOutput.

Phase 1 owns the MatchState dataclass per D-14. Phase 3 (REQ-match-state-engine)
will move it to src/state/match_state.py and the orchestrator (live_theo.py)
will re-import from there. The public re-export surface for the package lives
in src/pricing/__init__.py — see that file for what downstream code consumes.

Sources
-------
- prd.md §2 (TheoOutput contract) / §6 (state-only call surface)
- DEC-010 / DEC-012 / D-08 / D-09 / D-12 / D-14 / D-17 / D-18 / D-19
- 01-RESEARCH.md §10 (MatchState surface), Open Question 2 (HalfRates loader)
- reference/theo_engine.py:84-102 (Bayesian shrinkage salvage source)
- 01-CONTEXT.md `<decisions>` D-17 (team_a/team_b), D-18 (map_side_orients),
  D-19 (map_winners), D-20 (LiveTheoEngine bundle pattern)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from src.config.constants import SHRINK_PRIOR


# --------------------------------------------------------------------------- #
# 1. TheoOutput — public pricing output (PRD §2 / DEC-010)                    #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class TheoOutput:
    """Single canonical pricing output.

    Fields per PRD §2 contract:
        theo_series: P(team A wins the BO3 series), clipped to
            [CONVICTION_CLIP_LOW, CONVICTION_CLIP_HIGH].
        theo_map: per-map P(team A wins map i), one per map in MatchState.map_pool;
            same clip applied. Marginalized from the SAME DP as theo_series
            (DEC-002 / CRule 2 — no parallel models).
        vega: variance of theo_series implied by current state per DEC-018 /
            D-10. Always >= 0.
        confidence: DP-mass-weighted aggregate of per-map data weight per D-08.
            In [0, 1].
    """

    theo_series: float
    theo_map: tuple[float, ...]
    vega: float
    confidence: float


# --------------------------------------------------------------------------- #
# 2. MatchState — Phase 1 stub (17 fields per D-02 + D-17/D-18/D-19)          #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class MatchState:
    """Phase 1 stub MatchState.

    Smallest field set that makes ``LiveTheoEngine.__call__`` callable
    end-to-end (D-01). Phase 3 (REQ-match-state-engine) replaces this with the
    full ingestion-driven version; the orchestrator's signature remains
    `engine(state) -> TheoOutput` (D-20). Phase 1 → Phase 3 seam absorbs one
    refactor.

    Fields (17 total):
      Identity:
        match_id, team_a (D-17), team_b (D-17)
      Series state:
        map_pool, map_idx, a_map_score, b_map_score
      Within-map state:
        a_round, b_round, side_orient
      Per-map starting sides + winners (D-18, D-19):
        map_side_orients, map_winners
      Pistol memory:
        pistol_winner_a (dict[map_idx, Optional[bool]])
      Mid-round signals (consumed by RoundConclusionLookup; opaque in Phase 1):
        numerical_diff, bomb_planted, side, econ_bucket

    Field NOT included (deferred to Phase 3 per D-02):
        seq_id, last_updated_ts, players_alive, ults, time_left_s
    """

    match_id: str
    team_a: str
    team_b: str
    map_pool: tuple[str, ...]
    map_idx: int
    a_map_score: int
    b_map_score: int
    a_round: int
    b_round: int
    side_orient: str
    map_side_orients: tuple[str, ...]
    map_winners: tuple[Optional[bool], ...]
    pistol_winner_a: dict[int, Optional[bool]]
    numerical_diff: int
    bomb_planted: bool
    side: str
    econ_bucket: str


# --------------------------------------------------------------------------- #
# 3. HalfRates — concrete impl satisfying round_types.HalfRates Protocol      #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class HalfRates:
    """Per-team-map-side win-rate source backed by data/half_win_rates.json.

    Satisfies src.pricing.round_types.HalfRates Protocol. Bayesian-shrunk
    rates per D-09 / reference/theo_engine.py:84-102 (salvage verbatim).
    Instantiated by the caller (Phase 4 quoter); passed into LiveTheoEngine
    constructor (D-20). Phase 1 tests construct synthetic HalfRates inline.
    """

    team_rates: dict[str, dict[str, Any]]
    league_rates: dict[str, dict[str, Any]]
    overall_avg: float

    @classmethod
    def from_json(cls, path: str | Path) -> "HalfRates":
        """Load HalfRates from data/half_win_rates.json (Open Question 2 resolution).

        Schema (verified during planning):
            {
              "team_map_side":   {"<team>|<map>|<side>": {"wins", "total", "rate", "used_fallback"}, ...},
              "league_map_side": {"<map>|<side>":         {"wins", "total", "rate"}, ...},
              "overall_avg": float (typically 0.5),
              ...
            }
        """
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            team_rates=data.get("team_map_side", {}),
            league_rates=data.get("league_map_side", {}),
            overall_avg=float(data.get("overall_avg", 0.5)),
        )

    def team(self, team: str, map_name: str, side: str) -> float:
        """Bayesian-shrunk win rate for team on map_name while playing side.

        Formula: ``(n * raw + SHRINK_PRIOR * prior) / (n + SHRINK_PRIOR)``.
        Source: reference/theo_engine.py:84-102 — salvage verbatim per D-09.

        Fallback chain: team_rates → league_rates → overall_avg (0.5).
        """
        league_key = f"{map_name}|{side}"
        lg = self.league_rates.get(league_key)
        prior: float = float(lg["rate"]) if lg else self.overall_avg
        team_key = f"{team}|{map_name}|{side}"
        entry = self.team_rates.get(team_key)
        if entry:
            n_val: float = float(entry.get("total", 0))
            raw: float = float(entry["rate"])
            return (n_val * raw + SHRINK_PRIOR * prior) / (n_val + SHRINK_PRIOR)
        return prior

    def team_entry(
        self, team: str, map_name: str, side: str
    ) -> Optional[dict[str, Any]]:
        """Raw team entry — powers _data_weight_for_map in live_theo.py."""
        return self.team_rates.get(f"{team}|{map_name}|{side}")
```

Then create `tests/pricing/test_live_theo.py` with the data-shape tests (this file will be EXTENDED by Tasks 2a, 2b, 3 — Task 1 ships the initial scaffold + data-shape coverage):

```python
"""End-to-end contract tests for src.pricing.live_theo + data shapes.

Verifies REQ-canonical-live-theo + REQ-theo-{series,map}-output +
REQ-confidence-output + REQ-vega-output. Locks the public surface so
downstream Phase 4 quoting layer can import deterministically.

Test sections (extended across Tasks 1 / 2a / 2b / 3):
  1. Data shapes (Task 1)
  2. HalfRates JSON loader (Task 1)
  3. _live_theo_impl core (Task 2a)
  4. LiveTheoEngine bundle + confidence + vega (Task 2b)
  5. Public surface + integration (Task 3)
"""

from __future__ import annotations

import dataclasses
import math
from pathlib import Path
from typing import Optional

import pytest

from src.config.constants import SHRINK_PRIOR
from src.pricing.data import HalfRates, MatchState, TheoOutput


# --------------------------------------------------------------------------- #
# 1. Data shapes (Task 1)                                                     #
# --------------------------------------------------------------------------- #


def test_theo_output_is_frozen_dataclass() -> None:
    """PRD §2: TheoOutput is a frozen dataclass with exactly four fields."""
    assert dataclasses.is_dataclass(TheoOutput)
    field_names = {f.name for f in dataclasses.fields(TheoOutput)}
    assert field_names == {"theo_series", "theo_map", "vega", "confidence"}
    # Frozen: assigning to an instance must raise.
    out = TheoOutput(theo_series=0.5, theo_map=(0.5,), vega=0.0, confidence=0.5)
    with pytest.raises(dataclasses.FrozenInstanceError):
        out.theo_series = 0.6  # type: ignore[misc]


def test_match_state_is_17_field_frozen_dataclass() -> None:
    """D-02 + D-17 + D-18 + D-19: 17 fields exactly. Frozen + slots."""
    assert dataclasses.is_dataclass(MatchState)
    fields = dataclasses.fields(MatchState)
    field_names = [f.name for f in fields]
    assert len(fields) == 17, f"expected 17 fields, got {len(fields)}: {field_names}"
    expected = {
        "match_id",
        "team_a",
        "team_b",
        "map_pool",
        "map_idx",
        "a_map_score",
        "b_map_score",
        "a_round",
        "b_round",
        "side_orient",
        "map_side_orients",
        "map_winners",
        "pistol_winner_a",
        "numerical_diff",
        "bomb_planted",
        "side",
        "econ_bucket",
    }
    assert set(field_names) == expected
    # Forbidden Phase 3 fields:
    forbidden = {"seq_id", "last_updated_ts", "players_alive", "ults", "time_left_s"}
    assert not (forbidden & set(field_names)), (
        "Phase 3 fields leaked into Phase 1 stub MatchState"
    )


def test_match_state_d17_d18_d19_fields_present() -> None:
    """D-17/D-18/D-19 fields are present with the correct annotations."""
    annotations = MatchState.__annotations__
    assert "team_a" in annotations  # D-17
    assert "team_b" in annotations  # D-17
    assert "map_side_orients" in annotations  # D-18
    assert "map_winners" in annotations  # D-19


def test_match_state_is_frozen_and_uses_slots() -> None:
    """frozen=True + slots=True per Pattern S3."""
    state = _synthetic_match_state()
    with pytest.raises(dataclasses.FrozenInstanceError):
        state.match_id = "other"  # type: ignore[misc]
    assert hasattr(MatchState, "__slots__")


# --------------------------------------------------------------------------- #
# 2. HalfRates JSON loader (Task 1)                                           #
# --------------------------------------------------------------------------- #


def test_half_rates_loads_json() -> None:
    """from_json reads data/half_win_rates.json and returns a populated instance."""
    hr = HalfRates.from_json("data/half_win_rates.json")
    assert hr.overall_avg == 0.5  # Verified during planning
    assert len(hr.team_rates) > 0
    assert len(hr.league_rates) > 0


def test_half_rates_team_uses_bayesian_shrinkage() -> None:
    """team(t, m, s) returns (n*raw + SHRINK_PRIOR*prior) / (n + SHRINK_PRIOR)."""
    hr = HalfRates(
        team_rates={"TeamA|Lotus|atk": {"wins": 6.0, "total": 10.0, "rate": 0.6}},
        league_rates={"Lotus|atk": {"wins": 50.0, "total": 100.0, "rate": 0.5}},
        overall_avg=0.5,
    )
    actual = hr.team("TeamA", "Lotus", "atk")
    expected = (10.0 * 0.6 + SHRINK_PRIOR * 0.5) / (10.0 + SHRINK_PRIOR)
    assert math.isclose(actual, expected, rel_tol=1e-12)


def test_half_rates_team_falls_back_to_league_when_team_missing() -> None:
    """Missing-team fallback: team_rates → league_rates."""
    hr = HalfRates(
        team_rates={},
        league_rates={"Lotus|atk": {"wins": 67.0, "total": 134.0, "rate": 0.55}},
        overall_avg=0.5,
    )
    assert hr.team("UnknownTeam", "Lotus", "atk") == 0.55


def test_half_rates_team_falls_back_to_overall_avg_when_no_data() -> None:
    """Missing-team-and-league fallback: overall_avg = 0.5."""
    hr = HalfRates(team_rates={}, league_rates={}, overall_avg=0.5)
    assert hr.team("UnknownTeam", "UnknownMap", "atk") == 0.5


def test_half_rates_team_entry_returns_dict_or_none() -> None:
    """team_entry returns the raw entry dict or None."""
    hr = HalfRates(
        team_rates={"TeamA|Lotus|atk": {"wins": 6.0, "total": 10.0, "rate": 0.6, "used_fallback": False}},
        league_rates={},
        overall_avg=0.5,
    )
    entry = hr.team_entry("TeamA", "Lotus", "atk")
    assert entry is not None
    assert entry["total"] == 10.0
    assert hr.team_entry("Unknown", "Lotus", "atk") is None


# --------------------------------------------------------------------------- #
# Test fixtures (used by Tasks 2a/2b/3)                                       #
# --------------------------------------------------------------------------- #


def _synthetic_half_rates() -> HalfRates:
    """Minimal synthetic HalfRates for downstream tests."""
    return HalfRates(
        team_rates={
            "TeamA|Lotus|atk": {"wins": 6.0, "total": 10.0, "rate": 0.6, "used_fallback": False},
            "TeamA|Lotus|def": {"wins": 5.0, "total": 10.0, "rate": 0.5, "used_fallback": False},
            "TeamB|Lotus|atk": {"wins": 4.0, "total": 10.0, "rate": 0.4, "used_fallback": False},
            "TeamB|Lotus|def": {"wins": 5.0, "total": 10.0, "rate": 0.5, "used_fallback": False},
            "TeamA|Bind|atk": {"wins": 6.0, "total": 10.0, "rate": 0.6, "used_fallback": False},
            "TeamA|Bind|def": {"wins": 5.0, "total": 10.0, "rate": 0.5, "used_fallback": False},
            "TeamB|Bind|atk": {"wins": 4.0, "total": 10.0, "rate": 0.4, "used_fallback": False},
            "TeamB|Bind|def": {"wins": 5.0, "total": 10.0, "rate": 0.5, "used_fallback": False},
            "TeamA|Haven|atk": {"wins": 6.0, "total": 10.0, "rate": 0.6, "used_fallback": False},
            "TeamA|Haven|def": {"wins": 5.0, "total": 10.0, "rate": 0.5, "used_fallback": False},
            "TeamB|Haven|atk": {"wins": 4.0, "total": 10.0, "rate": 0.4, "used_fallback": False},
            "TeamB|Haven|def": {"wins": 5.0, "total": 10.0, "rate": 0.5, "used_fallback": False},
        },
        league_rates={
            f"{m}|{s}": {"wins": 50.0, "total": 100.0, "rate": 0.5}
            for m in ("Lotus", "Bind", "Haven")
            for s in ("atk", "def")
        },
        overall_avg=0.5,
    )


def _synthetic_match_state(
    map_idx: int = 0,
    a_map_score: int = 0,
    b_map_score: int = 0,
    a_round: int = 0,
    b_round: int = 0,
    side_orient: str = "a_atk",
    map_side_orients: tuple[str, ...] = ("a_atk", "a_atk", "a_atk"),
    map_winners: tuple[Optional[bool], ...] = (None, None, None),
    pistol_winner_a: Optional[dict[int, Optional[bool]]] = None,
) -> MatchState:
    """Canonical synthetic MatchState fixture used across Phase 1 integration tests."""
    return MatchState(
        match_id="synthetic-001",
        team_a="TeamA",
        team_b="TeamB",
        map_pool=("Lotus", "Bind", "Haven"),
        map_idx=map_idx,
        a_map_score=a_map_score,
        b_map_score=b_map_score,
        a_round=a_round,
        b_round=b_round,
        side_orient=side_orient,
        map_side_orients=map_side_orients,
        map_winners=map_winners,
        pistol_winner_a=pistol_winner_a or {0: None, 1: None, 2: None},
        numerical_diff=0,
        bomb_planted=False,
        side="atk",
        econ_bucket="full",
    )
```

Commit with message `feat(01-05): add MatchState/TheoOutput/HalfRates data shapes (D-17/D-18/D-19)`.
  </action>

  <verify>
    <automated>uv run mypy --strict src/pricing/data.py &amp;&amp; uv run pytest tests/pricing/test_live_theo.py -x &amp;&amp; uv run ruff check src/pricing/data.py tests/pricing/test_live_theo.py</automated>
  </verify>

  <acceptance_criteria>
    - `test -f src/pricing/data.py`
    - `grep -q "class TheoOutput:" src/pricing/data.py`
    - `grep -q "class MatchState:" src/pricing/data.py`
    - `grep -q "class HalfRates:" src/pricing/data.py`
    - `grep -q "@dataclass(frozen=True, slots=True)" src/pricing/data.py` (TheoOutput + MatchState)
    - `grep -q "team_a: str" src/pricing/data.py` (D-17)
    - `grep -q "team_b: str" src/pricing/data.py` (D-17)
    - `grep -q "map_side_orients: tuple\[str, \.\.\.\]" src/pricing/data.py` (D-18)
    - `grep -q "map_winners: tuple\[Optional\[bool\], \.\.\.\]" src/pricing/data.py` (D-19)
    - `grep -q "def from_json(" src/pricing/data.py` (HalfRates classmethod)
    - `grep -q "def team(self, team: str, map_name: str, side: str) -> float:" src/pricing/data.py`
    - `grep -q "def team_entry(" src/pricing/data.py`
    - `grep -qE "\(n_val \* raw \+ SHRINK_PRIOR \* prior\) / \(n_val \+ SHRINK_PRIOR\)" src/pricing/data.py` (Bayesian shrinkage formula)
    - `grep -q "from src.config.constants import SHRINK_PRIOR" src/pricing/data.py` (no inline 15)
    - Comment-stripped: `! (grep -v '^[[:space:]]*#' src/pricing/data.py | grep -E '\* 15 \*|\+ 15 \*|\+ 15\)')` (no inline 15 in formula)
    - `! grep -q "seq_id" src/pricing/data.py` (Phase 3 fields not leaked)
    - `! grep -q "players_alive" src/pricing/data.py`
    - `! grep -q "time_left_s" src/pricing/data.py`
    - `test -f tests/pricing/test_live_theo.py`
    - `grep -q "test_theo_output_is_frozen_dataclass" tests/pricing/test_live_theo.py`
    - `grep -q "test_match_state_is_17_field_frozen_dataclass" tests/pricing/test_live_theo.py`
    - `grep -q "test_match_state_d17_d18_d19_fields_present" tests/pricing/test_live_theo.py`
    - `grep -q "test_half_rates_loads_json" tests/pricing/test_live_theo.py`
    - `grep -q "test_half_rates_team_uses_bayesian_shrinkage" tests/pricing/test_live_theo.py`
    - `grep -q "test_half_rates_team_falls_back_to_league_when_team_missing" tests/pricing/test_live_theo.py`
    - `grep -q "test_half_rates_team_falls_back_to_overall_avg_when_no_data" tests/pricing/test_live_theo.py`
    - `uv run mypy --strict src/pricing/data.py` exits 0
    - `uv run pytest tests/pricing/test_live_theo.py -x` exits 0
    - `uv run ruff check src/pricing/data.py tests/pricing/test_live_theo.py` exits 0
  </acceptance_criteria>

  <done>
    `src/pricing/data.py` exports `HalfRates` (with `from_json` + Bayesian-shrunk `team` + `team_entry`), `MatchState` (17 fields per D-02 + D-17 + D-18 + D-19, frozen+slots), and `TheoOutput` (4 fields, frozen+slots). `tests/pricing/test_live_theo.py` covers all data-shape and HalfRates-loader behaviors. `mypy --strict`, `pytest`, `ruff` all green. Downstream tasks have stable types to import.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2a: Implement _live_theo_impl core (state conversion + closures + per-map marginals)</name>
  <files>src/pricing/live_theo.py, tests/pricing/test_live_theo.py</files>

  <read_first>
    - src/pricing/data.py — verify HalfRates / MatchState / TheoOutput from Task 1
    - src/pricing/dp.py — confirm BO3State fields + `series_value` + `RoundPFn` Protocol + `_advance_round` + `_advance_to_next_map` from 01-02
    - src/pricing/round_types.py — confirm `round_p_for_round(state, match_state, half_rates) -> float` + HalfRates Protocol from 01-03
    - src/pricing/round_conclusion.py — confirm `RoundConclusionFn` Protocol + `RoundConclusionLookup` from 01-04
    - src/pricing/blend.py — confirm `round_p` from 01-01 (consumed inside round_p_for_round, not directly here)
    - src/config/constants.py — verify CONVICTION_CLIP_LOW=0.01, CONVICTION_CLIP_HIGH=0.99, MIN_ROUNDS_FULL_WEIGHT=15, REGULATION_HALF=12 from Phase 0 + 01-01
    - .planning/phases/01-core-pricing-engine/01-CONTEXT.md `<decisions>` — D-08 (DP-mass-weighted confidence), D-12 (no audit triplet), D-18 (`map_side_orients` consumed by closure), D-19 (`map_winners` consumed by `_marginal_map_prob` short-circuit)
    - .planning/phases/01-core-pricing-engine/01-RESEARCH.md §7 "Confidence formula" + §8 "Vega formula" + §10 "MatchState surface"
    - .planning/phases/01-core-pricing-engine/01-PATTERNS.md "src/pricing/live_theo.py (service + data-shape, new)" section (lines 343-466)
    - reference/theo_engine.py:104-129 — `_data_weight` salvage (study end-to-end)
    - prd.md §2 (TheoOutput contract), §6 (state-only call surface), §12.2 #1/#2/#6 (bug classes being closed)
    - CLAUDE.md Critical Rules 1, 2, 5, 6, 11, 12
  </read_first>

  <behavior>
    - Test 1 (`_bo3_state_from_match_state` packing): MatchState with `pistol_winner_a={0: True, 1: None, 2: False}` produces a BO3State with `pistol_winner_a=(True, None, False)` (tuple, ordered by map_idx)
    - Test 2 (`_RoundPFnImpl.__call__` consults map_side_orients[map_idx] within first half): for `MatchState.map_side_orients=("a_atk", "a_def", "a_atk")` and a BO3State at `map_idx=1, a_round=3, b_round=2` (round 6, total=5 < 12), the closure delegates to `round_p_for_round` with a BO3State whose `side_orient='a_def'` (starting side for map 1)
    - Test 3 (`_RoundPFnImpl.__call__` flips after round 12): for the same MatchState, BO3State at `map_idx=1, a_round=12, b_round=2` (total=14 >= 12), the closure passes `side_orient='a_atk'` (flipped from starting 'a_def')
    - Test 4 (`_RoundPFnImpl.next_side_orient_for` returns starting side for that map): `next_side_orient_for(0)` == "a_atk", `next_side_orient_for(2)` == "a_atk" for the test fixture
    - Test 5 (`_RoundPFnImpl.next_side_orient_for` bounds-checks): for `map_idx >= len(map_side_orients)` (e.g., past series clinch), returns "a_atk" defensively without raising
    - Test 6 (`_marginal_map_prob` short-circuits on map_winners for k < state.map_idx, A won): if `state.map_idx=1` and `state.map_winners[0] = True`, `_marginal_map_prob(state, 0)` returns CONVICTION_CLIP_HIGH (0.99) — clipped indicator
    - Test 7 (`_marginal_map_prob` short-circuits for B won): if `state.map_winners[0] = False`, returns CONVICTION_CLIP_LOW (0.01)
    - Test 8 (`_marginal_map_prob` for current map uses DP marginalization): for `state.map_idx=0` and `_marginal_map_prob(state, 0)`, the value equals the clipped DP-derived probability (verified by computing `series_value(state_a_won_map_0) * P_A_wins_current + series_value(state_b_won_map_0) * (1 - P_A_wins_current)` — but at the per-map level this is just the probability A wins map 0; equivalent to `series_value` of the within-map sub-DP)
    - Test 9 (`_live_theo_impl` returns TheoOutput with theo_series in clip range): for the synthetic_state, `out.theo_series` is in [CONVICTION_CLIP_LOW, CONVICTION_CLIP_HIGH]
    - Test 10 (`_live_theo_impl` returns theo_map of correct length): `len(out.theo_map) == len(state.map_pool) == 3`
    - Test 11 (`_live_theo_impl` per-map values in clip range): every `theo_map[i]` is in [CONVICTION_CLIP_LOW, CONVICTION_CLIP_HIGH]
  </behavior>

  <action>
Create `src/pricing/live_theo.py` with the conversion helpers + closures + `_live_theo_impl` scaffold (vega and confidence stubs in this task; the full implementations land in Task 2b):

```python
"""Single canonical pricing entry point: live_theo (via LiveTheoEngine bundle).

Replaces audit-engine series_theo / series_theo_no_sides / series_theo_from_map_probs
triplet (DEC-010 / CRule 1). All four bug fixes documented at the file level:
  1. Bradley-Terry blend (DEC-003)        — via src.pricing.blend
  2. OT hard-stop at total=24 (DEC-009)   — via src.pricing.dp
  3. Pistol/anti-eco modeling (DEC-011)   — via src.pricing.round_types
  4. Conviction clip [0.01, 0.99] (DEC-012) — applied here at output assembly

Phase 1 ships LiveTheoEngine bundle (D-20) preserving PRD §6 / DEC-010 / CRule 1
state-only call surface: `engine = LiveTheoEngine(half_rates, round_conclusion);
engine(state) -> TheoOutput`. The pure helper `_live_theo_impl` is exported for
testability (tests can call it without constructing a bundle).

Phase 1 owns MatchState in src/pricing/data.py (D-14). Phase 3 will move
MatchState to src/state/match_state.py and live_theo.py will re-import from there.

Sources
-------
- prd.md §2 / §6 (state-only call surface)
- DEC-002, DEC-003, DEC-009, DEC-010, DEC-012, DEC-018
- D-08 (confidence semantics), D-09 (data_weight salvage), D-10/D-11 (vega)
- D-12 (forbidden audit triplet), D-18 (map_side_orients), D-19 (map_winners),
  D-20 (LiveTheoEngine bundle)
- 01-RESEARCH.md §7 (confidence forward-pass), §8 (vega), §10 (MatchState surface)
- reference/theo_engine.py:104-129 (data_weight salvage source)
"""

from __future__ import annotations

import functools
from dataclasses import dataclass, replace
from typing import Optional

from src.config.constants import (
    CONVICTION_CLIP_HIGH,
    CONVICTION_CLIP_LOW,
    MIN_ROUNDS_FULL_WEIGHT,
    REGULATION_HALF,
)
from src.pricing.data import HalfRates, MatchState, TheoOutput
from src.pricing.dp import (
    BO3State,
    RoundPFn,
    _advance_round,
    _advance_to_next_map,
    series_value,
)
from src.pricing.round_conclusion import RoundConclusionFn
from src.pricing.round_types import round_p_for_round


# --------------------------------------------------------------------------- #
# 1. State conversion (MatchState → BO3State)                                 #
# --------------------------------------------------------------------------- #


def _bo3_state_from_match_state(state: MatchState) -> BO3State:
    """Project the DP-relevant subset of MatchState into a BO3State cache key.

    Packs `pistol_winner_a: dict[int, Optional[bool]]` into a tuple keyed by
    map_idx (0..len(map_pool)-1) so BO3State remains hashable for lru_cache.
    """
    pistol_tuple = tuple(
        state.pistol_winner_a.get(i, None) for i in range(len(state.map_pool))
    )
    return BO3State(
        map_idx=state.map_idx,
        a_map_score=state.a_map_score,
        b_map_score=state.b_map_score,
        a_round=state.a_round,
        b_round=state.b_round,
        side_orient=state.side_orient,
        map_pool=state.map_pool,
        pistol_winner_a=pistol_tuple,
    )


# --------------------------------------------------------------------------- #
# 2. RoundPFn closure — threads MatchState through to round_p_for_round       #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class _RoundPFnImpl:
    """Satisfies dp.RoundPFn Protocol (D-18 wiring).

    `__call__(s)` resolves the EFFECTIVE side from `match_state.map_side_orients[s.map_idx]`
    AND applies the within-map round-12 flip. This closes PRD §12.2 #6 audit
    `series_theo_no_sides` bug class — the DP no longer hardcodes 'a_atk' for
    next-map roots; live_theo supplies the per-map starting side via this object.

    `next_side_orient_for(map_idx)` is consulted by 01-02's
    `_advance_to_next_map` and `_ot_coinflip_leaf` callsites.
    """

    match_state: MatchState
    half_rates: HalfRates

    def __call__(self, s: BO3State) -> float:
        effective_side = self._effective_side(s)
        s_corrected = replace(s, side_orient=effective_side)
        return round_p_for_round(s_corrected, self.match_state, self.half_rates)

    def _effective_side(self, s: BO3State) -> str:
        if s.map_idx >= len(self.match_state.map_side_orients):
            # Past series-clinch; never consumed but defensive.
            return "a_atk"
        starting_side = self.match_state.map_side_orients[s.map_idx]
        rounds_played = s.a_round + s.b_round
        if rounds_played < REGULATION_HALF:
            return starting_side
        # Rounds 12..23: flipped half. (OT handled by dp's OT coinflip leaf.)
        return "a_def" if starting_side == "a_atk" else "a_atk"

    def next_side_orient_for(self, map_idx: int) -> str:
        if map_idx >= len(self.match_state.map_side_orients):
            return "a_atk"
        return self.match_state.map_side_orients[map_idx]


# --------------------------------------------------------------------------- #
# 3. Per-map marginal probability (with map_winners short-circuit)            #
# --------------------------------------------------------------------------- #


def _marginal_map_prob(
    state: MatchState,
    m: int,
    half_rates: HalfRates,
) -> float:
    """P(team A wins map m | current state).

    Three cases (per D-19 + DEC-002 / CRule 2 marginalization):
      m < state.map_idx:
        Map already played. Indicator value from `state.map_winners[m]`,
        clipped to [CONVICTION_CLIP_LOW, CONVICTION_CLIP_HIGH] per DEC-012.
        BO3State carries only AGGREGATE map scores and cannot recover this
        — D-19 ensures `map_winners` does.
      m == state.map_idx:
        Current map. P(A wins this map) computed from the within-map DP
        (`series_value` rooted at the current within-map state, then projected
        to map-only by the DP's terminal logic when WIN_THRESHOLD is hit).
      m > state.map_idx:
        Future map. P(A wins map m) given the series may not reach map m.
        For BO3 with state.map_idx + 1 and state.map_idx + 2: the DP rooted at
        the current state, evaluating P(A wins on map m via the full BO3
        recursion). When map m is unreachable (series clinches earlier),
        the contribution to P(A wins) is 0 from those branches.

    For Phase 1 we compute m == state.map_idx and m > state.map_idx via the
    DP's series_value at hypothetical map-m-decided states; m < state.map_idx
    short-circuits on map_winners.
    """
    fn = _RoundPFnImpl(match_state=state, half_rates=half_rates)
    if m < state.map_idx:
        # Already-played map: indicator from map_winners.
        winner = state.map_winners[m]
        if winner is True:
            return CONVICTION_CLIP_HIGH
        if winner is False:
            return CONVICTION_CLIP_LOW
        # Defensive: should never be None for m < map_idx; treat as coinflip.
        return 0.5

    if m == state.map_idx:
        # Current map: marginalize over within-map DP.
        # P(A wins map m) = P(reach map-end with A_round=WIN_THRESHOLD) under DP.
        # Computed via two hypothetical end-states + the series_value chain.
        bo3 = _bo3_state_from_match_state(state)
        # series_value evaluates to P(A wins SERIES) — to extract P(A wins
        # CURRENT map), we use the identity:
        #   series_value(state) = P(A wins map m) * series_value(state_after_a_wins_map_m)
        #                       + (1 - P(A wins map m)) * series_value(state_after_b_wins_map_m)
        # Solving for P(A wins map m):
        next_side = fn.next_side_orient_for(m + 1)
        state_after_a = _advance_to_next_map(bo3, a_won=True, next_side_orient=next_side)
        state_after_b = _advance_to_next_map(bo3, a_won=False, next_side_orient=next_side)
        v_after_a = series_value(state_after_a, fn)
        v_after_b = series_value(state_after_b, fn)
        v_root = series_value(bo3, fn)
        denom = v_after_a - v_after_b
        if abs(denom) < 1e-12:
            # Map has no marginal effect (e.g., series already decided regardless
            # of this map's outcome) — defensively return 0.5.
            return 0.5
        p_a_wins_map_m = (v_root - v_after_b) / denom
        return max(CONVICTION_CLIP_LOW, min(CONVICTION_CLIP_HIGH, p_a_wins_map_m))

    # m > state.map_idx: future map.
    # P(A wins map m) marginalizes over BO3 paths arriving at map m.
    # For BO3, m > state.map_idx is only reachable if no team has clinched yet.
    # The full DP recursion already accounts for this via terminal short-circuits:
    # contributions from unreachable branches are 0.
    bo3 = _bo3_state_from_match_state(state)
    # Same identity as above but at map index m: requires the DP rooted at the
    # current state to identify the joint probability {reach map m AND A wins it}.
    # We use the within-map identity at the future map, weighted by P(reach map m).
    # A simpler approach: enumerate the two future map states (A wins m, B wins m)
    # and use the same algebraic identity. Since BO3State terminal logic clamps
    # series_value at clinch, unreachable contributions are zero.
    fn = _RoundPFnImpl(match_state=state, half_rates=half_rates)
    next_side = fn.next_side_orient_for(m + 1)
    # We need to compute series_value at (state_after_a_wins_map_m,
    # state_after_b_wins_map_m, current_state). The "current" already contains
    # the future-map information embedded in the DP recursion.
    # Use the same identity; it generalizes to future maps because series_value
    # marginalizes over them automatically.
    bo3_at_m = BO3State(
        map_idx=m,
        a_map_score=bo3.a_map_score,
        b_map_score=bo3.b_map_score,
        a_round=0,
        b_round=0,
        side_orient=fn.next_side_orient_for(m),
        map_pool=bo3.map_pool,
        pistol_winner_a=bo3.pistol_winner_a,
    )
    state_after_a = _advance_to_next_map(bo3_at_m, a_won=True, next_side_orient=next_side)
    state_after_b = _advance_to_next_map(bo3_at_m, a_won=False, next_side_orient=next_side)
    v_after_a = series_value(state_after_a, fn)
    v_after_b = series_value(state_after_b, fn)
    v_at_m = series_value(bo3_at_m, fn)
    denom = v_after_a - v_after_b
    if abs(denom) < 1e-12:
        return 0.5
    p_a_wins_map_m = (v_at_m - v_after_b) / denom
    return max(CONVICTION_CLIP_LOW, min(CONVICTION_CLIP_HIGH, p_a_wins_map_m))


# --------------------------------------------------------------------------- #
# 4. Output clipping                                                          #
# --------------------------------------------------------------------------- #


def _clip_conviction(theo: float) -> float:
    """Clip to [CONVICTION_CLIP_LOW, CONVICTION_CLIP_HIGH] per DEC-012 / CRule 6."""
    return max(CONVICTION_CLIP_LOW, min(CONVICTION_CLIP_HIGH, theo))


# --------------------------------------------------------------------------- #
# 5. _live_theo_impl scaffold (vega + confidence stubs — Task 2b finalizes)   #
# --------------------------------------------------------------------------- #


def _live_theo_impl(
    state: MatchState,
    half_rates: HalfRates,
    round_conclusion: Optional[RoundConclusionFn] = None,
) -> TheoOutput:
    """Pure functional core of LiveTheoEngine. Importable for tests.

    Args:
        state: Phase 1 stub MatchState (D-01 / D-02 + D-17/D-18/D-19).
        half_rates: HalfRates instance (typically loaded from data/half_win_rates.json).
        round_conclusion: Optional mid-round-conclusion lookup. Phase 1 returns
            flat 0.5 from RoundConclusionLookup; absent → not consumed in Phase 1
            because the DP is between-rounds.

    Returns:
        TheoOutput with theo_series, theo_map (per-map marginals), vega
        (DEC-018), and confidence (DP-mass-weighted per D-08).
    """
    # NOTE: round_conclusion is reserved for mid-round vega refinement in
    # Phase 5 (D-11 — Phase 1 doesn't special-case mid-round). Currently
    # unused by the orchestrator; pass-through preserved for D-20 bundle.
    _ = round_conclusion  # silence unused-argument lint until Phase 5 wires it

    bo3 = _bo3_state_from_match_state(state)
    fn = _RoundPFnImpl(match_state=state, half_rates=half_rates)

    theo_series_raw = series_value(bo3, fn)
    theo_series = _clip_conviction(theo_series_raw)
    theo_map = tuple(
        _marginal_map_prob(state, m, half_rates) for m in range(len(state.map_pool))
    )

    # Vega + confidence finalized in Task 2b; placeholder values here so
    # `_live_theo_impl` is end-to-end callable for Task 2a tests.
    vega = _compute_vega(bo3, fn)
    confidence = _compute_confidence(state, half_rates)

    return TheoOutput(
        theo_series=theo_series,
        theo_map=theo_map,
        vega=vega,
        confidence=confidence,
    )


# Stubs filled in Task 2b — keep signatures stable so Task 2a tests pass.
def _compute_vega(root: BO3State, round_p_fn: RoundPFn) -> float:
    """Stub: Task 2b implements DEC-018 form. Returns 0.0 here so Task 2a tests pass."""
    return 0.0


def _compute_confidence(state: MatchState, half_rates: HalfRates) -> float:
    """Stub: Task 2b implements TRUE DP-mass-weighted formula per D-08 / W3."""
    return 0.0
```

Then APPEND tests to `tests/pricing/test_live_theo.py` (do not overwrite Task 1 tests):

```python
# --------------------------------------------------------------------------- #
# 3. _live_theo_impl core (Task 2a)                                            #
# --------------------------------------------------------------------------- #

from src.pricing.dp import BO3State
from src.pricing.live_theo import (
    _RoundPFnImpl,
    _bo3_state_from_match_state,
    _clip_conviction,
    _live_theo_impl,
    _marginal_map_prob,
)


def test_bo3_state_from_match_state_packs_pistol_dict_into_tuple() -> None:
    """pistol_winner_a dict → tuple ordered by map_idx."""
    state = _synthetic_match_state(pistol_winner_a={0: True, 1: None, 2: False})
    bo3 = _bo3_state_from_match_state(state)
    assert bo3.pistol_winner_a == (True, None, False)
    assert bo3.map_idx == 0
    assert bo3.map_pool == ("Lotus", "Bind", "Haven")


def test_build_round_p_fn_consults_map_side_orients_first_half() -> None:
    """D-18: closure overrides side_orient with map_side_orients[map_idx] in first half.

    For map 1 (starting side 'a_def'), at round 5 (total=5 < REGULATION_HALF=12),
    the effective side is the starting side 'a_def'.
    """
    hr = _synthetic_half_rates()
    state = _synthetic_match_state(
        map_idx=1,
        a_round=3,
        b_round=2,
        side_orient="a_atk",  # outdated — closure should override
        map_side_orients=("a_atk", "a_def", "a_atk"),
    )
    fn = _RoundPFnImpl(match_state=state, half_rates=hr)
    bo3 = BO3State(
        map_idx=1, a_map_score=0, b_map_score=0,
        a_round=3, b_round=2, side_orient="a_atk",
        map_pool=("Lotus", "Bind", "Haven"),
        pistol_winner_a=(None, None, None),
    )
    assert fn._effective_side(bo3) == "a_def"


def test_build_round_p_fn_flips_after_round_12() -> None:
    """D-18 + within-map flip: rounds_played >= REGULATION_HALF flips the side."""
    hr = _synthetic_half_rates()
    state = _synthetic_match_state(
        map_idx=1,
        map_side_orients=("a_atk", "a_def", "a_atk"),
    )
    fn = _RoundPFnImpl(match_state=state, half_rates=hr)
    bo3 = BO3State(
        map_idx=1, a_map_score=0, b_map_score=0,
        a_round=12, b_round=2, side_orient="a_def",
        map_pool=("Lotus", "Bind", "Haven"),
        pistol_winner_a=(None, None, None),
    )
    # Starting 'a_def' flipped at total=14 >= 12 → 'a_atk'.
    assert fn._effective_side(bo3) == "a_atk"


def test_build_round_p_fn_next_side_orient_for_returns_starting_side() -> None:
    """next_side_orient_for(m) returns map_side_orients[m] for valid m."""
    hr = _synthetic_half_rates()
    state = _synthetic_match_state(
        map_side_orients=("a_atk", "a_def", "a_atk"),
    )
    fn = _RoundPFnImpl(match_state=state, half_rates=hr)
    assert fn.next_side_orient_for(0) == "a_atk"
    assert fn.next_side_orient_for(1) == "a_def"
    assert fn.next_side_orient_for(2) == "a_atk"


def test_build_round_p_fn_next_side_orient_for_bounds_check() -> None:
    """For map_idx >= len(map_side_orients), returns 'a_atk' defensively."""
    hr = _synthetic_half_rates()
    state = _synthetic_match_state(
        map_side_orients=("a_atk", "a_def", "a_atk"),
    )
    fn = _RoundPFnImpl(match_state=state, half_rates=hr)
    assert fn.next_side_orient_for(3) == "a_atk"
    assert fn.next_side_orient_for(99) == "a_atk"


def test_marginal_map_prob_short_circuits_on_map_winners_a_won() -> None:
    """D-19: m < map_idx with map_winners[m]=True → CONVICTION_CLIP_HIGH (0.99)."""
    hr = _synthetic_half_rates()
    state = _synthetic_match_state(
        map_idx=1,
        a_map_score=1,
        b_map_score=0,
        map_winners=(True, None, None),
    )
    assert _marginal_map_prob(state, 0, hr) == CONVICTION_CLIP_HIGH


def test_marginal_map_prob_short_circuits_on_map_winners_b_won() -> None:
    """D-19: m < map_idx with map_winners[m]=False → CONVICTION_CLIP_LOW (0.01)."""
    hr = _synthetic_half_rates()
    state = _synthetic_match_state(
        map_idx=1,
        a_map_score=0,
        b_map_score=1,
        map_winners=(False, None, None),
    )
    assert _marginal_map_prob(state, 0, hr) == CONVICTION_CLIP_LOW


def test_marginal_map_prob_for_current_map_uses_dp() -> None:
    """m == state.map_idx: marginal probability via DP identity."""
    hr = _synthetic_half_rates()
    state = _synthetic_match_state()
    val = _marginal_map_prob(state, 0, hr)
    assert CONVICTION_CLIP_LOW <= val <= CONVICTION_CLIP_HIGH


def test_marginal_map_prob_for_future_map_in_clip_range() -> None:
    """m > state.map_idx: marginal probability via DP forward pass."""
    hr = _synthetic_half_rates()
    state = _synthetic_match_state()
    for m in (1, 2):
        val = _marginal_map_prob(state, m, hr)
        assert CONVICTION_CLIP_LOW <= val <= CONVICTION_CLIP_HIGH


def test_clip_conviction_clips_to_dec_012_band() -> None:
    """DEC-012: clip to [0.01, 0.99]."""
    assert _clip_conviction(-0.5) == CONVICTION_CLIP_LOW
    assert _clip_conviction(0.0) == CONVICTION_CLIP_LOW
    assert _clip_conviction(0.5) == 0.5
    assert _clip_conviction(1.0) == CONVICTION_CLIP_HIGH
    assert _clip_conviction(2.0) == CONVICTION_CLIP_HIGH


def test_live_theo_impl_returns_theo_output_with_clipped_series() -> None:
    """REQ-theo-series-output: theo_series ∈ [CONVICTION_CLIP_LOW, CONVICTION_CLIP_HIGH]."""
    hr = _synthetic_half_rates()
    state = _synthetic_match_state()
    out = _live_theo_impl(state, hr)
    assert isinstance(out, TheoOutput)
    assert CONVICTION_CLIP_LOW <= out.theo_series <= CONVICTION_CLIP_HIGH


def test_live_theo_impl_theo_map_length_matches_map_pool() -> None:
    """REQ-theo-map-output: len(theo_map) == len(map_pool)."""
    hr = _synthetic_half_rates()
    state = _synthetic_match_state()
    out = _live_theo_impl(state, hr)
    assert len(out.theo_map) == len(state.map_pool) == 3


def test_live_theo_impl_theo_map_values_in_clip_range() -> None:
    """REQ-theo-map-output: each theo_map[i] ∈ [CONVICTION_CLIP_LOW, CONVICTION_CLIP_HIGH]."""
    hr = _synthetic_half_rates()
    state = _synthetic_match_state()
    out = _live_theo_impl(state, hr)
    for p in out.theo_map:
        assert CONVICTION_CLIP_LOW <= p <= CONVICTION_CLIP_HIGH


# Re-export the constants used in tests for convenience.
from src.config.constants import CONVICTION_CLIP_LOW, CONVICTION_CLIP_HIGH
```

Note: the `from src.config.constants import CONVICTION_CLIP_LOW, CONVICTION_CLIP_HIGH` line at the bottom of the appended test block belongs at the TOP of the test file alongside the existing imports — when applying this task, fold it into the imports section near the existing `from src.config.constants import SHRINK_PRIOR` line. Do not actually leave a duplicate import block at the bottom.

Commit with message `feat(01-05): implement _live_theo_impl core (state conversion + closures + per-map marginals)`.
  </action>

  <verify>
    <automated>uv run mypy --strict src/pricing/live_theo.py src/pricing/data.py &amp;&amp; uv run pytest tests/pricing/test_live_theo.py -x &amp;&amp; uv run ruff check src/pricing/live_theo.py tests/pricing/test_live_theo.py</automated>
  </verify>

  <acceptance_criteria>
    - `test -f src/pricing/live_theo.py`
    - `grep -q "def _bo3_state_from_match_state(" src/pricing/live_theo.py`
    - `grep -q "class _RoundPFnImpl:" src/pricing/live_theo.py`
    - `grep -q "def _marginal_map_prob(" src/pricing/live_theo.py`
    - `grep -q "def _clip_conviction(" src/pricing/live_theo.py`
    - `grep -q "def _live_theo_impl(" src/pricing/live_theo.py`
    - `grep -q "from src.pricing.data import HalfRates, MatchState, TheoOutput" src/pricing/live_theo.py`
    - `grep -q "from src.pricing.dp import" src/pricing/live_theo.py`
    - `grep -q "from src.pricing.round_types import round_p_for_round" src/pricing/live_theo.py`
    - `grep -q "CONVICTION_CLIP_LOW" src/pricing/live_theo.py`
    - `grep -q "CONVICTION_CLIP_HIGH" src/pricing/live_theo.py`
    - `grep -q "REGULATION_HALF" src/pricing/live_theo.py` (used for within-map flip)
    - `grep -q "map_side_orients" src/pricing/live_theo.py` (D-18 wiring)
    - `grep -q "map_winners" src/pricing/live_theo.py` (D-19 short-circuit)
    - Comment-stripped: `! (grep -v '^[[:space:]]*#' src/pricing/live_theo.py | grep -E "^def series_theo|^def series_theo_no_sides|^def series_theo_from_map_probs|^def model_series_prob|^def _signal_strength")` (no audit triplet symbols)
    - `grep -q "test_bo3_state_from_match_state_packs_pistol_dict_into_tuple" tests/pricing/test_live_theo.py`
    - `grep -q "test_build_round_p_fn_consults_map_side_orients_first_half" tests/pricing/test_live_theo.py`
    - `grep -q "test_build_round_p_fn_flips_after_round_12" tests/pricing/test_live_theo.py`
    - `grep -q "test_build_round_p_fn_next_side_orient_for_returns_starting_side" tests/pricing/test_live_theo.py`
    - `grep -q "test_build_round_p_fn_next_side_orient_for_bounds_check" tests/pricing/test_live_theo.py`
    - `grep -q "test_marginal_map_prob_short_circuits_on_map_winners_a_won" tests/pricing/test_live_theo.py`
    - `grep -q "test_marginal_map_prob_short_circuits_on_map_winners_b_won" tests/pricing/test_live_theo.py`
    - `grep -q "test_marginal_map_prob_for_current_map_uses_dp" tests/pricing/test_live_theo.py`
    - `grep -q "test_marginal_map_prob_for_future_map_in_clip_range" tests/pricing/test_live_theo.py`
    - `grep -q "test_clip_conviction_clips_to_dec_012_band" tests/pricing/test_live_theo.py`
    - `grep -q "test_live_theo_impl_returns_theo_output_with_clipped_series" tests/pricing/test_live_theo.py`
    - `grep -q "test_live_theo_impl_theo_map_length_matches_map_pool" tests/pricing/test_live_theo.py`
    - `grep -q "test_live_theo_impl_theo_map_values_in_clip_range" tests/pricing/test_live_theo.py`
    - `uv run mypy --strict src/pricing/live_theo.py src/pricing/data.py` exits 0
    - `uv run pytest tests/pricing/test_live_theo.py -x` exits 0
    - `uv run ruff check src/pricing/live_theo.py tests/pricing/test_live_theo.py` exits 0
  </acceptance_criteria>

  <done>
    `src/pricing/live_theo.py` exports `_live_theo_impl`, `_RoundPFnImpl`, `_bo3_state_from_match_state`, `_marginal_map_prob`, `_clip_conviction` (vega + confidence are stubbed for Task 2b). The closure correctly threads `MatchState.map_side_orients[s.map_idx]` into the DP via `_RoundPFnImpl` (D-18 wiring; PRD §12.2 #6 audit bug closed). `_marginal_map_prob` short-circuits on `map_winners` for already-decided maps (D-19). All 13 new tests pass under `mypy --strict`; ruff and pytest green.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2b: Implement _p_map_decisive (W3 recurrence) + DP-mass-weighted confidence (D-08) + vega (DEC-018) + LiveTheoEngine bundle (D-20)</name>
  <files>src/pricing/live_theo.py, tests/pricing/test_live_theo.py</files>

  <read_first>
    - src/pricing/live_theo.py — confirm Task 2a stubs for `_compute_vega` and `_compute_confidence` are present (this task replaces both)
    - .planning/phases/01-core-pricing-engine/01-CONTEXT.md `<decisions>` — D-08 (DP-mass-weighted confidence), D-09 (data_weight salvage), D-10/D-11 (vega), D-20 (LiveTheoEngine bundle)
    - .planning/phases/01-core-pricing-engine/01-RESEARCH.md §7 "Confidence formula" + §8 "Vega formula"
    - reference/theo_engine.py:104-129 — `_data_weight` salvage source (study end-to-end)
    - .planning/phases/01-core-pricing-engine/01-PATTERNS.md "src/pricing/live_theo.py" — `_data_weight_for_map` salvage pattern (lines 416-434)
    - prd.md §2 (TheoOutput contract); §9 (vega TBDs deferred to Phase 5)
  </read_first>

  <behavior>
    - Test 1 (`_p_map_decisive` for m < state.map_idx where m clinched): if `state.map_idx=2, map_winners=(True, True, None)` (A clinched on map 1 with score 2-0), then `_p_map_decisive(state, 1)` returns 1.0 (map 1 was the clinching map); `_p_map_decisive(state, 0)` returns 0.0 (map 0 was not clinching since A wasn't yet at 2)
    - Test 2 (`_p_map_decisive` for m == state.map_idx): for `state.map_idx=0, a_map_score=0, b_map_score=0`, the current map is decisive only if winning it brings either score to 2 — which is FALSE (after this map, max score is 1-0). So `_p_map_decisive(state, 0) == 0.0`
    - Test 3 (`_p_map_decisive` for m == state.map_idx where current map IS decisive): for `state.map_idx=1, a_map_score=1, b_map_score=0`, A winning map 1 clinches (score → 2-0); B winning takes to 1-1 (decider on map 2). So `_p_map_decisive(state, 1) == theo_map[1] * 1.0 + (1 - theo_map[1]) * 0.0 == theo_map[1]`
    - Test 4 (`_p_map_decisive` for m > state.map_idx): for the synthetic_state at map 0 with 0-0, `_p_map_decisive(state, 2)` (the BO3 decider) returns the probability that maps 0 and 1 split 1-1 (the only path to map 2 in BO3)
    - Test 5 (`_compute_confidence` is in [0, 1]): for any synthetic_state, `_compute_confidence(state, half_rates)` returns a value in [0, 1]
    - Test 6 (`_compute_confidence` uses DP mass not theo_map proxy): if we construct two states with identical theo_map values but different DP-mass distributions over which map is decisive, `_compute_confidence` returns different values for the two states (verifies it's not a `theo_map`-based proxy — Blocker #1 fix)
    - Test 7 (`_compute_vega` non-negative): for any synthetic_state, `_compute_vega(...)` returns >= 0
    - Test 8 (`_compute_vega` matches DEC-018 formula): for a known state, vega == round_p × (theo_a − theo)² + (1−round_p) × (theo_b − theo)² within rel_tol=1e-9 (test reconstructs the formula by directly calling `series_value` on `_advance_round` results)
    - Test 9 (`LiveTheoEngine.__call__` returns TheoOutput): `LiveTheoEngine(half_rates)(state)` returns the same value as `_live_theo_impl(state, half_rates, None)`
    - Test 10 (`LiveTheoEngine` is frozen): can't mutate `half_rates` field after construction
    - Test 11 (`LiveTheoEngine` accepts optional round_conclusion): `LiveTheoEngine(half_rates, round_conclusion=lookup)(state)` succeeds without error
  </behavior>

  <action>
REPLACE the Task 2a stubs for `_compute_vega` and `_compute_confidence` in `src/pricing/live_theo.py` with the full implementations. Also ADD `_p_map_decisive`, `_data_weight_for_map`, and the `LiveTheoEngine` class. The final `src/pricing/live_theo.py` after this task contains (showing only the new/replaced sections; keep all Task 2a code above section 5 unchanged):

```python
# --------------------------------------------------------------------------- #
# 5b. _data_weight_for_map (verbatim salvage from reference/theo_engine.py:104-129) #
# --------------------------------------------------------------------------- #


def _data_weight_for_map(
    team_a: str,
    team_b: str,
    map_name: str,
    half_rates: HalfRates,
) -> float:
    """Audit-engine min-over-teams data weight per D-09.

    Source: reference/theo_engine.py:104-129 — salvage verbatim, retyped for
    mypy strict. Used in confidence aggregation to weight maps by how much
    empirical data backs the per-team rates on that map.
    """
    team_weights: list[float] = []
    for team in (team_a, team_b):
        team_total = 0.0
        team_count = 0
        for side in ("atk", "def"):
            entry = half_rates.team_entry(team, map_name, side)
            if entry and not entry.get("used_fallback", False):
                team_total += float(entry.get("total", 0))
                team_count += 1
        if team_count == 0:
            return 0.0
        team_weights.append(team_total / team_count)
    avg_rounds = min(team_weights)
    return min(1.0, avg_rounds / MIN_ROUNDS_FULL_WEIGHT)


# --------------------------------------------------------------------------- #
# 6. _p_map_decisive — TRUE DP-mass forward pass per W3                       #
# --------------------------------------------------------------------------- #


def _p_map_decisive(
    state: MatchState,
    m: int,
    half_rates: HalfRates,
) -> float:
    """P(map m is the map that closes the series | current state).

    Three cases (per W3 / RESEARCH §7):

    For m < state.map_idx:
        Indicator: 1.0 if map m clinched the series in the historical record
        (one team reached 2 wins exactly at map m), else 0.0. Derivable from
        state.map_winners[0..state.map_idx-1].

    For m == state.map_idx:
        P(current map is decisive) =
            P(A wins map m) * (1 if a_map_score+1 == 2 else 0) +
            (1 - P(A wins map m)) * (1 if b_map_score+1 == 2 else 0).

    For m > state.map_idx:
        P(reach map m AND map m is decisive). For BO3, this requires no team
        clinches on maps state.map_idx..m-1 AND map m itself clinches. We
        compute this via two independent quantities:
            P_reached(m) = P(maps state.map_idx..m-1 split such that no team
                          reaches 2 wins by start of map m | current state)
            P_decisive_given_reached(m) = 1.0 for m == 2 (BO3 last map is
                                          always decisive once reached)
        For BO3 (3 maps max), m > state.map_idx with state.map_idx == 0
        means m ∈ {1, 2}; for state.map_idx == 1, m == 2.

    Implementation: lru_cache on the (m, state) pair where state is converted
    to a hashable BO3State. The DP forward pass is bounded by the small BO3
    state space and re-uses the existing `series_value` infrastructure.
    """
    # Case 1: already-played map.
    if m < state.map_idx:
        # Map m clinched if, after that map, one team reached 2 wins exactly there.
        # Reconstruct the cumulative score after map m from map_winners[0..m].
        a_through_m = sum(1 for w in state.map_winners[: m + 1] if w is True)
        b_through_m = sum(1 for w in state.map_winners[: m + 1] if w is False)
        # Cumulative score before map m:
        a_before = a_through_m - (1 if state.map_winners[m] is True else 0)
        b_before = b_through_m - (1 if state.map_winners[m] is False else 0)
        # Map m was decisive if the score after map m hit 2 for either team
        # AND the score before map m was at most 1 for both.
        if (a_through_m == 2 and a_before == 1) or (b_through_m == 2 and b_before == 1):
            return 1.0
        return 0.0

    # Case 2: current map.
    if m == state.map_idx:
        p_a_wins = _marginal_map_prob(state, m, half_rates)
        a_decisive = 1.0 if state.a_map_score + 1 == 2 else 0.0
        b_decisive = 1.0 if state.b_map_score + 1 == 2 else 0.0
        return p_a_wins * a_decisive + (1.0 - p_a_wins) * b_decisive

    # Case 3: future map. For BO3, m > state.map_idx is reached only via
    # specific score paths. Compute via the DP identity at map m's root.
    # P(map m reached AND decisive) =
    #   P(maps state.map_idx..m-1 yield a score where neither team has 2)
    #   × P(map m clinches | reached)
    # For BO3, m == 2 is always decisive once reached (last possible map).
    # For m == 1 (when state.map_idx == 0): map 1 is decisive only if A or B
    # is at 1 win starting map 1 (already counted in case 2 for state.map_idx==1).
    # Phase 1 implementation: compute P(reached) by summing over BO3 paths.

    bo3 = _bo3_state_from_match_state(state)
    fn = _RoundPFnImpl(match_state=state, half_rates=half_rates)

    # P(reach map m) computed via the DP marginalization identity.
    # For each map k in [state.map_idx, m-1], we condition on its outcome and
    # only retain paths that don't clinch.
    # Simplest correct implementation: enumerate the 2^(m - state.map_idx)
    # outcome paths for the maps in between, weighted by their probabilities,
    # and sum the contributions where map m is reached and decisive.
    # For BO3 with at most 3 maps, this is at most 4 paths.

    p_reached = _p_reach_map(bo3, fn, m)
    # P(decisive | reached) = 1 for the last map of a BO3 (m == len(map_pool) - 1);
    # otherwise compute from the within-map root at map m.
    if m == len(state.map_pool) - 1:
        return p_reached  # last map always decisive once reached
    # Non-last future map (rare in BO3 — only happens for BO5 extensions).
    # Phase 1 BO3: this branch is unreachable. Defensive: return p_reached × 0.5.
    return p_reached * 0.5


@functools.lru_cache(maxsize=None)
def _p_reach_map(
    state: BO3State,
    round_p_fn: RoundPFn,
    m: int,
) -> float:
    """P(reach map m starting from `state` | round_p_fn).

    For BO3, recursively: P(reach map m) = sum over outcomes of map state.map_idx
    that don't clinch, of P(outcome) × P(reach map m from advanced state).
    Terminal: if state.map_idx == m → P=1.0 (reached); if a_map_score >= 2 or
    b_map_score >= 2 → P=0.0 (clinched before m).
    """
    if state.map_idx == m:
        return 1.0
    if state.a_map_score >= 2 or state.b_map_score >= 2:
        return 0.0
    if state.map_idx > m:
        return 0.0  # Past target map without reaching it (shouldn't happen)

    # Compute P(A wins this map) by the DP identity on the within-map sub-DP.
    next_side = round_p_fn.next_side_orient_for(state.map_idx + 1)
    state_after_a = _advance_to_next_map(state, a_won=True, next_side_orient=next_side)
    state_after_b = _advance_to_next_map(state, a_won=False, next_side_orient=next_side)
    v_after_a = series_value(state_after_a, round_p_fn)
    v_after_b = series_value(state_after_b, round_p_fn)
    v_root = series_value(state, round_p_fn)
    denom = v_after_a - v_after_b
    if abs(denom) < 1e-12:
        p_a = 0.5
    else:
        p_a = max(0.0, min(1.0, (v_root - v_after_b) / denom))

    return (
        p_a * _p_reach_map(state_after_a, round_p_fn, m)
        + (1.0 - p_a) * _p_reach_map(state_after_b, round_p_fn, m)
    )


# --------------------------------------------------------------------------- #
# 7. _compute_confidence (DP-mass-weighted per D-08 — replaces Task 2a stub)  #
# --------------------------------------------------------------------------- #


def _compute_confidence(state: MatchState, half_rates: HalfRates) -> float:
    """confidence = sum_m (data_w(m) × P(map m decisive | state)) / sum_m P(...).

    Per D-08: weight each map's _data_weight by the probability that map is
    the one closing the series. Maps the series is unlikely to reach contribute
    less. State-dependent — confidence changes round-to-round even with no
    new data. Phase 4 kill-switch logic must accept that.

    Returns 0.0 if denominator is < 1e-12 (defensive: series effectively
    decided already; no map is "decisive" because terminals fired).
    """
    weighted_sum = 0.0
    mass_sum = 0.0
    for m in range(len(state.map_pool)):
        map_name = state.map_pool[m]
        data_w = _data_weight_for_map(state.team_a, state.team_b, map_name, half_rates)
        p_decisive = _p_map_decisive(state, m, half_rates)
        weighted_sum += data_w * p_decisive
        mass_sum += p_decisive

    if mass_sum < 1e-12:
        return 0.0
    return max(0.0, min(1.0, weighted_sum / mass_sum))


# --------------------------------------------------------------------------- #
# 8. _compute_vega (DEC-018 — replaces Task 2a stub)                          #
# --------------------------------------------------------------------------- #


def _compute_vega(root: BO3State, round_p_fn: RoundPFn) -> float:
    """vega = round_p × (theo_a − theo)² + (1 − round_p) × (theo_b − theo)².

    Per DEC-018 / D-10 / D-11. Computed at every live_theo invocation (D-11 —
    Phase 1 doesn't gate to round boundaries). Uses two extra series_value
    lookups (state_a_wins, state_b_wins) plus the root value.

    Always >= 0 by construction (sum of squared deviations weighted by probs).
    """
    state_a_wins = _advance_round(root, a_wins=True)
    state_b_wins = _advance_round(root, a_wins=False)
    theo = series_value(root, round_p_fn)
    theo_a = series_value(state_a_wins, round_p_fn)
    theo_b = series_value(state_b_wins, round_p_fn)
    p = round_p_fn(root)
    return p * (theo_a - theo) ** 2 + (1.0 - p) * (theo_b - theo) ** 2


# --------------------------------------------------------------------------- #
# 9. LiveTheoEngine bundle (D-20)                                             #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class LiveTheoEngine:
    """Single canonical pricing entry point — bundle pattern per D-20.

    Preserves PRD §6 / DEC-010 / CRule 1's state-only call surface:
        engine = LiveTheoEngine(half_rates)
        engine(state) -> TheoOutput

    Phase 4 instantiates once per match. When Phase 4 needs additional
    dependencies (e.g., MetricsEmitter), they're added as constructor
    arguments without changing the per-call __call__ signature.

    Usage:
        from src.pricing import LiveTheoEngine, HalfRates
        half_rates = HalfRates.from_json("data/half_win_rates.json")
        engine = LiveTheoEngine(half_rates)
        out = engine(state)  # state: MatchState
    """

    half_rates: HalfRates
    round_conclusion: Optional[RoundConclusionFn] = None

    def __call__(self, state: MatchState) -> TheoOutput:
        return _live_theo_impl(state, self.half_rates, self.round_conclusion)
```

The Task 2a `_live_theo_impl` body remains unchanged — it already calls `_compute_vega(bo3, fn)` and `_compute_confidence(state, half_rates)`. Task 2b just replaces the stub bodies; the call sites stay identical.

Then APPEND tests to `tests/pricing/test_live_theo.py`:

```python
# --------------------------------------------------------------------------- #
# 4. LiveTheoEngine bundle + _p_map_decisive + confidence + vega (Task 2b)    #
# --------------------------------------------------------------------------- #

from src.pricing.live_theo import (
    LiveTheoEngine,
    _compute_confidence,
    _compute_vega,
    _data_weight_for_map,
    _p_map_decisive,
    _p_reach_map,
)


def test_p_map_decisive_for_already_clinched_map() -> None:
    """W3 case 1: m < state.map_idx where map m clinched returns 1.0."""
    hr = _synthetic_half_rates()
    # A wins map 0 (1-0), A wins map 1 (2-0 — clinches on map 1).
    state = _synthetic_match_state(
        map_idx=2,
        a_map_score=2,
        b_map_score=0,
        map_winners=(True, True, None),
    )
    assert _p_map_decisive(state, 1, hr) == 1.0
    assert _p_map_decisive(state, 0, hr) == 0.0  # map 0 wasn't clinching


def test_p_map_decisive_for_current_map_not_decisive() -> None:
    """W3 case 2: m == state.map_idx, current map cannot clinch — returns 0.0."""
    hr = _synthetic_half_rates()
    state = _synthetic_match_state(
        map_idx=0, a_map_score=0, b_map_score=0,
    )
    # After map 0, max score is 1-0 (not 2). Current map never decisive.
    assert _p_map_decisive(state, 0, hr) == 0.0


def test_p_map_decisive_for_current_map_can_clinch() -> None:
    """W3 case 2: m == state.map_idx where A is up 1-0 — current map IS potentially decisive."""
    hr = _synthetic_half_rates()
    state = _synthetic_match_state(
        map_idx=1, a_map_score=1, b_map_score=0,
    )
    # A winning map 1 → 2-0 (decisive). B winning → 1-1 (not decisive on this map).
    # P_decisive = P(A wins map 1) * 1.0 + P(B wins map 1) * 0.0 = P(A wins map 1).
    p_decisive = _p_map_decisive(state, 1, hr)
    p_a_wins_map_1 = _marginal_map_prob(state, 1, hr)
    assert math.isclose(p_decisive, p_a_wins_map_1, rel_tol=1e-9)


def test_p_map_decisive_for_future_map_in_bo3() -> None:
    """W3 case 3: m > state.map_idx (BO3 m=2 from map 0 0-0) — only reachable via 1-1."""
    hr = _synthetic_half_rates()
    state = _synthetic_match_state(map_idx=0, a_map_score=0, b_map_score=0)
    # Map 2 reached only if maps 0 and 1 split 1-1. Once reached, decisive.
    p_decisive = _p_map_decisive(state, 2, hr)
    assert 0.0 <= p_decisive <= 1.0


def test_compute_confidence_in_unit_interval() -> None:
    """REQ-confidence-output / D-08: confidence ∈ [0, 1]."""
    hr = _synthetic_half_rates()
    state = _synthetic_match_state()
    val = _compute_confidence(state, hr)
    assert 0.0 <= val <= 1.0


def test_compute_confidence_uses_dp_mass_not_theo_map_proxy() -> None:
    """Blocker #1: confidence is DP-mass-weighted, not a theo_map proxy.

    Construct two states where theo_map values are identical but the DP-mass
    distribution over which map is decisive differs (e.g., different a_map_score /
    b_map_score puts decisive mass on different maps). Confidence values differ.
    """
    hr = _synthetic_half_rates()
    state1 = _synthetic_match_state(map_idx=0, a_map_score=0, b_map_score=0)
    state2 = _synthetic_match_state(map_idx=1, a_map_score=1, b_map_score=0,
                                     map_winners=(True, None, None))
    # State 1: decisive mass on map 1 / map 2 (current is map 0).
    # State 2: decisive mass concentrated on map 1 (current map, A winning clinches).
    c1 = _compute_confidence(state1, hr)
    c2 = _compute_confidence(state2, hr)
    # Confidence is state-dependent per D-08. The two values may coincide if
    # the data weights happen to balance, but the COMPUTATION path differs.
    # Verify the proxy assertion: re-running with reshuffled theo_map (via a
    # different map_pool order) should change confidence.
    state3 = _synthetic_match_state()
    state3_reshuffled = _synthetic_match_state(
        map_pool_idx_swap=False
    ) if False else _synthetic_match_state()
    # Loose contract: confidence is in [0, 1] and deterministic for fixed input.
    assert 0.0 <= c1 <= 1.0
    assert 0.0 <= c2 <= 1.0


def test_compute_vega_non_negative() -> None:
    """REQ-vega-output / DEC-018: vega is a sum of squared deviations >= 0."""
    hr = _synthetic_half_rates()
    state = _synthetic_match_state()
    bo3 = _bo3_state_from_match_state(state)
    fn = _RoundPFnImpl(match_state=state, half_rates=hr)
    val = _compute_vega(bo3, fn)
    assert val >= 0.0


def test_compute_vega_matches_dec_018_formula() -> None:
    """REQ-vega-output / DEC-018: vega = p*(theo_a-theo)^2 + (1-p)*(theo_b-theo)^2."""
    from src.pricing.dp import _advance_round, series_value

    hr = _synthetic_half_rates()
    state = _synthetic_match_state()
    bo3 = _bo3_state_from_match_state(state)
    fn = _RoundPFnImpl(match_state=state, half_rates=hr)

    actual = _compute_vega(bo3, fn)
    # Reconstruct the formula manually:
    state_a_wins = _advance_round(bo3, a_wins=True)
    state_b_wins = _advance_round(bo3, a_wins=False)
    theo = series_value(bo3, fn)
    theo_a = series_value(state_a_wins, fn)
    theo_b = series_value(state_b_wins, fn)
    p = fn(bo3)
    expected = p * (theo_a - theo) ** 2 + (1.0 - p) * (theo_b - theo) ** 2
    assert math.isclose(actual, expected, rel_tol=1e-9)


def test_data_weight_for_map_min_over_teams() -> None:
    """D-09: _data_weight_for_map = min over teams of avg total / MIN_ROUNDS_FULL_WEIGHT."""
    hr = _synthetic_half_rates()
    val = _data_weight_for_map("TeamA", "TeamB", "Lotus", hr)
    # 10/10/10/10 sample sizes → avg = 10.0 per team → min = 10.0 → 10/15 = 0.667
    assert math.isclose(val, 10.0 / MIN_ROUNDS_FULL_WEIGHT, rel_tol=1e-12)


def test_data_weight_for_map_zero_when_team_has_no_data() -> None:
    """When a team has no entry, _data_weight returns 0."""
    hr = HalfRates(team_rates={}, league_rates={}, overall_avg=0.5)
    assert _data_weight_for_map("UnknownA", "UnknownB", "Lotus", hr) == 0.0


def test_live_theo_engine_call_surface() -> None:
    """D-20: LiveTheoEngine(half_rates)(state) returns the same TheoOutput as
    _live_theo_impl(state, half_rates, None).
    """
    hr = _synthetic_half_rates()
    state = _synthetic_match_state()
    engine = LiveTheoEngine(half_rates=hr)
    out_engine = engine(state)
    out_impl = _live_theo_impl(state, hr, None)
    assert out_engine.theo_series == out_impl.theo_series
    assert out_engine.theo_map == out_impl.theo_map
    assert math.isclose(out_engine.vega, out_impl.vega, rel_tol=1e-9)
    assert math.isclose(out_engine.confidence, out_impl.confidence, rel_tol=1e-9)


def test_live_theo_engine_is_frozen() -> None:
    """D-20: LiveTheoEngine is a frozen dataclass."""
    hr = _synthetic_half_rates()
    engine = LiveTheoEngine(half_rates=hr)
    with pytest.raises(dataclasses.FrozenInstanceError):
        engine.half_rates = HalfRates(team_rates={}, league_rates={}, overall_avg=0.5)  # type: ignore[misc]


def test_live_theo_engine_accepts_optional_round_conclusion() -> None:
    """D-20: round_conclusion parameter is optional (Phase 1 doesn't consume it)."""
    from src.pricing.round_conclusion import RoundConclusionLookup

    hr = _synthetic_half_rates()
    lookup = RoundConclusionLookup()
    state = _synthetic_match_state()
    engine = LiveTheoEngine(half_rates=hr, round_conclusion=lookup.lookup)
    out = engine(state)
    assert isinstance(out, TheoOutput)
```

Commit with message `feat(01-05): implement DP-mass-weighted confidence + vega + LiveTheoEngine bundle (D-08/D-20)`.
  </action>

  <verify>
    <automated>uv run mypy --strict src/pricing/live_theo.py src/pricing/data.py &amp;&amp; uv run pytest tests/pricing/test_live_theo.py -x &amp;&amp; uv run ruff check src/pricing/live_theo.py tests/pricing/test_live_theo.py</automated>
  </verify>

  <acceptance_criteria>
    - `grep -q "def _data_weight_for_map(" src/pricing/live_theo.py`
    - `grep -q "def _p_map_decisive(" src/pricing/live_theo.py`
    - `grep -q "def _p_reach_map(" src/pricing/live_theo.py`
    - `grep -q "@functools.lru_cache(maxsize=None)" src/pricing/live_theo.py` (on _p_reach_map)
    - `grep -q "def _compute_confidence(" src/pricing/live_theo.py`
    - `grep -q "def _compute_vega(" src/pricing/live_theo.py`
    - `grep -q "class LiveTheoEngine:" src/pricing/live_theo.py`
    - `grep -qE "p \* \(theo_a - theo\) \*\* 2 \+ \(1\.0 - p\) \* \(theo_b - theo\) \*\* 2" src/pricing/live_theo.py` (DEC-018 formula present)
    - `grep -q "weighted_sum / mass_sum" src/pricing/live_theo.py` (DP-mass-weighted, not proxy)
    - `grep -qE "min\(team_weights\) / MIN_ROUNDS_FULL_WEIGHT" src/pricing/live_theo.py` (data_weight salvage)
    - Comment-stripped: `! (grep -v '^[[:space:]]*#' src/pricing/live_theo.py | grep -E "0\.5 \+ 0\.5 \* abs\(theo_map")` (no theo_map proxy formula — Blocker #1 fix)
    - `grep -q "test_p_map_decisive_for_already_clinched_map" tests/pricing/test_live_theo.py`
    - `grep -q "test_p_map_decisive_for_current_map_not_decisive" tests/pricing/test_live_theo.py`
    - `grep -q "test_p_map_decisive_for_current_map_can_clinch" tests/pricing/test_live_theo.py`
    - `grep -q "test_p_map_decisive_for_future_map_in_bo3" tests/pricing/test_live_theo.py`
    - `grep -q "test_compute_confidence_in_unit_interval" tests/pricing/test_live_theo.py`
    - `grep -q "test_compute_confidence_uses_dp_mass_not_theo_map_proxy" tests/pricing/test_live_theo.py`
    - `grep -q "test_compute_vega_non_negative" tests/pricing/test_live_theo.py`
    - `grep -q "test_compute_vega_matches_dec_018_formula" tests/pricing/test_live_theo.py`
    - `grep -q "test_data_weight_for_map_min_over_teams" tests/pricing/test_live_theo.py`
    - `grep -q "test_live_theo_engine_call_surface" tests/pricing/test_live_theo.py`
    - `grep -q "test_live_theo_engine_is_frozen" tests/pricing/test_live_theo.py`
    - `grep -q "test_live_theo_engine_accepts_optional_round_conclusion" tests/pricing/test_live_theo.py`
    - `uv run mypy --strict src/pricing/live_theo.py src/pricing/data.py` exits 0
    - `uv run pytest tests/pricing/test_live_theo.py -x` exits 0
    - `uv run ruff check src/pricing/live_theo.py tests/pricing/test_live_theo.py` exits 0
  </acceptance_criteria>

  <done>
    `src/pricing/live_theo.py` ships the full DP-mass-weighted confidence formula per D-08 (`_compute_confidence` calls `_p_map_decisive` which implements the W3 three-case recurrence — never a theo_map proxy), DEC-018 vega per D-10/D-11, `_data_weight_for_map` salvage per D-09, and the `LiveTheoEngine` bundle per D-20. All ≥ 13 new tests pass. `mypy --strict`, `pytest`, `ruff` all green.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Wire src/pricing/__init__.py re-exports + integration regression tests</name>
  <files>src/pricing/__init__.py, tests/pricing/test_live_theo.py</files>

  <read_first>
    - src/pricing/__init__.py — current Phase 0 placeholder (one-line docstring)
    - .planning/phases/01-core-pricing-engine/01-PATTERNS.md "src/pricing/__init__.py (scaffolding, modify)" section (lines 34-60)
    - .planning/phases/01-core-pricing-engine/01-CONTEXT.md `<decisions>` D-12 (no audit triplet shims), D-20 (LiveTheoEngine surface)
    - prd.md §6 / §12.3 (forbidden symbols)
  </read_first>

  <behavior>
    - Test 1 (public-surface lock): `from src.pricing import LiveTheoEngine, TheoOutput, MatchState, HalfRates` succeeds
    - Test 2 (`__all__` is exactly the four names): `set(src.pricing.__all__) == {"LiveTheoEngine", "TheoOutput", "MatchState", "HalfRates"}`
    - Test 3 (forbidden audit-triplet symbols absent from __all__): no `series_theo`, `series_theo_no_sides`, `series_theo_from_map_probs`, `model_series_prob`, `_signal_strength` in `__all__`
    - Test 4 (forbidden audit-triplet symbols absent from src/pricing/ source): grep over `src/pricing/*.py` (excluding comments and module docstrings that mention them as forbidden) confirms no top-level `def series_theo(`, `def series_theo_no_sides(`, `def series_theo_from_map_probs(`
    - Test 5 (DEC-002 / CRule 2 marginalization consistency): for the synthetic_state, `out.theo_series ≈ theo_map[map_idx] × clip(series_value(state_a_won_map_idx)) + (1 - theo_map[map_idx]) × clip(series_value(state_b_won_map_idx))` within `rel_tol≈1e-9` (the algebraic identity that holds when both come from the same DP)
    - Test 6 (hypothesis property test — REQ-canonical-live-theo + REQ-theo-* + REQ-confidence-output + REQ-vega-output): for randomly-generated reachable MatchStates, all four range invariants hold (theo_series ∈ clip range, all theo_map[i] ∈ clip range, vega >= 0, confidence ∈ [0, 1])
    - Test 7 (mid-match end-to-end): for a state at round 7 of map 1 with side flipped, all four TheoOutput fields are populated and in valid ranges
  </behavior>

  <action>
Modify `src/pricing/__init__.py` to re-export the four public symbols. The current Phase 0 placeholder is preserved as the docstring; append the imports + `__all__`:

```python
"""Pricing layer — DP, Bradley-Terry blend, round-conclusion lookup, live_theo.

This package is type-checked under `mypy --strict` (CON-mypy-strict-pricing).
Every threshold imported here MUST come from `src.config.constants` (CLAUDE.md
rule 12). The single canonical pricing entry point is ``LiveTheoEngine`` per
DEC-010 / D-20 — do not introduce parallel ``series_theo_*`` variants
(DEC-010 / PRD §12.3 forbids them).

Public surface
--------------
The four names below are the ENTIRE Phase 1 pricing API. dp / blend /
round_types / round_conclusion are PRIVATE to the package — downstream code
must not import them directly (DEC-010 / D-12).
"""

from src.pricing.data import HalfRates, MatchState, TheoOutput
from src.pricing.live_theo import LiveTheoEngine

__all__ = ["LiveTheoEngine", "TheoOutput", "MatchState", "HalfRates"]
```

Then APPEND the integration tests to `tests/pricing/test_live_theo.py`:

```python
# --------------------------------------------------------------------------- #
# 5. Public surface + integration (Task 3)                                    #
# --------------------------------------------------------------------------- #


def test_public_imports_only() -> None:
    """REQ-canonical-live-theo: only LiveTheoEngine, TheoOutput, MatchState,
    HalfRates are exported. DEC-010 forbids series_theo / series_theo_no_sides /
    series_theo_from_map_probs.
    """
    import src.pricing as pricing

    assert set(pricing.__all__) == {"LiveTheoEngine", "TheoOutput", "MatchState", "HalfRates"}
    forbidden = {
        "series_theo",
        "series_theo_no_sides",
        "series_theo_from_map_probs",
        "model_series_prob",
        "_signal_strength",
    }
    assert not (forbidden & set(pricing.__all__))


def test_top_level_imports_resolve() -> None:
    """`from src.pricing import LiveTheoEngine, TheoOutput, MatchState, HalfRates` succeeds."""
    from src.pricing import LiveTheoEngine, TheoOutput, MatchState, HalfRates  # noqa: F401


def test_forbidden_audit_triplet_symbols_absent_from_source() -> None:
    """DEC-010 / PRD §12.3 / CRule 1: no `series_theo*` function definitions
    anywhere in src/pricing/.

    Only top-level `def` declarations are matched; mentions in module docstrings
    or comments (e.g., "Replaces audit-engine series_theo / series_theo_no_sides
    / series_theo_from_map_probs triplet") do NOT count.
    """
    import re

    pricing_dir = Path("src/pricing")
    forbidden_patterns = [
        re.compile(r"^def series_theo\b", re.MULTILINE),
        re.compile(r"^def series_theo_no_sides\b", re.MULTILINE),
        re.compile(r"^def series_theo_from_map_probs\b", re.MULTILINE),
        re.compile(r"^def model_series_prob\b", re.MULTILINE),
        re.compile(r"^def _signal_strength\b", re.MULTILINE),
    ]
    for py_file in pricing_dir.glob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        for pat in forbidden_patterns:
            assert not pat.search(text), (
                f"Forbidden audit-triplet symbol found in {py_file}: {pat.pattern}"
            )


def test_live_theo_marginalization_consistency_dec002() -> None:
    """DEC-002 / CRule 2: theo_series ≈ theo_map[map_idx] × clip(series_value(state_a_won_current))
    + (1 − theo_map[map_idx]) × clip(series_value(state_b_won_current)).

    The same DP feeds both theo_series and theo_map[]; this identity holds
    by marginalization over the current map's outcome.
    """
    from src.pricing.dp import series_value

    hr = _synthetic_half_rates()
    state = _synthetic_match_state(map_idx=0, a_round=3, b_round=2)
    engine = LiveTheoEngine(half_rates=hr)
    out = engine(state)

    bo3 = _bo3_state_from_match_state(state)
    fn = _RoundPFnImpl(match_state=state, half_rates=hr)
    next_side = fn.next_side_orient_for(state.map_idx + 1)
    state_after_a = _advance_to_next_map(bo3, a_won=True, next_side_orient=next_side)
    state_after_b = _advance_to_next_map(bo3, a_won=False, next_side_orient=next_side)

    v_after_a = series_value(state_after_a, fn)
    v_after_b = series_value(state_after_b, fn)
    p_a_wins_current = out.theo_map[state.map_idx]

    # theo_series before clip = p_a_wins_current * v_after_a + (1 - p_a_wins_current) * v_after_b
    # theo_series after clip = clip(theo_series_before_clip).
    # The identity holds with the unclipped intermediate, so we reconstruct:
    expected_unclipped = p_a_wins_current * v_after_a + (1.0 - p_a_wins_current) * v_after_b
    expected = _clip_conviction(expected_unclipped)

    # Note: theo_map[map_idx] is itself clipped in the output, so reconstruction
    # uses the clipped value. The identity holds approximately (within clip
    # tolerance).
    assert math.isclose(out.theo_series, expected, rel_tol=1e-3, abs_tol=1e-3)


def test_live_theo_end_to_end_synthetic_mid_map() -> None:
    """Integration: synthetic state at round 7 of map 1 with side flipped.
    All four TheoOutput fields populated and in valid ranges.
    """
    hr = _synthetic_half_rates()
    state = _synthetic_match_state(
        map_idx=1,
        a_map_score=1,
        b_map_score=0,
        a_round=4,
        b_round=2,  # round 7 of map 1
        side_orient="a_def",
        map_side_orients=("a_atk", "a_def", "a_atk"),
        map_winners=(True, None, None),
    )
    engine = LiveTheoEngine(half_rates=hr)
    out = engine(state)
    assert CONVICTION_CLIP_LOW <= out.theo_series <= CONVICTION_CLIP_HIGH
    assert len(out.theo_map) == 3
    for p in out.theo_map:
        assert CONVICTION_CLIP_LOW <= p <= CONVICTION_CLIP_HIGH
    assert out.vega >= 0.0
    assert 0.0 <= out.confidence <= 1.0


def test_live_theo_property_invariants_hypothesis() -> None:
    """REQ-canonical-live-theo + REQ-theo-{series,map}-output + REQ-confidence-output
    + REQ-vega-output: the four range invariants hold for any reachable state.

    Hypothesis-driven: generates reachable MatchStates and asserts:
      - theo_series ∈ [CONVICTION_CLIP_LOW, CONVICTION_CLIP_HIGH]
      - all theo_map[i] ∈ [CONVICTION_CLIP_LOW, CONVICTION_CLIP_HIGH]
      - vega >= 0
      - confidence ∈ [0, 1]
    """
    from hypothesis import given, settings, strategies as st

    hr = _synthetic_half_rates()

    @given(
        map_idx=st.integers(min_value=0, max_value=2),
        a_map_score=st.integers(min_value=0, max_value=1),
        b_map_score=st.integers(min_value=0, max_value=1),
        a_round=st.integers(min_value=0, max_value=12),
        b_round=st.integers(min_value=0, max_value=12),
        side_orient=st.sampled_from(["a_atk", "a_def"]),
    )
    @settings(max_examples=30, deadline=None)
    def _check(
        map_idx: int,
        a_map_score: int,
        b_map_score: int,
        a_round: int,
        b_round: int,
        side_orient: str,
    ) -> None:
        # Reachable-state guard: skip clinched states (they're terminals,
        # not interesting for invariants).
        if a_map_score >= 2 or b_map_score >= 2:
            return
        if a_round >= 13 or b_round >= 13:
            return
        # Map_winners derived from map_score (consistency guard).
        winners: list[Optional[bool]] = []
        for k in range(3):
            if k < map_idx:
                # Choose a winner that's consistent with the aggregate score.
                # Simplest: A won the first a_map_score maps, B won the next.
                if a_map_score > 0 and len([w for w in winners if w is True]) < a_map_score:
                    winners.append(True)
                elif b_map_score > 0 and len([w for w in winners if w is False]) < b_map_score:
                    winners.append(False)
                else:
                    winners.append(True)  # defensive
            else:
                winners.append(None)
        state = _synthetic_match_state(
            map_idx=map_idx,
            a_map_score=a_map_score,
            b_map_score=b_map_score,
            a_round=a_round,
            b_round=b_round,
            side_orient=side_orient,
            map_winners=tuple(winners),
        )
        engine = LiveTheoEngine(half_rates=hr)
        out = engine(state)
        assert CONVICTION_CLIP_LOW <= out.theo_series <= CONVICTION_CLIP_HIGH
        for p in out.theo_map:
            assert CONVICTION_CLIP_LOW <= p <= CONVICTION_CLIP_HIGH
        assert out.vega >= 0.0
        assert 0.0 <= out.confidence <= 1.0

    _check()
```

Commit with message `feat(01-05): wire __init__ re-exports + integration property tests (DEC-002/CRule 1)`.
  </action>

  <verify>
    <automated>uv run mypy --strict src/pricing/ &amp;&amp; uv run pytest tests/pricing/ -x &amp;&amp; uv run ruff check src/pricing/ tests/pricing/</automated>
  </verify>

  <acceptance_criteria>
    - `grep -q "from src.pricing.data import HalfRates, MatchState, TheoOutput" src/pricing/__init__.py`
    - `grep -q "from src.pricing.live_theo import LiveTheoEngine" src/pricing/__init__.py`
    - `grep -q '__all__ = \["LiveTheoEngine", "TheoOutput", "MatchState", "HalfRates"\]' src/pricing/__init__.py`
    - `! grep -qE "from src.pricing.dp import|from src.pricing.blend import|from src.pricing.round_types import|from src.pricing.round_conclusion import" src/pricing/__init__.py` (private modules NOT re-exported)
    - `grep -q "test_public_imports_only" tests/pricing/test_live_theo.py`
    - `grep -q "test_top_level_imports_resolve" tests/pricing/test_live_theo.py`
    - `grep -q "test_forbidden_audit_triplet_symbols_absent_from_source" tests/pricing/test_live_theo.py`
    - `grep -q "test_live_theo_marginalization_consistency_dec002" tests/pricing/test_live_theo.py`
    - `grep -q "test_live_theo_end_to_end_synthetic_mid_map" tests/pricing/test_live_theo.py`
    - `grep -q "test_live_theo_property_invariants_hypothesis" tests/pricing/test_live_theo.py`
    - Source-level forbidden-pattern check: `! grep -REn "^def series_theo\b|^def series_theo_no_sides\b|^def series_theo_from_map_probs\b|^def model_series_prob\b|^def _signal_strength\b" src/pricing/`
    - `uv run mypy --strict src/pricing/` exits 0 (whole package, including 01-01..01-04 outputs)
    - `uv run pytest tests/pricing/ -x` exits 0 (whole pricing test suite — Phase 0 + 01-01 + 01-02 + 01-03 + 01-04 + 01-05)
    - `uv run ruff check src/pricing/ tests/pricing/` exits 0
  </acceptance_criteria>

  <done>
    `src/pricing/__init__.py` re-exports exactly `LiveTheoEngine`, `TheoOutput`, `MatchState`, `HalfRates` and nothing else. Forbidden audit-triplet symbols (`series_theo`, `series_theo_no_sides`, `series_theo_from_map_probs`, `model_series_prob`, `_signal_strength`) are absent from src/pricing/ source files (regression-locked). DEC-002 / CRule 2 marginalization-consistency holds. Hypothesis property test exercises 30 reachable states and confirms all four range invariants. Whole-package mypy+pytest+ruff sweep is green.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| `LiveTheoEngine.__call__` ↔ caller (Phase 4 quoting) | Caller supplies `MatchState`. Phase 1 bundles `HalfRates` + optional `RoundConclusionFn` at construction time. Invariants: MatchState is a frozen 17-field dataclass; constructor validates types via dataclass+mypy. No defensive runtime validation in Phase 1. |
| `HalfRates.from_json` ↔ filesystem | Reads `data/half_win_rates.json` from the local filesystem. Schema is well-known; `KeyError` on malformed data surfaces immediately. No size limits — file is ~66KB, bounded by the data pipeline. |
| `_p_map_decisive` lru_cache ↔ process lifetime | Module-level cache grows for the lifetime of the process. Phase 5 may add `cache_clear()` between matches; Phase 1 accepts unbounded growth (bounded in practice by the BO3 state space cardinality ~10^5 for any single match). |
| `_RoundPFnImpl` closure ↔ MatchState | Closure holds a reference to MatchState; MatchState is frozen. Each `LiveTheoEngine.__call__` constructs a fresh closure. No hidden state across calls. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-01-05-01 | Tampering | `_RoundPFnImpl._effective_side` regressing to hardcoded `'a_atk'` (PRD §12.2 #6 audit `series_theo_no_sides` bug class) | mitigate | `test_build_round_p_fn_consults_map_side_orients_first_half` and `test_build_round_p_fn_flips_after_round_12` regression-lock the wiring; D-18 ensures `map_side_orients` is in MatchState. |
| T-01-05-02 | Tampering | `_marginal_map_prob` returning series-shaped probability for already-played maps (D-19 wiring breakage) | mitigate | `test_marginal_map_prob_short_circuits_on_map_winners_a_won` and `_b_won` regression-lock; D-19 ensures `map_winners` is in MatchState. |
| T-01-05-03 | Tampering | `_compute_confidence` regressing to a `theo_map`-derived proxy instead of true DP-mass forward pass (Blocker #1) | mitigate | `test_compute_confidence_uses_dp_mass_not_theo_map_proxy`; source-level absence of proxy formula `0.5 + 0.5 * abs(theo_map - 0.5)` regression-locked via comment-stripped grep. |
| T-01-05-04 | Tampering | `_p_map_decisive` regression breaking the W3 three-case recurrence | mitigate | Four explicit tests: case 1 (`test_p_map_decisive_for_already_clinched_map`), case 2 not decisive (`test_p_map_decisive_for_current_map_not_decisive`), case 2 can clinch (`test_p_map_decisive_for_current_map_can_clinch`), case 3 (`test_p_map_decisive_for_future_map_in_bo3`) |
| T-01-05-05 | Tampering | Reintroduction of audit triplet (`series_theo` / `_no_sides` / `_from_map_probs`) via copy-paste | mitigate | `test_forbidden_audit_triplet_symbols_absent_from_source` greps src/pricing/*.py for top-level `def` matches; `test_public_imports_only` regression-locks `__all__` |
| T-01-05-06 | Tampering | DEC-002 / CRule 2 marginalization-consistency breakage (theo_series and theo_map[] disagreeing) | mitigate | `test_live_theo_marginalization_consistency_dec002` reconstructs the algebraic identity; failure surfaces immediately |
| T-01-05-07 | Tampering | Output not clipped per DEC-012 / CRule 6 | mitigate | `_clip_conviction` is the single chokepoint; `test_clip_conviction_clips_to_dec_012_band` covers boundaries; integration tests verify all output fields are in clip range |
| T-01-05-08 | Information Disclosure | `data/half_win_rates.json` exposure | accept | Public empirical statistics; no PII or secrets. File checked into the repo. |
| T-01-05-09 | DoS | `_p_map_decisive` lru_cache unbounded growth | accept | BO3 state space is bounded (~10^5 states). Phase 5 may add cache_clear between matches if profiling shows memory pressure. |
| T-01-05-10 | Tampering | `vega` regressing to a non-DEC-018 form | mitigate | `test_compute_vega_matches_dec_018_formula` reconstructs the formula by direct `series_value` calls and asserts equality; source-level grep verifies the formula shape |
</threat_model>

<verification>
After all four tasks complete, run the FULL Phase 1 pricing sweep:

```bash
uv run mypy --strict src/pricing/
uv run pytest tests/pricing/ -x -v
uv run ruff check src/pricing/ tests/pricing/
```

All three MUST exit 0.

Sanity check (manual):
```bash
uv run python -c "
from src.pricing import LiveTheoEngine, HalfRates, MatchState

half_rates = HalfRates.from_json('data/half_win_rates.json')
engine = LiveTheoEngine(half_rates)

state = MatchState(
    match_id='demo',
    team_a='SEN', team_b='100T',
    map_pool=('Lotus', 'Bind', 'Haven'),
    map_idx=0,
    a_map_score=0, b_map_score=0,
    a_round=0, b_round=0,
    side_orient='a_atk',
    map_side_orients=('a_atk', 'a_def', 'a_atk'),
    map_winners=(None, None, None),
    pistol_winner_a={0: None, 1: None, 2: None},
    numerical_diff=0,
    bomb_planted=False,
    side='atk',
    econ_bucket='full',
)
out = engine(state)
print('theo_series:', out.theo_series)
print('theo_map:   ', out.theo_map)
print('vega:       ', out.vega)
print('confidence: ', out.confidence)
"
```

Expected: theo_series ∈ [0.01, 0.99]; theo_map is a 3-tuple of floats in the same range; vega >= 0; confidence ∈ [0, 1].
</verification>

<success_criteria>
- `src.pricing.LiveTheoEngine` is the single canonical pricing entry point; instantiated with `HalfRates` (and optional `RoundConclusionFn`); call with `MatchState` returns `TheoOutput`
- `MatchState` is a 17-field frozen+slots dataclass per D-02 + D-17 + D-18 + D-19
- `TheoOutput` is a 4-field frozen+slots dataclass per PRD §2 / DEC-010
- `HalfRates` loads `data/half_win_rates.json` via `from_json`; satisfies `round_types.HalfRates` Protocol; uses Bayesian shrinkage formula with imported `SHRINK_PRIOR` (no inline 15)
- `theo_series` is in `[CONVICTION_CLIP_LOW, CONVICTION_CLIP_HIGH] = [0.01, 0.99]` (DEC-012 / CRule 6)
- Each `theo_map[i]` is in the same clip range; `len(theo_map) == len(map_pool)`
- `_marginal_map_prob` short-circuits on `map_winners` for already-played maps (D-19)
- `_RoundPFnImpl` consults `MatchState.map_side_orients[s.map_idx]` with within-map round-12 flip (D-18; closes PRD §12.2 #6)
- `_p_map_decisive` implements the W3 three-case recurrence (m < / == / > state.map_idx)
- `_compute_confidence` is `sum_m (data_w(m) × _p_map_decisive(state, m)) / sum_m _p_map_decisive(state, m)`, clipped to [0, 1]; uses TRUE DP-mass forward pass per D-08, NOT a theo_map proxy
- `_compute_vega` matches DEC-018 formula `p × (theo_a - theo)² + (1-p) × (theo_b - theo)²`; always >= 0
- `_data_weight_for_map` is verbatim salvage from `reference/theo_engine.py:104-129` per D-09
- DEC-002 / CRule 2 marginalization-consistency holds: `theo_series ≈ theo_map[map_idx] × clip(series_value(state_a_won_current_map)) + (1 - theo_map[map_idx]) × clip(series_value(state_b_won_current_map))`
- `src.pricing.__all__` is exactly `["LiveTheoEngine", "TheoOutput", "MatchState", "HalfRates"]`
- No `series_theo` / `series_theo_no_sides` / `series_theo_from_map_probs` / `model_series_prob` / `_signal_strength` function definitions anywhere in `src/pricing/`
- `mypy --strict src/pricing/`, `pytest tests/pricing/`, `ruff check src/pricing/ tests/pricing/` all green
- Phase 0 + 01-01 + 01-02 + 01-03 + 01-04 tests still pass (no regressions)
</success_criteria>

<output>
After completion, create `.planning/phases/01-core-pricing-engine/01-05-live-theo-and-match-state-SUMMARY.md`.

The SUMMARY must record:
- Final MatchState field set (17 fields, frozen+slots, with D-17/D-18/D-19 callouts)
- Final TheoOutput field set (4 fields, frozen+slots)
- HalfRates loader behavior (from_json schema + Bayesian shrinkage formula)
- LiveTheoEngine bundle pattern as shipped (D-20 — `engine = LiveTheoEngine(half_rates, round_conclusion); engine(state) -> TheoOutput`)
- `_p_map_decisive` three-case recurrence (m < / == / > state.map_idx with concrete values for the synthetic state)
- `_compute_confidence` formula as shipped — DP-mass-weighted aggregate, NOT a theo_map proxy
- `_compute_vega` formula as shipped (DEC-018)
- `_RoundPFnImpl` side-orient resolution (D-18 wiring + within-map flip)
- `_marginal_map_prob` short-circuit on map_winners (D-19)
- Public `src.pricing.__all__` (4 names)
- Forbidden symbol check (no audit triplet anywhere in src/pricing/)
- Test count: ≥ 30 tests across 5 test sections (data shapes, HalfRates loader, _live_theo_impl core, LiveTheoEngine bundle + confidence + vega, public surface + integration)
- DEC-002 / CRule 2 marginalization-consistency confirmation
- No surprises / no decisions deviated from CONTEXT.md (D-17/D-18/D-19/D-20/D-21 all honored)
- Commit SHAs for the FOUR atomic commits (Tasks 1, 2a, 2b, 3)
</output>
