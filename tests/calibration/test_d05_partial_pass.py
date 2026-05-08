"""BLOCKER 3 regression: when 02-PROBE-LOG.md records 'D-05 partial-pass triggered: true',
the calibrator MUST skip the cells_full population pass and yield empty cells_full
while populating cells_no_econ / cells_no_map / cells_minimal normally.

03-02 status: every test in this file exercises the v1 calibrator and the
v1 ``cells_no_econ`` field, both of which are deleted in 03-02 per
CLAUDE.md "Economy buckets — DEPRECATED in v2". 03-07 (calibrator rewrite)
replaces these tests against the v2 ETL re-run dataset; until then they
xfail.

Source: 02-CONTEXT.md D-05; checker pass-2 BLOCKER 3 fix.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_XFAIL_REASON = (
    "03-07 — v1 calibrator + cells_no_econ deleted; v2 calibrator rewrite pending"
)


def test_d05_active_yields_empty_cells_full(tmp_path: Path) -> None:
    pytest.xfail(_XFAIL_REASON)


def test_d05_inactive_populates_cells_full(tmp_path: Path) -> None:
    pytest.xfail(_XFAIL_REASON)


def test_d05_no_probe_log_defaults_to_full_walk(tmp_path: Path) -> None:
    pytest.xfail(_XFAIL_REASON)
