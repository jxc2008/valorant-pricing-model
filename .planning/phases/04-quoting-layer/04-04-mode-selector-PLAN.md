---
phase: 04-quoting-layer
plan: "04"
type: execute
wave: 3
depends_on: ["00", "01", "02", "03"]
files_modified:
  - src/quoting/mode_selector.py
  - src/quoting/__init__.py
  - src/pricing/live_theo.py
  - src/pricing/data.py
  - src/config/constants.py
  - tests/config/test_constants.py
  - tests/quoting/test_mode_selector.py
  - tests/pricing/test_vega_post_plant.py
autonomous: true
requirements:
  - REQ-mode-selector
  - REQ-vega-output
notes: |
  Wave 3 — pure-function mode selector + post-plant vega (DEC-018 v2 second-arm).

  CRITICAL — atomic deletion of VEGA_DIRECTIONAL_THRESHOLD. Per RESEARCH §"State
  of the Art" and DEC-018 v2, the v1 constant `VEGA_DIRECTIONAL_THRESHOLD = 0.04`
  is REMOVED — DIRECTIONAL_TAKE no longer triggers on vega magnitude (triggers on
  |theo - market_mid| > TAKE_THRESHOLD). The deletion happens atomically in this
  plan with two coupled changes:
    (a) src/config/constants.py — delete the constant + its docstring
    (b) tests/config/test_constants.py — remove "VEGA_DIRECTIONAL_THRESHOLD" from
        EXPECTED_NAMES allow-list AND remove it from EXPECTED_TYPES
  Same-commit Rule-3 prophylactic per Phase 03 D-08 (Plan 03-03 SUMMARY)
  documented this exact failure as a recurring blocking auto-fix.

  Six rules in declared order — IMPLEMENT AS A SEQUENCE OF `if ... return ...`
  STATEMENTS, NOT a match statement / dict dispatch / "highest priority wins"
  table. Per RESEARCH Pitfall 3, the literal source-code order IS the priority,
  and a tied DIRECTIONAL+MM situation must be resolved by order alone (rule 4
  comes before rule 5; DIRECTIONAL wins).

  vega_post_plant formula (DEC-018 v2 — TBD per PRD §9.5):
    Recommended formula per RESEARCH §"Open Questions" #2: between-round shape
    over post-plant outcomes. Outcomes: {kill, defuse, time-out}, parameterized
    by (att, def, time_bucket). Variance computed over hypothetical theo
    realizations after each outcome:
      var = sum_{o in outcomes} P(o) * (theo_after_outcome - theo_now)**2
    Calibrate concretely in Phase 5 against logged post-plant theo updates.
    Phase 04 ships the formula as a separate function
    `compute_vega_post_plant(state, lookup) -> float` in src/pricing/live_theo.py
    mirroring the Phase 1 between-round vega function.

  Mid-round detection per RESEARCH §"Pattern 1": `_is_mid_round(state)` returns
  `state.time_left_s is not None`. Phase 03 D-14 carry-forward — time_left_s is
  None except when bomb_planted=True OR a separate timer source has populated
  it. For Phase 04 simplicity, treat the populated state as mid-round; Phase 5
  calibration may refine.

