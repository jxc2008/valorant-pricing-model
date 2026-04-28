# Phase 1: Core pricing engine - Pattern Map

**Mapped:** 2026-04-27
**Files analyzed:** 14 (6 new source, 6 new tests, 2 modified)
**Analogs found:** 14 / 14

Every Phase 1 file has a concrete intra-repo or salvage-source analog. No "no analog found" rows.

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/pricing/__init__.py` (modify) | scaffolding (package-marker) | n/a | `src/config/__init__.py` | exact |
| `src/pricing/blend.py` (new) | math (atomic transform) | request-response (pure fn) | `reference/fair_value.py:77-79` `_bo3_series_prob` + `src/config/constants.py` (Final-typed module style) | role-match |
| `src/pricing/round_types.py` (new) | math (dispatch) | request-response (pure fn) | `reference/theo_engine.py:146-162` `_round_win_prob` (signature shape only; semantics REPLACED per DEC-003) | role-match |
| `src/pricing/dp.py` (new) | math (memoized recursion + dataclass cache key) | batch (DP forward/backward) | `reference/theo_engine.py:168-206` `_markov_map_win` (loop structure salvage; bug-fix per DEC-003/009/011) | role-match |
| `src/pricing/round_conclusion.py` (new) | data-shape (hierarchical lookup skeleton) | request-response (pure fn) | `reference/theo_engine.py:84-102` `_get_rate` (Bayesian shrinkage formula) | role-match |
| `src/pricing/live_theo.py` (new) | service (orchestration) + data-shape (`MatchState`, `TheoOutput`) | request-response (pure orchestrator) | `src/main.py` (module structure, Final, docstring style) + `reference/theo_engine.py:104-129` `_data_weight` (helper salvage) | role-match |
| `tests/pricing/__init__.py` (new) | scaffolding | n/a | `tests/config/__init__.py` | exact |
| `tests/pricing/test_blend.py` (new) | test (unit + property) | n/a | `tests/config/test_constants.py` (param style) + `reference/fair_value.py` for fixtures | role-match |
| `tests/pricing/test_round_types.py` (new) | test (unit) | n/a | `tests/config/test_constants.py` (param style) | role-match |
| `tests/pricing/test_dp.py` (new) | test (property + range invariants) | n/a | `tests/test_main.py` (parametrize / caplog) + `reference/fair_value.py:77-79` (closed-form fixture) | role-match |
| `tests/pricing/test_round_conclusion.py` (new) | test (unit, skeleton-invariants) | n/a | `tests/config/test_constants.py` (importability + value invariants) | role-match |
| `tests/pricing/test_live_theo.py` (new) | test (integration over Phase 1 modules) | n/a | `tests/test_main.py` (multi-aspect contract test) | role-match |
| `src/config/constants.py` (modify) | config | n/a | self (existing pattern in same file) | exact |
| `tests/config/test_constants.py` (modify) | test (config) | n/a | self (existing pattern in same file) | exact |

---

## Pattern Assignments

### `src/pricing/__init__.py` (scaffolding, modify)

**Analog:** `src/pricing/__init__.py` itself (already shipped as a Phase 0 placeholder) and `src/config/__init__.py`.

**Current contents** (`src/pricing/__init__.py`, lines 1-7):
```python
"""Pricing layer — DP, Bradley-Terry blend, round-conclusion lookup, live_theo.

This package is type-checked under `mypy --strict` (CON-mypy-strict-pricing).
Every threshold imported here MUST come from `src.config.constants` (CLAUDE.md
rule 12). The single canonical pricing entry point is `live_theo` per DEC-010 —
do not introduce parallel `series_theo_*` variants.
"""
```

**What to copy:** Keep the docstring as-is; per CLAUDE.md "one canonical implementation per concept" the public re-exports should be added when the modules land.

**What to adapt:** Append a public re-export block at the bottom:
```python
from src.pricing.live_theo import live_theo, TheoOutput, MatchState

__all__ = ["live_theo", "TheoOutput", "MatchState"]
```
Rationale: only `live_theo` and its in/out dataclasses are public surface (DEC-010 / D-12 / D-14). `dp.py`, `blend.py`, `round_types.py`, `round_conclusion.py` stay private to the package — never re-exported.

**What to drop:** Nothing.

---

### `src/pricing/blend.py` (math, new)

**Analog A (module structure):** `src/config/constants.py:1-44`
**Analog B (function-level math):** `reference/fair_value.py:77-79` (a pure-function math module with `from __future__ import annotations` + minimal dependencies)

**Imports pattern** (mirror `src/config/constants.py:36-38`):
```python
"""Bradley-Terry round-win-probability blend.

Replaces the audit-engine arithmetic-mean blend `(a + (1-b)) / 2` with the
log-odds form `a*(1-b) / (a*(1-b) + (1-a)*b)` (DEC-003 / CRule 3 / RESEARCH §3).
"""

from __future__ import annotations

from src.config.constants import BT_BLEND_EPSILON
```

**Core pattern** (RESEARCH.md §3, lines 575-583):
```python
def round_p(a_rate: float, b_rate_opposite_side: float) -> float:
    """P(team A wins one round) given A's rate on its side and B's rate on opposite side."""
    a = max(BT_BLEND_EPSILON, min(1.0 - BT_BLEND_EPSILON, a_rate))
    b = max(BT_BLEND_EPSILON, min(1.0 - BT_BLEND_EPSILON, b_rate_opposite_side))
    return (a * (1.0 - b)) / (a * (1.0 - b) + (1.0 - a) * b)
