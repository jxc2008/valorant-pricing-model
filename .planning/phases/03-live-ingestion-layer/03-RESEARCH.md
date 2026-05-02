# Phase 03: Live Ingestion Layer — Research

**Researched:** 2026-05-01
**Domain:** Real-time multi-source ingestion (rib.gg HTTP poller + OCR + Twitter v2 streaming) → arbited MatchState mutations → JSONL event log + six-stage latency lineage, all driven by a single asyncio loop on Windows 11 / Python 3.11
**Confidence:** HIGH on stack pins (verified live against PyPI + HuggingFace), MEDIUM on Twitter API tier limits (X has been rate-limit-evasive about exact tier numbers), HIGH on salvage-port deltas (codebase precedent is unambiguous), HIGH on arbiter mechanics + JSONL schema (decisions are locked, only mechanics need pinning)

## Summary

Phase 03 is plumbing-heavy but each leg has a canonical shape:

1. **MatchState** stays frozen+slots; the mutator is `state.with_update(**diffs) → new state` via `dataclasses.replace`. Atomic move from `src/pricing/data.py` to `src/state/match_state.py` is one commit; eight Phase 1 import sites rewrite cleanly. JSONL append is 30k events × ~250 bytes = ~7 MB/match, well within stdlib `json.dumps` + buffered `open(..., "a", buffering=1<<16)` speed envelope (no orjson needed; do NOT introduce a non-stdlib JSON dep just for this).
2. **OCR stack** = `onnxruntime==1.20.x` CPU + `breezedeus/cnocr-ppocr-en_PP-OCRv4/en_PP-OCRv4_rec_infer.onnx` (7.66 MB, Apache 2.0) for the kill-feed; `pytesseract==0.3.13` against the already-installed Tesseract 5.5.0 at `C:\Program Files\Tesseract-OCR\` for the other three targets. ONNX inference budget is 10–20ms on CPU; tesseract 100–300ms, both inside the per-target SLA.
3. **Concurrency** = `asyncio` + `loop.run_in_executor(ThreadPoolExecutor(max_workers=2), ...)` for OCR. ProactorEventLoop is the Windows 3.8+ default and works correctly with `aiohttp==3.13.x` and ThreadPoolExecutor in Python 3.11 (the historical BPO #23846 BlockingIOError was fixed in 2019; the only remaining footgun is `RuntimeError: Event loop is closed` on shutdown, mitigated by `await session.close()` + `await asyncio.sleep(0.1)` before loop exit).
4. **Twitter v2 streaming** = `tweepy>=4.15,<5` `AsyncStreamingClient` with bearer token from `TWITTER_BEARER_TOKEN` env var. Static rule set in `src/config/constants.TWITTER_RULE_SET`. **Tier reality (as of 2026-05):** Twitter retired Free/Essential streaming; Basic ($200/mo, no streaming), Pro ($5k/mo, streaming, 1000 rules / 1024 chars), Enterprise (25k+ rules / 2048 chars). Phase 3 listener MUST degrade gracefully (return immediately with structured warning log) when bearer token is missing or insufficient, so CI and dry-run dev work without paid access. The synthetic E2E test feeds a mock stream — no real connection required.
5. **Arbiter** = five `collections.deque[ArbiterPending]` with a 50ms `tick()` driven by `asyncio.create_task` + `asyncio.sleep`. Per-rule predicates evaluate distinct sources in window; emits `ConfirmedEvent` to a single `asyncio.Queue` consumed by the engine driver. Quarantined entries write to the SAME JSONL with `quarantined: true` + `seq_id: null`. Time discipline: `time.monotonic_ns()` for all latency math; `time.time()` only for the wall-clock `t_observed` field (so replays line up with broadcast timestamps).

**Primary recommendation:** Pin the dependency table in §Standard Stack verbatim, copy the three salvage files to `reference/` first, then follow the salvage-port delta checklist (§Don't Hand-Roll). Use the validation-architecture sampling targets in §Validation Architecture as PLAN must-haves.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01 — MatchState mutator:** `@dataclass(frozen=True, slots=True)` + `state.with_update(...)` returning a new instance with `seq_id = state.seq_id + 1`, `last_updated_ts = now()`. Pure-functional, single arbiter writer under one `asyncio.Lock`. No mutable+commit. No builder.
- **D-02 — JSONL log:** diff-only line per commit with `seq_id`, six-stage timestamps, `source`, `event_type`, `fields_changed`. Phase 4 fills `t_theo_computed`/`t_quote_sent` post-write keyed by `seq_id`. Quarantined events live in the SAME file with `quarantined: true` and `seq_id: null` (NOT bumped). Path: `data/event_log/{match_id}.jsonl`. ~5–10 MB per match.
- **D-03 — OCR backend:** Hybrid. ONNX small text-recognition CNN (Apache/MIT/BSD only, ~2–5 MB) for kill feed (latency-critical). tesseract for score banner / bomb icon / round-end banner. Dependencies in `pyproject.toml`: `onnxruntime` (CPU), `pytesseract`, `Pillow`, `numpy`. GPU-only rejected (Hetzner CCX13 has no GPU).
- **D-04 — Arbiter mechanism:** Per-event-type `collections.deque` (5 deques: `score_changes`, `kill_events`, `bomb_events`, `numerical_flips`, `round_end_events`). Each entry = `ArbiterPending(signal_value, source, t_observed, t_ingested)`. `tick(now)` evicts expired, re-evaluates predicates, emits `ConfirmedEvent`. Tick rate = max(20Hz, 2× highest source cadence). No RxPy. No tagged single stream.
- **D-05 — Quarantine policy:** Same JSONL, `"quarantined": true` + `quarantine_reason` + `fields_proposed`. seq_id NOT bumped. Replay tooling filters `quarantined != true`.
- **D-06 — Concurrency model:** `asyncio` event loop for I/O (rib.gg poller, Twitter stream, arbiter tick, engine reader). `ThreadPoolExecutor(max_workers=2)` for OCR via `loop.run_in_executor`. Single shared `asyncio.Queue` for confirmed events. No multiprocessing. No pure threading.
- **D-07 — Twitter rule set:** Static league watch list in `src/config/constants.py`. Initial: `["#VCT", "#VALORANTChampions", "#VCTAmericas", "#VCTEMEA", "#VCTPacific"]` plus pinned 2026 caster/league/team-org accounts. Pushed once at startup; not per-match. No dynamic per-match rule CRUD.

### Claude's Discretion

- Concrete ONNX checkpoint URL pin (Apache/MIT/BSD).
- onnxruntime/aiohttp/tweepy/pytesseract/Pillow/numpy/pytest-asyncio/pytest-benchmark exact version constraints for Python 3.11 + Windows 11.
- Twitter caster/league/team-org account names (to be filled into `TWITTER_RULE_SET`).
- ArbiterPending / ConfirmedEvent / EventLogLine concrete dataclass shapes.
- "Same frame" definition for kill/bomb/numerical cross-confirm (researcher: 100ms window = kill-feed cadence).
- Time-source mix (monotonic vs wall-clock).
- JSONL hot-path: simple `open()` + buffered append vs orjson batched flush — researcher recommends simple stdlib path.
- Synthetic E2E test wiring + p50 measurement methodology.
- Validation Architecture sampling rates (lifted into PLAN must-haves).

### Deferred Ideas (OUT OF SCOPE)

- bo3.gg API adapter (Phase 5 if rib.gg degrades).
- vlr.gg API adapter (Phase 5 robustness).
- Twitch / YouTube IRC chat soft cross-confirm (follow-up phase).
- Per-match dynamic Twitter rule sync (later if S/N becomes a problem).
- GPU-accelerated OCR (Phase 6 if paper-trade Brier exposes OCR-latency-driven misses).
- Per-event-class hybrid checkpoint snapshots in JSONL (later if 30k-diff replay is hot).
- 30-min operator-driven live smoke run (replaced by synthetic E2E in CI).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REQ-match-state-engine | `@dataclass MatchState` migrated to `src/state/match_state.py`, extended with `seq_id, last_updated_ts, players_alive_a/b, ults_a/b, time_left_s, econ_a/b`; mutators bump monotonic `seq_id`; JSONL append on every mutation. | §Architecture Patterns "Pattern 1: Frozen+slots `with_update()` mutator"; §Code Examples "MatchState v2 dataclass"; §Validation Architecture row REQ-match-state-engine. |
| REQ-scoreboard-polling | 5s-cadence rib.gg poller; reuse Phase 2 `scripts/probe_round_events.py` resilience patterns. | §Don't Hand-Roll "rib.gg HTTP layer"; §Salvage Port Delta Checklist; §Code Examples "ScoreboardPoller skeleton". |
| REQ-ocr-pipeline | Per-target cadences: score banner 250ms, kill feed 100ms, bomb icon 500ms, round-end banner 100ms; decode + inference < 100ms median; CPU-only. | §Standard Stack ONNX + tesseract pins; §Architecture Patterns "Pattern 2: ThreadPoolExecutor OCR worker"; §Common Pitfalls Pitfalls 1, 2, 3. |
| REQ-text-listener | Twitter v2 streaming filter; soft signal only; never sole-source confirmation. | §Standard Stack tweepy pin; §Architecture Patterns "Pattern 3: AsyncStreamingClient subclass with degrade-on-missing-token"; §Common Pitfalls Pitfall 5. |
| REQ-cross-source-arbiter | 5-deque pipeline; per-event-type rules per PRD §5.1 / DEC-006; quarantine on rule-fail. | §Architecture Patterns "Pattern 4: tick() pseudocode"; §Code Examples "Arbiter rule predicates"; §Validation Architecture REQ-cross-source-arbiter row. |
| REQ-latency-instrumentation | Six-stage timestamps on every event; metrics file (separate JSONL); replay-able. | §Architecture Patterns "Pattern 5: Six-stage timestamp lineage"; §Code Examples "EventLogLine + MetricsLogLine"; §Common Pitfalls Pitfall 8. |
| REQ-end-to-end-latency | E2E `t_observed → t_state_committed < 500ms (median)` in synthetic E2E test. | §Validation Architecture E2E latency row; §Code Examples "p50 measurement in pytest". |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| MatchState versioning + mutator | `src/state/` | — | Pure data + mutator; no I/O. Frozen+slots is a state-engine concern, not pricing. |
| JSONL event log writer | `src/state/` (writer in MatchState mutator OR arbiter) | — | Co-located with the mutator that bumps seq_id so the line write happens atomically with the state swap. Recommend the **arbiter** owns the write (it's the sole mutator caller per CONTEXT integration_points), keeping `match_state.py` pure-data. |
| rib.gg HTTP poller | `src/ingestion/` | — | I/O-bound source; uses Phase 2's resilience patterns. |
| OCR pipeline (decode + inference) | `src/ingestion/` (with ThreadPoolExecutor offload) | — | CPU-bound; runs in worker thread to avoid blocking the asyncio loop. |
| Twitter v2 listener | `src/ingestion/` | — | Long-lived async I/O; subclasses `tweepy.AsyncStreamingClient`. |
| Cross-source arbiter | `src/ingestion/` | `src/state/` (writes via mutator) | Sole writer to MatchState; owns deques + tick + JSONL append. |
| Engine driver (re-invokes `live_theo` after each commit) | `src/state/` (thin wrapper) | — | Holds the `LiveTheoEngine` reference; consumes confirmed events from the queue. Phase 4 will replace this with the quoting driver — keep the seam thin. |
| Latency instrumentation (timestamp stamping) | Distributed across sources + arbiter | — | Each source stamps `t_observed`/`t_ingested`; arbiter stamps `t_arbited`/`t_state_committed`; Phase 4 stamps `t_theo_computed`/`t_quote_sent`. |
| Constants (cadences, windows, rule set) | `src/config/constants.py` | — | CRule 12 — every threshold lives here. |

## Standard Stack

### Core (verified live 2026-05-01 against PyPI + HuggingFace)

| Library | Version | Purpose | Why Standard | Verification |
|---------|---------|---------|--------------|--------------|
| `aiohttp` | `>=3.10,<4` | Async HTTP client for rib.gg poller; backbone for `tweepy.AsyncStreamingClient` | De facto Python async HTTP, ships cp311-win_amd64 wheel, 3.13.5 latest | `[VERIFIED: pip index versions aiohttp]` 3.13.5 latest, cp311 wheel confirmed |
| `tweepy` | `>=4.15,<5` | Twitter API v2 streaming client (`AsyncStreamingClient`) | Official-blessed Twitter v2 client, AsyncStreamingClient since v4.10 | `[VERIFIED: pip dry-run]` 4.16.0 installs cleanly with oauthlib 3.3.1 |
| `onnxruntime` | `>=1.20,<1.22` | CPU inference for kill-feed CNN | Microsoft's reference ONNX runtime; CPU build is the default `pip install onnxruntime` (NOT `onnxruntime-gpu`) | `[VERIFIED: pip index versions onnxruntime]` 1.25.1 latest; pin range to 1.20–1.21 because 1.22+ deprecated some opset 17 ops still present in PaddleOCR exports — re-verify if pinning higher |
| `pytesseract` | `>=0.3.13,<0.4` | Python wrapper for the Tesseract binary | Standard Python OCR wrapper; no realistic alternative for tesseract integration | `[VERIFIED: pip index versions pytesseract]` 0.3.13 latest; **system tesseract 5.5.0.20241111 already installed at `C:\Program Files\Tesseract-OCR\tesseract.exe`** |
| `Pillow` | `>=11,<13` | Image decode/crop/preprocess for OCR + ONNX inputs | Stdlib-replacement image lib; required by pytesseract; numpy interop via `np.asarray(im)` | `[VERIFIED: pip index versions Pillow]` 12.2.0 latest; 11.x already installed locally |
| `numpy` | `>=1.26,<3` | ONNX input tensor build + image array math | Required by onnxruntime + downstream image normalization | `[VERIFIED: pip index versions numpy]` 2.4.4 latest; 1.26.2 installed locally; pin range covers the 1.x→2.x boundary |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pytest-asyncio` | `>=0.24,<2` | Run async tests in pytest | Required for any test that drives the asyncio event loop (arbiter tick, queue consumption, etc.). 1.x line stable since 2025. |
| `pytest-benchmark` | `>=4,<6` | OCR per-frame benchmark | REQ-ocr-pipeline acceptance: median decode + inference < 100ms over 50 frames. `pytest-benchmark` produces the median directly. |
| `structlog` | `>=24,<26` (optional) | Structured logging in ingestion modules | Replaces salvage-source `print()` calls. NOT in scope if planner picks plain stdlib `logging` with JSON formatter — either is fine, structlog is the smoother fit per project preferences. |
| `tenacity` | `>=8.5` (already pinned) | Retry decorator for rib.gg poller | Already in `pyproject.toml` from Phase 2. Reuse `_ribgg_wait` pattern verbatim. |
| `requests` | `>=2.32` (already pinned) | Sync HTTP for rib.gg poller — see notes | Already in `pyproject.toml` from Phase 2. **Decision point for planner:** the Phase 2 poller is sync `requests`. The planner can either (a) keep `requests.get` running inside `loop.run_in_executor` (zero-rewrite, validates the Phase 2 resilience patterns continue to apply), OR (b) port to `aiohttp.ClientSession`. Recommend **(a)** for Phase 3 — the 5s scoreboard cadence is not a latency-critical path, the wrapper is one line, and it preserves the verified `Connection: close` + `_ribgg_wait` resilience without re-validation. Use `aiohttp` only for the Twitter long-lived stream where it's required by tweepy. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `tweepy` | Raw `aiohttp` against `https://api.twitter.com/2/tweets/search/stream` | `tweepy` handles bearer auth, rule CRUD, reconnection backoff (`max_retries=inf` default), and lifecycle hooks (`on_disconnect`, `on_request_error`). Hand-rolling adds ~150 LOC of plumbing for zero correctness gain. **Pick tweepy.** |
| `tweepy.AsyncStreamingClient` | `tweepy.StreamingClient` (sync) | Sync client uses urllib3 + a worker thread. Async fits cleanly into D-06's asyncio-first model and shares the loop with the rib.gg poller. **Pick async.** |
| `onnxruntime` (CPU) | `onnxruntime-gpu` | D-03 explicitly rejects GPU per Hetzner CCX13 deployment target. **Don't install gpu variant.** Note: onnxruntime ships both wheels under different package names; install `onnxruntime` (NOT `onnxruntime-gpu`). |
| Bundled tesseract via `tesserocr` | `pytesseract` against system binary | `tesserocr` requires building Cython bindings on Windows — known-fragile. The system binary is already installed. **Pick pytesseract.** |
| `orjson` for JSONL hot path | stdlib `json.dumps` | At ~30k events × ~250 bytes = ~7 MB/match across a 90-min window, the throughput is ~30k/5400s = ~6 events/sec at peak. stdlib `json.dumps` does ~1M dumps/sec on a single core. orjson buys nothing here, drags in a Rust binary, and complicates `mypy --strict` on `src/state/`. **Stick with stdlib.** |
| `pytest-trio` | `pytest-asyncio` | Project is asyncio-native (D-06). Trio adds a foreign concurrency model. **Pick pytest-asyncio.** |