must_haves:
  truths:
    - "trading_mode is a pure function — no I/O, no hidden state, no class members"
    - "Rule 1 (kill_switch_active) returns IDLE regardless of every other input"
    - "Rule 2 (state.bomb_planted) returns POST_PLANT_QUOTE when kill switch is not active"
    - "Rule 3 (mid-round, not bomb-planted) returns IDLE"
    - "Rule 4 (|theo*100 - market.mid| > TAKE_THRESHOLD) returns DIRECTIONAL_TAKE"
    - "Rule 5 (market.spread > MM_MIN_EDGE) returns MM_BETWEEN_ROUND"
    - "Rule 6 (fall-through) returns IDLE"
    - "When BOTH rule 4 and rule 5 conditions hold, DIRECTIONAL_TAKE wins (declared order)"
    - "VEGA_DIRECTIONAL_THRESHOLD is deleted from src/config/constants.py AND tests/config/test_constants.py allow-list in the same commit"
    - "compute_vega_post_plant(state, lookup) returns variance over {kill, defuse, time-out} post-plant outcomes; documented Phase 5 calibration TODO"
  artifacts:
    - path: "src/quoting/mode_selector.py"
      provides: "Pure function trading_mode + TradingMode Literal type + _is_mid_round helper"
      min_lines: 60
      contains: "Literal"
    - path: "src/pricing/live_theo.py"
      provides: "compute_vega_post_plant function (DEC-018 v2 second arm)"
      contains: "compute_vega_post_plant"
    - path: "src/config/constants.py"
      provides: "VEGA_DIRECTIONAL_THRESHOLD DELETED; only TAKE_THRESHOLD/MM_MIN_EDGE remain"
      contains: "TAKE_THRESHOLD"
    - path: "tests/config/test_constants.py"
      provides: "EXPECTED_NAMES allow-list NO LONGER contains VEGA_DIRECTIONAL_THRESHOLD"
      contains: "TAKE_THRESHOLD"
    - path: "tests/quoting/test_mode_selector.py"
      provides: "7 GREEN tests: 6 rules + tie-break"
      contains: "test_tie_directional_dominates_mm"
  key_links:
    - from: "src/quoting/mode_selector.trading_mode"
      to: "src.config.constants.TAKE_THRESHOLD + MM_MIN_EDGE"
      via: "import + threshold comparisons in declared order"
      pattern: "TAKE_THRESHOLD"
    - from: "src/pricing/live_theo.compute_vega_post_plant"
      to: "src.pricing.round_conclusion.RoundConclusionLookup.post_plant_p"
      via: "computes variance over {kill, defuse, time-out} outcomes"
      pattern: "post_plant_p"
    - from: "src/quoting/mode_selector.trading_mode"
      to: "src/quoting/kill_switches.KillSwitchAggregator.any_tripped()[0]"
      via: "kill_switch_active: bool argument"
      pattern: "kill_switch_active"
---

<objective>
Build the pure-function mode selector that all four quoter/taker modes
key off (REQ-mode-selector v2). Six rules in declared order; literal
source-code order IS the priority. Atomically deletes
VEGA_DIRECTIONAL_THRESHOLD per DEC-018 v2 (with same-commit allow-list
update). Ships `compute_vega_post_plant(state, lookup) -> float` as the
DEC-018 v2 second-arm vega formula.

Purpose: REQ-mode-selector is the architectural seam between Phase 03
ingestion (MatchState) and Phase 04 quoting (per-mode quoters/takers). A
deterministic pure function over (state, theo, market, vegas, ks_active)
keeps the routing layer unit-testable without any Kalshi mocks.

Output: src/quoting/mode_selector.py + src/pricing/live_theo.py
extended with compute_vega_post_plant + atomic VEGA_DIRECTIONAL_THRESHOLD
deletion + GREEN test_mode_selector.py + GREEN test_vega_post_plant.py.
</objective>

<execution_context>
@C:/Users/Joseph Cheng/.claude/get-shit-done/workflows/execute-plan.md
@C:/Users/Joseph Cheng/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/phases/04-quoting-layer/04-RESEARCH.md
@src/config/constants.py
@src/state/match_state.py
@src/pricing/live_theo.py
@src/pricing/data.py
@src/pricing/round_conclusion.py
@src/quoting/kill_switches.py
@tests/config/test_constants.py

<interfaces>
<!-- Phase 04 constants this plan consumes -->
From src/config/constants.py:
```python
TAKE_THRESHOLD: Final[int] = 5            # cents — DIRECTIONAL_TAKE trigger
MM_MIN_EDGE: Final[int] = 4               # cents — MM_BETWEEN_ROUND trigger
# VEGA_DIRECTIONAL_THRESHOLD: Final[float] = 0.04  # DELETED in this plan
```

<!-- Plan 04-01 surface -->
From src/quoting/market_data.py:
```python
class MarketQuote:  # frozen + slots
    yes_bid: int
    yes_ask: int
    mid: int                              # cents
    spread: int
    is_valid: bool
    last_updated_ts: float
```

