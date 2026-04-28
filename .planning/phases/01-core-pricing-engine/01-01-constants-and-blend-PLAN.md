---
phase: 01-core-pricing-engine
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/config/constants.py
  - tests/config/test_constants.py
  - src/pricing/blend.py
  - tests/pricing/__init__.py
  - tests/pricing/test_blend.py
autonomous: true
requirements:
  - REQ-bradley-terry-blend
must_haves:
  truths:
    - "Bradley-Terry blend, not arithmetic mean (DEC-003 / CRule 3)"
    - "Conviction clip [0.01, 0.99] uniform (DEC-012 / CRule 6)"
    - "No magic numbers — every threshold in src/config/constants.py (CON-no-magic-numbers / CRule 12)"
    - "mypy --strict on src/pricing/ (CON-mypy-strict-pricing / CRule 11)"
    - "Single canonical entry point: live_theo(state) → TheoOutput (DEC-010 / CRule 1)"
    - "BT_BLEND_EPSILON clip happens on inputs only — clipping outputs breaks symmetry (RESEARCH §3 Pitfall 4)"
    - "round_p(a, b) + round_p(b, a) == 1 algebraically (BT symmetry property, REQ acceptance)"
  outputs:
    - "src/config/constants.py exports four new Final-typed constants: CONVICTION_CLIP_LOW=0.01, CONVICTION_CLIP_HIGH=0.99, MIN_ROUNDS_FULL_WEIGHT=15, BT_BLEND_EPSILON=1e-6"
    - "tests/config/test_constants.py extended: EXPECTED_NAMES + EXPECTED_TYPES include the four new constants; three new value-invariant tests (clip subinterval, MIN_ROUNDS_FULL_WEIGHT positive int, BT_BLEND_EPSILON small positive float)"
    - "src/pricing/blend.py exports `def round_p(a_rate: float, b_rate_opposite_side: float) -> float` implementing `(a*(1-b)) / (a*(1-b) + (1-a)*b)` with input clip to [BT_BLEND_EPSILON, 1-BT_BLEND_EPSILON]"
    - "tests/pricing/__init__.py exists (one-line docstring)"
    - "tests/pricing/test_blend.py: 3 unit cases ((0.5,0.5)→0.5; (0.7,0.3)→49/58; (1.0,0.0)→saturated near 1) + hypothesis BT-symmetry property + boundary-clip no-NaN test"
    - "`uv run mypy --strict src/pricing/blend.py` exits 0"
    - "`uv run mypy --strict src/config/constants.py` exits 0"
    - "`uv run pytest tests/pricing/test_blend.py tests/config/test_constants.py -x` exits 0"
    - "`uv run ruff check src/pricing/blend.py src/config/constants.py tests/pricing/ tests/config/test_constants.py` exits 0"
---

<rationale>
Wave 1 entry plan (no Phase 1 dependencies — Phase 0 already shipped constants.py baseline). Sized to ~3 tasks because:
1. The four-constant extension is small (~40 LoC + 3 test functions) but is a hard prerequisite for ALL downstream pricing modules — must land first.
2. blend.py is ~30 LoC of pure math with a property-test that's straightforward but load-bearing (Bradley-Terry symmetry is the load-bearing fix per DEC-003 / PRD §12.2 #4).
3. tests/pricing/__init__.py + test_blend.py establish the test scaffolding that 01-02, 01-03, 01-04, 01-05 will all extend.

Diverges from researcher's "Constants extension + Bradley-Terry blend" combined recommendation only in adding the explicit `tests/pricing/__init__.py` task (researcher folded it into Wave 0 of 01-RESEARCH §Validation Architecture; we ship it here so all downstream test-files import cleanly without needing a separate scaffold step).

NO Plan 01-XX after this can use the four new constants until they land here. Wave 1 = ZERO Phase 1 dependencies.
</rationale>

<objective>
Land the four Phase 1 constants (`CONVICTION_CLIP_LOW`, `CONVICTION_CLIP_HIGH`, `MIN_ROUNDS_FULL_WEIGHT`, `BT_BLEND_EPSILON`) in `src/config/constants.py`, ship the Bradley-Terry round blend module (`src/pricing/blend.py`) that ALL downstream Phase 1 modules consume, and stand up the `tests/pricing/` test package with the BT property tests.

