# CLAUDE.md — Valorant Live Pricing Model

Live pricing engine for Valorant BO3 series + per-map Kalshi markets. **Three-way mode + IDLE: opportunistic directional taking + between-round MM (paper-trade-evaluated peer) + post-plant quoting.** Runs locally during dev, cloud VM in production.

> **v2 architecture pivot (2026-05-02):** kill-feed CV / mid-round economy / ult tracking are CUT. Round-conclusion lookup is post-plant-only. Sizing uses portfolio Kelly with per-series aggregate cap. Promotion gate is relative-Brier vs market + fill-count. See `prd.md` change log + §2.1 for full framing.

**This is a separate project from `thunderedge/`.** It builds on artifacts from `thunderedge/worktrees/market-maker/` but does not import from it. The thunderedge repo has its own CLAUDE.md with different conventions for that codebase.

---

## Read first

- **`prd.md`** — full design doc. Decisions locked in (v2): three-way mode + IDLE, BO3+per-map via single DP, portfolio Kelly (per-market + per-series aggregate cap), simplified ingestion (3 OCR HUD targets + arbiter 3 deques), two-path round-conclusion (between-round + post-plant only), four kill switches always-on, hybrid local-dev / cloud-prod.
- **`roadmap.md`** — eight build phases with implementation guidance and dependency graph. ~5–6 week calendar to first live deploy (v2 — Phases 0/1/2 done).
- **`reference/`** — read-only. Salvaged files from the audit: `odds_utils.py` (as-is), `fair_value.py` (as-is), `theo_engine.py` (DP skeleton only — has documented bugs, see PRD §12.2), `market_maker.py` (Kalshi plumbing only).

---

## Repo layout

```
valorant-pricing-model/
  src/
    pricing/        # DP, Bradley-Terry blend, round-conclusion lookup, live_theo
    state/          # MatchState (single source of truth, versioned)
    ingestion/      # OCR, scoreboard polling, text listeners, cross-source arbiter
    quoting/        # KalshiOrderManager, MM, directional, kill switches
    sizing/         # half-Kelly + cap
    config/         # constants, thresholds (config/constants.py)
  tests/
  scripts/          # one-off probes, calibration runs
  data/             # half_win_rates.json (input), round_events (generated)
  models/           # cached DP table, round-conclusion lookup (generated)
  reference/        # read-only salvaged code
```

---

## Critical rules

These are non-negotiable design constraints from the PRD. Do not relax without updating `prd.md` first.

### Pricing

1. **Single canonical entry point: `live_theo(state) → TheoOutput(theo_series, theo_map, vega, confidence)`.** Do not recreate the `series_theo` / `series_theo_no_sides` / `series_theo_from_map_probs` triplet from the audited engine. Inconsistent `signal_strength` application across those three was a bug.
2. **BO3 series and per-map theos come from the same DP** — marginalize the DP for per-map. Never have two independent models that can disagree.
3. **Bradley-Terry round blend, not arithmetic mean.** `p = a*(1-b) / (a*(1-b) + (1-a)*b)`. The audited engine's `(a + (1-b))/2` under-weights compounding edges.
4. **Pistol + anti-eco modeled explicitly.** Rounds 1, 2, 3, 13, 14, 15 use separate probability inputs derived from `match_round_data` and `GUN_WIN_RATE = 0.822`. Constant `p1`/`p2` per half is wrong.
5. **OT is an explicit hard-stop at total = 24** with documented OT-as-coinflip leaf. Do NOT silently let the DP run past round 24 with `p = 0.5`.
6. **Conviction clips: `[0.01, 0.99]`** at the boundaries. Document any tighter clip.
6a. **Two clean code paths in `live_theo` (v2).** Between-round uses side baseline; post-plant uses lookup keyed on `(att, def, time_bucket, side, map)`. **No general mid-round path.** Mid-round-not-planted returns between-round theo with degraded confidence; quoting maps to IDLE.

### Trading