<!-- Phase 1 surface — vega_between_round is theo.vega -->
From src/pricing/data.py:
```python
class TheoOutput:  # frozen + slots
    theo_series: float
    theo_map: tuple[float, ...]
    vega: float                           # = vega_between_round (DEC-018 D-10/D-11)
    confidence: float
```

<!-- Phase 03 surface for compute_vega_post_plant -->
From src/pricing/round_conclusion.py:
```python
class RoundConclusionLookup:
    def post_plant_p(self, att: int, def_: int, time_bucket: int,
                     side: str, map_name: str) -> float: ...
```

<!-- New surface created by this plan -->
NEW src/quoting/mode_selector.py public surface:
```python
TradingMode = Literal["MM_BETWEEN_ROUND", "DIRECTIONAL_TAKE", "POST_PLANT_QUOTE", "IDLE"]

def trading_mode(
    state: MatchState,
    theo: TheoOutput,
    market: MarketQuote,
    vega_between: float,                  # = theo.vega
    vega_post_plant: float,               # computed via compute_vega_post_plant
    kill_switch_active: bool,
) -> TradingMode: ...
```

NEW src/pricing/live_theo.py public surface:
```python
def compute_vega_post_plant(
    state: MatchState,
    lookup: RoundConclusionLookup,
) -> float: ...
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: ATOMIC delete VEGA_DIRECTIONAL_THRESHOLD + ship src/quoting/mode_selector.py + GREEN test_mode_selector.py</name>
  <files>src/config/constants.py, tests/config/test_constants.py, src/quoting/mode_selector.py, src/quoting/__init__.py, tests/quoting/test_mode_selector.py</files>
  <behavior>
    - VEGA_DIRECTIONAL_THRESHOLD is no longer importable from src.config.constants
    - tests/config/test_constants.py EXPECTED_NAMES no longer contains "VEGA_DIRECTIONAL_THRESHOLD"
    - tests/config/test_constants.py passes (allow-list matches actual module surface)
    - trading_mode(state, theo, market, vega_between=0.0, vega_post_plant=0.0, kill_switch_active=True) returns "IDLE" regardless of all other inputs (rule 1)
    - trading_mode(bomb_planted=True, kill_switch_active=False, ...) returns "POST_PLANT_QUOTE" (rule 2)
    - trading_mode(mid-round but bomb_planted=False, ...) returns "IDLE" (rule 3 — no general mid-round path)
    - trading_mode with abs(theo_series*100 - market.mid) > TAKE_THRESHOLD returns "DIRECTIONAL_TAKE" (rule 4)
    - trading_mode with market.spread > MM_MIN_EDGE returns "MM_BETWEEN_ROUND" (rule 5)
    - trading_mode falling through all rules returns "IDLE" (rule 6)
    - Tie-break: when |theo*100 - market.mid| > TAKE_THRESHOLD AND market.spread > MM_MIN_EDGE both hold, returns "DIRECTIONAL_TAKE" (declared order, RESEARCH Pitfall 3)
    - trading_mode is pure: same inputs always produce same output (no hidden state)
  </behavior>
  <action>
(A) Atomic delete VEGA_DIRECTIONAL_THRESHOLD from src/config/constants.py.

    Use Edit tool with old_string spanning the constant declaration AND its
    docstring AND the section header:
    ```
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
    Replace with EMPTY STRING (delete the section entirely). The TAKE_THRESHOLD
    / MM_MIN_EDGE / POST_PLANT_TAKE_THRESHOLD / MIN_HALF_SPREAD constants in
    the "Phase 4 — quoting layer thresholds" section (added by plan 04-00) are
    the v2 replacement.

(B) Atomic update tests/config/test_constants.py — remove "VEGA_DIRECTIONAL_THRESHOLD"
    from EXPECTED_NAMES tuple AND from EXPECTED_TYPES dict.

    Use Edit tool with old_string = `"VEGA_DIRECTIONAL_THRESHOLD",\n` and
    new_string = `` (empty). Repeat for the EXPECTED_TYPES entry.

    If there is a section comment "Mode flip" between the kill-switch entries
    and the Phase 2 entries, drop it as well (now-empty section).

