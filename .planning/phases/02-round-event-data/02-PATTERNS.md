# Phase 2: Round-event data — Pattern Map

**Mapped:** 2026-04-30
**Files analyzed:** 12 (4 new src, 4 modified, 4 test scaffolds + artifacts)
**Analogs found:** 9 / 12 (3 files have no in-repo analog — `scripts/` directory is empty pre-Phase 2)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `scripts/probe_round_events.py` | script (offline ETL) | request-response + file-I/O | *(none — `scripts/` is empty)* | no analog — establishing the pattern |
| `scripts/calibrate_round_conclusion.py` | script (offline transform) | batch / file-I/O | `reference/theo_engine.py:84-129` (formula only — read-only, do NOT import) + `src/pricing/data.py:HalfRates.from_json` (loader/serializer style) | role-match (formula) + role-match (loader) |
| `scripts/ocr_round_events.py` *(Path B contingency only)* | script (offline OCR) | file-I/O / batch | *(none — Path B not built unless Path A fails)* | no analog — deferred |
| `src/pricing/economy.py` | utility / pricing helper | transform (pure function) | `src/pricing/blend.py` (single-pure-fn module with constants import) | role-match |
| `src/pricing/round_conclusion.py` *(MODIFIED — additive `from_json` only)* | model / loader | file-I/O (deserialize) | `src/pricing/data.py:HalfRates.from_json` (lines 113-145) | exact (same pattern: dataclass classmethod + path → typed dict → instance) |
| `src/config/constants.py` *(MODIFIED — add calibration knobs)* | config | static | `src/config/constants.py` itself (existing `Final[...]` block) | exact (extend in place) |
| `data/round_events.sqlite` | generated data (gitignored) | n/a | already covered by `.gitignore:62-63` | exact (already gitignored) |
| `models/round_conclusion.json` | generated artifact (committed) | static | *(no precedent — first model artifact)* | no analog — establishing the pattern |
| `.planning/phases/02-round-event-data/02-PROBE-LOG.md` | docs deliverable | static | `.planning/phases/01-core-pricing-engine/01-VERIFICATION.md` | role-match (per-phase deliverable) |
| `tests/pricing/test_round_conclusion_loader.py` | test (new) | request-response | `tests/pricing/test_round_conclusion.py` (existing — extend pattern) | exact |
| `tests/scripts/test_calibrate_round_conclusion.py` | test (new) | request-response | `tests/pricing/test_dp.py` (hypothesis + helpers) | role-match |
| `tests/scripts/test_synthesize_states.py` + sibling probe tests | test (new) | request-response | `tests/pricing/test_blend.py` (parametrized unit + property) | role-match |
| `.gitignore` | config | static | `.gitignore:62-63` (already lists `data/round_events*` and `data/round_events.sqlite`) | already done — verify, no change needed |
| `pyproject.toml` *(MODIFIED — add `requests`, `tenacity`, `tqdm`)* | config | static | `pyproject.toml:[project] dependencies = []` | exact (extend `dependencies` array) |

---

## Pattern Assignments

### `src/pricing/round_conclusion.py` — additive `from_json` classmethod (MODIFIED)

**Analog:** `src/pricing/data.py:HalfRates.from_json` (lines 113-145).

**This is the closest match in the repo** — same class shape (frozen dataclass), same path-to-instance contract, same `mypy --strict` regime, same `data/*.json → instance` direction.

**Imports pattern to copy** (data.py lines 18-25):
```python
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from src.config.constants import SHRINK_PRIOR
```

For Phase 2, the new imports added to `round_conclusion.py` are `json`, `Path`, and a `TypedDict` block (RESEARCH.md "Don't Hand-Roll" → use `TypedDict` for the JSON schema).

