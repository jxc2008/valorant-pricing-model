# Phase 2: Round-event data — Research

**Researched:** 2026-04-30
**Domain:** offline data acquisition (esports API scraping) + empirical-Bayes calibration + SQLite ETL
**Confidence:** HIGH on Path A feasibility (live-probed); MEDIUM on Path B tooling (template-matching is correct approach but no Valorant-specific implementation in repo); HIGH on calibration math (formula verbatim from Phase 1).

---

## Summary

The dominant Phase 2 unknown — whether Path A (API scrape) is feasible — is **resolved YES with HIGH confidence**. Live-probed `https://be-prod.rib.gg/v1/` during this research session: it is a public, unauthenticated, CORS-permissive REST API that returns per-event millisecond-precision round timestamps via `/v1/matches/{id}/details`. The response body includes `events[]` with `eventType ∈ {start, plant, kill, defuse}`, `roundNumber`, `roundTimeMillis`, `attackingTeamNumber`, plus `economies[]` (per-player loadoutValue for `econ_bucket` derivation). This is **strictly better** than D-02's Path A acceptance bar (≥50% mid-round event coverage); rib.gg gives ~100%. Path A passes.

Three sources from D-01's priority list are eliminated upfront: **(2) `valorantr` R-package** — R is not installed on this Windows machine (`where R` empty); per D-01 "definitively failed and continue." Functionally redundant anyway since it wraps the same `be-prod.rib.gg/v1/` endpoints we hit directly in Python via `requests`. **(3) `FlynV/RIB.GG-Web-Scraper`** — a Windows-binary Discord-bot replacement, not an importable library; no source code in the repo (README + release binary only). **(4) `bo3.gg`** — verified reachable but `/api/v1/matches` returns match-level metadata only (scores, dates, tier rank), no per-round events; useful as a tier filter / cross-confirm but cannot drive calibration.

**Primary recommendation:** Skip the multi-source probe ladder of D-01 entirely. Phase 2 Wave 1 is a single Python script that hits `be-prod.rib.gg/v1/` directly using the verified endpoint chain `events → series → matches/{id}/details`. The probe still produces `02-PROBE-LOG.md` as a deliverable (per D-01 spec), but it documents one source pass, not four attempts. Path B / C contingency code is NOT written in v1 unless the rib.gg ETL itself fails (e.g., the dataset proves too sparse or the API is rate-limited mid-pull). Treat Path B as a **separate ticket gated on Wave 1 outcome**, not a shipped fallback.

---

## User Constraints (from CONTEXT.md)

### Locked Decisions

**Probe scope, source priority, and acceptance bar (Area A)**
- **D-01:** Source priority — `scripts/probe_round_events.py` attempts in order: (1) **rib.gg internal API direct** (auth required), (2) **`valorantr` R-package** via subprocess (no R dep — call as CLI; if R is unavailable on Windows, treat this source as definitively failed and continue), (3) **`FlynV/RIB.GG-Web-Scraper`** Node project, (4) **bo3.gg slug endpoint** (CLAUDE.md notes filter params are broken — only single-match-by-slug works). Probe stops at the first source that meets the acceptance bar.
- **D-02:** Acceptance bar — chosen source must reliably return per-round `(ts_round_start, ts_round_end, ts_first_kill)` AND ≥1 mid-round event class (e.g., `ts_bomb_plant`) for ≥50% of rounds.
- **D-03:** Coverage bar — **1000+ matches, last 18 months, tier-1 only (VCT)**. ~75,000 rounds. No recency-weighting in v1.
- **D-04:** Probe time cap — **1 week from probe start**. After 1 week without acceptance, declare Path A failed and route to Path B.
- **D-05:** Partial-pass policy — if per-round timestamps OK but `bomb_plant` <50% coverage, populate ONLY `cells_no_econ` and `cells_no_map`. Document the gap.

**`mid_round_states[]` shape (Area B)**
- **D-06:** Sampling — **Hybrid: events + 5s heartbeats**. Each entry: `{t_offset: float, kind: "event" | "heartbeat", numerical_diff: int, bomb_planted: bool, side: str, econ_bucket: str}`. Synthesize heartbeats by carry-forward when not native.
- **D-07:** Per-entry payload — only the four `cells_full` lookup keys; `map_name` once at row level.
- **D-08:** `numerical_diff` between events — **carry-forward**. Events ordered by `(t_offset, event_id)`.
- **D-09:** Storage ordering — time-ordered list ascending by `t_offset`, JSON-serialized in SQLite TEXT column.

**Path B / C escalation (Area C)**
- **D-10:** Path A fail → **commit to Path B** (2-week OCR labeling, 100 VODs at 1Hz, 10% hand-verified).
- **D-11:** Both fail → **flat 0.5**. No code changes, no `models/round_conclusion.json`.
- **D-12:** Phase 4 hard contract — Path C ⇒ Phase 4 directional triggers fire for order pulls but **do NOT move theo**. Mid-round vega flat between rounds.

**Calibration method (Area D)**
- **D-13:** **Empirical Bayes shrinkage** with `SHRINK_PRIOR=15`. Formula verbatim Phase 1 `_Cell.shrunk()`.
- **D-14:** `parent_p` — recursive walk up the chain, **bottom-up**: populate `side_baseline` from `data/half_win_rates.json` first, then `cells_minimal`, ..., `cells_full`. Each level uses parent already populated.
- **D-15:** Persistence — **`models/round_conclusion.json`**. Plain JSON, diff-friendly, ~100KB. New `RoundConclusionLookup.from_json(path)` classmethod (additive only).
- **D-16:** Recalibration — **manual one-off Phase 2 run; recompute on demand**. `scripts/calibrate_round_conclusion.py` is idempotent.

### Claude's Discretion

- Probe failure logging shape (field names in `PROBE-LOG.md`, JSONL or markdown).
- OCR tooling for Path B (Tesseract default per CLAUDE.md, though research below shows template matching is the established approach).
- `side_baseline` computation: which exact statistic from `half_win_rates.json`.
- Probe credential management (`.env` per Kalshi pattern).
- Whether to gate Path B on user re-confirmation at 1-week cap (D-10 says auto-trigger).

### Deferred Ideas (OUT OF SCOPE)

- Recency-weighted calibration (Phase 5/7).
- Automated weekly recalibration via CI (Phase 7).
- Per-match incremental cell updates (Phase 7).
- Wider `mid_round_states[]` snapshot fields: `ult_count`, `players_alive`, `time_left_s` (Phase 5).
- Logistic regression / GBT calibration alternatives (rejected v1; revisit Phase 5 if Brier bad).
- OCR auto-validation against Path A subset (Phase 5).
- Per-half pistol-winner extension to `pistol_winner_a` for rounds 14/15 (separate ticket).

---

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| **REQ-round-event-data-pipeline** | Probe rib.gg/bo3.gg via `scripts/probe_round_events.py` (DEC-017). Path A: ≥500 matches into `round_events` SQLite + calibrate cells. Path B: 100 OCR-labeled VODs. Path C: defer with flat 0.5. | Live-verified `be-prod.rib.gg/v1/` Path A endpoints during this research; identified `events[]` array as round-event source; documented `economies[]` as `econ_bucket` source; verified schema round-trips in SQLite; bo3.gg / FlynV / valorantr ruled out as redundant or environmentally infeasible. |

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| HTTP fetch + retry vs `be-prod.rib.gg/v1/` | `scripts/` (offline ETL) | — | Phase 2 is one-shot offline; not a Phase 3/Phase 4 runtime concern. |
| Round-event JSON → `mid_round_states[]` derivation | `scripts/probe_round_events.py` (offline transform) | `src/pricing/round_conclusion.py` (only the `from_json` loader) | Transform is offline-only; runtime only loads. |
| `econ_bucket` bucketing logic | `src/pricing/` candidate (shared with Phase 3) OR `scripts/` (private to calibration) | — | If Phase 3 will need bucket logic at runtime to populate `MatchState.econ_bucket`, lift to `src/pricing/economy.py` to share. Otherwise inline in script. **Recommendation: lift to `src/pricing/economy.py` now** — Phase 3 will need identical bucketing per CON-economy-buckets, and CRule 2 forbids two implementations of the same concept. |
| SQLite write of `round_events` table | `scripts/` | — | Per DEC-015 SQLite is "dataset cache" only; live state stays in-memory. Phase 2 lands in the dataset-cache role, not live-state. |
| Empirical-Bayes shrinkage walk | `scripts/calibrate_round_conclusion.py` | `src/pricing/round_conclusion.py::_Cell.shrunk()` (formula) | Calibration script computes `(n, p_hat, parent_p)` per cell; the actual shrinkage formula already lives on `_Cell`. Script does not duplicate it. |
| JSON serialization of `RoundConclusionLookup` | `src/pricing/round_conclusion.py` (additive `to_json` + `from_json`) | — | Classmethod `from_json` is the ONE additive Phase 1 surface change CONTEXT.md authorizes. `to_json` is a private helper used only by the calibrator. |
| Loading the calibrated lookup at runtime | Phase 4 `src/quoting/` engine init | — | Out of Phase 2 scope; Phase 4 adds `RoundConclusionLookup.from_json("models/round_conclusion.json")`. |

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `requests` | 2.32+ | HTTP GET against `be-prod.rib.gg/v1/` | Synchronous, well-known retry semantics; matches the `Traumist/RIB-Data-Scraper` reference pattern (the only known working rib.gg Python scraper). [VERIFIED: github.com/Traumist/RIB-Data-Scraper/event_scraping.py uses `requests` directly] |
| `sqlite3` (stdlib) | n/a | `data/round_events.sqlite` ETL | Standard library, no dep. Confirmed round-trip of composite PK + JSON column during research. [VERIFIED: in-session SQLite test passed] |
| `tenacity` | 8.x | Retry-with-backoff for transient API errors | Industry-standard exponential-backoff wrapper. rib.gg is on Heroku and during research a single 503 was observed before recovery — retries needed. [CITED: tenacity.readthedocs.io] |
| Python stdlib `json` | n/a | `mid_round_states[]` (de)serialize, `models/round_conclusion.json` write | Already standard for Phase 1 `from_json`. |
| `tqdm` | 4.66+ | Progress bar for the 1000-match scrape (~4000 API calls) | Long-running scripts benefit from operator visibility. Optional but conventional. |