(C) Create src/quoting/mode_selector.py:

```python
"""Pure-function mode selector — REQ-mode-selector v2 (DEC-001 v2).

Six rules in declared order; literal source-code order IS the priority.
DO NOT use match statements, dict dispatch, or "highest priority wins"
tables — RESEARCH Pitfall 3 demands a sequence of `if ... return ...`
statements so the priority is grep-discoverable.

The function is PURE: same inputs always produce the same output. No I/O,
no hidden state, no class members. The caller passes the kill-switch
result (KillSwitchAggregator.any_tripped()[0]) explicitly so this module
doesn't need to know how kill switches are evaluated.

MM_BETWEEN_ROUND and DIRECTIONAL_TAKE are FIRST-CLASS PEERS per PRD §2.1
v2 — the "DIRECTIONAL evaluated before MM" ordering is a tie-break, not a
priority ranking. Paper trade decides which (or both) survives via the
fill-count gate (DEC-020 v2).

VEGA_DIRECTIONAL_THRESHOLD from v1 is REMOVED (DEC-018 v2) — DIRECTIONAL_TAKE
triggers on `|theo - market_mid|`, not vega magnitude.

Source: PRD §2.1 / DEC-001 v2 / ROADMAP §4.2 / RESEARCH §"Pattern 1" + Pitfall 3.
"""
from __future__ import annotations

from typing import Literal

from src.config.constants import MM_MIN_EDGE, TAKE_THRESHOLD
from src.pricing.data import TheoOutput
from src.quoting.market_data import MarketQuote
from src.state.match_state import MatchState

TradingMode = Literal[
    "MM_BETWEEN_ROUND",
    "DIRECTIONAL_TAKE",
    "POST_PLANT_QUOTE",
    "IDLE",
]


def trading_mode(
    state: MatchState,
    theo: TheoOutput,
    market: MarketQuote,
    vega_between: float,
    vega_post_plant: float,
    kill_switch_active: bool,
) -> TradingMode:
    """Return the trading mode for the current (state, theo, market) triple.

    Rules (literal source-code order is priority — RESEARCH Pitfall 3):
        1. kill_switch_active → IDLE
        2. state.bomb_planted → POST_PLANT_QUOTE
        3. mid-round and not bomb_planted → IDLE
        4. |theo - market_mid| > TAKE_THRESHOLD → DIRECTIONAL_TAKE
        5. market.spread > MM_MIN_EDGE → MM_BETWEEN_ROUND
        6. fall-through → IDLE

    Args:
        vega_between: theo.vega (= vega_between_round per DEC-018 D-10/D-11).
            Reserved for the MM_BETWEEN_ROUND quoter; selector currently does
            not use it for routing (DEC-001 v2 routes on |theo - mid| /
            spread, not vega).
        vega_post_plant: variance over {kill, defuse, time-out} outcomes
            computed via compute_vega_post_plant. Reserved for the
            POST_PLANT_QUOTE quoter; selector does not use it for routing.
    """
    # Rule 1: kill-switch dominates everything else.
    if kill_switch_active:
        return "IDLE"

    # Rule 2: bomb-planted → POST_PLANT branch (latency-critical 200ms budget).
    if state.bomb_planted:
        return "POST_PLANT_QUOTE"

    # Rule 3: mid-round-not-planted → IDLE (no general mid-round path per DEC-007 v2).
    if _is_mid_round(state) and not state.bomb_planted:
        return "IDLE"

    # Rules 4 & 5: between-round — DIRECTIONAL evaluated BEFORE MM (declared order).
    theo_cents = round(theo.theo_series * 100)
    if abs(theo_cents - market.mid) > TAKE_THRESHOLD:
        return "DIRECTIONAL_TAKE"
    if market.spread > MM_MIN_EDGE:
        return "MM_BETWEEN_ROUND"

    # Rule 6: fall-through.
    return "IDLE"


def _is_mid_round(state: MatchState) -> bool:
    """Mid-round means a round is in progress with the timer running.

    Phase 03 D-14 carry-forward: state.time_left_s is None except when
    bomb_planted=True OR a separate timer source has populated it. For
    Phase 04 we treat `time_left_s is not None` as the mid-round signal.
    Phase 5 calibration may refine if false-positives prove material.

    NOTE — when bomb_planted=True, both attackers_alive/defenders_alive AND
    time_left_s are populated, but rule 2 (state.bomb_planted) fires first
    and routes to POST_PLANT_QUOTE before this helper is reached.
    """
    return state.time_left_s is not None
```

