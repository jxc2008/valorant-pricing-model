# Phase 03: Live Ingestion Layer — Pattern Map

**Mapped:** 2026-05-01
**Files analyzed:** 26 (15 new src/scripts/tests, 8 modified, 3 user-copied salvage stubs)
**Analogs found:** 22 / 26 (4 NEW with no in-repo analog: text_listener, ocr, download_models, types)
**Output target:** `.planning/phases/03-live-ingestion-layer/03-PATTERNS.md`

---

## File Classification

| New / Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/state/match_state.py` | model (frozen+slots dataclass) | transform (pure-functional) | `src/pricing/data.py:32-105` (Phase 1 `MatchState` + `TheoOutput`) | exact (move + extend) |
| `src/state/__init__.py` | package re-export | n/a | `src/pricing/__init__.py` | exact |
| `src/state/engine_driver.py` | service (queue consumer) | event-driven (queue→callable) | `src/pricing/live_theo.py:650-684` (`LiveTheoEngine` bundle) | role-match |
| `src/ingestion/scoreboard.py` | service (HTTP poller) | event-driven (5s cadence → emit) | `scripts/probe_round_events.py:84-141` (`HEADERS`, `_ribgg_wait`, `get_json`) | exact (port + async wrap) |
| `src/ingestion/ocr.py` | service (CPU worker) | streaming (frames → events) | NONE in-repo (port from `reference/vision_parser.py` after user-copy) | NONE — use RESEARCH §Pattern 2 |
| `src/ingestion/text_listener.py` | service (long-lived stream) | streaming (tweets → soft events) | NONE in-repo | NONE — use RESEARCH §Pattern 3 |
| `src/ingestion/arbiter.py` | service (sole-writer state mutator) | event-driven (deques → tick → commit) | `src/pricing/round_conclusion.py:220-294` (frozen-dataclass-with-mutable-dicts pattern) for state-holder mechanics; `scripts/probe_round_events.py:651-720` for orchestration loop | role-match |
| `src/ingestion/types.py` | model (typed dataclasses) | transform | `src/pricing/data.py` (`TheoOutput`, `MatchState`) + `src/pricing/round_conclusion.py:79-100` (`_Cell`) | exact (frozen+slots dataclass shape) |
| `src/ingestion/__init__.py` | package re-export | n/a | `src/pricing/__init__.py` | exact |
| `scripts/download_models.py` | utility (CLI artifact fetcher) | file-I/O (download + verify) | `scripts/probe_round_events.py:1-50, 122-141` (CLI shape + tenacity-wrapped `get_json`) | role-match |
| `tests/state/test_match_state.py` | test (property + unit) | n/a | `tests/pricing/test_dp.py:111-117` (hypothesis `@given` + `@settings(max_examples=N)`); `tests/pricing/test_live_theo.py:52-94` (frozen-dataclass shape tests) | exact |
| `tests/state/__init__.py` | empty marker | n/a | `tests/pricing/__init__.py` | exact |
| `tests/ingestion/test_scoreboard.py` | test (integration) | n/a | `tests/probe/test_endpoint_shapes.py:1-100` (fixture-driven shape tests); `tests/probe/conftest.py` (session-scoped JSON loaders) | exact |
| `tests/ingestion/test_ocr.py` | test (benchmark + unit) | n/a | NONE in-repo for benchmark; `tests/pricing/test_round_conclusion_loader.py:21-46` (skipif + hypothesis) for the model-file-present skip pattern | partial |
| `tests/ingestion/test_text_listener.py` | test (integration) | n/a | NONE in-repo (Twitter mocked); use `tests/probe/conftest.py` fixture-loading idiom | partial |
| `tests/ingestion/test_arbiter.py` | test (property over enumerated rules) | n/a | `tests/pricing/test_dp.py:111-164` (hypothesis property tests); `tests/pricing/test_round_conclusion_loader.py:25-45` (`@given` + `@settings(max_examples=200)`) | exact |
| `tests/ingestion/test_e2e.py` | test (integration / async) | n/a | NONE in-repo (no async tests yet) — RESEARCH §Code Examples "Synthetic E2E test scaffold" | NONE — use RESEARCH excerpt |
| `tests/ingestion/conftest.py` | fixture | n/a | `tests/probe/conftest.py:1-44` (session-scoped JSON loader pattern) | exact |
| `tests/ingestion/__init__.py` | empty marker | n/a | `tests/pricing/__init__.py` | exact |
| `reference/vlr_scraper.py` | salvage (read-only) | n/a | `reference/theo_engine.py` etc. (user-copy, then read-only) | exact convention |
| `reference/rib_scraper.py` | salvage (read-only) | n/a | same | exact convention |
| `reference/vision_parser.py` | salvage (read-only) | n/a | same | exact convention |
| `src/pricing/data.py` (MODIFIED) | model (re-export shim) | n/a | `src/pricing/__init__.py:16-19` (re-export-only module) | exact |
| `src/pricing/__init__.py` (MODIFIED) | package re-export | n/a | self (current shape preserved; re-export adjusted) | exact |
| `src/pricing/live_theo.py`, `dp.py`, `round_conclusion.py`, `round_types.py`, `economy.py` (MODIFIED) | model/service (import-rewrite only) | n/a | self (current import lines updated) | exact |
| `src/config/constants.py` (MODIFIED) | config (Final[T] constants) | n/a | `src/config/constants.py:177-238` (rib.gg + heartbeat constants block) | exact |
| `pyproject.toml` (MODIFIED) | config (deps + tool override) | n/a | `pyproject.toml:100-106` (existing `src.pricing.*` strict mypy override) | exact |

---

## Pattern Assignments

### `src/state/match_state.py` (model, transform)

**Analog:** `src/pricing/data.py` (move + extend per CONTEXT D-14 / SPEC REQ-match-state-engine).

**Imports pattern** (analog `src/pricing/data.py:18-25`):

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from src.config.constants import SHRINK_PRIOR
```