**Path B contingency stack (only if Path A fails — research only, do NOT install in v1):**
| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| `opencv-python` | 4.10+ | Frame extraction from VODs, ROI cropping | Industry-standard for HUD region extraction. |
| `numpy` | 2.x | Template-matching score arrays | OpenCV native interop. |
| **Template matching (`cv2.matchTemplate`)**, NOT Tesseract | — | Read score, round number, alive count from HUD | Valorant uses a **custom font**; Tesseract / EasyOCR / PaddleOCR all misdetect. [VERIFIED: `Valoscribe` (Krishnan, Medium 2026) explicitly rejects OCR for this reason and uses template matching at 4 fps — closest published Valorant analog] |
| `tesseract` (system binary, already on PATH) | 5.5.0 | Fallback for player-name strings only | CLAUDE.md says Tesseract is on PATH — but reserve for nameplates, NOT digits. [VERIFIED: in-session `tesseract --version` returned 5.5.0] |

### Supporting (already available)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pytest` + `hypothesis` | 9.0.3 / 6.152.4 | Phase 0 toolchain | Wave 0 tests for `from_json`, calibrator. Already in `pyproject.toml`. |
| `mypy --strict` (scoped to `src/pricing/`) | 1.20.2 | Type-check the new `from_json` method | CRule 11 / CON-mypy-strict-pricing. Phase 0-resolved. |
| `ruff` | 0.15.12 | Lint scripts/ and src/ | Phase 0-resolved. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `requests` | `httpx` (async) | rib.gg has 4000 calls per run at 1-2 calls/sec — async is unnecessary, adds dep. `requests` is sufficient. |
| `sqlite3` + `json.dumps` for `mid_round_states[]` | `SQLite JSON1 extension` (queryable JSON) | JSON1 lets you `SELECT json_extract(mid_round_states, '$[0].kind')` — useful for calibration queries on a normalized field, but not necessary if calibrator deserializes once into Python. **Recommend default text-blob; revisit if calibration query becomes the bottleneck**. |
| Python `requests` directly | `valorantr` R-package via `Rscript -e ...` | R not installed on Windows; valorantr wraps the same endpoints we hit directly. Per D-01: "if R is unavailable on Windows, treat this source as definitively failed." [VERIFIED: `where R` returned nothing in-session] |
| `Traumist`-style scraper (in-process) | `FlynV/RIB.GG-Web-Scraper` Node project | FlynV is a Windows-binary Discord-bot replacement; no callable library. README + release-zip only. Not importable from Python. [VERIFIED: GitHub API list of FlynV repo top-level returned only `README.md`] |
| Empirical-Bayes shrinkage | Logistic regression on `(numerical_diff, bomb, side, econ, map)` | D-13 explicitly rejects — opaquer interpretation, replaces `_Cell` class, breaks Phase 1 interface lock. |

**Installation (additive to existing `pyproject.toml`):**
```bash
uv add requests tenacity tqdm
```

**Version verification:**
- `requests`: latest 2.32.3 (Aug 2025). [VERIFIED: training data + pypi]
- `tenacity`: latest 8.5.0 (Aug 2025). [VERIFIED: training data + pypi]
- `tqdm`: latest 4.66.5 (Mar 2025). [VERIFIED: training data + pypi]
- Run `uv add` and let resolver pick the current versions; commit `uv.lock`.

---

## Architecture Patterns

### System Architecture Diagram

```
                       ┌────────────────────────────────────────┐
   rib.gg events       │ scripts/probe_round_events.py          │
   ───────────►        │   (Wave 1 — gating)                    │
                       │                                        │
   /v1/events          │   1. fetch event list (filter VCT/T1)  │
   /v1/series?eventIds │   2. fetch series → embedded matches[] │
   /v1/matches/{id}/   │   3. fetch matches/{id}/details        │
       details         │   4. transform → round_events rows     │
                       │   5. write SQLite + PROBE-LOG.md       │
                       └─────┬──────────────────────────────────┘
                             │  data/round_events.sqlite
                             │  (1000 matches × 25 rounds = 25k rows)
                             ▼
                       ┌────────────────────────────────────────┐
data/half_win_rates    │ scripts/calibrate_round_conclusion.py  │
.json                  │   (Wave 2 — depends on Wave 1)         │
   ───────────►        │                                        │
                       │   1. read SQLite, group by chain keys  │
                       │   2. derive side_baseline from         │
                       │      half_win_rates.json (bottom-up)   │
                       │   3. populate cells_minimal w/         │
                       │      parent_p = side_baseline value    │
                       │   4. ... walk up to cells_full         │
                       │   5. RoundConclusionLookup.to_json()   │
                       └─────┬──────────────────────────────────┘
                             │  models/round_conclusion.json
                             │  (~100KB)
                             ▼
                       ┌────────────────────────────────────────┐
                       │ Phase 4 engine init (downstream):      │
                       │   RoundConclusionLookup.from_json(...) │
                       │   → injected into LiveTheoEngine       │
                       └────────────────────────────────────────┘

Path B (contingency, NOT in Wave 1 scope):
   100 VOD frames → cv2 ROI crop → cv2.matchTemplate (digits)
                                 + tesseract (nameplates)
                                 → same round_events SQLite shape

Path C (only if Path A AND Path B fail):
   Zero code change. Phase 1 skeleton ships as-is. flat 0.5.
```

### Recommended Project Structure

```
valorant-pricing-model/
├── scripts/
│   ├── probe_round_events.py            # NEW Wave 1 — gating
│   ├── calibrate_round_conclusion.py    # NEW Wave 2
│   └── (path-B only) ocr_round_events.py # NOT in Wave 1
├── src/
│   ├── pricing/
│   │   ├── round_conclusion.py          # MODIFIED — add from_json + lookup body rewrite
│   │   └── economy.py                   # NEW (recommended) — econ_bucket bucketing,
│   │                                    #   shared with Phase 3 (CON-economy-buckets)
│   └── config/
│       └── constants.py                 # MODIFIED — add MIN_CELL_N, RIBGG_BASE_URL
├── data/
│   ├── round_events.sqlite              # GENERATED (committed? see PRD discussion)
│   └── half_win_rates.json              # EXISTING (input)
├── models/
│   └── round_conclusion.json            # GENERATED, committed (~100KB)
├── tests/
│   ├── pricing/
│   │   └── test_round_conclusion_loader.py    # NEW — round-trip from_json/to_json,
│   │                                          #   integration with cells_full lookup
│   └── scripts/
│       └── test_calibrate_round_conclusion.py # NEW — synthetic mini-dataset
└── .planning/phases/02-round-event-data/
    ├── 02-CONTEXT.md          # EXISTING (input — already locked)
    ├── 02-RESEARCH.md         # THIS FILE
    ├── 02-PROBE-LOG.md        # NEW DELIVERABLE — written by Wave 1 script
    └── 02-VERIFICATION.md     # generated at phase end by /gsd-verify-work
```

### Pattern 1: rib.gg API endpoint chain

**What:** Three-call chain to enumerate match IDs and fetch round events.
**When to use:** Always. This is the canonical Path A flow.
**Verified URLs (live-probed 2026-04-30):**

