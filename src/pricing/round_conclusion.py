"""Hierarchical round-conclusion lookup — v2 surface (Phase 3 / D-04 / D-06 / D-10).

The v1 5-tier hierarchy keyed on
``(numerical_diff, bomb_planted, side, econ_bucket, map)`` is REMOVED in this
file. Per ``CLAUDE.md`` "Economy buckets — DEPRECATED in v2" and CONTEXT.md
D-04, the v2 surface keys cells on
``(attackers_alive, defenders_alive, time_bucket, side, map)`` and exposes two
distinct callable methods:

  - ``between_round_p(side, map_name, round_idx) -> float`` — between-round
    pricing path; returns the per-side baseline directly (no walk). Reserved
    arguments ``map_name`` / ``round_idx`` will be consulted by future
    per-map / per-round-idx baselines (Phase 5+); currently unused.
  - ``post_plant_p(att, def_, time_bucket, side, map_name) -> float`` —
    post-plant pricing path; walks the 5-tier fallback chain
    ``cells_full → cells_no_time → cells_no_map → cells_minimal → side_baseline``.

The Bayesian shrinkage formula on ``_Cell`` is preserved verbatim from
``reference/theo_engine.py:100`` per D-09 / DEC-013:
    shrunk = (n * p_hat + SHRINK_PRIOR * parent_p) / (n + SHRINK_PRIOR)

JSON schema (D-06): ``models/round_conclusion.json`` carries
``"schema_version": 2`` at the top level. ``from_json`` HARD-FAILS on any
other ``schema_version`` (raises ``ValueError``) — the v1 file is recoverable
via ``git show HEAD~N:models/round_conclusion.json``.

Sources
-------
- 03-CONTEXT.md D-04 (two methods + two Protocols), D-06 (schema_version=2),
  D-10 (5s post-plant time buckets), D-14 (45s post-plant timer)
- ``CLAUDE.md`` "Economy buckets — DEPRECATED in v2"
- ``prd.md`` §5.3 (two-path round-conclusion)
- ``reference/theo_engine.py:84-102`` (shrinkage source — preserved)

v1 -> v2 surface delta
----------------------
DELETED:
- ``RoundConclusionFn`` Protocol (v1 callable shape).
- ``RoundConclusionLookup.lookup`` method (v1 5-arg signature).
- ``cells_no_econ`` field + the (numerical_diff, bomb, side, econ, map) cell key.
- ``_PHASE_1_FLAT_CELL_VALUE`` defensive constant — replaced by the
  ``side_baseline.get(side, 0.5)`` default in the new methods.
- v1 key (de)serializers ``_format_key_*`` / ``_parse_key_*`` (replaced; see below).

ADDED:
- ``BetweenRoundFn`` Protocol — call shape (side, map_name, round_idx) -> float.
- ``PostPlantFn`` Protocol — call shape (att, def_, time_bucket, side, map_name) -> float.
- ``RoundConclusionLookup.between_round_p`` instance method.
- ``RoundConclusionLookup.post_plant_p`` instance method.
- ``cells_no_time`` field — drops time_bucket from the v2 cells_full key.
- ``_SCHEMA_VERSION_V2: Final[int] = 2`` module constant (top-level JSON gate).
- New v2 key (de)serializers ``_format_key_*`` / ``_parse_key_*`` taking
  integer ``att``/``def_`` and integer ``time_bucket``.

Why frozen=True with mutable dict fields
----------------------------------------
``@dataclass(frozen=True)`` blocks reassignment of the field reference, NOT
mutation of the dict object the field points to. The calibrator populates cells
via ``lookup_obj.cells_full[key] = _Cell(...)``, which works on frozen instances.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, Protocol, TypedDict

from src.config.constants import SHRINK_PRIOR

# --------------------------------------------------------------------------- #
# 1. JSON schema gate                                                         #
# --------------------------------------------------------------------------- #


_SCHEMA_VERSION_V2: Final[int] = 2
"""v2 ``schema_version`` value; ``from_json`` HARD-FAILS on any other value.

