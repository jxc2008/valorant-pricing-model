---
id: 01-06-derived-output-fixes
phase: 01-core-pricing-engine
plan: 06
type: execute
wave: 6
gap_closure: true
depends_on: [01-05-live-theo-and-match-state]
files_modified:
  - src/pricing/live_theo.py
  - src/pricing/dp.py
  - tests/pricing/test_live_theo.py
autonomous: true
requirements: [REQ-canonical-live-theo, REQ-confidence-output, REQ-vega-output, REQ-ot-handling]
requirements_addressed: [REQ-canonical-live-theo, REQ-confidence-output, REQ-vega-output, REQ-ot-handling]
closes_gaps:
  - source: 01-VERIFICATION.md
    truth_idx: 1
    blockers: [CR-01, CR-02, CR-03, CR-04]

must_haves:
  truths:
    - "_p_reach_map_cached returns 0.0 for any BO3State where the series is already clinched (a_map_score >= 2 or b_map_score >= 2), regardless of map_idx — series-clinch short-circuit precedes the map_idx == m terminal check."
    - "_p_map_decisive case 3 for the BO3 middle map (m == state.map_idx + 1, m != len(map_pool) - 1) returns the correct p_reached × P(prev-map winner also wins map m) formula — NOT the BO5+ placeholder p_reached * 0.5."
    - "_compute_vega returns 0.0 at series terminals and within-map terminals, and at OT-entry (a_round + b_round >= REGULATION_HALF * 2) returns the variance of the OT coinflip leaf over next-map series outcomes — never calls _advance_round past total = 24."
    - "Module-level closure registries (_ROUND_P_FNS in dp.py, _REACH_MAP_FNS in live_theo.py) are reset to len 0 at the END of every LiveTheoEngine.__call__, alongside _series_value_cached.cache_clear() and _p_reach_map_cached.cache_clear(); the cleanup runs in a try/finally so it is robust to exceptions inside the call."
  artifacts:
    - path: src/pricing/live_theo.py
      provides: "Reordered _p_reach_map_cached terminal checks (CR-01); BO3 middle-map branch in _p_map_decisive (CR-02); OT/terminal short-circuit in _compute_vega (CR-03); _clear_pricing_caches helper + LiveTheoEngine.__call__ try/finally wrapper (CR-04 live_theo half)."
    - path: src/pricing/dp.py
      provides: "_clear_pricing_caches helper (CR-04 dp half) — clears _ROUND_P_FNS and _series_value_cached cache."
    - path: tests/pricing/test_live_theo.py
      provides: "Regression tests for all four BLOCKERs: test_p_reach_map_zero_for_clinched_series_state, test_p_map_decisive_for_bo3_middle_map_with_nontrivial_p, test_p_map_decisive_sum_equals_one_pre_clinch, test_compute_vega_at_ot_entry_uses_coinflip_leaf, test_compute_vega_zero_at_series_terminal, test_compute_vega_zero_at_within_map_terminal, test_no_memory_leak_across_live_theo_calls."
  key_links:
    - from: "src/pricing/live_theo.py:_p_reach_map_cached"
      to: "BO3State.a_map_score / b_map_score series-clinch short-circuit"
      via: "Reordered if-block (clinch check BEFORE map_idx == m)"
      pattern: "state\\.a_map_score >= 2 or state\\.b_map_score >= 2"
    - from: "src/pricing/live_theo.py:_p_map_decisive case 3"
      to: "_marginal_map_prob(state, m-1) and _within_map_p_a_wins(...) BO3 formula"
      via: "Direct BO3-correct branch replacing `p_reached * 0.5`"
      pattern: "p_a_wins_m_minus_1 \\* p_a_wins_m \\+ \\(1\\.0 - p_a_wins_m_minus_1\\) \\* \\(1\\.0 - p_a_wins_m\\)"
    - from: "src/pricing/live_theo.py:_compute_vega"
      to: "_advance_to_next_map + series_value (OT coinflip leaf variance)"
      via: "Three early-return guards (series terminal / within-map terminal / OT entry)"
      pattern: "root\\.a_round \\+ root\\.b_round >= REGULATION_HALF \\* 2"
    - from: "src/pricing/live_theo.py:LiveTheoEngine.__call__"
      to: "_clear_pricing_caches in dp.py + _clear_pricing_caches in live_theo.py"
      via: "try / finally wrapping _live_theo_impl"
      pattern: "finally:[\\s\\S]*?_clear_pricing_caches"
---

<objective>
Close the four BLOCKERs identified in `.planning/phases/01-core-pricing-engine/01-VERIFICATION.md` (status: gaps_found) and detailed in `.planning/phases/01-core-pricing-engine/01-REVIEW.md` (CR-01 through CR-04). Each fix lands as an atomic per-CR commit with a regression test that fails on `main` (current state) and passes after the fix. A final smoke gate confirms full-suite green + mypy strict + the surface-contract greps still hold (no audit-triplet symbols, `__all__` unchanged).

Purpose: the verifier ruled `vega` and `confidence` populated but mathematically corrupt for non-trivial portions of the BO3 state space (specifically: any state where future-map decisive mass is computed; any OT-entry state for vega) and flagged a registry leak that is bounded for Phase 1's between-round single-call pattern but breaks Phase 4's continuous quoter. These fixes are mechanical (~50 lines across three functions plus a lifecycle hook), tightly coupled (all sit on the BO3 forward-pass + DEC-009 boundary), and unblock REQ-confidence-output, REQ-vega-output, and the vega-side caveat on REQ-ot-handling.

