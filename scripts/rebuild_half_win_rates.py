"""Rebuild data/half_win_rates*.json with exponential time decay + hierarchical shrinkage.

Input: thunderedge research DB (tables research_matches, map_results, map_rounds, teams;
built by thunderedge/research/build_db.py). Regulation rounds only (1-24).

Model (all sums are time-decayed, weight w = 0.5 ** (age_days / half_life_days)):
  League map-side:  L[m,atk] = (W_atk + K_LEAGUE*0.5) / (N_atk + K_LEAGUE);  L[m,def] = 1 - L[m,atk]
  Team side offset: b_ts = E_w[L[m,s]] over the team's own rounds (its map mix)
                    T_ts = (W_ts + k_team*b_ts) / (N_ts + k_team)
                    d_ts = logit(T_ts) - logit(b_ts)
  Cell prior:       P0 = expit(logit(L[m,s]) + d_ts)       (team tendency moved onto the map)
  Cell rate:        (W_tms + k_map*P0) / (N_tms + k_map)
  fallback_level:   'none'   if effective cell rounds >= MIN_ROUNDS
                    'team'   if the cell is thin but the team has >= MIN_ROUNDS on that side
                    'league' otherwise

Output schema matches src/pricing/data.py HalfRates.from_json, plus "pre_shrunk": true so the
loader does not shrink a second time.

Usage:
  python scripts/rebuild_half_win_rates.py --db ../thunderedge/data/valorant_stats.db \
      --half-life 90 --k-map 40 --k-team 150 --out data/half_win_rates_v2.json
"""
from __future__ import annotations

import argparse
import json
import math
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np

MIN_ROUNDS = 15
K_LEAGUE = 50.0
EPOCH = datetime(2020, 1, 1)
SIDES = ("atk", "def")


def _days(ts: str) -> float:
    return (datetime.strptime(ts, "%Y-%m-%d %H:%M:%S") - EPOCH).total_seconds() / 86400.0


def logit(p: np.ndarray | float) -> np.ndarray | float:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def expit(x: np.ndarray | float) -> np.ndarray | float:
    return 1.0 / (1.0 + np.exp(-x))


@dataclass
class Rounds:
    """Two records per regulation round (winner + loser), as parallel numpy arrays."""

    day: np.ndarray        # float days since EPOCH
    team: np.ndarray       # int team_id
    map_idx: np.ndarray    # int into maps
    side: np.ndarray       # 0 atk / 1 def
    won: np.ndarray        # 0/1
    event: np.ndarray      # int event_id (for the legacy builder)
    maps: list[str]


def load_rounds(db_path: str | Path) -> Rounds:
    con = sqlite3.connect(db_path)
    q = """
      SELECT rm.date_utc, mr.map_name, r.winner_id, r.winner_side, rm.team1_id, rm.team2_id,
             rm.event_id
      FROM map_rounds r
      JOIN map_results mr ON mr.game_id = r.game_id
      JOIN research_matches rm ON rm.match_id = mr.match_id
      WHERE r.round_num <= 24 AND r.winner_side IN ('atk','def') AND rm.date_utc IS NOT NULL
    """
    rows = con.execute(q).fetchall()
    con.close()
    maps = sorted({r[1] for r in rows})
    mi = {m: i for i, m in enumerate(maps)}
    n = len(rows)
    day = np.empty(2 * n)
    team = np.empty(2 * n, dtype=np.int64)
    mp = np.empty(2 * n, dtype=np.int64)
    side = np.empty(2 * n, dtype=np.int8)
    won = np.empty(2 * n, dtype=np.int8)
    ev = np.empty(2 * n, dtype=np.int64)
    for i, (ts, m, w, ws, t1, t2, e) in enumerate(rows):
        d = _days(ts)
        loser = t2 if w == t1 else t1
        s = 0 if ws == "atk" else 1
        day[2 * i: 2 * i + 2] = d
        team[2 * i], team[2 * i + 1] = w, loser
        mp[2 * i: 2 * i + 2] = mi[m]
        side[2 * i], side[2 * i + 1] = s, 1 - s
        won[2 * i], won[2 * i + 1] = 1, 0
        ev[2 * i: 2 * i + 2] = e
    return Rounds(day, team, mp, side, won, ev, maps)


