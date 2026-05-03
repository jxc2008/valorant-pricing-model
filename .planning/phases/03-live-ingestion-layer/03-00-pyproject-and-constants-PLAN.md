---
id: 03-00-pyproject-and-constants
phase: 03
plan: 0
type: execute
wave: 0
depends_on: []
files_modified:
  - pyproject.toml
  - src/config/constants.py
  - .gitignore
  - data/event_log/.gitkeep
  - data/metrics/.gitkeep
  - models/.gitkeep
  - .env.example
autonomous: true
requirements:
  - REQ-match-state-engine
  - REQ-scoreboard-polling
  - REQ-ocr-pipeline
  - REQ-text-listener
  - REQ-cross-source-arbiter
  - REQ-latency-instrumentation
  - REQ-end-to-end-latency
user_setup: []
must_haves:
  truths:
    - "All 6 new runtime deps + 2 new dev deps appear in pyproject.toml with the pinned version constraints from RESEARCH §Standard Stack"
    - "asyncio_mode = \"auto\" present under [tool.pytest.ini_options]"
    - "[[tool.mypy.overrides]] block exists for src.state.* with strict = true (Phase 3 SPEC.constraints extends mypy strict)"
    - "[[tool.mypy.overrides]] ignore_missing_imports block exists for pytesseract + PIL.*"
    - "Every cadence/window/threshold for Phase 3 lives in src/config/constants.py (CRule 12)"
    - "data/event_log/, data/metrics/, models/*.onnx are gitignored; existing models/round_conclusion.json exception preserved"
    - ".env.example documents TWITTER_BEARER_TOKEN with the no-op fallback note"
  artifacts:
    - path: pyproject.toml
      provides: "deps + asyncio_mode + src.state.* mypy strict override + missing-stubs override"
      contains: "asyncio_mode = \"auto\""
    - path: src/config/constants.py
      provides: "16 new Phase 3 constants (cadences, windows, OCR thresholds, paths, Twitter rules, arbiter timings, backoff cap)"
      contains: "OCR_KILLFEED_CADENCE_MS"
    - path: .gitignore
      provides: "models/*.onnx + data/event_log/ + data/metrics/ exclusions"
      contains: "models/*.onnx"
    - path: data/event_log/.gitkeep
      provides: "directory placeholder for per-match JSONL event log"
    - path: data/metrics/.gitkeep
      provides: "directory placeholder for per-match latency metrics JSONL"
    - path: .env.example
      provides: "documents TWITTER_BEARER_TOKEN env var"
      contains: "TWITTER_BEARER_TOKEN"
  key_links:
    - from: "every Phase 3 src file"
      to: "src/config/constants.py"
      via: "from src.config.constants import ..."
      pattern: "from src.config.constants import"
---

<objective>
Wave 0 infra plan #1 — install Phase 3 stack pins, declare all 16 new constants, lock mypy strict for src/state/, and prepare the on-disk directory layout for the JSONL event log + latency metrics file.

Purpose: every downstream Phase 3 plan imports from these constants and depends on these deps being present and pinned. Doing this in a single small wave-0 plan eliminates per-task pyproject churn during the body waves.

Output: pyproject.toml patched with 8 new deps + asyncio_mode + 2 mypy override blocks; src/config/constants.py extended with the 16 new Phase 3 constants (Final[T]-typed, docstring-cited per existing pattern); .gitignore + .gitkeep + .env.example updates.
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
@.planning/intel/constraints.md
@pyproject.toml
@src/config/constants.py
@.gitignore
@CLAUDE.md

<interfaces>
<!-- Existing pyproject.toml structure (analog for additions) — pyproject.toml:1-106 -->

```toml
[project]
dependencies = [
    "requests>=2.32",
    "tenacity>=8.5",
    "tqdm>=4.66",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "hypothesis>=6.100",
    "ruff>=0.6.0",
    "mypy>=1.11",
]

[tool.pytest.ini_options]
minversion = "8.0"
testpaths = ["tests"]
addopts = ["--strict-markers", "--strict-config", "-ra"]

[[tool.mypy.overrides]]
# CON-mypy-strict-pricing: the math layer must type-check fully.
module = "src.pricing.*"
strict = true
disallow_any_explicit = false
warn_return_any = true
```

<!-- Existing constants block style (analog) — src/config/constants.py:177-238 -->

