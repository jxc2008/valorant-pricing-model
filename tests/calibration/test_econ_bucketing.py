"""Smoke test that src.pricing.economy.credits_to_bucket is importable
and exposes the canonical CON-economy-buckets boundaries.

VALIDATION.md Wave 0 lists this as a "Phase-3-shareable boundary cases" file.
Detailed boundary coverage lives in tests/pricing/test_economy.py (Plan 02-01).
"""

from __future__ import annotations

import pytest

from src.pricing.economy import credits_to_bucket


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
