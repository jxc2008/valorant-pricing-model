# REQUIREMENTS — Valorant Live Pricing Model

**Source of truth:** `prd.md` (root) for design intent; `roadmap.md` (root) for build sequencing and acceptance criteria. This file enumerates the requirements derived from those docs, grouped by the phase they belong to.

> **v2 architecture pivot (2026-05-02):** Phase 3/4/5 REQs restructured. Cut: kill-feed CV, mid-round economy, ult tracking, single-vega DIRECTIONAL trigger. Added: REQ-post-plant-quoter, REQ-portfolio-kelly-aggregate-cap. Modified: REQ-mode-selector (three-way + IDLE), REQ-mm-quoter (between-round only), REQ-directional-taker (first-class peer), REQ-kelly-sizer (portfolio-aware), REQ-ocr-pipeline (3 HUD targets only), REQ-cross-source-arbiter (3 deques), REQ-match-state-engine (fewer fields), REQ-round-conclusion-lookup (rekeyed post-plant only), REQ-paper-trading (relative Brier + fill-count gate).

Each REQ has a stable slug-ID, a single source-of-truth section, scope, description, and (where source provides) acceptance criteria.

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

### REQ-round-conclusion-lookup (REKEYED v2)
- **Source:** roadmap.md §3.6; prd.md §5.3 (v2 pivot)
- **Scope:** post-plant pricing (no general mid-round)
- **Description:** Hierarchical fallback chain (DEC-007 v2): `(att, def, time_bucket, side, map) → (att, def, side, map) → (att, def, side) → (att, def) → side baseline`. Bayesian shrinkage cell-to-parent. Persist as nested dict, JSON-serialized, sub-microsecond lookup. **Filtered to bomb_planted=True rounds only.** Between-round and mid-round-not-planted use `live_theo`'s side-baseline path; lookup is NOT consulted in those states.
- **Note:** Skeleton + v1 calibration data shipped via Phase 1/2. **Phase 3 rekeys to v2 schema** by filtering the existing 1000-match / 42586-round dataset to ~25k post-plant samples and recomputing cells. Phase 3 verifies the captured `mid_round_states[]` schema includes the required fields; partial Phase 2 ETL re-run scoped to post-plant if missing.

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

### REQ-vega-output (TWO CONTEXTS v2)
- **Source:** prd.md §2, §5.4; roadmap.md §1.6 (v2 pivot)
- **Scope:** pricing output contract
- **Description:** Return TWO vega values, used in different modes (DEC-018 v2):
  - `vega_between_round` = `round_p × (theo_after_a_win − theo)² + (1−round_p) × (theo_after_b_win − theo)²` — variance over next round outcome. Sizes MM_BETWEEN_ROUND quote width.
  - `vega_post_plant` = variance over post-plant outcomes {kill, defuse, time-out}. **TBD formula** — picked + calibrated in Phase 4 against observed post-plant theo updates.
- **Acceptance:** Phase 1 ships `vega_between_round`. `vega_post_plant` ships in Phase 4. The single `VEGA_DIRECTIONAL_THRESHOLD` constant from v1 is REMOVED — DIRECTIONAL_TAKE triggers on `|theo − market_mid|`, not on vega magnitude.

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

### REQ-match-state-engine (RESCOPED v2) — **Complete (2026-05-08, plan 03-01)**
- **Source:** roadmap.md §3.1; prd.md §5.2 (v2 pivot)
- **Scope:** state engine
- **Description:** Single `@dataclass(frozen=True, slots=True) MatchState` at `src/state/match_state.py` with fields:
  `match_id, map_idx, a_map_score, b_map_score, a_round, b_round, side_orient, bomb_planted, attackers_alive | None, defenders_alive | None, time_left_s | None, seq_id, last_updated_ts`.
  `attackers_alive` / `defenders_alive` populated only when `bomb_planted=True`. Versioned via monotonic `seq_id`. Mutators (`with_update(...)`) bump `seq_id` and append every mutation to a JSONL event log on disk.
