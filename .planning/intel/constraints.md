# Constraints (Intel)

Technical constraints, NFRs, and contracts. Sourced from PRD/SPEC; per-doc precedence applied (SPEC > PRD where both speak; here the SPEC operationalizes PRD without contradiction except on naming — see `INGEST-CONFLICTS.md` WARNINGS).

---

## CON-mypy-strict-pricing
- source: roadmap.md §0.2
- type: nfr
- statement: `mypy --strict` enforced on `src/pricing/`. The math layer must type-check.

## CON-no-magic-numbers
- source: roadmap.md §0.4
- type: nfr
- statement: Every magic number from PRD lives in `config/constants.py`. Threshold-tuning is a Phase 5 activity; ship initial values, never hardcode in business logic.

## CON-dry-run-default
- source: prd.md §5.5; CLAUDE.md critical rule #13 (project instructions encoding PRD intent)
- type: nfr
- statement: Bot defaults to `dry_run=True`. Live trading requires explicit `--live` CLI flag at the entry point. Promotion to live is gated by paper-trade results (DEC-020).

## CON-live-state-no-sqlite
- source: roadmap.md §0.3
- type: schema
- statement: Live state is in-memory only. SQLite is reserved for the dataset cache. Live state persists to disk only as JSONL event logs (replay/debug).

## CON-single-canonical-live-theo
- source: prd.md §6, §12.3
- type: api-contract
- statement: One function `live_theo(state) → TheoOutput`. No parallel pricing entry points. No `series_theo` / `series_theo_no_sides` / `series_theo_from_map_probs` triplet.

## CON-bo3-dp-signature
- source: roadmap.md §1.1
- type: api-contract
- statement: `series_value(state: BO3State, round_p_fn: Callable[[BO3State], float]) → float` where `BO3State = (map_idx, a_map_score, b_map_score, a_round, b_round, side_orient, map_pool)`. Memoized recursion; cache persisted to `models/dp_table.pkl`, mmap-loaded.

## CON-theo-output-schema
- source: roadmap.md §1.6
- type: schema
- statement: `TheoOutput` dataclass: `theo_series: float`, `theo_map: dict[int, float]`, `vega: float`, `confidence: float` (0..1, data_w-based).

## CON-match-state-schema
- source: prd.md §5.2; roadmap.md §3.1
- type: schema
- statement: `MatchState` fields: `match_id: str, map_idx: int, a_map_score: int, b_map_score: int, a_round: int, b_round: int, side_orient: str ('a_atk' | 'a_def'), econ_a: int, econ_b: int, ults_a: int, ults_b: int, players_alive_a: int, players_alive_b: int, bomb_planted: bool, time_left_s: float, seq_id: int, last_updated_ts: float`. Versioned via monotonic `seq_id`.

## CON-bradley-terry-formula
- source: prd.md §12.2 #4; roadmap.md §1.2
- type: api-contract
- statement: `round_p(a, b) = (a*(1-b)) / (a*(1-b) + (1-a)*b)` with `a, b ∈ [1e-6, 1-1e-6]`.

## CON-conviction-clip
- source: prd.md §12.2 #7
- type: api-contract
- statement: Probability outputs clipped to `[0.01, 0.99]` at boundaries. Any tighter clip must be documented.

## CON-ot-hard-stop
- source: prd.md §12.2 #3; roadmap.md §1.4
- type: api-contract
- statement: DP must hard-stop at `total = 24` with documented OT-as-coinflip leaf: `0.5 × value(after_a_OT_win) + 0.5 × value(after_b_OT_win)` at 12-12 boundary; OT continues with constant `p = 0.5` per round until win-by-2.

## CON-domain-constants-baseline
- source: roadmap.md §0.4; CLAUDE.md (project instructions, encoding PRD intent)
- type: nfr
- statement: Initial values in `config/constants.py`:
  - `SHRINK_PRIOR = 15.0`
  - `SIGNAL_SCALE = 0.10`
  - `GUN_WIN_RATE = 0.822`
  - `KELLY_MULTIPLIER = 0.5`
  - `PER_MARKET_CAP_FRAC = 0.05` (TBD)
  - `VEGA_DIRECTIONAL_THRESHOLD = 0.04` (TBD; calibrate after 20+ matches)
  - Kill-switch thresholds (canonical names):
    - `KILL_SWITCH_STALENESS_S = 5.0`
    - `KILL_SWITCH_DEVIATION_C = 20`
    - `KILL_SWITCH_BRIER_BOUND = 0.30`
    - `KILL_SWITCH_BRIER_WINDOW = 50`
  - Regulation half = 12, win threshold = 13
- note: Kill-switch constant names follow roadmap.md §0.4 (`KILL_SWITCH_*` prefix). User-resolved 2026-04-27 — CLAUDE.md updated to match. See INGEST-CONFLICTS.md INFO entry.

## CON-economy-buckets
- source: CLAUDE.md (project instructions, encoding inheritance from `thunderedge/match_round_data`)
- type: schema
- statement: Economy bucket labels and credit ranges:
  - full: ≥ 20,000
  - semi-buy: 10,000–19,999
  - semi-eco: 5,000–9,999
  - eco: < 5,000