```python
RIBGG_BASE_URL: Final[str] = "https://be-prod.rib.gg/v1"
"""rib.gg internal API base URL (live-verified 2026-04-30 in 02-RESEARCH.md).

Source: 02-RESEARCH.md §"Pattern 1" / DEC-017. ...
"""
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Patch pyproject.toml — Phase 3 deps + asyncio_mode + mypy override blocks</name>
  <files>pyproject.toml</files>
  <read_first>
    - pyproject.toml (entire file — only 106 lines)
    - .planning/phases/03-live-ingestion-layer/03-RESEARCH.md §Standard Stack (lines 84-133)
    - .planning/phases/03-live-ingestion-layer/03-RESEARCH.md §Code Examples — pyproject.toml additions (lines 967-997)
    - .planning/phases/03-live-ingestion-layer/03-PATTERNS.md §pyproject.toml block (lines 594-633)
  </read_first>
  <action>
Make these exact edits to pyproject.toml:

(a) In `[project].dependencies` (currently lines 10-14), append AFTER the existing `"tqdm>=4.66",` line, in this exact order:
```
    "aiohttp>=3.10,<4",
    "tweepy>=4.15,<5",
    "onnxruntime>=1.20,<1.22",
    "pytesseract>=0.3.13,<0.4",
    "Pillow>=11,<13",
    "numpy>=1.26,<3",
    "structlog>=24,<26",
```
(7 new runtime deps — `structlog` is the optional-but-recommended logger per RESEARCH §Standard Stack lines 102-103.)

(b) In `[dependency-groups].dev` (currently lines 16-23), append AFTER `"mypy>=1.11",`:
```
    "pytest-asyncio>=0.24,<2",
    "pytest-benchmark>=4,<6",
```

(c) In `[tool.pytest.ini_options]` (currently lines 66-73), add a new line `asyncio_mode = "auto"` after the existing `addopts = [...]` block. Place it as a top-level key under the section. Per RESEARCH §State of the Art line 1003 this is required (warning becomes error in pytest-asyncio 2.0).

(d) Append two NEW `[[tool.mypy.overrides]]` blocks AFTER the existing `src.pricing.*` block (which ends at line 106):

```toml
[[tool.mypy.overrides]]
# Phase 3 SPEC.constraints — extend strict from src/pricing/ to src/state/.
# Per CON-mypy-strict-pricing scope expansion (SPEC §Constraints).
module = "src.state.*"
strict = true
disallow_any_explicit = false
warn_return_any = true

[[tool.mypy.overrides]]
# Phase 3 — third-party libs without complete type stubs.
# Source: 03-RESEARCH.md §Code Examples (lines 994-996).
module = ["pytesseract", "PIL.*"]
ignore_missing_imports = true
```

Do NOT change anything else in pyproject.toml. Preserve `requires-python = ">=3.11,<3.12"`, the `[tool.ruff]` block, and the `[tool.coverage.*]` blocks unchanged.

After editing, run `uv sync` (or `uv lock && uv sync`) to install the new deps. Confirm `which tesseract` (Windows: `where tesseract`) shows the system tesseract at `C:\Program Files\Tesseract-OCR\tesseract.exe` per RESEARCH §Standard Stack pytesseract row.
  </action>
  <verify>
    <automated>python -c "import aiohttp, tweepy, onnxruntime, pytesseract, PIL, numpy, structlog; print('all imports ok')" &amp;&amp; python -c "import pytest_asyncio, pytest_benchmark; print('dev deps ok')" &amp;&amp; grep -q 'asyncio_mode = "auto"' pyproject.toml &amp;&amp; grep -q 'module = "src.state.\*"' pyproject.toml &amp;&amp; grep -q 'ignore_missing_imports = true' pyproject.toml</automated>
  </verify>
  <done>All 7 new runtime deps + 2 new dev deps installed; asyncio_mode + 2 new mypy override blocks present; existing src.pricing.* override block preserved unchanged; existing tests still pass (`pytest tests/ -x -k "not benchmark and not e2e"` GREEN as a regression gate).</done>
</task>

<task type="auto">
  <name>Task 2: Add 16 new Phase 3 constants to src/config/constants.py</name>
  <files>src/config/constants.py</files>
  <read_first>
    - src/config/constants.py (entire file — 276 lines)
    - .planning/phases/03-live-ingestion-layer/03-PATTERNS.md §src/config/constants.py block (lines 564-590)
    - .planning/phases/03-live-ingestion-layer/03-RESEARCH.md §Reusable Assets line 127 (per-CONTEXT 13-floor list)
    - .planning/phases/03-live-ingestion-layer/03-RESEARCH.md §Pattern 4 arbiter constants (lines 376-382)
    - .planning/phases/03-live-ingestion-layer/03-RESEARCH.md §Common Pitfalls 2, 3, 6 (constants surfaced: OCR_KILLFEED_CONF_THRESHOLD, RIBGG_LIVE_BACKOFF_CAP_S, OCR_BACKLOG_MAX)
    - .planning/phases/03-live-ingestion-layer/03-CONTEXT.md `<reusable_assets>` block (line 127 — 13 floor list)
  </read_first>
  <action>
Append a new section block at the END of src/config/constants.py (after line 276, after the existing Phase 2 Path B contingency block). Use the existing within-file pattern (analog `src/config/constants.py:177-238`): a `# ---` divider, a section header comment, then `Final[T]`-typed constants each followed by a triple-quoted docstring with `Source: ...` citations.