Purpose: Replace the audit engine's arithmetic-mean blend `(a + (1-b))/2` with the Bradley-Terry log-odds blend `a*(1-b) / (a*(1-b) + (1-a)*b)` (DEC-003 / CRule 3 / PRD §12.2 #4). This is the load-bearing fix for compounding edges — `(0.7, 0.3)` produces 0.84 under BT vs 0.70 under arithmetic mean. Locks four new constants per CON-no-magic-numbers (CRule 12) so no Phase 1 module ever inlines `0.01`, `0.99`, `15`, or `1e-6`.
Output: Module `src/pricing/blend.py` with `round_p`, four new constants, three test additions in `tests/config/test_constants.py`, full new `tests/pricing/test_blend.py`, and the `tests/pricing/` package marker.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/REQUIREMENTS.md
@.planning/phases/01-core-pricing-engine/01-CONTEXT.md
@.planning/phases/01-core-pricing-engine/01-RESEARCH.md
@.planning/phases/01-core-pricing-engine/01-PATTERNS.md
@CLAUDE.md
@prd.md
@roadmap.md
@src/config/constants.py
@tests/config/test_constants.py
@reference/theo_engine.py
@reference/fair_value.py
@pyproject.toml

<interfaces>
<!-- Patterns from existing Phase-0 source modules and reference salvage. Embedded so executor needs no codebase exploration. -->

From src/config/constants.py (existing block style — match exactly for new constants):
```python
SHRINK_PRIOR: Final[float] = 15.0
"""Bayesian prior weight in rounds for the round-conclusion lookup.

Source: DEC-007 / CLAUDE.md "Domain constants" / reference/theo_engine.py:37.
Re-fit in Phase 5 after 100+ matches of paper-trade data (REQ-calibration-loop).
"""
```

From tests/config/test_constants.py (existing pattern to extend at lines 23-40, 87-100, 119+):
```python
EXPECTED_NAMES: tuple[str, ...] = (
    # Pricing
    "SHRINK_PRIOR", "SIGNAL_SCALE", "GUN_WIN_RATE", "REGULATION_HALF", "WIN_THRESHOLD",
    # Sizing
    "KELLY_MULTIPLIER", "PER_MARKET_CAP_FRAC",
    # Kill switches
    "KILL_SWITCH_STALENESS_S", "KILL_SWITCH_DEVIATION_C",
    "KILL_SWITCH_BRIER_BOUND", "KILL_SWITCH_BRIER_WINDOW",
    # Mode flip
    "VEGA_DIRECTIONAL_THRESHOLD",
)

EXPECTED_TYPES: dict[str, type] = {
    "SHRINK_PRIOR": float, "SIGNAL_SCALE": float, ...
}

@pytest.mark.parametrize("name,expected_type", list(EXPECTED_TYPES.items()))
def test_constant_has_expected_type(name: str, expected_type: type) -> None:
    value = getattr(constants, name)
    assert not isinstance(value, bool), f"{name} must not be a bool"
    assert isinstance(value, expected_type), ...
```

From tests/config/__init__.py (analog for tests/pricing/__init__.py):
```python
"""Tests for src.config.* — threshold module sanity checks."""
```

The Bradley-Terry formula (CON-bradley-terry-formula / RESEARCH.md §3, ship verbatim):
```python
from src.config.constants import BT_BLEND_EPSILON

def round_p(a_rate: float, b_rate_opposite_side: float) -> float:
    a = max(BT_BLEND_EPSILON, min(1.0 - BT_BLEND_EPSILON, a_rate))
    b = max(BT_BLEND_EPSILON, min(1.0 - BT_BLEND_EPSILON, b_rate_opposite_side))
    return (a * (1.0 - b)) / (a * (1.0 - b) + (1.0 - a) * b)
```

