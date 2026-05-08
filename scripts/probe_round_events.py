"""Phase 2 Wave 2: scrape rib.gg round events into data/round_events.sqlite.

Path A — DEC-017 / D-01..D-09. Per 02-RESEARCH.md Summary (in-session live probe of
be-prod.rib.gg 2026-04-30), the 4-source ladder collapses to a single Python source.
Sources 2-4 (valorantr / FlynV / bo3.gg) are documented in 02-PROBE-LOG.md as
"considered, rejected" — see Reasons table.

Public API (consumed by tests/calibration/ via importorskip in Wave 0):
    create_round_events_schema(conn)      — install the 8-column CON-round-events-schema
    side_for_team_a(round_num, ...)       — Pitfall 3 round-13 half-flip
    synthesize_mid_round_states(...)      — D-06 hybrid event+heartbeat list (W7: t=0 pre-emit)
    transform_match_to_rows(...)          — yields TWO rows per round (BLOCKER 4 perspective sym)
    list_tier1_events(...)                — VCT filter (W10 test pins this)
    get_json(url)                          — tenacity-wrapped requests.get with W6 Retry-After

CLI:
    python -m scripts.probe_round_events --dry-run                  # 5-series sample, no DB write
    python -m scripts.probe_round_events --live --out-db data/round_events.sqlite
    python -m scripts.probe_round_events --live --target 500        # quick floor

Sources
-------
- 02-RESEARCH.md §"Pattern 1" / §"Pattern 2" / §"Code Examples"
- 02-CONTEXT.md D-01..D-09
- CON-round-events-schema (constraints.md)
- src/config/constants.py (RIBGG_*, MID_ROUND_HEARTBEAT_S)
- credits_to_bucket inline shim (TODO 03-07 — src/pricing/economy.py was DELETED in 03-02)
- CRule 12 (no magic numbers); CRule 13 (dry-run by default)
- BLOCKER 4 (revision feedback): perspective-symmetric row doubling
- W6 (revision feedback): Retry-After header honoring
- W7 (revision feedback): pre-emit t=0 heartbeat before loop
- BLOCKER 3 (revision feedback): D-05 partial-pass coverage in PROBE-LOG
- BLOCKER 1 (revision feedback): FAIL writes 02-PHASE-STATUS.md and exits non-zero
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, TypedDict

import requests
from tenacity import RetryCallState, RetryError, retry, stop_after_attempt
from tqdm import tqdm

from src.config.constants import (
    MID_ROUND_HEARTBEAT_S,
    RIBGG_BASE_URL,
    RIBGG_RATE_LIMIT_RPS,
    RIBGG_RECENCY_MONTHS,
    RIBGG_TARGET_MATCH_COUNT,
    RIBGG_TIER_FILTER,
)


# TODO(03-07): the v2 ETL re-run rewrite removes credits_to_bucket entirely.
# Phase 2's econ_bucket key is dropped from the v2 mid_round_states[] schema.
# Inline shim retained ONLY so the v1 ETL script remains importable until
# 03-07 swaps it out — DO NOT call this from new code.
def credits_to_bucket(credits: int) -> str:
    if credits >= 20_000:
        return "full"
    if credits >= 10_000:
        return "semi-buy"
    if credits >= 5_000:
        return "semi-eco"
    return "eco"

# --------------------------------------------------------------------------- #
# Typed shapes                                                                #
# --------------------------------------------------------------------------- #


class _RibEvent(TypedDict, total=False):
    roundNumber: int
    roundTimeMillis: int
    eventType: str
    attackingTeamNumber: int
    killId: int | None
    bombId: int | None
    playerId: int | None
    referencePlayerId: int | None


class _RibEconomy(TypedDict, total=False):
    roundNumber: int
    playerId: int
    loadoutValue: int


HEADERS: dict[str, str] = {
    "User-Agent": "Mozilla/5.0 (compatible; valorant-pricing-model/0.1; +github)",
    "Referer": "https://www.rib.gg/",
    # Disable urllib3's default keep-alive pooling. On Windows, pooled sockets
    # to be-prod.rib.gg go stale after the server closes them silently — next
    # `requests.get` reuses the dead socket and hangs at the 30s read timeout.
    # `Connection: close` makes the server close cleanly and prevents urllib3
    # from caching the socket. Costs ~0.2s extra TLS handshake per call (≈3 min
    # over a 1000-match scrape) for full reliability.
    "Connection": "close",
}


# --------------------------------------------------------------------------- #
# HTTP layer (W6 Retry-After honoring + Pitfall 2 503 retry)                  #
# --------------------------------------------------------------------------- #


def _ribgg_wait(retry_state: RetryCallState) -> float:
    """Custom tenacity wait function honoring rib.gg's Retry-After header (W6).

    If the most recent attempt raised an HTTPError carrying a `Retry-After`
    header (typical 429/503 from Heroku-fronted APIs), wait that many seconds
    capped at 60. Otherwise fall through to exponential backoff
    (multiplier=1, max=30) — same shape as wait_exponential(multiplier=1, max=30).
    """
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        ra = exc.response.headers.get("Retry-After")
        if ra is not None:
            try:
                return min(float(ra), 60.0)
            except ValueError:
                pass
    attempt = retry_state.attempt_number
    return min(2.0 ** (attempt - 1), 30.0)


@retry(stop=stop_after_attempt(5), wait=_ribgg_wait)
def get_json(url: str) -> dict[str, Any]:
    """GET with tenacity retry. Heroku 503 cold-start handled (Pitfall 2).

    Wait function honors `Retry-After` header (W6) before falling through
    to exponential backoff capped at 30s.

    60s per-call timeout (was 30s) — rib.gg pages occasionally stall under load;
    a longer per-call wait is cheaper than retrying the whole 5-attempt cycle.
    """
    resp = requests.get(url, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    out: dict[str, Any] = resp.json()
    return out


def _throttle() -> None:
    """Sleep 1/RIBGG_RATE_LIMIT_RPS seconds between fetches (~2 rps polite)."""
    time.sleep(1.0 / RIBGG_RATE_LIMIT_RPS)


# --------------------------------------------------------------------------- #
# Schema (CON-round-events-schema + companion matches table)                  #
# --------------------------------------------------------------------------- #


def create_round_events_schema(conn: sqlite3.Connection) -> None:
    """Install CON-round-events-schema verbatim (8 columns + composite PK + map_num index).

    Companion `matches` table holds per-match metadata (D-07: map_name once at
    row level, not duplicated in mid_round_states[]). Per BLOCKER 4 row-doubling,
    matches PK is (match_id, team_a_team_num) so both perspective rows coexist.
    """
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS round_events (
            match_id        TEXT    NOT NULL,
            map_num         INTEGER NOT NULL,
            round_num       INTEGER NOT NULL,
            ts_round_start  REAL    NOT NULL,
            ts_first_kill   REAL,
            ts_bomb_plant   REAL,
            ts_round_end    REAL    NOT NULL,
            mid_round_states TEXT   NOT NULL,
            PRIMARY KEY (match_id, map_num, round_num)
        );
        CREATE INDEX IF NOT EXISTS idx_round_events_map ON round_events(map_num);

        CREATE TABLE IF NOT EXISTS matches (
            match_id                  TEXT    NOT NULL,
            event_id                  INTEGER,
            series_id                 INTEGER,
            map_num                   INTEGER NOT NULL,
            map_name                  TEXT    NOT NULL,
            team_a_team_num           INTEGER NOT NULL,
            attacking_first_team_num  INTEGER NOT NULL,
            team1_score               INTEGER NOT NULL,
            team2_score               INTEGER NOT NULL,
            round_won_by_a            INTEGER,
            PRIMARY KEY (match_id, team_a_team_num)
        );
        """
    )
    conn.commit()