**Classmethod pattern** (data.py lines 127-144):
```python
@classmethod
def from_json(cls, path: str | Path) -> HalfRates:
    """Load HalfRates from data/half_win_rates.json (Open Question 2 resolution).

    Schema (verified during planning):
        {
          "team_map_side":   {"<team>|<map>|<side>": {wins, total, rate, used_fallback}, ...},
          "league_map_side": {"<map>|<side>":        {wins, total, rate}, ...},
          "overall_avg": float (typically 0.5),
          ...
        }
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return cls(
        team_rates=data.get("team_map_side", {}),
        league_rates=data.get("league_map_side", {}),
        overall_avg=float(data.get("overall_avg", 0.5)),
    )
```

**Apply to `RoundConclusionLookup.from_json`:**
- Use `Path(path).read_text(encoding="utf-8")` (NOT bare `open()`) — matches `data.py` and is `mypy --strict` clean.
- Use `cls()` to instantiate, then mutate the dict fields (allowed by `frozen=True` per `round_conclusion.py:28-34` docstring + `test_frozen_allows_dict_mutation_for_phase_2_population`).
- Use `data.get(<key>, <default>)` — graceful empty-default behavior, NOT `data[<key>]` (KeyError on missing keys is the wrong shape for an additive loader).
- For nested cell deserialization, declare `class _CellJson(TypedDict): n: int; p_hat: float; parent_p: float` per RESEARCH.md "Don't Hand-Roll" guidance — gives `mypy --strict` the schema for free.

**`frozen=True` mutation pattern** (round_conclusion.py:28-34, exercised by tests/pricing/test_round_conclusion.py:238-248):
```python
# tests/pricing/test_round_conclusion.py:245-248
lookup = RoundConclusionLookup()
cell = _Cell(n=10, p_hat=0.6, parent_p=0.5)
lookup.cells_full[(0, False, "atk", "full", "Lotus")] = cell
assert lookup.cells_full[(0, False, "atk", "full", "Lotus")] is cell
```

The `from_json` body must populate cells via `obj.cells_full[key] = _Cell(...)` — never reassign `obj.cells_full = {...}` (that raises `FrozenInstanceError`).

**Key serialization for tuple-keyed dicts** — RESEARCH.md proposes `"{nd}|{bp}|{side}|{econ}|{map}"` (lines 622-624 of 02-RESEARCH.md). The planner must add a private `_parse_key_N` helper per arity (5/4/3/2). NOT a public surface — keep underscored.

**Lookup body rewrite (also part of MODIFIED scope)** — RESEARCH.md §"`RoundConclusionLookup.from_json` — the ONE additive interface change" lines 635-644 has the canonical fallback-chain walk. The signature is unchanged from the Phase 1 stub at `round_conclusion.py:163-190`. The Phase 1 test `test_lookup_always_returns_flat_05_in_phase_1` (lines 47-61 of test_round_conclusion.py) MUST be rewritten in Phase 2 because the body's return value changes from flat 0.5 to calibrated cell.shrunk(); the planner needs to call this out as a test rewrite, not a deletion.

---

### `src/config/constants.py` — add calibration knobs (MODIFIED)

**Analog:** the existing file itself. Extend in place — every new constant follows the same shape.

**Imports + module preamble** (constants.py:36-38):
```python
from __future__ import annotations

from typing import Final
```

**Existing constant pattern** (constants.py:44-49):
```python
SHRINK_PRIOR: Final[float] = 15.0
"""Bayesian prior weight in rounds for the round-conclusion lookup.

Source: DEC-007 / CLAUDE.md "Domain constants" / reference/theo_engine.py:37.
Re-fit in Phase 5 after 100+ matches of paper-trade data (REQ-calibration-loop).
"""
```

