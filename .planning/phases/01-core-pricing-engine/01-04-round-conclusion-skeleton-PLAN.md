---
phase: 01-core-pricing-engine
plan: 04
type: execute
wave: 2
depends_on:
  - 01-01-constants-and-blend
files_modified:
  - src/pricing/round_conclusion.py
  - tests/pricing/test_round_conclusion.py
autonomous: true
requirements:
  - REQ-round-conclusion-lookup
must_haves:
  truths:
    - "Bradley-Terry blend, not arithmetic mean (DEC-003 / CRule 3)"
    - "Conviction clip [0.01, 0.99] uniform (DEC-012 / CRule 6)"
    - "No magic numbers — every threshold in src/config/constants.py (CON-no-magic-numbers / CRule 12)"
    - "mypy --strict on src/pricing/ (CON-mypy-strict-pricing / CRule 11)"
    - "Single canonical entry point: live_theo(state) → TheoOutput (DEC-010 / CRule 1)"
    - "round_conclusion cells return flat 0.5 in Phase 1 — Phase 2 calibrates without changing the interface (D-06/D-07)"
    - "Hierarchical fallback chain order: (num_diff, bomb, side, econ_bucket, map) → side baseline → overall (D-07)"
    - "Bayesian shrinkage uses SHRINK_PRIOR=15.0 — never inline 15 (CRule 12)"
  outputs:
    - "src/pricing/round_conclusion.py exports `class RoundConclusionLookup` (frozen dataclass with 5 fallback-chain dict fields + side_baseline) + `_Cell` (n, p_hat, parent_p, shrunk()) + `class RoundConclusionFn(Protocol)` callable shape (numerical_diff: int, bomb_planted: bool, side: str, econ_bucket: str, map_name: str) -> float for live_theo to type against"
    - "RoundConclusionLookup.lookup(numerical_diff, bomb_planted, side, econ_bucket, map_name) returns _PHASE_1_FLAT_CELL_VALUE = 0.5 for ALL inputs in Phase 1 (D-06)"
    - "Fallback chain dict layout shipped (cells_full → cells_no_econ → cells_no_map → cells_minimal → side_baseline) so Phase 2 can populate without changing the public interface (D-07)"
    - "_Cell.shrunk() implements `(n * p_hat + SHRINK_PRIOR * parent_p) / (n + SHRINK_PRIOR)` — verbatim salvage from reference/theo_engine.py:100 with SHRINK_PRIOR imported from constants (CRule 12)"
    - "_PHASE_1_FLAT_CELL_VALUE = 0.5 is a Final[float] module-level constant (Pattern S1) with Source docstring referencing D-06"
    - "tests/pricing/test_round_conclusion.py: hypothesis test_lookup_always_returns_flat_05_in_phase_1 over (numerical_diff, bomb, side, econ_bucket, map) cartesian product, test_cell_shrunk_matches_audit_engine_formula, test_cell_shrunk_uses_shrink_prior_constant (no inline 15), test_round_conclusion_fn_protocol_shape, test_fallback_chain_dict_fields_present (5 dict fields exist for Phase 2 population)"
    - "`uv run mypy --strict src/pricing/round_conclusion.py` exits 0"
    - "`uv run pytest tests/pricing/test_round_conclusion.py -x` exits 0"
    - "`uv run ruff check src/pricing/round_conclusion.py tests/pricing/test_round_conclusion.py` exits 0"
---

<rationale>
Wave 2 — depends on 01-01 for `tests/pricing/__init__.py` package marker. Runs in parallel with 01-02 and 01-03. File-overlap analysis:
- 01-01 modifies src/config/constants.py + src/pricing/blend.py + tests/config/test_constants.py + tests/pricing/__init__.py + tests/pricing/test_blend.py
- 01-04 modifies ONLY src/pricing/round_conclusion.py + tests/pricing/test_round_conclusion.py

Zero source-file overlap with 01-01, BUT 01-04's `tests/pricing/test_round_conclusion.py` requires `tests/pricing/__init__.py` (the package marker created in 01-01 Task 2) for `import tests.pricing.test_round_conclusion` semantics to be deterministic. Per checker Warning W2, the original `wave: 1, depends_on: []` was incorrect: even though pytest can discover test files without an `__init__.py` via rootdir conftest, the dependency is real and must be encoded so the wave structure is correct. Wave 2 ensures 01-01 Task 2 has landed before this plan runs.

**Why a single task:** Module is small (~80 LoC source + ~80 LoC tests). Splitting "skeleton structure" from "tests" would force the executor to write half the contract in plan A and tests in plan B with no executable code in between — anti-TDD and anti-cohesion. Task is sized at ~15-20% context per the planner sizing guide.

**Why this plan exists at all (vs folding into 01-05):** RESEARCH §6 puts round_conclusion at ~120 LoC with its own dataclass family (`_Cell`, `RoundConclusionLookup`, fallback chain) — distinct concern from `live_theo`'s orchestration. Folding into 01-05 would push that plan above the 50% context budget. Splitting also enables Wave 1 parallelism: 01-04 runs WITH 01-01 (zero file overlap) instead of serializing behind the DP/round_types pair.

**Forbidden splits considered:** "Skeleton-only without _Cell" — rejected because Phase 2 needs the shrinkage formula to exist when calibration starts; shipping the structure without `shrunk()` would create a Phase-2 refactor when none is needed. "Lookup tests in 01-05" — rejected because round_conclusion semantics are independent of live_theo orchestration; testing them together couples concerns unnecessarily.

**Files NOT modified here:** `src/pricing/__init__.py` (re-exports land in 01-05); `src/config/constants.py` (no new constants — SHRINK_PRIOR is already in Phase 0).
</rationale>

