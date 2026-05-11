"""Canonical thresholds and magic numbers for the Valorant pricing model.

This module is the SINGLE source of truth for every threshold the system uses
(DEC-016, CLAUDE.md rule 12, CON-no-magic-numbers).

Rules
-----
1. No business logic anywhere else in `src/` may hardcode any of these values.
   Always import: ``from src.config.constants import KELLY_MULTIPLIER``.
2. Tuning these values is a Phase 5 activity (calibration loop, REQ-calibration-loop).
   Initial values below ship with documented sources; do not change without
   updating the citing doc (`prd.md` or `roadmap.md`) first.
3. Constants marked ``# TBD`` are intentional initial guesses, gated on future
   calibration data — see PRD §9 "Open TBDs" and STATE.md "Open TBDs".

Source of truth
---------------
- ``prd.md`` §6, §9 (locked decisions and open TBDs)
- ``roadmap.md`` §0.4 (Phase 0 — Configuration block; canonical KILL_SWITCH_* prefix)
- ``CLAUDE.md`` "Domain constants" (project-instructions encoding of PRD intent)
- ``.planning/intel/constraints.md`` CON-domain-constants-baseline
- ``.planning/intel/decisions.md`` DEC-004, DEC-005, DEC-007, DEC-011, DEC-016

Naming
------
``UPPER_SNAKE_CASE`` for all module-level constants. Kill-switch constants use the
``KILL_SWITCH_*`` prefix per roadmap.md §0.4 (user-resolved 2026-04-27) and
CLAUDE.md "Domain constants" lines 80-83.

Type annotations
----------------
Every constant uses ``typing.Final[...]`` so ``mypy --strict`` (enforced on
``src/pricing/`` per CON-mypy-strict-pricing) treats reassignment as an error.
"""

from __future__ import annotations

from typing import Final

# --------------------------------------------------------------------------- #
# Pricing                                                                     #
# --------------------------------------------------------------------------- #

SHRINK_PRIOR: Final[float] = 15.0
"""Bayesian prior weight in rounds for the round-conclusion lookup.

Source: DEC-007 / CLAUDE.md "Domain constants" / reference/theo_engine.py:37.
Re-fit in Phase 5 after 100+ matches of paper-trade data (REQ-calibration-loop).
"""

SIGNAL_SCALE: Final[float] = 0.10
"""Signal-strength scale: ``|model_p - 0.5| / SIGNAL_SCALE`` clipped to ``[0, 1]``.

Source: CLAUDE.md "Domain constants" / reference/theo_engine.py:38.
Used by the round-conclusion shrinkage layer to weight cell vs parent estimates.
"""

GUN_WIN_RATE: Final[float] = 0.822
"""Population mean ``P(team with rifles wins an eco round)``.

Source: DEC-011 / CLAUDE.md "Domain constants" / prd.md §6 Tier 1.
Used by the pistol+anti-eco round model (REQ-pistol-anti-eco-modeling) for
rounds 2, 3, 14, 15 conditional on the prior-pistol outcome.
"""

REGULATION_HALF: Final[int] = 12
"""Rounds per half (Valorant standard).

Source: CLAUDE.md "Domain constants" / reference/theo_engine.py:34.
DP hard-stops at total = 24 (REGULATION_HALF * 2) per DEC-009 / CON-ot-hard-stop.
"""

WIN_THRESHOLD: Final[int] = 13
"""Rounds needed to win a map (Valorant standard, BO13).

Source: CLAUDE.md "Domain constants" / reference/theo_engine.py:35.
"""

CONVICTION_CLIP_LOW: Final[float] = 0.01
"""Lower bound for theo_series and theo_map[i] clip at live_theo output.

Source: DEC-012 / CLAUDE.md rule 6 / CON-conviction-clip / 01-RESEARCH.md §12.
Replaces the audit engine's heterogeneous `[0.05, 0.95]` and `[0.03, 0.97]`
clips with a unified, wider `[0.01, 0.99]` band (PRD §12.2 #1).
"""