Add EXACTLY these 16 constants in this order:

```python
# --------------------------------------------------------------------------- #
# Phase 3 — live ingestion layer (REQ-match-state-engine, REQ-scoreboard-polling,
#                                 REQ-ocr-pipeline, REQ-text-listener,
#                                 REQ-cross-source-arbiter,
#                                 REQ-latency-instrumentation)              #
# --------------------------------------------------------------------------- #

OCR_KILLFEED_CADENCE_MS: Final[int] = 100
"""OCR kill-feed scan cadence, milliseconds (per PRD §5.1 / CON-ingestion-cadences).

Source: 03-CONTEXT.md D-03 (kill-feed is the latency-critical path) /
03-RESEARCH.md §Architecture Patterns row "ONNX". Latency-critical because
numerical_diff updates feed the four cell-keying fields the round-conclusion
lookup keys on (Phase 2 D-15).
"""

OCR_SCOREBOARD_CADENCE_MS: Final[int] = 250
"""OCR score-banner scan cadence, milliseconds (PRD §5.1).

Source: PRD §5.1 / CON-ingestion-cadences / roadmap.md §3.3.
Tesseract on a cropped score-banner region runs ~100-300ms — comfortably
within this budget per 03-RESEARCH.md §Architecture Patterns.
"""

OCR_BOMB_CADENCE_MS: Final[int] = 500
"""OCR bomb-icon scan cadence, milliseconds (PRD §5.1).

Source: PRD §5.1 / CON-ingestion-cadences. Bomb plant/defuse is a
discrete event; 500ms is fine because the arbiter cross-confirms
within ARBITER_BOMB_WINDOW_MS.
"""

OCR_ROUNDEND_CADENCE_MS: Final[int] = 100
"""OCR round-end-banner scan cadence, milliseconds, during the round-end window.

Source: PRD §5.1 / CON-ingestion-cadences. Sub-second cadence so the
soft round-end commit (DEC-006) lands quickly enough for hard-confirm by
the next score update.
"""

OCR_DECODE_BUDGET_MS: Final[int] = 50
"""Per-frame decode budget for the OCR pipeline (Pillow + crop + autocontrast).

Source: PRD §5.1 / 03-RESEARCH.md §Common Pitfalls Pitfall 1.
Aggregate decode + inference must stay <= 100ms per frame to satisfy
REQ-ocr-pipeline acceptance.
"""

OCR_INFERENCE_BUDGET_MS: Final[int] = 50
"""Per-frame inference budget (ONNX or pytesseract).

Source: PRD §5.1. ONNX CPU runs ~10-20ms per frame on a cropped HUD region;
pytesseract runs ~100-300ms on the full frame and ~50-100ms on a cropped
HUD bbox after autocontrast (Pitfall 1 mitigation).
"""

OCR_KILLFEED_CONF_THRESHOLD: Final[float] = 0.7
"""Softmax-top-1 confidence threshold for ONNX kill-feed inference.

Source: 03-RESEARCH.md §Common Pitfalls Pitfall 2. Below this threshold
the kill-feed OCR worker emits NO event (caller drops the frame). Phase 5
calibrates against ocr_low_confidence_drops counter logged to metrics.
"""

OCR_BACKLOG_MAX: Final[int] = 4
"""Maximum queued OCR jobs across the ThreadPoolExecutor before frame-drop.

Source: 03-RESEARCH.md §Common Pitfalls Pitfall 6 (asyncio task starvation).
When the pool's pending queue exceeds this, the OCR scheduler DROPS the
incoming frame and increments ocr_dropped_frames_total (visible in metrics).
Prevents unbounded backlog under sustained load.
"""

ARBITER_TICK_HZ: Final[int] = 20
"""Arbiter tick frequency, Hz (50 ms period).

Source: 03-CONTEXT.md D-04 / 03-RESEARCH.md §Architecture Patterns Pattern 4.
Tick = max(20Hz, 2 x highest source cadence). Kill-feed cadence is 100ms
(10Hz) so 20Hz tick keeps arbiter latency below the source cadence.
"""

ARBITER_SCORE_WINDOW_S: Final[float] = 2.0
"""Score-change confirmation window, seconds (DEC-006 / D-04).

Source: PRD §5.1 / DEC-006 / 03-CONTEXT.md D-04. Score-change events from
>=2 distinct sources within this window auto-confirm; single-source within
window quarantines.
"""

ARBITER_KILL_WINDOW_MS: Final[int] = 100
"""Kill-event "same frame" cross-confirm window, milliseconds (DEC-006).

Source: 03-RESEARCH.md §Assumptions Log A5 / DEC-006 ("same frame").
Equals the kill-feed cadence (1 frame). Single OCR-source kill events
within this window auto-confirm; Twitter-only kill events quarantine
(03-RESEARCH.md §Assumptions Log A9).
"""

ARBITER_BOMB_WINDOW_MS: Final[int] = 100
"""Bomb-event "same frame" cross-confirm window, milliseconds (DEC-006).

Source: DEC-006 + 03-RESEARCH.md §Pattern 4 (mirrors kill window).
"""

ARBITER_NUMERICAL_WINDOW_MS: Final[int] = 100
"""Numerical-flip "same frame" cross-confirm window, milliseconds (DEC-006).

Source: DEC-006 + 03-RESEARCH.md §Pattern 4 (mirrors kill window).
"""

ARBITER_ROUND_END_WINDOW_S: Final[float] = 5.0
"""Round-end soft-commit window, seconds (DEC-006).

Source: DEC-006 (round-end soft + hard pattern) / 03-RESEARCH.md §Pattern 4
_eval_round_end_rule. Phase 3 commits immediately with _round_end_soft=True
flag; hard-confirm comes from the next score update (rule mechanics
revisited in Phase 4 quoter).
"""

RIBGG_LIVE_BACKOFF_CAP_S: Final[float] = 10.0
"""Per-failure backoff cap for the LIVE rib.gg poller (override of Phase 2's 60s cap).

Source: 03-RESEARCH.md §Common Pitfalls Pitfall 3. Phase 2's 60s cap targets
batch ETL (slow is OK); Phase 3 live polling needs faster recovery so the
KILL_SWITCH_STALENESS_S kill-switch trips at the correct latency edge
(5s in src/config/constants.py:KILL_SWITCH_STALENESS_S). Used inside
src/ingestion/scoreboard.py's _ribgg_wait override.
"""

EVENT_LOG_DIR: Final[Path] = Path("data/event_log")
"""Per-match JSONL event-log directory (D-02). One file per match_id.

Source: 03-CONTEXT.md D-02 / 03-RESEARCH.md §Architecture Patterns. JSONL
shape per D-02: {seq_id, t_observed..t_quote_sent, source, event_type,
fields_changed} for committed events; {seq_id: null, quarantined: true,
quarantine_reason, fields_proposed, t_observed} for quarantined.
Gitignored — see .gitignore Phase 3 block.
"""

METRICS_LOG_DIR: Final[Path] = Path("data/metrics")
"""Per-match latency-metrics JSONL directory (REQ-latency-instrumentation).

Source: 03-CONTEXT.md integration_points (line 150) / 03-RESEARCH.md
§Pattern 5. Phase 3 writes the six-stage timestamp lineage; Phase 5
reads this for latency analysis (REQ-end-to-end-latency measurement).
Gitignored.
"""

TWITTER_API_BASE_URL: Final[str] = "https://api.twitter.com/2"
"""Twitter API v2 base URL for tweepy.AsyncStreamingClient.

Source: 03-RESEARCH.md §Standard Stack tweepy row. Used for filtered-stream
endpoint as documented at https://docs.x.com/x-api/posts/filtered-stream/introduction.
Listener degrades to no-op when TWITTER_BEARER_TOKEN is unset (CRule 13).
"""

TWITTER_RULE_SET: Final[tuple[str, ...]] = (
    "#VCT",
    "#VALORANTChampions",
    "#VCTAmericas",
    "#VCTEMEA",
    "#VCTPacific",
    "from:valesports_na",
    "from:valesports_emea",
    "from:valesports_pac",
    "from:VALORANTEsports",
    "from:Riot_Esports",
)
"""Static league/account watch-list pushed to Twitter v2 streaming filter at startup.

Source: 03-CONTEXT.md D-07 (static league rule set, NOT per-match). 5 hashtags
+ 5 official league/region accounts = 10 rules. Well under any Twitter tier
limit (Pro: 1000 rules / 1024 chars; see 03-RESEARCH.md §Standard Stack tweepy row).
Static for Phase 3 per D-07; per-match dynamic CRUD deferred (Phase 5+).
"""
```

