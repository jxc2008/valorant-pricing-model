---
id: 03-03-match-state-move-and-extend
phase: 03
plan: 3
type: execute
wave: 2
depends_on:
  - 03-00-pyproject-and-constants
  - 03-01-shared-types-and-download
files_modified:
  - src/state/match_state.py
  - src/state/__init__.py
  - src/pricing/data.py
  - src/pricing/__init__.py
  - src/pricing/live_theo.py
  - src/pricing/round_types.py
  - tests/pricing/test_live_theo.py
  - tests/pricing/test_live_theo_with_calibrated_round_conclusion.py
  - tests/pricing/test_round_types.py
  - tests/state/test_match_state.py
autonomous: true
requirements:
  - REQ-match-state-engine
user_setup: []
must_haves:
  truths:
    - "MatchState lives at src/state/match_state.py with 25 fields (17 Phase 1 verbatim + 8 Phase 3 additions per RESEARCH Code Examples lines 793-804)"
    - "MatchState stays @dataclass(frozen=True, slots=True) (D-01)"
    - "with_update(**diffs) returns a new instance with seq_id = state.seq_id + 1, last_updated_ts = time.time(); strips caller-provided seq_id/last_updated_ts (D-01 + RESEARCH Pattern 1 defensive)"
    - "All 5 in-repo MatchState import sites rewritten to from src.state.match_state import MatchState; src/pricing/data.py is either deleted or holds only HalfRates+TheoOutput (Option B per PATTERNS line 675)"
    - "tests/pricing/test_round_types.py:300 string-literal regression assertion retargeted to from src.state.match_state import MatchState"
    - "src/pricing/__init__.py public surface preserved (LiveTheoEngine, TheoOutput, MatchState, HalfRates) — MatchState now resolves through re-export"
    - "mypy --strict src/pricing/ AND mypy --strict src/state/ both clean"
    - "1000-mutator hypothesis test exercises seq_id strict monotonicity over >= 20k mutations; with_update strip-defensive test passes; JSONL replay round-trip test passes"
    - "All Phase 1 + 2 tests still GREEN (regression gate per SPEC acceptance #11)"
  artifacts:
    - path: src/state/match_state.py
      provides: "MatchState (frozen+slots, 25 fields, with_update mutator)"
      contains: "def with_update("
    - path: src/state/__init__.py
      provides: "MatchState re-export"
      exports: ["MatchState"]
    - path: src/pricing/data.py
      provides: "HalfRates + TheoOutput only (MatchState removed)"
      contains: "class TheoOutput"
    - path: tests/state/test_match_state.py
      provides: "5+ tests: monotonicity, replay round-trip, strip-defensive, field-count, slots"
  key_links:
    - from: "src/pricing/live_theo.py"
      to: "src/state/match_state.py"
      via: "from src.state.match_state import MatchState"
      pattern: "from src\\.state\\.match_state import MatchState"
    - from: "src/state/match_state.py:with_update"
      to: "self.seq_id"
      via: "replace(self, seq_id=self.seq_id + 1, ...)"
      pattern: "seq_id=self\\.seq_id \\+ 1"
---

<objective>
Wave 1 atomic plan — move `MatchState` from `src/pricing/data.py` to `src/state/match_state.py`, extend it with the 8 Phase 3 fields per CONTEXT D-02 carry-forward, add the `with_update` mutator per D-01, rewrite all in-repo import sites in one commit, and add the property-test gate (1000-mutator monotonicity + JSONL replay round-trip).

Purpose: this is the single most disruptive change in Phase 3. Doing it in ONE atomic plan (per SPEC.md "atomic move from src/pricing/data.py to src/state/match_state.py with Phase 3 fields added in ONE plan" + CONTEXT D-14) keeps the import-rewrite blast radius contained — no Wave 2 plan inherits a half-migrated state.

Output: new `src/state/match_state.py` with 25-field MatchState + `with_update`; rewritten imports across 5 in-repo sites + 1 string-literal regression assertion; `tests/state/test_match_state.py` covering D-01 + D-02 invariants + JSONL replay; `src/pricing/data.py` shrunk to just `HalfRates` + `TheoOutput`.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/03-live-ingestion-layer/03-SPEC.md
@.planning/phases/03-live-ingestion-layer/03-CONTEXT.md
@.planning/phases/03-live-ingestion-layer/03-RESEARCH.md
@.planning/phases/03-live-ingestion-layer/03-PATTERNS.md
@.planning/phases/03-live-ingestion-layer/03-VALIDATION.md
@src/pricing/data.py
@src/pricing/__init__.py
@src/pricing/live_theo.py
@src/pricing/round_types.py
@tests/pricing/test_live_theo.py
@tests/pricing/test_live_theo_with_calibrated_round_conclusion.py
@tests/pricing/test_round_types.py
@tests/pricing/test_dp.py
@tests/pricing/test_round_conclusion_loader.py
@CLAUDE.md

