# REQUIREMENTS — Valorant Live Pricing Model

**Source of truth:** `prd.md` (root) for design intent; `roadmap.md` (root) for build sequencing and acceptance criteria. This file enumerates the 37 requirements derived from those docs by `gsd-doc-synthesizer`, grouped by the phase they belong to.

Each REQ has a stable slug-ID, a single source-of-truth section, scope, description, and (where source provides) acceptance criteria. Phase mappings come from `roadmap.md` and `.planning/intel/requirements.md`.

For full intel form (raw extraction notes), see `.planning/intel/requirements.md`. For locked decisions referenced below (DEC-*), see `.planning/PROJECT.md` `<decisions>` blocks.

---

## Phase 0 — Foundation

No standalone REQs. Phase 0 deliverables (project structure, tooling, config skeleton) are codified as constraints in `.planning/intel/constraints.md`:

- `CON-package-layout` — `src/{pricing,state,ingestion,quoting,sizing,config}/` plus siblings
- `CON-tooling-versions` — Python 3.11, uv, pytest+hypothesis, ruff
- `CON-mypy-strict-pricing` — `mypy --strict` on `src/pricing/`
- `CON-no-magic-numbers` — every threshold in `config/constants.py`
- `CON-domain-constants-baseline` — initial values for SHRINK_PRIOR, KELLY_MULTIPLIER, KILL_SWITCH_*, etc.
- `CON-dry-run-default` — `dry_run=True` default; `--live` CLI flag required
- `CON-live-state-no-sqlite` — in-memory live state, JSONL event log; SQLite for cache only

Phase 0 is "complete" when the constraints above are satisfiable: directory tree exists, `pyproject.toml` is in place, `config/constants.py` declares the baseline values, and `mypy --strict src/pricing/` runs (even on empty modules).

---

## Phase 1 — Core pricing engine

### REQ-bo3-dp-engine
- **Source:** roadmap.md §1.1
- **Scope:** pricing core
- **Description:** Generalized BO3 DP `series_value(state, round_p_fn) → float` over `BO3State = (map_idx, a_map_score, b_map_score, a_round, b_round, side_orient, map_pool)`. Memoized recursion (`@functools.lru_cache(maxsize=None)` on a frozen state tuple); cache dumped to `models/dp_table.pkl` (~10MB), mmap on load.
- **Acceptance:**
  - `0 ≤ value ≤ 1` for any reachable state (property test)
  - For symmetric inputs (equal `round_p` across all states), value equals the closed-form `p²(3−2p)` from `fair_value.py`

### REQ-bradley-terry-blend
- **Source:** roadmap.md §1.2; prd.md §12.2 #4
- **Scope:** pricing core
- **Description:** `round_p(a_rate, b_rate_opposite_side) → (a*(1-b)) / (a*(1-b) + (1-a)*b)` with `a, b` clipped to `[1e-6, 1-1e-6]`. Replaces `(a_rate + (1 - b_rate)) / 2` from the audited engine (DEC-003).
- **Acceptance:**
  - `(0.5, 0.5) → 0.5`
  - `(0.7, 0.3) → 0.84` (compounding edge)
  - `(1.0, 0.0) → 1.0`
  - Symmetry: `round_p(a, b) == 1 − round_p(b, a)`

### REQ-pistol-anti-eco-modeling
- **Source:** roadmap.md §1.3; prd.md §12.2 #5
- **Scope:** round-type modeling
- **Description:** State-augmented DP carrying economy-memory of most recent round outcome. Rounds 1, 2, 3, 13, 14, 15 use separate probability inputs (DEC-011):
  - 1, 13 (pistol): `match_round_data` filtered to `round_num ∈ {1, 13}`, per team/side/map
  - 2, 3 (post-pistol-loss anti-eco): conditional on losing pistol; `GUN_WIN_RATE = 0.822` is population mean
  - 4–12, 16–24 (gunrounds): half-win-rate baseline
- **Acceptance:** empirical conversion rate ~75% on round 2 and ~60% on round 3 from a pistol win — measured per team/map where sample allows; shrunk to overall otherwise.

### REQ-ot-handling
- **Source:** roadmap.md §1.4; prd.md §12.2 #3
- **Scope:** DP termination
- **Description:** Hard-stop at `total = 24` (DEC-009). At 12-12 boundary leaf: `0.5 × value(after_a_OT_win) + 0.5 × value(after_b_OT_win)`; OT play continues with constant `p = 0.5` until someone is up by 2.
- **Acceptance:** DP must not silently iterate past `total = 24` with `p = 0.5`; explicit OT-coinflip leaf documented in code.

