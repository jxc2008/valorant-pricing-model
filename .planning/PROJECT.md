# PROJECT — Valorant Live Pricing Model

**Slug:** `valorant-pricing-model`
**Owner:** jxc2008@nyu.edu
**Status:** Draft (v2 architecture pivot — 2026-05-02)
**Created:** 2026-04-27

---

## Mission

Live pricing engine for Valorant BO3 series + per-map Kalshi markets. **Three-way mode + IDLE: opportunistic directional taking + between-round MM (paper-trade-evaluated peer) + post-plant quoting.** Re-prices the series at any moment during a live match, fast enough to either capture edge through directional takes or — at minimum — avoid being adversely selected by counterparties consuming the same data feeds with lower latency.

The existing `theo_engine.py` (in `thunderedge/worktrees/market-maker/backend/`) prices BO3 series winners pre-match using a Markov DP over team/map/side half-win-rates. Once the match starts, the only signal that updates is the scoreboard. This project closes that gap — but **only for between-round and post-plant states.** Mid-round-not-planted is explicitly out of scope; kill-feed CV, mid-round economy inference, and ult tracking are cut.

## Scope (v1)

The four-layer architecture from `prd.md` §5:

```
[Ingestion] → [State Engine] → [Theo Engine] → [Quoting / Orders]
```

In scope for v1 (v2 pivot applied):

- BO3 series winner + per-map winner pricing (single canonical DP, marginalize for per-map)
- **Three-way mode + IDLE** (`MM_BETWEEN_ROUND` / `DIRECTIONAL_TAKE` / `POST_PLANT_QUOTE` / `IDLE`); MM and directional are first-class peers, paper trade decides
- **Portfolio-aware Kelly sizing**: half-Kelly per-market cap PLUS per-series aggregate cap to bound correlated exposure across moneyline / map / handicap markets
- Four always-on kill switches (API errors, ingestion staleness, theo-vs-market deviation, rolling Brier)
- **Simplified tiered ingestion confirmation** (rib.gg poller + tesseract OCR on three HUD targets only + Twitter soft-confirm + arbiter); kill-feed CV / economy / ults explicitly out
- **Two-path round-conclusion**: between-round (side baseline) + post-plant lookup keyed on `(att, def, time_bucket, side, map)`; no general mid-round path
- Local Windows dev / paper-trade environment + cloud VM production deploy
- Operational maturity layer: daily metrics, weekly drift detection, incident runbook, portfolio loss limit, **full covariance-aware portfolio Kelly (Phase 7)**

## Non-goals (explicit)

From `prd.md` §3, §11:

- Beating tier-1 caster-API bots on absolute speed
- OT outcome prediction — DP hard-stops at total=24 with documented OT-as-coinflip leaf, not silent `p=0.5` past round 24
- Player-level prop pricing (kill-line track is a separate project)
- Modeling tilt, day-of player form, coach side-switch reads, crowd
- BO5 series modeling
- Pick/ban model (handled by pre-match `pickban_prediction`)
- Player kill-line markets
- **(v2 cuts)** General mid-round live pricing without bomb plant — bot returns degraded-confidence between-round theo and quoting maps to IDLE
- **(v2 cuts)** Kill-feed CV, mid-round economy inference, ult-count tracking
- **(v2 cuts)** OCR-driven VOD labeling (Phase 2 Path B) — never executed; rib.gg API path was sufficient

See `prd.md` §3, §11 for full non-goals list and `context.md / Out of scope` for synthesis-level reconciliation of the OT framing.

## Tech stack

- **Runtime:** Python 3.11 (local dev on Windows / production on Hetzner CCX13 cloud VM, US-East) — DEC-008
- **Toolchain:** `uv` for venv (faster than pip), `pyproject.toml`, `pytest` + `pytest-cov` + `hypothesis` for property tests, `ruff` for lint+format, `mypy --strict` enforced on `src/pricing/` — DEC-014
- **Persistence:** SQLite for dataset cache; live state in-memory only with JSONL event log replay — DEC-015
- **Layout:** `src/{pricing,state,ingestion,quoting,sizing,config}/` plus `tests/`, `scripts/`, `data/`, `models/`, `reference/` — DEC-019
- **Deploy artifact:** single multi-stage Dockerfile (builder + slim runtime), image size target < 500MB
- **Production host:** Hetzner CCX13 (~$20/mo, 2 vCPU, 8GB RAM, US-East); AWS t3.small as alternative