**Apply to new file:** mirror this exact block; replace `SHRINK_PRIOR` with no constants import (Phase 3 MatchState reads no constants). Add `from dataclasses import dataclass, field, replace` and `from typing import Self` (per RESEARCH Pattern 1 / Code Examples line 770-810).

**Frozen+slots dataclass pattern** (analog `src/pricing/data.py:59-105`):

```python
@dataclass(frozen=True, slots=True)
class MatchState:
    """Phase 1 stub MatchState. ... Fields (17 total): ..."""
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
    pistol_winner_a: dict[int, Optional[bool]]
    numerical_diff: int
    bomb_planted: bool
    side: str
    econ_bucket: str
```

**Apply to new file:** copy verbatim — these 17 fields stay in identical order at the top of the new class. Append the 8 Phase 3 fields below (per RESEARCH Code Examples line 793-804): `seq_id: int = 0`, `last_updated_ts: float = field(default_factory=time.time)`, `players_alive_a: int = 5`, `players_alive_b: int = 5`, `ults_a: int = 0`, `ults_b: int = 0`, `time_left_s: float = 100.0`, `econ_a: int = 0`, `econ_b: int = 0`. Preserve the exact `# noqa: UP045` comments (mypy + ruff already accept these).

**Mutator pattern** (NEW — no in-repo analog; lift from RESEARCH Pattern 1):

```python
def with_update(self, **diffs: Any) -> Self:
    diffs.pop("seq_id", None)
    diffs.pop("last_updated_ts", None)
    return replace(self, seq_id=self.seq_id + 1, last_updated_ts=time.time(), **diffs)
```

**Module-docstring pattern** (analog `src/pricing/data.py:1-16`):

```python
"""Phase 1 pricing data shapes: HalfRates, MatchState, TheoOutput.

Phase 1 owns the MatchState dataclass per D-14. Phase 3 (REQ-match-state-engine)
will move it to src/state/match_state.py and the orchestrator (live_theo.py)
will re-import from there. ...

Sources
-------
- prd.md §2 (TheoOutput contract) / §6 (state-only call surface)
- DEC-010 / DEC-012 / D-08 / D-09 / D-12 / D-14 / D-17 / D-18 / D-19
- 01-RESEARCH.md §10 (MatchState surface), Open Question 2 (HalfRates loader)
"""
```

**Apply to new file:** preserve the same docstring shape (purpose, source-list bullet block) but anchor the citations to Phase 3 artifacts: SPEC §1 / D-01 / D-02 / Phase 1 D-14 / 03-RESEARCH.md §Pattern 1 / Code Examples line 754-810.

---

### `src/state/__init__.py` (package re-export)

**Analog:** `src/pricing/__init__.py:1-19`.

**Excerpt (verbatim):**

```python
"""Pricing layer — DP, Bradley-Terry blend, round-conclusion lookup, live_theo.

This package is type-checked under `mypy --strict` (CON-mypy-strict-pricing).
...
"""

from src.pricing.data import HalfRates, MatchState, TheoOutput
from src.pricing.live_theo import LiveTheoEngine

__all__ = ["LiveTheoEngine", "TheoOutput", "MatchState", "HalfRates"]
```

**Apply to new file:** drop the existing 1-line docstring; replace with package-purpose docstring matching this shape. Re-export `MatchState` from `src.state.match_state`. Final form:

```python
"""State engine — versioned MatchState + JSONL event log (Phase 3).

This package is type-checked under `mypy --strict` (SPEC.constraints — extends
Phase 1's CON-mypy-strict-pricing scope from src/pricing/ to src/state/).
"""

from src.state.match_state import MatchState

__all__ = ["MatchState"]
```

(Engine driver's class is added to `__all__` only when `engine_driver.py` lands in the same plan.)

---

### `src/state/engine_driver.py` (service, event-driven)

**Analog:** `src/pricing/live_theo.py:650-684` (`LiveTheoEngine` bundle pattern).

**Bundle pattern** (analog lines 650-684):

```python
@dataclass(frozen=True)
class LiveTheoEngine:
    """Single canonical pricing entry point — bundle pattern per D-20.
    ...
    Usage:
        from src.pricing import LiveTheoEngine, HalfRates
        half_rates = HalfRates.from_json("data/half_win_rates.json")
        engine = LiveTheoEngine(half_rates)
        out = engine(state)  # state: MatchState
    """

    half_rates: HalfRates
    round_conclusion: Optional[RoundConclusionFn] = None  # noqa: UP045

    def __call__(self, state: MatchState) -> TheoOutput:
        from src.pricing import dp as _dp
        try:
            return _live_theo_impl(state, self.half_rates, self.round_conclusion)
        finally:
            _clear_pricing_caches()
            _dp._clear_pricing_caches()
```

**Apply to new file:** mirror the `@dataclass(frozen=True)` bundle holding the engine reference + the `asyncio.Queue`. Driver consumes `ConfirmedEvent`s from the queue (per CONTEXT integration_points line 151), calls `self.engine(state)` exactly via the locked Phase 1 D-20 surface — never widen the call signature. Use `try/finally` discipline for cleanup just like `LiveTheoEngine.__call__` line 680-684. Driver does NOT mutate state; it only reads the post-mutation state via the state-holder reference the arbiter writes to.

---

### `src/ingestion/scoreboard.py` (service, event-driven)

**Analog:** `scripts/probe_round_events.py` — Phase 2's verified rib.gg HTTP layer (per CONTEXT line 106 / RESEARCH §Don't Hand-Roll row "rib.gg HTTP layer").

