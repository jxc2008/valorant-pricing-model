"""Hierarchical mid-round-conclusion lookup (Phase 1 skeleton + Phase 2 calibration).

Phase 1 shipped the SHAPE per DEC-007 (5-level fallback chain) with every cell
returning ``_PHASE_1_FLAT_CELL_VALUE = 0.5`` regardless of input (D-06). Phase 2
adds the calibrated walk: ``lookup`` body is rewritten to traverse the chain and
return shrunk cell estimates, while two additive methods (``from_json`` /
``to_json``) round-trip the calibrated lookup through ``models/round_conclusion.json``.

The Bayesian shrinkage formula on ``_Cell`` is salvaged verbatim from
``reference/theo_engine.py:100`` per D-09 / DEC-013:
    shrunk = (n * p_hat + SHRINK_PRIOR * parent_p) / (n + SHRINK_PRIOR)

Sources
-------
- DEC-007 / roadmap.md §1.5 (hierarchical fallback chain)
- D-06, D-07, D-09, D-12, D-13, D-14, D-15 (CONTEXT.md)
- prd.md §5.3 (mid-round pricing design)
- 01-RESEARCH.md §6 (signature + shrinkage scaffold)
- 02-RESEARCH.md §"Pattern 3: Bottom-up shrinkage walk" / §from_json
- reference/theo_engine.py:84-102 (shrinkage source)

Phase 1 -> Phase 2 surface delta
--------------------------------
PRESERVED (frozen-surface contract):
- ``_Cell`` (frozen dataclass + ``shrunk()`` method) — unchanged.
- ``RoundConclusionFn`` Protocol — unchanged.
- ``RoundConclusionLookup`` dataclass field declarations — unchanged.
- ``RoundConclusionLookup.lookup`` SIGNATURE — unchanged.
- ``_PHASE_1_FLAT_CELL_VALUE`` — kept as defensive ultimate fallback when
  ``side_baseline`` has been mutated to drop a side.

CHANGED:
- ``RoundConclusionLookup.lookup`` BODY — rewritten from flat-0.5 to the 5-tier
  fallback chain walk per CON-round-conclusion-fallback-chain.

ADDED (additive, Phase 1 callers untouched):
- ``RoundConclusionLookup.from_json`` classmethod (D-15).
- ``RoundConclusionLookup.to_json`` instance method (D-15).
- ``_CellJson`` and ``_RoundConclusionJson`` TypedDicts for the JSON schema.
- Private key (de)serializer helpers ``_format_key_*`` / ``_parse_key_*``.

Why frozen=True with mutable dict fields
----------------------------------------
``@dataclass(frozen=True)`` blocks reassignment of the field reference, NOT
mutation of the dict object the field points to. The calibrator populates cells
via ``lookup_obj.cells_full[key] = _Cell(...)``, which works on frozen instances.
This matches the established Python idiom (verified by 01-PATTERNS.md S3).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, Protocol, TypedDict

from src.config.constants import SHRINK_PRIOR

# --------------------------------------------------------------------------- #
# 1. Phase 1 flat cell constant                                               #
# --------------------------------------------------------------------------- #


_PHASE_1_FLAT_CELL_VALUE: Final[float] = 0.5
"""Defensive ultimate fallback at the bottom of the chain.

Source: D-06 / CONTEXT.md — the flat-0.5 placeholder is Path-C-compatible. After
Phase 2 calibration, this constant is the LAST-RESORT return value when even
``side_baseline`` has been mutated to drop a side (a degenerate state that
should not arise in production but must not crash the lookup).
"""


# --------------------------------------------------------------------------- #
# 2. Bayesian-shrinkage cell                                                  #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class _Cell:
    """A single (numerical_diff, bomb_planted, side, econ_bucket, map) cell.

    Phase 1: only ``shrunk()`` was exercised by the formula test — no instances
    were stored in the lookup dicts (those were empty in Phase 1).

    Phase 2 populates instances of this class into the cells_* dicts on
    RoundConclusionLookup; ``lookup`` walks the chain and returns ``shrunk()``
    of the first matching cell.

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
# 2.5 JSON schema TypedDicts (Phase 2 additive — for from_json/to_json)       #
# --------------------------------------------------------------------------- #