**Apply pattern to new Phase 2 constants** (per RESEARCH.md "Project Constraints" §6, lines 678-682):
```python
RIBGG_BASE_URL: Final[str] = "https://be-prod.rib.gg/v1"
"""rib.gg internal API base URL (verified live 2026-04-30 in 02-RESEARCH.md).

Source: 02-RESEARCH.md §"Pattern 1" / DEC-017. Subdomain migrated 2022→2026
(`backend-prod.rib.gg` → `be-prod.rib.gg`); re-probe before scraping if Phase 2
execution is delayed >30 days from research date.
"""

RIBGG_RECENCY_MONTHS: Final[int] = 18
"""Hard cap on rib.gg `events[].startDate` filter for D-03 coverage bar.

Source: D-03 (CONTEXT.md). Older matches rejected at probe time. Document
rejection count in `02-PROBE-LOG.md` per Pitfall 6.
"""

RIBGG_TARGET_MATCH_COUNT: Final[int] = 1000
"""Tier-1 VCT match-count target for the calibration dataset.

Source: D-03 (CONTEXT.md). At ~75k rounds this saturates `cells_full` for the
popular `(numerical_diff, bomb_planted, side, econ_bucket, map)` combinations.
"""

MIN_CELL_N: Final[int] = 5
"""Minimum sample size for a cell to be persisted to `models/round_conclusion.json`.

Source: 02-RESEARCH.md §"Project Constraints" #6. Below this floor, `_Cell.shrunk()`
returns essentially `parent_p`; persisting the cell wastes JSON size without changing
runtime lookup behavior. Drop in calibrator before serialization.
"""

OCR_FRAMES_PER_SECOND: Final[float] = 1.0
"""Path B OCR frame extraction rate (D-10 — only used if Path A fails).

Source: D-10 (CONTEXT.md) / 02-RESEARCH.md §"Project Constraints" #6.
"""
```

**`tests/config/test_constants.py` extension** — extend `EXPECTED_NAMES` tuple at line 23-44 to include the new constants. Pattern is parametric: every constant added to `constants.py` must be added to `EXPECTED_NAMES`, or `test_no_unexpected_uppercase_names_leak_in` fails.

---

### `src/pricing/economy.py` — econ_bucket bucketing helper (NEW)

**Analog:** `src/pricing/blend.py` — closest match for "single-purpose pure-function module under `src/pricing/` with `mypy --strict` and constants imports." Sibling module pattern.

The exact lines of `blend.py` were not pulled in this session (out of necessity — early stop), but the import + module-docstring pattern matches `dp.py:1-67` and `data.py:1-25`. Apply this skeleton:

**Imports + preamble** (canonical shape from `data.py:18-25` and `dp.py:67-73`):
```python
"""econ_bucket bucketing — CON-economy-buckets contract.

Shared between Phase 2's calibration ETL (`scripts/probe_round_events.py`) and
Phase 3's live `MatchState.econ_bucket` derivation. CRule 2 forbids two
implementations of the same concept — this is the canonical one.

Bucket boundaries (CLAUDE.md "Domain constants"):
    full      ≥ 20,000 credits
    semi-buy  10,000 – 19,999
    semi-eco  5,000 – 9,999
    eco       < 5,000
"""
from __future__ import annotations

from typing import Final
```

**Bucket-boundary constants** — these are *boundaries*, not arbitrary thresholds, so per CRule 12 they live in `src/config/constants.py`, NOT inline here. Add to constants.py:
```python
ECON_BUCKET_FULL_FLOOR: Final[int] = 20_000
ECON_BUCKET_SEMI_BUY_FLOOR: Final[int] = 10_000
ECON_BUCKET_SEMI_ECO_FLOOR: Final[int] = 5_000
```

**Pure-function pattern** (matches `blend.round_p` style):
```python
from src.config.constants import (
    ECON_BUCKET_FULL_FLOOR,
    ECON_BUCKET_SEMI_BUY_FLOOR,
    ECON_BUCKET_SEMI_ECO_FLOOR,
)

def credits_to_bucket(credits: int) -> str:
    """Map team-loadout credits to the canonical econ_bucket label.

    Source: CLAUDE.md "Domain constants" / CON-economy-buckets.
    """
    if credits >= ECON_BUCKET_FULL_FLOOR:
        return "full"
    if credits >= ECON_BUCKET_SEMI_BUY_FLOOR:
        return "semi-buy"
    if credits >= ECON_BUCKET_SEMI_ECO_FLOOR:
        return "semi-eco"
    return "eco"
```