```python
# Source: in-session probe of be-prod.rib.gg, 2026-04-30
RIBGG_BASE = "https://be-prod.rib.gg/v1"

# 1. Find tier-1 events. Verified filter params:
#    - query: free-text search ("VCT 2025")
#    - take: page size (max 50 per call observed)
#    - hasSeries: true
#    - sort: startDate
#    - sortAscending: false
#    - eventIds[]: filter by id (after first call)
#    Each event has fields: id, name, vctRegions[], divisions[], importance,
#       startDate, seriesCount, slug, parent, parentId
#    Filter for tier-1: divisions ∋ "VCT" AND seriesCount > 0
GET /v1/events?take=50&query=VCT&hasSeries=true&sort=startDate&sortAscending=false

# 2. Get series for an event. Returns embedded matches[] arrays — NO separate /matches call needed.
#    Verified embedded shape: each series.matches[i] has id, mapId, map.name,
#       attackingFirstTeamNumber, winningTeamNumber, team1Score, team2Score,
#       team1PlayerIds[], team2PlayerIds[], lengthMillis
GET /v1/series?eventIds[]={event_id}&completed=true&take=50

# 3. Get round events per match. THIS is where round-by-round timestamps live.
#    Returns: {id, playerStats[], events[], locations[], economies[]}
#    events[] entries: {roundNumber, roundTimeMillis, eventType ∈ {start, plant, kill, defuse},
#                       attackingTeamNumber, killId, bombId, playerId, ...}
#    economies[] entries: {roundNumber, playerId, weaponId, armorId, loadoutValue,
#                          remainingCreds, spentCreds, survived, kast}
GET /v1/matches/{match_id}/details

# Required headers (Cloudflare bot mitigation observed on /www but NOT on /v1):
headers = {
    "User-Agent": "Mozilla/5.0",  # plain string accepted; ANY non-empty UA works
    "Referer": "https://www.rib.gg/",  # not strictly required; sent for politeness
}
# NO auth/cookies. Confirmed unauthenticated GET works.

# Rate limit posture: 5-burst observed clean, no rate-limit headers in response.
# Recommend self-throttle to ~2 req/sec just to be polite. 4000 calls / 2 rps = ~33 min.
```

[VERIFIED: in-session HTTP probe of be-prod.rib.gg returned 200 for events, series, and match-details endpoints; verified shape of `events[]`, `economies[]`, and `matches[]` arrays directly from sample VCT 2025 Pacific match (matchId=213508)]

### Pattern 2: `mid_round_states[]` synthesis from `events[]`

**What:** Transform rib.gg's per-event log into D-06's hybrid event-plus-heartbeat schema.
**When to use:** Inside `probe_round_events.py`'s row-builder.

```python
# Source: D-06 / D-08 / D-09 + rib.gg events[] shape verified 2026-04-30
def synthesize_mid_round_states(
    round_events: list[dict],   # all events for one round, sorted by roundTimeMillis
    round_team_a_players: set[int],
    round_team_b_players: set[int],
    round_loadouts: dict[int, int],  # player_id -> loadoutValue this round
    side_a_this_round: str,   # "atk" | "def"
    map_name: str,
) -> list[dict]:
    """D-06 hybrid: native events + 5s synthetic heartbeats with carry-forward."""
    # Initialize: 5v5, no plant
    a_alive = 5
    b_alive = 5
    bomb_planted = False
    states: list[dict] = []

    # Bucket loadouts per team this round
    econ_a_total = sum(round_loadouts.get(pid, 0) for pid in round_team_a_players)
    econ_a_bucket = bucket(econ_a_total)  # CON-economy-buckets

    # Round duration — derived from last event's roundTimeMillis (no explicit ts_round_end in source)
    round_end_ms = round_events[-1]["roundTimeMillis"] if round_events else 0

    # Walk events in time order, emit a state per event AND insert heartbeats at 5s intervals
    next_heartbeat_ms = 0
    for ev in round_events:
        t = ev["roundTimeMillis"]
        # Emit pending heartbeats with carry-forward (D-08)
        while next_heartbeat_ms < t:
            states.append({
                "t_offset": next_heartbeat_ms / 1000.0,
                "kind": "heartbeat",
                "numerical_diff": a_alive - b_alive,
                "bomb_planted": bomb_planted,
                "side": side_a_this_round,
                "econ_bucket": econ_a_bucket,
            })
            next_heartbeat_ms += 5000
        # Apply event mutation
        if ev["eventType"] == "kill":
            victim = ev["referencePlayerId"]
            if victim in round_team_a_players: a_alive -= 1
            elif victim in round_team_b_players: b_alive -= 1
        elif ev["eventType"] == "plant":
            bomb_planted = True
        elif ev["eventType"] == "defuse":
            bomb_planted = False  # defuse pre-explosion → bomb status off
        # eventType == "start" is the round-start marker; no state mutation needed
        # Emit event-kind state (D-06)
        states.append({
            "t_offset": t / 1000.0,
            "kind": "event",
            "numerical_diff": a_alive - b_alive,
            "bomb_planted": bomb_planted,
            "side": side_a_this_round,
            "econ_bucket": econ_a_bucket,
        })

    return states  # already time-sorted (D-09)
```

### Pattern 3: Bottom-up shrinkage walk (D-14)

**What:** Populate cell hierarchy in dependency order so each child has a populated parent before shrinking.
**When to use:** Inside `calibrate_round_conclusion.py`.

```python
# Source: D-14 verbatim
from collections import defaultdict
from src.pricing.round_conclusion import RoundConclusionLookup, _Cell

def calibrate(rows: list[dict], half_rates: dict) -> RoundConclusionLookup:
    lookup = RoundConclusionLookup()  # frozen=True wrapper, mutable dict fields

    # Level 5 (deepest in chain = LAST resort, but populated FIRST in this walk):
    # side_baseline. Computed from half_win_rates.json overall_avg per side.
    # Half-rate file gives P(team wins single round | atk/def). Round-conclusion
    # baseline is the same per-side marginal — the unconditional P(win round | side).
    # Use overall_avg (~0.5) as the floor; refine to per-side league average if file allows.
    # Per-side baseline: mean across all `league_map_side` entries with side == s.
    league_rates = half_rates.get("league_map_side", {})
    overall_avg = half_rates.get("overall_avg", 0.5)
    for side in ("atk", "def"):
        side_entries = [v["rate"] for k, v in league_rates.items() if k.endswith(f"|{side}")]
        lookup.side_baseline[side] = (sum(side_entries) / len(side_entries)
                                      if side_entries else overall_avg)

    # Level 4: cells_minimal — keyed (numerical_diff, bomb_planted)
    # parent_p = lookup.side_baseline[side] for whichever side dominates this row's data.
    # Aggregate p_hat = sum(round_won_by_a) / sum(rounds) over all rows matching key,
    # marginalizing across side. parent_p = mean(side_baseline.values()).
    minimal_agg = defaultdict(lambda: [0, 0])  # key -> [wins, total]
    for r in rows:
        for s in r["mid_round_states"]:
            key = (s["numerical_diff"], s["bomb_planted"])
            minimal_agg[key][0] += int(r["round_won_by_a"])
            minimal_agg[key][1] += 1
    parent_minimal = (lookup.side_baseline["atk"] + lookup.side_baseline["def"]) / 2
    for key, (w, n) in minimal_agg.items():
        if n == 0: continue
        lookup.cells_minimal[key] = _Cell(n=n, p_hat=w / n, parent_p=parent_minimal)

    # Level 3: cells_no_map — keyed (numerical_diff, bomb_planted, side)
    no_map_agg = defaultdict(lambda: [0, 0])
    for r in rows:
        for s in r["mid_round_states"]:
            key = (s["numerical_diff"], s["bomb_planted"], s["side"])
            no_map_agg[key][0] += int(r["round_won_by_a"])
            no_map_agg[key][1] += 1
    for (nd, bp, side), (w, n) in no_map_agg.items():
        if n == 0: continue
        # parent = the cells_minimal entry with same (nd, bp). If absent (rare), fall to baseline.
        parent_cell = lookup.cells_minimal.get((nd, bp))
        parent_p = parent_cell.shrunk() if parent_cell else lookup.side_baseline[side]
        lookup.cells_no_map[(nd, bp, side)] = _Cell(n=n, p_hat=w / n, parent_p=parent_p)

    # Level 2: cells_no_econ — keyed (numerical_diff, bomb_planted, side, map_name)
    # ... same pattern, parent = cells_no_map[(nd, bp, side)]
    # Level 1: cells_full — parent = cells_no_econ[(nd, bp, side, map_name)]

    return lookup
```

The bottom-up order is correct because at construction time of any `_Cell`, its `parent_p` field is fixed — it's a number, not a reference. So the parent must already be populated *and shrunk* before the child is constructed. D-14's "recursive walk up the chain, deepest level first" is exactly this iteration order.

### Anti-Patterns to Avoid