### REQ-round-conclusion-lookup
- **Source:** roadmap.md §1.5; prd.md §5.3
- **Scope:** mid-round pricing
- **Description:** Hierarchical fallback chain (DEC-007): `(numerical_diff, bomb, side, econ_bucket, map) → (numerical_diff, bomb, side, map) → (numerical_diff, bomb, side) → (numerical_diff, bomb) → side baseline`. Bayesian shrinkage cell-to-parent. Persist as nested dict, JSON-serialized, sub-microsecond lookup.
- **Note:** Skeleton built in Phase 1; calibration of cell values blocked by Phase 2 data.

### REQ-canonical-live-theo
- **Source:** roadmap.md §1.6; prd.md §6, §12.3
- **Scope:** pricing API
- **Description:** Single function `live_theo(state: MatchState) → TheoOutput` returning `theo_series`, `theo_map`, `vega`, `confidence` (DEC-010). Do NOT recreate the `series_theo` / `series_theo_no_sides` / `series_theo_from_map_probs` triplet.

### REQ-theo-series-output
- **Source:** prd.md §2
- **Scope:** pricing output contract
- **Description:** Given full current match state, return `theo_series ∈ [0, 1]` representing P(team A wins the series | current state).
- **Acceptance:** `live_theo(state).theo_series` is a float in `[0, 1]` for all reachable states; equals DP value at root state.

### REQ-theo-map-output
- **Source:** prd.md §2
- **Scope:** pricing output contract
- **Description:** Given match state, return `theo_map[i] ∈ [0, 1]` for each map i in the pool — P(team A wins map i | current state). Computed by marginalizing the DP over future map outcomes (DEC-002).
- **Acceptance:** `live_theo(state).theo_map` keys cover every map in the pool; each value in `[0, 1]`; values consistent with `theo_series` (sum-of-outcomes derivable per roadmap §5.1 property test).

### REQ-confidence-output
- **Source:** prd.md §2
- **Scope:** pricing output contract
- **Description:** Return `confidence ∈ [0, 1]` representing data-weight in the prediction.

### REQ-vega-output
- **Source:** prd.md §2; roadmap.md §1.6
- **Scope:** pricing output contract
- **Description:** Return `vega` representing variance of the next theo update; drives quote width and DIRECTIONAL-mode override threshold.
- **Acceptance:** initial implementation per DEC-018: `vega = round_p × (theo_after_a_win − theo)² + (1−round_p) × (theo_after_b_win − theo)²`.

### REQ-end-to-end-latency
- **Source:** prd.md §2
- **Scope:** latency budget
- **Description:** End-to-end latency from observable in-game event → updated theo must be < 500 ms (median). Quote-cancel must be < 100 ms from state change → all stale orders pulled.
- **Acceptance:** latency p50/p99 measured per REQ-latency-instrumentation; reported per Phase 5 paper-trading run.

---

## Phase 2 — Round-event data

### REQ-round-event-data-pipeline
- **Source:** roadmap.md §2; prd.md §7 step 4
- **Scope:** data acquisition
- **Description:** Probe rib.gg / bo3.gg APIs via `scripts/probe_round_events.py` (DEC-017 decision gate).
  - **Path A (~3 days):** if APIs are sufficient, pull 500+ historical matches into a `round_events` table with schema `(match_id, map_num, round_num, ts_round_start, ts_first_kill, ts_bomb_plant, ts_round_end, mid_round_states[])` and calibrate `round_conclusion.py` cells.
  - **Path B (~2 weeks):** if APIs are insufficient, OCR-label 100 VODs at 1Hz with hand-verification of 10% sample.
  - **Path C (defer):** if neither feasible, ship Phases 1, 3, 4 with `round_conclusion` returning fixed `p = 0.5`.

---

## Phase 3 — Live ingestion layer

### REQ-match-state-engine
- **Source:** roadmap.md §3.1; prd.md §5.2
- **Scope:** state engine
- **Description:** Single `@dataclass MatchState` with fields:
  `match_id, map_idx, a_map_score, b_map_score, a_round, b_round, side_orient, econ_a, econ_b, ults_a, ults_b, players_alive_a, players_alive_b, bomb_planted, time_left_s, seq_id, last_updated_ts`.
  Versioned via monotonic `seq_id`. Mutators bump `seq_id`. Append every mutation to JSONL event log on disk.