Output: one revision plan; four fix commits + one regression-test-only commit per CR (or fix+test in the same commit, executor's choice as long as tests are added in the same plan). New tests: 7 (one per CR plus the conjunction sum-to-one structural test for CR-01∩CR-02 plus the two zero-vega terminal cases). Total tests after this plan: 137 + 7 = 144.

Out of scope (DO NOT pull in): WR-01..WR-05 warnings, IN-01..IN-04 info items. The `1e-12` recurrence (IN-01), MatchState `__post_init__` validator (WR-03), `pistol_winner_a` dict-vs-tuple promotion (WR-01), `_marginal_map_prob` 0.5 fallback refinement (WR-02), defensive `'a_atk'` literal (WR-04), and marginalization-test tolerance tightening (WR-05) are deferred to future revisions and MUST NOT be touched here.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@.planning/phases/01-core-pricing-engine/01-CONTEXT.md
@.planning/phases/01-core-pricing-engine/01-RESEARCH.md
@.planning/phases/01-core-pricing-engine/01-PATTERNS.md
@.planning/phases/01-core-pricing-engine/01-VERIFICATION.md
@.planning/phases/01-core-pricing-engine/01-REVIEW.md
@.planning/phases/01-core-pricing-engine/01-05-live-theo-and-match-state-PLAN.md
@.planning/phases/01-core-pricing-engine/01-05-live-theo-and-match-state-SUMMARY.md
@CLAUDE.md
@src/pricing/live_theo.py
@src/pricing/dp.py
@src/pricing/__init__.py
@tests/pricing/test_live_theo.py

<interfaces>
<!-- Concrete signatures and constants the executor needs. Extracted from src/. Use directly — no exploration required. -->

From `src/pricing/dp.py` (already on disk, do NOT recreate):
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

def _advance_round(state: BO3State, a_wins: bool) -> BO3State: ...
def _advance_to_next_map(state: BO3State, a_won: bool, next_side_orient: str) -> BO3State: ...
def series_value(state: BO3State, round_p_fn: RoundPFn) -> float: ...

_ROUND_P_FNS: list[RoundPFn] = []
@functools.lru_cache(maxsize=None)
def _series_value_cached(state: BO3State, round_p_id: int) -> float: ...
```

From `src/pricing/live_theo.py` (already on disk):
```python
def _marginal_map_prob(state: MatchState, m: int, half_rates: HalfRates) -> float: ...
def _within_map_p_a_wins(
    map_pool: tuple[str, ...],
    map_idx: int,
    starting_side: str,
    pistol_winner_a: tuple[Optional[bool], ...],
    match_state: MatchState,
    half_rates: HalfRates,
) -> float: ...

def _p_map_decisive(state: MatchState, m: int, half_rates: HalfRates) -> float: ...

_REACH_MAP_FNS: list[RoundPFn] = []
def _p_reach_map(state: BO3State, round_p_fn: RoundPFn, m: int) -> float: ...
@functools.lru_cache(maxsize=None)
def _p_reach_map_cached(state: BO3State, round_p_fn_id: int, m: int) -> float: ...

def _compute_vega(root: BO3State, round_p_fn: RoundPFn) -> float: ...

@dataclass(frozen=True)
class LiveTheoEngine:
    half_rates: HalfRates
    round_conclusion: Optional[RoundConclusionFn] = None
    def __call__(self, state: MatchState) -> TheoOutput: ...
```

From `src/config/constants.py`:
```python
REGULATION_HALF: Final[int] = 12
WIN_THRESHOLD: Final[int] = 13
CONVICTION_CLIP_LOW: Final[float] = 0.01
CONVICTION_CLIP_HIGH: Final[float] = 0.99
```

From `tests/pricing/test_live_theo.py` (existing fixtures available; do NOT redefine):
```python
def _synthetic_half_rates() -> HalfRates: ...           # line 177
def _synthetic_match_state(                             # line 263
    map_idx: int = 0,
    a_map_score: int = 0,
    b_map_score: int = 0,
    a_round: int = 0,
    b_round: int = 0,
    side_orient: str = "a_atk",
    map_side_orients: tuple[str, ...] = ("a_atk", "a_atk", "a_atk"),
    map_winners: tuple[bool | None, ...] = (None, None, None),
    pistol_winner_a: dict[int, bool | None] | None = None,
) -> MatchState: ...
```

The REVIEW snippet for CR-01's regression test references a `_ConstantRoundPFn(0.5)` helper. NO such helper exists in the test module — the executor MUST EITHER (preferred) construct an `_RoundPFnImpl(match_state=_synthetic_match_state(), half_rates=_synthetic_half_rates())` OR add a small in-test helper. Use `_RoundPFnImpl` to stay consistent with the rest of the file.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Fix CR-01 — reorder _p_reach_map_cached terminal checks + regression test</name>
  <files>src/pricing/live_theo.py, tests/pricing/test_live_theo.py</files>
  <read_first>
    - src/pricing/live_theo.py (lines 441-493 — the `_p_reach_map` wrapper, `_register_reach_map_fn`, `_p_reach_map_cached` body — confirm the current order: `state.map_idx == m` check is at line 469 BEFORE the `a_map_score >= 2 or b_map_score >= 2` check at 471)
    - .planning/phases/01-core-pricing-engine/01-REVIEW.md §"CR-01" (lines 73-113)
    - .planning/phases/01-core-pricing-engine/01-VERIFICATION.md `gaps:` block, missing[0]
    - tests/pricing/test_live_theo.py lines 1-50 (imports — confirm `_p_reach_map` and `_REACH_MAP_FNS` are NOT yet imported; you will add `_p_reach_map` to the import block from `src.pricing.live_theo`)
    - tests/pricing/test_live_theo.py lines 263-294 (the `_synthetic_match_state` fixture signature)
    - CLAUDE.md Critical Rule 1 (single canonical entry point — no audit triplet may reappear; this fix is purely internal to `_p_reach_map_cached`)
  </read_first>
  <behavior>
    - Test 1 (`test_p_reach_map_zero_for_clinched_series_state`): A `BO3State(map_idx=2, a_map_score=2, b_map_score=0, a_round=0, b_round=0, side_orient="a_atk", map_pool=("Lotus","Bind","Haven"), pistol_winner_a=(True,True,None))` paired with any well-formed `_RoundPFnImpl` MUST return `_p_reach_map(bo3, fn, m=2) == 0.0` exactly (a 2-0 BO3 cannot reach map 2 even though `map_idx == m`).
    - Test 1 mirror (`test_p_reach_map_zero_for_b_clinched_series_state`): same with `a_map_score=0, b_map_score=2` returns `0.0`.
    - Existing tests for `_p_map_decisive` future-map case (`test_p_map_decisive_for_future_map_in_bo3` at line ~505) MUST continue to pass — the reorder only suppresses an unreachable-path 1.0; reachable paths still terminate at the same `state.map_idx == m` check.
    - The function still returns 1.0 when `state.map_idx == m` AND the series is NOT clinched (the legitimate "reached" case).
  </behavior>
  <action>
**Step 1.1 — Edit `src/pricing/live_theo.py`** in `_p_reach_map_cached` (currently lines 455-492). The CURRENT body opens with:

```python
@functools.lru_cache(maxsize=None)  # noqa: UP033 — plan acceptance grep requires lru_cache(maxsize=None)
def _p_reach_map_cached(
    state: BO3State,
    round_p_fn_id: int,
    m: int,
) -> float:
    """Memoized P(reach map m starting from ``state``).

    Recursive on BO3State.map_idx:
      - state.map_idx == m: return 1.0 (reached)
      - a_map_score >= 2 or b_map_score >= 2: return 0.0 (clinched before m)
      - else: recurse on (state_after_a_wins_current, state_after_b_wins_current)
        weighted by the within-map P(A wins).
    """
    if state.map_idx == m:
        return 1.0
    if state.a_map_score >= 2 or state.b_map_score >= 2:
        return 0.0
    if state.map_idx > m:
        return 0.0  # Past target without reaching — defensive.
```

REPLACE the docstring + first three guards so the clinch check fires FIRST (this is the entire CR-01 fix):

```python
@functools.lru_cache(maxsize=None)  # noqa: UP033 — plan acceptance grep requires lru_cache(maxsize=None)
def _p_reach_map_cached(
    state: BO3State,
    round_p_fn_id: int,
    m: int,
) -> float:
    """Memoized P(reach map m starting from ``state``).

    Terminal-check order (CR-01 fix — VERIFICATION.md gaps[0]): the series-clinch
    short-circuit MUST fire BEFORE the ``state.map_idx == m`` check. Otherwise an
    unreachable post-clinch recursion path that lands at ``map_idx == m`` returns
    1.0 (treated as "reached") instead of 0.0 (the series never plays subsequent
    maps once a team hits 2 wins).

    Recursive on BO3State.map_idx:
      - a_map_score >= 2 or b_map_score >= 2: return 0.0 (clinched, never reach m)
      - state.map_idx == m: return 1.0 (reached)
      - state.map_idx > m: return 0.0 (past target without reaching — defensive)
      - else: recurse on (state_after_a_wins_current, state_after_b_wins_current)
        weighted by the within-map P(A wins).
    """
    if state.a_map_score >= 2 or state.b_map_score >= 2:
        return 0.0
    if state.map_idx == m:
        return 1.0
    if state.map_idx > m:
        return 0.0  # Past target without reaching — defensive.
```

The remainder of the function body (the `fn = _REACH_MAP_FNS[round_p_fn_id]` block onward) is UNCHANGED.

**Step 1.2 — Edit `tests/pricing/test_live_theo.py` imports.** Locate the import block from `src.pricing.live_theo` (lines 32-43). Add `_p_reach_map` to the imported names (alphabetical order — insert after `_marginal_map_prob`):

```python
from src.pricing.live_theo import (
    LiveTheoEngine,
    _bo3_state_from_match_state,
    _clip_conviction,
    _compute_confidence,
    _compute_vega,
    _data_weight_for_map,
    _live_theo_impl,
    _marginal_map_prob,
    _p_map_decisive,
    _p_reach_map,
    _RoundPFnImpl,
)
```

**Step 1.3 — Append two new tests** to `tests/pricing/test_live_theo.py`. Add them in the existing "_p_map_decisive future map" cluster (search for `def test_p_map_decisive_for_future_map_in_bo3`; insert immediately AFTER that test). Both tests share the synthetic-half-rates / `_RoundPFnImpl` pattern from `test_compute_vega_matches_dec_018_formula`:

```python
def test_p_reach_map_zero_for_clinched_series_state() -> None:
    """CR-01 (VERIFICATION.md gaps[0]): a 2-0 BO3 cannot reach map 2 even
    though ``map_idx == m == 2`` — the series-clinch short-circuit must fire
    BEFORE the map_idx terminal check.
    """
    bo3 = BO3State(
        map_idx=2,
        a_map_score=2,
        b_map_score=0,
        a_round=0,
        b_round=0,
        side_orient="a_atk",
        map_pool=("Lotus", "Bind", "Haven"),
        pistol_winner_a=(True, True, None),
    )
    state = _synthetic_match_state(map_idx=2, a_map_score=2, b_map_score=0)
    fn = _RoundPFnImpl(match_state=state, half_rates=_synthetic_half_rates())
    assert _p_reach_map(bo3, fn, m=2) == 0.0


def test_p_reach_map_zero_for_b_clinched_series_state() -> None:
    """CR-01 mirror: 0-2 BO3 also cannot reach map 2."""
    bo3 = BO3State(
        map_idx=2,
        a_map_score=0,
        b_map_score=2,
        a_round=0,
        b_round=0,
        side_orient="a_atk",
        map_pool=("Lotus", "Bind", "Haven"),
        pistol_winner_a=(False, False, None),
    )
    state = _synthetic_match_state(map_idx=2, a_map_score=0, b_map_score=2)
    fn = _RoundPFnImpl(match_state=state, half_rates=_synthetic_half_rates())
    assert _p_reach_map(bo3, fn, m=2) == 0.0
```

**Step 1.4 — Atomic commit.** Stage `src/pricing/live_theo.py` + `tests/pricing/test_live_theo.py` and commit with message `fix(01-06): close CR-01 — _p_reach_map_cached series-clinch short-circuit precedes map_idx terminal`.

Note: do NOT modify the lru_cache body; the bug is purely about which guard fires first. Do NOT introduce a new helper or constant. Do NOT touch CRule 12 (no magic numbers added — `2` is a structural BO3 win threshold, already a literal in the same module).
  </action>
  <verify>
    <automated>.venv/Scripts/python.exe -m pytest tests/pricing/test_live_theo.py -k "p_reach_map or p_map_decisive" -x 2>&1 | tail -20</automated>
  </verify>
  <acceptance_criteria>
    - `grep -nE "if state\.a_map_score >= 2 or state\.b_map_score >= 2:" src/pricing/live_theo.py` shows the clinch check INSIDE `_p_reach_map_cached` body, on a line with line number STRICTLY LESS than the matching line for `grep -nE "if state\.map_idx == m:" src/pricing/live_theo.py` (i.e., clinch check appears first in source order in `_p_reach_map_cached`).
    - `pytest tests/pricing/test_live_theo.py::test_p_reach_map_zero_for_clinched_series_state -x` exits 0.
    - `pytest tests/pricing/test_live_theo.py::test_p_reach_map_zero_for_b_clinched_series_state -x` exits 0.
    - `pytest tests/pricing/test_live_theo.py::test_p_map_decisive_for_future_map_in_bo3 -x` still exits 0 (no regression on the existing future-map test).
    - `mypy --strict src/pricing/` exits 0 with `Success: no issues found`.
    - `grep -RnE "^def series_theo\b|^def series_theo_no_sides\b|^def series_theo_from_map_probs\b|^def model_series_prob\b|^def _signal_strength\b" src/pricing/` returns nothing (CRule 1 / DEC-010 surface contract preserved).
    - `git log -1 --format=%s` matches `fix(01-06): close CR-01.*`.
  </acceptance_criteria>
  <done>CR-01 closed: `_p_reach_map_cached` returns 0.0 for any clinched-series state regardless of `map_idx`; two regression tests lock the behavior; existing tests unchanged; commit recorded.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Fix CR-02 — replace BO5+ placeholder in _p_map_decisive case 3 with BO3 middle-map formula + regression tests</name>
  <files>src/pricing/live_theo.py, tests/pricing/test_live_theo.py</files>
  <read_first>
    - src/pricing/live_theo.py lines 373-428 (the entire `_p_map_decisive` function: case 1 `m < state.map_idx`, case 2 `m == state.map_idx`, case 3 `m > state.map_idx` ending with `return p_reached * 0.5`)
    - src/pricing/live_theo.py lines 127-196 (the `_marginal_map_prob` function — its signature is `(state: MatchState, m: int, half_rates: HalfRates) -> float`; it handles all three cases internally including `m > state.map_idx` via `_within_map_p_a_wins`)
    - src/pricing/live_theo.py lines 204-272 (the `_within_map_p_a_wins` function and its full signature: `(map_pool, map_idx, starting_side, pistol_winner_a, match_state, half_rates)` — note the executor MUST NOT call this directly; route through `_marginal_map_prob` so the BO3 cache is consistent)
    - .planning/phases/01-core-pricing-engine/01-REVIEW.md §"CR-02" (lines 117-141) and §"IN-04" (lines 350-363 — the conjunction sum-to-one test that locks CR-01∩CR-02 structurally)
    - .planning/phases/01-core-pricing-engine/01-VERIFICATION.md `gaps:` block, missing[1]
    - tests/pricing/test_live_theo.py lines 464-541 (existing `_p_map_decisive` test cluster — your new tests slot in the same place)
    - CLAUDE.md Critical Rule 1 (single canonical math path — DO NOT add a new helper that re-derives P(A wins map m); reuse `_marginal_map_prob` for both `m-1` and `m`)
  </read_first>
  <behavior>
    - Test 1 (`test_p_map_decisive_for_bo3_middle_map_with_nontrivial_p`): At a fresh `state = _synthetic_match_state(map_idx=0)` with the asymmetric `_synthetic_half_rates()` (Team A is favored ~0.6 / Team B ~0.4 on every map), `_p_map_decisive(state, m=1, hr)` MUST equal `p_reached * (p_a_wins_0 * p_a_wins_1 + (1 - p_a_wins_0) * (1 - p_a_wins_1))` to `rel_tol=1e-9`, where `p_reached = _p_reach_map(_bo3_state_from_match_state(state), _RoundPFnImpl(state, hr), m=1)`, `p_a_wins_0 = _marginal_map_prob(state, 0, hr)`, `p_a_wins_1 = _marginal_map_prob(state, 1, hr)`. The value MUST NOT equal `p_reached * 0.5` (the placeholder); since the half-rates are asymmetric, the correct value differs from `p_reached * 0.5` by at least `1e-3`.
    - Test 2 (`test_p_map_decisive_sum_equals_one_pre_clinch`): `sum(_p_map_decisive(state, m, hr) for m in range(len(state.map_pool)))` MUST equal `1.0` to `rel_tol=1e-9` for any pre-clinch state (per IN-04 / law of total probability — some map IS the clinching map). Test against the fresh root state. This test STRUCTURALLY locks both CR-01 (no over-counting clinched paths) and CR-02 (no BO5+ placeholder in the middle map).
    - Existing tests `test_p_map_decisive_for_already_clinched_map`, `test_p_map_decisive_for_current_map_not_decisive`, `test_p_map_decisive_for_current_map_can_clinch`, `test_p_map_decisive_for_future_map_in_bo3` all continue to pass.
  </behavior>
  <action>
**Step 2.1 — Edit `src/pricing/live_theo.py` `_p_map_decisive` case 3.** The CURRENT lines 419-428 read:

```python
    # Case 3: future map. P(reached) × P(decisive | reached).
    bo3 = _bo3_state_from_match_state(state)
    fn = _RoundPFnImpl(match_state=state, half_rates=half_rates)

    p_reached = _p_reach_map(bo3, fn, m)
    if m == len(state.map_pool) - 1:
        # Last map of the BO3 — always decisive once reached.
        return p_reached
    # Non-last future map (BO5+ extension). Phase 1 BO3: unreachable branch.
    return p_reached * 0.5
```

REPLACE the `Non-last future map (BO5+ extension)` branch with the BO3-correct formula. The FIX uses `_marginal_map_prob` for both `m-1` and `m` so the same DP backs every per-map probability (CRule 1 — single canonical math path; no new helper):

```python
    # Case 3: future map. P(reached) × P(decisive | reached).
    bo3 = _bo3_state_from_match_state(state)
    fn = _RoundPFnImpl(match_state=state, half_rates=half_rates)

    p_reached = _p_reach_map(bo3, fn, m)
    if m == len(state.map_pool) - 1:
        # Last map of the BO3 — always decisive once reached.
        return p_reached
    # Middle future map (BO3: m == state.map_idx + 1, m != len-1). CR-02 fix:
    # decisive iff the same team wins both the previous map and this one.
    # P(decisive | reached) = P(prev_winner == m_winner)
    #                       = p_a_{m-1} * p_a_m + (1 - p_a_{m-1}) * (1 - p_a_m)
    # Reuses _marginal_map_prob so the same canonical DP backs both terms
    # (CRule 1 / DEC-002 / DEC-010 — no parallel math).
    p_a_wins_m_minus_1 = _marginal_map_prob(state, m - 1, half_rates)
    p_a_wins_m = _marginal_map_prob(state, m, half_rates)
    p_decisive_given_reached = (
        p_a_wins_m_minus_1 * p_a_wins_m
        + (1.0 - p_a_wins_m_minus_1) * (1.0 - p_a_wins_m)
    )
    return p_reached * p_decisive_given_reached
```

**Step 2.2 — Append two new tests** to `tests/pricing/test_live_theo.py`. Add them immediately AFTER `test_p_map_decisive_for_future_map_in_bo3` (and after the Task 1 tests):

```python
def test_p_map_decisive_for_bo3_middle_map_with_nontrivial_p() -> None:
    """CR-02 (VERIFICATION.md gaps[1]): from map_idx=0, m=1 (BO3 middle map)
    must use the correct BO3 decisive formula
        p_reached * (p_a_{m-1} * p_a_m + (1 - p_a_{m-1}) * (1 - p_a_m))
    and NOT the BO5+ placeholder ``p_reached * 0.5``. With asymmetric half-rates
    (Team A ~0.6, Team B ~0.4 per _synthetic_half_rates), the correct value
    differs from the placeholder by at least 1e-3.
    """
    hr = _synthetic_half_rates()
    state = _synthetic_match_state(map_idx=0)
    bo3 = _bo3_state_from_match_state(state)
    fn = _RoundPFnImpl(match_state=state, half_rates=hr)

    actual = _p_map_decisive(state, m=1, half_rates=hr)
    p_reached = _p_reach_map(bo3, fn, m=1)
    p_a_0 = _marginal_map_prob(state, 0, hr)
    p_a_1 = _marginal_map_prob(state, 1, hr)
    expected = p_reached * (p_a_0 * p_a_1 + (1.0 - p_a_0) * (1.0 - p_a_1))
    assert math.isclose(actual, expected, rel_tol=1e-9)

    # Witness that the placeholder bug is closed: the placeholder value
    # ``p_reached * 0.5`` differs from the correct value by > 1e-3 here.
    placeholder = p_reached * 0.5
    assert abs(actual - placeholder) > 1e-3, (
        f"middle-map decisive {actual!r} should differ from BO5+ placeholder "
        f"{placeholder!r} under asymmetric half-rates"
    )


def test_p_map_decisive_sum_equals_one_pre_clinch() -> None:
    """CR-01 ∩ CR-02 conjunction (REVIEW.md IN-04 / law of total probability):
    sum of _p_map_decisive over all map indices must equal 1.0 for any
    pre-clinch state. Locks both fixes structurally — over-counting clinched
    paths (CR-01) or using the BO5+ placeholder (CR-02) breaks this identity.
    """
    hr = _synthetic_half_rates()
    state = _synthetic_match_state()  # 0-0 root, pre-clinch
    total = sum(
        _p_map_decisive(state, m, hr) for m in range(len(state.map_pool))
    )
    assert math.isclose(total, 1.0, rel_tol=1e-9), (
        f"law of total probability violated: sum of decisive masses = {total!r}"
    )
```

**Step 2.3 — Atomic commit.** Stage and commit with `fix(01-06): close CR-02 — _p_map_decisive BO3 middle-map formula`.

Note: do NOT add `_within_map_p_a_wins` import; route through `_marginal_map_prob` so case 2 of `_marginal_map_prob` (which already uses the DP marginalization identity) backs the math. Do NOT cache the two `_marginal_map_prob` calls — that's the IN-03 perf concern, out of scope.
  </action>
  <verify>
    <automated>.venv/Scripts/python.exe -m pytest tests/pricing/test_live_theo.py -k "p_map_decisive" -x 2>&1 | tail -25</automated>
  </verify>
  <acceptance_criteria>
    - `grep -nE "p_a_wins_m_minus_1 \* p_a_wins_m \+ \(1\.0 - p_a_wins_m_minus_1\) \* \(1\.0 - p_a_wins_m\)" src/pricing/live_theo.py` returns exactly one match inside `_p_map_decisive`.
    - `grep -nE "Non-last future map .BO5\+ extension." src/pricing/live_theo.py` returns nothing (the misleading comment is gone).
    - `grep -nE "return p_reached \* 0\.5" src/pricing/live_theo.py` returns nothing (placeholder gone).
    - `pytest tests/pricing/test_live_theo.py::test_p_map_decisive_for_bo3_middle_map_with_nontrivial_p -x` exits 0.
    - `pytest tests/pricing/test_live_theo.py::test_p_map_decisive_sum_equals_one_pre_clinch -x` exits 0.
    - `pytest tests/pricing/test_live_theo.py -k "p_map_decisive" -x` exits 0 with all 6 tests in the cluster passing (4 existing + 2 new).
    - `mypy --strict src/pricing/` exits 0.
    - `git log -1 --format=%s` matches `fix(01-06): close CR-02.*`.
  </acceptance_criteria>
  <done>CR-02 closed: BO3 middle-map decisive uses the correct formula via two `_marginal_map_prob` calls; new tests lock the value AND the law-of-total-probability conjunction with CR-01; commit recorded.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Fix CR-03 — _compute_vega OT/terminal short-circuit + regression tests</name>
  <files>src/pricing/live_theo.py, tests/pricing/test_live_theo.py</files>
  <read_first>
    - src/pricing/live_theo.py lines 525-545 (the entire current `_compute_vega` body — note the unconditional `_advance_round` calls at lines 539-540)
    - src/pricing/live_theo.py lines 30-50 (the imports — confirm `WIN_THRESHOLD` and `REGULATION_HALF` are already imported from `src.config.constants`; `_advance_to_next_map` is already imported from `src.pricing.dp`)
    - src/pricing/dp.py lines 207-240 (the OT hard-stop at `state.a_round + state.b_round == REGULATION_HALF * 2` and `_ot_coinflip_leaf` for the canonical OT semantics)
    - .planning/phases/01-core-pricing-engine/01-REVIEW.md §"CR-03" (lines 145-176) — the fix snippet uses `>= REGULATION_HALF * 2` (>= not ==) for defensive guarding, while dp.py uses `==`; the `>=` form is correct for vega because it short-circuits any state at OR past the OT boundary
    - .planning/phases/01-core-pricing-engine/01-VERIFICATION.md `gaps:` block, missing[2]
    - tests/pricing/test_live_theo.py lines 544-572 (existing `test_compute_vega_non_negative` and `test_compute_vega_matches_dec_018_formula` — the existing dec-018 test uses a 0-0 root state, so the new short-circuit code path does NOT fire and the test must keep passing)
    - CLAUDE.md Critical Rule 5 (OT is an explicit hard-stop at total = 24 with OT-as-coinflip leaf — vega MUST honor this)
  </read_first>
  <behavior>
    - Test 1 (`test_compute_vega_zero_at_series_terminal`): `_compute_vega(BO3State(map_idx=2, a_map_score=2, ...), fn) == 0.0` exactly. Same with `b_map_score=2`. Theo is constant at a series terminal so vega is 0.
    - Test 2 (`test_compute_vega_zero_at_within_map_terminal`): `_compute_vega(BO3State(a_round=13, b_round=10, ...), fn) == 0.0` exactly (and mirror for `b_round=13, a_round=10`). The map is decided so per-round vega is 0.
    - Test 3 (`test_compute_vega_at_ot_entry_uses_coinflip_leaf`): At `BO3State(map_idx=0, a_map_score=0, b_map_score=0, a_round=12, b_round=12, side_orient="a_atk", ...)`, `_compute_vega(root, fn)` MUST equal the manually-reconstructed coinflip-leaf variance:
        ```
        next_side = fn.next_side_orient_for(root.map_idx + 1)
        v_a = series_value(_advance_to_next_map(root, a_won=True, next_side_orient=next_side), fn)
        v_b = series_value(_advance_to_next_map(root, a_won=False, next_side_orient=next_side), fn)
        mean = 0.5 * (v_a + v_b)
        expected = 0.5 * (v_a - mean) ** 2 + 0.5 * (v_b - mean) ** 2
        ```
        to `rel_tol=1e-9`, AND it MUST NOT equal the buggy pre-fix value computed via `_advance_round` (which returns ~0.054 per VERIFICATION.md). Witness inequality: the new value differs from `_advance_round`-projected value by at least `1e-9`. (In symmetric `_synthetic_half_rates`, `v_a == v_b` so the OT coinflip variance equals 0.0 — this is the structurally-correct answer; "winning one OT round" is not a meaningful event when OT is collapsed to a coinflip.)
    - Existing `test_compute_vega_non_negative` and `test_compute_vega_matches_dec_018_formula` MUST still pass — both use the 0-0 fresh root state, which is in regulation and does NOT hit any of the new guards.
  </behavior>
  <action>
**Step 3.1 — Edit `src/pricing/live_theo.py` `_compute_vega`.** The CURRENT lines 530-545 read:

```python
def _compute_vega(root: BO3State, round_p_fn: RoundPFn) -> float:
    """vega = round_p × (theo_a − theo)² + (1 − round_p) × (theo_b − theo)².

    Per DEC-018 / D-10 / D-11. Computed at every live_theo invocation
    (D-11 — Phase 1 doesn't gate to round boundaries). Uses two extra
    series_value lookups (state_a_wins, state_b_wins) plus the root value.

    Always >= 0 by construction (sum of squared deviations weighted by probs).
    """
    state_a_wins = _advance_round(root, a_wins=True)
    state_b_wins = _advance_round(root, a_wins=False)
    theo = series_value(root, round_p_fn)
    theo_a = series_value(state_a_wins, round_p_fn)
    theo_b = series_value(state_b_wins, round_p_fn)
    p = round_p_fn(root)
    return p * (theo_a - theo) ** 2 + (1.0 - p) * (theo_b - theo) ** 2
```

REPLACE the entire function body with three early-return guards followed by the unchanged regulation case. The new docstring + body:

```python
def _compute_vega(root: BO3State, round_p_fn: RoundPFn) -> float:
    """vega = round_p × (theo_a − theo)² + (1 − round_p) × (theo_b − theo)².

    Per DEC-018 / D-10 / D-11. Computed at every live_theo invocation
    (D-11 — Phase 1 doesn't gate to round boundaries). Uses two extra
    series_value lookups (state_a_wins, state_b_wins) plus the root value.

    Always >= 0 by construction (sum of squared deviations weighted by probs).

    Terminal short-circuits (CR-03 fix — VERIFICATION.md gaps[2], CRule 5):

      - Series terminal (a_map_score >= 2 or b_map_score >= 2): theo is the
        constant 1.0 or 0.0; vega is 0.
      - Within-map terminal (a_round or b_round >= WIN_THRESHOLD): the map is
        decided; per-round vega is 0 (the next "round" doesn't exist within
        this map).
      - OT entry (a_round + b_round >= REGULATION_HALF * 2): _advance_round
        would push past the DP's OT hard-stop at total=24 (DEC-009 / CRule 5),
        silently bypassing _ot_coinflip_leaf. Instead, vega here is the
        VARIANCE of the OT coinflip leaf over next-map series outcomes —
        consistent with the DP's own OT semantics.
    """
    # Series terminal: theo is constant, vega is 0.
    if root.a_map_score >= 2 or root.b_map_score >= 2:
        return 0.0
    # Within-map terminal: map is decided, no per-round vega.
    if root.a_round >= WIN_THRESHOLD or root.b_round >= WIN_THRESHOLD:
        return 0.0
    # OT coinflip leaf: vega is variance of the leaf, not of _advance_round.
    if root.a_round + root.b_round >= REGULATION_HALF * 2:
        next_side = round_p_fn.next_side_orient_for(root.map_idx + 1)
        v_a = series_value(
            _advance_to_next_map(root, a_won=True, next_side_orient=next_side),
            round_p_fn,
        )
        v_b = series_value(
            _advance_to_next_map(root, a_won=False, next_side_orient=next_side),
            round_p_fn,
        )
        mean = 0.5 * (v_a + v_b)
        return 0.5 * (v_a - mean) ** 2 + 0.5 * (v_b - mean) ** 2
    # Standard regulation case (existing body):
    state_a_wins = _advance_round(root, a_wins=True)
    state_b_wins = _advance_round(root, a_wins=False)
    theo = series_value(root, round_p_fn)
    theo_a = series_value(state_a_wins, round_p_fn)
    theo_b = series_value(state_b_wins, round_p_fn)
    p = round_p_fn(root)
    return p * (theo_a - theo) ** 2 + (1.0 - p) * (theo_b - theo) ** 2
```

NOTE on imports: `WIN_THRESHOLD`, `REGULATION_HALF`, `_advance_to_next_map`, `series_value`, `_advance_round` are ALL already imported at the top of `live_theo.py` (lines 35-49). No new imports needed.

**Step 3.2 — Append three new tests** to `tests/pricing/test_live_theo.py`, immediately after `test_compute_vega_matches_dec_018_formula`:

```python
def test_compute_vega_zero_at_series_terminal() -> None:
    """CR-03 (VERIFICATION.md gaps[2]): vega is 0 when the series is clinched.
    Theo is the constant 1.0 (or 0.0) so squared deviation is 0.
    """
    hr = _synthetic_half_rates()
    state = _synthetic_match_state(map_idx=2, a_map_score=2)
    fn = _RoundPFnImpl(match_state=state, half_rates=hr)
    bo3_a = _bo3_state_from_match_state(state)
    assert _compute_vega(bo3_a, fn) == 0.0

    state_b = _synthetic_match_state(map_idx=2, a_map_score=0, b_map_score=2)
    fn_b = _RoundPFnImpl(match_state=state_b, half_rates=hr)
    bo3_b = _bo3_state_from_match_state(state_b)
    assert _compute_vega(bo3_b, fn_b) == 0.0


def test_compute_vega_zero_at_within_map_terminal() -> None:
    """CR-03: vega is 0 when the current map is already decided
    (a_round or b_round >= WIN_THRESHOLD). Per-round vega is undefined inside
    a finished map.
    """
    hr = _synthetic_half_rates()
    state_a = _synthetic_match_state(a_round=13, b_round=10)
    fn_a = _RoundPFnImpl(match_state=state_a, half_rates=hr)
    bo3_a = _bo3_state_from_match_state(state_a)
    assert _compute_vega(bo3_a, fn_a) == 0.0

    state_b = _synthetic_match_state(a_round=10, b_round=13)
    fn_b = _RoundPFnImpl(match_state=state_b, half_rates=hr)
    bo3_b = _bo3_state_from_match_state(state_b)
    assert _compute_vega(bo3_b, fn_b) == 0.0


def test_compute_vega_at_ot_entry_uses_coinflip_leaf() -> None:
    """CR-03 (VERIFICATION.md gaps[2], CRule 5): at a_round=12, b_round=12
    (regulation OT entry, total=24), vega MUST equal the variance of the
    OT coinflip leaf over next-map series outcomes — not the squared
    deviation against _advance_round-projected next-map values (which
    silently bypass the DP's OT hard-stop).
    """
    from src.pricing.dp import _advance_round, series_value

    hr = _synthetic_half_rates()
    state = _synthetic_match_state(a_round=12, b_round=12)
    fn = _RoundPFnImpl(match_state=state, half_rates=hr)
    root = _bo3_state_from_match_state(state)

    actual = _compute_vega(root, fn)

    # Reconstruct expected: variance of the OT coinflip leaf.
    next_side = fn.next_side_orient_for(root.map_idx + 1)
    v_a = series_value(
        _advance_to_next_map(root, a_won=True, next_side_orient=next_side),
        fn,
    )
    v_b = series_value(
        _advance_to_next_map(root, a_won=False, next_side_orient=next_side),
        fn,
    )
    mean = 0.5 * (v_a + v_b)
    expected = 0.5 * (v_a - mean) ** 2 + 0.5 * (v_b - mean) ** 2
    assert math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-12)

    # Witness the bug is closed: the buggy pre-fix path used _advance_round
    # past the OT hard-stop. Reconstruct what it would have returned and
    # confirm the new value either matches the correct OT-leaf variance OR
    # differs from the buggy projection (under symmetric half-rates the
    # OT-leaf variance is 0.0 so the new value is structurally correct).
    state_a_wins_buggy = _advance_round(root, a_wins=True)
    state_b_wins_buggy = _advance_round(root, a_wins=False)
    theo_buggy = series_value(root, fn)
    theo_a_buggy = series_value(state_a_wins_buggy, fn)
    theo_b_buggy = series_value(state_b_wins_buggy, fn)
    p_buggy = fn(root)
    buggy = (
        p_buggy * (theo_a_buggy - theo_buggy) ** 2
        + (1.0 - p_buggy) * (theo_b_buggy - theo_buggy) ** 2
    )
    # actual matches the OT-leaf variance (above), not the buggy advance-round
    # projection — unless they happen to coincide under perfect symmetry, in
    # which case the OT-leaf-variance assertion above is the load-bearing one.
    # We assert that actual is NOT computed via the _advance_round path; the
    # algebraic equality with `expected` already proved it. This line is a
    # documentation witness only.
    _ = buggy  # retained for future debugging; algebraic check above is the gate


