---
phase: 03-live-ingestion-layer
plan: "01"
type: execute
wave: 2
depends_on: ["03-00"]
files_modified:
  - src/state/match_state.py
  - src/state/__init__.py
  - src/pricing/data.py
  - src/pricing/__init__.py
  - src/pricing/live_theo.py
  - src/pricing/dp.py
  - src/pricing/round_types.py
  - src/pricing/economy.py
  - tests/pricing/test_live_theo.py
  - tests/pricing/test_live_theo_with_calibrated_round_conclusion.py
  - tests/pricing/test_round_types.py
  - tests/ingestion/conftest.py
  - tests/ingestion/test_match_state.py
  - tests/ingestion/test_match_state_jsonl.py
autonomous: true
requirements:
  - REQ-match-state-engine
notes: |
  Wave 1 — atomic move of MatchState from src/pricing/data.py to
  src/state/match_state.py with v2 field set. Two atomic commits:
  Task 1 lands the new module + migration; Task 2 lands the commit/quarantine
  helpers + JSONL replay. Re-export shim path picked: KEEP a one-line shim in
  src/pricing/data.py for one transition commit (Task 1) then DELETE in Task 2
  alongside the helper additions — simplifies grep-search-and-replace in tests
  while keeping the long-term import path canonical (src.state.match_state).

must_haves:
  truths:
    - "MatchState lives at src/state/match_state.py with v2 field set (19 fields per D-01)"
    - "MatchState.with_update(**diff) bumps seq_id by 1 and returns a new frozen instance, no I/O"
    - "All Phase 1+2 in-repo MatchState imports resolve to src.state.match_state"
    - "JSONL replay determinism: write 1000 events, replay = identical final state"
    - "mypy --strict src/state/ clean (RESEARCH Pitfall 7 — strict override active)"
    - "Phase 1 + Phase 2 regression suite STILL GREEN under the new import path"
  artifacts:
    - path: "src/state/match_state.py"
      provides: "MatchState v2 dataclass + with_update + commit + quarantine helpers"
      min_lines: 150
      contains: "with_update"
    - path: "src/state/__init__.py"
      provides: "Re-exports MatchState, commit, quarantine"
      contains: "MatchState"
    - path: "src/pricing/data.py"
      provides: "HalfRates + TheoOutput only (MatchState DELETED post-Task 2)"
    - path: "tests/ingestion/test_match_state.py"
      provides: "GREEN seq_id property test + with_update field semantics"
      contains: "test_seq_id_strictly_monotonic"
    - path: "tests/ingestion/test_match_state_jsonl.py"
      provides: "GREEN JSONL replay determinism + commit/quarantine line schema"
      contains: "test_replay_determinism"
  key_links:
    - from: "src/pricing/live_theo.py"
      to: "src/state/match_state.py:MatchState"
      via: "from src.state.match_state import MatchState"
      pattern: "from src\\.state(\\.match_state)? import.*MatchState"
    - from: "src/pricing/__init__.py"
      to: "src.state.match_state.MatchState"
      via: "re-export so `from src.pricing import MatchState` still works"
      pattern: "from src\\.state(\\.match_state)? import MatchState"
    - from: "tests/ingestion/test_match_state_jsonl.py"
      to: "src/state/match_state.py:commit, quarantine"
      via: "from src.state import commit, quarantine"
      pattern: "commit|quarantine"
---

<objective>
Move `MatchState` from `src/pricing/data.py` to `src/state/match_state.py` with
the v2 field set (D-01). Add the pure `with_update` mutator (D-02) and the
arbiter-only `commit` / `quarantine` helpers (D-02 / D-03 — single-writer
guarantee documented at the helper). Atomically rewrite the 5 in-repo imports.

Purpose: REQ-match-state-engine is the structural foundation for every other
Phase 3 wave. The arbiter (3A), OCR pipeline (3C), poller (3B), and listener
(3D) all push diffs through `with_update`; the live_theo dispatch (2A) reads
the new `bomb_planted | attackers_alive | defenders_alive | time_left_s` fields.
Without Wave 1 GREEN, every other wave is blocked.

Output:
- `src/state/match_state.py` (~200 LOC: dataclass + with_update + commit + quarantine + module docstring)
- `src/state/__init__.py` re-exports
- `src/pricing/data.py` shrunk to HalfRates + TheoOutput
- All 5 import sites rewritten
- 3 new GREEN tests + Phase 1/2 regression suite STILL GREEN
</objective>