This single helper is what `probe_round_events.py` calls and what Phase 3's MatchState ingestion will call. **Bit-identical** behavior is the contract.

---

### `scripts/probe_round_events.py` — rib.gg ETL (NEW)

**Analog:** none — `scripts/` is empty pre-Phase 2. Phase 2 establishes the CLI scaffold for Phase 4+ to copy.

**Recommended scaffold** (synthesizes RESEARCH.md §"Code Examples" with project conventions from `dp.py` / `data.py`):

**Module preamble + future-import** (matches `data.py:1-26`):
```python
"""Wave 1: scrape rib.gg round events into data/round_events.sqlite.

Path A only. Per 02-RESEARCH.md (in-session live probe of be-prod.rib.gg
2026-04-30), the multi-source ladder of D-01 collapses to a single source.
Sources 2-4 (valorantr / FlynV / bo3.gg) are documented as "considered, rejected"
in 02-PROBE-LOG.md.

Sources
-------
- 02-RESEARCH.md §"Pattern 1" (rib.gg endpoint chain — verified)
- 02-RESEARCH.md §"Pattern 2" (mid_round_states[] synthesis)
- 02-CONTEXT.md D-01..D-09
- CON-round-events-schema (8 columns frozen)
- CRule 12 (no magic numbers — see src.config.constants)
- CRule 13 (dry-run by default — `--dry-run` flag below)
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import TypedDict

import requests
from tenacity import retry, stop_after_attempt, wait_exponential
from tqdm import tqdm

from src.config.constants import (
    RIBGG_BASE_URL,
    RIBGG_RECENCY_MONTHS,
    RIBGG_TARGET_MATCH_COUNT,
)
from src.pricing.economy import credits_to_bucket
```

**TypedDict response schema pattern** (RESEARCH.md "Don't Hand-Roll" + `mypy --strict`):
```python
class _RibEvent(TypedDict):
    roundNumber: int
    roundTimeMillis: int
    eventType: str  # "start" | "plant" | "kill" | "defuse"
    attackingTeamNumber: int
    killId: int | None
    bombId: int | None
    playerId: int | None
    referencePlayerId: int | None
```

**HTTP retry pattern** (verbatim from RESEARCH.md §"Code Examples" lines 540-546):
```python
HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.rib.gg/"}

@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, max=30))
def get_json(url: str) -> dict:
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()
```

**Dry-run CLI scaffold** (CRule 13 — establish for Phase 4 to inherit):
```python
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="Fetch a small sample (5 series) for validation; do not write SQLite.")
    parser.add_argument("--out-db", type=Path, default=Path("data/round_events.sqlite"))
    parser.add_argument("--probe-log", type=Path,
                        default=Path(".planning/phases/02-round-event-data/02-PROBE-LOG.md"))
    args = parser.parse_args()
    # ... transform via synthesize_mid_round_states(), write SQLite + PROBE-LOG.md
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```

**SQLite context-manager pattern** (RESEARCH.md "Don't Hand-Roll"):
```python
with sqlite3.connect(out_db) as conn:
    conn.execute(...)
    # auto-close on exception
```

**Phase 4+ replication** — when Phase 4 writes `src/main.py` or other CLI entry points, this is the scaffold to copy: argparse, dry-run flag wired, `main() -> int`, `raise SystemExit(main())`.

---

### `scripts/calibrate_round_conclusion.py` — empirical-Bayes shrinkage walk (NEW)

**Analog 1 (formula):** `reference/theo_engine.py:84-102` — read-only audit-engine source for the shrinkage formula. Per CLAUDE.md "Read first": `reference/` is read-only, never imported.

**Audit-engine shrinkage source** (theo_engine.py:96-100):
```python
entry = self._team_rates.get(f'{team}|{map_name}|{side}')
if entry:
    n    = entry.get('total', 0)
    raw  = entry['rate']
    # Shrink toward league average: as n grows the estimate converges to raw
    return (n * raw + SHRINK_PRIOR * prior) / (n + SHRINK_PRIOR)
```