```

**Validation pattern:** Input clip BEFORE the formula; never clip the output (RESEARCH §3 Pitfall 4 — clipping output breaks `round_p(a,b) + round_p(b,a) == 1` symmetry). Borrow this exact constraint into the docstring as a `Notes` section.

**Constants discipline:** Critical Rule 12 + CON-no-magic-numbers. The literal `1e-6` MUST come from `BT_BLEND_EPSILON`. No inline `0.99` / `0.01` either — those land in `live_theo.py` from `CONVICTION_CLIP_HIGH/LOW`.

**Drop from analog:** `reference/theo_engine.py:146-162` `_round_win_prob` is the wrong-blend version (PRD §12.2 #4); copy NOTHING from it. Only the `_round_win_prob` function name pattern (single-purpose round-prob fn) maps to `round_p`.

---

### `src/pricing/round_types.py` (math, new)

**Analog:** RESEARCH.md §4 (lines 605-645) — concrete dispatch per round number, plus `reference/theo_engine.py:146-162` for `team_a_side` / `team_b_side` derivation pattern (lines 158: `team_b_side = 'def' if team_a_side == 'atk' else 'atk'`).

**Imports pattern:**
```python
"""Pistol / anti-eco / gunround round-type dispatch.

Resolves P(team A wins this round) per round number, conditional on
`pistol_winner_a` for rounds 2, 3, 14, 15. Implements DEC-011 (rounds
{1,2,3,13,14,15} are pistol-or-anti-eco; others use the gunround baseline).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.config.constants import GUN_WIN_RATE
from src.pricing import blend

if TYPE_CHECKING:
    from src.pricing.dp import BO3State
    from src.pricing.live_theo import MatchState  # avoid circular at runtime
```

**Core dispatch pattern** (RESEARCH.md §4, lines 609-644 — ship verbatim, redacted to MatchState/HalfRates protocol):
```python
def round_p_for_round(
    state: BO3State,
    match_state: MatchState,
    half_rates: HalfRates,
) -> float:
    """Resolve P(team A wins the round about to start in `state`)."""
    round_num = state.a_round + state.b_round + 1  # 1-indexed
    map_name = state.map_pool[state.map_idx]
    side = state.side_orient

    if round_num == 1 or round_num == 13:
        # Pistol — Phase 1 falls back to half_rates (Phase 2 calibrates per A8 in RESEARCH).
        a_rate = half_rates.team(match_state.team_a, map_name, _team_a_side(side))
        b_rate = half_rates.team(match_state.team_b, map_name, _team_b_side(side))
        return blend.round_p(a_rate, b_rate)

    if round_num in (2, 3, 14, 15):
        pistol_won_by_a = state.pistol_winner_a[state.map_idx]
        if pistol_won_by_a is None:
            return 0.5  # defensive — shouldn't happen
        return GUN_WIN_RATE if pistol_won_by_a else 1.0 - GUN_WIN_RATE

    # Gunround baseline (rounds 4-12, 16-24)
    a_rate = half_rates.team(match_state.team_a, map_name, _team_a_side(side))
    b_rate = half_rates.team(match_state.team_b, map_name, _team_b_side(side))
    return blend.round_p(a_rate, b_rate)
```

**Side-derivation helpers** — copy `_team_b_side` pattern from `reference/theo_engine.py:158`:
```python
# Source: reference/theo_engine.py:158 (verified correct in audit engine)
def _team_b_side(side_orient: str) -> str:
    """Opposite side for team B given team A's side orientation."""
    return "def" if side_orient.endswith("atk") else "atk"
