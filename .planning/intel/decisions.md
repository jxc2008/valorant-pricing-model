# Decisions (Intel)

Synthesized from PRD and SPEC. No ADRs in scope. Decisions inherit precedence from their source: SPEC > PRD where they speak to the same field. None of these are flagged `locked: true` at the classification level, but the PRD §9 explicitly enumerates "resolved" decisions which are treated as authoritative-by-source.

---

## DEC-001 — Hybrid trading style (event-trigger with vega override)
- source: prd.md §2.1, §9
- scope: trading mode selection
- statement: Default to MM (market-maker) mode with theo ± vega-scaled spread. Flip to DIRECTIONAL on (a) numerical imbalance ≥ 1, (b) bomb planted, (c) map-point round, (d) score 12-12 / 1-1 decider, OR (e) `vega > VEGA_DIRECTIONAL_THRESHOLD`. Reset to MM at round end + 5v5 + no event flags.
- corroborating-source: roadmap.md §4.2 (`trading_mode(state, vega)` pure function implements this exact rule list)

## DEC-002 — Single DP for BO3 series + per-map (single canonical model)
- source: prd.md §2.2, §5.3
- scope: pricing model architecture
- statement: BO3 series and per-map theos derive from one DP. P(series) is the DP value at root state; P(map_i) is computed by marginalizing the DP over future map outcomes. Mathematically arb-free by construction; quoting cannot internally cross.
- corroborating-source: roadmap.md §1.6 (`live_theo` returns both `theo_series` and `theo_map[i]` from same DP, "no second model")

## DEC-003 — Bradley-Terry round-win-prob blend
- source: prd.md §12.2 #4
- scope: round probability composition
- statement: Replace arithmetic mean `(a + (1-b))/2` with `p = a*(1-b) / (a*(1-b) + (1-a)*b)`. Arithmetic mean under-weights compounding edges.
- corroborating-source: roadmap.md §1.2 (formula and unit-test cases provided)

## DEC-004 — Half-Kelly sizing with per-market cap
- source: prd.md §2.3, §9
- scope: position sizing
- statement: `f = 0.5 × Kelly_full`, capped at `PER_MARKET_CAP_FRAC` of bankroll. Never full Kelly. For YES buys: `Kelly_fraction = (theo − market_yes_ask) / (1 − market_yes_ask)`; symmetric for NO.
- corroborating-source: roadmap.md §4.5 (`kelly_size` implementation matches)

## DEC-005 — Four kill switches, all-on, no per-switch disable flag
- source: prd.md §5.4, §9
- scope: risk controls
- statement: Always-on triggers, each pulls all resting quotes: (a) Kalshi API errors / network disconnect, (b) ingestion staleness > 5s, (c) `|theo − market| > 20¢`, (d) rolling Brier > 0.30 over last 50 round predictions.
- corroborating-source: roadmap.md §4.6 ("Always-on by default; no config flag to disable individual switches")

## DEC-006 — Tiered ingestion confirmation by event type
- source: prd.md §5.1
- scope: ingestion arbitration
- statement: Score change requires ≥ 2 independent sources within a 2s window. Bomb plant / kill / numerical flip commits on 1 CV-based source if kill-feed cross-confirms within same frame. Round-end banner is a soft commit, hard-confirmed by next score update. Pre-match lineup/sides accepts a single API source.
- corroborating-source: roadmap.md §3.5 (arbiter implements PRD §5.1 verbatim)

## DEC-007 — Hierarchical-lookup round-conclusion model
- source: prd.md §5.3, §9
- scope: mid-round round-win probability
- statement: `P(team A wins this round | mid-round state)` indexed by `(numerical_diff, bomb_status, side, econ_bucket, map)`. ~500–2000 cells with Bayesian shrinkage to lower-dimensional parent cells when sample is thin: cell → side+map → side → overall. Inherits `SHRINK_PRIOR=15`, `SIGNAL_SCALE=0.10` from `theo_engine.py` until ≥100 live matches of calibration data exist.
- corroborating-source: roadmap.md §1.5 (fallback chain reproduced exactly)

## DEC-008 — Hybrid local dev / cloud production deployment
- source: prd.md §5.5, §9
- scope: deployment topology
- statement: Local Windows for dev/backtest/paper-trade. Cloud VM in US-East (AWS / GCP / Hetzner near Kalshi infra) for live trading. Docker image + SSH deploy. Promotion gate: backtest Brier < threshold + ≥1 full event of paper trading meeting target metrics.
- corroborating-source: roadmap.md §6.2 (Hetzner CCX13 ~$20/mo recommended; AWS t3.small alternative)

