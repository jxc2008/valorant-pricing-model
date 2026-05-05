# Roadmap — Valorant Live Pricing Model

Companion to `prd.md`. Lists every step from empty `src/` to live-trading production, with the implementation approach for each.

> **v2 architecture pivot (2026-05-02):** Phase 3 onwards is rescoped. The bot is now built around opportunistic directional taking + post-plant pricing, with MM as a paper-trade-evaluated peer rather than the primary strategy. Kill-feed CV, mid-round economy inference, and ult tracking are cut. See `prd.md` change log + §2.1 for full framing.

**Critical-path dependency graph (v2):**

```
Phase 0 (foundation) ──┬→ Phase 1 (pricing engine) ──┐
                       └→ Phase 2 (round-event data) ┘
                                ↓
                     Phase 3 (rescoped: live ingestion + post-plant rekey)
                                ↓
                     Phase 4 (rescoped: three-way mode + portfolio Kelly)
                                ↓
                     Phase 5 (relative-Brier + fill-count gates)
                                ↓
                     Phase 6 (deployment) → Phase 7 (operational maturity)
```

Phase 1 and Phase 2 ran in parallel. Phase 3 now folds the round-conclusion rekeying into ingestion (single phase), since the rekey is a Phase 2 dataset filter + recalibration that depends on what Phase 3 actually captures from live broadcasts.

---

## Phase 0 — Foundation (~2 days)  ✅ Complete (2026-04-27)

### 0.1 Project structure

```
valorant-pricing-model/
  src/
    pricing/        # DP, round-conclusion, vega
    state/          # State engine
    ingestion/      # OCR (3 targets), polling, text listener, arbiter
    quoting/        # KalshiOrderManager, MM, directional, post-plant, kill switches
    sizing/         # Half-Kelly + per-market cap + per-series aggregate cap
    config/         # constants, thresholds
  tests/
  scripts/          # one-off probes, calibration runs
  data/             # half_win_rates.json, round-event dataset
  models/           # cached DP table, post-plant lookup
  reference/        # already populated
  prd.md
  roadmap.md
```

### 0.2 Tooling

- Python 3.11, `uv` for venv, `pyproject.toml`
- `pytest` + `pytest-cov` + `hypothesis` for property tests
- `ruff` for lint + format
- `mypy --strict` on `src/pricing/` (math layer must type-check); extends to `src/state/` in Phase 3

### 0.3 Data store decision

Existing repo uses SQLite for the dataset cache. Stick with it for cache. **Live state is in-memory + JSONL event log only.** No SQLite for live state.

### 0.4 Configuration

Every magic number lives in `config/constants.py`. v2 baseline:

```python
# Pricing math (locked)
SHRINK_PRIOR = 15.0
SIGNAL_SCALE = 0.10
GUN_WIN_RATE = 0.822
REGULATION_HALF = 12
WIN_THRESHOLD = 13

# Sizing — portfolio Kelly (v2)
KELLY_MULTIPLIER = 0.5
PER_MARKET_CAP_FRAC = 0.05            # TBD — depends on bankroll
SERIES_AGGREGATE_CAP_FRAC = 0.10      # NEW v2 — TBD, calibrate after first paper-trade event
MIN_HALF_SPREAD = ...                 # TBD — must beat Kalshi commission + slippage

# Mode-selector thresholds (v2)
TAKE_THRESHOLD = ...                  # TBD — calibrate from observed market structure
MM_MIN_EDGE = ...                     # TBD — minimum spread to make MM worth quoting
POST_PLANT_TAKE_THRESHOLD = ...       # TBD — narrower than between-round take

# Kill switches
KILL_SWITCH_STALENESS_S = 5.0
KILL_SWITCH_DEVIATION_C = 20
KILL_SWITCH_BRIER_BOUND = 0.30
KILL_SWITCH_BRIER_WINDOW = 50

# Promotion gate (v2)
RELATIVE_BRIER_EDGE_MIN = 0.02        # NEW v2 — model must beat market by this much
MIN_FILLS_PER_MATCH = 3               # NEW v2 — MM cut if hypothetical fills below this
```

**Removed from v1:** `VEGA_DIRECTIONAL_THRESHOLD` (DIRECTIONAL_TAKE no longer triggers on vega; triggers on `|theo - market_mid|`).

Threshold-tuning is a Phase 5 activity; ship initial values, never hardcode in business logic.

---

## Phase 1 — Core pricing engine  ✅ Complete (2026-04-29)

