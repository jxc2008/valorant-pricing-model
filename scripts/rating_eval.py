"""Dual-output dynamic rating model: tune on 2024-25, walk forward on 2026 (no 2026 tuning).

  (a) close model:   logit(close) = head_a( engine-a outputs )      trained on the de-vigged close
  (b) outcome model: engine-b ratings -> round logits -> production map DP (tabulated) -> series
Both heads use only pre-match information; the market price is never an input.

The engine runs chronologically over every tier-1 map from 2023 (2023 = burn-in): each match is
predicted from the state before it, then the state is updated with its maps. Engine
hyper-parameters are chosen by coordinate descent on 2024-25 only: map log loss for (b),
squared logit error of the fitted head for (a).

Close target: Thunderpick's published closing price for the winner (vlr "pre-match odds"),
de-vigged with the same match's two-sided Wayback snapshot overround when one exists, else the
season median. Because only the winner's close is published, the target carries a small
outcome-correlated error from the overround assumption (≈ ±0.25 pp at the measured spread).

Usage: python scripts/rating_eval.py --db ../thunderedge/data/valorant_stats.db \
          --out ../thunderedge/research/out/rating_eval.json
"""
from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
import time
from collections import defaultdict
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.rebuild_half_win_rates import _days, load_rounds  # noqa: E402
from scripts.walkforward_eval import fit_logit_noint, lg, ll, load_matches, series_p  # noqa: E402
from scripts.walkforward_eval import predict as wf_predict  # noqa: E402
from src.rating.dp_table import MapTable  # noqa: E402
from src.rating.engine import Engine, EngineParams, Team  # noqa: E402

TRAIN, TEST = (2024, 2025), 2026
NB = 2000
V2_PARAMS = (240.0, 810.0)  # walk-forward choice for the 2026 fold (tuned on seasons < 2026)
GRID = {
    "kappa": [0.15, 0.3, 0.5, 0.8, 1.0],
    "v0_player": [0.02, 0.05, 0.1, 0.2, 0.4],
    "q_player": [0.0, 5e-5, 2e-4, 8e-4, 3e-3],
    "v_offseason": [0.0, 0.01, 0.03, 0.1],
    "w_newplayer": [0.0, 0.5, 0.8, 1.0],
    "v0_region": [0.005, 0.02, 0.05, 0.1],
    "v0_teammap": [0.0, 0.003, 0.01, 0.03],
}
GAP_BINS = [0, 2, 5, 10, 100]  # |gap| in probability points
LGB_PARAMS = dict(learning_rate=0.03, num_leaves=7, min_data_in_leaf=40, bagging_fraction=0.8,
                  bagging_freq=1, feature_fraction=0.8, lambda_l2=1.0, seed=0, verbose=-1)
LGB_ROUNDS = 200  # fixed a priori; not tuned


def lgb_fit(X: np.ndarray, y: np.ndarray, objective: str):
    import lightgbm as lgbm  # noqa: PLC0415
    return lgbm.train({**LGB_PARAMS, "objective": objective}, lgbm.Dataset(X, y), num_boost_round=LGB_ROUNDS)


def sig(x):
    return 1.0 / (1.0 + np.exp(-np.asarray(x, float)))


