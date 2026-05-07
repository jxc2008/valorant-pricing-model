---
phase: 03-live-ingestion-layer
plan: "07"
type: execute
wave: 5
depends_on: ["03-01", "03-02"]
files_modified:
  - scripts/probe_round_events.py
  - scripts/probe_round_events_v2.py
  - scripts/calibrate_round_conclusion_v2.py
  - pyproject.toml
  - src/config/constants.py
  - models/round_conclusion.json
  - data/round_events_v2.sqlite
  - data/ribgg_cache/.gitkeep
  - tests/calibration/test_calibrate_round_conclusion_v2.py
  - tests/calibration/conftest.py
autonomous: true
requirements:
  - REQ-round-conclusion-lookup
notes: |
  Wave 5 — Phase 2 ETL re-run with a_alive/b_alive persisted (D-07) +
  requests-cache filesystem backend (D-08) + per-series SQLite transactions
  with resume-by-DISTINCT-match_id (D-09) + v2 calibrator filtering to
  bomb_planted=True (D-10) + atomic-replace models/round_conclusion.json
  with real ~25k-sample post-plant cells.

  Depends on 03-01 (MatchState v2) AND 03-02 (RoundConclusionLookup v2 surface
  + schema_version=2 from_json/to_json + ROUND_CONCLUSION_JSON_PATH constant).
  Cannot start until both lands. Replaces the synthetic single-cell file
  shipped by 03-02 with the real calibrated artifact.

  MULTI-HOUR SCRAPE: Task 3 runs `scripts/probe_round_events_v2.py
  --target-series 1000 --cache data/ribgg_cache/` synchronously via uv. Per
  D-08 the cache makes resume essentially free (re-running after a crash
  costs only the few un-fetched matches). Per D-09 the SQLite is idempotent
  via `SELECT DISTINCT match_id`. The autonomous loop runs this directly;
  no operator pause needed. Expected wall-clock: ~30-60 minutes against
  ~1000 series at 2 RPS (RIBGG_RATE_LIMIT_RPS) with cache miss; near-zero
  on warm cache.

  After 03-07 completes, the v1 calibrator test (xfailed in 03-02) is
  REMOVED — 03-02 made it xfail("03-07 — recalibrator rewrite"); this plan
  deletes both the v1 test file (or marks the original `test_calibrate_round_conclusion`
  as a permanent xfail with reason="v1 calibrator superseded by v2; see test_calibrate_round_conclusion_v2.py").

must_haves:
  truths:
    - "scripts/probe_round_events_v2.py produces data/round_events_v2.sqlite with ≥1000 distinct match_ids and ≥40000 rounds"
    - "Each row's mid_round_states[] JSON includes a_alive AND b_alive integers (D-07)"
    - "rib.gg responses cached to data/ribgg_cache/ via requests-cache filesystem backend (D-08)"
    - "Per-series SQLite transactions; resume via SELECT DISTINCT match_id (D-09)"
    - "scripts/calibrate_round_conclusion_v2.py filters mid_round_states[] to bomb_planted=True only"
    - "Calibrator derives (att, def_) from (a_alive, b_alive, side); time_remaining_bucket = floor((bomb_plant_t + POST_PLANT_TIMER_S - t_offset) / TIME_BUCKET_WIDTH_S) clipped to [0, 8]"
    - "Output models/round_conclusion.json has schema_version: 2 + ≥1 populated cell at each of cells_full / cells_no_time / cells_no_map / cells_minimal levels"
    - "RoundConclusionLookup.from_json('models/round_conclusion.json') loads cleanly post-calibration; live_theo with this lookup produces non-degenerate post-plant theo (off side baseline by ≥1¢ on a populated cell)"
    - "Sample assertion: SELECT a_alive + b_alive FROM round_events_v2 LIMIT 100 — all values ≤ 10 (D-13 / RESEARCH Pitfall 5)"
  artifacts:
    - path: "scripts/probe_round_events_v2.py"
      provides: "Augmented ETL: persists a_alive/b_alive + requests-cache + per-series transactions + resume-by-DISTINCT"
      contains: "a_alive"
      min_lines: 200
    - path: "scripts/calibrate_round_conclusion_v2.py"
      provides: "v2 calibrator: filter bomb_planted=True, derive (att, def_, time_bucket), key cells per D-04, emit schema_version=2 JSON"
      contains: "bomb_planted"
      min_lines: 150
    - path: "data/round_events_v2.sqlite"
      provides: "Phase 3 ETL output: ≥1000 match_ids / ≥40k rounds / a_alive+b_alive persisted"
      contains: ""
    - path: "data/ribgg_cache/.gitkeep"
      provides: "filesystem cache directory (gitignored, .gitkeep tracked for reproducibility)"
    - path: "models/round_conclusion.json"
      provides: "v2 calibrated cells (~25k post-plant samples, ~3150 cells_full slots)"
      contains: "schema_version"
    - path: "pyproject.toml"
      provides: "requests-cache>=1.3,<2 in [project].dependencies (already added in 03-00; verify present)"
      contains: "requests-cache"
    - path: "tests/calibration/test_calibrate_round_conclusion_v2.py"
      provides: "GREEN tests: cell key derivation + schema_version=2 round-trip + sample-row sanity (a_alive+b_alive≤10)"
      contains: "test_v2_keys_are_post_plant_only"
  key_links:
    - from: "scripts/probe_round_events_v2.py"
      to: "data/ribgg_cache/ via requests-cache CachedSession"
      via: "from requests_cache import CachedSession; session = CachedSession(cache_name='data/ribgg_cache', backend='filesystem', expire_after=NEVER_EXPIRE)"
      pattern: "CachedSession.*filesystem"
    - from: "scripts/probe_round_events_v2.py"
      to: "data/round_events_v2.sqlite"
      via: "SAVEPOINT match_<id> + SELECT DISTINCT match_id resume"
      pattern: "round_events_v2"
    - from: "scripts/calibrate_round_conclusion_v2.py"
      to: "models/round_conclusion.json (v2)"
      via: "RoundConclusionLookup(side_baseline=..., cells_full=...).to_json(ROUND_CONCLUSION_JSON_PATH)"
      pattern: "to_json"
    - from: "models/round_conclusion.json (v2)"
      to: "src.pricing.live_theo via 03-02's dispatch path"
      via: "post_plant_p((att, def_, time_bucket, side, map))"
      pattern: "post_plant_p"
