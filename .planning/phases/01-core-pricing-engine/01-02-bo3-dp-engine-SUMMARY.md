---
phase: 01-core-pricing-engine
plan: 02
subsystem: pricing

tags: [dp, bo3, ot-hardstop, lru-cache, hypothesis, mypy-strict, regression-locks]

# Dependency graph
requires:
  - phase: 00-foundation
    provides: src/config/constants.py (REGULATION_HALF=12, WIN_THRESHOLD=13), src/pricing/ package, pytest+hypothesis+mypy+ruff toolchain
  - phase: 01-core-pricing-engine
    plan: 01
    provides: BT_BLEND_EPSILON / CONVICTION_CLIP_* baseline constants; tests/pricing/ test package marker; ruff+mypy patterns for src/pricing/
provides:
  - "src/pricing/dp.py — generalized BO3 DP `series_value(state, round_p_fn) -> float`, replacing audit `_markov_map_win`"
  - "BO3State frozen+slots dataclass (8 fields) — DP cache key distinct from MatchState (Pitfall 5)"
  - "RoundPFn Protocol — `__call__(state) -> float` + `next_side_orient_for(map_idx) -> str` (Blocker #3 fix surface)"
  - "_advance_round / _advance_to_next_map state-advance helpers (within-map side flip at total==REGULATION_HALF; next-map side from explicit parameter)"
  - "OT coinflip leaf: `_ot_coinflip_leaf` collapses entire OT sub-DP into 50/50 over next-map series-value recursions (DEC-009 / D-05)"
  - "Callable cache-key indirection: `_ROUND_P_FNS: list[RoundPFn]` registry + `_register_round_p_fn(fn) -> int` (RESEARCH §9)"
  - "lru_cache(maxsize=None) on `_series_value_cached(BO3State, int)` — in-process memoization, ~hundreds of hits per root call"
  - "12-test property + regression suite for the DP module (2 hypothesis property tests + asymmetric OT leaf + side-orient spy + 4 source-grep regression locks for PRD §12.2 #3, #5, #6)"
