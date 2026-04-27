# Codebase Concerns

**Analysis Date:** 2026-04-27

This codebase is **greenfield-on-top-of-brownfield-references**: `src/` and `tests/` are empty (`.gitkeep` only), but `reference/` contains four salvaged files from the audited `thunderedge/worktrees/market-maker/backend/`. The PRD §12 already audited the inherited code; this document captures the audit plus integration, dependency, and operational risks. Most concerns are **not yet bugs in this repo** — they are **pre-mortem risks** the rewrite must not re-introduce.

---

## Tech Debt

### Inherited DP skeleton has documented bugs (carry-forward risk)

- Issue: `reference/theo_engine.py` is the salvaged DP skeleton. Per `prd.md` §12.1 the verdict is "Partial — keep DP skeleton, rewrite the rest." Naively lifting code into `src/pricing/` will inherit the bugs catalogued in `prd.md` §12.2 (see "Known Bugs" section below).
- Files: `reference/theo_engine.py`, future `src/pricing/dp.py`, `src/pricing/blend.py`, `src/pricing/live_theo.py`
- Impact: Mis-priced theos in production. Each bug independently corrupts the live theo; together they compound.
- Fix approach: Treat `reference/theo_engine.py` as **DP shape reference only**. Rewrite per `roadmap.md` §1.1–1.6 with single canonical `live_theo`, Bradley-Terry blend, explicit pistol/anti-eco rounds, hard OT stop at total=24, `[0.01, 0.99]` clip. Do not import from `reference/` into `src/`.

### Three parallel pricing entry points in inherited code

- Issue: `reference/theo_engine.py` exposes `series_theo` (line 281), `series_theo_from_map_probs` (line 330), and `series_theo_no_sides` (line 390). `_signal_strength` is applied in two but not the third, and `data_w` confidence-label thresholds differ (`0.8/0.4` vs `0.5/0.2`). Switching entry points silently changes results.
- Files: `reference/theo_engine.py:281`, `reference/theo_engine.py:330`, `reference/theo_engine.py:390`
- Impact: Inconsistent pricing. The map-pricer and series-pricer can disagree, creating internal arb the bot would happily fill against itself.
- Fix approach: `CLAUDE.md` rule #1 + `prd.md` §12.3.1: build one canonical `live_theo(state) → (theo, vega, confidence)`. BO3 series and per-map theos derived from the same DP via marginalization (`CLAUDE.md` rule #2). Delete the three-function pattern; do not recreate it.

### Inherited `market_maker.py` is mostly obsolete

- Issue: `reference/market_maker.py` is verdicted "Partial — extract Kalshi plumbing into `KalshiOrderManager`. The 10s poll loop, single quoting mode, and pre-veto var mutation are obsolete" (`prd.md` §12.1).
- Files: `reference/market_maker.py:104` (`_compute_quotes` — single-mode logic, no MM/directional split), `reference/market_maker.py:417` (`saved_width = self.quote_width; self.quote_width = effective_width` — mutates instance attrs in `update_market` then restores; classic concurrency landmine), `reference/market_maker.py:458` (`run` is a 10s poll loop — incompatible with event-driven architecture in `prd.md` §5.4)
- Impact: Wholesale lifting drags in the obsolete control flow.
- Fix approach: Per `roadmap.md` §4.1, salvage only `Quote` dataclass, `_place_quote`, `_cancel_quote`, `cancel_all_orders`, `_is_near_close`, error-streak retry, and dry-run mode. Stripped components belong in `src/quoting/order_manager.py`.

### TBD constants block live trading

- Issue: `CLAUDE.md` flags `PER_MARKET_CAP_FRAC = 0.05` and `VEGA_DIRECTIONAL_THRESHOLD = 0.04` as TBD. Both are sizing/mode-flip critical. `roadmap.md` §0.4 also lists them as TBD; `prd.md` §9 §1 confirms bankroll size + per-market exposure cap is unresolved.
- Files: future `src/config/constants.py` (does not exist yet)
- Impact: Without calibrated values the bot cannot be promoted past dry-run. `PER_MARKET_CAP_FRAC` directly bounds blast radius of a bad theo; `VEGA_DIRECTIONAL_THRESHOLD` decides when MM flips to taker.
- Fix approach: Per `roadmap.md` §5.4, calibrate after 100 paper-trade matches. Until then, ship conservative defaults and gate `--live` flag behind a documented bankroll/cap decision.