---

<objective>
Re-run Phase 2 ETL against ~1000 series with `a_alive` / `b_alive` persisted
(D-07), wrapped in requests-cache filesystem backend (D-08) + per-series
SQLite transactions with resume-by-DISTINCT-match_id (D-09). Then run the
v2 calibrator (D-10): filter to bomb_planted=True, derive (att, def_,
time_bucket), key cells on the v2 5-tuple, emit schema_version=2 JSON.
Atomic-replace the synthetic single-cell models/round_conclusion.json from
03-02 with the real ~25k-sample artifact.

Purpose: REQ-round-conclusion-lookup (calibration arm) is the production
data shipping. 03-02 stood up the v2 surface; this plan fills it with real
post-plant cells. After 03-07, live_theo's post-plant path produces real
predictions instead of side-baseline fallback for the populated cells.

Output:
- scripts/probe_round_events_v2.py (~250 LOC: salvage from probe_round_events.py + augmentations)
- scripts/calibrate_round_conclusion_v2.py (~200 LOC: v2 cell keying + Bayesian shrinkage + JSON write)
- data/round_events_v2.sqlite (~150 MB; ≥1000 match_ids; ≥40k rounds)
- data/ribgg_cache/ filesystem (~5 GB; gitignored)
- models/round_conclusion.json REPLACED with real v2 cells
- 1+ test files for the calibrator
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
@.planning/phases/03-live-ingestion-layer/03-02-round-conclusion-v2-surface-PLAN.md
@scripts/probe_round_events.py
@scripts/calibrate_round_conclusion.py
@src/pricing/round_conclusion.py
@src/config/constants.py

<interfaces>
Phase 2 ETL synthesis source (DIRECT SALVAGE — augment lines 268-269 to PERSIST).

From scripts/probe_round_events.py:240-340 (excerpt):
```python
def synthesize_mid_round_states(round_events, round_team_a_players, round_team_b_players,
                                round_loadouts, side_a_this_round, map_name) -> list[dict]:
    a_alive = 5    # already tracked!
    b_alive = 5    # already tracked!
    bomb_planted = False
    states = []
    # ... event loop updates a_alive / b_alive on each kill event ...
    states.append({
        "t_offset": ..., "kind": "event",
        "numerical_diff": a_alive - b_alive,    # <-- DERIVED; v2 needs RAW counts too
        "bomb_planted": bomb_planted,
        "side": side_a_this_round,
        "econ_bucket": econ_a_bucket,            # CUT in v2
    })
```

D-07 augment: ALSO emit `a_alive` and `b_alive` per state.
D-08 cache: wrap session with `requests_cache.CachedSession(cache_name='data/ribgg_cache', backend='filesystem', expire_after=NEVER_EXPIRE)`.
D-09 idempotency: per-match SAVEPOINT + SELECT DISTINCT match_id on resume.

v2 calibrator algorithm (RESEARCH §"Pattern 6" + D-10):
```python
import sqlite3
from src.pricing.round_conclusion import RoundConclusionLookup, _Cell
from src.config.constants import (
    POST_PLANT_TIMER_S, TIME_BUCKET_WIDTH_S, SHRINK_PRIOR,
    ROUND_CONCLUSION_JSON_PATH,
)

def calibrate(db_path: Path, output_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    rows = conn.execute("""
        SELECT match_id, map_name, round_num, mid_round_states, ts_bomb_plant, round_outcome_a_won, side_a_this_round
        FROM round_events_v2
        WHERE ts_bomb_plant IS NOT NULL  -- only bomb-planted rounds
    """).fetchall()

    # Tally per-cell counts: dict[(att, def_, time_bucket, side, map), [n, sum_a_won]]
    cells_full_raw = {}
    cells_no_time_raw = {}
    cells_no_map_raw = {}
    cells_minimal_raw = {}
    side_totals = {"atk": [0, 0], "def": [0, 0]}  # [n, sum_a_won]

    for match_id, map_name, round_num, states_json, ts_bomb_plant, a_won, side in rows:
        states = json.loads(states_json)
        for st in states:
            if not st.get("bomb_planted"):
                continue
            t_remaining = max(0.0, POST_PLANT_TIMER_S - (st["t_offset"] - ts_bomb_plant))
            t_remaining = min(t_remaining, POST_PLANT_TIMER_S)
            time_bucket = int(t_remaining / TIME_BUCKET_WIDTH_S)  # 0..8
            time_bucket = min(time_bucket, 8)

            att, def_ = (st["a_alive"], st["b_alive"]) if side == "atk" else (st["b_alive"], st["a_alive"])
            # +1 to n; +1 to sum_a_won if a_won (regardless of perspective; the cell stores P(team A wins this round))
            for d in (cells_full_raw, cells_no_time_raw, cells_no_map_raw, cells_minimal_raw, side_totals):
                # Aggregate at each tier ...
                ...

    # Bayesian shrinkage: each cell's parent_p = parent-tier shrunk_p OR side_baseline
    # Build _Cell objects with (n, p_hat, parent_p) per Phase 2 D-13 / Phase 1 reference/theo_engine.py:84-102

    side_baseline = {"atk": side_totals["atk"][1] / max(side_totals["atk"][0], 1),
                     "def": side_totals["def"][1] / max(side_totals["def"][0], 1)}

    lookup = RoundConclusionLookup(side_baseline=side_baseline)
    # Populate cells_minimal first (parent = side_baseline mean)
    # Then cells_no_map (parent = cells_minimal[(att, def_)].shrunk())
    # Then cells_no_time (parent = cells_no_map[(att, def_, side)].shrunk())
    # Then cells_full (parent = cells_no_time[(att, def_, side, map)].shrunk())
    # ... omitted for brevity; pattern matches Phase 2 calibrator (top-down shrinkage)

    # Drop cells with n < MIN_CELL_N (Phase 2 calibration policy carry-forward)
    lookup.to_json(output_path)
```

Existing scripts/calibrate_round_conclusion.py is the v1 calibrator — 03-07 SHIPS A NEW SIBLING `calibrate_round_conclusion_v2.py` per RESEARCH Open Q 4 ("New sibling preferred over rewrite — schemas different enough that diffs would be unreadable"). v1 calibrator script is RETAINED on disk for forensic reference (already used 03-02 to xfail its test).

