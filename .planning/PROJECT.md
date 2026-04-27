# PROJECT — Valorant Live Pricing Model

**Slug:** `valorant-pricing-model`
**Owner:** jxc2008@nyu.edu
**Status:** Draft
**Created:** 2026-04-27

---

## Mission

Live pricing engine for Valorant BO3 series + per-map Kalshi markets. Hybrid market-maker / directional taker. Re-prices the series at any moment during a live match, fast enough to either capture edge or — at minimum — avoid being adversely selected by counterparties consuming the same data feeds with lower latency.

The existing `theo_engine.py` (in `thunderedge/worktrees/market-maker/backend/`) prices BO3 series winners pre-match using a Markov DP over team/map/side half-win-rates. Once the match starts, the only signal that updates is the scoreboard — every other piece of state (numerical advantage, bomb plant, economy, ult counts) is invisible to the pricer. This project closes that gap.

## Scope (v1)

The four-layer architecture from `prd.md` §5:

```
[Ingestion] → [State Engine] → [Theo Engine] → [Quoting / Orders]
```

In scope for v1:

- BO3 series winner + per-map winner pricing (single canonical DP, marginalize for per-map)
- Hybrid trading mode (MM default, event-trigger + vega override flips to DIRECTIONAL)
- Half-Kelly sizing with per-market cap
- Four always-on kill switches (API errors, ingestion staleness, theo-vs-market deviation, rolling Brier)
- Tiered ingestion confirmation (CV/OCR + scoreboard polling + text listeners + arbiter)
- Round-conclusion lookup (hierarchical fallback chain) — gated by Phase 2 API decision (DEC-017)
- Local Windows dev / paper-trade environment + cloud VM production deploy
- Operational maturity layer: daily metrics, weekly drift detection, incident runbook, portfolio loss limit

## Non-goals (explicit)

From `prd.md` §3, §11:

- Beating tier-1 caster-API bots on absolute speed
- OT outcome prediction — DP hard-stops at total=24 with documented OT-as-coinflip leaf, not silent `p=0.5` past round 24
- Player-level prop pricing (kill-line track is a separate project)
- Modeling tilt, day-of player form, coach side-switch reads, crowd
- BO5 series modeling
- Pick/ban model (handled by pre-match `pickban_prediction`)
- Player kill-line markets

See `prd.md` §3, §11 for full non-goals list and `context.md / Out of scope` for synthesis-level reconciliation of the OT framing.

## Tech stack

- **Runtime:** Python 3.11 (local dev on Windows / production on Hetzner CCX13 cloud VM, US-East) — DEC-008
- **Toolchain:** `uv` for venv (faster than pip), `pyproject.toml`, `pytest` + `pytest-cov` + `hypothesis` for property tests, `ruff` for lint+format, `mypy --strict` enforced on `src/pricing/` — DEC-014
- **Persistence:** SQLite for dataset cache; live state in-memory only with JSONL event log replay — DEC-015
- **Layout:** `src/{pricing,state,ingestion,quoting,sizing,config}/` plus `tests/`, `scripts/`, `data/`, `models/`, `reference/` — DEC-019
- **Deploy artifact:** single multi-stage Dockerfile (builder + slim runtime), image size target < 500MB
- **Production host:** Hetzner CCX13 (~$20/mo, 2 vCPU, 8GB RAM, US-East); AWS t3.small as alternative

## Success metrics

Developer-facing gates and ongoing measurements (per `prd.md` §2, §8 and `roadmap.md` §5.3):

- **Latency:** < 500 ms median (in-game event → updated theo); < 100 ms (state change → all stale orders pulled)
- **Brier:** live theo Brier ≤ rib.gg-derived static-prior baseline by ≥ 0.02 over a 50-round window during paper trading
- **Promotion gate to live:** ≥ 1 full event of paper trading with Brier < 0.22 AND zero kill-switch trips for ingestion bugs (model-trip kill-switch trips are acceptable; bug-trip ones are not)
- **Adverse-selection rate as MM:** % of fills that move against us within 5s — baseline observed during paper trading, then tracked
- **Quote uptime during live matches:** % of seconds with active quotes

## Status

| Phase | Status |
|---|---|
| 0 — Foundation | Pending |
| 1 — Pricing engine | Pending |
| 2 — Round-event data | Pending |
| 3 — Live ingestion | Pending |
| 4 — Quoting | Pending |
| 5 — Validation | Pending |
| 6 — Deployment | Pending |
| 7 — Operational maturity | Pending |

