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
from hypothesis import given, settings
from hypothesis import strategies as st

from src.config.constants import SHRINK_PRIOR
from src.pricing.round_conclusion import (
    _PHASE_1_FLAT_CELL_VALUE,
    RoundConclusionFn,
    RoundConclusionLookup,
    _Cell,
)

# --------------------------------------------------------------------------- #
# 1. Path-C empty-lookup invariant (D-12 — preserves Phase 1 behavior)        #
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
def test_empty_lookup_returns_side_baseline(
    numerical_diff: int,
    bomb_planted: bool,
    side: str,
    econ_bucket: str,
    map_name: str,
) -> None:
    """D-12 / Path-C regression: an unpopulated RoundConclusionLookup returns
    side_baseline[side] (which defaults to 0.5 atk / 0.5 def per D-06).

    Phase 2 rewrites the body to walk a 5-tier fallback chain. With every cell
    dict empty AND default side_baseline, the lookup degrades to the 0.5
    behavior Phase 1 shipped — locking the Path-C contract.
    """
    lookup = RoundConclusionLookup()
    expected = lookup.side_baseline[side]
    assert lookup.lookup(numerical_diff, bomb_planted, side, econ_bucket, map_name) == expected
    assert expected == 0.5  # default factory


def test_phase_1_flat_cell_value_is_05() -> None:
    """The exported Phase 1 constant equals 0.5 (D-06).

    Still exported because it is the defensive ultimate fallback in
    ``lookup()`` when even side_baseline has been emptied (a degenerate
    state that should not arise in production but must not crash).
    """
    assert _PHASE_1_FLAT_CELL_VALUE == 0.5


def test_lookup_falls_back_to_flat_when_side_baseline_missing() -> None:
    """Defensive: if side_baseline is mutated to drop a side, lookup still
    returns _PHASE_1_FLAT_CELL_VALUE (0.5). Guards against accidental
    pop("atk") downstream.
    """
    lookup = RoundConclusionLookup()
    lookup.side_baseline.pop("atk", None)
    assert lookup.lookup(0, False, "atk", "full", "Lotus") == _PHASE_1_FLAT_CELL_VALUE


# --------------------------------------------------------------------------- #
# 2. _Cell Bayesian shrinkage formula (D-09)                                  #
# --------------------------------------------------------------------------- #


def test_cell_shrunk_matches_audit_engine_formula() -> None:
    """`(n * p_hat + SHRINK_PRIOR * parent_p) / (n + SHRINK_PRIOR)` per ref:100."""
    cell = _Cell(n=10, p_hat=0.6, parent_p=0.5)
    expected = (10 * 0.6 + SHRINK_PRIOR * 0.5) / (10 + SHRINK_PRIOR)
    # SHRINK_PRIOR=15.0 -> (6.0 + 7.5) / 25.0 = 13.5 / 25.0 = 0.54
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
    # Quantitative: with n=1000, the empirical weight is 1000/(1000+15) ~ 0.985.
    assert math.isclose(
        val,
        (1000 * 0.6 + SHRINK_PRIOR * 0.5) / (1000 + SHRINK_PRIOR),
        rel_tol=1e-12,
    )


@given(
    n=st.integers(min_value=0, max_value=10_000),
    p_hat=st.floats(min_value=0.0, max_value=1.0),
    parent_p=st.floats(min_value=0.0, max_value=1.0),
)
@settings(max_examples=100, deadline=None)
def test_cell_shrunk_in_unit_interval(n: int, p_hat: float, parent_p: float) -> None:
    """Property: for any (n, p_hat, parent_p) in valid bounds, shrunk in [0, 1]."""
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
    a.cells_full[(0, False, "atk", "full", "Lotus")] = _Cell(
        n=10, p_hat=0.5, parent_p=0.5
    )
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
