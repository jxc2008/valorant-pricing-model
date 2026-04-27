# Requirements (Intel)

Derived from PRD §2 (Goal) and per-phase deliverables in roadmap.md. Each REQ has a stable slug-ID, a single source-of-truth doc, and acceptance criteria where the source provides them.

---

## REQ-theo-series-output
- source: prd.md §2
- scope: pricing output contract
- description: Given full current match state, return `theo_series ∈ [0, 1]` representing P(team A wins the series | current state).
- acceptance: `live_theo(state).theo_series` is a float in `[0, 1]` for all reachable states; equals DP value at root state.

## REQ-theo-map-output
- source: prd.md §2
- scope: pricing output contract
- description: Given match state, return `theo_map[i] ∈ [0, 1]` for each map i in the pool — P(team A wins map i | current state).
- acceptance: `live_theo(state).theo_map` keys cover every map in the pool; each value in `[0, 1]`; values consistent with `theo_series` (sum-of-outcomes derivable per roadmap §5.1 property test).

## REQ-confidence-output
- source: prd.md §2
- scope: pricing output contract
- description: Return `confidence ∈ [0, 1]` representing data-weight in the prediction.

## REQ-vega-output
- source: prd.md §2; roadmap.md §1.6
- scope: pricing output contract
- description: Return `vega` representing variance of the next theo update; drives quote width and DIRECTIONAL-mode override threshold.
- acceptance: initial implementation per roadmap §1.6: `vega = round_p × (theo_after_a_win − theo)² + (1−round_p) × (theo_after_b_win − theo)²`.

## REQ-end-to-end-latency
- source: prd.md §2
- scope: latency budget
- description: End-to-end latency from observable in-game event → updated theo must be < 500 ms (median). Quote-cancel must be < 100 ms from state change → all stale orders pulled.
- acceptance: latency p50/p99 measured per roadmap §3.6 instrumentation; reported per Phase 5 paper-trading run.

## REQ-mode-selector
- source: prd.md §2.1; roadmap.md §4.2
- scope: trading mode
- description: A pure function `trading_mode(state, vega) → {"MM", "DIRECTIONAL"}` evaluating event triggers (numerical imbalance, bomb planted, map-point, decider) before vega override.
- acceptance: rules evaluated in PRD §2.1 order; reset to MM at round end + 5v5 + no flags.

## REQ-bo3-dp-engine
- source: roadmap.md §1.1
- scope: pricing core
- description: Generalized BO3 DP `series_value(state, round_p_fn) → float` over `BO3State = (map_idx, a_map_score, b_map_score, a_round, b_round, side_orient, map_pool)`. Memoized recursion; cache dumped to `models/dp_table.pkl` (~10MB), mmap on load.
- acceptance: `0 ≤ value ≤ 1` for any state (property test); for symmetric inputs, value equals closed-form `p²(3−2p)` from `fair_value.py`.

## REQ-bradley-terry-blend
- source: roadmap.md §1.2
- scope: pricing core
- description: `round_p(a_rate, b_rate_opposite_side)` returns `(a*(1-b)) / (a*(1-b) + (1-a)*b)` with `a, b` clipped to `[1e-6, 1-1e-6]`.
- acceptance: `(0.5, 0.5) → 0.5`; `(0.7, 0.3) → 0.84` (compounding edge); `(1.0, 0.0) → 1.0`; symmetry: `round_p(a, b) == 1 − round_p(b, a)`.

## REQ-pistol-anti-eco-modeling
- source: prd.md §12.2 #5; roadmap.md §1.3
- scope: round-type modeling
- description: State-augmented DP carrying economy-memory of most recent round outcome. Rounds 1, 2, 3, 13, 14, 15 use separate probability inputs:
  - 1, 13 (pistol): `match_round_data` filtered to `round_num ∈ {1, 13}`, per team/side/map
  - 2, 3 (post-pistol-loss anti-eco): conditional on losing pistol; `GUN_WIN_RATE = 0.822` is population mean
  - 4–12, 16–24 (gunrounds): half-win-rate baseline
- acceptance: empirical conversion rate ~75% on round 2 and ~60% on round 3 from a pistol win — measured per team/map where sample allows; shrunk to overall otherwise.

## REQ-ot-handling
- source: prd.md §12.2 #3; roadmap.md §1.4
- scope: DP termination
- description: Hard-stop at `total = 24`. At 12-12 boundary leaf: `0.5 × value(after_a_OT_win) + 0.5 × value(after_b_OT_win)`; OT play continues with constant `p = 0.5` until someone is up by 2.
- acceptance: DP must not silently iterate past `total = 24` with `p = 0.5`; explicit OT-coinflip leaf documented in code.