Source: 03-CONTEXT.md D-06. Atomic-replace migration from v1 (no
``schema_version`` field) to v2 (``schema_version: 2``). Forensic recovery
of the v1 file via ``git show HEAD~N:models/round_conclusion.json``.
"""


# --------------------------------------------------------------------------- #
# 2. Bayesian-shrinkage cell                                                  #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class _Cell:
    """A single calibrated cell — unchanged from v1.

    v2 keys these cells on ``(att, def_, time_bucket, side, map)`` (cells_full)
    or weaker projections (cells_no_time / cells_no_map / cells_minimal). The
    cell payload itself is unchanged: ``(n, p_hat, parent_p)`` with the
    Bayesian-shrunk estimate computed by ``shrunk()``.

    Attributes
    ----------
    n: Observed sample size in this cell (rounds matching the cell's keys).
    p_hat: Observed P(attacking team holds for the round | cell context).
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
# 3. JSON schema TypedDicts (D-06)                                            #
# --------------------------------------------------------------------------- #


class _CellJson(TypedDict):
    """Serialized form of a `_Cell` (unchanged from v1).

    NEVER serializes the precomputed ``shrunk()`` float — only the raw
    triple. Phase 5 calibration loops re-tune ``SHRINK_PRIOR`` and must
    recover ``n`` and ``p_hat`` from disk.
    """

    n: int
    p_hat: float
    parent_p: float


class _RoundConclusionJsonV2(TypedDict):
    """Top-level shape of the v2 ``models/round_conclusion.json`` (D-06)."""

    schema_version: int
    side_baseline: dict[str, float]
    cells_minimal: dict[str, _CellJson]
    cells_no_map: dict[str, _CellJson]
    cells_no_time: dict[str, _CellJson]
    cells_full: dict[str, _CellJson]


# --------------------------------------------------------------------------- #
# 4. v2 tuple-key (de)serializers                                             #
# --------------------------------------------------------------------------- #
#                                                                             #
# v2 keys (D-04):                                                             #
#   cells_minimal: (att, def_)                                                #
#   cells_no_map:  (att, def_, side)                                          #
#   cells_no_time: (att, def_, side, map)                                     #
#   cells_full:    (att, def_, time_bucket, side, map)                        #
#                                                                             #
# Pipe-separated string form preserved from v1 for grep-ability.              #


def _format_key_2(key: tuple[int, int]) -> str:
    return f"{key[0]}|{key[1]}"


def _format_key_3(key: tuple[int, int, str]) -> str:
    return f"{key[0]}|{key[1]}|{key[2]}"


def _format_key_4(key: tuple[int, int, str, str]) -> str:
    return f"{key[0]}|{key[1]}|{key[2]}|{key[3]}"


def _format_key_5(key: tuple[int, int, int, str, str]) -> str:
    return f"{key[0]}|{key[1]}|{key[2]}|{key[3]}|{key[4]}"


def _parse_key_2(s: str) -> tuple[int, int]:
    att, def_ = s.split("|", 1)
    return int(att), int(def_)


def _parse_key_3(s: str) -> tuple[int, int, str]:
    att, def_, side = s.split("|", 2)
    return int(att), int(def_), side


def _parse_key_4(s: str) -> tuple[int, int, str, str]:
    att, def_, side, mp = s.split("|", 3)
    return int(att), int(def_), side, mp


def _parse_key_5(s: str) -> tuple[int, int, int, str, str]:
    att, def_, tb, side, mp = s.split("|", 4)
    return int(att), int(def_), int(tb), side, mp


# --------------------------------------------------------------------------- #
# 5. Public callable Protocols (D-04)                                         #
# --------------------------------------------------------------------------- #


class BetweenRoundFn(Protocol):
    """v2 between-round callable shape (D-04).

    ``RoundConclusionLookup.between_round_p`` (bound method) satisfies this
    Protocol; test fakes can also satisfy it. Consumed by ``live_theo`` for
    the between-round pricing path.
    """

    def __call__(
        self,
        side: str,
        map_name: str,
        round_idx: int,
    ) -> float: ...


class PostPlantFn(Protocol):
    """v2 post-plant callable shape (D-04).

    ``RoundConclusionLookup.post_plant_p`` (bound method) satisfies this
    Protocol; test fakes can also satisfy it. Consumed by ``live_theo`` for
    the post-plant pricing path (state.bomb_planted=True).
    """

    def __call__(
        self,
        att: int,
        def_: int,
        time_bucket: int,
        side: str,
        map_name: str,
    ) -> float: ...


# --------------------------------------------------------------------------- #
# 6. v2 hierarchical fallback chain                                           #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class RoundConclusionLookup:
    """v2 round-conclusion lookup (D-04 / D-06).

    Two surfaces:
      - ``between_round_p(side, map_name, round_idx)`` — direct side baseline.
      - ``post_plant_p(att, def_, time_bucket, side, map_name)`` — 5-tier walk.

    Fallback chain order for ``post_plant_p`` (D-04):
        1. ``cells_full``    keyed on (att, def_, time_bucket, side, map)
        2. ``cells_no_time`` keyed on (att, def_, side, map)
        3. ``cells_no_map``  keyed on (att, def_, side)
        4. ``cells_minimal`` keyed on (att, def_)
        5. ``side_baseline`` per-side default {"atk": 0.5, "def": 0.5}

    Field order: ``side_baseline`` is FIRST so callers can construct
    ``RoundConclusionLookup({"atk": 0.6, "def": 0.4})`` positionally.
    """

    side_baseline: dict[str, float] = field(
        default_factory=lambda: {"atk": 0.5, "def": 0.5}
    )
    cells_minimal: dict[tuple[int, int], _Cell] = field(default_factory=dict)
    cells_no_map: dict[tuple[int, int, str], _Cell] = field(default_factory=dict)
    cells_no_time: dict[tuple[int, int, str, str], _Cell] = field(
        default_factory=dict
    )
    cells_full: dict[tuple[int, int, int, str, str], _Cell] = field(
        default_factory=dict
    )

    def between_round_p(
        self,
        side: str,
        map_name: str,
        round_idx: int,
    ) -> float:
        """Between-round pricing surface — returns side baseline directly (D-04).

        ``map_name`` and ``round_idx`` are reserved for future per-map /
        per-round-idx baselines (Phase 5+) and currently unused. Defaults to
        0.5 for unknown sides — keeps the call total even on a degenerate
        ``side_baseline`` dict.
        """
        del map_name, round_idx  # reserved for future baselines
        return self.side_baseline.get(side, 0.5)

    def post_plant_p(
        self,
        att: int,
        def_: int,
        time_bucket: int,
        side: str,
        map_name: str,
    ) -> float:
        """Post-plant pricing surface — 5-tier hierarchical walk (D-04).

        Walks ``cells_full → cells_no_time → cells_no_map → cells_minimal →
        side_baseline``. Each cell hit returns the Bayesian-shrunk estimate
        via ``_Cell.shrunk()``. Output is unclipped — Phase 4's ``live_theo``
        applies the ``[CONVICTION_CLIP_LOW, CONVICTION_CLIP_HIGH]`` band;
        clipping here would double-clip and silently bias the math (CRule 6).
        """
        if (cell := self.cells_full.get((att, def_, time_bucket, side, map_name))) is not None:
            return cell.shrunk()
        if (cell := self.cells_no_time.get((att, def_, side, map_name))) is not None:
            return cell.shrunk()
        if (cell := self.cells_no_map.get((att, def_, side))) is not None:
            return cell.shrunk()
        if (cell := self.cells_minimal.get((att, def_))) is not None:
            return cell.shrunk()
        return self.side_baseline.get(side, 0.5)

    @classmethod
    def from_json(cls, path: str | Path) -> RoundConclusionLookup:
        """Load a calibrated v2 lookup from disk (D-06).

        HARD-FAILS on ``schema_version != 2`` (raises ``ValueError``) — v1
        file is recoverable via git history.

        Raises
        ------
        FileNotFoundError: if the JSON file does not exist (do NOT silently
            return empty — callers must distinguish "calibrated absent" from
            "calibrated empty").
        ValueError: if ``schema_version`` is missing or not equal to
            ``_SCHEMA_VERSION_V2``.
        """
        text = Path(path).read_text(encoding="utf-8")
        data: _RoundConclusionJsonV2 = json.loads(text)
        sv = data.get("schema_version")
        if sv != _SCHEMA_VERSION_V2:
            raise ValueError(
                f"Expected schema_version={_SCHEMA_VERSION_V2}, got {sv!r}"
            )
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
        for k4, v4 in data.get("cells_no_time", {}).items():
            obj.cells_no_time[_parse_key_4(k4)] = _Cell(
                n=v4["n"], p_hat=v4["p_hat"], parent_p=v4["parent_p"]
            )
        for k5, v5 in data.get("cells_full", {}).items():
            obj.cells_full[_parse_key_5(k5)] = _Cell(
                n=v5["n"], p_hat=v5["p_hat"], parent_p=v5["parent_p"]
            )
        return obj

    def to_json(self, path: str | Path) -> None:
        """Persist this lookup to JSON in the v2 D-06 format.

        Pitfall 5 (preserved from v1): serializes raw (n, p_hat, parent_p) —
        never the precomputed shrunk() value. Phase 5 re-calibration must be
        able to recover the input triples without rebuilding the whole dataset.
        """
        out: _RoundConclusionJsonV2 = {
            "schema_version": _SCHEMA_VERSION_V2,
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
            "cells_no_time": {
                _format_key_4(k): {
                    "n": v.n,
                    "p_hat": v.p_hat,
                    "parent_p": v.parent_p,
                }
                for k, v in self.cells_no_time.items()
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