**Installation commands:**
```bash
uv add aiohttp tweepy onnxruntime pytesseract Pillow numpy
uv add --dev pytest-asyncio pytest-benchmark
# Optional, recommended:
uv add structlog
```

**Version verification (run before locking pyproject.toml):**
```bash
pip index versions onnxruntime
pip index versions tweepy
pip index versions aiohttp
# Confirm cp311-win_amd64 wheel exists for each.
```

[VERIFIED: pip index versions, 2026-05-01] All packages above ship cp311-win_amd64 wheels. No source builds needed on the dev machine.

## Architecture Patterns

### System Architecture Diagram

```
                    ┌──────────────────┐
                    │  rib.gg /v1/...  │ (5s cadence — sync requests in executor OR aiohttp)
                    └────────┬─────────┘
                             │ ScoreboardEvent(t_observed=time.time(), t_ingested=time.monotonic_ns())
                             ▼
   ┌──────────────┐    ┌─────────────────┐    ┌──────────────┐
   │ YouTube/HLS  │───▶│ ThreadPool×2    │───▶│              │
   │ frame source │    │ (OCR: ONNX +    │    │              │
   │ (mocked in   │    │  pytesseract)   │    │              │
   │  CI)         │    └────────┬────────┘    │              │
   └──────────────┘             │             │              │
                                ▼             │   ARBITER    │       ConfirmedEvent
                         OCREvent             │   (5 deques) │ ──┐  asyncio.Queue
   ┌──────────────┐                           │              │   │
   │ Twitter v2   │───▶ TextEvent (soft) ────▶│  tick(now)   │   │
   │ stream       │                           │  every 50ms  │   │
   │ (mocked in   │                           │              │   │
   │  CI)         │                           │  rules:      │   │
   └──────────────┘                           │  - score≥2/2s│   │
                                              │  - 1CV+kill  │   │
                                              │  - round-end │   │
                                              │     soft+hard│   │
                                              └──────┬───────┘   │
                                                     │           │
                                          (quarantined?) ─yes──▶ │
                                                     │           │  same JSONL,
                                                     │           ▼  quarantined:true
                                                     ▼           │
                                           state.with_update(…) │
                                                     │           │
                                                     ▼           │
                                              MatchState.seq_id++│
                                          ┌──────────────────────┘
                                          │
                                          ▼
                              ┌────────────────────┐    JSONL: data/event_log/{match_id}.jsonl
                              │  Engine driver     │   (one diff line per commit + quarantine)
                              │  invokes           │
                              │  LiveTheoEngine    │     Metrics: data/metrics/{match_id}.metrics.jsonl
                              │  (state) →TheoOut  │     (six-stage timestamps; Phase 5 reads this)
                              └────────────────────┘
```

Data-flow: every source produces an `ArbiterPending` with two timestamps stamped at observation. Arbiter's `tick()` evicts expired entries and evaluates rules against remaining; on rule-fire the arbiter calls `state.with_update(...)` (the sole writer), stamps `t_state_committed`, appends one JSONL line, and pushes a `ConfirmedEvent` onto the queue. The engine driver consumes the queue, calls `LiveTheoEngine(state)`, and stamps `t_theo_computed` (Phase 4 will eventually fill `t_quote_sent`). Quarantined entries write to the SAME JSONL with `seq_id: null`, `quarantined: true`, and never enter the queue.

### Recommended Project Structure

```
src/
├── config/
│   └── constants.py         # +OCR_*_CADENCE_MS, ARBITER_*_S, TWITTER_*, EVENT_LOG_DIR, METRICS_LOG_DIR
├── ingestion/
│   ├── __init__.py
│   ├── scoreboard.py        # rib.gg 5s poller (port from reference/rib_scraper.py)
│   ├── ocr.py               # ONNX kill-feed + tesseract for 3 other targets (port from reference/vision_parser.py)
│   ├── text_listener.py     # tweepy.AsyncStreamingClient subclass (NEW, no salvage source)
│   ├── arbiter.py           # 5 deques + tick() + JSONL writer + queue producer
│   └── types.py             # ArbiterPending, ConfirmedEvent, EventLogLine, MetricsLogLine dataclasses
├── state/
│   ├── __init__.py
│   ├── match_state.py       # MatchState (frozen+slots, with_update mutator) — moved from src/pricing/data.py
│   └── engine_driver.py     # consumes ConfirmedEvent queue → invokes LiveTheoEngine
├── pricing/
│   └── data.py              # SHRINK to: re-export TheoOutput, HalfRates only; MatchState gone (or re-export shim)
data/
├── event_log/{match_id}.jsonl
└── metrics/{match_id}.metrics.jsonl
models/
└── en_PP-OCRv4_rec_infer.onnx       # 7.66 MB, Apache 2.0, downloaded from HuggingFace via build script
reference/
├── vlr_scraper.py           # NEW — copied from thunderedge/ before plan starts
├── rib_scraper.py           # NEW — copied from thunderedge/ before plan starts
└── vision_parser.py         # NEW — copied from thunderedge/ before plan starts
tests/
├── ingestion/
│   ├── __init__.py
│   ├── conftest.py          # fixtures: mock rib.gg, fake OCR frame source, fake Twitter stream
│   ├── test_scoreboard.py
│   ├── test_ocr.py          # includes 50-frame benchmark
│   ├── test_text_listener.py
│   ├── test_arbiter.py      # property tests over enumerated (source, event_type)
│   └── test_e2e.py          # SPEC acceptance #8 — synthetic E2E gate
└── state/
    ├── __init__.py
    ├── test_match_state.py  # 1000-mutator monotonicity property test, JSONL replay round-trip
    └── test_engine_driver.py
```