# ---------------------------------------------------------------------------------- data
def load(db: str) -> dict:
    con = sqlite3.connect(db)
    region = {t: r for t, r in con.execute("SELECT team_id, home_region FROM teams")}
    fives = {}
    for g, t, *ps in con.execute("SELECT game_id, team_id, p1, p2, p3, p4, p5 FROM lineups"):
        f = tuple(int(p) for p in ps if p is not None)
        if len(f) == 5:
            fives[(g, t)] = f
    rounds: dict = defaultdict(lambda: [0, 0, 0, 0])  # game -> [k_atk1, n_atk1, k_def1, n_def1]
    info = {}
    for g, _m, t1, t2 in con.execute("""SELECT mr.game_id, mr.match_id, rm.team1_id, rm.team2_id
                                       FROM map_results mr JOIN research_matches rm USING(match_id)"""):
        info[g] = (t1, t2)
    for g, w, s in con.execute("""SELECT game_id, winner_id, winner_side FROM map_rounds
                                  WHERE round_num <= 24 AND winner_side IN ('atk','def')"""):
        if g not in info:
            continue
        t1, _ = info[g]
        t1_atk = (w == t1) == (s == "atk")
        r = rounds[g]
        if t1_atk:
            r[1] += 1
            r[0] += int(w == t1)
        else:
            r[3] += 1
            r[2] += int(w == t1)
    matches = []
    for row in con.execute("""SELECT rm.match_id, rm.date_utc, rm.season, rm.team1_id, rm.team2_id,
                                     rm.event_id, rm.is_international, rm.weeks_since_season_start,
                                     rm.best_of
                              FROM research_matches rm WHERE rm.date_utc IS NOT NULL
                              ORDER BY rm.date_utc, rm.match_id"""):
        mid, date, season, t1, t2, ev, intl, wk, bo = row
        games = con.execute("SELECT game_id, map_name FROM map_results WHERE match_id=? ORDER BY map_num",
                            (mid,)).fetchall()
        matches.append({"match_id": mid, "t": _days(date), "season": season, "a": t1, "b": t2,
                        "event_id": ev, "intl": int(intl or 0), "weeks": wk, "best_of": bo,
                        "games": [(g, mp, tuple(rounds[g])) for g, mp in games]})
    # close target
    vs: dict = defaultdict(list)
    snapV = {}
    for mid, season, v in con.execute("""SELECT p.match_id, rm.season, SUM(1.0/p.odds) FROM prematch_odds p
                                         JOIN research_matches rm USING(match_id) WHERE p.book='thunderpick'
                                         GROUP BY p.match_id HAVING COUNT(*)=2"""):
        vs[season].append(v)
        snapV[mid] = v
    season_V = {s: float(np.median(x)) for s, x in vs.items()}
    snap = defaultdict(dict)
    for mid, tid, o in con.execute("SELECT match_id, team_id, odds FROM prematch_odds WHERE book='thunderpick'"):
        snap[mid][tid] = o
    close = {}
    for mid, tid, o, season, t1 in con.execute(
            """SELECT o.match_id, o.team_id, o.odds, rm.season, rm.team1_id FROM match_odds o
               JOIN research_matches rm USING(match_id)
               WHERE o.book='thunderpick' AND o.observed_side='winner' AND o.odds > 1.01"""):
        V = snapV.get(mid, season_V.get(season, float(np.median(sum(vs.values(), [])))))
        pw = min((1 / o) / V, 0.995)
        close[mid] = {"p1": pw if tid == t1 else 1 - pw, "winner_odds": o, "winner": tid,
                      "V": V, "V_src": "snapshot" if mid in snapV else "season",
                      "snap": dict(snap[mid]) if len(snap.get(mid, {})) == 2 else None}
    return {"region": region, "fives": fives, "matches": matches, "close": close, "season_V": season_V}


