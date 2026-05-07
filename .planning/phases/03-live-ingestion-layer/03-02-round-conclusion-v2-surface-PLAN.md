---
phase: 03-live-ingestion-layer
plan: "02"
type: execute
wave: 3
depends_on: ["03-01"]
files_modified:
  - src/pricing/round_conclusion.py
  - src/pricing/live_theo.py
  - src/pricing/__init__.py
  - src/pricing/economy.py
  - src/config/constants.py
  - models/round_conclusion.json
  - tests/pricing/test_round_conclusion.py
  - tests/pricing/test_round_conclusion_v2.py
  - tests/pricing/test_live_theo_dispatch.py
  - tests/pricing/test_live_theo.py
  - tests/pricing/test_live_theo_with_calibrated_round_conclusion.py
  - tests/calibration/test_calibrate_round_conclusion.py
  - tests/calibration/conftest.py
autonomous: true
requirements:
  - REQ-round-conclusion-lookup
notes: |
  Wave 3 — round_conclusion v2 surface (D-04) + live_theo bomb_planted dispatch
  (D-05) + atomic-replace models/round_conclusion.json with schema_version=2
  (D-06). Also DELETES src/pricing/economy.credits_to_bucket per CLAUDE.md
  ("economy buckets — DEPRECATED in v2", no callers after rekey).

  Phase 1+2 regression strategy: the v1 lookup signature
  (numerical_diff, bomb_planted, side, econ_bucket, map_name) is DELETED in
  the same commit as the v2 surface lands. Phase 1+2 tests that exercise the
  v1 surface fall into TWO buckets:
  (a) tests asserting v1 lookup math (cells_full hierarchy with numerical_diff
      keys) — REWRITE to assert v2 lookup math (post_plant_p hierarchy with
      (att, def, time_bucket, side, map) keys); the calibrator test
      (tests/calibration/test_calibrate_round_conclusion.py) is xfailed with
      a TODO that 03-07 (the calibrator rewrite) clears.
  (b) tests asserting LiveTheoEngine integration (test_live_theo,
      test_live_theo_with_calibrated_round_conclusion) — patch to use v2
      surface; assert dispatch + post-plant-shifts-theo path.

  Synthetic v2 cells: Task 2 writes a small models/round_conclusion.json with
  schema_version=2 + a HANDFUL of synthetic cells covering the dispatch test
  surface. Real calibration replaces this in 03-07 (Wave 5). The v1 file
  (324 KB, 22/44/524/1886 cells) is git-show'able for forensic recovery.

  v2 constants added: POST_PLANT_TIMER_S=45.0, TIME_BUCKET_WIDTH_S=5.0,
  ROUND_CONCLUSION_JSON_PATH constant for the canonical load path.

must_haves:
  truths:
    - "RoundConclusionLookup.between_round_p(side, map, round_idx) returns side baseline directly (no walk)"
    - "RoundConclusionLookup.post_plant_p(att, def_, time_bucket, side, map) walks cells_full → cells_no_time → cells_no_map → cells_minimal → side_baseline"
    - "RoundConclusionLookup.from_json HARD-FAILS on schema_version != 2 (ValueError)"
    - "v1 lookup() method + v1 RoundConclusionFn Protocol DELETED from src/pricing/round_conclusion.py"
    - "live_theo dispatches: state.bomb_planted=True invokes post_plant_p; otherwise uses between-round (side baseline) path"
    - "models/round_conclusion.json on disk has schema_version=2 + at least one populated cells_full cell that the dispatch test exercises"
    - "src/pricing/economy.py is DELETED (no callers after v2 rekey per CLAUDE.md)"
    - "live_theo call surface engine(state) → TheoOutput preserved (CRule 1 / DEC-010)"
  artifacts:
    - path: "src/pricing/round_conclusion.py"
      provides: "v2 RoundConclusionLookup with between_round_p + post_plant_p + BetweenRoundFn + PostPlantFn Protocols + schema_version=2 JSON I/O"
      contains: "post_plant_p"
      min_lines: 200
    - path: "src/pricing/live_theo.py"
      provides: "_live_theo_impl with state.bomb_planted dispatch per D-05; round_conclusion now REQUIRED (not Optional)"
      contains: "state.bomb_planted"
    - path: "src/config/constants.py"
      provides: "POST_PLANT_TIMER_S=45.0 + TIME_BUCKET_WIDTH_S=5.0 + ROUND_CONCLUSION_JSON_PATH"
      contains: "POST_PLANT_TIMER_S"
    - path: "models/round_conclusion.json"
      provides: "v2 schema_version=2 file with side_baseline + at least one cells_full cell for dispatch test"
      contains: "schema_version"
    - path: "tests/pricing/test_round_conclusion_v2.py"
      provides: "GREEN test_post_plant_p_hierarchy + test_from_json_rejects_v1 + test_between_round_p_returns_side_baseline"
      contains: "test_post_plant_p_hierarchy"
    - path: "tests/pricing/test_live_theo_dispatch.py"
      provides: "GREEN test_dispatch_bomb_planted + test_dispatch_between_round"
      contains: "test_dispatch_bomb_planted"
  key_links:
    - from: "src/pricing/live_theo.py:_live_theo_impl"
      to: "src/pricing/round_conclusion.py:RoundConclusionLookup.post_plant_p"
      via: "if state.bomb_planted: round_conclusion.post_plant_p(...)"
      pattern: "post_plant_p"
    - from: "models/round_conclusion.json"
      to: "RoundConclusionLookup.from_json"
      via: "schema_version=2 hard-fail gate"
      pattern: "schema_version"
    - from: "src/pricing/__init__.py"
      to: "src.pricing.round_conclusion"
      via: "RoundConclusionLookup re-export still works"
      pattern: "RoundConclusionLookup"
---

<objective>
Land the v2 RoundConclusionLookup surface (D-04), the v2 JSON schema_version=2
gate (D-06), the live_theo bomb_planted dispatch (D-05), and the deletion of
src/pricing/economy.py (per CLAUDE.md — no callers after v2 rekey). Atomic-
replace models/round_conclusion.json with a synthetic v2 file scoped to the
dispatch test surface — real calibration is 03-07.