```

**Drop from analog:**
- `reference/theo_engine.py:161` clip `[0.05, 0.95]` — replaced by `[0.01, 0.99]` (DEC-012). Clipping is `live_theo.py`'s job, not this module's.
- The arithmetic-mean line `p = (a_rate + (1.0 - b_rate)) / 2.0` (line 161) — DEC-003 forbids it.

---

### `src/pricing/dp.py` (math, new)

**Analog A (loop structure):** `reference/theo_engine.py:168-206` `_markov_map_win` — adapt with the four bug fixes.
**Analog B (Final-typed module constants):** `src/config/constants.py:36-44` for `BO3State` field-naming style.

**Imports pattern:**
```python
"""Generalized BO3 DP (`series_value`).

Replaces audit-engine `_markov_map_win` (reference/theo_engine.py:168-206) with
a single recursion over the full BO3 BO3State (DEC-002 — same DP for series and
per-map, no parallel models). Fixes documented bugs per DEC-003 / 009 / 011.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass
from typing import Callable, Optional

from src.config.constants import REGULATION_HALF, WIN_THRESHOLD
```

**Dataclass pattern (BO3State)** — RESEARCH.md §1 (lines 487-497) with `frozen=True, slots=True` for hashability + memory:
```python
@dataclass(frozen=True, slots=True)
class BO3State:
    """DP cache key. Hashable; suitable for @lru_cache.

    Distinct from MatchState: BO3State holds ONLY DP-relevant fields. Live state
    (seq_id, ts, players_alive, etc.) does NOT belong here.
    """
    map_idx: int
    a_map_score: int
    b_map_score: int
    a_round: int
    b_round: int
    side_orient: str                              # 'a_atk' | 'a_def'
    map_pool: tuple[str, ...]                     # frozen for hashability
    pistol_winner_a: tuple[Optional[bool], ...]   # per-map; None=pre-pistol
```

**DP recursion shape** — adapt `reference/theo_engine.py:168-206` with bug fixes (RESEARCH.md §2, lines 513-558):
```python
@functools.lru_cache(maxsize=None)
def _series_value_cached(state: BO3State, round_p_id: int) -> float:
    """Top-down memoized recursion. Terminals + within-map recurrence."""
    if state.a_map_score >= 2:
        return 1.0
    if state.b_map_score >= 2:
        return 0.0
    if state.a_round >= WIN_THRESHOLD:
        return _series_value_cached(_advance_to_next_map(state, a_won=True), round_p_id)
    if state.b_round >= WIN_THRESHOLD:
        return _series_value_cached(_advance_to_next_map(state, a_won=False), round_p_id)

    # OT hard-stop at total=24 (DEC-009 / CRule 5; FIX for theo_engine.py:179 range(26))
    if state.a_round + state.b_round == REGULATION_HALF * 2:
        return _ot_coinflip_leaf(state, round_p_id)

    # Within-map recurrence (FIX for theo_engine.py:189-194 constant p1/p2)
    p = _ROUND_P_FNS[round_p_id](state)
    return (
        p * _series_value_cached(_advance_round(state, a_wins=True), round_p_id)
        + (1.0 - p) * _series_value_cached(_advance_round(state, a_wins=False), round_p_id)
    )
```

**Callable cache-key indirection** (RESEARCH.md §9, lines 836-850):
```python
# Module-level registry — keys lru_cache on int rather than unhashable Callable.
_ROUND_P_FNS: list[Callable[[BO3State], float]] = []

def _register_round_p_fn(fn: Callable[[BO3State], float]) -> int:
    _ROUND_P_FNS.append(fn)
    return len(_ROUND_P_FNS) - 1

def series_value(state: BO3State, round_p_fn: Callable[[BO3State], float]) -> float:
    return _series_value_cached(state, _register_round_p_fn(round_p_fn))
```

**OT leaf** (RESEARCH.md §5, lines 668-678):
```python
def _ot_coinflip_leaf(state: BO3State, round_p_id: int) -> float:
    """At total=24, OT-as-coinflip collapses entire OT sub-DP into 50/50 series leaf."""
    return (
        0.5 * _series_value_cached(_advance_to_next_map(state, a_won=True), round_p_id)
        + 0.5 * _series_value_cached(_advance_to_next_map(state, a_won=False), round_p_id)
    )
```

**Drop from analog (theo_engine.py):**
- Line 179 `for total in range(WIN_THRESHOLD * 2)` runs to 26 — replace with explicit OT hard-stop at `REGULATION_HALF * 2 == 24`.
- Lines 189-194 `if total < REGULATION_HALF: p = p1` else `p = p2` — replace with `_ROUND_P_FNS[round_p_id](state)` per round.
- The bottom-up forward propagation pattern (lines 196-204) — keep the *idea* (state advance) but flip to top-down recursion since we use `lru_cache` not a manual `dp` dict.

**No magic numbers:** Per CRule 12 the OT leaf check uses `REGULATION_HALF * 2`, not `24`. `OT_TOTAL_HARDSTOP` is NOT introduced as a constant per RESEARCH.md §12 final recommendation.

---

### `src/pricing/round_conclusion.py` (data-shape, new)

**Analog:** `reference/theo_engine.py:84-102` `_get_rate` — Bayesian-shrinkage formula `(n * raw + SHRINK_PRIOR * prior) / (n + SHRINK_PRIOR)` (line 100). This is the formula `_Cell.shrunk()` reuses verbatim.

**Imports pattern:**
```python
"""Hierarchical mid-round-conclusion lookup skeleton (Phase 1).

Phase 1 ships the SHAPE per DEC-007 (5-level fallback chain) but every cell
returns 0.5 (D-06). Phase 2 calibrates real cell values without changing this
interface. Bayesian shrinkage formula salvaged from reference/theo_engine.py:100
per D-09.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

from src.config.constants import SHRINK_PRIOR
```

**Core skeleton pattern** (RESEARCH.md §6, lines 690-738):
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
    cells_full: dict[tuple[int, bool, str, str, str], _Cell] = field(default_factory=dict)
    cells_no_econ: dict[tuple[int, bool, str, str], _Cell] = field(default_factory=dict)
    cells_no_map: dict[tuple[int, bool, str], _Cell] = field(default_factory=dict)
    cells_minimal: dict[tuple[int, bool], _Cell] = field(default_factory=dict)
    side_baseline: dict[str, float] = field(default_factory=lambda: {"atk": 0.5, "def": 0.5})

    def lookup(
        self,
        numerical_diff: int,
        bomb_planted: bool,
        side: str,
        econ_bucket: str,
        map_name: str,
    ) -> float:
        """Phase 1: always returns 0.5. Phase 2: walks the fallback chain."""
        return _PHASE_1_FLAT_CELL_VALUE
```

**Bayesian-shrinkage formula salvage source** (`reference/theo_engine.py:96-100`):
```python
# Salvage source — copy verbatim into _Cell.shrunk(), retyping for mypy strict:
entry = self._team_rates.get(f'{team}|{map_name}|{side}')
if entry:
    n    = entry.get('total', 0)
    raw  = entry['rate']
    return (n * raw + SHRINK_PRIOR * prior) / (n + SHRINK_PRIOR)
```

**Drop from analog:**
- The JSON loading `_get_rate` does (lines 92-95) — Phase 1 doesn't load any cell data; everything returns 0.5.
- Anything to do with `_team_rates` / `_league_rates` — those belong to `live_theo.py`'s `HalfRates` helper, not `round_conclusion.py`.

**Note on `frozen=True` + mutable defaults:** RESEARCH.md §6 shows `frozen=True` with `dict[..., _Cell]` fields. The `field(default_factory=dict)` pattern is required because frozen dataclasses still need writable per-instance defaults. This is the established Python idiom (verified — works under `mypy --strict`).

---

### `src/pricing/live_theo.py` (service + data-shape, new)

This is the load-bearing orchestrator. Multiple analogs.

**Analog A (module structure + Final + docstring style):** `src/main.py:1-56`
**Analog B (`_data_weight` salvage):** `reference/theo_engine.py:104-129` — verbatim per D-09
**Analog C (`_get_rate` for `HalfRates`):** `reference/theo_engine.py:84-102`