# --------------------------------------------------------------------------- #
# Side mapping (Pitfall 3 — round-13 half flip)                               #
# --------------------------------------------------------------------------- #


def side_for_team_a(
    round_num: int,
    attacking_first_team_num: int,
    team_a_team_num: int,
) -> str:
    """Returns 'atk' or 'def' for team A in this round.

    Sides flip at round 13 (start of second half). OT (rounds 25+) flip every
    pair, but Phase 2 collects regulation rounds only — OT data is sparse and
    handled by the `RoundConclusionLookup` defensive fallback to side_baseline.

    Pitfall 3: easy to bit-flip every row; tested in tests/calibration/test_side_mapping.py.
    """
    is_first_half = round_num <= 12
    is_a_attacker_in_first_half = attacking_first_team_num == team_a_team_num
    a_attacks_this_round = (
        is_a_attacker_in_first_half if is_first_half else not is_a_attacker_in_first_half
    )
    return "atk" if a_attacks_this_round else "def"


# --------------------------------------------------------------------------- #
# mid_round_states[] synthesis (D-06 hybrid + D-08 carry-forward + Pitfall 4) #
# --------------------------------------------------------------------------- #


def synthesize_mid_round_states(
    round_events: list[dict[str, Any]],
    round_team_a_players: set[int],
    round_team_b_players: set[int],
    round_loadouts: dict[int, int],
    side_a_this_round: str,
    map_name: str,
) -> list[dict[str, Any]]:
    """D-06 hybrid: native events + MID_ROUND_HEARTBEAT_S synthetic heartbeats.

    W7 fix: pre-emit a heartbeat at t=0 immediately after the start event before
    entering the heartbeat loop. The strict-less-than loop condition would
    otherwise skip t=0 if the first event is also at t=0. The TDD test
    `test_heartbeat_cadence_matches_constant` pins t=0 explicitly.

    BLOCKER 3 / D-05 partial-pass policy: missing bomb_plant events for >50% of
    rounds is detected by the orchestrator (counter accumulation in
    `_run_scrape`), not by this function. This function emits states faithfully
    from the data it receives.

    Pitfall 4: defuse terminates the round-states list (post-defuse heartbeats
    would contaminate cells with `bomb_planted=False, numerical_diff=high`
    rows that were actually planted scenarios).

    D-08 carry-forward: between events, heartbeats inherit numerical_diff and
    bomb_planted from the most recent event.

    Args:
        round_events: All events for one round, sorted by roundTimeMillis ascending.
        round_team_a_players: Player IDs comprising team A in this round.
        round_team_b_players: Player IDs comprising team B in this round.
        round_loadouts: player_id -> loadoutValue this round (from economies[]).
        side_a_this_round: 'atk' or 'def' for team A; output by side_for_team_a.
        map_name: Map name (e.g. 'Lotus'); stored once per row, not per state.

    Returns:
        Time-ordered list of state dicts per D-09. Each dict has the four
        cells_full lookup keys (numerical_diff, bomb_planted, side, econ_bucket)
        plus t_offset and kind. map_name lives at the row level, not here.
    """
    # `map_name` is intentionally accepted but unused inside the per-state dicts
    # (D-07: map_name is row-level metadata only, never duplicated per state).
    del map_name

    sorted_events = sorted(
        round_events,
        key=lambda e: (e["roundTimeMillis"], e.get("killId") or 0),
    )

    a_alive = 5
    b_alive = 5
    bomb_planted = False
    states: list[dict[str, Any]] = []

    # Per-team loadout total → bucket. NOTE: econ_bucket is from team A's
    # perspective only; the BLOCKER 4 row-doubling in transform_match_to_rows
    # handles team B's perspective in a separate row.
    econ_a_total = sum(round_loadouts.get(pid, 0) for pid in round_team_a_players)
    econ_a_bucket = credits_to_bucket(econ_a_total)

    heartbeat_period_ms = int(MID_ROUND_HEARTBEAT_S * 1000)

    # W7: pre-emit t=0 heartbeat BEFORE entering the loop. The strict-less-than
    # condition `next_heartbeat_ms < t_ms` would otherwise skip t=0 when the
    # first event is also at t_ms=0 (which is the canonical "start" event).
    states.append(
        {
            "t_offset": 0.0,
            "kind": "heartbeat",
            "numerical_diff": 0,
            "bomb_planted": False,
            "side": side_a_this_round,
            "econ_bucket": econ_a_bucket,
        }
    )
    next_heartbeat_ms = heartbeat_period_ms  # next heartbeat after t=0
    terminated = False

    for ev in sorted_events:
        if terminated:
            break
        t_ms = int(ev["roundTimeMillis"])

        # Emit any pending heartbeats up to (but not including) this event's t.
        while next_heartbeat_ms < t_ms:
            states.append(
                {
                    "t_offset": next_heartbeat_ms / 1000.0,
                    "kind": "heartbeat",
                    "numerical_diff": a_alive - b_alive,
                    "bomb_planted": bomb_planted,
                    "side": side_a_this_round,
                    "econ_bucket": econ_a_bucket,
                }
            )
            next_heartbeat_ms += heartbeat_period_ms

        # Apply event semantics
        et = ev["eventType"]
        if et == "kill":
            victim = ev.get("referencePlayerId")
            if victim in round_team_a_players:
                a_alive -= 1
            elif victim in round_team_b_players:
                b_alive -= 1
        elif et == "plant":
            bomb_planted = True
        elif et == "defuse":
            bomb_planted = False
        # eventType == "start" — no state change

        # Emit event-kind state. Skip the start event at t=0 since the t=0
        # heartbeat already covers it; emit all other events.
        if not (et == "start" and t_ms == 0):
            states.append(
                {
                    "t_offset": t_ms / 1000.0,
                    "kind": "event",
                    "numerical_diff": a_alive - b_alive,
                    "bomb_planted": bomb_planted,
                    "side": side_a_this_round,
                    "econ_bucket": econ_a_bucket,
                }
            )

        # Defuse is a round terminator (Pitfall 4)
        if et == "defuse":
            terminated = True

    return states


