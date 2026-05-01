"""RoundConclusionLookup.to_json -> from_json identity round-trip.

D-15: serialized form must reconstruct the exact same lookup.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.pricing.round_conclusion import RoundConclusionLookup, _Cell


def test_roundtrip_empty_lookup(tmp_path: Path) -> None:
    """Default-constructed lookup serializes and reloads identically."""
    a = RoundConclusionLookup()
    out = tmp_path / "rc.json"
    a.to_json(out)
    b = RoundConclusionLookup.from_json(out)
    assert a.cells_full == b.cells_full == {}
    assert a.cells_no_econ == b.cells_no_econ == {}
    assert a.cells_no_map == b.cells_no_map == {}
    assert a.cells_minimal == b.cells_minimal == {}
    assert a.side_baseline == b.side_baseline == {"atk": 0.5, "def": 0.5}


def test_roundtrip_populated_lookup(tmp_path: Path) -> None:
    """Populated cells round-trip identity (modulo dataclass __eq__)."""
    a = RoundConclusionLookup()
    a.side_baseline["atk"] = 0.46
    a.side_baseline["def"] = 0.54
    a.cells_minimal[(0, False)] = _Cell(n=42, p_hat=0.51, parent_p=0.50)
    a.cells_minimal[(2, True)] = _Cell(n=15, p_hat=0.63, parent_p=0.50)
    a.cells_no_map[(0, False, "atk")] = _Cell(n=20, p_hat=0.49, parent_p=0.51)
    a.cells_no_econ[(0, False, "atk", "Lotus")] = _Cell(
        n=12, p_hat=0.55, parent_p=0.49
    )
    a.cells_full[(0, False, "atk", "full", "Lotus")] = _Cell(
        n=8, p_hat=0.60, parent_p=0.55
    )

    out = tmp_path / "rc.json"
    a.to_json(out)
    b = RoundConclusionLookup.from_json(out)

    assert b.side_baseline == a.side_baseline
    assert b.cells_minimal == a.cells_minimal
    assert b.cells_no_map == a.cells_no_map
    assert b.cells_no_econ == a.cells_no_econ
    assert b.cells_full == a.cells_full


def test_from_json_raises_filenotfound_on_missing(tmp_path: Path) -> None:
    """Phase 4 must distinguish 'no JSON file' from 'empty JSON' (Path C vs error)."""
    with pytest.raises(FileNotFoundError):
        RoundConclusionLookup.from_json(tmp_path / "does-not-exist.json")


def test_serialized_cells_carry_n_p_hat_parent_p_not_shrunk(tmp_path: Path) -> None:
    """Pitfall 5: never serialize the precomputed shrunk() float."""
    a = RoundConclusionLookup()
    a.cells_full[(0, True, "atk", "full", "Lotus")] = _Cell(
        n=42, p_hat=0.61, parent_p=0.55
    )
    out = tmp_path / "rc.json"
    a.to_json(out)
    payload = json.loads(out.read_text(encoding="utf-8"))
    cell_serialized = payload["cells_full"]["0|true|atk|full|Lotus"]
    assert cell_serialized == {"n": 42, "p_hat": 0.61, "parent_p": 0.55}
