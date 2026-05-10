"""Permanent xfail wrapper for the deprecated v1 calibrator integration tests.

03-07 status: this file's v1 calibrator tests have been retired. The v1
calibrator (``scripts/calibrate_round_conclusion.py``) keys cells on the
deleted v1 schema ``(numerical_diff, bomb_planted, side, econ_bucket, map)``
and consumes ``cells_no_econ`` — both gone in 03-02 (RoundConclusionLookup
v2 surface) and 03-07 (atomic-replace ``models/round_conclusion.json``).

The active v2 calibrator surface tests live at
``tests/calibration/test_calibrate_round_conclusion_v2.py``. The original
v1 calibrator script remains on disk as forensic reference (its module
docstring lists the v1-vs-v2 differences and points at the v2 sibling).

This file's single ``test_v1_calibrator_deprecated`` test is a permanent
xfail pointer; deleting the file would also work, but keeping the marker
preserves git-blame continuity for the v1 calibration test history.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.xfail(
    reason=(
        "v1 calibrator superseded by scripts/calibrate_round_conclusion_v2.py "
        "per 03-07; see tests/calibration/test_calibrate_round_conclusion_v2.py"
    ),
    strict=False,
)


def test_v1_calibrator_deprecated() -> None:
    """Permanent xfail: v1 calibrator deprecated.

    See ``scripts/calibrate_round_conclusion_v2.py`` for the v2 calibrator
    and ``tests/calibration/test_calibrate_round_conclusion_v2.py`` for
    its surface tests.
    """
    raise NotImplementedError(
        "v1 calibrator deprecated — see test_calibrate_round_conclusion_v2.py"
    )