# --------------------------------------------------------------------------- #
# Endpoint helpers                                                            #
# --------------------------------------------------------------------------- #


def _eighteen_months_ago_iso() -> str:
    return (
        datetime.now(tz=UTC) - timedelta(days=30 * RIBGG_RECENCY_MONTHS)
    ).isoformat()


def list_tier1_events(recency_iso: str) -> list[dict[str, Any]]:
    """Filter rib.gg events to RIBGG_TIER_FILTER division within RIBGG_RECENCY_MONTHS.

    Pinned by W10 test in tests/probe/test_list_tier1_events.py: monkeypatches
    `get_json` to return the events_response.json fixture and asserts only events
    whose `divisions` contain `"VCT"` are yielded (rejects VCL).
    """
    out: list[dict[str, Any]] = []
    skip = 0
    consecutive_page_failures = 0
    while True:
        # `hasSeries=true` and `divisions[]=VCT` are both ignored / pathological on
        # rib.gg's backend: hasSeries=true triggers an unindexed aggregate that
        # 30s-times-out every request, and divisions[]=VCT does not actually filter
        # server-side (meta.total stays at ~6340 either way). Drop both server-side
        # filters and rely on the client-side checks at the bottom of this loop
        # (`seriesCount > 0` AND `RIBGG_TIER_FILTER in divisions`). This means we
        # paginate ~127 pages of 50 events instead of ~4, but each page returns in
        # ~0.5s rather than timing out.
        url = (
            f"{RIBGG_BASE_URL}/events?take=50"
            f"&sort=startDate&sortAscending=false&skip={skip}"
        )
        try:
            resp = get_json(url)
        except (RetryError, requests.exceptions.RequestException) as exc:
            # Per-page resilience: rib.gg occasionally returns 5xx for a stretch
            # of pages under sustained load. Skip the page rather than aborting.
            consecutive_page_failures += 1
            sys.stderr.write(
                f"events page skip={skip} failed ({type(exc).__name__}); "
                f"advancing past 50 events (consecutive failures: "
                f"{consecutive_page_failures})\n"
            )
            if consecutive_page_failures >= 5:
                # 5 consecutive failures = streak of 503s. Cool off 5 min and
                # try one more stretch before giving up. Reset the counter so
                # subsequent isolated failures don't immediately re-abort.
                cool_off_seconds = 300
                sys.stderr.write(
                    f"events page streak: 5 consecutive failures — cooling off "
                    f"{cool_off_seconds}s before retrying\n"
                )
                time.sleep(cool_off_seconds)
                consecutive_page_failures = 0
            skip += 50
            _throttle()
            continue
        consecutive_page_failures = 0
        events = resp.get("data") or []
        if not events:
            break
        stop = False
        for e in events:
            if e.get("startDate", "") < recency_iso:
                stop = True
                break
            divisions = e.get("divisions") or []
            if RIBGG_TIER_FILTER in divisions and (e.get("seriesCount") or 0) > 0:
                out.append(e)
        skip += len(events)
        _throttle()
        if stop:
            break
        if skip >= int(resp.get("meta", {}).get("total", 0)):
            break
    return out


