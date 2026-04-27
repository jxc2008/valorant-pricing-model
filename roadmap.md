# Roadmap — Valorant Live Pricing Model

Companion to `prd.md`. Lists every step from empty `src/` to live-trading production, with the implementation approach for each.

**Critical-path dependency graph:**

```
Phase 0 (foundation) → Phase 1 (pricing engine) ─┬→ Phase 4 (quoting)
                       Phase 2 (round-event data) ┤   ↑
                       Phase 3 (live ingestion) ──┴───┘
                                                       ↓
                                          Phase 5 (validation)
                                                       ↓
                                          Phase 6 (deployment)
                                                       ↓
                                          Phase 7 (operational maturity)
```

Phase 1 has no data dependencies and can start immediately. Phase 2's API scope decision gates whether the round-conclusion model is built now or deferred.

---

## Phase 0 — Foundation (~2 days)

### 0.1 Project structure

```
valorant-pricing-model/
  src/
    pricing/        # DP, round-conclusion, vega
    state/          # State engine
    ingestion/      # OCR, polling, text listener, arbiter
    quoting/        # KalshiOrderManager, MM, directional, kill switches
    sizing/         # Half-Kelly + cap
    config/         # constants, thresholds
  tests/
  scripts/          # one-off probes, calibration runs
  data/             # half_win_rates.json, round-event dataset
  models/           # cached DP table, round-conclusion lookup
  reference/        # already populated
  prd.md
  roadmap.md
```

### 0.2 Tooling

- Python 3.11, `uv` for venv (faster than pip), `pyproject.toml`
- `pytest` + `pytest-cov` + `hypothesis` for property-based tests
- `ruff` for lint + format (one tool, fast)
- `mypy --strict` on `src/pricing/` (the math layer must type-check)

### 0.3 Data store decision

Existing repo uses SQLite. Stick with it for the dataset cache. **Do not** put live state in SQLite — the state engine is in-memory only, persisted to disk only as event logs for replay/debugging.

### 0.4 Configuration

Single `config/constants.py` with every magic number from the PRD:

```python
SHRINK_PRIOR = 15.0
SIGNAL_SCALE = 0.10
GUN_WIN_RATE = 0.822
KILL_SWITCH_STALENESS_S = 5.0
KILL_SWITCH_DEVIATION_C = 20
KILL_SWITCH_BRIER_BOUND = 0.30
KILL_SWITCH_BRIER_WINDOW = 50
KELLY_MULTIPLIER = 0.5
PER_MARKET_CAP_FRAC = 0.05  # TBD
VEGA_DIRECTIONAL_THRESHOLD = 0.04  # TBD, calibrate later
```

Threshold-tuning is a Phase 5 activity; ship initial values, never hardcode in business logic.

---

## Phase 1 — Core pricing engine (~5–7 days)

No data dependencies. Start here.

### 1.1 Generalized BO3 DP (`src/pricing/dp.py`)

Function signature:

```python
def series_value(
    state: BO3State,
    round_p_fn: Callable[[BO3State], float],
) -> float
```

Where `BO3State = (map_idx, a_map_score, b_map_score, a_round, b_round, side_orient, map_pool)`.

**Implementation approach:**

- Memoized recursion via `@functools.lru_cache(maxsize=None)` on a frozen state tuple
- Bottom-up base cases: `a_map_score == 2 → return 1.0`, `b_map_score == 2 → return 0.0`
- Map terminal: `a_round == 13 → recurse with (map_idx+1, a_map_score+1, ...)` etc.
- Within-map recurrence: `value(state) = round_p × value(state_after_a_wins) + (1-round_p) × value(state_after_b_wins)`
- After warm-up, dump the cache to `models/dp_table.pkl` (~10MB) and mmap on load

**Test:** for any `state`, `0 ≤ value ≤ 1`. For symmetric inputs (equal round_p across all states), value equals the closed-form `p²(3-2p)` from `fair_value.py`.

### 1.2 Bradley-Terry round blend (`src/pricing/blend.py`)

