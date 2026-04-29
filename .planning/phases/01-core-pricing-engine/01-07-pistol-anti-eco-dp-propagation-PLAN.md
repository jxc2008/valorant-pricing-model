---
id: 01-07-pistol-anti-eco-dp-propagation
phase: 01-core-pricing-engine
plan: 07
type: execute
wave: 7
gap_closure: true
depends_on: [01-06-derived-output-fixes]
files_modified:
  - src/pricing/dp.py
  - src/pricing/live_theo.py
  - tests/pricing/test_dp.py
  - tests/pricing/test_live_theo.py
  - tests/pricing/test_round_types.py
autonomous: true
requirements: [REQ-pistol-anti-eco-modeling, REQ-bo3-dp-engine, REQ-canonical-live-theo]
requirements_addressed: [REQ-pistol-anti-eco-modeling]
closes_gaps:
  - source: 01-VERIFICATION.md
    truth_idx: 1
    blockers: [CR-05]
    warnings: [WR-06]

must_haves:
  truths:
    - "`_advance_round` in `dp.py` sets `pistol_winner_a[map_idx] = a_wins` when (and only when) `state.a_round == 0 AND state.b_round == 0 AND state.pistol_winner_a[state.map_idx] is None`. Already-settled values are NEVER overridden; the returned tuple has the same length as `state.pistol_winner_a` and is type `tuple[Optional[bool], ...]`."
    - "`_advance_to_next_map` keeps the next map's `pistol_winner_a[next_map_idx]` slot as-is (will be `None` for an unstarted next map; `_advance_round` will populate it when round 1 of that map settles inside the recursion). No new override at the map boundary."
    - "`_within_map_p_a_wins` in `live_theo.py` applies the same `pistol_winner_a` update inside its inline state-advance (synthetic-state rebuild at lines 242-251 + recursion call at lines 263-267) — at the round-1 boundary the synthetic state passed into the recursion has `pistol_winner_a[map_idx]` set to the branch's `a_wins` truth, mirroring `dp._advance_round`."
    - "DP forward-pass produces P(A wins round 2 | A won round 1) == GUN_WIN_RATE (0.822) for a fresh `BO3State` rooted with `pistol_winner_a=(None, None, None)`. The new regression test `test_dp_anti_eco_uses_gun_win_rate_after_round_1_branch` asserts this with `math.isclose(rel_tol=1e-9)`. Runs on `main` (current state) → FAIL with returned 0.5; runs after the fix → PASS with returned 0.822."
    - "`_within_map_p_a_wins` analog: P(A wins round 2 of a future map | A won that map's round 1) == GUN_WIN_RATE under matching half_rates / pistol_winner_a state. New regression test `test_within_map_anti_eco_uses_gun_win_rate_after_round_1_branch` locks WR-06 closure."
    - "Re-scoped `test_anti_eco_with_none_pistol_winner_returns_defensive_05` (renamed `test_anti_eco_with_none_pistol_winner_returns_defensive_05_for_malformed_external_input`) carries an updated docstring stating the 0.5 fallback is for malformed *external* inputs only — DP forward-pass states will never reach `round_p_for_round` with `pistol_winner_a[map_idx] is None` for in-recursion rounds 2/3 after this fix lands. The assertion target is unchanged (still `actual == 0.5`)."
    - "`dp.py` module docstring (or an inline `# Phase-2 follow-up:` comment near `_advance_round`) documents the second-half pistol limitation: `pistol_winner_a` is keyed only by `map_idx`, so rounds 14/15 cannot be conditioned on a separately-tracked second-half pistol winner under the current data shape. Phase 1 ships rounds 14/15 falling through to the half-rates blend per round_types.py:140; per-half pistol-winner shape is a Phase 2 task. NO data-shape change in this plan."
    - "All 147 prior tests + ≥2 new regression tests (CR-05 + WR-06) + the asymmetric-matchup behavioral integration test pass. `mypy --strict src/pricing/` exits 0; `ruff check src/pricing/ tests/pricing/` exits 0; the public surface contract is unchanged (`src.pricing.__all__ == ['LiveTheoEngine', 'TheoOutput', 'MatchState', 'HalfRates']`); forbidden audit-triplet symbols stay absent."
    - "Memory invariant: `test_no_memory_leak_across_live_theo_calls` continues to pass — no per-call state escapes the `try/finally` cleanup landed in CR-04."
  artifacts:
    - path: src/pricing/dp.py
      provides: "`_advance_round` updates `pistol_winner_a` at the round-1 boundary via tuple-rebuild (BO3State stays frozen + slots + hashable); module docstring (or adjacent comment) flags the second-half pistol limitation as a Phase 2 follow-up."
    - path: src/pricing/live_theo.py
      provides: "`_within_map_p_a_wins` inline state-advance applies the same `pistol_winner_a` update at the round-1 boundary (or refactored to call `dp._advance_round` directly — executor's choice as long as the chosen shape is consistent with dp.py)."
    - path: tests/pricing/test_dp.py
      provides: "`test_dp_anti_eco_uses_gun_win_rate_after_round_1_branch` — fails on main, passes after fix; locks the CR-05 invariant at the dp.py level."
    - path: tests/pricing/test_live_theo.py
      provides: "`test_within_map_anti_eco_uses_gun_win_rate_after_round_1_branch` — locks WR-06; `test_live_theo_asymmetric_pistols_match_unset_pistols_after_dp_propagation` — behavioral integration test confirming the prior 9.25pp swing is closed under TeamA=0.55/TeamB=0.45 with `total=1e9`."
    - path: tests/pricing/test_round_types.py
      provides: "Re-scoped defensive-fallback test (renamed + updated docstring); assertion target unchanged."
  key_links:
    - from: "src/pricing/dp.py:_advance_round"
      to: "BO3State.pistol_winner_a tuple-rebuild on round-1 boundary"
      via: "if state.a_round == 0 and state.b_round == 0 and existing is None: tuple-rebuild"
      pattern: "state\\.a_round == 0 and state\\.b_round == 0"
    - from: "src/pricing/live_theo.py:_within_map_p_a_wins"
      to: "Same pistol_winner_a tuple-rebuild on round-1 boundary inside the inline state-advance"
      via: "Either inline rebuild at lines 242-267 OR refactor to call dp._advance_round (executor's choice)"
      pattern: "(a_round == 0 and b_round == 0|_advance_round\\()"
    - from: "src/pricing/round_types.py:round_p_for_round (UNCHANGED)"
      to: "Defensive 0.5 fallback at line 152"
      via: "round_p_for_round dispatch on state.pistol_winner_a[state.map_idx]"
      pattern: "if pistol_won_by_a is None:"
---