**Imports pattern** (analog `scripts/probe_round_events.py:36-60`):

```python
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, TypedDict

import requests
from tenacity import RetryCallState, RetryError, retry, stop_after_attempt
from tqdm import tqdm

from src.config.constants import (
    MID_ROUND_HEARTBEAT_S,
    RIBGG_BASE_URL,
    RIBGG_RATE_LIMIT_RPS,
    RIBGG_RECENCY_MONTHS,
    RIBGG_TARGET_MATCH_COUNT,
    RIBGG_TIER_FILTER,
)
from src.pricing.economy import credits_to_bucket
```

**Apply to new file:** drop `argparse`, `sqlite3`, `sys`, `tqdm`, `Iterable`, `datetime` block (those are CLI/ETL-only). Keep `requests`, `tenacity`, `Final`, `TypedDict`. Add `import asyncio`, `from concurrent.futures import ThreadPoolExecutor` (RESEARCH Standard Stack tradeoff line 104: keep sync `requests.get` inside `loop.run_in_executor` rather than rewriting to aiohttp). Also import `from src.pricing.economy import credits_to_bucket` (CONTEXT line 128 — same canonical bucketing).

**HTTP HEADERS pattern** (analog `scripts/probe_round_events.py:84-94` — verbatim transplant):

```python
HEADERS: dict[str, str] = {
    "User-Agent": "Mozilla/5.0 (compatible; valorant-pricing-model/0.1; +github)",
    "Referer": "https://www.rib.gg/",
    # Disable urllib3's default keep-alive pooling. On Windows, pooled sockets
    # to be-prod.rib.gg go stale after the server closes them silently — next
    # `requests.get` reuses the dead socket and hangs at the 30s read timeout.
    # `Connection: close` makes the server close cleanly and prevents urllib3
    # from caching the socket. Costs ~0.2s extra TLS handshake per call (≈3 min
    # over a 1000-match scrape) for full reliability.
    "Connection": "close",
}
```

**Apply to new file:** copy verbatim (this is the proven Phase 2 pattern called out in CONTEXT line 76). Update the User-Agent comment to reference `live-ingestion-layer/0.3` if you want phase-tagging — keep `Connection: close`.

**Tenacity retry + Retry-After pattern** (analog `scripts/probe_round_events.py:102-135`, verbatim transplant):

```python
def _ribgg_wait(retry_state: RetryCallState) -> float:
    """Custom tenacity wait function honoring rib.gg's Retry-After header (W6).

    If the most recent attempt raised an HTTPError carrying a `Retry-After`
    header (typical 429/503 from Heroku-fronted APIs), wait that many seconds
    capped at 60. Otherwise fall through to exponential backoff
    (multiplier=1, max=30) — same shape as wait_exponential(multiplier=1, max=30).
    """
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        ra = exc.response.headers.get("Retry-After")
        if ra is not None:
            try:
                return min(float(ra), 60.0)
            except ValueError:
                pass
    attempt = retry_state.attempt_number
    return min(2.0 ** (attempt - 1), 30.0)


@retry(stop=stop_after_attempt(5), wait=_ribgg_wait)
def get_json(url: str) -> dict[str, Any]:
    """GET with tenacity retry. ..."""
    resp = requests.get(url, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    out: dict[str, Any] = resp.json()
    return out
```

**Apply to new file:** copy `_ribgg_wait` verbatim. For `get_json`, replace the cap of `30.0` in the fallback line `min(2.0 ** (attempt - 1), 30.0)` with a new constant `RIBGG_LIVE_BACKOFF_CAP_S = 10.0` per RESEARCH Pitfall 3 ("the live cap is 10s, not 60s"). This is the ONLY behavioral delta from Phase 2's batch resilience.

**Defensive null-roster pattern** (analog `scripts/probe_round_events.py:531-543`):

```python
# rib.gg sometimes returns match records with null rosters / null
# attackingFirstTeamNumber (cancelled, forfeited, or not-yet-played
# matches that still ship in the series payload). Skip them — the
# caller treats an empty yield as `matches_skipped_no_events`.
t1 = match_meta.get("team1PlayerIds")
t2 = match_meta.get("team2PlayerIds")
atk_first = match_meta.get("attackingFirstTeamNumber")
if not t1 or not t2 or atk_first is None:
    return
```

**Apply to new file:** mirror at the entry of the per-match parser. Live poller can simply emit no `ScoreEvent` and continue (no caller-side counter needed for Phase 3; surface a `ocr_dropped_frames_total`-style metric only if planner adds it).

**Event-shape parser** (analog uses `transform_match_to_rows`); for Phase 3 the live poller emits an `ArbiterPending` per RESEARCH §Pattern 4 (`signal_value=...`, `source="ribgg"`, `event_type="score_change"`, `t_observed=time.time()`, `t_ingested=time.monotonic_ns()`).

---

### `src/ingestion/arbiter.py` (service, event-driven)

**Analog (state-holder mechanics):** `src/pricing/round_conclusion.py:220-294` — frozen-dataclass-with-mutable-dicts pattern. Confirms that frozen=True does not block mutation of dict/deque field contents.