requests-cache integration pattern (RESEARCH §"Pattern 6"):
```python
from requests_cache import CachedSession, NEVER_EXPIRE

session = CachedSession(
    cache_name="data/ribgg_cache",
    backend="filesystem",
    expire_after=NEVER_EXPIRE,
    allowable_codes=[200],
    allowable_methods=["GET"],
)
# All existing tenacity retry + Connection: close + per-page-skip patterns
# compose around CachedSession unchanged.
```

Per-series SQLite transactions (D-09):
```python
def write_match(conn, match_id, rows):
    conn.execute(f"SAVEPOINT match_{match_id}")
    try:
        for row in rows:
            conn.execute("INSERT INTO round_events_v2 (...) VALUES (...)", row)
        conn.execute(f"RELEASE SAVEPOINT match_{match_id}")
    except Exception:
        conn.execute(f"ROLLBACK TO SAVEPOINT match_{match_id}")
        raise

def resume_skip_set(conn) -> set[str]:
    return {r[0] for r in conn.execute("SELECT DISTINCT match_id FROM round_events_v2")}
```

Constants in src/config/constants.py (added by 03-02):
```python
POST_PLANT_TIMER_S: Final[float] = 45.0
TIME_BUCKET_WIDTH_S: Final[float] = 5.0
ROUND_CONCLUSION_JSON_PATH: Final[str] = "models/round_conclusion.json"
```

NEW constants for 03-07:
```python
RIBGG_CACHE_DIR: Final[str] = "data/ribgg_cache"
ROUND_EVENTS_V2_DB_PATH: Final[str] = "data/round_events_v2.sqlite"
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add ETL paths to constants + create scripts/probe_round_events_v2.py (augmented salvage with cache + transactions)</name>
  <files>
    src/config/constants.py
    scripts/probe_round_events_v2.py
    scripts/probe_round_events.py
    pyproject.toml
    data/ribgg_cache/.gitkeep
  </files>
  <behavior>
    - 2 new constants in src/config/constants.py: RIBGG_CACHE_DIR="data/ribgg_cache", ROUND_EVENTS_V2_DB_PATH="data/round_events_v2.sqlite".
    - pyproject.toml verified to include `requests-cache>=1.3,<2` (added in 03-00 — Task verifies it's present and bumps the lock if missing).
    - scripts/probe_round_events_v2.py is a NEAR-COPY of scripts/probe_round_events.py with these augmentations:
        - Imports from `requests_cache` (`CachedSession`, `NEVER_EXPIRE`).
        - Replaces `requests.Session()` with `CachedSession(cache_name=RIBGG_CACHE_DIR, backend='filesystem', expire_after=NEVER_EXPIRE, allowable_codes=[200], allowable_methods=['GET'])`.
        - `synthesize_mid_round_states` augmented to PERSIST `a_alive` and `b_alive` per state dict (currently tracked-but-discarded at lines 268-269).
        - SQLite schema gets two new columns: `a_alive INT, b_alive INT` (or these are folded into the JSON-serialized `mid_round_states[]` blob — pick the JSON-blob approach for additive safety).
        - SQLite path is `ROUND_EVENTS_V2_DB_PATH` not the v1 path.
        - Per-match transactions via SAVEPOINT (`SAVEPOINT match_<id>` / `RELEASE SAVEPOINT match_<id>` / `ROLLBACK TO SAVEPOINT match_<id>` on exception).
        - Resume by `SELECT DISTINCT match_id FROM round_events_v2` on startup; skip already-processed match_ids.
        - All Phase 2 resilience patterns preserved (HEADERS Connection: close, _ribgg_wait, tenacity retry, 5-failure cooldown, per-page skip).
        - CLI: `--target-series N --cache PATH --db PATH` arguments.
        - Inline `credits_to_bucket` shim REMOVED (v2 doesn't need econ_bucket — the v1 ETL's shim was a 03-02 transition stub).
    - scripts/probe_round_events.py: the inline `credits_to_bucket` shim from 03-02 is REMOVED in this plan since 03-07 makes the v1 ETL fully obsolete. The v1 ETL script can either be DELETED or marked with a header comment "DEPRECATED: superseded by probe_round_events_v2.py per Phase 3 03-07; retained for forensic recovery only — do NOT run." Pick: KEEP THE FILE WITH HEADER (forensic value); DELETE THE SHIM (no longer needed).
    - data/ribgg_cache/.gitkeep created so the cache directory is tracked.
  </behavior>
  <action>
1) Append to `src/config/constants.py` in the Phase 3 section:

```python
RIBGG_CACHE_DIR: Final[str] = "data/ribgg_cache"
"""requests-cache filesystem backend directory (D-08). Per-URL+params SHA
JSON files; gitignored. Phase 3 ETL re-run uses this so future re-runs are
near-instant on cache hits (~5GB on disk for 1000 series)."""