Phase 1 shipped the math layer: generalized BO3 DP, Bradley-Terry round blend, pistol/anti-eco modeling (rounds 1, 2, 3, 13, 14, 15), explicit OT hard-stop at total=24 with documented coinflip leaf, conviction clips at `[0.01, 0.99]`, and the canonical `live_theo(state) → TheoOutput(theo_series, theo_map, vega, confidence)` entry point.

The math layer is **strategy-agnostic** — none of it cares whether the quoting layer is MM-primary or directional-primary. The v2 pivot doesn't touch Phase 1 except for §1.5 below (round-conclusion lookup keys, which are touched in Phase 3, not retroactively in Phase 1).

### 1.5 Round-conclusion lookup (skeleton in Phase 1, **rekeyed in Phase 3**)

The Phase 1 skeleton supports the `(numerical_diff, bomb, side, econ_bucket, map)` keys used by the v1 architecture and was calibrated in Phase 2 against that schema. **In v2, Phase 3 rekeys this to `(attackers_alive, defenders_alive, time_remaining_bucket, side, map)` filtered to `bomb_planted=True` rounds.** The recalibration uses the same Phase 2 dataset; the `_Cell` data structure and Bayesian shrinkage code are unchanged.

---

## Phase 2 — Round-event data  ✅ Complete (2026-05-01)

Phase 2 took **Path A** (rib.gg API). 1000 matches / 42586 rounds calibrated. `models/round_conclusion.json` populated with cells keyed on the v1 schema.

**v2 follow-up in Phase 3:** filter the dataset to `bomb_planted=True` rounds (~25k samples), rekey cells to `(att, def, time_bucket, side, map)`, recalibrate. Phase 3 also verifies whether the captured `mid_round_states[]` schema includes `attackers_alive`, `defenders_alive`, `time_remaining` at bomb-plant moments — if not, partial Phase 2 ETL re-run scoped to post-plant.

Path B (OCR-driven VOD labeling) is **dropped in v2** — it was always the weakest of the three paths and the new architecture explicitly avoids the kill-feed CV that was its primary motivation.

Path C (defer mid-round) is **the chosen design**, just with a more honest framing: between-round + post-plant only, no general mid-round path.

---

## Phase 3 — Live ingestion layer (RESCOPED v2, ~5–7 days)

> **v2 scope cut:** kill-feed CV, mid-round economy inference, ult tracking — all out. OCR is tesseract-only against three HUD elements. MatchState shrinks to scoreboard + bomb-plant context.

### 3.1 State engine (`src/state/match_state.py`, ~1 day)

```python
@dataclass(frozen=True, slots=True)
class MatchState:
    match_id: str
    map_idx: int
    a_map_score: int; b_map_score: int
    a_round: int; b_round: int
    side_orient: str  # 'a_atk' | 'a_def'
    bomb_planted: bool
    attackers_alive: int | None  # only when bomb_planted=True
    defenders_alive: int | None  # only when bomb_planted=True
    time_left_s: float | None
    seq_id: int
    last_updated_ts: float
```

Fields cut from v1: `econ_a/b`, `ults_a/b`, `players_alive_a/b`. Mutators bump `seq_id`. Append every mutation to a JSONL event log. Atomic move from `src/pricing/data.py` to `src/state/match_state.py`; all Phase 1 imports updated together.

### 3.2 Scoreboard polling (`src/ingestion/scoreboard.py`, ~1–2 days)

Reuse the Phase 2 `scripts/probe_round_events.py` resilience patterns: tenacity retry with `Retry-After` honoring, `Connection: close` header, per-page-skip on transient errors, 5-failure cooldown. Poll rib.gg every 5 s. Authoritative but slowest source.

bo3.gg / vlr.gg adapters **deferred to Phase 5 robustness work** (rib.gg primary is sufficient and proven).

### 3.3 OCR pipeline (`src/ingestion/ocr.py`, ~1–2 days)

**Three targets only.** Tesseract handles all three.

| Target | Cadence | Output |
|---|---|---|
| Score banner | 250 ms | score-change events |
| Bomb-plant icon | 500 ms | plant/defuse events; drives `POST_PLANT_QUOTE` mode + defensive quote-pull |
| Round-end banner | 100 ms during round-end window | predicted round outcome (~500 ms before scoreboard updates) |

**Latency target:** decode + inference < 100 ms median per frame. CPU-only (Hetzner CCX13 has no GPU).

**Cut from v1 scope:** kill feed, ult orbs, player-alive indicators, ONNX runtime, CTC decoder, GPU dependency, `vision_parser.py` salvage.

