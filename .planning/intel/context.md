# Context (Intel)

Background, framing, and topical notes from the source docs. Verbatim with attribution where useful.

---

## Project relationship to thunderedge/

- source: prd.md §1, §10; roadmap.md (general); CLAUDE.md (project instructions)
- topic: separation from parent repo
- This is a **separate project** from `thunderedge/`. It builds on artifacts from `thunderedge/worktrees/market-maker/` but does NOT import from it. The thunderedge repo has its own CLAUDE.md with different conventions for that codebase. The original worktree is untouched and continues to function for pre-match BO3 quoting.

## Origin problem statement

- source: prd.md §1
- topic: motivation
- The existing `theo_engine.py` (in `thunderedge/worktrees/market-maker/backend/`) prices BO3 series winners pre-match using a Markov DP over team/map/side half-win-rates. Once the match starts, the only signal that updates is the scoreboard — every other piece of state (numerical advantage, bomb plant, economy, ult counts) is invisible to the pricer. This project builds a live pricing model that re-prices the series at any moment during a match, on Kalshi, fast enough to either capture edge or — at minimum — avoid being adversely selected.

## Conceptual framing — Black-Scholes analog

- source: prd.md §4
- topic: model intuition
- Mapping the five BS inputs to event-market analogs:
  - Strike: always 50¢ for binary YES/NO (not used)
  - Expiry: rounds/maps to series resolution (theta-decay is real)
  - Underlying: true P(team A wins series) (what we model)
  - Rate: ~0 on Kalshi (not used)
  - Volatility: how fast P(win) can swing per round (most underrated input)
- No closed-form solution. Right framing is recursive expectation: `P(series | now) = E[P(series | next state)]`. Pre-match Markov DP already does this from `(0,0)`; live pricing is the same DP started from arbitrary state.
- Greeks have natural analogs: delta = ∂P(series)/∂P(round); gamma = curvature, peaks near 12-12 / 1-1 maps; vega = sensitivity to round-win-prob estimate (drives quote width); theta = drift toward 0/100 as rounds tick.

## Architecture overview

- source: prd.md §5
- topic: layer composition
- Four layers, each independently buildable:
  ```
  [Ingestion] → [State Engine] → [Theo Engine] → [Quoting / Orders]
  ```

## Inputs taxonomy — three tiers

- source: prd.md §6 ("Inputs — taxonomy")
- topic: feature inclusion policy
- **Tier 1 (clean model inputs, fold into round_p):** half-win-rate by team/map/side; round type/economy state (generalize `GUN_WIN_RATE = 0.822` into a lookup over `(econ_a, econ_b, side, map)`); player numerical state (5v5, 5v4, 4v3, 1v3) — biggest single in-round factor; bomb plant status pre/post-plant per side; pistol / anti-eco / conversion modifiers.
- **Tier 2 (model inputs, painful live data):** ult counts per team (need CV on HUD orb tracker); utility remaining mid-round (proxy via abilities-used in kill feed); agent comp matchup on the map.
- **Tier 3 (trader intuition only — do NOT model):** tilt / momentum; day-of player form; coach side-switch reads; anti-strat reads on a return map; LAN vs online, crowd.

## Latency budget per source

- source: prd.md §5.1
- topic: ingestion source profile
- | Source | Latency | Reliability |
- |---|---|---|
- | Caster client | ~0s | N/A (not accessible) |
- | YouTube low-latency mode | ~3s | High |
- | Kalshi embedded video | ~3–10s | Medium |
- | Twitch HLS | ~5–15s | High |
- | Scoreboard scrapers | 5–60s post round | Authoritative |
- | Twitter/Discord text | ~1–3s post event | Noisy but fast |

## Salvage from audited engine

- source: prd.md §12.1
- topic: code reuse from `thunderedge/worktrees/market-maker/`
- Salvageable files copied into `valorant-pricing-model/reference/` and `valorant-pricing-model/data/`. Per-file disposition:
  - `odds_utils.py` — salvage as-is, reused unchanged
  - `fair_value.py` — salvage as-is, used as `fallback_q` baseline for no-data states
  - `half_win_rates.json` — salvage as-is, direct input to the new DP
  - `theo_engine.py` — partial; keep DP skeleton, rewrite the rest (see DEC-009 / DEC-010 / REQ-pistol-anti-eco-modeling and bug list below)
  - `market_maker.py` — partial; extract Kalshi plumbing into `KalshiOrderManager`. The 10s poll loop, single quoting mode, and pre-veto var mutation are obsolete
  - `market_implied.py` — skip (wrong project; kill-line markets, Poisson inversion)
  - `map_bidder.py` — skip (subsumed by single-DP map pricing; has same atk/def averaging bug as `series_theo_no_sides`)
  - `run_market_maker.py`, `run_quote_bot.py`, `run_map_bidder.py` — skip (new entry points are event-driven)

## Documented bugs in audited `theo_engine.py`

- source: prd.md §12.2
- topic: bugs the rewrite must fix
- **Definite bugs:**
  1. Docstring drift in `series_theo_from_map_probs` (line 343-348) — docstring references `0.5` where code uses `fallback_q`.
  2. Three pricing entry points apply `signal_strength` inconsistently (`series_theo` and `series_theo_no_sides` apply it; `series_theo_from_map_probs` does not). Switching entry points silently changes results.
  3. Silent OT-as-coinflip despite "no OT" policy. `_markov_map_win` runs DP loop through `range(WIN_THRESHOLD * 2) = range(26)`; at `total >= 24` uses `p = 0.5`. Either change the policy or stop the loop at `total = 24`.
