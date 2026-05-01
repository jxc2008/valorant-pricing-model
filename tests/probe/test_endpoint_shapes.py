"""Schema parsers for be-prod.rib.gg/v1/ endpoints (offline fixtures only).

Pins the rib.gg JSON contract Plan 02-03's probe consumes. If rib.gg silently
changes a field name or type, these tests fail before the live probe wastes
bandwidth on a thousand calls.

Sources
-------
- 02-RESEARCH.md §"Pattern 1: rib.gg API endpoint chain" (verified 2026-04-30)
- tests/probe/fixtures/*.json (recorded samples covering plant / defuse / no-plant rounds)
"""

from __future__ import annotations

from typing import Any

VALID_EVENT_TYPES: frozenset[str] = frozenset({"start", "plant", "kill", "defuse"})


# --------------------------------------------------------------------------- #
# 1. /v1/events response shape                                                #
# --------------------------------------------------------------------------- #


def test_events_response_top_level_shape(events_response: dict[str, Any]) -> None:
    """Top-level: {data: list, meta: {total: int}}."""
    assert "data" in events_response
    assert "meta" in events_response
    assert isinstance(events_response["data"], list)
    assert isinstance(events_response["meta"], dict)
    assert "total" in events_response["meta"]
    assert isinstance(events_response["meta"]["total"], int)


def test_events_entries_have_required_fields(events_response: dict[str, Any]) -> None:
    """Each entry has id, name, divisions, seriesCount, startDate, vctRegions."""
    required = {"id", "name", "divisions", "seriesCount", "startDate", "vctRegions"}
    for entry in events_response["data"]:
        missing = required - set(entry.keys())
        assert not missing, f"event entry missing {missing}: {entry}"
        assert isinstance(entry["divisions"], list)
        assert isinstance(entry["vctRegions"], list)
        assert isinstance(entry["seriesCount"], int)


def test_events_filter_picks_vct_only(events_response: dict[str, Any]) -> None:
    """The filter `'VCT' in event.divisions` accepts VCT and rejects VCL."""
    accepted = [e for e in events_response["data"] if "VCT" in e.get("divisions", [])]
    rejected = [e for e in events_response["data"] if "VCT" not in e.get("divisions", [])]
    assert len(accepted) >= 1, "fixture must contain at least one VCT event"
    assert len(rejected) >= 1, "fixture must contain at least one non-VCT event"


# --------------------------------------------------------------------------- #
# 2. /v1/series response shape                                                #
# --------------------------------------------------------------------------- #


def test_series_response_embeds_matches(series_response: dict[str, Any]) -> None:
    """Each series.matches[i] has the fields the probe transforms into round_events rows."""
    required = {
        "id",
        "mapId",
        "map",
        "attackingFirstTeamNumber",
        "winningTeamNumber",
        "team1Score",
        "team2Score",
        "team1PlayerIds",
        "team2PlayerIds",
    }
    for series in series_response["data"]:
        assert "matches" in series
        for match in series["matches"]:
            missing = required - set(match.keys())
            assert not missing, f"match missing {missing}"
            assert isinstance(match["team1PlayerIds"], list)
            assert isinstance(match["team2PlayerIds"], list)
            assert "name" in match["map"]


# --------------------------------------------------------------------------- #
# 3. /v1/matches/{id}/details events[] + economies[] shape                    #
# --------------------------------------------------------------------------- #


def test_match_details_top_level_shape(match_details: dict[str, Any]) -> None:
    """Top-level: events (list), economies (list)."""
    assert "events" in match_details
    assert "economies" in match_details
    assert isinstance(match_details["events"], list)
    assert isinstance(match_details["economies"], list)


def test_match_details_event_required_fields(match_details: dict[str, Any]) -> None:
    """events[] entries have roundNumber, roundTimeMillis, eventType, attackingTeamNumber."""
    required = {"roundNumber", "roundTimeMillis", "eventType", "attackingTeamNumber"}
    for ev in match_details["events"]:
        missing = required - set(ev.keys())
        assert not missing, f"event missing {missing}: {ev}"
        assert isinstance(ev["roundNumber"], int)
        assert isinstance(ev["roundTimeMillis"], int)
        assert isinstance(ev["eventType"], str)
        assert isinstance(ev["attackingTeamNumber"], int)


def test_match_details_event_type_closure(match_details: dict[str, Any]) -> None:
    """Every events[].eventType is one of {start, plant, kill, defuse}."""
    for ev in match_details["events"]:
        assert ev["eventType"] in VALID_EVENT_TYPES, (
            f"unexpected eventType {ev['eventType']!r}"
        )


def test_match_details_economies_shape(match_details: dict[str, Any]) -> None:
    """economies[] entries have roundNumber, playerId, loadoutValue."""
    required = {"roundNumber", "playerId", "loadoutValue"}
    for econ in match_details["economies"]:
        missing = required - set(econ.keys())
        assert not missing, f"economy entry missing {missing}: {econ}"
        assert isinstance(econ["roundNumber"], int)
        assert isinstance(econ["playerId"], int)
        assert isinstance(econ["loadoutValue"], int)


# --------------------------------------------------------------------------- #
# 4. Round-termination coverage (Pitfall 4)                                   #
# --------------------------------------------------------------------------- #


def test_match_details_fixture_covers_three_termination_patterns(
    match_details: dict[str, Any],
) -> None:
    """Fixture must exercise plant-then-defuse, plant-then-time, and no-plant rounds.

    Pitfall 4 (defuse semantics) and Pitfall 4-related calibrator behavior depend on
    Plan 02-03 transforming all three patterns correctly. Wave 0 anchors them here.
    """
    rounds: dict[int, list[str]] = {}
    for ev in match_details["events"]:
        rounds.setdefault(ev["roundNumber"], []).append(ev["eventType"])

    has_plant_defuse = any("plant" in et and "defuse" in et for et in rounds.values())
    has_plant_no_defuse = any(
        "plant" in et and "defuse" not in et for et in rounds.values()
    )
    has_no_plant = any("plant" not in et for et in rounds.values())

    assert has_plant_defuse, "fixture missing plant-then-defuse round"
    assert has_plant_no_defuse, "fixture missing plant-without-defuse round"
    assert has_no_plant, "fixture missing no-plant round"