```python
def round_p(a_rate: float, b_rate_opposite_side: float) -> float:
    a = max(1e-6, min(1 - 1e-6, a_rate))
    b = max(1e-6, min(1 - 1e-6, b_rate_opposite_side))
    return (a * (1 - b)) / (a * (1 - b) + (1 - a) * b)
```

Replaces `(a_rate + (1 - b_rate)) / 2` from the audited engine. Unit-test against three cases: `(0.5, 0.5) → 0.5`, `(0.7, 0.3) → 0.84` (compounding edge), `(1.0, 0.0) → 1.0`.

### 1.3 Pistol + anti-eco round modeling (`src/pricing/round_types.py`)

The single largest accuracy gain. Rounds 1, 13 are pistols; 2, 3, 14, 15 are conditional on the prior outcome.

**Approach: state-augmented DP.** Extend `BO3State` with a small "economy memory" — the most recent round outcome. The DP transitions know whether they're at round 1 (pistol), round 2 conditional on round-1 result, etc.

Probability inputs:

| Round | Source |
|---|---|
| 1, 13 (pistol) | `match_round_data` filtered to round_num ∈ {1,13}, per team/side/map |
| 2, 3 (post-pistol-loss = anti-eco) | `match_round_data` round_num ∈ {2,3} conditional on losing pistol — `GUN_WIN_RATE = 0.822` is the population mean |
| 4–12, 16–24 (gunrounds) | half-win-rate baseline |

Empirical conversion rate from a pistol win is ~75% on round 2 and ~60% on round 3 — measured from `match_round_data`. Compute these per team/map where sample allows; shrink to overall otherwise.

### 1.4 OT decision

Recommendation: explicit hard-stop at total = 24, with a documented OT-as-coinflip leaf. The DP returns `0.5 × value(after_a_OT_win) + 0.5 × value(after_b_OT_win)` at the 12-12 boundary, and OT play continues with constant `p = 0.5` per round until someone is up by 2. This matches CLAUDE.md's "no OT modeling" intent without silently corrupting probabilities.

### 1.5 Round-conclusion lookup (`src/pricing/round_conclusion.py`)

**Blocked by Phase 2 data.** Skeleton can be built now.

Hierarchical fallback chain:

```
(numerical_diff, bomb, side, econ_bucket, map)
  → (numerical_diff, bomb, side, map)
  → (numerical_diff, bomb, side)
  → (numerical_diff, bomb)
  → side baseline
```

Each cell estimate uses Bayesian shrinkage to its parent. Persist as nested dict, JSON-serialized. Sub-microsecond lookup.

### 1.6 Canonical `live_theo` (`src/pricing/live_theo.py`)

The single entry point. Replaces the three-function sprawl in the audited engine:

```python
@dataclass
class TheoOutput:
    theo_series: float
    theo_map: dict[int, float]
    vega: float
    confidence: float  # 0..1, data_w-based

def live_theo(state: MatchState) -> TheoOutput
```

`theo_map[i]` is computed by marginalizing the DP over future map outcomes — same DP, no second model.

**Vega:** start with the simple definition: `vega = round_p × (theo_after_a_win - theo)² + (1-round_p) × (theo_after_b_win - theo)²` — the variance of the next theo update conditional on the next round outcome. Refine in Phase 5.

---

## Phase 2 — Round-event data (~3 days API path, ~2 weeks OCR path)

**This is the decision gate that determines Phase 1.5's timeline.**

### 2.1 API scoping (Day 1)

Write `scripts/probe_round_events.py`:

```python
# For 5 known matches, hit each candidate endpoint.
# Look for: per-round timestamps, kill events with player names,
#           bomb plant/defuse, mid-round numerical state.

candidates = [
    "https://api.rib.gg/v2/matches/{id}",
    "https://api.rib.gg/v2/matches/{id}/rounds",
    "https://api.rib.gg/v2/matches/{id}/events",
    "https://api.bo3.gg/api/v1/matches/{slug}",
]
```

