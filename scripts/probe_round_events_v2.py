"""Phase 3 v2 ETL — augmented Phase 2 rib.gg scrape with a_alive/b_alive persisted.

REQ-round-conclusion-lookup (calibration arm). Salvages
``scripts/probe_round_events.py`` (Phase 2 v1 ETL) wholesale, then layers four
v2 augmentations per 03-CONTEXT.md:

  - **D-07**: ``synthesize_mid_round_states`` PERSISTS ``a_alive`` and
    ``b_alive`` per state dict. The v1 ETL tracked these locally then
    discarded them (lines 268-269 of the v1 file); the v2 calibrator needs the
    raw counts to derive ``(att, def_)`` per row.
  - **D-08**: HTTP layer wraps ``requests_cache.CachedSession`` filesystem
    backend at ``data/ribgg_cache``. Re-runs after a crash hit the cache (~1ms
    disk read per call) so resume is essentially free for already-fetched
    pages. Phase 2 resilience patterns (Connection: close, ``_ribgg_wait``
    Retry-After honoring, per-page skip + 5-failure cooldown) compose
    unchanged through CachedSession.
  - **D-09**: per-match SAVEPOINT transactions. ``write_match_atomic(conn,
    match_id, rows)`` opens ``SAVEPOINT match_<id>``, writes all rounds, then
    ``RELEASE``; on exception, ``ROLLBACK TO SAVEPOINT match_<id>``. Resume
    via ``SELECT DISTINCT match_id`` over the existing rows skips already-
    persisted matches without a separate progress file.
  - v2 schema cut: ``econ_bucket`` is REMOVED from each state dict. The v2
    ``RoundConclusionLookup`` keys cells on ``(att, def_, time_bucket, side,
    map)`` with no economy dimension (CLAUDE.md "Economy buckets — DEPRECATED
    in v2"). The ``map_name`` parameter remains row-level metadata only.

Output: ``data/round_events_v2.sqlite``. Reads via
``scripts/calibrate_round_conclusion_v2.py``.

CLI
---

    python scripts/probe_round_events_v2.py --target-series 1000 \\
        --cache data/ribgg_cache --db data/round_events_v2.sqlite

Resume after a crash by re-running with the same flags — already-persisted
match_ids skip via ``SELECT DISTINCT match_id``.

Sources
-------
- 03-CONTEXT.md D-07 / D-08 / D-09 / D-10
- 03-RESEARCH.md §"Pattern 6" (requests-cache filesystem backend)
- scripts/probe_round_events.py (Phase 2 v1 ETL — direct salvage source; now
  DEPRECATED per its module docstring)
- src/config/constants.py (RIBGG_*, MID_ROUND_HEARTBEAT_S, RIBGG_CACHE_DIR,
  ROUND_EVENTS_V2_DB_PATH)
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
from requests_cache import NEVER_EXPIRE, CachedSession
from tenacity import RetryCallState, RetryError, retry, stop_after_attempt
from tqdm import tqdm

from src.config.constants import (
    MID_ROUND_HEARTBEAT_S,
    RIBGG_BASE_URL,
    RIBGG_CACHE_DIR,
    RIBGG_RATE_LIMIT_RPS,
    RIBGG_RECENCY_MONTHS,
    RIBGG_TARGET_MATCH_COUNT,
    RIBGG_TIER_FILTER,
    ROUND_EVENTS_V2_DB_PATH,
)

# --------------------------------------------------------------------------- #
# Typed shapes (v1 carry-forward; econ_bucket removed in state dicts below)   #
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
    # Per Phase 2 v1 ETL: disable urllib3 keep-alive pooling. Pooled sockets to
    # be-prod.rib.gg go stale on Windows; ``Connection: close`` makes the server
    # close cleanly and prevents urllib3 from caching the dead socket. Carried
    # forward verbatim — composes through CachedSession unchanged.
    "Connection": "close",
}


# --------------------------------------------------------------------------- #
# HTTP layer — D-08 CachedSession + W6 Retry-After honoring                   #
# --------------------------------------------------------------------------- #
#
# Module-level CachedSession; ``data/ribgg_cache`` filesystem backend. The
# session is shared across all HTTP calls in the module and is the SAME object
# that ``tenacity`` wraps around. Re-running after a crash with the same cache
# directory hits the cache for already-fetched pages (~1ms disk read).

session: CachedSession = CachedSession(
    cache_name=RIBGG_CACHE_DIR,
    backend="filesystem",
    expire_after=NEVER_EXPIRE,
    allowable_codes=[200],
    allowable_methods=["GET"],
)


def _ribgg_wait(retry_state: RetryCallState) -> float:
    """Custom tenacity wait function honoring rib.gg's Retry-After header (W6).

    If the most recent attempt raised an HTTPError carrying a ``Retry-After``
    header (typical 429/503 from Heroku-fronted APIs), wait that many seconds
    capped at 60. Otherwise fall through to exponential backoff capped at 30s.

    Phase 2 v1 ETL pattern carried forward verbatim.
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
    """GET via CachedSession with tenacity retry. 60s per-call timeout.

    Wait function honors ``Retry-After`` header before falling through to
    exponential backoff capped at 30s.
    """
    resp = session.get(url, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    out: dict[str, Any] = resp.json()
    return out


def _throttle() -> None:
    """Sleep 1/RIBGG_RATE_LIMIT_RPS seconds between fetches (~2 rps polite)."""
    time.sleep(1.0 / RIBGG_RATE_LIMIT_RPS)


# --------------------------------------------------------------------------- #
# Schema (v2 — same shape as Phase 2 v1, but stored at v2 path)               #
# --------------------------------------------------------------------------- #
#
# The ``mid_round_states`` JSON blob now carries ``a_alive`` / ``b_alive`` per
# state and DROPS ``econ_bucket``. The SQLite columns themselves are unchanged
# from Phase 2 — the schema delta is contained inside the JSON blob, which is
# additive and forward-compatible (D-07 RESEARCH §"Architecture Patterns").


def create_round_events_v2_schema(conn: sqlite3.Connection) -> None:
    """Install the v2 schema. Same column shape as Phase 2 — JSON blob delta only."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS round_events_v2 (
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
        CREATE INDEX IF NOT EXISTS idx_round_events_v2_map ON round_events_v2(map_num);

        CREATE TABLE IF NOT EXISTS matches_v2 (
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
            side_a_this_round         TEXT,
            PRIMARY KEY (match_id, team_a_team_num)
        );
        """
    )
    conn.commit()