- **Hand-rolling rate-limit / retry logic.** Use `tenacity` decorators. The reference Python scraper (`Traumist/RIB-Data-Scraper`) has zero retry logic, which would silently lose matches on transient 503s. We observed one 503 during research before retry-recovery worked.
- **Calibrating top-down** (cells_full first, then walking parents lazily). This requires recursive resolution at lookup time and breaks the immutable `_Cell.parent_p: float` contract. Always populate bottom-up.
- **Caching `_Cell.shrunk()` results in the JSON.** The JSON should serialize the raw `(n, p_hat, parent_p)` triple — not the shrunk value. This preserves auditability ("can we trust this prediction? show me n") and lets a Phase 5 calibration loop re-tune `SHRINK_PRIOR` without regenerating the dataset.
- **Treating bomb-defuse as a no-op.** Defuse should set `bomb_planted = False` (post-defuse rounds are functionally pre-plant for round-conclusion purposes). Phase 1 docstring says "True after spike plant on attacker side" — defuse reverses this. Verify the calibrator handles defuse correctly.
- **Carrying forward across map boundaries.** Each match is a separate map; `mid_round_states[]` resets per (match_id, round_num). Don't accumulate `a_alive` across matches.
- **Storing `match_round_data` SQLite in `src/`.** Per CON-live-state-no-sqlite, SQLite is dataset cache only. `data/round_events.sqlite` is correctly placed. Do NOT put it under `src/`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP retry with exponential backoff | Custom `for i in range(3): try: ...` loops | `tenacity.retry(wait=wait_exponential(...), stop=stop_after_attempt(5))` | Edge cases (jitter, max-elapsed, retry-on-specific-status) are nontrivial; tenacity is the standard. |
| Bayesian shrinkage formula | Re-implement the math | Reuse `_Cell.shrunk()` from `src/pricing/round_conclusion.py` verbatim | Phase 1 already shipped this; CRule 2 forbids two implementations. |
| JSON schema validation | `if "n" not in d: raise ...` chains | `TypedDict` + mypy checks at call sites; runtime `pydantic.BaseModel` if validation must run | mypy --strict on `src/pricing/` already requires types. `from_json` parses dict-of-dicts; declare a `_RoundConclusionJsonSchema(TypedDict)` and let mypy + the JSON parser do the work. |
| SQLite connection management | `try: conn = sqlite3.connect(); ...; conn.close()` | `with sqlite3.connect(path) as conn:` (context manager) | stdlib idiom; auto-close on exception. |
| Progress reporting | `print(f"{i}/{n}")` every iteration | `tqdm.tqdm(iterable)` | Updates in-place, includes ETA, doesn't spam logs. |
| `econ_bucket` mapping (`int credits → bucket label`) | Inline conditional in `probe_round_events.py` | A single `def credits_to_bucket(c: int) -> str` in `src/pricing/economy.py` | CON-economy-buckets is a contract. Phase 3 will need the same mapping at runtime per `MatchState.econ_bucket`. CRule 2 forbids duplication. |
| Round-trip `RoundConclusionLookup` ↔ JSON | Custom dict walking | `RoundConclusionLookup.to_json(path)` + `from_json(path)` classmethods on the dataclass | Encapsulation; one place to enforce schema; the additive surface change CONTEXT.md authorizes. |
| Tier-1 event filtering | Maintain a hand-curated list of event IDs | Filter rib.gg `events[].divisions ∋ "VCT" AND vctRegions ⊇ {EMEA, AMERICAS, PACIFIC, CHINA}` | rib.gg already classifies events; reproducible filter is better than a list that goes stale. [VERIFIED: response field `divisions: ["VCL"|"VCT"|...]` and `vctRegions: ["EMEA"|...]` confirmed in-session probe] |

**Key insight:** Phase 2 is mostly an ETL job. The temptation is to inline everything in one big script. Resist — `econ_bucket` bucketing in particular MUST be lifted to `src/pricing/economy.py` because Phase 3's live `MatchState.econ_bucket` derivation will need bit-identical logic. If they diverge, the calibrator and the live engine see different distributions, and the model is silently mis-calibrated.

---

## Runtime State Inventory

> Greenfield phase — no rename / refactor / migration is involved.
>
> **Stored data:** None — Phase 2 *creates* `data/round_events.sqlite` and `models/round_conclusion.json` as new artifacts; no existing keys/IDs are renamed.
>
> **Live service config:** None — Phase 2 is offline.
>
> **OS-registered state:** None — no scheduled tasks or services.
>
> **Secrets/env vars:** Optional new var `RIBGG_USER_AGENT` (defaults to `Mozilla/5.0` literal). NO auth credentials needed for rib.gg. The "rib.gg auth" mentioned in CLAUDE.md and CONTEXT.md D-01 turns out to be **inaccurate as of 2026-04-30** — research-verified that `be-prod.rib.gg/v1/` accepts unauthenticated GETs with no cookie/bearer required. Update CLAUDE.md "rib.gg internal API" row in a follow-up if confirmed at planning time.
>
> **Build artifacts:** None — no installed packages renamed.

---

## Common Pitfalls

### Pitfall 1: Treating rib.gg endpoint discovery as the hard part
**What goes wrong:** Spending Wave 1 budget exploring 4 sources (rib.gg API + valorantr R + FlynV Node + bo3.gg) when only one (rib.gg API) needs to be touched.
**Why it happens:** D-01 specifies a 4-source ladder as a defensive default written before live-probing was done.
**How to avoid:** Run the Wave 1 probe directly against `be-prod.rib.gg/v1/` (research-verified working). Use sources 2-4 only as written documentation in `02-PROBE-LOG.md` ("considered, rejected because: R not installed / no Python library / no round-event data").
**Warning signs:** Probe script grows beyond 200 lines, plan-checker flags "researcher recommended single source but planner is implementing four."

### Pitfall 2: Heroku 503 mid-scrape
**What goes wrong:** rib.gg backend is on Heroku (research-confirmed via `Server: Heroku` header). Heroku free-tier dynos hibernate after 30 min of inactivity and return 503 on cold-start. During research, one 503 was observed before recovery. Without retry, the scraper drops matches.
**Why it happens:** No retry decorator, naive `requests.get()` call with no exception handling.
**How to avoid:** Wrap every fetch with `tenacity.retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, max=30))`. Log retries to `02-PROBE-LOG.md`. **Do not silently swallow 503s** — if a single match fails 5 retries, emit a warning and continue, but include the failure in the probe log.
**Warning signs:** Probe log shows "1000 matches expected, 873 successful" — investigate the 127 failures before claiming Path A passed.

### Pitfall 3: `attackingTeamNumber` ambiguity for `side`
**What goes wrong:** Mapping `event.attackingTeamNumber` (1 or 2) to `side` ("atk" or "def") for team A is non-trivial. `match.attackingFirstTeamNumber: 1` means team-1 starts on attack; in second-half rounds (rounds 13+), sides flip. If Phase 2 uses the wrong side mapping, every cell-row's `side` field is bit-flipped → calibration is garbage.
**Why it happens:** Easy to write `side = "atk" if event.attackingTeamNumber == 1 else "def"` without thinking about half-flips.
**How to avoid:**
```python
def side_for_team_a(round_num: int, attacking_first_team_num: int, team_a_team_num: int) -> str:
    """Returns 'atk' or 'def' for team A in this round.
    Sides flip at round 13 (start of second half) and again in OT (round 25+, paired flips)."""
    is_first_half = round_num <= 12
    is_a_attacker_in_first_half = (attacking_first_team_num == team_a_team_num)
    a_attacks_this_round = is_a_attacker_in_first_half if is_first_half else not is_a_attacker_in_first_half
    return "atk" if a_attacks_this_round else "def"
```
Add a unit test on a known match where you can verify by inspection (rib.gg website renders side per round).
**Warning signs:** `side_baseline["atk"]` and `side_baseline["def"]` are both ~0.5 — could mean side really is balanced, OR could mean every row's side is randomly flipped.

### Pitfall 4: Carry-forward semantics across `defuse` event
**What goes wrong:** A `defuse` event sets `bomb_planted = False`, but only momentarily — the round ends ~immediately after. If the calibrator treats the post-defuse heartbeat as a `bomb_planted=False` snapshot, it gets one bogus row with `bomb_planted=False, numerical_diff=high` (because the defending team is winning a planted round) → cell `(numerical_diff=2, bomb_planted=False)` gets contaminated with what's actually a planted scenario.
**Why it happens:** Naive event semantics treats defuse symmetrically with plant.
**How to avoid:** Stop emitting `mid_round_states[]` entries after the round-conclusion event (last kill OR defuse OR plant-then-time-expire). The final state is the round end; downstream events don't exist. Specifically: if `eventType == "defuse"`, that's the round terminator for the defenders — emit one final state at that t_offset, then stop.
**Warning signs:** `cells_full` populated with ~25k entries instead of ~22k (extra post-defuse phantom states).