- **Acceptance:** quoting layer only acts on monotonically-increasing seq_ids.

### REQ-scoreboard-polling
- **Source:** roadmap.md §3.2
- **Scope:** ingestion source
- **Description:** Poll rib.gg / bo3.gg / vlr.gg live endpoints every 5s. Reuse `vlr_scraper.py` / `rib_scraper.py` patterns from existing repo. Authoritative but slowest source.

### REQ-ocr-pipeline
- **Source:** roadmap.md §3.3; prd.md §5.1
- **Scope:** ingestion source
- **Description:** Port `vision_parser.py` into `src/ingestion/ocr.py`. Targets and cadences:
  - Score banner: every 250 ms → score-change events
  - Kill feed: every 100 ms → kill events, infer numerical state
  - Bomb icon: every 500 ms → plant/defuse events
  - Round-end banner: every 100 ms during round-end window → "predicted round outcome"
- **Acceptance:** 50 ms decode + 50 ms inference per frame. GPU if available; else tesseract + small CNNs.

### REQ-text-listener
- **Source:** roadmap.md §3.4
- **Scope:** ingestion source
- **Description:** Twitter API v2 streaming filter on match-related hashtags / accounts. Soft signal only — never sole-source confirmation.

### REQ-cross-source-arbiter
- **Source:** roadmap.md §3.5; prd.md §5.1
- **Scope:** ingestion arbitration
- **Description:** Three-queue pipeline: `sources → pending_updates → arbiter → confirmed_updates → state engine`; quarantined updates logged but not committed. Per-event-type rules per DEC-006:
  - score change: ≥ 2 independent sources within 2s window
  - bomb plant / kill / numerical flip: 1 CV-based source if kill-feed cross-confirms within same frame
  - round-end banner: soft commit, hard-confirmed by next score update
  - pre-match lineup, sides: API single-source

### REQ-latency-instrumentation
- **Source:** roadmap.md §3.6
- **Scope:** observability
- **Description:** Every event carries timestamps at each stage: `t_observed, t_ingested, t_arbited, t_state_committed, t_theo_computed, t_quote_sent`. Logged to a metrics file.

---

## Phase 4 — Quoting layer

### REQ-kalshi-order-manager
- **Source:** roadmap.md §4.1
- **Scope:** order plumbing
- **Description:** Extract from `reference/market_maker.py` (per DEC-013): `Quote` dataclass, `_place_quote`, `_cancel_quote`, `cancel_all_orders`, error-streak retry, `_is_near_close` close-time guard, dry-run mode.

### REQ-mode-selector
- **Source:** roadmap.md §4.2; prd.md §2.1
- **Scope:** trading mode
- **Description:** A pure function `trading_mode(state, vega) → Literal["MM", "DIRECTIONAL"]` evaluating event triggers (numerical imbalance, bomb planted, map-point, decider) before vega override (DEC-001).
- **Acceptance:** rules evaluated in PRD §2.1 order; reset to MM at round end + 5v5 + no flags.

### REQ-mm-quoter
- **Source:** roadmap.md §4.3; prd.md §5.4
- **Scope:** market-making
- **Description:** Quote `theo ± vega-scaled spread`. Replace fixed `quote_width` with `max(MIN_HALF_SPREAD, k × sqrt(vega))`. Add staleness penalty: `time_since_last_state_update > 2s` → widen aggressively or pull. Skew quotes when adverse-selection risk is high.

### REQ-directional-taker
- **Source:** roadmap.md §4.4; prd.md §2.1
- **Scope:** directional trading
- **Description:** When `|theo_cents − market_mid| > TAKE_THRESHOLD`, lift the offer (or hit the bid). Sized by half-Kelly per REQ-kelly-sizer.

### REQ-kelly-sizer
- **Source:** roadmap.md §4.5; prd.md §2.3
- **Scope:** position sizing
- **Description:** `kelly_size(theo: float, market_yes_ask: float, bankroll: float) → int contracts`. Internal: `b = (1 − ask) / ask`, `f_full = (b*p − q) / b`, `f = max(0, KELLY_MULTIPLIER × f_full)`, `f = min(f, PER_MARKET_CAP_FRAC)`, returns `int(f × bankroll / market_yes_ask)`. Implements DEC-004.

