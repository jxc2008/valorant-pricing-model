---
phase: 01-core-pricing-engine
plan: 03
subsystem: pricing
tags: [pricing, round-types, pistol, anti-eco, gun-win-rate, dispatch]
requires:
  - DEC-003-bradley-terry-blend
  - DEC-011-pistol-anti-eco-modeling
  - DEC-016-no-magic-numbers
  - CON-mypy-strict-pricing
  - CON-no-magic-numbers
  - REQ-pistol-anti-eco-modeling
  - 01-01-constants-and-blend  # blend.round_p, GUN_WIN_RATE
provides:
  - src.pricing.round_types.round_p_for_round
  - src.pricing.round_types.HalfRates  # Protocol
  - src.pricing.round_types._team_a_side
  - src.pricing.round_types._team_b_side
affects:
  - 01-05-live-theo  # consumes round_p_for_round via _build_round_p_fn closure
  - 01-02-bo3-dp-engine  # injection point: round_p_fn passed into series_value
tech-stack:
  added: []
  patterns:
    - "TYPE_CHECKING guard for forward references to avoid runtime circular imports"
    - "Protocol-based duck typing for HalfRates seam (concrete impl deferred to 01-05)"
key-files:
  created:
    - src/pricing/round_types.py
    - tests/pricing/test_round_types.py
  modified: []
decisions:
  - DEC-003 honored: round_p_for_round consumes blend.round_p, never the arithmetic-mean form
  - DEC-011 implemented: rounds {1, 2, 3, 13, 14, 15} dispatched explicitly per round type
  - A6 (Phase 1 simplification): rounds 3 / 15 use the same GUN_WIN_RATE model as rounds 2 / 14; Phase 2 calibration may differentiate
  - A8 (Phase 1 simplification): pistol rounds {1, 13} fall back to half_rates blend; per-team pistol rates deferred to Phase 2
  - Architectural seam preserved: round_types.py imports dp.BO3State and live_theo.MatchState only under TYPE_CHECKING, so dp.py stays domain-pure
  - Rule 3 deviation: tests use a local _FakeBO3State dataclass instead of importing the real src.pricing.dp.BO3State, since dp.py is owned by the parallel 01-02 worktree
metrics:
  duration_min: 16
  completed: 2026-04-28
---

# Phase 01 Plan 03: Round-type dispatch (pistol / anti-eco / gunround) Summary

**One-liner:** Round-number-aware probability dispatcher (`round_p_for_round`) routing pistol rounds {1, 13} → half-rates Bradley-Terry blend, anti-eco rounds {2, 3, 14, 15} → `GUN_WIN_RATE` (0.822) or complement based on `pistol_winner_a[map_idx]`, and gunrounds {4-12, 16-24} → half-rates blend; closes audit-engine bug PRD §12.2 #5 (constant `p1` / `p2` per half).

## Dispatch table (as shipped)

| Round numbers | Path | Returns |
|---|---|---|
| 1, 13 | Pistol — Phase 1 fallback to half-rates blend (A8) | `blend.round_p(half_rates.team(team_a, map, a_side), half_rates.team(team_b, map, b_side))` |
| 2, 3, 14, 15 (A won pistol) | Anti-eco | `GUN_WIN_RATE` (= 0.822) exactly |
| 2, 3, 14, 15 (B won pistol) | Anti-eco | `1 - GUN_WIN_RATE` (= 0.178) exactly |
| 2, 3, 14, 15 (`pistol_winner_a[map_idx] is None`) | Defensive fallthrough | `0.5` exactly |
| 4-12, 16-24 | Gunround baseline | `blend.round_p(half_rates.team(team_a, map, a_side), half_rates.team(team_b, map, b_side))` |

Side derivation (per `reference/theo_engine.py:158`, salvaged with attribution):
- `_team_a_side('a_atk') == 'atk'`, `_team_a_side('a_def') == 'def'`
- `_team_b_side('a_atk') == 'def'`, `_team_b_side('a_def') == 'atk'`

## Phase 1 simplifications taken

- **A6 — rounds 3 / 15 use rounds-2 / 14 GUN_WIN_RATE.** Roadmap §1.3 notes empirical anti-eco rate is ~60% on round 3 vs ~75% on round 2; Phase 2 calibration (REQ-round-event-data-pipeline) may differentiate. Phase 1 ships the structurally-correct dispatch; the rate value can be swapped in without touching call sites.
- **A8 — pistol rounds {1, 13} fall back to half-rates blend.** Phase 2 will calibrate per-team pistol-only win rates from `match_round_data` and swap them in via the same call shape (HalfRates Protocol → swap concrete impl).

Both simplifications are documented inline in the module docstring with explicit "Phase 1 simplification" headers so the deferral is discoverable when Phase 2 lands.