# ---------------------------------------------------------------------------------- engine run
def run(D: dict, params: EngineParams, table: MapTable, eval_ms: dict, until: int) -> dict:
    """Predict every eval match pre-match, then update on its maps. Returns per-match outputs."""
    eng = Engine(params)
    out = {}
    last_five: dict = {}
    last_season_five: dict = defaultdict(dict)
    last_t: dict = {}
    last_surprise: dict = {}
    for m in D["matches"]:
        if m["season"] > until:
            break
        a, b = m["a"], m["b"]
        ra, rb = D["region"].get(a), D["region"].get(b)
        if ra is None or rb is None or not m["games"]:
            continue
        g0 = m["games"][0][0]
        fa, fb = D["fives"].get((g0, a)), D["fives"].get((g0, b))
        em = eval_ms.get(m["match_id"])
        if em is not None and fa and fb:
            A, B = Team(a, fa, ra), Team(b, fb, rb)
            pm, dsd, dmean = [], [], []
            for mp in em["pool"]:
                d, dv, dl, _ = eng.predict_map(A, B, mp, m["t"], m["season"])
                pm.append(table.map_p(d, dv, dl))
                dsd.append(math.sqrt(dv))
                dmean.append(d)
            ps = series_p(pm, em["best_of"])
            churn = []
            for t, f in ((a, fa), (b, fb)):
                prev = last_season_five[t].get(m["season"] - 1)
                churn.append(1 - len(set(f) & set(prev)) / 5 if prev else np.nan)
            out[m["match_id"]] = {
                "series": ps, "maps": {mp: p for mp, p in zip(em["pool"], pm, strict=True)},
                "d_mean": float(np.mean(dmean)), "d_sd": float(np.mean(dsd)),
                "lineup_change": int(last_five.get(a, fa) != fa or last_five.get(b, fb) != fb),
                "churn_max": float(np.nanmax(churn)) if not all(np.isnan(churn)) else np.nan,
                "days_since": float(max(m["t"] - last_t.get(a, m["t"] - 60), m["t"] - last_t.get(b, m["t"] - 60))),
                "surprise_diff": float(last_surprise.get(a, 0.0) - last_surprise.get(b, 0.0)),
            }
            y = em["y"]
            last_surprise[a], last_surprise[b] = y - ps, (1 - y) - (1 - ps)
        for g, mp, (k1, n1, k2, n2) in m["games"]:
            f1, f2 = D["fives"].get((g, a)), D["fives"].get((g, b))
            if f1 and f2 and n1 + n2 > 0:
                eng.update_map(Team(a, f1, ra), Team(b, f2, rb), mp, m["t"], m["season"], (k1, n1), (k2, n2))
        if fa and fb:
            last_five[a], last_five[b] = fa, fb
            last_season_five[a][m["season"]], last_season_five[b][m["season"]] = fa, fb
            last_t[a] = last_t[b] = m["t"]
    return out


def map_ll(pred: dict, eval_ms: dict, seasons) -> float:
    ps, ys = [], []
    for mid, o in pred.items():
        em = eval_ms[mid]
        if em["season"] in seasons:
            for name, ya in em["maps"]:
                if name in o["maps"]:
                    ps.append(o["maps"][name])
                    ys.append(ya)
    return float(np.mean(ll(np.array(ps), np.array(ys))))


def head_X(rows: list[dict], key: str = "x") -> np.ndarray:
    x = np.array([r[key] for r in rows])
    lc = np.array([r["lineup_change"] for r in rows])
    it = np.array([r["intl"] for r in rows])
    return np.column_stack([np.ones_like(x), x, x * lc, x * it])


def rows_for(pred: dict, eval_ms: dict, D: dict, seasons) -> list[dict]:
    rows = []
    for mid, o in pred.items():
        em = eval_ms[mid]
        if em["season"] not in seasons:
            continue
        c = D["close"].get(mid)
        rows.append({**o, "match_id": mid, "season": em["season"], "event_id": em["event_id"],
                     "y": em["y"], "intl": em["intl"], "weeks": em["weeks"] if em["weeks"] is not None else 99.0,
                     "best_of": em["best_of"], "x": float(lg(np.array([o["series"]]))[0]),
                     "close": c["p1"] if c else None, "close_info": c})
    return rows


def fit_head_a(rows: list[dict]) -> np.ndarray:
    r = [x for x in rows if x["close"] is not None]
    X, y = head_X(r), lg(np.array([x["close"] for x in r]))
    return np.linalg.lstsq(X, y, rcond=None)[0]


