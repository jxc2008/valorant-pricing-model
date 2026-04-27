"""Pricing layer — DP, Bradley-Terry blend, round-conclusion lookup, live_theo.

This package is type-checked under `mypy --strict` (CON-mypy-strict-pricing).
Every threshold imported here MUST come from `src.config.constants` (CLAUDE.md
rule 12). The single canonical pricing entry point is `live_theo` per DEC-010 —
do not introduce parallel `series_theo_*` variants.
"""