**Imports pattern** (mirror `src/main.py:30-37`):
```python
"""Single canonical pricing entry point: live_theo(state) → TheoOutput.

Replaces audit-engine series_theo / series_theo_no_sides / series_theo_from_map_probs
triplet (DEC-010 / CRule 1). All four bug fixes documented at the file level:
  1. Bradley-Terry blend (DEC-003)        — via src.pricing.blend
  2. OT hard-stop at total=24 (DEC-009)   — via src.pricing.dp
  3. Pistol/anti-eco modeling (DEC-011)   — via src.pricing.round_types
  4. Conviction clip [0.01, 0.99] (DEC-012) — applied here at output assembly

Phase 1 owns the MatchState dataclass (D-14). Phase 3 will move it to
src/state/match_state.py and live_theo.py will re-import from there.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Final, Optional

from src.config.constants import (
    CONVICTION_CLIP_HIGH,
    CONVICTION_CLIP_LOW,
    MIN_ROUNDS_FULL_WEIGHT,
)
from src.pricing import blend, dp, round_conclusion, round_types

logger = logging.getLogger(__name__)
```

**MatchState dataclass** (RESEARCH.md §10, lines 868-892 — note `team_a/b` and `map_side_orients` additions per A4/A5):
```python
@dataclass(frozen=True, slots=True)
class MatchState:
    """Phase 1 stub. Phase 3 (REQ-match-state-engine) replaces with full version."""
    match_id: str
    team_a: str
    team_b: str
    map_pool: tuple[str, ...]
    map_idx: int
    a_map_score: int
    b_map_score: int
    a_round: int
    b_round: int
    side_orient: str
    map_side_orients: tuple[str, ...]
    pistol_winner_a: dict[int, Optional[bool]]
    numerical_diff: int
    bomb_planted: bool
    side: str
    econ_bucket: str
```

**TheoOutput dataclass** (PRD §2 / RESEARCH.md architecture diagram):
```python
@dataclass(frozen=True, slots=True)
class TheoOutput:
    """Single canonical pricing output (DEC-010 / CRule 1)."""
    theo_series: float                 # ∈ [CONVICTION_CLIP_LOW, CONVICTION_CLIP_HIGH]
    theo_map: tuple[float, ...]        # one per map in pool; same clip
    vega: float                        # ≥ 0
    confidence: float                  # ∈ [0, 1]
```

**`_data_weight` salvage** (verbatim from `reference/theo_engine.py:104-129`, retyped for mypy strict):
```python
# Source: reference/theo_engine.py:104-129 — D-09 mandates verbatim salvage.
def _data_weight_for_map(team_a: str, team_b: str, map_name: str, half_rates: HalfRates) -> float:
    """Audit-engine min-over-teams data weight. Powers DP-mass-weighted confidence (D-08)."""
    team_weights: list[float] = []
    for team in (team_a, team_b):
        team_total = 0.0
        team_count = 0
        for side in ("atk", "def"):
            entry = half_rates.team_entry(team, map_name, side)
            if entry and not entry.get("used_fallback", False):
                team_total += float(entry.get("total", 0))
                team_count += 1
        if team_count == 0:
            return 0.0
        team_weights.append(team_total / team_count)
    return min(1.0, min(team_weights) / MIN_ROUNDS_FULL_WEIGHT)
```

**Output clipping pattern** (DEC-012 / CRule 6):
```python
def _clip_conviction(theo: float) -> float:
    """Clip to [CONVICTION_CLIP_LOW, CONVICTION_CLIP_HIGH] = [0.01, 0.99] per DEC-012."""
    return max(CONVICTION_CLIP_LOW, min(CONVICTION_CLIP_HIGH, theo))
```

**Public entry point shape** (PRD §2 / DEC-010):
```python
def live_theo(state: MatchState, half_rates: HalfRates) -> TheoOutput:
    """Single canonical pricing entry point. Pure read of `state`."""
    root = _bo3_state_from_match_state(state)
    round_p_fn = _build_round_p_fn(state, half_rates)
    theo = dp.series_value(root, round_p_fn)
    theo_map = tuple(_marginal_map_prob(root, i, round_p_fn) for i in range(len(state.map_pool)))
    vega = _compute_vega(root, round_p_fn)
    confidence = _compute_confidence(root, state, half_rates)
    return TheoOutput(
        theo_series=_clip_conviction(theo),
        theo_map=tuple(_clip_conviction(p) for p in theo_map),
        vega=vega,
        confidence=confidence,
    )
```

