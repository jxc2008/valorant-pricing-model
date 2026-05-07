---
phase: 03-live-ingestion-layer
plan: "00"
type: execute
wave: 1
depends_on: []
files_modified:
  - pyproject.toml
  - tests/ingestion/__init__.py
  - tests/ingestion/conftest.py
  - tests/ingestion/test_match_state.py
  - tests/ingestion/test_match_state_jsonl.py
  - tests/ingestion/test_scoreboard.py
  - tests/ingestion/test_ocr_score.py
  - tests/ingestion/test_ocr_bomb.py
  - tests/ingestion/test_ocr_round_end.py
  - tests/ingestion/test_ocr_alive_widget.py
  - tests/ingestion/test_text_listener.py
  - tests/ingestion/test_arbiter.py
  - tests/ingestion/test_latency.py
  - tests/ingestion/test_e2e.py
  - tests/ingestion/fixtures/.gitkeep
  - tests/pricing/test_round_conclusion_v2.py
  - tests/pricing/test_live_theo_dispatch.py
  - .gitignore
autonomous: true
requirements:
  - REQ-match-state-engine
  - REQ-scoreboard-polling
  - REQ-ocr-pipeline
  - REQ-text-listener
  - REQ-cross-source-arbiter
  - REQ-latency-instrumentation
  - REQ-round-conclusion-lookup
  - REQ-end-to-end-latency
notes: |
  Wave 0 — RED-stub test infrastructure. Lays the per-REQ test files (skipped
  with xfail) so each subsequent wave can swap stubs for assertions atomically.
  Also adds dev deps (pytest-asyncio, aioresponses, pytesseract, Pillow,
  opencv-python, numpy, requests-cache, tweepy, aiohttp) and the
  `[[tool.mypy.overrides]] module = "src.state.*"` strict override per RESEARCH
  Pitfall 7. Per orchestrator gate: NO operator pause — placeholder ROIs land
  in Wave 3C; this wave only touches test scaffolds + tooling.

must_haves:
  truths:
    - "tests/ingestion/ package collects under pytest with 0 errors (xfail-stubs allowed)"
    - "uv-installed dev deps (pytest-asyncio, aioresponses) load without ImportError"
    - "mypy --strict src/state/ runs without 'unrecognized module' errors (empty module passes)"
  artifacts:
    - path: "tests/ingestion/conftest.py"
      provides: "shared fixtures: make_match_state, tmp_event_log_path, synthetic_frame_factory, arbiter_with_stub_sources"
      min_lines: 30
    - path: "tests/ingestion/test_match_state.py"
      provides: "RED stub for REQ-match-state-engine seq_id property test"
      contains: "test_seq_id_strictly_monotonic"
    - path: "tests/pricing/test_round_conclusion_v2.py"
      provides: "RED stub for post_plant_p hierarchy + from_json schema_version gate"
      contains: "test_post_plant_p_hierarchy"
    - path: "tests/pricing/test_live_theo_dispatch.py"
      provides: "RED stub for D-05 dispatch test (bomb_planted=True path)"
      contains: "test_dispatch_bomb_planted"
    - path: "pyproject.toml"
      provides: "[[tool.mypy.overrides]] module = \"src.state.*\" strict = true"
      contains: "src.state.*"
  key_links:
    - from: "pyproject.toml [project].dependencies"
      to: "uv-installed packages (aiohttp, pytesseract, Pillow, opencv-python, numpy, requests-cache, tweepy)"
      via: "uv add"
      pattern: "aiohttp.*pytesseract.*requests-cache"
    - from: "pyproject.toml [dependency-groups].dev"
      to: "uv-installed dev packages (pytest-asyncio, aioresponses)"
      via: "uv add --dev"
      pattern: "pytest-asyncio.*aioresponses"
    - from: "tests/ingestion/test_*.py"
      to: "shared fixtures in tests/ingestion/conftest.py"
      via: "pytest auto-discovery"
      pattern: "def test_"
---

<objective>
Wave 0 establishes the test scaffolding that every subsequent Phase 3 wave drops
GREEN tests into. Adds the eight new runtime + dev dependencies the rest of
Phase 3 needs. Adds the `src.state.*` mypy strict override per RESEARCH Pitfall
7 so executors land mypy-clean code from Wave 1 onward without re-tooling.

