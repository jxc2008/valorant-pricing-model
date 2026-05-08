"""ROI overlay helper for operator HUD calibration (03-CONTEXT D-11 / RESEARCH Pitfall 6).

Usage::

    uv run python scripts/dump_roi_overlay.py --frame <input.png> --output <annotated.png>

Reads a 1920x1080 broadcast frame, draws colored rectangles for every
configured OCR ROI from ``src/config/constants.py`` with text labels, and
writes the annotated frame.

Operator workflow
-----------------

1. Capture a representative live broadcast frame (post-plant + score
   banner + bomb icon visible).
2. Run this script.
3. Visually verify each rectangle lands on the right HUD element.
4. If any rectangle is off:
     - Edit ``src/config/constants.py`` (tuple values).
     - Bump ``BROADCAST_TEMPLATE_VERSION`` (e.g.,
       ``"vct-2026-international-rev2"``).
     - Re-run this script to re-verify.
5. Commit the updated constants + the updated annotated PNG to
   ``fixtures/calibration/`` for forensic record.

This script is read-only against ``src/``; it never modifies constants.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import cv2

from src.config.constants import (
    BOMB_PLANT_ICON_ROI,
    BROADCAST_TEMPLATE_VERSION,
    POST_PLANT_ATTACKERS_ROI,
    POST_PLANT_DEFENDERS_ROI,
    ROUND_END_BANNER_ROI,
    SCORE_BANNER_TEAM1_ROI,
    SCORE_BANNER_TEAM2_ROI,
)

# (color_BGR, label, roi)
_OVERLAYS: list[tuple[tuple[int, int, int], str, tuple[int, int, int, int]]] = [
    ((0, 255, 0),    "SCORE_T1",       SCORE_BANNER_TEAM1_ROI),
    ((0, 255, 0),    "SCORE_T2",       SCORE_BANNER_TEAM2_ROI),
    ((0, 0, 255),    "BOMB_ICON",      BOMB_PLANT_ICON_ROI),
    ((0, 255, 255),  "ROUND_END",      ROUND_END_BANNER_ROI),
    ((255, 255, 0),  "POST_PLANT_ATT", POST_PLANT_ATTACKERS_ROI),
    ((255, 0, 255),  "POST_PLANT_DEF", POST_PLANT_DEFENDERS_ROI),
]


def annotate(frame_path: Path, output_path: Path) -> None:
    """Read frame_path, draw all configured ROIs as labeled rectangles, save to output_path."""
    frame = cv2.imread(str(frame_path))
    if frame is None:
        raise FileNotFoundError(f"Cannot read frame: {frame_path}")
    h, w = frame.shape[:2]
    if (w, h) != (1920, 1080):
        print(
            f"WARNING: frame is {w}x{h}; constants assume 1920x1080. "
            "Recalibration likely needed."
        )
    for color, label, (x1, y1, x2, y2) in _OVERLAYS:
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        cv2.putText(
            frame, label, (x1, max(0, y1 - 5)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1,
        )
    # Stamp the broadcast template version in the bottom-left corner.
    cv2.putText(
        frame, f"template={BROADCAST_TEMPLATE_VERSION}",
        (10, h - 10),
        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), frame)
    print(f"Wrote annotated frame to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--frame", type=Path, required=True,
        help="Input broadcast frame PNG (1920x1080).",
    )
    parser.add_argument(
        "--output", type=Path, required=True,
        help="Output annotated PNG path.",
    )
    args = parser.parse_args()
    annotate(args.frame, args.output)


if __name__ == "__main__":
    main()