- **Cut from v1 schema:** `econ_a/b` (not directly observable from broadcast), `ults_a/b` (cut from scope per DEC-024), `players_alive_a/b` (cut — replaced by post-plant-only `attackers_alive` / `defenders_alive` from a separate HUD widget).
- **Acceptance:** quoting layer only acts on monotonically-increasing seq_ids; `seq_id` strictly monotonic over 1000 random `with_update` calls; JSONL replay reproduces final state.
- **Implementation:** plan 03-01 — `src/state/match_state.py` (19-field frozen+slots dataclass + pure `with_update` + module-level `commit`/`quarantine` JSONL helpers per D-03 schema). Acceptance proven by `tests/ingestion/test_match_state.py::test_seq_id_strictly_monotonic` (hypothesis property test) and `tests/ingestion/test_match_state_jsonl.py::test_replay_determinism` (1000 commits → JSONL → in-order replay reconstructs state byte-for-byte).

### REQ-scoreboard-polling
- **Source:** roadmap.md §3.2
- **Scope:** ingestion source
- **Description:** Poll rib.gg / bo3.gg / vlr.gg live endpoints every 5s. Reuse `vlr_scraper.py` / `rib_scraper.py` patterns from existing repo. Authoritative but slowest source.

### REQ-ocr-pipeline (RESCOPED v2 — three HUD targets only)
- **Source:** roadmap.md §3.3; prd.md §5.1 (v2 pivot — DEC-024)
- **Scope:** ingestion source
- **Description:** `src/ingestion/ocr.py` with **three** broadcast HUD targets, tesseract-only, CPU-only:
  - **Score banner**: 250 ms cadence → score-change events
  - **Bomb-plant icon**: 500 ms cadence → plant/defuse events; drives POST_PLANT_QUOTE + defensive quote-pull
  - **Round-end banner**: 100 ms during round-end window → predicted round outcome (~500 ms before scoreboard updates)

  When `bomb_planted=True`, a separate post-plant attackers/defenders-alive HUD widget is parsed at 250 ms cadence (single integer per side, high contrast — much simpler than full kill-feed parsing).
- **Cut from v1 scope (per DEC-024):** kill-feed CV, ult-count tracking, mid-round economy inference, ONNX runtime, CTC decoder, GPU dependency, `vision_parser.py` salvage.
- **Acceptance:** decode + inference < 100 ms median per frame across the three primary targets; per-target cadence within ±10% jitter under sustained load.

### REQ-text-listener
- **Source:** roadmap.md §3.4
- **Scope:** ingestion source
- **Description:** Twitter API v2 streaming filter on match-related hashtags / accounts. Soft signal only — never sole-source confirmation.

### REQ-cross-source-arbiter (SIMPLIFIED v2 — 3 deques) — **Complete (2026-05-08, plan 03-03)**
- **Source:** roadmap.md §3.5; prd.md §5.1 (v2 pivot — DEC-006 v2)
- **Scope:** ingestion arbitration
- **Description:** Three-queue pipeline: `sources → pending_updates → arbiter → confirmed_updates → state engine`; quarantined updates logged but not committed. Per-event-type deques (3 — was 5 in v1; `kill_events` and `numerical_flips` removed):
  - **score_changes**: ≥ 2 independent sources within 2s window (rib.gg + OCR + Twitter as soft-confirm)
  - **bomb_events**: 1 OCR source — soft commit; hard-confirmed by next round-end or score
  - **round_end_events**: 1 OCR source — soft commit; hard-confirmed by next score update
  - pre-match lineup, sides: API single-source (no deque needed)

### REQ-latency-instrumentation — **Complete (2026-05-08, plan 03-03)**
- **Source:** roadmap.md §3.6
- **Scope:** observability
- **Description:** Every event carries timestamps at each stage: `t_observed, t_ingested, t_arbited, t_state_committed, t_theo_computed, t_quote_sent`. Logged to a metrics file.

---

## Phase 4 — Quoting layer

### REQ-kalshi-order-manager
- **Source:** roadmap.md §4.1
- **Scope:** order plumbing
- **Description:** Extract from `reference/market_maker.py` (per DEC-013): `Quote` dataclass, `_place_quote`, `_cancel_quote`, `cancel_all_orders`, error-streak retry, `_is_near_close` close-time guard, dry-run mode.