def list_series_for_event(event_id: int) -> list[dict[str, Any]]:
    url = f"{RIBGG_BASE_URL}/series?eventIds[]={event_id}&completed=true&take=50"
    data: list[dict[str, Any]] = get_json(url).get("data") or []
    _throttle()
    return data


def get_match_details(match_id: int) -> dict[str, Any]:
    out: dict[str, Any] = get_json(f"{RIBGG_BASE_URL}/matches/{match_id}/details")
    _throttle()
    return out


# --------------------------------------------------------------------------- #
# Row transform (BLOCKER 4 — perspective-symmetric row doubling)              #
# --------------------------------------------------------------------------- #


def _row_for_round(
    *,
    match_id: str,
    map_num: int,
    round_num: int,
    sorted_events: list[dict[str, Any]],
    round_loadouts: dict[int, int],
    team_a_players: set[int],
    team_b_players: set[int],
    side_a: str,
    map_name: str,
) -> dict[str, Any] | None:
    """Build one round_events row; None if no events."""
    if not sorted_events:
        return None
    ts_round_start = sorted_events[0]["roundTimeMillis"] / 1000.0
    ts_round_end = sorted_events[-1]["roundTimeMillis"] / 1000.0
    kills = [e for e in sorted_events if e["eventType"] == "kill"]
    plants = [e for e in sorted_events if e["eventType"] == "plant"]
    states = synthesize_mid_round_states(
        round_events=sorted_events,
        round_team_a_players=team_a_players,
        round_team_b_players=team_b_players,
        round_loadouts=round_loadouts,
        side_a_this_round=side_a,
        map_name=map_name,
    )
    return {
        "match_id": match_id,
        "map_num": map_num,
        "round_num": round_num,
        "ts_round_start": ts_round_start,
        "ts_first_kill": (kills[0]["roundTimeMillis"] / 1000.0) if kills else None,
        "ts_bomb_plant": (plants[0]["roundTimeMillis"] / 1000.0) if plants else None,
        "ts_round_end": ts_round_end,
        "mid_round_states": json.dumps(states, separators=(",", ":")),
    }