ALSO add `from pathlib import Path` to the existing import block at top of file (insert it as a new line after the `from typing import Final` line on line 38). Verify with `grep -c "^from " src/config/constants.py` — count goes from 1 to 2.

NOTE: The constants list above is 19 names but only 16 distinct concepts when you collapse the four ARBITER_*_WINDOW siblings into "the arbiter windows" group. The PATTERNS.md §src/config/constants.py block (line 590) explicitly says "Treat CONTEXT line 127's '13' as a floor, not a ceiling." Final count delivered: 19 constants. Do NOT trim — every one is referenced by a downstream task.

Do NOT modify any existing constants. Append-only.
  </action>
  <verify>
    <automated>python -c "from src.config.constants import OCR_KILLFEED_CADENCE_MS, OCR_SCOREBOARD_CADENCE_MS, OCR_BOMB_CADENCE_MS, OCR_ROUNDEND_CADENCE_MS, OCR_DECODE_BUDGET_MS, OCR_INFERENCE_BUDGET_MS, OCR_KILLFEED_CONF_THRESHOLD, OCR_BACKLOG_MAX, ARBITER_TICK_HZ, ARBITER_SCORE_WINDOW_S, ARBITER_KILL_WINDOW_MS, ARBITER_BOMB_WINDOW_MS, ARBITER_NUMERICAL_WINDOW_MS, ARBITER_ROUND_END_WINDOW_S, RIBGG_LIVE_BACKOFF_CAP_S, EVENT_LOG_DIR, METRICS_LOG_DIR, TWITTER_API_BASE_URL, TWITTER_RULE_SET; print('all 19 ok')" &amp;&amp; mypy --strict src/pricing/ &amp;&amp; ruff check src/config/constants.py</automated>
  </verify>
  <done>All 19 constants exist; `from src.config.constants import <each>` succeeds; `mypy --strict src/pricing/` is clean; `ruff check src/config/constants.py` is clean; existing constants block (lines 1-276) untouched.</done>