<interfaces>
<!-- Phase 1 MatchState (verbatim from src/pricing/data.py:59-105) — copy these 17 fields verbatim. -->

```python
@dataclass(frozen=True, slots=True)
class MatchState:
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
    map_winners: tuple[Optional[bool], ...]  # noqa: UP045 — Optional[bool] required for tuple keying
    pistol_winner_a: dict[int, Optional[bool]]  # noqa: UP045 — Optional[bool] kept for clarity
    numerical_diff: int
    bomb_planted: bool
    side: str
    econ_bucket: str
```

<!-- 5 import sites needing rewrite (grep results) -->

```
src/pricing/__init__.py:16   from src.pricing.data import HalfRates, MatchState, TheoOutput
src/pricing/live_theo.py:42  from src.pricing.data import HalfRates, MatchState, TheoOutput
src/pricing/round_types.py:55 (TYPE_CHECKING block):  from src.pricing.data import MatchState
tests/pricing/test_live_theo.py:30        from src.pricing.data import HalfRates, MatchState, TheoOutput
tests/pricing/test_live_theo_with_calibrated_round_conclusion.py:41  from src.pricing.data import HalfRates, MatchState, TheoOutput
```

<!-- 1 string-literal regression assertion (grep result) -->

```
tests/pricing/test_round_types.py:300   assert "from src.pricing.data import MatchState" in src
tests/pricing/test_round_types.py:302   matchstate_idx = src.find("from src.pricing.data import MatchState")
```

<!-- Mutator pattern from RESEARCH Pattern 1 + Code Examples lines 806-810 -->