The forbidden audit-engine arithmetic-mean line (NEVER appear in blend.py):
```python
# reference/theo_engine.py:161 — DROP per DEC-003 / PRD §12.2 #4
p = (a_rate + (1.0 - b_rate)) / 2.0
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Extend src/config/constants.py with four Phase 1 constants</name>
  <files>src/config/constants.py, tests/config/test_constants.py</files>

  <read_first>
    - src/config/constants.py (full file, ~145 lines) — observe the Final-typed `Source:` docstring pattern at lines 44-49, 51-56, 58-64
    - tests/config/test_constants.py (full file, ~175 lines) — extend EXPECTED_NAMES (lines 23-40), EXPECTED_TYPES (lines 87-100), and add value-invariant tests after line 119
    - .planning/phases/01-core-pricing-engine/01-RESEARCH.md §12 "CON-no-magic-numbers compliance — new constants" (lines 956-971)
    - .planning/phases/01-core-pricing-engine/01-PATTERNS.md "src/config/constants.py (modify)" section (lines 469-522) and "tests/config/test_constants.py (modify)" section (lines 525-574)
    - reference/theo_engine.py:36 (source of MIN_ROUNDS_FULL_WEIGHT=15)
  </read_first>

  <behavior>
    - Test 1: `from src.config.constants import CONVICTION_CLIP_LOW, CONVICTION_CLIP_HIGH, MIN_ROUNDS_FULL_WEIGHT, BT_BLEND_EPSILON` succeeds
    - Test 2: All four are present in `constants.__annotations__` with `Final[...]` annotations (test_no_unexpected_uppercase_names_leak_in must continue to pass after adding to EXPECTED_NAMES)
    - Test 3: Types match — float for clips and epsilon, int for MIN_ROUNDS_FULL_WEIGHT
    - Test 4 (clip subinterval invariant): `0.0 < CONVICTION_CLIP_LOW < 0.5`, `0.5 < CONVICTION_CLIP_HIGH < 1.0`, `CONVICTION_CLIP_LOW + CONVICTION_CLIP_HIGH == pytest.approx(1.0)`
    - Test 5: `MIN_ROUNDS_FULL_WEIGHT > 0`
    - Test 6: `0.0 < BT_BLEND_EPSILON < 0.01` (small positive float)
  </behavior>

  <action>
Append four new Final-typed constants to `src/config/constants.py` immediately after the `WIN_THRESHOLD` block (line 77, end of the Pricing section, before the `# --- Sizing ---` divider at line 79). Use the EXACT Final-typed-with-`Source:`-block pattern that the existing constants follow. Concrete code to insert:

```python
CONVICTION_CLIP_LOW: Final[float] = 0.01
"""Lower bound for theo_series and theo_map[i] clip at live_theo output.

Source: DEC-012 / CLAUDE.md rule 6 / CON-conviction-clip / 01-RESEARCH.md §12.
Replaces the audit engine's heterogeneous `[0.05, 0.95]` and `[0.03, 0.97]`
clips with a unified, wider `[0.01, 0.99]` band (PRD §12.2 #1).
"""

CONVICTION_CLIP_HIGH: Final[float] = 0.99
"""Upper bound for theo_series and theo_map[i] clip at live_theo output.

Source: DEC-012 / CLAUDE.md rule 6 / CON-conviction-clip / 01-RESEARCH.md §12.
"""

MIN_ROUNDS_FULL_WEIGHT: Final[int] = 15
"""Effective rounds for full data confidence in the audit-engine `_data_weight`
formula (D-09). Min-over-teams normalizer for confidence aggregation.

Source: reference/theo_engine.py:36 / D-09 / 01-RESEARCH.md §12. Used by
src/pricing/live_theo.py::_data_weight_for_map only.
"""

BT_BLEND_EPSILON: Final[float] = 1e-6
"""Bradley-Terry blend input clip — protects against 0/0 at boundary inputs.

Source: CON-bradley-terry-formula / 01-RESEARCH.md §3 (Pitfall 4) / §12.
Inputs to blend.round_p are clipped to [BT_BLEND_EPSILON, 1 - BT_BLEND_EPSILON]
BEFORE the formula. Output is NEVER clipped — that breaks BT symmetry.
"""
```

DO NOT add `OT_TOTAL_HARDSTOP` (per RESEARCH §12 final recommendation — `dp.py` will use `REGULATION_HALF * 2` inline so the relationship stays explicit).

Then update `tests/config/test_constants.py`:

1. Append four new entries to `EXPECTED_NAMES` after `"WIN_THRESHOLD"` (line 29) and BEFORE the `# Sizing` comment block:
```python
    "CONVICTION_CLIP_LOW",
    "CONVICTION_CLIP_HIGH",
    "MIN_ROUNDS_FULL_WEIGHT",
    "BT_BLEND_EPSILON",
```

