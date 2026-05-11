"""PortfolioState — per-series exposure registry (REQ-kelly-sizer support).

Owns the ``dict[series_id, fractional_exposure]`` that
``src/sizing/kelly.kelly_size`` consumes via the ``snapshot()`` method. The
pure-function sizer + mutable registry split lets the sizer stay
``mypy --strict`` clean (no I/O, no state), while the registry exposes the
``on_place`` / ``on_settle`` pair that the quoter loops invoke.

Pitfall 5 (RESEARCH §"Common Pitfalls"): exposure MUST be decremented on
round resolution. If ``on_settle`` is never called, exposure monotonically
grows and ``kelly_size`` returns 0 forever after the first few placements.
The class makes the ``on_place`` / ``on_settle`` pair grep-discoverable
(``rg "on_settle"``) so plan 04-08 reconciliation can wire the
round-resolution callback correctly.

Source: PRD §2.3 / DEC-023 v2 / RESEARCH §"Architecture Patterns" Pattern 2.
"""
from __future__ import annotations


class PortfolioState:
    """Registry of per-series fractional exposure.

    Single owner per bot process. Quoters CALL ``on_place`` at placement time
    (with the fraction that ``kelly_size`` produced divided by bankroll); the
    round-resolution path CALLS ``on_settle`` when the series-level position
    settles (Phase 03 metrics JSONL records the ``seq_id`` of the resolution
    event; plan 04-08 reconciliation wires the callback).
    """

    __slots__ = ("_exposure",)

    def __init__(self) -> None:
        self._exposure: dict[str, float] = {}

    def on_place(self, series_id: str, fraction: float) -> None:
        """Increment ``exposure[series_id]`` by ``fraction``.

        Raises:
            ValueError: if ``fraction < 0`` (placements always increase
                exposure; a negative fraction means a programming error).
        """
        if fraction < 0:
            raise ValueError(
                f"on_place fraction must be non-negative; got {fraction}"
            )
        self._exposure[series_id] = self._exposure.get(series_id, 0.0) + fraction

    def on_settle(self, series_id: str, fraction: float) -> None:
        """Decrement ``exposure[series_id]`` by ``fraction``; clip at 0.0.

        Clipping at 0 protects against double-settlement bugs (e.g.,
        a resolution event delivered twice) — exposure should never go
        negative under any real-world sequence of placements + settlements.

        Raises:
            ValueError: if ``fraction < 0``.
        """
        if fraction < 0:
            raise ValueError(
                f"on_settle fraction must be non-negative; got {fraction}"
            )
        new_exposure = self._exposure.get(series_id, 0.0) - fraction
        self._exposure[series_id] = max(0.0, new_exposure)

    def current(self, series_id: str) -> float:
        """Return current fractional exposure for ``series_id``; 0.0 if unknown."""
        return self._exposure.get(series_id, 0.0)

    def snapshot(self) -> dict[str, float]:
        """Return a fresh dict copy.

        ``kelly_size`` consumes this; mutation of the returned dict does NOT
        affect this ``PortfolioState``.
        """
        return dict(self._exposure)