<execution_context>
@C:/Users/Joseph Cheng/.claude/get-shit-done/workflows/execute-plan.md
@C:/Users/Joseph Cheng/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/STATE.md
@.planning/phases/03-live-ingestion-layer/03-SPEC.md
@.planning/phases/03-live-ingestion-layer/03-CONTEXT.md
@.planning/phases/03-live-ingestion-layer/03-RESEARCH.md
@.planning/phases/03-live-ingestion-layer/03-VALIDATION.md
@src/pricing/data.py
@src/pricing/__init__.py
@src/pricing/live_theo.py

<interfaces>
<!-- Phase 1 MatchState (current — 17 fields). Wave 1 cuts 3, adds 6 → 19 v2 fields. -->
From src/pricing/data.py (CURRENT — to be removed):
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
    map_winners: tuple[Optional[bool], ...]
    pistol_winner_a: dict[int, Optional[bool]]
    numerical_diff: int    # CUT in v2
    bomb_planted: bool
    side: str              # CUT in v2 (not the same as side_orient)
    econ_bucket: str       # CUT in v2
```

Target v2 shape (D-01 / RESEARCH §"Pattern 1"):
```python
@dataclass(frozen=True, slots=True)
class MatchState:
    # 6 static fields (Phase 1 D-17/D-18/D-19 — REQUIRED by live_theo)
    match_id: str
    team_a: str
    team_b: str
    map_pool: tuple[str, ...]
    map_side_orients: tuple[str, ...]
    map_winners: tuple[Optional[bool], ...]
    pistol_winner_a: dict[int, Optional[bool]]
    # 13 dynamic fields (v2 spec)
    map_idx: int
    a_map_score: int
    b_map_score: int
    a_round: int
    b_round: int
    side_orient: str
    bomb_planted: bool
    attackers_alive: Optional[int]   # NEW v2 (post-plant only)
    defenders_alive: Optional[int]   # NEW v2 (post-plant only)
    time_left_s: Optional[float]     # NEW v2 (computed per D-14)
    seq_id: int                       # NEW v2
    last_updated_ts: float            # NEW v2

    def with_update(self, **fields_changed: Any) -> "MatchState":
        return replace(self, seq_id=self.seq_id + 1, last_updated_ts=time.time(), **fields_changed)
```

Module-level helpers (D-02 / D-03 / RESEARCH §"Code Examples"):
```python
def commit(prev: MatchState, fields_changed: dict[str, Any], *,
           source: str, event_type: str,
           timestamps: dict[str, float | int | None],
           jsonl_path: Path) -> MatchState: ...
def quarantine(prev: MatchState, fields_proposed: dict[str, Any], *,
               source: str, event_type: str, quarantine_reason: str,
               t_observed: float, jsonl_path: Path) -> None: ...
```

Existing import sites (5 files — confirmed via grep on src/):
- src/pricing/__init__.py:16 — `from src.pricing.data import HalfRates, MatchState, TheoOutput`
- src/pricing/live_theo.py:42 — `from src.pricing.data import HalfRates, MatchState, TheoOutput`
- src/pricing/dp.py — references MatchState in type aliases
- src/pricing/round_types.py — references MatchState in round_p_for_round signature
- src/pricing/economy.py — references MatchState (verify at execution time)

Phase 1+2 test files importing MatchState:
- tests/pricing/test_live_theo.py
- tests/pricing/test_live_theo_with_calibrated_round_conclusion.py
- tests/pricing/test_round_types.py
- (others surface via grep at execution time)
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Create src/state/match_state.py v2 dataclass + with_update; rewrite imports</name>
  <files>
    src/state/match_state.py
    src/state/__init__.py
    src/pricing/data.py
    src/pricing/__init__.py
    src/pricing/live_theo.py
    src/pricing/dp.py
    src/pricing/round_types.py
    src/pricing/economy.py
    tests/pricing/test_live_theo.py
    tests/pricing/test_live_theo_with_calibrated_round_conclusion.py
    tests/pricing/test_round_types.py
    tests/ingestion/conftest.py
    tests/ingestion/test_match_state.py
  </files>
  <behavior>
    - `MatchState` dataclass at `src/state/match_state.py` with the 19 fields enumerated in <interfaces>; `frozen=True, slots=True`.
    - `MatchState.with_update(**fields_changed)` returns a NEW instance with `seq_id += 1` and `last_updated_ts = time.time()`. Pure: no JSONL I/O.
    - `seq_id` strictly monotonic across 1000 random `with_update` calls (RESEARCH §"Code Examples" hypothesis pattern).
    - `with_update()` with no kwargs still bumps seq_id (semantic: state has changed via heartbeat).
    - `tests/ingestion/test_match_state.py::test_seq_id_strictly_monotonic` GREEN; `test_with_update_field_semantics` GREEN.
    - `from src.pricing import MatchState` STILL works (re-export shim in src/pricing/__init__.py points to src.state.match_state).
    - `from src.state.match_state import MatchState` works.
    - `from src.state import MatchState` works (via __init__.py re-export).
    - All Phase 1 + Phase 2 tests STILL GREEN — every internal `MatchState(...)` constructor call passes the 6 new v2 fields with defaults (existing tests call MatchState with kwargs; the test files need a one-line patch to drop `numerical_diff/side/econ_bucket` from kwargs and add `bomb_planted=False, attackers_alive=None, defenders_alive=None, time_left_s=None, seq_id=0, last_updated_ts=0.0`).
    - `mypy --strict src/state/` clean.
    - tests/ingestion/conftest.py `make_match_state()` fixture upgraded from `dict` return to direct `MatchState(**base)` construction.
    - `src/pricing/data.py` retains a re-export shim: `from src.state.match_state import MatchState  # re-export for transition; remove in Task 2`.
  </behavior>
  <action>