## Public surface

```python
class HalfRates(Protocol):
    def team(self, team: str, map_name: str, side: str) -> float: ...
    def team_entry(self, team: str, map_name: str, side: str) -> dict[str, Any] | None: ...

def round_p_for_round(
    state: BO3State,            # type-only import
    match_state: MatchState,    # type-only import
    half_rates: HalfRates,
) -> float: ...

def _team_a_side(side_orient: str) -> str: ...
def _team_b_side(side_orient: str) -> str: ...
```

## Architectural seam (DEC-010 / CRule 1)

`round_p_for_round` IS the function body that `live_theo.py` (01-05) wraps in a closure and passes to `dp.series_value` (01-02) via the `round_p_fn` injection point. The seam preserves three properties:

1. **`dp.py` stays domain-pure** — it never imports `round_types.py`; instead it accepts a `RoundPFn` Protocol via constructor parameter.
2. **`round_types.py` never imports `dp.py` at runtime** — `BO3State` is referenced via `if TYPE_CHECKING:` only. Verified at the source level: `grep -E "^from src\.pricing\.(dp|live_theo)" src/pricing/round_types.py` returns no matches.
3. **`round_types.py` never imports `live_theo.py` at runtime** — `MatchState` is referenced via `if TYPE_CHECKING:` only. Verified by `test_source_uses_type_checking_guard_for_circular_imports`.

This means the three modules can be developed in parallel worktrees without circular-import pitfalls.

## Tests shipped (20 total, 5 sections)

| # | Section | Test | Notes |
|---|---|---|---|
| 1 | 0. Protocol | `test_halfrates_protocol_runtime_check` | Sanity duck-types `_FakeHalfRates` against the `HalfRates` Protocol |
| 2-3 | 1. Side helpers | `test_side_derivation[a_atk]`, `[a_def]` | parametrize |
| 4 | 2. Pistol rounds | `test_round_1_pistol_uses_half_rates_blend` | atk-side wiring |
| 5 | 2. Pistol rounds | `test_round_13_pistol_uses_flipped_side` | def-side wiring (post-half flip) |
| 6-9 | 3. Anti-eco | `test_anti_eco_returns_gun_win_rate_when_a_won_pistol[round 2/3/14/15]` | parametrize × 4 |
| 10-13 | 3. Anti-eco | `test_anti_eco_returns_complement_when_b_won_pistol[round 2/3/14/15]` | parametrize × 4 |
| 14 | 3. Anti-eco | `test_anti_eco_with_none_pistol_winner_returns_defensive_05` | Defensive fallthrough |
| 15-18 | 4. Gunround | `test_gunround_uses_half_rates_blend[round 4/12/16/24]` | parametrize × 4, includes side flip at round 16 |
| 19 | 5. Source regression | `test_source_does_not_contain_arithmetic_mean_blend` | DEC-003 lock |
| 20 | 5. Source regression | `test_source_uses_type_checking_guard_for_circular_imports` | RESEARCH §Architectural Map lock |

Test count exceeds the plan's required floor of 14.

## Verification

```text
$ uv run mypy --strict src/pricing/round_types.py
Success: no issues found in 1 source file

$ uv run pytest tests/pricing/test_round_types.py -x
============================= 20 passed in 0.93s =============================

$ uv run ruff check src/pricing/round_types.py tests/pricing/test_round_types.py
All checks passed!

$ uv run pytest -x  # full suite — no regressions on 01-01 / Phase 0
============================= 71 passed in 1.52s ==============================
```

Manual sanity check (from `<verification>` block in plan):
```text
round 2 (A won pistol): 0.822
```
Returned exactly `GUN_WIN_RATE`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Used `_FakeBO3State` dataclass in tests instead of `from src.pricing.dp import BO3State`**
- **Found during:** Task 1 (test authoring)
- **Issue:** The plan's test skeleton imports `BO3State` from `src.pricing.dp`. Plan 01-02 (which ships `dp.py`) is being executed in a sibling parallel worktree. Creating a `dp.py` here would cause a merge conflict when both worktrees land. Without a stub, `pytest` fails at import: `ModuleNotFoundError: No module named 'src.pricing.dp'`.
- **Fix:** Tests now define a local `_FakeBO3State` frozen dataclass with the exact field shape documented in `01-02-bo3-dp-engine-PLAN.md` lines 162-170 / 265-282. `round_types.round_p_for_round` is duck-typed at runtime (`BO3State` only appears under `if TYPE_CHECKING:`), so this fake is functionally identical to the real type for these tests. After both worktrees merge, the real `src.pricing.dp.BO3State` is exercised indirectly via 01-05's `live_theo` integration tests.
- **Files modified:** `tests/pricing/test_round_types.py` (uses `_FakeBO3State`); module docstring documents the rationale.
- **Commit:** `c65d6d0`