@dataclass
class Rates:
    league: dict[tuple[str, str], tuple[float, float, float]]          # (map, side) -> (W, N, rate)
    cells: dict[tuple[int, str, str], dict]                            # (team, map, side) -> entry
    team_side: dict[tuple[int, str], tuple[float, float]]              # (team, side) -> (N, delta)
    params: dict

    def rate(self, team: int, map_name: str, side: str) -> tuple[float, str]:
        e = self.cells.get((team, map_name, side))
        if e is not None:
            return e["rate"], e["fallback_level"]
        lg = self.league_rate(map_name, side)
        ts = self.team_side.get((team, side))
        if ts and ts[0] >= MIN_ROUNDS:
            return float(expit(logit(lg) + ts[1])), "team"
        return lg, "league"

    def league_rate(self, map_name: str, side: str) -> float:
        e = self.league.get((map_name, "atk"))
        atk = e[2] if e else 0.5
        return atk if side == "atk" else 1.0 - atk


def build(r: Rounds, as_of_day: float, half_life: float, k_map: float, k_team: float,
          window_days: float = 730.0) -> Rates:
    m = (r.day < as_of_day) & (r.day >= as_of_day - window_days)
    age = as_of_day - r.day[m]
    w = np.ones_like(age) if math.isinf(half_life) else 0.5 ** (age / half_life)
    team, mp, side, won = r.team[m], r.map_idx[m], r.side[m], r.won[m]
    nm = len(r.maps)

    # league map-side (atk records only; def = 1 - atk)
    a = side == 0
    W_atk = np.bincount(mp[a], weights=w[a] * won[a], minlength=nm)
    N_atk = np.bincount(mp[a], weights=w[a], minlength=nm)
    L_atk = (W_atk + K_LEAGUE * 0.5) / (N_atk + K_LEAGUE)
    L = np.stack([L_atk, 1 - L_atk], axis=1)  # [map, side]
    league = {}
    for i, mname in enumerate(r.maps):
        league[(mname, "atk")] = (float(W_atk[i]), float(N_atk[i]), float(L_atk[i]))
        league[(mname, "def")] = (float(N_atk[i] - W_atk[i]), float(N_atk[i]), float(1 - L_atk[i]))

    base = L[mp, side]
    # team x side aggregates
    teams, tinv = np.unique(team, return_inverse=True)
    key_ts = tinv * 2 + side
    nts = len(teams) * 2
    W_ts = np.bincount(key_ts, weights=w * won, minlength=nts)
    N_ts = np.bincount(key_ts, weights=w, minlength=nts)
    E_ts = np.bincount(key_ts, weights=w * base, minlength=nts)
    b_ts = np.where(N_ts > 0, E_ts / np.maximum(N_ts, 1e-12), 0.5)
    T_ts = (W_ts + k_team * b_ts) / (N_ts + k_team)
    d_ts = logit(T_ts) - logit(b_ts)
    team_side = {(int(teams[k // 2]), SIDES[k % 2]): (float(N_ts[k]), float(d_ts[k])) for k in range(nts)}

    # cells
    key_c = (tinv * nm + mp) * 2 + side
    nc = len(teams) * nm * 2
    W_c = np.bincount(key_c, weights=w * won, minlength=nc)
    N_c = np.bincount(key_c, weights=w, minlength=nc)
    R_c = np.bincount(key_c, minlength=nc)  # raw (undecayed) rounds
    cells = {}
    for k in np.nonzero(R_c)[0]:
        ti, rem = divmod(int(k), nm * 2)
        mi, si = divmod(rem, 2)
        tid = int(teams[ti])
        prior = float(expit(logit(L[mi, si]) + d_ts[ti * 2 + si]))
        rate = (W_c[k] + k_map * prior) / (N_c[k] + k_map)
        if N_c[k] >= MIN_ROUNDS:
            lvl = "none"
        elif N_ts[ti * 2 + si] >= MIN_ROUNDS:
            lvl = "team"
        else:
            lvl = "league"
        cells[(tid, r.maps[mi], SIDES[si])] = {
            "wins": round(float(W_c[k]), 3), "total": round(float(N_c[k]), 3),
            "raw_rounds": int(R_c[k]), "rate": round(float(rate), 6),
            "used_fallback": lvl != "none", "fallback_level": lvl,
        }
    return Rates(league, cells, team_side,
                 {"half_life_days": half_life, "k_map": k_map, "k_team": k_team,
                  "window_days": window_days, "as_of_day": as_of_day})


def build_legacy(r: Rounds, as_of_day: float) -> dict[tuple[int, str, str], tuple[float, float]]:
    """Replicates the pre-existing builder: per team, its most recent event before as_of has
    weight 1.0, the previous event 0.5, older excluded. Returns raw (W, N) per cell; the
    HalfRates loader then shrinks with SHRINK_PRIOR toward league map-side (also built here
    with the same event weights pooled over teams)."""
    m = r.day < as_of_day
    team, mp, side, won, ev, day = r.team[m], r.map_idx[m], r.side[m], r.won[m], r.event[m], r.day[m]
    w = np.zeros(len(team))
    for t in np.unique(team):
        it = team == t
        evs = {}
        for e, d in zip(ev[it], day[it], strict=True):
            evs[e] = max(evs.get(e, -1e18), d)
        order = sorted(evs, key=evs.get, reverse=True)
        wt = {order[0]: 1.0}
        if len(order) > 1:
            wt[order[1]] = 0.5
        w[it] = [wt.get(e, 0.0) for e in ev[it]]
    out = {}
    nm = len(r.maps)
    for mi in range(nm):
        for si in (0, 1):
            sel = (mp == mi) & (side == si)
            for t in np.unique(team[sel]):
                s2 = sel & (team == t)
                N = float(w[s2].sum())
                if N > 0:
                    out[(int(t), r.maps[mi], SIDES[si])] = (float((w[s2] * won[s2]).sum()), N)
    return out


def to_json(rates: Rates, tag_of: dict[int, str], as_of: str) -> dict:
    tm = {}
    for (tid, m, s), e in rates.cells.items():
        tm[f"{tag_of.get(tid, tid)}|{m}|{s}"] = e
    lg = {f"{m}|{s}": {"wins": round(W, 3), "total": round(N, 3), "rate": round(rt, 6)}
          for (m, s), (W, N, rt) in rates.league.items()}
    return {
        "team_map_side": tm, "league_map_side": lg, "overall_avg": 0.5,
        "min_rounds_threshold": MIN_ROUNDS, "maps_in_data": sorted({k[1] for k in rates.cells}),
        "pre_shrunk": True,
        "build": {**rates.params, "as_of": as_of, "method": "exp-decay + hierarchical shrink",
                  "script": "scripts/rebuild_half_win_rates.py"},
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--half-life", type=float, default=90.0)
    ap.add_argument("--k-map", type=float, default=40.0)
    ap.add_argument("--k-team", type=float, default=150.0)
    ap.add_argument("--window-days", type=float, default=730.0)
    ap.add_argument("--as-of", default=None, help="YYYY-MM-DD (default: now)")
    ap.add_argument("--out", default="data/half_win_rates_v2.json")
    a = ap.parse_args()
    r = load_rounds(a.db)
    as_of = a.as_of or datetime.utcnow().strftime("%Y-%m-%d")
    rates = build(r, _days(as_of + " 00:00:00"), a.half_life, a.k_map, a.k_team, a.window_days)
    con = sqlite3.connect(a.db)
    tag_of = {t: (tag or name) for t, tag, name in con.execute("SELECT team_id, tag, name FROM teams")}
    Path(a.out).write_text(json.dumps(to_json(rates, tag_of, as_of), indent=1, ensure_ascii=False),
                           encoding="utf-8")
    n = len(rates.cells)
    fb = sum(1 for e in rates.cells.values() if e["used_fallback"])
    med = float(np.median([e["raw_rounds"] for e in rates.cells.values()])) if n else 0
    print(f"wrote {a.out}: {n} cells, fallback share {fb / max(n, 1):.1%}, median raw rounds/cell {med}")


if __name__ == "__main__":
    main()