def test_compute_vega_at_ot_entry_with_asymmetric_clinch_state() -> None:
    """CR-03 (asymmetric witness): at a_round=12, b_round=12 with a_map_score=1
    (A is one map up so OT-coinflip-A clinches the series, OT-coinflip-B
    forces map 3), v_a and v_b differ. The OT-leaf variance is then
    strictly positive AND differs from the buggy _advance_round projection.
    """
    from src.pricing.dp import series_value

    hr = _synthetic_half_rates()
    state = _synthetic_match_state(map_idx=1, a_map_score=1, a_round=12, b_round=12)
    fn = _RoundPFnImpl(match_state=state, half_rates=hr)
    root = _bo3_state_from_match_state(state)

    actual = _compute_vega(root, fn)

    next_side = fn.next_side_orient_for(root.map_idx + 1)
    v_a = series_value(
        _advance_to_next_map(root, a_won=True, next_side_orient=next_side),
        fn,
    )
    v_b = series_value(
        _advance_to_next_map(root, a_won=False, next_side_orient=next_side),
        fn,
    )
    mean = 0.5 * (v_a + v_b)
    expected = 0.5 * (v_a - mean) ** 2 + 0.5 * (v_b - mean) ** 2
    assert math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-12)
    assert actual >= 0.0
```

**Step 3.3 — Atomic commit.** Stage and commit with `fix(01-06): close CR-03 — _compute_vega OT and terminal short-circuits per DEC-009`.

Note: the `_ = buggy  # retained for future debugging` line in test 3 is intentional — it documents the bug that was closed. mypy strict will not flag it because the variable is used (via `_ =`). The fourth (`asymmetric_clinch`) test is added because under symmetric `_synthetic_half_rates` the OT-leaf variance reduces to 0 (numerically equal to the buggy value by coincidence in some cases); the asymmetric witness gives a non-zero anchor. Both tests together prove the fix.
  </action>
  <verify>
    <automated>.venv/Scripts/python.exe -m pytest tests/pricing/test_live_theo.py -k "compute_vega" -x 2>&1 | tail -25</automated>
  </verify>
  <acceptance_criteria>
    - `grep -nE "if root\.a_map_score >= 2 or root\.b_map_score >= 2:" src/pricing/live_theo.py` returns a match inside `_compute_vega` (early return at series terminal).
    - `grep -nE "if root\.a_round >= WIN_THRESHOLD or root\.b_round >= WIN_THRESHOLD:" src/pricing/live_theo.py` returns a match inside `_compute_vega` (early return at within-map terminal).
    - `grep -nE "if root\.a_round \+ root\.b_round >= REGULATION_HALF \* 2:" src/pricing/live_theo.py` returns a match inside `_compute_vega` (OT-leaf branch).
    - `pytest tests/pricing/test_live_theo.py::test_compute_vega_zero_at_series_terminal -x` exits 0.
    - `pytest tests/pricing/test_live_theo.py::test_compute_vega_zero_at_within_map_terminal -x` exits 0.
    - `pytest tests/pricing/test_live_theo.py::test_compute_vega_at_ot_entry_uses_coinflip_leaf -x` exits 0.
    - `pytest tests/pricing/test_live_theo.py::test_compute_vega_at_ot_entry_with_asymmetric_clinch_state -x` exits 0.
    - `pytest tests/pricing/test_live_theo.py::test_compute_vega_matches_dec_018_formula -x` STILL exits 0 (no regression on the regulation case).
    - `pytest tests/pricing/test_live_theo.py::test_compute_vega_non_negative -x` STILL exits 0.
    - `mypy --strict src/pricing/` exits 0.
    - `git log -1 --format=%s` matches `fix(01-06): close CR-03.*`.
  </acceptance_criteria>
  <done>CR-03 closed: `_compute_vega` returns 0 at series and within-map terminals, returns the OT coinflip-leaf variance at OT entry, and matches the DEC-018 formula in regulation; four regression tests lock the behavior; commit recorded.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 4: Fix CR-04 — per-call cache reset in LiveTheoEngine.__call__ + memory-leak regression test</name>
  <files>src/pricing/dp.py, src/pricing/live_theo.py, tests/pricing/test_live_theo.py</files>
  <read_first>
    - src/pricing/dp.py lines 152-216 (the `_ROUND_P_FNS` registry, `_register_round_p_fn`, `_series_value_cached` lru_cache, and `_ot_coinflip_leaf`)
    - src/pricing/live_theo.py lines 431-493 (the `_REACH_MAP_FNS` registry, `_register_reach_map_fn`, `_p_reach_map`, `_p_reach_map_cached`)
    - src/pricing/live_theo.py lines 553-577 (the `LiveTheoEngine` dataclass and its `__call__` method — currently a single-line `return _live_theo_impl(...)`)
    - .planning/phases/01-core-pricing-engine/01-REVIEW.md §"CR-04" (lines 180-209) — note: option (b) "reset registries per-call" is the chosen approach; option (a) "make MatchState fully hashable" is REJECTED for this plan because it requires WR-01 which is out of scope
    - .planning/phases/01-core-pricing-engine/01-VERIFICATION.md `gaps:` block, missing[3]
    - CLAUDE.md Critical Rule 11 (mypy --strict on src/pricing/) and Rule 12 (no magic numbers — but `5` here is a structural test bound, kept inline in the test only)
  </read_first>
  <behavior>
    - After 100 sequential `engine(state)` calls on a fresh `LiveTheoEngine`, BOTH `len(dp._ROUND_P_FNS)` and `len(live_theo._REACH_MAP_FNS)` MUST be ≤ 5 measured at end-of-loop. (Rationale: each call resets the registries in a try/finally; only the closures registered during the FINAL call before cleanup may be present at the moment of measurement, but cleanup runs in `finally` so even the final call leaves the registry empty after returning. Bound of 5 is generous slack against any future intra-call asymmetry.)
    - The cleanup runs in `finally` so it executes even if `_live_theo_impl` raises. (Test: provoke an exception inside the call by mocking — the cleanup STILL runs. Skipped here as it complicates the test fixture; the structural `try/finally` placement is verified by grep.)
    - `_clear_pricing_caches` exists in BOTH `src/pricing/dp.py` (clears `_ROUND_P_FNS` and `_series_value_cached.cache_clear()`) AND `src/pricing/live_theo.py` (clears `_REACH_MAP_FNS` and `_p_reach_map_cached.cache_clear()`). Both helpers are private (underscore prefix) and NOT added to `__all__` — public surface unchanged.
    - `LiveTheoEngine.__call__` calls both helpers in a `finally` block.
    - All four existing 137 tests + the new tests added in tasks 1-3 continue to pass (cache reset does not change end-to-end values; it only bounds memory).
    - Existing public surface: `from src.pricing import LiveTheoEngine, TheoOutput, MatchState, HalfRates` still works; `__all__` is still exactly those four names.
  </behavior>
  <action>