**Decision tree:**

- Round outcomes + sides per round: this is the minimum. Both APIs likely have it (already used in `match_round_data`).
- Kill feed timestamps + numerical state per second: nice to have. Unlikely from public APIs.
- Bomb plant timestamp: needed for the round-conclusion model. Maybe.

### 2.2 If APIs are sufficient (Path A, ~3 days)

- Pull 500+ historical matches' round events into a new `round_events` table
- Schema: `(match_id, map_num, round_num, ts_round_start, ts_first_kill, ts_bomb_plant, ts_round_end, mid_round_states[])`
- Calibrate `round_conclusion.py` cells from this dataset
- Done.

### 2.3 If APIs are insufficient (Path B, ~2 weeks)

OCR-driven VOD labeling:

- Use `vision_parser.py` as the OCR backbone
- Sample 100 matches' VODs at 1Hz, label numerical state + bomb status + round outcome
- Hand-verify a 10% sample for OCR accuracy
- Train cells from the labeled set

### 2.4 If neither path is feasible right now (Path C)

**Defer.** Ship Phases 1, 3, 4 with `round_conclusion` returning a fixed mid-round prior `p = 0.5`. Live theo only re-prices between rounds, not mid-round. Phase 4 still works; you just lose mid-round edge.

---

## Phase 3 — Live ingestion layer (~7–10 days)

### 3.1 State engine (`src/state/match_state.py`, ~1 day)

Single class, in-memory:

```python
@dataclass
class MatchState:
    match_id: str
    map_idx: int
    a_map_score: int; b_map_score: int
    a_round: int; b_round: int
    side_orient: str  # 'a_atk' | 'a_def'
    econ_a: int; econ_b: int  # estimated
    ults_a: int; ults_b: int
    players_alive_a: int; players_alive_b: int
    bomb_planted: bool
    time_left_s: float
    seq_id: int
    last_updated_ts: float
```

Mutators bump `seq_id`. Append every mutation to a JSONL event log on disk (cheap, useful for replay/debug).

### 3.2 Scoreboard polling (`src/ingestion/scoreboard.py`, ~2 days)

Reuse the `vlr_scraper.py` / `rib_scraper.py` patterns from the existing repo. Poll every 5s. This is the slowest source but the most authoritative.

### 3.3 OCR pipeline (`src/ingestion/ocr.py`, ~3–5 days)

Port `vision_parser.py` into `src/ingestion/ocr.py`. Targets:

- **Score banner** (every 250ms): emits score-change events
- **Kill feed** (every 100ms): emits kill events, infers numerical state
- **Bomb icon** (every 500ms): emits plant/defuse events
- **Round-end banner** (every 100ms during round-end window): emits "predicted round outcome" before scoreboard updates

**Latency target:** 50ms decode + 50ms inference per frame. Run on GPU if available; otherwise tesseract + small CNNs are fine.

### 3.4 Text listeners (`src/ingestion/text.py`, ~1 day)

Twitter API v2 streaming filter on match-related hashtags / accounts. Cheap, surprisingly fast (~1–3s after events). Treat as a soft signal — never sole-source confirmation.

### 3.5 Cross-source arbiter (`src/ingestion/arbiter.py`, ~2 days)

Implements PRD §5.1 tiered confirmation. Three queues:

```
sources → [pending_updates] → arbiter → [confirmed_updates] → state engine
                                     → [quarantined_updates] (logged, not committed)
```

Per-event-type rules in a config dict. Score updates require ≥2 sources within 2s window. Mid-round events commit on 1 CV-based source if kill-feed cross-confirms within same frame.

### 3.6 Latency instrumentation (~1 day)

Every event carries timestamps at each stage: `t_observed`, `t_ingested`, `t_arbited`, `t_state_committed`, `t_theo_computed`, `t_quote_sent`. Log to a metrics file. Build a dashboard later.

---

## Phase 4 — Quoting layer (~5–7 days)