## REQ-round-conclusion-lookup
- source: prd.md §5.3; roadmap.md §1.5
- scope: mid-round pricing
- description: Hierarchical fallback chain `(numerical_diff, bomb, side, econ_bucket, map) → (numerical_diff, bomb, side, map) → (numerical_diff, bomb, side) → (numerical_diff, bomb) → side baseline`. Bayesian shrinkage to parent. Persist as nested dict, JSON-serialized, sub-microsecond lookup.

## REQ-canonical-live-theo
- source: prd.md §6, §12.3; roadmap.md §1.6
- scope: pricing API
- description: Single function `live_theo(state: MatchState) → TheoOutput` returning `theo_series`, `theo_map`, `vega`, `confidence`. Do not recreate the `series_theo` / `series_theo_no_sides` / `series_theo_from_map_probs` triplet.

## REQ-round-event-data-pipeline
- source: prd.md §7 step 4; roadmap.md §2
- scope: data acquisition
- description: Probe rib.gg / bo3.gg APIs via `scripts/probe_round_events.py`. If sufficient (Path A), pull 500+ historical matches into a `round_events` table with schema `(match_id, map_num, round_num, ts_round_start, ts_first_kill, ts_bomb_plant, ts_round_end, mid_round_states[])` and calibrate `round_conclusion.py` cells. If insufficient (Path B), OCR-label 100 VODs at 1Hz with hand-verification of 10% sample. If infeasible (Path C), defer.

## REQ-match-state-engine
- source: prd.md §5.2; roadmap.md §3.1
- scope: state engine
- description: Single `@dataclass MatchState` with fields per PRD §5.2 + roadmap §3.1: `match_id, map_idx, a_map_score, b_map_score, a_round, b_round, side_orient, econ_a, econ_b, ults_a, ults_b, players_alive_a, players_alive_b, bomb_planted, time_left_s, seq_id, last_updated_ts`. Versioned via monotonic `seq_id`. Mutators bump seq_id. Append every mutation to JSONL event log on disk.
- acceptance: quoting layer only acts on monotonically-increasing seq_ids.

## REQ-scoreboard-polling
- source: roadmap.md §3.2
- scope: ingestion source
- description: Poll rib.gg / bo3.gg / vlr.gg live endpoints every 5s. Reuse `vlr_scraper.py` / `rib_scraper.py` patterns from existing repo. Authoritative but slowest source.

## REQ-ocr-pipeline
- source: prd.md §5.1; roadmap.md §3.3
- scope: ingestion source
- description: Port `vision_parser.py` into `src/ingestion/ocr.py`. Targets and cadences:
  - Score banner: every 250ms → score-change events
  - Kill feed: every 100ms → kill events, infer numerical state
  - Bomb icon: every 500ms → plant/defuse events
  - Round-end banner: every 100ms during round-end window → "predicted round outcome"
- acceptance: 50ms decode + 50ms inference per frame. GPU if available; else tesseract + small CNNs.

## REQ-text-listener
- source: roadmap.md §3.4
- scope: ingestion source
- description: Twitter API v2 streaming filter on match-related hashtags / accounts. Soft signal only — never sole-source confirmation.

## REQ-cross-source-arbiter
- source: prd.md §5.1; roadmap.md §3.5
- scope: ingestion arbitration
- description: Three-queue pipeline: `sources → pending_updates → arbiter → confirmed_updates → state engine`; quarantined updates logged but not committed. Per-event-type rules per DEC-006 / PRD §5.1.

## REQ-latency-instrumentation
- source: roadmap.md §3.6
- scope: observability
- description: Every event carries timestamps at each stage: `t_observed, t_ingested, t_arbited, t_state_committed, t_theo_computed, t_quote_sent`. Logged to a metrics file.

## REQ-kalshi-order-manager
- source: roadmap.md §4.1
- scope: order plumbing
- description: Extract from `reference/market_maker.py`: `Quote` dataclass, `_place_quote`, `_cancel_quote`, `cancel_all_orders`, error-streak retry, `_is_near_close` close-time guard, dry-run mode.

## REQ-mm-quoter
- source: prd.md §5.4; roadmap.md §4.3
- scope: market-making
- description: Quote `theo ± vega-scaled spread`. Replace fixed `quote_width` with `max(MIN_HALF_SPREAD, k × sqrt(vega))`. Add staleness penalty: `time_since_last_state_update > 2s` → widen aggressively or pull. Skew quotes when adverse-selection risk is high.

## REQ-directional-taker
- source: prd.md §2.1; roadmap.md §4.4
- scope: directional trading
- description: When `|theo_cents − market_mid| > TAKE_THRESHOLD`, lift the offer (or hit the bid). Sized by half-Kelly per REQ-kelly-sizer.