def transform_match_to_rows(
    match_meta: dict[str, Any],
    details: dict[str, Any],
    map_num: int,
) -> Iterable[dict[str, Any]]:
    """For each round in the match, yield TWO rows: one per team perspective.

    BLOCKER 4 fix (revision feedback): the prior implementation set
    `team_a_team_num = int(match["winningTeamNumber"])` for every row, silently
    encoding "rounds where the eventual match winner was team A" rather than the
    neutral "P(team A wins this round | state)". That contaminated Phase 4's
    calibration with match-winner bias.

    The fix: emit two perspective rows per round.
      - row_a: team_a_team_num = team1.id; round_won_by_a = (winningTeamNumber == 1)
      - row_b: team_a_team_num = team2.id; round_won_by_a = (winningTeamNumber == 2)

    Each row's `mid_round_states[]` is computed from THAT row's team A
    perspective. Specifically:
      - `numerical_diff` = (team_a_alive - team_b_alive) where team_a is the
        row's own team_a. The row_b numerical_diff is the negation of row_a's.
      - `side` = side_for_team_a(round_num, attacking_first_team_num, team_a_team_num)
        — row_b's side is therefore opposite (atk↔def) row_a's.
      - `econ_bucket` = credits_to_bucket of THAT row's team A loadout total.

    The aggregate result: doubled row count (2 × num_rounds × num_maps),
    perspective-symmetric. Each cell averages over both perspectives naturally
    in Plan 02-04's calibrator with no calibrator-side change required.

    Yields:
        Round_events rows (dict). Each row is suitable for executemany INSERT.
        Caller must associate the row with the correct (team_a_team_num) when
        inserting into the matches table.
    """
    by_round: dict[int, list[dict[str, Any]]] = {}
    for ev in details.get("events") or []:
        by_round.setdefault(ev["roundNumber"], []).append(ev)
    loadouts_by_round: dict[int, dict[int, int]] = {}
    for ec in details.get("economies") or []:
        loadouts_by_round.setdefault(ec["roundNumber"], {})[ec["playerId"]] = ec[
            "loadoutValue"
        ]

    # rib.gg sometimes returns match records with null rosters / null
    # attackingFirstTeamNumber (cancelled, forfeited, or not-yet-played
    # matches that still ship in the series payload). Skip them — the
    # caller treats an empty yield as `matches_skipped_no_events`.
    t1 = match_meta.get("team1PlayerIds")
    t2 = match_meta.get("team2PlayerIds")
    atk_first = match_meta.get("attackingFirstTeamNumber")
    if not t1 or not t2 or atk_first is None:
        return
    team1_players = set(t1)
    team2_players = set(t2)
    attacking_first = int(atk_first)

    # team1.id and team2.id are 1 and 2 in rib.gg's schema. We yield two
    # perspectives keyed by team_a_team_num ∈ {1, 2}.
    for team_a_team_num in (1, 2):
        if team_a_team_num == 1:
            team_a_players = team1_players
            team_b_players = team2_players
        else:
            team_a_players = team2_players
            team_b_players = team1_players

        for round_num, sorted_events in sorted(by_round.items()):
            side_a = side_for_team_a(
                round_num=round_num,
                attacking_first_team_num=attacking_first,
                team_a_team_num=team_a_team_num,
            )
            row = _row_for_round(
                match_id=str(match_meta["id"]),
                map_num=map_num,
                round_num=round_num,
                sorted_events=sorted_events,
                round_loadouts=loadouts_by_round.get(round_num, {}),
                team_a_players=team_a_players,
                team_b_players=team_b_players,
                side_a=side_a,
                map_name=match_meta["map"]["name"],
            )
            if row is not None:
                # Annotate with team_a_team_num so insert_match can route the
                # row to the right matches-table row. Stripped before SQL bind.
                row["_team_a_team_num"] = team_a_team_num
                yield row