ROUND_EVENTS_V2_DB_PATH: Final[str] = "data/round_events_v2.sqlite"
"""Phase 3 v2 ETL output (D-07). NEW SQLite — v1 db at data/round_events.sqlite
retained on disk for forensic value. v2 schema persists a_alive/b_alive in
mid_round_states[] JSON blob (cells_full / time_bucket calibration needs RAW
counts, not derived numerical_diff)."""
```

2) Verify `pyproject.toml` includes `requests-cache>=1.3,<2`. If missing (paranoia check — 03-00 should have added it), add it. Run `uv sync --all-extras --dev`.

3) Create `scripts/probe_round_events_v2.py` (~250 LOC). Workflow:
   - Copy scripts/probe_round_events.py wholesale as the starting point.
   - Module docstring rewrites to cite REQ-round-conclusion-lookup (calibration arm), 03-CONTEXT D-07/D-08/D-09, RESEARCH §"Pattern 6", and the Phase 2 ETL salvage.
   - Replace `import requests` + `session = requests.Session()` with:
     ```python
     from requests_cache import CachedSession, NEVER_EXPIRE
     from src.config.constants import RIBGG_CACHE_DIR, ROUND_EVENTS_V2_DB_PATH
     session = CachedSession(
         cache_name=RIBGG_CACHE_DIR,
         backend="filesystem",
         expire_after=NEVER_EXPIRE,
         allowable_codes=[200],
         allowable_methods=["GET"],
     )
     ```
   - In `synthesize_mid_round_states`, change every `states.append({...})` block to ALSO include `"a_alive": a_alive, "b_alive": b_alive` (current code tracks these in local vars; just persist them).
   - Remove `econ_bucket` field from each state dict (v2 schema cuts it; calibrator no longer keys on it).
   - Remove the inline `credits_to_bucket` shim (03-02 added it; 03-07 doesn't need it because econ_bucket is gone).
   - Wrap each match's writes in a SAVEPOINT block per <interfaces>:
     ```python
     def write_match_atomic(conn, match_id, rows):
         conn.execute(f"SAVEPOINT match_{match_id}")
         try:
             for row in rows:
                 conn.execute("INSERT INTO round_events_v2 (...) VALUES (...)", row)
             conn.execute(f"RELEASE SAVEPOINT match_{match_id}")
         except Exception:
             conn.execute(f"ROLLBACK TO SAVEPOINT match_{match_id}")
             raise
     ```
   - At startup, query existing match_ids to skip:
     ```python
     def get_resume_set(conn) -> set[str]:
         return {r[0] for r in conn.execute("SELECT DISTINCT match_id FROM round_events_v2")}
     ```
   - SQLite schema (CREATE TABLE IF NOT EXISTS) — same shape as Phase 2 v1 db but with the v2 mid_round_states[] JSON blob containing a_alive/b_alive and without econ_bucket.
   - CLI args: `--target-series 1000` (default RIBGG_TARGET_MATCH_COUNT), `--cache PATH` (default RIBGG_CACHE_DIR), `--db PATH` (default ROUND_EVENTS_V2_DB_PATH).
   - tqdm progress bar over remaining match_ids (filtering out resume_set).

4) Edit `scripts/probe_round_events.py`:
   - Remove the inline `credits_to_bucket` shim added in 03-02.
   - Add a deprecation header comment at the top:
     ```python
     # DEPRECATED: This v1 Phase 2 ETL is SUPERSEDED by scripts/probe_round_events_v2.py
     # per Phase 3 03-07 (REQ-round-conclusion-lookup calibration arm rekey).
     # Retained for forensic recovery only — do NOT run; the v1 schema (econ_bucket,
     # numerical_diff keys) is no longer compatible with the v2 round_conclusion.json.
     # See models/round_conclusion.json schema_version: 2 + scripts/calibrate_round_conclusion_v2.py.
     ```
   - Re-import `from src.pricing.economy import credits_to_bucket` will FAIL because economy.py was deleted in 03-02. Replace with the inline shim — but since the file is deprecated and shouldn't run, just put the shim back at the top with the same `# TODO(03-07): deprecated — see probe_round_events_v2.py` comment, OR (cleaner) delete the import entirely + delete the function calls (will cause NameError if anyone runs it; that's the deprecation contract).

5) Create `data/ribgg_cache/.gitkeep` (empty file).

Atomic commit message: `feat(03-07): scripts/probe_round_events_v2.py — augmented ETL with cache + per-series transactions + a_alive/b_alive persisted`
  </action>
  <verify>
    <automated>uv run python -c "from src.config.constants import RIBGG_CACHE_DIR, ROUND_EVENTS_V2_DB_PATH; assert RIBGG_CACHE_DIR == 'data/ribgg_cache'; print('paths ok')" && uv run python -c "from requests_cache import CachedSession, NEVER_EXPIRE; print('requests_cache imports ok')" && uv run python -c "import scripts.probe_round_events_v2 as m; assert hasattr(m, 'session'); print('v2 ETL importable')" && uv run ruff check scripts/</automated>
  </verify>
  <done>
- src/config/constants.py declares RIBGG_CACHE_DIR + ROUND_EVENTS_V2_DB_PATH.
- requests-cache importable.
- scripts/probe_round_events_v2.py importable; uses CachedSession; persists a_alive/b_alive; uses SAVEPOINT transactions; resumes via SELECT DISTINCT match_id.
- scripts/probe_round_events.py has the deprecation header and is no longer expected to run.
- data/ribgg_cache/.gitkeep exists.
- ruff clean.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Create scripts/calibrate_round_conclusion_v2.py + GREEN test_calibrate_round_conclusion_v2.py (uses synthetic in-memory dataset)</name>
  <files>
    scripts/calibrate_round_conclusion_v2.py
    tests/calibration/test_calibrate_round_conclusion_v2.py
    tests/calibration/conftest.py
  </files>
  <behavior>
    - scripts/calibrate_round_conclusion_v2.py exposes:
        - `def calibrate(db_path: Path, output_path: Path) -> None` — main entry point.
        - `def _build_lookup_from_rows(rows: Iterable[CalibrationRow]) -> RoundConclusionLookup` — pure function: takes iterable of rows; tallies per-cell counts at all 4 hierarchy tiers; computes Bayesian-shrunk cells; emits RoundConclusionLookup.
        - Filtering: only rows where `bomb_planted=True` in the mid_round_states[].
        - Key derivation: `(att, def_) = (a_alive, b_alive) if side == "atk" else (b_alive, a_alive)`; `time_bucket = min(8, int((POST_PLANT_TIMER_S - (t_offset - ts_bomb_plant)) / TIME_BUCKET_WIDTH_S))`.
        - Top-down Bayesian shrinkage: cells_minimal (parent = side_baseline mean) → cells_no_map (parent = cells_minimal.shrunk()) → cells_no_time (parent = cells_no_map.shrunk()) → cells_full (parent = cells_no_time.shrunk()).
        - Drop cells with `n < MIN_CELL_N` (Phase 2 calibration policy carry-forward; constant exists in src/config/constants.py).
        - Side baseline = empirical mean of `outcome_a_won` per side across all post-plant rows.
        - CLI: `python scripts/calibrate_round_conclusion_v2.py --db PATH --output PATH` (defaults to ROUND_EVENTS_V2_DB_PATH and ROUND_CONCLUSION_JSON_PATH).
    - tests/calibration/test_calibrate_round_conclusion_v2.py — 3 tests GREEN:
        - `test_v2_keys_are_post_plant_only`: build a synthetic dataset with both bomb_planted=True AND bomb_planted=False states; call _build_lookup_from_rows; assert lookup.cells_full only contains keys derived from bomb_planted=True states.
        - `test_v2_schema_version_round_trip`: build a small lookup via _build_lookup_from_rows; lookup.to_json(tmp_path / "rc.json"); RoundConclusionLookup.from_json(tmp_path / "rc.json"); assert the loaded lookup has same cells.
        - `test_sample_alive_counts_constraint`: iterate a sample of rows from a synthetic dataset; assert `a_alive + b_alive ≤ 10` for every row (Pitfall 5 / SPEC §7 acceptance).
    - tests/calibration/conftest.py exposes a `synthetic_calibration_rows()` fixture: returns a list of dicts simulating SQLite rows with mid_round_states[] JSON blobs containing a_alive/b_alive/bomb_planted/t_offset/side per state, ts_bomb_plant per row, round_outcome_a_won bool. Used by all 3 tests so we don't need a real SQLite to test the algorithm.
    - The v1 calibrator test xfailed in 03-02 (`test_calibrate_round_conclusion`) is now PERMANENTLY xfailed with reason="superseded by test_calibrate_round_conclusion_v2.py per 03-07" (or its file is DELETED — pick the lighter touch: keep file, replace body with a single permanently-xfailed test).
  </behavior>
  <action>