1) **Create `src/state/match_state.py`** with module docstring citing D-01 / D-02 / D-14 / RESEARCH §"Pattern 1":
   - `from __future__ import annotations`
   - imports: `dataclasses.dataclass, dataclasses.replace`, `time`, `typing.Any, Optional`
   - 19-field `@dataclass(frozen=True, slots=True) class MatchState` per <interfaces> shape
   - field-order discipline: 7 static fields first (match_id..pistol_winner_a), then 12 dynamic fields. Reasoning: matches Phase 1 stub field order to minimize call-site churn; new v2 fields appended at the end with sensible defaults possible only via `field(default=None)`-on-Optional fields.
   - **NOTE on default values:** Since `frozen+slots` dataclasses don't allow positional defaults to follow positional non-defaults, use kw-only fields for the 6 new dynamic ones — declare with `dataclass(frozen=True, slots=True, kw_only=True)` if needed, OR keep ALL fields positional and require callers to pass everything. Pick: ALL POSITIONAL with NO defaults — forces callers to be explicit and matches Phase 1 idiom (Phase 1 MatchState has no defaults either).
   - `def with_update(self, **fields_changed: Any) -> "MatchState":` body uses `dataclasses.replace`. Bumps seq_id and last_updated_ts. NO I/O.
   - DO NOT add `commit` / `quarantine` helpers in this task — those land in Task 2.

2) **Create `src/state/__init__.py`** re-export:
   ```python
   """State engine — MatchState v2 dataclass + JSONL event log (Phase 3)."""
   from src.state.match_state import MatchState
   __all__ = ["MatchState"]
   ```
   (commit/quarantine added in Task 2.)