Purpose: Per VALIDATION.md, every per-REQ test file must already exist (RED
stub) so executors can land `<automated>` verify commands as plain `pytest -k`
invocations. Without Wave 0 the executor stubs would race with implementation,
break the Nyquist sampling rate, and fail the per-task verify gate.

Output: Empty test files (xfail-stubs only) + populated conftest + dep updates
+ mypy override. No `src/` code changes.
</objective>

<execution_context>
@C:/Users/Joseph Cheng/.claude/get-shit-done/workflows/execute-plan.md
@C:/Users/Joseph Cheng/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/03-live-ingestion-layer/03-SPEC.md
@.planning/phases/03-live-ingestion-layer/03-CONTEXT.md
@.planning/phases/03-live-ingestion-layer/03-RESEARCH.md
@.planning/phases/03-live-ingestion-layer/03-VALIDATION.md
@pyproject.toml

<interfaces>
<!-- Phase 1 MatchState (TO BE MOVED in Wave 1 — fixtures must work against either path during transition) -->
From src/pricing/data.py:
```python
@dataclass(frozen=True, slots=True)
class MatchState:  # 17 fields — Phase 1 stub. Wave 1 cuts numerical_diff/side/econ_bucket and adds 6 v2 dynamic fields.
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
    numerical_diff: int      # CUT in Wave 1
    bomb_planted: bool
    side: str                # CUT in Wave 1
    econ_bucket: str         # CUT in Wave 1
```

Phase 1 fixtures DO NOT yet exist for `make_match_state(**overrides)`. Wave 0
creates the helper such that it builds a v2-shaped state dict (rather than a
direct `MatchState(...)` call) so the same conftest survives Wave 1's atomic
move. Use `dict[str, Any]` returns; Wave 1 task converts to direct dataclass
construction once the v2 dataclass exists.

Existing test pattern (tests/pricing/conftest.py and tests/pricing/test_live_theo.py)
shows how MatchState fixtures are built today — mirror its shape but use the
v2 field set.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add Phase 3 deps + mypy strict override for src.state</name>
  <files>pyproject.toml</files>
  <action>
Add the following to `pyproject.toml` (in-place edit; preserve everything else):

1) Append to `[project].dependencies` (alphabetical insertion):
```
"aiohttp>=3.13,<4",
"numpy>=1.26,<3",
"opencv-python>=4.10,<5",
"Pillow>=10.4,<12",
"pytesseract>=0.3.13,<1",
"requests-cache>=1.3,<2",
"tweepy>=4.14,<5",
```

2) Append to `[dependency-groups].dev` (alphabetical insertion):
```
"aioresponses>=0.7.6",
"pytest-asyncio>=0.23",
```

3) Add a NEW `[[tool.mypy.overrides]]` block AFTER the existing `module = "src.pricing.*"` block:
```
[[tool.mypy.overrides]]
# Phase 3 SPEC §"Constraints" (CRule 11): mypy --strict extends from src/pricing/
# to ALSO cover src/state/. RESEARCH Pitfall 7 — must add the override here
# explicitly so CI runs strict, not just CLI invocations.
module = "src.state.*"
strict = true
disallow_any_explicit = false
warn_return_any = true
```

4) Run `uv lock` then `uv sync --all-extras --dev` so the lock file is regenerated and the new deps install.

Pin reasoning (from 03-RESEARCH.md §"Standard Stack"):
- `aiohttp 3.13.x` — TaskGroup-compatible (3.11+); de-facto async HTTP
- `pytesseract 0.3.13` — subprocess wrapper, GIL-friendly
- `Pillow >=10.4` — pytesseract dep; pin upper bound to <12 for ABI safety
- `opencv-python 4.10` — Otsu threshold + BGR/RGB; binary wheel works on Windows + Linux
- `numpy >=1.26,<3` — image array shuffling; pyproject.toml-style constraint matches scientific-stack norms
- `requests-cache 1.3.x` — filesystem backend stable since 1.0
- `tweepy >=4.14` — `AsyncStreamingClient` shipped 4.10
- `aioresponses >=0.7.6` — context-manager mock for aiohttp
- `pytest-asyncio >=0.23` — `@pytest.mark.asyncio` decorator