### REQ-kill-switches
- **Source:** roadmap.md §4.6; prd.md §5.4
- **Scope:** risk controls
- **Description:** Four pure predicates over `(state, theo, market, recent_briers)`. Each call cycle, all four evaluated; if ANY trips, all resting quotes cancelled and alert fires. Always-on; no per-switch disable flag (DEC-005). Triggers:
  - `KILL_SWITCH_*` API errors / network disconnect
  - Ingestion staleness > `KILL_SWITCH_STALENESS_S` (5.0s)
  - `|theo − market| > KILL_SWITCH_DEVIATION_C` (20¢)
  - Rolling Brier > `KILL_SWITCH_BRIER_BOUND` (0.30) over last `KILL_SWITCH_BRIER_WINDOW` (50) round predictions

### REQ-order-lifecycle-reconciliation
- **Source:** roadmap.md §4.7
- **Scope:** order-state consistency
- **Description:** Every poll cycle: fetch open orders from Kalshi, reconcile against in-memory `_active_quotes`. Cancel orders Kalshi has that we don't track; drop our reference for quotes Kalshi doesn't have.

---

## Phase 5 — Validation

### REQ-unit-and-property-tests
- **Source:** roadmap.md §5.1
- **Scope:** testing
- **Description:** 80% line coverage on `src/pricing/`. `hypothesis` property tests:
  - DP value in `[0, 1]` for any state
  - DP value monotonic in `round_p`
  - `theo_series` equals sum over outcomes derivable from `theo_map[]`
  - Bradley-Terry blend is symmetric: `round_p(a, b)` and `1 − round_p(b, a)` agree

### REQ-backtest
- **Source:** roadmap.md §5.2
- **Scope:** validation
- **Description:** Replay past season's matches against `live_theo` running on synthetic state from `match_round_data`. Compute Brier per state-bucket (early-game, mid-game, post-plant, etc.). No fills — model-only validation. Order-fill backtest skipped in favor of paper trading (DEC-020).

### REQ-paper-trading
- **Source:** roadmap.md §5.3
- **Scope:** live-readiness validation
- **Description:** Run full bot with `dry_run=True` against live Kalshi matches. Track hypothetical fills, hypothetical P&L, realized Brier per round prediction, latency p50/p99 from event → quote.
- **Acceptance:** Promotion gate per DEC-020 — ≥ 1 full event with Brier < 0.22 and zero kill-switch trips for ingestion bugs (model-trip kill switches are OK; bug-trip kill switches are not).

### REQ-calibration-loop
- **Source:** roadmap.md §5.4
- **Scope:** ongoing tuning
- **Description:** After 100 matches of paper-trade data: re-fit `SHRINK_PRIOR` to minimize live Brier; re-tune `VEGA_DIRECTIONAL_THRESHOLD` against observed mode-flip optimality; re-tune kill-switch thresholds against observed false-positive rate.

---

## Phase 6 — Deployment

### REQ-containerization
- **Source:** roadmap.md §6.1
- **Scope:** deployment artifact
- **Description:** Single multi-stage `Dockerfile` (builder + slim runtime). Image size target < 500MB.

### REQ-cloud-vm
- **Source:** roadmap.md §6.2
- **Scope:** production host
- **Description:** Hetzner CCX13 (~$20/mo, 2 vCPU, 8GB RAM, US-East) recommended; AWS t3.small alternative.

### REQ-deploy-pipeline
- **Source:** roadmap.md §6.3
- **Scope:** CI/CD
- **Description:** Local `uv run` against `dry_run=True` with real Kalshi creds in `.env`. CI (GitHub Actions): build Docker image, push to GHCR, run tests. Cloud: `docker pull && docker run` with secrets mounted from a separate key file (never in image, never in env in `docker inspect`).

### REQ-secrets-handling
- **Source:** roadmap.md §6.4
- **Scope:** credentials
- **Description:** Kalshi private key file mounted as Docker secret — NOT in image, NOT in env vars. `.env` for non-sensitive config. Backup private key in a password manager.

### REQ-logging-and-alerting
- **Source:** roadmap.md §6.5
- **Scope:** observability
- **Description:** Structured JSON logs to stdout, captured by Docker. Ship to log aggregator (Loki / Grafana Cloud free tier). PagerDuty / SMS alerts on kill-switch trips and process crashes.

### REQ-monitoring-dashboard
- **Source:** roadmap.md §6.6
- **Scope:** observability
- **Description:** Grafana dashboard: theo vs market over time, fill rate, current inventory, kill-switch trip log, latency p50/p99, daily P&L.

---