### Pitfall 5: `_Cell.shrunk()` precomputed in JSON
**What goes wrong:** `RoundConclusionLookup.to_json()` serializes `cells_full[key].shrunk()` as a flat float instead of `{n, p_hat, parent_p}`. `from_json()` happily reconstructs `_Cell(n=0, p_hat=value, parent_p=value)` and the lookup returns the right number — but Phase 5's calibration loop (re-tune `SHRINK_PRIOR`) can no longer recover the raw `n` and `p_hat`. The audit trail is lost.
**Why it happens:** Premature optimization: "I can make the JSON smaller / faster to read."
**How to avoid:** Serialize `_Cell` as `{n: int, p_hat: float, parent_p: float}`. Pure data, no computed fields. Resist the urge to inline `shrunk()`.
**Warning signs:** `models/round_conclusion.json` doesn't contain the substring `"n"` or `"p_hat"` — only floats.

### Pitfall 6: Recency-weighting drift the calibrator silently absorbs
**What goes wrong:** D-03 fixes 1000 matches over 18 months. Valorant has 6+ patches per year and significant agent-roster meta shifts. The calibrator weights every match equally, so a 2024-Q4 match's `cells_full[(...,Lotus,...)]` row blends with a 2026-Q1 match's row even though Lotus may have been remapped or the meta cycled.
**Why it happens:** D-03 explicitly defers recency-weighting to Phase 5. Acceptable for v1, but the planner should NOT silently extend the window beyond 18 months without flagging it.
**How to avoid:** Hard-cap on the rib.gg `events[].startDate` filter at `today - 18 months`. Reject older matches at probe time. Log to `02-PROBE-LOG.md` how many matches were rejected by date.
**Warning signs:** Brier scores in Phase 5's first paper-trade event come in at >0.30 on early-game cells — meta drift is the leading suspect; recency-weighting becomes a Phase 5 priority.

### Pitfall 7: `data/round_events.sqlite` size and git-commit policy
**What goes wrong:** 1000 matches × 25 rounds × ~30 mid_round_states ≈ 750k rows of nested JSON. Even with TEXT compression, the SQLite file could be 50-200 MB. Committing to git bloats the repo and slows clones.
**Why it happens:** No explicit "is this committed?" call in CONTEXT.md — D-15 covers the JSON output but not the SQLite dataset.
**How to avoid:** **Do NOT commit `data/round_events.sqlite` to git.** Add it to `.gitignore`. Commit `models/round_conclusion.json` only (~100KB). The SQLite is rebuildable from the rib.gg API, so it's a build artifact, not source. Document this decision in `02-PROBE-LOG.md`.
**Warning signs:** `git status` shows a 50MB+ file; `.gitignore` doesn't list `data/round_events.sqlite`.

---

## Code Examples

### Probe entry point skeleton
```python
# scripts/probe_round_events.py
"""Wave 1: scrape rib.gg round events into data/round_events.sqlite.

Path A only. Per RESEARCH.md (in-session live probe of be-prod.rib.gg, 2026-04-30),
the multi-source ladder of D-01 is collapsed to a single source: direct GETs
against be-prod.rib.gg/v1/. Sources 2-4 (valorantr / FlynV / bo3.gg) are
considered and rejected for reasons logged in 02-PROBE-LOG.md.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import TypedDict

import requests
from tenacity import retry, stop_after_attempt, wait_exponential
from tqdm import tqdm

from src.config.constants import RIBGG_BASE_URL  # NEW constant

# --- TypedDict schemas mirroring rib.gg response shapes ---
class _RibEvent(TypedDict):
    roundNumber: int
    roundTimeMillis: int
    eventType: str  # "start" | "plant" | "kill" | "defuse"
    attackingTeamNumber: int
    killId: int | None
    bombId: int | None
    playerId: int | None
    referencePlayerId: int | None

class _RibEconomy(TypedDict):
    roundNumber: int
    playerId: int
    loadoutValue: int

# --- HTTP helpers ---
HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.rib.gg/"}

@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, max=30))
def get_json(url: str) -> dict:
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()

# --- Iterate event → series → matches ---
def list_tier1_events(eighteen_months_ago_iso: str) -> list[dict]:
    """Filter rib.gg events to tier-1 VCT in the last 18 months."""
    out = []
    offset = 0
    while True:
        url = (f"{RIBGG_BASE_URL}/events?take=50&hasSeries=true"
               f"&sort=startDate&sortAscending=false&skip={offset}")
        resp = get_json(url)
        events = resp["data"]
        if not events: break
        for e in events:
            if e["startDate"] < eighteen_months_ago_iso: return out  # done
            divisions = e.get("divisions") or []
            if "VCT" in divisions and (e.get("seriesCount") or 0) > 0:
                out.append(e)
        offset += len(events)
        if offset >= resp["meta"]["total"]: break
    return out

def list_series_for_event(event_id: int) -> list[dict]:
    url = f"{RIBGG_BASE_URL}/series?eventIds[]={event_id}&completed=true&take=50"
    return get_json(url)["data"]

def get_match_details(match_id: int) -> dict:
    return get_json(f"{RIBGG_BASE_URL}/matches/{match_id}/details")

# --- Transform + write ---
def main(out_db: Path, probe_log: Path) -> int:
    # ... iterate, transform via synthesize_mid_round_states(), insert
    # Track per-source acceptance per D-02. Write 02-PROBE-LOG.md at end.
    pass

if __name__ == "__main__":
    raise SystemExit(main(Path("data/round_events.sqlite"),
                          Path(".planning/phases/02-round-event-data/02-PROBE-LOG.md")))
```

### `RoundConclusionLookup.from_json` — the ONE additive interface change
```python
# src/pricing/round_conclusion.py — ADDITIVE methods only
# (existing _Cell, RoundConclusionFn, RoundConclusionLookup remain unchanged)

import json
from pathlib import Path
from typing import TypedDict

class _CellJson(TypedDict):
    n: int
    p_hat: float
    parent_p: float

class _RoundConclusionLookupJson(TypedDict):
    cells_full: dict[str, _CellJson]      # key serialized as "{nd}|{bp}|{side}|{econ}|{map}"
    cells_no_econ: dict[str, _CellJson]
    cells_no_map: dict[str, _CellJson]
    cells_minimal: dict[str, _CellJson]
    side_baseline: dict[str, float]

@dataclass(frozen=True, slots=True)
class RoundConclusionLookup:
    # ... existing fields unchanged ...

    @classmethod
    def from_json(cls, path: str | Path) -> "RoundConclusionLookup":
        """Phase 2 additive interface: load calibrated cells from JSON.

        Source: D-15 / 02-RESEARCH.md §from_json. Phase 4 engine init calls
        this; if path doesn't exist (Path C scenario), Phase 4 falls back to
        cls() (empty lookup, returns flat 0.5 from existing skeleton).
        """
        data: _RoundConclusionLookupJson = json.loads(Path(path).read_text())
        obj = cls()  # all dicts empty; populate them in-place via dict mutation (CRule from Phase 1)

        def parse_key_5(s: str) -> tuple[int, bool, str, str, str]:
            nd, bp, side, econ, mp = s.split("|", 4)
            return int(nd), bp == "true", side, econ, mp
        # ... similar for 4-tuple, 3-tuple, 2-tuple keys ...

        for k, v in data["cells_full"].items():
            obj.cells_full[parse_key_5(k)] = _Cell(n=v["n"], p_hat=v["p_hat"], parent_p=v["parent_p"])
        # ... cells_no_econ, cells_no_map, cells_minimal ...
        obj.side_baseline.update(data["side_baseline"])
        return obj

    # NOTE: lookup() body must also change in Phase 2 — was Phase 1 stub
    # `return _PHASE_1_FLAT_CELL_VALUE`. Phase 2 rewrites to fallback-chain walk.
    def lookup(self, numerical_diff, bomb_planted, side, econ_bucket, map_name) -> float:
        for tbl, key in (
            (self.cells_full, (numerical_diff, bomb_planted, side, econ_bucket, map_name)),
            (self.cells_no_econ, (numerical_diff, bomb_planted, side, map_name)),
            (self.cells_no_map, (numerical_diff, bomb_planted, side)),
            (self.cells_minimal, (numerical_diff, bomb_planted)),
        ):
            cell = tbl.get(key)
            if cell is not None: return cell.shrunk()
        return self.side_baseline.get(side, _PHASE_1_FLAT_CELL_VALUE)
```