Do NOT touch `requires-python` (already `>=3.11,<3.12`). Do NOT touch ruff
config or other mypy override.
  </action>
  <verify>
    <automated>uv sync --all-extras --dev && uv run python -c "import aiohttp, pytesseract, PIL, cv2, numpy, requests_cache, tweepy, aioresponses, pytest_asyncio; print('all imports ok')"</automated>
  </verify>
  <done>
- All 9 new deps appear in `pyproject.toml` (7 runtime + 2 dev).
- `[[tool.mypy.overrides]]` for `src.state.*` exists with `strict = true`.
- `uv sync` succeeds, `uv.lock` updated.
- Smoke import command above prints `all imports ok`.
- `uv run mypy src/state/` runs without "module not configured" errors (empty module → 0 issues).
  </done>
</task>

<task type="auto">
  <name>Task 2: Create tests/ingestion/ package + conftest with shared fixtures</name>
  <files>
    tests/ingestion/__init__.py
    tests/ingestion/conftest.py
    tests/ingestion/fixtures/.gitkeep
    .gitignore
  </files>
  <action>
1) Create `tests/ingestion/__init__.py` — single line: `"""Phase 3 live-ingestion test package."""`

2) Create `tests/ingestion/fixtures/.gitkeep` (empty file) so the dir is tracked under git for Wave 3C synthetic OCR frames.

3) Create `tests/ingestion/conftest.py` with the four shared fixtures the VALIDATION.md table requires. Use `dict[str, Any]` returns from `make_match_state()` so the same fixture survives the Wave 1 atomic move — Wave 1's first task patches the helper to return a `MatchState` instance. Skeleton:

```python
"""Phase 3 ingestion test fixtures.

Used by every tests/ingestion/test_*.py file per VALIDATION.md.
Designed to survive the Wave 1 atomic move of MatchState from
src/pricing/data.py to src/state/match_state.py — fixtures return
dict[str, Any] payloads that callers convert to dataclass instances.
"""
from __future__ import annotations

import json
import time
from collections import deque
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pytest


@pytest.fixture
def make_match_state() -> Callable[..., dict[str, Any]]:
    """Build a v2-shape MatchState dict; tests convert to dataclass post-Wave-1.

    Default state: BO3 series in progress, map 0 active, T1 vs Sentinels on
    Lotus|Bind|Haven, side_orient=a_atk, no bomb planted, seq_id=0.
    Override any field via kwargs.
    """
    def _make(**overrides: Any) -> dict[str, Any]:
        base: dict[str, Any] = {
            "match_id": "test-match-001",
            "team_a": "T1",
            "team_b": "Sentinels",
            "map_pool": ("Lotus", "Bind", "Haven"),
            "map_side_orients": ("a_atk", "a_def", "a_atk"),
            "map_winners": (None, None, None),
            "pistol_winner_a": {0: None, 1: None, 2: None},
            "map_idx": 0,
            "a_map_score": 0,
            "b_map_score": 0,
            "a_round": 0,
            "b_round": 0,
            "side_orient": "a_atk",
            "bomb_planted": False,
            "attackers_alive": None,
            "defenders_alive": None,
            "time_left_s": None,
            "seq_id": 0,
            "last_updated_ts": 0.0,
        }
        base.update(overrides)
        return base
    return _make


@pytest.fixture
def tmp_event_log_path(tmp_path: Path) -> Path:
    """Per-test JSONL event-log path; gitignored data/event_log/ format mirrored."""
    p = tmp_path / "event_log" / "test-match-001.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


@pytest.fixture
def synthetic_frame_factory() -> Callable[..., np.ndarray]:
    """Build a fake BGR uint8 1920x1080 frame with optional digit overlays at ROI coords.

    Used by Wave 3C OCR benchmarks. Caller passes (att, def_) tuples and
    pixel coordinates; returns a frame ready for cv2 ROI extraction.
    """
    def _make(
        att: int | None = None,
        def_: int | None = None,
        att_roi: tuple[int, int, int, int] | None = None,
        def_roi: tuple[int, int, int, int] | None = None,
    ) -> np.ndarray:
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        # Wave 3C will draw digits via cv2.putText into the ROI rects;
        # this stub just allocates the frame buffer for collection.
        del att, def_, att_roi, def_roi  # populated by Wave 3C
        return frame
    return _make


@pytest.fixture
def arbiter_with_stub_sources() -> Callable[..., Any]:
    """Build an Arbiter wired to in-memory stub sources.

    Returns a builder Wave 3A populates once src/ingestion/arbiter.py exists.
    Wave 0 stub: returns SimpleNamespace with empty deques.
    """
    from types import SimpleNamespace
    def _build(**kwargs: Any) -> SimpleNamespace:
        del kwargs
        return SimpleNamespace(
            score_changes=deque(maxlen=128),
            bomb_events=deque(maxlen=64),
            round_end_events=deque(maxlen=64),
        )
    return _build
```