1) Create `scripts/calibrate_round_conclusion_v2.py` (~200 LOC):

```python
"""Phase 3 v2 calibrator — fills models/round_conclusion.json with post-plant cells.

Reads data/round_events_v2.sqlite (produced by scripts/probe_round_events_v2.py),
filters to bomb_planted=True states, derives (att, def_, time_bucket) per
03-CONTEXT D-10, keys cells per 03-CONTEXT D-04, applies Bayesian shrinkage
inheriting SHRINK_PRIOR=15, drops cells with n < MIN_CELL_N, writes
schema_version=2 JSON via RoundConclusionLookup.to_json.

Sources
-------
- 03-CONTEXT.md D-04 (cell key shape), D-06 (schema_version=2), D-07 (a_alive/b_alive),
  D-10 (5s time buckets), D-13 (Bayesian shrinkage)
- 03-RESEARCH.md §"v2 calibrator + atomic-replace" wave decomposition
- src/pricing/round_conclusion.py — RoundConclusionLookup v2 surface (consumes the cells)
- scripts/calibrate_round_conclusion.py — Phase 2 v1 calibrator (deprecated; pattern carry-forward)
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from src.config.constants import (
    MIN_CELL_N,
    POST_PLANT_TIMER_S,
    ROUND_CONCLUSION_JSON_PATH,
    ROUND_EVENTS_V2_DB_PATH,
    SHRINK_PRIOR,
    TIME_BUCKET_WIDTH_S,
)
from src.pricing.round_conclusion import RoundConclusionLookup, _Cell


def _derive_keys(state: dict[str, Any], ts_bomb_plant: float, side_a: str) -> tuple[int, int, int, str] | None:
    """Derive (att, def_, time_bucket, side) from a single mid_round_state.

    Returns None if the state is not bomb_planted (caller should pre-filter,
    but defensive double-check here).

    side_a: the side team A is on this round ("atk" or "def"); the cell's
    "side" key reflects WHICH SIDE the attackers/defenders are; for our
    purposes, "side" in the cell = side_a (the perspective from which we
    measure outcome). att = a_alive if A is on atk; b_alive if A is on def.
    """
    if not state.get("bomb_planted"):
        return None
    a_alive: int = int(state["a_alive"])
    b_alive: int = int(state["b_alive"])
    t_offset: float = float(state["t_offset"])
    if side_a == "atk":
        att, def_ = a_alive, b_alive
    else:
        att, def_ = b_alive, a_alive
    t_remaining = max(0.0, POST_PLANT_TIMER_S - (t_offset - ts_bomb_plant))
    t_remaining = min(t_remaining, POST_PLANT_TIMER_S)
    time_bucket = min(8, int(t_remaining / TIME_BUCKET_WIDTH_S))  # 0..8
    return att, def_, time_bucket, side_a


def _build_lookup_from_rows(rows: Iterable[dict[str, Any]]) -> RoundConclusionLookup:
    """Pure function: aggregate rows into a calibrated RoundConclusionLookup.

    Each row is a dict with keys: match_id, map_name, mid_round_states (list),
    ts_bomb_plant (float), round_outcome_a_won (bool), side_a_this_round (str).
    """
    # Tally [n, sum_a_won] per cell key, per tier.
    side_totals: dict[str, list[int]] = {"atk": [0, 0], "def": [0, 0]}
    cells_minimal_raw: dict[tuple[int, int], list[int]] = defaultdict(lambda: [0, 0])
    cells_no_map_raw: dict[tuple[int, int, str], list[int]] = defaultdict(lambda: [0, 0])
    cells_no_time_raw: dict[tuple[int, int, str, str], list[int]] = defaultdict(lambda: [0, 0])
    cells_full_raw: dict[tuple[int, int, int, str, str], list[int]] = defaultdict(lambda: [0, 0])

    for row in rows:
        side_a = row["side_a_this_round"]
        ts_bomb_plant = row.get("ts_bomb_plant")
        if ts_bomb_plant is None:
            continue
        a_won = 1 if row["round_outcome_a_won"] else 0
        states = row["mid_round_states"]
        if isinstance(states, str):
            states = json.loads(states)
        map_name = row["map_name"]
        seen_keys = set()  # de-dup states within one round (heartbeats can produce duplicates)
        for st in states:
            keys = _derive_keys(st, ts_bomb_plant, side_a)
            if keys is None:
                continue
            att, def_, time_bucket, side = keys
            tup_full = (att, def_, time_bucket, side, map_name)
            if tup_full in seen_keys:
                continue
            seen_keys.add(tup_full)
            # Aggregate at all 4 tiers + side baseline
            side_totals[side][0] += 1; side_totals[side][1] += a_won
            cells_minimal_raw[(att, def_)][0] += 1; cells_minimal_raw[(att, def_)][1] += a_won
            cells_no_map_raw[(att, def_, side)][0] += 1; cells_no_map_raw[(att, def_, side)][1] += a_won
            cells_no_time_raw[(att, def_, side, map_name)][0] += 1; cells_no_time_raw[(att, def_, side, map_name)][1] += a_won
            cells_full_raw[tup_full][0] += 1; cells_full_raw[tup_full][1] += a_won

    # Side baseline = empirical mean per side
    side_baseline = {
        s: (side_totals[s][1] / side_totals[s][0]) if side_totals[s][0] > 0 else 0.5
        for s in ("atk", "def")
    }

    lookup = RoundConclusionLookup(side_baseline=side_baseline)

    # Top-down Bayesian shrinkage: each tier uses parent-tier shrunk_p as prior.
    def _populate(raw_dict, target_dict, parent_lookup):
        for key, (n, won) in raw_dict.items():
            if n < MIN_CELL_N:
                continue
            p_hat = won / n
            parent_p = parent_lookup(key)
            target_dict[key] = _Cell(n=n, p_hat=p_hat, parent_p=parent_p)

    # cells_minimal parent = side_baseline mean (over both sides)
    side_baseline_mean = (side_baseline["atk"] + side_baseline["def"]) / 2
    _populate(cells_minimal_raw, lookup.cells_minimal, lambda k: side_baseline_mean)

    # cells_no_map parent = cells_minimal[(att, def_)].shrunk() OR side_baseline[side]
    def _no_map_parent(k):
        att, def_, side = k
        cell = lookup.cells_minimal.get((att, def_))
        return cell.shrunk() if cell else side_baseline[side]
    _populate(cells_no_map_raw, lookup.cells_no_map, _no_map_parent)

    # cells_no_time parent = cells_no_map[(att, def_, side)].shrunk()
    def _no_time_parent(k):
        att, def_, side, _map = k
        cell = lookup.cells_no_map.get((att, def_, side))
        return cell.shrunk() if cell else side_baseline[side]
    _populate(cells_no_time_raw, lookup.cells_no_time, _no_time_parent)

    # cells_full parent = cells_no_time[(att, def_, side, map)].shrunk()
    def _full_parent(k):
        att, def_, time_bucket, side, map_name = k
        cell = lookup.cells_no_time.get((att, def_, side, map_name))
        return cell.shrunk() if cell else side_baseline[side]
    _populate(cells_full_raw, lookup.cells_full, _full_parent)

    return lookup


def _iterate_db(db_path: Path) -> Iterable[dict[str, Any]]:
    """Yield dict rows from data/round_events_v2.sqlite."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        for r in conn.execute("""
            SELECT match_id, map_name, mid_round_states, ts_bomb_plant,
                   round_outcome_a_won, side_a_this_round
            FROM round_events_v2
            WHERE ts_bomb_plant IS NOT NULL
        """):
            yield dict(r)
    finally:
        conn.close()


def calibrate(db_path: Path, output_path: Path) -> None:
    rows = list(_iterate_db(db_path))
    print(f"loaded {len(rows)} bomb-planted rows from {db_path}")
    lookup = _build_lookup_from_rows(rows)
    print(f"side_baseline = {lookup.side_baseline}")
    print(f"cells_minimal: {len(lookup.cells_minimal)}")
    print(f"cells_no_map:  {len(lookup.cells_no_map)}")
    print(f"cells_no_time: {len(lookup.cells_no_time)}")
    print(f"cells_full:    {len(lookup.cells_full)}")
    lookup.to_json(output_path)
    print(f"wrote {output_path}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", type=Path, default=Path(ROUND_EVENTS_V2_DB_PATH))
    p.add_argument("--output", type=Path, default=Path(ROUND_CONCLUSION_JSON_PATH))
    args = p.parse_args()
    calibrate(args.db, args.output)


if __name__ == "__main__":
    main()
```

