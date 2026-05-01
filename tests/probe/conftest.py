"""Shared probe-test fixtures.

Loads recorded JSON fixtures from sibling `fixtures/` directory. NO live HTTP
in CI per 02-VALIDATION.md "Manual-Only Verifications" — live probe is opt-in
via Plan 02-03 manual checkpoint.

Sources
-------
- 02-VALIDATION.md (Wave 0: tests/probe/fixtures/match_details.json)
- 02-RESEARCH.md §"Pattern 1" (verified schema)
- src/pricing/data.py:128-144 (Path+json.loads encoding="utf-8" pattern)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

FIXTURE_DIR: Path = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def events_response() -> dict[str, Any]:
    """GET /v1/events response sample."""
    return _load("events_response.json")


@pytest.fixture(scope="session")
def series_response() -> dict[str, Any]:
    """GET /v1/series response sample."""
    return _load("series_response.json")


@pytest.fixture(scope="session")
def match_details() -> dict[str, Any]:
    """GET /v1/matches/{id}/details response sample."""
    return _load("match_details.json")