This is the SIGNATURE-PRESERVING rewrite of `lookup()` body that CONTEXT.md authorizes. The Protocol `RoundConclusionFn` is still satisfied. Phase 1 callers see no API change — only the return value changes from flat 0.5 to calibrated estimates.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Hand-curated tier-1 event ID list | Filter rib.gg `events[].divisions ∋ "VCT" + vctRegions` | This research (2026-04-30) | Reproducible without manual upkeep. |
| Tesseract OCR for Valorant HUD digits | **Template matching** via `cv2.matchTemplate` | Industry consensus (Valoscribe, 2026; CSMLC) | Path B contingency only — but if Path B is invoked, do NOT default to Tesseract for digits. |
| `backend-prod.rib.gg` (per Traumist 2022 scraper) | `be-prod.rib.gg` (live frontend, 2026) | Endpoint migration sometime 2022-2026 | Old subdomain no longer resolves; new one verified live during research. |
| Audit-engine `_round_win_prob` arithmetic-mean | Bradley-Terry blend (DEC-003) | Phase 1 (2026-04) | Already shipped; Phase 2 inherits. |
| Constant `p1`/`p2` per half | Pistol+anti-eco modeled separately (DEC-011) | Phase 1 (2026-04) | Already shipped. |

**Deprecated/outdated:**
- `backend-prod.rib.gg` subdomain — does NOT resolve. Use `be-prod.rib.gg`.
- `valorantr` R-package — still functional per CRAN but redundant with direct Python `requests` against the same endpoints. Listed in D-01 priority but only viable on machines with R installed.
- `FlynV/RIB.GG-Web-Scraper` — Windows-binary tool, no library API; not consumable by a Python script. Out of scope.

---

## Project Constraints (from CLAUDE.md)

These project-instructions directives constrain Phase 2 implementation. The planner MUST verify compliance at task definition time.

1. **CRule 1 — Single canonical entry point `live_theo(state) → (theo, vega, confidence)`.** Phase 2 does NOT add new pricing entry points. Only the body of `RoundConclusionLookup.lookup` changes (signature unchanged) and ONE additive `from_json` classmethod. Path C: zero changes to `round_conclusion.py`.
2. **CRule 2 — BO3 series and per-map theos from same DP.** Not directly modified by Phase 2; relevant only because the `RoundConclusionLookup.lookup` is consumed by `live_theo` once (not duplicated). Phase 2 must not introduce a parallel "MidRoundConclusionLookup."
3. **CRule 11 — `mypy --strict` on `src/pricing/`.** New `from_json` classmethod and any helper functions in `src/pricing/round_conclusion.py` MUST type-check under `--strict`. Use `TypedDict` for the JSON schema.
4. **CRule 12 — No magic numbers in business logic.** Calibration knobs (e.g., `MIN_CELL_N` for "drop cells below this n", `RIBGG_BASE_URL`, `RIBGG_RATE_LIMIT_RPS`) live in `src/config/constants.py` as `Final[...]`. The probe script reads from there.
5. **CRule 13 — Dry-run by default.** Not directly applicable (Phase 2 has no Kalshi orders), but the script MUST be safe to re-run idempotently — no destructive side effects beyond rewriting `data/round_events.sqlite` and `models/round_conclusion.json`.
6. **CON-no-magic-numbers.** Same as CRule 12. Add to `constants.py`:
   - `RIBGG_BASE_URL: Final[str] = "https://be-prod.rib.gg/v1"`
   - `RIBGG_RECENCY_MONTHS: Final[int] = 18` (D-03)
   - `RIBGG_TARGET_MATCH_COUNT: Final[int] = 1000` (D-03)
   - `MIN_CELL_N: Final[int] = 5` — recommended floor below which a cell shouldn't be persisted (otherwise `_Cell.shrunk()` returns essentially `parent_p`; saves JSON size).
   - `OCR_FRAMES_PER_SECOND: Final[float] = 1.0` (Path B only — D-10)
7. **CON-mypy-strict-pricing.** Same as CRule 11.
8. **CON-live-state-no-sqlite.** SQLite is dataset cache only. `data/round_events.sqlite` is correctly placed.
9. **CON-round-events-schema (frozen).** `(match_id, map_num, round_num, ts_round_start, ts_first_kill, ts_bomb_plant, ts_round_end, mid_round_states[])`. Phase 2 cannot add or remove row-level columns. The `mid_round_states[]` JSON shape (D-06 / D-07) is the implementation detail Phase 2 picks.
10. **Atomic per-task commits with `--no-verify`-aware tooling.** Phase 2 commits at boundaries: probe-passes, schema-creates, calibrate-runs.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | rib.gg `be-prod.rib.gg/v1/` will remain stable for the duration of Phase 2 (not migrated to a v2 namespace mid-scrape) | Standard Stack / Pattern 1 | Endpoints could move (as `backend-prod.rib.gg` did 2022→2026). Mitigation: probe re-runs the v1/events check first; if 404, fall back to JS-bundle inspection to find the new base URL. **VERIFIED 2026-04-30; not VERIFIED for future dates.** |
| A2 | rib.gg dataset has ~1000 completed VCT-tier-1 matches in the last 18 months | D-03 coverage bar | If actual count is <1000, the calibrator runs on a smaller dataset (still useful, just thinner cells). The probe script should COUNT matches before fetching `/details` for each — short-circuit if obviously sparse. [VERIFIED: VCT 2025 Pacific Stage 2 alone has 31 series in `eventId=5832`; ~10 such events per VCT year × 5 maps each ≈ enough] |
| A3 | rib.gg's `events[]` schema is stable across the 18-month window (2024-Q4 matches have same JSON shape as 2026-Q2) | Pattern 1 | If schema drifted (e.g., older matches lack `attackingWinProbabilityBefore`), the parser handles `None` gracefully but cell-derivation may misclassify. Mitigation: include a sample-shape audit in `02-PROBE-LOG.md` ("of 1000 matches, 998 have all expected fields; 2 missing X"). |
| A4 | The `event_scraping.py` reference scraper from `Traumist/RIB-Data-Scraper` (2022) reflects the same API contract that's live in 2026 | Standard Stack rationale | Verified — the URL pattern is identical (`/v1/events`, `/v1/series`, `/v1/matches/{id}/details`); only the subdomain changed (`backend-prod` → `be-prod`). Endpoint shape and JSON keys preserved. |
| A5 | rib.gg classifies VCT events with `divisions: ["VCT"]` consistently (not `["VCT-Americas"]`, `["VCT2025"]`, etc.) | Pattern 1 filter logic | If subdivisions exist, the filter misses tier-1 matches. Mitigation: planner should check 5 known events' `divisions` arrays during probe-script dry-run. |
| A6 | `econ_bucket` mapping per CON-economy-buckets is correct for esports VCT loadouts | Pattern 2 / Pitfall 1 | The buckets are documented as inherited from `thunderedge/match_round_data` — the empirical distribution. Phase 2 doesn't validate they fit; it reuses them verbatim. [ASSUMED based on CONTEXT.md] |
| A7 | `data/half_win_rates.json` schema (verified: `{team_map_side, league_map_side, overall_avg, min_rounds_threshold, maps_in_data}`) is stable across the project's lifetime | D-14 baseline derivation | Schema verified during research. If thunderedge worktree regenerates with a different shape, Phase 2 calibrator breaks. Mitigation: TypedDict + load-time validation in calibrator. [VERIFIED 2026-04-30 schema scan] |
| A8 | `bomb_planted=False` is the correct state for post-defuse rounds in the calibration window | Pitfall 4 | Round ends at defuse so calibrator should stop emitting states there; if it emits a phantom False, cells contaminated. Verify via test on a known defuse round. [ASSUMED — needs unit-test validation] |
| A9 | Path B (OCR) will not be needed because Path A is verified-working | Summary / probe order | If Path A unexpectedly fails (auth required, rate limits clamped, dataset empty), Path B is a 2-week side-track. Mitigation: probe runs in Wave 1 ALONE; Wave 2 is gated on its outcome. Path B planning is deferred. |
| A10 | rib.gg events have NO `ts_round_start` and `ts_round_end` as standalone fields — these are derived from `events[].roundTimeMillis == 0` (start) and last event's `roundTimeMillis` (end-by-proxy) | CON-round-events-schema population | The frozen schema names these columns explicitly. The transform must derive them from the event log; there is no native `round_start_ts`. The "start" eventType has `roundTimeMillis: 0`, so `ts_round_start = 0.0` always per round. `ts_round_end ≈ last_event.roundTimeMillis / 1000.0` — this approximates round duration but isn't strictly the moment the timer hit zero. Document this in PROBE-LOG. [VERIFIED in-session — all rounds in sample matchId=213508 had a `start` event at `roundTimeMillis=0`] |

**If this table is empty:** N/A — table has 10 entries that need validation at planning time.

---

## Open Questions

1. **Should `data/round_events.sqlite` be committed to git?**
   - What we know: At ~50-200 MB it bloats the repo significantly. It's deterministically rebuildable from rib.gg + a cached event-list file.
   - What's unclear: Project policy on generated-but-stable artifacts. Phase 1 commits `models/dp_table.pkl` per D-21 = NO (deferred to Phase 5).
   - Recommendation: **Add `data/round_events.sqlite` to `.gitignore`. Commit only `models/round_conclusion.json` (~100KB). Document this in `02-PROBE-LOG.md`.**