# --------------------------------------------------------------------------- #
# Side mapping (Pitfall 3 — round-13 half flip, carry-forward from v1)        #
# --------------------------------------------------------------------------- #


def side_for_team_a(
    round_num: int,
    attacking_first_team_num: int,
    team_a_team_num: int,
) -> str:
    """Returns 'atk' or 'def' for team A in this round.

    Sides flip at round 13 (start of second half). OT (rounds 25+) flip every
    pair, but Phase 2 carry-forward collects regulation rounds only.
    """
    is_first_half = round_num <= 12
    is_a_attacker_in_first_half = attacking_first_team_num == team_a_team_num
    a_attacks_this_round = (
        is_a_attacker_in_first_half if is_first_half else not is_a_attacker_in_first_half
    )
    return "atk" if a_attacks_this_round else "def"


# --------------------------------------------------------------------------- #
# v2 mid_round_states[] synthesis — D-07 a_alive/b_alive PERSIST              #
# --------------------------------------------------------------------------- #


def synthesize_mid_round_states_v2(
    round_events: list[dict[str, Any]],
    round_team_a_players: set[int],
    round_team_b_players: set[int],
    side_a_this_round: str,
) -> list[dict[str, Any]]:
    """v2 hybrid event+heartbeat synthesis with a_alive/b_alive persisted (D-07).

    Delta vs Phase 2 v1 ``synthesize_mid_round_states``:
      - PERSIST ``a_alive`` and ``b_alive`` per state dict (the v1 tracked
        these in local vars at lines 268-269 then discarded them).
      - DROP ``econ_bucket`` field — v2 schema cuts the economy dimension.
      - DROP ``numerical_diff`` field — derivable as ``a_alive - b_alive``
        when needed; the calibrator keys on raw alive counts.

    Carry-forward semantics (D-06 hybrid + D-08 carry-forward):
      - Pre-emit a t=0 heartbeat before the event loop.
      - Heartbeats every MID_ROUND_HEARTBEAT_S seconds carry forward
        ``bomb_planted`` and ``a_alive`` / ``b_alive`` from the most recent
        event.
      - Defuse terminates the round-states list (Pitfall 4).

    Args
    ----
    round_events: All events for one round, sorted by roundTimeMillis ascending.
    round_team_a_players: Player IDs comprising team A in this round.
    round_team_b_players: Player IDs comprising team B in this round.
    side_a_this_round: 'atk' or 'def' for team A; from ``side_for_team_a``.

    Returns
    -------
    Time-ordered list of state dicts. Each carries:
        ``t_offset, kind, a_alive, b_alive, bomb_planted, side``.
    """
    sorted_events = sorted(
        round_events,
        key=lambda e: (e["roundTimeMillis"], e.get("killId") or 0),
    )

    a_alive = 5
    b_alive = 5
    bomb_planted = False
    states: list[dict[str, Any]] = []

    heartbeat_period_ms = int(MID_ROUND_HEARTBEAT_S * 1000)

    # W7 carry-forward: pre-emit t=0 heartbeat before the loop. The strict-
    # less-than condition would otherwise skip t=0 when the first event is
    # also at t=0 (the canonical "start" event).
    states.append(
        {
            "t_offset": 0.0,
            "kind": "heartbeat",
            "a_alive": a_alive,
            "b_alive": b_alive,
            "bomb_planted": bomb_planted,
            "side": side_a_this_round,
        }
    )
    next_heartbeat_ms = heartbeat_period_ms
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
                    "a_alive": a_alive,
                    "b_alive": b_alive,
                    "bomb_planted": bomb_planted,
                    "side": side_a_this_round,
                }
            )
            next_heartbeat_ms += heartbeat_period_ms

        et = ev["eventType"]
        if et == "kill":
            victim = ev.get("referencePlayerId")
            if victim in round_team_a_players:
                a_alive = max(0, a_alive - 1)
            elif victim in round_team_b_players:
                b_alive = max(0, b_alive - 1)
        elif et == "plant":
            bomb_planted = True
        elif et == "defuse":
            bomb_planted = False
        # eventType == "start" — no state change

        # Skip the start event at t=0 (the t=0 heartbeat above already covers it).
        if not (et == "start" and t_ms == 0):
            states.append(
                {
                    "t_offset": t_ms / 1000.0,
                    "kind": "event",
                    "a_alive": a_alive,
                    "b_alive": b_alive,
                    "bomb_planted": bomb_planted,
                    "side": side_a_this_round,
                }
            )

        # Defuse is a round terminator (Pitfall 4)
        if et == "defuse":
            terminated = True

    return states