CONVICTION_CLIP_HIGH: Final[float] = 0.99
"""Upper bound for theo_series and theo_map[i] clip at live_theo output.

Source: DEC-012 / CLAUDE.md rule 6 / CON-conviction-clip / 01-RESEARCH.md §12.
"""

MIN_ROUNDS_FULL_WEIGHT: Final[int] = 15
"""Effective rounds for full data confidence in the audit-engine `_data_weight`
formula (D-09). Min-over-teams normalizer for confidence aggregation.

Source: reference/theo_engine.py:36 / D-09 / 01-RESEARCH.md §12. Used by
src/pricing/live_theo.py::_data_weight_for_map only.
"""

BT_BLEND_EPSILON: Final[float] = 1e-6
"""Bradley-Terry blend input clip — protects against 0/0 at boundary inputs.

Source: CON-bradley-terry-formula / 01-RESEARCH.md §3 (Pitfall 4) / §12.
Inputs to blend.round_p are clipped to [BT_BLEND_EPSILON, 1 - BT_BLEND_EPSILON]
BEFORE the formula. Output is NEVER clipped — that breaks BT symmetry.
"""

# --------------------------------------------------------------------------- #
# Sizing                                                                      #
# --------------------------------------------------------------------------- #

KELLY_MULTIPLIER: Final[float] = 0.5
"""Half-Kelly multiplier applied to the full Kelly fraction before per-market cap.

Source: DEC-004 / CLAUDE.md rule 7.
``f = max(0, KELLY_MULTIPLIER * f_full)`` then ``f = min(f, PER_MARKET_CAP_FRAC)``.
NEVER full Kelly (CLAUDE.md rule 7).
"""

PER_MARKET_CAP_FRAC: Final[float] = 0.05  # TBD
"""Maximum fraction of bankroll allocated to a single Kalshi market.

Source: DEC-004 / CLAUDE.md "Domain constants".
TBD — depends on final bankroll allocation decision (PRD §9.1).
Initial value 0.05 is a placeholder; revisit when bankroll is fixed.
"""

# --------------------------------------------------------------------------- #
# Kill switches (DEC-005: all four always-on, no per-switch disable flag)     #
# --------------------------------------------------------------------------- #

KILL_SWITCH_STALENESS_S: Final[float] = 5.0
"""Ingestion-staleness kill-switch threshold, seconds.

If ``time.now() - state.last_updated_ts > KILL_SWITCH_STALENESS_S``, kill-switch (b)
trips and ``KalshiOrderManager.cancel_all_orders()`` is invoked.
Source: DEC-005 / CLAUDE.md rule 9 / PRD §5.4.
"""

KILL_SWITCH_DEVIATION_C: Final[int] = 20
"""Theo-vs-market deviation kill-switch threshold, cents.

If ``abs(theo_cents - market_cents) > KILL_SWITCH_DEVIATION_C``, kill-switch (c)
trips. Suggests our model is materially mis-priced relative to other participants
or our state is wrong; either way, stop trading.
Source: DEC-005 / CLAUDE.md rule 9 / PRD §5.4.
"""

KILL_SWITCH_BRIER_BOUND: Final[float] = 0.30
"""Rolling-Brier kill-switch upper bound (over the most recent
``KILL_SWITCH_BRIER_WINDOW`` round predictions).

If realized rolling Brier exceeds this bound, kill-switch (d) trips.
Source: DEC-005 / CLAUDE.md rule 9 / PRD §5.4.
"""

KILL_SWITCH_BRIER_WINDOW: Final[int] = 50
"""Number of round predictions in the rolling-Brier window.

Source: DEC-005 / CLAUDE.md rule 9 / PRD §5.4.
"""

# --------------------------------------------------------------------------- #
# Phase 2 — rib.gg probe ETL (REQ-round-event-data-pipeline)                  #
# --------------------------------------------------------------------------- #

