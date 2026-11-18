"""Tier-2 player priors as an optional feature (REPORT_v5 §1). Research only; the frozen model is unchanged.

Runs the rating engine over tier-1 + tier-2 (VCL 2025-26) maps in time order with the T1+T2 arm's params
(thunderedge research/out/rating_ablation.json, `params_b_t1t2`). For every player whose first tier-1 map
comes with no earlier tier-1 map but with earlier tier-2 maps, it records the engine's player state just
before that debut: posterior mean / variance, number of tier-2 maps and the last tier-2 date. The
tier-1-only engine would give such a player the new-player prior (mean = w_newplayer x known teammates,
variance v0_player), so these rows are what tier-2 data adds.

Output: table t2_player_priors in the tier-2 DB (rebuilt) + a JSON copy.
Usage: python scripts/t2_player_priors.py --db ../thunderedge/data/valorant_stats.db \
          --t2-db ../thunderedge/data/valorant_tier2.db --ablation ../thunderedge/research/out/rating_ablation.json \
          --out ../thunderedge/research/out/t2_player_priors.json
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.rating_ablation import load_combined  # noqa: E402
from src.rating.engine import Engine, EngineParams, Team  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--t2-db", required=True)
    ap.add_argument("--ablation", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    D = load_combined(a.db, a.t2_db)
    eng = Engine(EngineParams(**json.loads(Path(a.ablation).read_text())["params_b_t1t2"]))
    seen_t1: set[int] = set()
    t2_maps: Counter = Counter()
    last_t2: dict[int, str] = {}
    priors: dict[int, dict] = {}

    def tier(team: int, season: int) -> int:
        return 1 if team in D["t1_by_season"].get(season, ()) else 2

    for m in D["matches"]:
        aa, bb = m["a"], m["b"]
        ra, rb = D["region"].get(aa), D["region"].get(bb)
        if m["season"] is None or ra is None or rb is None:
            continue
        for g, mp, (k1, n1, k2, n2) in m["games"]:
            f1, f2 = D["fives"].get((g, aa)), D["fives"].get((g, bb))
            if not (f1 and f2) or n1 + n2 == 0:
                continue
            if m["tier"] == 1:
                for q in (*f1, *f2):
                    if q not in seen_t1 and q not in priors and t2_maps[q] > 0:
                        mu, var = eng._peek("player", eng.players.get(q), m["t"], m["season"])  # noqa: SLF001
                        priors[q] = {"player_id": q, "first_t1_match_id": m["match_id"], "first_t1_season": m["season"],
                                     "mu": mu, "var": var, "n_t2_maps": t2_maps[q], "last_t2_match_date": last_t2[q]}
                    seen_t1.add(q)
            else:
                for q in (*f1, *f2):
                    if q not in seen_t1:
                        t2_maps[q] += 1
                        last_t2[q] = m.get("date") or str(m["t"])
            eng.update_map(Team(aa, f1, ra, tier(aa, m["season"])), Team(bb, f2, rb, tier(bb, m["season"])), mp,
                           m["t"], m["season"], (k1, n1), (k2, n2))
    rows = sorted(priors.values(), key=lambda r: (r["first_t1_season"], r["first_t1_match_id"]))
    con = sqlite3.connect(a.t2_db)
    con.execute("DROP TABLE IF EXISTS t2_player_priors")
    con.execute("""CREATE TABLE t2_player_priors(player_id INTEGER PRIMARY KEY, first_t1_match_id INTEGER,
                   first_t1_season INTEGER, mu REAL, var REAL, n_t2_maps INTEGER, last_t2_match_date TEXT)""")
    con.executemany("INSERT INTO t2_player_priors VALUES (?,?,?,?,?,?,?)", [tuple(r.values()) for r in rows])
    con.commit()
    by_season = Counter(r["first_t1_season"] for r in rows)
    summ = {"n_players": len(rows), "by_first_t1_season": dict(sorted(by_season.items())),
            "params": "params_b_t1t2", "v0_player": eng.p.v0_player,
            "var_median": sorted(r["var"] for r in rows)[len(rows) // 2] if rows else None,
            "n_t2_maps_median": sorted(r["n_t2_maps"] for r in rows)[len(rows) // 2] if rows else None}
    Path(a.out).write_text(json.dumps({"summary": summ, "rows": rows}, indent=1))
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()