<objective>
Ship the hierarchical mid-round-conclusion lookup SKELETON in `src/pricing/round_conclusion.py`. The structure (5-level fallback chain + Bayesian-shrinkage cell + public Protocol callable shape for `live_theo` to type against) is built to spec per DEC-007 / D-07, but every cell returns the flat constant `_PHASE_1_FLAT_CELL_VALUE = 0.5` per D-06. Phase 2 will calibrate the cell values without changing the call interface — the SHAPE is what's load-bearing here.

Purpose: Implement REQ-round-conclusion-lookup at the Phase 1 scope: skeleton-only, Path-C compatible (per CONTEXT.md `<specifics>`), no false-signal from un-calibrated cells. Locks the Bayesian-shrinkage formula `(n * p_hat + SHRINK_PRIOR * parent_p) / (n + SHRINK_PRIOR)` salvaged verbatim from `reference/theo_engine.py:100` per D-09 / DEC-013, with `SHRINK_PRIOR=15.0` imported from `src.config.constants` (CRule 12 — no inline 15). Defines the `RoundConclusionFn` Protocol callable so 01-05's `live_theo` can type against `Callable[[int, bool, str, str, str], float]` without importing `round_conclusion` internals.

Output: `RoundConclusionLookup` frozen dataclass with the 5-tier fallback chain field layout, `_Cell` shrinkage helper, `RoundConclusionFn` Protocol, `_PHASE_1_FLAT_CELL_VALUE` Final constant, full hypothesis property test for the 0.5 invariant, plus shrinkage formula and Protocol shape tests.
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
@CLAUDE.md
@prd.md
@roadmap.md
@src/config/constants.py
@reference/theo_engine.py

<interfaces>
<!-- All code skeletons drawn from RESEARCH §6 + PATTERNS lines 267-339 + reference/theo_engine.py:84-102 (verbatim shrinkage salvage). -->

From src/config/constants.py (verified Phase 0 — already shipped, do NOT redefine):
```python
SHRINK_PRIOR: Final[float] = 15.0
"""Bayesian prior weight in rounds for the round-conclusion lookup.

Source: DEC-007 / CLAUDE.md "Domain constants" / reference/theo_engine.py:37.
Re-fit in Phase 5 after 100+ matches of paper-trade data (REQ-calibration-loop).
"""
```

From reference/theo_engine.py:96-100 (Bayesian shrinkage SOURCE — salvage verbatim per D-09):
```python
entry = self._team_rates.get(f'{team}|{map_name}|{side}')
if entry:
    n    = entry.get('total', 0)
    raw  = entry['rate']
    # Shrink toward league average: as n grows the estimate converges to raw
    return (n * raw + SHRINK_PRIOR * prior) / (n + SHRINK_PRIOR)
```

The skeleton (RESEARCH §6 lines 690-738 — ship verbatim with the Phase 1 short-circuit + Phase 2 fallback chain comment hints):
```python
_PHASE_1_FLAT_CELL_VALUE: Final[float] = 0.5

@dataclass(frozen=True, slots=True)
class _Cell:
    """Bayesian-shrinkage cell (Phase 2 will populate)."""
    n: int
    p_hat: float
    parent_p: float

    def shrunk(self) -> float:
        # Source: reference/theo_engine.py:100 — salvage verbatim per D-09.
        return (self.n * self.p_hat + SHRINK_PRIOR * self.parent_p) / (self.n + SHRINK_PRIOR)


@dataclass(frozen=True, slots=True)
class RoundConclusionLookup:
    cells_full:    dict[tuple[int, bool, str, str, str], _Cell] = field(default_factory=dict)
    cells_no_econ: dict[tuple[int, bool, str, str], _Cell]      = field(default_factory=dict)
    cells_no_map:  dict[tuple[int, bool, str], _Cell]           = field(default_factory=dict)
    cells_minimal: dict[tuple[int, bool], _Cell]                = field(default_factory=dict)
    side_baseline: dict[str, float] = field(default_factory=lambda: {"atk": 0.5, "def": 0.5})

    def lookup(
        self,
        numerical_diff: int,
        bomb_planted: bool,
        side: str,
        econ_bucket: str,
        map_name: str,
    ) -> float:
        """Phase 1: always returns _PHASE_1_FLAT_CELL_VALUE = 0.5 (D-06).

        Phase 2: walks the fallback chain (D-07):
          (numerical_diff, bomb, side, econ_bucket, map_name)  → cells_full
          → (numerical_diff, bomb, side, map_name)             → cells_no_econ
          → (numerical_diff, bomb, side)                       → cells_no_map
          → (numerical_diff, bomb)                             → cells_minimal
          → side_baseline[side]
          → _PHASE_1_FLAT_CELL_VALUE (defensive)
        """
        return _PHASE_1_FLAT_CELL_VALUE
```

