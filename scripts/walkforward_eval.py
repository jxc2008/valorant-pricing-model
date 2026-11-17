"""Walk-forward evaluation of pre-match map / series P(win) vs the de-vigged Thunderpick close.

For each test season Y in --test-seasons:
  1. Tune (half_life, k_map) on seasons < Y only: map-level log loss of rolling predictions
     (rates rebuilt as of each match date, data strictly before it).
  2. Predict every season-Y match with the tuned params (still rolling as-of).
  3. Fit the Benter blend  logit(p) = a*logit(model) + b*logit(market)  on seasons < Y
     (two-sided market rows only) and score it on season Y.

Variants scored on the test seasons:
  legacy_bt   legacy builder (current event 1.0 / previous 0.5, single shrink) + old blend (L=0.5)
  legacy_log5 legacy builder + new log5 blend
  v2_log5     decayed hierarchical builder + log5 blend (tuned)
  market      de-vigged Thunderpick (two-sided snapshot where available)
  benter      blend of v2_log5 and market

Per map, P(A wins) = mean over A starting atk / def of the production within-map DP
(src.pricing.live_theo._within_map_p_a_wins). Series P composes per-map P over the veto pool
(picks then decider) — exact under the DP's map independence. Writes JSON for the report.

Usage: python scripts/walkforward_eval.py --db ../thunderedge/data/valorant_stats.db \
          --out ../thunderedge/research/out/walkforward.json
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.rebuild_half_win_rates import (  # noqa: E402
    Rates,
    _days,
    build,
    build_legacy,
    load_rounds,
)
from src.pricing.data import HalfRates  # noqa: E402
from src.pricing.live_theo import _within_map_p_a_wins  # noqa: E402
from src.state.match_state import MatchState  # noqa: E402

HALF_LIVES = [30.0, 60.0, 120.0, 240.0, math.inf]
K_MAPS = [10.0, 30.0, 90.0, 270.0, 810.0]  # 90 was a boundary optimum in the first run
K_TEAM = 150.0
EPS = 1e-4


class _FlatLeague(HalfRates):
    """Old blend: league side rate fixed at 0.5 -> log5 reduces to Bradley-Terry."""

    def league(self, map_name: str, side: str) -> float:  # type: ignore[override]
        return 0.5


def halfrates_from_v2(r: Rates) -> HalfRates:
    tm = {f"{t}|{m}|{s}": e for (t, m, s), e in r.cells.items()}
    # thin cells with no entry must fall back to the team-offset prior, not the league rate:
    for (t, s), (n, _d) in r.team_side.items():
        if n < 15:
            continue
        for (m, s2) in r.league:
            if s2 == s and f"{t}|{m}|{s}" not in tm:
                tm[f"{t}|{m}|{s}"] = {"rate": r.rate(t, m, s)[0], "total": 0.0,
                                      "used_fallback": True}
    lg = {f"{m}|{s}": {"rate": v[2], "total": v[1]} for (m, s), v in r.league.items()}
    return HalfRates(team_rates=tm, league_rates=lg, overall_avg=0.5, pre_shrunk=True)


def halfrates_from_legacy(cells: dict, flat: bool) -> HalfRates:
    lgW: dict = defaultdict(float)
    lgN: dict = defaultdict(float)
    tm = {}
    for (t, m, s), (W, N) in cells.items():
        tm[f"{t}|{m}|{s}"] = {"wins": W, "total": N, "rate": W / N, "used_fallback": N < 15}
        lgW[(m, s)] += W
        lgN[(m, s)] += N
    lg = {}
    for (m, s), N in lgN.items():
        if s == "atk":
            lg[f"{m}|atk"] = {"rate": lgW[(m, s)] / N, "total": N}
    cls = _FlatLeague if flat else HalfRates
    return cls(team_rates=tm, league_rates=lg, overall_avg=0.5)


def map_p(hr: HalfRates, a: int, b: int, pool: tuple[str, ...], idx: int) -> float:
    ms = MatchState(f"{a}-{b}", str(a), str(b), pool, ("a_atk",) * len(pool),
                    (None,) * len(pool), {}, 0, 0, 0, 0, 0, "a_atk", False, None, None,
                    None, 0, 0.0)
    ps = [_within_map_p_a_wins(pool, idx, side, (None,) * len(pool), ms, hr)
          for side in ("a_atk", "a_def")]
    return 0.5 * (ps[0] + ps[1])


def series_p(ps: list[float], best_of: int) -> float:
    need = best_of // 2 + 1

    def rec(i: int, wa: int, wb: int) -> float:
        if wa == need:
            return 1.0
        if wb == need or i >= len(ps):
            return 0.0
        return ps[i] * rec(i + 1, wa + 1, wb) + (1 - ps[i]) * rec(i + 1, wa, wb + 1)

    return rec(0, 0, 0)


def ll(p: np.ndarray, y: np.ndarray) -> np.ndarray:
    p = np.clip(p, EPS, 1 - EPS)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def lg(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, EPS, 1 - EPS)
    return np.log(p / (1 - p))


def fit_logit_noint(X: np.ndarray, y: np.ndarray, iters: int = 50) -> np.ndarray:
    """Logistic regression without intercept, Newton-Raphson."""
    beta = np.zeros(X.shape[1])
    for _ in range(iters):
        p = 1 / (1 + np.exp(-X @ beta))
        g = X.T @ (y - p)
        H = (X * (p * (1 - p))[:, None]).T @ X
        step = np.linalg.solve(H + 1e-9 * np.eye(len(beta)), g)
        beta += step
        if np.abs(step).max() < 1e-10:
            break
    return beta


def cluster_boot(vals: dict[str, np.ndarray], clusters: np.ndarray, n: int = 2000,
                 seed: int = 0) -> dict[str, tuple[float, float, float]]:
    rng = np.random.default_rng(seed)
    uc = np.unique(clusters)
    idx = {c: np.nonzero(clusters == c)[0] for c in uc}
    out = {}
    draws = {k: [] for k in vals}
    for _ in range(n):
        pick = np.concatenate([idx[c] for c in rng.choice(uc, size=len(uc), replace=True)])
        for k, v in vals.items():
            draws[k].append(float(np.mean(v[pick])))
    for k, v in vals.items():
        out[k] = (float(np.mean(v)), float(np.percentile(draws[k], 2.5)),
                  float(np.percentile(draws[k], 97.5)))
    return out


def load_matches(db: str) -> list[dict]:
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    ms = []
    teams_ok = {r[0] for r in con.execute("SELECT team_id FROM teams WHERE home_region IS NOT NULL")}
    for r in con.execute("""SELECT * FROM research_matches WHERE winner_id IS NOT NULL
                            AND map_pool IS NOT NULL ORDER BY date_utc"""):
        if r["team1_id"] not in teams_ok or r["team2_id"] not in teams_ok:
            continue  # showmatches / all-star teams
        pool = tuple(json.loads(r["map_pool"]))
        if r["best_of"] not in (3, 5) or len(pool) != r["best_of"]:
            continue
        maps = con.execute("""SELECT map_num, map_name, team1_score, team2_score FROM map_results
                              WHERE match_id=? ORDER BY map_num""", (r["match_id"],)).fetchall()
        two = {row[0]: row[1] for row in con.execute(
            "SELECT team_id, odds FROM prematch_odds WHERE match_id=? AND book='thunderpick'",
            (r["match_id"],))}
        win_only = {row[0]: row[1] for row in con.execute(
            "SELECT team_id, odds FROM match_odds WHERE match_id=? AND book='thunderpick'",
            (r["match_id"],))}
        ms.append({"match_id": r["match_id"], "date": r["date_utc"], "season": r["season"],
                   "event_id": r["event_id"], "best_of": r["best_of"], "a": r["team1_id"],
                   "b": r["team2_id"], "y": int(r["winner_id"] == r["team1_id"]), "pool": pool,
                   "maps": [(m[1], int(m[2] > m[3])) for m in maps if m[2] is not None],
                   "two_sided": two if len(two) == 2 else None, "winner_only": win_only})
    return ms


def market_p(m: dict, overround: float) -> tuple[float | None, str]:
    if m["two_sided"]:
        ia, ib = 1 / m["two_sided"][m["a"]], 1 / m["two_sided"][m["b"]]
        return ia / (ia + ib), "two_sided"
    if m["winner_only"]:
        (tid, o), = list(m["winner_only"].items())[:1]
        pw = (1 / o) / overround
        return (pw if tid == m["a"] else 1 - pw), "winner_only"
    return None, "none"


def predict(ms: list[dict], rounds, variant: str, params: tuple[float, float] | None) -> dict:
    cache: dict = {}
    out = {}
    for m in ms:
        day = math.floor(_days(m["date"]))
        if day not in cache:
            if variant.startswith("legacy"):
                cache = {day: halfrates_from_legacy(build_legacy(rounds, day), variant == "legacy_bt")}
            else:
                hl, km = params  # type: ignore[misc]
                cache = {day: halfrates_from_v2(build(rounds, day, hl, km, K_TEAM))}
        hr = cache[day]
        pm = [map_p(hr, m["a"], m["b"], m["pool"], i) for i in range(len(m["pool"]))]
        lookups = []
        for t in (m["a"], m["b"]):
            for mapname in m["pool"]:
                for side in ("atk", "def"):
                    e = hr.team_rates.get(f"{t}|{mapname}|{side}")
                    n = float(e.get("total", 0)) if e else 0.0
                    lookups.append((e is not None and n >= 15, n, int(e.get("raw_rounds", 0)) if e else 0))
        played = []
        for name, ya in m["maps"]:
            if name in m["pool"]:
                played.append((pm[m["pool"].index(name)], ya))
        out[m["match_id"]] = {"series": series_p(pm, m["best_of"]), "maps": played,
                              "lookups": lookups}
    return out


def map_logloss(pred: dict, ids: list[int]) -> float:
    ps, ys = [], []
    for i in ids:
        for p, y in pred[i]["maps"]:
            ps.append(p)
            ys.append(y)
    return float(np.mean(ll(np.array(ps), np.array(ys)))) if ps else float("nan")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--test-seasons", default="2025,2026")
    ap.add_argument("--overrounds", default="1.04,1.06,1.08")
    a = ap.parse_args()
    rounds = load_rounds(a.db)
    ms = load_matches(a.db)
    tests = [int(x) for x in a.test_seasons.split(",")]
    ors = [float(x) for x in a.overrounds.split(",")]
    print(f"{len(ms)} matches with veto pool; seasons {sorted({m['season'] for m in ms})}", flush=True)

    # rolling predictions for every grid point over ALL matches (each prediction uses only
    # data before its own date, so computing them once is leak-free; selection is per fold)
    preds: dict = {}
    for hl, km in itertools.product(HALF_LIVES, K_MAPS):
        preds[("v2", hl, km)] = predict(ms, rounds, "v2", (hl, km))
        print(f"  v2 hl={hl} k={km} done", flush=True)
    preds["legacy_bt"] = predict(ms, rounds, "legacy_bt", None)
    preds["legacy_log5"] = predict(ms, rounds, "legacy_log5", None)

    report: dict = {"n_matches": len(ms), "folds": {}, "grid": HALF_LIVES and
                    {"half_lives": [str(h) for h in HALF_LIVES], "k_maps": K_MAPS, "k_team": K_TEAM}}
    for Y in tests:
        tr = [m["match_id"] for m in ms if m["season"] < Y]
        te = [m for m in ms if m["season"] == Y]
        if not tr or not te:
            continue
        grid = {f"{hl}|{km}": map_logloss(preds[("v2", hl, km)], tr)
                for hl, km in itertools.product(HALF_LIVES, K_MAPS)}
        best = min(grid, key=grid.get)
        hl, km = (float(x) for x in best.split("|"))
        best_pred = preds[("v2", hl, km)]
        fold: dict = {"train_n_matches": len(tr), "test_n_matches": len(te), "grid_train_map_ll": grid,
                      "chosen": {"half_life_days": hl, "k_map": km}}
        # map-level test metrics
        mp_rows = defaultdict(list)
        mp_ev = []
        for m in te:
            for v in ("legacy_bt", "legacy_log5"):
                for p, y in preds[v][m["match_id"]]["maps"]:
                    mp_rows[v].append((p, y))
            for p, y in best_pred[m["match_id"]]["maps"]:
                mp_rows["v2_log5"].append((p, y))
                mp_ev.append(m["event_id"])
        fold["lookup_coverage"] = {}
        for v, pr in (("legacy", preds["legacy_log5"]), ("v2", best_pred)):
            lk = [x for m in te for x in pr[m["match_id"]]["lookups"]]
            fold["lookup_coverage"][v] = {
                "n_lookups": len(lk),
                "fallback_share": float(np.mean([not ok for ok, _, _ in lk])),
                "median_effective_rounds": float(np.median([n for _, n, _ in lk])),
                "median_raw_rounds": float(np.median([r for _, _, r in lk])) if v == "v2" else None}
        fold["map_level"] = {}
        for v, rows in mp_rows.items():
            p, y = np.array([r[0] for r in rows]), np.array([r[1] for r in rows])
            fold["map_level"][v] = {"n_maps": len(rows), "log_loss": float(ll(p, y).mean()),
                                    "brier": float(((p - y) ** 2).mean())}
        # series-level, by market type
        for orr in ors:
            key = f"overround_{orr}"
            rows = []
            for m in te:
                mk, kind = market_p(m, orr)
                if mk is None:
                    continue
                rows.append((m, mk, kind))
            if not rows:
                continue
            y = np.array([r[0]["y"] for r in rows], dtype=float)
            ev = np.array([r[0]["event_id"] for r in rows])
            two = np.array([r[2] == "two_sided" for r in rows])
            P = {"market": np.array([r[1] for r in rows]),
                 "v2_log5": np.array([best_pred[r[0]["match_id"]]["series"] for r in rows]),
                 "legacy_bt": np.array([preds["legacy_bt"][r[0]["match_id"]]["series"] for r in rows]),
                 "legacy_log5": np.array([preds["legacy_log5"][r[0]["match_id"]]["series"] for r in rows])}
            # Benter fit on TRAIN seasons, two-sided rows only (winner-only market feature is
            # outcome-dependent through the overround assumption -> biased coefficients)
            trm = [m for m in ms if m["season"] < Y and m["two_sided"]]
            benter = None
            if len(trm) >= 30:
                Xtr = np.array([[lg(np.array(best_pred[m["match_id"]]["series"])),
                                 lg(np.array(market_p(m, orr)[0]))] for m in trm])
                ytr = np.array([m["y"] for m in trm], dtype=float)
                coef = fit_logit_noint(Xtr, ytr)
                P["benter"] = 1 / (1 + np.exp(-(coef[0] * lg(P["v2_log5"]) + coef[1] * lg(P["market"]))))
                benter = {"a_model": float(coef[0]), "b_market": float(coef[1]), "n_train": len(trm)}
            out = {"benter_fit": benter}
            for subset, mask in (("all", np.ones(len(rows), bool)), ("two_sided", two),
                                 ("winner_only", ~two)):
                if mask.sum() < 10:
                    continue
                vals = {f"ll_{k}": ll(v[mask], y[mask]) for k, v in P.items()}
                vals.update({f"brier_{k}": (v[mask] - y[mask]) ** 2 for k, v in P.items()})
                vals.update({f"ll_diff_{k}_minus_market":
                             ll(P[k][mask], y[mask]) - ll(P["market"][mask], y[mask])
                             for k in P if k != "market"})
                out[subset] = {"n_series": int(mask.sum()), "n_events": int(len(np.unique(ev[mask]))),
                               "metrics": cluster_boot(vals, ev[mask])}
            fold[key] = out
        report["folds"][str(Y)] = fold
        print(f"fold {Y}: chosen hl={hl} k={km}; test n={len(te)}", flush=True)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(report, indent=1))
    print("wrote", a.out)

    # Production artifact: v2 rates on ALL data with the latest fold's train-chosen params.
    # Written beside (not over) the live data/half_win_rates.json.
    from scripts.rebuild_half_win_rates import to_json
    last = report["folds"][max(report["folds"])]["chosen"]
    as_of_day = math.floor(float(rounds.day.max())) + 1
    final = build(rounds, as_of_day, last["half_life_days"], last["k_map"], K_TEAM)
    con = sqlite3.connect(a.db)
    tag_of = {t: (tag or name) for t, tag, name in con.execute("SELECT team_id, tag, name FROM teams")}
    repo = Path(__file__).resolve().parent.parent
    v2_path = repo / "data" / "half_win_rates_v2.json"
    v2_path.write_text(json.dumps(to_json(final, tag_of, "latest data"), indent=1, ensure_ascii=False),
                       encoding="utf-8")
    old = json.loads((repo / "data" / "half_win_rates.json").read_text(encoding="utf-8"))["team_map_side"]
    summ = {
        "before": {"file": "data/half_win_rates.json", "cells": len(old),
                   "fallback_share": float(np.mean([bool(e.get("used_fallback")) for e in old.values()])),
                   "median_rounds": float(np.median([float(e.get("total", 0)) for e in old.values()]))},
        "after": {"file": "data/half_win_rates_v2.json", "cells": len(final.cells),
                  "fallback_share": float(np.mean([e["used_fallback"] for e in final.cells.values()])),
                  "median_rounds": float(np.median([e["raw_rounds"] for e in final.cells.values()])),
                  "median_effective_rounds": float(np.median([e["total"] for e in final.cells.values()])),
                  "params": last},
    }
    (Path(a.out).parent / "hwr_summary.json").write_text(json.dumps(summ, indent=1))
    print("wrote", v2_path, "and hwr_summary.json")


if __name__ == "__main__":
    main()