### Pattern 1: Frozen+slots `with_update()` mutator

**What:** D-01 — `MatchState` stays frozen, mutator returns a new instance with `seq_id` bumped.

**When to use:** Every state mutation in `arbiter.py`.

**Example:**
```python
# src/state/match_state.py
from __future__ import annotations
import time
from dataclasses import dataclass, field, replace
from typing import Any, Optional, Self

@dataclass(frozen=True, slots=True)
class MatchState:
    # ... 17 Phase 1 fields (copied verbatim from src/pricing/data.py) ...
    # Phase 3 additions:
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
        # Bump seq_id and last_updated_ts atomically with the diff.
        # Reject any caller-provided seq_id / last_updated_ts override (defensive).
        diffs.pop("seq_id", None)
        diffs.pop("last_updated_ts", None)
        return replace(
            self,
            seq_id=self.seq_id + 1,
            last_updated_ts=time.time(),
            **diffs,
        )
```

Allocation cost per mutation: ~200 bytes (slots=True keeps it minimal). At 30k mutations/match that's ~6 MB of GC churn — well below concern.

### Pattern 2: ThreadPoolExecutor OCR worker

**What:** D-06 — OCR runs in a 2-worker thread pool, dispatched via `loop.run_in_executor`.

**When to use:** Every OCR frame (kill-feed, score-banner, bomb-icon, round-end).

**Example:**
```python
# src/ingestion/ocr.py
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Final

_OCR_POOL: Final[ThreadPoolExecutor] = ThreadPoolExecutor(
    max_workers=2,
    thread_name_prefix="ocr",
)

async def run_ocr_frame(frame: bytes, target: str) -> dict[str, Any]:
    """Decode + inference in a worker thread; returns OCREvent dict.

    target ∈ {"kill_feed", "score_banner", "bomb_icon", "round_end_banner"}
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_OCR_POOL, _ocr_blocking, frame, target)

def _ocr_blocking(frame: bytes, target: str) -> dict[str, Any]:
    # Decode (Pillow), preprocess (numpy), inference (onnxruntime OR pytesseract).
    ...
```

### Pattern 3: AsyncStreamingClient subclass with degrade-on-missing-token

**What:** D-07 — listener subclasses `tweepy.AsyncStreamingClient` and **degrades to a no-op coroutine** when bearer token is missing or empty (CRule 13: dry-run default; CI must work without paid Twitter access).

**When to use:** `src/ingestion/text_listener.py`.

**Example:**
```python
# src/ingestion/text_listener.py
import os
import asyncio
import logging
from typing import Optional
from tweepy.asynchronous import AsyncStreamingClient
from tweepy import StreamRule

from src.config.constants import TWITTER_RULE_SET

log = logging.getLogger(__name__)

class ValorantTextListener(AsyncStreamingClient):
    """Twitter v2 streaming filter for Valorant match signals.

    Soft-signal source — never sole-source per arbiter D-05.
    Degrades to a no-op coroutine if TWITTER_BEARER_TOKEN is unset
    (CI / dev / dry-run).
    """

    def __init__(self, arbiter_pending_emit, bearer_token: Optional[str] = None) -> None:
        token = bearer_token or os.environ.get("TWITTER_BEARER_TOKEN", "")
        if not token:
            log.warning("TWITTER_BEARER_TOKEN unset — text listener will run as no-op")
            self._noop = True
            return
        self._noop = False
        super().__init__(token, max_retries=10, wait_on_rate_limit=True)
        self._emit = arbiter_pending_emit

    async def start(self) -> None:
        if self._noop:
            return  # CRule 13: dry-run default; never block on missing creds
        # Idempotent rule push — fetch existing, diff, push only delta.
        existing = await self.get_rules()
        existing_values = {r.value for r in (existing.data or [])}
        new_rules = [StreamRule(v) for v in TWITTER_RULE_SET if v not in existing_values]
        if new_rules:
            await self.add_rules(new_rules)
        await self.filter()  # blocks; runs forever until disconnect

    async def on_tweet(self, tweet) -> None:
        # Parse text for round/score signals; emit ArbiterPending with source="twitter".
        ...

    async def on_request_error(self, status_code: int) -> None:
        # tweepy already retries with exponential backoff up to max_retries=10.
        # Just log; never give up silently.
        log.error("twitter stream error status=%s", status_code)
```

### Pattern 4: tick() pseudocode

**What:** D-04 — arbiter has 5 deques; `tick()` evicts expired entries and re-evaluates rules.

**When to use:** Inside `Arbiter.run()` driven by `asyncio.create_task(self._tick_loop())`.

**Example:**
```python
# src/ingestion/arbiter.py
import asyncio
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Literal

from src.config.constants import (
    ARBITER_TICK_HZ,             # NEW — recommend 20 (50ms tick)
    ARBITER_SCORE_WINDOW_S,      # NEW — 2.0 per DEC-006
    ARBITER_KILL_WINDOW_MS,      # NEW — 100 (one kill-feed cadence "frame")
    ARBITER_BOMB_WINDOW_MS,      # NEW — 100
    ARBITER_NUMERICAL_WINDOW_MS, # NEW — 100
    ARBITER_ROUND_END_WINDOW_S,  # NEW — 5.0 (round-end-banner-active period)
)

@dataclass(frozen=True, slots=True)
class ArbiterPending:
    signal_value: dict[str, Any]
    source: Literal["ribgg", "ocr", "twitter"]
    event_type: Literal["score_change", "kill", "bomb", "numerical_flip", "round_end"]
    t_observed: float       # wall-clock for replay
    t_ingested: int         # monotonic_ns for latency math

@dataclass(frozen=True, slots=True)
class ConfirmedEvent:
    fields_changed: dict[str, Any]
    source_set: tuple[str, ...]   # which sources agreed
    event_type: str
    t_observed: float
    t_ingested: int
    t_arbited: int               # monotonic_ns; arbiter writes this
    # t_state_committed populated AFTER state.with_update() returns

class Arbiter:
    def __init__(self, state_holder, queue: asyncio.Queue, jsonl_writer):
        self._state_holder = state_holder      # has .swap(new_state); holds asyncio.Lock internally
        self._queue = queue                    # asyncio.Queue[ConfirmedEvent]
        self._jsonl = jsonl_writer
        self._lock = asyncio.Lock()
        self._score_changes: deque[ArbiterPending]    = deque()
        self._kill_events: deque[ArbiterPending]      = deque()
        self._bomb_events: deque[ArbiterPending]      = deque()
        self._numerical_flips: deque[ArbiterPending]  = deque()
        self._round_end_events: deque[ArbiterPending] = deque()

    async def submit(self, pending: ArbiterPending) -> None:
        async with self._lock:
            self._dq_for(pending.event_type).append(pending)

    async def _tick_loop(self) -> None:
        period_s = 1.0 / ARBITER_TICK_HZ
        while True:
            await asyncio.sleep(period_s)
            await self._tick(time.monotonic_ns())

    async def _tick(self, now_ns: int) -> None:
        async with self._lock:
            self._evict(self._score_changes,    now_ns, int(ARBITER_SCORE_WINDOW_S    * 1e9))
            self._evict(self._kill_events,      now_ns, ARBITER_KILL_WINDOW_MS      * 1_000_000)
            self._evict(self._bomb_events,      now_ns, ARBITER_BOMB_WINDOW_MS      * 1_000_000)
            self._evict(self._numerical_flips,  now_ns, ARBITER_NUMERICAL_WINDOW_MS * 1_000_000)
            self._evict(self._round_end_events, now_ns, int(ARBITER_ROUND_END_WINDOW_S * 1e9))
            self._eval_score_rule(now_ns)
            self._eval_kill_rule(now_ns)
            self._eval_bomb_rule(now_ns)
            self._eval_numerical_rule(now_ns)
            self._eval_round_end_rule(now_ns)

    @staticmethod
    def _evict(dq: deque[ArbiterPending], now_ns: int, window_ns: int) -> None:
        while dq and (now_ns - dq[0].t_ingested) > window_ns:
            dq.popleft()

    def _eval_score_rule(self, now_ns: int) -> None:
        # DEC-006: score change ≥ 2 distinct sources within 2s window.
        # Group by signal_value (e.g., {"a_round": 7}); fire when ≥2 distinct sources match.
        from collections import defaultdict
        by_signal: dict[tuple, set[str]] = defaultdict(set)
        for p in self._score_changes:
            key = tuple(sorted(p.signal_value.items()))
            by_signal[key].add(p.source)
        for key, sources in by_signal.items():
            if len(sources) >= 2:
                self._commit(
                    fields_changed=dict(key),
                    source_set=tuple(sorted(sources)),
                    event_type="score_change",
                    inputs=[p for p in self._score_changes
                            if tuple(sorted(p.signal_value.items())) == key],
                    now_ns=now_ns,
                )
                # Remove committed inputs.
                for p in list(self._score_changes):
                    if tuple(sorted(p.signal_value.items())) == key:
                        self._score_changes.remove(p)

    def _eval_kill_rule(self, now_ns: int) -> None:
        # DEC-006: 1 CV-based source if kill-feed cross-confirms within same frame
        # (= ARBITER_KILL_WINDOW_MS = 100ms = one kill-feed cadence "frame").
        # Practically: a single OCR kill-feed event within window auto-confirms.
        # Twitter-only kill-feed events QUARANTINE per D-05 (REQ-text-listener acceptance).
        for p in list(self._kill_events):
            if p.source == "ocr":
                self._commit(
                    fields_changed=p.signal_value,
                    source_set=("ocr",),
                    event_type="kill",
                    inputs=[p],
                    now_ns=now_ns,
                )
                self._kill_events.remove(p)
            elif p.source == "twitter":
                self._quarantine(p, "kill needs CV source; twitter-only", now_ns)
                self._kill_events.remove(p)

    # _eval_bomb_rule / _eval_numerical_rule mirror _eval_kill_rule.

    def _eval_round_end_rule(self, now_ns: int) -> None:
        # DEC-006: soft commit on banner; hard-confirm by next score update.
        # Implementation: a round-end OCR event commits with a soft flag; when the
        # next score_change confirms in the same window, upgrade to hard. The
        # planner can simplify to "commit immediately, mark as soft" since the
        # downstream theo doesn't distinguish — Phase 5 calibration will revisit.
        for p in list(self._round_end_events):
            if p.source == "ocr":
                fields = dict(p.signal_value, _round_end_soft=True)
                self._commit(fields, ("ocr",), "round_end", [p], now_ns)
                self._round_end_events.remove(p)

    def _commit(self, fields_changed, source_set, event_type, inputs, now_ns):
        # Build ConfirmedEvent, swap state, write JSONL, push to queue.
        ce = ConfirmedEvent(
            fields_changed=fields_changed,
            source_set=source_set,
            event_type=event_type,
            t_observed=min(p.t_observed for p in inputs),
            t_ingested=min(p.t_ingested for p in inputs),
            t_arbited=now_ns,
        )
        new_state, t_committed_ns = self._state_holder.swap_with(fields_changed)
        self._jsonl.write_committed(ce, new_state.seq_id, t_committed_ns)
        self._queue.put_nowait(ce)

    def _quarantine(self, pending, reason, now_ns):
        self._jsonl.write_quarantined(pending, reason, now_ns)
```