When `bomb_planted=True`, a separate **post-plant attackers/defenders-alive HUD widget** (visible only post-plant) is parsed at 250 ms cadence to populate the lookup keys. This is a separate, simpler OCR target than full kill-feed parsing.

### 3.4 Text listeners (`src/ingestion/text_listener.py`, ~1 day)

Twitter API v2 streaming filter on match-related hashtags / accounts. Soft cross-confirmation only — never sole-source. Degrades to no-op when `TWITTER_BEARER_TOKEN` is empty (CI cannot exercise live Twitter v2 streaming since paid tier is required).

### 3.5 Cross-source arbiter (`src/ingestion/arbiter.py`, ~1 day)

**Three deques** (was five in v1): `score_changes`, `bomb_events`, `round_end_events`. Cut: `kill_events`, `numerical_flips`.

Per-event-type rules:

| Event type | Rule |
|---|---|
| Score change | ≥ 2 sources within 2 s window (rib.gg + OCR + Twitter as soft-confirm) |
| Bomb plant/defuse | 1 OCR source — soft commit; hard-confirmed by next round-end or score |
| Round-end banner | 1 OCR source — soft commit; hard-confirmed by next score update |

Quarantined updates logged to the same JSONL with `quarantined: true`, `seq_id: null` (not bumped).

### 3.6 Round-conclusion rekey + post-plant calibration (`src/pricing/round_conclusion.py`, ~1 day)

Filter the Phase 2 dataset to `bomb_planted=True` rows. Verify the captured schema includes `attackers_alive`, `defenders_alive`, `time_remaining`. If missing fields, partial Phase 2 ETL re-run scoped to post-plant moments.

Rekey lookup cells to `(att, def, time_bucket, side, map)`. Recalibrate with the same Bayesian shrinkage (cell → side+map → side → att+def baseline). Update `live_theo` to dispatch:

```python
if state.bomb_planted:
    round_p = post_plant_lookup(...)
else:
    round_p = side_baseline(...)
```

No general mid-round path.

### 3.7 Latency instrumentation (~0.5 day)

Every confirmed event carries six-stage timestamps: `t_observed`, `t_ingested`, `t_arbited`, `t_state_committed`, `t_theo_computed`, `t_quote_sent` (last filled by Phase 4). Logged to a metrics file.

### 3.8 Synthetic E2E gate (~1 day)

`tests/ingestion/test_e2e.py` drives synthetic rib.gg + OCR (3 HUD targets) + Twitter through arbiter → MatchState → `live_theo`. Asserts:

- `seq_id` strictly monotonic over ≥ 30 events
- p50 `t_observed → t_state_committed` < 500 ms
- bomb-detect → quote-pull p50 < 200 ms (latency-critical defensive path)
- `theo_series` non-degenerate post-plant (∈ (0.01, 0.99), shifts off baseline when post-plant lookup fires)

---

## Phase 4 — Quoting layer (~5–7 days)

> **v2 architecture:** three-way mode + IDLE. MM and DIRECTIONAL run on **separate hypothetical-fill ledgers** during paper trade — neither is "primary".

### 4.1 Extract `KalshiOrderManager` (`src/quoting/order_manager.py`, ~1 day)

From `reference/market_maker.py`, salvage:

- `Quote` dataclass
- `_place_quote`, `_cancel_quote`, `cancel_all_orders`
- Error-streak retry logic
- `_is_near_close` close-time guard
- Dry-run mode

Strip everything else.

### 4.2 Mode selector (`src/quoting/mode.py`, ~0.5 day)

Pure function:

```python
def trading_mode(
    state: MatchState,
    theo: float,
    market: MarketQuote,
    vega_between: float,
    vega_post_plant: float,
    kill_switch_active: bool,
) -> Literal["MM_BETWEEN_ROUND", "DIRECTIONAL_TAKE", "POST_PLANT_QUOTE", "IDLE"]:
    if kill_switch_active: return "IDLE"
    if state.bomb_planted: return "POST_PLANT_QUOTE"
    if state.is_mid_round and not state.bomb_planted: return "IDLE"
    # between-round from here:
    if abs(theo - market.mid_cents) > TAKE_THRESHOLD: return "DIRECTIONAL_TAKE"
    if market.spread_cents > MM_MIN_EDGE: return "MM_BETWEEN_ROUND"
    return "IDLE"
```

### 4.3 MM quoter (`src/quoting/mm.py`, ~1 day)