(D) Update src/quoting/__init__.py to export trading_mode + TradingMode.

(E) Flip RED stubs in tests/quoting/test_mode_selector.py to GREEN. Required tests:

```python
"""Plan 04-04 — REQ-mode-selector (v2 three-way + IDLE) GREEN tests.

Six rules in declared order. Tie-break test verifies RESEARCH Pitfall 3
(DIRECTIONAL evaluated BEFORE MM when both conditions hold).
"""
from __future__ import annotations

from src.pricing.data import TheoOutput
from src.quoting.market_data import make_quote
from src.quoting.mode_selector import trading_mode


def _theo(theo_series: float = 0.50) -> TheoOutput:
    return TheoOutput(theo_series=theo_series, theo_map=(theo_series,),
                       vega=0.0, confidence=1.0)


def test_rule_1_kill_switch_dominates_bomb_planted(make_match_state) -> None:
    """Rule 1: kill_switch_active=True returns IDLE even when bomb_planted=True."""
    state = make_match_state(bomb_planted=True, attackers_alive=2,
                              defenders_alive=3, time_left_s=20.0)
    market = make_quote(48, 52)
    assert trading_mode(state, _theo(0.99), market, 0.0, 0.0,
                          kill_switch_active=True) == "IDLE"


def test_rule_2_bomb_planted_returns_post_plant_quote(make_match_state) -> None:
    """Rule 2: bomb_planted=True → POST_PLANT_QUOTE when kill switch is not active."""
    state = make_match_state(bomb_planted=True, attackers_alive=2,
                              defenders_alive=3, time_left_s=20.0)
    market = make_quote(48, 52)
    assert trading_mode(state, _theo(0.50), market, 0.0, 0.0,
                          kill_switch_active=False) == "POST_PLANT_QUOTE"


def test_rule_3_mid_round_not_planted_returns_idle(make_match_state) -> None:
    """Rule 3: time_left_s is not None AND bomb_planted=False → IDLE."""
    state = make_match_state(bomb_planted=False, time_left_s=30.0)  # mid-round timer
    market = make_quote(48, 52)
    # theo=0.99 vs mid=50 would normally trigger DIRECTIONAL, but rule 3 fires first.
    assert trading_mode(state, _theo(0.99), market, 0.0, 0.0,
                          kill_switch_active=False) == "IDLE"


def test_rule_4_take_threshold_returns_directional(make_match_state) -> None:
    """Rule 4: |theo*100 - market.mid| > TAKE_THRESHOLD (5) → DIRECTIONAL_TAKE."""
    state = make_match_state(bomb_planted=False, time_left_s=None)  # between-round
    market = make_quote(40, 44)  # mid=42, spread=4
    # theo=0.50 (50c), mid=42 → |50-42| = 8 > 5 → DIRECTIONAL
    assert trading_mode(state, _theo(0.50), market, 0.0, 0.0,
                          kill_switch_active=False) == "DIRECTIONAL_TAKE"


def test_rule_5_mm_min_edge_returns_mm_between_round(make_match_state) -> None:
    """Rule 5: market.spread > MM_MIN_EDGE (4) → MM_BETWEEN_ROUND."""
    state = make_match_state(bomb_planted=False, time_left_s=None)
    market = make_quote(46, 54)  # mid=50, spread=8 > 4
    # theo=0.50, mid=50 → diff=0 < 5 (rule 4 false), spread=8 > 4 (rule 5 true)
    assert trading_mode(state, _theo(0.50), market, 0.0, 0.0,
                          kill_switch_active=False) == "MM_BETWEEN_ROUND"


def test_rule_6_fall_through_returns_idle(make_match_state) -> None:
    """Rule 6: fall-through (no rule fires) → IDLE."""
    state = make_match_state(bomb_planted=False, time_left_s=None)
    market = make_quote(49, 51)  # mid=50, spread=2
    # theo=0.50, diff=0 < 5; spread=2 < 4 → all rules fall through → IDLE
    assert trading_mode(state, _theo(0.50), market, 0.0, 0.0,
                          kill_switch_active=False) == "IDLE"


def test_tie_directional_dominates_mm(make_match_state) -> None:
    """Pitfall 3: when BOTH rule 4 AND rule 5 conditions hold, declared order
    says rule 4 (DIRECTIONAL_TAKE) wins."""
    state = make_match_state(bomb_planted=False, time_left_s=None)
    market = make_quote(40, 50)  # mid=45, spread=10 > 4
    # theo=0.60 (60c), mid=45 → |60-45|=15 > 5 (rule 4) AND spread=10 > 4 (rule 5)
    assert trading_mode(state, _theo(0.60), market, 0.0, 0.0,
                          kill_switch_active=False) == "DIRECTIONAL_TAKE"


def test_pure_function_no_hidden_state(make_match_state) -> None:
    """Same inputs → same output across multiple calls."""
    state = make_match_state(bomb_planted=False, time_left_s=None)
    market = make_quote(46, 54)
    results = [trading_mode(state, _theo(0.50), market, 0.0, 0.0, False)
                for _ in range(10)]
    assert all(r == results[0] for r in results)
```
  </action>
  <verify>
    <automated>uv run pytest tests/config/test_constants.py tests/quoting/test_mode_selector.py -x --no-cov &amp;&amp; uv run mypy --strict src/quoting/ src/state/ src/pricing/</automated>
  </verify>
  <done>