Purpose: REQ-round-conclusion-lookup is the v2 pricing-side rekey. Without
this wave, live_theo cannot dispatch on state.bomb_planted (the key behavioral
unlock for POST_PLANT_QUOTE in Phase 4) and the v1 lookup signature still
points at deleted MatchState fields (numerical_diff, side, econ_bucket).

Output:
- src/pricing/round_conclusion.py rewritten to v2 surface (~250 LOC: dataclass
  + 2 methods + 2 Protocols + from_json/to_json with schema_version=2 gate +
  key (de)serializers).
- src/pricing/live_theo.py:_live_theo_impl modified to dispatch on
  state.bomb_planted (~30 LOC delta — preserves call surface).
- src/pricing/economy.py DELETED + src/pricing/__init__.py cleaned.
- src/config/constants.py adds POST_PLANT_TIMER_S, TIME_BUCKET_WIDTH_S,
  ROUND_CONCLUSION_JSON_PATH (deletes the 4 ECON_BUCKET_*_FLOOR + OCR_FRAMES_PER_SECOND constants).
- models/round_conclusion.json atomic-replaced with v2 synthetic cells.
- tests/pricing/test_round_conclusion_v2.py + test_live_theo_dispatch.py GREEN.
- Phase 1+2 regression suite: tests using LiveTheoEngine patched to v2 surface;
  v1 calibrator test xfailed with TODO pointer to 03-07.
</objective>

<execution_context>
@C:/Users/Joseph Cheng/.claude/get-shit-done/workflows/execute-plan.md
@C:/Users/Joseph Cheng/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/phases/03-live-ingestion-layer/03-SPEC.md
@.planning/phases/03-live-ingestion-layer/03-CONTEXT.md
@.planning/phases/03-live-ingestion-layer/03-RESEARCH.md
@.planning/phases/03-live-ingestion-layer/03-VALIDATION.md
@.planning/phases/03-live-ingestion-layer/03-01-match-state-v2-migration-PLAN.md
@src/pricing/round_conclusion.py
@src/pricing/live_theo.py
@src/pricing/economy.py
@src/config/constants.py

<interfaces>
<!-- v1 surface (CURRENT — to be DELETED in this wave) -->
From src/pricing/round_conclusion.py:
```python
class RoundConclusionFn(Protocol):
    def __call__(self, numerical_diff: int, bomb_planted: bool, side: str,
                 econ_bucket: str, map_name: str) -> float: ...

@dataclass(frozen=True, slots=True)
class RoundConclusionLookup:
    cells_full: dict[tuple[int, bool, str, str, str], _Cell]   # numerical_diff|bomb|side|econ|map
    cells_no_econ: dict[tuple[int, bool, str, str], _Cell]
    cells_no_map: dict[tuple[int, bool, str], _Cell]
    cells_minimal: dict[tuple[int, bool], _Cell]
    side_baseline: dict[str, float]

    def lookup(self, numerical_diff: int, bomb_planted: bool, side: str,
               econ_bucket: str, map_name: str) -> float: ...
    @classmethod
    def from_json(cls, path) -> "RoundConclusionLookup": ...
    def to_json(self, path) -> None: ...
```

<!-- v2 target surface (D-04 / D-06 / RESEARCH §"round_conclusion v2 surface") -->
Target src/pricing/round_conclusion.py:
```python
_SCHEMA_VERSION_V2: Final[int] = 2

class BetweenRoundFn(Protocol):
    def __call__(self, side: str, map_name: str, round_idx: int) -> float: ...

class PostPlantFn(Protocol):
    def __call__(self, att: int, def_: int, time_bucket: int, side: str, map_name: str) -> float: ...

@dataclass(frozen=True, slots=True)
class RoundConclusionLookup:
    side_baseline: dict[str, float] = field(default_factory=lambda: {"atk": 0.5, "def": 0.5})
    cells_minimal: dict[tuple[int, int], _Cell] = field(default_factory=dict)              # (att, def_)
    cells_no_map:  dict[tuple[int, int, str], _Cell] = field(default_factory=dict)         # (att, def_, side)
    cells_no_time: dict[tuple[int, int, str, str], _Cell] = field(default_factory=dict)    # (att, def_, side, map)
    cells_full:    dict[tuple[int, int, int, str, str], _Cell] = field(default_factory=dict)  # (att, def_, time_bucket, side, map)

    def between_round_p(self, side: str, map_name: str, round_idx: int) -> float:
        del map_name, round_idx  # reserved for future per-map per-round-idx baseline
        return self.side_baseline.get(side, 0.5)

    def post_plant_p(self, att: int, def_: int, time_bucket: int, side: str, map_name: str) -> float:
        if (cell := self.cells_full.get((att, def_, time_bucket, side, map_name))) is not None:
            return cell.shrunk()
        if (cell := self.cells_no_time.get((att, def_, side, map_name))) is not None:
            return cell.shrunk()
        if (cell := self.cells_no_map.get((att, def_, side))) is not None:
            return cell.shrunk()
        if (cell := self.cells_minimal.get((att, def_))) is not None:
            return cell.shrunk()
        return self.side_baseline.get(side, 0.5)

    @classmethod
    def from_json(cls, path) -> "RoundConclusionLookup":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if data.get("schema_version") != _SCHEMA_VERSION_V2:
            raise ValueError(f"Expected schema_version={_SCHEMA_VERSION_V2}, got {data.get('schema_version')!r}")
        # parse cells per new keying...
        return obj
```

<!-- v2 live_theo dispatch (D-05) -->
From src/pricing/live_theo.py — current _live_theo_impl signature:
```python
def _live_theo_impl(
    state: MatchState,
    half_rates: HalfRates,
    round_conclusion: Optional[RoundConclusionFn] = None,  # v1 — must change to Required v2 type
) -> TheoOutput: ...
```

Target dispatch logic:
```python
def _live_theo_impl(
    state: MatchState, half_rates: HalfRates, round_conclusion: RoundConclusionLookup,
) -> TheoOutput:
    bo3 = _bo3_state_from_match_state(state)
    fn_between = _RoundPFnImpl(match_state=state, half_rates=half_rates)
    if state.bomb_planted:
        # D-05 dispatch — single current-round override
        time_bucket_idx = int(min(state.time_left_s, POST_PLANT_TIMER_S) / TIME_BUCKET_WIDTH_S)
        p_round = round_conclusion.post_plant_p(
            att=state.attackers_alive, def_=state.defenders_alive,
            time_bucket=time_bucket_idx,
            side=state.side_orient,
            map_name=state.map_pool[state.map_idx],
        )
        state_after_a = _advance_round(bo3, a_wins=True)
        state_after_b = _advance_round(bo3, a_wins=False)
        theo_series = (
            p_round * series_value(state_after_a, fn_between)
            + (1 - p_round) * series_value(state_after_b, fn_between)
        )
    else:
        theo_series = series_value(bo3, fn_between)
    theo_series = _clip_conviction(theo_series)
    # ... rest of vega/confidence/theo_map unchanged
```