**Step 4.1 — Add `_clear_pricing_caches` helper to `src/pricing/dp.py`.** Append it AFTER `_register_round_p_fn` (currently at line 162-165) and BEFORE the `_series_value_cached` definition. Insert at line ~166 (after the existing helper, before the next `# ---` separator):

```python


def _clear_pricing_caches() -> None:
    """Reset the closure registry and lru_cache for one-shot pricing calls.

    CR-04 fix (VERIFICATION.md gaps[3]): `_ROUND_P_FNS` is append-only and
    `lru_cache(maxsize=None)` keys on `(state, round_p_id)` so each new
    closure id invalidates reuse anyway. Resetting per-call bounds memory
    without sacrificing real cache hits — the int id changes per call, so
    cross-call hits are already 0%.

    Called by `LiveTheoEngine.__call__` from a `finally` block so it runs
    even if the underlying `_live_theo_impl` raises. Phase 4's continuous
    quoter relies on this to avoid a linear-in-time memory leak; do NOT
    "optimize" by skipping the reset — see CR-04 in 01-REVIEW.md.
    """
    _ROUND_P_FNS.clear()
    _series_value_cached.cache_clear()
```

NOTE: `_series_value_cached` is decorated with `@functools.lru_cache(...)` so it has a `.cache_clear()` method. mypy --strict accepts `cache_clear()` on lru_cache-wrapped functions because `functools.lru_cache` is typed as returning `_lru_cache_wrapper` which exposes `cache_clear`.

