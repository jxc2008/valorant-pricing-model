"""Tests for src.pricing.round_conclusion — REQ-round-conclusion-lookup (v2 surface).

03-02 rewrites this file in-place from the v1 5-arg ``lookup`` surface to the
v2 two-method surface (``between_round_p`` + ``post_plant_p``). The Phase 1+2
hierarchy semantics are PRESERVED (cell hit at tier N returns the shrunk value;
fall-through at every tier walks down to side_baseline) — only the key shapes
shift to ``(att, def_, time_bucket, side, map)`` for cells_full and weaker
projections for the upper tiers (D-04).

What this file asserts:
  - Empty-lookup invariant: post_plant_p with no cells returns side_baseline
    (Path-C compatibility carry-forward — bit-identical to the Phase 1 stub).
  - ``_Cell.shrunk()`` Bayesian formula matches reference:100 verbatim.
  - The 4 v2 fallback-chain dict fields are present + default to empty.
  - ``BetweenRoundFn`` / ``PostPlantFn`` Protocols are satisfied by the bound
    methods.
  - ``frozen=True`` is enforced (Pattern S3).
  - Source uses SHRINK_PRIOR — no inline 15.0 literal in the formula (CRule 12).

The v1-surface test file (Phase 1+2) referenced ``numerical_diff``,
``econ_bucket``, ``cells_no_econ``, ``RoundConclusionFn``, and the 5-arg
``lookup()`` method — ALL DELETED in 03-02 per CLAUDE.md "Economy buckets —
DEPRECATED in v2". Test names that contained ``test_lookup_*`` have been
renamed to ``test_post_plant_p_*``.
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
    BetweenRoundFn,
    PostPlantFn,
    RoundConclusionLookup,
    _Cell,
)

# --------------------------------------------------------------------------- #
# 1. Empty-lookup / Path-C invariant — D-04 (carry-forward of v1 D-12)        #
# --------------------------------------------------------------------------- #


@given(
    att=st.integers(min_value=0, max_value=5),
    def_=st.integers(min_value=0, max_value=5),
    time_bucket=st.integers(min_value=0, max_value=8),
    side=st.sampled_from(["atk", "def"]),
    map_name=st.sampled_from(
        ["Lotus", "Bind", "Haven", "Ascent", "Pearl", "Split", "Sunset"]
    ),
)
@settings(max_examples=100, deadline=None)
def test_empty_lookup_post_plant_returns_side_baseline(
    att: int,
    def_: int,
    time_bucket: int,
    side: str,
    map_name: str,
) -> None:
    """Empty RoundConclusionLookup returns side_baseline[side] from post_plant_p.

    With every cell dict empty AND default side_baseline {"atk": 0.5, "def": 0.5},
    post_plant_p degrades to 0.5 — bit-identical to the Phase 1 stub's behavior
    on the v1 surface. Locks the Path-C-equivalent contract for v2.
    """
    lookup = RoundConclusionLookup()
    expected = lookup.side_baseline[side]
    assert lookup.post_plant_p(att, def_, time_bucket, side, map_name) == expected
    assert expected == 0.5  # default factory


def test_empty_lookup_between_round_returns_side_baseline() -> None:
    """between_round_p on a default lookup returns side_baseline directly."""
    lookup = RoundConclusionLookup()
    assert lookup.between_round_p("atk", "Lotus", 5) == 0.5
    assert lookup.between_round_p("def", "Bind", 11) == 0.5


def test_post_plant_p_falls_back_to_05_when_side_baseline_missing() -> None:
    """Defensive: if side_baseline is mutated to drop a side, post_plant_p
    still returns 0.5 (the get-default). Guards against accidental
    ``pop("atk")`` downstream.
    """
    lookup = RoundConclusionLookup()
    lookup.side_baseline.pop("atk", None)
    assert lookup.post_plant_p(0, 0, 0, "atk", "Lotus") == 0.5


# --------------------------------------------------------------------------- #
# 2. _Cell Bayesian shrinkage formula (D-09 — preserved verbatim from v1)     #
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
    val = cell.shrunk()
    assert abs(val - 0.6) < abs(val - 0.5)
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
    """
    src = Path("src/pricing/round_conclusion.py").read_text(encoding="utf-8")
    code_lines: list[str] = []
    in_docstring = False
    for line in src.splitlines():
        stripped = line.strip()
        if stripped.startswith('"""') or stripped.startswith("'''"):
            count = stripped.count('"""') + stripped.count("'''")
            if count == 2:
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
    assert "15.0" not in code, "Bare 15.0 literal found in code; use SHRINK_PRIOR"
    assert "* 15 *" not in code
    assert "+ 15 *" not in code
    assert "+ 15)" not in code
    assert "SHRINK_PRIOR" in code


# --------------------------------------------------------------------------- #
# 4. Protocols (D-04) — BetweenRoundFn + PostPlantFn                          #
# --------------------------------------------------------------------------- #