**Drop from analog (theo_engine.py):**
- Lines 41-51 `_signal_strength` — DROP (PRD §12.2 #2 bug class).
- Lines 281-426 `series_theo` / `series_theo_no_sides` / `series_theo_from_map_probs` — DROP all three (DEC-010).
- Line 162 clip `[0.05, 0.95]` — replaced with `[0.01, 0.99]`.
- Lines 225-252 `model_series_prob` IID closed form — DROP, the DP handles it.

---

### `src/config/constants.py` (modify)

**Analog:** the file itself, lines 36-77 (Final-typed pricing constants block).

**Existing pattern to mirror exactly** (`src/config/constants.py:44-49`):
```python
SHRINK_PRIOR: Final[float] = 15.0
"""Bayesian prior weight in rounds for the round-conclusion lookup.

Source: DEC-007 / CLAUDE.md "Domain constants" / reference/theo_engine.py:37.
Re-fit in Phase 5 after 100+ matches of paper-trade data (REQ-calibration-loop).
"""
```

**Four constants to add** (RESEARCH.md §12, lines 960-971; insert into the Pricing block, between lines 77 and 79):

```python
CONVICTION_CLIP_LOW: Final[float] = 0.01
"""Lower bound for theo_series and theo_map[i] clip at live_theo output.

Source: DEC-012 / CLAUDE.md rule 6 / CON-conviction-clip / RESEARCH.md §12.
Replaces the audit engine's heterogeneous `[0.05, 0.95]` and `[0.03, 0.97]`
clips with a unified, wider `[0.01, 0.99]` band (PRD §12.2 #1).
"""

CONVICTION_CLIP_HIGH: Final[float] = 0.99
"""Upper bound for theo_series and theo_map[i] clip at live_theo output.

Source: DEC-012 / CLAUDE.md rule 6 / CON-conviction-clip / RESEARCH.md §12.
"""

MIN_ROUNDS_FULL_WEIGHT: Final[int] = 15
"""Effective rounds for full data confidence in the audit-engine `_data_weight`
formula (D-09). Min-over-teams normalizer for confidence aggregation.

Source: reference/theo_engine.py:36 / D-09 / RESEARCH.md §12. Used in
src/pricing/live_theo.py::_data_weight_for_map only.
"""

BT_BLEND_EPSILON: Final[float] = 1e-6
"""Bradley-Terry blend input clip — protects against 0/0 at boundary inputs.

Source: CON-bradley-terry-formula / RESEARCH.md §3 (Pitfall 4) / §12.
Inputs to blend.round_p are clipped to [BT_BLEND_EPSILON, 1 - BT_BLEND_EPSILON]
BEFORE the formula. Output is NEVER clipped — that breaks BT symmetry.
"""
```

**What to copy:** Final-typed assignment + docstring with `Source:` block (every existing constant follows this pattern).

**What to adapt:** Place new constants in the `Pricing` block (between line 77 `WIN_THRESHOLD` and line 79 `Sizing` divider). Keep the visual divider style (`# ---...---`) that demarcates blocks.

**What to drop:** Per RESEARCH.md §12 final recommendation, do NOT add `OT_TOTAL_HARDSTOP` — express as `REGULATION_HALF * 2` inline in `dp.py` so the `12-per-half × 2` relationship stays explicit.

---

### `tests/config/test_constants.py` (modify)

**Analog:** the file itself.

**Existing pattern to extend** (`tests/config/test_constants.py:23-40` `EXPECTED_NAMES` tuple):
```python
EXPECTED_NAMES: tuple[str, ...] = (
    # Pricing
    "SHRINK_PRIOR",
    "SIGNAL_SCALE",
    "GUN_WIN_RATE",
    "REGULATION_HALF",
    "WIN_THRESHOLD",
    # Sizing
    ...
)
```

**Modifications required:**
1. Append four new pricing constants to `EXPECTED_NAMES` (between `WIN_THRESHOLD` and `# Sizing`):
   ```python
   "CONVICTION_CLIP_LOW",
   "CONVICTION_CLIP_HIGH",
   "MIN_ROUNDS_FULL_WEIGHT",
   "BT_BLEND_EPSILON",
   ```
2. Append corresponding entries to `EXPECTED_TYPES` (lines 87-100):
   ```python
   "CONVICTION_CLIP_LOW": float,
   "CONVICTION_CLIP_HIGH": float,
   "MIN_ROUNDS_FULL_WEIGHT": int,
   "BT_BLEND_EPSILON": float,
   ```
3. Add value-invariant tests, one per new constant (mirror `test_gun_win_rate_is_a_probability` style at lines 129-132):
   ```python
   def test_conviction_clips_are_a_unit_subinterval() -> None:
       assert 0.0 < constants.CONVICTION_CLIP_LOW < 0.5
       assert 0.5 < constants.CONVICTION_CLIP_HIGH < 1.0
       assert constants.CONVICTION_CLIP_LOW + constants.CONVICTION_CLIP_HIGH == pytest.approx(1.0)

   def test_min_rounds_full_weight_positive() -> None:
       assert constants.MIN_ROUNDS_FULL_WEIGHT > 0

   def test_bt_blend_epsilon_is_a_small_positive_float() -> None:
       assert 0.0 < constants.BT_BLEND_EPSILON < 0.01
   ```

**What to copy:** The triple-section structure (importability / types / value invariants) at lines 19-21, 83-85, 114-116. The `test_no_unexpected_uppercase_names_leak_in` (lines 54-80) regression-locks new constants automatically once added to `EXPECTED_NAMES`.

**What NOT to drop:** `test_no_unexpected_uppercase_names_leak_in` — this is a contract that catches typos in `EXPECTED_NAMES` adoption.

---

### `tests/pricing/__init__.py` (scaffolding, new)

**Analog:** `tests/config/__init__.py:1`
```python
"""Tests for src.config.* — threshold module sanity checks."""
```

**Excerpt to mirror exactly:**
```python
"""Tests for src.pricing.* — DP, blend, round-types, round-conclusion, live_theo."""
```

That is the entire file. One-line docstring, nothing else.

---

### `tests/pricing/test_blend.py` (test, new)

**Analog A (parametrize style):** `tests/config/test_constants.py:103-111` (`@pytest.mark.parametrize` with `name, expected` pairs).
**Analog B (math fixtures):** `reference/fair_value.py:77-79` `_bo3_series_prob`.

**Imports pattern:**
```python
"""Property + unit tests for src.pricing.blend.

Verifies REQ-bradley-terry-blend acceptance criteria from roadmap §1.2:
  - round_p(0.5, 0.5) == 0.5 (coin flip)
  - round_p(0.7, 0.3) ≈ 0.84 (compounding edge)
  - round_p(1.0, 0.0) ≈ 1.0 (saturated)
  - Bradley-Terry symmetry: round_p(a,b) + round_p(b,a) == 1
"""

from __future__ import annotations

import math

import pytest
from hypothesis import given, strategies as st

from src.config.constants import BT_BLEND_EPSILON
from src.pricing.blend import round_p
```

**Unit-cases pattern** (parametrize like `tests/config/test_constants.py:103-111`):
```python
@pytest.mark.parametrize(
    "a,b,expected",
    [
        (0.5, 0.5, 0.5),
        (0.7, 0.3, 49.0 / 58.0),  # 0.84482...
    ],
)
def test_round_p_unit_cases(a: float, b: float, expected: float) -> None:
    assert math.isclose(round_p(a, b), expected, rel_tol=1e-9)
```

**Property-test pattern** (RESEARCH.md §3 algebraic proof, ship as hypothesis test):
```python
@given(
    a=st.floats(min_value=0.001, max_value=0.999),
    b=st.floats(min_value=0.001, max_value=0.999),
)
def test_round_p_bradley_terry_symmetry(a: float, b: float) -> None:
    """round_p(a, b) + round_p(b, a) == 1 (clip-symmetry preserves identity)."""
    assert math.isclose(round_p(a, b) + round_p(b, a), 1.0, rel_tol=1e-9)
```

**Boundary-clip pattern:**
```python
def test_round_p_handles_zero_one_boundary() -> None:
    """Inputs of 0/1 are clipped to BT_BLEND_EPSILON before the formula — no NaN."""
    assert not math.isnan(round_p(0.0, 1.0))
    assert not math.isnan(round_p(1.0, 0.0))
    assert round_p(1.0, 0.0) > 1.0 - 1e-6
```

---

### `tests/pricing/test_round_types.py` (test, new)

**Analog:** `tests/config/test_constants.py:103-111` (parametrize) + `tests/test_main.py:36-56` (build-and-call style).

**Imports pattern:**
```python
"""Tests for src.pricing.round_types — REQ-pistol-anti-eco-modeling.

Verifies:
  - Round-num dispatch correctly routes to pistol / anti-eco / gunround paths.
  - Pistol_winner_a fall-through (None pre-pistol → defensive 0.5).
  - GUN_WIN_RATE wired correctly: rounds 2/3/14/15 return 0.822 (or 0.178).
"""

from __future__ import annotations

import pytest

from src.config.constants import GUN_WIN_RATE
from src.pricing.dp import BO3State
from src.pricing.round_types import round_p_for_round
```

**Dispatch test** (parametrize over round numbers — pattern mirrors `tests/config/test_constants.py:103-111`):
```python
@pytest.mark.parametrize(
    "a_round,b_round,pistol_won_by_a,expected",
    [
        # Rounds 2, 3, 14, 15: anti-eco, conditional on pistol winner
        (1, 0, True, GUN_WIN_RATE),       # round 2, A won pistol → A on guns
        (1, 0, False, 1.0 - GUN_WIN_RATE),# round 2, B won pistol → A on eco
        (2, 0, True, GUN_WIN_RATE),       # round 3, A won pistol
        (12, 0, True, GUN_WIN_RATE),      # round 13 is pistol, but a_round+b_round+1=13 → pistol path NOT anti-eco
    ],
)
def test_round_p_for_round_anti_eco_dispatch(...) -> None:
    ...
```

---

### `tests/pricing/test_dp.py` (test, new)

**Analog A (property-test fixture):** `reference/fair_value.py:77-79` `_bo3_series_prob` — closed form for symmetric input.
**Analog B (parametrize / asserts):** `tests/test_main.py:36-118`.

**Imports pattern** (RESEARCH.md §11, lines 925-945):
```python
"""Property tests for src.pricing.dp — REQ-bo3-dp-engine + REQ-ot-handling.

Verifies:
  - DP value ∈ [0, 1] for any reachable state.
  - Symmetric inputs → DP value == p²(3-2p) (closed form from fair_value).
  - OT hard-stop: DP returns coinflip leaf at total=24, never iterates past.
"""

from __future__ import annotations

import math

import pytest
from hypothesis import given, strategies as st

from reference.fair_value import _bo3_series_prob
from src.pricing.dp import BO3State, series_value
```

**Symmetric-input closed-form test** (RESEARCH.md §11, ship verbatim):
```python
@given(p=st.floats(min_value=0.05, max_value=0.95))
def test_dp_symmetric_input_matches_closed_form(p: float) -> None:
    """Constant round_p across all states → DP value equals p²(3-2p)."""
    state = BO3State(
        map_idx=0, a_map_score=0, b_map_score=0,
        a_round=0, b_round=0, side_orient="a_atk",
        map_pool=("Lotus", "Bind", "Haven"),
        pistol_winner_a=(None, None, None),
    )
    actual = series_value(state, lambda _s: p)
    expected = _bo3_series_prob(p)
    assert math.isclose(actual, expected, rel_tol=1e-9)
```

**Range-invariant test:**
```python
@given(p=st.floats(min_value=0.0, max_value=1.0))
def test_dp_value_in_unit_interval(p: float) -> None:
    state = BO3State(
        map_idx=0, a_map_score=0, b_map_score=0,
        a_round=0, b_round=0, side_orient="a_atk",
        map_pool=("Lotus", "Bind", "Haven"),
        pistol_winner_a=(None, None, None),
    )
    val = series_value(state, lambda _s: p)
    assert 0.0 <= val <= 1.0
```

**OT hard-stop test:**
```python
def test_dp_ot_hardstop_returns_coinflip_leaf() -> None:
    """At total=24 (12-12), DP returns 0.5×next_map_state(A_won) + 0.5×next_map_state(B_won)."""
    state = BO3State(
        map_idx=0, a_map_score=0, b_map_score=0,
        a_round=12, b_round=12, side_orient="a_def",
        map_pool=("Lotus", "Bind", "Haven"),
        pistol_winner_a=(True, None, None),
    )
    val = series_value(state, lambda _s: 0.5)
    # By symmetry under p=0.5, val should equal 0.5 (each map equally winnable).
    assert math.isclose(val, 0.5, rel_tol=1e-9)
```

**Critical:** Use `pytest.approx(rel=1e-9)` or `math.isclose(rel_tol=1e-9)` — NEVER `==` (Pitfall 7).

---

### `tests/pricing/test_round_conclusion.py` (test, new)

**Analog:** `tests/config/test_constants.py:43-51` (importability + value invariants).

**Imports pattern:**
```python
"""Tests for src.pricing.round_conclusion — REQ-round-conclusion-lookup (skeleton-only).

Verifies the Phase 1 invariants:
  - Skeleton signature matches DEC-007 / roadmap §1.5.
  - All cells return _PHASE_1_FLAT_CELL_VALUE = 0.5 regardless of inputs.
  - _Cell.shrunk() Bayesian formula matches reference/theo_engine.py:100.
"""

from __future__ import annotations

import math

import pytest
from hypothesis import given, strategies as st

from src.config.constants import SHRINK_PRIOR
from src.pricing.round_conclusion import RoundConclusionLookup, _Cell
```

**Flat-0.5 invariant test (Phase 1 contract per D-06):**
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

**`_Cell.shrunk` Bayesian formula test:**
```python
def test_cell_shrunk_matches_audit_engine_formula() -> None:
    """`(n * p_hat + SHRINK_PRIOR * parent_p) / (n + SHRINK_PRIOR)` per ref:100."""
    cell = _Cell(n=10, p_hat=0.6, parent_p=0.5)
    expected = (10 * 0.6 + SHRINK_PRIOR * 0.5) / (10 + SHRINK_PRIOR)
    assert math.isclose(cell.shrunk(), expected, rel_tol=1e-12)
```

---

### `tests/pricing/test_live_theo.py` (test, new)

**Analog:** `tests/test_main.py:1-126` — multi-aspect contract test for the single public surface.

**Imports pattern** (mirror `tests/test_main.py:14-19`):
```python
"""End-to-end contract tests for src.pricing.live_theo.

Verifies REQ-canonical-live-theo + REQ-theo-{series,map}-output +
REQ-confidence-output + REQ-vega-output. Locks the public surface so
downstream Phase 4 quoting layer can import deterministically.
"""

from __future__ import annotations

import math

from src.pricing.live_theo import live_theo, MatchState, TheoOutput
```

**Import-surface contract test** (CRule 1 / DEC-010):
```python
def test_public_imports_only() -> None:
    """live_theo, MatchState, TheoOutput are the ONLY public names exported.

    DEC-010 forbids series_theo / series_theo_no_sides / series_theo_from_map_probs.
    """
    import src.pricing as pricing
    assert "live_theo" in pricing.__all__
    assert "MatchState" in pricing.__all__
    assert "TheoOutput" in pricing.__all__
    forbidden = {"series_theo", "series_theo_no_sides", "series_theo_from_map_probs"}
    assert not (forbidden & set(pricing.__all__))
```

**Theo range / map-series consistency** (REQ-theo-map-output, RESEARCH.md §11 consistency):
```python
def test_theo_series_in_unit_interval(synthetic_state: MatchState, half_rates) -> None:
    out = live_theo(synthetic_state, half_rates)
    assert 0.01 <= out.theo_series <= 0.99   # CONVICTION_CLIP

def test_theo_map_consistency_with_series(synthetic_state: MatchState, half_rates) -> None:
    """theo_series and theo_map[i] both come from the same DP — must agree under marginalization."""
    out = live_theo(synthetic_state, half_rates)
    # theo_map[i] ∈ [0, 1] for every map
    for p in out.theo_map:
        assert 0.01 <= p <= 0.99
```

**Vega formula test** (RESEARCH.md §8, lines 814-820):
```python
def test_vega_matches_dec_018_formula(synthetic_state: MatchState, half_rates) -> None:
    """vega == round_p × (theo_a − theo)² + (1−round_p) × (theo_b − theo)²"""
    out = live_theo(synthetic_state, half_rates)
    assert out.vega >= 0.0
    # Exact-formula test by reconstruction in the test body, with rel_tol=1e-9.
```

**Note on fixtures:** Establish `tests/pricing/conftest.py` with `synthetic_state` and `half_rates` fixtures. RESEARCH.md §Validation Architecture (lines 1110-1117) lists this as a required Wave 0 file. Borrow the fixture-naming style from `tests/test_main.py` (no fixtures there) and the parametrize style from `tests/config/test_constants.py:103`.

---

## Shared Patterns

### Pattern S1 — `Final[...]`-typed module constants with `Source:` block

**Source:** `src/config/constants.py:44-49`
**Apply to:** `src/pricing/round_conclusion.py` (`_PHASE_1_FLAT_CELL_VALUE`), and any future per-module constants that are NOT business-tunable. Tunable thresholds always go in `src/config/constants.py` (CRule 12).

```python
SHRINK_PRIOR: Final[float] = 15.0
"""Bayesian prior weight in rounds for the round-conclusion lookup.

Source: DEC-007 / CLAUDE.md "Domain constants" / reference/theo_engine.py:37.
Re-fit in Phase 5 after 100+ matches of paper-trade data (REQ-calibration-loop).
"""
```

Every constant docstring carries: (a) what it controls, (b) `Source:` line citing the locked DEC / CRule / reference line, (c) phase note for when it gets re-fit.

---

### Pattern S2 — `from __future__ import annotations` + lazy typing imports

**Source:** `src/main.py:30`, `src/config/constants.py:36`, `tests/config/test_constants.py:13`
**Apply to:** every new file in Phase 1 (source and test).

```python
from __future__ import annotations

from typing import Final, Optional, Callable
```

Required by `mypy --strict` to allow `tuple[str, ...]` syntax on Python 3.11 without runtime cost.

---

### Pattern S3 — Frozen-dataclass-with-slots for hashable cache keys

**Source:** Established convention from RESEARCH.md §1, no in-tree analog yet. The pattern matches Python 3.11 stdlib idiom and `@functools.lru_cache` requirements.

**Apply to:** `BO3State`, `MatchState`, `TheoOutput`, `_Cell`, `RoundConclusionLookup`.

```python
@dataclass(frozen=True, slots=True)
class FooState:
    field_a: int
    field_b: tuple[str, ...]   # NEVER list (unhashable)
```

Critical: tuples not lists for collection fields (Pitfall 1). `dict` fields require `field(default_factory=dict)`.

---

### Pattern S4 — Test-file structure: docstring + section comments

**Source:** `tests/config/test_constants.py:1-12` then `:19-21`, `:83-85`, `:114-116`
**Apply to:** every new test file.

```python
"""Module docstring — what this file tests, which REQ it covers, what it does NOT cover.

Tuning / calibration tests do NOT belong here (Phase 5).
"""

from __future__ import annotations

# ... imports ...

# --------------------------------------------------------------------------- #
# 1. Importability                                                            #
# --------------------------------------------------------------------------- #

# ... test functions ...

# --------------------------------------------------------------------------- #
# 2. Types                                                                    #
# --------------------------------------------------------------------------- #
```

Ruled lines (79 chars `#`) demarcate sections — borrow exactly from `tests/config/test_constants.py:19-21`.

---

### Pattern S5 — Docstring style: explicit Source / DEC / CRule references

**Source:** `src/main.py:1-28`, `src/config/constants.py:1-34`
**Apply to:** every new module — every public function and dataclass.

Module docstring template:
```python
"""<one-line purpose>.

<paragraph: what this module does and replaces.>

Phase N scope
-------------
<scope/non-goals statement.>

<Promotion/seam comment>
-------
<E.g., 'Phase 3 will replace MatchState here with the full ingestion-driven version.'>
"""
```

Every Phase 1 module needs the `<bug fixes documented at file level>` block (the four-bug table) so that future readers can audit-trail what changed and why (see `src/pricing/live_theo.py` excerpt above).

---

### Pattern S6 — Logging convention (call sites only, never library)

**Source:** `src/main.py:33, 37, 152-157`
**Apply to:** `src/pricing/live_theo.py` if any logging is needed (Phase 1 minimal — likely none).

```python
import logging
logger = logging.getLogger(__name__)
# Never logging.basicConfig() in library code (CONVENTIONS.md per main.py:153 comment).
```

For Phase 1 the math layer is silent by design — no logging unless a kill-switch precondition fires (and those land in Phase 4).

---

### Pattern S7 — Test isolation: parametrize for tabular cases

**Source:** `tests/config/test_constants.py:103-111`
**Apply to:** `tests/pricing/test_blend.py`, `tests/pricing/test_round_types.py`.

```python
@pytest.mark.parametrize("input,expected", [
    (case_1, result_1),
    (case_2, result_2),
])
def test_function_name(input, expected) -> None:
    assert math.isclose(fn(input), expected, rel_tol=1e-9)
```

For property tests use `hypothesis.given` instead (RESEARCH.md §11 + Pattern S4).

---

### Pattern S8 — Salvage-with-attribution from `reference/`

**Source:** Multiple lines in `reference/theo_engine.py` get salvaged. Standard format for the salvage comment:

```python
# Source: reference/theo_engine.py:100 — verbatim per D-09 / DEC-013.
# DO NOT modify the formula — Phase 5 calibration may re-fit but the
# shape must remain (n * raw + SHRINK_PRIOR * prior) / (n + SHRINK_PRIOR).
```

Apply to: every block adapted from `reference/theo_engine.py` lines 84-129. Always cite the source line range and the locked DEC that mandates the salvage.

---

## No Analog Found

**None.** Every Phase 1 file has either a direct in-tree analog or a salvage-source analog. The constants extension and test scaffolding are pure-pattern repetition; the math modules either adapt `reference/theo_engine.py` (with documented bug fixes) or use `reference/fair_value.py` as a property-test fixture.

The closest thing to a "no analog" case is `src/pricing/dp.py`'s `_register_round_p_fn` callable-cache-key indirection (RESEARCH.md §9, lines 836-850) — there is no in-tree precedent because the codebase has no other `lru_cache`-on-Callable usage. **Planner action:** treat this as new infrastructure; no analog to mine. Property-tests should explicitly verify cache behavior (`cache_info().hits` after repeat calls).

---

## Metadata

**Analog search scope:**
- `src/config/constants.py` (Phase-0 constants pattern — exact match for `src/config/constants.py` modification)
- `src/main.py`, `src/__main__.py`, `src/__init__.py` (Phase-0 source-module patterns)
- `tests/config/test_constants.py`, `tests/test_main.py`, `tests/test_smoke.py` (Phase-0 test patterns)
- `reference/theo_engine.py` (DP / data-weight / shrinkage salvage source per DEC-013)
- `reference/fair_value.py` (closed-form symmetric-input fixture per REQ-bo3-dp-engine)
- `pyproject.toml` (mypy strict scope on `src.pricing.*` already wired)
- `src/pricing/__init__.py` (Phase-0 placeholder; modify in Plan 01-XX)

**Files scanned:** 14 in-tree files + 2 reference files = 16 files inspected.

**Pattern extraction date:** 2026-04-27
