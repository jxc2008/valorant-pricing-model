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
# Mode flip                                                                   #
# --------------------------------------------------------------------------- #

VEGA_DIRECTIONAL_THRESHOLD: Final[float] = 0.04  # TBD
"""Vega threshold above which the trading mode flips from MM to DIRECTIONAL.

Source: DEC-001 / CLAUDE.md "Domain constants" / roadmap.md §4.2.
TBD — initial guess; calibrate after 20+ live matches (PRD §9.2,
REQ-calibration-loop).
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
# Phase 2 — economy buckets (CON-economy-buckets / CLAUDE.md "Domain constants") #
# --------------------------------------------------------------------------- #

ECON_BUCKET_FULL_FLOOR: Final[int] = 20_000
"""Lower bound (inclusive) for `econ_bucket == "full"` (CON-economy-buckets).

Source: CLAUDE.md "Domain constants" / inherited from thunderedge/match_round_data.
Used by src.pricing.economy.credits_to_bucket. NEVER inline this literal — every
caller imports from here per CRule 12 / CON-no-magic-numbers.
"""

ECON_BUCKET_SEMI_BUY_FLOOR: Final[int] = 10_000
"""Lower bound (inclusive) for `econ_bucket == "semi-buy"` (CON-economy-buckets).

Source: CLAUDE.md "Domain constants". Range: [10000, 19999].
"""

ECON_BUCKET_SEMI_ECO_FLOOR: Final[int] = 5_000
"""Lower bound (inclusive) for `econ_bucket == "semi-eco"` (CON-economy-buckets).

Source: CLAUDE.md "Domain constants". Range: [5000, 9999]. Below this floor
(< 5000) the bucket is "eco".
"""

# --------------------------------------------------------------------------- #
# Phase 2 — Path B contingency (deferred per 02-RESEARCH.md Summary)          #
# --------------------------------------------------------------------------- #

OCR_FRAMES_PER_SECOND: Final[float] = 1.0
"""Path B OCR frame extraction rate (D-10 — only used if Path A fails).

Source: D-10 (CONTEXT.md) / 02-RESEARCH.md §"Project Constraints" #6.
Currently unused at runtime — Path A is the verified primary path. Constant
declared so the Path B contingency stub (scripts/ocr_round_events.py) has
its threshold pre-located in constants.py without a future planning loop.
"""