class _CellJson(TypedDict):
    """Serialized form of a `_Cell` (D-15 / Pitfall 5).

    NEVER serializes the precomputed ``shrunk()`` float — only the raw
    triple. Phase 5 calibration loops re-tune ``SHRINK_PRIOR`` and must
    recover ``n`` and ``p_hat`` from disk.
    """

    n: int
    p_hat: float
    parent_p: float


class _RoundConclusionJson(TypedDict):
    """Top-level shape of `models/round_conclusion.json` (D-15)."""

    side_baseline: dict[str, float]
    cells_minimal: dict[str, _CellJson]
    cells_no_map: dict[str, _CellJson]
    cells_no_econ: dict[str, _CellJson]
    cells_full: dict[str, _CellJson]


# --------------------------------------------------------------------------- #
# 2.6 Tuple-key (de)serializers for JSON                                      #
# --------------------------------------------------------------------------- #


def _format_key_2(key: tuple[int, bool]) -> str:
    return f"{key[0]}|{str(key[1]).lower()}"


def _format_key_3(key: tuple[int, bool, str]) -> str:
    return f"{key[0]}|{str(key[1]).lower()}|{key[2]}"


def _format_key_4(key: tuple[int, bool, str, str]) -> str:
    return f"{key[0]}|{str(key[1]).lower()}|{key[2]}|{key[3]}"


def _format_key_5(key: tuple[int, bool, str, str, str]) -> str:
    return f"{key[0]}|{str(key[1]).lower()}|{key[2]}|{key[3]}|{key[4]}"


def _parse_key_2(s: str) -> tuple[int, bool]:
    nd, bp = s.split("|", 1)
    return int(nd), bp == "true"


def _parse_key_3(s: str) -> tuple[int, bool, str]:
    nd, bp, side = s.split("|", 2)
    return int(nd), bp == "true", side


def _parse_key_4(s: str) -> tuple[int, bool, str, str]:
    nd, bp, side, mp = s.split("|", 3)
    return int(nd), bp == "true", side, mp


