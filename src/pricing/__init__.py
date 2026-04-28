"""Pricing layer — DP, Bradley-Terry blend, round-conclusion lookup, live_theo.

This package is type-checked under `mypy --strict` (CON-mypy-strict-pricing).
Every threshold imported here MUST come from `src.config.constants` (CLAUDE.md
rule 12). The single canonical pricing entry point is ``LiveTheoEngine`` per
DEC-010 / D-20 — do not introduce parallel ``series_theo_*`` variants
(DEC-010 / PRD §12.3 forbids them).

Public surface
--------------
The four names below are the ENTIRE Phase 1 pricing API. dp / blend /
round_types / round_conclusion are PRIVATE to the package — downstream code
must not import them directly (DEC-010 / D-12).
"""

from src.pricing.data import HalfRates, MatchState, TheoOutput
from src.pricing.live_theo import LiveTheoEngine

__all__ = ["LiveTheoEngine", "TheoOutput", "MatchState", "HalfRates"]