<!-- v2 JSON shape (D-06) -->
```json
{
  "schema_version": 2,
  "side_baseline": {"atk": 0.5256, "def": 0.4751},
  "cells_minimal":  {"<att>|<def>": {"n": 100, "p_hat": 0.6, "parent_p": 0.5}, ...},
  "cells_no_map":   {"<att>|<def>|<side>": {...}, ...},
  "cells_no_time":  {"<att>|<def>|<side>|<map>": {...}, ...},
  "cells_full":     {"<att>|<def>|<time_bucket>|<side>|<map>": {...}, ...}
}
```

<!-- _Cell shape (UNCHANGED from v1) -->
```python
@dataclass(frozen=True, slots=True)
class _Cell:
    n: int
    p_hat: float
    parent_p: float
    def shrunk(self) -> float:
        return (self.n * self.p_hat + SHRINK_PRIOR * self.parent_p) / (self.n + SHRINK_PRIOR)
```

<!-- src/pricing/__init__.py current re-export -->
```python
from src.pricing.data import HalfRates, TheoOutput   # MatchState moved to src.state in 03-01
from src.state.match_state import MatchState
from src.pricing.live_theo import LiveTheoEngine
__all__ = ["LiveTheoEngine", "TheoOutput", "MatchState", "HalfRates"]
```

<!-- LiveTheoEngine bundle (CRule 1 — call surface PRESERVED) -->
From src/pricing/live_theo.py (lower in file):
```python
@dataclass(frozen=True)
class LiveTheoEngine:
    half_rates: HalfRates
    round_conclusion: RoundConclusionLookup  # WAS Optional in Phase 1; now REQUIRED
    def __call__(self, state: MatchState) -> TheoOutput:
        return _live_theo_impl(state, self.half_rates, self.round_conclusion)
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add v2 constants + delete src/pricing/economy.py + clean __init__.py</name>
  <files>
    src/config/constants.py
    src/pricing/economy.py
    src/pricing/__init__.py
    tests/calibration/conftest.py
  </files>
  <behavior>
    - src/config/constants.py declares: `POST_PLANT_TIMER_S: Final[float] = 45.0`, `TIME_BUCKET_WIDTH_S: Final[float] = 5.0`, `ROUND_CONCLUSION_JSON_PATH: Final[str] = "models/round_conclusion.json"`.
    - The 4 v1 ECON_BUCKET_*_FLOOR constants are DELETED (no callers after credits_to_bucket deletion).
    - The Phase 2 OCR_FRAMES_PER_SECOND constant is DELETED (Path-B contingency, never used at runtime; v2 OCR cadences live in 03-05).
    - src/pricing/economy.py is DELETED (per CLAUDE.md "Economy buckets — DEPRECATED in v2": "Phase 3 deletes it").
    - src/pricing/__init__.py is unchanged (it doesn't re-export economy).
    - Any tests/calibration imports of `credits_to_bucket` or `ECON_BUCKET_*` are pruned: tests/calibration/conftest.py and tests/calibration/test_*.py — find via grep, neutralize via xfail with TODO comment pointing at 03-07.
    - `mypy --strict src/pricing/` clean (economy.py is gone; no orphan import resolves to a dead module).
    - `ruff check src/ tests/` clean (no unused imports).
    - Phase 1+2 regression suite STILL GREEN modulo the calibrator test, which is xfailed with TODO("03-07 — recalibrator rewrite").
  </behavior>
  <action>
1) **Edit `src/config/constants.py`** — append a new "Phase 3 — round-conclusion v2" section AFTER the Phase 2 section (current EOF):

```python
# --------------------------------------------------------------------------- #
# Phase 3 — round-conclusion v2 (D-04 / D-06 / D-10)                          #
# --------------------------------------------------------------------------- #

POST_PLANT_TIMER_S: Final[float] = 45.0
"""Valorant post-plant bomb timer (seconds).

Source: 03-CONTEXT.md D-14 / Riot rules. Drives `time_remaining_bucket`
computation in live_theo's post-plant dispatch path. Bombs that exceed this
timer auto-detonate; live_theo clips `state.time_left_s` to this max.
"""

TIME_BUCKET_WIDTH_S: Final[float] = 5.0
"""Width of each post-plant time bucket (seconds); 9 buckets across 0-45s.

Source: 03-CONTEXT.md D-10. Buckets: [0-5, 5-10, ..., 40-45]. Cell estimate
~3150 cells_full slots × ~25k post-plant samples → ~8 samples/cell average,
shrunk to parent (cells_no_time) per Bayesian SHRINK_PRIOR=15.
"""