### REQ-mode-selector (RESTRUCTURED v2 — three-way + IDLE)
- **Source:** roadmap.md §4.2; prd.md §2.1 (v2 pivot — DEC-001 v2)
- **Scope:** trading mode
- **Description:** Pure function:
  ```
  trading_mode(state, theo, market, vega_between, vega_post_plant, kill_switch_active)
    → Literal["MM_BETWEEN_ROUND", "DIRECTIONAL_TAKE", "POST_PLANT_QUOTE", "IDLE"]
  ```
  Selection logic (in order):
  1. `kill_switch_active` → IDLE
  2. `state.bomb_planted` → POST_PLANT_QUOTE
  3. `state.is_mid_round and not state.bomb_planted` → IDLE (no general mid-round path)
  4. `abs(theo - market.mid) > TAKE_THRESHOLD` → DIRECTIONAL_TAKE
  5. `market.spread > MM_MIN_EDGE` → MM_BETWEEN_ROUND
  6. otherwise → IDLE
- **Acceptance:** rules evaluated in declared order; mode is a deterministic function of inputs (no hidden state); MM_BETWEEN_ROUND and DIRECTIONAL_TAKE are first-class peers (no "default" mode).

### REQ-mm-quoter (NARROWED v2 — between-round only)
- **Source:** roadmap.md §4.3; prd.md §5.4 (v2 pivot)
- **Scope:** market-making
- **Description:** Active only when `mode == MM_BETWEEN_ROUND`. Quote `theo ± vega-scaled spread` using `vega_between_round`. `spread = max(MIN_HALF_SPREAD, k × sqrt(vega_between)) + staleness_penalty`. **Spread floor must beat Kalshi commission + slippage** to avoid lossy quotes. `time_since_last_state_update > 2s` → widen or pull. Skew when adverse-selection risk is high. Hypothetical fills tracked on a SEPARATE LEDGER from DIRECTIONAL_TAKE during paper trade for fill-count gate evaluation (DEC-020 v2).

### REQ-directional-taker (FIRST-CLASS PEER v2)
- **Source:** roadmap.md §4.4; prd.md §2.1 (v2 pivot)
- **Scope:** directional trading — first-class strategy
- **Description:** Active when `mode == DIRECTIONAL_TAKE`. When `|theo_cents − market_mid| > TAKE_THRESHOLD`, lift the offer (or hit the bid). Sized by REQ-kelly-sizer (portfolio-aware v2). **Runs on its own hypothetical-fill ledger during paper trade**, parallel to MM. Promotion gate (DEC-020 v2) evaluates the two ledgers independently — DIRECTIONAL_TAKE can promote even if MM is cut for thin fills.

### REQ-post-plant-quoter (NEW v2)
- **Source:** roadmap.md §4.5; prd.md §2.1, §5.4 (v2 pivot)
- **Scope:** post-plant pricing + defensive quote-pull
- **Description:** Active when `mode == POST_PLANT_QUOTE`. Three actions on bomb-plant detection:
  1. **Defensive quote-pull** within 200 ms (latency-critical — cancel any resting between-round MM quotes).
  2. **Re-price** using `live_theo(state)` post-plant code path (post-plant lookup keyed on `(att, def, time_bucket, side, map)`).
  3. **Take or quote**: take if `|theo − market| > POST_PLANT_TAKE_THRESHOLD` (narrower than between-round take); otherwise quote at theo ± narrow spread (high-conviction state).
- **Acceptance:** bomb-detect → quote-pull p50 < 200 ms; re-price uses post-plant lookup, not between-round path.

### REQ-kelly-sizer (PORTFOLIO-AWARE v2)
- **Source:** roadmap.md §4.6; prd.md §2.3 (v2 pivot — DEC-023)
- **Scope:** position sizing — correlation handling
- **Description:** `kelly_size(theo, market_yes_ask, bankroll, series_id, current_series_exposure) → int contracts`.
  Internal:
  ```
  b = (1 − ask) / ask
  f_full = (b*p − q) / b
  f = max(0, KELLY_MULTIPLIER * f_full)
  f = min(f, PER_MARKET_CAP_FRAC)                          # per-market cap (0.05)
  headroom = max(0, SERIES_AGGREGATE_CAP_FRAC - current_series_exposure[series_id])
  f = min(f, headroom)                                      # per-series aggregate cap (0.10)
  return 0 if f == 0 else int(f * bankroll / ask)
  ```
  The aggregate cap bounds correlated exposure across moneyline + map handicaps + round handicaps on the same series. Returns 0 if aggregate cap already exceeded.