</task>

<task type="auto">
  <name>Task 3: Update .gitignore and create runtime data directories + .env.example</name>
  <files>.gitignore, data/event_log/.gitkeep, data/metrics/.gitkeep, models/.gitkeep, .env.example</files>
  <read_first>
    - .gitignore (entire file — 73 lines)
    - .planning/phases/03-live-ingestion-layer/03-RESEARCH.md §Runtime State Inventory (lines 609-619) — env vars + onnx model handling
    - .planning/phases/03-live-ingestion-layer/03-CONTEXT.md `<integration_points>` line 149 (gitignored event-log dir)
  </read_first>
  <action>
(a) Edit `.gitignore`. After the existing `models/dp_table.pkl` line (line 61) and BEFORE the `# Calibrated round-conclusion lookup is a committed artifact` comment block (line 65), insert:

```
# Phase 3 — live ingestion layer (D-02 JSONL event log + REQ-latency-instrumentation metrics)
data/event_log/
data/metrics/
!data/event_log/.gitkeep
!data/metrics/.gitkeep

# Phase 3 — ONNX model checkpoints (downloaded via scripts/download_models.py; NOT committed)
models/*.onnx
```

The existing `models/round_conclusion.json` exception (line 67) MUST remain in place after this insertion (the blanket `models/*` rule on line 37 already allows the new `models/*.onnx` rule to add to the deny-list while preserving the explicit JSON exception).

