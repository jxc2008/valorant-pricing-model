"""Sizing layer — portfolio-aware half-Kelly with per-market + per-series caps.

DEC-004 + DEC-023 v2. Pure functional surface; the mutable
per-series-exposure registry lives at ``src/quoting/portfolio.py``.
"""
from src.sizing.kelly import kelly_size

__all__ = ["kelly_size"]