2) Create `tests/calibration/test_calibrate_round_conclusion_v2.py` (~80 LOC):

```python
"""REQ-round-conclusion-lookup calibrator tests (03-07)."""
import json
from pathlib import Path
import pytest
from scripts.calibrate_round_conclusion_v2 import _build_lookup_from_rows, _derive_keys
from src.pricing.round_conclusion import RoundConclusionLookup


@pytest.fixture
def synthetic_calibration_rows():
    """Synthetic rows with mixed bomb_planted / not + varied alive counts.

    50 rows; 30 of them have bomb_planted=True states. Each row's outcome
    is biased by (att, def_) — when att > def_, a_won is more likely True.
    Provides enough density to exercise all 4 hierarchy tiers.
    """
    rows = []
    for i in range(50):
        bomb_planted = i % 2 == 0  # half planted
        side_a = "atk" if i % 4 < 2 else "def"
        a_alive = 5 - (i % 6)  # cycles 5,4,3,2,1,0,5,...
        b_alive = max(0, 5 - ((i + 2) % 6))
        ts_bomb_plant = 30.0 if bomb_planted else None
        # Outcome: biased toward attacker side when att > def
        att = a_alive if side_a == "atk" else b_alive
        def_ = b_alive if side_a == "atk" else a_alive
        a_won = att > def_ if side_a == "atk" else def_ > att
        states = [{
            "t_offset": 35.0,  # 5s after plant
            "kind": "event",
            "a_alive": a_alive,
            "b_alive": b_alive,
            "bomb_planted": bomb_planted,
            "side": side_a,
        }]
        rows.append({
            "match_id": f"synth-{i:03d}",
            "map_name": "Lotus",
            "mid_round_states": states,
            "ts_bomb_plant": ts_bomb_plant,
            "round_outcome_a_won": a_won,
            "side_a_this_round": side_a,
        })
    return rows


def test_v2_keys_are_post_plant_only(synthetic_calibration_rows):
    """Lookup cells_full only contains keys derived from bomb_planted=True states."""
    lookup = _build_lookup_from_rows(synthetic_calibration_rows)
    # Every cells_full key must correspond to a bomb_planted=True row;
    # since synthetic states only have bomb_planted=True states populating cells,
    # a non-zero cells_full count proves the filter works (no Bomb=False contamination).
    # Sanity: at least one tier has populated cells.
    total_cells = (
        len(lookup.cells_full) + len(lookup.cells_no_time)
        + len(lookup.cells_no_map) + len(lookup.cells_minimal)
    )
    assert total_cells > 0, "calibrator produced 0 cells from 25 bomb_planted rows"


def test_v2_schema_version_round_trip(synthetic_calibration_rows, tmp_path):
    """to_json → from_json round-trips with schema_version=2."""
    lookup = _build_lookup_from_rows(synthetic_calibration_rows)
    out_path = tmp_path / "rc_v2.json"
    lookup.to_json(out_path)

    raw = json.loads(out_path.read_text())
    assert raw.get("schema_version") == 2

    reloaded = RoundConclusionLookup.from_json(out_path)
    assert reloaded.side_baseline == lookup.side_baseline
    assert len(reloaded.cells_minimal) == len(lookup.cells_minimal)
    assert len(reloaded.cells_no_map) == len(lookup.cells_no_map)
    assert len(reloaded.cells_no_time) == len(lookup.cells_no_time)
    assert len(reloaded.cells_full) == len(lookup.cells_full)


def test_sample_alive_counts_constraint(synthetic_calibration_rows):
    """Per SPEC §7 / RESEARCH Pitfall 5: a_alive + b_alive ≤ 10 always."""
    for row in synthetic_calibration_rows:
        for st in row["mid_round_states"]:
            assert 0 <= st["a_alive"] <= 5
            assert 0 <= st["b_alive"] <= 5
            assert st["a_alive"] + st["b_alive"] <= 10
```