### Pattern 5: Six-stage timestamp lineage

**What:** REQ-latency-instrumentation — every event carries `t_observed, t_ingested, t_arbited, t_state_committed, t_theo_computed, t_quote_sent`.

**Time-source discipline (researcher recommendation):**
- `t_observed` = `time.time()` (wall-clock; needed for replay vs broadcast timeline).
- All five other timestamps = `time.monotonic_ns()` (latency math; immune to NTP jumps).
- For the JSONL on-disk schema, write all six as floats in seconds (convert `monotonic_ns / 1e9`); the ratio between two monotonic timestamps is the latency, not the absolute value.
- `time.perf_counter_ns()` is unnecessary at < 500ms target — `monotonic_ns` is plenty (Windows resolution: 100ns since Win10).

```python
# src/ingestion/types.py
import time
from dataclasses import dataclass
from typing import Any, Optional

@dataclass(frozen=True, slots=True)
class EventLogLine:
    seq_id: Optional[int]            # None for quarantined
    t_observed: float                # wall-clock, seconds since epoch
    t_ingested: float                # monotonic seconds
    t_arbited: float                 # monotonic seconds
    t_state_committed: Optional[float]   # monotonic seconds, None for quarantined
    t_theo_computed: Optional[float]     # filled by Phase 4
    t_quote_sent: Optional[float]        # filled by Phase 4
    source: str
    event_type: str
    fields_changed: dict[str, Any]   # for committed
    fields_proposed: Optional[dict[str, Any]]  # for quarantined
    quarantined: bool = False
    quarantine_reason: Optional[str] = None
```

### Anti-Patterns to Avoid

- **Mutable MatchState with `.commit()` method.** Breaks D-01 frozen invariant; reintroduces lock contention with the Phase 1 reader path.
- **Two separate JSONL files (one for committed, one for quarantined).** D-05 explicitly chose unified file; replay tooling stays single-pass.
- **Per-mutation `open(path, "a")` + `close()`.** On Windows, file-handle churn at 30k events/match × open-close pairs runs ~50–100 ms aggregate. Open ONCE at match-start, append with `buffering=1<<16`, `flush()` periodically.
- **`asyncio.wait_for(coro, timeout=...)` for cancellation in Python 3.11.** Use `async with asyncio.timeout(...):` (PEP 654) — `wait_for` has subtle "task swallowed cancellation" bugs that surface under pytest. `asyncio.timeout` is the 3.11+ idiom.
- **OCR loop running synchronously on the asyncio event loop.** Pytesseract takes 100–300ms per call; running it inline starves all other coroutines. ALWAYS via `loop.run_in_executor`.
- **Parsing tweet text with regex inside `on_tweet`.** Slow + brittle. The keyword filter is already at Twitter; in `on_tweet` just look for known signals (team names, score patterns) and emit. Defer the heavy parsing to a separate parser module that's unit-testable.
- **Polling `time.time()` in tight loop.** Cache `time.monotonic_ns()` once per arbiter tick; pass `now_ns` down. Saves ~50µs/tick at 20Hz = ~1ms/sec total but more importantly keeps the entire tick consistent.
- **Bumping seq_id on quarantine.** D-05 forbids it; replay tooling expects seq_id density to match committed events only.
- **Allowing `with_update()` callers to override `seq_id` or `last_updated_ts`.** Defensive: `with_update` strips them from `**diffs` (see Pattern 1).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Async HTTP for rib.gg under asyncio | Custom `urllib.request` wrapper | Phase 2's sync `requests.get` inside `loop.run_in_executor` (recommended) OR `aiohttp.ClientSession` | Phase 2's `_ribgg_wait` + `Connection: close` patterns are validated. Don't re-validate. |
| rib.gg retry / Retry-After honoring | New retry loop | `tenacity` `@retry(stop=stop_after_attempt(5), wait=_ribgg_wait)` from `scripts/probe_round_events.py:122` (verbatim transplant) | Phase 2 proved this in production. |
| Twitter v2 streaming + reconnection + rule CRUD | Raw `aiohttp` against `/2/tweets/search/stream` | `tweepy.AsyncStreamingClient` | Saves ~150 LOC; handles bearer auth, rule diffing, exponential backoff, lifecycle hooks. |
| Image decode | OpenCV-Python | `Pillow` | Already a `pytesseract` dep; no extra install. OpenCV pulls in ~80MB. |
| Image-to-tensor for ONNX | NumPy from scratch | `np.asarray(im).transpose(2,0,1).astype(np.float32) / 255.0` then expand_dims | Three-line idiom; well-documented in onnxruntime examples. |
| Kill-feed text-recognition CNN | Train one | `breezedeus/cnocr-ppocr-en_PP-OCRv4/en_PP-OCRv4_rec_infer.onnx` (7.66 MB, Apache 2.0) | Ready-to-use; English; 80%+ word accuracy on synthetic gameplay frames per cnocr's published metrics. |
| Score-banner / bomb-icon / round-end-banner OCR | Train CNN | `pytesseract.image_to_string(im, lang="eng", config="--psm 7")` | psm 7 = "single text line"; 100–300ms on Windows; well within 250–500ms cadences. |
| JSONL writer | Buffered file abstraction | `pathlib.Path.open("a", buffering=1<<16, encoding="utf-8")` + periodic `f.flush()` | stdlib; correct on Windows; mypy-clean. |
| Latency p50 measurement | `statistics.median(latencies)` ad hoc | `pytest-benchmark` (or `statistics.median`) | pytest-benchmark already used elsewhere; outputs median + percentiles natively. |
| Async test driver | `asyncio.run(coro)` per test | `pytest-asyncio` with `asyncio_mode = "auto"` | Auto mode treats `async def test_...` as an async test without per-test markers. |
| Property-test source generation | Manual loops | `hypothesis` strategies (`st.integers()`, `st.lists(st.tuples(...))`) | Already a dev dep from Phase 0; the 1000-mutator monotonicity test fits a single `@given` decorator. |
| Twitter API version pinning | DIY OAuth2 | tweepy bearer-token client | Bearer auth handled internally; one env var. |

### Salvage-Port Delta Checklist

The user MUST copy three files from `thunderedge/worktrees/market-maker/.../` into `reference/` BEFORE the plan starts (per SPEC §boundaries.salvage-discipline). Once present, the plan instructs the executor to port them to `src/ingestion/` applying these deltas:

**For all three (`vlr_scraper.py`, `rib_scraper.py`, `vision_parser.py`):**

- [ ] **Replace bare `requests`/`urllib` calls** with the Phase 2 `get_json` wrapper (or its async-friendly twin) — gains `_ribgg_wait`, `Connection: close`, 60s timeout, tenacity retry. Inline it from `scripts/probe_round_events.py:122` if not yet promoted to `src/`.
- [ ] **Replace globals / module-level state** with constructor-injected dependencies. The executor must construct an `Arbiter`/`ScoreboardPoller`/`OCRPipeline` instance per match; there must be no module-level mutable state (especially no global `requests.Session`). Module-level _constants_ are fine.
- [ ] **Add type annotations on every function** (parameters and return). `src/ingestion/` stays gradual mypy per SPEC, but new code annotates fully (matches Phase 1 + 2 discipline).
- [ ] **Replace `print(...)` calls** with `structlog` (or stdlib `logging` JSON formatter). NEVER print in production code paths.
- [ ] **Replace inline thresholds** (any number > 1 or < 0.1 in business logic) with imports from `src/config/constants.py`. CRule 12.
- [ ] **Drop sys.exit / argparse / `__main__` blocks** — these belong only in the eventual `python -m src.main` entry point (Phase 4 work). Ingestion modules export classes only.
- [ ] **Replace any `time.sleep` in I/O loops** with `await asyncio.sleep(...)`. Synchronous sleeps inside coroutines block the event loop.
- [ ] **Drop OS-specific path handling** — use `pathlib.Path` exclusively.

**`vlr_scraper.py` / `rib_scraper.py` specifically:**
- [ ] **Verify rib.gg endpoints** match Phase 2's verified set: `/v1/events`, `/v1/series`, `/v1/matches/{id}/details`. If salvage points at older `/v2/...` URLs (the README in PRD mentions `/v2/matches/{id}` as a candidate), re-route through the verified Phase 2 chain.
- [ ] **Replace `divisions[]=VCT` query param** with client-side filter — Phase 2 STATE.md "in-flight bug fixes" notes this server-side filter doesn't work; use `RIBGG_TIER_FILTER` constant.
- [ ] **Drop `hasSeries=true` URL param** if present — Phase 2 STATE.md notes 30s server timeouts on every page; removed in commit `fafa6ae`.
- [ ] **Replace bo3.gg / vlr.gg endpoint code paths** with `# Phase 5 deferred per SPEC out-of-scope` comment and skip — Phase 3 is rib.gg-only.
- [ ] **Apply defensive `.get()` + early-return** for null-roster matches (Phase 2 fix in `transform_match_to_rows`, commit `fafa6ae`).

**`vision_parser.py` specifically:**
- [ ] **Replace any GPU-specific code paths** (CUDA detection, GPU model loads) with CPU-only ONNX runtime (`onnxruntime.InferenceSession(model_path, providers=["CPUExecutionProvider"])`). D-03 + REQ-cloud-vm.
- [ ] **Pin the model path** to `models/en_PP-OCRv4_rec_infer.onnx` and document the download URL + checksum in a `models/README.md` or `scripts/download_models.py`.
- [ ] **Wire a `prefilter` step** before tesseract: PIL crop to known HUD bbox, optional contrast normalization (`PIL.ImageOps.autocontrast(im)`). Tesseract on raw 1080p frames is ~2s; on a cropped + autocontrast 200×50 region is < 200ms. See Pitfall 1.
- [ ] **Map salvage-source frame fetcher** (likely `cv2.VideoCapture`) to a pluggable `FrameSource` Protocol — production uses YouTube-DL-streaming or similar; tests use a `FakeFrameSource` that yields canned PNGs. Frame-source plumbing is OUT of strict scope (synthetic E2E mocks it) but the seam matters.

**Key insight:** the salvage files are reference implementations; the executor takes them as **shape templates**, not as drop-in modules. Every line copied across must pass through this delta.

