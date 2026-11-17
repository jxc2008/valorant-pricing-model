"""Shadow-mode pre-match quotes: legacy vs v2 half-win rates, logged side by side. No orders.

Reads the latest Kalshi VALORANT rows captured by the thunderedge odds logger
(data/odds_snapshots.db — no extra network requests) and, for each team market, computes
the pre-match theo three ways with the same production DP (src.pricing.live_theo):

  live_main      data/half_win_rates.json + the main-branch blend (side baseline fixed at 0.5)
                 -> what the code on `main` would quote today
  branch_legacy  data/half_win_rates.json + the log5 blend (fix/side-baseline-blend)
  branch_v2      data/half_win_rates_v2.json + the log5 blend   <- the proposed swap

So  branch_v2 - branch_legacy  isolates the rates-file swap, and
    branch_v2 - live_main      is the total change if the branch and the swap both ship.

Pre-veto the maps are unknown (Kalshi map markets are "map 1/2/3"), so a map quote is the
mean over the current map pool of P(A wins map), each averaged over A starting atk/def, and a
series quote is the BO3 composition of that mean. Touches nothing in src/quoting or src/main.py.

Usage:
  python scripts/shadow_quotes.py poll      # one pass (scheduled every 15 min)
  python scripts/shadow_quotes.py report [--since 2026-11-17T00:00]   # deltas -> markdown
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts.walkforward_eval import map_p, series_p  # noqa: E402
from src.pricing.data import HalfRates  # noqa: E402

TE = ROOT.parent / "thunderedge" / "data"
SNAP_DB = TE / "odds_snapshots.db"
TEAMS_DB = TE / "valorant_stats.db"
OUT_DB = ROOT / "data" / "shadow_quotes.db"
LEGACY = ROOT / "data" / "half_win_rates.json"
V2 = ROOT / "data" / "half_win_rates_v2.json"
FRESH_MIN = 30
POOL_SIZE = 7  # only quote markets seen by the logger in the last 30 minutes

SCHEMA = """
CREATE TABLE IF NOT EXISTS shadow_quotes(
  ts_utc TEXT, snap_ts TEXT, match_key TEXT, market TEXT, start_utc TEXT,
  team TEXT, opp TEXT, tag TEXT, opp_tag TEXT,
  cov_legacy INTEGER, cov_v2 INTEGER,          -- 0/1/2 teams with any team-level cells
  kalshi_bid REAL, kalshi_ask REAL, kalshi_mid REAL,
  p_live_main REAL, p_branch_legacy REAL, p_branch_v2 REAL,
  pool TEXT, rates_legacy TEXT, rates_v2 TEXT,
  PRIMARY KEY (ts_utc, match_key, team));
