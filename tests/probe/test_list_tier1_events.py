"""W10: unit test that monkeypatches scripts.probe_round_events.get_json
to return the events_response.json fixture, then calls list_tier1_events
and asserts only events whose `divisions` contain "VCT" are yielded.

Sources
-------
- Plan 02-02: tests/probe/fixtures/events_response.json (3 events: 2 VCT, 1 VCL)
- Revision feedback W10
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

probe_mod = pytest.importorskip(
    "scripts.probe_round_events",
    reason="Plan 02-03 must ship scripts/probe_round_events.py",
)

FIXTURE_DIR: Path = Path(__file__).parent / "fixtures"


def test_list_tier1_events_filters_to_vct_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fixture has 2 VCT events and 1 VCL event; only the VCT pair is yielded."""
    fixture: dict[str, Any] = json.loads(
        (FIXTURE_DIR / "events_response.json").read_text(encoding="utf-8")
    )

    call_count = {"n": 0}

    def fake_get_json(url: str) -> dict[str, Any]:
        # First call returns the fixture; subsequent calls return empty data
        # to terminate the pagination loop.
        call_count["n"] += 1
        if call_count["n"] == 1:
            return fixture
        return {"data": [], "meta": {"total": fixture["meta"]["total"]}}

    monkeypatch.setattr(probe_mod, "get_json", fake_get_json)
    # Disable the throttle to keep the test instant.
    monkeypatch.setattr(probe_mod, "_throttle", lambda: None)

    # Recency window wide enough that all fixture events qualify
    far_past_iso = (datetime.now(tz=UTC) - timedelta(days=365 * 5)).isoformat()
    out = probe_mod.list_tier1_events(far_past_iso)

    # Fixture has 2 VCT entries (id=5832, id=5833) and 1 VCL entry (id=5900).
    out_ids = {e["id"] for e in out}
    assert 5832 in out_ids
    assert 5833 in out_ids
    assert 5900 not in out_ids, "VCL event leaked through the VCT filter"
    for e in out:
        assert "VCT" in e.get("divisions", []), f"non-VCT event yielded: {e}"