def test_between_round_fn_protocol_is_satisfied_by_lookup() -> None:
    """RoundConclusionLookup.between_round_p is assignable to BetweenRoundFn."""
    lookup = RoundConclusionLookup()
    fn: BetweenRoundFn = lookup.between_round_p
    result = fn("atk", "Lotus", 5)
    assert result == 0.5


def test_post_plant_fn_protocol_is_satisfied_by_lookup() -> None:
    """RoundConclusionLookup.post_plant_p is assignable to PostPlantFn."""
    lookup = RoundConclusionLookup()
    fn: PostPlantFn = lookup.post_plant_p
    result = fn(0, 0, 0, "atk", "Lotus")
    assert result == 0.5


def test_between_round_fn_protocol_runtime_callable() -> None:
    """A simple lambda satisfying the shape is callable as BetweenRoundFn."""

    def fake(side: str, map_name: str, round_idx: int) -> float:
        return 0.7

    fn: BetweenRoundFn = fake
    assert fn("atk", "Lotus", 5) == 0.7


def test_post_plant_fn_protocol_runtime_callable() -> None:
    """A simple lambda satisfying the shape is callable as PostPlantFn."""

    def fake(att: int, def_: int, time_bucket: int, side: str, map_name: str) -> float:
        return 0.6

    fn: PostPlantFn = fake
    assert fn(3, 2, 0, "atk", "Lotus") == 0.6


# --------------------------------------------------------------------------- #
# 5. v2 fallback-chain dict-field layout (D-04)                               #
# --------------------------------------------------------------------------- #


def test_fallback_chain_dict_fields_are_present() -> None:
    """All 4 v2 fallback-chain fields exist on a default RoundConclusionLookup.

    cells_no_econ (v1 surface) is DELETED — the v2 schema rekeys to
    cells_no_time. Tests asserting cells_no_econ existence have been removed
    in 03-02.
    """
    lookup = RoundConclusionLookup()
    assert hasattr(lookup, "cells_full")
    assert hasattr(lookup, "cells_no_time")
    assert hasattr(lookup, "cells_no_map")
    assert hasattr(lookup, "cells_minimal")
    assert hasattr(lookup, "side_baseline")
    # Default values:
    assert lookup.cells_full == {}
    assert lookup.cells_no_time == {}
    assert lookup.cells_no_map == {}
    assert lookup.cells_minimal == {}
    assert lookup.side_baseline == {"atk": 0.5, "def": 0.5}
    # v1 surface field DELETED — guards against accidental reintroduction
    assert not hasattr(lookup, "cells_no_econ")


def test_default_factory_fresh_instance_per_lookup() -> None:
    """Each RoundConclusionLookup() gets its own dict instances.

    Phase 5 may construct multiple lookups (e.g., per match) — they must NOT
    share state via the default_factory mistake.
    """
    a = RoundConclusionLookup()
    b = RoundConclusionLookup()
    a.cells_full[(3, 2, 0, "atk", "Lotus")] = _Cell(n=10, p_hat=0.5, parent_p=0.5)
    assert (3, 2, 0, "atk", "Lotus") not in b.cells_full


# --------------------------------------------------------------------------- #
# 6. v2 hierarchy walk (D-04 — replaces v1 ``test_lookup_*`` tests)           #
# --------------------------------------------------------------------------- #


def test_post_plant_p_cells_full_hit_returns_shrunk() -> None:
    """Tier 1: cells_full hit returns shrunk(n, p_hat, parent_p)."""
    lookup = RoundConclusionLookup()
    lookup.cells_full[(3, 2, 0, "atk", "Lotus")] = _Cell(
        n=42, p_hat=0.61, parent_p=0.55
    )
    expected = (42 * 0.61 + SHRINK_PRIOR * 0.55) / (42 + SHRINK_PRIOR)
    assert math.isclose(
        lookup.post_plant_p(3, 2, 0, "atk", "Lotus"), expected, rel_tol=1e-12
    )


def test_post_plant_p_cells_no_time_fall_through() -> None:
    """Tier 2: cells_no_time hit when cells_full misses."""
    lookup = RoundConclusionLookup()
    lookup.cells_no_time[(2, 1, "atk", "Lotus")] = _Cell(
        n=20, p_hat=0.49, parent_p=0.51
    )
    expected = (20 * 0.49 + SHRINK_PRIOR * 0.51) / (20 + SHRINK_PRIOR)
    # Different time_bucket; cells_full has no entry; fall through
    assert math.isclose(
        lookup.post_plant_p(2, 1, 7, "atk", "Lotus"), expected, rel_tol=1e-12
    )


def test_post_plant_p_cells_no_map_fall_through() -> None:
    """Tier 3: cells_no_map hit when cells_full + cells_no_time miss."""
    lookup = RoundConclusionLookup()
    lookup.cells_no_map[(1, 0, "def")] = _Cell(n=15, p_hat=0.7, parent_p=0.5)
    expected = (15 * 0.7 + SHRINK_PRIOR * 0.5) / (15 + SHRINK_PRIOR)
    # Different map; no cells_full / cells_no_time match; fall through
    assert math.isclose(
        lookup.post_plant_p(1, 0, 0, "def", "Bind"), expected, rel_tol=1e-12
    )