3) **Patch `src/pricing/data.py`** — DELETE the `MatchState` class (lines 59-105 of current file) and ADD a re-export shim at that location:
   ```python
   # ----------------------------------------------------------------------- #
   # 2. MatchState — moved to src/state/match_state.py per Phase 3 D-01     #
   # ----------------------------------------------------------------------- #
   # Phase 3 (REQ-match-state-engine) moved MatchState to src/state/match_state.py
   # with the v2 field set. This re-export shim preserves `from src.pricing.data
   # import MatchState` for the duration of the Wave 1 atomic-rename commit;
   # Task 2 of plan 03-01 deletes the shim entirely. Downstream code MUST migrate
   # to `from src.state.match_state import MatchState` (or `from src.state import
   # MatchState`).
   from src.state.match_state import MatchState  # noqa: F401 — transition re-export
   ```

4) **Patch `src/pricing/__init__.py`** — change line 16 from
   `from src.pricing.data import HalfRates, MatchState, TheoOutput` to:
   ```python
   from src.pricing.data import HalfRates, TheoOutput
   from src.state.match_state import MatchState
   ```
   `__all__` STAYS unchanged — `MatchState` still re-exported from `src.pricing`.

5) **Patch `src/pricing/live_theo.py:42`** identically: split the import into pricing-side (HalfRates, TheoOutput) and state-side (MatchState).

6) **Patch `src/pricing/dp.py`, `src/pricing/round_types.py`, `src/pricing/economy.py`** — for any `from src.pricing.data import MatchState` lines, swap to `from src.state.match_state import MatchState`. (Verify by `grep -rn 'pricing.data import.*MatchState' src/` before patching.)

7) **Patch Phase 1+2 test files** — every test that constructs `MatchState(...)` directly. The minimum-disruption patch:
   - DROP these kwargs from the constructor call: `numerical_diff=N, side='X', econ_bucket='Y'`
   - ADD these kwargs (in this order to match the new positional declaration): `bomb_planted=False, attackers_alive=None, defenders_alive=None, time_left_s=None, seq_id=0, last_updated_ts=0.0`
   - Some tests already pass `bomb_planted=...` — preserve those values.
   - Files to patch: `tests/pricing/test_live_theo.py`, `tests/pricing/test_live_theo_with_calibrated_round_conclusion.py`, `tests/pricing/test_round_types.py`. Verify with grep before patching: `grep -n 'MatchState(' tests/pricing/`. If grep surfaces additional files, patch them too.
   - Pricing tests that previously checked Phase 1 stub fields (`assert state.numerical_diff == ...`) need their assertions deleted with a comment `# Phase 3 v2: numerical_diff cut from MatchState (D-01); see src.state.match_state`.

8) **Upgrade `tests/ingestion/conftest.py::make_match_state`** to return a `MatchState` instance instead of `dict[str, Any]`:
   ```python
   from src.state.match_state import MatchState

   @pytest.fixture
   def make_match_state() -> Callable[..., MatchState]:
       def _make(**overrides: Any) -> MatchState:
           base: dict[str, Any] = { ...same defaults as Wave 0... }
           base.update(overrides)
           return MatchState(**base)
       return _make
   ```

9) **Wire `tests/ingestion/test_match_state.py`** to GREEN — replace both xfail stubs with real implementations:
   - `test_seq_id_strictly_monotonic`: copy the hypothesis recipe from RESEARCH §"Code Examples" / "Hypothesis property test for seq_id monotonicity". Use `make_match_state` fixture for the initial state.
   - `test_with_update_field_semantics`: assert that `state.with_update(bomb_planted=True).bomb_planted is True`, that other fields are unchanged, that `seq_id` bumps by 1, that `last_updated_ts` strictly > prior value (use `time.sleep(1e-3)` between calls to dodge Windows wall-clock resolution per RESEARCH Pitfall 8).

Atomic commit message: `feat(03-01): move MatchState to src/state with v2 field set + with_update mutator`
  </action>
  <verify>
    <automated>uv run pytest tests/ingestion/test_match_state.py tests/pricing/ tests/probe/ tests/calibration/ -x --no-cov && uv run mypy --strict src/state/ src/pricing/ && uv run ruff check src/ tests/</automated>
  </verify>
  <done>
