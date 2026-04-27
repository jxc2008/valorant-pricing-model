---
phase: 00-foundation
plan: 02
type: execute
wave: 2
depends_on: [01]
files_modified:
  - src/config/constants.py
  - tests/config/__init__.py
  - tests/config/test_constants.py
autonomous: true
requirements: []
must_haves:
  truths:
    - "DEC-016 / CON-no-magic-numbers — every PRD threshold has a single home in `src/config/constants.py`"
    - "CON-domain-constants-baseline — `SHRINK_PRIOR=15.0`, `SIGNAL_SCALE=0.10`, `GUN_WIN_RATE=0.822`, `KELLY_MULTIPLIER=0.5`, `PER_MARKET_CAP_FRAC=0.05` (TBD-marked), `VEGA_DIRECTIONAL_THRESHOLD=0.04` (TBD-marked), `KILL_SWITCH_STALENESS_S=5.0`, `KILL_SWITCH_DEVIATION_C=20`, `KILL_SWITCH_BRIER_BOUND=0.30`, `KILL_SWITCH_BRIER_WINDOW=50`, `REGULATION_HALF=12`, `WIN_THRESHOLD=13` all declared with the exact literal values"
    - "DEC-005 / CON-domain-constants-baseline — kill-switch constants use the user-resolved `KILL_SWITCH_*` prefix (NOT the older `KILL_*` form from CLAUDE.md)"
    - "CON-mypy-strict-pricing — constants module type-checks under `mypy --strict` (every constant has an explicit `: Final[type] = value` annotation)"
    - "ROADMAP Phase 0 must-have #3 satisfied: `src/config/constants.py` declares the full baseline value set per DEC-016 / CON-domain-constants-baseline"
  artifacts:
    - path: "src/config/constants.py"
      provides: "Canonical thresholds module — single import surface for every magic number in the system"
      exports:
        - "SHRINK_PRIOR"
        - "SIGNAL_SCALE"
        - "GUN_WIN_RATE"
        - "REGULATION_HALF"
        - "WIN_THRESHOLD"
        - "KELLY_MULTIPLIER"
        - "PER_MARKET_CAP_FRAC"
        - "KILL_SWITCH_STALENESS_S"
        - "KILL_SWITCH_DEVIATION_C"
        - "KILL_SWITCH_BRIER_BOUND"
        - "KILL_SWITCH_BRIER_WINDOW"
        - "VEGA_DIRECTIONAL_THRESHOLD"
      contains: "module docstring referencing DEC-016 / CON-no-magic-numbers; section comments for Pricing / Sizing / Kill switches / Mode flip; `Final` annotation on every constant"
    - path: "tests/config/__init__.py"
      provides: "tests.config subpackage marker"
    - path: "tests/config/test_constants.py"
      provides: "Smoke tests asserting every constant is importable, of the documented type, and within sensible invariants"
      contains: "test_all_constants_importable, test_constant_types, test_constant_value_invariants"
  key_links:
    - from: "src/config/constants.py"
      to: "Future src/pricing/, src/sizing/, src/quoting/ business logic"
      via: "explicit `from src.config.constants import KELLY_MULTIPLIER` etc."
      pattern: "from src\\.config\\.constants import"
    - from: "tests/config/test_constants.py"
      to: "src/config/constants.py"
      via: "imports every public name from the constants module and asserts type + range"
      pattern: "from src\\.config\\.constants import"
---

<objective>
Create the canonical magic-numbers module `src/config/constants.py` containing every threshold from PRD §6 / CLAUDE.md "Domain constants" / roadmap.md §0.4 with EXACT values, organized into four labeled sections (Pricing, Sizing, Kill switches, Mode flip), each constant typed with `Final[...]` so `mypy --strict` accepts it. Add a small `tests/config/test_constants.py` that imports every name and asserts type + value invariants.

Purpose: This is the foundation for CON-no-magic-numbers (DEC-016 / CLAUDE.md rule 12). Every downstream plan in Phases 1–7 imports from this module instead of hardcoding. Without this in place, downstream plans will scatter literals across business logic and the rule cannot be enforced retroactively without painful refactors.