The Protocol (added in this plan — gives 01-05's live_theo a typed shape to consume):
```python
from typing import Protocol

class RoundConclusionFn(Protocol):
    """Callable shape for the round-conclusion lookup, consumed by live_theo.

    The bound method ``RoundConclusionLookup.lookup`` satisfies this Protocol;
    so does any test fake. Live_theo (01-05) types its parameter as this
    Protocol to avoid importing the concrete RoundConclusionLookup class
    (keeps the dependency direction live_theo → round_conclusion one-way).
    """

    def __call__(
        self,
        numerical_diff: int,
        bomb_planted: bool,
        side: str,
        econ_bucket: str,
        map_name: str,
    ) -> float: ...
```

Pattern S3 (PATTERNS lines 919-933) — frozen dataclass with mutable default fields:
```python
# field(default_factory=...) is REQUIRED for dict fields on frozen dataclasses.
# `frozen=True` only blocks reassignment of the field, not mutation of the dict
# the field points to. Phase 2 will mutate cells_* dicts; this is intentional.
```

Test scaffolding (PATTERNS lines 778-818 — ship the hypothesis property test verbatim):
```python
@given(
    numerical_diff=st.integers(min_value=-4, max_value=4),
    bomb_planted=st.booleans(),
    side=st.sampled_from(["atk", "def"]),
    econ_bucket=st.sampled_from(["full", "semi-buy", "semi-eco", "eco"]),
    map_name=st.sampled_from(["Lotus", "Bind", "Haven", "Ascent", "Pearl", "Split", "Sunset"]),
)
def test_lookup_always_returns_flat_05_in_phase_1(...) -> None:
    lookup = RoundConclusionLookup()
    assert lookup.lookup(numerical_diff, bomb_planted, side, econ_bucket, map_name) == 0.5
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Implement src/pricing/round_conclusion.py with skeleton + Bayesian shrinkage cell + Protocol + property tests</name>
  <files>src/pricing/round_conclusion.py, tests/pricing/test_round_conclusion.py</files>

  <read_first>
    - src/config/constants.py:44-49 — verify SHRINK_PRIOR=15.0 is exported from Phase 0 (do NOT redefine)
    - .planning/phases/01-core-pricing-engine/01-RESEARCH.md §6 "Hierarchical-lookup skeleton signature" (lines 685-760)
    - .planning/phases/01-core-pricing-engine/01-PATTERNS.md "src/pricing/round_conclusion.py (data-shape, new)" section (lines 267-340) and "tests/pricing/test_round_conclusion.py (test, new)" section (lines 772-818)
    - .planning/phases/01-core-pricing-engine/01-CONTEXT.md D-06 (flat 0.5 in Phase 1), D-07 (fallback chain shape ships in Phase 1), D-09 (shrinkage formula salvage)
    - reference/theo_engine.py:84-102 — `_get_rate` containing the shrinkage formula at line 100 (read this entire block; the formula at line 100 is the source-of-truth being salvaged verbatim)
    - prd.md §5.3 (round-conclusion design intent) and §12.3 (no audit-engine triplet)
    - roadmap.md §1.5 (hierarchical fallback chain with cell→parent shrinkage)
    - CLAUDE.md Critical Rules 11 (mypy --strict), 12 (no magic numbers — SHRINK_PRIOR must come from constants)
  </read_first>

  <behavior>
    - Test 1 (flat 0.5 invariant — hypothesis): `RoundConclusionLookup().lookup(numerical_diff, bomb_planted, side, econ_bucket, map_name)` returns EXACTLY 0.5 for all (numerical_diff ∈ [-4..4], bomb_planted ∈ {True, False}, side ∈ {atk, def}, econ_bucket ∈ {full, semi-buy, semi-eco, eco}, map_name ∈ map_pool). D-06 invariant.
    - Test 2 (shrinkage formula): `_Cell(n=10, p_hat=0.6, parent_p=0.5).shrunk()` equals `(10 * 0.6 + 15.0 * 0.5) / (10 + 15.0) = 13.5 / 25.0 = 0.54` (within `rel_tol=1e-12`)
    - Test 3 (shrinkage with n=0): `_Cell(n=0, p_hat=0.0, parent_p=0.5).shrunk() == 0.5` — pure prior dominates when no data
    - Test 4 (shrinkage with large n): `_Cell(n=1000, p_hat=0.6, parent_p=0.5).shrunk()` is much closer to 0.6 than 0.5 — empirical dominates as n grows
    - Test 5 (no inline 15): `_Cell.shrunk` source contains `SHRINK_PRIOR` and does NOT contain bare ` 15 ` or `15.0` literal in the formula (CRule 12)
    - Test 6 (Protocol shape): `RoundConclusionFn` is a `Protocol`; `RoundConclusionLookup().lookup` is assignable to a `RoundConclusionFn`-typed variable (covered by `mypy --strict` + a runtime assignability check)
    - Test 7 (fallback chain fields exist): `RoundConclusionLookup()` has `cells_full`, `cells_no_econ`, `cells_no_map`, `cells_minimal`, `side_baseline` attributes; all five are present, even though Phase 1 never reads them. Phase 2 needs them populated.
    - Test 8 (side_baseline default): `RoundConclusionLookup().side_baseline == {"atk": 0.5, "def": 0.5}` — the leaf-level fallback has the right default shape
    - Test 9 (frozen): mutating `RoundConclusionLookup` fields raises `dataclasses.FrozenInstanceError` (frozen=True enforced)
    - Test 10 (cells dicts are mutable per Phase 2 expectation): `lookup_obj.cells_full[(0, False, "atk", "full", "Lotus")] = _Cell(...)` succeeds despite frozen=True — frozen blocks reassignment of the field, not mutation of the dict object
  </behavior>

  <action>
Create `src/pricing/round_conclusion.py` with this EXACT content:

```python
"""Hierarchical mid-round-conclusion lookup skeleton (Phase 1).

Phase 1 ships the SHAPE per DEC-007 (5-level fallback chain) but every cell
returns ``_PHASE_1_FLAT_CELL_VALUE = 0.5`` regardless of input (D-06). Phase 2
calibrates real cell values without changing this interface — Path-C compatible.

The Bayesian shrinkage formula on ``_Cell`` is salvaged verbatim from
``reference/theo_engine.py:100`` per D-09 / DEC-013:
    shrunk = (n * p_hat + SHRINK_PRIOR * parent_p) / (n + SHRINK_PRIOR)

Sources
-------
- DEC-007 / roadmap.md §1.5 (hierarchical fallback chain)
- D-06, D-07, D-09 (CONTEXT.md)
- prd.md §5.3 (mid-round pricing design)
- 01-RESEARCH.md §6 (signature + shrinkage scaffold)
- reference/theo_engine.py:84-102 (shrinkage source)

Phase 1 → Phase 2 seam
----------------------
Phase 2 (REQ-round-event-data-pipeline) populates ``cells_full``, ``cells_no_econ``,
``cells_no_map``, ``cells_minimal`` from rib.gg / OCR-derived round-event data and
extends ``lookup`` to walk the fallback chain. The PUBLIC interface
(``RoundConclusionLookup.lookup`` and ``RoundConclusionFn`` Protocol) does NOT
change — only the body of ``lookup`` is rewritten and the dict fields populated.
This locks Path-C compatibility (Phase 4 quoting can ship without Phase 2).

Why frozen=True with mutable dict fields
----------------------------------------
``@dataclass(frozen=True)`` blocks reassignment of the field reference, NOT
mutation of the dict object the field points to. Phase 2 will populate cells
via ``lookup_obj.cells_full[key] = _Cell(...)``, which works on frozen instances.
This matches the established Python idiom (verified by 01-PATTERNS.md §S3).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final, Protocol

from src.config.constants import SHRINK_PRIOR


# --------------------------------------------------------------------------- #
# 1. Phase 1 flat cell constant                                               #
# --------------------------------------------------------------------------- #


_PHASE_1_FLAT_CELL_VALUE: Final[float] = 0.5
"""Every ``RoundConclusionLookup.lookup`` invocation returns this value in Phase 1.

Source: D-06 / CONTEXT.md — the flat-0.5 placeholder is Path-C-compatible. Phase 2
calibrates real cell values; this constant is then unused at runtime but kept as
the defensive fallback at the bottom of the chain.
"""


# --------------------------------------------------------------------------- #
# 2. Bayesian-shrinkage cell                                                  #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class _Cell:
    """A single (numerical_diff, bomb_planted, side, econ_bucket, map) cell.

    Phase 1: only ``shrunk()`` is exercised by the formula test — no instances
    are stored in the lookup dicts (those are empty in Phase 1).

    Phase 2 populates instances of this class into the cells_* dicts on
    RoundConclusionLookup, then extends ``lookup`` to walk the chain.

    Attributes
    ----------
    n: Observed sample size in this cell (rounds matching the cell's keys).
    p_hat: Observed P(team A wins this round | cell context).
    parent_p: Parent-cell estimate (one level up the fallback chain) used as
        the Bayesian prior in ``shrunk()``.
    """

    n: int
    p_hat: float
    parent_p: float

    def shrunk(self) -> float:
        """Return the shrunk estimate.

        Source: ``reference/theo_engine.py:100`` — salvage verbatim per D-09.
        Formula: ``(n * p_hat + SHRINK_PRIOR * parent_p) / (n + SHRINK_PRIOR)``.

        Behavior:
          - At ``n == 0``: pure ``parent_p`` (prior dominates).
          - At ``n >> SHRINK_PRIOR``: converges to ``p_hat`` (empirical dominates).
          - At ``n == SHRINK_PRIOR``: arithmetic mean of empirical and prior.

        SHRINK_PRIOR is imported from src.config.constants per CRule 12 — never
        inline the literal 15 here.
        """
        return (self.n * self.p_hat + SHRINK_PRIOR * self.parent_p) / (
            self.n + SHRINK_PRIOR
        )


# --------------------------------------------------------------------------- #
# 3. Public callable Protocol (consumed by live_theo in 01-05)                #
# --------------------------------------------------------------------------- #


class RoundConclusionFn(Protocol):
    """Callable shape for the round-conclusion lookup.

    ``RoundConclusionLookup.lookup`` (bound method) satisfies this Protocol;
    test fakes can also satisfy it. ``live_theo`` (01-05) types its
    round_conclusion parameter as ``RoundConclusionFn`` so it consumes the
    interface, not the concrete class — keeps the dependency direction
    one-way (live_theo → round_conclusion).
    """

    def __call__(
        self,
        numerical_diff: int,
        bomb_planted: bool,
        side: str,
        econ_bucket: str,
        map_name: str,
    ) -> float: ...


# --------------------------------------------------------------------------- #
# 4. Hierarchical fallback chain skeleton                                     #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class RoundConclusionLookup:
    """5-tier hierarchical fallback-chain lookup (DEC-007 / roadmap §1.5).

    Phase 1 returns ``_PHASE_1_FLAT_CELL_VALUE`` for all inputs (D-06). The
    cells_* dicts and side_baseline ship empty/default; Phase 2 populates them
    from rib.gg / OCR round-event data without changing this class's public
    surface.

    Fallback chain order (D-07, walked by Phase 2 ``lookup``):
        1. ``cells_full``    — keyed on (numerical_diff, bomb, side, econ_bucket, map)
        2. ``cells_no_econ`` — drop econ_bucket: (numerical_diff, bomb, side, map)
        3. ``cells_no_map``  — drop map_name:    (numerical_diff, bomb, side)
        4. ``cells_minimal`` — drop side:        (numerical_diff, bomb)
        5. ``side_baseline`` — per-side default: {"atk": 0.5, "def": 0.5}
        6. ``_PHASE_1_FLAT_CELL_VALUE`` — defensive ultimate fallback (0.5)
    """

    cells_full: dict[tuple[int, bool, str, str, str], _Cell] = field(
        default_factory=dict
    )
    cells_no_econ: dict[tuple[int, bool, str, str], _Cell] = field(
        default_factory=dict
    )
    cells_no_map: dict[tuple[int, bool, str], _Cell] = field(default_factory=dict)
    cells_minimal: dict[tuple[int, bool], _Cell] = field(default_factory=dict)
    side_baseline: dict[str, float] = field(
        default_factory=lambda: {"atk": 0.5, "def": 0.5}
    )

    def lookup(
        self,
        numerical_diff: int,
        bomb_planted: bool,
        side: str,
        econ_bucket: str,
        map_name: str,
    ) -> float:
        """P(team A wins THIS round | mid-round context).

        Args:
            numerical_diff: Players-alive differential (A_alive - B_alive).
                Positive = A advantage; range typically [-4, 4].
            bomb_planted: True after spike plant on attacker side.
            side: 'atk' or 'def' — team A's side this half.
            econ_bucket: One of {'full', 'semi-buy', 'semi-eco', 'eco'} per
                Phase 0's CON-economy-buckets.
            map_name: Map this round is being played on.

        Returns:
            ``_PHASE_1_FLAT_CELL_VALUE = 0.5`` in Phase 1 (D-06). Phase 2
            replaces the body with the fallback-chain walk; the SIGNATURE and
            return type contract remain unchanged.
        """
        # Phase 1: short-circuit. Phase 2 will replace this single return with
        # the chain walk described in the class docstring. The dict fields are
        # already in place to be populated; this is the seam (D-07).
        return _PHASE_1_FLAT_CELL_VALUE
```

Then create `tests/pricing/test_round_conclusion.py` with this EXACT content:

```python
"""Tests for src.pricing.round_conclusion — REQ-round-conclusion-lookup (skeleton).

Verifies the Phase 1 invariants:
  - All cells return ``_PHASE_1_FLAT_CELL_VALUE = 0.5`` regardless of inputs (D-06).
  - ``_Cell.shrunk()`` Bayesian formula matches ``reference/theo_engine.py:100``
    verbatim with SHRINK_PRIOR=15.0 imported from constants (D-09 / CRule 12).
  - The 5-tier fallback-chain dict fields are present so Phase 2 can populate
    without changing the interface (D-07).
  - ``RoundConclusionFn`` Protocol is satisfied by ``RoundConclusionLookup.lookup``.
  - frozen=True is enforced on the dataclass (Pattern S3).
  - Source contains no inline `15` / `15.0` for the shrinkage formula (CRule 12).
"""

from __future__ import annotations

import dataclasses
import math
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

from src.config.constants import SHRINK_PRIOR
from src.pricing.round_conclusion import (
    RoundConclusionFn,
    RoundConclusionLookup,
    _Cell,
    _PHASE_1_FLAT_CELL_VALUE,
)


# --------------------------------------------------------------------------- #
# 1. Flat-0.5 invariant (Phase 1 contract per D-06)                           #
# --------------------------------------------------------------------------- #


@given(
    numerical_diff=st.integers(min_value=-4, max_value=4),
    bomb_planted=st.booleans(),
    side=st.sampled_from(["atk", "def"]),
    econ_bucket=st.sampled_from(["full", "semi-buy", "semi-eco", "eco"]),
    map_name=st.sampled_from(
        ["Lotus", "Bind", "Haven", "Ascent", "Pearl", "Split", "Sunset"]
    ),
)
@settings(max_examples=100, deadline=None)
def test_lookup_always_returns_flat_05_in_phase_1(
    numerical_diff: int,
    bomb_planted: bool,
    side: str,
    econ_bucket: str,
    map_name: str,
) -> None:
    """D-06: every cell returns _PHASE_1_FLAT_CELL_VALUE = 0.5 in Phase 1.

    Phase 2 calibration replaces the body of ``lookup`` without touching this
    test's signature — when calibration lands, this test is rewritten to
    expect calibrated values. For Phase 1, the invariant is flat 0.5.
    """
    lookup = RoundConclusionLookup()
    assert lookup.lookup(numerical_diff, bomb_planted, side, econ_bucket, map_name) == 0.5


def test_phase_1_flat_cell_value_is_05() -> None:
    """The exported Phase 1 constant equals 0.5 (D-06)."""
    assert _PHASE_1_FLAT_CELL_VALUE == 0.5


# --------------------------------------------------------------------------- #
# 2. _Cell Bayesian shrinkage formula (D-09)                                  #
# --------------------------------------------------------------------------- #


def test_cell_shrunk_matches_audit_engine_formula() -> None:
    """`(n * p_hat + SHRINK_PRIOR * parent_p) / (n + SHRINK_PRIOR)` per ref:100."""
    cell = _Cell(n=10, p_hat=0.6, parent_p=0.5)
    expected = (10 * 0.6 + SHRINK_PRIOR * 0.5) / (10 + SHRINK_PRIOR)
    # SHRINK_PRIOR=15.0 → (6.0 + 7.5) / 25.0 = 13.5 / 25.0 = 0.54
    assert math.isclose(cell.shrunk(), expected, rel_tol=1e-12)
    assert math.isclose(cell.shrunk(), 0.54, rel_tol=1e-12)


def test_cell_shrunk_at_zero_n_returns_parent() -> None:
    """At n=0, pure prior dominates: shrunk == parent_p."""
    cell = _Cell(n=0, p_hat=0.0, parent_p=0.5)
    assert math.isclose(cell.shrunk(), 0.5, rel_tol=1e-12)


def test_cell_shrunk_at_large_n_converges_to_p_hat() -> None:
    """At n=1000 (>> SHRINK_PRIOR=15), shrunk converges toward p_hat=0.6."""
    cell = _Cell(n=1000, p_hat=0.6, parent_p=0.5)
    # Distance to 0.6 should be much smaller than distance to 0.5.
    val = cell.shrunk()
    assert abs(val - 0.6) < abs(val - 0.5)
    # Quantitative: with n=1000, the empirical weight is 1000/(1000+15) ≈ 0.985.
    assert math.isclose(val, (1000 * 0.6 + SHRINK_PRIOR * 0.5) / (1000 + SHRINK_PRIOR), rel_tol=1e-12)


@given(
    n=st.integers(min_value=0, max_value=10_000),
    p_hat=st.floats(min_value=0.0, max_value=1.0),
    parent_p=st.floats(min_value=0.0, max_value=1.0),
)
@settings(max_examples=100, deadline=None)
def test_cell_shrunk_in_unit_interval(n: int, p_hat: float, parent_p: float) -> None:
    """Property: for any (n, p_hat, parent_p) in valid bounds, shrunk ∈ [0, 1]."""
    val = _Cell(n=n, p_hat=p_hat, parent_p=parent_p).shrunk()
    assert 0.0 <= val <= 1.0
    assert not math.isnan(val)


# --------------------------------------------------------------------------- #
# 3. CRule 12 — no inline 15 / 15.0 in the shrinkage formula                  #
# --------------------------------------------------------------------------- #


def test_source_uses_shrink_prior_constant_not_inline_literal() -> None:
    """CRule 12 / CON-no-magic-numbers: shrinkage formula must use SHRINK_PRIOR.

    Bare ``15`` or ``15.0`` literal in the formula body would violate the rule.
    The only places `15` / `15.0` may appear: import lines, comments, or test
    expectations. The shrunk() function body must reference the imported name.
    """
    src = Path("src/pricing/round_conclusion.py").read_text(encoding="utf-8")
    # Strip comments and docstrings to check executable lines only.
    code_lines: list[str] = []
    in_docstring = False
    for line in src.splitlines():
        stripped = line.strip()
        if stripped.startswith('"""') or stripped.startswith("'''"):
            # Toggle docstring state — handles single-line and multi-line cases.
            count = stripped.count('"""') + stripped.count("'''")
            if count == 2:
                # Single-line docstring; skip but don't toggle.
                continue
            in_docstring = not in_docstring
            continue
        if in_docstring:
            continue
        if stripped.startswith("#"):
            continue
        if not stripped:
            continue
        code_lines.append(line)
    code = "\n".join(code_lines)
    # The formula must NOT contain a bare 15 / 15.0 literal.
    assert "15.0" not in code, "Bare 15.0 literal found in code; use SHRINK_PRIOR"
    # `15` could appear in slice indices or other contexts in the future, so
    # check the specific formula shape:
    assert "* 15 *" not in code
    assert "+ 15 *" not in code
    assert "+ 15)" not in code
    # And confirm SHRINK_PRIOR IS used:
    assert "SHRINK_PRIOR" in code


# --------------------------------------------------------------------------- #
# 4. RoundConclusionFn Protocol — shape consumed by live_theo (01-05)         #
# --------------------------------------------------------------------------- #


def test_round_conclusion_fn_protocol_is_satisfied_by_lookup() -> None:
    """RoundConclusionLookup.lookup is assignable to RoundConclusionFn."""
    lookup = RoundConclusionLookup()
    # Assigning to a Protocol-typed name exercises structural typing under mypy.
    # At runtime, Protocol is not strict — we verify the call-shape works.
    fn: RoundConclusionFn = lookup.lookup
    result = fn(0, False, "atk", "full", "Lotus")
    assert result == 0.5


def test_round_conclusion_fn_protocol_runtime_callable() -> None:
    """A simple lambda satisfying the shape is also callable as RoundConclusionFn."""
    # Useful for test fakes in 01-05.
    def fake(num: int, bomb: bool, side: str, econ: str, m: str) -> float:
        return 0.7
    fn: RoundConclusionFn = fake
    assert fn(0, False, "atk", "full", "Lotus") == 0.7


# --------------------------------------------------------------------------- #
# 5. Fallback chain dict-field layout (D-07 — Phase 2 readiness)              #
# --------------------------------------------------------------------------- #


def test_fallback_chain_dict_fields_are_present() -> None:
    """All five fallback-chain fields exist on a default RoundConclusionLookup.

    Phase 2 must be able to populate cells_full / cells_no_econ / cells_no_map
    / cells_minimal and override side_baseline without changing the dataclass.
    """
    lookup = RoundConclusionLookup()
    assert hasattr(lookup, "cells_full")
    assert hasattr(lookup, "cells_no_econ")
    assert hasattr(lookup, "cells_no_map")
    assert hasattr(lookup, "cells_minimal")
    assert hasattr(lookup, "side_baseline")
    # Default values: empty dicts for cells_*, populated baseline for sides.
    assert lookup.cells_full == {}
    assert lookup.cells_no_econ == {}
    assert lookup.cells_no_map == {}
    assert lookup.cells_minimal == {}
    assert lookup.side_baseline == {"atk": 0.5, "def": 0.5}


def test_default_factory_fresh_instance_per_lookup() -> None:
    """Each RoundConclusionLookup() gets its own dict instances.

    Phase 2 may construct multiple lookups (e.g., per match) — they must NOT
    share state via the default_factory mistake.
    """
    a = RoundConclusionLookup()
    b = RoundConclusionLookup()
    a.cells_full[(0, False, "atk", "full", "Lotus")] = _Cell(n=10, p_hat=0.5, parent_p=0.5)
    assert (0, False, "atk", "full", "Lotus") not in b.cells_full


# --------------------------------------------------------------------------- #
# 6. frozen=True (Pattern S3 — blocks reassignment, not dict mutation)        #
# --------------------------------------------------------------------------- #


def test_frozen_blocks_field_reassignment() -> None:
    """`frozen=True` raises FrozenInstanceError on field reassignment."""
    lookup = RoundConclusionLookup()
    with pytest.raises(dataclasses.FrozenInstanceError):
        lookup.cells_full = {}  # type: ignore[misc]


def test_frozen_allows_dict_mutation_for_phase_2_population() -> None:
    """Phase 2 will populate cells_full via dict mutation — must work despite frozen.

    `frozen=True` blocks reassignment of the field reference, NOT mutation of
    the dict object the field points to. This is the Python idiom; verifying
    here so Phase 2 doesn't get a surprise.
    """
    lookup = RoundConclusionLookup()
    cell = _Cell(n=10, p_hat=0.6, parent_p=0.5)
    lookup.cells_full[(0, False, "atk", "full", "Lotus")] = cell
    assert lookup.cells_full[(0, False, "atk", "full", "Lotus")] is cell
```

Commit with message `feat(01-04): add round-conclusion lookup skeleton + Bayesian shrinkage cell + Protocol`.
  </action>

  <verify>
    <automated>uv run mypy --strict src/pricing/round_conclusion.py &amp;&amp; uv run pytest tests/pricing/test_round_conclusion.py -x &amp;&amp; uv run ruff check src/pricing/round_conclusion.py tests/pricing/test_round_conclusion.py</automated>
  </verify>

  <acceptance_criteria>
    - `test -f src/pricing/round_conclusion.py`
    - `grep -q "_PHASE_1_FLAT_CELL_VALUE: Final\[float\] = 0.5" src/pricing/round_conclusion.py`
    - `grep -q "@dataclass(frozen=True, slots=True)" src/pricing/round_conclusion.py` (Pattern S3 — both _Cell and RoundConclusionLookup)
    - `grep -q "class _Cell:" src/pricing/round_conclusion.py`
    - `grep -q "class RoundConclusionLookup:" src/pricing/round_conclusion.py`
    - `grep -q "class RoundConclusionFn(Protocol):" src/pricing/round_conclusion.py`
    - `grep -q "def shrunk(self) -> float:" src/pricing/round_conclusion.py`
    - `grep -q "def lookup(" src/pricing/round_conclusion.py`
    - `grep -qE "\(self\.n \* self\.p_hat \+ SHRINK_PRIOR \* self\.parent_p\) / \(self\.n \+ SHRINK_PRIOR\)" src/pricing/round_conclusion.py` (formula present, uses SHRINK_PRIOR)
    - `grep -q "from src.config.constants import SHRINK_PRIOR" src/pricing/round_conclusion.py` (no inline 15)
    - `grep -q "cells_full" src/pricing/round_conclusion.py`
    - `grep -q "cells_no_econ" src/pricing/round_conclusion.py`
    - `grep -q "cells_no_map" src/pricing/round_conclusion.py`
    - `grep -q "cells_minimal" src/pricing/round_conclusion.py`
    - `grep -q "side_baseline" src/pricing/round_conclusion.py`
    - `grep -q "field(default_factory=dict)" src/pricing/round_conclusion.py` (Pattern S3 — mutable default per frozen-dataclass idiom)
    - Comment-stripped: `! (grep -v '^[[:space:]]*#' src/pricing/round_conclusion.py | grep -v '^[[:space:]]*"' | grep -E '\* 15 \*|\+ 15 \*|\+ 15\)')` (no inline 15 in formula)
    - `test -f tests/pricing/test_round_conclusion.py`
    - `grep -q "test_lookup_always_returns_flat_05_in_phase_1" tests/pricing/test_round_conclusion.py`
    - `grep -q "test_cell_shrunk_matches_audit_engine_formula" tests/pricing/test_round_conclusion.py`
    - `grep -q "test_cell_shrunk_at_zero_n_returns_parent" tests/pricing/test_round_conclusion.py`
    - `grep -q "test_cell_shrunk_at_large_n_converges_to_p_hat" tests/pricing/test_round_conclusion.py`
    - `grep -q "test_cell_shrunk_in_unit_interval" tests/pricing/test_round_conclusion.py`
    - `grep -q "test_source_uses_shrink_prior_constant_not_inline_literal" tests/pricing/test_round_conclusion.py`
    - `grep -q "test_round_conclusion_fn_protocol_is_satisfied_by_lookup" tests/pricing/test_round_conclusion.py`
    - `grep -q "test_fallback_chain_dict_fields_are_present" tests/pricing/test_round_conclusion.py`
    - `grep -q "test_frozen_blocks_field_reassignment" tests/pricing/test_round_conclusion.py`
    - `grep -q "test_frozen_allows_dict_mutation_for_phase_2_population" tests/pricing/test_round_conclusion.py`
    - `uv run mypy --strict src/pricing/round_conclusion.py` exits 0
    - `uv run pytest tests/pricing/test_round_conclusion.py -x` exits 0 (all 11+ tests pass; hypothesis runs ≥ 100 examples on the flat-0.5 invariant and ≥ 100 on shrunk-in-unit)
    - `uv run ruff check src/pricing/round_conclusion.py tests/pricing/test_round_conclusion.py` exits 0
  </acceptance_criteria>

  <done>
    `src/pricing/round_conclusion.py` exports `RoundConclusionLookup` (frozen dataclass, 5 fallback-chain dict fields + side_baseline), `_Cell` (Bayesian shrinkage with `(n*p_hat + SHRINK_PRIOR*parent_p)/(n+SHRINK_PRIOR)`), `RoundConclusionFn` Protocol, and `_PHASE_1_FLAT_CELL_VALUE` Final constant. `lookup(...)` returns 0.5 for ALL inputs (D-06 invariant locked by 100-example hypothesis test). Shrinkage formula uses imported `SHRINK_PRIOR` (CRule 12 regression-locked). All 11+ tests pass under `mypy --strict`; ruff and pytest green. Phase 2 can populate cells_* without touching the public surface.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| `RoundConclusionLookup.lookup` ↔ `live_theo` (01-05) | live_theo passes mid-round inputs (`numerical_diff`, `bomb_planted`, `side`, `econ_bucket`, `map_name`) sourced from `MatchState`. Phase 1 returns flat 0.5 regardless — no input validation needed. |
| `_Cell.shrunk` ↔ Phase 2 callers | Phase 2 populates _Cell instances with `(n, p_hat, parent_p)`. Inputs may include malformed empirical data — the formula handles `n=0` (returns parent_p) and any `p_hat ∈ [0, 1]`. |
| `cells_*` dicts ↔ Phase 2 mutators | Frozen dataclass blocks reassignment but allows dict mutation by design. Phase 2 must not replace the dict object — only mutate it. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-01-04-01 | Tampering | `_Cell.shrunk` regressing to inline `15` literal during refactor | mitigate | `test_source_uses_shrink_prior_constant_not_inline_literal` greps source for bare `15.0` / `* 15 *` / `+ 15 *` / `+ 15)` patterns; failure surfaces at commit time. SHRINK_PRIOR import is also asserted present. |
| T-01-04-02 | Tampering | `RoundConclusionLookup.lookup` returning a non-0.5 value in Phase 1 (e.g., a stray cells_* lookup before Phase 2 calibration) | mitigate | `test_lookup_always_returns_flat_05_in_phase_1` runs 100 hypothesis examples spanning the cartesian product; D-06 invariant regression-locked. Phase 2 will rewrite this test, NOT delete it. |
| T-01-04-03 | Tampering | `_Cell.shrunk` producing NaN at boundary inputs (n + SHRINK_PRIOR == 0) | mitigate | SHRINK_PRIOR=15.0 is a positive Final constant; n is non-negative; denominator >= 15.0 strictly. `test_cell_shrunk_in_unit_interval` runs 100 hypothesis examples to confirm no NaN propagation. |
| T-01-04-04 | Tampering | `default_factory` mutable-default trap (all instances sharing one dict) | mitigate | `test_default_factory_fresh_instance_per_lookup` constructs two lookups, mutates one, and asserts the other is unaffected. The `field(default_factory=dict)` idiom is the established Python fix. |
| T-01-04-05 | DoS | `cells_*` dicts growing unboundedly under Phase 2 population | accept | Phase 1 ships empty dicts. Cardinality bound is Phase 2's concern (cells_full ≤ ~9 (numerical_diff) × 2 (bomb) × 2 (side) × 4 (econ) × 7 (map) = ~1000 cells). Bounded for any realistic dataset. |
| T-01-04-06 | Information Disclosure | The lookup module | accept | No PII, no secrets — flat 0.5 is the only data exposed; Phase 2 cell values are aggregated empirical statistics from public match data. |
</threat_model>

<verification>
After Task 1 completes:

```bash
uv run mypy --strict src/pricing/round_conclusion.py
uv run pytest tests/pricing/test_round_conclusion.py -x -v
uv run ruff check src/pricing/round_conclusion.py tests/pricing/test_round_conclusion.py
```

All three MUST exit 0. Test count: 11 tests including 2 hypothesis property tests (≥ 100 examples each).

Sanity check (manual):
```bash
uv run python -c "
from src.pricing.round_conclusion import RoundConclusionLookup, _Cell

lookup = RoundConclusionLookup()
print('lookup(0, False, atk, full, Lotus):', lookup.lookup(0, False, 'atk', 'full', 'Lotus'))
print('lookup(-3, True,  def, eco,  Bind ):', lookup.lookup(-3, True, 'def', 'eco', 'Bind'))
print('_Cell(10, 0.6, 0.5).shrunk():', _Cell(n=10, p_hat=0.6, parent_p=0.5).shrunk())
print('_Cell(0, 0.0, 0.5).shrunk():', _Cell(n=0, p_hat=0.0, parent_p=0.5).shrunk())
"
```
Expected output:
- `lookup(0, False, atk, full, Lotus): 0.5`
- `lookup(-3, True,  def, eco,  Bind ): 0.5`
- `_Cell(10, 0.6, 0.5).shrunk(): 0.54`
- `_Cell(0, 0.0, 0.5).shrunk(): 0.5`
</verification>

<success_criteria>
- `RoundConclusionLookup` (frozen+slots dataclass) exists with all five fallback-chain dict fields plus `side_baseline = {"atk": 0.5, "def": 0.5}`
- `RoundConclusionLookup().lookup(...)` returns exactly 0.5 for every input combination (D-06 invariant locked by 100-example hypothesis test)
- `_Cell` (frozen+slots dataclass) implements `shrunk() = (n * p_hat + SHRINK_PRIOR * parent_p) / (n + SHRINK_PRIOR)` per D-09 / `reference/theo_engine.py:100`
- `_Cell.shrunk` returns parent_p at `n=0`, converges to p_hat at `n >> SHRINK_PRIOR`, stays in [0, 1] always
- `RoundConclusionFn` Protocol is defined and satisfied by `RoundConclusionLookup.lookup` (so 01-05 can type its parameter)
- No inline `15` / `15.0` literal in source (CRule 12 regression-locked by source-grep test)
- `field(default_factory=dict)` produces fresh dict instances per `RoundConclusionLookup()` call (no shared-mutable-default trap)
- frozen=True blocks field reassignment but allows dict mutation (Phase 2 readiness)
- `mypy --strict src/pricing/round_conclusion.py`, `pytest tests/pricing/test_round_conclusion.py`, `ruff check` all green
- All Phase 0 tests still pass (no regression in `tests/test_smoke.py`, `tests/test_main.py`, `tests/config/test_constants.py`)
</success_criteria>

<output>
After completion, create `.planning/phases/01-core-pricing-engine/01-04-round-conclusion-skeleton-SUMMARY.md`.

The SUMMARY must record:
- Confirmation that ALL cells return `_PHASE_1_FLAT_CELL_VALUE = 0.5` in Phase 1 (D-06)
- The 5-tier fallback-chain field layout as shipped (cells_full → cells_no_econ → cells_no_map → cells_minimal → side_baseline → 0.5)
- The Bayesian shrinkage formula as shipped (one line: `(n * p_hat + SHRINK_PRIOR * parent_p) / (n + SHRINK_PRIOR)`)
- Confirmation that SHRINK_PRIOR is imported (no inline 15)
- The `RoundConclusionFn` Protocol signature (5 args, returns float) for 01-05 to consume
- Test count: 11 tests including 2 hypothesis property tests (flat-0.5 invariant + shrunk-in-unit)
- No surprises / no decisions deviated from CONTEXT.md
- Commit SHA for the single atomic commit
</output>
</content>
</invoke>