affects: [01-03-round-types, 01-04-round-conclusion, 01-05-live-theo, 04-quoting, 05-validation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Protocol + module-level registry indirection for non-hashable Callable lru_cache keys (RESEARCH §9)"
    - "Frozen+slots dataclass cache key with hashable atoms only (int/str/tuple); live-state fields explicitly excluded (Pitfall 5)"
    - "Source-grep regression tests with AST-based docstring stripping — module/function docstrings can legitimately mention forbidden bug patterns; AST-level stripping prevents false positives"
    - "AST-walk function-body extraction for source-grep regression on multi-line signatures (replaces line-pattern heuristic that breaks on `def fn(\\n    ...\\n) -> T:`)"
    - "Per-line `# noqa` for plan-mandated forms that conflict with default ruff rules (lru_cache(maxsize=None) vs UP033, Optional[bool] vs UP045 — both required by acceptance greps)"
    - "Hypothesis property tests over [0.0, 1.0] (range invariant) and [0.05, 0.95] (numerical-tolerance range for closed-form composition)"
    - "Symmetric-input closed-form check composes through DP-derived per-map prob — `_bo3_series_prob` consumes per-MAP prob, but DP consumes per-ROUND prob, so the test computes per-map prob via `series_value(decider_state, fn)` first (Rule 1 fix vs plan's literal phrasing)"

key-files:
  created:
    - src/pricing/dp.py
    - tests/pricing/test_dp.py
  modified: []

key-decisions:
  - "AST-based source-grep helpers: `_executable_dp_source` strips both `#` comments AND module/function/class docstrings via `ast.parse` -> walk -> `ast.unparse`. Required because the module docstring legitimately documents the audit bugs being regression-locked."
  - "Test 2 (closed-form symmetric) rewritten to compose through DP-derived per-map prob: the plan's literal `series_value(root, lambda _s: p) ≈ _bo3_series_prob(p)` is mathematically wrong (the DP consumes per-round prob, the closed form consumes per-map prob). Fix: derive per-map prob from `series_value(decider_state, fn)` first, then compare to `_bo3_series_prob(per_map_prob)`. Closed-form fixture and IID symmetry invariant still verified."
  - "`@functools.lru_cache(maxsize=None)` retained over ruff's UP033 suggestion (`@functools.cache`) because the plan's acceptance-grep requires the explicit form; suppressed inline with `# noqa: UP033`."
  - "`tuple[Optional[bool], ...]` retained over ruff's UP045 suggestion (`bool | None`) because the plan's interface spec dictates the form; suppressed inline with `# noqa: UP045`."
  - "Within-map side flip implemented in `_advance_round` at `new_a_round + new_b_round == REGULATION_HALF` (i.e., right after round 12 completes), not on round 13 dispatch — keeps the side-flip a pure state transition rather than a dispatch concern."

patterns-established:
  - "Phase 1 DP module layout: section dividers (1. BO3State, 2. RoundPFn Protocol, 3. State-advance helpers, 4. Callable cache-key indirection, 5. DP recursion, 6. Public entry) — downstream 01-04 round-conclusion and 01-05 live_theo will mirror this section style."
  - "Spy-based RoundPFn fixtures in tests record `BO3State` arguments observed at `__call__` invocations for behavioral verification of recursion paths (e.g., side-orient threading through OT leaf)."

requirements-completed: [REQ-bo3-dp-engine, REQ-ot-handling]

# Metrics
duration: 25min
completed: 2026-04-28
---

# Phase 01 Plan 02: BO3 DP Engine Summary

**Generalized top-down memoized BO3 DP `series_value(state, round_p_fn) -> float` shipped at `src.pricing.dp`, replacing audit-engine `_markov_map_win` with explicit OT hard-stop at total=24 (recursive coinflip leaf), per-round closure-injected probability (no constant p1/p2 dispatch), and parameter-supplied next-map side orientation (no hardcoded `'a_atk'`). 12 hypothesis-property + source-grep regression tests pass under `mypy --strict`.**

## Performance

- **Duration:** ~25 min
- **Completed:** 2026-04-28
- **Cache reference (canonical 3-map root, p=0.6 constant per-round):** `(hits=673, misses=776, currsize=776)` after one `series_value` call from cold cache — substantial reuse, confirms memoization. Reference for 01-05 D-16 profiling decision (pickle-warm needed only if < 500 ms latency budget breached).

## Files

**Created:**
- `src/pricing/dp.py` (277 lines) — DP module
- `tests/pricing/test_dp.py` (430 lines) — property + regression test suite

**Modified:** none

## Public Surface (as shipped)

### `BO3State` (frozen+slots dataclass)

8 fields, all hashable atoms:

| Field | Type | Semantics |
|---|---|---|
| `map_idx` | `int` | 0-based index into `map_pool` |
| `a_map_score` | `int` | Maps A has won (0/1/terminal-2) |
| `b_map_score` | `int` | Maps B has won (0/1/terminal-2) |
| `a_round` | `int` | Rounds A won in CURRENT map |
| `b_round` | `int` | Rounds B won in CURRENT map |
| `side_orient` | `str` | `"a_atk"` or `"a_def"` — current half's side for A |
| `map_pool` | `tuple[str, ...]` | Frozen tuple of map names; series-constant |
| `pistol_winner_a` | `tuple[Optional[bool], ...]` | Per-map; `None` pre-pistol, `True`/`False` after |

### `RoundPFn` Protocol (Blocker #3 fix)

```python
class RoundPFn(Protocol):
    def __call__(self, state: BO3State) -> float: ...
    def next_side_orient_for(self, map_idx: int) -> str: ...
```

### `_advance_to_next_map(state, a_won, next_side_orient)`

Three required parameters; no default for `next_side_orient`. Body forwards the parameter through to the new BO3State; no hardcoded `'a_atk'` or `'a_def'` literal.

### `series_value(state, round_p_fn) -> float`

Public entry. Registers `round_p_fn` in `_ROUND_P_FNS`, calls cached recursion. Returns float in `[0.0, 1.0]`. NEVER clipped — output clipping to `[CONVICTION_CLIP_LOW, CONVICTION_CLIP_HIGH]` is live_theo's responsibility (01-05).

## DP Terminals (5 cases)

| Condition | Return |
|---|---|
| `state.a_map_score >= 2` | `1.0` (A clinched series) |
| `state.b_map_score >= 2` | `0.0` (B clinched series) |
| `state.a_round >= WIN_THRESHOLD` | recurse `_advance_to_next_map(state, a_won=True, next_side_orient=fn.next_side_orient_for(map_idx+1))` |
| `state.b_round >= WIN_THRESHOLD` | recurse `_advance_to_next_map(state, a_won=False, next_side_orient=fn.next_side_orient_for(map_idx+1))` |
| `state.a_round + state.b_round == REGULATION_HALF * 2` | `_ot_coinflip_leaf(state, round_p_id)` |

## OT Leaf Math (DEC-009 / D-05)

```
_ot_coinflip_leaf(state, round_p_id):
    next_side = _ROUND_P_FNS[round_p_id].next_side_orient_for(state.map_idx + 1)
    return (
        0.5 * series_value(_advance_to_next_map(state, a_won=True,  next_side_orient=next_side))
      + 0.5 * series_value(_advance_to_next_map(state, a_won=False, next_side_orient=next_side))
    )
```

The leaf RECURSES into next-map series-value (not a flat constant), so asymmetric leaf semantics work: at A=1-0 in maps + 12-12 in regulation, the leaf returns `0.5 * 1.0 + 0.5 * P(A wins decider at 0-0) = 0.5 + 0.5 * 0.5 = 0.75` under constant per-round p=0.5. Verified by `test_dp_ot_hardstop_recurses_into_next_map_for_asymmetric_state`.

The next-map starting side is fetched from the closure's `next_side_orient_for(...)` accessor — NO hardcoded `'a_atk'` literal anywhere in the module body. Live wiring verified by `test_dp_ot_path_consults_round_p_fn_next_side_orient` (spy-based).

## Callable Cache-Key Indirection (RESEARCH §9)

```python
_ROUND_P_FNS: list[RoundPFn] = []  # module-level registry

def _register_round_p_fn(fn: RoundPFn) -> int:
    _ROUND_P_FNS.append(fn)
    return len(_ROUND_P_FNS) - 1

@functools.lru_cache(maxsize=None)  # noqa: UP033 — plan acceptance grep
def _series_value_cached(state: BO3State, round_p_id: int) -> float:
    fn = _ROUND_P_FNS[round_p_id]
    ...
```

`lru_cache` requires hashable keys; `Callable` is not stably hashable, so each `series_value` call appends the closure and keys the cache on the resulting `int` id. T-01-02-02 (registry growth) accepted: ~50-100 calls/match → bounded for any realistic workload.

## Test Suite (12 tests, all passing)

| # | Test | Type | Assertion |
|---|---|---|---|
| 1 | `test_dp_value_in_unit_interval` | hypothesis (50 ex) | DP value ∈ [0, 1] for any p ∈ [0.0, 1.0] |
| 2 | `test_dp_symmetric_input_matches_closed_form` | hypothesis (50 ex) | `series_value(root, fn) == _bo3_series_prob(per_map_prob)` where `per_map_prob = series_value(decider_state, fn)` (composes through DP-derived per-map prob to match closed-form's per-map argument) |
| 3 | `test_dp_ot_hardstop_returns_coinflip_leaf_symmetric` | unit | DP at 12-12 + p=0.5 + 0-0 maps == 0.5 |
| 4 | `test_dp_ot_hardstop_recurses_into_next_map_for_asymmetric_state` | unit | DP at 12-12 + 1-0 maps + p=0.5 == 0.75 (proves leaf recurses, not flat) |
| 5 | `test_dp_ot_path_consults_round_p_fn_next_side_orient` | unit (spy) | `next_side_orient_for(1)` value flows into next-map root state's `side_orient` field |
| 6 | `test_dp_terminal_a_clinched_returns_1` | unit | a_map_score=2 → 1.0 |
| 7 | `test_dp_terminal_b_clinched_returns_0` | unit | b_map_score=2 → 0.0 |
| 8 | `test_dp_lru_cache_records_hits_on_repeat_call` | unit | `_series_value_cached.cache_info().hits > 0` after one root call |
| 9 | `test_dp_source_does_not_loop_past_24` | regression | source has no `range(26)` or `range(WIN_THRESHOLD * 2)` (PRD §12.2 #3) |
| 10 | `test_dp_source_uses_explicit_ot_hardstop_constant` | regression | source contains `REGULATION_HALF * 2` (no inline `24`) |
| 11 | `test_dp_source_does_not_use_constant_p1_p2_dispatch` | regression | source has no `p = p1` / `p = p2` (PRD §12.2 #5) |
| 12 | `test_dp_advance_to_next_map_takes_explicit_next_side_orient` | regression (AST) | `_advance_to_next_map` signature has `next_side_orient: str`; body has no `side_orient="a_atk"` etc literal; body forwards `side_orient=next_side_orient` (PRD §12.2 #6 / Blocker #3) |

## Threat Mitigation Confirmation (from plan threat_model)

| Threat ID | Disposition | Mitigation Status |
|---|---|---|
| T-01-02-01 — NaN propagation | mitigate | Range property test covers all p ∈ [0, 1]; `assert not math.isnan(val)` explicit |
| T-01-02-02 — registry unbounded growth | accept | Acknowledged; ~100 entries/match is fine |
| T-01-02-03 — silent OT past 24 | mitigate | `test_dp_source_does_not_loop_past_24` + asymmetric leaf test |
| T-01-02-04 — constant p1/p2 dispatch | mitigate | `test_dp_source_does_not_use_constant_p1_p2_dispatch` |
| T-01-02-05 — BO3State cache collision via mutable field | mitigate | `frozen=True, slots=True`; tuples not lists; mypy --strict blocks reassignment |
| T-01-02-06 — hardcoded next-map side regression | mitigate | `test_dp_advance_to_next_map_takes_explicit_next_side_orient` (AST) + `test_dp_ot_path_consults_round_p_fn_next_side_orient` (live spy) |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test 2 closed-form comparison was mathematically wrong**
- **Found during:** Task 1 verification (`uv run pytest tests/pricing/test_dp.py -x`)
- **Issue:** Plan specified `series_value(root, lambda _s: p) ≈ _bo3_series_prob(p)`, but `_bo3_series_prob` consumes per-MAP win probability, while the DP consumes per-ROUND win probability. At p=0.75 per round, the DP returned 0.9999 vs the closed form's 0.84375. The two are equal only at the degenerate point p=0.5.
- **Fix:** Rewrote `test_dp_symmetric_input_matches_closed_form` to compose through DP-derived per-map prob: compute `per_map_prob = series_value(decider_state_at_1-1_in_maps, fn)`, then assert `series_value(root, fn) ≈ _bo3_series_prob(per_map_prob)`. Closed-form fixture (`_bo3_series_prob`) and IID symmetry invariant are still verified, just with the correct argument.
- **Files modified:** tests/pricing/test_dp.py
- **Commit:** a7cc99f

**2. [Rule 1 - Bug] `_executable_dp_source` helper didn't strip docstrings, causing `range(26)` mention in module docstring to false-positive**
- **Found during:** Task 1 verification (`test_dp_source_does_not_loop_past_24` failed)
- **Issue:** The plan-spec helper stripped only `#` comments. The DP module docstring legitimately documents the bug being regression-locked by referencing `range(26)`. The grep tripped on the docstring instead of executable code.
- **Fix:** Rewrote `_executable_dp_source` to use `ast.parse` → walk → blank-out docstring `Expr/Constant(str)` first-statements on Module/FunctionDef/ClassDef bodies → `ast.unparse` → tokenize-strip remaining `#` comments. Comments AND docstrings now both excluded from the grep target.
- **Files modified:** tests/pricing/test_dp.py
- **Commit:** a7cc99f

**3. [Rule 1 - Bug] `test_dp_advance_to_next_map_takes_explicit_next_side_orient` body extraction broke on multi-line signature**
- **Found during:** Task 1 verification
- **Issue:** Plan-spec test extracted function body via line-pattern matching (`break` when next non-indented line appears). The signature `def _advance_to_next_map(\n    state: BO3State,\n    a_won: bool,\n    next_side_orient: str,\n) -> BO3State:` triggers the break on the `) -> BO3State:` line because `)` is not whitespace, so the body collection terminated at the closing paren of the signature, missing the actual function body.
- **Fix:** Rewrote the body extraction to use `ast.walk` → find `FunctionDef` with `name == "_advance_to_next_map"` → drop the docstring → `ast.unparse` the remaining body. Robust against multi-line signatures.
- **Files modified:** tests/pricing/test_dp.py
- **Commit:** a7cc99f

**4. [Rule 3 - Lint] Per-line `# noqa` for two ruff rules conflicting with plan-mandated forms**
- **Found during:** Task 1 verification (`uv run ruff check src/pricing/dp.py`)
- **Issue:** Ruff UP033 wants `@functools.cache` instead of `@functools.lru_cache(maxsize=None)`; UP045 wants `bool | None` instead of `Optional[bool]`. Both forms are required verbatim by the plan's acceptance-grep checks (`grep -q "@functools.lru_cache(maxsize=None)" src/pricing/dp.py` and the `Optional` import / RESEARCH §1 spec).
- **Fix:** Added inline `# noqa: UP033` and `# noqa: UP045` comments with one-line justifications. Did not disable the rules globally.
- **Files modified:** src/pricing/dp.py
- **Commit:** a7cc99f

### Architectural changes

None.

### Authentication gates

None — no external services / credentials required at this layer.

## Verification Results

```
$ uv run mypy --strict src/pricing/dp.py
Success: no issues found in 1 source file

$ uv run ruff check src/pricing/dp.py tests/pricing/test_dp.py
All checks passed!

$ uv run pytest tests/
============================= 63 passed in 1.90s ==============================
```

12 new tests + 51 prior tests (test_smoke, test_main, test_constants, test_blend) = 63 pass. No regressions.

## Notes for Downstream Plans

- **01-03 (round_types):** Will build on `BO3State` to dispatch round-type → probability. The `pistol_winner_a` field in BO3State is already in place for rounds {2, 3, 14, 15} dispatch.
- **01-04 (round_conclusion):** Will not consume `BO3State` directly — it consumes mid-round live state. The DP doesn't model mid-round events; round_conclusion feeds into the round_p_fn closure that 01-05 builds.
- **01-05 (live_theo):** Will implement the canonical `RoundPFn` Protocol implementer in `_build_round_p_fn`. It MUST bind `next_side_orient_for(map_idx)` to `MatchState.map_side_orients[map_idx]` with bounds-checking for series-clinch states. The DP relies on this (test 5 verifies the wiring).
- **Cache hygiene between matches:** `_series_value_cached.cache_clear()` is exposed for caller-side resets; the registry `_ROUND_P_FNS` is append-only (T-01-02-02 accepted). Phase 5 may add explicit clear-on-match-end hooks.

## Self-Check: PASSED

- [x] `src/pricing/dp.py` exists
- [x] `tests/pricing/test_dp.py` exists
- [x] Commit `a7cc99f` exists in git log
- [x] All 12 new tests pass; no regressions in 51 existing tests
- [x] mypy --strict clean
- [x] ruff check clean (with two documented per-line noqa for plan-mandated forms)
- [x] Plan acceptance greps verified (13 grep counts all > 0)
- [x] No `'a_atk'` / `'a_def'` literal inside `_advance_to_next_map` body (Blocker #3 fix live)
- [x] Source contains `REGULATION_HALF * 2` (no inline 24)
