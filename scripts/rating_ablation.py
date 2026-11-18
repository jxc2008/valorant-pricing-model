"""Tier-2 ablation for the dual-output rating model (REPORT_v4 §3).

Arm T1    : the frozen tier-1-only model (params + head (a) from thunderedge research/out/rating_eval.json).
Arm T1+T2 : the same engine also updated on every tier-2 (VCL, 2025-26) map from a separate DB, with a
            tier offset (a team is tier 1 in a season if it played any tier-1 match that season, else
            tier 2). Engine params re-tuned by the same coordinate descent on 2024-25 tier-1 only
            (map log loss for (b), close fit for (a)), plus v0_tier.
Arm T1r   : control — tier-1 only, re-tuned by the identical procedure from the frozen params, so the
            T1+T2 vs T1r difference isolates the tier-2 data (primary comparison).
All arms are scored on 2026 tier-1 series: outcome log loss of (b) and close error of (a), paired
per match, CIs from an event bootstrap. Keep tier-2 only if both improve.
Does not modify scripts/rating_eval.py (frozen by the Kickoff 2027 pre-registration).

Usage: python scripts/rating_ablation.py --db ../thunderedge/data/valorant_stats.db \
          --t2-db ../thunderedge/data/valorant_tier2.db --frozen ../thunderedge/research/out/rating_eval.json \
          --out ../thunderedge/research/out/rating_ablation.json
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import rating_eval as R  # noqa: E402
from scripts.walkforward_eval import lg, ll, load_matches, series_p  # noqa: E402
from src.rating.dp_table import MapTable  # noqa: E402
from src.rating.engine import Engine, EngineParams, Team  # noqa: E402

TRAIN, TEST = (2024, 2025), 2026


def load_combined(db1: str, db2: str) -> dict:
    D1, D2 = R.load(db1), R.load(db2)
    for m in D1["matches"]:
        m["tier"] = 1
    for m in D2["matches"]:
        m["tier"] = 2
    t1_by_season: dict = defaultdict(set)
    for m in D1["matches"]:
        t1_by_season[m["season"]].update((m["a"], m["b"]))
    return {"region": {**D2["region"], **D1["region"]}, "fives": {**D2["fives"], **D1["fives"]},
            "matches": sorted(D1["matches"] + D2["matches"], key=lambda m: (m["t"], m["match_id"])),
            "close": D1["close"], "season_V": D1["season_V"], "t1_by_season": t1_by_season,
            "n_t2_maps": sum(len(m["games"]) for m in D2["matches"])}


def run_tiered(D: dict, params: EngineParams, table: MapTable, eval_ms: dict, until: int) -> dict:
    """R.run with a per-team tier; tier-2 maps update the engine, only tier-1 eval matches are predicted."""
    eng = Engine(params)
    out = {}
    last_five: dict = {}
    last_season_five: dict = defaultdict(dict)
    last_t: dict = {}
    last_surprise: dict = {}

    def tier(team: int, season: int) -> int:
        return 1 if team in D["t1_by_season"].get(season, ()) else 2

    for m in D["matches"]:
        if m["season"] is None or m["season"] > until:
            continue
        a, b = m["a"], m["b"]
        ra, rb = D["region"].get(a), D["region"].get(b)
        if ra is None or rb is None or not m["games"]:
            continue
        g0 = m["games"][0][0]
        fa, fb = D["fives"].get((g0, a)), D["fives"].get((g0, b))
        em = eval_ms.get(m["match_id"]) if m.get("tier", 1) == 1 else None
        if em is not None and fa and fb:
            A, B = Team(a, fa, ra, tier(a, m["season"])), Team(b, fb, rb, tier(b, m["season"]))
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
                "surprise_diff": float(last_surprise.get(a, 0.0) - last_surprise.get(b, 0.0))}
            y = em["y"]
            last_surprise[a], last_surprise[b] = y - ps, (1 - y) - (1 - ps)
        for g, mp, (k1, n1, k2, n2) in m["games"]:
            f1, f2 = D["fives"].get((g, a)), D["fives"].get((g, b))
            if f1 and f2 and n1 + n2 > 0:
                eng.update_map(Team(a, f1, ra, tier(a, m["season"])), Team(b, f2, rb, tier(b, m["season"])), mp,
                               m["t"], m["season"], (k1, n1), (k2, n2))
        if fa and fb:
            last_five[a], last_five[b] = fa, fb
            last_season_five[a][m["season"]], last_season_five[b][m["season"]] = fa, fb
            last_t[a] = last_t[b] = m["t"]
    return out


def score_rows(pred_b: dict, pred_a: dict, beta: np.ndarray, eval_ms: dict, D: dict) -> dict[int, dict]:
    rb = {r["match_id"]: r for r in R.rows_for(pred_b, eval_ms, D, (TEST,))}
    ra = {r["match_id"]: r for r in R.rows_for(pred_a, eval_ms, D, (TEST,))}
    out = {}
    for mid, r in rb.items():
        if mid in ra:
            out[mid] = {"event_id": r["event_id"], "y": r["y"], "p_b": r["series"], "close": r["close"],
                        "lineup_change": r["lineup_change"],
                        "p_a": float(R.sig(R.head_X([ra[mid]]) @ beta)[0])}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--t2-db", required=True)
    ap.add_argument("--frozen", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    t0 = time.time()
    frozen = json.loads(Path(a.frozen).read_text())
    table = MapTable()
    ms = load_matches(a.db)
    eval_ms = {m["match_id"]: m for m in ms}
    D1 = R.load(a.db)
    for m in D1["matches"]:
        if m["match_id"] in eval_ms:
            eval_ms[m["match_id"]].update(event_id=m["event_id"], intl=m["intl"], weeks=m["weeks"])
    D12 = load_combined(a.db, a.t2_db)
    print(f"tier-2 maps added: {D12['n_t2_maps']} ({time.time() - t0:.0f}s)", flush=True)

    # arm T1: frozen params (tuned on tier-1 2024-25), frozen head (a)
    pb1, pa1 = EngineParams(**frozen["params_b"]), EngineParams(**frozen["params_a"])
    s1 = score_rows(R.run(D1, pb1, table, eval_ms, 2026), R.run(D1, pa1, table, eval_ms, 2026),
                    np.array(frozen["head_a_beta"]), eval_ms, D1)

    # arm T1+T2: same coordinate descent on 2024-25 tier-1, engine also sees tier-2 maps
    R.GRID["v0_tier"] = [0.05, 0.25, 1.0]
    pb2, _ = R.coord_descent(lambda p: R.map_ll(run_tiered(D12, p, table, eval_ms, 2025), eval_ms, TRAIN),
                             pb1, "b+t2")

    def score_a(p: EngineParams) -> float:
        rows = [x for x in R.rows_for(run_tiered(D12, p, table, eval_ms, 2025), eval_ms, D1, TRAIN)
                if x["close"] is not None]
        beta = R.fit_head_a(rows)
        return float(np.mean((R.head_X(rows) @ beta - lg(np.array([x["close"] for x in rows]))) ** 2))

    pa2, _ = R.coord_descent(score_a, pa1, "a+t2")
    beta2 = R.fit_head_a([x for x in R.rows_for(run_tiered(D12, pa2, table, eval_ms, 2025), eval_ms, D1, TRAIN)])
    s2 = score_rows(run_tiered(D12, pb2, table, eval_ms, 2026), run_tiered(D12, pa2, table, eval_ms, 2026),
                    beta2, eval_ms, D1)

    # control arm T1r: identical tuning procedure, tier-1 data only
    pbr, _ = R.coord_descent(lambda p: R.map_ll(R.run(D1, p, table, eval_ms, 2025), eval_ms, TRAIN), pb1, "b-ctrl")

    def score_ar(p: EngineParams) -> float:
        rws = [x for x in R.rows_for(R.run(D1, p, table, eval_ms, 2025), eval_ms, D1, TRAIN) if x["close"] is not None]
        beta = R.fit_head_a(rws)
        return float(np.mean((R.head_X(rws) @ beta - lg(np.array([x["close"] for x in rws]))) ** 2))

    par, _ = R.coord_descent(score_ar, pa1, "a-ctrl")
    betar = R.fit_head_a([x for x in R.rows_for(R.run(D1, par, table, eval_ms, 2025), eval_ms, D1, TRAIN)])
    sr = score_rows(R.run(D1, pbr, table, eval_ms, 2026), R.run(D1, par, table, eval_ms, 2026), betar, eval_ms, D1)

    ids = sorted(set(s1) & set(s2) & set(sr))
    rows = [{"event_id": s1[i]["event_id"], "y": s1[i]["y"], "close": s1[i]["close"],
             "lineup_change": s1[i]["lineup_change"], "b1": s1[i]["p_b"], "b2": s2[i]["p_b"], "br": sr[i]["p_b"],
             "a1": s1[i]["p_a"], "a2": s2[i]["p_a"], "ar": sr[i]["p_a"]} for i in ids]

    def ll_of(k):
        return lambda rs: float(np.mean(ll(np.array([r[k] for r in rs]), np.array([r["y"] for r in rs]))))

    def med_err(k):
        return lambda rs: float(np.median([100 * abs(r[k] - r["close"]) for r in rs]))

    wc = [r for r in rows if r["close"] is not None]
    st = [r for r in wc if r["lineup_change"] == 0]
    res = {"n_test": len(rows), "n_with_close": len(wc), "n_stable": len(st), "n_t2_maps": D12["n_t2_maps"],
           "params_b_t1t2": asdict(pb2), "params_a_t1t2": asdict(pa2),
           "outcome_ll": {"t1_frozen": ll_of("b1")(rows), "t1_retuned": ll_of("br")(rows), "t1t2": ll_of("b2")(rows),
                          "diff_t1t2_minus_t1r": R.boot(lambda rs: ll_of("b2")(rs) - ll_of("br")(rs), rows),
                          "diff_t1t2_minus_t1frozen": R.boot(lambda rs: ll_of("b2")(rs) - ll_of("b1")(rs), rows)},
           "close_err_median_all": {"t1_frozen": med_err("a1")(wc), "t1_retuned": med_err("ar")(wc), "t1t2": med_err("a2")(wc),
                                    "diff_t1t2_minus_t1r": R.boot(lambda rs: med_err("a2")(rs) - med_err("ar")(rs), wc),
                                    "diff_t1t2_minus_t1frozen": R.boot(lambda rs: med_err("a2")(rs) - med_err("a1")(rs), wc)},
           "close_err_median_stable": {"t1_frozen": med_err("a1")(st), "t1_retuned": med_err("ar")(st), "t1t2": med_err("a2")(st),
                                       "diff_t1t2_minus_t1r": R.boot(lambda rs: med_err("a2")(rs) - med_err("ar")(rs), st)},
           "params_b_t1r": asdict(pbr), "params_a_t1r": asdict(par),
           "runtime_s": time.time() - t0}
    res["keep_tier2"] = bool(res["outcome_ll"]["diff_t1t2_minus_t1r"]["est"] < 0
                             and res["close_err_median_all"]["diff_t1t2_minus_t1r"]["est"] < 0)
    Path(a.out).write_text(json.dumps(res, indent=1, default=float))
    print(json.dumps({k: v for k, v in res.items() if not k.startswith("params")}, indent=1, default=float))


if __name__ == "__main__":
    main()