- `src/state/match_state.py` exists with v2 dataclass + `with_update`.
- `src/state/__init__.py` re-exports MatchState.
- `src/pricing/data.py` retains 1-line re-export shim (Task 2 deletes it).
- All 5 in-repo MatchState imports resolve correctly.
- `tests/ingestion/test_match_state.py` GREEN (2 tests pass).
- Phase 1 + Phase 2 regression suite GREEN (`uv run pytest tests/pricing/ tests/probe/ tests/calibration/ -x` 0 failures).
- `mypy --strict src/state/` and `mypy --strict src/pricing/` both clean.
- `ruff check src/ tests/` clean.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Add commit() / quarantine() JSONL helpers + replay determinism test; delete pricing/data.py shim</name>
  <files>
    src/state/match_state.py
    src/state/__init__.py
    src/pricing/data.py
    tests/ingestion/test_match_state_jsonl.py
  </files>
  <behavior>
    - `commit(prev, fields_changed, *, source, event_type, timestamps, jsonl_path) → MatchState` writes a single JSONL line per the D-03 schema and returns the new state.
    - `commit()` synchronously appends; relies on single-writer atomicity per RESEARCH Pitfall 4. Module docstring documents the single-writer invariant.
    - `quarantine(prev, fields_proposed, *, source, event_type, quarantine_reason, t_observed, jsonl_path) → None` writes a JSONL line with `seq_id: null`, `quarantined: true`. State UNCHANGED — caller is responsible for not swapping references.
    - JSONL line schema EXACTLY matches D-03:
      - commit line: `{"seq_id": int, "t_observed": float, "t_ingested": int, "t_arbited": int, "t_state_committed": int, "t_theo_computed": null, "t_quote_sent": null, "source": str, "event_type": str, "fields_changed": dict}`
      - quarantine line: `{"seq_id": null, "quarantined": true, "quarantine_reason": str, "t_observed": float, "source": str, "event_type": str, "fields_proposed": dict}`
    - `t_state_committed` is recorded INSIDE commit() via `time.monotonic_ns()` AFTER `with_update()` returns and BEFORE the JSONL write per D-03 hot-path budget.
    - `tests/ingestion/test_match_state_jsonl.py::test_replay_determinism` GREEN: write 1000 commits, read JSONL line-by-line, replay via `with_update(**line["fields_changed"])` in seq_id order, assert final state == in-memory final state.
    - `tests/ingestion/test_match_state_jsonl.py::test_commit_line_schema` GREEN: assert line dict has exactly the 9 keys above with correct types.
    - `tests/ingestion/test_match_state_jsonl.py::test_quarantine_line_schema` GREEN: assert quarantine line has exactly the 7 keys above with `seq_id is None` and `quarantined is True`.
    - `src/pricing/data.py` no longer mentions `MatchState` (the Task 1 transition shim is DELETED).
    - All Phase 1 + Phase 2 tests STILL GREEN.
  </behavior>
  <action>
1) **Append `commit` and `quarantine` to `src/state/match_state.py`** (per RESEARCH §"Code Examples" — copy the implementations and adapt for type annotations):
   ```python
   from pathlib import Path
   import json

   def commit(
       prev: MatchState,
       fields_changed: dict[str, Any],
       *,
       source: str,
       event_type: str,
       timestamps: dict[str, float | int | None],
       jsonl_path: Path,
   ) -> MatchState:
       """Commit a state mutation: bump seq_id, write JSONL diff line, return new state.

       Caller is the arbiter (sole writer per D-02 / RESEARCH Pitfall 4). The
       jsonl_path SHOULD be a per-match file at data/event_log/{match_id}.jsonl.
       t_state_committed is recorded BEFORE the synchronous JSONL append to
       satisfy the D-03 / SPEC §6 bomb-detect → t_state_committed p50 < 100ms
       budget — disk write latency is excluded from the latency math.
       """
       new_state = prev.with_update(**fields_changed)
       timestamps["t_state_committed"] = time.monotonic_ns()
       line: dict[str, Any] = {
           "seq_id": new_state.seq_id,
           "t_observed": timestamps.get("t_observed"),
           "t_ingested": timestamps.get("t_ingested"),
           "t_arbited": timestamps.get("t_arbited"),
           "t_state_committed": timestamps["t_state_committed"],
           "t_theo_computed": timestamps.get("t_theo_computed"),
           "t_quote_sent": timestamps.get("t_quote_sent"),
           "source": source,
           "event_type": event_type,
           "fields_changed": fields_changed,
       }
       jsonl_path.parent.mkdir(parents=True, exist_ok=True)
       with jsonl_path.open("a", encoding="utf-8") as f:
           f.write(json.dumps(line, separators=(",", ":")) + "\n")
       return new_state

   def quarantine(
       prev: MatchState,
       fields_proposed: dict[str, Any],
       *,
       source: str,
       event_type: str,
       quarantine_reason: str,
       t_observed: float,
       jsonl_path: Path,
   ) -> None:
       """Record a quarantined event; state UNCHANGED.

       prev is accepted (and unused at body level) to keep the call-site
       symmetric with commit(...) — the arbiter calls one or the other and
       passes prev for context.
       """
       del prev  # symmetric with commit() signature; state unchanged
       line: dict[str, Any] = {
           "seq_id": None,
           "quarantined": True,
           "quarantine_reason": quarantine_reason,
           "t_observed": t_observed,
           "source": source,
           "event_type": event_type,
           "fields_proposed": fields_proposed,
       }
       jsonl_path.parent.mkdir(parents=True, exist_ok=True)
       with jsonl_path.open("a", encoding="utf-8") as f:
           f.write(json.dumps(line, separators=(",", ":")) + "\n")
   ```

