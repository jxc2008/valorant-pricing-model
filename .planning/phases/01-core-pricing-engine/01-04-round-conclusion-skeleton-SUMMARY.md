---
phase: 01-core-pricing-engine
plan: 04
subsystem: pricing
tags: [round-conclusion, hierarchical-lookup, bayesian-shrinkage, protocol, skeleton]
dependency_graph:
  requires:
    - 00-02 (src/config/constants.py — SHRINK_PRIOR=15.0)
    - 01-01 (tests/pricing/__init__.py package marker)
  provides:
    - src.pricing.round_conclusion.RoundConclusionLookup (5-tier fallback chain)
    - src.pricing.round_conclusion._Cell (Bayesian shrinkage helper)
    - src.pricing.round_conclusion.RoundConclusionFn (Protocol callable shape)
    - src.pricing.round_conclusion._PHASE_1_FLAT_CELL_VALUE (defensive leaf = 0.5)
  affects:
    - 01-05 (live_theo will type round_conclusion arg as RoundConclusionFn)
    - Phase 2 REQ-round-event-data-pipeline (will populate cells_* dicts; public surface unchanged)
tech_stack:
  added: []
  patterns:
    - frozen=True+slots dataclass with mutable dict fields via field(default_factory=...)
    - Protocol callable shape for dependency-inversion type contracts
    - source-grep regression test to lock CRule 12 (no inline magic numbers)
key_files:
  created:
    - src/pricing/round_conclusion.py
    - tests/pricing/test_round_conclusion.py
  modified: []
decisions:
  - DEC-007 / D-06 / D-07 / D-09 honored verbatim — no deviations.
metrics:
  duration_minutes: 8
  completed_date: 2026-04-28
  tasks_completed: 1
  tests_added: 13
  hypothesis_property_tests: 2
requirements_completed:
  - REQ-round-conclusion-lookup
---

# Phase 01 Plan 04: Round-Conclusion Skeleton Summary

**One-liner:** Hierarchical 5-tier fallback-chain lookup skeleton with Bayesian-shrinkage `_Cell` and `RoundConclusionFn` Protocol shipped — `lookup()` returns flat `_PHASE_1_FLAT_CELL_VALUE = 0.5` per D-06; Phase 2 calibrates without changing the interface.

---

## What was built

### Phase 1 invariant (D-06)

`RoundConclusionLookup.lookup(numerical_diff, bomb_planted, side, econ_bucket, map_name)` returns **EXACTLY 0.5** for all inputs in Phase 1. Locked by 100-example hypothesis test `test_lookup_always_returns_flat_05_in_phase_1` over the cartesian product (`numerical_diff ∈ [-4..4] × bomb ∈ {T,F} × side ∈ {atk, def} × econ ∈ {full, semi-buy, semi-eco, eco} × map ∈ 7-map pool`).

### 5-tier fallback chain field layout (D-07)

Shipped as frozen+slots dataclass fields on `RoundConclusionLookup`, all populated with `field(default_factory=...)` so each instance gets fresh dicts:

| Tier | Field            | Key shape                                            | Default |
|------|------------------|------------------------------------------------------|---------|
| 1    | `cells_full`     | `(numerical_diff, bomb, side, econ_bucket, map)`     | `{}`    |
| 2    | `cells_no_econ`  | `(numerical_diff, bomb, side, map)`                  | `{}`    |
| 3    | `cells_no_map`   | `(numerical_diff, bomb, side)`                       | `{}`    |
| 4    | `cells_minimal`  | `(numerical_diff, bomb)`                             | `{}`    |
| 5    | `side_baseline`  | `str` -> `float`                                     | `{"atk": 0.5, "def": 0.5}` |
| 6    | `_PHASE_1_FLAT_CELL_VALUE` (module-level Final) | n/a — defensive ultimate leaf | `0.5` |

Phase 2's `lookup` rewrite walks this chain with the parent-cell shrinkage applied at each match; the public signature does not change.

### Bayesian shrinkage formula (D-09 / DEC-013)

Salvaged verbatim from `reference/theo_engine.py:100` and shipped as `_Cell.shrunk()`:

```python
return (self.n * self.p_hat + SHRINK_PRIOR * self.parent_p) / (
    self.n + SHRINK_PRIOR
)
```

`SHRINK_PRIOR = 15.0` is imported from `src.config.constants` per CRule 12. **No inline `15` / `15.0` literal anywhere in source** — regression-locked by `test_source_uses_shrink_prior_constant_not_inline_literal` which strips comments/docstrings then greps for the formula's bare-literal patterns (`* 15 *`, `+ 15 *`, `+ 15)`, `15.0`).