Quote `theo ± vega-scaled spread` between rounds only. `spread = max(MIN_HALF_SPREAD, k × sqrt(vega_between)) + staleness_penalty`. Spread floor must beat Kalshi commission + slippage. Skew quotes when adverse-selection risk is high.

### 4.4 Directional taker (`src/quoting/directional.py`, ~1 day) — **first-class peer**

When mode = `DIRECTIONAL_TAKE`, lift the offer (or hit the bid). Sized by portfolio Kelly (§4.6). **Runs on its own hypothetical-fill ledger during paper trade** — fills, P&L, and Brier tracked separately from MM.

### 4.5 Post-plant quoter (`src/quoting/post_plant.py`, ~0.5 day)

When mode = `POST_PLANT_QUOTE`:

1. **Defensive quote-pull on plant detection** — cancel any resting quotes within 200 ms (latency-critical).
2. **Re-price** using `live_theo(state)` with the post-plant code path.
3. **Take** if `|theo − market| > POST_PLANT_TAKE_THRESHOLD` (narrower than between-round take).
4. Otherwise **quote** at theo ± narrow spread (high-conviction state).

### 4.6 Portfolio Kelly sizer (`src/sizing/kelly.py`, ~1 day) — **v2 portfolio-aware**

```python
def kelly_size(
    theo: float,
    market_yes_ask: float,
    bankroll: float,
    series_id: str,
    current_series_exposure: dict[str, float],
) -> int:
    p, q = theo, 1 - theo
    b = (1 - market_yes_ask) / market_yes_ask
    f_full = (b * p - q) / b
    f = max(0.0, KELLY_MULTIPLIER * f_full)
    f = min(f, PER_MARKET_CAP_FRAC)

    # Portfolio cap — bound aggregate exposure across correlated markets on this series
    used = current_series_exposure.get(series_id, 0.0)
    headroom = max(0.0, SERIES_AGGREGATE_CAP_FRAC - used)
    f = min(f, headroom)

    if f == 0.0: return 0
    return int(f * bankroll / market_yes_ask)
```

The simple aggregate cap is the v1 floor. **Full covariance-aware portfolio Kelly with per-series correlation matrix is Phase 7 maturity work** (§7.5).

### 4.7 Kill switches (`src/quoting/kill_switches.py`, ~1 day)

Each switch is a pure predicate over `(state, theo, market, recent_briers)`. Quoter calls all four every cycle; if ANY trips, all resting quotes cancelled and alert fires. Always-on; no per-switch disable flag.

### 4.8 Order lifecycle reconciliation (~1 day)

Every poll cycle: fetch open orders from Kalshi, reconcile against in-memory `_active_quotes`. Defends against state-drift bugs.

---

## Phase 5 — Validation (~2–4 weeks, calendar-bound by live events)

### 5.1 Unit + property tests (~ongoing through Phases 1–4)

80% line coverage on `src/pricing/`. `hypothesis` property tests:

- DP value in [0, 1] for any state
- DP value monotonic in `round_p`
- `theo_series` equals sum over outcomes derivable from `theo_map[]`
- Bradley-Terry blend symmetry: `round_p(a, b) == 1 − round_p(b, a)`

### 5.2 Backtest (~3–5 days)

Replay past season's matches against `live_theo` running on synthetic state from `match_round_data`. Compute Brier per state-bucket (between-round / post-plant). **No fills** — model-only validation. Order-fill backtest skipped (Kalshi historical order book unavailable).

**v2 addition:** also compute `Brier(market_mid)` per bucket from synced Kalshi historical close prices. Compare model and market Brier side-by-side.

### 5.3 Paper trading (~1+ event of live matches, ~2 weeks)

Run full bot with `dry_run=True` against live Kalshi matches. Track:

- Hypothetical fills **on two separate ledgers**: MM ledger and DIRECTIONAL ledger
- Hypothetical P&L per ledger
- Realized Brier per round prediction (model vs market)
- Latency p50, p99 per pipeline stage
- POST_PLANT_QUOTE: bomb-detect → quote-pull p50

### 5.4 Promotion gate (v2 — replaces absolute Brier 0.22)

After ≥ 1 full event of paper trading:

1. **Relative Brier:** `Brier(model) < Brier(market_mid) − RELATIVE_BRIER_EDGE_MIN` (0.02) over a 50-round window. If model Brier ≥ market Brier, **do not deploy** — no edge.
2. **Fill-count gate (MM):** if MM hypothetical fills < `MIN_FILLS_PER_MATCH` (3) averaged over the event, **MM is cut from production.** Only DIRECTIONAL_TAKE (and POST_PLANT_QUOTE if active) promotes to live.
3. **Latency:** p50 event → state-commit < 500 ms; bomb-detect → quote-pull p50 < 200 ms; quote-cancel p99 < 100 ms.
4. **Zero kill-switch trips for ingestion bugs.** Model-trip OK; bug-trip not.

