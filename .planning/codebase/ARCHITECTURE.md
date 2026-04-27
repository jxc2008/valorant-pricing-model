<!-- refreshed: 2026-04-27 -->
# Architecture

**Analysis Date:** 2026-04-27

> **Implementation status:** This document describes the *intended* architecture from `prd.md` and `roadmap.md`. As of 2026-04-27, `src/` contains only `.gitkeep` placeholders — no Python modules have been written. Salvageable inputs live in `reference/` (read-only). Sections marked **(Planned)** describe target state; sections marked **(Salvaged input)** describe code that exists in `reference/` but is not yet wired in.

## System Overview

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                          Ingestion Layer (Planned)                       │
│  `src/ingestion/`                                                        │
├──────────────────┬──────────────────┬──────────────────┬─────────────────┤
│   OCR / CV       │   Scoreboard     │   Text Listener  │  Cross-Source   │
│  (vision)        │   Polling        │  (Twitter/Disc.) │     Arbiter     │
│ `ocr.py`         │ `scoreboard.py`  │ `text.py`        │ `arbiter.py`    │
│ ~3s latency      │ 5–60s post-round │ ~1–3s, noisy     │ tiered confirm  │
└────────┬─────────┴────────┬─────────┴────────┬─────────┴────────┬────────┘
         │                  │                  │                  │
         └──────────────────┴──────────────────┴──────────────────┘
                                    │
                                    ▼ confirmed updates
┌─────────────────────────────────────────────────────────────────────────┐
│                       State Engine (Planned)                             │
│  `src/state/match_state.py`  —  single source of truth, versioned        │
│  MatchState dataclass: scores, sides, econ, alive, bomb, ults, seq_id    │
│  Mutators bump seq_id; every mutation appended to JSONL event log        │
└────────┬────────────────────────────────────────────────────────────────┘
         │ MatchState (seq_id N)
         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        Pricing Layer (Planned)                           │
│  `src/pricing/`                                                          │
│  ┌─────────────────┐  ┌──────────────────┐  ┌─────────────────────┐   │
│  │  BO3 DP         │  │  Bradley-Terry   │  │ Round-Conclusion    │   │
│  │  `dp.py`        │  │  `blend.py`      │  │ Lookup              │   │
│  │  mmap'd table   │  │                  │  │ `round_conclusion.py│   │
│  └────────┬────────┘  └────────┬─────────┘  └──────────┬──────────┘   │
│           └────────────────────┴────────────────────────┘              │
│                                │                                        │
│                                ▼                                        │
│           SINGLE CANONICAL ENTRY POINT: `live_theo(state)`             │
│           `src/pricing/live_theo.py` → TheoOutput                      │
│           (theo_series, theo_map[i], vega, confidence)                  │
└────────┬────────────────────────────────────────────────────────────────┘
         │ TheoOutput
         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       Quoting Layer (Planned)                            │