RIBGG_BASE_URL: Final[str] = "https://be-prod.rib.gg/v1"
"""rib.gg internal API base URL (live-verified 2026-04-30 in 02-RESEARCH.md).

Source: 02-RESEARCH.md §"Pattern 1" / DEC-017. The 2022 `Traumist/RIB-Data-Scraper`
reference used `backend-prod.rib.gg`; the subdomain migrated to `be-prod.rib.gg`
sometime 2022-2026 (verified 200 OK in research session). Re-probe before scraping
if Phase 2 execution is delayed >30 days from research date.
"""

RIBGG_RECENCY_MONTHS: Final[int] = 18
"""Hard cap on rib.gg `events[].startDate` filter for D-03 coverage bar.

Source: D-03 (CONTEXT.md). Older matches are rejected at probe time. The 18-month
window straddles 2-3 patch metas; recency-weighting is deferred to Phase 5/7
(Pitfall 6 / 02-RESEARCH.md). Document rejection count in 02-PROBE-LOG.md.
"""

RIBGG_TARGET_MATCH_COUNT: Final[int] = 1000
"""Tier-1 VCT match-count target for the calibration dataset.

Source: D-03 (CONTEXT.md). At ~75k rounds this saturates `cells_full` for the
popular `(numerical_diff, bomb_planted, side, econ_bucket, map)` combinations.
Floor for must-have #1 acceptance is 500 matches; 1000 is the target.
"""

RIBGG_TIER_FILTER: Final[str] = "VCT"
"""rib.gg `events[].divisions` filter token for tier-1 events.

Source: D-03 (CONTEXT.md) / 02-RESEARCH.md §"Don't Hand-Roll" tier-1 filter row.
Match if `"VCT" in event.divisions`. Verified shape during 2026-04-30 probe.
"""

RIBGG_RATE_LIMIT_RPS: Final[float] = 2.0
"""Self-imposed throttle for rib.gg HTTP fetches, requests-per-second.

Source: 02-RESEARCH.md §"Pattern 1" — rib.gg returned no rate-limit headers, but
~4000 calls / 2 rps = ~33 minutes is polite-citizen behavior on a public API.
Probe script sleeps `1 / RIBGG_RATE_LIMIT_RPS` seconds between calls.
"""

# --------------------------------------------------------------------------- #
# Phase 2 — calibration                                                       #
# --------------------------------------------------------------------------- #

MIN_CELL_N: Final[int] = 5
"""Minimum sample size for a cell to be persisted to models/round_conclusion.json.

Source: 02-RESEARCH.md §"Project Constraints" #6. Below this floor, `_Cell.shrunk()`
returns essentially `parent_p`; persisting the cell wastes JSON size without
changing runtime lookup behavior. Drop in calibrator before serialization.
"""

MID_ROUND_HEARTBEAT_S: Final[float] = 5.0
"""Synthetic-heartbeat interval for `mid_round_states[]` carry-forward (D-06).

Source: D-06 (CONTEXT.md). Each round emits a heartbeat every 5s on top of the
native event log; values are carry-forward from the most recent event (D-08).
This keeps Phase 2 calibration data and Phase 3 runtime data on the same grid.
"""

# --------------------------------------------------------------------------- #
# Phase 2 — economy buckets (DELETED in Phase 3 v2; see CLAUDE.md "Economy    #
# buckets — DEPRECATED in v2"). Bucket constants removed because their sole   #
# caller (src/pricing/economy.credits_to_bucket) has no callers after the v2  #
# rekey of round_conclusion.json. Forensic recovery via git show HEAD~N.     #
# --------------------------------------------------------------------------- #

# OCR cadences moved to "Phase 3 — OCR pipeline" section (03-05 PLAN owns).

# --------------------------------------------------------------------------- #
# Phase 3 — round-conclusion v2 (D-04 / D-06 / D-10)                          #
# --------------------------------------------------------------------------- #