## DEC-009 — OT explicit hard-stop at total=24 with documented coinflip leaf
- source: prd.md §12.2 #3
- scope: DP termination policy
- statement: DP must NOT silently model OT as `p=0.5` past round 24 (audit bug in `_markov_map_win`'s `range(26)` loop). Either explicit OT model OR hard-stop at `total = 24` with a documented OT-as-coinflip leaf.
- corroborating-source: roadmap.md §1.4 (chooses the explicit hard-stop with documented OT-as-coinflip leaf: `0.5 × value(after_a_OT_win) + 0.5 × value(after_b_OT_win)` at the 12-12 boundary, OT continues with constant `p=0.5` until win-by-2)
- note: prd.md §3 "Non-goals" lists "OT modeling (excluded everywhere per existing repo convention)" — see `INGEST-CONFLICTS.md` INFO bucket for reconciliation framing.

## DEC-010 — Single canonical pricing entry point: `live_theo(state)`
- source: prd.md §6 (Goal), §12.2 #2, §12.3
- scope: pricing API surface
- statement: One function `live_theo(state) → (theo_series, theo_map, vega, confidence)`. Do NOT recreate the `series_theo` / `series_theo_no_sides` / `series_theo_from_map_probs` triplet from the audited engine — inconsistent `signal_strength` application across those three was a bug.
- corroborating-source: roadmap.md §1.6 (`TheoOutput` dataclass with `theo_series`, `theo_map`, `vega`, `confidence`)

## DEC-011 — Pistol + anti-eco rounds modeled explicitly
- source: prd.md §12.2 #5
- scope: round-type modeling
- statement: Rounds 1, 2, 3, 13, 14, 15 use separate probability inputs derived from `match_round_data` and `GUN_WIN_RATE = 0.822`. Constant `p1` for rounds 1–12 and `p2` for 13–24 is wrong — it ignores pistol cascades into anti-eco rounds.
- corroborating-source: roadmap.md §1.3 (state-augmented DP with economy memory; per-round source table mapping rounds to data origins)

## DEC-012 — Conviction clips at [0.01, 0.99]
- source: prd.md §12.2 #7
- scope: probability bounds
- statement: Replace audited engine's `[0.05, 0.95]` and `[0.03, 0.97]` clips with `[0.01, 0.99]`. Document any tighter clip explicitly.

## DEC-013 — Salvage map: keep / partial / skip
- source: prd.md §12.1
- scope: code reuse from audited engine
- statement:
  - Salvage as-is: `odds_utils.py`, `fair_value.py`, `half_win_rates.json`
  - Partial: `theo_engine.py` (DP skeleton only; rewrite the rest per §12.2/§12.3); `market_maker.py` (extract Kalshi plumbing into `KalshiOrderManager`)
  - Skip: `market_implied.py` (kill-line markets), `map_bidder.py` (atk/def averaging bug), `run_market_maker.py` / `run_quote_bot.py` / `run_map_bidder.py` (new entry points are event-driven)

## DEC-014 — Tooling: Python 3.11, uv, pytest+hypothesis, ruff, mypy --strict on src/pricing/
- source: roadmap.md §0.2
- scope: developer toolchain
- statement: Python 3.11 with `uv` for venv (faster than pip), `pyproject.toml`. `pytest` + `pytest-cov` + `hypothesis` for property-based tests. `ruff` for lint+format (one tool, fast). `mypy --strict` enforced on `src/pricing/`.

## DEC-015 — Data store: SQLite for cache, in-memory only for live state
- source: roadmap.md §0.3
- scope: persistence layer
- statement: Existing repo's SQLite is reused for the dataset cache. Live state is in-memory only, persisted to disk only as JSONL event logs for replay/debug. Do NOT put live state in SQLite.

## DEC-016 — Configuration centralization: `config/constants.py`
- source: roadmap.md §0.4
- scope: magic-number policy
- statement: Every magic number from PRD lives in `config/constants.py`. Threshold-tuning is a Phase 5 activity; ship initial values, never hardcode in business logic.

## DEC-017 — Phase-2 API decision gate
- source: prd.md §7 step 4, §9; roadmap.md §2 (Phase 2)
- scope: round-event data acquisition
- statement: Probe rib.gg / bo3.gg APIs for per-round events first (Path A, ~3 days). If insufficient, escalate to OCR-driven VOD labeling (Path B, ~2 weeks). If neither feasible, defer round-conclusion model and ship Phases 1, 3, 4 with `round_conclusion` returning fixed `p=0.5` (Path C — between-round live MM only).

## DEC-018 — Vega initial definition (refine in Phase 5)
- source: roadmap.md §1.6
- scope: vega computation
- statement: Initial: `vega = round_p × (theo_after_a_win − theo)² + (1−round_p) × (theo_after_b_win − theo)²` — variance of next theo update conditional on next round outcome. Refine in Phase 5. (PRD §9 TBD #3 lists three defensible alternatives; this picks (a).)

## DEC-019 — Project layout: `src/{pricing,state,ingestion,quoting,sizing,config}/`
- source: roadmap.md §0.1
- scope: package structure
- statement: Standard `src/` package layout. `tests/`, `scripts/`, `data/`, `models/`, `reference/` siblings of `src/`.

## DEC-020 — Paper-trade promotion gate
- source: roadmap.md §5.3, §5.2
- scope: live-trading readiness
- statement: ≥ 1 full event of paper-trading with Brier < 0.22 and zero kill-switch trips for ingestion bugs (model-trip kill switches are OK; bug-trip kill switches are not). Backtest validates the model alone; order-fill backtest is skipped in favor of paper trading (more honest given Kalshi historical order-book unavailability).

## DEC-021 — Daily portfolio loss limit (distinct from per-market kill switches)
- source: roadmap.md §7.4
- scope: portfolio-level circuit breaker
- statement: Beyond per-market cap, halt the bot when cumulative realized + unrealized P&L < −X% of bankroll until manual review. Distinct from kill switches (which are per-market signals).

## DEC-022 — Dry-run by default; live trading requires explicit `--live` flag
- source: prd.md §5.5 (paper-trade promotion gate); CLAUDE.md critical rule #13 (project instructions)
- scope: safety default
- statement: Bot stays in `dry_run=True` until promotion gate is met. Live trading requires explicit CLI flag at the entry point. (Note: this rule is sourced from CLAUDE.md project instructions which encode PRD intent; surfaced here for synthesis completeness.)