**Frozen + mutable-collection field pattern** (analog `src/pricing/round_conclusion.py:220-249`):

```python
@dataclass(frozen=True, slots=True)
class RoundConclusionLookup:
    """5-tier hierarchical fallback-chain lookup ...

    Why frozen=True with mutable dict fields: ``@dataclass(frozen=True)`` blocks
    reassignment of the field reference, NOT mutation of the dict object the
    field points to. The calibrator populates cells via
    ``lookup_obj.cells_full[key] = _Cell(...)``, which works on frozen instances.
    """
    cells_full: dict[tuple[int, bool, str, str, str], _Cell] = field(default_factory=dict)
    cells_no_econ: dict[tuple[int, bool, str, str], _Cell] = field(default_factory=dict)
    cells_no_map: dict[tuple[int, bool, str], _Cell] = field(default_factory=dict)
    cells_minimal: dict[tuple[int, bool], _Cell] = field(default_factory=dict)
    side_baseline: dict[str, float] = field(
        default_factory=lambda: {"atk": 0.5, "def": 0.5}
    )
```

**Apply to new file:** Arbiter is `frozen=False` (it owns mutable runtime state and an `asyncio.Lock`), but the same `field(default_factory=...)` discipline applies for its 5 deques. Use the ROUND_CONCLUSION docstring's "Why frozen with mutable fields" paragraph as the docstring template explaining "the deques are populated under `self._lock`; instances are not deepcopied".

**Core arbiter pattern** (NEW — lift from RESEARCH Pattern 4 / arbiter pseudocode RESEARCH lines 369-515):

```python
class Arbiter:
    def __init__(self, state_holder, queue: asyncio.Queue, jsonl_writer):
        self._state_holder = state_holder
        self._queue = queue
        self._jsonl = jsonl_writer
        self._lock = asyncio.Lock()
        self._score_changes: deque[ArbiterPending]    = deque()
        self._kill_events: deque[ArbiterPending]      = deque()
        self._bomb_events: deque[ArbiterPending]      = deque()
        self._numerical_flips: deque[ArbiterPending]  = deque()
        self._round_end_events: deque[ArbiterPending] = deque()
```

The five rule predicates (`_eval_score_rule`, `_eval_kill_rule`, etc.), `_evict`, `_commit`, `_quarantine`, and the 50ms `_tick_loop` come from RESEARCH lines 419-515 — copy that block as the implementation skeleton; the planner's WAVE-PLAN already lists each predicate as an individual task.

**Constants imported** (CRule 12) — every threshold goes through `src/config/constants.py`:

```python
from src.config.constants import (
    ARBITER_TICK_HZ,             # NEW — 20 (50ms tick)
    ARBITER_SCORE_WINDOW_S,      # NEW — 2.0 per DEC-006
    ARBITER_KILL_WINDOW_MS,      # NEW — 100
    ARBITER_BOMB_WINDOW_MS,      # NEW — 100
    ARBITER_NUMERICAL_WINDOW_MS, # NEW — 100
    ARBITER_ROUND_END_WINDOW_S,  # NEW — 5.0
)
```

---

### `src/ingestion/types.py` (model, transform)

**Analog:** `src/pricing/data.py:32-51` (`TheoOutput` frozen+slots) AND `src/pricing/round_conclusion.py:79-100` (`_Cell` frozen+slots).

**Frozen+slots dataclass pattern** (analog `src/pricing/data.py:32-51`):

```python
@dataclass(frozen=True, slots=True)
class TheoOutput:
    """Single canonical pricing output.

    Fields per PRD §2 contract:
        theo_series: P(team A wins the BO3 series), clipped ...
        theo_map: per-map P(team A wins map i) ...
        vega: ...
        confidence: ...
    """

    theo_series: float
    theo_map: tuple[float, ...]
    vega: float
    confidence: float
```

**Apply to new file:** create 4 frozen+slots dataclasses (`ArbiterPending`, `ConfirmedEvent`, `EventLogLine`, `MetricsLogLine`) using the exact same docstring/field-block shape. Field set per RESEARCH lines 386-548 — copy the typed declarations (with `Literal[...]` for the bounded enums on `source` and `event_type`) verbatim from the research excerpt. Mark the file with `from __future__ import annotations` and `from typing import Any, Literal, Optional` matching `src/pricing/data.py:18-23` import discipline.

---

### `src/ingestion/__init__.py` (package re-export)

**Analog:** `src/pricing/__init__.py`. Same shape as `src/state/__init__.py`. Initial Wave-0 form: empty docstring-only (existing `src/ingestion/__init__.py:1` already starts there). Re-exports added per-task as classes land: `Arbiter`, `ScoreboardPoller`, `OCRPipeline`, `ValorantTextListener`, `ArbiterPending`, `ConfirmedEvent`.

---

### `scripts/download_models.py` (utility, file-I/O)

**Analog:** `scripts/probe_round_events.py:1-50, 122-141` — file/CLI shape + tenacity-wrapped HTTP.

**Module-docstring + CLI shape** (analog `scripts/probe_round_events.py:1-34`):

```python
"""Phase 2 Wave 2: scrape rib.gg round events into data/round_events.sqlite.
...
CLI:
    python -m scripts.probe_round_events --dry-run                  # 5-series sample, no DB write
    python -m scripts.probe_round_events --live --out-db data/round_events.sqlite
    python -m scripts.probe_round_events --live --target 500        # quick floor

Sources
-------
- 02-RESEARCH.md §"Pattern 1" / ...
- CRule 13 (dry-run by default)
"""
```