│  `src/quoting/`                                                          │
│  ┌──────────────┐  ┌─────────┐  ┌─────────────┐  ┌────────────────┐ │
│  │ Mode Selector│  │   MM    │  │ Directional │  │ Kill Switches  │ │
│  │  `mode.py`   │  │ `mm.py` │  │`directional`│  │ `kill_switches`│ │
│  └──────┬───────┘  └────┬────┘  └──────┬──────┘  └────────┬───────┘ │
│         └────────────────┴───────────────┘                  │         │
│                          │                                   │         │
│                          ▼                                   ▼         │
│              `src/sizing/kelly.py` ──→  KalshiOrderManager           │
│              (half-Kelly + cap)         `quoting/order_manager.py`   │
└────────┬────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Kalshi API v2  (live, RSA PKCS1v15/SHA-256, no sandbox, dry-run gate)  │
└─────────────────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File (Planned) | Status |
|-----------|----------------|----------------|--------|
| OCR/CV ingestion | Score banner, kill feed, bomb icon, ult orbs from low-latency video | `src/ingestion/ocr.py` | Not implemented; ports `vision_parser.py` from thunderedge |
| Scoreboard polling | rib.gg / bo3.gg / vlr.gg authoritative score updates | `src/ingestion/scoreboard.py` | Not implemented |
| Text listener | Twitter/Discord soft signals (~1–3s) | `src/ingestion/text.py` | Not implemented |
| Cross-source arbiter | Enforces tiered confirmation per PRD §5.1 | `src/ingestion/arbiter.py` | Not implemented |
| MatchState | Single source of truth, versioned via `seq_id` | `src/state/match_state.py` | Not implemented |
| BO3 DP | Memoized recursive series-value over `BO3State`, mmap'd to disk | `src/pricing/dp.py` | Skeleton lives in `reference/theo_engine.py` (`_markov_map_win`); has documented bugs (PRD §12.2) |
| Bradley-Terry blend | `p = a(1-b) / (a(1-b) + (1-a)b)` round-win blend | `src/pricing/blend.py` | Not implemented; replaces audited arithmetic mean bug |
| Round-type model | Pistol + anti-eco probability inputs for rounds 1,2,3,13,14,15 | `src/pricing/round_types.py` | Not implemented |
| Round-conclusion lookup | Hierarchical lookup `(num_diff, bomb, side, econ, map)` with Bayesian shrinkage | `src/pricing/round_conclusion.py` | Not implemented; blocked on Phase 2 data |
| `live_theo` | THE single canonical entry point: state → (theo_series, theo_map, vega, confidence) | `src/pricing/live_theo.py` | Not implemented |
| KalshiOrderManager | Place/cancel/reconcile orders, dry-run gate, error-streak retry | `src/quoting/order_manager.py` | Salvage from `reference/market_maker.py` (lines around `Quote`, `_place_quote`, `_cancel_quote`, `cancel_all_orders`) |
| Mode selector | Pure function: state + vega → `'MM'` or `'DIRECTIONAL'` | `src/quoting/mode.py` | Not implemented |
| MM quoter | Quote `theo ± vega-scaled spread` | `src/quoting/mm.py` | Not implemented |
| Directional taker | Lift offer / hit bid when `|theo − market| > threshold` | `src/quoting/directional.py` | Not implemented |
| Kill switches | Four always-on predicates over `(state, theo, market, brier_window)` | `src/quoting/kill_switches.py` | Not implemented |
| Kelly sizer | `f = 0.5 × kelly_full`, capped at `PER_MARKET_CAP_FRAC` | `src/sizing/kelly.py` | Not implemented |
| Constants | All thresholds and magic numbers | `src/config/constants.py` | Not implemented; values listed in `CLAUDE.md` lines 67–87 |
| Utilities (salvaged) | American↔implied prob, vig removal | `reference/odds_utils.py` | Salvaged as-is; reused unchanged |
| Fair-value baseline (salvaged) | IID BO3 closed-form `p²(3-2p)`, used as `fallback_q` | `reference/fair_value.py` | Salvaged as-is |

## Pattern Overview

**Overall:** **Layered event-driven pipeline** with a single canonical pricing entry point and a state-centric data model.

**Key Characteristics:**

- **Unidirectional data flow.** Ingestion → State → Pricing → Quoting. No back-edges. Pricing never mutates state; quoting never mutates pricing.
- **Single source of truth.** `MatchState` is the only place runtime state lives. In-memory + JSONL event log on disk for replay/debug. **No SQLite for live state** (CLAUDE.md "Differences" §).
- **Single canonical pricing path.** One function — `live_theo(state) → TheoOutput` — replaces the 3-entry-point sprawl (`series_theo` / `series_theo_no_sides` / `series_theo_from_map_probs`) of the audited engine. No two functions doing the same thing differently.
- **Single DP, marginalized.** BO3 series winner and per-map winner are derived from the *same* DP. `theo_series` reads the DP at the root; `theo_map[i]` marginalizes the DP over future map outcomes. Mathematically arb-free by construction.
- **Hybrid trading mode.** MM by default; flip to directional on event triggers (numerical imbalance, bomb plant, map point, score 12-12 / 1-1 decider) OR vega override.
- **Always-on kill switches.** Four predicates (Kalshi API errors, ingestion staleness > 5s, `|theo − market| > 20¢`, rolling Brier > 0.30 over 50 rounds) evaluated every cycle. **No flag to disable individual switches.**
- **Tiered ingestion confirmation.** Different event types require different cross-source rules (PRD §5.1). Score updates need ≥2 sources within 2s; mid-round events commit on 1 CV source if kill-feed cross-confirms.
- **Dry-run by default.** Live trading requires explicit `--live` flag at the CLI entry point. Not a constructor arg, not an env var.
- **Strict typing on the math layer.** `mypy --strict` runs on `src/pricing/`. The rest of the tree is gradual.