Output: `src/config/constants.py` is the single import surface for thresholds; `mypy --strict src/pricing/` still passes (will be exercised once Phase 1 imports from here); `tests/config/test_constants.py` proves every constant is wired and within invariants.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/intel/constraints.md
@.planning/intel/decisions.md
@.planning/codebase/CONVENTIONS.md
@CLAUDE.md
@roadmap.md
@.planning/phases/00-foundation/00-01-SUMMARY.md

<interfaces>
<!-- This plan defines the constants contract that all downstream phases consume.
     The exports below ARE the contract. Do not deviate. -->

Constant import contract — downstream plans rely on these EXACT names, types, and values:

```python
# Pricing
SHRINK_PRIOR: Final[float] = 15.0           # Bayesian prior weight in rounds (DEC-007 / CLAUDE.md L67)
SIGNAL_SCALE: Final[float] = 0.10           # |model_p - 0.5| / scale → weight in [0,1] (CLAUDE.md L68)
GUN_WIN_RATE: Final[float] = 0.822          # P(gun team wins eco round) — empirical (DEC-011 / CLAUDE.md L69)
REGULATION_HALF: Final[int] = 12            # Rounds per half (CLAUDE.md L70)
WIN_THRESHOLD: Final[int] = 13              # Rounds needed to win a map (CLAUDE.md L71)

# Sizing (DEC-004 / CLAUDE.md L74-L75)
KELLY_MULTIPLIER: Final[float] = 0.5        # Half-Kelly per CLAUDE.md rule 7
PER_MARKET_CAP_FRAC: Final[float] = 0.05    # TBD — depends on bankroll (PRD §9.1)

# Kill switches (DEC-005 / CON-domain-constants-baseline — KILL_SWITCH_* prefix locked)
KILL_SWITCH_STALENESS_S: Final[float] = 5.0     # CLAUDE.md rule 9
KILL_SWITCH_DEVIATION_C: Final[int] = 20        # cents (CLAUDE.md rule 9)
KILL_SWITCH_BRIER_BOUND: Final[float] = 0.30    # CLAUDE.md rule 9
KILL_SWITCH_BRIER_WINDOW: Final[int] = 50       # rounds (CLAUDE.md rule 9)

# Mode flip
VEGA_DIRECTIONAL_THRESHOLD: Final[float] = 0.04 # TBD — calibrate after 20+ matches (PRD §9.2)
```

