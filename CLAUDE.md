# CLAUDE.md — Valorant Live Pricing Model

Live pricing engine for Valorant BO3 series + per-map Kalshi markets. Hybrid market-maker / directional taker. Runs locally during dev, cloud VM in production.

**This is a separate project from `thunderedge/`.** It builds on artifacts from `thunderedge/worktrees/market-maker/` but does not import from it. The thunderedge repo has its own CLAUDE.md with different conventions for that codebase.

---

## Read first

- **`prd.md`** — full design doc. Decisions locked in: hybrid trading, BO3+per-map via single DP, half-Kelly + cap, tiered ingestion confirmation, hierarchical-lookup round model, four kill switches always-on, hybrid local-dev / cloud-prod.
- **`roadmap.md`** — eight build phases with implementation guidance and dependency graph. ~7–8 week timeline if rib.gg API path works.
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

1. **Single canonical entry point: `live_theo(state) → (theo, vega, confidence)`.** Do not recreate the `series_theo` / `series_theo_no_sides` / `series_theo_from_map_probs` triplet from the audited engine. Inconsistent `signal_strength` application across those three was a bug.
2. **BO3 series and per-map theos come from the same DP** — marginalize the DP for per-map. Never have two independent models that can disagree.
3. **Bradley-Terry round blend, not arithmetic mean.** `p = a*(1-b) / (a*(1-b) + (1-a)*b)`. The audited engine's `(a + (1-b))/2` under-weights compounding edges.
4. **Pistol + anti-eco modeled explicitly.** Rounds 1, 2, 3, 13, 14, 15 use separate probability inputs derived from `match_round_data` and `GUN_WIN_RATE = 0.822`. Constant `p1`/`p2` per half is wrong.
5. **OT is an explicit hard-stop at total = 24** with documented OT-as-coinflip leaf. Do NOT silently let the DP run past round 24 with `p = 0.5` (the audited engine's bug).
6. **Conviction clips: `[0.01, 0.99]`** at the boundaries. Document any tighter clip.

### Trading

7. **Half-Kelly with per-market cap.** `f = 0.5 × kelly_full`, capped at `PER_MARKET_CAP_FRAC` of bankroll. Never full Kelly.
8. **Hybrid mode: event-trigger with vega override.** MM by default; flip to directional on numerical imbalance, bomb plant, map-point, score 12-12 / 1-1 decider, OR vega > threshold.
9. **All four kill switches always-on** (Kalshi API errors, ingestion staleness > 5s, |theo − market| > 20¢, rolling Brier > 0.30 over 50 rounds). No flag to disable individual switches.
10. **Tiered ingestion confirmation** per PRD §5.1. Score updates need ≥ 2 sources within 2s. Mid-round events commit on 1 CV-based source if kill-feed cross-confirms.

### Code

11. **`mypy --strict` on `src/pricing/`.** The math layer must type-check.
12. **No magic numbers in business logic.** Every threshold lives in `src/config/constants.py`.
13. **Dry-run by default.** Live trading requires explicit `--live` flag at the entry point.

---

## Domain constants (lifted from thunderedge/CLAUDE.md, will move to `src/config/constants.py`)

```python
# Pricing
SHRINK_PRIOR              = 15.0     # Bayesian prior weight in rounds
SIGNAL_SCALE              = 0.10     # |model_p - 0.5| / scale → weight in [0,1]
GUN_WIN_RATE              = 0.822    # P(gun team wins eco round) — empirical
REGULATION_HALF           = 12
WIN_THRESHOLD             = 13

# Sizing
KELLY_MULTIPLIER          = 0.5
PER_MARKET_CAP_FRAC       = 0.05     # TBD — depends on bankroll

# Kill switches
KILL_SWITCH_STALENESS_S   = 5.0
KILL_SWITCH_DEVIATION_C   = 20
KILL_SWITCH_BRIER_BOUND   = 0.30
KILL_SWITCH_BRIER_WINDOW  = 50

# Mode flip
VEGA_DIRECTIONAL_THRESHOLD = 0.04    # TBD — calibrate after 20+ matches
```

### Economy buckets (inherited from `thunderedge/match_round_data`)

| Label | Credits |
|---|---|
| full | ≥ 20,000 |
| semi-buy | 10,000–19,999 |
| semi-eco | 5,000–9,999 |
| eco | < 5,000 |

---

## Data sources

| Source | Use | Latency | Notes |
|---|---|---|---|
| `data/half_win_rates.json` | Pre-match per-team/map/side rates | offline | Generated by `thunderedge/worktrees/half-win-rate/`. Recompute upstream when needed. |
| rib.gg internal API | Round-by-round events for round-conclusion model | offline | No public REST. Routes via `FlynV/RIB.GG-Web-Scraper` or `{valorantr}` R package. **Phase 2.1 scoping required.** |
| bo3.gg API | Backup match data | offline | Filter params broken — use slug endpoint only (per thunderedge CLAUDE.md). |
| Kalshi API v2 | Live market quotes + order placement | live | RSA PKCS1v15/SHA-256 auth. Key in `.env`. **No sandbox** — bot stays in `dry_run=True` until paper-trading promotion gate is met. |
| YouTube low-latency stream | Primary visual feed for OCR | ~3s | Lowest latency public source. |
| Twitter/Discord match threads | Soft cross-confirmation | ~1–3s | Never sole-source. |

---

## Run commands

(Placeholders — to be filled as code lands.)

```bash
# Phase 2.1 API probe
python scripts/probe_round_events.py

# Phase 1 DP pre-compute
python scripts/build_dp_table.py

# Live bot (dry-run default)
python -m src.main --match <ticker>
python -m src.main --match <ticker> --live   # only after paper-trade gate
```

---

## Differences from `thunderedge/CLAUDE.md`

- Single canonical pricing path (no four parallel tracks).
- `src/` package layout, not flat `backend/`.
- Strict typing on pricing layer (thunderedge is gradual).
- All kill switches always-on (thunderedge has no kill switches).
- No SQLite for live state — in-memory + JSONL event log.
- Dry-run is enforced via CLI flag, not constructor arg.

---

## Preferences

- Terse responses, no trailing summaries.
- One canonical implementation per concept — no two functions doing the same thing differently.
- Decisions in `prd.md`, build steps in `roadmap.md`, critical rules here. Do not duplicate.