- VEGA_DIRECTIONAL_THRESHOLD no longer in src/config/constants.py (verified by `rg "VEGA_DIRECTIONAL_THRESHOLD" src/`).
- tests/config/test_constants.py allow-list updated atomically; passes.
- src/quoting/mode_selector.py defines TradingMode + trading_mode + _is_mid_round.
- 8 tests in tests/quoting/test_mode_selector.py pass GREEN.
- mypy --strict src/quoting/ + src/state/ + src/pricing/ clean.
- src/quoting/__init__.py exports TradingMode + trading_mode.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: src/pricing/live_theo.compute_vega_post_plant + GREEN test_vega_post_plant.py</name>
  <files>src/pricing/live_theo.py, tests/pricing/test_vega_post_plant.py</files>
  <behavior>
    - compute_vega_post_plant(state, lookup) returns a non-negative float
    - When state.bomb_planted=False, function returns 0.0 (no post-plant context)
    - When state.bomb_planted=True with attackers_alive=2, defenders_alive=3, time_left_s=20.0, returns variance over neighbor cells reachable via plausible {kill, defuse, time-out} transitions
    - For an extreme cell (att=5, def=0 — defenders dead, no defuse possible), variance is small (low uncertainty; theo near 1.0 across all outcomes)
    - For a balanced cell (att=2, def=2, mid-time), variance is non-trivial
    - Function is pure (no I/O) — tests assert deterministic output across multiple calls
    - Function does NOT crash on sparse cells — falls back to between-round vega = 0 if neighbor cells aren't populated (defensive None-guard mirroring Phase 03 D-05)
  </behavior>
  <action>
(A) Extend src/pricing/live_theo.py with `compute_vega_post_plant`. Add it as a
    new top-level function (NOT a method of LiveTheoEngine — pure-function shape
    matches the existing `_live_theo_impl` pattern):

