---
id: 03-01-shared-types-and-download
phase: 03
plan: 1
type: execute
wave: 1
depends_on:
  - 03-00-pyproject-and-constants
files_modified:
  - src/ingestion/types.py
  - src/state/__init__.py
  - src/ingestion/__init__.py
  - tests/state/__init__.py
  - tests/ingestion/__init__.py
  - tests/ingestion/conftest.py
  - tests/ingestion/fixtures/.gitkeep
  - scripts/download_models.py
  - tests/ingestion/test_download_models.py
autonomous: true
requirements:
  - REQ-cross-source-arbiter
  - REQ-latency-instrumentation
  - REQ-ocr-pipeline
user_setup: []
must_haves:
  truths:
    - "src/ingestion/types.py exports ArbiterPending, ConfirmedEvent, EventLogLine, MetricsLogLine — every other Phase 3 module imports from here (CRule 2 single-source)"
    - "All four types are @dataclass(frozen=True, slots=True) with Literal[...] enums on source and event_type for compile-time correctness"
    - "tests/ingestion/conftest.py re-uses tests/probe/conftest.py via pytest_plugins (no fixture duplication; CRule 2)"
    - "scripts/download_models.py downloads en_PP-OCRv4_rec_infer.onnx with SHA-256 verification before InferenceSession is ever instantiated (T-deser-01 mitigation)"
    - "Six-stage timestamps (t_observed, t_ingested, t_arbited, t_state_committed, t_theo_computed, t_quote_sent) declared on ConfirmedEvent + EventLogLine; t_theo_computed and t_quote_sent are Optional[float] for Phase 4 fill (D-02)"
    - "Quarantined log shape: seq_id=None, quarantined=True, fields_proposed populated, fields_changed empty (D-05)"
    - "ConfirmedEvent.is_soft: bool = False channel (BLOCKER-1) carries round_end soft-commit signal WITHOUT injecting underscore-prefixed sentinel keys into fields_changed; StateHolder.swap_with strips and rejects unknown keys before dataclasses.replace"
  artifacts:
    - path: src/ingestion/types.py
      provides: "ArbiterPending, ConfirmedEvent, EventLogLine, MetricsLogLine"
      contains: "@dataclass(frozen=True, slots=True)"
    - path: src/state/__init__.py
      provides: "package docstring; MatchState re-export added by 03-03"
    - path: src/ingestion/__init__.py
      provides: "package docstring; class re-exports added incrementally"
    - path: tests/ingestion/conftest.py
      provides: "fake_ocr_frame_source, fake_twitter_stream fixtures + reuse of tests/probe/conftest.py"
      contains: "pytest_plugins"
    - path: scripts/download_models.py
      provides: "ONNX model downloader with SHA-256 verify"
      contains: "hashlib.sha256"
    - path: tests/ingestion/test_download_models.py
      provides: "unit test for SHA-256 verify path"
  key_links:
    - from: "src/ingestion/arbiter.py"
      to: "src/ingestion/types.py"
      via: "from src.ingestion.types import ArbiterPending, ConfirmedEvent, EventLogLine"
      pattern: "from src\\.ingestion\\.types import"
    - from: "scripts/download_models.py"
      to: "models/en_PP-OCRv4_rec_infer.onnx"
      via: "requests.get + chunked write + hashlib.sha256().hexdigest() == pinned hash"
      pattern: "sha256.*hexdigest"
---

<objective>
Wave 0 infra plan #2 — declare the shared typed dataclasses every Phase 3 source/arbiter consumes (`ArbiterPending`, `ConfirmedEvent`, `EventLogLine`, `MetricsLogLine`), wire test infrastructure (`tests/ingestion/conftest.py` reusing Phase 2's probe fixtures), and ship the ONNX model downloader with SHA-256 verification.

Purpose: downstream plans build against these types directly — no scavenger hunt. The download script enables the kill-feed OCR plan (03-04) to call `onnxruntime.InferenceSession(...)` against a verified-integrity binary (T-deser-01 mitigation).

Output: `src/ingestion/types.py` (4 frozen+slots dataclasses), `src/state/__init__.py` (placeholder docstring; MatchState re-export added by 03-03), `src/ingestion/__init__.py` (placeholder docstring; classes re-exported as they land), `tests/ingestion/conftest.py` (fixtures + reuse of probe fixtures), `scripts/download_models.py` (downloader + verifier), one test for the verify path.
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
@tests/probe/conftest.py
@scripts/probe_round_events.py
@CLAUDE.md

<interfaces>
<!-- Frozen+slots dataclass analog from src/pricing/data.py:32-51 -->

```python
@dataclass(frozen=True, slots=True)
class TheoOutput:
    """Single canonical pricing output. ..."""
    theo_series: float
    theo_map: tuple[float, ...]
    vega: float
    confidence: float
```

