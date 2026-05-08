"""RoundConclusionLookup.to_json -> from_json identity round-trip.

03-02: every test in this file exercises the v1 5-key cells_full schema
``(numerical_diff, bomb_planted, side, econ_bucket, map)`` + the deleted
``cells_no_econ`` field. The v2 surface drops cells_no_econ and rekeys
cells_full to ``(att, def_, time_bucket, side, map)`` (D-04). v2 round-trip
coverage moved to tests/pricing/test_round_conclusion.py
``test_to_json_and_from_json_roundtrip`` + ``test_to_json_writes_schema_version_2``.

Tests below xfail with a TODO pointer to 03-07 (calibrator rewrite); the v2
calibrator + ETL re-run will replace this file's calibration-flavored
fixtures with the real v2 surface.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_XFAIL_REASON = (
    "03-07 — v1 cells_no_econ + 5-key cells_full schema deleted; "
    "v2 round-trip coverage in tests/pricing/test_round_conclusion.py"
)


def test_roundtrip_empty_lookup(tmp_path: Path) -> None:
    pytest.xfail(_XFAIL_REASON)


def test_roundtrip_populated_lookup(tmp_path: Path) -> None:
    pytest.xfail(_XFAIL_REASON)


def test_from_json_raises_filenotfound_on_missing(tmp_path: Path) -> None:
    pytest.xfail(_XFAIL_REASON)


def test_serialized_cells_carry_n_p_hat_parent_p_not_shrunk(tmp_path: Path) -> None:
    pytest.xfail(_XFAIL_REASON)