ROUND_CONCLUSION_JSON_PATH: Final[str] = "models/round_conclusion.json"
"""Canonical disk path for the v2 calibrated lookup (D-06).

Atomic-replace target. `RoundConclusionLookup.from_json(path)` HARD-FAILS on
schema_version != 2; v1 file recoverable via git history.
"""
```

2) **Delete the 4 v1 ECON_BUCKET_*_FLOOR constants** from `src/config/constants.py` (lines ~244-263 — the section "Phase 2 — economy buckets"). Replace the whole `--- Phase 2 — economy buckets ---` block with a single comment:

```python
# --------------------------------------------------------------------------- #
# Phase 2 — economy buckets (DELETED in Phase 3 v2; see CLAUDE.md "Economy    #
# buckets — DEPRECATED in v2"). Bucket constants removed because their sole   #
# caller (src/pricing/economy.credits_to_bucket) has no callers after the v2  #
# rekey of round_conclusion.json. Forensic recovery via git show HEAD~N.     #
# --------------------------------------------------------------------------- #
```

3) **Delete the OCR_FRAMES_PER_SECOND constant** (Phase 2 Path-B contingency, never instantiated at runtime; v2 OCR cadences are owned by 03-05). Replace with a 1-line comment pointing at the new constants:

```python
# OCR cadences moved to "Phase 3 — OCR pipeline" section (03-05 PLAN owns).
```

4) **Delete `src/pricing/economy.py`** entirely (`rm src/pricing/economy.py` via Bash).

5) **Verify `src/pricing/__init__.py`** still resolves cleanly (it never imported economy.py — economy is consumed only by `scripts/probe_round_events.py:277` which is a Phase 2 ETL script that 03-07 rewrites). DO NOT touch __init__.py if it doesn't import economy.

6) **Patch `scripts/probe_round_events.py`** — add a TEMPORARY shim at the top that re-implements `credits_to_bucket` inline so the file still parses (03-07 rewrites this entire file; this shim only buys regression-suite uptime for waves 4-6 in parallel):
```python
# TODO(03-07): the v2 ETL re-run rewrite removes credits_to_bucket entirely.
# Phase 2's econ_bucket key is dropped from the v2 mid_round_states[] schema.
# Inline shim retained ONLY so the v1 ETL script remains importable until
# 03-07 swaps it out — DO NOT call this from new code.
def credits_to_bucket(credits: int) -> str:
    if credits >= 20_000: return "full"
    if credits >= 10_000: return "semi-buy"
    if credits >= 5_000: return "semi-eco"
    return "eco"
```
Replace the `from src.pricing.economy import credits_to_bucket` line with this inline shim. Verify with grep that no other src/ file imports economy.

7) **Patch `tests/calibration/conftest.py` and `tests/calibration/test_*.py`** — for any `from src.pricing.economy import credits_to_bucket` lines, swap to:
```python
def credits_to_bucket(credits: int) -> str:
    # 03-02: src.pricing.economy DELETED per CLAUDE.md "Economy buckets — DEPRECATED in v2".
    # Local stub so this v1 calibrator test still parses; 03-07 rewrites the calibrator.
    if credits >= 20_000: return "full"
    if credits >= 10_000: return "semi-buy"
    if credits >= 5_000: return "semi-eco"
    return "eco"