(b) Create empty placeholder files (use `Write` with empty content or a single-line `# placeholder` comment):
- `data/event_log/.gitkeep` — content: `# Per-match JSONL event log directory (D-02). Files: data/event_log/{match_id}.jsonl. Gitignored.`
- `data/metrics/.gitkeep` — content: `# Per-match latency-metrics JSONL directory (REQ-latency-instrumentation). Files: data/metrics/{match_id}.metrics.jsonl. Gitignored.`
- `models/.gitkeep` — only create if it does not already exist (`ls models/.gitkeep || true`); content: `# Models directory (round_conclusion.json committed; ONNX checkpoints downloaded via scripts/download_models.py).`

(c) Create `.env.example` (do NOT touch any actual `.env`):
```
# Phase 3 — Twitter v2 streaming bearer token.
# Source: 03-CONTEXT.md D-07 / 03-RESEARCH.md §Standard Stack tweepy row.
# When unset/empty, src/ingestion/text_listener.py degrades to a no-op coroutine
# (CRule 13: dry-run default; CI cannot exercise paid Twitter Pro tier $5k/mo).
# Obtain a Pro/Enterprise tier bearer token from https://developer.twitter.com/
# and copy this file to .env (which is gitignored — see .gitignore line 2).
TWITTER_BEARER_TOKEN=
```

Confirm `.env.example` is NOT excluded by the `.env.*` line in `.gitignore` (line 3) — it IS, so confirm the existing `!.env.example` exception (line 4) preserves it. Do NOT modify lines 1-7 of .gitignore.
  </action>
  <verify>
    <automated>test -f data/event_log/.gitkeep &amp;&amp; test -f data/metrics/.gitkeep &amp;&amp; test -f .env.example &amp;&amp; grep -q "data/event_log/" .gitignore &amp;&amp; grep -q "data/metrics/" .gitignore &amp;&amp; grep -q "models/\*\.onnx" .gitignore &amp;&amp; grep -q "TWITTER_BEARER_TOKEN" .env.example &amp;&amp; grep -q "!models/round_conclusion.json" .gitignore</automated>
  </verify>
  <done>3 .gitkeep files exist; .env.example exists with TWITTER_BEARER_TOKEN and the no-op-on-empty docstring; .gitignore has new event_log/metrics/onnx exclusions; the existing round_conclusion.json exception is preserved; `git status` shows the 3 new tracked files (.gitkeep + .env.example) and the modified .gitignore.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| filesystem write | Plan creates new directories `data/event_log/`, `data/metrics/`; downstream plans append JSONL here keyed by `match_id`. |
| environment | Plan declares the `TWITTER_BEARER_TOKEN` env-var contract; the Wave-2 listener actually reads it. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-03-00-01 | I (Information disclosure) | `.env.example` | mitigate | File contains the env-var NAME only, NEVER a value; explicit comment instructs operator to copy to `.env` (which is in `.gitignore` line 2). |
| T-03-00-02 | I | `.gitignore` event_log/metrics rules | mitigate | New rules added so per-match JSONL (which may carry team/match identifiers) never lands in git. The `!data/event_log/.gitkeep` exception is intentional and contains zero match data. |
| T-03-00-03 | T (Tampering) | `pyproject.toml` deps | mitigate | All 9 new pins use upper-bound version constraints (`<X`) per RESEARCH §Standard Stack. Pinned ranges close the door on uncontrolled major-version drift. `uv lock` produces `uv.lock` which records exact resolved versions for reproducibility. |
| T-03-00-04 | D (Denial of service) | `models/.gitkeep` directory creation | accept | Directory creation is idempotent; no DoS surface. |

## Phase 3 attack surface coverage by this plan

This plan covers ONLY infra prerequisites for the network/file/cred threats listed in the orchestrator's `<security_threat_model>`. The actual mitigations land in downstream plans:
- T-net-01 (TLS / cert) — handled in 03-03 (scoreboard) + 03-05 (text listener) by reusing Phase 2's tenacity-retry HTTP layer (TLS via `requests`/`aiohttp` defaults; no plaintext fallback).
- T-creds-01 (Twitter token handling) — this plan declares `.env.example`; 03-05 enforces the no-op + no-log behavior.
- T-files-01 (JSONL match_id sanitization) — this plan creates the directory; 03-07 enforces `match_id` sanitization in the writer.
- T-deser-01 (ONNX SHA-256) — 03-01 (download script).
- T-input-01 (tweet bound + control-char drop) — 03-05.
- T-resource-01 (deque bounds) — 03-07.
</threat_model>

