"""Path B contingency stub — OCR labeling of Valorant VOD frames (DEFERRED).

NOT IMPLEMENTED. This file is a placeholder per Phase 2 phase_specific_guidance:
  Plan 02-03 (Path A rib.gg ETL) is the verified primary path.
  Path B (this file) only activates if Path A's --live scrape fails to yield
  >=500 distinct match_id values OR if the user explicitly elects Path B per D-10.

If you arrived here because Path A failed:
  1. Re-read .planning/phases/02-round-event-data/02-PROBE-LOG.md for the
     failure mode.
  2. Read 02-RESEARCH.md §"State of the Art" — use `cv2.matchTemplate`, NOT
     Tesseract, for Valorant HUD digits (Valorant uses a custom font; OCR
     misdetects). Tesseract is reserved for player nameplates only.
  3. Open a new GSD plan-phase task:
     ``phase 02.5 (path-b-ocr) via /gsd-insert-phase 02.5 --slug path-b-ocr``.
  4. The new plan handles cv2 frame extraction, ROI cropping, template matching
     at `OCR_FRAMES_PER_SECOND = 1.0` (declared in src/config/constants.py per
     Plan 02-01).
  5. Output the same `data/round_events.sqlite` shape (CON-round-events-schema)
     so Plan 02-04's calibrator consumes Path B output unmodified.

Sources
-------
- 02-CONTEXT.md D-10 (Path A fails -> commit to Path B; 2-week OCR labeling)
- 02-CONTEXT.md D-11 (Both fail -> Path C flat 0.5)
- 02-RESEARCH.md Summary (Path B explicitly deferred — Path A live-verified working)
- 02-RESEARCH.md §"State of the Art" (template matching, not Tesseract)
- src/config/constants.OCR_FRAMES_PER_SECOND (anchored here)
- ROADMAP.md §2 (must-have #2 Path B branch — 100 VODs at 1Hz, 10% hand-verified)
"""

from __future__ import annotations

from src.config.constants import (  # noqa: F401 — anchor reference for phase 02.5
    OCR_FRAMES_PER_SECOND,
)


def main() -> int:
    raise NotImplementedError(
        "Path B OCR labeling is deferred (D-10 / 02-RESEARCH.md Summary). "
        "Plan A (rib.gg ETL via scripts/probe_round_events.py) is the verified "
        "primary path. If Plan 02-03's --live run failed acceptance "
        "(<500 matches), open a new GSD plan named 'phase 02.5 (path-b-ocr) "
        "via /gsd-insert-phase 02.5 --slug path-b-ocr' per the module "
        f"docstring. Reference: OCR_FRAMES_PER_SECOND={OCR_FRAMES_PER_SECOND}."
    )


if __name__ == "__main__":
    raise SystemExit(main())