**Apply to new file:** mirror docstring shape (Public API, CLI section, Sources section). CLI: `python -m scripts.download_models` downloads `models/en_PP-OCRv4_rec_infer.onnx` from the HuggingFace URL pinned in RESEARCH §Standard Stack ONNX row, verifies SHA-256 (URL: `https://huggingface.co/breezedeus/cnocr-ppocr-en_PP-OCRv4/resolve/main/en_PP-OCRv4_rec_infer.onnx`, 7.66 MB, Apache 2.0). Use the same `requests.get(..., headers=HEADERS, timeout=60)` shape as `get_json` line 132 — but with `stream=True` to write the binary in chunks.

**Tenacity retry pattern:** reuse `_ribgg_wait` if you promote it to `src/`, or duplicate inline; the cleaner option is to extract `_ribgg_wait` and `get_json` into `src/ingestion/_http.py` (planner decides — flagged in RESEARCH "Don't Hand-Roll" row 1).

---

### `tests/state/test_match_state.py` (test, property + unit)

**Analog (property tests):** `tests/pricing/test_dp.py:111-117` (hypothesis `@given` + `@settings(max_examples=N)`).

**Property test pattern** (analog lines 111-117):

```python
@given(p=st.floats(min_value=0.0, max_value=1.0, allow_nan=False))
@settings(max_examples=50, deadline=None)
def test_dp_value_in_unit_interval(p: float) -> None:
    """REQ-bo3-dp-engine acceptance: DP value in [0, 1] for any reachable state."""
    val = series_value(_root(), _ConstantRoundPFn(p))
    assert 0.0 <= val <= 1.0
    assert not math.isnan(val)
```

**Apply to new file:** for `test_seq_id_monotonic_1000_mutators` use `@given(diffs=st.lists(st.dictionaries(st.text(), st.integers()), min_size=1000, max_size=1000))` + `@settings(max_examples=20, deadline=None)` per RESEARCH Sampling Rate line 1114. For `test_with_update_strips_seq_id`: a unit test (no `@given`) — call `state.with_update(seq_id=999)` and assert the resulting state's `seq_id == state.seq_id + 1` (NOT 999).

**Frozen-dataclass shape test pattern** (analog `tests/pricing/test_live_theo.py:52-94`):

```python
def test_match_state_is_17_field_frozen_dataclass() -> None:
    """D-02 + D-17 + D-18 + D-19: 17 fields exactly. Frozen + slots."""
    assert dataclasses.is_dataclass(MatchState)
    fields = dataclasses.fields(MatchState)
    field_names = [f.name for f in fields]
    assert len(fields) == 17, f"expected 17 fields, got {len(fields)}: {field_names}"
    expected = {"match_id", "team_a", "team_b", ...}
    assert set(field_names) == expected
    # Forbidden Phase 3 fields:
    forbidden = {"seq_id", "last_updated_ts", "players_alive", "ults", "time_left_s"}
    assert not (forbidden & set(field_names)), (
        "Phase 3 fields leaked into Phase 1 stub MatchState"
    )
```

**Apply to new file:** rewrite to assert 25 fields (17 Phase 1 + 8 Phase 3) and that the 8 Phase 3 fields ARE present (the negative assertion above is now inverted). Keep the `dataclasses.is_dataclass(MatchState)` + `dataclasses.fields(MatchState)` introspection idiom.

---

### `tests/ingestion/test_scoreboard.py` (test, integration)

**Analog (fixture-driven shape tests):** `tests/probe/test_endpoint_shapes.py:1-100` + `tests/probe/conftest.py:1-44`.

**Session-scoped JSON fixture pattern** (analog `tests/probe/conftest.py:1-44`):

```python
"""Shared probe-test fixtures.

Loads recorded JSON fixtures from sibling `fixtures/` directory. NO live HTTP
in CI per 02-VALIDATION.md "Manual-Only Verifications" — live probe is opt-in
via Plan 02-03 manual checkpoint.

Sources
-------
- 02-VALIDATION.md (Wave 0: tests/probe/fixtures/match_details.json)
- 02-RESEARCH.md §"Pattern 1" (verified schema)
- src/pricing/data.py:128-144 (Path+json.loads encoding="utf-8" pattern)
"""

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
    """GET /v1/events response sample."""
    return _load("events_response.json")
```

**Apply to new file:** mirror `tests/probe/conftest.py` exactly into `tests/ingestion/conftest.py`. Reuse the SAME `events_response.json`, `series_response.json`, `match_details.json` files via a soft path: either symlink/copy under `tests/ingestion/fixtures/` OR re-import the existing fixtures via `pytest_plugins = ["tests.probe.conftest"]` at the top of `tests/ingestion/conftest.py` (cleaner; preserves CRule 1 single-source). Add new fixtures `fake_ocr_frame_source`, `fake_twitter_stream`, `mock_ribgg_response` as the file grows.

**Endpoint-shape pinning pattern** (analog `tests/probe/test_endpoint_shapes.py:25-43`):

```python
def test_events_response_top_level_shape(events_response: dict[str, Any]) -> None:
    """Top-level: {data: list, meta: {total: int}}."""
    assert "data" in events_response
    assert "meta" in events_response
    assert isinstance(events_response["data"], list)
    ...
```

**Apply to new file:** `test_scoreboard.py::test_resilience_patterns` does NOT need real HTTP — it monkeypatches `requests.get` (per SPEC REQ-scoreboard-polling acceptance) to return the fixtures, and asserts (a) `Connection: close` in headers, (b) tenacity retries on simulated 503, (c) `ScoreEvent`s emitted at the configured cadence (use `monkeypatch.setattr` on `time.sleep` or override the cadence constant to make tests fast).

