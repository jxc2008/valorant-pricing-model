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