## CON-tooling-versions
- source: roadmap.md §0.2
- type: nfr
- statement: Python 3.11; `uv` for venv; `pyproject.toml`; `pytest` + `pytest-cov` + `hypothesis`; `ruff` for lint+format.

## CON-package-layout
- source: roadmap.md §0.1
- type: schema
- statement: Repo layout:
  ```
  src/{pricing, state, ingestion, quoting, sizing, config}/
  tests/
  scripts/
  data/
  models/
  reference/
  ```

## CON-trading-mode-signature
- source: roadmap.md §4.2
- type: api-contract
- statement: `trading_mode(state: MatchState, vega: float) → Literal["MM", "DIRECTIONAL"]`. Pure function. Evaluation order: numerical imbalance → bomb planted → map-point → late decider → vega override → MM default.

## CON-kelly-sizer-signature
- source: roadmap.md §4.5
- type: api-contract
- statement: `kelly_size(theo: float, market_yes_ask: float, bankroll: float) → int`. Internal: `b = (1 - market_yes_ask) / market_yes_ask`, `f_full = (b*p - q) / b`, `f = max(0, KELLY_MULTIPLIER * f_full)`, `f = min(f, PER_MARKET_CAP_FRAC)`, returns `int(f * bankroll / market_yes_ask)`.

## CON-arbiter-tiered-confirmation
- source: prd.md §5.1; roadmap.md §3.5
- type: protocol
- statement: Per-event-type rules in arbiter config dict:
  - score change: ≥ 2 independent sources within 2s window
  - bomb plant / kill / numerical flip: 1 CV-based source if kill-feed cross-confirms within same frame
  - round-end banner: soft commit; hard-confirmed by next score update
  - pre-match lineup, sides: API single-source

## CON-ingestion-cadences
- source: roadmap.md §3.2, §3.3
- type: nfr
- statement: Scoreboard polling every 5s. OCR per-target cadences: score banner 250ms; kill feed 100ms; bomb icon 500ms; round-end banner 100ms during end window. OCR latency target: 50ms decode + 50ms inference per frame.

## CON-event-timestamp-fields
- source: roadmap.md §3.6
- type: schema
- statement: Every event carries: `t_observed, t_ingested, t_arbited, t_state_committed, t_theo_computed, t_quote_sent`.

## CON-mm-spread-formula
- source: roadmap.md §4.3
- type: api-contract
- statement: MM half-spread: `max(MIN_HALF_SPREAD, k × sqrt(vega))`. Add staleness penalty when `time_since_last_state_update > 2s` (widen aggressively or pull).

## CON-kill-switches-always-on
- source: prd.md §5.4; roadmap.md §4.6
- type: nfr
- statement: All four kill switches always-on. No config flag to disable individual switches. Each is a pure predicate over `(state, theo, market, recent_briers)`. ANY trip → cancel all resting quotes + alert.

## CON-round-events-schema
- source: roadmap.md §2.2
- type: schema
- statement: `round_events` table: `(match_id, map_num, round_num, ts_round_start, ts_first_kill, ts_bomb_plant, ts_round_end, mid_round_states[])`.

## CON-round-conclusion-fallback-chain
- source: prd.md §5.3; roadmap.md §1.5
- type: api-contract
- statement: Lookup hierarchy: `(numerical_diff, bomb, side, econ_bucket, map) → (numerical_diff, bomb, side, map) → (numerical_diff, bomb, side) → (numerical_diff, bomb) → side baseline`. Bayesian shrinkage cell-to-parent.

## CON-secrets-handling
- source: roadmap.md §6.4
- type: nfr
- statement: Kalshi private key file mounted as Docker secret. NOT in image. NOT in env vars (visible to `docker inspect`). `.env` only for non-sensitive config. Private key backed up in password manager.

## CON-image-size-target
- source: roadmap.md §6.1
- type: nfr
- statement: Docker image size target < 500MB. Multi-stage build (builder + slim Python runtime).

## CON-coverage-target
- source: roadmap.md §5.1
- type: nfr
- statement: 80% line coverage on `src/pricing/`. Property-based tests via `hypothesis`.

## CON-promotion-gate
- source: roadmap.md §5.3
- type: nfr
- statement: Promotion to live requires ≥ 1 full event of paper trading with Brier < 0.22 AND zero kill-switch trips for ingestion bugs (model-trip kill switches are acceptable; bug-trip kill switches are not).

## CON-phase-dependency-graph
- source: roadmap.md (header diagram + Critical path summary)
- type: protocol
- statement: Phase ordering:
  ```
  Phase 0 (foundation) → Phase 1 (pricing engine) ─┬→ Phase 4 (quoting) → Phase 5 → Phase 6 → Phase 7
                         Phase 2 (round-event data) ┤
                         Phase 3 (live ingestion) ──┘
  ```
  Phase 1 has no data dependencies; can start immediately. Phase 2's API scope decision gates whether the round-conclusion model is built now (Phase 1.5 inline) or deferred (Path C).