# --------------------------------------------------------------------------- #
# Persistence                                                                 #
# --------------------------------------------------------------------------- #


def insert_match(
    conn: sqlite3.Connection,
    match_meta: dict[str, Any],
    rows: list[dict[str, Any]],
    *,
    event_id: int,
    series_id: int,
    map_num: int,
) -> None:
    """Insert a match's two perspective sets of round_events rows.

    `rows` is the full list yielded by transform_match_to_rows (2 × num_rounds).
    Each row carries `_team_a_team_num` (1 or 2) which routes it to the right
    matches-table row.
    """
    perspectives_seen: set[int] = set()
    for r in rows:
        ta = int(r["_team_a_team_num"])
        if ta in perspectives_seen:
            continue
        perspectives_seen.add(ta)
        winning = int(match_meta["winningTeamNumber"])
        round_won_by_a = int(winning == ta)
        conn.execute(
            """INSERT OR REPLACE INTO matches
               (match_id, event_id, series_id, map_num, map_name, team_a_team_num,
                attacking_first_team_num, team1_score, team2_score, round_won_by_a)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(match_meta["id"]),
                event_id,
                series_id,
                map_num,
                match_meta["map"]["name"],
                ta,
                int(match_meta["attackingFirstTeamNumber"]),
                int(match_meta["team1Score"]),
                int(match_meta["team2Score"]),
                round_won_by_a,
            ),
        )

    # Round_events rows: strip the routing key before SQL bind. Use match_id
    # of form "{id}::{ta}" so the round_events PK admits both perspectives
    # without changing CON-round-events-schema.
    rows_for_sql: list[dict[str, Any]] = []
    for r in rows:
        ta = int(r["_team_a_team_num"])
        sql_row = {k: v for k, v in r.items() if k != "_team_a_team_num"}
        sql_row["match_id"] = f"{r['match_id']}::{ta}"
        rows_for_sql.append(sql_row)

    conn.executemany(
        """INSERT OR REPLACE INTO round_events
           (match_id, map_num, round_num, ts_round_start, ts_first_kill,
            ts_bomb_plant, ts_round_end, mid_round_states)
           VALUES (:match_id, :map_num, :round_num, :ts_round_start,
                   :ts_first_kill, :ts_bomb_plant, :ts_round_end,
                   :mid_round_states)""",
        rows_for_sql,
    )


# --------------------------------------------------------------------------- #
# Scrape orchestration (BLOCKER 3 — D-05 partial-pass coverage tracking)      #
# --------------------------------------------------------------------------- #


def _run_scrape(
    conn: sqlite3.Connection,
    target_match_count: int,
    progress: bool = True,
) -> dict[str, int]:
    """Main scrape loop. Returns counters for the PROBE-LOG.

    BLOCKER 3 / D-05 partial-pass policy tracking: counts per-event-class coverage
    so _render_probe_log can emit the canonical D-05 partial-pass flag.
    """
    counters: dict[str, int] = {
        "events": 0,
        "series": 0,
        "matches": 0,
        "rounds_inserted": 0,
        "matches_skipped_no_events": 0,
        "rounds_total": 0,
        "rounds_with_round_start": 0,
        "rounds_with_first_kill": 0,
        "rounds_with_round_end": 0,
        "rounds_with_bomb_plant": 0,
    }
    recency_iso = _eighteen_months_ago_iso()
    events = list_tier1_events(recency_iso)
    counters["events"] = len(events)

    matches_done = 0
    iter_events = tqdm(events, desc="events", disable=not progress)
    for event in iter_events:
        if matches_done >= target_match_count:
            break
        try:
            series_list = list_series_for_event(event["id"])
        except Exception as exc:  # noqa: BLE001
            tqdm.write(f"event {event['id']} series fetch failed: {exc}")
            continue
        counters["series"] += len(series_list)
        for series in series_list:
            if matches_done >= target_match_count:
                break
            for map_num, match in enumerate(series.get("matches") or []):
                if matches_done >= target_match_count:
                    break
                try:
                    details = get_match_details(match["id"])
                except Exception as exc:  # noqa: BLE001
                    tqdm.write(f"match {match['id']} fetch failed: {exc}")
                    continue
                # BLOCKER 4: row-doubling — yield both perspectives.
                # Belt-and-suspenders: a single malformed match (rib.gg schema
                # drift, partial roster data, etc.) must not abort a multi-hour
                # scrape. transform_match_to_rows already returns empty for
                # known-sparse cases; this guards against unknown-unknowns.
                try:
                    rows = list(transform_match_to_rows(match, details, map_num))
                except Exception as exc:  # noqa: BLE001
                    tqdm.write(f"match {match.get('id')} transform failed: {exc}")
                    counters["matches_skipped_no_events"] += 1
                    continue
                if not rows:
                    counters["matches_skipped_no_events"] += 1
                    continue
                # BLOCKER 3 / D-05 coverage tracking: count UNIQUE rounds (not
                # both perspectives) so percentages reflect actual data coverage.
                seen_rounds: set[tuple[int, int]] = set()
                for r in rows:
                    key = (r["map_num"], r["round_num"])
                    if key in seen_rounds:
                        continue
                    seen_rounds.add(key)
                    counters["rounds_total"] += 1
                    if r["ts_round_start"] is not None:
                        counters["rounds_with_round_start"] += 1
                    if r["ts_first_kill"] is not None:
                        counters["rounds_with_first_kill"] += 1
                    if r["ts_round_end"] is not None:
                        counters["rounds_with_round_end"] += 1
                    if r["ts_bomb_plant"] is not None:
                        counters["rounds_with_bomb_plant"] += 1
                insert_match(
                    conn,
                    match,
                    rows,
                    event_id=event["id"],
                    series_id=series["id"],
                    map_num=map_num,
                )
                counters["rounds_inserted"] += len(rows)
                counters["matches"] += 1
                matches_done += 1
        conn.commit()
    return counters


def _write_probe_log(
    log_path: Path,
    counters: dict[str, int],
    target: int,
    decision: str,
) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        _render_probe_log(counters, target, decision), encoding="utf-8"
    )


def _pct(num: int, denom: int) -> str:
    if denom == 0:
        return "0.0"
    return f"{(num * 100.0 / denom):.1f}"


def _render_probe_log(counters: dict[str, int], target: int, decision: str) -> str:
    n_rounds = counters.get("rounds_total", 0)
    n_plant = counters.get("rounds_with_bomb_plant", 0)
    pct_plant = (n_plant * 100.0 / n_rounds) if n_rounds else 0.0
    d05_triggered = n_rounds > 0 and pct_plant < 50.0
    return (
        "# Phase 2 — Probe Log\n\n"
        f"**Run completed:** {datetime.now(tz=UTC).isoformat()}\n"
        f"**Decision:** {decision}\n\n"
        "## Path A — be-prod.rib.gg/v1/ (primary)\n\n"
        f"- Events fetched: {counters.get('events', 0)}\n"
        f"- Series fetched: {counters.get('series', 0)}\n"
        f"- Matches inserted: {counters.get('matches', 0)} (target {target})\n"
        f"- Rounds inserted: {counters.get('rounds_inserted', 0)}\n"
        f"- Matches skipped (no events): "
        f"{counters.get('matches_skipped_no_events', 0)}\n\n"
        "## Event Coverage (D-05 partial-pass policy)\n\n"
        f"- Rounds total: {n_rounds}\n"
        f"- Rounds with `ts_round_start`: "
        f"{_pct(counters.get('rounds_with_round_start', 0), n_rounds)}% "
        f"({counters.get('rounds_with_round_start', 0)})\n"
        f"- Rounds with `ts_first_kill`: "
        f"{_pct(counters.get('rounds_with_first_kill', 0), n_rounds)}% "
        f"({counters.get('rounds_with_first_kill', 0)})\n"
        f"- Rounds with `ts_round_end`: "
        f"{_pct(counters.get('rounds_with_round_end', 0), n_rounds)}% "
        f"({counters.get('rounds_with_round_end', 0)})\n"
        f"- Rounds with `ts_bomb_plant`: "
        f"{_pct(n_plant, n_rounds)}% ({n_plant})\n"
        f"- **D-05 partial-pass triggered:** {'true' if d05_triggered else 'false'}\n"
        f"  - If true: calibrator MUST populate only `cells_no_econ` and "
        f"`cells_no_map`; `cells_full` will be empty.\n\n"
        "## Sources considered, rejected\n\n"
        "- (2) `valorantr` R-package — R not installed on this Windows host; "
        "redundant with direct Python `requests` against the same `/v1/` endpoints.\n"
        "- (3) `FlynV/RIB.GG-Web-Scraper` — Windows-binary Discord-bot tool, "
        "no Python library.\n"
        "- (4) `bo3.gg` — match-level metadata only (no per-round events); "
        "useful as cross-confirm only.\n\n"
        "## Acceptance evaluation (D-02)\n\n"
        f"- Target: {target} matches.\n"
        f"- Achieved: {counters.get('matches', 0)} matches.\n"
        "- Floor for must-have #1: 500 matches.\n"
        f"- Pass: {'YES' if counters.get('matches', 0) >= 500 else 'NO'}\n"
    )


# --------------------------------------------------------------------------- #
# CLI (BLOCKER 1 — explicit FAIL halt with 02-PHASE-STATUS.md)                #
# --------------------------------------------------------------------------- #


def _write_phase_status_fail(status_path: Path, reason: str) -> None:
    """BLOCKER 1: write 02-PHASE-STATUS.md when Path A FAILs acceptance.

    The orchestrator reads this file; the operator runs
    `/gsd-insert-phase 02.5-path-b-ocr` to plan Path B as a separate phase.
    """
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(
        "# Phase 02 — Status: FAIL\n\n"
        f"**Reason:** {reason}\n\n"
        f"**Recorded:** {datetime.now(tz=UTC).isoformat()}\n\n"
        "## Next steps (operator)\n\n"
        "Per D-10 and revision-feedback BLOCKER 1, Path A's --live run failed\n"
        "the acceptance bar. Plan Path B as decimal phase 02.5:\n\n"
        "```\n"
        "/gsd-insert-phase 02.5-path-b-ocr\n"
        "```\n\n"
        "Plan 02-04 and Plan 02-05 are SKIPPED until Path B (or Path C deferral)\n"
        "satisfies REQ-round-event-data-pipeline. See 02-PROBE-LOG.md for the\n"
        "full failure evidence.\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live",
        action="store_true",
        help=(
            "Perform the full live scrape (writes data/round_events.sqlite + "
            "02-PROBE-LOG.md). Default is --dry-run (no HTTP / no SQLite write — "
            "CRule 13 safety)."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Default mode. Resolve recency cutoff and exit; no HTTP; no SQLite write.",
    )
    parser.add_argument(
        "--target",
        type=int,
        default=RIBGG_TARGET_MATCH_COUNT,
        help=f"Target match count (default {RIBGG_TARGET_MATCH_COUNT}; floor 500).",
    )
    parser.add_argument(
        "--out-db",
        type=Path,
        default=Path("data/round_events.sqlite"),
        help="Output SQLite path (live mode only).",
    )
    parser.add_argument(
        "--probe-log",
        type=Path,
        default=Path(".planning/phases/02-round-event-data/02-PROBE-LOG.md"),
        help="Probe log markdown destination.",
    )
    parser.add_argument(
        "--phase-status",
        type=Path,
        default=Path(".planning/phases/02-round-event-data/02-PHASE-STATUS.md"),
        help="Phase status markdown (written on FAIL per BLOCKER 1).",
    )
    args = parser.parse_args(argv)

    # Default: dry-run is implicit unless --live
    if not args.live:
        recency_iso = _eighteen_months_ago_iso()
        sys.stdout.write(
            f"DRY-RUN: target={args.target} recency_cutoff={recency_iso} "
            f"out_db={args.out_db} probe_log={args.probe_log}\n"
            "Pass --live to perform the live scrape.\n"
        )
        return 0

    args.out_db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(args.out_db) as conn:
        create_round_events_schema(conn)
        counters = _run_scrape(conn, target_match_count=args.target)

    # BLOCKER 1: explicit PASS / FAIL handling
    matches = counters.get("matches", 0)
    if matches >= 500:
        decision = "Path A passed"
        _write_probe_log(args.probe_log, counters, args.target, decision)
        return 0
    decision = (
        f"Path A insufficient ({matches} < 500 matches) — "
        "phase HALTED. Plan Path B as decimal phase 02.5 per BLOCKER 1 / D-10."
    )
    _write_probe_log(args.probe_log, counters, args.target, decision)
    _write_phase_status_fail(args.phase_status, decision)
    sys.stderr.write(
        f"FAIL: only {matches} matches ingested (target {args.target}, floor 500).\n"
        f"02-PHASE-STATUS.md written to {args.phase_status}.\n"
        "Halt the executor; run `/gsd-insert-phase 02.5-path-b-ocr` to plan Path B.\n"
    )
    return 2  # non-zero: orchestrator must NOT proceed to Wave 3


if __name__ == "__main__":
    raise SystemExit(main())