```python
# --------------------------------------------------------------------------- #
# 4. Post-plant vega (DEC-018 v2 second arm — REQ-vega-output)                #
# --------------------------------------------------------------------------- #

def compute_vega_post_plant(
    state: MatchState,
    lookup: RoundConclusionLookup,
) -> float:
    """Variance over post-plant outcomes {kill, defuse, time-out}.

    Mirrors the between-round vega shape (DEC-018 D-10/D-11):
        var = sum_{o in outcomes} P(o) * (theo_after_outcome - theo_now)**2

    Outcomes parameterized by (att, def, time_bucket); the post-plant
    lookup hierarchy provides the marginal probability per outcome.

    Returns 0.0 when state.bomb_planted=False (no post-plant context) — the
    mode selector reads this in the IDLE / between-round branches and
    correctly avoids using it for routing.

    Returns 0.0 on sparse cells (defensive fallback, mirroring Phase 03
    D-05 between-round-fn semantics) — Phase 5 calibration prioritizes
    populating sparse cells.

    DEC-018 v2: this formula is TBD per PRD §9.5. The shape implemented
    here is the recommended starting point per RESEARCH §"Open Questions"
    #2; calibrate concretely in Phase 5 against logged post-plant theo
    updates by minimizing realized vega-vs-spread tracking error.

    TODO(phase-5-calibrate): refine outcome probabilities + theo-after
    transitions once calibration data exists.

    Source: REQ-vega-output / DEC-018 v2 / RESEARCH §"Open Questions" #2.
    """
    if not state.bomb_planted:
        return 0.0
    if state.attackers_alive is None or state.defenders_alive is None:
        return 0.0
    if state.time_left_s is None:
        return 0.0

    side = state.side_orient
    map_name = state.map_pool[state.map_idx]
    att = state.attackers_alive
    def_ = state.defenders_alive
    time_bucket = int(state.time_left_s // TIME_BUCKET_WIDTH_S)

    # Current post-plant theo (the cell estimate).
    p_now = lookup.post_plant_p(att, def_, time_bucket, side, map_name)

    # Three plausible outcomes:
    #   - kill: defender team killed (att, def_ - 1)        — attackers win round
    #   - defuse: defender defuses (att, def_) at time 0    — defenders win round
    #   - time-out: timer expires (att, def_) at time 0     — attackers win round
    # Phase 04 simplification: equal-probability weights (1/3 each); Phase 5
    # calibration replaces with empirical frequencies. The variance is what
    # quote-width sizing consumes; getting the SHAPE right matters more than
    # getting the EXACT probabilities right at this stage.
    p_kill = lookup.post_plant_p(att, max(0, def_ - 1), time_bucket, side, map_name)
    p_defuse = lookup.post_plant_p(att, def_, 0, side, map_name)
    p_timeout = lookup.post_plant_p(att, def_, 0, side, map_name)

    weights = (1 / 3, 1 / 3, 1 / 3)
    outcomes = (p_kill, p_defuse, p_timeout)
    return sum(w * (p_outcome - p_now) ** 2 for w, p_outcome in zip(weights, outcomes))
```

    Add the import at the top of the file:
    ```python
    from src.config.constants import (
        # ... existing imports
        TIME_BUCKET_WIDTH_S,
    )
    ```

(B) Create tests/pricing/test_vega_post_plant.py with 6+ tests:

