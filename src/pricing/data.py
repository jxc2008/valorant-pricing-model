"""Phase 1 pricing data shapes: HalfRates, TheoOutput.

MatchState moved to ``src/state/match_state.py`` per Phase 3 D-01
(REQ-match-state-engine). Use ``from src.state.match_state import MatchState``
or ``from src.state import MatchState``. The transition re-export shim that
lived here in plan 03-01 Task 1 has been deleted as of plan 03-01 Task 2.

Sources
-------
- prd.md §2 (TheoOutput contract) / §6 (state-only call surface)
- DEC-010 / DEC-012 / D-08 / D-09 / D-12 / D-14 / D-17 / D-18 / D-19
- 01-RESEARCH.md §10 (MatchState surface), Open Question 2 (HalfRates loader)
- reference/theo_engine.py:84-102 (Bayesian shrinkage salvage source)
- 01-CONTEXT.md `<decisions>` D-17 (team_a/team_b), D-18 (map_side_orients),
  D-19 (map_winners), D-20 (LiveTheoEngine bundle pattern)
- 03-CONTEXT.md D-01 (MatchState moved to src/state/match_state.py)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from src.config.constants import SHRINK_PRIOR

# --------------------------------------------------------------------------- #
# 1. TheoOutput — public pricing output (PRD §2 / DEC-010)                    #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class TheoOutput:
    """Single canonical pricing output.

    Fields per PRD §2 contract:
        theo_series: P(team A wins the BO3 series), clipped to
            [CONVICTION_CLIP_LOW, CONVICTION_CLIP_HIGH].
        theo_map: per-map P(team A wins map i), one per map in MatchState.map_pool;
            same clip applied. Marginalized from the SAME DP as theo_series
            (DEC-002 / CRule 2 — no parallel models).
        vega: variance of theo_series implied by current state per DEC-018 /
            D-10. Always >= 0.
        confidence: DP-mass-weighted aggregate of per-map data weight per D-08.
            In [0, 1].
    """

    theo_series: float
    theo_map: tuple[float, ...]
    vega: float
    confidence: float


# --------------------------------------------------------------------------- #
# 2. HalfRates — concrete impl satisfying round_types.HalfRates Protocol      #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class HalfRates:
    """Per-team-map-side win-rate source backed by data/half_win_rates.json.

    Satisfies src.pricing.round_types.HalfRates Protocol. Bayesian-shrunk
    rates per D-09 / reference/theo_engine.py:84-102 (salvage verbatim).
    Instantiated by the caller (Phase 4 quoter); passed into LiveTheoEngine
    constructor (D-20). Phase 1 tests construct synthetic HalfRates inline.
    """

    team_rates: dict[str, dict[str, Any]]
    league_rates: dict[str, dict[str, Any]]
    overall_avg: float

    @classmethod
    def from_json(cls, path: str | Path) -> HalfRates:
        """Load HalfRates from data/half_win_rates.json (Open Question 2 resolution).

        Schema (verified during planning):
            {
              "team_map_side":   {"<team>|<map>|<side>": {wins, total, rate, used_fallback}, ...},
              "league_map_side": {"<map>|<side>":        {wins, total, rate}, ...},
              "overall_avg": float (typically 0.5),
              ...
            }
        """
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            team_rates=data.get("team_map_side", {}),
            league_rates=data.get("league_map_side", {}),
            overall_avg=float(data.get("overall_avg", 0.5)),
        )

    def team(self, team: str, map_name: str, side: str) -> float:
        """Bayesian-shrunk win rate for team on map_name while playing side.

        Formula: ``(n * raw + SHRINK_PRIOR * prior) / (n + SHRINK_PRIOR)``.
        Source: reference/theo_engine.py:84-102 — salvage verbatim per D-09.

        Fallback chain: team_rates → league_rates → overall_avg (0.5).
        """
        league_key = f"{map_name}|{side}"
        lg = self.league_rates.get(league_key)
        prior: float = float(lg["rate"]) if lg else self.overall_avg
        team_key = f"{team}|{map_name}|{side}"
        entry = self.team_rates.get(team_key)
        if entry:
            n_val: float = float(entry.get("total", 0))
            raw: float = float(entry["rate"])
            return (n_val * raw + SHRINK_PRIOR * prior) / (n_val + SHRINK_PRIOR)
        return prior

    def team_entry(
        self, team: str, map_name: str, side: str
    ) -> Optional[dict[str, Any]]:  # noqa: UP045 — Optional[dict] satisfies Protocol shape
        """Raw team entry — powers _data_weight_for_map in live_theo.py."""
        return self.team_rates.get(f"{team}|{map_name}|{side}")