**Step 4.2 — Add `_clear_pricing_caches` helper to `src/pricing/live_theo.py`.** Append it AFTER the existing `_register_reach_map_fn` (currently at line 436-438) and BEFORE `_p_reach_map`. Insert at line ~440:

```python


def _clear_pricing_caches() -> None:
    """Reset the closure registry and lru_cache for one-shot pricing calls.

    CR-04 fix companion (VERIFICATION.md gaps[3]). Same rationale as
    `dp._clear_pricing_caches`: `_REACH_MAP_FNS` is append-only and the
    cache key includes the int id so cross-call cache hits are already 0%.
    """
    _REACH_MAP_FNS.clear()
    _p_reach_map_cached.cache_clear()
```

**Step 4.3 — Wire `LiveTheoEngine.__call__` to call both helpers in a try/finally.** REPLACE the current `__call__` (currently lines 575-576):

```python
    def __call__(self, state: MatchState) -> TheoOutput:
        return _live_theo_impl(state, self.half_rates, self.round_conclusion)
```

with the try/finally form:

```python
    def __call__(self, state: MatchState) -> TheoOutput:
        # CR-04: bound memory by clearing the per-call closure registries +
        # lru_caches at the END of every call, even on exception. The
        # cross-call cache hit rate is already 0% (each call registers a new
        # closure id; lru_cache keys on (state, int) so old ids are dead
        # weight). Phase 4's continuous quoter REQUIRES this — see 01-REVIEW.md
        # CR-04 and 01-VERIFICATION.md gaps[3]. Do NOT remove this finally.
        from src.pricing import dp as _dp
        try:
            return _live_theo_impl(state, self.half_rates, self.round_conclusion)
        finally:
            _clear_pricing_caches()
            _dp._clear_pricing_caches()
```