### 5.5 Calibration loop (~ongoing)

After 100 matches of paper-trade data:

- Re-fit `SHRINK_PRIOR` to minimize live Brier
- Calibrate `TAKE_THRESHOLD`, `MM_MIN_EDGE`, `POST_PLANT_TAKE_THRESHOLD` from observed market structure
- Recompute `SERIES_AGGREGATE_CAP_FRAC` from observed inter-market correlation
- Re-tune kill-switch thresholds against observed false-positive rate
- Pick + calibrate `vega_post_plant` formula

---

## Phase 6 — Deployment (~3–5 days)

### 6.1 Containerization

Single multi-stage `Dockerfile` (builder + slim runtime). Image size target < 500 MB. Tesseract installed in the runtime image (~50 MB).

### 6.2 Cloud VM

Hetzner CCX13 (~$20/mo, 2 vCPU, 8 GB RAM, US-East). AWS t3.small alternative.

### 6.3 Deploy pipeline

Local `uv run` against `dry_run=True` with real Kalshi creds in `.env`. CI (GitHub Actions): build Docker image, push to GHCR, run tests. Cloud: `docker pull && docker run` with secrets mounted from a separate key file (never in image, never in env vars).

### 6.4 Secrets

Kalshi private key file mounted as Docker secret. `TWITTER_BEARER_TOKEN` (if used) in mounted secret too. `.env` for non-sensitive config.

### 6.5 Logging + alerting

Structured JSON logs to stdout, captured by Docker. Loki / Grafana Cloud free tier. PagerDuty / SMS alerts on kill-switch trips and process crashes.

### 6.6 Monitoring

Grafana dashboard: theo vs market over time, fill rate **per ledger (MM / DIRECTIONAL / POST_PLANT)**, current inventory, kill-switch trip log, latency p50/p99, daily P&L.

---

## Phase 7 — Operational maturity (ongoing)

### 7.1 Daily metrics report

Cron job emails daily summary: matches traded, fill count per strategy, P&L per strategy, Brier vs market, kill-switch trips, model version.

### 7.2 Weekly drift detection

Compare last 7 days' Brier distribution to baseline calibration set. If KL divergence exceeds threshold, alert.

### 7.3 Incident runbook

Halt remotely. Manual cancel via Kalshi UI. Image rollback. Per-kill-switch interpretation.

### 7.4 Operational risk limits

Daily loss limit halts the bot when cumulative realized + unrealized P&L < −X% of bankroll. Distinct from per-market kill switches.

### 7.5 Full covariance-aware portfolio Kelly (NEW v2 maturity item)

Replace the simple per-series aggregate cap (Phase 4.6) with covariance-aware portfolio Kelly. Inputs: per-series correlation matrix derived from paper-trade + live Brier history. Output: position sizing that accounts for inter-market correlation rather than just bounding aggregate fractional exposure.

This is **Phase 7 work, not Phase 4.** The simple cap is "safe-enough for paper trade"; the covariance-aware version is "correct".

---

## Critical path summary (v2)

| Sequence | Duration | Blocks |
|---|---|---|
| Phase 0 | 2 days ✅ | Everything |
| Phase 1 (pricing core) | 5–7 days ✅ | Phase 4 |
| Phase 2 (data scoping + pull) | 3 days API ✅ | Phase 3 rekey |
| Phase 3 (rescoped ingestion + post-plant rekey) | **5–7 days** (was 7–10) | Phase 4 |
| Phase 4 (rescoped quoting) | 5–7 days | Phase 5 |
| Phase 5.1–5.2 (tests + backtest) | 3–5 days | Phase 5.3 |
| Phase 5.3 (paper trading) | 2 weeks calendar | Phase 6 |
| Phase 6 (deployment) | 3–5 days | Phase 7 |

**v2 realistic total:** 3–4 weeks of remaining build time (Phases 0/1/2 done), then 2 weeks paper trading. ~5–6 weeks calendar to first live deploy.

**Earliest revenue:** between-round directional taking after ~3 weeks if Phase 3 ingestion + Phase 4 mode selector + portfolio Kelly land cleanly. Post-plant quoting is additive on top. MM survives only if the fill-count gate clears in paper trade.