### Missing `src/config/constants.py`

- Issue: `CLAUDE.md` rule #12 ("No magic numbers in business logic. Every threshold lives in `src/config/constants.py`") and `roadmap.md` §0.4 mandate a single constants module. The directory exists (`src/config/`) but contains only `.gitkeep`.
- Files: `src/config/.gitkeep` (placeholder only)
- Impact: First implementer of any pricing/quoting code will be tempted to inline numbers. Once magic numbers spread, kill-switch tuning + calibration loop (`roadmap.md` §5.4) becomes painful.
- Fix approach: Create `src/config/constants.py` as Phase 0 deliverable per `roadmap.md` §0.4, before any pricing code lands.

### `prd.md` §9.3 — vega computation formula undecided

- Issue: Three defensible vega definitions (round-outcome variance only / + ingestion noise / bootstrap over recent error). `roadmap.md` §1.6 ships definition (a) but flags it for refinement in Phase 5.
- Files: future `src/pricing/live_theo.py`
- Impact: Vega drives quote width AND mode-flip threshold. Choice (a) underestimates spread when ingestion is noisy; the bot will quote tight and get adversely selected.
- Fix approach: Ship definition (a) for Phase 1 (per roadmap), instrument adverse-selection rate per `prd.md` §8, decide before live promotion.

### `prd.md` §9.4 — backtest fidelity unresolved

- Issue: Order-book replay against historical Kalshi prices may not be feasible (no public order-book history). Decision pending: synthetic counterparty vs. paper-trade-only validation.
- Files: N/A (Phase 5 work, not yet started)
- Impact: Without realistic fill simulation, the only validation path is live paper trading, which is calendar-bound (~2 weeks per `roadmap.md` §5.3).
- Fix approach: Per `roadmap.md` §5.2, choose paper-trade-live as primary validation. Backtest validates model alone (no fills). Synthetic-counterparty fill backtest is explicitly deferred.

---

## Known Bugs

These are bugs **in the inherited reference code** documented in `prd.md` §12.2. They must NOT be carried into `src/`.

### Docstring drift in `series_theo_from_map_probs`

- Symptoms: Docstring claims `p_map = fallback_q + dw_map * (blended_p - 0.5)` but code does `(1.0 - dw) * fallback_q + dw * blended_p` = `fallback_q + dw * (blended_p - fallback_q)`. The constant `0.5` should be `fallback_q`.
- Files: `reference/theo_engine.py:343-348` (docstring), `reference/theo_engine.py:374` (code)
- Trigger: Anyone reasoning from the docstring writes a different model than the one in production.
- Workaround: Trust the code, distrust the docstring. The rewrite uses a single canonical entry point so this confusion cannot recur.
- Source: `prd.md` §12.2 bug #1.

### Inconsistent `signal_strength` across pricing entry points