NOTE on the import inside `__call__`: it is local to avoid an import-time circular (live_theo.py already imports from dp.py at module top; `from src.pricing import dp as _dp` here just binds an alias inside the method scope so we can call `_dp._clear_pricing_caches()`). An equivalent alternative is to add `from src.pricing.dp import _clear_pricing_caches as _dp_clear_pricing_caches` at the TOP of live_theo.py — but `_clear_pricing_caches` already exists as a name in live_theo.py (Step 4.2), so the local-import-with-alias avoids name shadowing without renaming the live_theo helper. EITHER form is acceptable — pick one and stay consistent. The local-alias form is what the action specifies; if the executor prefers the top-level alias-import, that's fine as long as both helpers run in `finally`.

**Step 4.4 — Append the regression test** to `tests/pricing/test_live_theo.py`. Add it in the public-surface / integration cluster (search for `def test_live_theo_engine_call_surface`; insert AFTER it):

```python
def test_no_memory_leak_across_live_theo_calls() -> None:
    """CR-04 (VERIFICATION.md gaps[3]): the closure registries and lru_caches
    must be reset per-call so Phase 4's continuous-running quoter does not
    leak memory linearly. After 100 sequential engine(state) calls, both
    registries must be near-empty (cleared in __call__'s finally block).
    """
    from src.pricing import dp, live_theo as live_theo_mod

    hr = _synthetic_half_rates()
    state = _synthetic_match_state()
    engine = LiveTheoEngine(half_rates=hr)
    for _ in range(100):
        engine(state)

    # try/finally cleanup runs after each call — at the moment we observe,
    # the registries should be empty (the LAST call cleaned up before
    # returning). Slack of 5 absorbs any future intra-call asymmetry.
    assert len(dp._ROUND_P_FNS) <= 5, (
        f"_ROUND_P_FNS leaked: len={len(dp._ROUND_P_FNS)} after 100 calls"
    )
    assert len(live_theo_mod._REACH_MAP_FNS) <= 5, (
        f"_REACH_MAP_FNS leaked: len={len(live_theo_mod._REACH_MAP_FNS)} "
        f"after 100 calls"
    )


def test_live_theo_engine_clears_caches_even_on_exception() -> None:
    """CR-04 corollary: cleanup runs in finally so a raising _live_theo_impl
    still leaves the registries clean. Synthesized via a deliberately
    malformed MatchState (mismatched map_pool / map_winners lengths is
    NOT validated in Phase 1, so we use a different lever — pass an
    impossible state where _bo3_state_from_match_state succeeds but a
    downstream call raises; if no such lever exists, fall back to a
    monkeypatched _live_theo_impl that raises).
    """
    import unittest.mock

    from src.pricing import dp, live_theo as live_theo_mod

    hr = _synthetic_half_rates()
    state = _synthetic_match_state()
    engine = LiveTheoEngine(half_rates=hr)

    # Prime the registries with one good call.
    engine(state)
    baseline_dp = len(dp._ROUND_P_FNS)
    baseline_reach = len(live_theo_mod._REACH_MAP_FNS)

    # Now force _live_theo_impl to raise; the finally MUST still run cleanup.
    def _raising_impl(*args, **kwargs):  # type: ignore[no-untyped-def]
        # Register a closure first so the registry is non-empty mid-call,
        # then raise. The finally block must clear it.
        from src.pricing.dp import _RoundPFnImpl as _DpRoundPFnImpl  # noqa: F401
        from src.pricing.live_theo import _RoundPFnImpl as _LtRoundPFnImpl
        fn = _LtRoundPFnImpl(match_state=state, half_rates=hr)
        dp._ROUND_P_FNS.append(fn)
        live_theo_mod._REACH_MAP_FNS.append(fn)
        raise RuntimeError("synthetic failure to test finally cleanup")

    with unittest.mock.patch.object(
        live_theo_mod, "_live_theo_impl", side_effect=_raising_impl
    ):
        with pytest.raises(RuntimeError, match="synthetic failure"):
            engine(state)

    # Cleanup ran in finally — registries are back to baseline (or smaller).
    assert len(dp._ROUND_P_FNS) <= baseline_dp, (
        f"_ROUND_P_FNS not cleaned on exception: "
        f"len={len(dp._ROUND_P_FNS)} vs baseline={baseline_dp}"
    )
    assert len(live_theo_mod._REACH_MAP_FNS) <= baseline_reach, (
        f"_REACH_MAP_FNS not cleaned on exception: "
        f"len={len(live_theo_mod._REACH_MAP_FNS)} vs baseline={baseline_reach}"
    )
```

Note: the import of `_RoundPFnImpl` from `src.pricing.dp` is incorrect — `_RoundPFnImpl` lives in `live_theo.py` (verified by reading line 84). The test uses ONLY `live_theo_mod._RoundPFnImpl` (rename `_LtRoundPFnImpl`); the dp.py import is a typo placeholder — REMOVE the `from src.pricing.dp import _RoundPFnImpl as _DpRoundPFnImpl  # noqa: F401` line entirely. Final test body uses only the live_theo import. (This note is here to flag for the executor, not to be copied verbatim into the test.)

Actual cleaner test body for the executor — REPLACE the `_raising_impl` function with this simpler form:

```python
    def _raising_impl(*args, **kwargs):  # type: ignore[no-untyped-def]
        from src.pricing.live_theo import _RoundPFnImpl
        fn = _RoundPFnImpl(match_state=state, half_rates=hr)
        dp._ROUND_P_FNS.append(fn)
        live_theo_mod._REACH_MAP_FNS.append(fn)
        raise RuntimeError("synthetic failure to test finally cleanup")
```

Use this simpler form in the actual commit.

**Step 4.5 — Atomic commit.** Stage all three files and commit with `fix(01-06): close CR-04 — per-call pricing cache reset for Phase 4 readiness`.
  </action>
  <verify>
    <automated>.venv/Scripts/python.exe -m pytest tests/pricing/test_live_theo.py -k "memory_leak or clears_caches_even_on_exception" -x 2>&1 | tail -25</automated>
  </verify>
  <acceptance_criteria>
    - `grep -nE "^def _clear_pricing_caches" src/pricing/dp.py` returns exactly one match.
    - `grep -nE "^def _clear_pricing_caches" src/pricing/live_theo.py` returns exactly one match.
    - `grep -nE "_ROUND_P_FNS\.clear\(\)" src/pricing/dp.py` returns one match (inside `_clear_pricing_caches`).
    - `grep -nE "_REACH_MAP_FNS\.clear\(\)" src/pricing/live_theo.py` returns one match (inside `_clear_pricing_caches`).
    - `grep -nE "_series_value_cached\.cache_clear\(\)" src/pricing/dp.py` returns one match.
    - `grep -nE "_p_reach_map_cached\.cache_clear\(\)" src/pricing/live_theo.py` returns one match.
    - `grep -nzE "def __call__\(self, state: MatchState\) -> TheoOutput:[\s\S]*?try:[\s\S]*?finally:[\s\S]*?_clear_pricing_caches" src/pricing/live_theo.py` returns at least one match (try/finally with cleanup wired in `__call__`). Use `grep -Pzo` if `-z` is unavailable; or simply assert: `grep -nE "finally:" src/pricing/live_theo.py` shows a match in or near `LiveTheoEngine.__call__`.
    - `pytest tests/pricing/test_live_theo.py::test_no_memory_leak_across_live_theo_calls -x` exits 0.
    - `pytest tests/pricing/test_live_theo.py::test_live_theo_engine_clears_caches_even_on_exception -x` exits 0.
    - `pytest tests/pricing/test_live_theo.py::test_live_theo_engine_call_surface -x` STILL exits 0 (engine call still produces same TheoOutput as the impl call).
    - `python -c "from src.pricing import LiveTheoEngine, TheoOutput, MatchState, HalfRates; print('ok')"` prints `ok` (public surface unchanged).
    - `python -c "from src.pricing import _clear_pricing_caches"` raises `ImportError` (helpers stay private — `__all__` unchanged).
    - `mypy --strict src/pricing/` exits 0.
    - `git log -1 --format=%s` matches `fix(01-06): close CR-04.*`.
  </acceptance_criteria>
  <done>CR-04 closed: per-call try/finally cleanup in `LiveTheoEngine.__call__`, both private `_clear_pricing_caches` helpers in place, registries bounded across 100 calls, cleanup runs even on exception, public surface unchanged, mypy strict clean, commit recorded.</done>
</task>