2) **Update `src/state/__init__.py`** to re-export the helpers:
   ```python
   from src.state.match_state import MatchState, commit, quarantine
   __all__ = ["MatchState", "commit", "quarantine"]
   ```

3) **Delete the Task 1 re-export shim from `src/pricing/data.py`** — remove the entire MatchState section (the comment block + `from src.state.match_state import MatchState` shim line). The file's module docstring should be updated to note "MatchState moved to src/state/match_state.py per Phase 3 D-01".

4) **Wire `tests/ingestion/test_match_state_jsonl.py`** to GREEN — three tests:

   `test_replay_determinism` (use `tmp_event_log_path` + `make_match_state` fixtures):
   ```python
   import json
   import time
   from src.state import MatchState, commit
   # Generate 1000 random diffs (use hypothesis or seeded random.Random for determinism)
   # For each diff: state = commit(state, diff, source="test", event_type="test_event",
   #                                timestamps={"t_observed": time.time(), "t_ingested": time.monotonic_ns(),
   #                                             "t_arbited": time.monotonic_ns(),
   #                                             "t_theo_computed": None, "t_quote_sent": None},
   #                                jsonl_path=tmp_event_log_path)
   # After 1000 commits: read jsonl line-by-line, replay via with_update(**line["fields_changed"])
   # in seq_id order, assert final replayed state == final in-memory state.
   ```

   `test_commit_line_schema`: write ONE commit, read back, assert the 9 keys + types per D-03.

   `test_quarantine_line_schema`: write ONE quarantine, read back, assert the 7 keys with `seq_id is None`, `quarantined is True`.

5) Confirm with grep that no remaining `MatchState` reference exists in `src/pricing/data.py` (`grep MatchState src/pricing/data.py` should return 0 hits).

Atomic commit message: `feat(03-01): add commit/quarantine JSONL helpers + replay determinism (REQ-match-state-engine)`
  </action>
  <verify>
    <automated>uv run pytest tests/ingestion/test_match_state_jsonl.py tests/ingestion/test_match_state.py tests/pricing/ tests/probe/ tests/calibration/ -x --no-cov && uv run mypy --strict src/state/ src/pricing/ && ! grep -E "class MatchState" src/pricing/data.py</automated>
  </verify>
  <done>
- `src/state/match_state.py` exports `commit` and `quarantine` helpers per D-03 schema.
- `src/state/__init__.py` re-exports all three names.
- `src/pricing/data.py` no longer references MatchState (grep returns 0 hits).
- `tests/ingestion/test_match_state_jsonl.py` GREEN (3 tests).
- Phase 1 + Phase 2 regression suite STILL GREEN.
- mypy --strict clean on both packages.
  </done>
</task>

</tasks>

<verification>
- `uv run pytest tests/ingestion/test_match_state.py tests/ingestion/test_match_state_jsonl.py -v` — 5 tests pass (2 from Task 1, 3 from Task 2).
- `uv run pytest tests/pricing/ tests/probe/ tests/calibration/ -x` — Phase 1 + Phase 2 regression GREEN.
- `uv run mypy --strict src/state/` — 0 errors.
- `uv run mypy --strict src/pricing/` — 0 errors (existing strict scope preserved).
- `uv run ruff check src/ tests/` — clean.
- `grep -rn 'pricing.data import.*MatchState' src/` — 0 hits (all migrated to src.state).
</verification>

<success_criteria>
- REQ-match-state-engine acceptance criteria #1-3 from SPEC.md GREEN.
- All 5 src/-side import sites swap to `from src.state(.match_state) import MatchState`.
- JSONL replay over 1000 events produces identical state.
- D-03 line schema test GREEN.
</success_criteria>

<output>
After completion, create `.planning/phases/03-live-ingestion-layer/03-01-SUMMARY.md`
documenting:
- v2 MatchState field list (19 fields) + the 3 cut + 6 added vs Phase 1 stub
- commit/quarantine JSONL line schema (9-key commit, 7-key quarantine)
- 5 import sites rewritten + the test-fixture upgrade
- Phase 1 + Phase 2 regression: PASS (count tests by package)
- next-wave dependency: Wave 2A (round_conclusion v2 surface) consumes
  `state.bomb_planted | attackers_alive | defenders_alive | time_left_s`;
  Wave 3A (arbiter) calls `commit()`/`quarantine()` directly
</output>