"""


@dataclass(frozen=True)
class _MainBlend(HalfRates):
    """main-branch blend: round_p(a, b) = odds(a)*odds(1-b), i.e. log5 with L_side = 0.5."""

    def league(self, map_name: str, side: str) -> float:
        return 0.5


def _load(path: Path, main_blend: bool = False) -> HalfRates:
    hr = HalfRates.from_json(path)
    if main_blend:
        return _MainBlend(hr.team_rates, hr.league_rates, hr.overall_avg, hr.pre_shrunk)
    return hr


def current_pool(con: sqlite3.Connection) -> tuple[str, ...]:
    """The 7 most-played maps in the last 120 days of data (the competitive pool size)."""
    rows = con.execute("""SELECT map_name, COUNT(*) FROM map_results r JOIN research_matches m USING(match_id)
                          WHERE m.date_utc >= (SELECT date(MAX(date_utc), '-120 days') FROM research_matches)
                          GROUP BY 1 ORDER BY 2 DESC""").fetchall()
    return tuple(sorted(m for m, _ in rows[:POOL_SIZE]))


def tag_lookup(con: sqlite3.Connection) -> dict[str, str]:
    out: dict[str, str] = {}
    for name, tag in con.execute("SELECT name, tag FROM teams WHERE tag IS NOT NULL"):
        out[name.lower()] = tag
        out[tag.lower()] = tag
    for alias, tag in con.execute("""SELECT a.alias, t.tag FROM team_aliases a JOIN teams t USING(team_id)
                                     WHERE t.tag IS NOT NULL"""):
        out.setdefault(alias.lower(), tag)
    return out


def _covered(hr: HalfRates, tag: str) -> bool:
    return any(k.startswith(f"{tag}|") for k in hr.team_rates)


def poll() -> int:
    now = datetime.now(UTC)
    snap = sqlite3.connect(f"file:{SNAP_DB}?mode=ro", uri=True)
    rows = snap.execute(
        """SELECT s.ts_utc, s.match_key, s.event, s.start_utc, s.team, s.yes_bid, s.yes_ask
           FROM odds_snapshots s JOIN (SELECT match_key, team, MAX(ts_utc) ts FROM odds_snapshots
                                       WHERE source='kalshi' GROUP BY 1, 2) l
             ON l.match_key=s.match_key AND l.team=s.team AND l.ts=s.ts_utc
           WHERE s.source='kalshi' AND s.ts_utc >= ?""",
        ((now - timedelta(minutes=FRESH_MIN)).isoformat(timespec="seconds"),)).fetchall()
    tdb = sqlite3.connect(f"file:{TEAMS_DB}?mode=ro", uri=True)
    pool, tags = current_pool(tdb), tag_lookup(tdb)
    live, legacy, v2 = _load(LEGACY, main_blend=True), _load(LEGACY), _load(V2)
    meta = {p: json.loads(p.read_text(encoding="utf-8")).get("build", {}) for p in (LEGACY, V2)}
    by_mk: dict[str, list] = {}
    for r in rows:
        by_mk.setdefault(r[1], []).append(r)
    out = []
    for mk, rs in by_mk.items():
        if len(rs) != 2:
            continue
        for me, op in ((rs[0], rs[1]), (rs[1], rs[0])):
            start = me[3] or ""
            if start and start < now.strftime("%Y-%m-%dT%H:%M"):
                continue  # pre-match only
            ta, tb = tags.get(me[4].lower(), me[4]), tags.get(op[4].lower(), op[4])
            ps = []
            for hr in (live, legacy, v2):
                pm = float(np.mean([map_p(hr, ta, tb, pool, i) for i in range(len(pool))]))
                ps.append(series_p([pm] * 3, 3) if "GAME" in (me[2] or mk) else pm)
            bid, ask = me[5], me[6]
            mid = (bid + ask) / 2 if bid is not None and ask is not None and ask > 0 else None
            out.append((now.isoformat(timespec="seconds"), me[0], mk, me[2], start, me[4], op[4], ta, tb,
                        _covered(legacy, ta) + _covered(legacy, tb), _covered(v2, ta) + _covered(v2, tb),
                        bid, ask, mid, *ps, ",".join(pool), json.dumps(meta[LEGACY]), json.dumps(meta[V2])))
    con = sqlite3.connect(OUT_DB)
    con.executescript(SCHEMA)
    con.executemany(f"INSERT OR REPLACE INTO shadow_quotes VALUES ({','.join('?' * 20)})", out)
    con.commit()
    print(f"{now:%Y-%m-%d %H:%M} shadow rows {len(out)} from {len(by_mk)} markets; pool {pool}")
    return len(out)


def report(since: str | None) -> str:
    con = sqlite3.connect(OUT_DB)
    q = "SELECT * FROM shadow_quotes" + (" WHERE ts_utc >= ?" if since else "")
    cols = [c[1] for c in con.execute("PRAGMA table_info(shadow_quotes)")]
    data = [dict(zip(cols, r, strict=True)) for r in con.execute(q, (since,) if since else ())]
    if not data:
        return "no shadow rows yet"
    L = ["# Shadow quotes: v2 vs legacy half-win rates (pre-match, no trading)", "",
         f"{len(data)} quote rows, {len({d['match_key'] for d in data})} markets, "
         f"{data[0]['ts_utc']} → {data[-1]['ts_utc']}. Deltas in cents of a $1 contract (P × 100); "
         "one row per market × team × 15-min poll (rows within a market are highly correlated — "
         "per-market medians are the effective sample).", "",
         "| Coverage (teams with team-level cells: legacy / v2) | markets | Δ rates swap (v2 − legacy), median |Δ| ¢ | p90 |Δ| ¢ | max |Δ| ¢ | Δ total (v2 − main), median |Δ| ¢ | max |Δ| ¢ |",
         "|---|---|---|---|---|---|---|"]
    groups: dict = {}
    for d in data:
        groups.setdefault((d["cov_legacy"], d["cov_v2"]), []).append(d)
    for k in sorted(groups):
        g = groups[k]
        per_mk: dict = {}
        for d in g:
            per_mk.setdefault((d["match_key"], d["team"]), []).append(d)
        dr = np.array([100 * np.median([x["p_branch_v2"] - x["p_branch_legacy"] for x in v]) for v in per_mk.values()])
        dt = np.array([100 * np.median([x["p_branch_v2"] - x["p_live_main"] for x in v]) for v in per_mk.values()])
        L.append(f"| {k[0]} / {k[1]} | {len({m for m, _ in per_mk})} | {np.median(abs(dr)):.1f} | "
                 f"{np.percentile(abs(dr), 90):.1f} | {abs(dr).max():.1f} | {np.median(abs(dt)):.1f} | {abs(dt).max():.1f} |")
    L += ["", "Distance to the Kalshi mid (not an accuracy test — pre-match mids are thin and the "
          "outcome is what matters; reported so large disagreements are visible):", "",
          "| Variant | rows with a mid | mean |p − mid| ¢ |", "|---|---|---|"]
    wm = [d for d in data if d["kalshi_mid"] is not None]
    for v in ("p_live_main", "p_branch_legacy", "p_branch_v2"):
        if wm:
            L.append(f"| {v[2:]} | {len(wm)} | {100 * np.mean([abs(d[v] - d['kalshi_mid']) for d in wm]):.1f} |")
    L += ["", "Largest rates-swap deltas (latest row per market × team):", "",
          "| market | team (tag) vs opp (tag) | legacy ¢ | v2 ¢ | Δ ¢ | Kalshi mid ¢ |", "|---|---|---|---|---|---|"]
    latest: dict = {}
    for d in data:
        latest[(d["match_key"], d["team"])] = d
    top = sorted(latest.values(), key=lambda d: -abs(d["p_branch_v2"] - d["p_branch_legacy"]))[:10]
    for d in top:
        mid = "—" if d["kalshi_mid"] is None else f"{100 * d['kalshi_mid']:.0f}"
        L.append(f"| {d['match_key'].split(':')[-1]} | {d['team']} ({d['tag']}) vs {d['opp']} ({d['opp_tag']}) | "
                 f"{100 * d['p_branch_legacy']:.1f} | {100 * d['p_branch_v2']:.1f} | "
                 f"{100 * (d['p_branch_v2'] - d['p_branch_legacy']):+.1f} | {mid} |")
    return "\n".join(L) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["poll", "report"])
    ap.add_argument("--since")
    ap.add_argument("--out", default=str(ROOT / "data" / "shadow_report.md"))
    a = ap.parse_args()
    if a.cmd == "poll":
        poll()
    else:
        md = report(a.since)
        Path(a.out).write_text(md, encoding="utf-8")
        print(md)


if __name__ == "__main__":
    main()
