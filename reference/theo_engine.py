"""
backend/theo_engine.py

Pre-match Markov series-winner theo engine.

Theo calculation:
  1. For each map in the pool, compute per-round win probabilities from
     half_win_rates.json (per team/map/side historical rates).
  2. Run a Markov DP over (a_score, b_score) states to get P(team_a wins map).
  3. Chain map probs into a BO3 series win probability.
  4. Blend market and model:
       final_theo = (1 - data_w) * market_p + data_w * model_series_p
     When data is thin (data_w -> 0): output = market price.
     When data is rich (data_w -> 1): output = pure Markov model probability.

Fallback chain for rate lookups:
  team-specific rate → league map/side average → overall average
"""

import json
import math
import os
from typing import Dict, List, Optional, Tuple

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

_DEFAULT_RATES_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    '..', 'data', 'half_win_rates.json'
)

REGULATION_HALF = 12
WIN_THRESHOLD   = 13
MIN_ROUNDS_FULL_WEIGHT = 15   # effective rounds for full data confidence
SHRINK_PRIOR    = 15.0        # Bayesian prior weight (in rounds) toward league average
SIGNAL_SCALE    = 0.10        # model_p must deviate this far from 0.5 for full weight


def _signal_strength(model_p: float) -> float:
    """
    Scale factor [0, 1] for how much the model's prediction deviates from coin-flip.

    model_p = 0.5  → 0.0  (model sees equal teams, no info above market)
    model_p = 0.6  → 1.0  (model has clear directional signal, full weight)

    Prevents phantom edges when both teams look average per round/map rates
    but the market prices one team as a heavy favorite due to overall quality.
    """
    return min(1.0, abs(model_p - 0.5) / SIGNAL_SCALE)


# --------------------------------------------------------------------------- #
# TheoEngine
# --------------------------------------------------------------------------- #