## REQ-kelly-sizer
- source: prd.md §2.3; roadmap.md §4.5
- scope: position sizing
- description: `kelly_size(theo, market_yes_ask, bankroll)` returns int contracts. `b = (1 − ask) / ask`, `f_full = (b*p − q) / b`, `f = max(0, KELLY_MULTIPLIER × f_full)`, `f = min(f, PER_MARKET_CAP_FRAC)`, return `int(f × bankroll / market_yes_ask)`.

## REQ-kill-switches
- source: prd.md §5.4; roadmap.md §4.6
- scope: risk controls
- description: Four pure predicates over `(state, theo, market, recent_briers)`. Each call cycle, all four evaluated; if ANY trips, all resting quotes cancelled and alert fires. Always-on; no per-switch disable flag. Triggers per DEC-005.

## REQ-order-lifecycle-reconciliation
- source: roadmap.md §4.7
- scope: order-state consistency
- description: Every poll cycle: fetch open orders from Kalshi, reconcile against in-memory `_active_quotes`. Cancel orders Kalshi has that we don't track; drop our reference for quotes Kalshi doesn't have.

## REQ-unit-and-property-tests
- source: roadmap.md §5.1
- scope: testing
- description: 80% line coverage on `src/pricing/`. `hypothesis` property tests:
  - DP value in `[0, 1]` for any state
  - DP value monotonic in `round_p`
  - `theo_series` equals sum over outcomes derivable from `theo_map[]`
  - Bradley-Terry blend is symmetric: `round_p(a, b)` and `1 − round_p(b, a)` agree

## REQ-backtest
- source: roadmap.md §5.2
- scope: validation
- description: Replay past season's matches against `live_theo` running on synthetic state from `match_round_data`. Compute Brier per state-bucket (early-game, mid-game, post-plant, etc.). No fills — model-only validation. Order-fill backtest skipped in favor of paper trading.

## REQ-paper-trading
- source: roadmap.md §5.3
- scope: live-readiness validation
- description: Run full bot with `dry_run=True` against live Kalshi matches. Track hypothetical fills, hypothetical P&L, realized Brier per round prediction, latency p50/p99 from event → quote. Promotion gate per DEC-020.

## REQ-calibration-loop
- source: roadmap.md §5.4
- scope: ongoing tuning
- description: After 100 matches of paper-trade data: re-fit `SHRINK_PRIOR` to minimize live Brier; re-tune `VEGA_DIRECTIONAL_THRESHOLD` against observed mode-flip optimality; re-tune kill-switch thresholds against observed false-positive rate.

## REQ-containerization
- source: roadmap.md §6.1
- scope: deployment artifact
- description: Single multi-stage `Dockerfile` (builder + slim runtime). Image size target < 500MB.

## REQ-cloud-vm
- source: roadmap.md §6.2
- scope: production host
- description: Hetzner CCX13 (~$20/mo, 2 vCPU, 8GB RAM, US-East) recommended; AWS t3.small alternative.

## REQ-deploy-pipeline
- source: roadmap.md §6.3
- scope: CI/CD
- description: Local `uv run` against `dry_run=True` with real Kalshi creds in `.env`. CI (GitHub Actions): build Docker image, push to GHCR, run tests. Cloud: `docker pull && docker run` with secrets mounted from a separate key file (never in image, never in env in `docker inspect`).

## REQ-secrets-handling
- source: roadmap.md §6.4
- scope: credentials
- description: Kalshi private key file mounted as Docker secret — NOT in image, NOT in env vars. `.env` for non-sensitive config. Backup private key in a password manager.

## REQ-logging-and-alerting
- source: roadmap.md §6.5
- scope: observability
- description: Structured JSON logs to stdout, captured by Docker. Ship to log aggregator (Loki / Grafana Cloud free tier). PagerDuty / SMS alerts on kill-switch trips and process crashes.

## REQ-monitoring-dashboard
- source: roadmap.md §6.6
- scope: observability
- description: Grafana dashboard: theo vs market over time, fill rate, current inventory, kill-switch trip log, latency p50/p99, daily P&L.

## REQ-daily-metrics-report
- source: roadmap.md §7.1
- scope: operational
- description: Cron job emails daily summary: matches traded, fill count, P&L, Brier score, kill-switch trips, model version.

## REQ-weekly-drift-detection
- source: roadmap.md §7.2
- scope: operational
- description: Compare last 7 days' Brier distribution to baseline calibration set. If KL divergence exceeds threshold, alert (potential patch, meta shift, roster change drift).

## REQ-incident-runbook
- source: roadmap.md §7.3
- scope: operational
- description: Short doc covering: how to halt bot remotely, how to manually cancel all orders via Kalshi UI, how to roll back to previous Docker image, how to interpret each kill-switch alert.

## REQ-portfolio-loss-limit
- source: roadmap.md §7.4
- scope: risk controls
- description: Daily loss limit halts bot when cumulative realized + unrealized P&L < −X% of bankroll until manual review. Distinct from per-market kill switches.