- **Modeling rigor concerns:**
  4. Round-win-prob blend is an arithmetic mean (line 161) — replace with Bradley-Terry log-odds.
  5. Two-half flat model ignores pistol/anti-eco — DP assumes constant `p1` for rounds 1-12 and `p2` for 13-24, but rounds 1, 2, 3, 13, 14, 15 deserve explicit modeling. Largest single modeling gap.
  6. `series_theo_no_sides` averages atk-start and def-start (line 420) — wrong; starting side is determined by veto, not random.
  7. Hardcoded `[0.05, 0.95]` and `[0.03, 0.97]` clips — invisible bounds on conviction. Push to `[0.01, 0.99]` and document.

## Open questions still TBD

- source: prd.md §9 ("Still TBD (resolve after data exists)")
- topic: deferred decisions
1. **Bankroll size and per-market exposure cap.** Operational, depends on capital allocation decision.
2. **Numerical thresholds.** `VEGA_DIRECTIONAL_THRESHOLD`, kill-switch values (5s, 20¢, 0.30, 50-round Brier window) — initial guesses; re-tune after 20+ live matches.
3. **Vega computation formula.** Three defensible variants: (a) variance under round-outcome distribution only, (b) variance including ingestion-noise term, (c) bootstrap over recent calibration error. Roadmap §1.6 picks (a) initially.
4. **Backtest fidelity.** Replaying past matches against historical market prices requires either order-book replay (Kalshi may not provide) or a synthetic counterparty. Roadmap §5.2 chooses to skip order-fill backtest in favor of paper trading.

## Out of scope (explicit non-goals)

- source: prd.md §3, §11
- topic: explicit exclusions
- Beating tier-1 caster-API bots on absolute speed.
- OT modeling — note: PRD §3 lists this as a non-goal "(excluded everywhere per existing repo convention)" but PRD §12.2 #3 and roadmap.md §1.4 prescribe explicit hard-stop at total=24 with documented OT-as-coinflip leaf. Reconciled framing: the model does not attempt to *predict OT outcomes*; it documents the leaf as a coinflip rather than letting the DP silently run with `p=0.5` past round 24. See INGEST-CONFLICTS.md INFO bucket.
- Player-level prop pricing (kill-line track).
- Modeling tilt, day-of form, coach reads, crowd.
- BO5 series modeling.
- Pick/ban model (handled by pre-match `pickban_prediction`).
- Player kill-line markets.

## Build phases (PRD framing — pre-roadmap)

- source: prd.md §7
- topic: PRD-level phase ordering
- 1. Generalize Markov DP to arbitrary start state. ~1 day. Immediate value: between-round live pricing, no new data sources.
- 2. Round-type / economy lookup generalizing `GUN_WIN_RATE`. Pull from existing `match_round_data`. ~1 day.
- 3. Cross-source state arbiter wrapping `vision_parser` + scoreboard polling. ~3–5 days. The latency-defense layer.
- 4. Scope rib.gg / bo3.gg round-event APIs. Decision gate.
- 5. Round-conclusion model (conditional on phase 4).
- 6. Ult tracking last — high effort, modest single-input edge.
- Note: roadmap.md operationalizes these into 8 phases (0–7) with finer granularity. PRD's phases 1–3 turn the pre-match engine into a live engine with no new data sources.

## Critical-path / timeline summary

- source: roadmap.md (Critical path summary)
- topic: timeline
- Realistic total: 4–6 weeks of build time, then 2 weeks paper trading before going live.
- ~7–8 weeks calendar end-to-end if Phase 2 hits the API path; ~10–12 weeks if OCR labeling is needed.
- Earliest revenue: between-round live MM after ~3 weeks if Phases 1, 3, 4 ship with `round_conclusion` deferred (Path C).

## Data sources summary

- source: prd.md §10; CLAUDE.md (project instructions)
- topic: external dependencies
- | Source | Use | Latency | Notes |
- | `data/half_win_rates.json` | Pre-match per-team/map/side rates | offline | Generated by `thunderedge/worktrees/half-win-rate/`; recompute upstream when needed. |
- | rib.gg internal API | Round-by-round events for round-conclusion model | offline | No public REST. Routes via `FlynV/RIB.GG-Web-Scraper` or `{valorantr}` R package. Phase 2.1 scoping required. |
- | bo3.gg API | Backup match data | offline | Filter params broken — use slug endpoint only. |
- | Kalshi API v2 | Live market quotes + order placement | live | RSA PKCS1v15/SHA-256 auth. Key in `.env`. No sandbox — bot stays in `dry_run=True` until paper-trade promotion gate is met. |
- | YouTube low-latency stream | Primary visual feed for OCR | ~3s | Lowest latency public source. |
- | Twitter/Discord match threads | Soft cross-confirmation | ~1–3s | Never sole-source. |

## Success metrics

- source: prd.md §8
- topic: validation criteria
- Brier score of live theo vs. realized outcome (per-state, bucketed by time-to-resolution)
- Adverse-selection rate as MM (% of fills that move against us within 5s)
- Quote uptime during live matches (% of seconds with active quotes)
- Latency: median + p99 from in-game event → state update → quote refresh
