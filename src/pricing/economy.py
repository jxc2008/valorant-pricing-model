"""econ_bucket bucketing — CON-economy-buckets contract.

Shared between Phase 2 calibration ETL (`scripts/probe_round_events.py`) and
Phase 3 live `MatchState.econ_bucket` derivation (REQ-match-state-engine).
CRule 2 forbids two implementations of the same concept — this module is the
canonical one. NEVER duplicate this logic elsewhere; always import.

Bucket boundaries (CLAUDE.md "Domain constants" / CON-economy-buckets):
    full       credits >= ECON_BUCKET_FULL_FLOOR        (>= 20,000)
    semi-buy   credits >= ECON_BUCKET_SEMI_BUY_FLOOR    (>= 10,000)
    semi-eco   credits >= ECON_BUCKET_SEMI_ECO_FLOOR    (>= 5,000)
    eco        otherwise                                 (< 5,000)

Sources
-------
- CLAUDE.md "Domain constants" (CON-economy-buckets table)
- 02-RESEARCH.md §"Architectural Responsibility Map" (lift to src/pricing/ for Phase-3 share)
- 02-PATTERNS.md §"src/pricing/economy.py" (canonical skeleton)
- src/config/constants.py (ECON_BUCKET_*_FLOOR — single source of bucket floors)
"""

from __future__ import annotations

from src.config.constants import (
    ECON_BUCKET_FULL_FLOOR,
    ECON_BUCKET_SEMI_BUY_FLOOR,
    ECON_BUCKET_SEMI_ECO_FLOOR,
)


def credits_to_bucket(credits: int) -> str:
    """Map team-loadout credits to the canonical econ_bucket label.

    Returns one of {"full", "semi-buy", "semi-eco", "eco"} per CON-economy-buckets.

    Args:
        credits: Team-loadout total credits for the round (sum across the 5
            players' loadoutValue from rib.gg `economies[]`).

    Returns:
        The canonical bucket label. Negative credits (defensive — should not
        occur in real data) bucket as "eco".

    Source: CLAUDE.md "Domain constants" / CON-economy-buckets / D-07.
    """
    if credits >= ECON_BUCKET_FULL_FLOOR:
        return "full"
    if credits >= ECON_BUCKET_SEMI_BUY_FLOOR:
        return "semi-buy"
    if credits >= ECON_BUCKET_SEMI_ECO_FLOOR:
        return "semi-eco"
    return "eco"