```
ALSO add `pytest.xfail("03-07 — Phase 2 v1 calibrator dataset will be replaced by v2 ETL re-run")` to the body of the `test_calibrate_round_conclusion.py::test_*` functions that exercise the calibrator end-to-end. Tests that ONLY exercise `credits_to_bucket` directly (if any) can stay GREEN against the local stub.

Atomic commit message: `feat(03-02): add v2 round-conclusion constants + delete economy.py per CLAUDE.md`
  </action>
  <verify>
    <automated>uv run pytest tests/ -x --no-cov -k "not test_calibrate_round_conclusion" && uv run mypy --strict src/pricing src/state && uv run ruff check src tests scripts && uv run python -c "from src.config.constants import POST_PLANT_TIMER_S, TIME_BUCKET_WIDTH_S, ROUND_CONCLUSION_JSON_PATH; assert POST_PLANT_TIMER_S == 45.0; assert TIME_BUCKET_WIDTH_S == 5.0"</automated>
  </verify>
  <done>
- POST_PLANT_TIMER_S, TIME_BUCKET_WIDTH_S, ROUND_CONCLUSION_JSON_PATH appear in src/config/constants.py with `Final[...]` annotations.
- ECON_BUCKET_*_FLOOR (4 constants) and OCR_FRAMES_PER_SECOND removed.
- src/pricing/economy.py no longer exists on disk.
- scripts/probe_round_events.py has the inline credits_to_bucket shim with the TODO marker.
- tests/calibration/* compiles and runs (calibrator end-to-end test xfailed pointing at 03-07).
- mypy --strict src/pricing src/state — 0 errors.
- ruff check src tests scripts — 0 errors.
- All tests pass (modulo the xfailed calibrator test).
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Rewrite RoundConclusionLookup to v2 surface + atomic-replace round_conclusion.json with schema_version=2 + GREEN test_round_conclusion_v2</name>
  <files>
    src/pricing/round_conclusion.py
    models/round_conclusion.json
    tests/pricing/test_round_conclusion.py
    tests/pricing/test_round_conclusion_v2.py
  </files>
  <behavior>
    - `src/pricing/round_conclusion.py` rewritten to v2 surface per <interfaces> (the entire file changes; this is a wholesale rewrite, not a patch).
    - v1 `lookup()` method DELETED. v1 `RoundConclusionFn` Protocol DELETED. v1 cells_full/cells_no_econ shape DELETED.
    - `between_round_p(side, map_name, round_idx) -> float` returns `self.side_baseline.get(side, 0.5)` (no walk).
    - `post_plant_p(att, def_, time_bucket, side, map_name) -> float` walks 5-tier hierarchy: `cells_full → cells_no_time → cells_no_map → cells_minimal → side_baseline`.
    - 4 new key (de)serializers: `_format_key_2((att, def_))`, `_format_key_3((att, def_, side))`, `_format_key_4((att, def_, side, map))`, `_format_key_5((att, def_, time_bucket, side, map))` (and inverse `_parse_key_*`). Use `|` separator like v1.
    - `_SCHEMA_VERSION_V2: Final[int] = 2` module constant.
    - `from_json(path)` reads JSON, asserts `data["schema_version"] == 2`, raises `ValueError(f"Expected schema_version=2, got {sv!r}")` otherwise. Parses each cells_* dict via the new key parsers. Side baseline reads as before.
    - `to_json(path)` writes top-level `"schema_version": 2` + the 4 cells_* dicts + side_baseline; uses the new key formatters.
    - 2 new Protocols `BetweenRoundFn`, `PostPlantFn` per D-04.
    - `_Cell` (n, p_hat, parent_p) UNCHANGED — same shrunk() formula.
    - `models/round_conclusion.json` REPLACED with a synthetic v2 file containing:
        - `"schema_version": 2`
        - `"side_baseline": {"atk": 0.5256, "def": 0.4751}` (carry the empirical values from Phase 2 v1)
        - `"cells_minimal": {}` (empty for now — 03-07 fills)
        - `"cells_no_map": {}`
        - `"cells_no_time": {}`
        - `"cells_full": {"3|2|0|atk|Lotus": {"n": 100, "p_hat": 0.7, "parent_p": 0.5}}` (one cell so the dispatch test in Task 3 has a populated key to lookup; documents the test contract)
    - `tests/pricing/test_round_conclusion.py` (Phase 2 GREEN tests) is rewritten in-place — every test that referenced the v1 surface is converted to assert v2 behavior. Tests that exercised v1 cells_full hierarchy walks become tests on v2 cells_full hierarchy walks (key shape changes, hierarchy semantics preserved). The `test_lookup_*` family becomes `test_post_plant_p_*`. Tests asserting from_json/to_json round-trip preserve the round-trip invariant under v2 schema.
    - `tests/pricing/test_round_conclusion_v2.py` (RED stubs from 03-00) all GREEN:
        - `test_post_plant_p_hierarchy`: build a lookup with one cell at each tier; call post_plant_p with key matching cells_full (assert n*p_hat formula); call with key matching cells_no_time only (assert fall-through); etc. through side_baseline.
        - `test_from_json_rejects_v1`: write a JSON file with `schema_version: 1` (or no field), call from_json, assert ValueError.
        - `test_between_round_p_returns_side_baseline`: build lookup with side_baseline={"atk": 0.6, "def": 0.4}; call between_round_p("atk", "Lotus", 5) — assert 0.6.
    - `mypy --strict src/pricing/` clean.
  </behavior>
  <action>
1) **Wholesale rewrite `src/pricing/round_conclusion.py`** to the v2 surface. Skeleton outline (use the <interfaces> section verbatim as the implementation source):
   - Module docstring rewrite citing D-04 / D-06 / 03-CONTEXT.md "round_conclusion v2 surface".
   - Imports: `from __future__ import annotations`, `import json`, `dataclass, field, `, `Path`, `Final, Protocol, TypedDict`. SHRINK_PRIOR from src.config.constants.
   - `_SCHEMA_VERSION_V2: Final[int] = 2`.
   - `_Cell` dataclass — UNCHANGED (n, p_hat, parent_p, shrunk()).
   - `_CellJson` TypedDict — UNCHANGED.
   - `_RoundConclusionJsonV2` TypedDict — has `schema_version: int`, `side_baseline: dict[str, float]`, `cells_minimal: dict[str, _CellJson]`, `cells_no_map: dict[str, _CellJson]`, `cells_no_time: dict[str, _CellJson]`, `cells_full: dict[str, _CellJson]`.
   - 8 key (de)serializers — `_format_key_2((att, def_))`, `_format_key_3((att, def_, side))`, `_format_key_4((att, def_, side, map_name))`, `_format_key_5((att, def_, time_bucket, side, map_name))`, plus 4 inverse `_parse_key_N`. Use `|` separator. Example: `f"{att}|{def_}"`.
   - 2 Protocols: `BetweenRoundFn` (call: side, map_name, round_idx → float), `PostPlantFn` (call: att, def_, time_bucket, side, map_name → float).
   - `RoundConclusionLookup` dataclass per <interfaces>: 4 cells_* dicts (default_factory=dict) + side_baseline (default_factory=lambda: {"atk": 0.5, "def": 0.5}). Note the field order: side_baseline FIRST so callers can construct `RoundConclusionLookup({"atk": 0.6, "def": 0.4})` positionally.
   - `between_round_p(self, side: str, map_name: str, round_idx: int) -> float` — body: `del map_name, round_idx; return self.side_baseline.get(side, 0.5)`.
   - `post_plant_p(self, att: int, def_: int, time_bucket: int, side: str, map_name: str) -> float` — walks the 5-tier hierarchy with walrus operator per <interfaces>.
   - `from_json(cls, path)` — reads JSON; checks `data.get("schema_version") == _SCHEMA_VERSION_V2`; raises ValueError otherwise; parses each cells_* dict.
   - `to_json(self, path)` — writes JSON with `"schema_version": _SCHEMA_VERSION_V2` + the 4 cells_* dicts + side_baseline.

2) **Atomic-replace `models/round_conclusion.json`** with the v2 synthetic file:
```json
{
  "schema_version": 2,
  "side_baseline": {"atk": 0.5256, "def": 0.4751},
  "cells_minimal": {},
  "cells_no_map": {},
  "cells_no_time": {},
  "cells_full": {
    "3|2|0|atk|Lotus": {"n": 100, "p_hat": 0.7, "parent_p": 0.5256}
  }
}
```
The single populated cell at `(att=3, def=2, time_bucket=0, side="atk", map="Lotus")` exists ONLY so the live_theo dispatch test in Task 3 has a known cell to hit. shrunk = (100*0.7 + 15*0.5256)/(100+15) = 0.6816 (vs side_baseline atk=0.5256 — clearly off baseline by ~0.16, satisfies E2E acceptance >=1¢ shift). 03-07 replaces this with the real ~25k-sample calibrated file.

3) **Rewrite `tests/pricing/test_round_conclusion.py`** in-place — every reference to v1 surface (`numerical_diff`, `econ_bucket`, `cells_no_econ`, `lookup(...)` with 5-arg signature, `RoundConclusionFn`) becomes its v2 equivalent (`att`, `def_`, `time_bucket`, `cells_no_time`, `post_plant_p(...)`, `PostPlantFn`). Test naming: rename `test_lookup_*` → `test_post_plant_p_*`. Hierarchy tests: same structure (build cell at level N, call lookup with key at level N, assert shrunk value), just with new key shapes.

4) **Wire `tests/pricing/test_round_conclusion_v2.py`** (RED stubs from 03-00) to GREEN:

```python
"""REQ-round-conclusion-lookup — v2 surface tests (03-02 / D-04 / D-06)."""
from pathlib import Path
import json
import pytest
from src.pricing.round_conclusion import RoundConclusionLookup, _Cell, _SCHEMA_VERSION_V2
from src.config.constants import SHRINK_PRIOR