POST_PLANT_TIMER_S: Final[float] = 45.0
"""Valorant post-plant bomb timer (seconds).

Source: 03-CONTEXT.md D-14 / Riot rules. Drives `time_remaining_bucket`
computation in live_theo's post-plant dispatch path. Bombs that exceed this
timer auto-detonate; live_theo clips `state.time_left_s` to this max.
"""

TIME_BUCKET_WIDTH_S: Final[float] = 5.0
"""Width of each post-plant time bucket (seconds); 9 buckets across 0-45s.

Source: 03-CONTEXT.md D-10. Buckets: [0-5, 5-10, ..., 40-45]. Cell estimate
~3150 cells_full slots × ~25k post-plant samples → ~8 samples/cell average,
shrunk to parent (cells_no_time) per Bayesian SHRINK_PRIOR=15.
"""

ROUND_CONCLUSION_JSON_PATH: Final[str] = "models/round_conclusion.json"
"""Canonical disk path for the v2 calibrated lookup (D-06).

Atomic-replace target. `RoundConclusionLookup.from_json(path)` HARD-FAILS on
schema_version != 2; v1 file recoverable via git history.
"""

RIBGG_CACHE_DIR: Final[str] = "data/ribgg_cache"
"""requests-cache filesystem backend directory (D-08). Per-URL+params SHA
JSON files; gitignored per `.gitignore` (data/ribgg_cache/). Phase 3 ETL re-run
uses this so future re-runs are near-instant on cache hits (~5GB on disk for
1000 series cold cache; near-zero subsequent re-runs).

Source: 03-CONTEXT.md D-08 / 03-RESEARCH.md §"Pattern 6"."""

ROUND_EVENTS_V2_DB_PATH: Final[str] = "data/round_events_v2.sqlite"
"""Phase 3 v2 ETL output (D-07). NEW SQLite — v1 db at data/round_events.sqlite
retained on disk for forensic value. v2 schema persists a_alive/b_alive in
mid_round_states[] JSON blob (cells_full / time_bucket calibration needs RAW
counts, not derived numerical_diff).

Source: 03-CONTEXT.md D-07 / 03-RESEARCH.md §"Architecture Patterns"."""

# --------------------------------------------------------------------------- #
# Phase 3 — ingestion arbiter + event logs (DEC-006 v2 / D-03)               #
# --------------------------------------------------------------------------- #

ARBITER_TICK_HZ: Final[int] = 20
"""Arbiter drain frequency (Hz). 20Hz = 50ms tick interval, well within the
500ms event→state-commit budget. Used by src/main.py asyncio loop only;
src/ingestion/arbiter.py exposes the bare tick() — driver picks the cadence.

Source: 03-CONTEXT.md "Claude's discretion" / DEC-006 v2.
"""

ARBITER_SCORE_WINDOW_S: Final[float] = 2.0
"""Score-change cross-confirm window (seconds). DEC-006 v2: a score_change
event commits when ≥ 2 independent sources push events with t_observed
within this window of each other.

Source: 03-CONTEXT.md / DEC-006 v2 / CLAUDE.md CRule 10 simplified arbiter.
"""

EVENT_LOG_DIR: Final[str] = "data/event_log"
"""JSONL diff log directory (one file per match_id). Gitignored per
03-00-PLAN's .gitignore additions.

Source: 03-CONTEXT.md D-03 / Plan 03-01 commit/quarantine helpers.
"""

METRICS_LOG_DIR: Final[str] = "data/metrics"
"""6-stage timestamp metrics directory (one file per match_id). Phase 4
fills t_theo_computed / t_quote_sent on a parallel metrics line per D-03.

Source: 03-CONTEXT.md D-03 / SPEC §"Constraints" latency analysis.
"""

# --------------------------------------------------------------------------- #
# Phase 3 — scoreboard poller (REQ-scoreboard-polling / 03-04 / D-09)         #
# --------------------------------------------------------------------------- #