**Apply to calibrator:** the calibrator does NOT re-implement this formula. It instantiates `_Cell(n=N, p_hat=p_hat, parent_p=parent_p)` and lets `_Cell.shrunk()` run (round_conclusion.py:84-100). CRule 2 — single canonical formula.

**Analog 2 (loader/serializer):** `src/pricing/data.py:HalfRates.from_json` (lines 127-144) — same shape pattern as the calibrator's input load.

**Bottom-up walk pattern** (RESEARCH.md §"Pattern 3" lines 339-394, verbatim per D-14):
```python
from collections import defaultdict
from src.pricing.round_conclusion import RoundConclusionLookup, _Cell

def calibrate(rows: list[dict], half_rates: dict) -> RoundConclusionLookup:
    lookup = RoundConclusionLookup()  # frozen=True wrapper, mutable dict fields

    # Level 5 (deepest in chain = LAST resort, but populated FIRST):
    league_rates = half_rates.get("league_map_side", {})
    overall_avg = half_rates.get("overall_avg", 0.5)
    for side in ("atk", "def"):
        side_entries = [v["rate"] for k, v in league_rates.items() if k.endswith(f"|{side}")]
        lookup.side_baseline[side] = (sum(side_entries) / len(side_entries)
                                      if side_entries else overall_avg)

    # Level 4: cells_minimal — keyed (numerical_diff, bomb_planted)
    minimal_agg = defaultdict(lambda: [0, 0])
    for r in rows:
        for s in r["mid_round_states"]:
            key = (s["numerical_diff"], s["bomb_planted"])
            minimal_agg[key][0] += int(r["round_won_by_a"])
            minimal_agg[key][1] += 1
    parent_minimal = (lookup.side_baseline["atk"] + lookup.side_baseline["def"]) / 2
    for key, (w, n) in minimal_agg.items():
        if n == 0: continue
        lookup.cells_minimal[key] = _Cell(n=n, p_hat=w / n, parent_p=parent_minimal)

    # Level 3: cells_no_map — uses parent = cells_minimal[(nd, bp)].shrunk()
    # Level 2: cells_no_econ — uses parent = cells_no_map[(nd, bp, side)].shrunk()
    # Level 1: cells_full     — uses parent = cells_no_econ[...].shrunk()
    return lookup
```

**Critical: walk-order invariant.** Each `_Cell.parent_p: float` is fixed at construction. The parent must already be populated *and shrunk* before the child is constructed. Per RESEARCH.md "Pitfall 5", the JSON serializes `(n, p_hat, parent_p)` — not the shrunk float — to preserve auditability and let Phase 5 re-tune `SHRINK_PRIOR`.