<objective>
Close the single remaining BLOCKER from `.planning/phases/01-core-pricing-engine/01-VERIFICATION.md` (re-verification #2, status: gaps_found, score 2/3) — **CR-05: DP forward-pass never updates `pistol_winner_a`; anti-eco dispatch silently dead in DP recursion** — together with its scoped twin **WR-06** in `_within_map_p_a_wins`.

Purpose: REQ-pistol-anti-eco-modeling is structurally satisfied by the dispatch in `round_types.py:140-153`, but the DP forward-pass in `dp.py:_advance_round` (lines 104-122) and `dp.py:_advance_to_next_map` (lines 125-149) propagate `BO3State.pistol_winner_a` verbatim — never updating `pistol_winner_a[state.map_idx] = a_wins` when round 1 settles. The natural Phase-4 call site (pre-match pricing with `pistol_winner_a={0:None, 1:None, 2:None}`) therefore enters round 2 with `pistol_winner_a[0] is None`, hits the defensive 0.5 fallback in `round_types.py:148-152`, and the pistol+anti-eco model (DEC-011 / CRule 4) is silently inactive for all 12 anti-eco rounds × 3 maps in DP recursion. Re-verified at runtime in re-verification #2: 9.25pp theo_series swing at TeamA=0.55/TeamB=0.45 between unset-pistols (0.887) and set-pistols (0.979). Phase 4's `VEGA_DIRECTIONAL_THRESHOLD = 0.04` and `KILL_SWITCH_DEVIATION_C = 20¢` would force unintended mode flips and false kill-switch trips against this systematic bias.

The fix is mechanical: ~10 lines in `_advance_round`, mirrored ~6 lines in `_within_map_p_a_wins`'s inline state-advance, plus two new regression tests + one re-scoped existing test + a Phase-2 follow-up doc note on the second-half pistol limitation. CR-05's concrete fix code is shown verbatim in `01-REVIEW.md` lines 140-175 and the regression test code is at `01-REVIEW.md` lines 192-210; this plan surfaces both verbatim in the task `<action>` blocks per Anti-Shallow rules.

Output: one revision plan; six atomic per-task commits (failing-then-passing test → dp.py fix → live_theo.py fix + WR-06 test → re-scope existing test → docstring note → final smoke gate). New tests: ≥2 (CR-05 + WR-06 + asymmetric-matchup integration). Total tests after this plan: 147 + ≥2 = ≥149.

Out of scope (DO NOT pull in):
- WR-07 (`_within_map_p_a_wins` docstring claims `lru_cache` but uses `dict`) — documentation papercut, deferred (01-REVIEW.md WR-07).
- WR-08 (per-`m` re-registration in `_p_reach_map` defeats `lru_cache` reuse) — performance, out of v1 scope.
- IN-05..IN-07 (style/maintainability papercuts).
- WR-01..WR-05 + IN-01..IN-04 from original 01-REVIEW.md — already deferred per 01-06 plan.
- Extending `pistol_winner_a` to `tuple[Optional[tuple[bool, bool]], ...]` per (map, half) — Phase 2 task; flagged via doc note only in this plan.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<canonical_refs>
The following are mandatory pre-implementation reads. The fix code is already shown verbatim in 01-REVIEW.md §CR-05 and the regression test code is at the §end. Do NOT abstract back to "apply the fix"; surface the actual code.

- `.planning/phases/01-core-pricing-engine/01-VERIFICATION.md` — re-verification #2 (2026-04-28T23:45:00Z); the gap source. Read the `gaps:` block (lines 15-78) and the `## Gaps Summary` section (lines 200-235).
- `.planning/phases/01-core-pricing-engine/01-REVIEW.md` — CR-05 fix code at lines 140-175; regression test code at lines 192-210; WR-06 description at lines 216-235.
- `.planning/phases/01-core-pricing-engine/01-RESEARCH.md` — round-type dispatch design (§4) and Phase 1 simplifications (A6, A8).
- `.planning/phases/01-core-pricing-engine/01-CONTEXT.md` — D-04 / DEC-011 / `pistol_winner_a` data shape decisions.
- `.planning/phases/01-core-pricing-engine/01-06-derived-output-fixes-PLAN.md` — prior gap-closure plan; mimic `closes_gaps`/`gap_closure: true`/atomic-commit pattern.
- `.planning/phases/01-core-pricing-engine/01-06-derived-output-fixes-SUMMARY.md` — confirms CR-01..CR-04 closure surface invariants this plan must NOT regress.
- `src/pricing/dp.py` — read in full before touching; the BO3State definition is at lines 48-76, `_advance_round` at lines 104-122, `_advance_to_next_map` at lines 125-149, `_clear_pricing_caches` (CR-04) at lines 168-184.
- `src/pricing/live_theo.py` — `_within_map_p_a_wins` is at lines 204-272 (the inline state-advance is at lines 242-267); `LiveTheoEngine.__call__` try/finally (CR-04) is in the dataclass below `_compute_vega`.
- `src/pricing/round_types.py` — **read-only**; the dispatch at lines 140-153 is correct in isolation. DO NOT modify this module. After this fix, the round-2/3 in-recursion path NEVER reaches the `if pistol_won_by_a is None: return 0.5` branch on a well-formed live state; the branch remains as a defensive guard for malformed external inputs.
- `tests/pricing/test_dp.py` — `_ConstantRoundPFn` helper at lines 35-52, `_root()` at lines 55-66; new dp-level regression test slots in here.
- `tests/pricing/test_live_theo.py` — `_synthetic_half_rates()` at lines 178-261, `_synthetic_match_state()` at lines 264-294; new within-map and integration tests slot here.
- `tests/pricing/test_round_types.py` — `_FakeBO3State` at lines 48-65, `_state(...)` at lines 98-113, the test-to-rescope at lines 213-222.
- `CLAUDE.md` — Critical Rules 1, 4, 11, 12 (single canonical entry point; pistol/anti-eco modeled explicitly with GUN_WIN_RATE; mypy --strict on src/pricing/; no magic numbers — `GUN_WIN_RATE` already lives in `src/config/constants.py`, no new constant required).
</canonical_refs>

<context>
@.planning/STATE.md
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@.planning/phases/01-core-pricing-engine/01-CONTEXT.md
@.planning/phases/01-core-pricing-engine/01-RESEARCH.md
@.planning/phases/01-core-pricing-engine/01-PATTERNS.md
@.planning/phases/01-core-pricing-engine/01-VERIFICATION.md
@.planning/phases/01-core-pricing-engine/01-REVIEW.md
@.planning/phases/01-core-pricing-engine/01-06-derived-output-fixes-PLAN.md
@.planning/phases/01-core-pricing-engine/01-06-derived-output-fixes-SUMMARY.md
@CLAUDE.md
@src/pricing/dp.py
@src/pricing/live_theo.py
@src/pricing/round_types.py
@src/pricing/__init__.py
@tests/pricing/test_dp.py
@tests/pricing/test_live_theo.py
@tests/pricing/test_round_types.py

<interfaces>
<!-- Concrete signatures and constants the executor needs. Extracted from src/. Use directly — no exploration required. -->

From `src/pricing/dp.py` (DO NOT recreate; modify only `_advance_round` per the action below):

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
    pistol_winner_a: tuple[Optional[bool], ...]  # noqa: UP045 — plan-mandated form

class RoundPFn(Protocol):
    def __call__(self, state: BO3State) -> float: ...
    def next_side_orient_for(self, map_idx: int) -> str: ...

def _advance_round(state: BO3State, a_wins: bool) -> BO3State: ...      # MODIFIED in Task 2
def _advance_to_next_map(state: BO3State, a_won: bool, next_side_orient: str) -> BO3State: ...  # UNCHANGED
def series_value(state: BO3State, round_p_fn: RoundPFn) -> float: ...   # UNCHANGED

_ROUND_P_FNS: list[RoundPFn] = []
@functools.lru_cache(maxsize=None)
def _series_value_cached(state: BO3State, round_p_id: int) -> float: ...

def _clear_pricing_caches() -> None: ...   # CR-04 — unchanged
```

From `src/pricing/live_theo.py` (DO NOT recreate; modify only `_within_map_p_a_wins` per Task 3):

```python
@dataclass(frozen=True)
class _RoundPFnImpl:
    match_state: MatchState
    half_rates: HalfRates
    def __call__(self, state: BO3State) -> float: ...
    def _effective_side(self, state: BO3State) -> str: ...
    def next_side_orient_for(self, map_idx: int) -> str: ...

def _bo3_state_from_match_state(state: MatchState) -> BO3State: ...

def _within_map_p_a_wins(
    map_pool: tuple[str, ...],
    map_idx: int,
    starting_side: str,
    pistol_winner_a: tuple[Optional[bool], ...],   # noqa: UP045
    match_state: MatchState,
    half_rates: HalfRates,
) -> float: ...   # MODIFIED in Task 3 (inline state-advance at lines 242-267)
```

From `src/pricing/round_types.py` (READ-ONLY for this plan):

```python
def round_p_for_round(state: BO3State, match_state: MatchState, half_rates: HalfRates) -> float:
    round_num = state.a_round + state.b_round + 1  # 1-indexed
    ...
    if round_num in (2, 3, 14, 15):
        pistol_won_by_a = state.pistol_winner_a[state.map_idx]
        if pistol_won_by_a is None:
            return 0.5     # defensive — fires only for malformed external inputs after CR-05 fix
        return GUN_WIN_RATE if pistol_won_by_a else 1.0 - GUN_WIN_RATE
    ...
```

From `src/config/constants.py`:

```python
GUN_WIN_RATE: Final[float] = 0.822
REGULATION_HALF: Final[int] = 12
WIN_THRESHOLD: Final[int] = 13
```

From `tests/pricing/test_dp.py` (existing helpers — reuse, do NOT redefine):

```python
class _ConstantRoundPFn:    # line 35
    def __init__(self, p: float, side_orients: tuple[str, ...] = ("a_atk", "a_atk", "a_atk")) -> None: ...
    def __call__(self, state: BO3State) -> float: return self._p
    def next_side_orient_for(self, map_idx: int) -> str: ...

def _root() -> BO3State: ...    # line 55 — fresh BO3 root, pistol_winner_a=(None, None, None)
```

From `tests/pricing/test_live_theo.py` (existing fixtures — reuse, do NOT redefine):

```python
def _synthetic_half_rates() -> HalfRates: ...           # line 178 — symmetric-ish (TeamA atk 0.6, def 0.5)
def _synthetic_match_state(                             # line 264
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

From `tests/pricing/test_round_types.py` (the test to re-scope, lines 213-222):

```python
def test_anti_eco_with_none_pistol_winner_returns_defensive_05() -> None:
    """Defensive: round 2 with pistol_winner_a=None → 0.5 (shouldn't happen in
    well-formed states, but covered for robustness)."""
    state = _state(a_round=1, b_round=0, pistol_winner_a=(None, None, None))
    actual = round_p_for_round(state, _FakeMatchState(), _FakeHalfRates())
    assert actual == 0.5
```

The 01-REVIEW.md regression test code (lines 192-210) references an `_RoundPFnImpl(...)` constructed via `_synthetic_match_state` and `_synthetic_half_rates`, plus a `_bo3_state_from_match_state(state)` projection. ALL of these helpers exist in `tests/pricing/test_live_theo.py` already (verified above). The dp-level test in Task 1 SHOULD live in `tests/pricing/test_dp.py` (uses `_root()` + `_ConstantRoundPFn` for the dp-level invariant) AND the within-map analog in Task 3 SHOULD live in `tests/pricing/test_live_theo.py` (needs `_RoundPFnImpl` + `_bo3_state_from_match_state` which are already imported there).
</interfaces>
</context>

<task_dependencies>
Sequential within this plan; all tasks at wave 7 (after 01-06 = wave 6).

Task 1 (failing dp-level test) → Task 2 (dp.py `_advance_round` fix; flips Task 1's test from FAIL → PASS) → Task 3 (live_theo.py `_within_map_p_a_wins` fix + WR-06 test) → Task 4 (re-scope existing round_types test) → Task 5 (Phase-2 follow-up doc note) → Task 6 (final smoke gate + asymmetric-matchup integration test).

Each task = atomic commit (gap-closure pattern from 01-06). Task 6 records no commit (verification-only).
</task_dependencies>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add failing CR-05 regression test in test_dp.py (RED — must fail on current main)</name>
  <files>tests/pricing/test_dp.py</files>
  <read_first>
    - tests/pricing/test_dp.py lines 1-66 (imports + `_ConstantRoundPFn` + `_root` helpers — both reused below)
    - tests/pricing/test_dp.py lines 130-180 (existing OT/regression test cluster — slot the new test in section 6 alongside DEC-011 regression locks)
    - .planning/phases/01-core-pricing-engine/01-REVIEW.md §CR-05 `**Fix:**` block (lines 140-210, especially the verbatim test code at lines 192-210)
    - .planning/phases/01-core-pricing-engine/01-VERIFICATION.md `gaps:` block, missing[2]
    - src/pricing/dp.py lines 104-122 (`_advance_round` — confirm the current pistol_winner_a propagation: line 121 reads `pistol_winner_a=state.pistol_winner_a` verbatim with no conditional update)
    - src/config/constants.py — confirm `GUN_WIN_RATE` is exported (it is — used by tests/pricing/test_round_types.py:34)
    - CLAUDE.md Critical Rule 4 (Pistol + anti-eco modeled explicitly using GUN_WIN_RATE = 0.822 — this test asserts the rule holds in the DP forward-pass, not just at the dispatch site)
  </read_first>
  <behavior>
    - Test 1 (`test_dp_anti_eco_uses_gun_win_rate_after_round_1_branch`): Build a closure over `_RoundPFnImpl(match_state, half_rates)` (NOT `_ConstantRoundPFn`, because the anti-eco branch dispatches off `state.pistol_winner_a[state.map_idx]` — the production round_p_for_round path must execute, not a constant). Step the DP forward via `_advance_round(_root(), a_wins=True)`. Then assert `_RoundPFnImpl(state, hr)(state_after_a_wins_round_1)` returns `GUN_WIN_RATE` (0.822) to `rel_tol=1e-9`. **On `main` (current state) this MUST FAIL** with returned value `0.5` (the defensive fallback) because `_advance_round` propagates `pistol_winner_a=(None, None, None)` verbatim. After Task 2 lands, this test PASSES.
    - The test uses `_synthetic_match_state()` + `_synthetic_half_rates()` from `test_live_theo.py` — but `test_dp.py` does not currently import those. Two acceptable paths:
      (a) Add the imports `from tests.pricing.test_live_theo import _synthetic_half_rates, _synthetic_match_state` (cross-test-module import — discouraged because pytest doesn't always treat test modules as importable packages depending on rootdir config).
      (b) Define a local minimal `_FakeMatchState` + `_FakeHalfRates` (analog of the `test_round_types.py` pattern at lines 67-95) inline in `test_dp.py` — this is the preferred path; it keeps `test_dp.py` self-contained and matches the existing duck-typing convention.
    - Choose path (b). The `_FakeMatchState` only needs `team_a` and `team_b` strings; the `_FakeHalfRates` needs `team(team, map, side) -> float` and `team_entry(team, map, side) -> dict | None` — even returning constant 0.5 / None works, because the anti-eco branch in `round_p_for_round` does NOT consult `half_rates` (it dispatches purely on `pistol_winner_a[map_idx]`).
    - The test does NOT need `_bo3_state_from_match_state` — `_root()` already returns a BO3State with `pistol_winner_a=(None, None, None)`.
  </behavior>
  <action>
**Step 1.1 — Edit `tests/pricing/test_dp.py`.** Locate the imports block (lines 13-28). The current imports already pull `BO3State`, `_series_value_cached`, `series_value` from `src.pricing.dp`. Add three new imports + a `dataclass` import + Any/Optional imports:

```python
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from reference.fair_value import _bo3_series_prob
from src.config.constants import GUN_WIN_RATE
from src.pricing.dp import (
    BO3State,
    _advance_round,
    _series_value_cached,
    series_value,
)
from src.pricing.round_types import round_p_for_round
```

Add `_advance_round` to the import list (currently absent), add `from src.config.constants import GUN_WIN_RATE`, add `from src.pricing.round_types import round_p_for_round`, and add the `from dataclasses import dataclass` + `from typing import Any` if not already present at module scope.

**Step 1.2 — Append minimal duck-typed fakes** AFTER `_root()` (currently ending at line 66) and BEFORE the `# 1. Range invariant` separator. These mirror the test_round_types.py pattern:

```python
# --------------------------------------------------------------------------- #
# Test fixtures for the round_p_for_round dispatch (CR-05 regression)         #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class _FakeMatchState:
    """Minimal MatchState shape required by round_p_for_round.

    The anti-eco branch in round_types.round_p_for_round (lines 146-153) does
    not read MatchState.team_a/team_b, but the gunround/pistol branches do. We
    only need anti-eco coverage for CR-05, but keep team_a/team_b for safety.
    """

    team_a: str = "TeamA"
    team_b: str = "TeamB"


class _FakeHalfRates:
    """Minimal HalfRates Protocol implementation. Anti-eco branch never reads
    these — returning 0.5 / None is sufficient for the CR-05 regression.
    """

    def team(self, team: str, map_name: str, side: str) -> float:
        return 0.5

    def team_entry(
        self, team: str, map_name: str, side: str
    ) -> dict[str, Any] | None:
        return None
```

**Step 1.3 — Append the failing regression test** to section 6 (after `test_dp_advance_to_next_map_takes_explicit_next_side_orient`, line ~432). The test is the verbatim 01-REVIEW.md §CR-05 form, adapted to use the local fakes (the original review snippet referenced `_RoundPFnImpl` from live_theo.py which would force a cross-module dep; the round_p_for_round function is a stable public-ish entry that the executor invokes directly — same numerical answer because `_RoundPFnImpl.__call__` ultimately delegates to `round_p_for_round`):

```python
# --------------------------------------------------------------------------- #
# 7. CR-05 regression — pistol_winner_a propagation through DP forward-pass   #
# --------------------------------------------------------------------------- #


def test_dp_anti_eco_uses_gun_win_rate_after_round_1_branch() -> None:
    """CR-05 (VERIFICATION.md gaps[0]): the DP forward-pass MUST update
    BO3State.pistol_winner_a when round 1 settles, so that round 2 (anti-eco)
    dispatches to GUN_WIN_RATE — not the defensive 0.5 fallback in
    round_types.round_p_for_round.

    Setup: fresh BO3 root with pistol_winner_a=(None, None, None) and the A-wins
    branch of round 1 applied. The resulting state has a_round=1, b_round=0 and
    the next round is round 2 (anti-eco). After the CR-05 fix, the propagated
    pistol_winner_a tuple is (True, None, None), so round_p_for_round dispatches
    to GUN_WIN_RATE.

    On current `main` this test FAILS — _advance_round propagates
    pistol_winner_a verbatim and the dispatch falls through to 0.5.
    """
    bo3 = BO3State(
        map_idx=0,
        a_map_score=0,
        b_map_score=0,
        a_round=0,
        b_round=0,
        side_orient="a_atk",
        map_pool=("Lotus", "Bind", "Haven"),
        pistol_winner_a=(None, None, None),
    )

    state_after_round_1_a = _advance_round(bo3, a_wins=True)
    # Verify the state-shape invariant: round counts advanced, pistol slot for
    # the current map populated, others untouched.
    assert state_after_round_1_a.a_round == 1
    assert state_after_round_1_a.b_round == 0
    assert state_after_round_1_a.pistol_winner_a[0] is True, (
        f"CR-05 not closed: pistol_winner_a[0] = "
        f"{state_after_round_1_a.pistol_winner_a[0]!r}, expected True"
    )
    assert state_after_round_1_a.pistol_winner_a[1] is None
    assert state_after_round_1_a.pistol_winner_a[2] is None

    # The A-wins state's next round is round 2 (anti-eco). Dispatch via
    # round_p_for_round directly — same path live_theo's _RoundPFnImpl uses.
    p_round_2 = round_p_for_round(
        state_after_round_1_a, _FakeMatchState(), _FakeHalfRates()  # type: ignore[arg-type]
    )
    assert math.isclose(p_round_2, GUN_WIN_RATE, rel_tol=1e-9), (
        f"CR-05: anti-eco round 2 should use GUN_WIN_RATE ({GUN_WIN_RATE}) "
        f"after A won round 1, got {p_round_2!r}"
    )


def test_dp_anti_eco_returns_complement_after_b_wins_round_1() -> None:
    """CR-05 mirror: B-wins branch of round 1 propagates pistol_winner_a[0] = False,
    and round 2 dispatches to 1 - GUN_WIN_RATE.
    """
    bo3 = BO3State(
        map_idx=0,
        a_map_score=0,
        b_map_score=0,
        a_round=0,
        b_round=0,
        side_orient="a_atk",
        map_pool=("Lotus", "Bind", "Haven"),
        pistol_winner_a=(None, None, None),
    )

    state_after_round_1_b = _advance_round(bo3, a_wins=False)
    assert state_after_round_1_b.a_round == 0
    assert state_after_round_1_b.b_round == 1
    assert state_after_round_1_b.pistol_winner_a[0] is False
    assert state_after_round_1_b.pistol_winner_a[1] is None
    assert state_after_round_1_b.pistol_winner_a[2] is None

    p_round_2 = round_p_for_round(
        state_after_round_1_b, _FakeMatchState(), _FakeHalfRates()  # type: ignore[arg-type]
    )
    assert math.isclose(p_round_2, 1.0 - GUN_WIN_RATE, rel_tol=1e-9), (
        f"CR-05 mirror: anti-eco round 2 should use 1-GUN_WIN_RATE "
        f"({1.0 - GUN_WIN_RATE}) after B won round 1, got {p_round_2!r}"
    )


def test_dp_advance_round_does_not_override_already_settled_pistol() -> None:
    """CR-05 invariant: when pistol_winner_a[map_idx] is already set (e.g., live
    ingestion has populated it), _advance_round MUST NOT override it on subsequent
    round-1 advances. Only None → True/False is permitted; True/False is
    immutable through the DP forward-pass.

    (Construction note: an already-settled pistol_winner_a[0] paired with
    a_round=0, b_round=0 is theoretically reachable only if a caller hand-rolls
    such a state — it is not a state the DP itself produces. The test guards
    against a regression where `_advance_round` unconditionally overrides.)
    """
    bo3 = BO3State(
        map_idx=0,
        a_map_score=0,
        b_map_score=0,
        a_round=0,
        b_round=0,
        side_orient="a_atk",
        map_pool=("Lotus", "Bind", "Haven"),
        pistol_winner_a=(True, None, None),  # already-settled
    )

    state_after = _advance_round(bo3, a_wins=False)
    # B winning the "round 1" should NOT flip pistol_winner_a[0] from True → False.
    assert state_after.pistol_winner_a[0] is True, (
        f"CR-05 invariant violated: _advance_round overrode an already-settled "
        f"pistol_winner_a[0] from True → {state_after.pistol_winner_a[0]!r}"
    )
```

**Step 1.4 — Verify the test fails on current main.** Run:

```bash
.venv/Scripts/python.exe -m pytest tests/pricing/test_dp.py::test_dp_anti_eco_uses_gun_win_rate_after_round_1_branch -x 2>&1 | tail -20
```

Expected: FAIL with `CR-05: anti-eco round 2 should use GUN_WIN_RATE (0.822) ... got 0.5`. (The state-shape assertion at `pistol_winner_a[0] is True` will fail FIRST because `_advance_round` propagates `(None, None, None)` verbatim — that's still a CR-05 failure mode, just a stricter assertion. Either failure flavor is acceptable.)

**Step 1.5 — Atomic commit.** Stage `tests/pricing/test_dp.py` and commit with `test(01-07): add failing CR-05 regression — pistol_winner_a propagation through DP forward-pass`.

NOTE: `test_dp_advance_round_does_not_override_already_settled_pistol` — given the current codebase (no override logic at all), this test PASSES on `main` because `_advance_round` propagates verbatim and `True` survives. After Task 2 lands the conditional `if existing is None` guard, the test still passes (the guard explicitly preserves already-settled values). It's a forward-looking invariant lock; if a future "optimization" ever drops the guard, this test catches the regression.
  </action>
  <verify>
    <automated>.venv/Scripts/python.exe -m pytest tests/pricing/test_dp.py::test_dp_anti_eco_uses_gun_win_rate_after_round_1_branch -x 2>&1 | tail -25</automated>
  </verify>
  <acceptance_criteria>
    - `grep -nE "^def test_dp_anti_eco_uses_gun_win_rate_after_round_1_branch" tests/pricing/test_dp.py` returns exactly one match.
    - `grep -nE "^def test_dp_anti_eco_returns_complement_after_b_wins_round_1" tests/pricing/test_dp.py` returns exactly one match.
    - `grep -nE "^def test_dp_advance_round_does_not_override_already_settled_pistol" tests/pricing/test_dp.py` returns exactly one match.
    - `grep -nE "from src\.config\.constants import GUN_WIN_RATE" tests/pricing/test_dp.py` returns one match.
    - `grep -nE "from src\.pricing\.round_types import round_p_for_round" tests/pricing/test_dp.py` returns one match.
    - `pytest tests/pricing/test_dp.py::test_dp_anti_eco_uses_gun_win_rate_after_round_1_branch -x` exits **NON-ZERO** (the test MUST fail on current main — this is the RED step in TDD).
    - `pytest tests/pricing/test_dp.py::test_dp_anti_eco_returns_complement_after_b_wins_round_1 -x` exits **NON-ZERO** (also fails on current main).
    - `pytest tests/pricing/test_dp.py::test_dp_advance_round_does_not_override_already_settled_pistol -x` exits 0 (already passes — invariant lock for after the fix).
    - `pytest tests/pricing/test_dp.py -k "not anti_eco_uses_gun_win_rate and not anti_eco_returns_complement_after_b_wins" -x` exits 0 (no regression on existing dp tests; only the two new CR-05 tests fail; the `_does_not_override_already_settled_pistol` test passes by accident on main and continues to pass).
    - `mypy --strict src/pricing/` exits 0 (no source change in this task; mypy clean).
    - `ruff check tests/pricing/test_dp.py` exits 0.
    - `git log -1 --format=%s` matches `test\(01-07\): add failing CR-05 regression.*`.
  </acceptance_criteria>
  <done>RED step landed: two failing tests lock the CR-05 invariant at the dp.py level; one already-passing invariant test guards against future regressions; commit recorded.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Fix CR-05 in dp._advance_round (GREEN — Task 1's failing tests now pass)</name>
  <files>src/pricing/dp.py</files>
  <read_first>
    - src/pricing/dp.py lines 104-122 (the current `_advance_round` body — confirm `pistol_winner_a=state.pistol_winner_a` propagates verbatim with no conditional)
    - src/pricing/dp.py lines 125-149 (`_advance_to_next_map` — verify it ALSO propagates `pistol_winner_a` verbatim; this plan does NOT change that behavior because the next map's pistol_winner_a slot must remain None until that map's round 1 settles inside the recursion. The `_advance_round` fix at the next map's round-1 boundary then sets it correctly.)
    - src/pricing/dp.py lines 48-76 (BO3State definition — confirm `pistol_winner_a: tuple[Optional[bool], ...]` is the type, immutable tuple, and BO3State remains frozen+slots+hashable after the rebuild)
    - src/pricing/dp.py lines 168-184 (CR-04 `_clear_pricing_caches` — surface invariant: do NOT touch this; the new tuple-rebuild lands inside `_advance_round` which is called from inside `_series_value_cached`, no lifecycle change)
    - .planning/phases/01-core-pricing-engine/01-REVIEW.md §CR-05 `**Fix:**` block at lines 140-175 (verbatim fix code)
    - .planning/phases/01-core-pricing-engine/01-VERIFICATION.md `gaps:` block, missing[0]
    - CLAUDE.md Critical Rule 11 (mypy --strict on src/pricing/) — the new tuple comprehension MUST type-check; if mypy can't infer `tuple[Optional[bool], ...]` from the comprehension, add an explicit annotation following the `noqa: UP045` precedent already used at line 76
    - tests/pricing/test_dp.py — the three CR-05 tests added in Task 1 must transition from FAIL → PASS after this commit
  </read_first>
  <behavior>
    - `_advance_round(state, a_wins=True)` from `state(a_round=0, b_round=0, pistol_winner_a=(None, None, None))` returns a new `BO3State` with `pistol_winner_a == (True, None, None)`. Length unchanged; type unchanged (`tuple[Optional[bool], ...]`); BO3State remains hashable.
    - `_advance_round(state, a_wins=False)` from the same root returns `pistol_winner_a == (False, None, None)`.
    - `_advance_round(state, a_wins=False)` from `state(a_round=0, b_round=0, pistol_winner_a=(True, None, None))` returns `pistol_winner_a == (True, None, None)` UNCHANGED — the existing True is NOT overridden.
    - `_advance_round(state, a_wins=True)` from `state(a_round=1, b_round=0, pistol_winner_a=(None, None, None))` (i.e., NOT a round-1 boundary) returns `pistol_winner_a == (None, None, None)` UNCHANGED — only the round-1 boundary triggers the update.
    - All three CR-05 tests from Task 1 transition from FAIL → PASS.
    - All 147 prior tests continue to pass: the new tuple-rebuild only fires on the round-1 boundary AND only when `pistol_winner_a[map_idx] is None`, so pre-existing tests with already-settled pistol_winner_a values (e.g., `(True, None, None)` in the OT tests, `(True, True, None)` in the terminal tests) see no change.
    - `mypy --strict src/pricing/` exits 0.
    - `ruff check src/pricing/` exits 0.
  </behavior>
  <action>
**Step 2.1 — Edit `src/pricing/dp.py` `_advance_round`.** The CURRENT body (lines 104-122) reads:

```python
def _advance_round(state: BO3State, a_wins: bool) -> BO3State:
    """Increment the winner's round count; flip side at the round-12 boundary."""
    new_a_round = state.a_round + (1 if a_wins else 0)
    new_b_round = state.b_round + (0 if a_wins else 1)
    # Within-map sides flip after round 12 (i.e., when total==REGULATION_HALF).
    if new_a_round + new_b_round == REGULATION_HALF:
        new_side_orient = "a_def" if state.side_orient == "a_atk" else "a_atk"
    else:
        new_side_orient = state.side_orient
    return BO3State(
        map_idx=state.map_idx,
        a_map_score=state.a_map_score,
        b_map_score=state.b_map_score,
        a_round=new_a_round,
        b_round=new_b_round,
        side_orient=new_side_orient,
        map_pool=state.map_pool,
        pistol_winner_a=state.pistol_winner_a,
    )
```

REPLACE with the version that updates `pistol_winner_a` at the round-1 boundary (verbatim from 01-REVIEW.md §CR-05 `**Fix:**` block lines 144-174, with the docstring expanded to reference VERIFICATION.md):

```python
def _advance_round(state: BO3State, a_wins: bool) -> BO3State:
    """Increment the winner's round count; flip side at the round-12 boundary;
    update ``pistol_winner_a[map_idx]`` when round 1 settles.

    CR-05 fix (VERIFICATION.md gaps[0] / 01-REVIEW.md): the DP forward-pass
    MUST update ``pistol_winner_a[map_idx] = a_wins`` when advancing past
    round 1 of the current map. Round 1 completes when the round count was
    ``(0, 0)`` and is now ``(1, 0)`` or ``(0, 1)``. The update fires ONLY when
    the existing slot is ``None`` (don't override an ingested live value if
    already settled — see ``test_dp_advance_round_does_not_override_already_settled_pistol``
    for the regression lock).

    Phase-2 follow-up: ``pistol_winner_a`` is keyed only by ``map_idx``, so
    rounds 14/15 cannot be conditioned on a separately-tracked second-half
    pistol winner. Phase 1 ships rounds 14/15 falling through to the
    half-rates blend in ``round_types.round_p_for_round`` (the dispatch at
    line 140 + the defensive 0.5 at line 152 covers the gap). Per-half pistol
    shape (``tuple[Optional[tuple[bool, bool]], ...]``) is a Phase 2 task —
    see REQ-round-event-data-pipeline.
    """
    new_a_round = state.a_round + (1 if a_wins else 0)
    new_b_round = state.b_round + (0 if a_wins else 1)
    # Within-map sides flip after round 12 (i.e., when total==REGULATION_HALF).
    if new_a_round + new_b_round == REGULATION_HALF:
        new_side_orient = "a_def" if state.side_orient == "a_atk" else "a_atk"
    else:
        new_side_orient = state.side_orient

    # CR-05: update pistol_winner_a when advancing past round 1 of the current
    # map. The trigger is "round count was (0, 0)" — i.e., we are committing
    # the outcome of round 1 (the pistol). Only update if the slot is currently
    # None; do NOT override ingested live values. The rebuild is a tuple
    # comprehension (BO3State stays frozen / slots / hashable; see line 48).
    new_pistol: tuple[Optional[bool], ...] = state.pistol_winner_a  # noqa: UP045
    if state.a_round == 0 and state.b_round == 0:
        existing = state.pistol_winner_a[state.map_idx]
        if existing is None:
            new_pistol = tuple(
                (a_wins if i == state.map_idx else state.pistol_winner_a[i])
                for i in range(len(state.pistol_winner_a))
            )

    return BO3State(
        map_idx=state.map_idx,
        a_map_score=state.a_map_score,
        b_map_score=state.b_map_score,
        a_round=new_a_round,
        b_round=new_b_round,
        side_orient=new_side_orient,
        map_pool=state.map_pool,
        pistol_winner_a=new_pistol,
    )
```

**Step 2.2 — Verify the tests transition FAIL → PASS.** Run:

```bash
.venv/Scripts/python.exe -m pytest tests/pricing/test_dp.py -x 2>&1 | tail -10
```

Expected: all dp tests pass — including the three CR-05 tests added in Task 1. If any other test breaks, STOP and investigate; the most likely false-failure is a hash-key collision in `_series_value_cached` (because `pistol_winner_a` is now a richer key — but it's still a hashable tuple of `Optional[bool]`, so this is fine; the lru_cache will just see different keys for round-1-boundary states). The OT tests use `pistol_winner_a=(True, None, None)` already, so the round-1 boundary doesn't fire (a_round + b_round != 0 at the OT entry); these continue to pass.

**Step 2.3 — Verify mypy + ruff.**

```bash
.venv/Scripts/python.exe -m mypy --strict src/pricing/ 2>&1 | tail -3
.venv/Scripts/python.exe -m ruff check src/pricing/ 2>&1 | tail -3
```

Expected: both clean. The explicit `tuple[Optional[bool], ...]` annotation + `noqa: UP045` matches the precedent at line 76 of dp.py. If ruff complains about the long docstring, no action needed — it stays under 88 cols (the project's ruff line-length is 100 per pyproject.toml).

**Step 2.4 — Verify the full pricing-test suite.**

```bash
.venv/Scripts/python.exe -m pytest tests/pricing/ -x 2>&1 | tail -10
```

Expected: at least 147 + 2 = 149 passed (the third CR-05 test, `_does_not_override_already_settled_pistol`, was already passing on main — total NEW passing transitions is 2). If the count is lower, a pre-existing test regressed; investigate.

**Step 2.5 — Atomic commit.** Stage `src/pricing/dp.py` and commit with `fix(01-07): close CR-05 — _advance_round updates pistol_winner_a at round-1 boundary`.
  </action>
  <verify>
    <automated>.venv/Scripts/python.exe -m pytest tests/pricing/test_dp.py -x 2>&1 | tail -10 && .venv/Scripts/python.exe -m mypy --strict src/pricing/ 2>&1 | tail -3</automated>
  </verify>
  <acceptance_criteria>
    - `grep -nE "state\.a_round == 0 and state\.b_round == 0" src/pricing/dp.py` returns at least one match (the CR-05 trigger guard inside `_advance_round`).
    - `grep -nE "tuple\(.*for i in range\(len\(state\.pistol_winner_a\)\)" src/pricing/dp.py` returns at least one match (the tuple-rebuild form).
    - `grep -nE "if existing is None:" src/pricing/dp.py` returns one match (the don't-override guard).
    - `grep -nE "CR-05" src/pricing/dp.py` returns at least one match (the docstring + comment trail referencing the gap).
    - `pytest tests/pricing/test_dp.py::test_dp_anti_eco_uses_gun_win_rate_after_round_1_branch -x` exits 0 (RED → GREEN).
    - `pytest tests/pricing/test_dp.py::test_dp_anti_eco_returns_complement_after_b_wins_round_1 -x` exits 0.
    - `pytest tests/pricing/test_dp.py::test_dp_advance_round_does_not_override_already_settled_pistol -x` exits 0 (still passes — invariant survives).
    - `pytest tests/pricing/ -x` exits 0 with all dp + live_theo + round_types + round_conclusion + blend tests passing.
    - `pytest tests/ -x` exits 0 with `>= 149 passed` (147 baseline + 2 newly-passing CR-05 tests; the third already passed on main).
    - `mypy --strict src/pricing/` reports `Success: no issues found in 7 source files`.
    - `ruff check src/pricing/` reports `All checks passed!`.
    - `python -c "from src.pricing.dp import BO3State; from dataclasses import is_dataclass, fields; b = BO3State(map_idx=0,a_map_score=0,b_map_score=0,a_round=0,b_round=0,side_orient='a_atk',map_pool=('x',),pistol_winner_a=(True,)); hash(b); print('hashable')"` prints `hashable` (BO3State stays hashable after the change — frozen+slots invariant preserved).
    - `git log -1 --format=%s` matches `fix\(01-07\): close CR-05.*`.
  </acceptance_criteria>
  <done>CR-05 closed at the dp.py level: `_advance_round` rebuilds `pistol_winner_a` at the round-1 boundary while preserving already-settled values; Task 1's RED tests are GREEN; full suite + mypy + ruff clean; commit recorded.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Fix WR-06 in live_theo._within_map_p_a_wins (GREEN — same root cause, scoped to future-map sub-DP)</name>
  <files>src/pricing/live_theo.py, tests/pricing/test_live_theo.py</files>
  <read_first>
    - src/pricing/live_theo.py lines 204-272 (the entire `_within_map_p_a_wins` body — note the inline state-advance at lines 242-267 which builds a `synthetic` BO3State at lines 242-251 and recurses at lines 263-267 without touching `pistol_winner_a`)
    - src/pricing/live_theo.py lines 30-50 (imports — `BO3State` is imported from `src.pricing.dp` at line 44; if the executor chooses the refactor-to-call-`_advance_round` shape, `_advance_round` is already imported at line 46. NO new imports needed for either shape.)
    - src/pricing/dp.py lines 104-145 (post-Task-2 `_advance_round` — this is the canonical reference shape; the inline-rebuild path in `_within_map_p_a_wins` MUST mirror this logic exactly)
    - .planning/phases/01-core-pricing-engine/01-REVIEW.md §WR-06 (lines 216-235)
    - .planning/phases/01-core-pricing-engine/01-VERIFICATION.md `gaps:` block, missing[1]
    - tests/pricing/test_live_theo.py lines 30-44 (imports — `_within_map_p_a_wins` is NOT currently imported; you'll add it for the new test) and lines 178-294 (`_synthetic_half_rates`, `_synthetic_match_state`, plus existing `_RoundPFnImpl`/`_bo3_state_from_match_state` import).
    - CLAUDE.md Critical Rule 1 (single canonical entry point — the executor MUST pick ONE shape: inline-rebuild OR refactor-to-`_advance_round`. Mixing both — half rebuild, half delegate — is forbidden.)
  </read_first>
  <behavior>
    - `_within_map_p_a_wins` now propagates `pistol_winner_a` correctly through its own forward-pass. After the fix, calling `_within_map_p_a_wins(map_pool=("Lotus","Bind","Haven"), map_idx=1, starting_side="a_atk", pistol_winner_a=(None, None, None), match_state=..., half_rates=...)` and instrumenting the inner `_p_a_recursive` produces, for the round-2 sub-state under "A won round 1 of map 1", a `synthetic` BO3State with `pistol_winner_a[1] = True` (not `None`) when `round_p_for_round` is invoked — so the dispatch hits `GUN_WIN_RATE`, not the 0.5 fallback.
    - Test 1 (`test_within_map_anti_eco_uses_gun_win_rate_after_round_1_branch`): A behavioral probe via the law-of-total-probability decomposition — call `_within_map_p_a_wins` three times with the SAME (state, half_rates, map_idx=1, starting_side) but DIFFERENT pistol_winner_a tuples: (None,None,None) [the unset case], (None,True,None) [A-wins-pistol branch], and (None,False,None) [B-wins-pistol branch]. Probe `p_round_1 = _RoundPFnImpl(state, hr)(round_1_synthetic_at_map_1)`. Then assert `p_unset == p_round_1 * p_a_pistol + (1 - p_round_1) * p_b_pistol` to rel_tol=1e-6. This decomposition is the DP recursion's own forward-pass at the round-1 boundary; it holds STRUCTURALLY when WR-06 is closed and fails by > 1e-3 pre-fix (when the unset call ignores round 1 because round 2 onwards always returns 0.5). No instrumentation / spy / observer pattern needed — `_within_map_p_a_wins` constructs its own `_RoundPFnImpl` closure internally with no clean injection seam.
    - All 149 prior tests + the new test pass.
    - `mypy --strict src/pricing/` exits 0.
    - `ruff check src/pricing/ tests/pricing/` exits 0.
  </behavior>
  <action>
**Step 3.1 — Choose ONE shape.** Two acceptable forms exist; pick exactly one:

- **Form A (inline rebuild — preferred, matches the existing within-map style):** Add the same `pistol_winner_a` tuple-rebuild logic at the inline state-advance site (lines 253-262). The synthetic BO3State at lines 242-251 stays as-is; the rebuild logic is added at the recursion call site, computing the next `pistol_winner_a` tuple before recursing.
- **Form B (refactor to call `_advance_round`):** Drop the inline state-advance entirely and call `_advance_round(synthetic, a_wins=True)` / `_advance_round(synthetic, a_wins=False)` to build the next states, then read `.a_round`, `.b_round`, `.side_orient`, `.pistol_winner_a` off the returned BO3State.

Form A is preferred because:
1. The inline state-advance currently uses an integer-tuple memo key `(a_round, b_round, side_orient)` — Form B would force restructuring the memo to also key on `pistol_winner_a` (or to abandon memoization, hurting perf). Form A keeps the memo intact.
2. The existing inline state-advance is structurally simpler than `_advance_round`'s full BO3State rebuild — it only updates `a_round`, `b_round`, `side_orient`. Form A adds the minimal pistol-update code alongside.
3. Form B introduces a new function call inside the recursion's hot path; lru_cache benefits don't transfer because `_advance_round` is a regular function (not cached).

USE FORM A. The action below assumes Form A. If the executor strongly prefers Form B for cleanliness, the corresponding acceptance criterion (the grep pattern) must be loosened to `(state\.a_round == 0 and state\.b_round == 0|_advance_round\()`.

**Step 3.2 — Edit `src/pricing/live_theo.py` `_within_map_p_a_wins`.** The CURRENT inline state-advance (lines 242-267) reads:

```python
        synthetic = BO3State(
            map_idx=map_idx,
            a_map_score=0,
            b_map_score=0,
            a_round=a_round,
            b_round=b_round,
            side_orient=side_orient,
            map_pool=map_pool,
            pistol_winner_a=pistol_winner_a,
        )
        p_round = fn(synthetic)
        new_a_round = a_round + 1
        if new_a_round + b_round == REGULATION_HALF:
            side_after_a_win = "a_def" if side_orient == "a_atk" else "a_atk"
        else:
            side_after_a_win = side_orient
        new_b_round = b_round + 1
        if a_round + new_b_round == REGULATION_HALF:
            side_after_b_win = "a_def" if side_orient == "a_atk" else "a_atk"
        else:
            side_after_b_win = side_orient
        result = p_round * _p_a_recursive(
            new_a_round, b_round, side_after_a_win
        ) + (1.0 - p_round) * _p_a_recursive(
            a_round, new_b_round, side_after_b_win
        )
        memo[(a_round, b_round, side_orient)] = result
        return result
```

The `synthetic` BO3State at the TOP carries the closure-bound `pistol_winner_a` (which for future maps is `(None, None, None)` at the call site). When `fn(synthetic)` is invoked AT the round-2 boundary (i.e., `a_round=1, b_round=0` after one recursion step), the `synthetic` STILL has `pistol_winner_a[map_idx] is None` because the recursion's state-advance only touches `a_round, b_round, side_orient`, not `pistol_winner_a`.

**Form A fix:** Track the per-recursion `pistol_winner_a` as the FOURTH recursion variable. The memo key extends to `(a_round, b_round, side_orient, pistol_winner_a)` — but `pistol_winner_a` is already a hashable tuple, so the memo stays well-typed. REPLACE the entire `_within_map_p_a_wins` body (lines 224-272) with:

```python
    """P(A wins the map at ``map_idx`` | within-map root at (0, 0)).

    Used ONLY by ``_marginal_map_prob`` for ``m > state.map_idx``, where
    feeding the BO3 ``series_value`` DP an unreachable synthetic root would
    push it past ``len(map_pool)`` (audit-engine series_value always advances
    to next map after a within-map clinch). Terminates strictly at
    WIN_THRESHOLD or the explicit OT-as-coinflip leaf (DEC-009 / D-05).
    Output clipped per DEC-012.

    WR-06 fix (VERIFICATION.md gaps[1] / 01-REVIEW.md WR-06 — same root cause
    as CR-05 scoped to the future-map sub-DP): the inline state-advance now
    propagates ``pistol_winner_a`` through the recursion, mirroring
    ``dp._advance_round``. At the round-1 boundary (a_round == 0 and b_round
    == 0), the next sub-state's ``pistol_winner_a[map_idx]`` is set to the
    branch's ``a_wins`` truth IF the slot was previously None (don't override
    ingested live values). The recursion then carries the updated tuple
    forward so round 2 / 3 dispatch hits GUN_WIN_RATE in
    ``round_p_for_round``, not the defensive 0.5 fallback. The cache key
    is extended to ``(a_round, b_round, side_orient, pistol_winner_a)`` — the
    propagated tuple is hashable, so the memo stays well-typed.

    Memoizes the within-map sub-states with functools.lru_cache. The cache is
    cleared between calls via ``_clear_pricing_caches`` (CR-04). Per-call
    allocation is intentional (per-call closure binding of ``match_state`` /
    ``half_rates`` differs across callers).
    """
    # Build a lightweight closure over the within-map state space.
    fn = _RoundPFnImpl(match_state=match_state, half_rates=half_rates)
    memo: dict[
        tuple[int, int, str, tuple[Optional[bool], ...]],  # noqa: UP045
        float,
    ] = {}

    def _p_a_recursive(
        a_round: int,
        b_round: int,
        side_orient: str,
        pistol: tuple[Optional[bool], ...],  # noqa: UP045
    ) -> float:
        cached = memo.get((a_round, b_round, side_orient, pistol))
        if cached is not None:
            return cached
        if a_round >= WIN_THRESHOLD:
            return 1.0
        if b_round >= WIN_THRESHOLD:
            return 0.0
        if a_round + b_round == REGULATION_HALF * 2:
            # OT-as-coinflip leaf per DEC-009. Within-map OT continues with
            # constant p=0.5 until win-by-2; collapsed here to a scalar 0.5
            # because the within-map P(A wins) stays at 0.5 in OT (symmetric).
            return 0.5
        synthetic = BO3State(
            map_idx=map_idx,
            a_map_score=0,
            b_map_score=0,
            a_round=a_round,
            b_round=b_round,
            side_orient=side_orient,
            map_pool=map_pool,
            pistol_winner_a=pistol,
        )
        p_round = fn(synthetic)

        # WR-06: propagate pistol_winner_a at the round-1 boundary, mirroring
        # dp._advance_round (CR-05 fix). Round 1 settles when (a_round, b_round)
        # was (0, 0) on entry — the about-to-recurse sub-states represent
        # post-round-1 states, so we update pistol_winner_a[map_idx] for each
        # branch IF the slot is currently None.
        if a_round == 0 and b_round == 0 and pistol[map_idx] is None:
            pistol_after_a: tuple[Optional[bool], ...] = tuple(  # noqa: UP045
                (True if i == map_idx else pistol[i]) for i in range(len(pistol))
            )
            pistol_after_b: tuple[Optional[bool], ...] = tuple(  # noqa: UP045
                (False if i == map_idx else pistol[i]) for i in range(len(pistol))
            )
        else:
            pistol_after_a = pistol
            pistol_after_b = pistol

        new_a_round = a_round + 1
        if new_a_round + b_round == REGULATION_HALF:
            side_after_a_win = "a_def" if side_orient == "a_atk" else "a_atk"
        else:
            side_after_a_win = side_orient
        new_b_round = b_round + 1
        if a_round + new_b_round == REGULATION_HALF:
            side_after_b_win = "a_def" if side_orient == "a_atk" else "a_atk"
        else:
            side_after_b_win = side_orient
        result = p_round * _p_a_recursive(
            new_a_round, b_round, side_after_a_win, pistol_after_a
        ) + (1.0 - p_round) * _p_a_recursive(
            a_round, new_b_round, side_after_b_win, pistol_after_b
        )
        memo[(a_round, b_round, side_orient, pistol)] = result
        return result

    raw = _p_a_recursive(0, 0, starting_side, pistol_winner_a)
    return max(CONVICTION_CLIP_LOW, min(CONVICTION_CLIP_HIGH, raw))
```

DIRECTIVE (per checker fix I-08 — WR-07 stays DEFERRED): the docstring's existing "Memoizes the within-map sub-states with functools.lru_cache" line MUST be preserved verbatim. The WR-06 fix lands by ADDING a new paragraph (the "WR-06 fix (...)" block above) — it does NOT touch the existing lru_cache wording. WR-07 (the docstring's incorrect lru_cache claim) is explicitly listed as out-of-scope at the top of this plan; closing it here would be silent scope creep. The acceptance criteria below grep for BOTH (1) the preserved lru_cache wording AND (2) the new WR-06 / pistol_winner_a paragraph — confirming WR-07 is still open while WR-06 is closed.

**Step 3.3 — Append the WR-06 regression test** to `tests/pricing/test_live_theo.py`. First, add `_within_map_p_a_wins` to the imports (lines 32-44):

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
    _within_map_p_a_wins,
)
```

Then append the new test after the existing `_within_map_p_a_wins` cluster (search for the first `def test_*` that mentions `_within_map`; if none exists, slot it in the public-surface cluster — the test does NOT depend on any other test module, only on `_synthetic_half_rates` / `_synthetic_match_state`):

```python
def test_within_map_anti_eco_uses_gun_win_rate_after_round_1_branch() -> None:
    """WR-06 (VERIFICATION.md gaps[1] / 01-REVIEW.md WR-06 — CR-05 scoped to
    future-map sub-DP): _within_map_p_a_wins's inline state-advance must
    propagate pistol_winner_a through the recursion, so round 2 of a future
    map dispatches to GUN_WIN_RATE — not the defensive 0.5 fallback.

    Behavioral assertion (load-bearing): the law-of-total-probability
    decomposition holds. Specifically, with pistol_winner_a=(None,None,None)
    at the call site, the post-fix value of _within_map_p_a_wins(map_idx=1)
    EQUALS:
        p_round_1 * _within_map_p_a_wins(pistol_winner_a=(None,True,None))
        + (1 - p_round_1) * _within_map_p_a_wins(pistol_winner_a=(None,False,None))
    where p_round_1 is the half-rates BT blend for round 1 of map 1 (the
    Phase-1 pistol round dispatch). Pre-fix, the equality fails — the unset
    call ignores round 1 because round 2 onwards hits 0.5 regardless.

    On current main (pre-WR-06 fix), the decomposition equality fails by
    > 1e-3 under asymmetric anti-eco contributions. After the fix it holds
    to rel_tol=1e-6.
    """
    hr = _synthetic_half_rates()
    state = _synthetic_match_state(map_idx=0, pistol_winner_a={0: None, 1: None, 2: None})
    bo3 = _bo3_state_from_match_state(state)

    p_unset = _within_map_p_a_wins(
        map_pool=bo3.map_pool,
        map_idx=1,
        starting_side="a_atk",
        pistol_winner_a=(None, None, None),
        match_state=state,
        half_rates=hr,
    )
    p_a_pistol = _within_map_p_a_wins(
        map_pool=bo3.map_pool,
        map_idx=1,
        starting_side="a_atk",
        pistol_winner_a=(None, True, None),
        match_state=state,
        half_rates=hr,
    )
    p_b_pistol = _within_map_p_a_wins(
        map_pool=bo3.map_pool,
        map_idx=1,
        starting_side="a_atk",
        pistol_winner_a=(None, False, None),
        match_state=state,
        half_rates=hr,
    )

    # Round 1 of map 1 with starting_side='a_atk': p_round_1 is the half-rates
    # blend (Phase 1 simplification A8). Compute it via _RoundPFnImpl on a
    # synthetic round-1 state.
    fn_probe = _RoundPFnImpl(match_state=state, half_rates=hr)
    round_1_synthetic = BO3State(
        map_idx=1,
        a_map_score=0,
        b_map_score=0,
        a_round=0,
        b_round=0,
        side_orient="a_atk",
        map_pool=bo3.map_pool,
        pistol_winner_a=(None, None, None),
    )
    p_round_1 = fn_probe(round_1_synthetic)

    # After the WR-06 fix: p_unset == p_round_1 * p_a_pistol + (1 - p_round_1) * p_b_pistol
    # This is the law-of-total-probability decomposition. Pre-fix, p_unset is
    # systematically wrong because round 2 onwards uses 0.5 regardless of
    # round-1 outcome.
    expected = p_round_1 * p_a_pistol + (1.0 - p_round_1) * p_b_pistol
    assert math.isclose(p_unset, expected, rel_tol=1e-6, abs_tol=1e-9), (
        f"WR-06 not closed: _within_map_p_a_wins with unset pistol_winner_a "
        f"returned {p_unset!r}, expected the law-of-total-probability "
        f"decomposition {expected!r} (= {p_round_1!r} * {p_a_pistol!r} + "
        f"{1.0 - p_round_1!r} * {p_b_pistol!r})"
    )
    # The decomposition assertion above is the load-bearing one. Under the
    # symmetric _synthetic_half_rates, p_a_pistol > 0.5 and p_b_pistol < 0.5
    # (asymmetric anti-eco), so the decomposition differs from any flat-0.5
    # anti-eco dispatch — pre-fix, p_unset ignored round 1 entirely.
```

NOTE on the test design: the law-of-total-probability decomposition assertion is the load-bearing one. It STRUCTURALLY locks WR-06 without depending on absolute magnitudes: pre-fix, `p_unset` ignores round-1 entirely (round 2 always returns 0.5), so the decomposition equality fails by ~1e-3 or more under asymmetric half-rates; post-fix, the equality holds to `rel_tol=1e-6`. We deliberately do NOT use a spy / observer pattern on `_RoundPFnImpl` — `_within_map_p_a_wins` constructs its own closure internally, there is no clean injection seam, and the decomposition assertion is behaviorally equivalent without requiring instrumentation.

**Step 3.4 — Verify all tests pass.**

```bash
.venv/Scripts/python.exe -m pytest tests/pricing/ -x 2>&1 | tail -10
.venv/Scripts/python.exe -m mypy --strict src/pricing/ 2>&1 | tail -3
.venv/Scripts/python.exe -m ruff check src/pricing/ tests/pricing/ 2>&1 | tail -3
```

Expected: `>= 150 passed`, `Success`, `All checks passed!`.

**Step 3.5 — Atomic commit.** Stage `src/pricing/live_theo.py` + `tests/pricing/test_live_theo.py` and commit with `fix(01-07): close WR-06 — _within_map_p_a_wins propagates pistol_winner_a through future-map sub-DP`.
  </action>
  <verify>
    <automated>.venv/Scripts/python.exe -m pytest tests/pricing/ -x 2>&1 | tail -10 && .venv/Scripts/python.exe -m mypy --strict src/pricing/ 2>&1 | tail -3</automated>
  </verify>
  <acceptance_criteria>
    - `grep -nE "a_round == 0 and b_round == 0 and pistol\[map_idx\] is None" src/pricing/live_theo.py` returns at least one match (the WR-06 trigger guard inside the inner `_p_a_recursive`).
    - `grep -nE "pistol_after_a|pistol_after_b" src/pricing/live_theo.py` returns at least two matches (the per-branch propagated tuples).
    - `grep -nE "WR-06" src/pricing/live_theo.py` returns at least one match (the docstring trail referencing the gap).
    - `grep -nE "tuple\(.*for i in range\(len\(pistol\)\)" src/pricing/live_theo.py` returns at least two matches (the two per-branch tuple-rebuilds — one for A-wins, one for B-wins).
    - `grep -q "functools.lru_cache" src/pricing/live_theo.py` exits 0 (per checker fix I-08 — WR-07 stays deferred; the original docstring's lru_cache claim is preserved verbatim).
    - `grep -qE "pistol_winner_a.*update|CR-05|WR-06" src/pricing/live_theo.py` exits 0 (per checker fix I-08 — confirms the WR-06 paragraph IS added).
    - `ruff check tests/pricing/test_live_theo.py` exits 0 (lint regression caught at task-end, not at smoke-gate — explicitly named here per checker fix I-02).
    - `pytest tests/pricing/test_live_theo.py::test_within_map_anti_eco_uses_gun_win_rate_after_round_1_branch -x` exits 0.
    - `pytest tests/pricing/ -x` exits 0 with all tests passing.
    - `pytest tests/ -x` exits 0 with `>= 150 passed`.
    - `mypy --strict src/pricing/` reports `Success: no issues found in 7 source files`.
    - `ruff check src/pricing/ tests/pricing/` reports `All checks passed!`.
    - `git log -1 --format=%s` matches `fix\(01-07\): close WR-06.*`.
  </acceptance_criteria>
  <done>WR-06 closed at the live_theo.py level: `_within_map_p_a_wins` propagates `pistol_winner_a` through its inline recursion, mirroring `dp._advance_round`; law-of-total-probability decomposition test locks the behavior; commit recorded.</done>
</task>

<task type="auto">
  <name>Task 4: Re-scope test_anti_eco_with_none_pistol_winner_returns_defensive_05 (rename + docstring update)</name>
  <files>tests/pricing/test_round_types.py</files>
  <read_first>
    - tests/pricing/test_round_types.py lines 213-222 (the test to re-scope — current docstring blesses the broken behavior)
    - src/pricing/round_types.py lines 146-153 (the dispatch the test exercises — UNCHANGED in this plan; the defensive 0.5 fallback remains as a guard for malformed external inputs)
    - .planning/phases/01-core-pricing-engine/01-VERIFICATION.md `gaps:` block, missing[3]
    - .planning/phases/01-core-pricing-engine/01-REVIEW.md §CR-05 commentary on test re-scoping (the body of CR-05 explains why the test must be retained — the dispatch is correct in isolation, the bug was upstream in dp.py)
  </read_first>
  <behavior>
    - The renamed test `test_anti_eco_with_none_pistol_winner_returns_defensive_05_for_malformed_external_input` exists in `tests/pricing/test_round_types.py`.
    - The docstring is updated to clarify: the 0.5 fallback at `round_types.py:152` is for malformed *external* inputs only; DP forward-pass states will never reach this branch with `pistol_winner_a[map_idx] is None` for in-recursion rounds 2/3 after CR-05 (this plan) closes.
    - The assertion target is UNCHANGED — `actual == 0.5` — because the round_types.py dispatch is unchanged. Only the docstring changes; the behavior contract for malformed external input is preserved.
    - The test continues to pass.
    - All 150+ prior tests + this re-scoped test pass.
  </behavior>
  <action>
**Step 4.1 — Edit `tests/pricing/test_round_types.py` lines 213-222.** REPLACE:

```python
def test_anti_eco_with_none_pistol_winner_returns_defensive_05() -> None:
    """Defensive: round 2 with pistol_winner_a=None → 0.5 (shouldn't happen in
    well-formed states, but covered for robustness)."""
    state = _state(
        a_round=1,
        b_round=0,
        pistol_winner_a=(None, None, None),
    )
    actual = round_p_for_round(state, _FakeMatchState(), _FakeHalfRates())  # type: ignore[arg-type]
    assert actual == 0.5
```

with:

```python
def test_anti_eco_with_none_pistol_winner_returns_defensive_05_for_malformed_external_input() -> None:
    """The 0.5 fallback at round_types.py:152 is for MALFORMED EXTERNAL INPUTS
    only — e.g., a caller hand-rolling a state with `a_round + b_round + 1 == 2`
    AND `pistol_winner_a[map_idx] is None` (an inconsistent live-ingestion
    payload). In a well-formed DP forward-pass after the CR-05 fix
    (01-VERIFICATION.md gaps[0] / 01-07 plan), `dp._advance_round` populates
    `pistol_winner_a[map_idx]` when round 1 settles, so the round-2/3 dispatch
    in DP recursion NEVER reaches this branch. Same for the future-map sub-DP
    after the WR-06 fix in `_within_map_p_a_wins`.

    The assertion target is UNCHANGED: the round_types.py dispatch is unchanged;
    only the upstream DP forward-pass updates pistol_winner_a. This test now
    documents the post-fix invariant — the 0.5 fallback is a defensive guard
    against malformed external inputs, not a code path the DP ever hits.
    """
    state = _state(
        a_round=1,
        b_round=0,
        pistol_winner_a=(None, None, None),
    )
    actual = round_p_for_round(state, _FakeMatchState(), _FakeHalfRates())  # type: ignore[arg-type]
    assert actual == 0.5
```

**Step 4.2 — Verify the test passes.**

```bash
.venv/Scripts/python.exe -m pytest tests/pricing/test_round_types.py -x 2>&1 | tail -10
```

Expected: all tests pass — including the renamed one. (The test count stays 10 in this file because it was a rename, not an add.)

**Step 4.3 — Atomic commit.** Stage `tests/pricing/test_round_types.py` and commit with `test(01-07): re-scope CR-05 defensive-fallback test to clarify post-fix invariant`.

NOTE: do NOT delete the old test name. The rename is a single replacement; downstream test-discovery + git-history grep on the new name will surface this test as the canonical post-fix invariant lock.
  </action>
  <verify>
    <automated>.venv/Scripts/python.exe -m pytest tests/pricing/test_round_types.py -x 2>&1 | tail -10</automated>
  </verify>
  <acceptance_criteria>
    - `grep -nE "^def test_anti_eco_with_none_pistol_winner_returns_defensive_05_for_malformed_external_input" tests/pricing/test_round_types.py` returns exactly one match.
    - `grep -nE "^def test_anti_eco_with_none_pistol_winner_returns_defensive_05\b" tests/pricing/test_round_types.py` returns ZERO matches (the OLD name is gone — rename, not add).
    - `grep -nE "MALFORMED EXTERNAL INPUTS|malformed external input" tests/pricing/test_round_types.py` returns at least one match (new docstring substring).
    - `grep -nE "CR-05" tests/pricing/test_round_types.py` returns at least one match (docstring trail).
    - `grep -nE "assert actual == 0\.5" tests/pricing/test_round_types.py` returns at least one match — the assertion target is unchanged.
    - `pytest tests/pricing/test_round_types.py::test_anti_eco_with_none_pistol_winner_returns_defensive_05_for_malformed_external_input -x` exits 0.
    - `pytest tests/pricing/ -x` exits 0.
    - `pytest tests/ -x` exits 0 with `>= 150 passed` (test count unchanged from Task 3 — rename only).
    - `ruff check tests/pricing/test_round_types.py` exits 0.
    - `git log -1 --format=%s` matches `test\(01-07\): re-scope CR-05.*`.
  </acceptance_criteria>
  <done>Re-scoped test landed: docstring documents the post-fix invariant; assertion target unchanged; commit recorded.</done>
</task>

<task type="auto">
  <name>Task 5: Document the second-half pistol Phase-2 follow-up in dp.py</name>
  <files>src/pricing/dp.py</files>
  <read_first>
    - src/pricing/dp.py lines 1-33 (current module docstring — note the existing four-bullet "Fixes documented bugs" list at lines 4-15; the Phase-2 follow-up note slots cleanly as a fifth bullet OR as a separate "Phase 1 simplifications" subsection)
    - src/pricing/round_types.py lines 16-30 (the existing "Phase 1 simplification (A8)" and "Phase 1 simplification (A6)" docstrings — pattern this section after them)
    - .planning/phases/01-core-pricing-engine/01-RESEARCH.md (the Assumptions Log — A6/A8 pattern)
    - .planning/phases/01-core-pricing-engine/01-VERIFICATION.md `gaps:` block, missing[4]
  </read_first>
  <behavior>
    - `src/pricing/dp.py` module docstring carries a new section/bullet documenting that `pistol_winner_a` is keyed only by `map_idx`, so rounds 14/15 cannot be conditioned on a separately-tracked second-half pistol winner under the current data shape.
    - The note explicitly references Phase 2 (REQ-round-event-data-pipeline) as the follow-up venue.
    - The note explicitly states that Phase 1 ships rounds 14/15 falling through to the half-rates blend via `round_types.round_p_for_round` line 140 (rounds 14/15 dispatch on `pistol_winner_a[map_idx]` which for the second half is the FIRST-half pistol winner — Phase-1 acceptable per RESEARCH.md A8; Phase 2 will refine).
    - mypy + ruff stay clean (docstring-only change).
    - All tests continue to pass.
    - The note is grep-discoverable via `Phase 2|Phase-2|second-half pistol`.
  </behavior>
  <action>
**Step 5.1 — Edit `src/pricing/dp.py` module docstring.** The CURRENT module docstring (lines 1-33) reads:

```python
"""Generalized BO3 DP (`series_value`).

Replaces audit-engine `_markov_map_win` (reference/theo_engine.py:168-206) with
a single top-down memoized recursion over the full BO3 ``BO3State`` (DEC-002 —
same DP for series and per-map; no parallel models). Fixes documented bugs:

  1. OT-as-coinflip via ``range(26)`` (PRD §12.2 #3) → explicit hard-stop at
     ``total = REGULATION_HALF * 2`` with documented coinflip leaf (DEC-009).
  2. Constant ``p1``/``p2`` per half (PRD §12.2 #5) → ``round_p_fn(state)``
     called per-round (the round-type-aware closure ships in
     src/pricing/round_types.py + src/pricing/live_theo.py).
  3. Hardcoded `'a_atk'` start-of-next-map side (PRD §12.2 #6) → next-map
     side comes from `RoundPFn.next_side_orient_for(map_idx)` which live_theo
     binds to `MatchState.map_side_orients[map_idx]`. NO 'a_atk' default
     literal lives in this module.

Cache strategy
--------------
...
"""
```

INSERT a new "Phase 1 simplifications" section AFTER the "Fixes documented bugs" list and BEFORE "Cache strategy" — i.e., between line 15 (`literal lives in this module.`) and line 17 (`Cache strategy`). The new section:

```python
"""Generalized BO3 DP (`series_value`).

Replaces audit-engine `_markov_map_win` (reference/theo_engine.py:168-206) with
a single top-down memoized recursion over the full BO3 ``BO3State`` (DEC-002 —
same DP for series and per-map; no parallel models). Fixes documented bugs:

  1. OT-as-coinflip via ``range(26)`` (PRD §12.2 #3) → explicit hard-stop at
     ``total = REGULATION_HALF * 2`` with documented coinflip leaf (DEC-009).
  2. Constant ``p1``/``p2`` per half (PRD §12.2 #5) → ``round_p_fn(state)``
     called per-round (the round-type-aware closure ships in
     src/pricing/round_types.py + src/pricing/live_theo.py).
  3. Hardcoded `'a_atk'` start-of-next-map side (PRD §12.2 #6) → next-map
     side comes from `RoundPFn.next_side_orient_for(map_idx)` which live_theo
     binds to `MatchState.map_side_orients[map_idx]`. NO 'a_atk' default
     literal lives in this module.
  4. DP forward-pass dropped pistol_winner_a updates at the round-1 boundary
     (CR-05 / 01-VERIFICATION.md gaps[0]) → ``_advance_round`` now sets
     ``pistol_winner_a[map_idx] = a_wins`` when (and only when) round 1
     settles AND the slot is currently None. Anti-eco rounds {2, 3, 14, 15}
     in DP recursion now dispatch correctly via round_types.py.

Phase 1 simplifications (A6 / A8 in RESEARCH.md Assumptions Log; the second-half pistol limitation below is a NEW Phase-1 simplification — Phase-2 follow-up)
---------------------------------------------------------------------
- Rounds 1, 13 (pistols): half-rates Bradley-Terry blend (A8). Phase 2 will
  calibrate per-team pistol-only rates from match_round_data and swap them
  in via the round_types.py dispatch — the call shape doesn't change.
- Rounds 3, 15 use the same GUN_WIN_RATE as rounds 2, 14 (A6). Phase 2
  calibration may differentiate (~75% on round 2 vs ~60% on round 3 per
  roadmap §1.3).
- pistol_winner_a SECOND-HALF LIMITATION (NEW Phase-1 simplification; Phase-2 follow-up — track separately at the roadmap level if Phase 4 calibration surfaces it as a need): the
  ``pistol_winner_a: tuple[Optional[bool], ...]`` shape is keyed by ``map_idx``
  ONLY (one slot per map). It records the FIRST-half pistol winner. Rounds
  14/15 (anti-eco for the second-half pistol) currently dispatch on
  ``pistol_winner_a[map_idx]`` — i.e., they re-use the first-half pistol
  winner as a proxy. This is structurally wrong but quantitatively bounded
  for Phase 1: the dispatch produces GUN_WIN_RATE / 1-GUN_WIN_RATE biased
  toward the first-half pistol's outcome. Phase 2 (REQ-round-event-data-pipeline)
  will extend the data shape to ``tuple[Optional[tuple[bool, bool]], ...]``
  per (map, half) and update the round_types.py dispatch to consult the
  appropriate half. NO data-shape change in Phase 1 — round_types.py:140
  + the defensive 0.5 fallback at round_types.py:152 cover the gap until
  Phase 2 lands.

Cache strategy
--------------
...
"""
```

The four-item bug-fix list now grows to FIVE items (CR-05 closure as item 4), and a new "Phase 1 simplifications" section documents the second-half pistol Phase-2 follow-up limitation explicitly. The "Cache strategy" subsection and everything below stays unchanged.

**Step 5.2 — Verify mypy + ruff + full suite.**

```bash
.venv/Scripts/python.exe -m mypy --strict src/pricing/ 2>&1 | tail -3
.venv/Scripts/python.exe -m ruff check src/pricing/ 2>&1 | tail -3
.venv/Scripts/python.exe -m pytest tests/ -x 2>&1 | tail -5
```

Expected: all clean / pass. Docstring-only change is a no-op for mypy + ruff.

**Step 5.3 — Atomic commit.** Stage `src/pricing/dp.py` and commit with `docs(01-07): document second-half pistol Phase-2 follow-up`.
  </action>
  <verify>
    <automated>.venv/Scripts/python.exe -m mypy --strict src/pricing/ 2>&1 | tail -3 && .venv/Scripts/python.exe -m pytest tests/ -x 2>&1 | tail -3</automated>
  </verify>
  <acceptance_criteria>
    - `grep -nE "Phase 2|Phase-2|second-half pistol" src/pricing/dp.py` returns at least one match (the new doc note).
    - `grep -nE "Phase-2 follow-up.*pistol|second-half pistol winner|SECOND-HALF LIMITATION" src/pricing/dp.py` returns at least one match (the new Phase-2-follow-up doc note wording).
    - `grep -nE "REQ-round-event-data-pipeline" src/pricing/dp.py` returns at least one match.
    - `grep -nE "CR-05" src/pricing/dp.py` returns at least two matches (one in `_advance_round` from Task 2, one in the new module docstring item 4).
    - `mypy --strict src/pricing/` reports `Success: no issues found in 7 source files`.
    - `ruff check src/pricing/` reports `All checks passed!`.
    - `pytest tests/ -x` exits 0 with `>= 150 passed` (no test count change — docstring-only commit).
    - `git log -1 --format=%s` matches `docs\(01-07\): document second-half pistol.*`.
  </acceptance_criteria>
  <done>Phase-2 follow-up note landed in dp.py module docstring; second-half pistol limitation explicitly documented as a Phase-2 follow-up (track separately if Phase 4 calibration surfaces it as a need); commit recorded.</done>
</task>

<task type="auto">
  <name>Task 6: Final smoke gate — full suite + mypy + ruff + surface contract + asymmetric-matchup integration test + CR-05 runtime probe</name>
  <files>tests/pricing/test_live_theo.py (one new integration test) — verification mostly</files>
  <read_first>
    - .planning/phases/01-core-pricing-engine/01-VERIFICATION.md "Behavioral Spot-Checks" table (lines 151-165) — the gate replays the same probes; the CR-05 / round 3 / end-to-end-9.25pp probes MUST now PASS (their failing rows in the prior re-verification become passing rows here)
    - .planning/phases/01-core-pricing-engine/01-VERIFICATION.md `## Gaps Summary` (lines 200-235) — the 9.25pp swing baseline numbers
    - src/pricing/__init__.py (the `__all__` line MUST still be exactly `["LiveTheoEngine", "TheoOutput", "MatchState", "HalfRates"]`)
    - .planning/phases/01-core-pricing-engine/01-06-derived-output-fixes-PLAN.md Task 5 final smoke gate (the existing analog — the four CR-04 probes there are the precedent for the CR-05 probe added here)
    - CLAUDE.md Critical Rules 1, 4, 5, 11, 12 (all five must still hold)
  </read_first>
  <behavior>
    - Test 1 (`test_live_theo_asymmetric_pistols_match_unset_pistols_after_dp_propagation`): A behavioral integration test that exercises the natural Phase-4 call site — `LiveTheoEngine` on TeamA=0.55/TeamB=0.45 across all maps/sides with `total=1e9` (no shrinkage) and `pistol_winner_a={0:None, 1:None, 2:None}`. Expected: post-fix, `theo_series` exceeds the prior buggy baseline of `0.887` by a meaningful amount AND is close to the set-pistols-True-True-True baseline of `0.979`. Concrete tolerance: `theo_series > 0.96` AND `abs(theo_series - 0.979) < 0.02`. The test STRUCTURALLY locks the 9.25pp swing closure.
    - Full pytest suite passes with `>= 151 passed` (147 baseline + 2 CR-05 dp tests + 1 invariant lock + 1 WR-06 test + 1 integration test = 152; range allowed `[150, 160]` to absorb minor textual decisions in tasks 1-5).
    - mypy --strict on src/pricing/ exits 0.
    - ruff check on src/pricing/ + tests/pricing/ exits 0.
    - Surface contract: `src.pricing.__all__` unchanged.
    - Forbidden audit-triplet symbols absent.
    - CR-05 runtime probe (matches VERIFICATION.md spot-check #13/#14/#15): all THREE print their `closed` line and exit 0.
    - Memory-leak invariant: `test_no_memory_leak_across_live_theo_calls` STILL passes.
    - This task records ONE commit (the new integration test) and runs verification commands — does NOT modify source code.
  </behavior>
  <action>
**Step 6.1 — Append the asymmetric-matchup integration test** to `tests/pricing/test_live_theo.py`. Slot it after the existing public-surface tests (search for `def test_live_theo_engine_call_surface` and slot AFTER that, in the same cluster as `test_no_memory_leak_across_live_theo_calls`). The test uses an asymmetric `HalfRates` constructed inline (not `_synthetic_half_rates` which is symmetric-ish):

```python
def test_live_theo_asymmetric_pistols_match_unset_pistols_after_dp_propagation() -> None:
    """CR-05 / WR-06 end-to-end behavioral lock (01-VERIFICATION.md re-verification
    9.25pp swing): under asymmetric half-rates (TeamA 0.55, TeamB 0.45 across all
    maps/sides) with total=1e9 (no shrinkage) and pistol_winner_a all-None at the
    call site, the post-fix theo_series MUST satisfy the law-of-total-probability
    decomposition over the round-1 outcome:

        theo_unset == P(A wins R1) * theo_set_AAA + (1 - P(A wins R1)) * theo_set_BBB

    where theo_set_AAA / theo_set_BBB are the engine outputs under
    pistol_winner_a=(True,True,True) / (False,False,False) respectively. Pre-fix,
    this equality fails — the unset call ignored round 1 and returned 0.887 (a
    9.25pp systematic bias from the set-AAA baseline 0.979); post-fix, the DP
    recursion's own forward-pass guarantees the equality.

    The structural decomposition assertion is the LOAD-BEARING check (per
    checker fix I-04); the soft sanity floors below (theo_series > 0.5,
    |theo_unset - theo_set| < 0.5) are NOT load-bearing — they only catch
    totally-broken DPs. The decomposition is mechanically derivable from the
    DP recursion's definition and is independent of GUN_WIN_RATE compounding
    magnitude.
    """
    asymmetric_hr = HalfRates(
        team_rates={
            f"{t}|{m}|{s}": {
                "wins": (0.55 if t == "TeamA" else 0.45) * 1e9,
                "total": 1e9,
                "rate": 0.55 if t == "TeamA" else 0.45,
                "used_fallback": False,
            }
            for t in ("TeamA", "TeamB")
            for m in ("Lotus", "Bind", "Haven")
            for s in ("atk", "def")
        },
        league_rates={
            f"{m}|{s}": {"wins": 50.0 * 1e9, "total": 100.0 * 1e9, "rate": 0.5}
            for m in ("Lotus", "Bind", "Haven")
            for s in ("atk", "def")
        },
        overall_avg=0.5,
    )
    state_unset = _synthetic_match_state(
        pistol_winner_a={0: None, 1: None, 2: None},
    )
    engine = LiveTheoEngine(half_rates=asymmetric_hr)
    out_unset = engine(state_unset)

    state_set = _synthetic_match_state(
        pistol_winner_a={0: True, 1: True, 2: True},
    )
    out_set = engine(state_set)

    # Structural decomposition (load-bearing — independent of compounding
    # magnitudes). After CR-05 fix: theo_series with pistol_winner_a all-None
    # EQUALS the marginal expectation over the round-1 outcome:
    #   theo_unset == P(A wins R1) * theo_set_TTT + (1 - P(A wins R1)) * theo_set_FFF
    # where:
    #   * theo_set_TTT is theo_series under pistol_winner_a=(True,True,True)
    #     (A-wins-pistol branch — coarse approximation: ALL maps' pistols set
    #     to A-wins; for the structural decomposition only the CURRENT map's
    #     pistol entry matters because future maps' entries get re-set by
    #     the DP forward-pass once CR-05 is closed).
    #   * theo_set_FFF is theo_series under pistol_winner_a=(False,False,False)
    #     (B-wins-pistol branch — same coarse approximation).
    # This is the DP's own forward-pass decomposition: the recursion at the
    # round-1 boundary expands as `p * series_value(advance_a_wins) + (1-p) *
    # series_value(advance_b_wins)`.
    p_round_1 = _RoundPFnImpl(match_state=state_unset, half_rates=asymmetric_hr)(
        _bo3_state_from_match_state(state_unset)
    )

    state_pistol_a = _synthetic_match_state(
        pistol_winner_a={0: True, 1: True, 2: True},
    )
    state_pistol_b = _synthetic_match_state(
        pistol_winner_a={0: False, 1: False, 2: False},
    )
    out_set_a = engine(state_pistol_a)
    out_set_b = engine(state_pistol_b)

    decomposition = p_round_1 * out_set_a.theo_series + (1.0 - p_round_1) * out_set_b.theo_series
    assert math.isclose(
        out_unset.theo_series, decomposition, rel_tol=1e-3, abs_tol=1e-3
    ), (
        f"theo_unset ({out_unset.theo_series}) does not match law-of-total-"
        f"probability decomposition ({decomposition}) under "
        f"p_round_1={p_round_1}, out_set_a={out_set_a.theo_series}, "
        f"out_set_b={out_set_b.theo_series}. CR-05/WR-06 not closed at "
        f"the DP forward-pass level."
    )

    # Soft sanity floors (NOT load-bearing — the structural assertion above
    # is the actual content). The absolute magnitude depends on a
    # marginalization over pistol outcomes whose closed-form is fragile to
    # BT-blend asymmetry (P(A wins map | B wins pistol) = 1 - GUN_WIN_RATE
    # = 0.178 per anti-eco round, much lower than TeamA=0.55's per-round
    # baseline; the marginalization recovers most but not all of the set-A
    # baseline). Pre-fix, theo_unset was 0.887 (verification re-run #2);
    # the > 0.5 floor is sufficient to detect a totally-broken DP, while
    # the structural assertion catches the actual CR-05 regression.
    assert out_unset.theo_series > 0.5, (
        f"sanity floor: theo_series with unset pistols = "
        f"{out_unset.theo_series!r}, expected > 0.5 (asymmetric matchup "
        f"with TeamA=0.55 should produce P(TeamA wins series) > 0.5 in any "
        f"reasonable model). The structural decomposition assertion above "
        f"is the load-bearing CR-05 closure check."
    )
    assert abs(out_unset.theo_series - out_set.theo_series) < 0.5, (
        f"extremely loose absolute bound: |theo_unset - theo_set| = "
        f"{abs(out_unset.theo_series - out_set.theo_series)!r}. The "
        f"structural decomposition assertion above is the load-bearing "
        f"CR-05 closure check."
    )
    # Witness the conviction clip is in range; both sides should respect [0.01, 0.99].
    assert 0.01 <= out_unset.theo_series <= 0.99
    assert 0.01 <= out_set.theo_series <= 0.99
```

RATIONALE for the structural decomposition assertion (per checker fix I-04): we assert the law-of-total-probability decomposition, NOT absolute magnitude, because the absolute magnitude depends on a marginalization over pistol outcomes whose closed-form is fragile to BT-blend asymmetry. Specifically, P(A wins map | B wins pistol) = compound of (1 - GUN_WIN_RATE) = 0.178 across anti-eco rounds, which is much lower than P(A wins map | A wins pistol) = compound of GUN_WIN_RATE = 0.822; the marginalization recovers most but not all of the set-A baseline depending on per-round half-rates. Hard-coded magnitude bounds like `> 0.96` are unreachable under the actual marginalization (the verification re-run #2's 0.979 was a SET-pistols-True-True-True measurement; the corresponding all-None-pistol value after the CR-05 fix is the marginal, not 0.979). The structural decomposition is mechanically derivable from the DP recursion's own definition and is independent of GUN_WIN_RATE compounding magnitude.

If the structural decomposition assertion fails, the executor should:
1. Re-verify CR-05 closure at the dp.py level by re-running Task 1's RED tests (they should be GREEN post-Task-2). If they're not GREEN, return to Task 2.
2. Re-verify WR-06 closure at the live_theo.py level by re-running Task 3's regression test. If it's not GREEN, return to Task 3.
3. Inspect the per-map decomposition: verify that for each map m, P(A wins map m | A wins R1 of m) and P(A wins map m | B wins R1 of m) compose correctly with p_round_1.
4. NEVER weaken the fix or the decomposition tolerance to make the test pass — the decomposition is a mathematical invariant of the DP, not a calibration knob.

**Step 6.2 — Run the full smoke gate.**

```bash
# Full pytest:
.venv/Scripts/python.exe -m pytest tests/ --tb=line 2>&1 | tail -10
```

Expected: `>= 151 passed`, zero failures.

```bash
# mypy strict:
.venv/Scripts/python.exe -m mypy --strict src/pricing/ 2>&1 | tail -5
```

Expected: `Success: no issues found in 7 source files`.

```bash
# ruff:
.venv/Scripts/python.exe -m ruff check src/pricing/ tests/pricing/ 2>&1 | tail -5
```

Expected: `All checks passed!`.

```bash
# Surface contract greps (CRule 1 / DEC-010):
grep -RnE "^def series_theo\b|^def series_theo_no_sides\b|^def series_theo_from_map_probs\b|^def model_series_prob\b|^def _signal_strength\b" src/pricing/
```

Expected: exit 1, no matches.

```bash
# Public __all__:
.venv/Scripts/python.exe -c "from src.pricing import LiveTheoEngine, TheoOutput, MatchState, HalfRates; import src.pricing as p; assert p.__all__ == ['LiveTheoEngine', 'TheoOutput', 'MatchState', 'HalfRates'], p.__all__; print('public surface ok')"
```

Expected: `public surface ok`.

**Step 6.3 — CR-05 / WR-06 runtime probes** (matches VERIFICATION.md spot-checks #13/#14/#15 — the previously-failing rows MUST now print `closed`):

```bash
# CR-05 probe: round 2 dispatches to GUN_WIN_RATE after A wins round 1 (was: 0.5).
.venv/Scripts/python.exe -c "
import math
from src.config.constants import GUN_WIN_RATE
from src.pricing.dp import BO3State, _advance_round
from src.pricing.round_types import round_p_for_round
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class FakeMS:
    team_a: str = 'A'
    team_b: str = 'B'

class FakeHR:
    def team(self, t, m, s): return 0.5
    def team_entry(self, t, m, s): return None

bo3 = BO3State(map_idx=0, a_map_score=0, b_map_score=0, a_round=0, b_round=0,
               side_orient='a_atk', map_pool=('Lotus','Bind','Haven'),
               pistol_winner_a=(None, None, None))
state_after_r1_a = _advance_round(bo3, a_wins=True)
assert state_after_r1_a.pistol_winner_a[0] is True, f'CR-05 NOT closed: pistol_winner_a[0] = {state_after_r1_a.pistol_winner_a[0]!r}'
p = round_p_for_round(state_after_r1_a, FakeMS(), FakeHR())
assert math.isclose(p, GUN_WIN_RATE, rel_tol=1e-9), f'CR-05 NOT closed: round 2 returned {p}, expected {GUN_WIN_RATE}'
print(f'CR-05 closed (round 2 -> {p:.4f})')
"
```

Expected: `CR-05 closed (round 2 -> 0.8220)`.

```bash
# CR-05 probe: round 3 also dispatches correctly after stepping forward twice.
.venv/Scripts/python.exe -c "
import math
from src.config.constants import GUN_WIN_RATE
from src.pricing.dp import BO3State, _advance_round
from src.pricing.round_types import round_p_for_round
from dataclasses import dataclass

@dataclass(frozen=True)
class FakeMS:
    team_a: str = 'A'
    team_b: str = 'B'

class FakeHR:
    def team(self, t, m, s): return 0.5
    def team_entry(self, t, m, s): return None

bo3 = BO3State(map_idx=0, a_map_score=0, b_map_score=0, a_round=0, b_round=0,
               side_orient='a_atk', map_pool=('Lotus','Bind','Haven'),
               pistol_winner_a=(None, None, None))
s1 = _advance_round(bo3, a_wins=True)
s2 = _advance_round(s1, a_wins=True)
# s2 is now round 3 about to play (a_round=2, b_round=0).
assert s2.pistol_winner_a[0] is True, 'CR-05 round 3: pistol_winner_a[0] not propagated'
p = round_p_for_round(s2, FakeMS(), FakeHR())
assert math.isclose(p, GUN_WIN_RATE, rel_tol=1e-9), f'CR-05 NOT closed: round 3 returned {p}'
print(f'CR-05 round-3 closed ({p:.4f})')
"
```

Expected: `CR-05 round-3 closed (0.8220)`.

```bash
# CR-05 end-to-end probe: 9.25pp swing closed at TeamA=0.55/TeamB=0.45.
.venv/Scripts/python.exe -c "
from src.pricing import LiveTheoEngine, HalfRates, MatchState
hr = HalfRates(
    team_rates={f'{t}|{m}|{s}': {'wins': (0.55 if t == 'TeamA' else 0.45) * 1e9,
                                  'total': 1e9,
                                  'rate': 0.55 if t == 'TeamA' else 0.45,
                                  'used_fallback': False}
                for t in ('TeamA','TeamB') for m in ('Lotus','Bind','Haven') for s in ('atk','def')},
    league_rates={f'{m}|{s}': {'wins': 50.0*1e9, 'total': 100.0*1e9, 'rate': 0.5}
                  for m in ('Lotus','Bind','Haven') for s in ('atk','def')},
    overall_avg=0.5)

base = dict(match_id='probe', team_a='TeamA', team_b='TeamB',
            map_pool=('Lotus','Bind','Haven'), map_idx=0,
            a_map_score=0, b_map_score=0, a_round=0, b_round=0,
            side_orient='a_atk',
            map_side_orients=('a_atk','a_atk','a_atk'),
            map_winners=(None,None,None),
            numerical_diff=0, bomb_planted=False, side='atk', econ_bucket='full')
state_unset = MatchState(**{**base, 'pistol_winner_a': {0:None,1:None,2:None}})
state_set = MatchState(**{**base, 'pistol_winner_a': {0:True,1:True,2:True}})
engine = LiveTheoEngine(half_rates=hr)
o_unset = engine(state_unset)
o_set = engine(state_set)
swing = abs(o_unset.theo_series - o_set.theo_series)
assert swing < 0.05, f'CR-05 swing NOT closed: |unset-set| = {swing} (pre-fix was 0.0925; tolerance loosened per I-04 — structural decomposition is the load-bearing check)'
assert o_unset.theo_series > 0.5, f'CR-05 unset sanity floor: {o_unset.theo_series} <= 0.5 (asymmetric matchup TeamA=0.55 should produce > 0.5; the structural decomposition assertion in the pytest integration test is the load-bearing check)'
print(f'CR-05 end-to-end closed (unset={o_unset.theo_series:.4f}, set={o_set.theo_series:.4f}, swing={swing:.4f})')
"
```

Expected: `CR-05 end-to-end closed (unset=0.5x-0.99, set=0.97-0.99, swing<0.05)`. The exact unset value depends on the marginalization over pistol outcomes (NOT the set-AAA baseline 0.979); the structural decomposition assertion in the pytest integration test (Task 6 Step 6.1) is the load-bearing check.

ALL THREE PROBES MUST PRINT their `closed` line. Any AssertionError is a gate failure — return to the offending task.

**Step 6.4 — Atomic commit.** Stage `tests/pricing/test_live_theo.py` and commit with `test(01-07): add asymmetric-matchup CR-05/WR-06 end-to-end behavioral lock`.

NOTE: this is the ONLY commit on Task 6. The verification probes in Step 6.3 do NOT commit; they're runtime gates.
  </action>
  <verify>
    <automated>.venv/Scripts/python.exe -m pytest tests/ --tb=line 2>&1 | tail -5 && .venv/Scripts/python.exe -m mypy --strict src/pricing/ 2>&1 | tail -3 && .venv/Scripts/python.exe -m ruff check src/pricing/ tests/pricing/ 2>&1 | tail -3</automated>
  </verify>
  <acceptance_criteria>
    - `grep -nE "^def test_live_theo_asymmetric_pistols_match_unset_pistols_after_dp_propagation" tests/pricing/test_live_theo.py` returns exactly one match.
    - `pytest tests/pricing/test_live_theo.py::test_live_theo_asymmetric_pistols_match_unset_pistols_after_dp_propagation -x` exits 0.
    - `pytest tests/ --tb=line` reports `>= 151 passed` (range allowed `[150, 160]` to absorb minor textual decisions in tasks 1-5; FAILURES are forbidden).
    - `mypy --strict src/pricing/` reports `Success: no issues found in 7 source files` (CRule 11).
    - `ruff check src/pricing/ tests/pricing/` reports `All checks passed!`.
    - `grep -RnE "^def series_theo\b|^def series_theo_no_sides\b|^def series_theo_from_map_probs\b|^def model_series_prob\b|^def _signal_strength\b" src/pricing/` exits 1 with no output (forbidden audit-triplet symbols absent — CRule 1 / DEC-010).
    - `python -c "import src.pricing as p; assert p.__all__ == ['LiveTheoEngine', 'TheoOutput', 'MatchState', 'HalfRates']"` exits 0.
    - All three CR-05 runtime probe scripts (round 2 dispatch, round 3 dispatch, end-to-end 9.25pp swing) print their `closed` line and exit 0.
    - `pytest tests/pricing/test_live_theo.py::test_no_memory_leak_across_live_theo_calls -x` STILL exits 0 (CR-04 invariant preserved — the new tuple-rebuild does not introduce per-call state escape).
    - `pytest tests/pricing/test_live_theo.py::test_live_theo_engine_clears_caches_even_on_exception -x` STILL exits 0 (CR-04 try/finally cleanup preserved).
    - `git log -1 --format=%s` matches `test\(01-07\): add asymmetric-matchup.*`.
  </acceptance_criteria>
  <done>Phase 1 CR-05 / WR-06 gap closure verified end-to-end: full suite green, mypy strict clean, ruff clean, public surface contract preserved, asymmetric-matchup integration test locks the 9.25pp swing closure, all three CR-05 runtime probes print their `closed` line.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| (none — internal pricing module) | This plan only modifies in-process pricing math + test fixtures. No external input flows to the changed code paths in Phase 1. Phase 3 (ingestion) and Phase 4 (Kalshi I/O) own all trust boundaries; they will exercise the corrected pistol/anti-eco dispatch but cannot inject untrusted state into the math layer in this plan. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-01-07-01 | Tampering | `BO3State.pistol_winner_a` tuple-rebuild in `_advance_round` | accept | The rebuild fires only when `state.a_round == 0 AND state.b_round == 0 AND state.pistol_winner_a[map_idx] is None`. Already-settled values are immutable through the DP forward-pass (regression-locked by `test_dp_advance_round_does_not_override_already_settled_pistol`). No external import path mutates `BO3State`; it is `frozen=True, slots=True`. |
| T-01-07-02 | Information Disclosure | Recursive within-map memo carries `pistol_winner_a` as a key component | accept | The memo is per-call (allocated fresh inside `_within_map_p_a_wins`); `pistol_winner_a` is a hashable tuple of `Optional[bool]`; no PII or secret material crosses this boundary. The CR-04 try/finally cleanup in `LiveTheoEngine.__call__` ensures the memo is GC-eligible after each call. |
| T-01-07-03 | Denial of Service | Memo cardinality grows with the number of distinct `pistol_winner_a` tuples seen | accept | The within-map sub-DP visits at most `O(WIN_THRESHOLD^2 * 2 * (len(map_pool) * 3))` states per call. For BO3 with 3 maps this is ~2400 entries — well within memory budget. The CR-04 cleanup bounds total memory at zero added latency cost. |
| T-01-07-04 | Spoofing | A malformed external `pistol_winner_a` (wrong length or non-bool entry) bypasses the round-types dispatch | mitigate (existing) | The defensive 0.5 fallback at `round_types.py:152` (re-scoped in Task 4) catches malformed external inputs. Phase 3 ingestion arbiter (out of scope) will add a `__post_init__` validator on `MatchState.pistol_winner_a` (related to WR-03 from original review, deferred). |
</threat_model>

<verification>
Final phase-level grep-runnable verification (run after Task 6 passes; this is the consolidated gate the verifier will replay):

```bash
# CR-05: _advance_round updates pistol_winner_a at round-1 boundary
grep -qE "state\.a_round == 0 and state\.b_round == 0" src/pricing/dp.py || (echo "CR-05 trigger guard missing in dp.py"; exit 1)
grep -qE "tuple\(.*for i in range\(len\(state\.pistol_winner_a\)\)" src/pricing/dp.py || (echo "CR-05 tuple-rebuild missing"; exit 1)
grep -qE "if existing is None:" src/pricing/dp.py || (echo "CR-05 do-not-override guard missing"; exit 1)
echo "CR-05 dp.py grep ok"

# WR-06: _within_map_p_a_wins propagates pistol_winner_a
grep -qE "a_round == 0 and b_round == 0 and pistol\[map_idx\] is None" src/pricing/live_theo.py || (echo "WR-06 trigger guard missing in live_theo.py"; exit 1)
grep -qE "pistol_after_a|pistol_after_b" src/pricing/live_theo.py || (echo "WR-06 per-branch tuples missing"; exit 1)
echo "WR-06 live_theo.py grep ok"

# Re-scoped test exists
grep -qE "^def test_anti_eco_with_none_pistol_winner_returns_defensive_05_for_malformed_external_input" tests/pricing/test_round_types.py || (echo "Re-scoped test missing"; exit 1)
grep -qE "MALFORMED EXTERNAL INPUTS|malformed external input" tests/pricing/test_round_types.py || (echo "Re-scoped docstring missing"; exit 1)
! grep -qE "^def test_anti_eco_with_none_pistol_winner_returns_defensive_05\(\)" tests/pricing/test_round_types.py || (echo "Old test name still present"; exit 1)
echo "Re-scoped test grep ok"

# Phase-2 follow-up doc note in dp.py
grep -qE "Phase 2|Phase-2|second-half pistol" src/pricing/dp.py || (echo "Phase-2 doc note missing in dp.py"; exit 1)
grep -qE "Phase-2 follow-up.*pistol|second-half pistol winner|SECOND-HALF LIMITATION" src/pricing/dp.py || (echo "Phase-2 follow-up doc note missing in dp.py"; exit 1)
echo "Phase-2 doc note grep ok"

# Surface contract (CRule 1 / DEC-010) — forbidden symbols absent
grep -RnE "^def series_theo\b|^def series_theo_no_sides\b|^def series_theo_from_map_probs\b|^def model_series_prob\b|^def _signal_strength\b" src/pricing/ && (echo "audit-triplet leak"; exit 1) || echo "surface contract ok"

# Public __all__ unchanged
.venv/Scripts/python.exe -c "import src.pricing as p; assert p.__all__ == ['LiveTheoEngine', 'TheoOutput', 'MatchState', 'HalfRates'], p.__all__; print('__all__ ok')"

# CR-04 invariants preserved (regression check)
grep -qE "^def _clear_pricing_caches" src/pricing/dp.py || (echo "CR-04 dp helper regressed"; exit 1)
grep -qE "^def _clear_pricing_caches" src/pricing/live_theo.py || (echo "CR-04 live_theo helper regressed"; exit 1)
grep -qE "finally:" src/pricing/live_theo.py || (echo "CR-04 try/finally regressed"; exit 1)
echo "CR-04 invariants ok"

# Test suite + mypy + ruff
.venv/Scripts/python.exe -m pytest tests/ --tb=line 2>&1 | tail -3
.venv/Scripts/python.exe -m mypy --strict src/pricing/ 2>&1 | tail -3
.venv/Scripts/python.exe -m ruff check src/pricing/ tests/pricing/ 2>&1 | tail -3
```

ALL of the above lines must print their `ok` (or `closed`) message and exit 0; pytest must report `>= 150 passed` with zero failures; mypy must report `Success: no issues found in 7 source files`; ruff must report `All checks passed!`.
</verification>

<success_criteria>
- `pytest tests/` exits 0 with at least 150 tests passing (147 baseline + minimum 2 new regression tests across tasks 1-3 + 1 integration test in task 6; range allowed `[150, 160]` to absorb minor textual decisions).
- `mypy --strict src/pricing/` exits 0 with `Success: no issues found in 7 source files`.
- `ruff check src/pricing/ tests/pricing/` exits 0 with `All checks passed!`.
- The single open BLOCKER from `01-VERIFICATION.md` (CR-05) and its scoped twin (WR-06) are closed at the source level with regression tests asserting the exact behavior the verifier confirmed broken at runtime: `_advance_round` updates `pistol_winner_a[map_idx]` at the round-1 boundary; `_within_map_p_a_wins` mirrors the same logic; round-2 dispatch in DP recursion now hits GUN_WIN_RATE; end-to-end 9.25pp swing closed via the LAW-OF-TOTAL-PROBABILITY DECOMPOSITION assertion (per checker fix I-04 — `theo_unset == p_round_1 * theo_set_AAA + (1-p_round_1) * theo_set_BBB` to `rel_tol=1e-3`), with soft sanity floors (`theo_unset > 0.5`, `|theo_unset - theo_set| < 0.5`) as non-load-bearing guards.
- Public surface contract preserved: `src.pricing.__all__ == ["LiveTheoEngine", "TheoOutput", "MatchState", "HalfRates"]`; no audit-triplet symbols reappear in `src/pricing/`.
- Six atomic commits land in order: `test(01-07): add failing CR-05 regression ...`, `fix(01-07): close CR-05 ...`, `fix(01-07): close WR-06 ...`, `test(01-07): re-scope CR-05 ...`, `docs(01-07): document second-half pistol ...`, `test(01-07): add asymmetric-matchup ...`.
- No source file outside `src/pricing/dp.py`, `src/pricing/live_theo.py`, `tests/pricing/test_dp.py`, `tests/pricing/test_live_theo.py`, `tests/pricing/test_round_types.py` is modified — no scope creep into WR-07/WR-08, IN-05..IN-07, or remaining deferred items.
- The re-scoped test `test_anti_eco_with_none_pistol_winner_returns_defensive_05_for_malformed_external_input` retains the assertion target `actual == 0.5` while documenting the post-fix invariant via its docstring.
- The dp.py module docstring documents the second-half pistol Phase-2 follow-up (a NEW Phase-1 simplification; not in the original A1..A8 RESEARCH.md log) with explicit reference to REQ-round-event-data-pipeline.
- BO3State remains `frozen=True, slots=True` and hashable; the new tuple-rebuild produces a `tuple[Optional[bool], ...]` of the same length as `state.pistol_winner_a`.
- CR-01..CR-04 invariants from 01-06 all still hold: `_p_reach_map_cached` clinch-first ordering, `_p_map_decisive` BO3 middle-map formula, `_compute_vega` OT/terminal short-circuits, `LiveTheoEngine.__call__` try/finally cleanup. The 100-call memory-leak test continues to pass.
- REQ-pistol-anti-eco-modeling moves from BLOCKED → SATISFIED after this plan; the verifier replay of the 01-VERIFICATION.md spot-check rows 13/14/15 (currently FAIL) all transition to PASS.
</success_criteria>

<output>
After completion, create `.planning/phases/01-core-pricing-engine/01-07-pistol-anti-eco-dp-propagation-SUMMARY.md` documenting:
- Which gaps closed (CR-05, WR-06) with the line ranges modified in `src/pricing/dp.py` and `src/pricing/live_theo.py`.
- New tests added (test names + count): `test_dp_anti_eco_uses_gun_win_rate_after_round_1_branch`, `test_dp_anti_eco_returns_complement_after_b_wins_round_1`, `test_dp_advance_round_does_not_override_already_settled_pistol` (test_dp.py); `test_within_map_anti_eco_uses_gun_win_rate_after_round_1_branch`, `test_live_theo_asymmetric_pistols_match_unset_pistols_after_dp_propagation` (test_live_theo.py).
- Re-scoped test renamed: `test_anti_eco_with_none_pistol_winner_returns_defensive_05_for_malformed_external_input` (test_round_types.py).
- Test count delta (147 → 151+).
- Confirmation that mypy --strict, ruff, surface contract, `__all__`, and CR-01..CR-04 invariants are unchanged.
- Note for the Phase 4 planner: the pistol+anti-eco model is now structurally active in the DP forward-pass for the natural pre-match call site. `VEGA_DIRECTIONAL_THRESHOLD = 0.04` and `KILL_SWITCH_DEVIATION_C = 20¢` operate on accurate theo_series values; the previously-systematic 9.25pp bias at TeamA=0.55/TeamB=0.45 is closed.
- Note for the Phase 2 planner: the second-half pistol limitation (rounds 14/15 dispatch on `pistol_winner_a[map_idx]` which is the FIRST-half pistol winner) is documented as a Phase-2 follow-up in the `dp.py` module docstring (NEW Phase-1 simplification; not in the original A1..A8 RESEARCH.md Assumptions Log — track separately at the roadmap level if Phase 4 calibration surfaces it as a need). Phase 2 will extend the data shape to `tuple[Optional[tuple[bool, bool]], ...]` per (map, half) and update the `round_types.py` dispatch to consult the appropriate half. NO data-shape change in Phase 1.
- Out-of-scope items still deferred: WR-07 (`_within_map_p_a_wins` docstring's `functools.lru_cache` claim — explicitly preserved per checker fix I-08; the docstring still says lru_cache while the implementation uses dict), WR-08 (per-`m` re-registration perf), IN-05..IN-07, WR-01..WR-05 + IN-01..IN-04 from original review.
</output>