def _parse_key_5(s: str) -> tuple[int, bool, str, str, str]:
    nd, bp, side, econ, mp = s.split("|", 4)
    return int(nd), bp == "true", side, econ, mp


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
# 4. Hierarchical fallback chain                                              #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class RoundConclusionLookup:
    """5-tier hierarchical fallback-chain lookup (DEC-007 / roadmap 1.5).

    Phase 1 returned ``_PHASE_1_FLAT_CELL_VALUE`` for all inputs (D-06). Phase 2
    rewrites ``lookup`` to walk the chain; when no cell matches at any level,
    the lookup falls back to ``side_baseline[side]`` (default 0.5/0.5 — bit-
    identical to the Phase 1 stub, preserving Path-C compatibility per D-12).

    Fallback chain order (D-07, walked by ``lookup``):
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

        Phase 2 (D-07 / D-13 / DEC-007): walk the 5-tier fallback chain.
        - cells_full       (numerical_diff, bomb, side, econ_bucket, map)
        - cells_no_econ    (numerical_diff, bomb, side, map)
        - cells_no_map     (numerical_diff, bomb, side)
        - cells_minimal    (numerical_diff, bomb)
        - side_baseline    side -> float
        - _PHASE_1_FLAT_CELL_VALUE 0.5 (defensive ultimate fallback)

        Each cell hit returns the Bayesian-shrunk estimate via ``_Cell.shrunk()``.
        Output is unclipped — Phase 4's ``live_theo`` applies the
        ``[CONVICTION_CLIP_LOW, CONVICTION_CLIP_HIGH]`` band; clipping here would
        double-clip and silently bias the math (CRule 6).

        Args / Returns: as Phase 1 (signature unchanged per CONTEXT.md frozen
        public surface). Path-C compatibility: an empty lookup (no cells, default
        side_baseline) returns 0.5 for both atk and def — bit-identical to the
        Phase 1 stub, preserving Phase 4's optional-injection contract.
        """
        cell_full = self.cells_full.get(
            (numerical_diff, bomb_planted, side, econ_bucket, map_name)
        )
        if cell_full is not None:
            return cell_full.shrunk()
        cell_no_econ = self.cells_no_econ.get(
            (numerical_diff, bomb_planted, side, map_name)
        )
        if cell_no_econ is not None:
            return cell_no_econ.shrunk()
        cell_no_map = self.cells_no_map.get((numerical_diff, bomb_planted, side))
        if cell_no_map is not None:
            return cell_no_map.shrunk()
        cell_minimal = self.cells_minimal.get((numerical_diff, bomb_planted))
        if cell_minimal is not None:
            return cell_minimal.shrunk()
        return self.side_baseline.get(side, _PHASE_1_FLAT_CELL_VALUE)

    @classmethod
    def from_json(cls, path: str | Path) -> RoundConclusionLookup:
        """Load a calibrated lookup from `models/round_conclusion.json` (D-15).

        Phase 4's engine init calls this; if path doesn't exist, the caller is
        expected to fall back to ``cls()`` (empty lookup, returns side_baseline /
        flat 0.5 — Path-C contract D-12).

        Raises:
            FileNotFoundError: if the JSON file does not exist (do NOT silently
                return empty — callers must distinguish "calibrated absent" from
                "calibrated empty").

        Source: D-15 / 02-RESEARCH.md §from_json.
        """
        text = Path(path).read_text(encoding="utf-8")
        data: _RoundConclusionJson = json.loads(text)
        obj = cls()  # frozen wrapper, mutable dict fields
        obj.side_baseline.update(data.get("side_baseline", {}))
        for k2, v2 in data.get("cells_minimal", {}).items():
            obj.cells_minimal[_parse_key_2(k2)] = _Cell(
                n=v2["n"], p_hat=v2["p_hat"], parent_p=v2["parent_p"]
            )
        for k3, v3 in data.get("cells_no_map", {}).items():
            obj.cells_no_map[_parse_key_3(k3)] = _Cell(
                n=v3["n"], p_hat=v3["p_hat"], parent_p=v3["parent_p"]
            )
        for k4, v4 in data.get("cells_no_econ", {}).items():
            obj.cells_no_econ[_parse_key_4(k4)] = _Cell(
                n=v4["n"], p_hat=v4["p_hat"], parent_p=v4["parent_p"]
            )
        for k5, v5 in data.get("cells_full", {}).items():
            obj.cells_full[_parse_key_5(k5)] = _Cell(
                n=v5["n"], p_hat=v5["p_hat"], parent_p=v5["parent_p"]
            )
        return obj

    def to_json(self, path: str | Path) -> None:
        """Persist this lookup to JSON in the D-15 format.

        Pitfall 5: serializes raw (n, p_hat, parent_p) — never the precomputed
        shrunk() value. Phase 5 re-calibration must be able to recover the input
        triples without rebuilding the whole dataset.
        """
        out: _RoundConclusionJson = {
            "side_baseline": dict(self.side_baseline),
            "cells_minimal": {
                _format_key_2(k): {
                    "n": v.n,
                    "p_hat": v.p_hat,
                    "parent_p": v.parent_p,
                }
                for k, v in self.cells_minimal.items()
            },
            "cells_no_map": {
                _format_key_3(k): {
                    "n": v.n,
                    "p_hat": v.p_hat,
                    "parent_p": v.parent_p,
                }
                for k, v in self.cells_no_map.items()
            },
            "cells_no_econ": {
                _format_key_4(k): {
                    "n": v.n,
                    "p_hat": v.p_hat,
                    "parent_p": v.parent_p,
                }
                for k, v in self.cells_no_econ.items()
            },
            "cells_full": {
                _format_key_5(k): {
                    "n": v.n,
                    "p_hat": v.p_hat,
                    "parent_p": v.parent_p,
                }
                for k, v in self.cells_full.items()
            },
        }
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(
            json.dumps(out, indent=2, sort_keys=True), encoding="utf-8"
        )