---

### `tests/ingestion/test_arbiter.py` (test, property)

**Analog:** `tests/pricing/test_dp.py:111-164` (hypothesis property over enumerated states) + `tests/pricing/test_round_conclusion_loader.py:25-45` (`@given(numerical_diff=st.integers(...), bomb_planted=st.booleans(), side=st.sampled_from([...]), ...)` enumerated parametric).

**Enumerated property pattern** (analog `tests/pricing/test_round_conclusion_loader.py:25-45`):

```python
@given(
    numerical_diff=st.integers(min_value=-4, max_value=4),
    bomb_planted=st.booleans(),
    side=st.sampled_from(["atk", "def"]),
    econ_bucket=st.sampled_from(["full", "semi-buy", "semi-eco", "eco"]),
    map_name=st.sampled_from(["Lotus", "Bind", "Haven", ...]),
)
@settings(max_examples=200, deadline=None)
def test_loaded_lookup_returns_in_range(
    numerical_diff: int,
    bomb_planted: bool,
    side: str,
    econ_bucket: str,
    map_name: str,
) -> None:
    lookup = RoundConclusionLookup.from_json(MODEL_PATH)
    val = lookup.lookup(numerical_diff, bomb_planted, side, econ_bucket, map_name)
    assert 0.0 <= val <= 1.0
```

**Apply to new file:** for `test_rule_matrix` enumerate `(source, event_type) ∈ {ribgg, ocr, twitter} × {score_change, kill, bomb, numerical_flip, round_end}` (15 combos) per RESEARCH Sampling Rate line 1115; use `@settings(max_examples=100, deadline=None)`. For `test_score_change_window` use `@given(time_offset_s=st.floats(min_value=-3.0, max_value=3.0))` per RESEARCH line 1116. For `test_quarantine_log_shape` it's a unit test (one fixed input, one assertion against the JSONL line shape).

---

### `tests/ingestion/test_e2e.py` (test, integration)

**No in-repo analog** — there are no async tests in the repo today. Use RESEARCH §Code Examples "Synthetic E2E test scaffold" (RESEARCH lines 893-965) as the implementation template verbatim. Key call-outs from that excerpt:

- `@pytest.mark.asyncio` decorator on the test fn (RESEARCH line 916).
- `monkeypatch.setenv("TWITTER_BEARER_TOKEN", "")` to force the no-op listener path (RESEARCH line 918 — also REQ-text-listener acceptance line 96).
- `tmp_path` fixture for the JSONL output dir.
- `arbiter_task = asyncio.create_task(arbiter.run())` + `try/finally arbiter_task.cancel()` shape (RESEARCH lines 932-947).
- `latencies_ms.append((ce.t_state_committed - ce.t_ingested) * 1000)` → `assert statistics.median(latencies_ms) < 500.0` (RESEARCH lines 941, 958-960 — REQ-end-to-end-latency acceptance).
- Reload `LiveTheoEngine` on the final state to assert non-degenerate theo (RESEARCH lines 952-957).

---

### `src/config/constants.py` (MODIFIED — config)

**Analog (within-file pattern):** `src/config/constants.py:177-238` — the Phase 2 rib.gg constants block.

**Final[T] declaration pattern** (analog lines 180-186):

```python
RIBGG_BASE_URL: Final[str] = "https://be-prod.rib.gg/v1"
"""rib.gg internal API base URL (live-verified 2026-04-30 in 02-RESEARCH.md).

Source: 02-RESEARCH.md §"Pattern 1" / DEC-017. The 2022 `Traumist/RIB-Data-Scraper`
reference used `backend-prod.rib.gg`; the subdomain migrated to `be-prod.rib.gg`
sometime 2022-2026 (verified 200 OK in research session). Re-probe before scraping
if Phase 2 execution is delayed >30 days from research date.
"""
```

**Apply to file:** add a new Phase 3 section header (matching the existing `# Phase 2 — rib.gg probe ETL` divider on line 178). Add the 13 new constants per CONTEXT line 127 / RESEARCH §Pattern 4 enums + RESEARCH §Wave 0 Gaps line 1141. Each constant gets a `Final[T]` annotation, an inline triple-string docstring with `Source: ...` line citing 03-RESEARCH §Pattern 4 / D-04 / DEC-006, and ZERO inline literal usage at the call site (CRule 12).

**13 new constants (verbatim list from CONTEXT line 127):**
- `OCR_KILLFEED_CADENCE_MS`, `OCR_SCOREBOARD_CADENCE_MS`, `OCR_BOMB_CADENCE_MS`, `OCR_ROUNDEND_CADENCE_MS`
- `OCR_DECODE_BUDGET_MS`, `OCR_INFERENCE_BUDGET_MS`
- `ARBITER_TICK_HZ`, `ARBITER_SCORE_WINDOW_S`, `ARBITER_KILL_WINDOW_MS`
- `TWITTER_RULE_SET`, `TWITTER_API_BASE_URL`
- `EVENT_LOG_DIR`, `METRICS_LOG_DIR`