<!-- Module docstring + Sources block analog from src/pricing/data.py:1-25 -->

```python
"""Phase 1 pricing data shapes: HalfRates, MatchState, TheoOutput. ...

Sources
-------
- prd.md §2 (TheoOutput contract) / §6 (state-only call surface)
- DEC-010 / DEC-012 / D-08 / D-09 / D-12 / D-14 / D-17 / D-18 / D-19
- 01-RESEARCH.md §10 (MatchState surface), Open Question 2 (HalfRates loader)
"""
from __future__ import annotations
```

<!-- Probe conftest pattern (analog for tests/ingestion/conftest.py) — tests/probe/conftest.py:1-44 -->

```python
"""Shared probe-test fixtures. ..."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
import pytest

FIXTURE_DIR: Path = Path(__file__).parent / "fixtures"

def _load(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))

@pytest.fixture(scope="session")
def events_response() -> dict[str, Any]:
    return _load("events_response.json")
```

<!-- Probe HTTP pattern (analog for download_models.py) — scripts/probe_round_events.py:84-135 -->

```python
HEADERS: dict[str, str] = {
    "User-Agent": "Mozilla/5.0 (compatible; valorant-pricing-model/0.1; +github)",
    "Referer": "https://www.rib.gg/",
    "Connection": "close",
}

@retry(stop=stop_after_attempt(5), wait=_ribgg_wait)
def get_json(url: str) -> dict[str, Any]:
    resp = requests.get(url, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    return resp.json()
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create src/ingestion/types.py with the 4 shared frozen dataclasses</name>
  <files>src/ingestion/types.py, src/ingestion/__init__.py, src/state/__init__.py, tests/ingestion/__init__.py, tests/state/__init__.py</files>
  <read_first>
    - src/pricing/data.py:1-105 (frozen+slots dataclass + module docstring + Sources block analog)
    - src/pricing/__init__.py:1-19 (package re-export analog)
    - .planning/phases/03-live-ingestion-layer/03-PATTERNS.md §src/ingestion/types.py block (lines 361-385)
    - .planning/phases/03-live-ingestion-layer/03-RESEARCH.md §Pattern 4 ArbiterPending+ConfirmedEvent shape (lines 386-401)
    - .planning/phases/03-live-ingestion-layer/03-RESEARCH.md §Pattern 5 EventLogLine shape (lines 528-548)
  </read_first>
  <action>
Create `src/ingestion/types.py` with this EXACT skeleton (every name/type pinned):

```python
"""Phase 3 ingestion-layer typed dataclasses.

Shared shapes consumed by:
  - src/ingestion/scoreboard.py (emits ArbiterPending source="ribgg")
  - src/ingestion/ocr.py (emits ArbiterPending source="ocr")
  - src/ingestion/text_listener.py (emits ArbiterPending source="twitter")
  - src/ingestion/arbiter.py (consumes ArbiterPending; emits ConfirmedEvent;
    writes EventLogLine + MetricsLogLine via the JSONL writer)
  - src/state/engine_driver.py (consumes ConfirmedEvent from asyncio.Queue)

Per CRule 2 (single canonical implementation) — every other Phase 3 module
imports from here; no duplicate dataclass shapes.

Six-stage timestamp lineage (REQ-latency-instrumentation):
  t_observed       wall-clock (time.time()) — needed for replay vs broadcast
  t_ingested       monotonic seconds — source-side ingestion (Phase 3)
  t_arbited        monotonic seconds — arbiter rule-fire (Phase 3)
  t_state_committed monotonic seconds — state.with_update returned (Phase 3)
  t_theo_computed  monotonic seconds — LiveTheoEngine returned (Phase 3 fills,
                   Phase 4 may override via second-line append per D-02)
  t_quote_sent     monotonic seconds — Kalshi order accepted (Phase 4 ONLY;
                   Phase 3 leaves None placeholder)

Sources
-------
- 03-SPEC.md §1-6 (REQ-cross-source-arbiter, REQ-latency-instrumentation)
- 03-CONTEXT.md D-02 (JSONL diff-only schema), D-04 (5-deque arbiter), D-05 (quarantine policy)
- 03-RESEARCH.md §Architecture Patterns Pattern 4 (ArbiterPending/ConfirmedEvent), Pattern 5 (EventLogLine)
- 03-PATTERNS.md §src/ingestion/types.py (lines 361-385)
- src/pricing/data.py:32-51 (frozen+slots dataclass shape analog)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Optional

# Bounded enums for compile-time correctness (D-04 5-deque alphabet).
SourceTag = Literal["ribgg", "ocr", "twitter"]
EventType = Literal["score_change", "kill", "bomb", "numerical_flip", "round_end"]


@dataclass(frozen=True, slots=True)
class ArbiterPending:
    """Source-emitted candidate event awaiting arbiter rule fire (D-04).

    Each source stamps `t_observed` (wall-clock) and `t_ingested`
    (monotonic seconds) at the moment of observation/parse. The arbiter
    deque holds these until rule predicates evaluate.
    """

    signal_value: dict[str, Any]
    source: SourceTag
    event_type: EventType
    t_observed: float       # wall-clock seconds since epoch
    t_ingested: float       # monotonic seconds


@dataclass(frozen=True, slots=True)
class ConfirmedEvent:
    """Arbiter-confirmed event ready for state mutation + queue dispatch (D-04).

    Built by Arbiter._commit() after a per-rule predicate fires. Carries the
    six-stage timestamp lineage; Phase 3 fills t_observed..t_theo_computed,
    Phase 4 fills t_quote_sent.
    """

    fields_changed: dict[str, Any]
    source_set: tuple[str, ...]      # which sources agreed (sorted)
    event_type: EventType
    t_observed: float                # min over inputs
    t_ingested: float                # min over inputs (monotonic seconds)
    t_arbited: float                 # arbiter tick monotonic seconds
    t_state_committed: Optional[float] = None  # filled post-state.with_update  # noqa: UP045
    t_theo_computed: Optional[float] = None    # filled by engine_driver        # noqa: UP045
    t_quote_sent: Optional[float] = None       # Phase 4 ONLY                   # noqa: UP045
    is_soft: bool = False                       # BLOCKER-1: round_end soft-commit channel
    confirmed_seq_id: Optional[int] = None     # set after state swap           # noqa: UP045


@dataclass(frozen=True, slots=True)
class EventLogLine:
    """JSONL event-log line shape (D-02 diff-only + D-05 quarantine in same file).

    Two shapes share one dataclass:
      Committed:  seq_id=int, quarantined=False, fields_changed populated,
                  fields_proposed=None, t_state_committed populated.
      Quarantined: seq_id=None, quarantined=True, quarantine_reason populated,
                  fields_proposed populated, fields_changed={}, t_state_committed=None.
    """

    seq_id: Optional[int]                # None for quarantined (D-05)          # noqa: UP045
    t_observed: float
    t_ingested: float
    t_arbited: float
    t_state_committed: Optional[float]   # None for quarantined                  # noqa: UP045
    t_theo_computed: Optional[float]     # filled by Phase 4 follow-up line      # noqa: UP045
    t_quote_sent: Optional[float]        # filled by Phase 4 follow-up line      # noqa: UP045
    source: str
    event_type: str
    fields_changed: dict[str, Any] = field(default_factory=dict)
    fields_proposed: Optional[dict[str, Any]] = None                              # noqa: UP045
    quarantined: bool = False
    quarantine_reason: Optional[str] = None                                       # noqa: UP045


@dataclass(frozen=True, slots=True)
class MetricsLogLine:
    """JSONL metrics-file line shape (REQ-latency-instrumentation).

    Written to data/metrics/{match_id}.metrics.jsonl in addition to the
    event log line. Phase 5 latency analysis consumes this file.
    """

    seq_id: int
    t_observed: float
    t_ingested: float
    t_arbited: float
    t_state_committed: float
    t_theo_computed: Optional[float] = None  # noqa: UP045
    t_quote_sent: Optional[float] = None     # noqa: UP045
    source: str = ""
    event_type: str = ""


__all__ = [
    "ArbiterPending",
    "ConfirmedEvent",
    "EventLogLine",
    "MetricsLogLine",
    "SourceTag",
    "EventType",
]
```

Then update the placeholder `__init__.py` files:

(b) `src/ingestion/__init__.py` — replace the existing 1-line docstring with:

```python
"""Ingestion layer — OCR, scoreboard polling, text listeners, cross-source arbiter (Phase 3).

