"""Smoke test that the (deprecated) credits_to_bucket boundaries still match.

03-02 status: src/pricing/economy.py was DELETED per CLAUDE.md "Economy
buckets — DEPRECATED in v2". The function `credits_to_bucket` is now an
inline shim in `tests/calibration/conftest.py` (and `scripts/probe_round_events.py`)
retained ONLY so the v1 ETL script + v1 calibrator test still parse until
03-07 rewrites them. This test confirms the inline shim still implements the
canonical CON-economy-buckets boundaries; it will be deleted alongside the
calibrator rewrite in 03-07.
"""

from __future__ import annotations

import pytest

from tests.calibration.conftest import credits_to_bucket


@pytest.mark.parametrize(
    "credits,expected",
    [
        (4_999, "eco"),
        (5_000, "semi-eco"),
        (9_999, "semi-eco"),
        (10_000, "semi-buy"),
        (19_999, "semi-buy"),
        (20_000, "full"),
    ],
)
def test_econ_bucket_boundaries_for_calibration(credits: int, expected: str) -> None:
    assert credits_to_bucket(credits) == expected