Current phase: **none** (planning artifacts just bootstrapped). See `.planning/STATE.md` for live state.

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
  title: Hybrid trading style (event-trigger with vega override)
  source: prd.md §2.1, §9
  corroborating: roadmap.md §4.2
  scope: trading mode selection
  statement: |
    Default to MM (market-maker) mode with theo ± vega-scaled spread. Flip to DIRECTIONAL on any of:
    (a) numerical imbalance ≥ 1, (b) bomb planted, (c) map-point round, (d) score 12-12 / 1-1 decider,
    OR (e) `vega > VEGA_DIRECTIONAL_THRESHOLD`. Reset to MM at round end + 5v5 + no event flags.

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
  title: Tiered ingestion confirmation by event type
  source: prd.md §5.1
  corroborating: roadmap.md §3.5
  scope: ingestion arbitration
  statement: |
    Score change requires ≥ 2 independent sources within a 2s window.
    Bomb plant / kill / numerical flip commits on 1 CV-based source if kill-feed cross-confirms within same frame.
    Round-end banner is a soft commit, hard-confirmed by next score update.
    Pre-match lineup/sides accepts a single API source.

- id: DEC-007
  title: Hierarchical-lookup round-conclusion model
  source: prd.md §5.3, §9
  corroborating: roadmap.md §1.5
  scope: mid-round round-win probability
  statement: |
    `P(team A wins this round | mid-round state)` indexed by
    `(numerical_diff, bomb_status, side, econ_bucket, map)`. ~500–2000 cells with Bayesian shrinkage to
    lower-dimensional parent cells when sample is thin: cell → side+map → side → overall.
    Inherits `SHRINK_PRIOR=15`, `SIGNAL_SCALE=0.10` until ≥100 live matches of calibration data exist.

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
  title: Vega initial definition (refine in Phase 5)
  source: roadmap.md §1.6
  scope: vega computation
  statement: |
    Initial: `vega = round_p × (theo_after_a_win − theo)² + (1−round_p) × (theo_after_b_win − theo)²`
    — variance of next theo update conditional on next round outcome. Refine in Phase 5.
    (PRD §9 TBD #3 lists three defensible alternatives; this picks (a).)

- id: DEC-019
  title: Project layout — src/{pricing,state,ingestion,quoting,sizing,config}/
  source: roadmap.md §0.1
  scope: package structure
  statement: |
    Standard `src/` package layout. `tests/`, `scripts/`, `data/`, `models/`, `reference/` siblings of `src/`.

- id: DEC-020
  title: Paper-trade promotion gate
  source: roadmap.md §5.3, §5.2
  scope: live-trading readiness
  statement: |
    ≥ 1 full event of paper-trading with Brier < 0.22 and zero kill-switch trips for ingestion bugs
    (model-trip kill switches are OK; bug-trip kill switches are not). Backtest validates the model alone;
    order-fill backtest is skipped in favor of paper trading (more honest given Kalshi historical
    order-book unavailability).

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
</decisions>

---

## Open TBDs (deferred from PRD §9, intentional)

These are flagged here so plan-phase agents know they are not yet locked:

1. **Bankroll size and per-market exposure cap.** Operational; depends on capital allocation decision. `PER_MARKET_CAP_FRAC = 0.05` is a placeholder.
2. **Threshold values.** `VEGA_DIRECTIONAL_THRESHOLD = 0.04` and the four kill-switch constants ship with initial guesses, re-tune after 20+ live matches (Phase 5 calibration).
3. **Vega formula refinement.** DEC-018 picks variant (a); revisit in Phase 5 if observed predictive variance underperforms.
4. **Backtest fidelity.** DEC-020 skips order-fill backtest in favor of paper trading. Reconsider if Kalshi exposes historical order-book data.

See `prd.md` §9 and `.planning/intel/context.md / Open questions still TBD` for full framing.

## Cross-references

- `CLAUDE.md` (project instructions) — terse, surfaces critical rules + domain constants. Do not duplicate decisions there; the source of truth for design choices is `prd.md` and this file.
- `.planning/codebase/` — produced by `/gsd-map-codebase`, supplementary context for understanding current code structure (read-only here).
- `.planning/INGEST-CONFLICTS.md` — full three-bucket report from doc synthesis (4 INFO entries, 0 BLOCKERs, 0 WARNINGs as of 2026-04-27).
