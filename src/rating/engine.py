"""Dynamic rating engine (research). NOT wired into live_theo or src/quoting.

State (all Gaussian, round-logit units, kept as independent marginals Glicko-style):
  player strength       theta_p      team strength = mean over its current five
  region offset         rho_r        identified by cross-region (international) maps
  tier offset           tau_t        tier-2 vs tier-1 (inactive until tier-2 data is loaded)
  team x map offset     gamma_(t,m)  map-pool specialisation, strongly shrunk
  league map side       delta_m      attack advantage on map m

Round model for team A attacking against B on map m:
  logit P(A wins round) = S_A - S_B + gamma_A,m - gamma_B,m + delta_m      (A defending: -delta_m)
  S_X = mean(theta over X's five) + rho_region(X) + tau_tier(X)

After every map the involved states get a Laplace (Newton) update from the per-half round
counts, with the round likelihood down-weighted by ``kappa`` (rounds within a map are not
independent). Variances inflate with time (``q_*`` per day), at season boundaries
(``v_offseason``) and start wide for new players (``v0_player``); a new player's prior mean is
``w_newplayer`` x the mean of his known teammates.

Pre-match output: for each map, the mean/variance of the strength difference d and delta_m,
which the caller turns into round probabilities for the production map DP (see dp_table.py).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np


@dataclass(frozen=True)
class EngineParams:
    v0_player: float = 0.08
    q_player: float = 2e-4
    v_offseason: float = 0.02
    w_newplayer: float = 0.5
    v0_region: float = 0.04
    q_region: float = 2e-5
    v0_teammap: float = 0.01
    q_teammap: float = 2e-5
    v0_map: float = 0.01
    v0_tier: float = 0.25
    kappa: float = 0.5
    newton_steps: int = 2


@dataclass
class _State:
    mu: float
    var: float
    t: float          # day of last update
    season: int


@dataclass
class Team:
    """A side in a map: its current five, region, tier and team id."""

    team_id: int
    five: tuple[int, ...]
    region: str
    tier: int = 1


@dataclass
class Engine:
    p: EngineParams = field(default_factory=EngineParams)
    players: dict[int, _State] = field(default_factory=dict)
    regions: dict[str, _State] = field(default_factory=dict)
    tiers: dict[int, _State] = field(default_factory=dict)
    teammap: dict[tuple[int, str], _State] = field(default_factory=dict)
    maps: dict[str, _State] = field(default_factory=dict)

    # ------------------------------------------------------------------ priors / time
    def _cap_v0(self, kind: str) -> float:
        return {"player": self.p.v0_player, "region": self.p.v0_region, "tier": self.p.v0_tier,
                "teammap": self.p.v0_teammap, "map": self.p.v0_map}[kind]

    def _q(self, kind: str) -> float:
        return {"player": self.p.q_player, "region": self.p.q_region, "tier": 0.0,
                "teammap": self.p.q_teammap, "map": 1e-6}[kind]

    def _peek(self, kind: str, s: _State | None, t: float, season: int,
              new_mu: float = 0.0) -> tuple[float, float]:
        """(mu, var) as of time t, without mutating the stored state."""
        v0 = self._cap_v0(kind)
        if s is None:
            return new_mu, v0
        var = s.var + self._q(kind) * max(0.0, t - s.t)
        if kind == "player" and season > s.season:
            var += self.p.v_offseason
        return s.mu, min(var, v0 if kind != "player" else max(v0, s.var))

    def _new_player_mu(self, five: tuple[int, ...], t: float, season: int) -> float:
        known = [self._peek("player", self.players[q], t, season)[0] for q in five if q in self.players]
        return self.p.w_newplayer * (sum(known) / len(known)) if known else 0.0

    def _components(self, side: Team, sign: float, map_name: str, t: float, season: int
                    ) -> list[tuple[str, object, float, float, float]]:
        """(kind, key, coef, mu, var) for one side's strength terms on this map."""
        out: list[tuple[str, object, float, float, float]] = []
        nm = self._new_player_mu(side.five, t, season)
        for q in side.five:
            mu, var = self._peek("player", self.players.get(q), t, season, nm)
            out.append(("player", q, sign / len(side.five), mu, var))
        mu, var = self._peek("region", self.regions.get(side.region), t, season)
        out.append(("region", side.region, sign, mu, var))
        if side.tier != 1:
            mu, var = self._peek("tier", self.tiers.get(side.tier), t, season)
            out.append(("tier", side.tier, sign, mu, var))
        if self.p.v0_teammap > 0:
            mu, var = self._peek("teammap", self.teammap.get((side.team_id, map_name)), t, season)
            out.append(("teammap", (side.team_id, map_name), sign, mu, var))
        return out

    @staticmethod
    def _merge(comps: list[tuple[str, object, float, float, float]]
               ) -> tuple[list[tuple[str, object]], np.ndarray, np.ndarray, np.ndarray]:
        """Collapse duplicate states (same region on both sides cancels)."""
        idx: dict[tuple[str, object], int] = {}
        keys: list[tuple[str, object]] = []
        coef: list[float] = []
        mu: list[float] = []
        var: list[float] = []
        for kind, key, c, m, v in comps:
            k = (kind, key)
            if k in idx:
                coef[idx[k]] += c
                continue
            idx[k] = len(keys)
            keys.append(k)
            coef.append(c)
            mu.append(m)
            var.append(v)
        return keys, np.array(coef), np.array(mu), np.array(var)

    # ------------------------------------------------------------------ prediction
    def predict_map(self, a: Team, b: Team, map_name: str, t: float, season: int
                    ) -> tuple[float, float, float, float]:
        """(d_mean, d_var, delta_mean, delta_var): A-minus-B strength difference and the map's
        attack offset, both in round-logit units, as of time t (pre-match)."""
        comps = self._components(a, 1.0, map_name, t, season) + self._components(b, -1.0, map_name, t, season)
        _, coef, mu, var = self._merge(comps)
        dm, dv = self._peek("map", self.maps.get(map_name), t, season)
        return float(coef @ mu), float((coef ** 2) @ var), dm, dv

    # ------------------------------------------------------------------ update
    def update_map(self, a: Team, b: Team, map_name: str, t: float, season: int,
                   a_atk: tuple[int, int], a_def: tuple[int, int]) -> None:
        """Update from one map. a_atk = (rounds A won while attacking, rounds A attacked),
        a_def likewise for A defending. Regulation rounds only."""
        comps = self._components(a, 1.0, map_name, t, season) + self._components(b, -1.0, map_name, t, season)
        dm, dv = self._peek("map", self.maps.get(map_name), t, season)
        comps.append(("map", map_name, 0.0, dm, dv))
        keys, coef, mu0, var0 = self._merge(comps)
        j_map = len(keys) - 1
        halves = []
        for (k, n), dsign in ((a_atk, 1.0), (a_def, -1.0)):
            if n > 0:
                h = coef.copy()
                h[j_map] = dsign
                halves.append((h, float(k), float(n)))
        if not halves:
            return
        prec0 = 1.0 / var0
        m = mu0.copy()
        H = np.diag(prec0)
        for _ in range(self.p.newton_steps):
            g = -prec0 * (m - mu0)
            H = np.diag(prec0)
            for h, k, n in halves:
                pr = 1.0 / (1.0 + math.exp(-float(h @ m)))
                g += self.p.kappa * h * (k - n * pr)
                H += self.p.kappa * n * pr * (1 - pr) * np.outer(h, h)
            m = m + np.linalg.solve(H, g)
        post_var = np.diag(np.linalg.inv(H))
        store = {"player": self.players, "region": self.regions, "tier": self.tiers,
                 "teammap": self.teammap, "map": self.maps}
        for (kind, key), mu_new, v_new in zip(keys, m, post_var, strict=True):
            store[kind][key] = _State(float(mu_new), float(v_new), t, season)  # type: ignore[index]