```python
def with_update(self, **diffs: Any) -> Self:
    diffs.pop("seq_id", None)
    diffs.pop("last_updated_ts", None)
    return replace(self, seq_id=self.seq_id + 1, last_updated_ts=time.time(), **diffs)
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Create src/state/match_state.py with 25-field MatchState + with_update mutator</name>
  <files>src/state/match_state.py, src/state/__init__.py, tests/state/test_match_state.py</files>
  <read_first>
    - src/pricing/data.py (entire file — verbatim source for the 17 Phase 1 fields)
    - .planning/phases/03-live-ingestion-layer/03-PATTERNS.md §src/state/match_state.py block (lines 46-119)
    - .planning/phases/03-live-ingestion-layer/03-RESEARCH.md §Code Examples MatchState v2 dataclass (lines 754-810)
    - .planning/phases/03-live-ingestion-layer/03-RESEARCH.md §Common Pitfalls Pitfall 7 (replace + slots interaction — keep MatchState shape simple, no __post_init__)
    - .planning/phases/03-live-ingestion-layer/03-VALIDATION.md Sampling minimums (lines 67-68)
    - tests/pricing/test_dp.py:111-117 (hypothesis @given + @settings(max_examples=N) analog)
    - tests/pricing/test_live_theo.py:52-94 (frozen-dataclass shape test analog)
  </read_first>
  <behavior>
    - Test 1 (test_match_state_is_25_field_frozen_slots): MatchState is a frozen+slots dataclass with EXACTLY 25 fields whose names match the union of the 17 Phase 1 names + the 8 Phase 3 names; mypy and ruff pass.
    - Test 2 (test_with_update_bumps_seq_id_and_ts): state.with_update(numerical_diff=5).seq_id == state.seq_id + 1; .last_updated_ts > state.last_updated_ts; .numerical_diff == 5.
    - Test 3 (test_with_update_strips_seq_id_override): state.with_update(seq_id=999, numerical_diff=5).seq_id == state.seq_id + 1 (NOT 999); .numerical_diff == 5.
    - Test 4 (test_with_update_strips_last_updated_ts_override): state.with_update(last_updated_ts=42.0, numerical_diff=5).last_updated_ts != 42.0.
    - Test 5 (test_with_update_replace_slots_smoke): basic dataclasses.replace(state, a_round=5).a_round == 5 (Pitfall 7 regression smoke).
    - Test 6 (test_seq_id_monotonic_1000_mutators): hypothesis property — generate a list of 1000 random diff-dicts; apply each via with_update; assert seq_ids are strictly monotonic and dense (i, i+1, i+2, ...). @settings(max_examples=20, deadline=None) per VALIDATION line 67. Total: 20 * 1000 = 20k mutations exercised.
    - Test 7 (test_jsonl_replay_round_trip): write 1000 with_update events as diff-only JSONL; replay by re-applying with_update on a seed; assert final state equals the directly-mutated final state on every non-time field. Per VALIDATION line 68.
    - Test 8 (test_phase3_fields_present_with_correct_defaults): seq_id default 0; last_updated_ts is a float; players_alive_a/b default 5; ults_a/b default 0; time_left_s default 100.0; econ_a/b default 0.
  </behavior>
  <action>
Create `src/state/match_state.py`:

```python
"""Phase 3 versioned MatchState — moved from src/pricing/data.py per D-14.

Frozen+slots invariant preserved (D-01). Single mutator: with_update().
Caller (sole writer = arbiter) bumps seq_id and last_updated_ts atomically
with the diff. Defensive: strips caller-provided seq_id / last_updated_ts
overrides so the mutator's invariant cannot be violated by accident.

Fields (25 total = 17 Phase 1 + 8 Phase 3):
  Phase 1 (verbatim from previous src/pricing/data.py:60-105):
    Identity:                match_id, team_a, team_b
    Series state:            map_pool, map_idx, a_map_score, b_map_score
    Within-map state:        a_round, b_round, side_orient
    Per-map sides+winners:   map_side_orients, map_winners
    Pistol memory:           pistol_winner_a
    Mid-round signals:       numerical_diff, bomb_planted, side, econ_bucket
  Phase 3 additions (D-02 + REQ-match-state-engine):
    Versioning:              seq_id, last_updated_ts
    Live HUD signals:        players_alive_a, players_alive_b, ults_a, ults_b,
                             time_left_s, econ_a, econ_b

The arbiter is the sole writer (D-04 + 03-CONTEXT integration_points line 148);
no other module mutates state. mypy --strict per pyproject.toml `src.state.*`
override block (added by 03-00).

Sources
-------
- 03-SPEC.md §1 (REQ-match-state-engine)
- 03-CONTEXT.md D-01 (mutator API), D-02 (8 new fields + JSONL diff schema), D-14 (atomic move)
- 03-RESEARCH.md §Architecture Patterns Pattern 1 (frozen+slots with_update mutator)
- 03-RESEARCH.md §Code Examples MatchState v2 dataclass (lines 754-810)
- 03-RESEARCH.md §Common Pitfalls Pitfall 7 (replace + slots interaction — no __post_init__)
- 03-PATTERNS.md §src/state/match_state.py (lines 46-119)
- src/pricing/data.py:32-105 (Phase 1 source — fields 1-17 copied verbatim)
- Phase 1 D-02 (Phase 3 fields explicitly deferred; this plan unblocks them)
- Phase 1 D-14 (MatchState location moves here)
- Phase 1 D-20 (LiveTheoEngine bundle signature unchanged — only what flows through state changes)
- Phase 2 D-08 (carry-forward semantics — implemented natively by replace-with-only-changed-fields)
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field, replace
from typing import Any, Optional, Self


@dataclass(frozen=True, slots=True)
class MatchState:
    """Versioned, frozen+slots MatchState (D-01 + D-02).

    See module docstring for field lineage. Constructor: positional args for the
    17 required Phase 1 fields; the 8 Phase 3 fields all have defaults so legacy
    Phase 1 callers (e.g., tests/pricing/test_live_theo.py) do not need to supply
    them.
    """

    # --- Phase 1 fields (verbatim from src/pricing/data.py:89-105) ---
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
    map_winners: tuple[Optional[bool], ...]  # noqa: UP045 — Optional[bool] required for tuple keying
    pistol_winner_a: dict[int, Optional[bool]]  # noqa: UP045 — Optional[bool] kept for clarity
    numerical_diff: int
    bomb_planted: bool
    side: str
    econ_bucket: str
    # --- Phase 3 additions (D-02 — REQ-match-state-engine) ---
    seq_id: int = 0
    last_updated_ts: float = field(default_factory=time.time)
    players_alive_a: int = 5
    players_alive_b: int = 5
    ults_a: int = 0
    ults_b: int = 0
    time_left_s: float = 100.0
    econ_a: int = 0
    econ_b: int = 0

    def with_update(self, **diffs: Any) -> Self:
        """Return a new MatchState with seq_id bumped + last_updated_ts refreshed.

        Defensive: strips caller-provided seq_id / last_updated_ts overrides
        BEFORE replace(), so the mutator's invariant ("seq_id strictly
        increases by 1 per call") cannot be broken by accident.

        Sources
        -------
        - 03-RESEARCH.md §Architecture Patterns Pattern 1 (line 256)
        - 03-CONTEXT.md D-01 (mutator API)
        """
        diffs.pop("seq_id", None)
        diffs.pop("last_updated_ts", None)
        return replace(
            self,
            seq_id=self.seq_id + 1,
            last_updated_ts=time.time(),
            **diffs,
        )
```

Then update `src/state/__init__.py`:

```python
"""State engine — versioned MatchState + JSONL event log (Phase 3).