def test_post_plant_p_hierarchy(tmp_path):
    """Hierarchy walk: cells_full → cells_no_time → cells_no_map → cells_minimal → side_baseline."""
    lookup = RoundConclusionLookup()
    # Tier 1: cells_full
    lookup.cells_full[(3, 2, 0, "atk", "Lotus")] = _Cell(n=100, p_hat=0.7, parent_p=0.5)
    expected_full = (100 * 0.7 + SHRINK_PRIOR * 0.5) / (100 + SHRINK_PRIOR)
    assert lookup.post_plant_p(3, 2, 0, "atk", "Lotus") == pytest.approx(expected_full)
    # Tier 2: fall-through to cells_no_time
    lookup.cells_no_time[(2, 1, "atk", "Lotus")] = _Cell(n=50, p_hat=0.6, parent_p=0.5)
    expected_no_time = (50 * 0.6 + SHRINK_PRIOR * 0.5) / (50 + SHRINK_PRIOR)
    assert lookup.post_plant_p(2, 1, 5, "atk", "Lotus") == pytest.approx(expected_no_time)  # time_bucket=5 not in cells_full
    # Tier 3: fall-through to cells_no_map
    lookup.cells_no_map[(1, 1, "def")] = _Cell(n=30, p_hat=0.4, parent_p=0.5)
    expected_no_map = (30 * 0.4 + SHRINK_PRIOR * 0.5) / (30 + SHRINK_PRIOR)
    assert lookup.post_plant_p(1, 1, 0, "def", "Bind") == pytest.approx(expected_no_map)
    # Tier 4: fall-through to cells_minimal
    lookup.cells_minimal[(0, 1)] = _Cell(n=10, p_hat=0.3, parent_p=0.5)
    expected_minimal = (10 * 0.3 + SHRINK_PRIOR * 0.5) / (10 + SHRINK_PRIOR)
    assert lookup.post_plant_p(0, 1, 0, "atk", "Bind") == pytest.approx(expected_minimal)
    # Tier 5: fall-through to side_baseline
    lookup.side_baseline["atk"] = 0.5256
    assert lookup.post_plant_p(5, 5, 0, "atk", "Bind") == pytest.approx(0.5256)

def test_from_json_rejects_v1(tmp_path):
    p = tmp_path / "v1.json"
    p.write_text(json.dumps({"side_baseline": {"atk": 0.5, "def": 0.5}, "cells_full": {}}))  # no schema_version
    with pytest.raises(ValueError, match="schema_version"):
        RoundConclusionLookup.from_json(p)

def test_between_round_p_returns_side_baseline():
    lookup = RoundConclusionLookup(side_baseline={"atk": 0.6, "def": 0.4})
    assert lookup.between_round_p("atk", "Lotus", 5) == 0.6
    assert lookup.between_round_p("def", "Bind", 12) == 0.4
    assert lookup.between_round_p("unknown_side", "Haven", 0) == 0.5  # default
```

Replace the xfail stubs in tests/pricing/test_round_conclusion_v2.py with these implementations.

5) Run the regression suite to confirm nothing else broke.

Atomic commit message: `feat(03-02): rewrite RoundConclusionLookup to v2 surface + atomic-replace round_conclusion.json (D-04/D-06)`
  </action>
  <verify>
    <automated>uv run pytest tests/pricing/test_round_conclusion_v2.py tests/pricing/test_round_conclusion.py -v -x --no-cov && uv run mypy --strict src/pricing/ && uv run python -c "from src.pricing.round_conclusion import RoundConclusionLookup; rc = RoundConclusionLookup.from_json('models/round_conclusion.json'); print('schema OK; baseline=', rc.side_baseline)"</automated>
  </verify>
  <done>
- src/pricing/round_conclusion.py wholly rewritten to v2 surface; no v1 lookup() / RoundConclusionFn references remain (grep verifies).
- models/round_conclusion.json has schema_version=2 + the synthetic Lotus cell.
- tests/pricing/test_round_conclusion_v2.py — 3 tests GREEN.
- tests/pricing/test_round_conclusion.py rewritten — all v1-surface tests converted to v2 surface and GREEN.
- mypy --strict src/pricing/ clean.
- `from src.pricing.round_conclusion import RoundConclusionLookup; RoundConclusionLookup.from_json('models/round_conclusion.json')` runs cleanly and returns a lookup with schema_version=2.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Wire live_theo bomb_planted dispatch (D-05) + GREEN test_live_theo_dispatch + Phase 1+2 regression</name>
  <files>
    src/pricing/live_theo.py
    tests/pricing/test_live_theo_dispatch.py
    tests/pricing/test_live_theo.py
    tests/pricing/test_live_theo_with_calibrated_round_conclusion.py
  </files>
  <behavior>
    - `_live_theo_impl(state, half_rates, round_conclusion: RoundConclusionLookup)` (round_conclusion now REQUIRED, type changed from `Optional[RoundConclusionFn]` to `RoundConclusionLookup`).
    - When `state.bomb_planted is True`, the function computes `time_bucket_idx = int(min(state.time_left_s, POST_PLANT_TIMER_S) / TIME_BUCKET_WIDTH_S)`, then `p_round = round_conclusion.post_plant_p(att=state.attackers_alive, def_=state.defenders_alive, time_bucket=time_bucket_idx, side=state.side_orient, map_name=state.map_pool[state.map_idx])`, then `theo_series = p_round * series_value(state_after_a, fn_between) + (1 - p_round) * series_value(state_after_b, fn_between)`. The future-round transitions ALWAYS use between-round semantics (no nested post-plant lookups in the recursion — D-05).
    - When `state.bomb_planted is False`, behavior is IDENTICAL to current Phase 1+2 (call `series_value(bo3, fn_between)` directly).
    - `LiveTheoEngine.round_conclusion: RoundConclusionLookup` — type changed from `Optional[RoundConclusionLookup]` (or whatever Phase 1+2 had) to required `RoundConclusionLookup`.
    - vega + confidence + theo_map computation paths UNCHANGED (vega still uses `_compute_vega(bo3, fn_between)`; confidence still uses `_compute_confidence(state, half_rates)`).
    - `tests/pricing/test_live_theo_dispatch.py` (RED stubs from 03-00) GREEN:
        - `test_dispatch_bomb_planted`: build state with bomb_planted=True, attackers_alive=3, defenders_alive=2, time_left_s=43.0, side_orient="atk", map_pool=("Lotus", ...), map_idx=0; build lookup with cells_full[(3,2,0,"atk","Lotus")] = _Cell(n=100, p_hat=0.7, parent_p=0.5); call live_theo; assert that theo_series differs from the bomb_planted=False version (proves the dispatch is exercised).
        - `test_dispatch_between_round`: build state with bomb_planted=False; call live_theo; assert theo_series uses fn_between (compare to a hand-computed series_value with side baseline).
    - All Phase 1+2 tests STILL GREEN. test_live_theo.py and test_live_theo_with_calibrated_round_conclusion.py: each test that constructs a `LiveTheoEngine(half_rates, round_conclusion=None)` pattern is patched to construct `LiveTheoEngine(half_rates, round_conclusion=RoundConclusionLookup())` (default-constructed empty lookup gives side_baseline=0.5/0.5 — bit-identical to Phase 1 stub). Tests that construct `LiveTheoEngine(half_rates, round_conclusion=RoundConclusionLookup.from_json("models/round_conclusion.json"))` continue to work (file is now v2).
    - Tests that previously asserted on lookup-keyed cells (Phase 2 calibrated lookup test) need their cell-keying patched: any `lookup_obj.cells_full[(numerical_diff, ...)] = _Cell(...)` becomes `lookup_obj.cells_full[(att, def_, time_bucket, side, map)] = _Cell(...)`.
    - `mypy --strict src/pricing/` clean.
  </behavior>
  <action>
1) **Edit `src/pricing/live_theo.py`** at imports (top of file):
   - Add `from src.config.constants import POST_PLANT_TIMER_S, TIME_BUCKET_WIDTH_S` to the existing constants import block.
   - Change `from src.pricing.round_conclusion import RoundConclusionFn` → `from src.pricing.round_conclusion import RoundConclusionLookup`.
   - Add `from src.pricing.dp import _advance_round` if not already imported (it's the same module).

2) **Edit `_live_theo_impl` signature**:
   - Change `round_conclusion: Optional[RoundConclusionFn] = None` → `round_conclusion: RoundConclusionLookup` (REQUIRED, no default).
   - Drop the `_ = round_conclusion  # silence unused-argument lint` line.