Naming-prefix note: CLAUDE.md "Domain constants" lines 80-83 use the shorter `KILL_*` prefix.
roadmap.md §0.4, intel/constraints.md (CON-domain-constants-baseline), and intel/decisions.md
(DEC-005 corroborating note "Constants prefixed `KILL_SWITCH_*` per roadmap.md §0.4 — user-resolved
2026-04-27") all use `KILL_SWITCH_*`. The user's resolution as of 2026-04-27 LOCKS `KILL_SWITCH_*`.
This plan implements `KILL_SWITCH_*` — CLAUDE.md will be updated to match in a separate doc-fix
PR (NOT this plan; this plan only writes code).
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Write src/config/constants.py with all 12 thresholds, fully typed and sectioned</name>
  <files>src/config/constants.py</files>
  <read_first>
    - CLAUDE.md ("Domain constants" code block, lines ~67-87 — gives source values; note `KILL_*` prefix is the OLDER form being superseded by `KILL_SWITCH_*`)
    - .planning/intel/constraints.md (CON-domain-constants-baseline — gives the canonical `KILL_SWITCH_*` names + the TBD markings; CON-no-magic-numbers; CON-mypy-strict-pricing)
    - .planning/intel/decisions.md (DEC-016 magic-number policy; DEC-005 kill-switch naming; DEC-011 GUN_WIN_RATE rationale; DEC-007 SHRINK_PRIOR / SIGNAL_SCALE rationale; DEC-004 KELLY_MULTIPLIER / PER_MARKET_CAP_FRAC rationale)
    - roadmap.md (§0.4 — gives the canonical `KILL_SWITCH_*` prefix and the order of constants)
    - .planning/codebase/CONVENTIONS.md (Naming Patterns / Variables / Authoritative Constants section — confirms UPPER_SNAKE_CASE convention and the prefix gap; Anti-Patterns to Avoid #6 — class-attribute thresholds are forbidden)
    - .planning/codebase/STRUCTURE.md ("src/config/" → "constants.py is the entire layer. No magic numbers anywhere else.")
  </read_first>
  <action>
Use the Write tool. Create `src/config/constants.py` with EXACTLY the following content (preserve every comment, every blank line, every annotation; do not paraphrase docstrings):

```python
"""Canonical thresholds and magic numbers for the Valorant pricing model.

This module is the SINGLE source of truth for every threshold the system uses
(DEC-016, CLAUDE.md rule 12, CON-no-magic-numbers).

Rules
-----
1. No business logic anywhere else in `src/` may hardcode any of these values.
   Always import: ``from src.config.constants import KELLY_MULTIPLIER``.
2. Tuning these values is a Phase 5 activity (calibration loop, REQ-calibration-loop).
   Initial values below ship with documented sources; do not change without
   updating the citing doc (`prd.md` or `roadmap.md`) first.
3. Constants marked ``# TBD`` are intentional initial guesses, gated on future
   calibration data — see PRD §9 "Open TBDs" and STATE.md "Open TBDs".

Source of truth
---------------
- ``prd.md`` §6, §9 (locked decisions and open TBDs)
- ``roadmap.md`` §0.4 (Phase 0 — Configuration block; canonical KILL_SWITCH_* prefix)
- ``CLAUDE.md`` "Domain constants" (project-instructions encoding of PRD intent)
- ``.planning/intel/constraints.md`` CON-domain-constants-baseline
- ``.planning/intel/decisions.md`` DEC-004, DEC-005, DEC-007, DEC-011, DEC-016

Naming
------
``UPPER_SNAKE_CASE`` for all module-level constants. Kill-switch constants use the
``KILL_SWITCH_*`` prefix per roadmap.md §0.4 (user-resolved 2026-04-27); the
shorter ``KILL_*`` form in CLAUDE.md "Domain constants" is the older form and
will be reconciled in a doc-fix PR.

Type annotations
----------------
Every constant uses ``typing.Final[...]`` so ``mypy --strict`` (enforced on
``src/pricing/`` per CON-mypy-strict-pricing) treats reassignment as an error.
"""

from __future__ import annotations

from typing import Final

# --------------------------------------------------------------------------- #
# Pricing                                                                     #
# --------------------------------------------------------------------------- #

SHRINK_PRIOR: Final[float] = 15.0
"""Bayesian prior weight in rounds for the round-conclusion lookup.

Source: DEC-007 / CLAUDE.md "Domain constants" / reference/theo_engine.py:37.
Re-fit in Phase 5 after 100+ matches of paper-trade data (REQ-calibration-loop).
"""

SIGNAL_SCALE: Final[float] = 0.10
"""Signal-strength scale: ``|model_p - 0.5| / SIGNAL_SCALE`` clipped to ``[0, 1]``.

Source: CLAUDE.md "Domain constants" / reference/theo_engine.py:38.
Used by the round-conclusion shrinkage layer to weight cell vs parent estimates.
"""

GUN_WIN_RATE: Final[float] = 0.822
"""Population mean ``P(team with rifles wins an eco round)``.

Source: DEC-011 / CLAUDE.md "Domain constants" / prd.md §6 Tier 1.
Used by the pistol+anti-eco round model (REQ-pistol-anti-eco-modeling) for
rounds 2, 3, 14, 15 conditional on the prior-pistol outcome.
"""

REGULATION_HALF: Final[int] = 12
"""Rounds per half (Valorant standard).

Source: CLAUDE.md "Domain constants" / reference/theo_engine.py:34.
DP hard-stops at total = 24 (REGULATION_HALF * 2) per DEC-009 / CON-ot-hard-stop.
"""

WIN_THRESHOLD: Final[int] = 13
"""Rounds needed to win a map (Valorant standard, BO13).

Source: CLAUDE.md "Domain constants" / reference/theo_engine.py:35.
"""

# --------------------------------------------------------------------------- #
# Sizing                                                                      #
# --------------------------------------------------------------------------- #

KELLY_MULTIPLIER: Final[float] = 0.5
"""Half-Kelly multiplier applied to the full Kelly fraction before per-market cap.

Source: DEC-004 / CLAUDE.md rule 7.
``f = max(0, KELLY_MULTIPLIER * f_full)`` then ``f = min(f, PER_MARKET_CAP_FRAC)``.
NEVER full Kelly (CLAUDE.md rule 7).
"""

PER_MARKET_CAP_FRAC: Final[float] = 0.05  # TBD
"""Maximum fraction of bankroll allocated to a single Kalshi market.

Source: DEC-004 / CLAUDE.md "Domain constants".
TBD — depends on final bankroll allocation decision (PRD §9.1).
Initial value 0.05 is a placeholder; revisit when bankroll is fixed.
"""

# --------------------------------------------------------------------------- #
# Kill switches (DEC-005: all four always-on, no per-switch disable flag)     #
# --------------------------------------------------------------------------- #

KILL_SWITCH_STALENESS_S: Final[float] = 5.0
"""Ingestion-staleness kill-switch threshold, seconds.

If ``time.now() - state.last_updated_ts > KILL_SWITCH_STALENESS_S``, kill-switch (b)
trips and ``KalshiOrderManager.cancel_all_orders()`` is invoked.
Source: DEC-005 / CLAUDE.md rule 9 / PRD §5.4.
"""

KILL_SWITCH_DEVIATION_C: Final[int] = 20
"""Theo-vs-market deviation kill-switch threshold, cents.

If ``abs(theo_cents - market_cents) > KILL_SWITCH_DEVIATION_C``, kill-switch (c)
trips. Suggests our model is materially mis-priced relative to other participants
or our state is wrong; either way, stop trading.
Source: DEC-005 / CLAUDE.md rule 9 / PRD §5.4.
"""

KILL_SWITCH_BRIER_BOUND: Final[float] = 0.30
"""Rolling-Brier kill-switch upper bound (over the most recent
``KILL_SWITCH_BRIER_WINDOW`` round predictions).

If realized rolling Brier exceeds this bound, kill-switch (d) trips.
Source: DEC-005 / CLAUDE.md rule 9 / PRD §5.4.
"""

KILL_SWITCH_BRIER_WINDOW: Final[int] = 50
"""Number of round predictions in the rolling-Brier window.

Source: DEC-005 / CLAUDE.md rule 9 / PRD §5.4.
"""

# --------------------------------------------------------------------------- #
# Mode flip                                                                   #
# --------------------------------------------------------------------------- #

VEGA_DIRECTIONAL_THRESHOLD: Final[float] = 0.04  # TBD
"""Vega threshold above which the trading mode flips from MM to DIRECTIONAL.

Source: DEC-001 / CLAUDE.md "Domain constants" / roadmap.md §4.2.
TBD — initial guess; calibrate after 20+ live matches (PRD §9.2,
REQ-calibration-loop).
"""
```

Notes for the executor:
- The `from __future__ import annotations` is present per CONVENTIONS.md "`__future__` imports" recommendation for new code in `src/`.
- `Final[...]` annotations are MANDATORY for `mypy --strict` to detect accidental reassignment. Do not omit them or replace with bare type annotations.
- The blank-line layout matches PEP 8 + ruff defaults; do not collapse the section banners.
- Do NOT add `__all__` — per CONVENTIONS.md "Exports" (no `__all__` declared; consistent with reference/ style).
- After writing, run `uv run mypy --strict src/pricing/` and `uv run mypy --strict src/config/` to confirm no type errors. The pricing strict override doesn't catch src/config by default; add a one-shot manual check on src/config/constants.py to be safe.
  </action>
  <verify>
    <automated>test -f src/config/constants.py &amp;&amp; grep -q '^SHRINK_PRIOR: Final\[float\] = 15\.0$' src/config/constants.py &amp;&amp; grep -q '^SIGNAL_SCALE: Final\[float\] = 0\.10$' src/config/constants.py &amp;&amp; grep -q '^GUN_WIN_RATE: Final\[float\] = 0\.822$' src/config/constants.py &amp;&amp; grep -q '^REGULATION_HALF: Final\[int\] = 12$' src/config/constants.py &amp;&amp; grep -q '^WIN_THRESHOLD: Final\[int\] = 13$' src/config/constants.py &amp;&amp; grep -q '^KELLY_MULTIPLIER: Final\[float\] = 0\.5$' src/config/constants.py &amp;&amp; grep -q '^PER_MARKET_CAP_FRAC: Final\[float\] = 0\.05  # TBD$' src/config/constants.py &amp;&amp; grep -q '^KILL_SWITCH_STALENESS_S: Final\[float\] = 5\.0$' src/config/constants.py &amp;&amp; grep -q '^KILL_SWITCH_DEVIATION_C: Final\[int\] = 20$' src/config/constants.py &amp;&amp; grep -q '^KILL_SWITCH_BRIER_BOUND: Final\[float\] = 0\.30$' src/config/constants.py &amp;&amp; grep -q '^KILL_SWITCH_BRIER_WINDOW: Final\[int\] = 50$' src/config/constants.py &amp;&amp; grep -q '^VEGA_DIRECTIONAL_THRESHOLD: Final\[float\] = 0\.04  # TBD$' src/config/constants.py &amp;&amp; uv run mypy --strict src/config/constants.py &amp;&amp; uv run ruff check src/config/constants.py</automated>
  </verify>
  <done>
    `src/config/constants.py` contains all 12 constants with EXACT names and values from the action block, each typed `Final[...]`, organized into four sections (Pricing / Sizing / Kill switches / Mode flip), with module docstring referencing DEC-016 + CON-no-magic-numbers + the source-of-truth doc list. `uv run mypy --strict src/config/constants.py` exits 0. `uv run ruff check src/config/constants.py` exits 0.
  </done>
</task>

<task type="auto">
  <name>Task 2: Add tests/config/test_constants.py asserting every constant is importable, typed, and within range invariants</name>
  <files>tests/config/__init__.py, tests/config/test_constants.py</files>
  <read_first>
    - src/config/constants.py (the file just created in Task 1 — names, types, values must match)
    - .planning/codebase/CONVENTIONS.md (test-naming hint: `test_<concept>.py` mirroring source path; pytest-style functions, no test classes)
    - pyproject.toml (the `[tool.pytest.ini_options]` block for test discovery)
  </read_first>
  <action>
**Step A — Create `tests/config/__init__.py`**:
```python
"""Tests for src.config.* — threshold module sanity checks."""
```

**Step B — Create `tests/config/test_constants.py`** with the following content:
```python
"""Smoke tests for src.config.constants.

These tests are NOT calibration tests — they verify only:
1. Every constant documented in CON-domain-constants-baseline is importable.
2. Each constant has the documented type.
3. Each constant satisfies the obvious sanity invariants (probabilities in
   [0, 1], rounds positive, fractions in (0, 1], etc.).

Tuning of these values happens in Phase 5 (REQ-calibration-loop). Updates to
the values must update both `src/config/constants.py` AND this test.
"""

from __future__ import annotations

import pytest

from src.config import constants as C


# --------------------------------------------------------------------------- #
# 1. Importability                                                            #
# --------------------------------------------------------------------------- #

EXPECTED_NAMES: tuple[str, ...] = (
    # Pricing
    "SHRINK_PRIOR",
    "SIGNAL_SCALE",
    "GUN_WIN_RATE",
    "REGULATION_HALF",
    "WIN_THRESHOLD",
    # Sizing
    "KELLY_MULTIPLIER",
    "PER_MARKET_CAP_FRAC",
    # Kill switches
    "KILL_SWITCH_STALENESS_S",
    "KILL_SWITCH_DEVIATION_C",
    "KILL_SWITCH_BRIER_BOUND",
    "KILL_SWITCH_BRIER_WINDOW",
    # Mode flip
    "VEGA_DIRECTIONAL_THRESHOLD",
)


def test_all_expected_constants_are_importable() -> None:
    """Every name in EXPECTED_NAMES must be present and non-None on the module."""
    missing: list[str] = []
    for name in EXPECTED_NAMES:
        if not hasattr(C, name):
            missing.append(name)
        elif getattr(C, name) is None:
            missing.append(f"{name} (is None)")
    assert not missing, f"Constants module is missing: {missing}"


def test_no_unexpected_uppercase_names_leak_in() -> None:
    """Catch typos / accidental new constants that weren't added to EXPECTED_NAMES."""
    actual_uppercase = {
        n
        for n in dir(C)
        if n.isupper() and not n.startswith("_") and not callable(getattr(C, n))
    }
    expected = set(EXPECTED_NAMES)
    extras = actual_uppercase - expected
    assert not extras, (
        f"Unexpected UPPER_CASE names in constants module: {extras}. "
        f"If intentional, add to EXPECTED_NAMES in this test."
    )


# --------------------------------------------------------------------------- #
# 2. Types                                                                    #
# --------------------------------------------------------------------------- #

EXPECTED_TYPES: dict[str, type] = {
    "SHRINK_PRIOR": float,
    "SIGNAL_SCALE": float,
    "GUN_WIN_RATE": float,
    "REGULATION_HALF": int,
    "WIN_THRESHOLD": int,
    "KELLY_MULTIPLIER": float,
    "PER_MARKET_CAP_FRAC": float,
    "KILL_SWITCH_STALENESS_S": float,
    "KILL_SWITCH_DEVIATION_C": int,
    "KILL_SWITCH_BRIER_BOUND": float,
    "KILL_SWITCH_BRIER_WINDOW": int,
    "VEGA_DIRECTIONAL_THRESHOLD": float,
}


@pytest.mark.parametrize("name,expected_type", list(EXPECTED_TYPES.items()))
def test_constant_has_expected_type(name: str, expected_type: type) -> None:
    value = getattr(C, name)
    # `bool` is a subclass of int — reject it explicitly so a stray `True` literal
    # is caught as a type bug instead of silently passing as int.
    assert not isinstance(value, bool), f"{name} must not be a bool"
    assert isinstance(value, expected_type), (
        f"{name} expected {expected_type.__name__}, got {type(value).__name__}"
    )


# --------------------------------------------------------------------------- #
# 3. Value invariants                                                         #
# --------------------------------------------------------------------------- #


def test_shrink_prior_positive() -> None:
    assert C.SHRINK_PRIOR > 0


def test_signal_scale_in_unit_interval() -> None:
    # SIGNAL_SCALE divides |model_p - 0.5| (max 0.5) — values >0.5 would
    # always clip to weight 1 and be useless; values <=0 are nonsensical.
    assert 0.0 < C.SIGNAL_SCALE <= 0.5


def test_gun_win_rate_is_a_probability() -> None:
    assert 0.0 < C.GUN_WIN_RATE < 1.0
    # Sanity: GUN_WIN_RATE is empirical "rifles beat eco" — should be well above 0.5.
    assert C.GUN_WIN_RATE > 0.5


def test_regulation_half_and_win_threshold_match_valorant_rules() -> None:
    # Valorant: 12 rounds per half, 13 to win regulation.
    assert C.REGULATION_HALF == 12
    assert C.WIN_THRESHOLD == 13
    assert C.WIN_THRESHOLD == C.REGULATION_HALF + 1


def test_kelly_multiplier_is_half() -> None:
    # CLAUDE.md rule 7: half-Kelly. Anything else is a violation of the locked decision.
    assert C.KELLY_MULTIPLIER == 0.5


def test_per_market_cap_frac_is_a_small_fraction() -> None:
    assert 0.0 < C.PER_MARKET_CAP_FRAC <= 0.25  # 25% of bankroll on one market is the
    # generous upper bound for sanity; the actual locked initial value is 0.05.


def test_kill_switch_staleness_positive_seconds() -> None:
    assert C.KILL_SWITCH_STALENESS_S > 0


def test_kill_switch_deviation_positive_cents() -> None:
    assert C.KILL_SWITCH_DEVIATION_C > 0
    # Kalshi prices are 1-99 cents; a deviation > 99 would never trip.
    assert C.KILL_SWITCH_DEVIATION_C < 100


def test_kill_switch_brier_bound_in_unit_interval() -> None:
    # Brier scores for binary outcomes lie in [0, 1].
    # An upper bound of 0 would always trip; an upper bound of 1 would never.
    assert 0.0 < C.KILL_SWITCH_BRIER_BOUND < 1.0


def test_kill_switch_brier_window_is_positive_int() -> None:
    assert C.KILL_SWITCH_BRIER_WINDOW > 0


def test_vega_directional_threshold_in_unit_interval() -> None:
    # Vega here is variance of next theo update, theo in [0,1] => vega in [0, 0.25].
    assert 0.0 < C.VEGA_DIRECTIONAL_THRESHOLD <= 0.25
```

Notes for the executor:
- Use the Write tool for both files.
- After writing, run `uv run pytest tests/config/test_constants.py -v` and confirm ALL tests pass (the parametrize will produce 12 + 12 individual test cases for the type checks).
- Also run `uv run mypy --strict src/pricing/` (must still exit 0 — no regression from Plan 01) and `uv run ruff check tests/` (must exit 0).
  </action>
  <verify>
    <automated>test -f tests/config/__init__.py &amp;&amp; test -f tests/config/test_constants.py &amp;&amp; uv run pytest tests/config/test_constants.py -v &amp;&amp; uv run ruff check tests/config/ &amp;&amp; uv run mypy --strict src/pricing/</automated>
  </verify>
  <done>
    `tests/config/test_constants.py` contains: importability test + unexpected-extras test + parametrized type test (12 cases) + 10 value-invariant tests. `uv run pytest tests/config/test_constants.py` reports all tests passing (24+ test cases). `uv run ruff check tests/config/` exits 0. `uv run mypy --strict src/pricing/` exits 0 (regression check — Plan 01 contract still holds).
  </done>
</task>

</tasks>

<verification>
After both tasks complete:

```bash
# Constants file present with all 12 names
test -f src/config/constants.py
for name in SHRINK_PRIOR SIGNAL_SCALE GUN_WIN_RATE REGULATION_HALF WIN_THRESHOLD \
            KELLY_MULTIPLIER PER_MARKET_CAP_FRAC \
            KILL_SWITCH_STALENESS_S KILL_SWITCH_DEVIATION_C \
            KILL_SWITCH_BRIER_BOUND KILL_SWITCH_BRIER_WINDOW \
            VEGA_DIRECTIONAL_THRESHOLD; do
  grep -q "^${name}: Final\[" src/config/constants.py || echo "MISSING: ${name}"
done

# Test file passes
uv run pytest tests/config/test_constants.py -v   # all green

# Strict type check still passes on pricing (Plan 01 contract preserved)
uv run mypy --strict src/pricing/                 # exit 0

# Whole-repo ruff still clean
uv run ruff check .                               # exit 0

# Direct sanity check from REPL
uv run python -c "from src.config.constants import KILL_SWITCH_STALENESS_S, KELLY_MULTIPLIER, GUN_WIN_RATE; assert KILL_SWITCH_STALENESS_S == 5.0 and KELLY_MULTIPLIER == 0.5 and GUN_WIN_RATE == 0.822; print('ok')"
```
</verification>

<success_criteria>
1. `src/config/constants.py` exports all 12 constants with EXACT names, types (`Final[float]` / `Final[int]`), and values listed in the interfaces block.
2. Kill-switch constants use `KILL_SWITCH_*` prefix (NOT `KILL_*`) per user-resolved CON-domain-constants-baseline.
3. `PER_MARKET_CAP_FRAC` and `VEGA_DIRECTIONAL_THRESHOLD` carry the `# TBD` inline comment per the source docs.
4. `tests/config/test_constants.py` covers importability + unexpected-extras + type checks + value-range invariants for every constant.
5. `uv run pytest tests/config/test_constants.py` is fully green.
6. `uv run mypy --strict src/pricing/` is still green (Plan 01 contract preserved — no regression).
7. `uv run ruff check .` is still green for the whole repo.
</success_criteria>

<output>
After completion, create `.planning/phases/00-foundation/00-02-SUMMARY.md` covering:
- The full final contents of `src/config/constants.py` (or a unified diff vs. empty).
- The list of constants exported with their values and types.
- The pytest output for `tests/config/test_constants.py`.
- Note on the `KILL_*` vs `KILL_SWITCH_*` naming reconciliation: this plan uses `KILL_SWITCH_*` per the user-locked CON-domain-constants-baseline; CLAUDE.md "Domain constants" still shows the older `KILL_*` form and should be updated in a separate doc-fix PR after Phase 0 lands. Flag this for the project owner.
- Confirmation that the toolchain commands (`mypy --strict src/pricing/`, `ruff check .`, `pytest`) all remain green.
</output>