2. Append four entries to `EXPECTED_TYPES` (insert in the Pricing block at line ~92):
```python
    "CONVICTION_CLIP_LOW": float,
    "CONVICTION_CLIP_HIGH": float,
    "MIN_ROUNDS_FULL_WEIGHT": int,
    "BT_BLEND_EPSILON": float,
```

3. Add three new value-invariant tests after `test_regulation_half_and_win_threshold_match_valorant_rules` (line 139, before the Sizing-block tests):

```python
def test_conviction_clips_are_a_unit_subinterval() -> None:
    """DEC-012 / CRule 6 — clip band is a symmetric sub-interval of (0, 1)."""
    assert 0.0 < constants.CONVICTION_CLIP_LOW < 0.5
    assert 0.5 < constants.CONVICTION_CLIP_HIGH < 1.0
    assert constants.CONVICTION_CLIP_LOW + constants.CONVICTION_CLIP_HIGH == pytest.approx(1.0)


def test_min_rounds_full_weight_positive() -> None:
    """D-09 — `_data_weight` divisor must be a positive sample size."""
    assert constants.MIN_ROUNDS_FULL_WEIGHT > 0


def test_bt_blend_epsilon_is_a_small_positive_float() -> None:
    """CON-bradley-terry-formula — epsilon must be a tiny positive number."""
    assert 0.0 < constants.BT_BLEND_EPSILON < 0.01
```

Commit with message `feat(01-01): add Phase 1 constants (clips, MIN_ROUNDS_FULL_WEIGHT, BT_BLEND_EPSILON)`.
  </action>

  <verify>
    <automated>uv run mypy --strict src/config/constants.py &amp;&amp; uv run pytest tests/config/test_constants.py -x &amp;&amp; uv run ruff check src/config/constants.py tests/config/test_constants.py</automated>
  </verify>

  <acceptance_criteria>
    - `grep -q "CONVICTION_CLIP_LOW: Final\[float\] = 0.01" src/config/constants.py`
    - `grep -q "CONVICTION_CLIP_HIGH: Final\[float\] = 0.99" src/config/constants.py`
    - `grep -q "MIN_ROUNDS_FULL_WEIGHT: Final\[int\] = 15" src/config/constants.py`
    - `grep -q "BT_BLEND_EPSILON: Final\[float\] = 1e-6" src/config/constants.py`
    - `! grep -q "OT_TOTAL_HARDSTOP" src/config/constants.py` (not added per RESEARCH §12 final rec)
    - `grep -q '"CONVICTION_CLIP_LOW"' tests/config/test_constants.py`
    - `grep -q "test_conviction_clips_are_a_unit_subinterval" tests/config/test_constants.py`
    - `grep -q "test_min_rounds_full_weight_positive" tests/config/test_constants.py`
    - `grep -q "test_bt_blend_epsilon_is_a_small_positive_float" tests/config/test_constants.py`
    - `uv run pytest tests/config/test_constants.py -x` exits 0 (all 16+ tests pass — was 12 before, now 16)
    - `uv run mypy --strict src/config/constants.py` exits 0
    - `uv run ruff check src/config/constants.py tests/config/test_constants.py` exits 0
  </acceptance_criteria>

  <done>
    Four constants land in `src/config/constants.py` with Final-typed annotations and `Source:` docstrings. `tests/config/test_constants.py` extended to cover them. `mypy --strict`, `pytest`, and `ruff` all green. `test_no_unexpected_uppercase_names_leak_in` still passes (extras set is empty).
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Create tests/pricing/ package marker</name>
  <files>tests/pricing/__init__.py</files>

  <read_first>
    - tests/config/__init__.py (one-line docstring; ship analog)
    - .planning/phases/01-core-pricing-engine/01-PATTERNS.md "tests/pricing/__init__.py (scaffolding, new)" section (lines 578-590)
  </read_first>

  <behavior>
    - Test 1: `import tests.pricing` succeeds (file exists and is a valid Python module)
    - Test 2: Module docstring describes the test scope
  </behavior>

  <action>
Create `tests/pricing/__init__.py` with EXACTLY one line:

```python
"""Tests for src.pricing.* — DP, blend, round-types, round-conclusion, live_theo."""
```