def coord_descent(score, base: EngineParams, label: str, passes: int = 2) -> tuple[EngineParams, list]:
    best, best_s = base, score(base)
    log = [(asdict(best), best_s)]
    print(f"[{label}] start {best_s:.5f}", flush=True)
    for _ in range(passes):
        improved = False
        for k, vals in GRID.items():
            for v in vals:
                if getattr(best, k) == v:
                    continue
                cand = replace(best, **{k: v})
                s = score(cand)
                log.append((asdict(cand), s))
                if s < best_s - 1e-6:
                    best, best_s, improved = cand, s, True
            print(f"[{label}] {k} -> {getattr(best, k)}  {best_s:.5f}", flush=True)
        if not improved:
            break
    return best, log


# ---------------------------------------------------------------------------------- stats
def boot(fn, rows: list[dict], n: int = NB, seed: int = 0) -> dict:
    ev = np.array([r["event_id"] for r in rows])
    uc = np.unique(ev)
    idx = {c: np.nonzero(ev == c)[0] for c in uc}
    rng = np.random.default_rng(seed)
    est = fn(rows)
    draws = []
    for _ in range(n):
        pick = np.concatenate([idx[c] for c in rng.choice(uc, size=len(uc), replace=True)])
        try:
            draws.append(fn([rows[i] for i in pick]))
        except (ValueError, np.linalg.LinAlgError, ZeroDivisionError):
            continue
    d = np.array([x for x in draws if x is not None and np.isfinite(x)])
    return {"est": float(est), "lo": float(np.percentile(d, 2.5)), "hi": float(np.percentile(d, 97.5)),
            "n": len(rows), "n_events": len(uc)}


def pnl(r: dict, back_team1: bool) -> float | None:
    c = r["close_info"]
    if c is None:
        return None
    won = (r["y"] == 1) == back_team1
    return c["winner_odds"] - 1 if won else -1.0


def clv(r: dict, back_team1: bool, a_id: int, b_id: int) -> float | None:
    """log(bet price at the Wayback snapshot / close) for the backed side (two-sided rows)."""
    c = r["close_info"]
    if c is None or c["snap"] is None:
        return None
    tid = a_id if back_team1 else b_id
    o_bet = c["snap"].get(tid)
    if o_bet is None:
        return None
    if c["winner"] == tid:
        o_close = c["winner_odds"]
    else:
        rest = c["V"] - 1 / c["winner_odds"]
        if rest <= 0.01:
            return None
        o_close = 1 / rest
    return math.log(o_bet / o_close)