# --------------------------------------------------------------------------- #
# Endpoint helpers (carry-forward verbatim)                                   #
# --------------------------------------------------------------------------- #


def _eighteen_months_ago_iso() -> str:
    return (
        datetime.now(tz=UTC) - timedelta(days=30 * RIBGG_RECENCY_MONTHS)
    ).isoformat()


def list_tier1_events(recency_iso: str) -> list[dict[str, Any]]:
    """VCT-tier-1 filter; mirrors Phase 2 v1 with paginated retries + cool-off."""
    out: list[dict[str, Any]] = []
    skip = 0
    consecutive_page_failures = 0
    while True:
        url = (
            f"{RIBGG_BASE_URL}/events?take=50"
            f"&sort=startDate&sortAscending=false&skip={skip}"
        )
        try:
            resp = get_json(url)
        except (RetryError, requests.exceptions.RequestException) as exc:
            consecutive_page_failures += 1
            sys.stderr.write(
                f"events page skip={skip} failed ({type(exc).__name__}); "
                f"advancing past 50 events (consecutive failures: "
                f"{consecutive_page_failures})\n"
            )
            if consecutive_page_failures >= 5:
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
# Row transform — perspective doubling + v2 state synthesis                   #
# --------------------------------------------------------------------------- #


def _row_for_round(
    *,
    match_id: str,
    map_num: int,
    round_num: int,
    sorted_events: list[dict[str, Any]],
    team_a_players: set[int],
    team_b_players: set[int],
    side_a: str,
) -> dict[str, Any] | None:
    """Build one round_events_v2 row; None if no events."""
    if not sorted_events:
        return None
    ts_round_start = sorted_events[0]["roundTimeMillis"] / 1000.0
    ts_round_end = sorted_events[-1]["roundTimeMillis"] / 1000.0
    kills = [e for e in sorted_events if e["eventType"] == "kill"]
    plants = [e for e in sorted_events if e["eventType"] == "plant"]
    states = synthesize_mid_round_states_v2(
        round_events=sorted_events,
        round_team_a_players=team_a_players,
        round_team_b_players=team_b_players,
        side_a_this_round=side_a,
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
    """Yield TWO rows per round (perspective doubling — BLOCKER 4 carry-forward)."""
    by_round: dict[int, list[dict[str, Any]]] = {}
    for ev in details.get("events") or []:
        by_round.setdefault(ev["roundNumber"], []).append(ev)

    t1 = match_meta.get("team1PlayerIds")
    t2 = match_meta.get("team2PlayerIds")
    atk_first = match_meta.get("attackingFirstTeamNumber")
    if not t1 or not t2 or atk_first is None:
        return
    team1_players = set(t1)
    team2_players = set(t2)
    attacking_first = int(atk_first)

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
                team_a_players=team_a_players,
                team_b_players=team_b_players,
                side_a=side_a,
            )
            if row is not None:
                row["_team_a_team_num"] = team_a_team_num
                row["_side_a_this_round"] = side_a
                yield row


