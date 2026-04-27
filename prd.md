# PRD — Valorant Live Pricing Model

**Owner:** jxc2008@nyu.edu
**Status:** Draft
**Created:** 2026-04-27
**Location:** `C:\Users\josep\OneDrive\Desktop\Thunderedge\valorant-pricing-model\`

---

## 1. Problem

The existing `theo_engine.py` (in `thunderedge/worktrees/market-maker/backend/`) prices BO3 series winners **pre-match** using a Markov DP over team/map/side half-win-rates. Once the match starts, the only signal that updates is the scoreboard — every other piece of state (numerical advantage, bomb plant, economy, ult counts) is invisible to the pricer.

We need a **live pricing model** that re-prices the series at any moment during a match, on Kalshi, fast enough to either capture edge or — at minimum — avoid being adversely selected.

## 2. Goal

A live theo engine that, given the full current match state, returns:

- `theo_series` ∈ [0, 1]: P(team A wins the series | current state)
- `theo_map[i]` ∈ [0, 1]: P(team A wins map i | current state) for each map in the pool
- `confidence`: data-weight in [0, 1]
- `vega`: variance of the next theo update (drives quote width)

End-to-end latency target: **< 500 ms** from observable in-game event → updated theo. Quote-cancel target: **< 100 ms** from state change → all stale orders pulled.

### 2.1 Trading style — hybrid (event-trigger with vega override)

Mode is a first-class state, computed every state update:

- **MM mode** (default) — during low-volatility states. Quote both YES/NO at theo ± vega-scaled spread.
- **Directional mode** — pull MM quotes, fire takes when `|theo − market| > threshold`.

Mode flip rules (in order of evaluation):

1. **Event triggers** (primary): mid-round with numerical imbalance ≥ 1, bomb planted, map-point round, score 12-12 / 1-1 decider.
2. **Vega override** (fallback): if computed vega exceeds `VEGA_DIRECTIONAL_THRESHOLD`, force directional mode regardless of event flags. Catches states the event list missed (extended 1v1 clutch, unusual eco scenario).
3. **Reset to MM** at round end + side count returns to 5v5 + no event flags active.

### 2.2 Markets in scope

**Phase 1:** BO3 series winner + per-map winner. Both price off the same series-from-state DP, so the marginal cost of pricing per-map is small.

**Pricing approach:** single DP, derive both markets. P(series) directly from DP value at root state; P(map_i) by marginalizing the DP over future map outcomes. Mathematically arb-free by construction — quoting can never internally cross.

### 2.3 Sizing — half-Kelly with per-market cap

Position size = `0.5 × Kelly_fraction × bankroll`, capped at a per-market exposure ceiling (TBD: §9.1). Half-Kelly preserves ~75% of full-Kelly long-run growth at ~25% of the variance and is the standard defense against theo miscalibration during the model's learning period.

For YES buys: `Kelly_fraction = (theo − market_yes_ask) / (1 − market_yes_ask)`. Symmetric for NO.

## 3. Non-goals

- Beating tier-1 caster-API bots on absolute speed. Out of scope.
- OT modeling (excluded everywhere per existing repo convention).
- Player-level prop pricing — that's the kill-line track, not this one.
- Modeling tilt, day-of form, coach reads, crowd. Trader intuition layer, not model.

## 4. Conceptual framing — the options-theory analog

The user came in via Black-Scholes intuition. Mapping the five inputs:

| BS input | Event-market analog | Used? |
|---|---|---|
| Strike | always 50¢ for binary YES/NO | No |
| Expiry | rounds/maps to series resolution | Yes — theta-decay is real |
| Underlying | true P(team A wins series) | Yes — what we're modeling |
| Rate | ~0 on Kalshi | No |
| Volatility | how fast P(win) can swing per round | **Yes — most underrated** |

There is no closed-form. The right framing is a **recursive expectation**:

```
P(series | now) = E[P(series | next state)]
```

— under the round-outcome distribution. The existing pre-match Markov DP already does this from `(0,0)`; live pricing is the same DP started from arbitrary state.

Greeks have natural analogs and are useful:

- **Delta** = ∂P(series)/∂P(round) — risk per round outcome
- **Gamma** = curvature, peaks near 12-12 / 1-1 maps
- **Vega** = sensitivity to round-win-prob estimate — drives quote width
- **Theta** = price drift toward 0/100 as rounds tick

## 5. Architecture

Four layers, each independently buildable:

```
[Ingestion]  →  [State Engine]  →  [Theo Engine]  →  [Quoting / Orders]
```

### 5.1 Ingestion layer

Parallel sources with **tiered cross-confirmation by event type**:

| Event type | Confirmation rule | Rationale |
|---|---|---|
| Score change (round/map win) | ≥ 2 independent sources within 2s window | Highest blast radius — false score commit corrupts the DP root state |
| Bomb plant | 1 source if CV-based (HUD icon) AND kill-feed cross-confirms within same frame | Local CV is high-fidelity here, no need to wait for second source |
| Kill / numerical flip | 1 source if CV-based AND kill-feed cross-confirms | Same as plant |
| Round-end announcement banner | 1 source (CV) — soft commit, hard-confirmed by next score update | Banner appears ~500ms before scoreboard updates; capture the alpha |
| Pre-match lineup, sides | API-only, single source | No latency pressure, scrapers are authoritative |

Sources:

- **CV/OCR on lowest-latency video stream** (extends `vision_parser.py`): score banner, kill feed, bomb icon, ult orbs, player-alive indicators
- **Scoreboard polling**: rib.gg / bo3.gg / vlr.gg live endpoints
- **Text listeners**: Twitter/Discord match-thread reactions (~1–3s, noisy but fast)

Latency budget per source (approximate):

| Source | Latency | Reliability |
|---|---|---|
| Caster client | ~0s | N/A (not accessible) |
| YouTube low-latency mode | ~3s | High |
| Kalshi embedded video | ~3–10s | Medium |
| Twitch HLS | ~5–15s | High |
| Scoreboard scrapers | 5–60s post round | Authoritative |
| Twitter/Discord text | ~1–3s post event | Noisy but fast |

### 5.2 State engine

Single source of truth:

```
{
  map_idx, map_score_a, map_score_b,
  round_score_a, round_score_b, side_orientation,
  econ_a, econ_b, ults_a, ults_b,
  players_alive_a, players_alive_b,
  bomb_planted, time_left,
  seq_id, last_updated_ts
}
```

Versioned via `seq_id`. Quoting layer only acts on monotonically increasing seq_ids.

### 5.3 Theo engine

Two timescales, composed:

**(a) Round-conclusion model — hierarchical lookup table.** `P(team A wins this round | mid-round state)`, indexed by `(numerical_diff, bomb_status, side, econ_bucket, map)`. ~500–2000 cells total. Bayesian shrinkage to lower-dimensional parent cells when sample is thin (cell → side+map → side → overall). Fully interpretable: any prediction can be audited by inspecting the relevant cell. Inherits the existing `SHRINK_PRIOR=15`, `SIGNAL_SCALE=0.10` from `theo_engine.py` until ≥100 live matches of calibration data exist, then re-fit to minimize live Brier.

**(b) Series-from-state DP.** Generalize existing `_markov_map_win` and `series_theo_from_map_probs` to accept arbitrary starting `(map_idx, round_score_a, round_score_b, side, remaining_pool)`. The state space is < 1M states for a BO3 — pre-compute once, mmap as a lookup table for sub-millisecond reads.

**Live theo:**

```
theo = round_p × dp[state_after_a_wins_round]
     + (1 - round_p) × dp[state_after_b_wins_round]