Boundary behavior (verified):
- `_Cell(n=0, ...).shrunk()` → pure `parent_p` (prior dominates)
- `_Cell(n=1000, p_hat=0.6, parent_p=0.5).shrunk()` ≈ 0.598 (empirical dominates)
- `_Cell(n=10, p_hat=0.6, parent_p=0.5).shrunk()` = 0.54 (deterministic)
- Property test (100 hypothesis examples) — output always in `[0, 1]`, never NaN.

### `RoundConclusionFn` Protocol

```python
class RoundConclusionFn(Protocol):
    def __call__(
        self,
        numerical_diff: int,
        bomb_planted: bool,
        side: str,
        econ_bucket: str,
        map_name: str,
    ) -> float: ...
```

Bound method `RoundConclusionLookup.lookup` satisfies this Protocol structurally (verified at `mypy --strict`); test fakes also satisfy it. `live_theo` (01-05) will type its `round_conclusion` parameter as `RoundConclusionFn` so it consumes the interface, not the concrete class.

---

## Tests

**13 tests, all passing.** Two are hypothesis property tests with `max_examples=100`:

| # | Test | Purpose |
|---|------|---------|
| 1 | `test_lookup_always_returns_flat_05_in_phase_1` (hypothesis ×100) | D-06 invariant lock |
| 2 | `test_phase_1_flat_cell_value_is_05` | Module constant correctness |
| 3 | `test_cell_shrunk_matches_audit_engine_formula` | Verbatim formula salvage check (= 0.54) |
| 4 | `test_cell_shrunk_at_zero_n_returns_parent` | Boundary: pure prior at n=0 |
| 5 | `test_cell_shrunk_at_large_n_converges_to_p_hat` | Boundary: empirical dominates |
| 6 | `test_cell_shrunk_in_unit_interval` (hypothesis ×100) | Output ∈ [0, 1], no NaN |
| 7 | `test_source_uses_shrink_prior_constant_not_inline_literal` | CRule 12 regression lock |
| 8 | `test_round_conclusion_fn_protocol_is_satisfied_by_lookup` | Protocol typing contract |
| 9 | `test_round_conclusion_fn_protocol_runtime_callable` | Protocol satisfied by lambdas/fakes |
| 10 | `test_fallback_chain_dict_fields_are_present` | All 5 fields exist with correct defaults |
| 11 | `test_default_factory_fresh_instance_per_lookup` | No mutable-default trap |
| 12 | `test_frozen_blocks_field_reassignment` | `FrozenInstanceError` on reassign |
| 13 | `test_frozen_allows_dict_mutation_for_phase_2_population` | Dict mutation works (Phase 2 readiness) |

### Verification commands (all exit 0)

```bash
uv run mypy --strict src/pricing/round_conclusion.py
uv run pytest tests/pricing/test_round_conclusion.py -x  # 13 passed
uv run ruff check src/pricing/round_conclusion.py tests/pricing/test_round_conclusion.py
uv run pytest                                              # 64 passed (no regressions)
```

### Sanity check output

```
lookup(0, False, atk, full, Lotus): 0.5
lookup(-3, True,  def, eco,  Bind ): 0.5
_Cell(10, 0.6, 0.5).shrunk(): 0.54
_Cell(0, 0.0, 0.5).shrunk(): 0.5
```

Matches expected output from plan §verification verbatim.

---

## Deviations from Plan

**None — plan executed exactly as written.**

Ruff auto-fixed import organization in the test file (`from hypothesis import strategies as st` was split into its own import line per ruff's I rule). This is a stylistic adjustment with no semantic impact; auto-applied via `ruff check --fix`.

---

## Authentication Gates

None encountered.

---

## Commit

| Task | Commit  | Files                                                                                  |
|------|---------|----------------------------------------------------------------------------------------|
| 1    | `eb74fdb` | `src/pricing/round_conclusion.py`, `tests/pricing/test_round_conclusion.py` (new)     |

---

## Phase 1 → Phase 2 seam

Phase 2 (`REQ-round-event-data-pipeline`) populates `cells_full`, `cells_no_econ`, `cells_no_map`, `cells_minimal` from rib.gg / OCR-derived round-event data and rewrites the body of `lookup` to walk the chain. The public surface — `RoundConclusionLookup.lookup` signature and `RoundConclusionFn` Protocol — is unchanged. Path-C compatibility (DEC-017) is locked: Phase 4 quoting can ship without Phase 2 data because the flat-0.5 leaf provides a documented, neutral fallback.

---

## Self-Check: PASSED

- `src/pricing/round_conclusion.py` — FOUND
- `tests/pricing/test_round_conclusion.py` — FOUND
- Commit `eb74fdb` — FOUND in `git log`
- All acceptance criteria greps — PASS (16/16)
- All 10 expected test names — present in test file
- mypy --strict, ruff, pytest — all exit 0
- Full test suite — 64/64 passing (no regressions in pre-existing `tests/test_smoke.py`, `tests/test_main.py`, `tests/config/test_constants.py`, `tests/pricing/test_blend.py`)