## Phase 7 — Operational maturity

### REQ-daily-metrics-report
- **Source:** roadmap.md §7.1
- **Scope:** operational
- **Description:** Cron job emails daily summary: matches traded, fill count, P&L, Brier score, kill-switch trips, model version.

### REQ-weekly-drift-detection
- **Source:** roadmap.md §7.2
- **Scope:** operational
- **Description:** Compare last 7 days' Brier distribution to baseline calibration set. If KL divergence exceeds threshold, alert (potential patch, meta shift, roster change drift).

### REQ-incident-runbook
- **Source:** roadmap.md §7.3
- **Scope:** operational
- **Description:** Short doc covering: how to halt bot remotely, how to manually cancel all orders via Kalshi UI, how to roll back to previous Docker image, how to interpret each kill-switch alert.

### REQ-portfolio-loss-limit
- **Source:** roadmap.md §7.4
- **Scope:** risk controls
- **Description:** Daily loss limit halts bot when cumulative realized + unrealized P&L < −X% of bankroll until manual review. Distinct from per-market kill switches (DEC-021).

---

## Traceability

| REQ-ID | Phase | Source section |
|---|---|---|
| REQ-bo3-dp-engine | 1 | roadmap §1.1 |
| REQ-bradley-terry-blend | 1 | roadmap §1.2 / prd §12.2 #4 |
| REQ-pistol-anti-eco-modeling | 1 | roadmap §1.3 / prd §12.2 #5 |
| REQ-ot-handling | 1 | roadmap §1.4 / prd §12.2 #3 |
| REQ-round-conclusion-lookup | 1 (skeleton), 2 (calibration) | roadmap §1.5 / prd §5.3 |
| REQ-canonical-live-theo | 1 | roadmap §1.6 / prd §6 |
| REQ-theo-series-output | 1 | prd §2 |
| REQ-theo-map-output | 1 | prd §2 |
| REQ-confidence-output | 1 | prd §2 |
| REQ-vega-output | 1 | prd §2 / roadmap §1.6 |
| REQ-end-to-end-latency | 1 (target), 5 (measure) | prd §2 |
| REQ-round-event-data-pipeline | 2 | roadmap §2 / prd §7 |
| REQ-match-state-engine | 3 | roadmap §3.1 / prd §5.2 |
| REQ-scoreboard-polling | 3 | roadmap §3.2 |
| REQ-ocr-pipeline | 3 | roadmap §3.3 / prd §5.1 |
| REQ-text-listener | 3 | roadmap §3.4 |
| REQ-cross-source-arbiter | 3 | roadmap §3.5 / prd §5.1 |
| REQ-latency-instrumentation | 3 | roadmap §3.6 |
| REQ-kalshi-order-manager | 4 | roadmap §4.1 |
| REQ-mode-selector | 4 | roadmap §4.2 / prd §2.1 |
| REQ-mm-quoter | 4 | roadmap §4.3 / prd §5.4 |
| REQ-directional-taker | 4 | roadmap §4.4 / prd §2.1 |
| REQ-kelly-sizer | 4 | roadmap §4.5 / prd §2.3 |
| REQ-kill-switches | 4 | roadmap §4.6 / prd §5.4 |
| REQ-order-lifecycle-reconciliation | 4 | roadmap §4.7 |
| REQ-unit-and-property-tests | 5 (and ongoing) | roadmap §5.1 |
| REQ-backtest | 5 | roadmap §5.2 |
| REQ-paper-trading | 5 | roadmap §5.3 |
| REQ-calibration-loop | 5 (and ongoing) | roadmap §5.4 |
| REQ-containerization | 6 | roadmap §6.1 |
| REQ-cloud-vm | 6 | roadmap §6.2 |
| REQ-deploy-pipeline | 6 | roadmap §6.3 |
| REQ-secrets-handling | 6 | roadmap §6.4 |
| REQ-logging-and-alerting | 6 | roadmap §6.5 |
| REQ-monitoring-dashboard | 6 | roadmap §6.6 |
| REQ-daily-metrics-report | 7 | roadmap §7.1 |
| REQ-weekly-drift-detection | 7 | roadmap §7.2 |
| REQ-incident-runbook | 7 | roadmap §7.3 |
| REQ-portfolio-loss-limit | 7 | roadmap §7.4 |

**Coverage:** 37/37 requirements mapped across Phases 1–7. Phase 0 has no REQs (bootstrap-only; constraints in `intel/constraints.md` cover its scope).