class TheoEngine:
    """
    Computes pre-match series win probabilities for Valorant BO3 markets.

    Args:
        rates_path: Path to half_win_rates.json produced by half_win_rate_model.py.
    """

    def __init__(self, rates_path: str = _DEFAULT_RATES_PATH):
        rates_path = os.path.normpath(rates_path)
        if not os.path.exists(rates_path):
            raise FileNotFoundError(
                f'half_win_rates.json not found at {rates_path}. '
                'Run scripts/half_win_rate_model.py first.'
            )
        with open(rates_path) as f:
            data = json.load(f)

        self._team_rates: dict  = data.get('team_map_side', {})
        self._league_rates: dict = data.get('league_map_side', {})
        self._overall_avg: float = data.get('overall_avg', 0.5)

    # ---------------------------------------------------------------------- #
    # Rate lookups
    # ---------------------------------------------------------------------- #

    def _get_rate(self, team: str, map_name: str, side: str) -> float:
        """
        P(team wins a single round) on this map/side.

        Applies Bayesian shrinkage toward the league average when team-specific
        data exists but sample size is small.  Falls back to league average (then
        overall average) when no team data is available at all.
        """
        lg    = self._league_rates.get(f'{map_name}|{side}')
        prior = lg['rate'] if lg else self._overall_avg

        entry = self._team_rates.get(f'{team}|{map_name}|{side}')
        if entry:
            n    = entry.get('total', 0)
            raw  = entry['rate']
            # Shrink toward league average: as n grows the estimate converges to raw
            return (n * raw + SHRINK_PRIOR * prior) / (n + SHRINK_PRIOR)

        return prior

    def _data_weight(self, team_a: str, team_b: str, map_name: str) -> float:
        """
        Confidence weight [0, 1] for a (team_a, team_b, map) combination.

        1.0 means both teams have at least MIN_ROUNDS_FULL_WEIGHT effective
        rounds on this map across both sides.  Below that we linearly shrink
        toward 0, which causes the market-odds adjustment to shrink toward 0
        (i.e. just use the market price as-is).
        """
        # Require both teams to have real (non-fallback) data.
        # Data weight is the minimum of each team's coverage so that one
        # team having rich data cannot compensate for the other having none.
        team_weights = []
        for team in (team_a, team_b):
            team_total = 0.0
            team_count = 0
            for side in ('atk', 'def'):
                entry = self._team_rates.get(f'{team}|{map_name}|{side}')
                if entry and not entry.get('used_fallback', False):
                    team_total += entry.get('total', 0)
                    team_count += 1
            if team_count == 0:
                return 0.0  # one team has no real data → no confidence
            team_weights.append(team_total / team_count)
        avg_rounds = min(team_weights)   # bottlenecked by weaker team's coverage
        return min(1.0, avg_rounds / MIN_ROUNDS_FULL_WEIGHT)

    def preferred_side(self, team: str, map_name: str) -> str:
        """
        Returns 'atk' or 'def' — whichever side the team wins more rounds on.

        Used to model side selection in the veto: the team given side choice
        will always pick their stronger half on that map.
        """
        atk = self._get_rate(team, map_name, 'atk')
        def_ = self._get_rate(team, map_name, 'def')
        return 'atk' if atk >= def_ else 'def'

    # ---------------------------------------------------------------------- #
    # Single-round probability
    # ---------------------------------------------------------------------- #

    def _round_win_prob(
        self,
        team_a: str,
        team_b: str,
        map_name: str,
        team_a_side: str,
    ) -> float:
        """
        P(team_a wins one round) given current sides.

        Blend: (team_a's rate on their side + team_b's weakness on opposite side) / 2
        """
        team_b_side = 'def' if team_a_side == 'atk' else 'atk'
        a_rate = self._get_rate(team_a, map_name, team_a_side)
        b_rate = self._get_rate(team_b, map_name, team_b_side)
        p = (a_rate + (1.0 - b_rate)) / 2.0
        return max(0.05, min(0.95, p))

    # ---------------------------------------------------------------------- #
    # Markov map win probability
    # ---------------------------------------------------------------------- #

    def _markov_map_win(self, p1: float, p2: float) -> float:
        """
        P(team_a wins map) via DP over (a_score, b_score) states.

        p1: P(team_a wins round) in phase 1 (rounds 1-12)
        p2: P(team_a wins round) in phase 2 (rounds 13-24)
        OT (12-12) resolved at 0.5.
        """
        dp = {(0, 0): 1.0}
        win_prob = 0.0

        for total in range(WIN_THRESHOLD * 2):
            for a in range(max(0, total - (WIN_THRESHOLD - 1)),
                           min(total + 1, WIN_THRESHOLD)):
                b = total - a
                if b < 0 or b >= WIN_THRESHOLD:
                    continue
                prob = dp.get((a, b), 0.0)
                if prob < 1e-14:
                    continue

                if total < REGULATION_HALF:
                    p = p1
                elif total < REGULATION_HALF * 2:
                    p = p2
                else:
                    p = 0.5  # OT

                new_a = a + 1
                if new_a == WIN_THRESHOLD:
                    win_prob += prob * p
                else:
                    dp[(new_a, b)] = dp.get((new_a, b), 0.0) + prob * p

                new_b = b + 1
                if new_b < WIN_THRESHOLD:
                    dp[(a, new_b)] = dp.get((a, new_b), 0.0) + prob * (1.0 - p)

        return win_prob

    def map_win_prob(
        self,
        team_a: str,
        team_b: str,
        map_name: str,
        team_a_starts: str = 'atk',
    ) -> float:
        """P(team_a wins this map) from score 0-0."""
        p1 = self._round_win_prob(team_a, team_b, map_name, team_a_starts)
        p2_side = 'def' if team_a_starts == 'atk' else 'atk'
        p2 = self._round_win_prob(team_a, team_b, map_name, p2_side)
        return self._markov_map_win(p1, p2)

    # ---------------------------------------------------------------------- #
    # Series win probability (model only, no market adjustment)
    # ---------------------------------------------------------------------- #

    def model_series_prob(
        self,
        team_a: str,
        team_b: str,
        map_pool: List[str],
        team_a_sides: Dict[str, str],
    ) -> float:
        """
        P(team_a wins BO3 series) using only the Markov map model.

        map_pool:     list of map names in play order (2 or 3 maps)
        team_a_sides: {map_name: 'atk'|'def'} — team_a's starting side.
                      Maps not listed default to 'atk'.
        """
        if len(map_pool) < 2:
            raise ValueError('map_pool must have at least 2 maps')

        probs = []
        for m in map_pool[:3]:
            side = team_a_sides.get(m, 'atk')
            probs.append(self.map_win_prob(team_a, team_b, m, side))

        p1, p2 = probs[0], probs[1]
        p3 = probs[2] if len(probs) >= 3 else 0.5

        p_2_0 = p1 * p2
        p_2_1 = p1 * (1 - p2) * p3 + (1 - p1) * p2 * p3
        return p_2_0 + p_2_1

    # ---------------------------------------------------------------------- #
    # Market-implied per-map win probability
    # ---------------------------------------------------------------------- #

    @staticmethod
    def _solve_map_win_prob(series_p: float) -> float:
        """
        Invert P(win BO3) = 3q^2 - 2q^3 = series_p to find per-map win prob q.

        Used as the fallback for maps where neither team has data: on an unknown
        map the model has no edge, so we assume the stronger team wins each map
        at the rate implied by the market series price.  This ensures no-data
        maps contribute zero edge vs market (rather than pulling toward 0.5).
        """
        lo, hi = 0.0, 1.0
        for _ in range(60):
            mid = (lo + hi) / 2.0
            if 3.0 * mid * mid - 2.0 * mid * mid * mid < series_p:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2.0

    # ---------------------------------------------------------------------- #
    # Final theo with market-odds adjustment
    # ---------------------------------------------------------------------- #

    def series_theo(
        self,
        team_a: str,
        team_b: str,
        map_pool: List[str],
        team_a_sides: Dict[str, str],
        kalshi_yes_ask: int,
    ) -> Tuple[float, float, str]:
        """
        Compute final theo for team_a winning the series.

        Formula:
            market_p   = kalshi_yes_ask / 100
            model_p    = Markov series win prob
            data_w     = confidence weight in [0, 1] based on sample size
            final_theo = (1 - data_w) * market_p + data_w * model_p

        Maps with no team-specific data use the market-implied per-map win
        probability as fallback (not league average), so unknown maps generate
        zero edge vs market.  data_w = 0 => final_theo = market_p exactly.

        Returns:
            (final_theo, data_weight, confidence_label)
        """
        market_p   = kalshi_yes_ask / 100.0
        fallback_q = self._solve_map_win_prob(market_p)

        map_probs = []
        weights   = []
        for m in map_pool[:3]:
            dw = self._data_weight(team_a, team_b, m)
            weights.append(dw)
            if dw == 0.0:
                map_probs.append(fallback_q)
            else:
                side = team_a_sides.get(m, 'atk')
                map_probs.append(self.map_win_prob(team_a, team_b, m, side))

        p1, p2 = map_probs[0], map_probs[1]
        p3 = map_probs[2] if len(map_probs) >= 3 else fallback_q
        model_p = p1 * p2 + p1 * (1 - p2) * p3 + (1 - p1) * p2 * p3

        data_w     = sum(weights) / len(weights)
        eff_dw     = data_w * _signal_strength(model_p)
        final_theo = max(0.03, min(0.97, market_p + eff_dw * (model_p - market_p)))

        conf = 'HIGH' if data_w >= 0.8 else ('MED' if data_w >= 0.4 else 'LOW')
        return final_theo, data_w, conf

    def series_theo_from_map_probs(
        self,
        map_pool: List[str],
        map_win_probs: Dict[str, float],
        map_data_weights: Dict[str, float],
        kalshi_yes_ask: int,
    ) -> Tuple[float, float, str]:
        """
        Series theo from pre-computed per-map win probabilities.

        Market-anchored design: the market's implied per-map win probability
        (fallback_q, derived by inverting the BO3 formula) is the baseline for
        every map.  Per-map data only adjusts the *deviation* from that baseline:

            p_map = fallback_q + dw_map * (blended_p - 0.5)

        This guarantees:
          - dw_map = 0 → p_map = fallback_q → series win = market_p (no edge invented)
          - blended_p = 0.5 → no adjustment regardless of dw (truly neutral map)
          - Only genuine map-specific relative edges vs 50/50 generate deviation

        The pick/ban simulation contributes by concentrating the pool on maps where
        each team has positive deviations — that concentration IS the model's signal.
        No outer market-adjustment step is needed since model_p is already anchored.

        Args:
            map_pool:         Ordered list of maps [pick_a, pick_b, decider].
            map_win_probs:    {map: P(team_a wins map)} — caller-computed blended estimate.
            map_data_weights: {map: confidence in [0,1]} for each map-specific estimate.
            kalshi_yes_ask:   YES ask price in cents.
        """
        market_p   = kalshi_yes_ask / 100.0
        fallback_q = self._solve_map_win_prob(market_p)

        probs, weights = [], []
        for m in map_pool[:3]:
            dw = map_data_weights.get(m, 0.0)
            weights.append(dw)
            blended_p = map_win_probs.get(m, fallback_q)
            # Weighted average of market prior (fallback_q) and map-specific data.
            # When dw=0: p_map = fallback_q (pure market, no edge invented).
            # When dw=1: p_map = blended_p (full confidence in map data).
            # Deviation from market = dw * (blended_p - fallback_q), so only
            # genuine map-specific edges beyond the market baseline create movement.
            p_map = (1.0 - dw) * fallback_q + dw * blended_p
            probs.append(max(0.03, min(0.97, p_map)))

        p1, p2 = probs[0], probs[1]
        p3 = probs[2] if len(probs) >= 3 else fallback_q
        model_p = p1 * p2 + p1 * (1 - p2) * p3 + (1 - p1) * p2 * p3

        data_w     = sum(weights) / len(weights)
        final_theo = max(0.03, min(0.97, model_p))
        conf = 'HIGH' if data_w >= 0.5 else ('MED' if data_w >= 0.2 else 'LOW')
        return final_theo, data_w, conf

    # ---------------------------------------------------------------------- #
    # Side-agnostic variant (when sides are unknown)
    # ---------------------------------------------------------------------- #

    def series_theo_no_sides(
        self,
        team_a: str,
        team_b: str,
        map_pool: List[str],
        kalshi_yes_ask: int,
    ) -> Tuple[float, float, str]:
        """
        Same as series_theo but averages over both possible starting sides
        for each map.  Use when pick/ban sides haven't been announced yet.
        """
        market_p   = kalshi_yes_ask / 100.0
        fallback_q = self._solve_map_win_prob(market_p)

        atk_probs, def_probs, weights = [], [], []
        for m in map_pool[:3]:
            dw = self._data_weight(team_a, team_b, m)
            weights.append(dw)
            if dw == 0.0:
                atk_probs.append(fallback_q)
                def_probs.append(fallback_q)
            else:
                atk_probs.append(self.map_win_prob(team_a, team_b, m, 'atk'))
                def_probs.append(self.map_win_prob(team_a, team_b, m, 'def'))

        def _bo3(p: list) -> float:
            fq = fallback_q
            p3 = p[2] if len(p) >= 3 else fq
            return p[0]*p[1] + p[0]*(1-p[1])*p3 + (1-p[0])*p[1]*p3

        model_p = (_bo3(atk_probs) + _bo3(def_probs)) / 2.0

        data_w     = sum(weights) / len(weights)
        eff_dw     = data_w * _signal_strength(model_p)
        final_theo = max(0.03, min(0.97, market_p + eff_dw * (model_p - market_p)))
        conf = 'HIGH' if data_w >= 0.8 else ('MED' if data_w >= 0.4 else 'LOW')
        return final_theo, data_w, conf