# --------------------------------------------------------------------------- #
# D-09 idempotency — per-match SAVEPOINT + resume by SELECT DISTINCT          #
# --------------------------------------------------------------------------- #


def get_resume_set(conn: sqlite3.Connection) -> set[str]:
    """Return the set of plain match_ids already persisted in round_events_v2.

    Suffix-aware: rib.gg perspective doubling appends ``::1`` / ``::2`` per
    Phase 2 BLOCKER 4 carry-forward. Strip the suffix on read so the resume
    skip-set keys on the original rib.gg match id (the orchestrator iterates
    in plain-id space).
    """
    out: set[str] = set()
    for (raw_id,) in conn.execute("SELECT DISTINCT match_id FROM round_events_v2"):
        if "::" in raw_id:
            out.add(raw_id.split("::", 1)[0])
        else:
            out.add(raw_id)
    return out


def write_match_atomic(
    conn: sqlite3.Connection,
    match_id: str,
    rows: list[dict[str, Any]],
    *,
    match_meta: dict[str, Any],
    event_id: int,
    series_id: int,
    map_num: int,
) -> None:
    """Per-match SAVEPOINT transaction (D-09).

    Opens ``SAVEPOINT match_<id>``, writes all rounds + match metadata under
    that savepoint, then ``RELEASE``. On any exception, ``ROLLBACK TO
    SAVEPOINT match_<id>`` so partial rounds for this match are rolled back
    atomically. SQLite identifier sanitation: the savepoint name strips
    non-alphanumeric chars from match_id to keep the SQL parser happy.
    """
    savepoint_name = "match_" + "".join(c for c in str(match_id) if c.isalnum())
    conn.execute(f"SAVEPOINT {savepoint_name}")
    try:
        # matches_v2 — one row per perspective (deduped by team_a_team_num).
        perspectives_seen: set[int] = set()
        for r in rows:
            ta = int(r["_team_a_team_num"])
            if ta in perspectives_seen:
                continue
            perspectives_seen.add(ta)
            winning = int(match_meta["winningTeamNumber"])
            round_won_by_a = int(winning == ta)
            conn.execute(
                """INSERT OR REPLACE INTO matches_v2
                   (match_id, event_id, series_id, map_num, map_name,
                    team_a_team_num, attacking_first_team_num,
                    team1_score, team2_score, round_won_by_a,
                    side_a_this_round)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
                    r["_side_a_this_round"],
                ),
            )

        # round_events_v2 — strip routing keys; suffix match_id with team perspective.
        rows_for_sql: list[dict[str, Any]] = []
        for r in rows:
            ta = int(r["_team_a_team_num"])
            sql_row = {
                k: v
                for k, v in r.items()
                if k not in ("_team_a_team_num", "_side_a_this_round")
            }
            sql_row["match_id"] = f"{r['match_id']}::{ta}"
            rows_for_sql.append(sql_row)

        conn.executemany(
            """INSERT OR REPLACE INTO round_events_v2
               (match_id, map_num, round_num, ts_round_start, ts_first_kill,
                ts_bomb_plant, ts_round_end, mid_round_states)
               VALUES (:match_id, :map_num, :round_num, :ts_round_start,
                       :ts_first_kill, :ts_bomb_plant, :ts_round_end,
                       :mid_round_states)""",
            rows_for_sql,
        )
        conn.execute(f"RELEASE SAVEPOINT {savepoint_name}")
    except Exception:
        conn.execute(f"ROLLBACK TO SAVEPOINT {savepoint_name}")
        raise


# --------------------------------------------------------------------------- #
# Scrape orchestration (resume-aware via D-09 + cache-aware via D-08)         #
# --------------------------------------------------------------------------- #


def _run_scrape(
    conn: sqlite3.Connection,
    target_match_count: int,
    progress: bool = True,
) -> dict[str, int]:
    """Main scrape loop with D-09 resume.

    Pre-fetches the resume set; skips matches whose rows are already in
    ``round_events_v2``. The ``target_match_count`` counts matches done in
    this run only (so a 1000-target re-run on a fully-populated DB exits
    immediately).
    """
    counters: dict[str, int] = {
        "events": 0,
        "series": 0,
        "matches": 0,
        "matches_skipped_resume": 0,
        "matches_skipped_no_events": 0,
        "rounds_inserted": 0,
        "rounds_total": 0,
        "rounds_with_round_start": 0,
        "rounds_with_first_kill": 0,
        "rounds_with_round_end": 0,
        "rounds_with_bomb_plant": 0,
    }
    resume_set = get_resume_set(conn)
    if resume_set:
        sys.stdout.write(
            f"resume: skipping {len(resume_set)} match_ids already persisted "
            f"in round_events_v2\n"
        )

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
                match_id = str(match.get("id"))
                if match_id in resume_set:
                    counters["matches_skipped_resume"] += 1
                    continue
                try:
                    details = get_match_details(match["id"])
                except Exception as exc:  # noqa: BLE001
                    tqdm.write(f"match {match['id']} fetch failed: {exc}")
                    continue
                try:
                    rows = list(transform_match_to_rows(match, details, map_num))
                except Exception as exc:  # noqa: BLE001
                    tqdm.write(f"match {match.get('id')} transform failed: {exc}")
                    counters["matches_skipped_no_events"] += 1
                    continue
                if not rows:
                    counters["matches_skipped_no_events"] += 1
                    continue

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

                try:
                    write_match_atomic(
                        conn,
                        match_id,
                        rows,
                        match_meta=match,
                        event_id=event["id"],
                        series_id=series["id"],
                        map_num=map_num,
                    )
                except Exception as exc:  # noqa: BLE001
                    tqdm.write(
                        f"match {match.get('id')} SAVEPOINT rolled back: {exc}"
                    )
                    counters["matches_skipped_no_events"] += 1
                    continue

                counters["rounds_inserted"] += len(rows)
                counters["matches"] += 1
                matches_done += 1
                resume_set.add(match_id)
        # Commit between events — keeps the SAVEPOINT chain shallow.
        conn.commit()
    return counters


# --------------------------------------------------------------------------- #
# CLI                                                                         #
# --------------------------------------------------------------------------- #


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target-series",
        type=int,
        default=RIBGG_TARGET_MATCH_COUNT,
        help=(
            f"Target match count (default {RIBGG_TARGET_MATCH_COUNT}; floor "
            "500). The scrape exits when this many *new* matches have been "
            "persisted in this run, so re-runs against a populated DB exit "
            "fast (D-09 resume)."
        ),
    )
    parser.add_argument(
        "--cache",
        type=Path,
        default=Path(RIBGG_CACHE_DIR),
        help=(
            f"requests-cache filesystem directory (default {RIBGG_CACHE_DIR}). "
            "On cold cache: ~5 GB after a 1000-series scrape. On warm cache: "
            "near-zero network bytes."
        ),
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=Path(ROUND_EVENTS_V2_DB_PATH),
        help=f"v2 SQLite output path (default {ROUND_EVENTS_V2_DB_PATH}).",
    )
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable tqdm progress bar (useful inside the autonomous loop).",
    )
    args = parser.parse_args(argv)

    # Honor CLI cache override by rebuilding the module-level session if the
    # caller passed a non-default path. Default: use the one already created
    # at import time against RIBGG_CACHE_DIR.
    global session
    if str(args.cache) != RIBGG_CACHE_DIR:
        session = CachedSession(
            cache_name=str(args.cache),
            backend="filesystem",
            expire_after=NEVER_EXPIRE,
            allowable_codes=[200],
            allowable_methods=["GET"],
        )

    args.db.parent.mkdir(parents=True, exist_ok=True)
    args.cache.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(args.db) as conn:
        create_round_events_v2_schema(conn)
        counters = _run_scrape(
            conn,
            target_match_count=args.target_series,
            progress=not args.no_progress,
        )

    sys.stdout.write(
        "v2 ETL complete:\n"
        f"  matches inserted (this run): {counters['matches']}\n"
        f"  matches skipped (resume):    {counters['matches_skipped_resume']}\n"
        f"  matches skipped (no events): {counters['matches_skipped_no_events']}\n"
        f"  rounds inserted:             {counters['rounds_inserted']}\n"
        f"  rounds total (counted):      {counters['rounds_total']}\n"
        f"  rounds with bomb_plant:      {counters['rounds_with_bomb_plant']}\n"
        f"  output db:                   {args.db}\n"
        f"  cache dir:                   {args.cache}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