## Layers

**Ingestion Layer (Planned):**
- Purpose: Convert real-world signals (video frames, HTTP polls, text streams) into versioned state updates with provenance metadata.
- Location: `src/ingestion/`
- Contains: OCR/CV pipeline, scoreboard scrapers, text listeners, cross-source arbiter
- Depends on: `src/config/constants.py` (latency thresholds), external APIs (rib.gg, bo3.gg, vlr.gg, YouTube stream, Twitter/Discord)
- Used by: State Engine (only confirmed updates pass through arbiter)

**State Engine (Planned):**
- Purpose: Single in-memory source of truth for the active match. Versioned, append-only event log on disk.
- Location: `src/state/`
- Contains: `MatchState` dataclass, mutators that bump `seq_id`, JSONL writer
- Depends on: nothing (pure data layer, no I/O except event-log append)
- Used by: Pricing layer (reads), Quoting layer (reads `seq_id` for monotonicity check)

**Pricing Layer (Planned):**
- Purpose: Compute `live_theo(state) → TheoOutput`. The math layer.
- Location: `src/pricing/`
- Contains: BO3 DP, Bradley-Terry blend, round-type model, round-conclusion lookup, vega computation, `live_theo` entry point
- Depends on: `src/state/`, `src/config/`, `data/half_win_rates.json`, `models/dp_table.pkl` (generated)
- Used by: Quoting layer
- **Constraint:** Must pass `mypy --strict`.

**Quoting Layer (Planned):**
- Purpose: Translate `TheoOutput` + market data into Kalshi orders. Apply mode selection, sizing, kill switches.
- Location: `src/quoting/`
- Contains: `KalshiOrderManager`, mode selector, MM quoter, directional taker, kill switches, order lifecycle reconciliation
- Depends on: `src/sizing/`, `src/config/`, Kalshi API v2 client
- Used by: CLI entry point (`python -m src.main`)

**Sizing Layer (Planned):**
- Purpose: Position-size computation. Half-Kelly with per-market cap.
- Location: `src/sizing/`
- Contains: `kelly.py` (`kelly_size(theo, market_yes_ask, bankroll) → contracts`)
- Depends on: `src/config/constants.py` (`KELLY_MULTIPLIER`, `PER_MARKET_CAP_FRAC`)
- Used by: Quoting layer (both MM and directional)

**Config Layer (Planned):**
- Purpose: Single home for every threshold and magic number. CLAUDE.md rule #12.
- Location: `src/config/constants.py`
- Contains: pricing constants, sizing constants, kill-switch thresholds, mode-flip thresholds
- Depends on: nothing
- Used by: every other layer

**Reference (Salvaged input — read-only):**
- Purpose: Source code from sibling `thunderedge/worktrees/market-maker/` to be partially salvaged into `src/`.
- Location: `reference/`
- Contains: `odds_utils.py` (use as-is), `fair_value.py` (use as-is, becomes `fallback_q` baseline), `theo_engine.py` (DP skeleton only — has documented bugs in PRD §12.2), `market_maker.py` (extract Kalshi plumbing only)
- **NOT a layer.** Inputs to Phase 1 / Phase 4 work, not part of the runtime architecture.

## Data Flow

