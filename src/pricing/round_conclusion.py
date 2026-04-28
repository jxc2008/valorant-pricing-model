"""Hierarchical mid-round-conclusion lookup skeleton (Phase 1).

Phase 1 ships the SHAPE per DEC-007 (5-level fallback chain) but every cell
returns ``_PHASE_1_FLAT_CELL_VALUE = 0.5`` regardless of input (D-06). Phase 2
calibrates real cell values without changing this interface — Path-C compatible.

The Bayesian shrinkage formula on ``_Cell`` is salvaged verbatim from
``reference/theo_engine.py:100`` per D-09 / DEC-013:
    shrunk = (n * p_hat + SHRINK_PRIOR * parent_p) / (n + SHRINK_PRIOR)

Sources
-------
- DEC-007 / roadmap.md §1.5 (hierarchical fallback chain)
- D-06, D-07, D-09 (CONTEXT.md)
- prd.md §5.3 (mid-round pricing design)
- 01-RESEARCH.md §6 (signature + shrinkage scaffold)
- reference/theo_engine.py:84-102 (shrinkage source)

Phase 1 -> Phase 2 seam
-----------------------
Phase 2 (REQ-round-event-data-pipeline) populates ``cells_full``, ``cells_no_econ``,
``cells_no_map``, ``cells_minimal`` from rib.gg / OCR-derived round-event data and
extends ``lookup`` to walk the fallback chain. The PUBLIC interface
(``RoundConclusionLookup.lookup`` and ``RoundConclusionFn`` Protocol) does NOT
change — only the body of ``lookup`` is rewritten and the dict fields populated.
This locks Path-C compatibility (Phase 4 quoting can ship without Phase 2).

Why frozen=True with mutable dict fields
----------------------------------------
``@dataclass(frozen=True)`` blocks reassignment of the field reference, NOT
mutation of the dict object the field points to. Phase 2 will populate cells
via ``lookup_obj.cells_full[key] = _Cell(...)``, which works on frozen instances.
This matches the established Python idiom (verified by 01-PATTERNS.md S3).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final, Protocol

from src.config.constants import SHRINK_PRIOR

# --------------------------------------------------------------------------- #
# 1. Phase 1 flat cell constant                                               #
# --------------------------------------------------------------------------- #


_PHASE_1_FLAT_CELL_VALUE: Final[float] = 0.5
"""Every ``RoundConclusionLookup.lookup`` invocation returns this value in Phase 1.