```

Between rounds, `round_p` is the side/map/econ baseline. Mid-round, `round_p` is the round-conclusion lookup output.

### 5.4 Quoting / orders

Extends existing `market_maker.py`:

- Spread width ∝ vega (variance of next theo update) + staleness penalty
- `time_since_last_state_update > 2s` → widen aggressively or pull
- Skew quotes when adverse-selection risk is high (tournament finals, big audience)

#### Kill switches (all-on, hard-pull all resting quotes)

| Trigger | Action |
|---|---|
| Kalshi API errors / network disconnect | Pull + alert. Always-on. |
| Ingestion staleness > 5s | Pull until fresh confirmed update resumes. |
| `\|theo − market\| > 20¢` | Pull + alert for human review. Asymmetric: broken-model risk dominates real-edge upside at this magnitude. |
| Rolling Brier score > 0.30 over last 50 round predictions | Pull + alert. Catches calibration breaks (roster changes, new map, regime shifts). |

Threshold values (5s, 20¢, 0.30, 50) are initial — re-tune after first 20 live matches of data.

### 5.5 Deployment — hybrid local dev + cloud production

- **Local Windows** (`C:\Users\josep\OneDrive\Desktop\Thunderedge\valorant-pricing-model\`): development, backtesting, paper trading. OneDrive filesystem quirks tolerated here since no live capital.
- **Cloud VM, US-East** (AWS / GCP / Hetzner near Kalshi infra): live trading. Docker image + SSH deploy. ~$30–100/mo. Consistent ~10–20ms RTT to Kalshi API.
- Promotion gate: backtest Brier < threshold + paper-trade for ≥ 1 full event with target metrics met → deploy to cloud.

## 6. Inputs — taxonomy

### Tier 1: clean model inputs (fold into round_p directly)

- Half-win-rate by team/map/side ← already in `half_win_rates.json`
- Round type / economy state ← generalize `GUN_WIN_RATE = 0.822` into a lookup over `(econ_a, econ_b, side, map)`
- Player numerical state (5v5, 5v4, 4v3, 1v3) ← biggest single in-round factor
- Bomb plant status (pre/post-plant) per side
- Pistol / anti-eco / conversion modifiers

### Tier 2: model inputs, painful live data

- Ult counts per team (need CV on HUD orb tracker)
- Utility remaining mid-round (proxy via abilities-used in kill feed)
- Agent comp matchup on the map

### Tier 3: trader intuition only — do not model

- Tilt / momentum
- Day-of player form
- Coach side-switch reads
- Anti-strat reads on a return map
- LAN vs. online, crowd

## 7. Build phases

In order, smallest-to-largest:

1. **Generalize Markov DP to arbitrary start state.** Pre-compute lookup table. ~1 day. Immediate value: between-round live pricing, no new data sources.
2. **Round-type / economy lookup** generalizing `GUN_WIN_RATE`. Pull from existing `match_round_data`. ~1 day.
3. **Cross-source state arbiter** wrapping `vision_parser` + scoreboard polling. ~3–5 days. The latency-defense layer.
4. **Scope rib.gg / bo3.gg round-event APIs.** Decision gate: if either exposes per-round (numerical, bomb, kill feed) events, build the round-conclusion model on top in ~3 days. If neither does, escalate to OCR-driven VOD labeling (2-week project) or defer the round-conclusion model and ship phases 1–3.
5. **Round-conclusion model** (conditional on phase 4 outcome). Numerical state + bomb status + econ delta as features. XGBoost or hierarchical lookup.
6. **Ult tracking** last — high effort, modest single-input edge.

Steps 1–3 turn the pre-match engine into a live engine with no new data sources.

## 8. Success metrics

- **Brier score** of live theo vs. realized outcome (per-state, bucketed by time-to-resolution)
- **Adverse-selection rate** as MM (% of fills that move against us within 5s)
- **Quote uptime** during live matches (% of seconds with active quotes)
- **Latency**: median + p99 from in-game event → state update → quote refresh

## 9. Open questions

Resolved in this PRD:

| Decision | Resolution |
|---|---|
| Trading style | Hybrid (event-trigger with vega override) |
| Markets in scope | BO3 series + per-map, via single DP |
| Label data source | Scope rib.gg / bo3.gg APIs first |
| Sizing | Half-Kelly with per-market cap |
| Ingestion confirmation | Tiered by event type |
| Round-conclusion model | Hierarchical lookup table |
| Live shrinkage prior | Inherit pre-match (`SHRINK_PRIOR=15`), recalibrate after ≥100 matches |
| Kill switches | All four: API errors, staleness > 5s, deviation > 20¢, rolling Brier > 0.30 |
| Deployment | Hybrid local dev + cloud production |

### Still TBD (resolve after data exists)

1. **Bankroll size and per-market exposure cap.** Operational, depends on capital allocation decision.
2. **Numerical thresholds.** `VEGA_DIRECTIONAL_THRESHOLD`, kill-switch values (5s, 20¢, 0.30, 50-round Brier window) — all initial guesses, re-tune after 20+ live matches.
3. **Vega computation formula.** Variance of next theo update is conceptually clear but has multiple defensible implementations: (a) variance under round-outcome distribution only, (b) variance including ingestion-noise term, (c) bootstrap over recent calibration error. Pick one in phase 1.
4. **Backtest fidelity.** Replaying past matches against historical market prices requires either an order-book replay (Kalshi may not provide) or a synthetic counterparty. Decide before phase 1 whether backtest is in-scope or whether paper-trade live is the validation path.

## 10. Dependencies

- Existing `theo_engine.py`, `half_win_rates.json`, `match_round_data` table
- Existing `vision_parser.py` (OCR backbone)
- Existing `kalshi_client.py` and `market_maker.py`
- Riot/rib.gg/bo3.gg/vlr.gg data availability for round-by-round events (TBD)

## 11. Out of scope (this PRD)

- BO5 series modeling
- Pick/ban model (handled by pre-match `pickban_prediction`)
- Player kill-line markets

---

## 12. Audit of existing pricing code (`worktrees/market-maker/backend/`)

Salvageable files have been copied into `valorant-pricing-model/reference/` and `valorant-pricing-model/data/`. The original worktree is untouched and continues to function for pre-match BO3 quoting.

### 12.1 Salvage decisions

| File | Verdict | Action |
|---|---|---|
| `odds_utils.py` | Salvage as-is | Reused unchanged |
| `fair_value.py` | Salvage as-is | Used as the `fallback_q` baseline for no-data states |
| `half_win_rates.json` | Salvage as-is | Direct input to the new DP |
| `theo_engine.py` | Partial — keep DP skeleton, rewrite the rest | See §12.2 below |
| `market_maker.py` | Partial — extract Kalshi plumbing into `KalshiOrderManager` | The 10s poll loop, single quoting mode, and pre-veto var mutation are obsolete |
| `market_implied.py` | Skip | Wrong project — kill-line markets, Poisson inversion |
| `map_bidder.py` | Skip — subsumed by single-DP map pricing | Has the same atk/def averaging bug as `series_theo_no_sides` |
| `run_market_maker.py`, `run_quote_bot.py`, `run_map_bidder.py` | Skip | New entry points will be event-driven |

### 12.2 Bugs and rigor issues in `theo_engine.py` (must fix in rewrite)

**Definite bugs:**

1. **Docstring drift in `series_theo_from_map_probs`** (line 343-348): docstring claims `p_map = fallback_q + dw_map * (blended_p - 0.5)` but code does `(1.0 - dw) * fallback_q + dw * blended_p` = `fallback_q + dw * (blended_p - fallback_q)`. The `0.5` should be `fallback_q`. Anyone reasoning from the docstring gets a different model than the code implements.

2. **Three pricing entry points with inconsistent math**: `signal_strength` is applied in `series_theo` and `series_theo_no_sides` but NOT in `series_theo_from_map_probs`. Switching entry points silently changes results. Rewrite as one canonical `live_theo`.

3. **Silent OT-as-coinflip despite "no OT" policy.** CLAUDE.md says OT is excluded everywhere. But `_markov_map_win` runs the DP loop through `range(WIN_THRESHOLD * 2) = range(26)`, and at `total >= 24` it uses `p = 0.5`. So OT is implicitly modeled as a coinflip. Either change the policy or stop the loop at `total = 24`.

**Modeling rigor concerns:**

4. **Round-win-prob blend is an arithmetic mean** (line 161): `p = (a_rate + (1.0 - b_rate)) / 2.0`. Replace with Bradley-Terry-style log-odds: `p = a_rate * (1-b_rate) / (a_rate * (1-b_rate) + (1-a_rate) * b_rate)`. The arithmetic mean under-weights compounding edges toward the extremes.

5. **Two-half flat model ignores pistol / anti-eco.** DP assumes constant `p1` for rounds 1-12 and `p2` for 13-24. But round 1 and round 13 are pistols (`GUN_WIN_RATE = 0.822`), and a pistol win cascades into 2-3 follow-up wins via anti-eco. **Largest single modeling gap.** The new DP must model rounds 1, 2, 3 (pistol + anti-eco/bonus) and 13, 14, 15 explicitly with their own probability inputs, then revert to side-baseline for 4-12 and 16-24.

6. **`series_theo_no_sides` averages atk-start and def-start** (line 420). Wrong — starting side is determined by veto, not random. Use the realized veto outcome.

7. **Hardcoded `[0.05, 0.95]` and `[0.03, 0.97]` clips.** Invisible bounds on conviction. Push to `[0.01, 0.99]` and document.

### 12.3 Rewrite priorities

Phase 1 work in the new project must:

1. Build a single canonical `live_theo(state) → (theo, vega, confidence)`.
2. Generalize the Markov DP to arbitrary `(map_idx, a_score, b_score, side, remaining_pool)` start states.
3. Replace arithmetic blend with Bradley-Terry round-win-prob.
4. Model pistol/anti-eco rounds (1, 2, 3, 13, 14, 15) with separate probability inputs from `GUN_WIN_RATE` and `match_round_data`.
5. Stop OT silently — either explicit OT model or hard-stop at total=24 with a documented OT-coinflip leaf.
6. Extract Kalshi plumbing from `market_maker.py` into a thin `KalshiOrderManager` that the new event-driven quoter uses.