This mirrors `tests/config/__init__.py` exactly (one-line docstring, no other code). Required so the four downstream test files in this plan-set (test_blend.py here, plus test_dp.py, test_round_types.py, test_round_conclusion.py, test_live_theo.py in later plans) all live in a discoverable Python package.

Commit alongside Task 3 (single commit `feat(01-01): add Bradley-Terry blend module + property tests`).
  </action>

  <verify>
    <automated>uv run python -c "import tests.pricing"</automated>
  </verify>

  <acceptance_criteria>
    - `test -f tests/pricing/__init__.py` (file exists)
    - `grep -q "Tests for src.pricing" tests/pricing/__init__.py`
    - `wc -l tests/pricing/__init__.py` reports ≤ 1 line of content (excluding trailing newline)
    - `uv run python -c "import tests.pricing"` exits 0
  </acceptance_criteria>

  <done>
    `tests/pricing/__init__.py` exists with the one-line docstring; test discovery treats `tests/pricing/` as a package.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Implement src/pricing/blend.py + tests/pricing/test_blend.py</name>
  <files>src/pricing/blend.py, tests/pricing/test_blend.py</files>

  <read_first>
    - src/pricing/__init__.py (current Phase-0 placeholder — observe docstring style; do NOT modify in this task — re-export wiring lands in 01-05)
    - src/config/constants.py (verify BT_BLEND_EPSILON is now exported per Task 1)
    - .planning/phases/01-core-pricing-engine/01-RESEARCH.md §3 "Bradley-Terry blend signature and edge cases" (lines 572-602)
    - .planning/phases/01-core-pricing-engine/01-PATTERNS.md "src/pricing/blend.py (math, new)" section (lines 63-95) and "tests/pricing/test_blend.py" section (lines 594-652)
    - reference/theo_engine.py lines 146-162 — DO NOT salvage `_round_win_prob` (uses arithmetic mean — DEC-003 forbids)
    - tests/config/test_constants.py — analog for parametrize style + section dividers
    - prd.md §12.2 #4 (the bug being fixed)
    - CLAUDE.md Critical Rule 3 (Bradley-Terry blend, not arithmetic mean)
  </read_first>

  <behavior>
    - Test 1 (unit, parametrized): `round_p(0.5, 0.5) == 0.5` (coin flip)
    - Test 2 (unit, parametrized): `round_p(0.7, 0.3) ≈ 49/58 ≈ 0.84483` (compounding edge — REQ-bradley-terry-blend acceptance)
    - Test 3 (unit): `round_p(1.0, 0.0)` is finite, no NaN, ≈ 1.0 (within 1e-6 due to BT_BLEND_EPSILON clip)
    - Test 4 (unit): `round_p(0.0, 1.0)` is finite, no NaN, ≈ 0.0
    - Test 5 (property, hypothesis): For `a, b ∈ [0.001, 0.999]`, `round_p(a, b) + round_p(b, a) == 1.0` within `rel_tol=1e-9` (BT symmetry)
    - Test 6 (property, hypothesis): For `a, b ∈ [0.001, 0.999]`, `0.0 ≤ round_p(a, b) ≤ 1.0` (range invariant)
    - Test 7 (regression): blend.py source does NOT contain the arithmetic-mean form `(a + (1 - b)) / 2`
  </behavior>

  <action>
Create `src/pricing/blend.py` with this EXACT content:

```python
"""Bradley-Terry round-win-probability blend.

Replaces the audit-engine arithmetic-mean blend ``(a + (1-b)) / 2`` with the
log-odds form ``a*(1-b) / (a*(1-b) + (1-a)*b)``.

Sources
-------
- DEC-003 / CLAUDE.md rule 3 / CON-bradley-terry-formula
- prd.md §12.2 #4 (audit-engine bug being fixed)
- roadmap.md §1.2 (acceptance criteria — see test_blend.py)
- 01-RESEARCH.md §3 (algebraic symmetry proof; clip-on-input rationale)

Why Bradley-Terry, not arithmetic mean
--------------------------------------
For ``(0.7, 0.3)`` (team A is 70% on its side, team B is 30% on its side, i.e.
team A's opponent gives up rounds at a 70% rate too), arithmetic mean returns
``(0.7 + 0.7) / 2 = 0.70``. Bradley-Terry returns ``0.49 / 0.58 ≈ 0.845``,
correctly capturing that compounding edges multiply rather than average.

Why clip inputs only, never outputs
-----------------------------------
``round_p(a, b) + round_p(b, a) == 1`` is required for downstream symmetry
(the DP relies on this in `series_value` recurrences). Clipping the OUTPUT
breaks this identity (``0.999... → 0.99`` does not pair with
``0.001... → 0.01`` for ``1 - x``). Clipping inputs symmetrically preserves
the algebra. See 01-RESEARCH.md §3 Pitfall 4.

The output clip ``[CONVICTION_CLIP_LOW, CONVICTION_CLIP_HIGH] = [0.01, 0.99]``
is applied in ``live_theo.py`` on the FINAL ``theo_series`` and per-map
probabilities, never on intermediate round probabilities.
"""

from __future__ import annotations

from src.config.constants import BT_BLEND_EPSILON


def round_p(a_rate: float, b_rate_opposite_side: float) -> float:
    """P(team A wins one round) given A's rate on its side and B's rate on opposite side.

    Args:
        a_rate: Team A's empirical win-rate on the side it plays this round.
            Must be in ``[0.0, 1.0]`` (will be clipped to
            ``[BT_BLEND_EPSILON, 1 - BT_BLEND_EPSILON]`` internally).
        b_rate_opposite_side: Team B's empirical win-rate on the OPPOSITE side
            (i.e., the side B plays while A is on `side`). Same bounds.

    Returns:
        ``(a*(1-b)) / (a*(1-b) + (1-a)*b)`` after BT_BLEND_EPSILON input clip.
        Always finite, in ``(0.0, 1.0)``. NEVER clipped on output (CON-bradley-
        terry-formula / 01-RESEARCH.md §3 Pitfall 4 — preserves BT symmetry
        ``round_p(a, b) + round_p(b, a) == 1``).

    Notes:
        DO NOT call this with the arithmetic-mean form. See module docstring.
    """
    a = max(BT_BLEND_EPSILON, min(1.0 - BT_BLEND_EPSILON, a_rate))
    b = max(BT_BLEND_EPSILON, min(1.0 - BT_BLEND_EPSILON, b_rate_opposite_side))
    return (a * (1.0 - b)) / (a * (1.0 - b) + (1.0 - a) * b)
```

Then create `tests/pricing/test_blend.py`:

```python
"""Property + unit tests for src.pricing.blend.

Verifies REQ-bradley-terry-blend acceptance criteria from roadmap §1.2:
  - round_p(0.5, 0.5) == 0.5 (coin flip)
  - round_p(0.7, 0.3) ≈ 0.845 (compounding edge — was 0.70 under audit's arithmetic mean)
  - round_p(1.0, 0.0) ≈ 1.0 (saturated, NaN-free via BT_BLEND_EPSILON clip)
  - Bradley-Terry symmetry: round_p(a, b) + round_p(b, a) == 1.0
  - Output is in [0.0, 1.0] for all valid inputs
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest
from hypothesis import given, strategies as st

from src.config.constants import BT_BLEND_EPSILON
from src.pricing.blend import round_p


# --------------------------------------------------------------------------- #
# 1. Unit cases (REQ-bradley-terry-blend acceptance)                          #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "a,b,expected",
    [
        (0.5, 0.5, 0.5),                   # coin flip
        (0.7, 0.3, 49.0 / 58.0),           # 0.84482... — compounding edge
        (0.6, 0.4, 0.36 / 0.52),           # 0.69230... — moderate edge
    ],
)
def test_round_p_unit_cases(a: float, b: float, expected: float) -> None:
    """REQ-bradley-terry-blend acceptance: known-value cases from roadmap §1.2."""
    assert math.isclose(round_p(a, b), expected, rel_tol=1e-9)


def test_round_p_saturation_high() -> None:
    """round_p(1.0, 0.0) is NaN-free and arbitrarily close to 1.0 (BT_BLEND_EPSILON clip)."""
    out = round_p(1.0, 0.0)
    assert not math.isnan(out)
    assert not math.isinf(out)
    assert out > 1.0 - 1e-6


def test_round_p_saturation_low() -> None:
    """round_p(0.0, 1.0) is NaN-free and arbitrarily close to 0.0."""
    out = round_p(0.0, 1.0)
    assert not math.isnan(out)
    assert not math.isinf(out)
    assert out < 1e-6


# --------------------------------------------------------------------------- #
# 2. Property tests (hypothesis)                                              #
# --------------------------------------------------------------------------- #


@given(
    a=st.floats(min_value=0.001, max_value=0.999),
    b=st.floats(min_value=0.001, max_value=0.999),
)
def test_round_p_bradley_terry_symmetry(a: float, b: float) -> None:
    """REQ-bradley-terry-blend: round_p(a, b) + round_p(b, a) == 1 (BT symmetry)."""
    assert math.isclose(round_p(a, b) + round_p(b, a), 1.0, rel_tol=1e-9)


@given(
    a=st.floats(min_value=0.0, max_value=1.0),
    b=st.floats(min_value=0.0, max_value=1.0),
)
def test_round_p_in_unit_interval(a: float, b: float) -> None:
    """Range invariant: round_p(a, b) ∈ [0.0, 1.0] for all reachable inputs."""
    out = round_p(a, b)
    assert 0.0 <= out <= 1.0
    assert not math.isnan(out)


# --------------------------------------------------------------------------- #
# 3. Regression — DEC-003 forbids arithmetic mean                             #
# --------------------------------------------------------------------------- #


def test_blend_source_does_not_contain_arithmetic_mean_form() -> None:
    """DEC-003 / CRule 3: arithmetic-mean blend (a + (1-b)) / 2 is forbidden."""
    src = Path("src/pricing/blend.py").read_text(encoding="utf-8")
    # Strip comments/docstrings: only check executable lines.
    code_lines = [
        line for line in src.splitlines()
        if line.strip() and not line.lstrip().startswith(("#", '"""', "'''"))
    ]
    code = "\n".join(code_lines)
    assert "(a_rate + (1.0 - b_rate)) / 2" not in code
    assert "(a + (1 - b)) / 2" not in code
    assert "(a_rate + (1 - b_rate)) / 2" not in code
```