### 4.1 Extract `KalshiOrderManager` (`src/quoting/order_manager.py`, ~1 day)

From `reference/market_maker.py`, salvage:

- `Quote` dataclass
- `_place_quote`, `_cancel_quote`, `cancel_all_orders`
- Error-streak retry logic
- `_is_near_close` close-time guard
- Dry-run mode

Strip out the rest.

### 4.2 Mode selector (`src/quoting/mode.py`, ~0.5 day)

Pure function over `MatchState`:

```python
def trading_mode(state: MatchState, vega: float) -> Literal["MM", "DIRECTIONAL"]:
    # Event triggers
    if state.players_alive_a != state.players_alive_b: return "DIRECTIONAL"
    if state.bomb_planted: return "DIRECTIONAL"
    if is_map_point(state): return "DIRECTIONAL"
    if is_decider_late(state): return "DIRECTIONAL"
    # Vega override
    if vega > VEGA_DIRECTIONAL_THRESHOLD: return "DIRECTIONAL"
    return "MM"
```

### 4.3 MM quoter (`src/quoting/mm.py`, ~1 day)

Quote `theo ± vega-scaled spread`. Salvage `_compute_quotes` from the audited `market_maker.py` but replace the fixed `quote_width` with `max(MIN_HALF_SPREAD, k × sqrt(vega))`. Add staleness penalty.

### 4.4 Directional taker (`src/quoting/directional.py`, ~1 day)

When `|theo_cents - market_mid| > TAKE_THRESHOLD`, lift the offer (or hit the bid). Sized by half-Kelly (§4.6).

### 4.5 Kelly sizer (`src/sizing/kelly.py`, ~0.5 day)

```python
def kelly_size(theo: float, market_yes_ask: float, bankroll: float) -> int:
    p, q = theo, 1 - theo
    b = (1 - market_yes_ask) / market_yes_ask  # decimal odds for YES
    f_full = (b * p - q) / b
    f = max(0.0, KELLY_MULTIPLIER * f_full)
    f = min(f, PER_MARKET_CAP_FRAC)
    return int(f * bankroll / market_yes_ask)
```

### 4.6 Kill switches (`src/quoting/kill_switches.py`, ~1 day)

Each switch is a pure predicate over `(state, theo, market, recent_briers)`. The quoter calls all four every cycle; if ANY trips, all resting quotes are cancelled and an alert fires. **Always-on by default; no config flag to disable individual switches.**

### 4.7 Order lifecycle reconciliation (~1 day)

Every poll cycle: fetch open orders from Kalshi, reconcile against in-memory `_active_quotes`. If Kalshi has an order we don't track, cancel it. If we think we have a quote but Kalshi doesn't, drop our reference. Defends against state-drift bugs.

---

## Phase 5 — Validation (~2–4 weeks, calendar-bound by live events)

### 5.1 Unit + property tests (~ongoing through Phases 1–4)

Aim for 80% line coverage on `src/pricing/`. Property tests via `hypothesis`:

- DP value is in [0, 1] for any state
- DP value is monotonic in `round_p`
- `theo_series` equals sum over outcomes derivable from `theo_map[]`
- Bradley-Terry blend is symmetric: `round_p(a, b)` and `1 - round_p(b, a)` agree

### 5.2 Backtest (~3–5 days)

Replay the past season's matches against `live_theo` running on synthetic state derived from `match_round_data`. Compute Brier score per state-bucket (early-game, mid-game, post-plant, etc.). No fills — this validates the model alone.

For order-fill backtest: Kalshi doesn't expose historical order-book replay easily. Two options: (a) skip and rely on paper trading, (b) build a synthetic counterparty that always quotes at vig-removed market price. Option (a) is faster and more honest.

### 5.3 Paper trading (~1+ event of live matches, ~2 weeks)

Run the full bot with `dry_run=True` against live Kalshi matches. Track:

- Hypothetical fills (would-have-filled orders)
- Hypothetical P&L
- Realized Brier score per round prediction
- Latency p50, p99 from event → quote