## Success metrics

Developer-facing gates and ongoing measurements (per `prd.md` §2, §8 and `roadmap.md` §5.3, §5.4 — v2):

- **Latency:** p50 < 500 ms (in-game event → updated theo); **bomb-detect → quote-pull p50 < 200 ms** (defensive, latency-critical); quote-cancel p99 < 100 ms
- **Relative Brier promotion gate:** `Brier(model) < Brier(market_mid) − 0.02` over a 50-round window during paper trading (model and market Brier recorded side-by-side every prediction). If model ≥ market, do NOT deploy.
- **Fill-count gate (MM strategy):** if hypothetical MM fills < `MIN_FILLS_PER_MATCH` (initial: 3) averaged over a paper-trade event, MM is cut from production. Only DIRECTIONAL_TAKE (and POST_PLANT_QUOTE if active) promotes to live.
- **Zero kill-switch trips for ingestion bugs** in paper trade (model-trip OK; bug-trip not).
- **Adverse-selection rate as MM** (only meaningful if MM survives the gate): % of fills that move against us within 5 s.
- **Quote uptime during live matches:** % of seconds with active quotes (mode ≠ IDLE).

## Status

| Phase | Status |
|---|---|
| 0 — Foundation | Complete |
| 1 — Pricing engine | Complete (2026-04-29) |
| 2 — Round-event data | Complete (2026-05-01 — Path A; 1000 matches / 42586 rounds calibrated) |
| 3 — Live ingestion (RESCOPED v2) | Pending — plans need teardown + replan under new architecture |
| 4 — Quoting (RESCOPED v2) | Pending |
| 5 — Validation (relative Brier + fill-count gates) | Pending |
| 6 — Deployment | Pending |
| 7 — Operational maturity (incl. covariance Kelly) | Pending |

Current phase: **3 — Live ingestion** (rescoped under v2 pivot 2026-05-02; existing 11 plans on commit `6677e5d` need teardown). See `.planning/STATE.md` for live state.

_Last updated: 2026-05-02 (v2 pivot)_

## Source-of-truth docs

The hand-written design docs at the repo root remain authoritative. The GSD planning artifacts under `.planning/` are derived from them and reference them — they do not replace them.

| File | Role |
|---|---|
| `prd.md` (root) | Full design doc, 14 sections. Locked decisions in §9. **Authoritative for design intent.** |
| `roadmap.md` (root) | 8-phase build plan with implementation guidance. **Authoritative for build sequencing.** |
| `CLAUDE.md` (root) | Critical rules + domain constants + run commands. **Authoritative for project conventions.** |
| `.planning/REQUIREMENTS.md` | 37 REQ-IDs derived from prd.md / roadmap.md, grouped by phase |
| `.planning/ROADMAP.md` | 8-phase index referencing roadmap.md sections |
| `.planning/STATE.md` | Live execution state |
| `.planning/intel/` | Synthesizer outputs (decisions, requirements, constraints, context) |
| `.planning/codebase/` | Output of `/gsd-map-codebase` — supplementary context, not produced here |
| `.planning/INGEST-CONFLICTS.md` | Three-bucket conflict report from doc synthesis |
| `reference/` (root) | Read-only salvaged code from audited engine |

---

## Locked decisions

The 22 decisions below are operationally locked. PRD §9 explicitly enumerates 9 as resolved; SPEC corroborates 17 of them with implementation specifics. Treat all 22 as authoritative for cross-phase context lookup. Full text of each in `.planning/intel/decisions.md`.

<decisions>
- id: DEC-001
  title: Three-way mode + IDLE (v2 — replaces hybrid event-trigger framing)
  source: prd.md §2.1, §9 (v2 pivot 2026-05-02)
  corroborating: roadmap.md §4.2 (v2)
  scope: trading mode selection
  statement: |
    Mode selector is a pure function over (state, theo, market, vega_between, vega_post_plant, kill_switch_active)
    returning one of MM_BETWEEN_ROUND / DIRECTIONAL_TAKE / POST_PLANT_QUOTE / IDLE.

    Selection logic (in order):
      1. kill_switch_active → IDLE
      2. state.bomb_planted → POST_PLANT_QUOTE
      3. state.is_mid_round and not state.bomb_planted → IDLE  (no general mid-round path)
      4. abs(theo - market.mid) > TAKE_THRESHOLD → DIRECTIONAL_TAKE
      5. market.spread > MM_MIN_EDGE → MM_BETWEEN_ROUND
      6. otherwise → IDLE

    MM and DIRECTIONAL are first-class peers — paper trade decides which (or both) survives via the fill-count
    gate (DEC-020). VEGA_DIRECTIONAL_THRESHOLD is REMOVED — DIRECTIONAL_TAKE triggers on |theo - market_mid|,
    not on vega magnitude.