## Runtime State Inventory

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — Phase 3 introduces NEW stored state (`data/event_log/{match_id}.jsonl`, `data/metrics/{match_id}.metrics.jsonl`). No prior state to migrate. `models/round_conclusion.json` is read-only consumed (Phase 2 artifact). | Add `data/event_log/` and `data/metrics/` to `.gitignore` (per CONTEXT integration_points: gitignored). |
| Live service config | None — no external service config needs updating for Phase 3. Twitter rules are pushed at startup, idempotently (see Pattern 3). | None. Twitter rule sync is at-startup; no migration. |
| OS-registered state | None — no Windows Task Scheduler / cron / systemd / pm2 entries; the bot runs as a foreground process. | None — confirmed. |
| Secrets/env vars | NEW: `TWITTER_BEARER_TOKEN` env var (read by `text_listener.py`). Phase 4's Kalshi keys are independent. NO legacy env vars to rename. | Document in `.env.example` (do NOT add `.env` to git per CRule equivalent in CON-secrets-handling). The listener degrades to no-op when missing — see Pattern 3. |
| Build artifacts | NEW: `models/en_PP-OCRv4_rec_infer.onnx` (7.66 MB) — must be downloaded once, NOT committed to git (size policy). Existing `models/round_conclusion.json` (Phase 2) is committed via `.gitignore` exception. | Add `scripts/download_models.py` (or `Makefile` target) that downloads the ONNX checkpoint with a SHA-256 verification. Add `models/*.onnx` to `.gitignore` with no exception. CI must run the download step before tests that hit OCR (or skip OCR tests if the file isn't present). |

**Nothing found for Stored data, Live service config, OS-registered state — verified by code review of `src/`, `scripts/`, and `.planning/`.**

## Common Pitfalls

### Pitfall 1: Tesseract returns empty string on raw 1080p HUD frames

**What goes wrong:** `pytesseract.image_to_string(full_1080p_frame)` runs in ~2 seconds on Windows AND often returns empty/garbage text because the surrounding HUD pixels confuse the page-segmentation model.

**Why it happens:** Tesseract's default `--psm 3` (auto-page-segmentation) assumes a document-style layout. A Valorant HUD has tiny isolated text on busy backgrounds.

**How to avoid:**
1. Crop to a known HUD bounding box (`PIL.Image.crop((x0, y0, x1, y1))`) BEFORE OCR. The bbox coordinates differ per HUD element; declare them as constants:
   ```python
   HUD_BBOX_SCORE_BANNER:    Final[tuple[int,int,int,int]] = (820, 20, 1100, 80)
   HUD_BBOX_KILL_FEED:       Final[tuple[int,int,int,int]] = (1500, 100, 1900, 400)
   HUD_BBOX_BOMB_ICON:       Final[tuple[int,int,int,int]] = (940, 110, 980, 150)
   HUD_BBOX_ROUND_END_BANNER:Final[tuple[int,int,int,int]] = (700, 400, 1220, 500)
   ```
   Pin these via inspection of a few archived VOD frames (out-of-scope to research; planner should add a one-task probe to confirm against a real frame, OR the executor calibrates them during synthetic-test wiring against the FakeFrameSource fixture).
2. Use `--psm 7` (single text line) for score banner / round-end banner; `--psm 8` (single word) for bomb-icon binary indicator.
3. `PIL.ImageOps.autocontrast(im)` before pass-in — Valorant's variable lighting on the HUD borders makes constant-threshold binarization brittle.

**Warning signs:** OCR latency spikes > 500ms, OR per-target accuracy benchmark < 80% on canned frames.

### Pitfall 2: ONNX inference returns low-confidence top-1 → false event emission

**What goes wrong:** The CNN's softmax peak sits at e.g. 0.35 — the model isn't confident which character it sees. If you accept it as "kill at slot 3", the arbiter commits a phantom event.

**Why it happens:** Kill-feed frames during action are heavily occluded; not every frame has resolvable text.

**How to avoid:**
1. Define `OCR_KILLFEED_CONF_THRESHOLD: Final[float] = 0.7` in constants.
2. After ONNX inference, check `softmax_top1_prob >= OCR_KILLFEED_CONF_THRESHOLD`. Below threshold: emit NO event (caller drops the frame).
3. Log `ocr_low_confidence_drops` counter to the metrics file for Phase 5 calibration of the threshold.

**Warning signs:** Twitter-only kill events get quarantined more often than they should — implies OCR is staying silent on real kills (threshold too high). Phase 5 calibrates.

### Pitfall 3: rib.gg cooldown lasting longer than 5s poll cycle

**What goes wrong:** The Phase 2 5-failure cooldown can pause the poller for 60+ seconds. During that window the kill-switch staleness threshold (5s) trips and Phase 4 cancels all quotes.

**Why it happens:** Phase 2's resilience is designed for batch ETL where slow is OK. Phase 3 is real-time; cooldown is the WRONG behavior.

**How to avoid:**
1. The rib.gg poller MUST emit a `t_observed` heartbeat to the arbiter EVERY successful poll, regardless of whether content changed. Stale heartbeat = staleness kill-switch trips correctly.
2. On consecutive failures (≥3), the poller emits a `degraded: true` flag (NEW source). The arbiter logs but does not commit. Phase 4 reads this flag (later); for Phase 3, just log to metrics.
3. Cap the per-failure backoff at 10s (NOT 60s) for the live poller — `_ribgg_wait` returns `min(2 ** (attempt - 1), 30.0)` in Phase 2; for live, override to `min(2 ** (attempt - 1), 10.0)` via a planner-provided wait function (or via `RIBGG_LIVE_BACKOFF_CAP_S = 10.0`).

**Warning signs:** kill-switch (b) trips during synthetic E2E with fake-but-flaky rib.gg fixture.

### Pitfall 4: ProactorEventLoop + ThreadPoolExecutor signal handling under Ctrl+C on Windows

**What goes wrong:** Pressing Ctrl+C in a Windows terminal running the bot may leave OCR worker threads orphaned, the asyncio loop closed before `await session.close()` runs → `RuntimeError: Event loop is closed` during process teardown.

**Why it happens:** ProactorEventLoop's signal handling differs from SelectorEventLoop. The default Python 3.11 behavior on Windows is to deliver `KeyboardInterrupt` to the main coroutine cleanly, BUT only if the executor has been explicitly shut down.

**How to avoid:**
```python
async def main() -> None:
    pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ocr")
    try:
        async with aiohttp.ClientSession() as session:
            # ... run arbiter, sources, engine driver ...
            ...
    finally:
        pool.shutdown(wait=True, cancel_futures=False)
        # cancel_futures=False ensures in-flight OCR completes (≤200ms wait).

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # Eat the signal cleanly; suppress traceback in dev.
        pass
```
Do NOT swap to `SelectorEventLoop` on Windows — `aiohttp` requires `Proactor` for full functionality.

**Warning signs:** Tests pass but a manual Ctrl+C run prints a traceback. Synthetic E2E test should NOT exercise signal handling — that's a Phase 5 concern.

### Pitfall 5: Twitter rate-limited connection drops

**What goes wrong:** Twitter v2 streaming silently drops the connection after 60–120s when rate-limited; if you don't reconnect, the listener stops emitting forever.

**Why it happens:** The streaming endpoint enforces per-minute and per-hour rate limits independently of the rule character budget.

**How to avoid:**
1. tweepy's `AsyncStreamingClient(max_retries=10, wait_on_rate_limit=True)` (Pattern 3 above) handles this — exponential backoff with rate-limit awareness.
2. Override `on_disconnect()` to log the disconnect AND increment a metric (`twitter_disconnects_total`). Phase 5 will alarm on > N disconnects/hour.
3. NEVER set `max_retries=None` (default `inf`) in production — pin to a finite number so the listener doesn't loop forever silently.

**Warning signs:** Twitter is the only source emitting; suddenly arbiter sees zero Twitter events for 5+ minutes mid-match.

### Pitfall 6: asyncio task starvation — OCR slower than its cadence

**What goes wrong:** Kill-feed cadence is 100ms but if the ThreadPoolExecutor pool is saturated (2 workers, both busy with previous frames), the next frame submits to a queue that drains FIFO; effective cadence drops to whatever the underlying OCR latency is. At 80ms inference, throughput is ~25 fps with 2 workers — fine. At 150ms (busy frame), throughput is ~13 fps — kill-feed cadence breaks.

**Why it happens:** `ThreadPoolExecutor` doesn't drop queued work; it backs up unboundedly.

**How to avoid:**
1. Use a bounded queue: `loop.run_in_executor(pool, ...)` returns an `asyncio.Future`; in the OCR scheduler coroutine, check `pool._work_queue.qsize() < OCR_BACKLOG_MAX` (NEW constant, recommend 4) before dispatching. If saturated, DROP the frame and log `ocr_dropped_frames_total`.
2. Alternative: use `asyncio.Semaphore(2)` to gate concurrent OCR submissions explicitly — cleaner and doesn't reach into the executor's private queue.
3. In the synthetic E2E test, assert `ocr_dropped_frames_total == 0` to ensure the test is exercising the happy path.

**Warning signs:** OCR p99 latency >> p50; per-target cadence jitter > ±10% (REQ-ocr-pipeline acceptance fails).

### Pitfall 7: dataclass `replace()` does NOT honor `slots=True` in Python 3.11 cleanly

**What goes wrong:** `dataclasses.replace(state, x=1)` works on a `slots=True` frozen dataclass on 3.11, BUT only if the dataclass has no `__post_init__`, no inherited fields with defaults, and no field with a `field(default_factory=...)` that takes args. If any constraint is violated, you get a `TypeError: __init__() got an unexpected keyword argument 'x'` or a missing-attribute error.

**Why it happens:** `replace()` introspects `__init__` signature; slots=True changes the descriptor layout subtly.

**How to avoid:**
1. Keep `MatchState` simple: positional args only, no `__post_init__`, defaults via `= 0` literals or `field(default_factory=time.time)`.
2. Test in `tests/state/test_match_state.py`: `assert dataclasses.replace(some_match_state, a_round=5).a_round == 5` — a one-liner that catches this regression.

**Warning signs:** `dataclasses.replace` raises `TypeError` at runtime; mypy --strict catches some but not all of these.

### Pitfall 8: Six-stage timestamps as `Optional[float]` confuse the JSONL parser

**What goes wrong:** Phase 4 fills `t_theo_computed` and `t_quote_sent` as a **second JSONL line** keyed by `seq_id` (per D-02). If the writer/reader assumes one line per seq_id, the metrics replay breaks.

**Why it happens:** D-02 chose append-only follow-up lines, not in-place mutation.

**How to avoid:**
1. The Phase 3 JSONL line for committed events emits `t_theo_computed: null` and `t_quote_sent: null` (literal nulls).
2. Phase 4 (later) appends a second line with shape `{"seq_id": N, "t_theo_computed": ..., "t_quote_sent": ...}` and NO other fields. The reader merges by seq_id.
3. Document this convention in a docstring at the top of `arbiter.py`. Phase 4 plan picks it up directly.
4. Replay tooling joins on seq_id at read time; idempotent if Phase 4 hasn't run yet.

**Warning signs:** Phase 5 latency analysis script crashes when running on a Phase-3-only metrics file.

## Code Examples

### MatchState v2 dataclass

```python
# src/state/match_state.py
"""Phase 3 versioned MatchState — moved from src/pricing/data.py per D-14.

Frozen+slots invariant preserved (D-01). Single mutator: with_update().
Caller (sole writer = arbiter) bumps seq_id and last_updated_ts atomically.

Fields (25 total = 17 Phase 1 + 8 Phase 3):
  Phase 1 (per src/pricing/data.py:60):
    match_id, team_a, team_b, map_pool, map_idx, a_map_score, b_map_score,
    a_round, b_round, side_orient, map_side_orients, map_winners,
    pistol_winner_a, numerical_diff, bomb_planted, side, econ_bucket
  Phase 3 (REQ-match-state-engine):
    seq_id, last_updated_ts, players_alive_a, players_alive_b,
    ults_a, ults_b, time_left_s, econ_a, econ_b
"""
from __future__ import annotations
import time
from dataclasses import dataclass, field, replace
from typing import Any, Optional, Self

@dataclass(frozen=True, slots=True)
class MatchState:
    # --- Phase 1 fields (verbatim from src/pricing/data.py) ---
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
    numerical_diff: int
    bomb_planted: bool
    side: str
    econ_bucket: str
    # --- Phase 3 additions ---
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
        diffs.pop("seq_id", None)
        diffs.pop("last_updated_ts", None)
        return replace(self, seq_id=self.seq_id + 1, last_updated_ts=time.time(), **diffs)
```

### EventLogLine + JSONL writer

```python
# src/ingestion/event_log.py
import json
import time
from pathlib import Path
from typing import Any, Final, Optional, TextIO

from src.config.constants import EVENT_LOG_DIR  # NEW: Path("data/event_log")

_FLUSH_EVERY_N: Final[int] = 32

class EventLogWriter:
    """Append-only JSONL writer; one file per match_id."""

    def __init__(self, match_id: str) -> None:
        EVENT_LOG_DIR.mkdir(parents=True, exist_ok=True)
        self._path: Path = EVENT_LOG_DIR / f"{match_id}.jsonl"
        self._fh: TextIO = self._path.open("a", buffering=1 << 16, encoding="utf-8")
        self._n_since_flush: int = 0

    def write_committed(
        self,
        seq_id: int,
        t_observed: float,
        t_ingested_ns: int,
        t_arbited_ns: int,
        t_state_committed_ns: int,
        source: str,
        event_type: str,
        fields_changed: dict[str, Any],
    ) -> None:
        line = {
            "seq_id": seq_id,
            "t_observed": t_observed,
            "t_ingested": t_ingested_ns / 1e9,
            "t_arbited": t_arbited_ns / 1e9,
            "t_state_committed": t_state_committed_ns / 1e9,
            "t_theo_computed": None,
            "t_quote_sent": None,
            "source": source,
            "event_type": event_type,
            "fields_changed": fields_changed,
        }
        self._fh.write(json.dumps(line, separators=(",", ":")) + "\n")
        self._maybe_flush()

    def write_quarantined(
        self,
        source: str,
        event_type: str,
        fields_proposed: dict[str, Any],
        t_observed: float,
        reason: str,
    ) -> None:
        line = {
            "seq_id": None,
            "quarantined": True,
            "quarantine_reason": reason,
            "source": source,
            "event_type": event_type,
            "fields_proposed": fields_proposed,
            "t_observed": t_observed,
        }
        self._fh.write(json.dumps(line, separators=(",", ":")) + "\n")
        self._maybe_flush()

    def _maybe_flush(self) -> None:
        self._n_since_flush += 1
        if self._n_since_flush >= _FLUSH_EVERY_N:
            self._fh.flush()
            self._n_since_flush = 0

    def close(self) -> None:
        self._fh.flush()
        self._fh.close()
```

### Synthetic E2E test scaffold

```python
# tests/ingestion/test_e2e.py
"""SPEC acceptance #8 — synthetic E2E for Phase 3.

Drives fake rib.gg + fake OCR + fake Twitter through the full pipeline:
  sources → arbiter → MatchState mutation → live_theo
Asserts:
  1. seq_id strictly monotonic across the run
  2. theo_series stays in [0.01, 0.99] and is non-degenerate
  3. p50 latency from t_observed → t_state_committed < 500ms
  4. metrics file is parseable
"""
from __future__ import annotations
import asyncio
import json
import statistics
import time
from pathlib import Path

import pytest

# pytest-asyncio asyncio_mode = "auto" -> async test functions run automatically.

@pytest.mark.asyncio
async def test_e2e_synthetic_50_events(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TWITTER_BEARER_TOKEN", "")  # force listener to no-op
    # Override EVENT_LOG_DIR / METRICS_LOG_DIR to tmp_path.
    from src.ingestion.arbiter import Arbiter
    from src.state.match_state import MatchState
    # ... (construct minimum valid MatchState seed, mock sources, instantiate arbiter)

    seed = MatchState(...)  # 17 phase-1 fields + 8 phase-3 defaults
    queue: asyncio.Queue = asyncio.Queue()
    # ... wire up arbiter, mock sources to push 50 ArbiterPending each at 100ms ...

    latencies_ms: list[float] = []
    seq_ids: list[int] = []
    state = seed

    arbiter_task = asyncio.create_task(arbiter.run())
    try:
        # Drive 50 synthetic events.
        for ev in synthetic_events:
            await arbiter.submit(ev)
        # Wait for queue to drain.
        for _ in range(50):
            ce = await asyncio.wait_for(queue.get(), timeout=1.0)
            seq_ids.append(ce.confirmed_seq_id)
            latencies_ms.append((ce.t_state_committed - ce.t_ingested) * 1000)
    finally:
        arbiter_task.cancel()
        try:
            await arbiter_task
        except asyncio.CancelledError:
            pass

    # Assertion 1: strict monotonicity.
    assert seq_ids == sorted(seq_ids) and len(set(seq_ids)) == len(seq_ids)
    # Assertion 2: theo non-degeneracy via live_theo on final state.
    from src.pricing.live_theo import LiveTheoEngine
    from src.pricing.data import HalfRates
    half = HalfRates.from_json("data/half_win_rates.json")
    engine = LiveTheoEngine(half)
    out = engine(final_state)
    assert 0.01 < out.theo_series < 0.99
    # Assertion 3: p50 latency budget.
    p50 = statistics.median(latencies_ms)
    assert p50 < 500.0, f"p50 latency {p50}ms exceeds 500ms budget"
    # Assertion 4: metrics file parseable.
    metrics_lines = (tmp_path / "metrics" / "synthetic.metrics.jsonl").read_text().splitlines()
    for line in metrics_lines:
        json.loads(line)  # raises if malformed
```

### pyproject.toml additions (target patch)

```toml
# Add to [project].dependencies:
"aiohttp>=3.10,<4",
"tweepy>=4.15,<5",
"onnxruntime>=1.20,<1.22",
"pytesseract>=0.3.13,<0.4",
"Pillow>=11,<13",
"numpy>=1.26,<3",
# Optional but recommended:
"structlog>=24,<26",

# Add to [dependency-groups].dev:
"pytest-asyncio>=0.24,<2",
"pytest-benchmark>=4,<6",

# Add to [tool.pytest.ini_options]:
asyncio_mode = "auto"

# Add to [[tool.mypy.overrides]] (after the src.pricing.* override):
[[tool.mypy.overrides]]
module = "src.state.*"
strict = true
warn_return_any = true

# Add to [[tool.mypy.overrides]] for ignoring missing stubs:
[[tool.mypy.overrides]]
module = ["pytesseract", "PIL.*"]
ignore_missing_imports = true
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `pytest-asyncio` `auto` mode warning when no `asyncio_mode` set | `pytest-asyncio` 1.0+ requires explicit `asyncio_mode` config | 2025-Q1 (pytest-asyncio 1.0 release) | Always set `asyncio_mode = "auto"` in pyproject.toml; otherwise warning becomes error in 2.0. |
| Twitter API v1.1 streaming (free) | Twitter API v2 streaming (paid: Pro $5k/mo or Enterprise) | 2023-Q2 retirement of v1.1 | Free streaming is gone. Phase 3 listener MUST degrade to no-op on missing token; CI cannot exercise live Twitter. |
| `asyncio.wait_for(coro, timeout)` | `async with asyncio.timeout(t):` | Python 3.11 (PEP 654) | Use the new context manager — safer cancellation semantics. |
| ProactorEventLoop BPO #23846 BlockingIOError | Fixed in Python 3.7+ | 2019-01 | No mitigation needed in 3.11. |
| PaddleOCR via paddlepaddle (huge: ~500 MB install) | ONNX export of small `en_PP-OCRv4_rec_infer.onnx` (7.66 MB) | 2024-Q1 | Run on `onnxruntime` CPU only; no paddlepaddle dep. |
| `dataclasses.replace` slots=True bugs | Mostly resolved in 3.10+ | Python 3.10 | Pitfall 7 still applies for unusual layouts; constrain MatchState to simple shapes. |
| Tesseract Windows binary install (multi-step) | Single MSI installer + auto-PATH | UB Mannheim builds, ongoing | tesseract 5.5.0 MSI installs to `C:\Program Files\Tesseract-OCR\` cleanly; already present on dev machine. |

**Deprecated / outdated:**
- **`tweepy.StreamingClient`** (sync) — works but mixes sync threads with our asyncio loop; prefer `AsyncStreamingClient`.
- **`onnxruntime` < 1.18** — doesn't fully support opset 19 used by some PaddleOCR exports. Pin `>=1.20`.
- **bo3.gg `divisions[]=VCT` query param** — broken server-side per Phase 2 STATE.md; client-side filter only.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | HUD bounding-box coordinates (`HUD_BBOX_*` Pitfall 1) are pinnable from a few archived VOD frames | Pitfall 1 | LOW — planner can add a single-task probe; if bbox doesn't generalize across VOD providers, the executor adds a per-source override map. Worst case: synthetic E2E uses fake bboxes against fake frames; production calibration becomes a Phase 5 task. |
| A2 | Tesseract `--psm 7` (single line) suffices for score banner / round-end banner; `--psm 8` (single word) for bomb icon | Pitfall 1 | LOW — pytesseract supports both; if accuracy is < 90% on canned frames, executor switches to `--psm 13` (raw line). Detected by per-target benchmark. |
| A3 | `breezedeus/cnocr-ppocr-en_PP-OCRv4` model accuracy on Valorant kill-feed text is ≥ 80% | Don't Hand-Roll OCR row | MEDIUM — the model was trained on document text, not gameplay HUD. If accuracy is sub-80% on canned frames, the planner has fallback options: (a) tesseract `--psm 8` for kill feed too (200-300ms; uses up the kill-feed budget but works), (b) pin a different ONNX checkpoint (e.g., `aigchacker/OCR/ch_PP-OCRv4_rec_infer.onnx` though Chinese-trained), (c) defer kill-feed CNN to Phase 5 and ship Phase 3 with tesseract for all four targets. The kill-feed cadence is 100ms; tesseract's 100-300ms straddles the budget — researcher recommends NOT relying on tesseract for kill-feed cadence. **User should confirm: is missing the 100ms kill-feed budget acceptable as a Phase 3 fallback if A3 fails?** |
| A4 | Twitter `TWITTER_BEARER_TOKEN` will be unavailable in CI, and the listener degrade-to-no-op pattern (Pattern 3) is the right behavior | Standard Stack tweepy row, Pitfall 5 | LOW — degrade-to-no-op is the standard pattern for credential-gated services; the synthetic E2E test injects a mocked stream so paid Twitter is never CI-required. |
| A5 | Per-event-type window sizes (100ms for kill/bomb/numerical "same frame") are correct readings of DEC-006 | Pattern 4 tick() | LOW — DEC-006 says "same frame" without numeric window; researcher inferred 100ms = kill-feed cadence. If the planner / user wants tighter (50ms) or looser (200ms), it's one constant change. **User should confirm before plan-phase.** |
| A6 | `time.monotonic_ns()` 100ns resolution on Windows is sufficient for sub-500ms latency math | Pattern 5 timestamps | LOW — verified Win10+ resolution; confirmed by Microsoft KB. |
| A7 | The static Twitter rule list in D-07 has < 25 rules total | Pattern 3 + Pitfall 5 | LOW — D-07 lists 5 hashtags + caster/league/team-orgs (probably 10-20 accounts) = ~25-30 rules. Pro tier supports 1000 rules / 1024 chars; well within limit even at Enterprise minimum 25. **User MUST confirm Twitter API access tier before live deployment** but Phase 3 ships against the no-op fallback. |
| A8 | The 5-failure cooldown override (10s cap, NOT 60s) for the live rib.gg poller is acceptable | Pitfall 3 | LOW — Phase 2's 60s cap was for batch ETL; live cap of 10s simply means kill-switch (b) trips slightly earlier on extended outages, which is correct behavior. |
| A9 | The kill-feed "1 CV-source if kill-feed cross-confirms within same frame" rule (DEC-006) means: a single OCR-source `kill` event auto-commits within the kill-feed window; Twitter-only `kill` events quarantine | Pattern 4 `_eval_kill_rule` | MEDIUM — researcher's reading: the rule is asymmetric (CV trusted, text not). If user intended "OCR + kill-feed-text-confirm", that's a different rule (and would never fire in practice since Twitter's text isn't structured kill data). **User should confirm during plan-phase.** |

If the user wants any of A3 / A5 / A9 confirmed, they should resolve in plan-phase (or a brief discuss-phase amendment) before the executor builds against them.

## Open Questions

1. **HUD bounding-box pinning (A1).** Static VOD-source-dependent or per-source override?
   - What we know: bboxes vary slightly between YouTube broadcast and Twitch HLS feeds.
   - What's unclear: Whether Phase 3 needs a configurable `bbox_provider` (per-source override map) or a single static set.
   - Recommendation: Plan a single static set in `src/config/constants.py` for Phase 3; defer per-source override to Phase 5 if production VOD source changes.

2. **Round-end "soft commit, hard-confirmed by next score update" mechanic (DEC-006 round-end rule).** Does this need a state machine, or is "always commit immediately, mark `_round_end_soft=True`, downstream ignores" enough?
   - What we know: Phase 1's `live_theo` doesn't read a soft-vs-hard flag.
   - What's unclear: Whether Phase 4 quoter wants the distinction.
   - Recommendation: Phase 3 commits immediately with `_round_end_soft=True`; Phase 4 plan can revisit. Documented as Pattern 4 `_eval_round_end_rule`.

3. **OCR ONNX model checkpoint accuracy on Valorant kill-feed.** Will `en_PP-OCRv4_rec_infer.onnx` actually hit 80%+ word accuracy on real gameplay frames?
   - What we know: It's English-trained, Apache 2.0, 7.66 MB, common in PaddleOCR ecosystem.
   - What's unclear: Performance on stylized/distorted in-game text overlays.
   - Recommendation: Plan adds a minimal "frame accuracy probe" task (~5 hand-labeled frames) before committing to the full pipeline. If accuracy < 70%, fall back to tesseract for kill-feed (degrades to ~250ms cadence — Phase 5 calibration redresses). See Assumption A3.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11 | All Phase 3 code | ✓ | 3.11.6 | — |
| `requests` (already installed) | rib.gg poller (sync-in-executor option) | ✓ | 2.33.1 | — |
| `tenacity` (already installed) | rib.gg retry decorator | ✓ | 8.5+ pinned in pyproject | — |
| `aiohttp` | Twitter stream backbone, optional rib.gg async | ✗ (not yet) | n/a | Install per pyproject patch |
| `tweepy` | Twitter v2 streaming | ✗ (not yet) | n/a | Install per pyproject patch; CI degrades to no-op |
| `onnxruntime` (CPU) | Kill-feed OCR | ✗ (not yet) | n/a | Install per pyproject patch |
| `pytesseract` | Score/bomb/round-end OCR | ✗ (not yet) | n/a | Install per pyproject patch |
| Tesseract binary | pytesseract backend | ✓ | 5.5.0.20241111 at `C:\Program Files\Tesseract-OCR\tesseract.exe` | — |
| `Pillow` | Image decode | ✓ (already installed locally) | 11.2.1 | — |
| `numpy` | Tensor build | ✓ (already installed locally) | 1.26.2 | — |
| `pytest-asyncio` | Async tests | ✗ (not yet) | n/a | Install per pyproject patch |
| `pytest-benchmark` | OCR p50 benchmark | ✗ (not yet) | n/a | Install per pyproject patch (or fall back to `statistics.median` if not installed) |
| `breezedeus/cnocr-ppocr-en_PP-OCRv4/en_PP-OCRv4_rec_infer.onnx` | Kill-feed inference | ✗ (must download) | 7.66 MB, Apache 2.0 | Plan adds `scripts/download_models.py` step; CI runs it before OCR tests |
| `TWITTER_BEARER_TOKEN` env var | Twitter v2 auth | ✗ (not set) | — | Listener degrades to no-op (Pattern 3) |

**Missing dependencies with no fallback:** None — every dependency either has a fallback or is install-able.

**Missing dependencies with fallback:**
- All Python deps: `uv add ...` per pyproject patch.
- ONNX model: download script.
- Twitter token: degrade to no-op.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | `pytest>=8.0` (already pinned) + `pytest-asyncio>=0.24,<2` (NEW) + `pytest-benchmark>=4,<6` (NEW) + `hypothesis>=6.100` (already pinned) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` — add `asyncio_mode = "auto"` |
| Quick run command | `pytest tests/ -x -k "not benchmark and not e2e"` |
| Full suite command | `pytest tests/` |
| Phase gate | `pytest tests/` GREEN, including `tests/ingestion/test_e2e.py` and `tests/ingestion/test_ocr.py::test_ocr_benchmark_50_frames`. `mypy --strict src/pricing/` AND `mypy --strict src/state/` clean. `ruff check src/ tests/ scripts/` clean. |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REQ-match-state-engine | `seq_id` strict monotonicity over 1000 random `with_update` calls | property (hypothesis) | `pytest tests/state/test_match_state.py::test_seq_id_monotonic_1000_mutators -x` | ❌ Wave 0 |
| REQ-match-state-engine | `with_update` strips caller-provided `seq_id`/`last_updated_ts` | unit | `pytest tests/state/test_match_state.py::test_with_update_strips_seq_id -x` | ❌ Wave 0 |
| REQ-match-state-engine | JSONL replay determinism: write 1000 events, replay → same final state | property | `pytest tests/state/test_match_state.py::test_jsonl_replay_round_trip -x` | ❌ Wave 0 |
| REQ-scoreboard-polling | Monkeypatched `requests.get` yields fixture series → poller emits N typed events at 5s cadence | integration | `pytest tests/ingestion/test_scoreboard.py -x` | ❌ Wave 0 |
| REQ-scoreboard-polling | Poller honors `Connection: close` + `_ribgg_wait` (Phase 2 patterns) | unit | `pytest tests/ingestion/test_scoreboard.py::test_resilience_patterns -x` | ❌ Wave 0 |
| REQ-ocr-pipeline | 50-frame median decode + inference < 100ms per target | benchmark | `pytest tests/ingestion/test_ocr.py::test_ocr_benchmark_50_frames -x` | ❌ Wave 0 |
| REQ-ocr-pipeline | Per-target cadence within ±10% jitter under sustained load | integration | `pytest tests/ingestion/test_ocr.py::test_per_target_cadence -x` | ❌ Wave 0 |
| REQ-ocr-pipeline | Below `OCR_KILLFEED_CONF_THRESHOLD`: no event emitted (Pitfall 2) | unit | `pytest tests/ingestion/test_ocr.py::test_low_confidence_drop -x` | ❌ Wave 0 |
| REQ-text-listener | Mocked Twitter stream → typed soft-events emitted | integration | `pytest tests/ingestion/test_text_listener.py -x` | ❌ Wave 0 |
| REQ-text-listener | Twitter-only state-change update is QUARANTINED (never committed) | unit | `pytest tests/ingestion/test_text_listener.py::test_twitter_only_quarantined -x` | ❌ Wave 0 |
| REQ-text-listener | Missing `TWITTER_BEARER_TOKEN` → listener no-ops, no exception | unit | `pytest tests/ingestion/test_text_listener.py::test_no_token_noop -x` | ❌ Wave 0 |
| REQ-cross-source-arbiter | Property test: enumerate `(source, event_type) ∈ {ribgg,ocr,twitter} × {score,kill,bomb,numerical,round_end}` (15 combos); arbiter rule fires correctly per DEC-006 | property | `pytest tests/ingestion/test_arbiter.py::test_rule_matrix -x` | ❌ Wave 0 |
| REQ-cross-source-arbiter | Quarantined events appear in JSONL with `quarantined: true`, `seq_id: null` | unit | `pytest tests/ingestion/test_arbiter.py::test_quarantine_log_shape -x` | ❌ Wave 0 |
| REQ-cross-source-arbiter | Score-change rule: 2 ribgg + 1 ocr within 2s → fire; 1 source → quarantine; 3 sources but spread > 2s → quarantine | property | `pytest tests/ingestion/test_arbiter.py::test_score_change_window -x` | ❌ Wave 0 |
| REQ-latency-instrumentation | Every confirmed event in JSONL has all six timestamp fields (Phase 4 fields = None) | unit | `pytest tests/ingestion/test_arbiter.py::test_six_stage_timestamps -x` | ❌ Wave 0 |
| REQ-latency-instrumentation | Metrics file is parseable line-by-line; ts ordered ascending by `t_observed` | unit | `pytest tests/ingestion/test_arbiter.py::test_metrics_parseable -x` | ❌ Wave 0 |
| REQ-end-to-end-latency | E2E synthetic ≥30 events: p50 `t_observed → t_state_committed` < 500ms | integration | `pytest tests/ingestion/test_e2e.py::test_e2e_p50_latency -x` | ❌ Wave 0 |
| REQ-end-to-end-latency | E2E synthetic: `theo_series` is non-degenerate (∈ (0.01, 0.99), not stuck at 0.5) on final state | integration | `pytest tests/ingestion/test_e2e.py::test_e2e_theo_non_degenerate -x` | ❌ Wave 0 |

### Sampling Rate (Nyquist)

The PLAN must include the following minimum sampling counts as **must_haves**:

- **REQ-match-state-engine — seq_id monotonicity property test:** ≥ 1000 calls (`@given(st.lists(st.dictionaries(st.text(), st.integers()), min_size=1000, max_size=1000))`). Hypothesis runs 100 examples by default; pin `@settings(max_examples=20)` for ergonomic test runtimes (still 20×1000 = 20k mutations exercised).
- **REQ-cross-source-arbiter — rule matrix property test:** enumerated 15 combos (3 sources × 5 event types) plus 5 multi-source combos; minimum 100 hypothesis examples per combo (`@settings(max_examples=100)`). Total: 20 combos × 100 = 2000 arbiter executions.
- **REQ-cross-source-arbiter — score-change window property test:** hypothesis-generated time offsets ∈ {-3.0s, -2.5s, ..., +2.5s, +3.0s} relative to a reference event; ≥ 200 examples covering boundary, in-window, out-of-window.
- **REQ-ocr-pipeline — per-frame benchmark:** ≥ 50 frames per target (4 targets × 50 = 200 frame inferences); pytest-benchmark default `--benchmark-min-rounds=5` is enough for CI; specify `--benchmark-min-rounds=50` for the acceptance benchmark.
- **REQ-end-to-end-latency — synthetic E2E:** ≥ 30 events (SPEC requirement). Recommend 50 to reduce p50 noise; one full test invocation.
- **REQ-state JSONL replay round-trip:** ≥ 1000 events written + replayed; assert final state equality.

### Per-task / per-wave / phase gate

- **Per task commit:** `pytest tests/ -x -k "not benchmark and not e2e"` (skips benchmark + E2E for fast feedback)
- **Per wave merge:** `pytest tests/` (full suite including benchmark + E2E)
- **Phase gate:** `pytest tests/` GREEN, `mypy --strict src/pricing/ src/state/` clean, `ruff check src/ tests/ scripts/` clean, AND all Phase 1 + 2 tests still GREEN (regression).

### Wave 0 Gaps

Every test file in the table above is NEW. Wave 0 of the plan must create, in order:

- [ ] `pyproject.toml` patch — add deps + `asyncio_mode = "auto"` + new mypy override block for `src.state.*`
- [ ] `tests/ingestion/__init__.py` — empty
- [ ] `tests/state/__init__.py` — empty
- [ ] `tests/ingestion/conftest.py` — fixtures: `mock_ribgg_response`, `fake_ocr_frame_source`, `fake_twitter_stream`
- [ ] `tests/ingestion/fixtures/canned_kill_feed_frames/` — 5 hand-labeled PNGs for the OCR accuracy probe (researcher's A3 mitigation)
- [ ] Wave-0 download script `scripts/download_models.py` — fetches `en_PP-OCRv4_rec_infer.onnx` to `models/`, verifies SHA-256
- [ ] `models/.gitkeep` + `.gitignore` updates for `models/*.onnx` (no exception)
- [ ] `data/event_log/.gitkeep` + `data/metrics/.gitkeep` + `.gitignore` for `data/event_log/` and `data/metrics/`
- [ ] `src/state/__init__.py` — re-exports MatchState
- [ ] `src/ingestion/__init__.py` — empty (or re-exports primary classes)
- [ ] `src/config/constants.py` — add 13 new constants (cadences, windows, thresholds, paths, rule set)
- [ ] `src/ingestion/types.py` — `ArbiterPending`, `ConfirmedEvent`, `EventLogLine`, `MetricsLogLine` dataclasses

## Project Constraints (from CLAUDE.md)

These are the actionable directives the planner MUST honor:

- **CRule 1: Single canonical entry point `live_theo(state) → (theo, vega, confidence)`.** Phase 3 does NOT alter this — only what flows through `state` changes. The arbiter calls `LiveTheoEngine(state)` after every commit; the signature is locked.
- **CRule 11: `mypy --strict` on `src/pricing/`.** Phase 3 EXTENDS strict to `src/state/` per SPEC.constraints. `src/ingestion/` stays gradual (current scoping in `pyproject.toml`).
- **CRule 12: No magic numbers in business logic.** Every new threshold (cadences, arbiter windows, OCR confidence threshold, OCR backlog cap, JSONL flush interval, HUD bboxes if used, Twitter rule set) goes into `src/config/constants.py`.
- **CRule 13: Dry-run by default.** Phase 3 ingestion runs alongside dry-run pricing; Twitter listener degrades to no-op without bearer token; rib.gg poller has read-only API access. The `--live` flag remains a Phase 4 concern.
- **CON-live-state-no-sqlite:** In-memory MatchState + JSONL on disk. NO SQLite for live state. (Phase 2 used SQLite for the offline calibration cache — that's allowed; Phase 3 must not.)
- **CON-mypy-strict-pricing:** Already covered by CRule 11; SPEC extends to `src/state/`.
- **CON-no-magic-numbers:** Already covered by CRule 12.
- **Single canonical implementation per concept.** No duplicate JSON serializers; no duplicate retry decorators; no duplicate timestamp utilities.
- **Salvage discipline:** `vlr_scraper.py`/`rib_scraper.py`/`vision_parser.py` MUST be copied to `reference/` first, then ported. Do NOT import from `thunderedge/` directly.
- **Diff-based commits per task** with `feat()`/`fix()`/`test()`/`docs()` prefixes (Phase 1 + 2 precedent).
- **Atomic move** of MatchState from `src/pricing/data.py` to `src/state/match_state.py` in one commit; all 8+ Phase 1 import sites updated together. (Re-export shim in `src/pricing/data.py` is OK; deletion is OK; mixing is not.)

## Sources

### Primary (HIGH confidence)

- **PyPI registry** (verified live 2026-05-01) for: `aiohttp 3.13.5`, `tweepy 4.16.0`, `onnxruntime 1.25.1`, `pytesseract 0.3.13`, `Pillow 12.2.0`, `numpy 2.4.4`, `pytest-asyncio 1.3.0`, `pytest-benchmark 5.2.3`, `structlog 25.5.0`, `httpx 0.28.1`. cp311-win_amd64 wheels confirmed for all `aiohttp`/`onnxruntime`/`Pillow`/`numpy`. — `pip index versions <pkg>` and `pip install --dry-run`.
- **HuggingFace** (verified live 2026-05-01) for: `breezedeus/cnocr-ppocr-en_PP-OCRv4/en_PP-OCRv4_rec_infer.onnx` 7.66 MB, Apache 2.0. URL: `https://huggingface.co/breezedeus/cnocr-ppocr-en_PP-OCRv4/resolve/main/en_PP-OCRv4_rec_infer.onnx`. Cross-verified: `PaddlePaddle/en_PP-OCRv4_mobile_rec` (no ONNX export, 7.61 MB inference.pdiparams, Apache 2.0); `PaddlePaddle/PP-OCRv4_server_rec` (71.2 MB, too large).
- **Local environment** (verified live 2026-05-01): Python 3.11.6, Tesseract 5.5.0.20241111 at `C:\Program Files\Tesseract-OCR\tesseract.exe` with leptonica-1.85.0. — `where tesseract`, `tesseract --version`.
- **tweepy 4.16 documentation** — `https://docs.tweepy.org/en/stable/asyncstreamingclient.html` for `AsyncStreamingClient` signature, lifecycle hooks (`on_disconnect`, `on_request_error`, etc.).
- **Phase 2 codebase** — `scripts/probe_round_events.py:102-140` (`_ribgg_wait`, `get_json`, `Connection: close` patterns); `src/config/constants.py:180-218` (existing rib.gg constants).

### Secondary (MEDIUM confidence)

- **X Developer Platform docs** — `https://docs.x.com/x-api/posts/filtered-stream/introduction`. Direct fetch surfaced two tier rows (pay-per-use 1000 rules / 1024 chars; Enterprise 25000+ rules / 2048 chars). Free/Basic streaming tiers appear retired; verified via webfetch 2026-05-01. Confirmed Pro tier ($5k/mo) exists via secondary source `wearefounders.uk`. Researcher inference: Phase 3's static rule set fits within any tier; degrade-to-no-op when tier unavailable.
- **Python 3.11 asyncio docs** — `https://docs.python.org/3.11/library/asyncio-eventloop.html` (ProactorEventLoop default on Windows; `asyncio.timeout` PEP 654).
- **PaddleOCR Apache 2.0 license** — verified on `PaddlePaddle/PP-OCRv4_server_rec` and `PaddlePaddle/PP-OCRv4_mobile_rec` HuggingFace cards. Inheritance to `breezedeus/cnocr-ppocr-en_PP-OCRv4` confirmed via that repo's `LICENSE` field.
- **pytest-asyncio 1.x docs** — `https://pytest-asyncio.readthedocs.io/en/stable/reference/configuration.html` for `asyncio_mode = "auto"` semantics.

### Tertiary (LOW confidence — flag for validation)

- **HUD bbox coordinates (Pitfall 1).** No live verification; researcher's coordinates are illustrative. Plan must include a one-task probe to pin them against a real frame, OR the executor inspects an archived VOD frame during Wave 0.
- **A3 — `breezedeus/cnocr-ppocr-en_PP-OCRv4` accuracy on Valorant kill-feed text.** No published benchmark on game HUD; researcher recommends adding a 5-frame accuracy probe to Wave 0.
- **A9 — kill/bomb/numerical "1 CV-source" rule asymmetry.** Researcher's reading of DEC-006; plan-phase or discuss-phase should confirm.

## Metadata

**Confidence breakdown:**
- Standard stack pins: HIGH — verified live against PyPI; no library substitutions needed.
- Architecture patterns: HIGH — D-01..D-07 are locked; researcher pinned mechanics consistent with locks.
- Pitfalls: HIGH on 1, 2, 3, 5, 6, 7; MEDIUM on 4 (Windows signal handling — varies by terminal); HIGH on 8 (D-02 explicit).
- Salvage-port deltas: HIGH — Phase 2 codebase precedent is unambiguous; Phase 1 frozen-dataclass pattern is established.
- ONNX checkpoint: HIGH on URL/license/size (HuggingFace verified); MEDIUM on accuracy on Valorant frames (A3).
- Twitter API tier limits: MEDIUM — X Developer Platform was vague on Free/Basic tiers; researcher confirmed Phase 3 ships against degrade-to-no-op which sidesteps the issue.

**Research date:** 2026-05-01
**Valid until:** 2026-06-01 for stack pins (PyPI updates frequently); 2026-08-01 for architecture/pattern guidance (Phase 3 design is locked); re-verify Twitter API tier table if entering Phase 5 paper-trade with real bearer token.