- **Acceptance:** sizing identical to v1 single-market case (when exposure is 0); aggregate cap kicks in when sum of fractional exposures across the series exceeds `SERIES_AGGREGATE_CAP_FRAC`.
- **Note:** This is the v1 floor. Full covariance-aware portfolio Kelly is REQ-portfolio-correlation-kelly (Phase 7).

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

### REQ-paper-trading (RECALIBRATED GATES v2)
- **Source:** roadmap.md §5.3, §5.4; prd.md §8 (v2 pivot — DEC-020 v2)
- **Scope:** live-readiness validation
- **Description:** Run full bot with `dry_run=True` against live Kalshi matches. Track:
  - Hypothetical fills on **two separate ledgers** (MM and DIRECTIONAL); POST_PLANT events tracked separately
  - Hypothetical P&L per ledger
  - Realized Brier per round prediction — **AND `Brier(market_mid)` recorded side-by-side**
  - Latency p50, p99 per pipeline stage; bomb-detect → quote-pull p50
- **Acceptance:** Promotion gate per DEC-020 v2 (all four required):
  1. **Relative Brier:** `Brier(model) < Brier(market_mid) − 0.02` over a 50-round window. If model ≥ market, do NOT deploy.
  2. **Fill-count gate (MM):** if hypothetical MM fills < `MIN_FILLS_PER_MATCH` (initial: 3) averaged over the event, MM is cut from production. Only DIRECTIONAL_TAKE (and POST_PLANT_QUOTE if active) promotes to live.
  3. **Latency:** p50 event → state-commit < 500 ms; bomb-detect → quote-pull p50 < 200 ms; quote-cancel p99 < 100 ms.
  4. **Zero kill-switch trips for ingestion bugs** (model-trip OK, bug-trip not).

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
- **Description:** Daily loss limit halts bot when cumulative realized + unrealized P&L < −X% of bankroll until manual review. Distinct from per-market kill switches (DEC-021) and from per-series aggregate cap (DEC-023 — that bounds exposure, this halts on realized loss).

### REQ-portfolio-correlation-kelly (NEW v2 — Phase 7 maturity)
- **Source:** roadmap.md §7.5; prd.md §2.3 (v2 pivot — DEC-023)
- **Scope:** portfolio-level Kelly sizing
- **Description:** Replace the simple per-series aggregate cap (REQ-kelly-sizer v2) with covariance-aware portfolio Kelly. Inputs: per-series correlation matrix derived from paper-trade + live Brier history across moneyline / map handicap / round handicap markets. Output: position sizing that accounts for inter-market correlation rather than just bounding aggregate fractional exposure.
- **Acceptance:** Phase 7 work, not Phase 4. Triggered when sufficient post-paper-trade correlation data exists. The simple aggregate cap remains the floor.

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
| REQ-mode-selector | 4 | roadmap §4.2 / prd §2.1 (v2) |
| REQ-mm-quoter | 4 | roadmap §4.3 / prd §5.4 (v2) |
| REQ-directional-taker | 4 | roadmap §4.4 / prd §2.1 (v2) |
| REQ-post-plant-quoter | 4 | roadmap §4.5 / prd §2.1 (NEW v2) |
| REQ-kelly-sizer | 4 | roadmap §4.6 / prd §2.3 (v2 portfolio-aware) |
| REQ-kill-switches | 4 | roadmap §4.7 / prd §5.4 |
| REQ-order-lifecycle-reconciliation | 4 | roadmap §4.8 |
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
| REQ-portfolio-correlation-kelly | 7 | roadmap §7.5 / prd §2.3 (NEW v2) |

**Coverage:** 39/39 requirements mapped across Phases 1–7 (was 37 in v1; +REQ-post-plant-quoter, +REQ-portfolio-correlation-kelly). Phase 0 has no REQs (bootstrap-only; constraints in `intel/constraints.md` cover its scope).
