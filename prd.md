# PRD — Valorant Live Pricing Model

**Owner:** jxc2008@nyu.edu
**Status:** Draft (v2 architecture pivot — 2026-05-02)
**Created:** 2026-04-27
**Location:** `C:\Users\josep\OneDrive\Desktop\Thunderedge\valorant-pricing-model\`

> **v2 pivot note (2026-05-02):** This PRD was originally framed as a market-maker-primary bot. After thinking through edge sources and fill-rate concerns on VCT Kalshi markets, the framing changed: the bot is built around **opportunistic directional taking** when DP-based theo disagrees materially with the market, supplemented by MM quoting between rounds when conditions are favorable, with **post-plant** as the one mid-round capability worth building. Kill-feed CV, mid-round economy inference, and ult tracking are explicitly out of scope. Paper trading decides whether MM, taking, or both is the actual edge source — neither is committed to a priori.

---

## 1. Problem

The existing `theo_engine.py` (in `thunderedge/worktrees/market-maker/backend/`) prices BO3 series winners **pre-match** using a Markov DP over team/map/side half-win-rates. Once the match starts, the only signal that updates is the scoreboard — every other piece of state (numerical advantage, bomb plant, economy, ult counts) is invisible to the pricer.

We need a **live pricing model** that re-prices the series at any moment during a match, on Kalshi, fast enough to either capture edge through directional takes or — at minimum — avoid being adversely selected.

## 2. Goal

A live theo engine that, given the current match state, returns:

- `theo_series` ∈ [0, 1]: P(team A wins the series | current state)
- `theo_map[i]` ∈ [0, 1]: P(team A wins map i | current state) for each map in the pool
- `confidence`: data-weight in [0, 1]
- `vega`: variance of the next theo update — context-dependent (see §5.4 — between-round and post-plant have separate vega definitions)

End-to-end latency target: **< 500 ms** from observable in-game event → updated theo. Defensive quote-pull on bomb-plant detection: **< 200 ms** from detection → all stale quotes pulled. Quote-cancel target: **< 100 ms** from state change → all stale orders pulled.

### 2.1 Trading style — three-way mode + IDLE (paper trade decides)

Mode is a first-class state, computed every state update. The mode selector is a **pure function** over `(state, theo, market_quote, vega_between, vega_post_plant)` returning one of:

| Mode | When | Action |
|---|---|---|
| `MM_BETWEEN_ROUND` | Between rounds, market spread > `MM_MIN_EDGE` | Quote both YES/NO at theo ± vega-scaled spread (floor ≥ Kalshi commission + slippage) |
| `DIRECTIONAL_TAKE` | Between rounds, `\|theo − market_mid\| > TAKE_THRESHOLD` | Lift offer / hit bid; sized by portfolio Kelly (§2.3) |
| `POST_PLANT_QUOTE` | Mid-round, `bomb_planted=True` | Re-price using post-plant lookup; quote at theo ± narrow spread, OR take if deviation high |
| `IDLE` | Pre-match, mid-round-not-planted, between-round insufficient edge, kill-switch active | Pull all resting quotes, no new orders |

Selection logic (evaluated in order):

```
if any_kill_switch_active: IDLE
if state.bomb_planted: POST_PLANT_QUOTE
if state.is_mid_round and not state.bomb_planted: IDLE     # no general mid-round trading
# between-round state from here:
if abs(theo - market_mid) > TAKE_THRESHOLD: DIRECTIONAL_TAKE
if market_spread > MM_MIN_EDGE: MM_BETWEEN_ROUND
otherwise: IDLE
```

**MM and DIRECTIONAL are first-class peers, not primary/fallback.** During paper trading they run on separate hypothetical-fill ledgers with separate Brier and P&L books, so the architecture survives if only one strategy generates fills (see §8 Promotion gate).

### 2.2 Markets in scope

**Phase 1:** BO3 series winner + per-map winner. Both price off the same series-from-state DP — single canonical model, never two that can disagree.

**Pricing approach:** single DP, derive both markets. `P(series)` = DP value at root state; `P(map_i)` = marginalize the DP over future map outcomes. Mathematically arb-free by construction — quoting cannot internally cross.

### 2.3 Sizing — half-Kelly, per-market cap, per-series aggregate cap

Position size = `0.5 × Kelly_full × bankroll`, capped at TWO ceilings:

1. **Per-market cap** (`PER_MARKET_CAP_FRAC = 0.05` initial): max fraction of bankroll on any single contract.
2. **Per-series aggregate cap** (`SERIES_AGGREGATE_CAP_FRAC = 0.10` initial): max fraction of bankroll across **all correlated markets on the same series** — moneyline + map-1 + map-2 + map handicaps + round handicaps all share underlying outcomes and move together.

Per-market caps alone do not bound aggregate risk: 4 correlated markets at 5% each = 20% on one outcome. The sizer takes a `current_series_exposure: dict[series_id, float]` argument and clips new positions so cumulative exposure ≤ aggregate cap. Returns `0` if the aggregate cap is already exceeded.

For YES buys: `Kelly_full = (theo − market_yes_ask) / (1 − market_yes_ask)`. Symmetric for NO. Half-Kelly preserves ~75% of full-Kelly long-run growth at ~25% of variance.

**This is the v1 floor.** Full covariance-aware portfolio Kelly with a per-series correlation matrix is Phase 7 maturity work — flagged explicitly in §9 and roadmap §7. The simple aggregate cap is "safe-enough for paper trade", not "correct".

## 3. Non-goals

- Beating tier-1 caster-API bots on absolute speed. Out of scope.
- OT modeling (excluded everywhere per existing repo convention).
- Player-level prop pricing — that's the kill-line track, not this one.
- Modeling tilt, day-of form, coach reads, crowd. Trader intuition layer, not model.
- **Live mid-round pricing without a bomb plant.** The bot returns degraded-confidence between-round theo when mid-round-not-planted; quoting layer maps to IDLE. No general mid-round path that depends on noisy state estimates.
- **Kill-feed CV.** Cut. Required reliability is too high for the build cost.
- **Mid-round economy inference.** Cut. Economy is not directly observable from broadcast.
- **Ult-count tracking.** Cut. Partially observable, modest single-input edge.

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

Greeks have natural analogs. **Vega is context-dependent**:

- **Between-round vega** = variance of theo update over the next round outcome (binary).
- **Post-plant vega** = variance over post-plant outcomes (kill / defuse / time-out) — richer state, formula calibrated in Phase 4.

## 5. Architecture

Four layers, each independently buildable:

```
[Ingestion]  →  [State Engine]  →  [Theo Engine]  →  [Quoting / Orders]
```

### 5.1 Ingestion layer

CV/OCR scope is **three broadcast HUD elements only.** Tesseract handles all three (small text, low cadence, high contrast). No ONNX kill-feed CNN, no CTC decoder, no GPU dependency.

| Target | Cadence | Purpose |
|---|---|---|
| Score banner | 250 ms | Score-change events (round/map win) |
| Round-end banner | 100 ms during round-end window | Soft round-outcome commit (~500 ms before scoreboard updates) |
| Bomb-planted icon | 500 ms | Plant/defuse — drives `POST_PLANT_QUOTE` mode + defensive quote-pulling |

Cross-source confirmation rules (collapsed from prior PRD):

| Event type | Confirmation rule | Rationale |
|---|---|---|
| Score change | ≥ 2 sources within 2s window (rib.gg + OCR + Twitter) | Highest blast radius — false score commit corrupts DP root state |
| Bomb plant / defuse | 1 OCR source — soft commit; hard-confirmed by next round-end or score | Bomb-icon CV is high-fidelity; defensive quote-pull is latency-critical |
| Round-end banner | 1 OCR source — soft commit; hard-confirmed by next score update | Banner appears ~500 ms before scoreboard updates; capture the alpha |
| Pre-match lineup, sides | API single-source | No latency pressure |

**Removed from earlier draft:** kill-feed cross-confirmation, numerical-flip events, individual kill events. Those signals are no longer ingested.

Sources:

- **OCR on lowest-latency video stream** (tesseract): three HUD targets above
- **Scoreboard polling**: rib.gg primary (Phase 2 proven). bo3.gg / vlr.gg deferred to Phase 5 robustness work
- **Text listeners**: Twitter API v2 streaming filter on match-related hashtags / accounts (~1–3 s, soft cross-confirmation only). Degrades to no-op without bearer token.

Latency budget per source (approximate):

| Source | Latency | Reliability |
|---|---|---|
| Caster client | ~0 s | N/A (not accessible) |
| YouTube low-latency mode | ~3 s | High |
| Kalshi embedded video | ~3–10 s | Medium |
| Twitch HLS | ~5–15 s | High |
| rib.gg scoreboard polling | 5–60 s post round | Authoritative |
| Twitter/Discord text | ~1–3 s post event | Noisy but fast |

### 5.2 State engine

Single source of truth, in-memory, frozen+slots dataclass:

```python
@dataclass(frozen=True, slots=True)
class MatchState:
    match_id: str
    map_idx: int
    a_map_score: int; b_map_score: int
    a_round: int; b_round: int
    side_orient: str  # 'a_atk' | 'a_def'
    bomb_planted: bool
    attackers_alive: int | None  # only populated when bomb_planted=True
    defenders_alive: int | None  # only populated when bomb_planted=True
    time_left_s: float | None    # only populated mid-round / post-plant
    seq_id: int
    last_updated_ts: float