3) **Insert the dispatch logic** in `_live_theo_impl` body, replacing the current `theo_series_raw = series_value(bo3, fn)` line with:

```python
if state.bomb_planted:
    # D-05: post-plant dispatch — single current-round override.
    # state.time_left_s, attackers_alive, defenders_alive are guaranteed
    # non-None by the arbiter when bomb_planted=True; defensive None checks
    # below keep mypy --strict clean and protect against malformed callers.
    if state.time_left_s is None or state.attackers_alive is None or state.defenders_alive is None:
        # Defensive: bomb_planted=True with missing post-plant fields → fall back
        # to between-round path with degraded confidence (per D-05 contract).
        theo_series_raw = series_value(bo3, fn)
    else:
        time_bucket_idx = int(min(state.time_left_s, POST_PLANT_TIMER_S) / TIME_BUCKET_WIDTH_S)
        p_round = round_conclusion.post_plant_p(
            att=state.attackers_alive,
            def_=state.defenders_alive,
            time_bucket=time_bucket_idx,
            side=state.side_orient,
            map_name=state.map_pool[state.map_idx],
        )
        # Future-round transitions ALWAYS use between-round semantics (D-05 —
        # no nested post-plant lookups in the recursion).
        state_after_a = _advance_round(bo3, a_wins=True)
        state_after_b = _advance_round(bo3, a_wins=False)
        theo_series_raw = (
            p_round * series_value(state_after_a, fn)
            + (1.0 - p_round) * series_value(state_after_b, fn)
        )
else:
    theo_series_raw = series_value(bo3, fn)
```

(`fn` is the local `_RoundPFnImpl` instance already constructed above this block. RENAME to `fn_between` if cleaner — but `fn` is fine; D-05 says "future-round transitions ALWAYS use between-round semantics" and `fn` IS the between-round closure.)

Keep `theo_series = _clip_conviction(theo_series_raw)` as-is.

4) **Edit `LiveTheoEngine` dataclass** further down in `live_theo.py` — the `round_conclusion` field type changes from whatever Phase 1 had to `RoundConclusionLookup` (REQUIRED). If Phase 1 had it Optional with a default of None, drop the default — callers must pass a lookup.

5) **Wire `tests/pricing/test_live_theo_dispatch.py`** (RED stubs from 03-00) to GREEN:

```python
"""REQ-round-conclusion-lookup — D-05 dispatch test (03-02)."""
from src.state.match_state import MatchState
from src.pricing.live_theo import LiveTheoEngine
from src.pricing.data import HalfRates
from src.pricing.round_conclusion import RoundConclusionLookup, _Cell

def _make_half_rates() -> HalfRates:
    """Symmetric HalfRates so theo_series isolation tracks the round_conclusion shift."""
    return HalfRates(team_rates={}, league_rates={}, overall_avg=0.5)

def _make_state(*, bomb_planted, attackers_alive=None, defenders_alive=None, time_left_s=None) -> MatchState:
    return MatchState(
        match_id="dispatch-001",
        team_a="A", team_b="B",
        map_pool=("Lotus", "Bind", "Haven"),
        map_side_orients=("a_atk", "a_def", "a_atk"),
        map_winners=(None, None, None),
        pistol_winner_a={0: None, 1: None, 2: None},
        map_idx=0,
        a_map_score=0, b_map_score=0,
        a_round=10, b_round=8,  # mid-game state
        side_orient="atk",
        bomb_planted=bomb_planted,
        attackers_alive=attackers_alive,
        defenders_alive=defenders_alive,
        time_left_s=time_left_s,
        seq_id=0,
        last_updated_ts=0.0,
    )

def test_dispatch_bomb_planted():
    """When bomb_planted=True, live_theo invokes post_plant_p (verified by populated-cell shift)."""
    lookup = RoundConclusionLookup()
    # Populate a cells_full hit for (att=3, def_=2, time_bucket=0, side="atk", map="Lotus")
    # shrunk = (100*0.7 + 15*0.5) / 115 = 0.6739 — clearly off side_baseline (0.5)
    lookup.cells_full[(3, 2, 0, "atk", "Lotus")] = _Cell(n=100, p_hat=0.7, parent_p=0.5)
    engine = LiveTheoEngine(half_rates=_make_half_rates(), round_conclusion=lookup)

    bp_state = _make_state(bomb_planted=True, attackers_alive=3, defenders_alive=2, time_left_s=43.0)
    bp_out = engine(bp_state)

    # Compare to bomb_planted=False with the SAME lookup — the difference proves dispatch.
    br_state = _make_state(bomb_planted=False)
    br_out = engine(br_state)

    assert bp_out.theo_series != br_out.theo_series  # dispatch exercised
    # Sanity: bomb_planted theo should be shifted up because att(3)>def(2) and our cell says p=0.7
    # (precise value depends on DP; assert direction only).
    assert bp_out.theo_series > br_out.theo_series

def test_dispatch_between_round():
    """When bomb_planted=False, live_theo uses between_round_p (= side baseline directly)."""
    lookup = RoundConclusionLookup()  # empty cells; default side_baseline = {atk: 0.5, def: 0.5}
    engine = LiveTheoEngine(half_rates=_make_half_rates(), round_conclusion=lookup)

    state = _make_state(bomb_planted=False)
    out = engine(state)

    # With symmetric HalfRates + between-round-only path + side_baseline=0.5,
    # theo_series should be the canonical 50-50 DP value (close to 0.5 at mid-game).
    assert 0.0 < out.theo_series < 1.0  # well-defined output
    assert abs(out.theo_series - 0.5) < 0.2  # broad sanity band — DP is symmetric
```