- id: DEC-002
  title: Single DP for BO3 series + per-map (single canonical model)
  source: prd.md §2.2, §5.3
  corroborating: roadmap.md §1.6
  scope: pricing model architecture
  statement: |
    BO3 series and per-map theos derive from one DP. P(series) is the DP value at root state;
    P(map_i) is computed by marginalizing the DP over future map outcomes. Mathematically arb-free
    by construction; quoting cannot internally cross.

- id: DEC-003
  title: Bradley-Terry round-win-prob blend
  source: prd.md §12.2 #4
  corroborating: roadmap.md §1.2
  scope: round probability composition
  statement: |
    Replace arithmetic mean `(a + (1-b))/2` with `p = a*(1-b) / (a*(1-b) + (1-a)*b)`.
    Arithmetic mean under-weights compounding edges.

- id: DEC-004
  title: Half-Kelly sizing with per-market cap
  source: prd.md §2.3, §9
  corroborating: roadmap.md §4.5
  scope: position sizing
  statement: |
    `f = 0.5 × Kelly_full`, capped at `PER_MARKET_CAP_FRAC` of bankroll. Never full Kelly.
    For YES buys: `Kelly_fraction = (theo − market_yes_ask) / (1 − market_yes_ask)`; symmetric for NO.

- id: DEC-005
  title: Four kill switches, all-on, no per-switch disable flag
  source: prd.md §5.4, §9
  corroborating: roadmap.md §4.6
  scope: risk controls
  statement: |
    Always-on triggers, each pulls all resting quotes:
    (a) Kalshi API errors / network disconnect,
    (b) ingestion staleness > 5s,
    (c) `|theo − market| > 20¢`,
    (d) rolling Brier > 0.30 over last 50 round predictions.
    Constants prefixed `KILL_SWITCH_*` per roadmap.md §0.4 (user-resolved 2026-04-27).

- id: DEC-006
  title: Tiered ingestion confirmation — collapsed for v2 (no kill-feed)
  source: prd.md §5.1 (v2 pivot 2026-05-02)
  corroborating: roadmap.md §3.5 (v2)
  scope: ingestion arbitration
  statement: |
    v2 confirmation rules (collapsed — kill_events / numerical_flips deques are REMOVED):

      Score change       → ≥ 2 sources within 2s window (rib.gg + OCR + Twitter as soft-confirm)
      Bomb plant/defuse  → 1 OCR source — soft commit; hard-confirmed by next round-end or score
      Round-end banner   → 1 OCR source — soft commit; hard-confirmed by next score update
      Pre-match lineup   → API single-source

    Kill-feed cross-confirmation requirements from v1 are gone because kill events / numerical flips
    are no longer ingested. The arbiter now has 3 deques (score_changes, bomb_events, round_end_events)
    instead of 5.

- id: DEC-007
  title: Two-path round-conclusion (v2 — between-round + post-plant only)
  source: prd.md §5.3 (v2 pivot 2026-05-02)
  corroborating: roadmap.md §3.6 (v2)
  scope: round-win probability
  statement: |
    Two clean code paths in `live_theo`:

      (a) Between-round path: round_p = side_baseline(side, map, round_idx) — fully observable from
          scoreboard; no lookup needed. Uses pistol/anti-eco modifiers from Phase 1 for rounds 1/2/3/13/14/15.

      (b) Post-plant path: round_p = post_plant_lookup(att, def, time_bucket, side, map). Hierarchical
          fallback: (att,def,time_bucket,side,map) → (att,def,side,map) → (att,def,side) → (att,def) →
          side_baseline. Bayesian shrinkage cell-to-parent. Inherits SHRINK_PRIOR=15, SIGNAL_SCALE=0.10.

    Mid-round-not-planted: live_theo returns the between-round theo with degraded confidence; mode
    selector maps to IDLE. NO general mid-round path.

    The lookup is calibrated against the existing Phase 2 dataset filtered to bomb_planted=True
    (~25k samples). v1 keys (numerical_diff, bomb, side, econ_bucket, map) are REPLACED.