**Promotion gate:** ≥ 1 full event with Brier < 0.22 and zero kill-switch trips for ingestion bugs (model-trip kill switches are OK; bug-trip kill switches are not).

### 5.4 Calibration loop (~ongoing)

After 100 matches of paper-trade data:

- Re-fit `SHRINK_PRIOR` to minimize live Brier
- Re-tune `VEGA_DIRECTIONAL_THRESHOLD` against observed mode-flip optimality
- Re-tune kill-switch thresholds against observed false-positive rate

---

## Phase 6 — Deployment (~3–5 days)

### 6.1 Containerization

Single `Dockerfile`. Multi-stage: builder installs deps, runtime image is slim Python. Image size target < 500MB.

### 6.2 Cloud VM

**Recommendation:** Hetzner CCX13 (~$20/mo, 2 vCPU, 8GB RAM, US-East). Adequate. AWS t3.small is the alternative if you prefer the AWS ecosystem.

### 6.3 Deploy pipeline

- Local: `uv run` against `dry_run=True`, real Kalshi credentials in `.env`
- CI (GitHub Actions): build Docker image, push to GHCR, run tests
- Cloud: `docker pull && docker run` with secrets mounted from a separate key file (never in image, never in env in `docker inspect`)

### 6.4 Secrets

- Kalshi private key file mounted as a Docker secret, **not** in the image, **not** in env vars
- `.env` for non-sensitive config
- Backup the private key in a password manager

### 6.5 Logging + alerting

- Structured JSON logs to stdout, captured by Docker
- Ship to a log aggregator (Loki / Grafana Cloud free tier)
- PagerDuty / SMS alerts on kill-switch trips and process crashes

### 6.6 Monitoring

A Grafana dashboard with: theo vs market over time, fill rate, current inventory, kill-switch trip log, latency p50/p99, daily P&L.

---

## Phase 7 — Operational maturity (ongoing)

### 7.1 Daily metrics report

A cron job that emails a daily summary: matches traded, fill count, P&L, Brier score, kill-switch trips, model version.

### 7.2 Weekly drift detection

Compare last 7 days' Brier distribution to the baseline calibration set. If KL divergence exceeds threshold, alert — model may be drifting (new patch, meta shift, roster changes).

### 7.3 Incident runbook

A short doc covering: how to halt the bot remotely, how to manually cancel all orders via Kalshi UI, how to roll back to a previous Docker image, how to interpret each kill-switch alert.

### 7.4 Operational risk limits

Beyond per-market cap, a daily loss limit: if cumulative realized + unrealized P&L < −X% of bankroll, halt the bot until manual review. Distinct from kill switches (which are per-market signals); this is a portfolio-level circuit breaker.

---

## Critical path summary

| Sequence | Duration (parallelizable) | Blocks |
|---|---|---|
| Phase 0 | 2 days | Everything |
| Phase 1.1–1.4, 1.6 (pricing core, no data deps) | 5 days | Phase 4 |
| Phase 2 (data scoping + pull) | 3 days API / 2 weeks OCR | Phase 1.5 |
| Phase 1.5 (round-conclusion model) | 2 days after Phase 2 | Mid-round live theo |
| Phase 3 (ingestion layer) | 7–10 days | Phase 4, Phase 5 |
| Phase 4 (quoting) | 5–7 days | Phase 5 |
| Phase 5.1–5.2 (tests + backtest) | 3–5 days | Phase 5.3 |
| Phase 5.3 (paper trading) | 2 weeks calendar | Phase 6 |
| Phase 6 (deployment) | 3–5 days | Phase 7 |

**Realistic total:** 4–6 weeks of build time, then 2 weeks paper trading before going live. ~7–8 weeks calendar time end-to-end if Phase 2 hits the API path; ~10–12 weeks if OCR labeling is needed.

**Earliest revenue:** between-round live MM after ~3 weeks if you ship Phases 1, 3, 4 with `round_conclusion` deferred.