SCOREBOARD_POLL_CADENCE_S: Final[float] = 5.0
"""rib.gg async poller cadence (seconds).

5s = baseline per SPEC §3.2 / REQ-scoreboard-polling. Slowest authoritative
source — OCR confirms within ARBITER_SCORE_WINDOW_S (2s window) per the
DEC-006 v2 cross-confirm rule.

Source: 03-CONTEXT.md / 03-04 PLAN. Coupled in code with ARBITER_SCORE_WINDOW_S
above (no longer a magic number floating across the ingestion layer).
"""

SCOREBOARD_FAILURE_COOLDOWN_S: Final[float] = 60.0
"""Cooldown after SCOREBOARD_MAX_RETRIES consecutive failures (seconds).

Salvaged from Phase 2's `_ribgg_cool_off` pattern in
``scripts/probe_round_events.py``. After this window the consecutive-failure
counter resets and polling resumes.
"""

SCOREBOARD_MAX_RETRIES: Final[int] = 5
"""Tenacity ``stop_after_attempt`` value AND the consecutive-failure cooldown
trigger. Phase 2 carry-forward (5 attempts has empirically been enough to
ride out rib.gg Heroku cold-starts and 503/429 spikes during VCT events).
"""

# --------------------------------------------------------------------------- #
# Phase 3 — OCR pipeline (DEC-024 v2 / D-11 / D-12 / D-13 / D-14)             #
# --------------------------------------------------------------------------- #

OCR_SCORE_BANNER_CADENCE_MS: Final[int] = 250
"""Score banner OCR cadence (ms). DEC-024 v2 — primary HUD target #1.

Source: 03-CONTEXT.md / DEC-024 v2 / CLAUDE.md CRule 10a OCR scope. The 250ms
floor matches ARBITER_SCORE_WINDOW_S=2.0s (multi-confirm rule) — fast enough
that an OCR push and a rib.gg push fall inside the same window."""

OCR_BOMB_ICON_CADENCE_MS: Final[int] = 500
"""Bomb-plant icon detection cadence (ms). DEC-024 v2 — primary HUD target #2.

Source: 03-CONTEXT.md / DEC-024 v2. 500ms is fast enough for the bomb-detect →
state-commit p50 < 100ms budget when a plant lands at the start of a 500ms
window (worst case ~600ms but median ~250ms)."""

OCR_ROUND_END_CADENCE_MS: Final[int] = 100
"""Round-end banner cadence during round-end window (ms). DEC-024 v2.

Source: 03-CONTEXT.md / DEC-024 v2. Tight 100ms cadence captures the ~500ms
banner-leads-scoreboard alpha noted in PRD §5.1."""

OCR_POST_PLANT_ALIVE_CADENCE_MS: Final[int] = 250
"""Post-plant alive widget cadence (ms). D-12: gated on bomb_planted=True.

Source: 03-CONTEXT.md D-12. The 250ms cadence is the floor that determines
how fast post-plant theo can update via attackers_alive/defenders_alive
deltas — D-12 hard-gate keeps the worker silent when no plant is active so
the ~30ms/cycle CPU is only spent during the 45s post-plant window."""

OCR_DECODE_BUDGET_MS: Final[int] = 100
"""Per-frame decode + inference budget (ms). SPEC §3 acceptance — p50 must
be below this across all 4 OCR targets.

Source: 03-RESEARCH.md Pitfall 2 — pytesseract subprocess fork overhead is
~10-20ms; budget accordingly. Bomb-detect → state-commit p50 < 100ms hot path
(SPEC §6) hinges on this floor."""

BROADCAST_TEMPLATE_VERSION: Final[str] = "vct-2026-international"
"""Layout-version anchor for ROI calibration. D-11: single-template assumption;
multi-template fallback is Phase 5 robustness work. Bump when broadcast layout
shifts (e.g., VCT regional vs international, or new season skin).

Source: 03-CONTEXT.md D-11. Operator runs scripts/dump_roi_overlay.py to
verify ROIs land cleanly against a captured broadcast frame; if any rectangle
is off, edit the ROI tuples below AND bump this version string in the same
commit so the calibration record is forensic-traceable."""