- Symptoms: `_signal_strength` is applied in `series_theo` (line 324) and `series_theo_no_sides` (line 423) but NOT in `series_theo_from_map_probs`. Output magnitude differs depending on which entry point is called for the same underlying state.
- Files: `reference/theo_engine.py:281` `series_theo`, `reference/theo_engine.py:330` `series_theo_from_map_probs`, `reference/theo_engine.py:390` `series_theo_no_sides`
- Trigger: Any code path that calls one of the three entry points expecting parity.
- Workaround: None in the legacy code. The rewrite (`CLAUDE.md` rule #1, `prd.md` §12.3.1) collapses to one entry point.
- Source: `prd.md` §12.2 bug #2.

### Silent OT-as-coinflip past round 24

- Symptoms: `_markov_map_win` runs the DP loop through `range(WIN_THRESHOLD * 2) = range(26)`. At `total >= 24` it sets `p = 0.5` (line 194) — i.e. OT is implicitly modeled as a coinflip despite the codebase's stated "no OT" policy.
- Files: `reference/theo_engine.py:179` (loop bound), `reference/theo_engine.py:189-194` (phase selector)
- Trigger: Any map state reaching 12-12.
- Workaround: None in legacy code.
- Source: `prd.md` §12.2 bug #3. Fix per `CLAUDE.md` rule #5 + `roadmap.md` §1.4: hard-stop at total=24 with documented OT-as-coinflip leaf.

### Round-win-prob is arithmetic mean, not Bradley-Terry

- Symptoms: `_round_win_prob` computes `p = (a_rate + (1.0 - b_rate)) / 2.0`. This under-weights compounding edges toward extremes vs the Bradley-Terry log-odds form `a*(1-b) / (a*(1-b) + (1-a)*b)`.
- Files: `reference/theo_engine.py:161`
- Trigger: Every round-prob computation.
- Workaround: None in legacy code.
- Source: `prd.md` §12.2 bug #4. Fix per `CLAUDE.md` rule #3 + `roadmap.md` §1.2.

### Two-half flat model ignores pistol / anti-eco rounds

- Symptoms: DP assumes constant `p1` for rounds 1-12 and `p2` for 13-24. But rounds 1 and 13 are pistols (`GUN_WIN_RATE = 0.822`), and a pistol win cascades into 2-3 follow-up rounds via anti-eco. Per `prd.md` §12.2 this is the **largest single modeling gap** in the legacy code.
- Files: `reference/theo_engine.py:168-206` (`_markov_map_win`)
- Trigger: Every map prediction.
- Workaround: None in legacy code.
- Source: `prd.md` §12.2 bug #5. Fix per `CLAUDE.md` rule #4 + `roadmap.md` §1.3: explicit modeling of rounds 1, 2, 3, 13, 14, 15 with separate probability inputs from `match_round_data` and `GUN_WIN_RATE`.

### `series_theo_no_sides` averages atk-start and def-start

- Symptoms: Line 420 computes `model_p = (_bo3(atk_probs) + _bo3(def_probs)) / 2.0`. Wrong — starting side is determined by veto, not by random.
- Files: `reference/theo_engine.py:420`
- Trigger: Use of `series_theo_no_sides` before veto is known.
- Workaround: Don't call this function. Use `series_theo_from_map_probs` with realized veto.
- Source: `prd.md` §12.2 bug #6. Function is excluded from rewrite (`prd.md` §12.1: "Skip — subsumed by single-DP map pricing").

### Hardcoded conviction clips `[0.05, 0.95]` and `[0.03, 0.97]`

- Symptoms: Invisible bounds on conviction. `series_theo` clips at `[0.03, 0.97]` (line 325), `series_theo_from_map_probs` clips at `[0.03, 0.97]` (line 375, 382), `_round_win_prob` clips at `[0.05, 0.95]` (line 162).
- Files: `reference/theo_engine.py:162`, `reference/theo_engine.py:325`, `reference/theo_engine.py:375`, `reference/theo_engine.py:382`
- Trigger: Any extreme-edge state.
- Workaround: None in legacy code.
- Source: `prd.md` §12.2 bug #7. Fix per `CLAUDE.md` rule #6: clip at `[0.01, 0.99]` and document any tighter clip.

### `reference/market_maker.py` mutates instance state in hot path

- Symptoms: `update_market` saves `self.quote_width` / `self.max_position`, overwrites them, calls `_compute_quotes`, then restores (lines 417-425). Not thread-safe; an exception between save and restore corrupts the instance for all subsequent calls.
- Files: `reference/market_maker.py:417-425`
- Trigger: Any exception in `_compute_quotes` during a pre-veto path.
- Workaround: Single-threaded operation makes the race impossible; the exception path is the real risk.
- Source: `prd.md` §12.1 ("pre-veto var mutation is obsolete"). Removed in rewrite — quote-width is computed per call from vega per `roadmap.md` §4.3.

---

## Security Considerations

### Kalshi RSA private key handling

- Risk: Kalshi auth uses RSA PKCS1v15/SHA-256 (`CLAUDE.md` data-sources table). Private key compromise = full account takeover.
- Files: No key file in repo (verified — `*.key` and `*.pem` matched 0 files at scan time). `.gitignore` lines 5-7 exclude `*.key`, `*.pem`, and `valorant*.txt`.
- Current mitigation: `.gitignore` covers the file extensions. `.env` and `.env.*` excluded (lines 2-3). `roadmap.md` §6.4 specifies key mounted as Docker secret in production, never in image, never in env.
- Recommendations:
  1. Document key-storage location in a `SECRETS.md` runbook before any key file is created locally.
  2. Define a key-rotation procedure (currently absent from `prd.md`, `roadmap.md`, `CLAUDE.md`).
  3. Ship a `.env.example` template so future developers do not improvise variable names.
  4. Add a pre-commit hook (e.g. `gitleaks`, `detect-secrets`) before the first secret lands.
  5. Verify backup procedure: `roadmap.md` §6.4 says "Backup the private key in a password manager" — this needs to be operational, not aspirational.

### No Kalshi sandbox — production-only API

- Risk: Per `CLAUDE.md` data-sources table, Kalshi has **no sandbox**. Every API call from dev hits production. Bug in order-placement code = real money lost / real position taken.
- Files: future `src/quoting/order_manager.py`
- Current mitigation: `CLAUDE.md` rule #13 — "Dry-run by default. Live trading requires explicit `--live` flag at the entry point." Inherited `reference/market_maker.py:84` defaults `dry_run=True`.
- Recommendations:
  1. Make `dry_run=True` non-overridable except via the documented `--live` CLI flag (no constructor kwarg, no env var override).
  2. Add a startup banner that prints `LIVE MODE` in red when `dry_run=False` so an operator cannot miss it.
  3. Per `CLAUDE.md` "Differences" + roadmap promotion gate (`roadmap.md` §5.3): bot stays `dry_run=True` until ≥1 full event paper-trade with Brier < 0.22 AND zero ingestion-bug kill-switch trips.

### Order lifecycle reconciliation gap until Phase 4.7

- Risk: Per `roadmap.md` §4.7, order reconciliation (fetch open orders from Kalshi each cycle, reconcile against in-memory `_active_quotes`) is a Phase 4 deliverable. Until then the bot can leak orders (Kalshi has resting orders the bot has forgotten about).
- Files: future `src/quoting/order_manager.py`
- Current mitigation: Inherited `cancel_all_orders` in `reference/market_maker.py:270` covers the KeyboardInterrupt shutdown path only.
- Recommendations: Implement Phase 4.7 in the same week as Phase 4.1; do not let MM/directional code (Phase 4.3-4.4) ship without reconciliation.

---

## Performance Bottlenecks

### YouTube OCR ~3s latency is the visual feed's hard floor

- Problem: Per `CLAUDE.md` data-sources table and `prd.md` §5.1 latency table, YouTube low-latency mode is ~3s. This is the **fastest accessible visual source** (caster client at ~0s is not accessible).
- Files: future `src/ingestion/ocr.py`
- Cause: Streaming protocol latency, not OCR. No engineering fix in scope.
- Improvement path: None on the YouTube path itself. Mitigations: (a) Twitter/Discord text listeners (~1-3s, soft signal only per `CLAUDE.md` rule #10), (b) round-end banner CV (~500ms before scoreboard updates per `prd.md` §5.1) for soft commits, (c) widen quotes / pull aggressively when ingestion staleness > 2s per `prd.md` §5.4.
- Operational implication: End-to-end <500ms target in `prd.md` §2 is measured from **observable in-game event arrives at our pipeline**, not from in-game clock. Do not confuse the two when reporting latency metrics.

### Scoreboard scrapers 5-60s post round (rib.gg / bo3.gg / vlr.gg)

- Problem: Per `prd.md` §5.1, scoreboard scrapers commit 5-60s after the round ends. Authoritative but slow.
- Files: future `src/ingestion/scoreboard.py`
- Cause: Upstream API refresh cadence.
- Improvement path: Use scoreboards as the **authoritative ground truth** (cross-confirmation per `prd.md` §5.1 tier-1 rule). Do not block quoting on them — let CV-based round-end banner soft-commit per the tiered rules.

### DP table size — < 1M states for BO3

- Problem: Per `prd.md` §5.3 and `roadmap.md` §1.1, the BO3 state space is < 1M states; the DP is pre-computed once and mmap'd as ~10MB.
- Files: future `models/dp_table.pkl` (does not exist; `models/.gitkeep` only)
- Cause: Memoized recursion via `@functools.lru_cache(maxsize=None)` (`roadmap.md` §1.1).
- Improvement path: This is fine as designed — sub-millisecond reads from mmap. Risk is forgetting to pre-compute (cache miss = pricing latency spike). Phase 1 build script `scripts/build_dp_table.py` (`CLAUDE.md`) must run before first live quote.

### OneDrive filesystem on local dev

- Problem: Local repo lives at `C:\Users\josep\OneDrive\Desktop\Thunderedge\valorant-pricing-model\`. OneDrive sync introduces filesystem quirks (file locking during sync, occasional move-to-cloud delays) that can affect JSONL event-log writes (`roadmap.md` §3.1).
- Files: future `logs/*.jsonl` (logs/ exists with `.gitkeep` only)
- Cause: OneDrive's transparent sync layer.
- Improvement path: `prd.md` §5.5 explicitly accepts this trade-off for local dev. Mitigation: production runs on a cloud VM with native filesystem; local dev accepts occasional log-write hiccups.

---

## Fragile Areas

### Boundary between salvaged `reference/` and new `src/`

- Files: `reference/theo_engine.py`, `reference/market_maker.py`, future `src/pricing/`, future `src/quoting/`
- Why fragile: `reference/` is **read-only salvage** (`CLAUDE.md` "Read first" + `prd.md` §12). It is tempting to `from reference.theo_engine import ...` to bootstrap quickly. Doing so imports the bugs catalogued above.
- Safe modification: Treat `reference/` as documentation, not as a Python package. Re-implement in `src/`; copy specific functions only with explicit comment `# salvaged from reference/X.py:LINE — see PRD §12.1` and only for the four green-listed verdicts (`odds_utils.py` as-is, `fair_value.py` as-is, DP skeleton in `theo_engine.py`, Kalshi plumbing in `market_maker.py`).
- Test coverage: None exists yet — `tests/.gitkeep` is the only file. Property-based tests per `roadmap.md` §5.1 (DP value in [0,1], monotonic in `round_p`, BT blend symmetry, theo_series consistent with theo_map[]) are the integration safety net for the salvage→rewrite boundary.

### Greenfield `src/` — entire implementation is yet to be written

- Files: `src/pricing/.gitkeep`, `src/state/.gitkeep`, `src/ingestion/.gitkeep`, `src/quoting/.gitkeep`, `src/sizing/.gitkeep`, `src/config/.gitkeep`
- Why fragile: All architecture rules in `CLAUDE.md` (single canonical `live_theo`, four always-on kill switches, tiered ingestion confirmation, dry-run by default, `mypy --strict` on pricing) are aspirational until Phase 0-4 land. Each rule represents a past mistake; failing to enforce them at write-time means re-litigating §12 of the PRD.
- Safe modification: Phase 0 (`roadmap.md` §0) gates everything else. Land `pyproject.toml`, `src/config/constants.py`, `mypy --strict` config, and CI ruff/mypy hooks **before** any pricing code so the rules are enforced from line one.

### Bo3.gg API filter params broken

- Files: future `src/ingestion/scoreboard.py` if it integrates bo3.gg
- Why fragile: `CLAUDE.md` data-sources table notes "Filter params broken — use slug endpoint only (per thunderedge CLAUDE.md)". Documented external API limitation.
- Safe modification: Slug endpoint only. Document the constraint in the scoreboard module docstring with link back to `CLAUDE.md`.

### State-engine `seq_id` monotonicity contract

- Files: future `src/state/match_state.py` (per `roadmap.md` §3.1)
- Why fragile: `CLAUDE.md` "State engine" section + `roadmap.md` §3.1 require quoting layer to act only on monotonically increasing `seq_id`. A bug that resets or duplicates `seq_id` (e.g. on replay-from-disk) silently lets stale state drive live quotes.
- Safe modification: Mutators bump `seq_id` exactly once per state change. JSONL event log (`roadmap.md` §3.1) replays by re-applying mutations, not by writing raw seq_ids. Add a property test that `seq_id` is strictly increasing across all observed states.

---

## Scaling Limits

### State space — BO3 only, not BO5

- Current capacity: BO3, < 1M DP states (`prd.md` §5.3, `roadmap.md` §1.1).
- Limit: BO5 series is explicitly out of scope per `prd.md` §11.
- Scaling path: BO5 expands the state space ~order-of-magnitude (5 maps × additional map-score states). Pre-compute strategy still works but table size grows. Defer until BO5 markets exist on Kalshi.

### Tournament concurrency

- Current capacity: Architecture is single-match-per-process (`CLAUDE.md` run command `python -m src.main --match <ticker>`).
- Limit: Live tournaments often have 2-3 concurrent matches. Single process cannot quote all simultaneously without changes.
- Scaling path: Run one process per match. Cloud VM (`prd.md` §5.5: Hetzner CCX13 2 vCPU / 8GB) supports 4-8 concurrent processes. Document this in the deployment runbook before tournament season.

### `data/half_win_rates.json` is ~67KB and offline-generated

- Current capacity: Single JSON file, ~67KB, generated upstream by `thunderedge/worktrees/half-win-rate/`.
- Limit: Stale rates as the meta drifts (new map, agent reworks, roster changes).
- Scaling path: Per `roadmap.md` §7.2 weekly drift detection (KL divergence on Brier distribution) catches drift; recompute upstream when it triggers. No automated re-generation pipeline yet.

---

## Dependencies at Risk

### rib.gg has no public REST API — Phase 2.1 spike risk

- Risk: Per `CLAUDE.md` data-sources and `roadmap.md` Phase 2.1, rib.gg has **no public REST**. Routes via `FlynV/RIB.GG-Web-Scraper` or `{valorantr}` R package. **Phase 2.1 is a scoping spike with real risk of failure.**
- Impact: If neither path exposes per-round events with timestamps + bomb plant + numerical state, the round-conclusion model (Phase 1.5 / 2.2) is blocked. Fallback paths per `roadmap.md` §2.3-§2.4: (a) ~2-week OCR labeling project, (b) defer mid-round pricing entirely (`round_conclusion` returns fixed `p = 0.5`).
- Migration plan: `scripts/probe_round_events.py` (per `roadmap.md` §2.1) runs the spike Day 1. Decision tree in §2.1 commits to Path A / B / C within 1 day. **Path C (defer) preserves the project — between-round MM still ships in 3 weeks per `roadmap.md` "Earliest revenue" note.**

### bo3.gg API filter params broken

- Risk: Per `CLAUDE.md` data-sources table, filter params on bo3.gg are broken — slug endpoint only.
- Impact: Cannot bulk-pull historical matches by date range or tournament. Slug-based lookup is one-match-at-a-time.
- Migration plan: Use rib.gg as primary, bo3.gg as backup with slug-only access pattern. Document constraint in `src/ingestion/scoreboard.py`.

### Kalshi API — single live venue, no sandbox

- Risk: Kalshi is the only quoting venue (`CLAUDE.md` data-sources, `prd.md` §1). No sandbox. API rate limits, downtime, or T&C changes are existential.
- Impact: Kalshi outage = bot offline. T&C change banning bots = project death.
- Migration plan: No alternative venue exists for Valorant series binary markets. Mitigations: (a) kill switch on API errors per `CLAUDE.md` rule #9, (b) operational risk limit per `roadmap.md` §7.4, (c) cloud VM in US-East near Kalshi infra to minimize network failure surface (`prd.md` §5.5).

### Twitter API v2 streaming filter — paid tier required

- Risk: Per `roadmap.md` §3.4, text listener uses Twitter API v2 streaming. Free tier was sunsetted; paid access required as of 2023.
- Impact: Soft-signal source becomes unavailable or expensive.
- Migration plan: Discord webhooks on match-thread channels are a free fallback. Document choice when `src/ingestion/text.py` lands.

### `data/half_win_rates.json` upstream regeneration

- Risk: File is generated by `thunderedge/worktrees/half-win-rate/` (`CLAUDE.md` data-sources). This project does not import that worktree but depends on its output.
- Impact: Upstream pipeline rot (broken bo3.gg integration, schema drift) silently produces stale rates.
- Migration plan: When weekly drift detection (`roadmap.md` §7.2) trips, re-run upstream. Add a freshness check (`max_age_days = 14`) at load time in the new DP module.

---

## Missing Critical Features

### No round-events dataset (Phase 2 deliverable)

- Problem: Mid-round pricing requires per-round timestamps + bomb plant + numerical state (`prd.md` §5.3, `roadmap.md` §1.5). No such dataset exists in `data/`.
- Blocks: `src/pricing/round_conclusion.py`, mid-round live theo, mid-round MM/directional flips on bomb plant per `prd.md` §2.1.
- Source: `roadmap.md` Phase 2 critical path.

### No paper-trading harness

- Problem: Promotion gate per `roadmap.md` §5.3 requires ≥1 full event of paper trading with Brier < 0.22. No paper-trade scaffolding exists.
- Blocks: Phase 6 deployment.
- Source: `roadmap.md` §5.3.

### No backtest infrastructure

- Problem: Per `roadmap.md` §5.2, backtest replays past matches against `live_theo` on synthetic state from `match_round_data`. Not built.
- Blocks: Pre-paper-trade model validation.
- Source: `roadmap.md` §5.2.

### No incident runbook

- Problem: Per `roadmap.md` §7.3, runbook should cover halt-bot-remotely, manual order cancel via Kalshi UI, Docker-image rollback, kill-switch alert interpretation. Not written.
- Blocks: Operational readiness for live trading.
- Source: `roadmap.md` §7.3.

### No daily metrics / drift detection

- Problem: Per `roadmap.md` §7.1-§7.2, daily metrics report and weekly KL-divergence drift detection are unbuilt.
- Blocks: Long-term operational hygiene; calibration loop per `roadmap.md` §5.4.
- Source: `roadmap.md` §7.

### No `.env.example` template

- Problem: `CLAUDE.md` references `.env` for Kalshi credentials. No `.env.example` checked in. New contributors must guess variable names.
- Blocks: Onboarding; reproducibility.
- Source: `.gitignore` line 4 explicitly allows `.env.example` (`!.env.example`) but the file does not exist.

---

## Test Coverage Gaps

### Zero tests exist

- What's not tested: Everything. `tests/` contains only `.gitkeep`.
- Files: `tests/.gitkeep`
- Risk: All `CLAUDE.md` critical rules are unenforced. `mypy --strict` config, ruff, pytest, hypothesis are not yet wired up.
- Priority: **High** — Phase 0 deliverable per `roadmap.md` §0.2.

### DP correctness properties (Phase 5.1)

- What's not tested: DP value ∈ [0,1] for any state; monotonicity in `round_p`; `theo_series` consistency with `theo_map[]`; Bradley-Terry symmetry `round_p(a,b) + round_p(b,a) == 1`.
- Files: future `tests/pricing/test_dp.py`, `tests/pricing/test_blend.py`, `tests/pricing/test_live_theo.py`
- Risk: Silent pricing miscalibration. The bugs in `prd.md` §12.2 went undetected in production for the legacy code; property tests are the line of defense.
- Priority: **High** — must land alongside Phase 1 implementation.

### Kill-switch trip behavior

- What's not tested: All four kill switches (`prd.md` §5.4): API errors, staleness > 5s, |theo − market| > 20¢, rolling Brier > 0.30 over 50 rounds. Per `CLAUDE.md` rule #9 these are always-on.
- Files: future `tests/quoting/test_kill_switches.py`
- Risk: A kill switch that silently fails to fire is the worst-case bug — it's exactly the scenario the switch exists to catch.
- Priority: **High** — Phase 4.6 deliverable. Each switch is a pure predicate; trivial to unit-test.

### Tiered ingestion arbiter

- What's not tested: Per-event-type confirmation rules (`prd.md` §5.1): score updates need ≥2 sources within 2s; mid-round events commit on 1 CV source if kill-feed cross-confirms.
- Files: future `tests/ingestion/test_arbiter.py`
- Risk: False score commits corrupt the DP root state — highest blast radius per `prd.md` §5.1.
- Priority: **High** — Phase 3.5 deliverable.

### Order lifecycle reconciliation

- What's not tested: Reconciliation between in-memory `_active_quotes` and Kalshi-side resting orders (Phase 4.7).
- Files: future `tests/quoting/test_order_lifecycle.py`
- Risk: State-drift bugs leak orders or duplicate cancels.
- Priority: **Medium-High** — Phase 4.7 deliverable.

### `mypy --strict` enforcement on `src/pricing/`

- What's not tested: Type-correctness of the math layer. `CLAUDE.md` rule #11 mandates `mypy --strict` on `src/pricing/`. Not yet wired.
- Files: future `pyproject.toml` (does not exist), future `mypy.ini` or `[tool.mypy]` block
- Risk: Type errors in pricing produce wrong numbers, not exceptions. Silent wrong is worse than loud broken.
- Priority: **High** — Phase 0.2 deliverable.

---

*Concerns audit: 2026-04-27*