**2. [Rule 1 - Lint compliance] Replaced `Optional[X]` with `X | None` and removed redundant string annotations**
- **Found during:** Task 1 (`uv run ruff check`)
- **Issue:** Project `pyproject.toml` enables `pyupgrade` (`UP`) lint rules under `[tool.ruff.lint]`. `Optional[dict[str, Any]]` triggers `UP045`; quoted forward-ref annotations (`state: "BO3State"`) trigger `UP037` because `from __future__ import annotations` is already in effect. The plan skeleton uses both old forms.
- **Fix:** Switched to `dict[str, Any] | None` and unquoted forward references (the `__future__` import lazily evaluates them). No semantic change.
- **Files modified:** `src/pricing/round_types.py`, `tests/pricing/test_round_types.py`
- **Commit:** `c65d6d0`

**3. [Rule 1 - Lint compliance] Removed blank-line block between import group and first divider**
- **Found during:** Task 1 (`uv run ruff check --fix`)
- **Issue:** `I001` triggered on the test file's import block — ruff's isort sorter rearranged blank lines around the import block.
- **Fix:** Auto-applied via `ruff check --fix`.
- **Files modified:** `tests/pricing/test_round_types.py`
- **Commit:** `c65d6d0`

No architectural deviations (no Rule 4 escalations).

## Source-level invariants verified

- `round_types.py` does NOT contain the arithmetic-mean blend form (`(a + (1-b)) / 2` etc.) — DEC-003 / CRule 3 regression-locked by `test_source_does_not_contain_arithmetic_mean_blend`.
- `round_types.py` does NOT runtime-import `src.pricing.dp` or `src.pricing.live_theo` — verified by `grep -E "^from src\.pricing\.(dp|live_theo)" src/pricing/round_types.py` returning empty, and by `test_source_uses_type_checking_guard_for_circular_imports`.
- All thresholds come from `src.config.constants` (only `GUN_WIN_RATE` is consumed; no magic numbers in business logic) — DEC-016 / CRule 12 honored.

## Threat-model coverage

All five threats from the plan's STRIDE register are mitigated as designed:

| Threat ID | Mitigation | Test |
|---|---|---|
| T-01-03-01 (regression to arithmetic mean) | Source check + `blend.round_p` is the only blend call site | `test_source_does_not_contain_arithmetic_mean_blend` |
| T-01-03-02 (None pistol → wrong p) | Defensive `if pistol_won_by_a is None: return 0.5` | `test_anti_eco_with_none_pistol_winner_returns_defensive_05` |
| T-01-03-03 (atk/def confusion) | `_team_a_side` / `_team_b_side` helpers + parametrize | `test_side_derivation`, `test_round_13_pistol_uses_flipped_side`, `test_gunround_uses_half_rates_blend[16/24]` |
| T-01-03-04 (round-number off-by-one) | Explicit `+ 1` with comment, tests cover round 1, 13, 24 | All round-N tests |
| T-01-03-05 (circular import) | TYPE_CHECKING guard | `test_source_uses_type_checking_guard_for_circular_imports` |

No new threat surface introduced beyond the documented Trust Boundary (caller supplies BO3State / MatchState / HalfRates).

## Authentication gates

None — purely offline math layer.

## Commits

| # | Hash | Type | Summary |
|---|---|---|---|
| 1 | `c65d6d0` | feat | feat(01-03): implement pistol/anti-eco round-type dispatch + tests |

## Cross-plan handoffs

- **To 01-05 (live_theo):** Import `from src.pricing.round_types import round_p_for_round, HalfRates`. Wrap in a closure inside `_build_round_p_fn(match_state, half_rates)`; pass the closure to `dp.series_value` via the `RoundPFn` Protocol. Concrete `HalfRates` implementation reads `data/half_win_rates.json` and is owned by `live_theo.py`.
- **To 01-02 (dp):** No direct dependency. `round_types.py` already imports `BO3State` under `TYPE_CHECKING`, which resolves correctly after 01-02's worktree merges.
- **To Phase 2:** Per-team pistol-only rates and per-round-3/15 anti-eco rates can be calibrated and dropped in without changing the dispatch surface — only the values returned by the underlying `HalfRates` source change. The structural dispatch is locked.

## Self-Check: PASSED

- `src/pricing/round_types.py` — FOUND
- `tests/pricing/test_round_types.py` — FOUND
- `c65d6d0` (feat: pistol/anti-eco dispatch) — FOUND in `git log`
- All 20 round_types tests pass; 71 total tests pass (no regression on 01-01 / Phase 0)
- `mypy --strict` clean on `src/pricing/round_types.py`
- `ruff check` clean on both new files