4) Append to `.gitignore` (NEW lines; verify they're not already present first):
```
# Phase 3 — live event log + metrics + ribgg cache (D-03 / D-08 / RESEARCH §"Project Structure")
data/event_log/
data/metrics/
data/ribgg_cache/
data/round_events_v2.sqlite
.claude-loop-output.tmp
```

(`.claude-loop-output.tmp` already exists at repo root per `git status`; ignore
it for cleanliness — does NOT block Phase 3 but unblocks operator's autonomous
loop hygiene.)
  </action>
  <verify>
    <automated>uv run pytest tests/ingestion/ --collect-only -q && uv run python -c "from tests.ingestion.conftest import *; print('conftest importable')"</automated>
  </verify>
  <done>
- `tests/ingestion/__init__.py`, `conftest.py`, `fixtures/.gitkeep` all exist.
- `pytest --collect-only` succeeds (0 collected, 0 errors — files exist but contain no tests yet).
- `.gitignore` carries the four new ignore lines.
  </done>
</task>

<task type="auto">
  <name>Task 3: Create RED-stub test files (one per REQ test from VALIDATION.md)</name>
  <files>
    tests/ingestion/test_match_state.py
    tests/ingestion/test_match_state_jsonl.py
    tests/ingestion/test_scoreboard.py
    tests/ingestion/test_ocr_score.py
    tests/ingestion/test_ocr_bomb.py
    tests/ingestion/test_ocr_round_end.py
    tests/ingestion/test_ocr_alive_widget.py
    tests/ingestion/test_text_listener.py
    tests/ingestion/test_arbiter.py
    tests/ingestion/test_latency.py
    tests/ingestion/test_e2e.py
    tests/pricing/test_round_conclusion_v2.py
    tests/pricing/test_live_theo_dispatch.py
  </files>
  <action>
Create 13 RED-stub test files. Each file:
- Has the test function name from VALIDATION.md (e.g. `test_seq_id_strictly_monotonic`).
- Body is a single `pytest.xfail("Wave N — implementation pending")` call so
  collection is GREEN but execution doesn't pollute CI red.
- Imports the right symbols from yet-unbuilt modules INSIDE the function (not
  at module top) — keeps collection clean even when the module doesn't exist.

Pattern for every stub function:
```python
import pytest

def test_seq_id_strictly_monotonic():
    pytest.xfail("Wave 1 — src/state/match_state.py + with_update implementation pending")
    # When Wave 1 lands, body becomes:
    # from src.state.match_state import MatchState
    # ... hypothesis property test per RESEARCH §"Code Examples"
```

Required test functions per file (mirror VALIDATION.md table EXACTLY — names
must match so VALIDATION.md test commands resolve):

`tests/ingestion/test_match_state.py`:
- `test_seq_id_strictly_monotonic` (xfail "Wave 1")
- `test_with_update_field_semantics` (xfail "Wave 1")

`tests/ingestion/test_match_state_jsonl.py`:
- `test_replay_determinism` (xfail "Wave 1")
- `test_commit_line_schema` (xfail "Wave 1")
- `test_quarantine_line_schema` (xfail "Wave 1")

`tests/ingestion/test_scoreboard.py`:
- `test_poller_emits_typed_events` (xfail "Wave 3B")
- `test_retry_honors_retry_after` (xfail "Wave 3B")

`tests/ingestion/test_ocr_score.py`:
- `test_decode_benchmark_p50` (xfail "Wave 3C")
- `test_decode_correctness` (xfail "Wave 3C")

`tests/ingestion/test_ocr_bomb.py`:
- `test_decode_benchmark_p50` (xfail "Wave 3C")
- `test_decode_correctness` (xfail "Wave 3C")

`tests/ingestion/test_ocr_round_end.py`:
- `test_decode_benchmark_p50` (xfail "Wave 3C")
- `test_decode_correctness` (xfail "Wave 3C")

`tests/ingestion/test_ocr_alive_widget.py`:
- `test_decode_benchmark_p50` (xfail "Wave 3C")
- `test_parse_failure_quarantine` (xfail "Wave 3C")

`tests/ingestion/test_text_listener.py`:
- `test_emits_typed_soft_events` (xfail "Wave 3D")
- `test_twitter_only_update_quarantined` (xfail "Wave 3D")
- `test_no_token_noop` (xfail "Wave 3D")

`tests/ingestion/test_arbiter.py`:
- `test_score_change_two_source_rule` (xfail "Wave 3A")
- `test_bomb_event_one_source_soft_commit` (xfail "Wave 3A")
- `test_round_end_one_source_soft_commit` (xfail "Wave 3A")
- `test_quarantine_jsonl_format` (xfail "Wave 3A")

`tests/ingestion/test_latency.py`:
- `test_six_stage_populated` (xfail "Wave 3A")

`tests/ingestion/test_e2e.py`:
- `test_e2e_latency_p50` (xfail "Wave 4")
- `test_bomb_detect_p50` (xfail "Wave 4")
- `test_post_plant_non_degenerate` (xfail "Wave 4")

`tests/pricing/test_round_conclusion_v2.py`:
- `test_post_plant_p_hierarchy` (xfail "Wave 2A")
- `test_from_json_rejects_v1` (xfail "Wave 2A")
- `test_between_round_p_returns_side_baseline` (xfail "Wave 2A")

`tests/pricing/test_live_theo_dispatch.py`:
- `test_dispatch_bomb_planted` (xfail "Wave 2A")
- `test_dispatch_between_round` (xfail "Wave 2A")

Each file's module docstring should cite the REQ-ID and the SPEC.md acceptance
criterion it implements (one-line). No imports at module top — keeps collection
clean while modules are unbuilt.
  </action>
  <verify>
    <automated>uv run pytest tests/ingestion/ tests/pricing/test_round_conclusion_v2.py tests/pricing/test_live_theo_dispatch.py -v --no-header 2>&1 | grep -E "XFAIL|XPASS|PASSED|ERROR" | head -50</automated>
  </verify>
  <done>
- All 13 RED-stub files exist.
- Each test function listed above resolves to an xfail outcome (NOT error / NOT pass).
- `uv run pytest tests/ -x` STILL passes (Phase 1 + Phase 2 regression GREEN; xfails don't fail CI).
- `uv run pytest tests/ingestion/ -x` reports only XFAILs (no ERRORs).
  </done>
</task>

</tasks>

<verification>
- All 9 new deps installed and importable.
- `[[tool.mypy.overrides]]` for `src.state.*` strict block exists in pyproject.toml.
- `tests/ingestion/` package exists with conftest + 11 RED-stub files + fixtures dir.
- `tests/pricing/` carries the 2 v2-surface RED-stub files.
- `.gitignore` excludes `data/event_log/`, `data/metrics/`, `data/ribgg_cache/`, `data/round_events_v2.sqlite`, `.claude-loop-output.tmp`.
- Phase 1 + Phase 2 regression suite: `uv run pytest tests/pricing/ tests/probe/ tests/calibration/ -x` GREEN.
</verification>

<success_criteria>
- `uv run pytest tests/ -x --no-cov` GREEN (xfails count as pass; no ERRORs).
- `uv run mypy src/state/` exits cleanly with the new strict override.
- All Wave 1+ executors can `from tests.ingestion.conftest import *` without `ModuleNotFoundError`.
- VALIDATION.md test commands resolve to a test function (currently xfail; Wave N task swaps stub for assertion).
</success_criteria>

<output>
After completion, create `.planning/phases/03-live-ingestion-layer/03-00-SUMMARY.md`
documenting:
- 9 new deps added (versions pinned per RESEARCH §"Standard Stack")
- 13 RED-stub test files created with test name → REQ-ID mapping
- mypy override location in pyproject.toml
- next-wave dependency: every Wave 1-4 task can land its `<automated>` verify by
  swapping the matching xfail-stub for real assertions
</output>