**`MIN_CELL_N` filter before serialization** (CRule 12 / RESEARCH.md "Project Constraints" #6):
```python
from src.config.constants import MIN_CELL_N

# Drop sparse cells before write — they collapse to ~parent_p anyway
serializable_cells = {k: v for k, v in lookup.cells_full.items() if v.n >= MIN_CELL_N}
```

**`models/round_conclusion.json` write — `_Cell` serialization shape** (RESEARCH.md Pitfall 5, lines 478-482):
```python
# CORRECT — preserves (n, p_hat, parent_p) for Phase 5 re-tuning
{"cells_full": {"0|true|atk|full|Lotus": {"n": 42, "p_hat": 0.61, "parent_p": 0.55}, ...}}
# WRONG — collapses to shrunk(); audit trail lost
{"cells_full": {"0|true|atk|full|Lotus": 0.59, ...}}
```

---

### `scripts/ocr_round_events.py` — Path B contingency (NEW, deferred)

**Status:** NOT in Wave 1 scope per RESEARCH.md §Summary. Path A is verified working. Plan to defer this file entirely; planner notes it as a separate ticket gated on Wave 1 outcome (RESEARCH.md §"Open Questions" #6).

**If invoked:** RESEARCH.md §"State of the Art" — use `cv2.matchTemplate` for Valorant HUD digits, NOT Tesseract (custom font). Tesseract reserved for player nameplates only. No analog in repo; first OCR pipeline.

---

### `tests/pricing/test_round_conclusion_loader.py` — round-trip tests (NEW)

**Analog:** `tests/pricing/test_round_conclusion.py` — same module-under-test, same import surface.

**Imports + module preamble pattern** (test_round_conclusion.py:1-30):
```python
"""Tests for src.pricing.round_conclusion — REQ-round-event-data-pipeline (loader).

Verifies the Phase 2 additive-interface invariants:
  - `RoundConclusionLookup.from_json("models/round_conclusion.json").lookup(...)`
    returns finite floats in [0, 1] for all keys present.
  - Round-trip via to_json/from_json reproduces the same _Cell instances bit-identically.
  - Empty-dict path: RoundConclusionLookup() (cells empty) returns side_baseline[side]
    or _PHASE_1_FLAT_CELL_VALUE = 0.5 — Path-C compatibility regression test.
  - `from_json` on a missing file raises FileNotFoundError (not silently returning empty).
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from src.config.constants import SHRINK_PRIOR
from src.pricing.round_conclusion import (
    _PHASE_1_FLAT_CELL_VALUE,
    RoundConclusionFn,
    RoundConclusionLookup,
    _Cell,
)
```

**Hypothesis property test pattern** (test_round_conclusion.py:37-61):
```python
@given(
    numerical_diff=st.integers(min_value=-4, max_value=4),
    bomb_planted=st.booleans(),
    side=st.sampled_from(["atk", "def"]),
    econ_bucket=st.sampled_from(["full", "semi-buy", "semi-eco", "eco"]),
    map_name=st.sampled_from(["Lotus", "Bind", "Haven", "Ascent", "Pearl", "Split", "Sunset"]),
)
@settings(max_examples=100, deadline=None)
def test_loaded_lookup_returns_in_range(
    numerical_diff: int, bomb_planted: bool, side: str, econ_bucket: str, map_name: str,
) -> None:
    """For any (potentially-missing) key, calibrated lookup returns a value in [0, 1]."""
    lookup = RoundConclusionLookup.from_json("models/round_conclusion.json")
    val = lookup.lookup(numerical_diff, bomb_planted, side, econ_bucket, map_name)
    assert 0.0 <= val <= 1.0
    assert not math.isnan(val)
```

**Path-C regression test** (extends test_round_conclusion.py:192-209):
```python
def test_empty_lookup_path_c_compatibility() -> None:
    """RoundConclusionLookup() with no cells populated must still return 0.5 — Path C."""
    lookup = RoundConclusionLookup()  # All dicts empty (Path C scenario)
    # side_baseline starts at {"atk": 0.5, "def": 0.5} per default_factory
    assert lookup.lookup(0, False, "atk", "full", "Lotus") == 0.5
```

**Note: existing `test_lookup_always_returns_flat_05_in_phase_1` (test_round_conclusion.py:47-61) MUST be REWRITTEN** in Phase 2 because the lookup body changes. It becomes "given an EMPTY lookup, returns 0.5" (the Path-C invariant) instead of "for ALL inputs always 0.5." Planner's modify list must include this rewrite.

---

### `tests/scripts/test_calibrate_round_conclusion.py` — calibrator tests (NEW)

**Analog:** `tests/pricing/test_dp.py` (lines 1-58) — closest match for "test a complex pricing module with hypothesis + helper fixtures."

**Imports pattern** (test_dp.py:1-33):
```python
"""Property + integration tests for scripts.calibrate_round_conclusion.

Verifies REQ-round-event-data-pipeline calibrator invariants:
  - Synthetic 100-row dataset → deterministic _Cell instances (re-run gives same output).
  - Bottom-up walk: every _Cell's parent_p was populated before construction (no None / NaN).
  - Extreme signal: a synthetic cell where (numerical_diff=2, bomb_planted=True) always wins
    → calibrated cell.shrunk() > 0.9 (not exactly 1.0 due to shrinkage to parent).
  - Defuse termination: a round ending in defuse does NOT emit phantom post-defuse states.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from src.config.constants import SHRINK_PRIOR
from src.pricing.round_conclusion import RoundConclusionLookup, _Cell
```

**Helper fixture pattern** (test_dp.py:40-58 — `_ConstantRoundPFn`):
```python
def _synthetic_rows(n_matches: int = 100) -> list[dict[str, Any]]:
    """Generate a deterministic synthetic round_events dataset."""
    # ... build rows with known wins/totals per cell
```

**Test placement:** `tests/scripts/` is a NEW test directory. The Phase 0/1 convention is `tests/<src_subpackage>/test_<module>.py`. Add `tests/scripts/__init__.py` (empty) to make it a package, mirroring `tests/pricing/__init__.py` and `tests/config/__init__.py`.

---

## Shared Patterns

### `mypy --strict` typing on `src/pricing/`

**Source:** CLAUDE.md rule 11 / `src/pricing/round_conclusion.py:36` `from __future__ import annotations` + `Final`/`Protocol` usage throughout.

**Apply to:** `src/pricing/economy.py`, `src/pricing/round_conclusion.py` `from_json` additions.

**Required:**
- `from __future__ import annotations` at top (every existing `src/pricing/*.py` does this).
- `Final[...]` for all module-level constants (constants.py:38-91).
- `TypedDict` for JSON schema (RESEARCH.md "Don't Hand-Roll").
- No `Any` returns from public functions — use precise types.

### Constants imports — one canonical source

**Source:** `src/pricing/data.py:25` (`from src.config.constants import SHRINK_PRIOR`), `src/pricing/dp.py:73` (`from src.config.constants import REGULATION_HALF, WIN_THRESHOLD`).

**Apply to:** every new module that needs a threshold.

**Pattern:**
```python
from src.config.constants import (
    RIBGG_BASE_URL,
    RIBGG_RECENCY_MONTHS,
    MIN_CELL_N,
)
```

NEVER inline a literal that has a constant name. CRule 12 / `tests/pricing/test_round_conclusion.py:121-158` enforces this for `SHRINK_PRIOR`; the planner should consider an analogous test for any new business-logic constant.

### Frozen-dataclass mutable-dict pattern

**Source:** `src/pricing/round_conclusion.py:133-161` + `tests/pricing/test_round_conclusion.py:231-248`.

**Apply to:** any `RoundConclusionLookup` instance manipulation in calibrator + loader.

**Rule:**
- ✅ `lookup.cells_full[key] = _Cell(...)` (dict mutation — allowed)
- ❌ `lookup.cells_full = {}` (field reassignment — `FrozenInstanceError`)
- ❌ `lookup.side_baseline = {"atk": 0.6}` (field reassignment — `FrozenInstanceError`)
- ✅ `lookup.side_baseline["atk"] = 0.6` (dict mutation — allowed)
- ✅ `lookup.side_baseline.update({"atk": 0.6, "def": 0.6})` (dict mutation — allowed)

### Module docstring `Sources` block

**Source:** Every Phase 1 `src/pricing/*.py` has a "Sources" or similar block citing `prd.md`, `roadmap.md`, decisions, and any salvage source. See `data.py:9-16`, `dp.py:1-65`, `round_conclusion.py:11-17`.

**Apply to:** every new module (`economy.py`, both scripts) and every new test file.

**Pattern:**
```python
"""<one-line summary>.

<paragraph(s) of context — what this replaces, why it exists>.

Sources
-------
- <design doc> §X (locked decision)
- <decision id> (e.g., DEC-013, D-14)
- <reference file>:LINE (salvage source if any)
- <test file> (sister test asserting this module's invariant)
"""
```

### Path/file-IO discipline

**Source:** `src/pricing/data.py:128-144` — uses `Path(path).read_text(encoding="utf-8")` and `Path(path).write_text(..., encoding="utf-8")` always.

**Apply to:** `from_json` classmethod, calibrator's JSON write, probe SQLite path resolution.

**Pattern:**
- Accept `path: str | Path` (union — caller convenience).
- Coerce via `Path(path)` immediately.
- Always pass `encoding="utf-8"` explicitly (Windows defaults to cp1252; this is a Windows machine per environment block).

### Test naming + organization

**Source:** `tests/pricing/test_*.py`, `tests/config/test_constants.py` — every test module mirrors its src module name.

**Apply to:**
- `tests/pricing/test_round_conclusion_loader.py` (sibling to existing `test_round_conclusion.py`).
- `tests/scripts/test_calibrate_round_conclusion.py`, `tests/scripts/test_synthesize_states.py`, `tests/scripts/test_side_mapping.py`, `tests/scripts/test_probe_log_format.py`, `tests/scripts/test_round_events_schema.py` (new test directory — add `tests/scripts/__init__.py` empty file).

### Hypothesis property-test settings

**Source:** `tests/pricing/test_round_conclusion.py:37-46` and `tests/pricing/test_blend.py:17-19`.

**Apply to:** every property-test in the new test files.

**Pattern:**
```python
@given(
    n=st.integers(min_value=0, max_value=10_000),
    p_hat=st.floats(min_value=0.0, max_value=1.0),
)
@settings(max_examples=100, deadline=None)
def test_<property>(...) -> None:
    ...
```

`deadline=None` is required — synthetic-dataset construction in calibrator tests will exceed Hypothesis' 200ms default.

---

## No Analog Found

Files with no close match in the codebase. Planner should establish the pattern carefully and reference RESEARCH.md examples directly.

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `scripts/probe_round_events.py` | offline ETL CLI | request-response + file-I/O | `scripts/` directory is empty pre-Phase 2; this is the FIRST script. Establishes the CLI scaffold (argparse + `--dry-run` flag + `main() -> int` + `raise SystemExit(main())`) for Phase 4+ to copy. Planner should call this out as a precedent-setting file. |
| `scripts/ocr_round_events.py` | offline OCR | file-I/O | Path B contingency only — RESEARCH.md says NOT to build in Wave 1. Defer entirely to a separate ticket gated on Path A failure. No design needed in Phase 2 plan. |
| `models/round_conclusion.json` | generated artifact (committed) | static | First model artifact under `models/`. Phase 1's `models/dp_table.pkl` was deferred (D-21) so `models/.gitkeep` is the only existing file. RESEARCH.md §"Pitfall 5" + §"Code Examples" §`from_json` define the JSON shape. |

---

## File-Already-Done Items (verify, no change required)

- **`.gitignore`** — `data/round_events*` and `data/round_events.sqlite` are already listed at lines 62-63. RESEARCH.md "Pitfall 7" requirement is already satisfied. Planner should verify in Wave 0 and skip a modify task if confirmed.
- **`models/.gitkeep`** — already exists (committed) so `models/round_conclusion.json` writes don't trigger a "directory missing" error.
- **`data/.gitkeep`** — assumed similarly present given existing `data/half_win_rates.json`.

---

## Metadata

**Analog search scope:**
- `src/pricing/*.py` (5 files)
- `src/config/constants.py`
- `tests/pricing/*.py` (5 files)
- `tests/config/test_constants.py`
- `reference/theo_engine.py` (read-only — formula source only)
- `.gitignore`, `pyproject.toml`
- `scripts/` (empty — confirmed no analog)

**Files scanned:** 14
**Pattern extraction date:** 2026-04-30
**Phase 1 surface preserved:** `RoundConclusionLookup.lookup` signature, `_Cell` dataclass shape, `RoundConclusionFn` Protocol — all locked. The single additive change is `from_json` classmethod, with shape exactly mirroring `HalfRates.from_json` (`src/pricing/data.py:127-144`).