Public surface added incrementally as wave-2/3 plans land. Wave 0 ships only
the typed shapes in `src.ingestion.types`. Mypy gradual per pyproject.toml
default scope; new code annotates fully.
"""

from src.ingestion.types import (
    ArbiterPending,
    ConfirmedEvent,
    EventLogLine,
    EventType,
    MetricsLogLine,
    SourceTag,
)

__all__ = [
    "ArbiterPending",
    "ConfirmedEvent",
    "EventLogLine",
    "EventType",
    "MetricsLogLine",
    "SourceTag",
]
```

(c) `src/state/__init__.py` — replace the existing docstring with:

```python
"""State engine — versioned MatchState + JSONL event log (Phase 3).

This package is type-checked under `mypy --strict` (SPEC.constraints — extends
Phase 1's CON-mypy-strict-pricing scope from src/pricing/ to src/state/).

Public surface (added by 03-03 atomic-move plan):
    MatchState  — frozen+slots dataclass with seq_id-bumping with_update mutator
"""

# Plan 03-03 adds: from src.state.match_state import MatchState
# (this file stays minimal until then so imports don't fail.)
```

(d) Create empty marker files:
- `tests/ingestion/__init__.py` — content: `"""Phase 3 ingestion-layer tests."""`
- `tests/state/__init__.py` — content: `"""Phase 3 state-engine tests."""`

`mypy --strict` MUST pass on `src/ingestion/types.py` AND `src/state/__init__.py` (the latter under the new strict override added by 03-00). Use `# noqa: UP045` on Optional[T] fields per the existing project precedent (`src/pricing/data.py:100-101`).
  </action>
  <verify>
    <automated>python -c "from src.ingestion.types import ArbiterPending, ConfirmedEvent, EventLogLine, MetricsLogLine, SourceTag, EventType; from src.ingestion import ArbiterPending as A; assert A is ArbiterPending; print('types ok')" &amp;&amp; mypy --strict src/state/ &amp;&amp; mypy src/ingestion/types.py &amp;&amp; ruff check src/ingestion/types.py src/ingestion/__init__.py src/state/__init__.py</automated>
  </verify>
  <done>src/ingestion/types.py exports the 4 dataclasses + 2 type aliases; src/ingestion/__init__.py re-exports them; src/state/__init__.py has the package docstring; both tests/__init__ files exist; `mypy --strict src/state/` clean; `mypy src/ingestion/types.py` clean (gradual scope).</done>
</task>

<task type="auto">
  <name>Task 2: Create tests/ingestion/conftest.py reusing Phase 2 fixtures + new ingestion fixtures</name>
  <files>tests/ingestion/conftest.py, tests/ingestion/fixtures/.gitkeep</files>
  <read_first>
    - tests/probe/conftest.py (entire file — 45 lines; verbatim analog)
    - tests/probe/fixtures/ (verify events_response.json, series_response.json, match_details.json present)
    - .planning/phases/03-live-ingestion-layer/03-PATTERNS.md §tests/ingestion/test_scoreboard.py + conftest reuse (lines 462-516)
    - .planning/phases/03-live-ingestion-layer/03-VALIDATION.md (Wave 0 conftest fixture list — lines 81)
  </read_first>
  <action>
Create `tests/ingestion/conftest.py`:

```python
"""Shared Phase 3 ingestion-test fixtures.

Reuses Phase 2 probe fixtures (events_response, series_response, match_details)
via pytest_plugins to avoid duplicating the JSON files (CRule 2). Adds new
fixtures for OCR + Twitter mocks needed by the Wave-2 source plans.

Sources
-------
- 03-VALIDATION.md Wave 0 Requirements (lines 81-82)
- 03-PATTERNS.md §tests/ingestion/test_scoreboard.py — fixture-reuse approach (lines 503-504)
- tests/probe/conftest.py:1-44 (verbatim analog for the loader idiom)
- src/ingestion/types.py (ArbiterPending shape consumed by fakes)
"""
from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any

import pytest

# Re-use Phase 2 probe fixtures (events_response, series_response, match_details)
# without duplicating the JSON files. CRule 2: single source per concept.
pytest_plugins = ["tests.probe.conftest"]

INGESTION_FIXTURE_DIR: Path = Path(__file__).parent / "fixtures"


@pytest.fixture
def fake_ocr_frame_source() -> Callable[[str, int], list[dict[str, Any]]]:
    """Yields synthetic OCR-detection results for a given target + frame count.

    Returns a function: (target, n_frames) -> list of dicts shaped like
    OCR worker output (signal_value, confidence). The OCR pipeline plan
    (03-04) consumes these in unit tests so it never needs a real frame.
    """

    def _factory(target: str, n_frames: int) -> list[dict[str, Any]]:
        # Mock kill-feed events with diff numerical_diff values.
        out: list[dict[str, Any]] = []
        for i in range(n_frames):
            out.append({
                "target": target,
                "signal_value": {"numerical_diff": i % 5 - 2},  # oscillates
                "confidence": 0.85,                              # above threshold
                "t_observed": time.time(),
                "t_ingested": time.monotonic(),
            })
        return out

    return _factory


@pytest.fixture
def fake_twitter_stream() -> Callable[[list[dict[str, Any]]], AsyncIterator[dict[str, Any]]]:
    """Yields a canned async-iterator of mock-tweet dicts for the listener test.

    Used by tests/ingestion/test_text_listener.py to exercise the on_tweet
    path without a real Twitter v2 connection. Free/Basic tier is retired
    (RESEARCH §State of the Art) so CI cannot exercise live Twitter; this
    fixture is the entire test surface for that REQ.
    """

    def _factory(tweets: list[dict[str, Any]]) -> AsyncIterator[dict[str, Any]]:
        async def _agen() -> AsyncIterator[dict[str, Any]]:
            for t in tweets:
                yield t
                await asyncio.sleep(0)
        return _agen()

    return _factory


@pytest.fixture
def mock_ribgg_response(match_details: dict[str, Any]) -> Callable[[str], dict[str, Any]]:
    """Maps URL substring -> Phase 2 fixture JSON for the rib.gg poller test.

    The scoreboard plan (03-04 in the wave order; concretely 03-04-scoreboard)
    monkeypatches `requests.get` to call this fixture for each URL it would
    hit live. Re-uses Phase 2's match_details payload to keep the schema
    shape Phase 2 verified.
    """

    def _by_url(url: str) -> dict[str, Any]:
        if "matches/" in url and "/details" in url:
            return match_details
        # Default empty payload for any unknown URL the test wires up.
        return {"data": [], "meta": {"total": 0}}

    return _by_url
```

Also create `tests/ingestion/fixtures/.gitkeep`:
```
# Phase 3 ingestion-test fixtures. Most fixtures reuse tests/probe/fixtures/
# via pytest_plugins (see ../conftest.py). This dir holds:
#   - canned_kill_feed_frames/ (PNGs added by 03-04 OCR plan for the A3 accuracy probe)
```

The `pytest_plugins` line in conftest.py is the canonical way to chain conftests in pytest >= 7; it avoids `import` errors that would arise from a relative import. Verify by running `pytest --collect-only tests/ingestion/` and confirming `events_response`, `series_response`, `match_details` show up as available fixtures alongside the new ones.
  </action>
  <verify>
    <automated>test -f tests/ingestion/conftest.py &amp;&amp; test -f tests/ingestion/fixtures/.gitkeep &amp;&amp; python -c "import sys; sys.path.insert(0, '.'); from tests.ingestion import conftest; print('conftest importable')" &amp;&amp; pytest --collect-only tests/ingestion/ --quiet 2>&amp;1 | head -20</automated>
  </verify>
  <done>tests/ingestion/conftest.py exists; pytest_plugins references tests.probe.conftest; 3 new fixtures (`fake_ocr_frame_source`, `fake_twitter_stream`, `mock_ribgg_response`) declared; tests/ingestion/fixtures/.gitkeep exists; pytest collects from tests/ingestion/ without error.</done>
</task>

<task type="auto">
  <name>Task 3: Create scripts/download_models.py with SHA-256 verification + a unit test</name>
  <files>scripts/download_models.py, tests/ingestion/test_download_models.py</files>
  <read_first>
    - scripts/probe_round_events.py:1-50 (CLI shape + module-docstring analog)
    - scripts/probe_round_events.py:84-141 (HEADERS + tenacity retry + get_json analog)
    - .planning/phases/03-live-ingestion-layer/03-PATTERNS.md §scripts/download_models.py block (lines 396-419)
    - .planning/phases/03-live-ingestion-layer/03-RESEARCH.md §Standard Stack ONNX row (lines 91, 1064-1065 — pinned URL + size + hash provenance)
    - .planning/phases/03-live-ingestion-layer/03-RESEARCH.md §Sources Primary lines 1163-1166 (HuggingFace URL + size verified live)
  </read_first>
  <action>
Create `scripts/download_models.py`:

```python
"""Phase 3 Wave 0: download + verify the kill-feed OCR ONNX checkpoint.

The kill-feed text-recognition CNN is downloaded from HuggingFace (NOT
committed to git per .gitignore models/*.onnx) and SHA-256-verified before
src/ingestion/ocr.py ever calls onnxruntime.InferenceSession() against it
(T-deser-01 mitigation: never deserialize an unverified model file).

Public API
----------
    python -m scripts.download_models
        Downloads en_PP-OCRv4_rec_infer.onnx to models/ and verifies SHA-256.
        Idempotent: if models/en_PP-OCRv4_rec_infer.onnx exists AND its SHA-256
        matches the pinned hash, returns 0 without re-downloading.
    python -m scripts.download_models --force
        Re-downloads even if the file exists.
    python -m scripts.download_models --check-only
        Verifies an existing download; exits 1 if missing or hash mismatch.
        Used by CI before OCR tests run.

Sources
-------
- 03-RESEARCH.md §Standard Stack ONNX row (lines 91, 1064-1065)
- 03-RESEARCH.md §Sources Primary HuggingFace URL (line 1165)
- 03-CONTEXT.md D-03 (OCR backend strategy — hybrid ONNX + tesseract)
- scripts/probe_round_events.py:1-50, 84-141 (module-docstring + HEADERS + tenacity-wrapped HTTP analogs)
- T-deser-01 in 03-orchestrator security_threat_model (verify hash before InferenceSession)
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path
from typing import Final

import requests
from tenacity import RetryCallState, retry, stop_after_attempt

MODEL_URL: Final[str] = (
    "https://huggingface.co/breezedeus/cnocr-ppocr-en_PP-OCRv4/"
    "resolve/main/en_PP-OCRv4_rec_infer.onnx"
)
"""HuggingFace download URL for the kill-feed ONNX checkpoint.

Source: 03-RESEARCH.md §Sources Primary line 1165 (verified live 2026-05-01,
7.66 MB, Apache 2.0). Re-verify URL resolves with `curl -I` if execution is
delayed >30 days from research date.
"""

MODEL_PATH: Final[Path] = Path("models") / "en_PP-OCRv4_rec_infer.onnx"
"""Local destination — gitignored via .gitignore models/*.onnx (Phase 3 block)."""

# SHA-256 of the upstream ONNX file. Pinned at first successful download
# (operator runs `python -m scripts.download_models` once, captures the
# printed hash, edits this constant). Subsequent runs verify against this
# value; mismatch implies upstream changed (re-pin only after auditing the
# diff). Initial value: empty placeholder triggers EXPECTED_HASH_UNPINNED
# behaviour on first run — script prints the observed hash and exits 1
# instructing the operator to update this constant.
EXPECTED_SHA256: Final[str] = ""

DOWNLOAD_CHUNK_BYTES: Final[int] = 1 << 16  # 64 KB; matches JSONL writer pattern
HTTP_TIMEOUT_S: Final[int] = 60
EXPECTED_SIZE_BYTES_MIN: Final[int] = 7_000_000   # 7.66 MB upstream; floor for sanity check
EXPECTED_SIZE_BYTES_MAX: Final[int] = 9_000_000

HEADERS: Final[dict[str, str]] = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; valorant-pricing-model/0.3 download_models; +github)"
    ),
    "Connection": "close",
}


def _wait_exp(retry_state: RetryCallState) -> float:
    """Tenacity exponential wait, capped at 30s. No Retry-After honoring needed
    for HuggingFace static asset; pattern mirrors scripts/probe_round_events.py."""
    attempt = retry_state.attempt_number
    return min(2.0 ** (attempt - 1), 30.0)


@retry(stop=stop_after_attempt(5), wait=_wait_exp)
def _download(url: str, dest: Path) -> int:
    """Stream-download to dest, returning bytes written. Retries 5x with
    exponential backoff on transient errors (HTTPError, ConnectionError)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with requests.get(url, headers=HEADERS, timeout=HTTP_TIMEOUT_S, stream=True) as resp:
        resp.raise_for_status()
        with dest.open("wb") as fh:
            for chunk in resp.iter_content(chunk_size=DOWNLOAD_CHUNK_BYTES):
                if not chunk:
                    continue
                fh.write(chunk)
                written += len(chunk)
    return written


def compute_sha256(path: Path) -> str:
    """Compute SHA-256 of `path` in chunks; returns hex digest.

    Stdlib only; no third-party hashing dep. Chunk size matches downloader.
    """
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(DOWNLOAD_CHUNK_BYTES)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def verify(path: Path, expected_hash: str) -> tuple[bool, str]:
    """Returns (ok, observed_hash). ok=False if path missing OR hash mismatch."""
    if not path.exists():
        return False, ""
    observed = compute_sha256(path)
    if not expected_hash:
        # Pin not yet captured — return observed for operator to copy into EXPECTED_SHA256.
        return False, observed
    return (observed == expected_hash), observed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0] if __doc__ else "")
    parser.add_argument("--force", action="store_true", help="re-download even if file exists")
    parser.add_argument("--check-only", action="store_true", help="verify-only; exit 1 on mismatch")
    args = parser.parse_args(argv)

    if args.check_only:
        ok, observed = verify(MODEL_PATH, EXPECTED_SHA256)
        if not ok:
            print(
                f"[check-only] FAIL: expected={EXPECTED_SHA256!r} observed={observed!r} "
                f"path={MODEL_PATH}",
                file=sys.stderr,
            )
            return 1
        print(f"[check-only] OK: {MODEL_PATH} sha256={observed}")
        return 0

    # Idempotent download path.
    if MODEL_PATH.exists() and not args.force:
        ok, observed = verify(MODEL_PATH, EXPECTED_SHA256)
        if ok:
            print(f"[download] up-to-date: {MODEL_PATH} sha256={observed}")
            return 0
        if not EXPECTED_SHA256:
            print(
                f"[download] file exists but EXPECTED_SHA256 is unpinned. "
                f"Observed sha256={observed}. Update EXPECTED_SHA256 in this script.",
                file=sys.stderr,
            )
            return 1
        print(
            f"[download] hash mismatch (expected={EXPECTED_SHA256} observed={observed}); "
            f"re-downloading",
            file=sys.stderr,
        )

    print(f"[download] fetching {MODEL_URL}")
    written = _download(MODEL_URL, MODEL_PATH)
    print(f"[download] wrote {written} bytes -> {MODEL_PATH}")
    if not (EXPECTED_SIZE_BYTES_MIN <= written <= EXPECTED_SIZE_BYTES_MAX):
        print(
            f"[download] size sanity check FAIL: {written} bytes outside "
            f"[{EXPECTED_SIZE_BYTES_MIN},{EXPECTED_SIZE_BYTES_MAX}]",
            file=sys.stderr,
        )
        return 1
    observed = compute_sha256(MODEL_PATH)
    if not EXPECTED_SHA256:
        print(
            f"[download] EXPECTED_SHA256 is unpinned. Observed sha256={observed}. "
            f"Update the EXPECTED_SHA256 constant in scripts/download_models.py to lock the pin.",
            file=sys.stderr,
        )
        return 1
    if observed != EXPECTED_SHA256:
        print(
            f"[download] hash MISMATCH after download: expected={EXPECTED_SHA256} "
            f"observed={observed}. Refusing to leave a corrupt file in place.",
            file=sys.stderr,
        )
        MODEL_PATH.unlink(missing_ok=True)
        return 1
    print(f"[download] verified sha256={observed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Then create `tests/ingestion/test_download_models.py`:

```python
"""Tests for scripts/download_models.py SHA-256 verification path.

The download itself is NOT exercised in CI (network + 7.66 MB binary).
These tests cover the SHA-256 + size sanity logic against synthetic
local files so the verify path is provably correct before the operator
runs the real download.

Sources
-------
- scripts/download_models.py (module under test)
- 03-VALIDATION.md Wave 0 download script row
- T-deser-01 (security_threat_model)
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from scripts.download_models import (
    DOWNLOAD_CHUNK_BYTES,
    EXPECTED_SHA256,
    compute_sha256,
    verify,
)


def test_compute_sha256_known_input(tmp_path: Path) -> None:
    """SHA-256 of b'hello' is the documented constant."""
    p = tmp_path / "x.bin"
    p.write_bytes(b"hello")
    assert compute_sha256(p) == hashlib.sha256(b"hello").hexdigest()


def test_compute_sha256_chunk_boundary(tmp_path: Path) -> None:
    """SHA-256 over a payload >2 chunks matches stdlib oneshot — confirms the
    chunked loop in compute_sha256 doesn't drop or double-count bytes."""
    p = tmp_path / "x.bin"
    payload = b"A" * (DOWNLOAD_CHUNK_BYTES * 2 + 7)
    p.write_bytes(payload)
    assert compute_sha256(p) == hashlib.sha256(payload).hexdigest()


def test_verify_missing_file_returns_false(tmp_path: Path) -> None:
    """verify() on a non-existent path returns (False, '') — never raises."""
    ok, observed = verify(tmp_path / "nope.onnx", "deadbeef")
    assert ok is False
    assert observed == ""


def test_verify_mismatch_returns_false_with_observed(tmp_path: Path) -> None:
    """verify() returns (False, observed_hash) when hashes don't match."""
    p = tmp_path / "x.bin"
    p.write_bytes(b"some content")
    ok, observed = verify(p, "deadbeef" * 8)  # 64 chars, but wrong
    assert ok is False
    assert observed == hashlib.sha256(b"some content").hexdigest()


def test_verify_match_returns_true(tmp_path: Path) -> None:
    """verify() returns (True, hash) when hashes match exactly."""
    p = tmp_path / "x.bin"
    p.write_bytes(b"some content")
    actual = hashlib.sha256(b"some content").hexdigest()
    ok, observed = verify(p, actual)
    assert ok is True
    assert observed == actual


def test_verify_unpinned_hash_returns_false(tmp_path: Path) -> None:
    """When EXPECTED_SHA256 is empty (initial pin state), verify returns
    (False, observed) so the operator can copy the observed hash into the
    EXPECTED_SHA256 constant."""
    p = tmp_path / "x.bin"
    p.write_bytes(b"first download")
    ok, observed = verify(p, "")  # empty pin
    assert ok is False
    assert observed == hashlib.sha256(b"first download").hexdigest()


def test_expected_sha256_constant_is_string() -> None:
    """EXPECTED_SHA256 must be a string (possibly empty for initial pin state).
    Catches accidental int/None typing."""
    assert isinstance(EXPECTED_SHA256, str)
```
  </action>
  <verify>
    <automated>test -f scripts/download_models.py &amp;&amp; test -f tests/ingestion/test_download_models.py &amp;&amp; python -m scripts.download_models --help &amp;&amp; pytest tests/ingestion/test_download_models.py -x</automated>
  </verify>
  <done>scripts/download_models.py exists with --help working; SHA-256 + size sanity checks present; EXPECTED_SHA256 placeholder pin captured in code with the operator-pin documentation; 6 unit tests in tests/ingestion/test_download_models.py all PASS without network; ruff + mypy gradual on the script clean.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| HuggingFace HTTP -> filesystem | `scripts/download_models.py` writes `models/en_PP-OCRv4_rec_infer.onnx`; the file later gets deserialized by `onnxruntime.InferenceSession()` in 03-04. |
| pytest -> conftest plugin chain | `pytest_plugins = ["tests.probe.conftest"]` imports the probe conftest module at collection time. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-03-01-01 (covers T-deser-01) | T (Tampering) | `models/en_PP-OCRv4_rec_infer.onnx` | mitigate | `scripts/download_models.py` SHA-256-verifies the binary against `EXPECTED_SHA256` BEFORE returning success; size sanity check rejects payloads outside [7MB, 9MB]; on hash mismatch the script DELETES the file (`MODEL_PATH.unlink(missing_ok=True)`) so 03-04 cannot accidentally load a corrupt model. Initial pin operator-captured on first run. |
| T-03-01-02 | T (Tampering) | HuggingFace download URL | mitigate | URL pinned in `MODEL_URL` constant; HTTPS-only (HuggingFace strict-transport); tenacity retry uses exponential backoff (no plaintext fallback). User-Agent identifies the project for upstream rate-limit attribution. |
| T-03-01-03 | I (Information disclosure) | `tests/ingestion/conftest.py` | accept | Fixtures synthesize fake data; no real Twitter tokens or match data is ever loaded. The `pytest_plugins` re-export of `tests.probe.conftest` only loads JSON fixtures already in the repo. |
| T-03-01-04 | E (Elevation of privilege) | `python -m scripts.download_models` | accept | Script runs with the operator's filesystem privileges; it writes to `models/` (relative path), so even hostile input from `MODEL_URL` cannot escape the working directory. Path is hard-coded; no user-supplied path. |
| T-03-01-05 | D (Denial of service) | tenacity retry loop | mitigate | `stop_after_attempt(5)` + exponential backoff capped at 30s prevents infinite-loop DoS against HuggingFace. |
</threat_model>

<verification>
- `python -c "from src.ingestion.types import ArbiterPending, ConfirmedEvent, EventLogLine, MetricsLogLine"` returns 0.
- `mypy --strict src/state/` clean (the new strict override block from 03-00 must be honored).
- `mypy src/ingestion/types.py` clean (gradual scope but the file annotates fully).
- `pytest tests/ingestion/test_download_models.py -x` PASSES (6 unit tests).
- `pytest --collect-only tests/ingestion/` lists `events_response`, `series_response`, `match_details`, `fake_ocr_frame_source`, `fake_twitter_stream`, `mock_ribgg_response` as available fixtures.
- `python -m scripts.download_models --help` exits 0.
- `python -m scripts.download_models --check-only` exits 1 with a clear `[check-only] FAIL` message (the file isn't downloaded yet — expected).
- All Phase 1 + 2 tests still GREEN: `pytest tests/ -x -k "not benchmark and not e2e"` PASSES.
</verification>

<success_criteria>
Wave 0 infra-2 plan is COMPLETE when:

1. `src/ingestion/types.py` exports the 4 frozen+slots dataclasses (`ArbiterPending`, `ConfirmedEvent`, `EventLogLine`, `MetricsLogLine`) plus 2 type aliases (`SourceTag`, `EventType`); `__init__.py` re-exports them.
2. `src/state/__init__.py` has the package docstring; mypy --strict src/state/ is clean.
3. `tests/ingestion/__init__.py` and `tests/state/__init__.py` exist as marker files.
4. `tests/ingestion/conftest.py` chains `tests.probe.conftest` via `pytest_plugins` (CRule 2: no fixture duplication) and exposes 3 new fixtures.
5. `scripts/download_models.py` has CLI (`--force`, `--check-only`), SHA-256 verify, size sanity check, hash-mismatch deletes the file, and a documented "initial pin" path that prints the observed hash for the operator to capture.
6. `tests/ingestion/test_download_models.py` has 6 unit tests covering the verify path; ALL PASS without network.
7. Phase 1 + 2 regression: `pytest tests/ -x -k "not benchmark and not e2e"` GREEN.
</success_criteria>

<output>
After completion, create `.planning/phases/03-live-ingestion-layer/03-01-SUMMARY.md` documenting the new types' field-by-field shape and the SHA-256 pin status (likely `EXPECTED_SHA256 = ""` until operator runs the download).
</output>