# TODO(operator): recalibrate ROIs below against first VCT 2026 broadcast frame;
# use scripts/dump_roi_overlay.py to verify. Coordinates assume 1920x1080 frame.
SCORE_BANNER_TEAM1_ROI: Final[tuple[int, int, int, int]] = (800, 15, 870, 51)
"""Team-1 score (left of banner) ROI: (x1, y1, x2, y2) at 1920x1080.

PLACEHOLDER pending operator recalibration (D-11)."""

# TODO(operator): recalibrate against first VCT 2026 broadcast frame.
SCORE_BANNER_TEAM2_ROI: Final[tuple[int, int, int, int]] = (1050, 15, 1125, 51)
"""Team-2 score (right of banner) ROI: (x1, y1, x2, y2) at 1920x1080.

PLACEHOLDER pending operator recalibration (D-11)."""

# TODO(operator): recalibrate against first VCT 2026 broadcast frame.
BOMB_PLANT_ICON_ROI: Final[tuple[int, int, int, int]] = (910, 60, 1010, 100)
"""Spike icon detection ROI (centered top, below score banner). PLACEHOLDER.

D-11: single-template assumption; multi-template is Phase 5 robustness work."""

# TODO(operator): recalibrate against first VCT 2026 broadcast frame.
ROUND_END_BANNER_ROI: Final[tuple[int, int, int, int]] = (760, 380, 1160, 480)
"""Round-end center-screen banner ROI. PLACEHOLDER.

Round-end banner appears ~500ms before scoreboard updates (PRD §5.1)."""

# TODO(operator): recalibrate against first VCT 2026 broadcast frame.
POST_PLANT_ATTACKERS_ROI: Final[tuple[int, int, int, int]] = (820, 105, 870, 155)
"""Post-plant attacker-alive single digit ROI. PLACEHOLDER (D-11).

Only parsed when bomb_planted=True (D-12 hard-gate); single-character ROI
per D-13 Tesseract config TESS_CONFIG_DIGIT_SINGLE."""

# TODO(operator): recalibrate against first VCT 2026 broadcast frame.
POST_PLANT_DEFENDERS_ROI: Final[tuple[int, int, int, int]] = (1050, 105, 1100, 155)
"""Post-plant defender-alive single digit ROI. PLACEHOLDER (D-11)."""

TESS_CONFIG_DIGIT_SINGLE: Final[str] = "--psm 10 --oem 3 -c tessedit_char_whitelist=012345"
"""Tesseract config for single-digit alive-count parsing (D-13).

PSM 10 = single character mode; OEM 3 = LSTM + legacy; whitelist enforces 0-5.
Source: 03-CONTEXT.md D-13 / 03-RESEARCH.md §"Code Examples" PSM 10 digit pipeline."""

TESS_CONFIG_DIGIT_MULTI: Final[str] = "--psm 7 --oem 3 -c tessedit_char_whitelist=0123456789"
"""Tesseract config for multi-digit score parsing (0-13).

PSM 7 = single line of text mode; needed for score banner where 2-digit values
(10, 11, 12, 13) appear after pistol-rich first halves."""

# --------------------------------------------------------------------------- #
# Phase 3 — text listener (REQ-text-listener / 03-06 / 03-CONTEXT D-07)       #
# --------------------------------------------------------------------------- #

TWITTER_API_BASE_URL: Final[str] = "https://api.twitter.com/2"
"""Twitter API v2 base URL.

Used by tweepy.asynchronous.AsyncStreamingClient under the hood; declared here
only as a module-init sanity anchor and as the canonical reference for any
future direct-aiohttp fallback path. Not used directly in production code.

Source: 03-CONTEXT.md D-07 / 03-RESEARCH.md §"Constants to Add" / 03-06 PLAN.
"""