7. **Portfolio Kelly: half-Kelly with per-market AND per-series aggregate cap (v2).** `f = 0.5 × kelly_full`, then `f = min(f, PER_MARKET_CAP_FRAC)` (0.05), then `f = min(f, SERIES_AGGREGATE_CAP_FRAC − current_series_exposure)` (0.10). Returns 0 if aggregate cap exceeded. Per-market cap alone does NOT bound aggregate correlated exposure across moneyline + map handicaps + round handicaps. Full covariance-aware Kelly is Phase 7.
8. **Three-way mode + IDLE (v2).** `MM_BETWEEN_ROUND` / `DIRECTIONAL_TAKE` / `POST_PLANT_QUOTE` / `IDLE`. Selection in order: kill-switch → bomb-planted → mid-round-not-planted (IDLE) → take-threshold → MM-min-edge → IDLE. **MM and DIRECTIONAL are first-class peers** running on parallel hypothetical-fill ledgers in paper trade — neither is "default". `VEGA_DIRECTIONAL_THRESHOLD` from v1 is REMOVED — DIRECTIONAL_TAKE triggers on `|theo − market_mid|`, not vega magnitude.
9. **All four kill switches always-on** (Kalshi API errors, ingestion staleness > 5s, |theo − market| > 20¢, rolling Brier > 0.30 over 50 rounds). No flag to disable individual switches.
10. **Simplified tiered ingestion confirmation (v2).** Arbiter has 3 deques (`score_changes`, `bomb_events`, `round_end_events`) — kill_events / numerical_flips REMOVED. Score updates need ≥ 2 sources within 2s. Bomb plant/defuse: 1 OCR source soft-commit (no kill-feed cross-confirm because kill feed is cut). Round-end: 1 OCR source soft-commit, hard-confirmed by next score.
10a. **OCR scope: three HUD targets only (v2).** Score banner (250ms), bomb-plant icon (500ms), round-end banner (100ms during window). Tesseract-only, CPU-only. **Kill-feed parsing, ult tracking, mid-round economy inference are explicitly out of scope.** When `bomb_planted=True`, a separate post-plant attackers/defenders-alive HUD widget is parsed at 250ms.
10b. **Promotion gate: relative Brier + fill-count (v2).** `Brier(model) < Brier(market_mid) − 0.02` over a 50-round window AND MM hypothetical fills ≥ `MIN_FILLS_PER_MATCH` (initial: 3). If MM fails the fill-count gate, MM is cut from production — only DIRECTIONAL_TAKE (and POST_PLANT_QUOTE if active) promotes to live. Absolute Brier 0.22 from v1 is REMOVED.

### Code

11. **`mypy --strict` on `src/pricing/`.** The math layer must type-check.
12. **No magic numbers in business logic.** Every threshold lives in `src/config/constants.py`.
13. **Dry-run by default.** Live trading requires explicit `--live` flag at the entry point.

---

## Domain constants (`src/config/constants.py`)

```python
# Pricing
SHRINK_PRIOR              = 15.0     # Bayesian prior weight in rounds
SIGNAL_SCALE              = 0.10     # |model_p - 0.5| / scale → weight in [0,1]
GUN_WIN_RATE              = 0.822    # P(gun team wins eco round) — empirical
REGULATION_HALF           = 12
WIN_THRESHOLD             = 13

# Sizing — portfolio Kelly (v2)
KELLY_MULTIPLIER          = 0.5
PER_MARKET_CAP_FRAC       = 0.05     # TBD — depends on bankroll
SERIES_AGGREGATE_CAP_FRAC = 0.10     # NEW v2 — TBD; calibrate after first paper-trade event
MIN_HALF_SPREAD           = ...      # TBD — must beat Kalshi commission + slippage

# Mode-selector thresholds (v2)
TAKE_THRESHOLD            = ...      # TBD — between-round take threshold
MM_MIN_EDGE               = ...      # TBD — minimum spread for MM to quote
POST_PLANT_TAKE_THRESHOLD = ...      # TBD — narrower than between-round take

# Kill switches
KILL_SWITCH_STALENESS_S   = 5.0
KILL_SWITCH_DEVIATION_C   = 20
KILL_SWITCH_BRIER_BOUND   = 0.30
KILL_SWITCH_BRIER_WINDOW  = 50

# Promotion gate (v2)
RELATIVE_BRIER_EDGE_MIN   = 0.02     # NEW v2 — Brier(model) < Brier(market_mid) − this
MIN_FILLS_PER_MATCH       = 3        # NEW v2 — MM cut if hypothetical fills below this
```

