"""REQ-round-conclusion-lookup — SPEC §7: D-05 dispatch (bomb_planted vs between-round).

RED stub. Wave 2A (plan 03-02) populates this with unit tests asserting that
_live_theo_impl routes bomb_planted=True to post_plant_p + override DP recursion
and bomb_planted=False to the between-round path; mid-round-not-planted uses
between-round with degraded confidence.
"""
from __future__ import annotations

import pytest


def test_dispatch_bomb_planted() -> None:
    pytest.xfail("Wave 2A — D-05 bomb_planted dispatch path pending")


def test_dispatch_between_round() -> None:
    pytest.xfail("Wave 2A — D-05 between-round dispatch path pending")