This package is type-checked under `mypy --strict` (SPEC.constraints — extends
Phase 1's CON-mypy-strict-pricing scope from src/pricing/ to src/state/).

Public surface:
    MatchState     — frozen+slots dataclass (25 fields) with seq_id-bumping
                     with_update mutator (D-01, D-02).
"""

from src.state.match_state import MatchState

__all__ = ["MatchState"]
```

Then create `tests/state/test_match_state.py`:

```python
"""Phase 3 MatchState tests — REQ-match-state-engine acceptance.

Covers D-01 (frozen+slots + with_update mutator semantics), D-02 (25-field
schema), and the seq_id monotonicity + JSONL replay invariants per
03-VALIDATION.md sampling minimums (lines 67-68).

Sources
-------
- 03-SPEC.md §1 (REQ-match-state-engine acceptance)
- 03-CONTEXT.md D-01 (mutator), D-02 (8 new fields)
- 03-RESEARCH.md §Architecture Patterns Pattern 1
- 03-VALIDATION.md Sampling minimums (lines 67-68)
- tests/pricing/test_dp.py:111-117 (hypothesis @given+@settings analog)
- tests/pricing/test_live_theo.py:52-94 (frozen-dataclass shape test analog)
"""
from __future__ import annotations

import dataclasses
import json
import time
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from src.state.match_state import MatchState


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #


def _seed_state() -> MatchState:
    """Minimal valid MatchState — 17 Phase 1 fields populated, 8 Phase 3 defaults."""
    return MatchState(
        match_id="m1",
        team_a="A",
        team_b="B",
        map_pool=("Lotus", "Bind", "Haven"),
        map_idx=0,
        a_map_score=0,
        b_map_score=0,
        a_round=0,
        b_round=0,
        side_orient="a_atk",
        map_side_orients=("a_atk", "a_def", "a_atk"),
        map_winners=(None, None, None),
        pistol_winner_a={0: None, 1: None, 2: None},
        numerical_diff=0,
        bomb_planted=False,
        side="atk",
        econ_bucket="full",
    )


# --------------------------------------------------------------------------- #
# Schema / shape tests                                                        #
# --------------------------------------------------------------------------- #


def test_match_state_is_25_field_frozen_slots_dataclass() -> None:
    """REQ-match-state-engine: 17 Phase 1 + 8 Phase 3 fields; frozen+slots."""
    assert dataclasses.is_dataclass(MatchState)
    fields = dataclasses.fields(MatchState)
    field_names = {f.name for f in fields}
    assert len(fields) == 25, (
        f"expected 25 fields (17 Phase 1 + 8 Phase 3), got {len(fields)}: "
        f"{sorted(field_names)}"
    )
    expected_phase1 = {
        "match_id", "team_a", "team_b", "map_pool", "map_idx",
        "a_map_score", "b_map_score", "a_round", "b_round", "side_orient",
        "map_side_orients", "map_winners", "pistol_winner_a",
        "numerical_diff", "bomb_planted", "side", "econ_bucket",
    }
    expected_phase3 = {
        "seq_id", "last_updated_ts", "players_alive_a", "players_alive_b",
        "ults_a", "ults_b", "time_left_s", "econ_a", "econ_b",
    }
    assert field_names == expected_phase1 | expected_phase3
    # frozen+slots invariant
    assert MatchState.__dataclass_params__.frozen is True
    assert MatchState.__dataclass_params__.slots is True


def test_phase3_field_defaults() -> None:
    """D-02: Phase 3 additions have sensible defaults so Phase 1 callers don't break."""
    s = _seed_state()
    assert s.seq_id == 0
    assert isinstance(s.last_updated_ts, float)
    assert s.players_alive_a == 5
    assert s.players_alive_b == 5
    assert s.ults_a == 0
    assert s.ults_b == 0
    assert s.time_left_s == 100.0
    assert s.econ_a == 0
    assert s.econ_b == 0


# --------------------------------------------------------------------------- #
# Mutator tests (D-01)                                                        #
# --------------------------------------------------------------------------- #


def test_with_update_bumps_seq_id_and_refreshes_ts() -> None:
    s = _seed_state()
    t0 = s.last_updated_ts
    time.sleep(0.001)  # ensure clock advances on fast platforms
    s2 = s.with_update(numerical_diff=5)
    assert s2.seq_id == s.seq_id + 1
    assert s2.last_updated_ts > t0
    assert s2.numerical_diff == 5
    # original immutable
    assert s.numerical_diff == 0
    assert s.seq_id == 0


def test_with_update_strips_seq_id_override() -> None:
    """D-01 defensive: caller cannot override seq_id."""
    s = _seed_state()
    s2 = s.with_update(seq_id=999, numerical_diff=5)
    assert s2.seq_id == s.seq_id + 1  # NOT 999
    assert s2.numerical_diff == 5


def test_with_update_strips_last_updated_ts_override() -> None:
    """D-01 defensive: caller cannot override last_updated_ts."""
    s = _seed_state()
    s2 = s.with_update(last_updated_ts=42.0, numerical_diff=5)
    assert s2.last_updated_ts != 42.0
    assert s2.numerical_diff == 5


def test_replace_slots_smoke() -> None:
    """Pitfall 7 regression: dataclasses.replace works on frozen+slots MatchState."""
    s = _seed_state()
    s2 = dataclasses.replace(s, a_round=5)
    assert s2.a_round == 5
    assert s.a_round == 0  # original immutable


# --------------------------------------------------------------------------- #
# Property tests (VALIDATION sampling minimums)                               #
# --------------------------------------------------------------------------- #


_diff_keys = st.sampled_from([
    "a_round", "b_round", "numerical_diff", "players_alive_a",
    "players_alive_b", "ults_a", "ults_b", "econ_a", "econ_b",
    "bomb_planted", "side",
])


def _draw_diff(draw: Any) -> dict[str, Any]:
    """One random diff dict drawn for a single with_update call."""
    n = draw(st.integers(min_value=0, max_value=3))
    out: dict[str, Any] = {}
    for _ in range(n):
        k = draw(_diff_keys)
        if k == "bomb_planted":
            out[k] = draw(st.booleans())
        elif k == "side":
            out[k] = draw(st.sampled_from(["atk", "def"]))
        else:
            out[k] = draw(st.integers(min_value=-10, max_value=10))
    return out


@st.composite
def _diff_list(draw: Any, n: int) -> list[dict[str, Any]]:
    return [_draw_diff(draw) for _ in range(n)]


@given(diffs=_diff_list(1000))
@settings(max_examples=20, deadline=None)
def test_seq_id_monotonic_1000_mutators(diffs: list[dict[str, Any]]) -> None:
    """REQ-match-state-engine + VALIDATION line 67: seq_id strictly monotonic
    over 1000 random with_update calls. Hypothesis runs 20 examples => 20k mutations."""
    s = _seed_state()
    seq_ids: list[int] = [s.seq_id]
    for d in diffs:
        s = s.with_update(**d)
        seq_ids.append(s.seq_id)
    # strict monotonicity
    assert all(seq_ids[i + 1] == seq_ids[i] + 1 for i in range(len(seq_ids) - 1))
    # density: 0..N
    assert seq_ids == list(range(len(seq_ids)))


@given(diffs=_diff_list(1000))
@settings(max_examples=10, deadline=None)
def test_jsonl_replay_round_trip(tmp_path_factory: pytest.TempPathFactory, diffs: list[dict[str, Any]]) -> None:
    """REQ-match-state-engine + VALIDATION line 68: write 1000 diff lines as
    JSONL; replay in seq_id order; final state equals direct-mutated state
    on every non-time field."""
    seed = _seed_state()
    direct = seed
    for d in diffs:
        direct = direct.with_update(**d)
    # Write diffs as JSONL (D-02 diff-only schema)
    log_path = tmp_path_factory.mktemp("evt") / "match.jsonl"
    with log_path.open("w", encoding="utf-8") as fh:
        for d in diffs:
            fh.write(json.dumps({"fields_changed": d}) + "\n")
    # Replay
    replayed = seed
    for line in log_path.read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        replayed = replayed.with_update(**rec["fields_changed"])
    # Field-by-field equality on everything EXCEPT last_updated_ts (wall-clock differs).
    for f in dataclasses.fields(MatchState):
        if f.name == "last_updated_ts":
            continue
        assert getattr(direct, f.name) == getattr(replayed, f.name), (
            f"field {f.name} mismatch: direct={getattr(direct, f.name)!r} "
            f"replayed={getattr(replayed, f.name)!r}"
        )
```

(The hypothesis composite strategy `_diff_list` constructs lists of random diff-dicts. The 20-example settings on the 1000-element strategy gives 20k total mutations — exactly matching VALIDATION §Sampling minimums.)
  </action>
  <verify>
    <automated>pytest tests/state/test_match_state.py -x &amp;&amp; mypy --strict src/state/ &amp;&amp; ruff check src/state/ tests/state/</automated>
  </verify>
  <done>src/state/match_state.py has MatchState with 25 fields + with_update; 8 tests in tests/state/test_match_state.py PASS (3 schema/defaults + 4 mutator unit + 2 hypothesis property = 9 named test functions, ~20k mutations exercised); mypy --strict src/state/ clean; ruff clean. Phase 1 + 2 tests still GREEN (verified by Task 2's import rewrite + regression run).</done>
</task>

<task type="auto">
  <name>Task 2: Atomic import rewrite — drop MatchState from src/pricing/data.py + retarget all 5 import sites + 1 string-literal regression</name>
  <files>src/pricing/data.py, src/pricing/__init__.py, src/pricing/live_theo.py, src/pricing/round_types.py, tests/pricing/test_live_theo.py, tests/pricing/test_live_theo_with_calibrated_round_conclusion.py, tests/pricing/test_round_types.py</files>
  <read_first>
    - src/pricing/data.py (entire file, especially lines 18-25 imports + 59-105 MatchState block + 113-169 HalfRates block)
    - src/pricing/__init__.py (entire file — 19 lines)
    - src/pricing/live_theo.py:30-50 (import block)
    - src/pricing/round_types.py:50-60 (TYPE_CHECKING block — preserve the TYPE_CHECKING guard pattern, just retarget the import)
    - tests/pricing/test_live_theo.py:1-50 (top of file imports)
    - tests/pricing/test_live_theo_with_calibrated_round_conclusion.py:35-50 (import block)
    - tests/pricing/test_round_types.py:295-310 (the string-literal assertion block)
    - .planning/phases/03-live-ingestion-layer/03-PATTERNS.md §src/pricing/data.py + import-rewrite (lines 636-678)
    - .planning/phases/03-live-ingestion-layer/03-CONTEXT.md `<integration_points>` line 147 (Option B picked: atomic deletion)
  </read_first>
  <action>
This task is the atomic import rewrite. Do all six file edits in one commit so no test ever observes a half-migrated state.

(a) **`src/pricing/data.py`** — delete the `MatchState` dataclass (lines 32 docstring update + 54-105 entire class block). Update the module docstring at top (lines 1-16) to drop the MatchState reference and add a one-line note that MatchState moved to `src/state/match_state.py` per Phase 3 D-14.

The result is a file with `TheoOutput` (lines 27-51) and `HalfRates` (lines 109-169) — about 80-90 lines total. Drop the now-unused `from typing import Optional` import IF it's no longer used (HalfRates uses `Optional[dict[str, Any]]` on line 167 so Optional MAY still be needed; verify by grep).

The file's top-of-module docstring should now read (replace the existing lines 1-16 verbatim):

```python
"""Phase 1 pricing-output + half-rates shapes: HalfRates, TheoOutput.

NOTE: ``MatchState`` was moved to ``src/state/match_state.py`` in Phase 3
(per CONTEXT D-14 atomic move). Downstream code imports MatchState from
``src.state.match_state``; the public ``src.pricing`` package re-exports
it for backward compatibility.

Sources
-------
- prd.md §2 (TheoOutput contract) / §6 (state-only call surface)
- DEC-010 / DEC-012 / D-08 / D-09
- 01-RESEARCH.md §10 (HalfRates loader)
- 03-CONTEXT.md D-14 (MatchState atomic move to src/state/)
- reference/theo_engine.py:84-102 (Bayesian shrinkage salvage source)
"""
```

(b) **`src/pricing/__init__.py`** — keep the public surface intact by re-exporting MatchState from its new home. Replace line 16 `from src.pricing.data import HalfRates, MatchState, TheoOutput` with two lines:

```python
from src.pricing.data import HalfRates, TheoOutput
from src.state.match_state import MatchState  # re-export per D-14 atomic move (03-CONTEXT line 147)
```

`__all__` on line 19 stays unchanged (`["LiveTheoEngine", "TheoOutput", "MatchState", "HalfRates"]`). The "from src.pricing import LiveTheoEngine, TheoOutput, MatchState, HalfRates" pattern in tests/pricing/test_live_theo.py:905 keeps working.

(c) **`src/pricing/live_theo.py`** — replace line 42 `from src.pricing.data import HalfRates, MatchState, TheoOutput` with:

```python
from src.pricing.data import HalfRates, TheoOutput
from src.state.match_state import MatchState
```

(d) **`src/pricing/round_types.py`** — inside the existing `if TYPE_CHECKING:` block on lines 53-55, replace `from src.pricing.data import MatchState` with `from src.state.match_state import MatchState`. Keep the TYPE_CHECKING guard.

(e) **`tests/pricing/test_live_theo.py`** — replace line 30 `from src.pricing.data import HalfRates, MatchState, TheoOutput` with:

```python
from src.pricing.data import HalfRates, TheoOutput
from src.state.match_state import MatchState
```

(f) **`tests/pricing/test_live_theo_with_calibrated_round_conclusion.py`** — replace line 41 with the same two-import pattern as (e).

(g) **`tests/pricing/test_round_types.py:300-302`** — retarget the string-literal regression assertion to track the new import path:

Existing (lines 300-302):
```python
assert "from src.pricing.data import MatchState" in src
...
matchstate_idx = src.find("from src.pricing.data import MatchState")
```

Replace BOTH occurrences with:
```python
assert "from src.state.match_state import MatchState" in src
...
matchstate_idx = src.find("from src.state.match_state import MatchState")
```

The surrounding test (likely something like `test_round_types_imports_matchstate_from_canonical_location` — check the function name and update its docstring if it references the old path) should keep its semantics: the import must exist and must come BEFORE any usage of MatchState in the file. Update the test function's docstring to cite "Phase 3 D-14 atomic move" as the rationale for the new path.

After all 7 file edits: run `mypy --strict src/pricing/ src/state/` (must be clean, NO regressions) and `pytest tests/ -x -k "not benchmark and not e2e"` (must be GREEN — every Phase 1 + 2 test still passes against the relocated MatchState).

If mypy complains about unused imports in `src/pricing/data.py` (e.g., `Optional` no longer needed), drop them. If mypy complains about Optional retention being needed for HalfRates.team_entry on line 167, keep the `from typing import Any, Optional` line as-is.
  </action>
  <verify>
    <automated>mypy --strict src/pricing/ src/state/ &amp;&amp; pytest tests/ -x -k "not benchmark and not e2e" &amp;&amp; python -c "from src.pricing import MatchState as A; from src.state.match_state import MatchState as B; assert A is B; print('re-export id-equal')" &amp;&amp; grep -q "from src.state.match_state import MatchState" tests/pricing/test_round_types.py &amp;&amp; ! grep -RIn "from src.pricing.data import MatchState" src/ tests/</automated>
  </verify>
  <done>All 5 in-repo MatchState imports resolved through src/state/match_state.py; src/pricing/__init__.py re-exports MatchState (id-equal to direct import); src/pricing/data.py contains ONLY HalfRates + TheoOutput; tests/pricing/test_round_types.py:300-302 string-literal regression retargeted; mypy --strict src/pricing/ src/state/ clean; ALL Phase 1 + 2 tests still PASS (regression gate per SPEC acceptance #11).</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| pure-data refactor | Plan only moves and extends a frozen dataclass + rewrites import statements; no I/O, no network, no subprocess. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-03-03-01 | T (Tampering) | `with_update()` mutator | mitigate | The mutator strips caller-provided `seq_id` and `last_updated_ts` (Pattern 1 defensive), preventing any caller from breaking the seq_id monotonic invariant the kill-switch + replay logic depend on. Test 3 + Test 4 in tests/state/test_match_state.py prove this. |
| T-03-03-02 | I (Information disclosure) | MatchState fields | accept | MatchState contains team names, match_ids, and game state — already public per the rib.gg API surface. No PII. |
| T-03-03-03 | D (Denial of service) | per-mutation allocation cost | mitigate | `slots=True` keeps each new MatchState ~200 bytes (D-01 / RESEARCH line 269). At 30k mutations/match that's ~6 MB GC churn — well below concern. The 1000-mutator hypothesis test indirectly proves no allocation pathology (test would time out at the default deadline if mutations ballooned). |
| T-03-03-04 | E (Elevation of privilege) | atomic import rewrite | mitigate | Single-commit atomic move means no test ever observes a half-migrated state where the old `src.pricing.data.MatchState` and the new `src.state.match_state.MatchState` are both importable as different classes. The verify command `python -c "from src.pricing import MatchState as A; from src.state.match_state import MatchState as B; assert A is B"` proves identity equality post-rewrite. |
</threat_model>

<verification>
- `mypy --strict src/pricing/ src/state/` clean.
- `pytest tests/state/test_match_state.py -x` PASSES (8 named test functions; 20k+ hypothesis-generated mutations exercised).
- `pytest tests/ -x -k "not benchmark and not e2e"` GREEN — Phase 1 + Phase 2 regressions all pass.
- `from src.pricing import MatchState` and `from src.state.match_state import MatchState` both resolve to the SAME class object (id-equal).
- `grep -RIn "from src.pricing.data import MatchState" src/ tests/` returns ZERO matches (atomic rewrite complete).
- `grep -q "from src.state.match_state import MatchState" tests/pricing/test_round_types.py` matches (string-literal regression retargeted).
- `ruff check src/state/ src/pricing/data.py src/pricing/__init__.py src/pricing/live_theo.py src/pricing/round_types.py tests/state/ tests/pricing/test_live_theo.py tests/pricing/test_live_theo_with_calibrated_round_conclusion.py tests/pricing/test_round_types.py` clean.
</verification>

<success_criteria>
Wave 1 atomic move + extend is COMPLETE when:

1. `src/state/match_state.py` exists with 25-field MatchState (frozen+slots) + `with_update` mutator that bumps `seq_id` by 1 and refreshes `last_updated_ts` while stripping caller-provided overrides.
2. `src/state/__init__.py` re-exports MatchState.
3. `src/pricing/data.py` no longer contains the MatchState class (it has only `TheoOutput` + `HalfRates`).
4. All 5 in-repo `from src.pricing.data import ... MatchState ...` import sites rewritten to use `src.state.match_state`.
5. The string-literal regression assertion in `tests/pricing/test_round_types.py:300, 302` is retargeted.
6. `src/pricing/__init__.py` still exports `["LiveTheoEngine", "TheoOutput", "MatchState", "HalfRates"]` — MatchState now resolves through re-export.
7. `tests/state/test_match_state.py` has 8 named tests covering schema, defaults, mutator semantics, replace-slots smoke, and 2 property tests (1000-mutator monotonicity, 1000-event JSONL replay round-trip) — ALL PASS.
8. `mypy --strict src/pricing/ src/state/` clean.
9. ALL Phase 1 + 2 tests still GREEN — `pytest tests/ -x -k "not benchmark and not e2e"` regression GATE passes (SPEC acceptance #11).
10. Wave 2 source plans (03-04 scoreboard, 03-05 OCR, 03-06 text-listener) can begin against the new MatchState location and shape.
</success_criteria>

<output>
After completion, create `.planning/phases/03-live-ingestion-layer/03-03-SUMMARY.md` documenting:
- Final field count (25), field list grouped by Phase 1 / Phase 3 origin
- Confirmed 5 import sites + 1 string-literal regression rewritten
- Phase 1 + 2 test count regression result (e.g., "252 tests pass, 0 fail")
- Verified `python -c "from src.pricing import MatchState; print(MatchState.__module__)"` prints `src.state.match_state` (proving re-export works)
- Hypothesis test totals: ~20,000 with_update mutations exercised across 20 examples
</output>