```python
"""Plan 04-04 — REQ-vega-output (DEC-018 v2 second arm) tests.

compute_vega_post_plant returns variance over {kill, defuse, time-out}
post-plant outcomes. Pure function — no I/O.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.pricing.live_theo import compute_vega_post_plant
from src.pricing.round_conclusion import RoundConclusionLookup


@pytest.fixture
def lookup() -> RoundConclusionLookup:
    """Load the calibrated v2 lookup from disk (shipped by plan 03-07)."""
    return RoundConclusionLookup.from_json("models/round_conclusion.json")


def test_returns_zero_when_not_bomb_planted(make_match_state, lookup) -> None:
    state = make_match_state(bomb_planted=False)
    assert compute_vega_post_plant(state, lookup) == 0.0


def test_returns_zero_when_attackers_alive_none(make_match_state, lookup) -> None:
    """Defensive None-guard mirroring Phase 03 D-05."""
    state = make_match_state(bomb_planted=True, attackers_alive=None,
                              defenders_alive=3, time_left_s=20.0)
    assert compute_vega_post_plant(state, lookup) == 0.0


def test_returns_zero_when_defenders_alive_none(make_match_state, lookup) -> None:
    state = make_match_state(bomb_planted=True, attackers_alive=2,
                              defenders_alive=None, time_left_s=20.0)
    assert compute_vega_post_plant(state, lookup) == 0.0


def test_returns_zero_when_time_left_none(make_match_state, lookup) -> None:
    state = make_match_state(bomb_planted=True, attackers_alive=2,
                              defenders_alive=3, time_left_s=None)
    assert compute_vega_post_plant(state, lookup) == 0.0


def test_returns_non_negative_for_bomb_planted_state(make_match_state, lookup) -> None:
    state = make_match_state(bomb_planted=True, attackers_alive=2,
                              defenders_alive=2, time_left_s=20.0)
    result = compute_vega_post_plant(state, lookup)
    assert result >= 0.0


def test_pure_function(make_match_state, lookup) -> None:
    """Same inputs → same output across multiple calls."""
    state = make_match_state(bomb_planted=True, attackers_alive=3,
                              defenders_alive=2, time_left_s=15.0)
    results = [compute_vega_post_plant(state, lookup) for _ in range(5)]
    assert all(r == results[0] for r in results)


def test_defenders_dead_low_variance(make_match_state, lookup) -> None:
    """When defenders are dead (def=0), no defuse possible → low variance.

    All three outcomes converge near p_now → variance close to 0.
    """
    state = make_match_state(bomb_planted=True, attackers_alive=5,
                              defenders_alive=0, time_left_s=20.0)
    result = compute_vega_post_plant(state, lookup)
    # Floor: should be very small but non-negative.
    assert 0.0 <= result <= 0.05
```
  </action>
  <verify>
    <automated>uv run pytest tests/pricing/test_vega_post_plant.py -x --no-cov &amp;&amp; uv run mypy --strict src/pricing/</automated>
  </verify>
  <done>
- src/pricing/live_theo.py exports compute_vega_post_plant.
- 7 tests in tests/pricing/test_vega_post_plant.py pass GREEN.
- Function is pure; defensive None-guards mirror Phase 03 D-05.
- mypy --strict src/pricing/ clean (Phase 1 + Phase 3 baseline preserved).
  </done>
</task>

</tasks>

<verification>
1. `rg "VEGA_DIRECTIONAL_THRESHOLD" src/ tests/` returns empty (constant fully deleted; no orphan references).
2. `uv run pytest tests/config/test_constants.py tests/quoting/test_mode_selector.py tests/pricing/test_vega_post_plant.py -x --no-cov` all GREEN.
3. `uv run mypy --strict src/quoting/ src/state/ src/pricing/` clean.
4. `uv run pytest tests/ -x --no-cov` — Phase 03 + plans 04-00..04-04 GREEN; remaining stubs (05, 06, 07, 08) xfail.
5. `python -c "from src.quoting import trading_mode, TradingMode; print(TradingMode)"` runs without ImportError.
</verification>

<success_criteria>
- VEGA_DIRECTIONAL_THRESHOLD deletion + tests/config allow-list update happen in the SAME commit (verifies same-commit Rule-3 prophylactic).
- trading_mode is a pure function with 6 rules in declared order.
- Tie-break test (test_tie_directional_dominates_mm) verifies RESEARCH Pitfall 3 mitigation.
- compute_vega_post_plant ships as DEC-018 v2 second arm with explicit Phase 5 calibration TODO.
</success_criteria>

<output>
After completion, create `.planning/phases/04-quoting-layer/04-04-SUMMARY.md` documenting:
- VEGA_DIRECTIONAL_THRESHOLD atomic deletion (constants.py + test_constants.py allow-list updated together).
- src/quoting/mode_selector.py file contents + 8 tests.
- src/pricing/live_theo.compute_vega_post_plant addition + 7 tests.
- Forward link: plans 04-05 (MM quoter consumes vega_between via theo.vega), 04-06 (directional taker consumes mode_selector return), 04-07 (post-plant quoter consumes vega_post_plant), 04-08 (e2e test composes the full pipe).
</output>