Commit with message `feat(01-01): add Bradley-Terry blend module + property tests`.
  </action>

  <verify>
    <automated>uv run mypy --strict src/pricing/blend.py &amp;&amp; uv run pytest tests/pricing/test_blend.py -x &amp;&amp; uv run ruff check src/pricing/blend.py tests/pricing/test_blend.py</automated>
  </verify>

  <acceptance_criteria>
    - `test -f src/pricing/blend.py` (module exists)
    - `grep -q "def round_p(a_rate: float, b_rate_opposite_side: float) -> float:" src/pricing/blend.py`
    - `grep -qE "\(a \* \(1\.0 - b\)\) / \(a \* \(1\.0 - b\) \+ \(1\.0 - a\) \* b\)" src/pricing/blend.py` (Bradley-Terry formula present)
    - `grep -q "BT_BLEND_EPSILON" src/pricing/blend.py` (epsilon imported and used)
    - `! grep -E "\(a_rate \+ \(1\.0? - b_rate\)\) / 2" src/pricing/blend.py` (arithmetic mean NOT present in source)
    - `! grep -E "\(a \+ \(1 - b\)\) / 2" src/pricing/blend.py`
    - `test -f tests/pricing/test_blend.py`
    - `grep -q "test_round_p_bradley_terry_symmetry" tests/pricing/test_blend.py`
    - `grep -q "test_round_p_unit_cases" tests/pricing/test_blend.py`
    - `grep -q "test_round_p_saturation_high" tests/pricing/test_blend.py`
    - `grep -q "test_blend_source_does_not_contain_arithmetic_mean_form" tests/pricing/test_blend.py`
    - `uv run mypy --strict src/pricing/blend.py` exits 0
    - `uv run pytest tests/pricing/test_blend.py -x` exits 0
    - `uv run ruff check src/pricing/blend.py tests/pricing/test_blend.py` exits 0
  </acceptance_criteria>

  <done>
    `src/pricing/blend.py` exports a single function `round_p(a_rate, b_rate_opposite_side)` implementing the Bradley-Terry log-odds blend with input clipping to `[BT_BLEND_EPSILON, 1-BT_BLEND_EPSILON]`. Three unit cases, two hypothesis property tests (symmetry + range), and a regression test (no arithmetic-mean form) all pass under `mypy --strict`. Phase 1's load-bearing math fix (DEC-003) is locked.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Pricing API ↔ caller | `live_theo` consumers (Phase 4 quoting, tests) feed `MatchState` and `HalfRates` into `round_p`. Inputs may include floats outside `[0, 1]` (test fixtures, malformed half_rates) — the blend must not produce NaN. |