- id: DEC-008
  title: Hybrid local dev / cloud production deployment
  source: prd.md §5.5, §9
  corroborating: roadmap.md §6.2
  scope: deployment topology
  statement: |
    Local Windows for dev/backtest/paper-trade. Cloud VM in US-East (Hetzner CCX13 ~$20/mo recommended;
    AWS t3.small alternative) for live trading. Docker image + SSH deploy. Promotion gate: backtest Brier
    below threshold + ≥ 1 full event of paper trading meeting target metrics.

- id: DEC-009
  title: OT explicit hard-stop at total=24 with documented coinflip leaf
  source: prd.md §12.2 #3
  corroborating: roadmap.md §1.4
  scope: DP termination policy
  statement: |
    DP must NOT silently model OT as `p=0.5` past round 24 (audit bug in `_markov_map_win`'s `range(26)` loop).
    Hard-stop at `total = 24` with documented OT-as-coinflip leaf:
    `0.5 × value(after_a_OT_win) + 0.5 × value(after_b_OT_win)` at the 12-12 boundary;
    OT continues with constant `p = 0.5` until win-by-2.
    Reconciles with prd.md §3 "OT non-goal" — the model documents the coinflip leaf rather than predicting OT.

- id: DEC-010
  title: Single canonical pricing entry point — `live_theo(state)`
  source: prd.md §6, §12.2 #2, §12.3
  corroborating: roadmap.md §1.6
  scope: pricing API surface
  statement: |
    One function `live_theo(state) → TheoOutput(theo_series, theo_map, vega, confidence)`.
    Do NOT recreate the `series_theo` / `series_theo_no_sides` / `series_theo_from_map_probs` triplet
    from the audited engine — inconsistent `signal_strength` application across those three was a bug.

- id: DEC-011
  title: Pistol + anti-eco rounds modeled explicitly
  source: prd.md §12.2 #5
  corroborating: roadmap.md §1.3
  scope: round-type modeling
  statement: |
    Rounds 1, 2, 3, 13, 14, 15 use separate probability inputs derived from `match_round_data` and
    `GUN_WIN_RATE = 0.822`. Constant `p1` for rounds 1–12 and `p2` for 13–24 is wrong — it ignores
    pistol cascades into anti-eco rounds.

- id: DEC-012
  title: Conviction clips at [0.01, 0.99]
  source: prd.md §12.2 #7
  scope: probability bounds
  statement: |
    Replace audited engine's `[0.05, 0.95]` and `[0.03, 0.97]` clips with `[0.01, 0.99]`.
    Document any tighter clip explicitly.

- id: DEC-013
  title: Salvage map — keep / partial / skip
  source: prd.md §12.1
  scope: code reuse from audited engine
  statement: |
    Salvage as-is: `odds_utils.py`, `fair_value.py`, `half_win_rates.json`.
    Partial: `theo_engine.py` (DP skeleton only; rewrite the rest per §12.2/§12.3);
    `market_maker.py` (extract Kalshi plumbing into `KalshiOrderManager`).
    Skip: `market_implied.py`, `map_bidder.py`, `run_market_maker.py`, `run_quote_bot.py`, `run_map_bidder.py`.

- id: DEC-014
  title: Tooling — Python 3.11, uv, pytest+hypothesis, ruff, mypy --strict on src/pricing/
  source: roadmap.md §0.2
  scope: developer toolchain
  statement: |
    Python 3.11 with `uv` for venv, `pyproject.toml`. `pytest` + `pytest-cov` + `hypothesis` for
    property-based tests. `ruff` for lint+format (one tool, fast). `mypy --strict` enforced on `src/pricing/`.

- id: DEC-015
  title: Data store — SQLite for cache, in-memory only for live state
  source: roadmap.md §0.3
  scope: persistence layer
  statement: |
    Existing repo's SQLite is reused for the dataset cache. Live state is in-memory only,
    persisted to disk only as JSONL event logs for replay/debug. Do NOT put live state in SQLite.

- id: DEC-016
  title: Configuration centralization in config/constants.py
  source: roadmap.md §0.4
  scope: magic-number policy
  statement: |
    Every magic number from PRD lives in `config/constants.py`. Threshold-tuning is a Phase 5 activity;
    ship initial values, never hardcode in business logic.

- id: DEC-017
  title: Phase-2 API decision gate (Path A / Path B / Path C)
  source: prd.md §7 step 4, §9; roadmap.md §2
  scope: round-event data acquisition
  statement: |
    Probe rib.gg / bo3.gg APIs for per-round events first (Path A, ~3 days). If insufficient, escalate
    to OCR-driven VOD labeling (Path B, ~2 weeks). If neither feasible, defer round-conclusion model and
    ship Phases 1, 3, 4 with `round_conclusion` returning fixed `p=0.5` (Path C — between-round live MM only).

- id: DEC-018
  title: Vega — two contexts (v2 update)
  source: roadmap.md §1.6 + prd.md §5.4 (v2 pivot 2026-05-02)
  scope: vega computation
  statement: |
    TWO vega definitions, used in different modes:

      vega_between_round = round_p × (theo_after_a_win − theo)² + (1−round_p) × (theo_after_b_win − theo)²
        — variance over next round outcome. Used to size MM_BETWEEN_ROUND quote width. Phase 1 ships this.

      vega_post_plant: variance over post-plant outcomes {kill, defuse, time-out}. TBD formula —
        pick + calibrate in Phase 4 against observed post-plant theo updates.

    The single VEGA_DIRECTIONAL_THRESHOLD constant from v1 is REMOVED — DIRECTIONAL_TAKE no longer
    triggers on vega magnitude (triggers on |theo − market_mid|).

- id: DEC-019
  title: Project layout — src/{pricing,state,ingestion,quoting,sizing,config}/
  source: roadmap.md §0.1
  scope: package structure
  statement: |
    Standard `src/` package layout. `tests/`, `scripts/`, `data/`, `models/`, `reference/` siblings of `src/`.

- id: DEC-020
  title: Paper-trade promotion gate (v2 — relative Brier + fill-count)
  source: roadmap.md §5.3, §5.4 + prd.md §8 (v2 pivot 2026-05-02)
  scope: live-trading readiness
  statement: |
    Promotion gate (all four required) after ≥ 1 full event of paper trading:

      1. Relative Brier: Brier(model) < Brier(market_mid) − RELATIVE_BRIER_EDGE_MIN (0.02) over a
         50-round window. Both recorded side-by-side every prediction. Absolute Brier 0.22 from v1
         is REPLACED.

      2. Fill-count gate (MM strategy): if hypothetical MM fills < MIN_FILLS_PER_MATCH (initial: 3)
         averaged over the event, MM is cut from production. Only DIRECTIONAL_TAKE (and POST_PLANT_QUOTE
         if active) promotes to live. This is what makes "MM and DIRECTIONAL run in parallel"
         architecturally honest.

      3. Latency: p50 event → state-commit < 500ms; bomb-detect → quote-pull p50 < 200ms;
         quote-cancel p99 < 100ms.

      4. Zero kill-switch trips for ingestion bugs (model-trip OK, bug-trip not).

    Backtest validates the model alone; order-fill backtest is skipped in favor of paper trading
    (Kalshi historical order book unavailable).

- id: DEC-021
  title: Daily portfolio loss limit (distinct from per-market kill switches)
  source: roadmap.md §7.4
  scope: portfolio-level circuit breaker
  statement: |
    Beyond per-market cap, halt the bot when cumulative realized + unrealized P&L < −X% of bankroll
    until manual review. Distinct from kill switches (which are per-market signals).

- id: DEC-022
  title: Dry-run by default; live trading requires explicit --live flag
  source: prd.md §5.5; CLAUDE.md critical rule #13
  scope: safety default
  statement: |
    Bot stays in `dry_run=True` until promotion gate is met. Live trading requires explicit CLI flag at
    the entry point. CLAUDE.md project instructions encode this PRD intent.

- id: DEC-023
  title: Portfolio Kelly with per-series aggregate cap (v2)
  source: prd.md §2.3 + roadmap.md §4.6 (v2 pivot 2026-05-02)
  scope: position sizing — correlation handling
  statement: |
    v1 sizing (half-Kelly + per-market cap) does not bound aggregate exposure across correlated markets
    on the same series. Quoting moneyline + map-1 + map-2 + map handicaps + round handicaps simultaneously
    can put 20%+ of bankroll on one outcome while staying within the per-market 5% cap.

    v2 adds a per-series aggregate cap layered over the per-market cap:

      kelly_size(theo, ask, bankroll, series_id, current_series_exposure):
        f = max(0, KELLY_MULTIPLIER * f_full)
        f = min(f, PER_MARKET_CAP_FRAC)                    # per-market floor: 0.05
        headroom = max(0, SERIES_AGGREGATE_CAP_FRAC - current_series_exposure[series_id])
        f = min(f, headroom)                                # per-series floor: 0.10
        return 0 if f == 0 else int(f * bankroll / ask)

    SERIES_AGGREGATE_CAP_FRAC = 0.10 initial; recalibrate after first paper-trade event from observed
    inter-market correlation.

    This is the v1 floor — full covariance-aware portfolio Kelly with per-series correlation matrix is
    Phase 7 maturity work (roadmap §7.5), not Phase 4. The simple aggregate cap is "safe-enough for
    paper trade", not "correct".

- id: DEC-024
  title: OCR scope cut to three HUD targets (v2)
  source: prd.md §5.1 + roadmap.md §3.3 (v2 pivot 2026-05-02)
  scope: ingestion CV scope
  statement: |
    OCR/CV scope is THREE broadcast HUD elements only:

      Score banner       — 250ms cadence — score-change events
      Bomb-plant icon    — 500ms cadence — plant/defuse → POST_PLANT_QUOTE + defensive quote-pull
      Round-end banner   — 100ms during round-end window — soft round-outcome commit (~500ms before scoreboard)

    Tesseract handles all three (small text, low cadence, high contrast). CPU-only.

    EXPLICITLY OUT OF SCOPE (v2 cuts):
      - Kill-feed CV
      - Mid-round economy inference
      - Ult-count tracking
      - ONNX runtime, ONNX kill-feed CNN, CTC decoder
      - GPU dependency
      - vision_parser.py salvage from sibling thunderedge/ repo

    When bomb_planted=True, a separate post-plant attackers/defenders-alive HUD widget is parsed at
    250ms cadence (much simpler than full kill-feed parsing — single integer per side, high contrast).

</decisions>

---

## Open TBDs (deferred from PRD §9, intentional)

v2-pivoted list (2026-05-02):

1. **Bankroll size and per-market exposure cap.** Operational; depends on capital allocation decision. `PER_MARKET_CAP_FRAC = 0.05` is a placeholder.
2. **Aggregate cap calibration.** `SERIES_AGGREGATE_CAP_FRAC = 0.10` is a defensive initial guess (DEC-023). After first paper-trade event with real correlation data, recompute from observed inter-market beta.
3. **Mode-selector thresholds.** `TAKE_THRESHOLD`, `MM_MIN_EDGE`, `POST_PLANT_TAKE_THRESHOLD`, `MIN_HALF_SPREAD` — all initial values TBD; calibrate from observed market structure during paper trade.
4. **Kill-switch numerical values** (5s, 20¢, 0.30, 50-round Brier window) and `MIN_FILLS_PER_MATCH` — initial guesses, re-tune after 20+ live matches (Phase 5 calibration).
5. **Post-plant vega formula.** DEC-018 ships between-round vega; post-plant variant TBD — pick a formula in Phase 4, calibrate against observed post-plant theo updates in Phase 5.
6. **Full covariance-aware portfolio Kelly.** Phase 7 maturity work (roadmap §7.5). Per-series correlation matrix derived from paper-trade Brier history.
7. **Backtest fidelity.** DEC-020 skips order-fill backtest in favor of paper trading. Reconsider if Kalshi exposes historical order-book data.
8. **Phase 2 dataset post-plant completeness.** Phase 3 must verify the captured `mid_round_states[]` schema includes `attackers_alive`, `defenders_alive`, `time_remaining` at bomb-plant moments. If missing, partial Phase 2 ETL re-run scoped to post-plant (DEC-007 implementation requirement).

REMOVED from v1 TBD list: `VEGA_DIRECTIONAL_THRESHOLD = 0.04` (constant deleted — see DEC-018 v2 update).

See `prd.md` §9 and `.planning/intel/context.md / Open questions still TBD` for full framing.

## Cross-references

- `CLAUDE.md` (project instructions) — terse, surfaces critical rules + domain constants. Do not duplicate decisions there; the source of truth for design choices is `prd.md` and this file.
- `.planning/codebase/` — produced by `/gsd-map-codebase`, supplementary context for understanding current code structure (read-only here).
- `.planning/INGEST-CONFLICTS.md` — full three-bucket report from doc synthesis (4 INFO entries, 0 BLOCKERs, 0 WARNINGs as of 2026-04-27).