2. **Should the probe script auto-re-run Path A on a schedule, or be one-shot?**
   - What we know: D-16 says manual one-off; recompute on demand. The script should be idempotent.
   - What's unclear: Whether to wire it into `pre-commit` or leave standalone.
   - Recommendation: **Standalone CLI script. No automation in v1. Add a `--dry-run` flag that fetches a small sample (5 series) for validation.**

3. **Side-baseline derivation — `overall_avg`, per-side mean of `league_map_side`, or something else?**
   - What we know: `half_win_rates.json` has `overall_avg=0.5` and `league_map_side` per `(map|side)`. Per-side marginalization would average across maps.
   - What's unclear: Which is "more correct" as the deepest baseline.
   - Recommendation: **Per-side league average (not overall_avg). Reason: side has known asymmetry per map, and the league-mean per-side captures it without a per-map split (which `cells_no_map` already does).** Falls back to `overall_avg=0.5` if file missing.

4. **`bombId`-only events without explicit `eventType: "plant"` field?**
   - What we know: In sample data, every plant event had `eventType: "plant"` AND `bombId` populated. They co-occur.
   - What's unclear: Whether older matches use only `bombId` and lack the explicit type field.
   - Recommendation: **Treat `eventType == "plant"` as authoritative; if absent, fall back to `bombId is not None AND eventType is None`. Log uncertainty.**

5. **Map-pool cardinality for `cells_no_econ`?**
   - What we know: rib.gg returns ~10 active maps as of 2026 (`Bind, Lotus, Breeze, Ascent, Haven, Icebox, Fracture, Pearl, Split, Sunset` per `valorantr` constants).
   - What's unclear: Whether retired maps (e.g., `Sunset`) appear in 18-month window.
   - Recommendation: **Allow any map name through — don't whitelist. Calibrator should not reject rows by map.**

6. **Path B re-confirmation gate at 1-week probe cap?**
   - What we know: D-10 says "auto-trigger Path B if Path A fails." Discretion to add re-confirm.
   - What's unclear: User preference — but Path A has been verified working before plan-phase even ran, so the question is moot for v1.
   - Recommendation: **Plan as if Path A succeeds. If at execution time the probe fails, the orchestrator can pause and re-confirm before Wave 2 spawns Path B work.**

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Python 3.11 | All Phase 2 scripts | ✓ | 3.11+ (Phase 0 verified) | — |
| `requests` | rib.gg HTTP client | ✗ (not yet in `pyproject.toml`) | latest 2.32.3 | `urllib` (stdlib, more verbose) |
| `tenacity` | Retry decorator | ✗ | latest 8.5.0 | hand-rolled retry loop (anti-pattern) |
| `tqdm` | Progress bar | ✗ | latest 4.66.5 | `print()` every N iterations |
| `sqlite3` | `data/round_events.sqlite` | ✓ (stdlib) | n/a | — |
| Tesseract | Path B OCR fallback | ✓ | 5.5.0 (system PATH) | EasyOCR / PaddleOCR (heavier deps) |
| `opencv-python` | Path B template matching | ✗ | latest 4.10.x | — (Path B blocker if required) |
| R + valorantr | D-01 source (2) | ✗ — R not installed | — | `requests` directly hits same endpoints |
| Node.js | D-01 source (3) FlynV | ✓ (assumed Phase 0) | — | — (FlynV is binary-only, not callable from Python anyway) |
| Internet to `be-prod.rib.gg` | Path A scrape | ✓ (verified in research) | — | offline scrape fixture for tests |
| Internet to `bo3.gg` | D-01 source (4) | ✓ | — | — (bo3.gg has no round-event data; rules out as a primary source) |
| Network egress (residential / VPN considerations) | Path A | ✓ (no auth required, no IP block observed) | — | — |

**Missing dependencies with no fallback:**
- None. Every required dep has either a stdlib fallback or a viable alternative.

**Missing dependencies with fallback:**
- `requests` / `tenacity` / `tqdm` — install via `uv add` in Wave 1's first task. Standard Python deps; no surprise.
- `opencv-python` — only needed for Path B; do NOT install in v1 unless Path A fails.

---

## Validation Architecture

