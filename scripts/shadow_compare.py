"""v2 half-win rates vs rating model (b) vs Kalshi mid on the shadow-quote markets (REPORT_v5 §6).

Reads data/shadow_quotes.db (written by scripts/shadow_quotes.py, which this script does not touch).
For each market x team it takes the LAST shadow row before the start (the pre-match quote) and adds:
  p_b      the frozen rating model (b) (params from thunderedge research/out/rating_eval.json), state
           updated on every tier-1 map in the DB, each team's latest five; map quote = mean over the
           current pool of P(A wins map) (as in shadow_quotes), series = BO3 composition of that mean;
  outcome  Kalshi settlement (public GET /markets?tickers=..., batches of 100; requests counted).
Scores v2, (b) and the Kalshi mid on the markets where all three exist: Brier and log loss vs the
settlement, and mean |p - mid|; CIs by bootstrap over Kalshi events (one event = one match).
(b) is defined only when both teams are in the tier-1 DB with a known five.

Usage: python scripts/shadow_compare.py [--since 2026-11-17T08:12] [--out ../thunderedge/research/out/shadow_compare.json]
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts import rating_eval as R  # noqa: E402
from scripts.shadow_quotes import OUT_DB, SNAP_DB, TEAMS_DB, current_pool  # noqa: E402
from scripts.walkforward_eval import series_p  # noqa: E402
from src.rating.dp_table import MapTable  # noqa: E402
from src.rating.engine import Engine, EngineParams, Team  # noqa: E402

KALSHI = "https://api.elections.kalshi.com/trade-api/v2"
FROZEN = ROOT.parent / "thunderedge" / "research" / "out" / "rating_eval.json"


def engine_now() -> tuple[Engine, dict, dict, dict]:
    D = R.load(str(TEAMS_DB))
    eng = Engine(EngineParams(**json.loads(FROZEN.read_text())["params_b"]))
    last_five: dict = {}
    for m in D["matches"]:
        a, b = m["a"], m["b"]
        ra, rb = D["region"].get(a), D["region"].get(b)
        if ra is None or rb is None:
            continue
        for g, mp, (k1, n1, k2, n2) in m["games"]:
            f1, f2 = D["fives"].get((g, a)), D["fives"].get((g, b))
            if f1 and f2:
                if n1 + n2 > 0:
                    eng.update_map(Team(a, f1, ra), Team(b, f2, rb), mp, m["t"], m["season"], (k1, n1), (k2, n2))
                last_five[a], last_five[b] = f1, f2
    con = sqlite3.connect(TEAMS_DB)
    ids: dict[str, int] = {}
    for tid, name, tag in con.execute("SELECT team_id, name, tag FROM teams"):
        for k in (name, tag):
            if k:
                ids.setdefault(k.lower(), tid)
    for alias, tid in con.execute("SELECT alias, team_id FROM team_aliases"):
        ids.setdefault(alias.lower(), tid)
    return eng, last_five, D["region"], ids


def settlements(markets: list[str]) -> tuple[dict[str, float], int]:
    out, n = {}, 0
    for i in range(0, len(markets), 100):
        r = requests.get(KALSHI + "/markets", params={"tickers": ",".join(markets[i:i + 100]), "limit": 100}, timeout=30)
        n += 1
        r.raise_for_status()
        for mk in r.json().get("markets", []):
            if mk.get("result") in ("yes", "no"):
                out[mk["ticker"]] = 1.0 if mk["result"] == "yes" else 0.0
    return out, n


def boot(rows: list[dict], fn, nb: int = 2000) -> dict:
    ev = sorted({r["event"] for r in rows})
    if len(ev) < 5:
        return {"n": len(rows), "n_events": len(ev), "est": float(fn(rows)) if rows else None}
    by = defaultdict(list)
    for r in rows:
        by[r["event"]].append(r)
    rng = np.random.default_rng(0)
    d = [fn([x for e in rng.choice(ev, len(ev)) for x in by[e]]) for _ in range(nb)]
    return {"n": len(rows), "n_events": len(ev), "est": float(fn(rows)), "lo": float(np.percentile(d, 2.5)),
            "hi": float(np.percentile(d, 97.5))}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2026-11-17T08:12")
    ap.add_argument("--out", default=str(ROOT.parent / "thunderedge" / "research" / "out" / "shadow_compare.json"))
    a = ap.parse_args()
    con = sqlite3.connect(OUT_DB)
    cols = [c[1] for c in con.execute("PRAGMA table_info(shadow_quotes)")]
    last: dict = {}
    for r in con.execute("SELECT * FROM shadow_quotes WHERE ts_utc >= ? ORDER BY ts_utc", (a.since,)):
        d = dict(zip(cols, r, strict=True))
        if d["start_utc"] and d["ts_utc"] < d["start_utc"].replace("Z", "+00:00"):
            last[(d["match_key"], d["team"])] = d
    snap = sqlite3.connect(f"file:{SNAP_DB}?mode=ro", uri=True)
    ticker = {(k, t): u for k, t, u in snap.execute(
        "SELECT DISTINCT match_key, team, match_url FROM odds_snapshots WHERE source='kalshi'")}
    eng, five, region, ids = engine_now()
    table = MapTable()
    pool = current_pool(sqlite3.connect(TEAMS_DB))
    now = datetime.now(UTC)
    t_now = R._days(now.astimezone(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S"))  # vlr dates are ET
    rows = []
    for (mk, team), d in last.items():
        ta, tb = ids.get((d["team"] or "").lower()), ids.get((d["opp"] or "").lower())
        p_b = None
        if ta in five and tb in five and region.get(ta) and region.get(tb):
            A, B = Team(ta, five[ta], region[ta]), Team(tb, five[tb], region[tb])
            pm = float(np.mean([table.map_p(*eng.predict_map(A, B, mp, t_now, now.year)[:3]) for mp in pool]))
            p_b = series_p([pm] * 3, 3) if "GAME" in (d["market"] or mk) else pm
        rows.append({"event": mk, "ticker": ticker.get((mk, team)), "market": d["market"], "team": team,
                     "p_v2": d["p_branch_v2"], "p_legacy": d["p_branch_legacy"], "p_b": p_b, "mid": d["kalshi_mid"],
                     "cov_v2": d["cov_v2"], "start": d["start_utc"]})
    res_y, n_req = settlements(sorted({r["ticker"] for r in rows if r["ticker"]}))
    for r in rows:
        r["y"] = res_y.get(r["ticker"])
    full = [r for r in rows if r["p_b"] is not None and r["mid"] is not None and r["y"] is not None]

    def brier(k):
        return lambda rs: float(np.mean([(x[k] - x["y"]) ** 2 for x in rs]))

    def logloss(k):
        return lambda rs: float(np.mean([-np.log(min(max(x[k] if x["y"] else 1 - x[k], 1e-6), 1)) for x in rs]))

    out = {"generated": now.isoformat(timespec="seconds"), "since": a.since, "kalshi_requests": n_req,
           "n_market_teams": len(rows), "n_with_b": sum(r["p_b"] is not None for r in rows),
           "n_with_mid": sum(r["mid"] is not None for r in rows), "n_settled": sum(r["y"] is not None for r in rows),
           "n_scored": len(full), "n_events_scored": len({r["event"] for r in full}),
           "scores": {v: {"brier": boot(full, brier(k)), "logloss": boot(full, logloss(k))}
                      for v, k in (("v2", "p_v2"), ("b", "p_b"), ("kalshi_mid", "mid"))},
           "mean_abs_minus_mid_c": {v: 100 * float(np.mean([abs(r[k] - r["mid"]) for r in full])) if full else None
                                    for v, k in (("v2", "p_v2"), ("b", "p_b"))},
           "rows": rows}
    Path(a.out).write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps({k: v for k, v in out.items() if k != "rows"}, indent=1, default=str))


if __name__ == "__main__":
    main()