Replace the xfail stubs with these implementations.

6) **Patch `tests/pricing/test_live_theo.py`** — every `LiveTheoEngine(half_rates=..., round_conclusion=None)` becomes `LiveTheoEngine(half_rates=..., round_conclusion=RoundConclusionLookup())`. Every `LiveTheoEngine(half_rates=...)` (relying on default) becomes `LiveTheoEngine(half_rates=..., round_conclusion=RoundConclusionLookup())`.

7) **Patch `tests/pricing/test_live_theo_with_calibrated_round_conclusion.py`** — Phase 2 calibrated-lookup integration tests:
   - The `RoundConclusionLookup.from_json("models/round_conclusion.json")` calls now load the v2 file; assertions on cells_full keys (if any) need rekeying to v2 shape.
   - If a test asserts on a SPECIFIC numerical_diff cell value, replace with an assertion on a SPECIFIC (att, def_, time_bucket, side, map) cell value — pick the populated `(3, 2, 0, "atk", "Lotus")` cell from the synthetic v2 JSON (Task 2).
   - If a test broadly asserts "calibrated lookup produces non-degenerate theo", that test PRESERVES its semantics under v2 — no change needed beyond the LiveTheoEngine constructor signature.
   - If asserting on Phase 2 cell counts (22/44/524/1886), DELETE those assertions with comment `# 03-02: v1 cell counts replaced by v2 schema; 03-07 will add real v2 calibration`. Test still runs but doesn't assert specific counts.

Atomic commit message: `feat(03-02): live_theo bomb_planted dispatch (D-05) + Phase 1+2 regression patch`
  </action>
  <verify>
    <automated>uv run pytest tests/pricing/ -x --no-cov && uv run mypy --strict src/pricing src/state && uv run ruff check src tests</automated>
  </verify>
  <done>
- _live_theo_impl signature: round_conclusion: RoundConclusionLookup (REQUIRED).
- _live_theo_impl dispatches on state.bomb_planted per D-05.
- Defensive None-guard for missing post-plant fields documented inline.
- LiveTheoEngine.round_conclusion: RoundConclusionLookup (no Optional default).
- tests/pricing/test_live_theo_dispatch.py — 2 tests GREEN.
- tests/pricing/test_live_theo*.py — all tests GREEN under v2 surface.
- tests/pricing/ overall: 0 failures.
- mypy --strict src/pricing src/state — 0 errors.
  </done>
</task>

</tasks>

<verification>
- `uv run pytest tests/pricing/ -x --no-cov` — all GREEN (calibrator test xfailed, that's fine).
- `uv run pytest tests/probe/ -x` — Phase 2 ETL tests STILL GREEN (probe doesn't import economy or round_conclusion).
- `uv run mypy --strict src/pricing/ src/state/` — 0 errors.
- `uv run ruff check src/ tests/ scripts/` — clean.
- `uv run python -c "from src.pricing.round_conclusion import RoundConclusionLookup; rc = RoundConclusionLookup.from_json('models/round_conclusion.json'); assert (3, 2, 0, 'atk', 'Lotus') in rc.cells_full"` — synthetic cell present.
- `! grep -E "RoundConclusionFn|def lookup\\(" src/pricing/round_conclusion.py` — v1 surface absent.
- `[ ! -f src/pricing/economy.py ]` — economy module deleted.
</verification>

<success_criteria>
- REQ-round-conclusion-lookup acceptance criteria from SPEC.md Acceptance Criteria #10-11 GREEN: v2 schema_version=2 file on disk; live_theo dispatch test exercises both paths.
- DEC-007 v2 two-path round-conclusion implemented; CRule 6a "two clean code paths in live_theo" satisfied.
- D-04 / D-05 / D-06 implementation locks landed.
- Phase 1+2 regression suite GREEN under v2 surface (calibrator test xfailed pointing at 03-07).
- src/pricing/economy.py deleted per CLAUDE.md "Economy buckets — DEPRECATED in v2".
</success_criteria>

<output>
After completion, create `.planning/phases/03-live-ingestion-layer/03-02-SUMMARY.md`
documenting:
- v1 surface deletions (RoundConclusionFn Protocol, lookup() method, cells_no_econ, 4 ECON_BUCKET_*_FLOOR + OCR_FRAMES_PER_SECOND constants, src/pricing/economy.py)
- v2 surface additions (between_round_p, post_plant_p, BetweenRoundFn, PostPlantFn, schema_version=2 gate, 5-tier hierarchy walk, POST_PLANT_TIMER_S + TIME_BUCKET_WIDTH_S + ROUND_CONCLUSION_JSON_PATH constants)
- live_theo dispatch logic landed at _live_theo_impl with defensive None-guard for malformed bomb_planted=True states
- models/round_conclusion.json synthetic v2 cell (`(3, 2, 0, "atk", "Lotus")`) note + pointer to 03-07 for real calibration
- Regression strategy: Phase 1+2 LiveTheoEngine tests patched in-place; calibrator test xfailed with TODO("03-07")
- Test count: 3 GREEN (round_conclusion_v2) + 2 GREEN (live_theo_dispatch) + Phase 1+2 regression GREEN
- next-wave dependency: Wave 4 plans (03-03/04/05/06) all depend on 03-01 only — they can run in parallel with 03-02; the 03-08 E2E gate at Wave 6 is the first downstream consumer of 03-02's dispatch path
</output>
</content>
</invoke>