### Primary Request Path (Live Re-Pricing on State Change)

1. **Observable in-game event** (e.g., kill, bomb plant, score change). Captured by one or more ingestion sources at `t_observed` (`src/ingestion/{ocr,scoreboard,text}.py` — Planned).
2. **Source emits raw event** to a pending-updates queue with timestamps `t_observed`, `t_ingested` (`src/ingestion/arbiter.py` — Planned).
3. **Cross-source arbiter** applies tiered confirmation rules per PRD §5.1. If confirmed → confirmed-updates queue; if not → quarantined log (`src/ingestion/arbiter.py` — Planned).
4. **State mutator** ingests the confirmed update, bumps `seq_id`, appends to JSONL event log, writes new `MatchState` (`src/state/match_state.py` — Planned).
5. **Pricing dispatch.** Quoter observes `seq_id` change and calls `live_theo(state)` (`src/pricing/live_theo.py` — Planned).
6. **DP lookup.** `live_theo` reads pre-computed DP table from `models/dp_table.pkl` (mmap'd) for the post-A-win and post-B-win successor states (`src/pricing/dp.py` — Planned).
7. **Round probability.** If mid-round, `round_conclusion.py` lookup; if between rounds, side/map/econ baseline blended via `blend.py` Bradley-Terry. Pistol/anti-eco rounds (1,2,3,13,14,15) use round-type-specific inputs from `round_types.py`.
8. **Theo composition.** `theo = round_p × dp[after_a_wins] + (1 − round_p) × dp[after_b_wins]`. Compute vega = variance of next theo update. Compute confidence from data weight.
9. **Mode selection.** `trading_mode(state, vega)` returns `'MM'` or `'DIRECTIONAL'` (`src/quoting/mode.py` — Planned).
10. **Kill-switch check.** All four predicates evaluated. If ANY trips → cancel all resting quotes, alert, exit cycle (`src/quoting/kill_switches.py` — Planned).
11. **Quote / take.** MM quoter computes spread; OR directional taker fires at market. Sized by `kelly_size(...)`. Submitted via `KalshiOrderManager` with `dry_run` flag honored (`src/quoting/order_manager.py` — Planned).
12. **End-to-end latency target:** < 500 ms (event → updated theo). Quote-cancel target: < 100 ms (state change → stale orders pulled). Per-event timestamps (`t_observed`, `t_ingested`, `t_arbited`, `t_state_committed`, `t_theo_computed`, `t_quote_sent`) logged for instrumentation.

### Pre-Compute Path (Offline, Phase 1)

1. `scripts/build_dp_table.py` (Planned) loads `data/half_win_rates.json`.
2. Walks every reachable `BO3State` via `series_value(...)` with memoized recursion (`@functools.lru_cache(maxsize=None)`).
3. Pickles the cache to `models/dp_table.pkl` (~10MB).
4. Live process mmaps the table on startup for sub-millisecond reads.

### Round-Event Data Path (Offline, Phase 2)

1. `scripts/probe_round_events.py` (Planned) hits rib.gg / bo3.gg endpoints for 5 known matches.
2. **Decision gate (Phase 2.1):** if APIs expose round-level events → Path A (3 days, pull 500+ matches into `data/round_events`); if not → Path B (2 weeks, OCR-driven VOD labeling); if neither → Path C (defer round-conclusion model, `round_conclusion` returns fixed `p = 0.5`).
3. Calibrated cells written under `models/round_conclusion.json`.

### Mode-Flip Path

Triggered every state update inside the quoting cycle:

1. **Event triggers (primary):** numerical imbalance ≥ 1, bomb planted, map-point round, score 12-12 / 1-1 decider → `'DIRECTIONAL'`
2. **Vega override (fallback):** `vega > VEGA_DIRECTIONAL_THRESHOLD` → `'DIRECTIONAL'` regardless of event flags
3. **Reset to MM:** at round end + side count returns to 5v5 + no event flags active

**State Management:**
- `MatchState` is the single source of truth. In-memory dataclass. Versioned via monotonically increasing `seq_id`.
- Quoting layer only acts on monotonically increasing `seq_id` — defends against out-of-order updates.
- Every mutation appended to a JSONL event log on disk (cheap, useful for replay/debug). **No SQLite for live state.**
- DP table (`models/dp_table.pkl`) and round-conclusion lookup (`models/round_conclusion.json`) are read-only at runtime — generated by offline scripts.

## Key Abstractions

**`MatchState` (Planned, `src/state/match_state.py`):**
- Purpose: Frozen-at-a-point-in-time snapshot of the live match.
- Fields (per roadmap §3.1): `match_id`, `map_idx`, `a_map_score`, `b_map_score`, `a_round`, `b_round`, `side_orient` (`'a_atk'`/`'a_def'`), `econ_a`, `econ_b`, `ults_a`, `ults_b`, `players_alive_a`, `players_alive_b`, `bomb_planted`, `time_left_s`, `seq_id`, `last_updated_ts`.
- Pattern: dataclass with mutator methods that bump `seq_id` and append to JSONL.

**`BO3State` (Planned, `src/pricing/dp.py`):**
- Purpose: DP key. Frozen tuple suitable for `lru_cache`.
- Fields: `(map_idx, a_map_score, b_map_score, a_round, b_round, side_orient, map_pool)` plus economy memory for round-type-aware DP transitions (Phase 1.3).

**`TheoOutput` (Planned, `src/pricing/live_theo.py`):**
- Purpose: Return value of the canonical pricing entry point.
- Fields: `theo_series: float`, `theo_map: dict[int, float]`, `vega: float`, `confidence: float`.

**`Quote` (Salvaged from `reference/market_maker.py` line 35):**
- Purpose: One resting limit order's tracking record.
- Fields: `ticker`, `side` (`'yes'`/`'no'`), `action` (`'buy'`/`'sell'`), `price` (cents 1–99), `count`, `order_id`, `placed_at`.

**Round-conclusion lookup (Planned, `src/pricing/round_conclusion.py`):**
- Purpose: Hierarchical lookup table mapping mid-round state → P(team A wins this round).
- Pattern: nested dict with Bayesian-shrinkage fallback chain `(num_diff, bomb, side, econ, map) → (num_diff, bomb, side, map) → (num_diff, bomb, side) → (num_diff, bomb) → side baseline`.

## Entry Points

**`python -m src.main --match <ticker>` (Planned):**
- Location: `src/main.py` (Planned, not yet created)
- Triggers: human operator starts a live trading session
- Responsibilities: bootstrap config, instantiate ingestion sources, instantiate `MatchState`, wire pricing + quoting, enter event loop. **Defaults to dry-run.**

**`python -m src.main --match <ticker> --live` (Planned):**
- Same as above but with live order placement enabled. **Only after paper-trade promotion gate is met** (PRD §5.5: backtest Brier < threshold + ≥1 full event paper-trade with target metrics).

**`scripts/build_dp_table.py` (Planned):**
- Offline pre-compute of the DP lookup table. Run once per pricing-model version. Output: `models/dp_table.pkl`.

**`scripts/probe_round_events.py` (Planned):**
- Phase 2.1 API scoping probe. Decision gate for round-conclusion model.

## Architectural Constraints

- **Threading:** Async event-driven (target). Each ingestion source is its own producer; the arbiter is the single consumer feeding the state engine. The pricing+quoting cycle runs on every confirmed `seq_id` bump. Specific async runtime (`asyncio` vs threads) is unspecified in PRD/roadmap — to be decided in Phase 3.
- **Global state:** `MatchState` is in-memory and effectively a singleton per match. No module-level mutable singletons elsewhere. DP table and round-conclusion lookup are read-only (loaded once at startup).
- **No SQLite for live state.** Existing thunderedge repo uses SQLite; this repo deliberately does not (CLAUDE.md "Differences" §). SQLite remains acceptable for offline dataset cache.
- **No imports from `thunderedge/`.** This is a separate project that builds on artifacts but does not import from the sibling repo (CLAUDE.md line 5).
- **No imports from `reference/`** at runtime. Salvageable code is copied into `src/` (with bug fixes), not imported across the boundary.
- **`mypy --strict` on `src/pricing/`.** The math layer must type-check fully. Other layers are gradual.
- **Dry-run is enforced via CLI flag, not constructor arg** (CLAUDE.md "Differences" §). Differs from audited `MarketMaker.__init__(dry_run=True)`.
- **No magic numbers in business logic.** Every threshold lives in `src/config/constants.py` (CLAUDE.md rule #12).
- **No sandbox for Kalshi.** Bot stays in `dry_run=True` until paper-trading gate is met (CLAUDE.md "Data sources" table).

## Anti-Patterns

### Three parallel pricing entry points

**What happens:** Audited `theo_engine.py` (in `reference/`) exposes `series_theo`, `series_theo_no_sides`, and `series_theo_from_map_probs` — three callers, inconsistent math. `signal_strength` is applied in two but not the third (PRD §12.2 bug #2).
**Why it's wrong:** Switching entry point silently changes results. Callers with the same intent get different numbers depending on which they happen to call.
**Do this instead:** **Single canonical `live_theo(state) → TheoOutput`** in `src/pricing/live_theo.py` (Planned). Marginalize the DP for per-map theo — never expose a second pricing function.

### Arithmetic-mean round-win blend

**What happens:** Audited `theo_engine.py` line 161 uses `p = (a_rate + (1 − b_rate)) / 2` (PRD §12.2 bug #4).
**Why it's wrong:** Under-weights compounding edges. A team with `(0.7, 0.3)` rates should resolve to `~0.84`, not `0.70`.
**Do this instead:** Bradley-Terry log-odds blend in `src/pricing/blend.py` (Planned): `p = a*(1-b) / (a*(1-b) + (1-a)*b)`. CLAUDE.md rule #3.

### Constant `p1`/`p2` per half ignoring pistols

**What happens:** Audited DP uses constant `p1` for rounds 1–12 and constant `p2` for 13–24 (PRD §12.2 bug #5).
**Why it's wrong:** Rounds 1 and 13 are pistols (`GUN_WIN_RATE = 0.822`), and a pistol win cascades into 2–3 follow-up wins via anti-eco. **Largest single modeling gap.**
**Do this instead:** State-augmented DP in `src/pricing/round_types.py` (Planned) with explicit probability inputs for rounds 1, 2, 3, 13, 14, 15. CLAUDE.md rule #4.

### Silent OT-as-coinflip

**What happens:** Audited `_markov_map_win` runs the DP loop through `range(WIN_THRESHOLD * 2) = range(26)`, and at `total >= 24` it uses `p = 0.5` (PRD §12.2 bug #3).
**Why it's wrong:** CLAUDE.md says no OT modeling, but the DP silently models OT as a coinflip. Documentation and code disagree.
**Do this instead:** Hard-stop at `total = 24` with an explicit `0.5 × value(after_a_OT_win) + 0.5 × value(after_b_OT_win)` leaf, documented in code (roadmap §1.4). CLAUDE.md rule #5.

### Non-marginalized per-map pricing

**What happens:** A second model (e.g., audited `map_bidder.py`) prices map markets independently of the series DP.
**Why it's wrong:** The two models can disagree → quotes can internally cross → arb against ourselves.
**Do this instead:** Per-map theo is computed by marginalizing the *same* DP that produces series theo (`src/pricing/live_theo.py` — Planned). CLAUDE.md rule #2.

### Hardcoded conviction clips

**What happens:** Audited engine uses hardcoded `[0.05, 0.95]` and `[0.03, 0.97]` clips (PRD §12.2 bug #7).
**Why it's wrong:** Invisible bounds on conviction; tighter than necessary.
**Do this instead:** Use `[0.01, 0.99]` and document any tighter clip explicitly. CLAUDE.md rule #6.

### Constructor-arg dry-run

**What happens:** Audited `MarketMaker.__init__(..., dry_run=True)` makes dry-run a per-instance flag.
**Why it's wrong:** Easy to flip to live by editing one line. Hard to grep for "is this run live?"
**Do this instead:** Dry-run is enforced via a CLI flag at the entry point (`python -m src.main` defaults to dry-run; `--live` opts in). CLAUDE.md rule #13 + "Differences" §.

### Configurable kill switches

**What happens:** A flag like `--disable-staleness-check`.
**Why it's wrong:** Kill switches exist precisely because the model can be wrong. Disabling them defeats the safety layer.
**Do this instead:** All four kill switches are always-on. No flag to disable individual switches. CLAUDE.md rule #9.

### Full Kelly sizing

**What happens:** Position size = `kelly_full × bankroll`.
**Why it's wrong:** Theo miscalibration during the model's learning period blows up bankroll. Half-Kelly preserves ~75% of long-run growth at ~25% of variance.
**Do this instead:** `f = 0.5 × kelly_full`, capped at `PER_MARKET_CAP_FRAC` of bankroll, in `src/sizing/kelly.py` (Planned). CLAUDE.md rule #7.

## Error Handling

**Strategy:** Defensive at the I/O boundary; fail-loud in the math layer.

**Patterns:**

- **Kalshi API errors:** kill switch trips → cancel all resting quotes → alert. Salvage error-streak retry from `reference/market_maker.py` (`_MAX_ERRORS_BEFORE_PAUSE = 3`, `_ERROR_PAUSE_SECONDS = 60`).
- **Ingestion staleness:** `time_since_last_state_update > 5s` → kill switch trips → pull quotes until fresh confirmed update resumes.
- **Theo / market deviation:** `|theo − market| > 20¢` → kill switch trips + human-review alert. Asymmetric: at this magnitude, broken-model risk dominates real-edge upside.
- **Brier breach:** rolling Brier > 0.30 over last 50 round predictions → kill switch trips + alert. Catches calibration breaks (roster changes, new map, regime shifts).
- **Quarantined updates:** failed cross-source confirmation → logged but not committed. Never silently dropped.
- **Order lifecycle drift:** every poll cycle reconciles in-memory `_active_quotes` against Kalshi's open-orders endpoint. If Kalshi has an order we don't track → cancel. If we think we have a quote but Kalshi doesn't → drop our reference.

## Cross-Cutting Concerns

**Logging:**
- Structured JSON logs to stdout (target — Phase 6.5).
- Every event carries timestamps at each pipeline stage: `t_observed`, `t_ingested`, `t_arbited`, `t_state_committed`, `t_theo_computed`, `t_quote_sent`.
- Logs land in `logs/` locally; shipped to Loki / Grafana Cloud free tier in production.

**Validation:**
- Cross-source arbiter (`src/ingestion/arbiter.py` — Planned) is the validation chokepoint for ingestion.
- Conviction clips `[0.01, 0.99]` at pricing boundaries.
- Property tests (Phase 5.1) on the DP: value ∈ [0, 1] for any state; monotonic in `round_p`; `theo_series` consistent with `theo_map[]`; Bradley-Terry symmetric.

**Authentication:**
- Kalshi API v2 uses RSA PKCS1v15/SHA-256. Private key file mounted as Docker secret in production (Phase 6.4); **never** in image, **never** in env vars.
- `.env` for non-sensitive config only. `.gitignore` blocks `.env`, `.env.*`, `*.key`, `*.pem`, `valorant*.txt`.

**Configuration:**
- Single `src/config/constants.py` (Planned) with every threshold from `CLAUDE.md` lines 67–87.
- Threshold-tuning is a Phase 5 activity (after 20+ live matches); ship with initial values, never hardcode in business logic.

**Observability (Planned, Phase 6.6):**
- Grafana dashboard with: theo vs market over time, fill rate, current inventory, kill-switch trip log, latency p50/p99, daily P&L.

---

*Architecture analysis: 2026-04-27*