(RESEARCH Pattern 4 surfaces additional ones — `ARBITER_BOMB_WINDOW_MS`, `ARBITER_NUMERICAL_WINDOW_MS`, `ARBITER_ROUND_END_WINDOW_S`, `OCR_KILLFEED_CONF_THRESHOLD`, `RIBGG_LIVE_BACKOFF_CAP_S` per Pitfall 3, `OCR_BACKLOG_MAX` per Pitfall 6 — planner must consolidate the final list. Treat CONTEXT line 127's "13" as a floor, not a ceiling.)

---

### `pyproject.toml` (MODIFIED — config)

**Analog (within-file pattern):** existing `[[tool.mypy.overrides]]` block at lines 100-106.

**Strict-mypy override pattern** (analog `pyproject.toml:100-106`):

```toml
[[tool.mypy.overrides]]
# CON-mypy-strict-pricing: the math layer must type-check fully.
module = "src.pricing.*"
strict = true
disallow_any_explicit = false  # allow Any in narrow places if explicitly written
warn_return_any = true
```

**Apply to file:** add a sibling override block for `src.state.*` (per SPEC.constraints — `mypy --strict` extends to `src/state/`):

```toml
[[tool.mypy.overrides]]
# Phase 3 SPEC.constraints — extend strict from src/pricing/ to src/state/.
module = "src.state.*"
strict = true
disallow_any_explicit = false
warn_return_any = true
```

Plus a `[[tool.mypy.overrides]] module = ["pytesseract", "PIL.*"] ignore_missing_imports = true` block per RESEARCH lines 994-996.

**Dependencies pattern** (analog `pyproject.toml:10-14`):

```toml
dependencies = [
    "requests>=2.32",
    "tenacity>=8.5",
    "tqdm>=4.66",
]
```

**Apply to file:** append the 6 new deps per RESEARCH lines 970-976: `aiohttp>=3.10,<4`, `tweepy>=4.15,<5`, `onnxruntime>=1.20,<1.22`, `pytesseract>=0.3.13,<0.4`, `Pillow>=11,<13`, `numpy>=1.26,<3`. Append 2 dev deps per RESEARCH lines 980-982: `pytest-asyncio>=0.24,<2`, `pytest-benchmark>=4,<6`. Add `asyncio_mode = "auto"` under `[tool.pytest.ini_options]` per RESEARCH line 985 (and Pitfall on pytest-asyncio 1.0+ requirement, RESEARCH line 1003).

---

### `src/pricing/data.py`, `src/pricing/__init__.py`, `src/pricing/live_theo.py`, `dp.py`, `round_conclusion.py`, `round_types.py`, `economy.py` (MODIFIED — import-rewrite only)

**Analog:** the existing import lines themselves (Grep results above).

**Existing import sites needing rewrite:**

```python
# src/pricing/__init__.py:16
from src.pricing.data import HalfRates, MatchState, TheoOutput

# src/pricing/live_theo.py:42
from src.pricing.data import HalfRates, MatchState, TheoOutput

# src/pricing/round_types.py:55  (TYPE_CHECKING block)
from src.pricing.data import MatchState

# tests/pricing/test_live_theo.py:30
from src.pricing.data import HalfRates, MatchState, TheoOutput

# tests/pricing/test_live_theo_with_calibrated_round_conclusion.py:41
from src.pricing.data import HalfRates, MatchState, TheoOutput
```

**Two implementation choices** (CONTEXT integration_points line 147 makes both legal; planner picks):

**Option A — Re-export shim (zero-blast-radius):**

`src/pricing/data.py` keeps `HalfRates` + `TheoOutput` (those stay in pricing) and adds:

```python
from src.state.match_state import MatchState  # re-export for backwards compat
```

All existing import lines stay legal. NEW imports in `src/ingestion/` use `from src.state import MatchState`.

**Option B — Atomic deletion (cleaner, more grep-able):**

Delete `MatchState` from `src/pricing/data.py`. Rewrite all 5 import sites above to `from src.state.match_state import MatchState` (or `from src.state import MatchState`). One commit, one diff.

**Recommendation:** Option B (CONTEXT line 73 D-14 "atomic move (one plan), all Phase 1 imports updated together") + planner's "Atomic move ... (Re-export shim ... is OK; deletion is OK; mixing is not.)" line 1158 — pick one and do it cleanly.

In addition, `tests/pricing/test_round_types.py:300` has a string literal `"from src.pricing.data import MatchState"` used as a regression check on the module's text source. That assertion must be retargeted to `"from src.state.match_state import MatchState"` if Option B is chosen, or kept as-is under Option A.

---

## Shared Patterns

### Frozen+slots dataclass (applies to: `match_state.py`, `types.py`)

**Source:** `src/pricing/data.py:32-51` (TheoOutput) + `src/pricing/round_conclusion.py:79-100` (_Cell).

**Excerpt (verbatim):**

```python
@dataclass(frozen=True, slots=True)
class TheoOutput:
    """Single canonical pricing output. ..."""

    theo_series: float
    theo_map: tuple[float, ...]
    vega: float
    confidence: float
```

**Apply to:** every new typed shape in `src/state/` and `src/ingestion/types.py`. The `Arbiter` class itself is NOT frozen (it has runtime mutable state under a lock).

---

### Constants imported from `src/config/constants.py` only (CRule 12)

**Source:** `src/pricing/economy.py:24-28` shows the exact import shape.

**Excerpt (verbatim):**

```python
from src.config.constants import (
    ECON_BUCKET_FULL_FLOOR,
    ECON_BUCKET_SEMI_BUY_FLOOR,
    ECON_BUCKET_SEMI_ECO_FLOOR,
)
```

**Apply to:** every new file. NO inline literals for cadences, windows, budgets, URLs, rule sets, HUD bboxes, confidence thresholds, JSONL flush intervals, backoff caps. RESEARCH Pitfall 1 + Pitfall 2 + Pitfall 6 surface 5+ new candidates the planner must promote to constants.

---

### `__future__ annotations` + module-docstring with Sources block (applies to all new src/ + tests/ files)

**Source:** `src/pricing/data.py:1-25` and `src/pricing/live_theo.py:1-29`.

**Excerpt (verbatim, abridged):**

```python
"""Phase 1 pricing data shapes: HalfRates, MatchState, TheoOutput.

Phase 1 owns the MatchState dataclass per D-14. Phase 3 (REQ-match-state-engine)
will move it to src/state/match_state.py ...

Sources
-------
- prd.md §2 (TheoOutput contract) / §6 (state-only call surface)
- DEC-010 / DEC-012 / D-08 / D-09 / D-12 / D-14 / D-17 / D-18 / D-19
- 01-RESEARCH.md §10 (MatchState surface), Open Question 2 (HalfRates loader)
- reference/theo_engine.py:84-102 (Bayesian shrinkage salvage source)
"""

from __future__ import annotations
```

**Apply to:** every new file. Source-list must cite SPEC REQ-N, CONTEXT D-N, RESEARCH section, and the analog file (with line numbers) being mirrored. Tests cite their REQ-N and the analog test file. This is the project's discoverability discipline — do NOT skip the `Sources` block.

---

### `# noqa: UP045` retention for `Optional[T]` shapes used as dict keys / tuple keys

**Source:** `src/pricing/data.py:100-101`:

```python
map_winners: tuple[Optional[bool], ...]  # noqa: UP045 — Optional[bool] required for tuple keying
pistol_winner_a: dict[int, Optional[bool]]  # noqa: UP045 — Optional[bool] kept for clarity
```

**Apply to:** the `MatchState` move into `src/state/match_state.py` carries these `# noqa: UP045` comments unchanged. New code in `types.py` uses `Optional[T]` (with the same noqa) where a dataclass field is intentionally nullable (e.g., `seq_id: Optional[int]` for quarantined log lines per RESEARCH line 538).

---

### Salvage-via-`reference/`-then-port (applies to: `reference/vlr_scraper.py`, `reference/rib_scraper.py`, `reference/vision_parser.py`)

**Source:** `reference/theo_engine.py` etc. — all four existing salvage files are kept read-only and lifted into `src/pricing/` selectively (per CONTEXT line 136).

**Convention (verbatim from CONTEXT line 136):** "Phase 1 used this for `theo_engine.py` (read-only reference, code lifted into `src/pricing/round_conclusion.py:_Cell` etc). Phase 3 applies the same to `vlr_scraper.py` / `rib_scraper.py` / `vision_parser.py`."

**Apply to:** the user copies the three files into `reference/` first (per SPEC line 87 / CONTEXT lines 110-114). They are NOT edited — they ship verbatim under `reference/` (already in `pyproject.toml:39` ruff exclude block, already in `pyproject.toml:90-93` mypy exclude scope). The port lives in `src/ingestion/scoreboard.py` + `src/ingestion/ocr.py`, and applies the 8-item delta checklist in RESEARCH lines 583-606.

---

### Single-source canonical helper extraction (applies to: rib.gg HTTP, econ bucketing, future JSONL writer)

**Source:** `src/pricing/economy.py:1-7` docstring:

> "Shared between Phase 2 calibration ETL (`scripts/probe_round_events.py`) and Phase 3 live `MatchState.econ_bucket` derivation (REQ-match-state-engine). CRule 2 forbids two implementations of the same concept — this module is the canonical one. NEVER duplicate this logic elsewhere; always import."

**Apply to:** if `_ribgg_wait` + `get_json` are needed by both `scripts/probe_round_events.py` AND `src/ingestion/scoreboard.py`, promote them to `src/ingestion/_http.py` (or similar) and have BOTH call sites import. Same for the JSONL writer if `download_models.py` needs structured logging — share via `src/ingestion/event_log.py` (RESEARCH §Code Examples lines 814-889) or accept duplication if `download_models.py` only writes plain progress messages.

---

## No Analog Found

| File | Role | Data Flow | Reason | Mitigation |
|---|---|---|---|---|
| `src/ingestion/ocr.py` | service | streaming | No CV / OCR code in repo. | Use RESEARCH Pattern 2 + lines 277-300 (`run_ocr_frame`) verbatim as starter; port from `reference/vision_parser.py` after user-copy applying RESEARCH §Salvage-Port Delta lines 601-606 deltas. |
| `src/ingestion/text_listener.py` | service | streaming | No tweepy / async-streaming code in repo. | Use RESEARCH Pattern 3 lines 309-359 verbatim. |
| `tests/ingestion/test_e2e.py` | test (async) | n/a | No async tests in repo. | Use RESEARCH §Code Examples lines 893-965 verbatim as scaffold. Pyproject must add `asyncio_mode = "auto"` first (Wave 0). |
| `scripts/download_models.py` | utility (binary fetch + SHA-256) | file-I/O | No binary-download script in repo (Phase 2 only writes SQLite). | Reuse `scripts/probe_round_events.py:1-50` CLI shape and `:122-141` HTTP layer; add `hashlib.sha256()` chunked verify (stdlib). |

---

## Metadata

**Analog search scope:** `src/`, `scripts/`, `tests/`, `reference/`, `pyproject.toml`.
**Files scanned:** ~40 source files (full pricing layer, scripts, tests, config, reference, pyproject).
**Pattern extraction date:** 2026-05-01.
**Concrete excerpts:** every "Apply to new file" block above cites a file path + line range and is < 30 lines per excerpt (RESEARCH §Code Examples blocks are explicitly named where used in lieu of in-repo analogs).