def test_post_plant_p_cells_minimal_fall_through() -> None:
    """Tier 4: cells_minimal hit when cells_full / no_time / no_map all miss."""
    lookup = RoundConclusionLookup()
    lookup.cells_minimal[(0, 1)] = _Cell(n=12, p_hat=0.55, parent_p=0.49)
    expected = (12 * 0.55 + SHRINK_PRIOR * 0.49) / (12 + SHRINK_PRIOR)
    # No upper-tier match; fall to cells_minimal regardless of side / map
    assert math.isclose(
        lookup.post_plant_p(0, 1, 0, "atk", "Bind"), expected, rel_tol=1e-12
    )


def test_post_plant_p_full_walk_priority() -> None:
    """Cells at every tier; cells_full must win over weaker tiers."""
    lookup = RoundConclusionLookup()
    lookup.cells_minimal[(3, 2)] = _Cell(n=10, p_hat=0.10, parent_p=0.5)
    lookup.cells_no_map[(3, 2, "atk")] = _Cell(n=10, p_hat=0.20, parent_p=0.5)
    lookup.cells_no_time[(3, 2, "atk", "Lotus")] = _Cell(
        n=10, p_hat=0.30, parent_p=0.5
    )
    lookup.cells_full[(3, 2, 0, "atk", "Lotus")] = _Cell(
        n=10, p_hat=0.40, parent_p=0.5
    )
    expected_full = (10 * 0.40 + SHRINK_PRIOR * 0.5) / (10 + SHRINK_PRIOR)
    assert math.isclose(
        lookup.post_plant_p(3, 2, 0, "atk", "Lotus"), expected_full, rel_tol=1e-12
    )


# --------------------------------------------------------------------------- #
# 7. JSON round-trip (D-06 — schema_version=2 + 4 cells_* dicts)              #
# --------------------------------------------------------------------------- #


def test_to_json_and_from_json_roundtrip(tmp_path: Path) -> None:
    """v2 round-trip: populated lookup serializes and reloads identically."""
    a = RoundConclusionLookup(side_baseline={"atk": 0.46, "def": 0.54})
    a.cells_minimal[(0, 0)] = _Cell(n=42, p_hat=0.51, parent_p=0.50)
    a.cells_minimal[(2, 1)] = _Cell(n=15, p_hat=0.63, parent_p=0.50)
    a.cells_no_map[(0, 0, "atk")] = _Cell(n=20, p_hat=0.49, parent_p=0.51)
    a.cells_no_time[(0, 0, "atk", "Lotus")] = _Cell(
        n=12, p_hat=0.55, parent_p=0.49
    )
    a.cells_full[(0, 0, 0, "atk", "Lotus")] = _Cell(
        n=8, p_hat=0.60, parent_p=0.55
    )

    out = tmp_path / "rc.json"
    a.to_json(out)
    b = RoundConclusionLookup.from_json(out)

    assert b.side_baseline == a.side_baseline
    assert b.cells_minimal == a.cells_minimal
    assert b.cells_no_map == a.cells_no_map
    assert b.cells_no_time == a.cells_no_time
    assert b.cells_full == a.cells_full


def test_to_json_writes_schema_version_2(tmp_path: Path) -> None:
    """to_json writes schema_version=2 at top level (D-06)."""
    import json

    a = RoundConclusionLookup()
    out = tmp_path / "rc.json"
    a.to_json(out)
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 2


def test_from_json_raises_filenotfound_on_missing(tmp_path: Path) -> None:
    """Phase 4 must distinguish 'no JSON file' from 'empty JSON' (Path C vs error)."""
    with pytest.raises(FileNotFoundError):
        RoundConclusionLookup.from_json(tmp_path / "does-not-exist.json")


# --------------------------------------------------------------------------- #
# 8. frozen=True (Pattern S3 — blocks reassignment, not dict mutation)        #
# --------------------------------------------------------------------------- #


def test_frozen_blocks_field_reassignment() -> None:
    """`frozen=True` raises FrozenInstanceError on field reassignment."""
    lookup = RoundConclusionLookup()
    with pytest.raises(dataclasses.FrozenInstanceError):
        lookup.cells_full = {}  # type: ignore[misc]


def test_frozen_allows_dict_mutation_for_calibrator_population() -> None:
    """Phase 3 v2 calibrator (03-07) populates cells via dict mutation.

    `frozen=True` blocks reassignment of the field reference, NOT mutation of
    the dict object the field points to. This is the Python idiom; verifying
    here so 03-07 doesn't get a surprise.
    """
    lookup = RoundConclusionLookup()
    cell = _Cell(n=10, p_hat=0.6, parent_p=0.5)
    lookup.cells_full[(3, 2, 0, "atk", "Lotus")] = cell
    assert lookup.cells_full[(3, 2, 0, "atk", "Lotus")] is cell