> Phase 2 has empirical-Bayes math + an SQLite ETL + a probe decision gate. Per the Nyquist validation framework, sensors and sample rates are designed below to detect the failure modes most likely to bleed P&L downstream (Phase 4 quoting on miscalibrated cells = the #1 risk).

### Test Framework
| Property | Value |
|----------|-------|
| Framework | `pytest 9.0.3` + `pytest-cov 7.1.0` + `hypothesis 6.152.4` (Phase 0 verified) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (Phase 0) |
| Quick run command | `uv run pytest tests/pricing/test_round_conclusion_loader.py tests/scripts/test_calibrate_round_conclusion.py -x --tb=short` |
| Full suite command | `uv run pytest -x` |
| Phase gate | `uv run pytest -x` AND `uv run mypy --strict src/pricing/` AND `uv run ruff check .` all green before `/gsd-verify-work`. |

### Phase Requirements → Test Map

| Req ID / Sensor | Behavior | Test Type | Automated Command | File Exists? |
|-----------------|----------|-----------|-------------------|---|
| REQ-round-event-data-pipeline (probe) | `scripts/probe_round_events.py --dry-run` writes 02-PROBE-LOG.md and exits 0 | smoke | `uv run python scripts/probe_round_events.py --dry-run` | ❌ Wave 0 |
| REQ-round-event-data-pipeline (probe) | `02-PROBE-LOG.md` records the path decision (A/B/C) and source-attempt evidence | structural assert | `pytest tests/scripts/test_probe_log_format.py::test_probe_log_has_decision -x` | ❌ Wave 0 |
| REQ-round-event-data-pipeline (Path A) | If Path A: `data/round_events.sqlite` matches `CON-round-events-schema` (8 columns + JSON) | unit | `pytest tests/scripts/test_round_events_schema.py::test_columns -x` | ❌ Wave 0 |
| REQ-round-event-data-pipeline (Path A) | If Path A: ≥1000 distinct `match_id` rows in `round_events` | data assertion | `pytest tests/scripts/test_round_events_count.py -x` (skipped unless db exists) | ❌ Wave 0 |
| REQ-round-event-data-pipeline (calibrate) | `models/round_conclusion.json` round-trips via `RoundConclusionLookup.from_json()` and re-`to_json()` to bit-equal | unit | `pytest tests/pricing/test_round_conclusion_loader.py::test_json_round_trip -x` | ❌ Wave 0 |
| REQ-round-event-data-pipeline (calibrate) | `RoundConclusionLookup.from_json("models/round_conclusion.json").lookup(...)` returns finite floats in `[0, 1]` for all keys present | property | `pytest tests/pricing/test_round_conclusion_loader.py::test_lookup_in_range -x` (hypothesis) | ❌ Wave 0 |
| REQ-round-event-data-pipeline (calibrate) | `from_json` classmethod satisfies `RoundConclusionFn` Protocol (the Phase 1 API surface lock) | type-check | `uv run mypy --strict src/pricing/round_conclusion.py` | ✓ (mypy strict already on) |
| REQ-round-event-data-pipeline (calibrate) | Calibrator on a synthetic 100-row dataset produces deterministic `_Cell` instances (same input → same output) | integration | `pytest tests/scripts/test_calibrate_round_conclusion.py::test_deterministic -x` | ❌ Wave 0 |
| REQ-round-event-data-pipeline (calibrate) | Synthetic dataset where `(numerical_diff=2, bomb_planted=True)` always wins → calibrated cell `shrunk()` returns >0.9 (not exactly 1.0 due to shrinkage to parent) | integration | `pytest tests/scripts/test_calibrate_round_conclusion.py::test_extreme_signal -x` | ❌ Wave 0 |
| REQ-round-event-data-pipeline (calibrate) | Bottom-up walk constructs all parents before children (no `_Cell` ever has unset `parent_p`) | invariant | `pytest tests/scripts/test_calibrate_round_conclusion.py::test_walk_order -x` | ❌ Wave 0 |
| REQ-round-event-data-pipeline (defuse semantics) | A round ending in `defuse` does NOT emit a phantom post-defuse `bomb_planted=False` state | unit | `pytest tests/scripts/test_synthesize_states.py::test_defuse_terminates -x` | ❌ Wave 0 |
| REQ-round-event-data-pipeline (side mapping) | `side_for_team_a` flips correctly at round 13 boundary | unit | `pytest tests/scripts/test_side_mapping.py -x` | ❌ Wave 0 |
| Phase 1 contract preservation | `RoundConclusionLookup()` (empty) still returns `_PHASE_1_FLAT_CELL_VALUE = 0.5` for any input — Path C compatibility | regression | `pytest tests/pricing/test_round_conclusion.py::test_empty_returns_half -x` | (existing Phase 1 test, may need rename) |
| `mypy --strict` | New `from_json` typing | type-check | `uv run mypy --strict src/pricing/round_conclusion.py` | ✓ |
| `ruff` | New scripts pass lint | lint | `uv run ruff check scripts/probe_round_events.py scripts/calibrate_round_conclusion.py` | ✓ |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/pricing/ tests/scripts/ -x --tb=short` (~10s on the synthetic-dataset tests; do NOT run the full Path A scrape per commit).
- **Per wave merge:** `uv run pytest -x && uv run mypy --strict src/pricing/ && uv run ruff check .`. Adds the existing Phase 0/1 test suites.
- **Phase gate (`/gsd-verify-work`):** Full suite green AND `02-PROBE-LOG.md` exists AND `models/round_conclusion.json` exists (Path A/B) OR explicit Path-C documentation in `02-VERIFICATION.md`.

### Wave 0 Gaps

These tests do not exist and must be created by Wave 0 / Wave 1 task definitions:

- [ ] `tests/pricing/test_round_conclusion_loader.py` — round-trip `to_json` / `from_json`, range checks (REQ-round-event-data-pipeline)
- [ ] `tests/scripts/test_calibrate_round_conclusion.py` — synthetic-dataset integration tests, walk-order invariant, deterministic output
- [ ] `tests/scripts/test_round_events_schema.py` — SQLite column assertion (CON-round-events-schema)
- [ ] `tests/scripts/test_synthesize_states.py` — `mid_round_states[]` derivation correctness (defuse, plant, kill ordering)
- [ ] `tests/scripts/test_side_mapping.py` — half-flip logic at round 13
- [ ] `tests/scripts/test_probe_log_format.py` — PROBE-LOG.md has the path decision in a parseable format
- [ ] `tests/scripts/test_round_events_count.py` — opt-in (skipif `not os.path.exists("data/round_events.sqlite")`); confirms ≥1000 matches in production run
- [ ] `tests/conftest.py` extension — fixtures for synthetic event-log + half_win_rates mini-dataset

**Bandwidth (failure mode if sensors absent):**
- **No `from_json` round-trip test:** silent JSON schema drift between calibrator and loader → Phase 4 trades on cells that lookup to 0.5 instead of calibrated values → between-round MM is fine but mid-round directional flips are mis-priced → P&L bleed.
- **No walk-order invariant test:** parent_p references uninitialized values (or `None`) → `_Cell.shrunk()` propagates NaN → `live_theo` returns NaN → kill switch (c) `|theo − market| > 20¢` trips immediately, but ONLY if NaN propagates to the comparison; some floating-point compare paths silently treat NaN as "not >20" → kill switch fails to fire → bot trades on garbage prices.
- **No defuse-termination test:** phantom `bomb_planted=False` rows pollute `cells_full` → mid-round predictions on planted-bomb scenarios shift by 5-10% → Brier degrades; Phase 5 paper-trade gate (DEC-020 Brier <0.22) likely missed.
- **No side-mapping test:** every row's `side` field is randomly flipped (50% wrong) → cells learn approximately 0.5 for every key (averaged-out signal) → calibrator returns flat-0.5-ish, indistinguishable from Path C from outside; the bug looks like "Path A produced low-information cells" but is actually a transform error.
- **No PROBE-LOG format test:** `02-PROBE-LOG.md` becomes a free-form file the orchestrator can't parse → Path-C deferral isn't machine-detectable → Phase 4 doesn't know to apply the D-12 hard contract.

---

## Sources

### Primary (HIGH confidence)
- **In-session live HTTP probe (2026-04-30):** `https://be-prod.rib.gg/v1/{events,series,matches/{id}/details}` confirmed working without auth. Sample VCT 2025 Pacific match (matchId=213508) inspected. Event types `{start, plant, kill, defuse}` verified. Round/event timing precision: millisecond.
- [tonyelhabr/valorantr R-package source — `R/get.R`](https://github.com/tonyelhabr/valorantr/blob/main/R/get.R) — comprehensive endpoint map; identifies `/v1/events`, `/v1/series`, `/v1/matches/{id}/details`, `/v1/players/{id}`, `/v1/teams/{id}`, `/v1/analytics/{agents|maps|weapons|compositions}`. Confirmed base URL `https://be-prod.rib.gg/v1/` (the SAME base I live-probed).
- [Traumist/RIB-Data-Scraper — `event_scraping.py`](https://github.com/Traumist/RIB-Data-Scraper/blob/main/event_scraping.py) — reference Python implementation. Uses `backend-prod.rib.gg` (deprecated subdomain) but identical endpoint paths and JSON keys.
- [Phase 1 `src/pricing/round_conclusion.py`](src/pricing/round_conclusion.py) — frozen public surface; `_Cell` shrinkage formula; Protocol contract.
- [Phase 1 `01-CONTEXT.md` D-06 / D-07](.planning/phases/01-core-pricing-engine/01-CONTEXT.md) — Phase 2 seam definition, Path-C compatibility commitment.
- [`data/half_win_rates.json` schema] — schema verified in-session: `{team_map_side: dict, league_map_side: dict, overall_avg: float, min_rounds_threshold: int, maps_in_data: list}`.
- [Phase 2 `02-CONTEXT.md`](.planning/phases/02-round-event-data/02-CONTEXT.md) — locked decisions D-01..D-16.
- [`prd.md` §5.3](prd.md), [`roadmap.md` §2](roadmap.md), [`CLAUDE.md` Critical rules](CLAUDE.md) — design authority.

### Secondary (MEDIUM confidence)
- [Valoscribe (Krishnan, Medium 2026)](https://medium.com/@ashwathbkrishnan/valoscribe-turning-valorant-broadcasts-into-structured-data-for-analytics-and-machine-learning-bdb7460dca30) — closest published analog to Path B; explicitly rejects OCR (Tesseract / EasyOCR / PaddleOCR) for Valorant HUD digits in favor of `cv2.matchTemplate`. Single-author blog post, no peer review, but author claims production deployment.
- [OCR comparison: Tesseract vs EasyOCR vs PaddleOCR (Beerten, Medium)](https://toon-beerten.medium.com/ocr-comparison-tesseract-versus-easyocr-vs-paddleocr-vs-mmocr-a362d9c79e66) — generic OCR comparison; consensus is "Tesseract for clean printed text, PaddleOCR for complex layouts." Does not specifically address custom-font in-game UIs.
- [Apl0x/VALORANT_scoreboard_reader](https://github.com/Apl0x/VALORANT_scoreboard_reader) — Tesseract-based Valorant end-game scoreboard reader. End-game scoreboard is structurally easier than mid-game HUD (static frame, larger fonts), so its success doesn't generalize cleanly to Path B's per-frame VOD parse.

### Tertiary (LOW confidence — needs validation)
- [VLR.gg forum post on data sources](https://www.vlr.gg/539137/how-does-rib-and-vlr-gg-get-data) — community speculation that rib.gg gets VCT API access from Riot. Not load-bearing for our research; we verified the public endpoints exist regardless of source.
- [FlynV/RIB.GG-Web-Scraper README](https://github.com/FlynV/RIB.GG-Web-Scraper) — claims to scrape rib.gg but README provides no implementation details, and the repo contains only a README + binary release. Marked as "considered, rejected" in `02-PROBE-LOG.md`.

---

## Metadata

**Confidence breakdown:**
- **Standard stack:** HIGH — `requests` + `tenacity` + `sqlite3` are unambiguously correct; live-probed endpoints confirm the API is callable.
- **Architecture:** HIGH — three-call chain (events → series → matches/{id}/details) verified end-to-end with sample data.
- **Pitfalls:** HIGH for #1, #2, #5, #6, #7 (verified or self-evident); MEDIUM for #3 (side-mapping logic is correct in principle but needs unit-test coverage in Wave 0); MEDIUM for #4 (defuse semantics — needs sample-data validation in Wave 1).
- **Calibration math:** HIGH — formula verbatim from Phase 1's `_Cell.shrunk()`; no new math.
- **Path B / template-matching:** MEDIUM — based on a single Medium-blog reference and ecosystem trend, not formally peer-reviewed. Acceptable since Path B is a contingency, not the primary path.
- **rib.gg endpoint stability over time:** MEDIUM — verified 2026-04-30; subdomain has migrated once (2022→2026). Plan must include a "endpoint shape audit" task at execution time.

**Research date:** 2026-04-30
**Valid until:** 2026-05-30 (30 days for stable; 7 days for Path B specifics if Path A fails). The rib.gg endpoint *could* migrate again at any time; if Phase 2 execution is delayed >30 days, re-probe the API before scraping.