**Removed in v2:** `VEGA_DIRECTIONAL_THRESHOLD` (DIRECTIONAL_TAKE no longer triggers on vega; triggers on `|theo - market_mid|`).

**`MatchState` field set (v2)** — `match_id, map_idx, a/b_map_score, a/b_round, side_orient, bomb_planted, attackers_alive | None, defenders_alive | None, time_left_s | None, seq_id, last_updated_ts`. Cut from v1: `econ_a/b`, `ults_a/b`, `players_alive_a/b`. `attackers_alive` / `defenders_alive` populated only when `bomb_planted=True` (via post-plant HUD widget OCR — separate from cut kill-feed).

### Economy buckets — DEPRECATED in v2

The v1 economy bucket schema (`full ≥ 20k / semi-buy 10–20k / semi-eco 5–10k / eco < 5k`) is no longer consumed by live pricing — mid-round economy inference is cut. The `credits_to_bucket` function in `src/pricing/economy.py` was used by the v1 round-conclusion lookup keys; with the v2 rekey to `(att, def, time_bucket, side, map)` it has no caller. Phase 3 deletes it. Buckets remain referenced in offline calibration tooling for historical analysis only.

---

## Data sources

| Source | Use | Latency | Notes |
|---|---|---|---|
| `data/half_win_rates.json` | Pre-match per-team/map/side rates | offline | Generated by `thunderedge/worktrees/half-win-rate/`. Recompute upstream when needed. |
| rib.gg internal API | Round-by-round events (offline calibration) + live scoreboard polling | offline + live | Phase 2 proven (1000 matches calibrated). Phase 3 reuses resilience patterns from `scripts/probe_round_events.py`. |
| bo3.gg / vlr.gg APIs | Backup score sources | live | **Deferred to Phase 5 robustness work** — rib.gg primary is sufficient and proven. |
| Kalshi API v2 | Live market quotes + order placement | live | RSA-PSS / SHA-256 auth (verified docs.kalshi.com 2026-05-09; MGF1(SHA256), salt_length=DIGEST_LENGTH). Key in `.env`. **No sandbox** — bot stays in `dry_run=True` until paper-trading promotion gate is met. |
| YouTube low-latency stream | Primary visual feed for OCR | ~3s | Lowest latency public source. **OCR scope (v2): three HUD targets only** (score banner, bomb-plant icon, round-end banner) + post-plant attackers/defenders-alive widget. Kill-feed parsing CUT. |
| Twitter API v2 streaming | Soft cross-confirmation | ~1–3s | Never sole-source. Degrades to no-op without `TWITTER_BEARER_TOKEN`. |

---

## Run commands

(Placeholders — to be filled as code lands.)

```bash
# Phase 2.1 API probe
python scripts/probe_round_events.py

# Phase 1 DP pre-compute
python scripts/build_dp_table.py

# Operator gate 2 — Kalshi auth smoke (one-time after .env populated)
python scripts/kalshi_auth_smoke.py

# Live bot (dry-run default)
python -m src.main --match <ticker>
python -m src.main --match <ticker> --live   # only after paper-trade gate
```

---

## Differences from `thunderedge/CLAUDE.md`

- Single canonical pricing path (no four parallel tracks).
- `src/` package layout, not flat `backend/`.
- Strict typing on pricing layer (thunderedge is gradual). Extends to `src/state/` per Phase 3.
- All kill switches always-on (thunderedge has no kill switches).
- No SQLite for live state — in-memory + JSONL event log.
- Dry-run is enforced via CLI flag, not constructor arg.
- **(v2)** Three-way mode + IDLE (no MM-as-default); portfolio-aware Kelly; OCR scope cut to three HUD targets; relative-Brier + fill-count promotion gate.

---

## Preferences

- Terse responses, no trailing summaries.
- One canonical implementation per concept — no two functions doing the same thing differently.
- Decisions in `prd.md`, build steps in `roadmap.md`, critical rules here. Do not duplicate.