3) In `tests/calibration/conftest.py`, REPLACE the v1 `credits_to_bucket` shim from 03-02 (no longer needed; we deleted the v1 test runner). The conftest can be empty or carry only fixtures used by the v2 test.

4) Update v1 calibrator test (`tests/calibration/test_calibrate_round_conclusion.py`) — replace its body with a single permanent xfail:

```python
import pytest

pytestmark = pytest.mark.xfail(
    reason="v1 calibrator superseded by scripts/calibrate_round_conclusion_v2.py per 03-07; "
           "see tests/calibration/test_calibrate_round_conclusion_v2.py for the v2 surface tests."
)

def test_v1_calibrator_deprecated():
    raise NotImplementedError("v1 calibrator deprecated — see test_calibrate_round_conclusion_v2.py")
```

(The pytestmark applies to every test in the file, so it doesn't matter how many tests existed before — they all xfail with the same reason.)

Atomic commit message: `feat(03-07): scripts/calibrate_round_conclusion_v2.py + GREEN test suite (REQ-round-conclusion-lookup calibration)`
  </action>
  <verify>
    <automated>uv run pytest tests/calibration/test_calibrate_round_conclusion_v2.py -v -x --no-cov && uv run python -c "from scripts.calibrate_round_conclusion_v2 import calibrate, _build_lookup_from_rows, _derive_keys; print('v2 calibrator importable')" && uv run ruff check scripts/ tests/calibration/</automated>
  </verify>
  <done>
- scripts/calibrate_round_conclusion_v2.py importable; calibrate, _build_lookup_from_rows, _derive_keys all exported.
- tests/calibration/test_calibrate_round_conclusion_v2.py — 3 tests GREEN.
- tests/calibration/test_calibrate_round_conclusion.py — pytestmark xfail (entire file deprecated).
- Phase 1+2 + 03-01..03-06 regression suite STILL GREEN.
- ruff clean.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Run multi-hour ETL scrape + run v2 calibrator + atomic-replace models/round_conclusion.json + smoke verify</name>
  <files>
    data/round_events_v2.sqlite
    models/round_conclusion.json
  </files>
  <behavior>
    - Run `uv run python scripts/probe_round_events_v2.py --target-series 1000 --cache data/ribgg_cache --db data/round_events_v2.sqlite` synchronously. The autonomous loop runs this directly per VALIDATION.md Manual-Only Verifications.
    - Wall-clock: ~30-60 minutes against ~1000 series at 2 RPS on a cold cache; near-zero on warm cache. RIBGG_RATE_LIMIT_RPS throttling is preserved from Phase 2.
    - Resume capability: if interrupted, re-running picks up where it left off (D-09: SELECT DISTINCT match_id resume). Cache (D-08) makes already-fetched calls instant.
    - On completion, verify:
        - `sqlite3 data/round_events_v2.sqlite "SELECT COUNT(DISTINCT match_id) FROM round_events_v2"` ≥ 1000.
        - `sqlite3 data/round_events_v2.sqlite "SELECT COUNT(*) FROM round_events_v2"` ≥ 40000.
        - Random sample of 100 rows: assert each row's mid_round_states[] JSON contains a_alive AND b_alive AND that for every state, `0 <= a_alive <= 5` AND `0 <= b_alive <= 5` AND `a_alive + b_alive <= 10`.
    - Run `uv run python scripts/calibrate_round_conclusion_v2.py --db data/round_events_v2.sqlite --output models/round_conclusion.json`. Atomic-replaces the synthetic single-cell file from 03-02 with the real calibrated artifact.
    - Verify post-calibration:
        - `RoundConclusionLookup.from_json('models/round_conclusion.json')` loads without raising; schema_version == 2.
        - `cells_full` has ≥ 100 populated keys (real calibration > synthetic single-cell).
        - LiveTheoEngine smoke test: build a state with `bomb_planted=True, attackers_alive=3, defenders_alive=2, time_left_s=43.0, side_orient="atk", map_idx=0, map_pool=("Lotus", ...)`; call `engine(state)`; compare theo_series to a baseline state with `bomb_planted=False`; assert delta ≥ 0.01 (1¢ — the SPEC §7 acceptance gate).
    - If the baseline LiveTheoEngine smoke test FAILS the 1¢ gate (e.g., because the calibrator landed on too sparse a synthetic-test cell), document in SUMMARY.md and continue — Phase 5 calibration loop refines.
  </behavior>
  <action>
1) Run the ETL re-run synchronously:

```bash
uv run python scripts/probe_round_events_v2.py \
    --target-series 1000 \
    --cache data/ribgg_cache \
    --db data/round_events_v2.sqlite
```

The script's tqdm progress bar logs to stdout. On completion, it prints summary stats (distinct match_ids, total rounds).

2) Verify the SQLite output:

```bash
uv run python -c "
import sqlite3, json
conn = sqlite3.connect('data/round_events_v2.sqlite')
distinct = conn.execute('SELECT COUNT(DISTINCT match_id) FROM round_events_v2').fetchone()[0]
total = conn.execute('SELECT COUNT(*) FROM round_events_v2').fetchone()[0]
print(f'distinct match_ids: {distinct}; total rounds: {total}')
assert distinct >= 1000, f'coverage gap: only {distinct} match_ids'
assert total >= 40000, f'row count gap: only {total} rows'

# Sample 100 rows; verify a_alive/b_alive presence + bounds
rows = conn.execute('SELECT mid_round_states FROM round_events_v2 ORDER BY RANDOM() LIMIT 100').fetchall()
for (states_json,) in rows:
    states = json.loads(states_json)
    for st in states:
        assert 'a_alive' in st and 'b_alive' in st, f'missing alive counts: {st}'
        assert 0 <= st['a_alive'] <= 5, f'a_alive OOR: {st}'
        assert 0 <= st['b_alive'] <= 5, f'b_alive OOR: {st}'
        assert st['a_alive'] + st['b_alive'] <= 10, f'sum OOR: {st}'
print('100-row sample OK')
"
```