Source: D-06 / CONTEXT.md — the flat-0.5 placeholder is Path-C-compatible. Phase 2
calibrates real cell values; this constant is then unused at runtime but kept as
the defensive fallback at the bottom of the chain.
"""


# --------------------------------------------------------------------------- #
# 2. Bayesian-shrinkage cell                                                  #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class _Cell:
    """A single (numerical_diff, bomb_planted, side, econ_bucket, map) cell.

    Phase 1: only ``shrunk()`` is exercised by the formula test — no instances
    are stored in the lookup dicts (those are empty in Phase 1).

    Phase 2 populates instances of this class into the cells_* dicts on
    RoundConclusionLookup, then extends ``lookup`` to walk the chain.

    Attributes
    ----------
    n: Observed sample size in this cell (rounds matching the cell's keys).
    p_hat: Observed P(team A wins this round | cell context).
    parent_p: Parent-cell estimate (one level up the fallback chain) used as
        the Bayesian prior in ``shrunk()``.
    """

    n: int
    p_hat: float
    parent_p: float

    def shrunk(self) -> float:
        """Return the shrunk estimate.

        Source: ``reference/theo_engine.py:100`` — salvage verbatim per D-09.
        Formula: ``(n * p_hat + SHRINK_PRIOR * parent_p) / (n + SHRINK_PRIOR)``.

        Behavior:
          - At ``n == 0``: pure ``parent_p`` (prior dominates).
          - At ``n >> SHRINK_PRIOR``: converges to ``p_hat`` (empirical dominates).
          - At ``n == SHRINK_PRIOR``: arithmetic mean of empirical and prior.

        SHRINK_PRIOR is imported from src.config.constants per CRule 12 — never
        inline the literal here.
        """
        return (self.n * self.p_hat + SHRINK_PRIOR * self.parent_p) / (
            self.n + SHRINK_PRIOR
        )


# --------------------------------------------------------------------------- #
# 3. Public callable Protocol (consumed by live_theo in 01-05)                #
# --------------------------------------------------------------------------- #


class RoundConclusionFn(Protocol):
    """Callable shape for the round-conclusion lookup.

    ``RoundConclusionLookup.lookup`` (bound method) satisfies this Protocol;
    test fakes can also satisfy it. ``live_theo`` (01-05) types its
    round_conclusion parameter as ``RoundConclusionFn`` so it consumes the
    interface, not the concrete class — keeps the dependency direction
    one-way (live_theo -> round_conclusion).
    """

    def __call__(
        self,
        numerical_diff: int,
        bomb_planted: bool,
        side: str,
        econ_bucket: str,
        map_name: str,
    ) -> float: ...


# --------------------------------------------------------------------------- #
# 4. Hierarchical fallback chain skeleton                                     #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class RoundConclusionLookup:
    """5-tier hierarchical fallback-chain lookup (DEC-007 / roadmap 1.5).

    Phase 1 returns ``_PHASE_1_FLAT_CELL_VALUE`` for all inputs (D-06). The
    cells_* dicts and side_baseline ship empty/default; Phase 2 populates them
    from rib.gg / OCR round-event data without changing this class's public
    surface.

    Fallback chain order (D-07, walked by Phase 2 ``lookup``):
        1. ``cells_full``    — keyed on (numerical_diff, bomb, side, econ_bucket, map)
        2. ``cells_no_econ`` — drop econ_bucket: (numerical_diff, bomb, side, map)
        3. ``cells_no_map``  — drop map_name:    (numerical_diff, bomb, side)
        4. ``cells_minimal`` — drop side:        (numerical_diff, bomb)
        5. ``side_baseline`` — per-side default: {"atk": 0.5, "def": 0.5}
        6. ``_PHASE_1_FLAT_CELL_VALUE`` — defensive ultimate fallback (0.5)
    """

    cells_full: dict[tuple[int, bool, str, str, str], _Cell] = field(
        default_factory=dict
    )
    cells_no_econ: dict[tuple[int, bool, str, str], _Cell] = field(
        default_factory=dict
    )
    cells_no_map: dict[tuple[int, bool, str], _Cell] = field(default_factory=dict)
    cells_minimal: dict[tuple[int, bool], _Cell] = field(default_factory=dict)
    side_baseline: dict[str, float] = field(
        default_factory=lambda: {"atk": 0.5, "def": 0.5}
    )

    def lookup(
        self,
        numerical_diff: int,
        bomb_planted: bool,
        side: str,
        econ_bucket: str,
        map_name: str,
    ) -> float:
        """P(team A wins THIS round | mid-round context).

        Args:
            numerical_diff: Players-alive differential (A_alive - B_alive).
                Positive = A advantage; range typically [-4, 4].
            bomb_planted: True after spike plant on attacker side.
            side: 'atk' or 'def' — team A's side this half.
            econ_bucket: One of {'full', 'semi-buy', 'semi-eco', 'eco'} per
                Phase 0's CON-economy-buckets.
            map_name: Map this round is being played on.

        Returns:
            ``_PHASE_1_FLAT_CELL_VALUE = 0.5`` in Phase 1 (D-06). Phase 2
            replaces the body with the fallback-chain walk; the SIGNATURE and
            return type contract remain unchanged.
        """
        # Phase 1: short-circuit. Phase 2 will replace this single return with
        # the chain walk described in the class docstring. The dict fields are
        # already in place to be populated; this is the seam (D-07).
        return _PHASE_1_FLAT_CELL_VALUE