```

**Removed from earlier draft:** `econ_a/b` (unobservable from broadcast), `ults_a/b` (cut from scope), `players_alive_a/b` (cut from scope — replaced post-plant by `attackers_alive` / `defenders_alive` from a separate HUD widget that's reliably parseable without kill-feed CV).

Versioned via monotonic `seq_id`. Mutators bump seq_id and append to a JSONL event log on disk for replay/debug. Quoting layer only acts on monotonically-increasing seq_ids. No SQLite for live state.

### 5.3 Theo engine

Two timescales, **two clean code paths** — no general mid-round path that depends on noisy state estimates.

**(a) Between-round path.** When `state.is_mid_round=False`, `live_theo` invokes the DP from current state with `round_p` derived from the side baseline (half_win_rates + pistol/anti-eco modifiers from Phase 1). Fully observable scoreboard state suffices — no lookup required.

**(b) Post-plant path.** When `state.bomb_planted=True`, `live_theo` invokes the round-conclusion lookup keyed on `(attackers_alive, defenders_alive, time_remaining_bucket, side, map)`, then propagates that `round_p` through the DP. Calibrated against the Phase 2 dataset filtered to `bomb_planted=True` rounds (~25k samples from the existing 1000-match / 42586-round calibration; subject to Phase 3 verification that the captured `mid_round_states[]` schema includes the required fields — if not, partial Phase 2 ETL re-run scoped to post-plant moments).

**Mid-round, not planted:** `live_theo` returns the between-round theo with degraded confidence; mode selector maps to `IDLE`.

Hierarchical fallback chain (when post-plant cell is sparse):

```
(att, def, time_bucket, side, map)
  → (att, def, side, map)
  → (att, def, side)
  → (att, def)
  → side baseline