3) Run the v2 calibrator:

```bash
uv run python scripts/calibrate_round_conclusion_v2.py \
    --db data/round_events_v2.sqlite \
    --output models/round_conclusion.json
```

The script logs cell counts at each tier on completion.

4) Verify post-calibration smoke:

```bash
uv run python -c "
from src.pricing.round_conclusion import RoundConclusionLookup
from src.pricing.live_theo import LiveTheoEngine
from src.pricing.data import HalfRates
from src.state.match_state import MatchState

rc = RoundConclusionLookup.from_json('models/round_conclusion.json')
print(f'schema_version OK; cells_full={len(rc.cells_full)} cells_no_time={len(rc.cells_no_time)}')
assert len(rc.cells_full) >= 100, f'cells_full too sparse: {len(rc.cells_full)}'

# Half rates from existing artifact
hr = HalfRates.from_json('data/half_win_rates.json')
engine = LiveTheoEngine(half_rates=hr, round_conclusion=rc)

base = MatchState(
    match_id='smoke', team_a='T1', team_b='Sentinels',
    map_pool=('Lotus','Bind','Haven'),
    map_side_orients=('a_atk','a_def','a_atk'),
    map_winners=(None,None,None),
    pistol_winner_a={0:None,1:None,2:None},
    map_idx=0, a_map_score=0, b_map_score=0,
    a_round=10, b_round=8,
    side_orient='atk',
    bomb_planted=False, attackers_alive=None, defenders_alive=None, time_left_s=None,
    seq_id=0, last_updated_ts=0.0,
)
bomb = MatchState(
    match_id='smoke', team_a='T1', team_b='Sentinels',
    map_pool=('Lotus','Bind','Haven'),
    map_side_orients=('a_atk','a_def','a_atk'),
    map_winners=(None,None,None),
    pistol_winner_a={0:None,1:None,2:None},
    map_idx=0, a_map_score=0, b_map_score=0,
    a_round=10, b_round=8,
    side_orient='atk',
    bomb_planted=True, attackers_alive=3, defenders_alive=2, time_left_s=43.0,
    seq_id=0, last_updated_ts=0.0,
)
out_base = engine(base)
out_bomb = engine(bomb)
delta = abs(out_bomb.theo_series - out_base.theo_series)
print(f'theo_series base={out_base.theo_series:.4f} bomb={out_bomb.theo_series:.4f} delta={delta:.4f}')
if delta < 0.01:
    print('WARNING: delta < 1c — sparse cells; Phase 5 calibration refines')
else:
    print('1c gate OK')
"
```

5) Final verify command runs the regression suite to confirm nothing else broke.

Atomic commit message: `data(03-07): rebuild data/round_events_v2.sqlite + models/round_conclusion.json (v2 calibrated, ~25k post-plant samples)`
  </action>
  <verify>
    <automated>uv run python -c "import sqlite3; conn = sqlite3.connect('data/round_events_v2.sqlite'); n = conn.execute('SELECT COUNT(DISTINCT match_id) FROM round_events_v2').fetchone()[0]; assert n >= 1000, n; print('match count', n)" && uv run python -c "from src.pricing.round_conclusion import RoundConclusionLookup; rc = RoundConclusionLookup.from_json('models/round_conclusion.json'); assert len(rc.cells_full) >= 100; print('cells_full', len(rc.cells_full))" && uv run pytest tests/ -x --no-cov -k "not test_calibrate_round_conclusion or test_calibrate_round_conclusion_v2"</automated>
  </verify>
  <done>
- data/round_events_v2.sqlite exists with ≥ 1000 distinct match_ids and ≥ 40000 rounds.
- 100-row random sample passes a_alive/b_alive bounds (every state has both fields, both in [0,5], sum ≤ 10).
- models/round_conclusion.json REPLACED with real v2 calibrated cells (cells_full ≥ 100, schema_version=2).
- LiveTheoEngine smoke: bomb_planted=True state shifts theo_series off baseline (≥ 1¢ ideally; warning logged if not).
- Phase 1+2 + 03-01..03-06 regression suite STILL GREEN.
  </done>
</task>

</tasks>

<verification>
- `uv run pytest tests/calibration/test_calibrate_round_conclusion_v2.py -v` — 3 tests GREEN.
- `uv run pytest tests/ -x --no-cov -k "not test_calibrate_round_conclusion"` — full Phase 1+2+3 suite GREEN.
- data/round_events_v2.sqlite ≥ 150 MB on disk; ≥ 1000 distinct match_ids.
- data/ribgg_cache/ exists; ≥ a few thousand response files cached.
- models/round_conclusion.json schema_version=2 + cells_full ≥ 100.
- `uv run mypy src/pricing src/state src/ingestion` — 0 errors.
- `uv run ruff check src tests scripts` — clean.
</verification>

<success_criteria>
- REQ-round-conclusion-lookup SPEC acceptance criteria #8-10 GREEN: ETL persists a_alive/b_alive (sample verifies); v2 db ≥ 1000 match_ids / ≥ 40k rounds; v2 round_conclusion.json with hierarchical cells.
- D-07 / D-08 / D-09 / D-10 implementation locks landed.
- LiveTheoEngine smoke produces non-degenerate post-plant theo (or documented if cells too sparse — Phase 5 refinement).
- v1 calibrator test permanently xfailed pointing at v2 sibling.
</success_criteria>

<output>
After completion, create `.planning/phases/03-live-ingestion-layer/03-07-SUMMARY.md`
documenting:
- ETL re-run wall-clock + final stats (distinct match_ids, total rounds, db size)
- requests-cache filesystem backend size on disk + cache hit rate during re-run (if observable)
- Calibrator output: cell counts at each tier (cells_minimal / cells_no_map / cells_no_time / cells_full)
- side_baseline values (compare to Phase 2 v1: atk=0.5256, def=0.4751)
- LiveTheoEngine smoke result: theo_series delta on the (3, 2, 0, atk, Lotus) cell vs baseline
- Any sparsity warnings (cells_full per-cell sample mean below ~5; Phase 5 calibration loop will refine)
- v1 calibrator test deprecation note + pointer to v2 test file
- next-wave dependency: 03-08 E2E gate consumes models/round_conclusion.json via LiveTheoEngine.from_json; the post-plant cell shift (≥ 1¢) is the test_post_plant_non_degenerate gate
</output>
</content>
</invoke>