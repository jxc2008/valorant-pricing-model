"""REQ-round-conclusion-lookup — SPEC §7 acceptance: post_plant_p hierarchy + schema_version gate.

RED stub. Wave 2A (plan 03-02) populates this with unit tests asserting
(a) post_plant_p walks the (att, def, time_bucket, side, map) -> ... -> side
baseline fallback chain, (b) RoundConclusionLookup.from_json hard-fails on
schema_version != 2 (D-06), (c) between_round_p returns the per-side baseline.
"""
from __future__ import annotations

import pytest


def test_post_plant_p_hierarchy() -> None:
    pytest.xfail("Wave 2A — RoundConclusionLookup.post_plant_p hierarchical fallback pending")


def test_from_json_rejects_v1() -> None:
    pytest.xfail("Wave 2A — D-06 schema_version=2 hard-fail gate pending")


def test_between_round_p_returns_side_baseline() -> None:
    pytest.xfail("Wave 2A — RoundConclusionLookup.between_round_p surface pending")