| `src/config/constants.py` ↔ all of `src/` | Read-only Final-typed module. Reassignment is a type error (`mypy --strict`). |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-01-01-01 | Tampering | `src/pricing/blend.py::round_p` (NaN propagation from boundary inputs) | mitigate | Input clip to `[BT_BLEND_EPSILON, 1 - BT_BLEND_EPSILON]` before formula; explicit unit tests for `(0.0, 1.0)` and `(1.0, 0.0)` cases assert no NaN in output |
| T-01-01-02 | Tampering | `src/config/constants.py` (silent reassignment of constants by another module) | mitigate | All four new constants typed `Final[...]` so `mypy --strict` blocks reassignment at compile time; `test_no_unexpected_uppercase_names_leak_in` regression-locks the EXPECTED_NAMES contract |
| T-01-01-03 | Tampering | `src/pricing/blend.py` (regression to arithmetic-mean blend during refactor) | mitigate | `test_blend_source_does_not_contain_arithmetic_mean_form` greps the source file at test time; failure surfaces immediately on commit |
| T-01-01-04 | Information Disclosure | constants module | accept | No PII, no secrets — empirical thresholds are public design constants documented in `prd.md` |
</threat_model>

<verification>
After all three tasks complete:

```bash
uv run mypy --strict src/pricing/blend.py src/config/constants.py
uv run pytest tests/pricing/test_blend.py tests/config/test_constants.py -x
uv run ruff check src/pricing/ src/config/ tests/pricing/ tests/config/
```

All three commands MUST exit 0.

Additional sanity:
- `python -c "from src.pricing.blend import round_p; print(round_p(0.5, 0.5))"` prints exactly `0.5`
- `python -c "from src.pricing.blend import round_p; print(round_p(0.7, 0.3))"` prints `0.8448275862068966`
- `python -c "from src.config.constants import CONVICTION_CLIP_LOW, CONVICTION_CLIP_HIGH, MIN_ROUNDS_FULL_WEIGHT, BT_BLEND_EPSILON"` exits 0 with no output
</verification>

<success_criteria>
- All four constants (`CONVICTION_CLIP_LOW`, `CONVICTION_CLIP_HIGH`, `MIN_ROUNDS_FULL_WEIGHT`, `BT_BLEND_EPSILON`) are importable from `src.config.constants` with `Final[...]` annotations
- `src.pricing.blend.round_p` returns Bradley-Terry blend with verified accuracy: `(0.5,0.5)→0.5`, `(0.7,0.3)→49/58`, `(1.0,0.0)→1-1e-6 < x < 1`, `(0.0,1.0)→0 < x < 1e-6`
- BT symmetry holds: `round_p(a, b) + round_p(b, a) == 1` within `1e-9` for all `a, b ∈ [0.001, 0.999]`
- `tests/pricing/__init__.py` exists; `tests/pricing/` is a discoverable Python package
- `mypy --strict src/pricing/`, `mypy --strict src/config/`, `ruff check`, and full `pytest tests/pricing/ tests/config/` are all green
- The arithmetic-mean form `(a + (1-b)) / 2` does not appear anywhere in `src/pricing/blend.py` (regression test passes)
- Phase 0 tests still pass (no regression in `tests/test_smoke.py`, `tests/test_main.py`)
</success_criteria>

<output>
After completion, create `.planning/phases/01-core-pricing-engine/01-01-constants-and-blend-SUMMARY.md`.

The SUMMARY must record:
- Final values of the four constants (and confirmation that `OT_TOTAL_HARDSTOP` was deliberately NOT added)
- The Bradley-Terry formula as shipped (one line: `(a * (1.0 - b)) / (a * (1.0 - b) + (1.0 - a) * b)`)
- Confirmation that `tests/pricing/__init__.py` lives so downstream test files can import
- Test counts: 3 new in `test_constants.py`, 7 new in `test_blend.py` (3 unit + 2 hypothesis + 2 saturation/regression)
- No surprises / no decisions deviated from CONTEXT.md
- Commit SHAs for the two atomic commits
</output>