TWITTER_RULE_SET: Final[tuple[str, ...]] = (
    "#VCT",
    "#VALORANTChampions",
    "#VCTAmericas",
    "#VCTEMEA",
    "#VCTPacific",
    # Operator-pinned 2026-season caster/league/team-org accounts.
    # CONTEXT D-07 carry-forward; researcher-pinned per RESEARCH §"Code Examples".
    "from:ValorantEsports",
    "from:VCT_Americas",
    "from:VCT_EMEA",
    "from:VCT_Pacific",
)
"""Static rule set for tweepy.asynchronous.AsyncStreamingClient filter (REQ-text-listener).

Twitter API v2 streaming rules — added once at listener init via add_rules.
Operator can extend by editing this tuple + redeploying. Per-match dynamic
rule sync is deferred (CONTEXT 'Deferred Ideas' / RESEARCH §"Open Questions").

PERMANENT DEGRADATION (RESEARCH Pitfall 1):
- Twitter API Basic tier ($200/mo) was deprecated 2026-02-06 for new accounts.
- Default deployments without TWITTER_BEARER_TOKEN env var degrade to no-op;
  the arbiter still satisfies its >=2-source rule via rib.gg + OCR.
"""

# --------------------------------------------------------------------------- #
# Phase 4 — quoting layer thresholds (DEC-001 v2 mode selector)               #
# --------------------------------------------------------------------------- #

TAKE_THRESHOLD: Final[int] = 5  # cents
"""Between-round directional-take threshold (cents).

DIRECTIONAL_TAKE fires when |theo_cents - market.mid| > TAKE_THRESHOLD.
Source: DEC-001 v2 (replaces VEGA_DIRECTIONAL_THRESHOLD), PRD §2.1.

TODO(phase-5-calibrate): Initial guess; tune from observed market structure
after 20+ live matches per PRD §9.3. RESEARCH §"Open Questions" #1 cites
5c as defensible starting point at typical Kalshi yes_bid/yes_ask spreads.
"""

MM_MIN_EDGE: Final[int] = 4  # cents
"""Minimum market spread (cents) for MM_BETWEEN_ROUND to engage.

MM_BETWEEN_ROUND fires when market.spread > MM_MIN_EDGE.
Source: DEC-001 v2 selection rule 5, PRD §2.1.

TODO(phase-5-calibrate): Initial guess; needs to exceed 2 * MIN_HALF_SPREAD
+ slippage budget so MM has room to quote inside the market. RESEARCH §"Open
Questions" #1.
"""

POST_PLANT_TAKE_THRESHOLD: Final[int] = 3  # cents
"""Post-plant directional-take threshold (cents) — narrower than between-round
because post-plant theo is a high-conviction state (DEC-007 v2).

POST_PLANT_QUOTE quoter takes when |theo - market| > POST_PLANT_TAKE_THRESHOLD,
otherwise quotes at theo +/- narrow spread.
Source: PRD §5.4, REQ-post-plant-quoter.

TODO(phase-5-calibrate): Initial guess.
"""

MIN_HALF_SPREAD: Final[int] = 3  # cents
"""MM half-spread floor (cents). MUST beat Kalshi commission + slippage per CRule 7.

Justification (RESEARCH Pitfall 4, verified 2026-05-09):
  - Kalshi taker fee at theo=50c: ceil(0.07 * 0.5 * 0.5 * 100) / 100 = 1.75c
  - Maker fee = 25% of taker = 0.44c (we quote post_only=True)
  - 3c half-spread + 0.44c maker fee = 2.56c net edge if theo is exact
  - Covers 1c of model slippage AND 1c of arbiter staleness slippage
Spread formula: spread = max(MIN_HALF_SPREAD, k * sqrt(vega_between)) + staleness_penalty.
Source: PRD §5.4, REQ-mm-quoter, RESEARCH §"Standard Stack" Kalshi fee curve.

TODO(phase-5-calibrate): Calibrate down to 2c only after Phase 5 paper-trade
shows 3c floor is tight (i.e., MM hypothetical fills are profitable net of fees
AND well above MIN_FILLS_PER_MATCH).
"""