<verification>
- `pyproject.toml` parses; `uv sync` (or `pip install -e ".[dev]"`) succeeds; `python -c "import aiohttp, tweepy, onnxruntime, pytesseract, PIL, numpy, structlog, pytest_asyncio, pytest_benchmark"` returns 0.
- `mypy --strict src/pricing/` clean (no regression from constants additions).
- `ruff check src/config/constants.py` clean.
- All 19 new constants importable: `python -c "from src.config import constants as c; assert all(hasattr(c, n) for n in ['OCR_KILLFEED_CADENCE_MS', 'ARBITER_TICK_HZ', 'EVENT_LOG_DIR', 'TWITTER_RULE_SET'])"`.
- `data/event_log/.gitkeep`, `data/metrics/.gitkeep`, `.env.example` committed to git.
- All Phase 1 + Phase 2 tests still GREEN: `pytest tests/ -x -k "not benchmark and not e2e"` passes.
</verification>

<success_criteria>
Wave 0 infra-1 plan is COMPLETE when:

1. `pyproject.toml` declares all 7 new runtime deps (aiohttp/tweepy/onnxruntime/pytesseract/Pillow/numpy/structlog) and 2 new dev deps (pytest-asyncio/pytest-benchmark) with the pinned RESEARCH version constraints.
2. `asyncio_mode = "auto"` present under `[tool.pytest.ini_options]`.
3. Two new `[[tool.mypy.overrides]]` blocks: one strict-mode for `src.state.*`, one ignore-missing-imports for `pytesseract`/`PIL.*`.
4. 19 new Phase 3 constants live in `src/config/constants.py` with `Final[T]` annotations and source-cited docstrings.
5. `.gitignore` has the new event_log/metrics/onnx exclusions; the existing `!models/round_conclusion.json` exception is preserved.
6. `data/event_log/.gitkeep`, `data/metrics/.gitkeep`, `.env.example` exist and are committed.
7. `mypy --strict src/pricing/` GREEN; `ruff check src/` GREEN; `pytest tests/ -x -k "not benchmark and not e2e"` GREEN (regression).
8. Per RESEARCH §Validation Architecture phase-gate, none of these tasks introduce failing tests because they don't add code paths — only deps + constants + directories.
</success_criteria>

<output>
After completion, create `.planning/phases/03-live-ingestion-layer/03-00-SUMMARY.md`:

```markdown
# 03-00 SUMMARY — pyproject + constants + dirs

**Status:** complete
**Wave:** 0
**Files modified:** pyproject.toml, src/config/constants.py, .gitignore
**Files created:** data/event_log/.gitkeep, data/metrics/.gitkeep, models/.gitkeep (if absent), .env.example
**Tests:** N/A (infra-only); regression `pytest tests/ -x -k "not benchmark and not e2e"` GREEN

## Constants added (19)
- OCR cadences: OCR_KILLFEED_CADENCE_MS (100), OCR_SCOREBOARD_CADENCE_MS (250), OCR_BOMB_CADENCE_MS (500), OCR_ROUNDEND_CADENCE_MS (100)
- OCR budgets: OCR_DECODE_BUDGET_MS (50), OCR_INFERENCE_BUDGET_MS (50)
- OCR safeguards: OCR_KILLFEED_CONF_THRESHOLD (0.7), OCR_BACKLOG_MAX (4)
- Arbiter: ARBITER_TICK_HZ (20), ARBITER_SCORE_WINDOW_S (2.0), ARBITER_KILL_WINDOW_MS (100), ARBITER_BOMB_WINDOW_MS (100), ARBITER_NUMERICAL_WINDOW_MS (100), ARBITER_ROUND_END_WINDOW_S (5.0)
- HTTP: RIBGG_LIVE_BACKOFF_CAP_S (10.0)
- Paths: EVENT_LOG_DIR, METRICS_LOG_DIR
- Twitter: TWITTER_API_BASE_URL, TWITTER_RULE_SET (10 rules)

## Deps added (9)
- runtime: aiohttp, tweepy, onnxruntime, pytesseract, Pillow, numpy, structlog
- dev: pytest-asyncio, pytest-benchmark

## Mypy
- New `src.state.*` strict block; new `pytesseract` + `PIL.*` ignore_missing_imports block.
```
</output>