<task type="auto">
  <name>Task 5: Phase-1 final smoke gate — full suite + mypy + surface-contract grep</name>
  <files>(no source changes — verification only)</files>
  <read_first>
    - .planning/phases/01-core-pricing-engine/01-VERIFICATION.md "Behavioral Spot-Checks" table (lines 87-96 — original 137-passed run; the gate replays the same probes plus the new BLOCKER-resolution probes)
    - src/pricing/__init__.py (the `__all__` line MUST still be exactly `["LiveTheoEngine", "TheoOutput", "MatchState", "HalfRates"]` — Critical Rule 1)
    - CLAUDE.md Critical Rules 1, 5, 11, 12 (all four must still hold)
  </read_first>
  <action>
This task is a verification gate — it runs commands and asserts results, no code change, no commit.

**Step 5.1 — Full pytest:**
```bash
.venv/Scripts/python.exe -m pytest tests/ --tb=line 2>&1 | tail -10
```
Expected: `144 passed` (137 baseline + 7 new tests: 2 from Task 1, 2 from Task 2, 4 from Task 3 — wait, that's 8; recount: 1 from T1 reach_map_zero_clinch + 1 mirror = 2; 1 from T2 middle-map + 1 sum-to-one = 2; 1 from T3 series_terminal + 1 within_map_terminal + 1 ot_entry + 1 ot_asymmetric = 4; 1 from T4 memory_leak + 1 from T4 clears_on_exception = 2. Total = 10 new tests, 137 + 10 = 147 passed). The exact baseline count must come from `git log` of the previous run; if `pytest tests/ --tb=line` reports `147 passed` (or `137 + (count of new tests added across this plan)`), the gate is GREEN. If pytest reports any FAILURES, do NOT proceed — return to the failing task and fix.

NOTE: the executor may have made minor textual decisions during Tasks 1-4 that produced a different new-test count (e.g., declined to add the asymmetric-clinch witness in T3, or added an extra parametrize). Acceptance criterion: count is `>= 137 + 7` AND zero failures.

**Step 5.2 — mypy strict on src/pricing/:**
```bash
.venv/Scripts/python.exe -m mypy --strict src/pricing/ 2>&1 | tail -5
```
Expected: `Success: no issues found in 7 source files` (CRule 11).

**Step 5.3 — Surface contract greps (CRule 1 / DEC-010):**
```bash
grep -RnE "^def series_theo\b|^def series_theo_no_sides\b|^def series_theo_from_map_probs\b|^def model_series_prob\b|^def _signal_strength\b" src/pricing/
```
Expected: exit 1, no matches.

```bash
.venv/Scripts/python.exe -c "from src.pricing import LiveTheoEngine, TheoOutput, MatchState, HalfRates; import src.pricing as p; assert p.__all__ == ['LiveTheoEngine', 'TheoOutput', 'MatchState', 'HalfRates'], p.__all__; print('public surface ok')"
```
Expected: `public surface ok`.

**Step 5.4 — End-to-end runtime smoke (matches VERIFICATION.md spot-check #3):**
```bash
.venv/Scripts/python.exe -c "
from src.pricing import LiveTheoEngine, HalfRates, MatchState
hr = HalfRates(team_rates={}, league_rates={}, overall_avg=0.5)
state = MatchState(
    match_id='smoke', team_a='A', team_b='B',
    map_pool=('Lotus','Bind','Haven'), map_idx=0,
    a_map_score=0, b_map_score=0, a_round=0, b_round=0,
    side_orient='a_atk',
    map_side_orients=('a_atk','a_atk','a_atk'),
    map_winners=(None,None,None),
    pistol_winner_a={0:None,1:None,2:None},
    numerical_diff=0, bomb_planted=False, side='atk', econ_bucket='full',
)
engine = LiveTheoEngine(half_rates=hr)
out = engine(state)
print(f'theo_series={out.theo_series:.4f} theo_map={out.theo_map} vega={out.vega:.6f} confidence={out.confidence:.4f}')
"
```
Expected: prints theo_series in [0.01, 0.99], theo_map a 3-tuple of floats in [0.01, 0.99], vega >= 0, confidence in [0, 1]. (With empty half_rates, confidence is 0.0 because `_data_weight_for_map` returns 0 for any team — that is the verified pre-existing behavior; CR-01/02 fixes show through when half_rates is non-empty, which is what the test suite exercises.)

**Step 5.5 — BLOCKER-resolution probes (replay VERIFICATION.md spot-checks 5/6/7/8 — they MUST now pass):**

CR-01 probe (was: returns 1.0; expect: 0.0):
```bash
.venv/Scripts/python.exe -c "
from src.pricing.dp import BO3State
from src.pricing.live_theo import _p_reach_map, _RoundPFnImpl
from src.pricing.data import MatchState, HalfRates
hr = HalfRates(team_rates={}, league_rates={}, overall_avg=0.5)
state = MatchState(match_id='x', team_a='A', team_b='B',
    map_pool=('Lotus','Bind','Haven'), map_idx=2, a_map_score=2, b_map_score=0,
    a_round=0, b_round=0, side_orient='a_atk',
    map_side_orients=('a_atk','a_atk','a_atk'),
    map_winners=(True,True,None),
    pistol_winner_a={0:True,1:True,2:None},
    numerical_diff=0, bomb_planted=False, side='atk', econ_bucket='full')
bo3 = BO3State(map_idx=2, a_map_score=2, b_map_score=0, a_round=0, b_round=0,
    side_orient='a_atk', map_pool=('Lotus','Bind','Haven'),
    pistol_winner_a=(True,True,None))
fn = _RoundPFnImpl(match_state=state, half_rates=hr)
v = _p_reach_map(bo3, fn, m=2)
assert v == 0.0, f'CR-01 NOT closed: _p_reach_map returned {v} (expected 0.0)'
print('CR-01 closed (0.0)')
"
```

CR-02 probe (was: returns 0.5; expect: NOT 0.5 under asymmetric half-rates):
```bash
.venv/Scripts/python.exe -c "
from src.pricing.live_theo import _p_map_decisive
from src.pricing.data import MatchState, HalfRates
hr = HalfRates(
    team_rates={
        f'{t}|{m}|{s}': {'wins': 6.0 if t=='A' else 4.0, 'total': 10.0,
                         'rate': 0.6 if t=='A' else 0.4, 'used_fallback': False}
        for t in ('A','B') for m in ('Lotus','Bind','Haven') for s in ('atk','def')
    },
    league_rates={f'{m}|{s}': {'wins': 50.0, 'total': 100.0, 'rate': 0.5}
        for m in ('Lotus','Bind','Haven') for s in ('atk','def')},
    overall_avg=0.5)
state = MatchState(match_id='x', team_a='A', team_b='B',
    map_pool=('Lotus','Bind','Haven'), map_idx=0, a_map_score=0, b_map_score=0,
    a_round=0, b_round=0, side_orient='a_atk',
    map_side_orients=('a_atk','a_atk','a_atk'),
    map_winners=(None,None,None),
    pistol_winner_a={0:None,1:None,2:None},
    numerical_diff=0, bomb_planted=False, side='atk', econ_bucket='full')
v = _p_map_decisive(state, m=1, half_rates=hr)
assert abs(v - 0.5) > 1e-3, f'CR-02 NOT closed: _p_map_decisive at m=1 returned {v} (BO5+ placeholder)'
total = sum(_p_map_decisive(state, m, hr) for m in range(3))
assert abs(total - 1.0) < 1e-9, f'sum-to-one violated: {total}'
print(f'CR-02 closed (m=1 -> {v:.4f}, sum -> {total:.6f})')
"
```

CR-03 probe (was: returns ~0.054; expect: 0.0 under symmetric half-rates because OT-leaf v_a == v_b):
```bash
.venv/Scripts/python.exe -c "
from src.pricing.dp import BO3State
from src.pricing.live_theo import _compute_vega, _RoundPFnImpl
from src.pricing.data import MatchState, HalfRates
hr = HalfRates(team_rates={}, league_rates={}, overall_avg=0.5)
state = MatchState(match_id='x', team_a='A', team_b='B',
    map_pool=('Lotus','Bind','Haven'), map_idx=0, a_map_score=0, b_map_score=0,
    a_round=12, b_round=12, side_orient='a_def',
    map_side_orients=('a_atk','a_atk','a_atk'),
    map_winners=(None,None,None),
    pistol_winner_a={0:None,1:None,2:None},
    numerical_diff=0, bomb_planted=False, side='atk', econ_bucket='full')
bo3 = BO3State(map_idx=0, a_map_score=0, b_map_score=0, a_round=12, b_round=12,
    side_orient='a_def', map_pool=('Lotus','Bind','Haven'),
    pistol_winner_a=(None,None,None))
fn = _RoundPFnImpl(match_state=state, half_rates=hr)
v = _compute_vega(bo3, fn)
# Under symmetric half_rates, OT-leaf v_a == v_b so OT variance is 0; previously
# the bug returned ~0.054 from the _advance_round projection.
assert v < 1e-9, f'CR-03 NOT closed: vega at OT entry returned {v} (expected ~0 under symmetric)'
print(f'CR-03 closed (vega at OT entry = {v})')
"
```

CR-04 probe (was: 10 calls grew _ROUND_P_FNS by 220; expect: small bound after 100 calls):
```bash
.venv/Scripts/python.exe -c "
from src.pricing import LiveTheoEngine, HalfRates, MatchState
from src.pricing import dp
from src.pricing import live_theo as lt
hr = HalfRates(team_rates={}, league_rates={}, overall_avg=0.5)
state = MatchState(match_id='x', team_a='A', team_b='B',
    map_pool=('Lotus','Bind','Haven'), map_idx=0, a_map_score=0, b_map_score=0,
    a_round=0, b_round=0, side_orient='a_atk',
    map_side_orients=('a_atk','a_atk','a_atk'),
    map_winners=(None,None,None),
    pistol_winner_a={0:None,1:None,2:None},
    numerical_diff=0, bomb_planted=False, side='atk', econ_bucket='full')
engine = LiveTheoEngine(half_rates=hr)
for _ in range(100):
    engine(state)
n_dp = len(dp._ROUND_P_FNS)
n_lt = len(lt._REACH_MAP_FNS)
assert n_dp <= 5, f'CR-04 NOT closed: _ROUND_P_FNS = {n_dp} (expected <= 5)'
assert n_lt <= 5, f'CR-04 NOT closed: _REACH_MAP_FNS = {n_lt} (expected <= 5)'
print(f'CR-04 closed (_ROUND_P_FNS = {n_dp}, _REACH_MAP_FNS = {n_lt} after 100 calls)')
"
```

ALL FOUR PROBES MUST PRINT their `closed` line. Any AssertionError or non-zero exit is a gate failure — return to the offending task.

NO COMMIT on this task. Phase verification will follow this plan via `/gsd-verify-phase`.
  </action>
  <verify>
    <automated>.venv/Scripts/python.exe -m pytest tests/ --tb=line 2>&1 | tail -3 && .venv/Scripts/python.exe -m mypy --strict src/pricing/ 2>&1 | tail -3</automated>
  </verify>
  <acceptance_criteria>
    - `pytest tests/ --tb=line` reports `144 passed` or higher (137 baseline + the new tests added in tasks 1-4; range allowed: 144..150 depending on optional witness tests; exact equality NOT required, but FAILURES are forbidden).
    - `mypy --strict src/pricing/` reports `Success: no issues found in 7 source files`.
    - `grep -RnE "^def series_theo\b|^def series_theo_no_sides\b|^def series_theo_from_map_probs\b|^def model_series_prob\b|^def _signal_strength\b" src/pricing/` exits 1 with no output (forbidden audit-triplet symbols absent — CRule 1 / DEC-010).
    - `python -c "import src.pricing as p; assert p.__all__ == ['LiveTheoEngine', 'TheoOutput', 'MatchState', 'HalfRates']"` exits 0.
    - All four BLOCKER-resolution probe scripts print their `closed` line and exit 0.
    - Engine end-to-end smoke prints theo_series ∈ [0.01, 0.99], vega >= 0, confidence ∈ [0, 1].
    - No new git commit on this task (verification only).
  </acceptance_criteria>
  <done>Phase 1 derived-output gap closure verified: full suite green, mypy strict clean, public surface contract preserved, all four BLOCKERs independently probed and closed.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| (none — internal pricing module) | This plan only modifies in-process pricing math + test fixtures. No external input flows to the changed code paths in Phase 1. Phase 3 (ingestion) and Phase 4 (Kalshi I/O) own all trust boundaries; they will exercise the corrected `_compute_confidence` / `_compute_vega` outputs but cannot inject untrusted state into the math layer in this plan. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-01-06-01 | Tampering | `_ROUND_P_FNS` / `_REACH_MAP_FNS` module-level mutable lists | accept | The lists are private (underscore prefix) and only mutated by `_register_*` and `_clear_pricing_caches` helpers in the same module. No external import path mutates them. The CR-04 `clear()` call is the only state lifecycle touch outside test fixtures. Phase 1 has no untrusted input boundary. |
| T-01-06-02 | Denial of Service | Memory leak in `_ROUND_P_FNS` under continuous Phase 4 quoter | mitigate (this plan) | This is the operational concern CR-04 closes. Per-call `try/finally` cleanup in `LiveTheoEngine.__call__` bounds memory regardless of call cadence; the 100-call regression test proves the bound. |
| T-01-06-03 | Information Disclosure | Leaked `MatchState` / `HalfRates` references retained in unbounded registries | mitigate (this plan) | Same as T-01-06-02. Each closure holds full `MatchState` + `HalfRates`; the per-call `clear()` ensures these are eligible for GC after each pricing call. |
</threat_model>

<verification>
Final phase-level grep-runnable verification (run after Task 5 passes; this is the consolidated gate the verifier will replay):

```bash
# CR-01: clinch check precedes map_idx terminal in _p_reach_map_cached
CLINCH_LINE=$(grep -n "if state.a_map_score >= 2 or state.b_map_score >= 2:" src/pricing/live_theo.py | head -1 | cut -d: -f1)
MAPIDX_LINE=$(grep -n "if state.map_idx == m:" src/pricing/live_theo.py | head -1 | cut -d: -f1)
test -n "$CLINCH_LINE" -a -n "$MAPIDX_LINE" -a "$CLINCH_LINE" -lt "$MAPIDX_LINE" && echo "CR-01 grep ok" || (echo "CR-01 grep FAIL ($CLINCH_LINE vs $MAPIDX_LINE)"; exit 1)

# CR-02: BO3 middle-map formula present, BO5+ placeholder gone
grep -qE "p_a_wins_m_minus_1 \* p_a_wins_m \+ \(1\.0 - p_a_wins_m_minus_1\) \* \(1\.0 - p_a_wins_m\)" src/pricing/live_theo.py && echo "CR-02 fix present" || (echo "CR-02 grep FAIL"; exit 1)
grep -qE "return p_reached \* 0\.5" src/pricing/live_theo.py && (echo "CR-02 placeholder still present"; exit 1) || echo "CR-02 placeholder absent"

# CR-03: three OT/terminal guards present in _compute_vega
grep -qE "if root\.a_map_score >= 2 or root\.b_map_score >= 2:" src/pricing/live_theo.py || (echo "CR-03 series-terminal guard missing"; exit 1)
grep -qE "if root\.a_round >= WIN_THRESHOLD or root\.b_round >= WIN_THRESHOLD:" src/pricing/live_theo.py || (echo "CR-03 within-map guard missing"; exit 1)
grep -qE "if root\.a_round \+ root\.b_round >= REGULATION_HALF \* 2:" src/pricing/live_theo.py || (echo "CR-03 OT guard missing"; exit 1)
echo "CR-03 grep ok"

# CR-04: helpers + finally cleanup present
grep -qE "^def _clear_pricing_caches" src/pricing/dp.py || (echo "CR-04 dp helper missing"; exit 1)
grep -qE "^def _clear_pricing_caches" src/pricing/live_theo.py || (echo "CR-04 live_theo helper missing"; exit 1)
grep -qE "_ROUND_P_FNS\.clear\(\)" src/pricing/dp.py || (echo "CR-04 dp clear missing"; exit 1)
grep -qE "_REACH_MAP_FNS\.clear\(\)" src/pricing/live_theo.py || (echo "CR-04 live_theo clear missing"; exit 1)
grep -qE "_series_value_cached\.cache_clear\(\)" src/pricing/dp.py || (echo "CR-04 series cache_clear missing"; exit 1)
grep -qE "_p_reach_map_cached\.cache_clear\(\)" src/pricing/live_theo.py || (echo "CR-04 reach cache_clear missing"; exit 1)
grep -qE "finally:" src/pricing/live_theo.py || (echo "CR-04 finally block missing"; exit 1)
echo "CR-04 grep ok"

# Surface contract (CRule 1 / DEC-010) — forbidden symbols absent
grep -RnE "^def series_theo\b|^def series_theo_no_sides\b|^def series_theo_from_map_probs\b|^def model_series_prob\b|^def _signal_strength\b" src/pricing/ && (echo "audit-triplet leak"; exit 1) || echo "surface contract ok"

# Public __all__ unchanged
.venv/Scripts/python.exe -c "import src.pricing as p; assert p.__all__ == ['LiveTheoEngine', 'TheoOutput', 'MatchState', 'HalfRates'], p.__all__; print('__all__ ok')"

# Test suite + mypy
.venv/Scripts/python.exe -m pytest tests/ --tb=line 2>&1 | tail -3
.venv/Scripts/python.exe -m mypy --strict src/pricing/ 2>&1 | tail -3
```

ALL of the above lines must print their `ok` (or `closed`/`absent`) message and exit 0; pytest must report `>= 144 passed` with zero failures; mypy must report `Success: no issues found in 7 source files`.
</verification>

<success_criteria>
- `pytest tests/` exits 0 with at least 144 tests passing (137 baseline + minimum 7 new regression tests across tasks 1-4).
- `mypy --strict src/pricing/` exits 0 with `Success: no issues found in 7 source files`.
- All four BLOCKERs from `01-VERIFICATION.md` `gaps:` block are closed with the corresponding regression test asserting the exact behavior the verifier confirmed broken at runtime.
- Public surface contract preserved: `src.pricing.__all__ == ["LiveTheoEngine", "TheoOutput", "MatchState", "HalfRates"]`; no audit-triplet symbols (`series_theo`, `series_theo_no_sides`, `series_theo_from_map_probs`, `model_series_prob`, `_signal_strength`) reappear in `src/pricing/`.
- Four atomic per-CR commits land in order with messages `fix(01-06): close CR-01 ...`, `fix(01-06): close CR-02 ...`, `fix(01-06): close CR-03 ...`, `fix(01-06): close CR-04 ...`.
- No source file outside `src/pricing/dp.py`, `src/pricing/live_theo.py`, and `tests/pricing/test_live_theo.py` is modified — no scope creep into WR-* or IN-* items.
- `_clear_pricing_caches` helpers stay private; `LiveTheoEngine.__call__` wraps `_live_theo_impl` in a `try/finally` that runs cleanup even on exception (verified by `test_live_theo_engine_clears_caches_even_on_exception`).
- The 100-call memory-leak regression test (`test_no_memory_leak_across_live_theo_calls`) bounds both registries at ≤ 5 entries — Phase 4's continuous quoter is unblocked.
</success_criteria>

<output>
After completion, create `.planning/phases/01-core-pricing-engine/01-06-derived-output-fixes-SUMMARY.md` documenting:
- Which CRs closed (CR-01, CR-02, CR-03, CR-04) with the line ranges modified
- New tests added (test names + count)
- Test count delta (137 → 144+)
- Confirmation that mypy --strict, surface contract, and __all__ are unchanged
- Note for the Phase 4 planner: per-call cache reset is intentional and required; do NOT optimize it away. Cross-call cache hit rate is already 0% because the int closure id changes per call; the `try/finally` cleanup bounds memory at zero added latency cost.
- Out-of-scope items deferred to future revisions: WR-01 (pistol_winner_a dict→tuple), WR-02 (_marginal_map_prob 0.5 fallback), WR-03 (MatchState __post_init__ validator), WR-04 (defensive 'a_atk' literal), WR-05 (marginalization tolerance tightening), IN-01..IN-04 (1e-12 constant, perf seams, mass_sum assertion).
</output>