```

Bayesian shrinkage cell-to-parent (inherits `SHRINK_PRIOR=15`, `SIGNAL_SCALE=0.10` until ≥100 live matches of paper-trade calibration data exist).

**Live theo (pseudocode):**

```python
def live_theo(state):
    if state.bomb_planted:
        round_p = post_plant_lookup(state.attackers_alive, state.defenders_alive,
                                     time_bucket(state.time_left_s),
                                     state.side_orient, state.map_idx)
    else:
        round_p = side_baseline(state.side_orient, state.map_idx, state.round_idx)
    return dp.value(state, round_p)
```

### 5.4 Quoting / orders

Three-way mode + IDLE per §2.1. No "default MM" — each mode is independently triggered by state.

- **`MM_BETWEEN_ROUND`**: spread = `max(MIN_HALF_SPREAD, k × sqrt(vega_between_round)) + staleness_penalty`. Spread floor must beat Kalshi commission + slippage. `time_since_last_state_update > 2s` → widen aggressively or pull. Skew when adverse-selection risk is high.
- **`DIRECTIONAL_TAKE`**: lift offer / hit bid; portfolio Kelly sizing.
- **`POST_PLANT_QUOTE`**: defensive quote-pull on plant detection (latency-critical, p50 < 200 ms); re-price with post-plant lookup; take if `|theo − market| > POST_PLANT_TAKE_THRESHOLD`; otherwise quote at theo ± narrow spread (high-conviction state, narrower than between-round MM).
- **`IDLE`**: pull all resting quotes, no new orders.

**Two vega definitions, two thresholds:**

- `vega_between_round = round_p × (theo_after_a_win − theo)² + (1 − round_p) × (theo_after_b_win − theo)²` — variance over next round outcome.
- `vega_post_plant`: variance over `{kill, defuse, time-out}` outcomes — TBD formula, calibrate in Phase 4 against observed post-plant theo updates.

The single `VEGA_DIRECTIONAL_THRESHOLD = 0.04` from earlier drafts is **removed**. `DIRECTIONAL_TAKE` triggers on `|theo − market_mid|`, not on vega magnitude — vega only sizes quote width within a mode.

#### Kill switches (all-on, hard-pull all resting quotes)

| Trigger | Action |
|---|---|
| Kalshi API errors / network disconnect | Pull + alert. Always-on. |
| Ingestion staleness > 5 s | Pull until fresh confirmed update resumes. |
| `\|theo − market\| > 20¢` | Pull + alert for human review. Asymmetric: broken-model risk dominates real-edge upside at this magnitude. |
| Rolling Brier > 0.30 over last 50 round predictions | Pull + alert. Catches calibration breaks (roster changes, new map, regime shifts). |

Threshold values (5s, 20¢, 0.30, 50) are initial — re-tune after first 20 live matches of data.

### 5.5 Deployment — hybrid local dev + cloud production

- **Local Windows** (`C:\Users\josep\OneDrive\Desktop\Thunderedge\valorant-pricing-model\`): development, backtesting, paper trading. OneDrive filesystem quirks tolerated here since no live capital.
- **Cloud VM, US-East** (Hetzner CCX13 ~$20/mo recommended; AWS t3.small alternative): live trading. Docker image + SSH deploy. Consistent ~10–20 ms RTT to Kalshi API.
- Promotion gate per §8 — relative Brier + fill-count.

## 6. Inputs — taxonomy

### Tier 1: clean model inputs (model uses these)

- Half-win-rate by team/map/side (`half_win_rates.json`) — between-round + baseline
- Round type / economy (`GUN_WIN_RATE`, pistol/anti-eco modifiers from `match_round_data`) — between-round only
- Bomb plant status — gates between-round vs post-plant code path
- Attackers-alive / defenders-alive — post-plant lookup key (only populated when `bomb_planted=True`)
- Side orientation, map, time-remaining bucket — context keys

### Tier 2: trader intuition only (do NOT model)

Everything previously framed as "Tier 2: model inputs, painful live data" collapses here. The build-cost-vs-edge tradeoff is unfavorable.

- Tilt / momentum / day-of player form
- Coach side-switch reads, anti-strat reads on a return map
- LAN vs. online, crowd
- **Ult counts / utility remaining** (cut from model)
- **Mid-round economy / purchases** (cut from model — not directly observable)
- **Live numerical state from kill feed** (cut — only observable post-plant via attackers/defenders-alive HUD widget)
- Agent comp matchup beyond pre-match map prior

The cut tier comes back only if paper trading shows residual mispricing concentrated in a state the cut signals would have resolved.

## 7. Build phases

In order, smallest-to-largest:

1. ✅ **Generalize Markov DP to arbitrary start state** (Phase 1) — done. Pre-computed lookup. Between-round live pricing works with no new data sources.
2. ✅ **Round-type / economy lookup generalizing `GUN_WIN_RATE`** (Phase 1) — done as part of pistol/anti-eco modeling.
3. ✅ **Round-event data ETL** (Phase 2) — done. 1000 matches / 42586 rounds calibrated. `models/round_conclusion.json` populated.
4. **Live ingestion layer (RESCOPED)** (Phase 3) — rib.gg poller + tesseract OCR on three HUD elements + Twitter soft-confirmation + arbiter (3 deques: score / bomb / round-end). MatchState shrunk to scoreboard + bomb context. Includes rekeying `round_conclusion.json` to post-plant-only with `(att, def, time_bucket, side, map)` keys. **No kill-feed CV. No economy inference. No ult tracking.**
5. **Quoting layer with three-way mode** (Phase 4) — KalshiOrderManager + four-way mode selector + MM_BETWEEN_ROUND quoter + DIRECTIONAL_TAKE + POST_PLANT_QUOTE + portfolio Kelly + four kill switches.
6. **Validation** (Phase 5) — backtest + paper trading with parallel MM and DIRECTIONAL ledgers. Promotion gate per §8.
7. **Deployment** (Phase 6) — Docker + Hetzner VM + secrets + observability.
8. **Operational maturity** (Phase 7) — daily reports + drift detection + incident runbook + portfolio loss limit. **Full covariance-aware portfolio Kelly lives here**, not v1.

OCR-driven VOD labeling (originally "Path B") is **dropped entirely.** Path C (defer mid-round) was the right call all along — it now becomes the explicit chosen design (post-plant only, no general mid-round).

## 8. Success metrics + promotion gate

### Promotion gate (live deploy)

After ≥ 1 full event of paper trading:

1. **Relative Brier:** `Brier(model) < Brier(market_mid) − 0.02` over a 50-round window. Both recorded side-by-side every round prediction. If model Brier ≥ market Brier, the bot has no edge — do not deploy.
2. **Fill-count gate (MM strategy):** if hypothetical MM fills < `MIN_FILLS_PER_MATCH` (initial: 3) averaged over the paper-trade event, **MM is cut from production.** Only `DIRECTIONAL_TAKE` (and `POST_PLANT_QUOTE` if active) promotes to live. The fill-count gate is what makes "MM and DIRECTIONAL run in parallel" architecturally honest.
3. **Latency:** p50 event → state-commit < 500 ms; bomb-detect → quote-pull p50 < 200 ms; quote-cancel p99 < 100 ms.
4. **Zero kill-switch trips for ingestion bugs.** Model-trip kill switches (deviation, Brier) are acceptable; bug-trip kill switches (staleness from broken poller, etc.) are not.

### Ongoing measurements

- **Brier score** of live theo vs. realized outcome, per state-bucket (between-round / post-plant).
- **Adverse-selection rate as MM** (only meaningful if MM survives the gate): % of fills that move against us within 5 s.
- **Quote uptime during live matches**: % of seconds with active quotes (mode ≠ IDLE).
- **Latency**: median + p99 from in-game event → state update → quote refresh.

## 9. Open questions

### Resolved (this PRD, after v2 pivot)

| Decision | Resolution |
|---|---|
| Trading style | Three-way mode + IDLE (`MM_BETWEEN_ROUND` / `DIRECTIONAL_TAKE` / `POST_PLANT_QUOTE` / `IDLE`); MM and directional are first-class peers; paper trade decides |
| Markets in scope | BO3 series + per-map, single canonical DP |
| Mid-round pricing | Two clean code paths — between-round (side baseline) and post-plant (rekeyed lookup); no general mid-round path |
| Ingestion CV scope | Three HUD targets only (score / round-end / bomb-icon); kill-feed / economy / ults explicitly out |
| Sizing | Half-Kelly per-market + per-series aggregate cap (portfolio-aware floor, not full covariance Kelly) |
| Promotion gate | Relative Brier (model < market − 0.02) + fill-count gate (MM cut if thin flow) |
| Kill switches | All four: API errors, staleness > 5 s, deviation > 20¢, rolling Brier > 0.30 |
| Round-conclusion model | Hierarchical lookup, rekeyed to `(att, def, time_bucket, side, map)`, post-plant-only |
| Deployment | Hybrid local dev + cloud production |

### Still TBD (resolve during paper trading)

1. **Bankroll size and per-market exposure cap.** Operational; depends on capital allocation. `PER_MARKET_CAP_FRAC = 0.05` placeholder.
2. **Aggregate cap calibration.** `SERIES_AGGREGATE_CAP_FRAC = 0.10` is a defensive initial guess. After first paper-trade event with real correlation data, recompute from observed inter-market beta.
3. **`TAKE_THRESHOLD`, `MM_MIN_EDGE`, `POST_PLANT_TAKE_THRESHOLD`.** Initial values TBD; calibrate from observed market structure during paper trade.
4. **Kill-switch numerical values** (5 s, 20¢, 0.30, 50-round Brier window) and `MIN_FILLS_PER_MATCH` — initial guesses, re-tune after 20+ live matches.
5. **Vega computation, two contexts.** Between-round vega is well-defined (variance over next round outcome). Post-plant vega TBD — pick a formula in Phase 4, calibrate against observed post-plant theo updates in Phase 5.
6. **Full covariance-aware portfolio Kelly.** Phase 7 maturity work. Per-series correlation matrix from paper-trade data, then recompute sizing under it. The simple aggregate cap is the v1 floor.
7. **Backtest fidelity.** Skipped order-fill backtest in favor of paper trading remains the right call (Kalshi historical order-book unavailability). Reconsider if order-book data becomes available.
8. **Phase 2 dataset completeness for post-plant rekeying.** Phase 3 must verify the captured `mid_round_states[]` schema includes `attackers_alive`, `defenders_alive`, `time_remaining` at bomb-planted moments. If not, partial Phase 2 ETL re-run scoped to post-plant.

## 10. Dependencies

- Existing `theo_engine.py`, `half_win_rates.json`, `match_round_data` table
- Existing `kalshi_client.py` and `market_maker.py` (Kalshi plumbing salvage only)
- rib.gg API for round-by-round events (proven via Phase 2 — 1000-match calibration done)
- Twitter API v2 streaming access (degrade-to-no-op without bearer token)
- Tesseract 5.x system binary for OCR

**Removed from earlier draft:** `vision_parser.py` salvage, ONNX runtime, ONNX kill-feed CNN checkpoint, GPU dependency.

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
| `vision_parser.py` | **DROPPED in v2 pivot** | OCR scope cut to three HUD targets that tesseract handles directly; no salvage needed |
| `market_implied.py` | Skip | Wrong project — kill-line markets, Poisson inversion |
| `map_bidder.py` | Skip — subsumed by single-DP map pricing | Has the same atk/def averaging bug as `series_theo_no_sides` |
| `run_market_maker.py`, `run_quote_bot.py`, `run_map_bidder.py` | Skip | New entry points will be event-driven |

### 12.2 Bugs and rigor issues in `theo_engine.py` (must fix in rewrite)

**Definite bugs:**

1. **Docstring drift in `series_theo_from_map_probs`** (line 343–348): docstring claims `p_map = fallback_q + dw_map * (blended_p - 0.5)` but code does `(1.0 - dw) * fallback_q + dw * blended_p` = `fallback_q + dw * (blended_p - fallback_q)`. The `0.5` should be `fallback_q`.
2. **Three pricing entry points with inconsistent math**: `signal_strength` is applied in `series_theo` and `series_theo_no_sides` but NOT in `series_theo_from_map_probs`. Switching entry points silently changes results. Rewrite as one canonical `live_theo`.
3. **Silent OT-as-coinflip despite "no OT" policy.** The DP loop runs through `range(WIN_THRESHOLD * 2) = range(26)`, and at `total >= 24` it uses `p = 0.5`. Hard-stop at `total = 24` with documented OT-coinflip leaf.

**Modeling rigor concerns:**

4. **Round-win-prob blend is an arithmetic mean** (line 161): `p = (a_rate + (1.0 - b_rate)) / 2.0`. Replace with Bradley-Terry log-odds.
5. **Two-half flat model ignores pistol / anti-eco.** DP assumes constant `p1` for rounds 1–12 and `p2` for 13–24. Round 1 and 13 are pistols (`GUN_WIN_RATE = 0.822`); pistol wins cascade into 2–3 follow-up wins via anti-eco. Largest single modeling gap.
6. **`series_theo_no_sides` averages atk-start and def-start** (line 420). Wrong — starting side is determined by veto, not random.
7. **Hardcoded `[0.05, 0.95]` and `[0.03, 0.97]` clips.** Push to `[0.01, 0.99]` and document.

### 12.3 Rewrite priorities

Phase 1 work (now complete) addressed items 1–5 + 7. Item 6 (veto-determined starting side) is handled by the new `MatchState.side_orient` field flowing through the DP correctly.

---

## Change log

- **2026-04-27** — Initial PRD draft (MM-primary framing, full mid-round CV scope).
- **2026-05-02 — v2 pivot.** Three-way mode + IDLE. Kill-feed / economy / ult tracking cut. Round-conclusion lookup rekeyed to post-plant-only. Portfolio Kelly aggregate cap added. Promotion gate switches from absolute Brier to relative-vs-market + fill-count. `vision_parser.py` salvage dropped.