# ---------------------------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--quick", action="store_true", help="1 coordinate-descent pass, 200 bootstraps")
    a = ap.parse_args()
    global NB
    if a.quick:
        NB = 200
    t0 = time.time()
    D = load(a.db)
    ms = load_matches(a.db)
    eval_ms = {m["match_id"]: m for m in ms}
    for m in D["matches"]:
        if m["match_id"] in eval_ms:
            eval_ms[m["match_id"]].update(event_id=m["event_id"], intl=m["intl"], weeks=m["weeks"])
    table = MapTable()
    print(f"loaded {len(D['matches'])} matches, {len(eval_ms)} eval matches, {len(D['close'])} closes "
          f"({time.time() - t0:.0f}s)", flush=True)

    # ---- tune (b) on 2024-25 map log loss; (a) on 2024-25 close fit. Engine never sees 2026.
    passes = 1 if a.quick else 2
    ckpt = Path(a.out).with_suffix(".tuning.json")
    if ckpt.exists():
        c = json.loads(ckpt.read_text())
        pb, pa, log_b, log_a = EngineParams(**c["pb"]), EngineParams(**c["pa"]), c["log_b"], c["log_a"]
        print(f"reusing tuning checkpoint {ckpt}", flush=True)
    else:
        pb, log_b = coord_descent(lambda p: map_ll(run(D, p, table, eval_ms, until=2025), eval_ms, TRAIN),
                                  EngineParams(), "b", passes)

    def score_a(p: EngineParams) -> float:
        rows = rows_for(run(D, p, table, eval_ms, until=2025), eval_ms, D, TRAIN)
        r = [x for x in rows if x["close"] is not None]
        beta = fit_head_a(r)
        return float(np.mean((head_X(r) @ beta - lg(np.array([x["close"] for x in r]))) ** 2))

    if not ckpt.exists():
        pa, log_a = coord_descent(score_a, pb, "a", passes)
        ckpt.write_text(json.dumps({"pb": asdict(pb), "pa": asdict(pa), "log_b": log_b, "log_a": log_a}))

    # ---- final runs through 2026 with frozen params
    pred_b = run(D, pb, table, eval_ms, until=2026)
    pred_a = run(D, pa, table, eval_ms, until=2026)
    rb_all = {r["match_id"]: r for r in rows_for(pred_b, eval_ms, D, (*TRAIN, TEST))}
    ra_all = {r["match_id"]: r for r in rows_for(pred_a, eval_ms, D, (*TRAIN, TEST))}
    beta_a = fit_head_a([r for r in ra_all.values() if r["season"] in TRAIN])
    rows = []
    for mid, rb in rb_all.items():
        ra = ra_all.get(mid)
        if ra is None:
            continue
        p_a = float(sig(head_X([ra]) @ beta_a)[0])
        rows.append({**rb, "p_b": rb["series"], "p_a": p_a, "x_a": ra["x"], "a_id": eval_ms[mid]["a"],
                     "b_id": eval_ms[mid]["b"]})
    tr = [r for r in rows if r["season"] in TRAIN]
    te = [r for r in rows if r["season"] == TEST]
    print(f"rows train {len(tr)} test {len(te)} ({time.time() - t0:.0f}s)", flush=True)

    # ---- v2 baseline on 2026 (same walk-forward builder as REPORT §4)
    rounds = load_rounds(a.db)
    te_ids = [r["match_id"] for r in te]
    v2 = wf_predict([eval_ms[i] for i in te_ids], rounds, "v2", V2_PARAMS)
    for r in te:
        r["p_v2"] = v2[r["match_id"]]["series"]
        r["maps_v2"] = v2[r["match_id"]]["maps"]

    res: dict = {"params_b": asdict(pb), "params_a": asdict(pa), "head_a_beta": beta_a.tolist(),
                 "head_a_cols": ["const", "x", "x*lineup_change", "x*intl"],
                 "n": {"train": len(tr), "test": len(te), "test_with_close": sum(r["close"] is not None for r in te),
                       "test_two_sided": sum(r["close"] is not None and r["close_info"]["snap"] is not None for r in te)},
                 "season_V": D["season_V"], "tuning_log_b": log_b[-5:], "tuning_log_a": log_a[-5:],
                 "map_ll_train_b": map_ll(pred_b, eval_ms, TRAIN)}

    # ---- D1 close error of (a)
    def abs_err(rs, key="p_a"):
        return [100 * abs(r[key] - r["close"]) for r in rs]

    d1 = {}
    tc = [r for r in te if r["close"] is not None]
    for sub, rs in (("all", tc), ("two_sided_V", [r for r in tc if r["close_info"]["snap"]])):
        for split, f in (("all", lambda r: True), ("stable", lambda r: r["lineup_change"] == 0),
                         ("lineup_change", lambda r: r["lineup_change"] == 1)):
            s = [r for r in rs if f(r)]
            if len(s) < 15:
                continue
            blk = {}
            for key in ("p_a", "p_b", "p_v2"):
                blk[key] = {"median": boot(lambda x, k=key: float(np.median(abs_err(x, k))), s),
                            "p90": boot(lambda x, k=key: float(np.percentile(abs_err(x, k), 90)), s)}
            d1[f"{sub}|{split}"] = blk
    res["D1_close_error"] = d1

    # ---- D2 residual predictability
    feats = ["churn_max", "lineup_change", "intl", "weeks", "d_sd", "days_since", "surprise_diff", "best_of",
             "abs_x"]

    def F(rs):
        out = []
        for r in rs:
            out.append([0.0 if np.isnan(r["churn_max"]) else r["churn_max"], r["lineup_change"], r["intl"],
                        min(r["weeks"], 60.0), r["d_sd"], min(r["days_since"], 120.0), r["surprise_diff"],
                        r["best_of"], abs(r["x_a"])])
        return np.array(out)

    trc = [r for r in tr if r["close"] is not None]
    # cross-fitted training residuals (5 folds by event) so the residual model sees honest errors
    evs = np.array([r["event_id"] for r in trc])
    folds = {e: i % 5 for i, e in enumerate(np.unique(evs))}
    res_tr = np.zeros(len(trc))
    for k in range(5):
        fit_idx = [i for i, r in enumerate(trc) if folds[r["event_id"]] != k]
        hold = [i for i, r in enumerate(trc) if folds[r["event_id"]] == k]
        Xf = head_X([{**trc[i], "x": trc[i]["x_a"]} for i in fit_idx])
        yf = lg(np.array([trc[i]["close"] for i in fit_idx]))
        bk = np.linalg.lstsq(Xf, yf, rcond=None)[0]
        Xh = head_X([{**trc[i], "x": trc[i]["x_a"]} for i in hold])
        res_tr[hold] = lg(np.array([trc[i]["close"] for i in hold])) - Xh @ bk
    res_te = np.array([float(lg(np.array([r["close"]]))[0] - lg(np.array([r["p_a"]]))[0]) for r in tc])
    Ftr, Fte = F(trc), F(tc)
    mu, sd = Ftr.mean(0), Ftr.std(0) + 1e-9
    Xl = np.column_stack([np.ones(len(Ftr)), (Ftr - mu) / sd])
    lam = 1.0
    bl = np.linalg.solve(Xl.T @ Xl + lam * np.diag([0] + [1] * Ftr.shape[1]), Xl.T @ res_tr)
    pred_lin = np.column_stack([np.ones(len(Fte)), (Fte - mu) / sd]) @ bl
    pred_gbm = lgb_fit(Ftr, res_tr, "regression").predict(Fte)
    for i, r in enumerate(tc):
        r["res"], r["res_lin"], r["res_gbm"] = res_te[i], pred_lin[i], pred_gbm[i]

    def r2(key):
        return lambda rs: 1 - sum((r["res"] - r[key]) ** 2 for r in rs) / sum(r["res"] ** 2 for r in rs)

    res["D2_residuals"] = {
        "features": feats, "ridge_coef_std": dict(zip(["const", *feats], bl.tolist(), strict=True)),
        "oos_r2_linear": boot(r2("res_lin"), tc), "oos_r2_lightgbm": boot(r2("res_gbm"), tc),
        "test_resid_sd_logit": float(np.std(res_te)),
        "corr_test": {f: float(np.corrcoef(Fte[:, j], res_te)[0, 1]) if np.std(Fte[:, j]) > 0 else None
                      for j, f in enumerate(feats)}}

    # ---- D3 outcome log loss (series) + map level
    def mean_ll(key):
        return lambda rs: float(np.mean(ll(np.array([r[key] for r in rs]), np.array([r["y"] for r in rs]))))

    def diff_ll(k1, k2):
        return lambda rs: mean_ll(k1)(rs) - mean_ll(k2)(rs)

    d3 = {}
    for sub, rs in (("all", te), ("with_close", tc), ("two_sided_V", [r for r in tc if r["close_info"]["snap"]])):
        blk = {"n": len(rs), "coin": math.log(2)}
        for k in ("p_b", "p_v2") + (("close",) if sub != "all" else ()):
            blk[k] = mean_ll(k)(rs)
        blk["b_minus_v2"] = boot(diff_ll("p_b", "p_v2"), rs)
        if sub != "all":
            blk["b_minus_close"] = boot(diff_ll("p_b", "close"), rs)
            blk["brier"] = {k: float(np.mean([(r[k] - r["y"]) ** 2 for r in rs])) for k in ("p_b", "p_v2", "close")}
        d3[sub] = blk
    mp_b, mp_v2, mp_y = [], [], []
    for r in te:
        em = eval_ms[r["match_id"]]
        played = [(n, y) for n, y in em["maps"] if n in em["pool"]]  # same order wf_predict uses
        for (pv, ya), (name, _) in zip(r["maps_v2"], played, strict=True):
            mp_b.append(r["maps"][name])
            mp_v2.append(pv)
            mp_y.append(ya)
    d3["map_level"] = {"n_maps": len(mp_y), "b": float(np.mean(ll(np.array(mp_b), np.array(mp_y)))),
                       "v2": float(np.mean(ll(np.array(mp_v2), np.array(mp_y)))), "coin": math.log(2)}
    res["D3_outcome"] = d3

    # ---- D4 gap (b - a): Benter, ROI and CLV by gap bucket
    trb = [r for r in tr if r["close"] is not None]
    Xb = np.column_stack([lg(np.array([r["p_b"] for r in trb])), lg(np.array([r["close"] for r in trb]))])
    beta_b = fit_logit_noint(Xb, np.array([r["y"] for r in trb], float))
    for r in tc:
        r["benter"] = float(sig(beta_b[0] * lg(np.array([r["p_b"]]))[0] + beta_b[1] * lg(np.array([r["close"]]))[0]))
    d4: dict = {"benter_beta": {"model_b": float(beta_b[0]), "close": float(beta_b[1]), "n_train": len(trb)},
                "benter_minus_close_ll": boot(diff_ll("benter", "close"), tc)}
    for gap_name, gkey in (("b_minus_a", "p_a"), ("b_minus_close", "close")):
        buckets = {}
        for lo, hi in zip(GAP_BINS[:-1], GAP_BINS[1:], strict=True):
            sel = [r for r in tc if lo <= 100 * abs(r["p_b"] - r[gkey]) < hi]
            for r in sel:
                back1 = r["p_b"] > r[gkey]
                r["_pnl"] = pnl(r, back1)
                r["_clv"] = clv(r, back1, r["a_id"], r["b_id"])
            blk = {"n_bets": len(sel)}
            if len(sel) >= 15:
                blk["roi"] = boot(lambda rs: float(np.mean([r["_pnl"] for r in rs])), sel)
            cs = [r for r in sel if r["_clv"] is not None]
            blk["n_clv"] = len(cs)
            if len(cs) >= 15:
                blk["clv"] = boot(lambda rs: float(np.mean([r["_clv"] for r in rs])), cs)
            buckets[f"{lo}-{hi}pp"] = blk
        d4[gap_name] = buckets
    res["D4_gap"] = d4

    # ---- stage 2: LightGBM heads with the same protocol
    def F2(rs, xkey):
        return np.column_stack([np.array([r[xkey] for r in rs]), F(rs)])

    trc_b = [r for r in tr]
    p_b2 = lgb_fit(F2(trc_b, "x"), np.array([r["y"] for r in trc_b], float), "binary").predict(F2(te, "x"))
    p_a2 = sig(lgb_fit(F2(trc, "x_a"), lg(np.array([r["close"] for r in trc])), "regression").predict(F2(tc, "x_a")))
    for r, p in zip(te, p_b2, strict=True):
        r["p_b2"] = float(p)
    for r, p in zip(tc, p_a2, strict=True):
        r["p_a2"] = float(p)
    res["stage2"] = {
        "outcome_ll_b2_minus_b": boot(diff_ll("p_b2", "p_b"), te),
        "close_err_median_a2": boot(lambda rs: float(np.median(abs_err(rs, "p_a2"))), tc),
        "close_err_median_a": boot(lambda rs: float(np.median(abs_err(rs, "p_a"))), tc)}

    res["runtime_s"] = time.time() - t0
    Path(a.out).write_text(json.dumps(res, indent=1, default=float))
    print(f"wrote {a.out} ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