MM_VEGA_SPREAD_K: Final[float] = 50.0  # TBD
"""Vega-to-spread scaling factor for MM_BETWEEN_ROUND quoter.

Half-spread formula (DEC-018 v2 / REQ-mm-quoter):
    hs = max(MIN_HALF_SPREAD, MM_VEGA_SPREAD_K * sqrt(vega_between))
          + staleness_penalty

Initial guess: 50.0 scales Phase 1's typical vega_between range
[0.001, 0.01] into a [1.5c, 5c] vega-driven band on top of the 3c floor.
Net effective spreads at the bounds:
  - vega = 0.001 (low conviction):  hs = max(3, 50*0.0316) = max(3, 1.58) = 3c
  - vega = 0.005 (mid):              hs = max(3, 50*0.0707) = max(3, 3.54) = 3.54c
  - vega = 0.01 (high):              hs = max(3, 50*0.1)    = max(3, 5)    = 5c
Source: DEC-018 v2 / PRD §5.4 / RESEARCH §"Code Examples" half-spread formula.

TODO(phase-5-calibrate): Tune k after 20+ live matches. If MM hypothetical
fills are ALL at the 3c floor (vega contribution is always below), reduce
k or raise vega normalization. If MM fills are ALL above 8c, raise k or
lower the floor.
"""

# --------------------------------------------------------------------------- #
# Phase 4 — portfolio Kelly v2 (DEC-023)                                      #
# --------------------------------------------------------------------------- #

SERIES_AGGREGATE_CAP_FRAC: Final[float] = 0.10
"""Per-series aggregate exposure cap (fraction of bankroll) — DEC-023 v2.

Bounds correlated exposure across moneyline + map handicaps + round handicaps
on the same series. PER_MARKET_CAP_FRAC alone (0.05) does NOT bound aggregate
correlated exposure; this layer adds the safety floor.

Sizer formula (DEC-023):
    f = max(0, KELLY_MULTIPLIER * f_full)
    f = min(f, PER_MARKET_CAP_FRAC)                              # 0.05
    headroom = max(0, SERIES_AGGREGATE_CAP_FRAC - exposure[s])  # 0.10
    f = min(f, headroom)
    return 0 if f == 0 else int(f * bankroll / ask)

TODO(phase-5-calibrate): Defensive initial guess. Recompute from observed
inter-market correlation after first paper-trade event. Full covariance-aware
Kelly is REQ-portfolio-correlation-kelly (Phase 7).
"""

# --------------------------------------------------------------------------- #
# Phase 4 — promotion gate (DEC-020 v2 — referenced by fill ledger / kill     #
# switches; primary consumer is Phase 5 paper-trade evaluation)               #
# --------------------------------------------------------------------------- #

RELATIVE_BRIER_EDGE_MIN: Final[float] = 0.02
"""Promotion gate: Brier(model) must beat Brier(market_mid) by this margin
over a 50-round window. Replaces v1 absolute Brier 0.22 floor (DEC-020 v2).

Source: DEC-020 v2, PRD §8, ROADMAP §5.3-5.4.
"""

MIN_FILLS_PER_MATCH: Final[int] = 3
"""Promotion gate: MM strategy is cut from production if hypothetical fills
averaged over a paper-trade event fall below this. DIRECTIONAL_TAKE
(and POST_PLANT_QUOTE) can promote independently per DEC-020 v2.

Source: DEC-020 v2, PRD §8.

TODO(phase-5-calibrate): Initial guess; tune from observed MM fill rates.
"""

# --------------------------------------------------------------------------- #
# Phase 4 — Kalshi endpoints                                                  #
# --------------------------------------------------------------------------- #

KALSHI_BASE_URL: Final[str] = "https://api.elections.kalshi.com/trade-api/v2"
"""Kalshi REST base URL (verified 2026-05-09 via docs.kalshi.com)."""

KALSHI_WS_URL: Final[str] = "wss://api.elections.kalshi.com/trade-api/ws/v2"
"""Kalshi WebSocket URL (verified 2026-05-09 via docs.kalshi.com/getting_started/quick_start_websockets)."""
